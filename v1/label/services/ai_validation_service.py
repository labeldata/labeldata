"""
표시사항 AI 2차 검증 (파일럿) — 원재료명 표시 순서.

v1/label/services/validation_service.py의 규칙 기반 검증은 정규식/키워드
매칭만 가능해서, "원재료는 사용된 함량이 많은 순으로 표시해야 한다"는
식품표시법의 핵심 규정을 지금까지 전혀 검증하지 못했다(자유서식 텍스트
안의 복합원재료·괄호 중첩 함량 표기를 정규식만으로 안정적으로 파싱할
수 없기 때문). 이 모듈은 그 공백 하나만 메운다.

설계 원칙(v1/regulatory/services/ai_parser.py와 동일한 철학):
  AI는 "구조화 추출"만 담당한다 — 텍스트에 실제로 적힌 원재료명과
  함량(%)을 등장 순서대로 뽑아낼 뿐, "이게 규정 위반이다"라는 판단
  자체는 AI에게 맡기지 않는다. 내림차순 여부 판정은 추출된 숫자를
  가지고 파이썬에서 결정론적으로 계산한다 — AI가 잘못 판단할 여지를
  판정 로직에서 원천 차단하기 위함(법적 리스크가 있는 도메인이라
  "AI가 다르게 말해서" 발생하는 재현 불가능한 오탐/누락을 피해야 함).

비용/지연 때문에 validate_label()(무료, 즉시)에는 포함하지 않고
별도 엔드포인트(POST /label/<id>/validate/ai/)로 명시적으로 호출한다.
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from v1.label.constants import ALLERGEN_KEYWORDS

logger = logging.getLogger(__name__)

# AI가 반환할 수 있는 알레르기 표준 명칭 화이트리스트 (constants.py의 22종
# 알레르기 유발요소 카테고리와 동일 — 할루시네이션 방지용 검증에 사용)
_ALLERGEN_CATEGORY_NAMES = set(ALLERGEN_KEYWORDS.keys())

# validate_label()의 category 코드 -> 화면에 보여줄 검증 항목명
# (기존 label_preview.js showValidationModal()의 "검증 항목" 열과 같은 스타일)
_CATEGORY_LABELS = {
    'required_missing': '필수 입력 항목',
    'calorie_consistency': '열량 표시 정합성',
    'content_weight': '내용량 표시',
    'farm_seafood': '농수산물 함량 표시',
    'forbidden_phrase': '금지 문구',
    'allergen': '알레르기 표시',
    'recycling_mark': '분리배출마크',
    'origin_missing': '원산지 표시',
    'additive_display_name': '식품첨가물 표시명',
    'ingredient_order': '원재료 표시 순서',
    'name_ingredient_match': '제품명-원재료 일치성 (AI)',
}

# "규정만 검증"(규칙 기반)에는 없고 AI검증에만 있는 항목들 — 사용자에게
# "AI가 규칙 기반보다 더 많이 본다"는 걸 실감하게 하려면 이 목록이
# 비어있으면 안 된다. run_full_review()의 요약·안내 문구에서 참조.
AI_ONLY_CATEGORIES = ['ingredient_order', 'name_ingredient_match']
AI_ONLY_CATEGORIES_KO = [_CATEGORY_LABELS[c] for c in AI_ONLY_CATEGORIES]

_INGREDIENT_ORDER_BASIS = '「식품등의 표시기준」 원재료명 표시 순서 규정(중량비율이 많은 순서로 표시)'
_ALLERGEN_BASIS = '「식품등의 표시기준」 알레르기 유발물질 표시 규정'
_NAME_INGREDIENT_BASIS = '「식품등의 표시기준」 제품명에 특정 원재료를 사용하거나 강조하는 경우의 표시 규정'

# ── AI 적용 범위에 대한 판단 메모 ───────────────────────────────────────────
# 6개 규칙기반 검증 중 이번에 AI로 추가 보강한 건 "알레르기 표시"(아래
# check_allergens_ai)와 기존 "원재료 표시 순서" 파일럿 2개뿐이다. 나머지는
# 검토 후 의도적으로 규칙 기반을 유지했다:
#   - content_weight / origin_missing: 단순 존재 여부 확인이라 AI가 더
#     정확하게 만들 여지가 없음(오히려 지연·비용만 추가).
#   - recycling_mark: 포장재질 <-> 마크 매핑은 확정적 대응표라 AI 판단이
#     끼어들 필요 없는 순수 lookup.
#   - farm_seafood: 현재 정규식(이름 뒤 콤마 전까지 아무 문자+숫자%)이
#     이미 폭넓게 매치해서 놓치는 사례가 적고, AI로 바꿔도 이득이 제한적.
#   - forbidden_phrase("천연"/"자연"): 예외 조건(원물 여부, 상표명 포함
#     여부 등) 판단은 사실 추출이 아니라 "규정 위반이다/아니다"라는 법적
#     평가 그 자체다. 이 프로젝트의 AI 설계 원칙(AI는 추출만, 판정은
#     결정론적 로직)에 정면으로 위배돼 지금은 적용하지 않음 — 대신 항상
#     보수적으로 전부 플래그하고 사용자가 사용조건을 직접 확인하게 유지.
#     (오탐이 나더라도 안전한 방향; 반대로 AI가 "괜찮다"고 잘못 판단해
#     실제 위반을 놓치는 게 훨씬 위험하다.)


# ── OpenAI 호출 공통 ────────────────────────────────────────────────────────
# 타임아웃을 명시하지 않으면 openai 클라이언트 기본값이 적용된다 —
# read 600초 × 재시도 2회 = 호출 하나가 최대 30분. PythonAnywhere 는 웹 요청을
# 300초에 끊으므로 워커가 죽고 500 이 난다. 실제로 그렇게 났다.
# gpt-4o-mini 한 번 호출은 정상이면 2~5초라, 20초면 넉넉하다.
_DEFAULT_AI_TIMEOUT = 20        # 초
_DEFAULT_AI_MAX_RETRIES = 1

# 검증하지 못한 이유. 화면이 "왜 못 봤는지" 를 사실대로 말할 수 있게 한다 —
# 예전에는 원인과 무관하게 "함량(%)이 명시돼 있지 않아서" 라고만 안내해서,
# API 가 죽어 있어도 사용자는 자기 입력 탓인 줄 알았다.
REASON_OK             = 'ok'
REASON_NO_INPUT       = 'no_input'         # 볼 텍스트 자체가 없음
REASON_NO_PERCENT     = 'no_percent'       # % 표기가 2개 미만이라 순서 판단 불가
REASON_NOT_CONFIGURED = 'not_configured'   # OPENAI_API_KEY 미설정
REASON_NO_PACKAGE     = 'no_package'       # openai 패키지 미설치
REASON_TIMEOUT        = 'timeout'          # 응답 지연
REASON_API_ERROR      = 'api_error'        # 그 외 호출 실패

REASON_MESSAGES = {
    REASON_NO_INPUT:       '원재료명이 비어 있어 확인하지 못했습니다.',
    REASON_NO_PERCENT:     '원재료명에 함량(%)이 2개 이상 명시돼 있지 않아 확인하지 못했습니다.',
    REASON_NOT_CONFIGURED: 'AI 검증이 설정돼 있지 않아 확인하지 못했습니다. (관리자 문의)',
    REASON_NO_PACKAGE:     'AI 검증 구성요소가 설치돼 있지 않아 확인하지 못했습니다. (관리자 문의)',
    REASON_TIMEOUT:        'AI 응답이 늦어 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    REASON_API_ERROR:      'AI 호출에 실패해 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
}

# 사용자 입력 때문이 아니라 시스템 쪽 문제로 못 본 경우 — 사용 횟수를 차감하지 않는다.
SYSTEM_FAILURE_REASONS = {
    REASON_NOT_CONFIGURED, REASON_NO_PACKAGE, REASON_TIMEOUT, REASON_API_ERROR,
}


def _ai_timeout() -> float:
    return getattr(settings, 'AI_VALIDATION_TIMEOUT', _DEFAULT_AI_TIMEOUT)


def _ai_max_retries() -> int:
    return getattr(settings, 'AI_VALIDATION_MAX_RETRIES', _DEFAULT_AI_MAX_RETRIES)


def get_openai_client():
    """(client, reason). 만들지 못하면 client 는 None."""
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return None, REASON_NOT_CONFIGURED
    try:
        from openai import OpenAI
    except ImportError:
        return None, REASON_NO_PACKAGE
    return OpenAI(
        api_key=api_key,
        timeout=_ai_timeout(),
        max_retries=_ai_max_retries(),
    ), REASON_OK


def call_openai(tag: str, prompt: str, max_tokens: int,
                temperature: float = 0.0, json_mode: bool = True):
    """
    OpenAI 한 번 호출. (내용, 사유) 를 돌려주고 예외는 밖으로 내보내지 않는다.
    json_mode 면 파싱된 dict, 아니면 문자열. 실패하면 내용은 None.
    """
    client, reason = get_openai_client()
    if client is None:
        logger.warning('[%s] %s', tag, REASON_MESSAGES.get(reason, reason))
        return None, reason

    kwargs = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if json_mode:
        kwargs['response_format'] = {'type': 'json_object'}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        # 타임아웃을 따로 구분해야 "잠시 후 다시" 안내가 맞는 말이 된다.
        name = type(exc).__name__.lower()
        is_timeout = 'timeout' in name or 'timeout' in str(exc).lower()
        reason = REASON_TIMEOUT if is_timeout else REASON_API_ERROR
        logger.error('[%s] OpenAI 호출 오류(%s): %s', tag, reason, exc)
        return None, reason

    content = (response.choices[0].message.content or '').strip()
    if not json_mode:
        return content, REASON_OK
    try:
        return json.loads(content), REASON_OK
    except Exception as exc:
        logger.error('[%s] 응답 JSON 파싱 실패: %s', tag, exc)
        return None, REASON_API_ERROR


def extract_ingredient_order(rawmtrl_text: str) -> list[dict]:
    """
    원재료명 표시 텍스트에서 원재료명과 명시된 함량(%)을 등장 순서 그대로 추출.

    Returns: [{'name': str, 'percent': float | None}, ...]
    텍스트에 명시된 숫자만 사용하고 없으면 percent=None (추론 금지).
    (items, reason) 를 돌려준다. 실패해도 예외를 밖으로 내보내지 않는다.
    """
    text = (rawmtrl_text or '').strip()
    if not text:
        return [], REASON_NO_INPUT

    prompt = f"""다음은 식품 라벨의 "원재료명" 표시 텍스트입니다.
