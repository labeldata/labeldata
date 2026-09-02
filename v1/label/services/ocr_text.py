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

# 이 점수 이상이면 "원문에 있다" 로 센다.
FOUND_THRESHOLD = 90


def _access_token() -> str:
    """
    서비스 계정 JSON 으로 Vision 용 액세스 토큰을 받는다.

    FCM 이 쓰는 방식과 같다(mobile/services/push_service._get_fcm_access_token).
    JSON 본문을 그대로 넣어도 되고 파일 경로를 넣어도 된다.

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

    token = _access_token()
    if not token:
        return ''

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
        response = requests.post(
            VISION_ENDPOINT,
            headers={'Authorization': f'Bearer {token}',
                     'Content-Type': 'application/json'},
            json=payload, timeout=60)
    except Exception:
        logger.exception('[OCR 원문] Vision 호출 실패')
        return ''

    if response.status_code != 200:
        logger.error('[OCR 원문] Vision 응답 %s: %s',
                     response.status_code, response.text[:500])
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

def _normalize(text) -> str:
    """
    견주기 전에 공백만 없앤다.

    괄호와 쉼표는 **남긴다.** 원재료명의 괄호 구조가 지금 가장 자주 무너지는
    자리라, 그걸 지우고 재면 정작 알고 싶은 것을 못 재게 된다.
    """
    return re.sub(r'\s+', '', str(text or ''))


def field_recall(expected: dict, text: str) -> list[dict]:
    """
    정답의 각 값이 원문에 있는가. 항목별 점수 목록.

    RapidFuzz 의 partial_ratio 로 본다 - 원문은 줄바꿈과 띄어쓰기가 라벨과
    다르고, 한두 글자는 늘 어긋난다. 정확히 같은지 보면 전부 "없다" 가 된다.

    짧은 값은 우연히 맞을 수 있다("g" 두 글자가 어딘가엔 있다). 그래서 가부
    판단은 이 목록 전체가 아니라 긴 칸(LONG_FIELDS)으로 한다 - long_recall 참고.
    """
    from rapidfuzz import fuzz

    haystack = _normalize(text)
    rows = []
    for field, value in (expected or {}).items():
        needle = _normalize(value)
        if not needle:
            continue   # 그 라벨에 없는 항목이다. 채점 대상이 아니다
        score = fuzz.partial_ratio(needle, haystack) if haystack else 0.0
        rows.append({
            'field': field,
            'length': len(needle),
            'score': round(score, 1),
            'found': score >= FOUND_THRESHOLD,
            'long': field in LONG_FIELDS,
        })
    rows.sort(key=lambda r: (not r['long'], -r['length']))
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
    long_rows = [r for r in rows if r['long']]
    return {
        'fields': len(rows),
        'found': sum(1 for r in rows if r['found']),
        'recall': round(sum(r['found'] for r in rows) / len(rows), 3) if rows else None,
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
    """정답지 한 장에 대해 "원문이 정답을 얼마나 담고 있는가" 를 낸다."""
    text = text_for_case(case, refresh=refresh)
    rows = field_recall(case.expected or {}, text)
    summary = recall_summary(rows)
    return {
        'case_id': case.pk,
        'name': case.name,
        'engine': 'google',
        'chars': len(text),
        'text': text,
        'rows': rows,
        **summary,
        'verdict': verdict(summary['long_recall']),
    }
