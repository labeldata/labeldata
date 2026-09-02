"""
사진에서 **글자 원문만** 뽑는다 (Google Cloud Vision).

여기는 판독이 아니다. 어느 글자가 어느 항목인지는 보지 않고, 사진에 적힌
글자를 그대로 받아 온다. 그 원문을 무엇에 쓸지는 다음 단계의 이야기다.

**왜 이걸 들이는가.** 측정이 답을 줬다(OCR_UPGRADE_PLAN.md §12).

    짧고 정형화된 값        100점, 편차 0
    긴 자유 문구            25~52점, 편차 80
    원재료명                86~92점, 괄호가 무너짐

VLM 은 레이아웃 이해(어느 칸이 어느 항목인가)가 탁월하고 **긴 문자열의 축자
전사를 못 한다.** 다음 토큰을 확률로 뽑으니 긴 문장에서 그럴듯한 쪽으로 흐른다.
전통 OCR 은 정확히 반대다 - 글자를 보고 글자를 내므로 지어낼 수가 없고, 대신
어느 칸인지는 모른다. 둘은 상보적이다.

문서함 PDF 는 이미 같은 구조로 돌고 있다(§4 ①). 텍스트 레이어를 뽑아 "글자는
이 원문을 그대로 옮기고, 그림은 어느 값이 어느 항목인지 판단하는 데만 쓰라" 고
지시한다. 사진에는 텍스트 레이어가 없어서 못 했을 뿐이다.

**지금은 1단계다 — 가부를 가른다.** 우리가 다루는 것은 6pt 원형 스티커, 곡면
용기, 작업지시서에 얹힌 도안이다. OCR 이 이걸 못 읽으면 "원문" 이 쓰레기가 되고,
그걸 그대로 옮기라고 하면 쓰레기를 확정한다. 추측이 아니라 §4 ① 에서 이미
겪었다 - 스캔 PDF 가 도장·서명만 벡터로 흘릴 때 그 조각을 원문이라 넘겼더니
모델이 그것을 믿고 나머지를 지어냈다.

그래서 **읽히는지부터 숫자로 잰다.** 정답지가 이미 있으니 그것을 자로 쓴다
(field_recall). 사람이 원문을 눈으로 보고 "읽을 만하네" 하고 판단하면, 이
프로젝트가 그동안 피해 온 "사람마다 다른 잣대" 로 되돌아간다.
"""
import base64
import io
import json
import logging
import re
import unicodedata

from django.conf import settings

logger = logging.getLogger(__name__)

VISION_ENDPOINT = 'https://vision.googleapis.com/v1/images:annotate'

# 글자가 이만큼도 안 나오면 못 읽은 것으로 본다.
#
# PDF 텍스트 레이어에 쓰는 가드와 같은 값이고 같은 이유다
# (vision_service.extract_pdf_text). 도장·서명 몇 글자만 흘러나온 원문을
# "사진에 이렇게 적혀 있다" 고 넘기면, 모델이 그 조각을 믿고 나머지를 지어낸다.
# 없는 원문이 나쁜 원문보다 낫다.
MIN_TEXT_CHARS = 40

# Vision 한 요청의 상한은 20MB 다. 우리 업로드 상한이 10MB 라 보통 걸리지
# 않지만, 걸렸을 때 무슨 일인지 모를 오류를 받느니 줄여서 보낸다.
MAX_IMAGE_BYTES = 18 * 1024 * 1024

# 긴 칸. **가부 판단은 이 칸들로 한다.**
#
# 짧은 칸은 VLM 이 이미 100점이라 OCR 이 도울 여지가 없다. 원문을 들이는 이유는
# 오직 이 세 칸이라, 여기서 안 읽히면 나머지가 아무리 읽혀도 의미가 없다.
LONG_FIELDS = ('rawmtrl_nm', 'cautions', 'additional_info')

