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

from django.conf import settings

from v1.label.constants import ALLERGEN_KEYWORDS

logger = logging.getLogger(__name__)

# AI가 반환할 수 있는 알레르기 표준 명칭 화이트리스트 (constants.py의 22종
# 알레르기 유발요소 카테고리와 동일 — 할루시네이션 방지용 검증에 사용)
_ALLERGEN_CATEGORY_NAMES = set(ALLERGEN_KEYWORDS.keys())

# validate_label()의 category 코드 -> 화면에 보여줄 검증 항목명
# (기존 label_preview.js showValidationModal()의 "검증 항목" 열과 같은 스타일)
_CATEGORY_LABELS = {
    'content_weight': '내용량 표시',
    'farm_seafood': '농수산물 함량 표시',
    'forbidden_phrase': '금지 문구',
    'allergen': '알레르기 표시',
    'recycling_mark': '분리배출마크',
    'origin_missing': '원산지 표시',
    'ingredient_order': '원재료 표시 순서 (AI)',
}

_INGREDIENT_ORDER_BASIS = '「식품등의 표시기준」 원재료명 표시 순서 규정(중량비율이 많은 순서로 표시)'
_ALLERGEN_BASIS = '「식품등의 표시기준」 알레르기 유발물질 표시 규정'

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


def extract_ingredient_order(rawmtrl_text: str) -> list[dict]:
    """
    원재료명 표시 텍스트에서 원재료명과 명시된 함량(%)을 등장 순서 그대로 추출.

    Returns: [{'name': str, 'percent': float | None}, ...]
    텍스트에 명시된 숫자만 사용하고 없으면 percent=None (추론 금지).
    실패 시 빈 리스트 반환(예외 전파 안 함 — ai_parser.py와 동일 원칙).
    """
    text = (rawmtrl_text or '').strip()
    if not text:
        return []

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        logger.warning('[원재료 순서 AI검증] OPENAI_API_KEY 미설정 – 건너뜀')
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        logger.error('[원재료 순서 AI검증] openai 패키지 미설치')
        return []

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

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.0,
            max_tokens=800,
        )
        result = json.loads(response.choices[0].message.content)
        raw_items = result.get('items', [])
        if not isinstance(raw_items, list):
            return []

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
        return items

    except Exception as exc:
        logger.error(f'[원재료 순서 AI검증] OpenAI 호출 오류: {exc}')
        return []


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
    items = extract_ingredient_order(label.rawmtrl_nm_display or label.rawmtrl_nm or '')
    dated = [i for i in items if i['percent'] is not None]

    if len(dated) < 2:
        return {'checked': False, 'ok': True, 'items': items, 'issues': []}

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

    return {'checked': True, 'ok': len(issues) == 0, 'items': items, 'issues': issues}


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
        return []

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        logger.warning('[알레르기 AI검증] OPENAI_API_KEY 미설정 – 건너뜀')
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        logger.error('[알레르기 AI검증] openai 패키지 미설치')
        return None

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

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.0,
            max_tokens=300,
        )
        result = json.loads(response.choices[0].message.content)
        raw = result.get('allergens', [])
        if not isinstance(raw, list):
            return []
        # 표준 22종 명칭 밖의 값(할루시네이션 방지)은 제거
        valid = {str(a).strip() for a in raw if isinstance(a, str)}
        return sorted(valid & _ALLERGEN_CATEGORY_NAMES)

    except Exception as exc:
        logger.error(f'[알레르기 AI검증] OpenAI 호출 오류: {exc}')
        return None


def check_allergens_ai(label) -> dict:
    """
    AI로 추출한 "실제 사용 알레르기 유발요소" 목록을 선언값(label.allergens)과
    대조한다. 규칙 기반 check_allergens()(단순 키워드 포함 매칭)보다 부정
    표현·오탐 문맥에 강하다. AI가 판단하지 못하면(checked=False) 호출부
    (run_full_review)가 규칙 기반 결과를 그대로 사용하도록 위임한다.
    """
    ingredients_text = label.rawmtrl_nm_display or label.rawmtrl_nm or ''
    if not ingredients_text:
        return {'checked': False, 'issues': []}

    detected = extract_allergens_ai(ingredients_text)
    if detected is None:
        return {'checked': False, 'issues': []}

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
    return {'checked': True, 'issues': issues}


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