텍스트에 나열된 순서 그대로, 각 원재료명과 그 옆에 명시적으로 적힌 함량(%)을 추출하세요.

규칙:
- 복합원재료 안의 하위 원료(예: "설탕[백설탕(70%), 흑설탕(30%)]")도 각각 별도 항목으로 추출하되,
  등장 순서(텍스트에서 왼쪽부터 읽은 순서)를 그대로 유지하세요.
- 원재료 옆에 숫자 %가 명시돼 있지 않으면 percent를 null로 두세요. 절대 추측하지 마세요.
- 원재료명이 아닌 것(예: "[알레르기 성분: ...]", "[GMO 성분: ...]")은 제외하세요.
- 텍스트에 실제로 적힌 것만 추출하고, 없는 원재료를 만들어내지 마세요.

응답 형식(JSON): {{"items": [{{"name": "설탕", "percent": 30.0}}, {{"name": "밀가루", "percent": null}}]}}

텍스트:
{text[:3000]}
"""

    result, reason = call_openai('원재료 순서 AI검증', prompt, max_tokens=800)
    if result is None:
        return [], reason

    try:
        raw_items = result.get('items', [])
        if not isinstance(raw_items, list):
            return [], REASON_API_ERROR

        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '')).strip()
            if not name:
                continue
            percent = item.get('percent', None)
            try:
                percent = float(percent) if percent is not None else None
            except (TypeError, ValueError):
                percent = None
            items.append({'name': name, 'percent': percent})
        return items, REASON_OK

    except Exception as exc:
        logger.error(f'[원재료 순서 AI검증] 응답 처리 오류: {exc}')
        return [], REASON_API_ERROR


def check_ingredient_order(label) -> dict:
    """
    원재료명 표시 순서가 명시된 함량 기준 내림차순인지 검사.

    함량(%)이 텍스트에 있는 항목들끼리만 순서를 비교한다(식품표시법의
    "함량이 많은 순으로 표시" 규정은 함량을 알 수 있는 범위에서만 검증
    가능 — % 표시가 없는 원재료끼리의 순서는 이 검사로 판단하지 않음).

    Returns:
        {'checked': bool, 'ok': bool, 'items': [...], 'issues': [...]}
        checked=False면 AI 추출이 비었거나(설정 미비·API 오류·원재료명
        텍스트에 % 표기 자체가 없음) 판단할 근거가 없다는 뜻 — "위반
        없음"과 구분해야 하므로 ok와 별도 필드로 노출한다.
    """
    items, reason = extract_ingredient_order(label.rawmtrl_nm_display or label.rawmtrl_nm or '')
    if reason != REASON_OK:
        return {'checked': False, 'ok': True, 'items': items, 'issues': [], 'reason': reason}

    dated = [i for i in items if i['percent'] is not None]

    if len(dated) < 2:
        return {'checked': False, 'ok': True, 'items': items, 'issues': [],
                'reason': REASON_NO_PERCENT}

    issues = []
    for i in range(len(dated) - 1):
        cur, nxt = dated[i], dated[i + 1]
        if cur['percent'] < nxt['percent']:
            issues.append({
                'category': 'ingredient_order',
                'message': (
                    f"원재료명 표시 순서가 함량 내림차순이 아닙니다: "
                    f"\"{cur['name']}\"({cur['percent']}%)가 \"{nxt['name']}\"({nxt['percent']}%)보다 "
                    f"앞에 있지만 함량은 더 적습니다. (근거: {_INGREDIENT_ORDER_BASIS})"
                ),
                'suggestion': '원재료는 사용된 함량(배합비율)이 많은 순서대로 표시해야 합니다. 순서를 바꿔주세요.',
            })

    return {'checked': True, 'ok': len(issues) == 0, 'items': items, 'issues': issues,
            'reason': REASON_OK}


def extract_allergens_ai(ingredients_text: str) -> list[str] | None:
    """
    원재료명 텍스트에서 실제로 "사용된 원료"로서 언급된 알레르기 유발요소만
    추출한다. constants.ALLERGEN_KEYWORDS의 단순 문자열 포함 매칭과 달리
    "대두 없음", "우유 미포함(Free)" 같은 부정 표현이나, 알레르기 표시란
    문구 자체("[알레르기 성분: ...]")를 다시 원료로 오인하는 걸 걸러낼 수
    있다. 22종 표준 명칭 중 텍스트에 실제로 근거가 있는 것만 추출하고
    추론하지 않는다. AI 미설정/호출 실패 시 None(호출부가 키워드 매칭
    방식으로 폴백하도록 — 원재료 순서 검증과 동일한 graceful degradation).
    """
    text = (ingredients_text or '').strip()
    if not text:
        return [], REASON_NO_INPUT

    allergen_names = ', '.join(_ALLERGEN_CATEGORY_NAMES)
    prompt = f"""다음은 식품 라벨의 "원재료명" 표시 텍스트입니다.