# **글자가 아닌 칸.** 채점에서 뺀다.
#
# 분리배출 표시는 도형 안의 재질 코드다. 저장하는 값("비닐류 PP / 띠지:PP")도
# 우리가 정규화한 형태라 인쇄면과 애초에 다르다. OCR 이 도울 수 있는 칸이
# 아니고 도울 필요도 없다 - ocr_apply.map_recycling_mark 가 맡고 있다.
#
# 이걸 "OCR 이 못 읽었다" 로 세면 회수율이 실제보다 낮게 나오고, 그 숫자로
# 방향을 정하게 된다.
NON_TEXT_FIELDS = ('recycling_mark',)

# **여러 문구를 하나로 모아 담는 칸.**
#
# 둘 다 판독 프롬프트가 "그 칸의 내용 전체" 를 이어서 적으라고 지시하는
# 자리다. 기타표시사항은 제품교환장소·고객상담실·신고번호·홈페이지, 주의사항은
# 혼입가능 문구·섭취 주의·보관 주의 - 서로 무관한 문구들이고 라벨에서도
# 여기저기 흩어져 인쇄된다. 사이에 다른 내용이 끼어 있는 게 정상이다.
#
# 그러니 이 두 칸만은 "이어 붙인 문자열이 원문에 연속으로 있는가" 를 물으면
# 안 된다. 조각이 다 있는지를 봐야 한다.
#
# **주의사항을 넣어도 지어냄 검사는 헐거워지지 않는다.** _scatter_pieces 가
# 낱말이 아니라 **문장**으로 가르기 때문이다 - 지어낸 문장은 쓰인 낱말이
# 아무리 흔해도 문장 전체로는 원문에 나오지 않는다. 낱말로 갈랐다면 이
# 칸에는 쓰지 못했을 것이다.
#
# 다른 칸에는 쓰지 않는다. 나머지는 한 덩어리의 값이라 흩어질 일이 없다.
ASSEMBLED_FIELDS = ('cautions', 'additional_info')

# 이 점수 이상이면 "원문에 있다" 로 센다.
FOUND_THRESHOLD = 90


def _api_key() -> str:
    """
    API 키. 있으면 이걸 먼저 쓴다.

    Vision 의 images:annotate 는 API 키로도 부를 수 있고, 서비스 계정 JSON 을
    서버에 두는 것보다 붙이기가 훨씬 쉽다. "API 키를 쓰면 파일이 공개돼 있어야
    한다" 는 제약은 이미지를 **URL 로 가리킬 때**의 이야기다. 우리는 사진을
    base64 로 실어 보내므로 해당되지 않는다.

    대신 키에는 **Cloud Vision API 로만 쓰도록 제한**을 걸어야 한다. 제한 없는
    키가 새면 그 프로젝트의 다른 API 까지 열린다.
    """
    return getattr(settings, 'GOOGLE_VISION_API_KEY', '') or ''