def generate_summary(category_results: list[dict]) -> str:
    """
    검증 결과 전체를 사람이 읽기 좋은 한글 요약 문장으로 압축한다.
    어떤 항목을 검증했는지(적합 포함)와, 부적합 항목은 근거 규정과 함께
    언급하도록 해 "전문성이 느껴지지 않는다"는 문제를 해결한다.

    OpenAI 미설정/호출 실패 시에도 항상 뭔가는 보여줘야 하므로, 결정론적
    폴백 요약(검증 항목 전체 나열 + 부적합 항목 근거 규정)을 우선
    만들어두고, AI 호출이 성공하면 그걸 조금 더 읽기 좋은 문장으로
    다듬은 결과로 교체한다. AI가 실패해도 화면이 빈 채로 뜨는 일은 없다.
    """
    problem_rows = [r for r in category_results if not r['ok']]
    all_labels = [r['label'] for r in category_results]

    if not problem_rows:
        checked = ', '.join(all_labels)
        return f'{checked} 등 {len(all_labels)}개 항목을 검증한 결과 확인된 문제가 없습니다. 모두 표시 규정에 적합합니다.'

    fallback_lines = [f"검증한 {len(all_labels)}개 항목({', '.join(all_labels)}) 중 {len(problem_rows)}개에서 확인이 필요합니다."]
    for row in problem_rows:
        for err in row['errors']:
            fallback_lines.append(re.sub(r'<[^>]+>', '', err))
    fallback = ' '.join(fallback_lines)

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

    prompt = f"""아래는 식품 표시사항(라벨) 검증 결과입니다.
이 내용을 식품 라벨을 처음 만들어보는 담당자도 이해할 수 있도록,
전문적이면서도 자연스러운 한국어 문장 3~4개로 요약하세요.

이번에 검증한 전체 항목({len(all_labels)}개): {', '.join(all_labels)}

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

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        text = (response.choices[0].message.content or '').strip()
        return text if text else fallback
    except Exception as exc:
        logger.error(f'[검증 결과 AI요약] OpenAI 호출 오류: {exc}')
        return fallback


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

    allowed, usage = check_rate_limit(user)
    if not allowed:
        return {
            'summary': usage['message'], 'ok': True, 'categories': [],
            'ingredient_order_checked': False, 'allergen_ai_checked': False,
            'from_cache': False, 'blocked': True, 'usage': usage,
        }

    rule_result = validate_label(label)
    order_result = check_ingredient_order(label)
    allergen_ai_result = check_allergens_ai(label)

    rule_issues = list(rule_result['issues'])
    if allergen_ai_result['checked']:
        # AI 알레르기 검증이 성공하면 규칙 기반(키워드 단순매칭) allergen
        # 이슈를 AI 결과로 교체 — 두 결과를 같이 보여주면 오히려 혼란만 줌
        rule_issues = [i for i in rule_issues if i.get('category') != 'allergen']
        rule_issues += allergen_ai_result['issues']

    all_issues = rule_issues + list(order_result['issues'])
    categories = group_issues_by_category(all_issues)

    # AI 순서검증을 판단하지 못한 경우(% 정보 부족 등) 목록에서 빼서
    # "적합"으로 오인되지 않게 한다.
    if not order_result['checked']:
        categories = [c for c in categories if c['label'] != _CATEGORY_LABELS['ingredient_order']]

    # 알레르기 검증이 AI로 됐으면 표에서도 구분되게 라벨 표시 (원재료 순서와 동일한 관례)
    if allergen_ai_result['checked']:
        for c in categories:
            if c['label'] == _CATEGORY_LABELS['allergen']:
                c['label'] = f"{_CATEGORY_LABELS['allergen']} (AI)"

    summary = generate_summary(categories)

    result = {
        'summary': summary,
        # categories가 이미 (알레르기 AI 대체 포함) 최종 병합된 issue 집합을
        # 반영하므로, 그 기준으로 전체 통과 여부를 계산하는 게 가장 정확하다.
        'ok': all(c['ok'] for c in categories),
        'categories': categories,
        'ingredient_order_checked': order_result['checked'],
        'allergen_ai_checked': allergen_ai_result['checked'],
        'from_cache': False,
        'blocked': False,
        'usage': usage,
    }
    set_cached_result(label, result)
    return result