아래 22종 알레르기 유발요소 표준 명칭 중, 이 제품에 **실제로 원료로 사용된 것으로
텍스트에 명시된 것만** 골라내세요.

표준 명칭 목록: {allergen_names}

규칙:
- "우유 미포함", "대두 프리(free)", "땅콩 없음" 등 부정·제외 표현으로 언급된 것은 제외하세요.
- "[알레르기 성분: 우유, 대두]"처럼 이미 알레르기 표시란에 선언된 문구 자체는 원료 사용 근거가
  아니므로 그것만으로 판단하지 말고, 원재료 목록(예: "우유", "탈지분유" 등 실제 원료명)에
  근거가 있는지로만 판단하세요.
- 텍스트에 명시된 원료만 근거로 삼고, 표준 명칭과 정확히 일치하지 않아도 같은 알레르기
  유발요소로 볼 수 있는 원료명(예: "탈지분유"->"우유", "대두유"->"대두")이면 표준 명칭으로
  변환해 포함하세요.
- 확실하지 않으면 포함하지 마세요(추론 금지, 과다 검출보다 누락이 나음 — 이건 파이썬 쪽에서
  선언값과 대조해 안내만 하지 최종 판단은 사람이 하기 때문).

응답 형식(JSON): {{"allergens": ["우유", "대두"]}}