def _access_token() -> str:
    """
    서비스 계정 JSON 으로 Vision 용 액세스 토큰을 받는다.

    API 키가 없을 때만 쓴다. 방식은 FCM 과 같다
    (mobile/services/push_service._get_fcm_access_token). JSON 본문을 그대로
    넣어도 되고 파일 경로를 넣어도 된다.

    전용 설정이 비어 있으면 FCM 것을 쓴다 - 대개 같은 Google Cloud 프로젝트라
    서비스 계정을 하나 더 만들 이유가 없다. 다만 그 계정에 **Vision API 사용
    설정이 켜져 있어야** 한다. 안 켜져 있으면 403 이 오고, 그건 아래에서
    로그로 남는다.
    """
    sa_json = (getattr(settings, 'GOOGLE_VISION_SERVICE_ACCOUNT_JSON', '')
               or getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', ''))
    if not sa_json:
        logger.warning('[OCR 원문] 서비스 계정이 설정돼 있지 않다 '
                       '(GOOGLE_VISION_SERVICE_ACCOUNT_JSON)')
        return ''

    try:
        import google.auth.transport.requests
        from google.oauth2 import service_account

        if sa_json.strip().startswith('{'):
            sa_info = json.loads(sa_json)
        else:
            with open(sa_json, 'r', encoding='utf-8') as fh:
                sa_info = json.load(fh)

        credentials = service_account.Credentials.from_service_account_info(
            sa_info, scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token or ''
    except Exception:
        logger.exception('[OCR 원문] 토큰 발급 실패')
        return ''


def _shrink(image_bytes: bytes) -> bytes:
    """상한을 넘는 사진을 줄인다. 줄이지 못하면 원본 그대로 돌려준다."""
    if len(image_bytes) <= MAX_IMAGE_BYTES:
        return image_bytes
    try:
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((4000, 4000), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        return buf.getvalue()
    except Exception:
        logger.exception('[OCR 원문] 사진 축소 실패 - 원본으로 보낸다')
        return image_bytes


def extract_text(image_bytes: bytes) -> str:
    """
    사진 한 장의 글자 원문. 못 읽으면 빈 문자열.

    DOCUMENT_TEXT_DETECTION 을 쓴다. TEXT_DETECTION 은 낱말 단위로 흩어진 간판·
    표지판용이고, 우리가 보는 것은 줄과 단락이 있는 빽빽한 표시사항이다.

    **실패는 빈 문자열이다.** 판독은 원문 없이도 지금처럼 돌아야 한다 - 여기서
    예외를 올리면 원문을 곁들이려다 판독 자체를 못 하게 된다.
    """
    if not image_bytes:
        return ''

    # API 키가 있으면 그걸로, 없으면 서비스 계정으로. 둘 다 없으면 조용히 비운다.
    key = _api_key()
    url, headers = VISION_ENDPOINT, {'Content-Type': 'application/json'}
    if key:
        url = f'{VISION_ENDPOINT}?key={key}'
    else:
        token = _access_token()
        if not token:
            return ''
        headers['Authorization'] = f'Bearer {token}'

    import requests

    payload = {
        'requests': [{
            'image': {'content': base64.b64encode(_shrink(image_bytes)).decode('ascii')},
            'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
            # 힌트를 안 주면 한글 라벨의 영문·숫자 혼재 구간에서 언어를 오판한다.
            'imageContext': {'languageHints': ['ko', 'en']},
        }],
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except Exception:
        logger.exception('[OCR 원문] Vision 호출 실패')
        return ''

    if response.status_code != 200:
        # 키가 URL 에 들어 있으므로 응답 본문에 섞여 나올 수 있다. 로그에
        # 남기기 전에 가린다.
        detail = response.text[:500]
        if key:
            detail = detail.replace(key, '***')
        logger.error('[OCR 원문] Vision 응답 %s: %s', response.status_code, detail)
        return ''

    try:
        body = response.json()['responses'][0]
    except Exception:
        logger.exception('[OCR 원문] Vision 응답을 읽지 못했다')
        return ''

    if body.get('error'):
        logger.error('[OCR 원문] Vision 오류: %s', body['error'])
        return ''

    text = ((body.get('fullTextAnnotation') or {}).get('text') or '').strip()
    if len(text) < MIN_TEXT_CHARS:
        # 몇 글자만 흘러나왔다. 이건 원문이 아니라 조각이다.
        logger.info('[OCR 원문] 글자가 %s 자뿐이라 버린다', len(text))
        return ''
    return text


# ── 읽히는가 — 정답지로 재기 ──────────────────────────────────────────────────

def _normalize_with_map(text) -> tuple[str, list[int], str]:
    """
    견줄 문자열, 그 각 글자가 **어디에서 왔는지** 의 자리표, 그리고 발췌용 원문.

    하는 일 세 가지.

      NFKC    호환 문자를 표준형으로 편다. 이게 없어서 멀쩡한 값이 빗나갔다 -
              보관방법 정답은 "냉장(0~10 ℃)" 인데 OCR 은 "냉장(0~10°C)" 로
              읽었다. ℃(U+2103) 하나와 °C 두 글자는 **같은 것**이고, NFKC 가
              전자를 후자로 편다. 76.9 -> 92.9, 86.7 -> 100 이 됐다.
              ㎎->mg, ㎖->ml, ④->4, 전각->반각도 같이 정리되고, 자모로 풀린
              한글(NFD)도 음절로 합쳐진다 - 파일명에서 실제로 섞여 들어온다.
      casefold  영문 대소문자를 지운다. www 와 WWW 는 같은 주소다.
      공백 제거  줄바꿈과 띄어쓰기는 라벨과 원문이 늘 다르다.

    괄호와 쉼표는 **남긴다.** 원재료명의 괄호 구조가 지금 가장 자주 무너지는
    자리라, 그걸 지우고 재면 정작 알고 싶은 것을 못 재게 된다.

    자리표는 세 번째로 돌려주는 NFKC 문자열 기준이다. 원문 그대로가 아니라
    **실제로 견준 문자열** 을 발췌해 보여 줘야, 왜 그 점수가 나왔는지가 눈에
    들어온다.
    """
    base = unicodedata.normalize('NFKC', str(text or ''))
    chars, index = [], []
    for i, ch in enumerate(base):
        if ch.isspace():
            continue
        for folded in ch.casefold():
            chars.append(folded)
            index.append(i)
    return ''.join(chars), index, base


def _normalize(text) -> str:
    """견줄 문자열만. 자리표 쪽과 규칙이 갈라지면 점수와 설명이 어긋난다."""
    return _normalize_with_map(text)[0]


def _fragments(value) -> list[str]:
    """
    한 칸의 값을 **원문에서 따로 찾아야 하는 조각**으로 가른다.

    기타표시사항(additional_info)은 고객상담실 번호, 부정불량식품 신고번호,
    홈페이지 주소처럼 **서로 무관한 문구를 줄바꿈으로 이어 붙인** 칸이다
    (판독 프롬프트가 그렇게 적으라고 지시한다). 라벨에서 그 문구들은 여기저기
    떨어져 인쇄돼 있으니, 이어 붙인 문자열 하나가 원문에 **연속해서** 있는지
    물으면 당연히 낮게 나온다.

    실제로 그렇게 나왔다 - 원문에 세 문구가 다 있는데도 55.8 점이었다. 그건
    OCR 이 못 읽은 게 아니라 **우리가 이어 붙인 방식을 재고 있었던 것**이다.

    조각이 하나뿐이면 예전과 똑같이 동작한다.
    """
    parts = [p.strip() for p in re.split(r'[\r\n]+', str(value or ''))]
    return [p for p in parts if p]


def _weighted(pieces, haystack) -> float | None:
    """조각마다 찾아 **글자 수로 가중평균.** 길이로 가중하지 않으면 "(주)" 세 글자가 200자짜리 문구와 같은 무게를 갖는다."""
    from rapidfuzz import fuzz

    total, weighted = 0, 0.0
    for piece in pieces:
        needle = _normalize(piece)
        if not needle:
            continue
        weighted += fuzz.partial_ratio(needle, haystack) * len(needle)
        total += len(needle)
    return weighted / total if total else None


# 문장 경계. 마침표는 **뒤에 공백이나 끝이 올 때만** 문장을 끊는다.
#
# 그냥 '.' 로 가르면 "www.spcsamlip.co.kr" 이 네 조각으로 부서지고
# "부정.불량식품" 의 "부정" 이 따로 떨어져 나간다. 둘 다 실제 라벨에 있는
# 표기라, 이 규칙이 없으면 멀쩡한 값이 빗나간다.
_SENTENCE_SPLIT = re.compile(r'(?:[.。](?=\s|$)|[\n\r])+')

# 데이터 토막이 섞여 있는가 — 전화번호, 홈페이지, 이메일.
_DATA_ISH = re.compile(r'[0-9]|https?://|www\.|@', re.IGNORECASE)


def _scatter_pieces(value) -> list[str]:
    """
    흩어져 인쇄된 값을 **따로 찾을 단위**로 가른다.

    **문장을 먼저 본다.** 이게 핵심이다 - 문장 하나는 원문에 통째로 있어야
    한다. 지어낸 문장은 쓰인 낱말이 아무리 흔해도 문장 전체로는 원문에
    나오지 않는다. 그래서 흩어짐을 허용하면서도 지어냄은 그대로 잡힌다.

    낱말로 가르면 그 성질을 잃는다. "제품을 개봉 후 냉장 보관하세요" 를
    지어내도 낱말은 저마다 라벨 어딘가에 있어서 점수가 채워진다.

    네 글자 미만인 조각은 버린다. "부정.불량식품" 처럼 문장 부호가 낱말
    안에 있는 경우가 흔한데, 그 조각("부정")까지 따로 찾으면 안 된다.

    문장이 하나뿐이면 띄어쓰기로 가른다 - 연락처·주소처럼 문장이 아닌 값이다
    (예: "고객상담실 080-739-8572 (수신자 부담) www.spcsamlip.co.kr").
    """
    raw = str(value or '')
    sentences = [s for s in re.split(_SENTENCE_SPLIT, raw) if len(_normalize(s)) >= 4]
    if len(sentences) >= 2:
        return sentences

    # 문장이 하나뿐이다. 낱말로 가르는 것은 **데이터 토막이 섞인 값**에만
    # 허용한다 - 전화번호·주소·홈페이지처럼 서로 다른 항목을 나란히 적은 값이다.
    #
    # 순수한 문장을 낱말로 가르면 지어냄이 통과한다. "제품을 냉장 보관하고
    # 개봉 후에는 서늘한 곳에 두십시오" 는 라벨에 없어도 낱말은 저마다 어딘가
    # 있어서 83 점이 나온다. 문장은 통째로 원문에 있어야 한다.
    if not _DATA_ISH.search(raw):
        return []
    return [t for t in re.split(r'\s+', raw) if len(_normalize(t)) >= 2]


def _scattered_score(value, haystack) -> float | None:
    """
    값의 조각들이 원문 **여기저기에 흩어져 있어도** 있는 것으로 본다.

    ASSEMBLED_FIELDS 에만 쓴다. 왜 필요한지는 실제 사례가 말해 준다.

        찾은 값 : 메밀, 땅콩, ... 잣 혼입가능성 있음. 가급적 빨리 드시기
                  바랍니다. 부정.불량식품 신고는 국번없이 1399
        원문 근처: 메밀, 땅콩, ... 잣 혼입가능성 있음. 포장지의 끝부분만 찢은
                  후에 전자레인지를 돌려 ⏎ 주세요. 제품이 뜨거울 수 있으니

    세 문장이 원문에 **다 있다.** 다만 라벨 여기저기에 인쇄돼 있어 사이에
    다른 주의사항이 끼어 있을 뿐이다. 이어 붙인 문자열이 연속으로 있는지
    물으면 59.1 점이 나오는데, 그건 OCR 이 못 읽어서가 아니다.
    문장으로 가르면 셋 다 100 점이다.
    """
    pieces = _scatter_pieces(value)
    if len(pieces) < 2:
        return None    # 조각이 하나뿐이면 흩어질 것도 없다
    return _weighted(pieces, haystack)


def match_score(value, text, assembled: bool = False) -> float:
    """
    값이 원문에 있는가. 0~100.

    줄바꿈으로 가른 조각마다 찾아 글자 수로 가중평균한다. RapidFuzz 의
    partial_ratio 를 쓴다 - 원문은 줄바꿈과 띄어쓰기가 라벨과 다르고 한두
    글자는 늘 어긋난다. 정확히 같은지 보면 전부 "없다" 가 된다.

    assembled=True 면 흩어져 인쇄된 경우도 함께 보고 **높은 쪽**을 쓴다.
    ASSEMBLED_FIELDS 주석 참고.
    """
    haystack = _normalize(text)
    if not haystack:
        return 0.0

    score = _weighted(_fragments(value), haystack)
    if score is None:
        return 0.0
    if assembled:
        scattered = _scattered_score(value, haystack)
        if scattered is not None:
            score = max(score, scattered)
    return round(score, 1)


def explain(value, text, pad: int = 12) -> list[dict]:
    """
    왜 그 점수가 나왔는지 — 조각마다 **원문의 어느 대목과 견줬는지** 보여 준다.

    점수만 보면 낮은 이유를 알 수 없어서 추측하게 된다. 실제로 그랬다 -
    additional_info 가 55.8 인 것을 "여러 문구를 이어 붙여서" 라고 짚고
    조각 분할을 넣었는데, 그 값에는 애초에 줄바꿈이 없어서 아무것도 바뀌지
    않았다. **보지 않고 고쳤다.**

    Returns: [{'fragment', 'score', 'nearest'}, ...]
             nearest 는 원문에서 가장 가까운 대목(앞뒤 pad 글자 포함).
    """
    from rapidfuzz import fuzz

    haystack, index, base = _normalize_with_map(text)
    rows = []
    for fragment in _fragments(value):
        needle = _normalize(fragment)
        if not needle:
            continue
        if not haystack:
            rows.append({'fragment': fragment, 'score': 0.0, 'nearest': ''})
            continue

        align = fuzz.partial_ratio_alignment(needle, haystack)
        if align is None:
            rows.append({'fragment': fragment, 'score': 0.0, 'nearest': ''})
            continue

        # 정규화 자리를 원문 자리로 되돌린다. 원문 그대로 보여야 띄어쓰기와
        # 줄바꿈까지 눈에 들어온다.
        start = index[align.dest_start] if align.dest_start < len(index) else 0
        end_i = min(align.dest_end, len(index)) - 1
        end = index[end_i] + 1 if end_i >= 0 else start
        rows.append({
            'fragment': fragment,
            'score': round(align.score, 1),
            'nearest': base[max(0, start - pad):end + pad].replace('\n', ' ⏎ '),
        })
    return rows


def field_recall(expected: dict, text: str) -> list[dict]:
    """
    정답의 각 값이 원문에 있는가. 항목별 점수 목록.

    짧은 값은 우연히 맞을 수 있다("2g" 가 어딘가엔 있다). 그래서 가부 판단은
    이 목록 전체가 아니라 긴 칸(LONG_FIELDS)으로 한다 - long_recall 참고.
    """
    rows = []
    for field, value in (expected or {}).items():
        needle = _normalize(value)
        if not needle:
            continue   # 그 라벨에 없는 항목이다. 채점 대상이 아니다
        skipped = field in NON_TEXT_FIELDS
        score = 0.0 if skipped else match_score(
            value, text, assembled=field in ASSEMBLED_FIELDS)
        rows.append({
            'field': field,
            'length': len(needle),
            'fragments': len(_fragments(value)),
            'score': round(score, 1),
            'found': (not skipped) and score >= FOUND_THRESHOLD,
            'long': field in LONG_FIELDS,
            'skipped': skipped,
        })
    rows.sort(key=lambda r: (r['skipped'], not r['long'], -r['length']))
    return rows


def recall_summary(rows: list[dict]) -> dict:
    """
    항목별 점수를 가부 판단에 쓸 숫자 둘로 줄인다.

    long_recall 이 판단 기준이다. OCR_UPGRADE_PLAN.md §13 의 문턱:

        >= 0.9   2~5단계 전부 진행
        0.6~0.9  검증자로만 쓴다 (원문 주입은 안 함)
        <  0.6   접는다

    긴 칸이 정답지에 하나도 없으면 long_recall 은 None 이다. **0 이 아니다** -
    못 읽은 것과 잴 것이 없는 것은 다르다.
    """
    scored = [r for r in rows if not r['skipped']]
    long_rows = [r for r in scored if r['long']]
    return {
        'fields': len(scored),
        'skipped': len(rows) - len(scored),
        'found': sum(1 for r in scored if r['found']),
        'recall': (round(sum(r['found'] for r in scored) / len(scored), 3)
                   if scored else None),
        'long_fields': len(long_rows),
        'long_recall': (round(sum(r['score'] for r in long_rows) / len(long_rows) / 100, 3)
                        if long_rows else None),
    }


def verdict(long_recall) -> str:
    """문턱을 문장으로. 숫자를 보고 사람마다 다르게 읽지 않도록."""
    if long_recall is None:
        return '긴 칸이 정답지에 없어 판단할 수 없다'
    if long_recall >= 0.9:
        return '읽힌다 — 원문 주입까지 진행할 만하다'
    if long_recall >= 0.6:
        return '반쯤 읽힌다 — 검증자로만 쓰고 원문 주입은 하지 않는다'
    return '못 읽는다 — 이 방향을 접는다'


def text_for_case(case, refresh: bool = False) -> str:
    """
    정답지 사진의 원문. 한 번 읽으면 정답지에 붙여 두고 다시 읽지 않는다.

    **캐시가 아니라 저장이다.** 측정은 같은 사진을 회차(기본 3) x 정답지 수 x
    프롬프트 판 수만큼 읽는다. 매번 Vision 을 부르면 잴수록 돈이 나가고, 무엇보다
    원문이 회차마다 달라지면 무엇을 재고 있는지 알 수 없게 된다.

    파일 캐시(CACHES['default'])에 두지 않는 이유는 MAX_ENTRIES 500 을 넘으면
    Django 가 1/3 을 잘라내기 때문이다 - ai_rate_limit 이 같은 이유로 일일
    카운터를 DB 로 옮겼다. 정답지 사진은 고정이니 정답지에 두는 것이 맞다.
    """
    if case.ocr_text and not refresh:
        return case.ocr_text

    try:
        with case.image.open('rb') as fh:
            image_bytes = fh.read()
    except Exception:
        logger.exception('[OCR 원문] 정답지 사진을 열지 못했다 (case=%s)', case.pk)
        return ''

    text = extract_text(image_bytes)
    if text:
        from django.utils import timezone
        case.ocr_text = text
        case.ocr_engine = 'google'
        case.ocr_fetched_at = timezone.now()
        case.save(update_fields=['ocr_text', 'ocr_engine', 'ocr_fetched_at'])
    return text


def measure_case(case, refresh: bool = False) -> dict:
    """
    정답지 한 장에 대해 "원문이 정답을 얼마나 담고 있는가" 를 낸다.

    원문을 못 받았으면 회수율은 **0 이 아니라 None** 이다. 이 둘은 전혀 다르다.

        원문을 받았는데 정답이 그 안에 없다   -> OCR 이 못 읽었다. 0 이 맞다
        원문 자체를 못 받았다                 -> 아직 아무것도 재지 못했다

    처음에 이걸 안 갈랐다가 실제로 틀린 결론이 나왔다 - Google Cloud 프로젝트에
    결제가 안 걸려 있어 403 이 왔는데, 화면에는 "긴 칸 회수율 0.000 / 판정: 못
    읽는다 - 이 방향을 접는다" 가 찍혔다. **OCR 은 한 번도 돌지 않았다.**
    설정 문제로 프로젝트를 접을 뻔했다.
    """
    text = text_for_case(case, refresh=refresh)
    if not text:
        return {
            'case_id': case.pk,
            'name': case.name,
            'engine': 'google',
            'chars': 0,
            'text': '',
            'rows': [],
            'fields': 0, 'skipped': 0, 'found': 0, 'recall': None,
            'long_fields': 0, 'long_recall': None,
            'measured': False,
            'verdict': '원문을 받지 못해 아직 재지 못했다',
        }

    rows = field_recall(case.expected or {}, text)
    # 못 찾은 항목만 "무엇을 찾았고 원문의 어디가 가장 가까웠는지" 를 붙인다.
    # 전부 붙이면 출력이 길어지기만 하고, 알고 싶은 것은 빗나간 자리뿐이다.
    for row in rows:
        if row['skipped'] or row['found']:
            continue
        row['expected'] = str((case.expected or {}).get(row['field']) or '')
        row['detail'] = explain(row['expected'], text)
    summary = recall_summary(rows)
    return {
        'case_id': case.pk,
        'name': case.name,
        'engine': 'google',
        'measured': True,
        'chars': len(text),
        'text': text,
        'rows': rows,
        **summary,
        'verdict': verdict(summary['long_recall']),
    }
