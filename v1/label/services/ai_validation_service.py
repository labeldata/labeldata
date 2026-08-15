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

from django.conf import settings

logger = logging.getLogger(__name__)


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