텍스트:
{text[:3000]}
"""

    result, reason = call_openai('알레르기 AI검증', prompt, max_tokens=300)
    if result is None:
        return None, reason

    try:
        raw = result.get('allergens', [])
        if not isinstance(raw, list):
            return [], REASON_OK
        # 표준 22종 명칭 밖의 값(할루시네이션 방지)은 제거
        valid = {str(a).strip() for a in raw if isinstance(a, str)}
        return sorted(valid & _ALLERGEN_CATEGORY_NAMES), REASON_OK

    except Exception as exc:
        logger.error(f'[알레르기 AI검증] 응답 처리 오류: {exc}')
        return None, REASON_API_ERROR


def check_allergens_ai(label) -> dict:
    """
    AI로 추출한 "실제 사용 알레르기 유발요소" 목록을 선언값(label.allergens)과
    대조한다. 규칙 기반 check_allergens()(단순 키워드 포함 매칭)보다 부정
    표현·오탐 문맥에 강하다. AI가 판단하지 못하면(checked=False) 호출부
    (run_full_review)가 규칙 기반 결과를 그대로 사용하도록 위임한다.
    """
    ingredients_text = label.rawmtrl_nm_display or label.rawmtrl_nm or ''
    if not ingredients_text:
        return {'checked': False, 'issues': [], 'reason': REASON_NO_INPUT}

    detected, reason = extract_allergens_ai(ingredients_text)
    if detected is None or reason != REASON_OK:
        return {'checked': False, 'issues': [], 'reason': reason}

    declared = {
        a.strip() for a in re.split(r'[,、，]', label.allergens or '')
        if a.strip()
    }
    missing = set(detected) - declared

    issues = []
    if missing:
        issues.append({
            'category': 'allergen',
            'message': (
                f'원재료명에서 실제로 사용된 것으로 보이는 알레르기 유발요소가 '
                f'알레르기 표시에 선언되지 않았습니다: {", ".join(sorted(missing))} '
                f'(근거: {_ALLERGEN_BASIS})'
            ),
            'suggestion': '원재료명을 확인해 실제로 사용된 원료라면 알레르기 표시 항목에 추가하세요.',
        })
    return {'checked': True, 'issues': issues, 'reason': REASON_OK}


def extract_emphasized_ingredients_ai(product_name: str) -> list[str] | None:
    """
    제품명에서 "이 제품에 실제로 들어있다고 강조하는 원재료/성분명"만 추출한다.

    규칙 기반 check_farm_seafood_content()는 constants.FARM_SEAFOOD_ITEMS
    (농수산물 약 1만 종 목록)에 있는 단어만 잡아내므로 "초코", "치즈",
    "카라멜", "리얼", "고기" 같은 비농산물 강조 표기는 원천적으로 놓친다.
    이건 규칙(고정 목록 대조)의 구조적 한계라 목록을 아무리 늘려도 못
    채우는 영역 — AI가 자유 텍스트에서 강조 원료명을 직접 추출해야
    메울 수 있다. 브랜드명·수식어("맛있는", "정성가득" 등)는 원재료가
    아니므로 제외하고, 실제 식품 원료/성분으로 보이는 단어만 추출한다.
    AI 미설정/실패 시 None(호출부가 이 검증을 건너뛰도록).
    """
    name = (product_name or '').strip()
    if not name:
        return [], REASON_NO_INPUT

    prompt = f"""다음은 식품 제품명입니다. 이 제품명에서 "실제로 제품에 사용됐다고
