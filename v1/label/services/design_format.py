"""
시안 파일에서 **서식**을 읽는다 — 글자 크기·굵기.

지금까지 활자 크기 검사(`validation_service.check_font_size`)는
`MyLabel.prv_font_size` 하나를 봤다. 그건 **우리 미리보기 표의 설정값**이라,
우리가 만든 표에만 걸리고 **받은 시안에는 못 건다.** 그런데 표시기준의 활자
규정은 인쇄물에 대한 것이다.

밖에서 본 시스템이 이 자리에서 졌다. 디자인시안이 PPTX 인데 텍스트만 뽑아서
(추출 결과에 "이미지 0장" 이라고 적혀 있다) 활자 크기·굵기·바탕색을 봐야 하는
항목이 전부 판정 불가가 됐다 — 알레르기 표시가 "바탕색·박스 구분을 확정하지
못함" 으로 부적합이 났다. **그런데 PPTX 는 그 정보를 갖고 있다.** 스스로 버린
것이다.

읽는 법은 파일마다 다르지만 **새 의존성은 쓰지 않는다.**

    PDF    PyMuPDF — 이미 requirements 에 있다(판독이 쓴다)
    PPTX   zip 안의 XML 을 표준 라이브러리로 연다. a:rPr 의 sz 가 1/100 pt 다

읽지 못하는 형식(이미지·HWP 등)은 **빈 목록**을 돌려준다. 못 읽은 것과 글자가
없는 것을 가르는 일은 부르는 쪽이 한다(`read_runs` 는 예외를 올린다).
"""
import logging
import os
import re
import zipfile
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

# a:rPr 의 sz 는 1/100 포인트다. 1400 이면 14 pt.
_PPTX_NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
_PPTX_SLIDE = re.compile(r'^ppt/slides/slide\d+\.xml$')

# PyMuPDF 의 span flags 에서 굵기를 나타내는 비트.
_PDF_BOLD_FLAG = 1 << 4

SUPPORTED = ('.pdf', '.pptx')


def is_supported(path: str) -> bool:
    return os.path.splitext(path or '')[1].lower() in SUPPORTED


def _pptx_runs(path: str) -> list[dict]:
    """
    PPTX 의 글자 조각. 슬라이드마다 a:r(런) 단위로 크기와 굵기를 읽는다.

    크기가 런에 안 적혀 있으면 문단(a:pPr)이나 마스터에서 물려받는데, 마스터
    까지 따라가면 파일마다 얽힌 관계를 다 풀어야 한다. **물려받은 것은 크기를
    None 으로 둔다** — 모르는 것을 0 으로 적으면 없는 위반을 만든다.
    """
    runs = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if _PPTX_SLIDE.match(n)):
            slide = int(re.search(r'(\d+)', name.rsplit('/', 1)[-1]).group(1))
            root = ElementTree.fromstring(z.read(name))
            for run in root.iter('{%s}r' % _PPTX_NS['a']):
                text = ''.join(t.text or '' for t in run.iter('{%s}t' % _PPTX_NS['a']))
                if not text.strip():
                    continue
                pr = run.find('a:rPr', _PPTX_NS)
                size = bold = None
                if pr is not None:
                    raw = pr.get('sz')
                    if raw and raw.isdigit():
                        size = int(raw) / 100.0
                    if pr.get('b') is not None:
                        bold = pr.get('b') in ('1', 'true')
                runs.append({'text': text, 'size_pt': size, 'bold': bold,
                             'page': slide})
    return runs


def _pdf_runs(path: str) -> list[dict]:
    """PDF 의 글자 조각. PyMuPDF 가 span 마다 크기와 굵기 플래그를 준다."""
    import pymupdf

    runs = []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            for block in page.get_text('dict').get('blocks', ()):
                for line in block.get('lines', ()):
                    for span in line.get('spans', ()):
                        text = span.get('text') or ''
                        if not text.strip():
                            continue
                        runs.append({
                            'text': text,
                            'size_pt': round(float(span.get('size') or 0), 2) or None,
                            'bold': bool(int(span.get('flags') or 0) & _PDF_BOLD_FLAG),
                            'page': number,
                        })
    return runs


def read_runs(path: str) -> list[dict]:
    """
    시안에서 글자 조각을 읽는다.

        [{'text': '프랑스 붕어빵', 'size_pt': 22.0, 'bold': True, 'page': 1}, …]

    **예외를 삼키지 않는다.** 읽지 못했다는 것과 글자가 없다는 것은 다른 말이고,
    조용히 빈 목록을 돌려주면 부르는 쪽이 "글자가 없다" 로 읽는다.
    """
    suffix = os.path.splitext(path or '')[1].lower()
    if suffix == '.pptx':
        return _pptx_runs(path)
    if suffix == '.pdf':
        return _pdf_runs(path)
    raise ValueError('서식을 읽을 수 없는 형식입니다: %s' % (suffix or path))


def smallest(runs, floor: float = 1.0):
    """
    가장 작은 글자. 크기를 모르는 조각(물려받은 것)은 세지 않는다.

    floor 보다 작은 값은 버린다 — 0.1 pt 짜리 조각은 인쇄되는 글자가 아니라
    도장·눈금 같은 것이고, 그것으로 라벨을 탓하면 고칠 데가 없다.
    """
    sized = [r for r in runs if r.get('size_pt') and r['size_pt'] >= floor]
    if not sized:
        return None
    return min(sized, key=lambda r: r['size_pt'])
