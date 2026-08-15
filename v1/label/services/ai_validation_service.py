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

logger = logging.getLogger(__name__)

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
                    f"앞에 있지만 함량은 더 적습니다."
                ),
                'suggestion': '원재료는 사용된 함량(배합비율)이 많은 순서대로 표시해야 합니다. 순서를 바꿔주세요.',
            })

    return {'checked': True, 'ok': len(issues) == 0, 'items': items, 'issues': issues}


def _group_by_category(issues: list[dict]) -> list[dict]:
    """
    validate_label()/check_ingredient_order()가 내는 flat한 issue 목록을
    showValidationModal()과 같은 "검증 항목별 행" 구조로 묶는다.
    항목에 issue가 하나도 없으면 ok=True인 빈 행으로 표시(적합 표시용).
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
    검증 결과 전체를 사람이 읽기 좋은 한글 요약 문장 2~3개로 압축한다.

    OpenAI 미설정/호출 실패 시에도 항상 뭔가는 보여줘야 하므로, 결정론적
    폴백 요약("N개 항목에서 확인 필요: ...")을 우선 만들어두고, AI 호출이
    성공하면 그걸 조금 더 읽기 좋은 문장으로 다듬은 결과로 교체한다.
    AI가 실패해도 화면이 빈 채로 뜨는 일은 없다.
    """
    problem_rows = [r for r in category_results if not r['ok']]

    if not problem_rows:
        return '검증 결과 확인된 문제가 없습니다. 모든 항목이 표시 규정에 적합합니다.'

    fallback = (
        f"{len(problem_rows)}개 항목에서 확인이 필요합니다: "
        + ', '.join(r['label'] for r in problem_rows) + '.'
    )

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

    prompt = f"""아래는 식품 표시사항(라벨) 검증에서 발견된 문제 목록입니다.
이 내용을 식품 라벨을 처음 만들어보는 담당자도 이해할 수 있도록,
자연스러운 한국어 문장 2~3개로 요약하세요.

규칙:
- 목록에 없는 내용을 지어내지 마세요(추론 금지, 있는 내용만 요약).
- 가장 시급하거나 법적으로 중요해 보이는 문제를 먼저 언급하세요.
- 딱딱한 목록 나열이 아니라 자연스러운 문장으로 쓰세요.
- 마크다운이나 특수기호(*, #, - 등) 없이 순수 문장만 출력하세요.

문제 목록:
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


def run_full_review(label) -> dict:
    """
    라벨 등록 화면의 "AI검증" 버튼에서 호출하는 통합 검증.

    1) 규칙 기반 검증(validation_service.validate_label) — 무료·즉시
    2) AI 원재료 순서 검증(check_ingredient_order) — 이 파일럿 하나만 AI 사용
    3) 위 결과를 항목별로 묶고, 전체를 아우르는 AI 요약 문장 생성

    Returns:
        {
          'summary': str,             # AI가 만든(또는 폴백) 한글 요약 문장
          'ok': bool,                 # 전체 통과 여부
          'categories': [...],        # showValidationModal과 같은 행 구조
          'ingredient_order_checked': bool,  # AI 순서검증이 실제로 판단했는지
        }
    """
    # 지연 임포트: validation_service가 이 모듈을 참조하지 않아 순환참조는
    # 없지만, 두 서비스의 책임을 명확히 분리하기 위해 여기서만 가져온다.
    from .validation_service import validate_label

    rule_result = validate_label(label)
    order_result = check_ingredient_order(label)

    all_issues = list(rule_result['issues']) + list(order_result['issues'])
    categories = _group_by_category(all_issues)

    # AI 순서검증을 판단하지 못한 경우(% 정보 부족 등) 목록에서 빼서
    # "적합"으로 오인되지 않게 한다.
    if not order_result['checked']:
        categories = [c for c in categories if c['label'] != _CATEGORY_LABELS['ingredient_order']]

    summary = generate_summary(categories)

    return {
        'summary': summary,
        'ok': rule_result['ok'] and order_result['ok'],
        'categories': categories,
        'ingredient_order_checked': order_result['checked'],
    }
