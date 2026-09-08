"""
올린 파일을 **판독이 읽을 수 있는 그림**으로 바꾼다.

판독 입구(사진으로 불러오기 · 디자인 시안과 대조)는 지금까지 이미지만 받았다.
그런데 실제로 오가는 것은 PDF 가 많다 — 인쇄용 도안도 품목제조보고서도
문서 프로그램에서 뽑은 PDF 다. 사람이 그것을 캡처해서 올리고 있었다.

**쪽마다 돈이 나간다.** 비전 모델은 이미지를 토큰으로 환산해 값을 매기고 그
배수가 크다(`OCR_UPGRADE_PLAN §11` — `detail: high` 한 장이 2만 토큰대).
그래서 두 가지를 지킨다.

  1. 기본 두 쪽만 본다. 표시사항은 대개 첫 쪽에 있다
  2. **글자가 든 PDF 는 그 글자를 함께 돌려준다.** 판독이 지어낸 값을
     그 원문과 대조할 수 있고, 그림으로 되돌려 다시 읽힐 이유가 없다

PPTX·워드는 여기서 다루지 않는다. 글자가 이미 들어 있어 판독을 부를 이유가
없고, 부르면 서식을 잃는다 — `design_format` 이 글자와 서식을 함께 읽는다.
"""
import io
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 2

# 판독에 넣을 그림의 해상도. 150 이면 10 pt 글자가 20 px 남짓이라 읽히고,
# 그 이상은 토큰만 늘어난다.
RENDER_DPI = 150

IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
PDF_SUFFIXES = ('.pdf',)

# 글자가 이만큼도 안 나오면 스캔본이다. 몇 글자를 "원문" 이라고 넘기면
# 판독이 그 조각을 믿고 나머지를 지어낼 수 있다
# (vision_service.PDF_TEXT_MIN_CHARS 와 같은 뜻).
TEXT_LAYER_MIN_CHARS = 30


class Page:
    """판독에 넣을 한 장. 이름과 바이트만 있으면 된다."""

    def __init__(self, name, data, content_type='image/jpeg'):
        self.name = name
        self._data = data
        self.content_type = content_type
        self.size = len(data)

    def read(self):
        return self._data

    def seek(self, *args):
        return 0


def suffix_of(upload) -> str:
    return os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()


def is_image(upload) -> bool:
    content_type = (getattr(upload, 'content_type', '') or '').lower()
    return content_type.startswith('image/') or suffix_of(upload) in IMAGE_SUFFIXES


def is_pdf(upload) -> bool:
    content_type = (getattr(upload, 'content_type', '') or '').lower()
    return content_type == 'application/pdf' or suffix_of(upload) in PDF_SUFFIXES


def accepts(upload) -> bool:
    return is_image(upload) or is_pdf(upload)


def _pdf_pages(data: bytes, max_pages: int):
    """PDF 를 쪽마다 JPEG 로. (그림 목록, 글자, 전체 쪽수)."""
    import pymupdf

    images, texts, total = [], [], 0
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        total = len(doc)
        zoom = RENDER_DPI / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        for number in range(min(max_pages, total)):
            page = doc[number]
            texts.append((page.get_text() or '').strip())
            images.append(Page('page%d.jpg' % (number + 1),
                               page.get_pixmap(matrix=matrix).tobytes('jpeg')))
    text = '\n\n'.join(t for t in texts if t).strip()
    return images, (text if len(text) >= TEXT_LAYER_MIN_CHARS else ''), total


def to_pages(upload, max_pages: int = DEFAULT_MAX_PAGES) -> dict:
    """
    올린 파일 하나를 판독이 읽을 그림들로.

        {'pages': [Page …], 'text_layer': str, 'total_pages': int,
         'kind': 'image' | 'pdf'}

    `text_layer` 는 PDF 에 글자가 들어 있을 때만 채워진다. 그림으로 되돌려 다시
    읽힌 값이 아니라 **문서가 원래 갖고 있던 글자**라, 판독 결과를 이것과
    대조하면 지어낸 값을 잡을 수 있다.

    읽을 수 없는 형식은 ValueError 를 올린다 — **조용히 빈 목록을 주지 않는다.**
    부르는 쪽이 "글자가 없다" 로 읽으면 안 된다.
    """
    if is_image(upload):
        return {'pages': [upload], 'text_layer': '', 'total_pages': 1,
                'kind': 'image'}
    if not is_pdf(upload):
        raise ValueError('판독할 수 없는 형식입니다: %s'
                         % (suffix_of(upload) or getattr(upload, 'name', '')))

    try:
        upload.seek(0)
    except Exception:
        pass
    data = upload.read()
    try:
        images, text, total = _pdf_pages(data, max_pages)
    except Exception as exc:
        logger.exception('PDF 를 그림으로 바꾸지 못했다 (name=%s)',
                         getattr(upload, 'name', ''))
        raise ValueError('PDF 를 열지 못했습니다.') from exc

    if not images:
        raise ValueError('PDF 에 쪽이 없습니다.')
    return {'pages': images, 'text_layer': text, 'total_pages': total,
            'kind': 'pdf'}


def note(result: dict) -> str:
    """사용자에게 보여 줄 한 줄. 몇 쪽을 봤는지 말해 준다."""
    if result.get('kind') != 'pdf':
        return ''
    read = len(result.get('pages') or ())
    total = result.get('total_pages') or read
    line = 'PDF %d쪽 중 %d쪽을 읽었습니다.' % (total, read)
    if total > read:
        line += ' 나머지 쪽은 보지 않았습니다 — 쪽마다 판독 비용이 듭니다.'
    if result.get('text_layer'):
        line += ' 이 PDF 에는 글자가 들어 있어 판독 결과를 원문과 대조합니다.'
    return line