소비자에게 강조하는 원재료/성분명"만 추출하세요.

규칙:
- 맛·향·재료를 나타내는 명사만 추출하세요 (예: "딸기요거트"->["딸기"], "초코과자"->["초코"],
  "치즈스틱"->["치즈"], "리얼바닐라아이스크림"->["바닐라"]).
- 브랜드명, 회사명, 단순 수식어("맛있는", "정성가득", "프리미엄", "국내산" 등 원산지
  표현), 포장 형태("스틱", "바", "컵") 등 원재료가 아닌 단어는 제외하세요.
- 식품유형 자체를 나타내는 일반명사(예: "과자", "아이스크림", "음료", "빵")는
  원재료가 아니므로 제외하세요.
- 제품명에 강조할 원재료가 없다고 판단되면 빈 배열을 반환하세요. 억지로 만들어내지 마세요.

응답 형식(JSON): {{"ingredients": ["딸기"]}}

제품명: {name[:200]}
"""

    result, reason = call_openai('제품명-원재료 AI검증', prompt, max_tokens=200)
    if result is None:
        return None, reason

    try:
        raw = result.get('ingredients', [])
        if not isinstance(raw, list):
            return [], REASON_OK
        return [str(i).strip() for i in raw if isinstance(i, str) and str(i).strip()], REASON_OK

    except Exception as exc:
        logger.error(f'[제품명-원재료 일치성 AI검증] 응답 처리 오류: {exc}')
        return None, REASON_API_ERROR


def check_name_ingredient_match_ai(label) -> dict:
    """
    제품명에서 AI가 추출한 강조 원료가 실제 원재료명(rawmtrl_nm_display)
    텍스트에 있는지 대조한다. 대조 자체는 파이썬의 단순 포함 여부
    확인이라 AI 판단 없이 결정론적이다 — AI는 "제품명에서 원료명을
    추출"하는 역할만 한다.

    규칙 기반 farm_seafood 검증(농수산물 한정)과 카테고리가 다르므로
    회사 name_ingredient_match로 별도 관리하고, 규칙 기반 결과와 합치지
    않는다 — 두 검증이 서로 다른 원료 범위를 보고 있어 대체 관계가
    아니라 보완 관계이기 때문.
    """
    product_name = label.prdlst_nm or ''
    ingredients_text = (label.rawmtrl_nm_display or label.rawmtrl_nm or '').lower()
    if not product_name or not ingredients_text:
        return {'checked': False, 'issues': [], 'reason': REASON_NO_INPUT}

    emphasized, reason = extract_emphasized_ingredients_ai(product_name)
    if emphasized is None or reason != REASON_OK:
        return {'checked': False, 'issues': [], 'reason': reason}

    missing = [item for item in emphasized if item.lower() not in ingredients_text]

    issues = []
    if missing:
        issues.append({
            'category': 'name_ingredient_match',
            'message': (
                f'제품명에 강조된 원료 {", ".join(missing)}가 원재료명에서 확인되지 않습니다. '
                f'(근거: {_NAME_INGREDIENT_BASIS})'
            ),
            'suggestion': '실제로 사용된 원료라면 원재료명에 포함하고, 사용하지 않았다면 제품명 표기를 재검토하세요.',
        })
    return {'checked': True, 'issues': issues, 'reason': REASON_OK}


def group_issues_by_category(issues: list[dict]) -> list[dict]:
    """
    validate_label()/check_ingredient_order()가 내는 flat한 issue 목록을
    showValidationModal()과 같은 "검증 항목별 행" 구조로 묶는다.
    항목에 issue가 하나도 없으면 ok=True인 빈 행으로 표시(적합 표시용).

    views.py의 "AI 없이 검증" 버튼(규칙 기반만 실행)에서도 재사용해
    두 검증 경로가 화면에 같은 모양으로 보이게 한다.
    """
    grouped: dict[str, dict] = {}
    for code, label in _CATEGORY_LABELS.items():
        grouped[code] = {'label': label, 'ok': True, 'errors': [], 'suggestions': []}

    for issue in issues:
        code = issue.get('category', 'other')
        label = _CATEGORY_LABELS.get(code, code)
        row = grouped.setdefault(code, {'label': label, 'ok': True, 'errors': [], 'suggestions': []})
        row['ok'] = False
        if issue.get('message'):
            row['errors'].append(issue['message'])
        if issue.get('suggestion'):
            row['suggestions'].append(issue['suggestion'])

    # 검증하지 않은 항목(예: 원재료 순서 - percent 정보 부족)은 목록에서 제외해
    # "적합"으로 오인되지 않게 한다. 호출부에서 checked 플래그로 별도 안내.
    return [row for row in grouped.values()]


def deterministic_summary(category_results: list[dict], ai_only_checked: bool = False) -> str:
    """
    OpenAI 없이 만드는 요약. generate_summary 의 폴백이자, AI 를 아예 부르지
    않기로 한 경로(run_full_review 의 조기 반환)가 쓰는 문장이기도 하다.
    """
    problem_rows = [r for r in category_results if not r['ok']]
    all_labels = [r['label'] for r in category_results]
    ai_note = ', 규정 검증(비AI)에는 없는 AI 전용 항목 포함' if ai_only_checked else ''
    labels_text = f"{', '.join(all_labels)}{ai_note}"

    if not problem_rows:
        return f'{labels_text} 등 {len(all_labels)}개 항목을 검증한 결과 확인된 문제가 없습니다. 모두 표시 규정에 적합합니다.'

    lines = [f"검증한 {len(all_labels)}개 항목({labels_text}) 중 {len(problem_rows)}개에서 확인이 필요합니다."]
    for row in problem_rows:
        for err in row['errors']:
            lines.append(re.sub(r'<[^>]+>', '', err))
    return ' '.join(lines)


def generate_summary(category_results: list[dict], ai_only_checked: bool = False) -> str:
    """
    검증 결과 전체를 사람이 읽기 좋은 한글 요약 문장으로 압축한다.
    어떤 항목을 검증했는지(적합 포함)와, 부적합 항목은 근거 규정과 함께
    언급하도록 해 "전문성이 느껴지지 않는다"는 문제를 해결한다.

    ai_only_checked=True면 이번 검증에 "규정만 검증"(규칙 기반)에는 없는
    AI 전용 항목(원재료 표시 순서/제품명-원재료 일치성)이 실제로 포함됐다는
    뜻 — 첫 문장에서 이를 명시해 "AI가 규칙 기반을 그냥 대행하는 것"처럼
    느껴지지 않게 한다.

    OpenAI 미설정/호출 실패 시에도 항상 뭔가는 보여줘야 하므로, 결정론적
    폴백 요약(검증 항목 전체 나열 + 부적합 항목 근거 규정)을 우선
    만들어두고, AI 호출이 성공하면 그걸 조금 더 읽기 좋은 문장으로
    다듬은 결과로 교체한다. AI가 실패해도 화면이 빈 채로 뜨는 일은 없다.
    """
    problem_rows = [r for r in category_results if not r['ok']]
    all_labels = [r['label'] for r in category_results]
    fallback = deterministic_summary(category_results, ai_only_checked)

    if not problem_rows:
        return fallback

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return fallback

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        return fallback

    issue_lines = []
    for row in problem_rows:
        for err in row['errors']:
            # AI 요약용으로는 HTML 태그(<strong> 등)를 제거해 순수 텍스트만 전달
            plain = re.sub(r'<[^>]+>', '', err)
            issue_lines.append(f"- [{row['label']}] {plain}")

    ai_coverage_note = (
        f"이번 검증엔 규칙 기반(정규식·키워드 매칭)만으로는 확인할 수 없는 항목도 포함돼 있습니다 "
        f"({', '.join(AI_ONLY_CATEGORIES_KO)}). 첫 문장에서 이 점을 자연스럽게 언급하세요.\n"
        if ai_only_checked else ''
    )

    prompt = f"""아래는 식품 표시사항(라벨) 검증 결과입니다.
이 내용을 식품 라벨을 처음 만들어보는 담당자도 이해할 수 있도록,
전문적이면서도 자연스러운 한국어 문장 3~4개로 요약하세요.

이번에 검증한 전체 항목({len(all_labels)}개): {', '.join(all_labels)}
{ai_coverage_note}
규칙:
- 첫 문장은 몇 개 항목을 검증했는지 간단히 언급하세요.
- 목록에 없는 내용을 지어내지 마세요(추론 금지, 있는 내용만 요약).
- 가장 시급하거나 법적으로 중요해 보이는 문제부터 언급하세요.
- 문제 목록에 "(근거: 「...」)" 형태로 법령·고시 근거가 적혀 있으면, 요약 문장에도
  그 근거를 반드시 그대로 포함하세요(생략하거나 바꿔 쓰지 말 것 — 사용자가 어떤
  규정에 근거해 지적된 건지 알 수 있어야 합니다).
- 딱딱한 목록 나열이 아니라 자연스러운 문장으로 쓰세요.
- 마크다운이나 특수기호(*, #, - 등) 없이 순수 문장만 출력하세요.

발견된 문제 목록:
{chr(10).join(issue_lines)}
"""

    text, _reason = call_openai('검증 결과 AI요약', prompt, max_tokens=300,
                                temperature=0.2, json_mode=False)
    return text if text else fallback


def _collect_unchecked(order_result, allergen_result, name_result) -> list[dict]:
    """
    검증하지 못한 AI 항목을 [{label, reason, message}] 로 모은다.
    사용자가 "무엇이 확인됐고 무엇이 안 됐는지" 를 구분할 수 있어야 한다.
    """
    rows = []
    for result, category in (
        (order_result,    'ingredient_order'),
        (allergen_result, 'allergen'),
        (name_result,     'name_ingredient_match'),
    ):
        if result.get('checked'):
            continue
        reason = result.get('reason') or REASON_API_ERROR
        rows.append({
            'category': category,
            'label': _CATEGORY_LABELS.get(category, category),
            'reason': reason,
            'message': REASON_MESSAGES.get(reason, 'AI 검증을 확인하지 못했습니다.'),
            'system_failure': reason in SYSTEM_FAILURE_REASONS,
        })
    return rows


def run_full_review(label, user) -> dict:
    """
    라벨 등록 화면의 "AI검증" 버튼에서 호출하는 통합 검증.

    1) 캐시 조회 — 라벨 내용이 직전 요청과 동일하면 OpenAI 호출도, 일일
       사용량 차감도 없이 최근 결과를 그대로 반환한다. 사용자가 결과를
       보고 다시 눌러보는 흔한 패턴에서 할당량이 조용히 깎이지 않게 함.
    2) 일일 사용량 확인 — 캐시 미스일 때만 실제로 1회 소모한다(무료/유료
       등급별 한도, v1/label/services/ai_rate_limit.py). 한도 초과 시
       OpenAI를 아예 호출하지 않고 blocked 응답을 반환.
    3) 규칙 기반 검증(무료) + AI 원재료 순서 검증 + AI 알레르기 검증
       (성공 시 규칙 기반 키워드매칭 결과를 대체 — 부정 표현에 더 강함)
    4) 위 결과를 항목별로 묶고, 전체를 아우르는 AI 요약 문장 생성

    Returns:
        {
          'summary': str,             # AI가 만든(또는 폴백) 한글 요약 문장
          'ok': bool,                 # 전체 통과 여부
          'categories': [...],        # showValidationModal과 같은 행 구조
          'ingredient_order_checked': bool,  # AI 순서검증이 실제로 판단했는지
          'allergen_ai_checked': bool,       # 알레르기 검증이 AI로 됐는지(False면 규칙기반)
          'from_cache': bool,
          'blocked': bool,            # True면 일일 한도 초과 — 나머지 필드는 무의미
          'usage': {'daily_used', 'daily_limit', 'is_paid', 'message'},
        }
    """
    # 지연 임포트: validation_service가 이 모듈을 참조하지 않아 순환참조는
    # 없지만, 두 서비스의 책임을 명확히 분리하기 위해 여기서만 가져온다.
    from .validation_service import validate_label
    from .ai_rate_limit import get_cached_result, set_cached_result, check_rate_limit, get_usage

    cached = get_cached_result(label)
    if cached is not None:
        return {**cached, 'from_cache': True, 'blocked': False, 'usage': get_usage(user)}

    # AI 검사 셋은 전부 제품명 아니면 원재료명(표시)을 본다. 둘 다 비어 있으면
    # 셋 다 REASON_NO_INPUT 으로 되돌아오므로 OpenAI 를 부를 일이 애초에 없다.
    # 그런데도 지금까지는 일일 한도가 1회 깎였고, 필수 입력 검사가 붙은 뒤로는
    # 지적거리가 생겨 요약용 호출까지 새로 발생하게 된다. 그 전에 끊는다.
    if not (label.prdlst_nm or '').strip() and not (label.rawmtrl_nm_display or label.rawmtrl_nm or '').strip():
        rule_result = validate_label(label)
        categories = group_issues_by_category(rule_result['issues'])
        categories = [c for c in categories
                      if c['label'] not in (_CATEGORY_LABELS['ingredient_order'],
                                            _CATEGORY_LABELS['name_ingredient_match'])]
        return {
            'summary': (
                '제품명과 원재료명이 비어 있어 AI 검증을 실행하지 않았습니다'
                '(일일 사용 횟수는 차감하지 않았습니다). '
                + deterministic_summary(categories)
            ),
            'ok': all(c['ok'] for c in categories),
            'categories': categories,
            'ingredient_order_checked': False,
            'allergen_ai_checked': False,
            'name_ingredient_checked': False,
            'unchecked': [
                {'category': c, 'label': _CATEGORY_LABELS[c], 'reason': REASON_NO_INPUT,
                 'message': REASON_MESSAGES[REASON_NO_INPUT], 'system_failure': False}
                for c in ('ingredient_order', 'allergen', 'name_ingredient_match')
            ],
            'ai_extra_coverage': AI_ONLY_CATEGORIES,
            'from_cache': False,
            'blocked': False,
            'usage': get_usage(user),
        }

    allowed, usage = check_rate_limit(user)
    if not allowed:
        return {
            'summary': usage['message'], 'ok': True, 'categories': [],
            'ingredient_order_checked': False, 'allergen_ai_checked': False,
            'from_cache': False, 'blocked': True, 'usage': usage,
        }

    rule_result = validate_label(label)

    # AI 검사 셋은 서로 독립이고(요약만 이 결과들에 의존한다) DB 를 건드리지
    # 않으므로 동시에 돌린다. 순차로 돌리면 대기시간이 그대로 더해져서,
    # 하나만 느려도 전체가 웹 요청 제한(PythonAnywhere 300초)에 걸린다.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            'order':    pool.submit(check_ingredient_order, label),
            'allergen': pool.submit(check_allergens_ai, label),
            'name':     pool.submit(check_name_ingredient_match_ai, label),
        }
        def _resolve(key, empty):
            try:
                return futures[key].result()
            except Exception:
                logger.exception('[AI검증] %s 검사 실패', key)
                return empty

        order_result       = _resolve('order', {'checked': False, 'ok': True, 'items': [],
                                                'issues': [], 'reason': REASON_API_ERROR})
        allergen_ai_result = _resolve('allergen', {'checked': False, 'issues': [],
                                                   'reason': REASON_API_ERROR})
        name_match_result  = _resolve('name', {'checked': False, 'issues': [],
                                               'reason': REASON_API_ERROR})

    rule_issues = list(rule_result['issues'])
    if allergen_ai_result['checked']:
        # AI 알레르기 검증이 성공하면 규칙 기반(키워드 단순매칭) allergen
        # 이슈를 AI 결과로 교체 — 두 결과를 같이 보여주면 오히려 혼란만 줌
        rule_issues = [i for i in rule_issues if i.get('category') != 'allergen']
        rule_issues += allergen_ai_result['issues']

    all_issues = rule_issues + list(order_result['issues']) + list(name_match_result['issues'])
    categories = group_issues_by_category(all_issues)

    # AI가 판단하지 못한 항목(% 정보 부족, 제품명/원재료명 미입력 등)은
    # 목록에서 빼서 "적합"으로 오인되지 않게 한다.
    if not order_result['checked']:
        # AI 가 판단 못 했다고 행을 지울 때, 규칙 기반(배합비 대조) 지적까지 지우면
        # 안 된다. 실제 위반이 조용히 사라진다.
        categories = [c for c in categories
                      if c['label'] != _CATEGORY_LABELS['ingredient_order'] or not c['ok']]
    if not name_match_result['checked']:
        categories = [c for c in categories if c['label'] != _CATEGORY_LABELS['name_ingredient_match']]

    # 알레르기 검증이 AI로 됐으면 표에서도 구분되게 라벨 표시 (원재료 순서와 동일한 관례)
    if allergen_ai_result['checked']:
        for c in categories:
            if c['label'] == _CATEGORY_LABELS['allergen']:
                c['label'] = f"{_CATEGORY_LABELS['allergen']} (AI)"
    if order_result['checked']:
        for c in categories:
            if c['label'] == _CATEGORY_LABELS['ingredient_order']:
                c['label'] = f"{_CATEGORY_LABELS['ingredient_order']} (AI 문구분석 포함)"

    summary = generate_summary(categories, ai_only_checked=(order_result['checked'] or name_match_result['checked']))

    result = {
        'summary': summary,
        # categories가 이미 (알레르기 AI 대체 포함) 최종 병합된 issue 집합을
        # 반영하므로, 그 기준으로 전체 통과 여부를 계산하는 게 가장 정확하다.
        'ok': all(c['ok'] for c in categories),
        'categories': categories,
        'ingredient_order_checked': order_result['checked'],
        'allergen_ai_checked': allergen_ai_result['checked'],
        'name_ingredient_checked': name_match_result['checked'],
        # 검증하지 못한 항목과 그 사유. 화면이 "확인하지 못했다" 를 사실대로
        # 말할 수 있게 한다 — 예전에는 원인과 무관하게 "함량(%)이 명시돼 있지
        # 않아서" 라고만 안내해서 API 가 죽어도 사용자 입력 탓으로 보였다.
        'unchecked': _collect_unchecked(order_result, allergen_ai_result, name_match_result),
        'ai_extra_coverage': AI_ONLY_CATEGORIES,  # 규정만 검증에는 없는, AI검증만의 확인 항목
        'from_cache': False,
        'blocked': False,
        'usage': usage,
    }
    set_cached_result(label, result)
    return result
