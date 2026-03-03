"""
AI 파서 (ai_parser.py)  ─ 역할: 텍스트에서 구조화된 사실 추출 (inference 금지)
─────────────────────────────────────────────────────────────────────────────
연관성 판정(내 제품과 관련 있나?)은 matcher.py(로컬)에서 처리합니다.

AI 추출 항목:
  violation_type : 위반 유형 코드 (하기 코드 중 정확히 하나)
  substances     : 텍스트에 명시된 검출 물질명 배열 (농약명·균명·중금속·첨가물 등)
  ingredients    : 텍스트에 명시된 식품 원재료 배열 (이름·원산지·제조사·식품유형)
  summary        : 50자 이내 한 줄 요약
  risk_level     : HIGH / MED / LOW

violation_type 코드표:
  pesticide    – 잔류농약 기준 초과
  microbe      – 미생물 기준 초과 (살모넬라, 황색포도상구균, 리스테리아 등)
  heavy_metal  – 중금속 기준 초과 (납, 카드뮴, 수은 등)
  additive     – 식품첨가물 기준 초과 (안식향산, 소브산, 아황산 등)
  foreign_body – 이물 혼입
  deficiency   – 성분·중량·규격 미달
  labeling     – 표시 위반 (알레르기 미표시, 한글표시 미표시 등)
  admin        – 행정처분 (무신고·무등록·폐업·시설멸실·영업정지 등)
  import_ban   – 수입금지 물질 검출 (실데나필 등 의약성분)
  recall       – 회수·폐기
  other        – 위 코드로 분류 불가
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def extract_keywords(detail_text: str, product_name: str = '') -> dict:
    """
    부적합 텍스트 → 구조화 추출 결과 dict

    Returns:
        {
          'violation_type': str,           # 위반 유형 코드
          'substances':     list[str],     # 검출된 물질명 (농약명·균명·첨가물명 등)
          'ingredients':    list[dict],    # 명시된 식품 원재료 목록
          'keywords':       list[str],     # UI 표시용 = ingredients.name + substances
          'issues':         list[dict],    # matcher 호환용 = ingredients (필드명 변환)
          'summary':        str,
          'risk_level':     str,
        }
    실패 시 빈 기본값 반환 (예외 전파 안 함)
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        logger.warning('[AI 파서] OPENAI_API_KEY 미설정 – 건너뜀')
        return _default_result()

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        logger.error('[AI 파서] openai 패키지가 설치되지 않음. pip install openai')
        return _default_result()

    combined = f"제품명: {product_name}\n\n{detail_text}" if product_name else detail_text
    truncated = combined[:4000]

    prompt = f"""다음은 식품 부적합·회수·행정처분 정보 텍스트입니다.
텍스트에 **명시적으로 쓰여진 사실만** 추출하여 아래 JSON 형식으로 응답하세요.
추론·유추·보완은 절대 금지합니다.

응답 형식:
{{
  "violation_type": "pesticide",
  "substances": ["다이아지논"],
  "ingredients": [
    {{
      "name": "시금치",
      "origin": "국내산",
      "manufacturer": null,
      "food_type": "농산물"
    }}
  ],
  "summary": "시금치에서 다이아지논 잔류농약 기준 초과",
  "risk_level": "HIGH"
}}

━━━ 추출 규칙 ━━━

[violation_type] 아래 코드 중 정확히 하나 선택:
  pesticide    잔류농약 기준 초과
  microbe      미생물 기준 초과 (살모넬라·황색포도상구균·리스테리아·대장균 등)
  heavy_metal  중금속 기준 초과 (납·카드뮴·수은·비소 등)
  additive     식품첨가물 기준 초과 (안식향산·소브산·타르색소 등)
  foreign_body 이물 혼입
  deficiency   성분·중량·용출기준 미달
  labeling     표시 위반 (알레르기 미표시·한글표시 미표시·유통기한 오표시 등)
  admin        행정처분 (무신고·무등록·폐업·시설멸실·영업정지 등 절차 위반)
  import_ban   수입금지·의약성분 검출 (실데나필·타다라필 등)
  recall       회수·폐기
  other        위 코드로 분류 불가

[substances] 텍스트에 명시된 검출 물질명 배열 (농약명·균명·중금속명·첨가물명)
  ✅ "다이아지논", "살모넬라", "납", "소브산", "안식향산"
  ❌ 식품 원재료명은 여기 넣지 않음
  ❌ 텍스트에 없으면 반드시 []

[ingredients] 텍스트에 명시된 식품 원재료 배열
  ✅ '검사원료(수입품목)' 라인이 있으면 그것이 origin/manufacturer/food_type과 결합된 주요 원재료임
     → name = 해당 라인의 품목명(한글 우선), origin = '원산지(제조국가)' 값, manufacturer = '제조/수출회사(제조사)' 값, food_type = '품목명(식품유형)' 값
  ✅ 텍스트에 원재료명이 명시됐을 때만 추출
  ❌ 제품명·브랜드명·업체명만 있고 '검사원료' 힌트도 없으면 []
  ❌ violation_type이 admin 또는 labeling이면 반드시 []
  ❌ 텍스트에 없는 원재료명을 추론해서 채우지 말 것
  - name: 원재료명 2글자 이상 (브랜드명·제품명 금지); 수입부적합의 경우 '검사원료(수입품목)' 값 사용
  - origin / manufacturer / food_type: 텍스트에 없으면 null

[summary] 위반 사유 + 주요 원재료/물질 포함 50자 이내 요약

[risk_level]
  HIGH  병원성 미생물·금지원료·중금속·농약 기준 초과
  MED   첨가물 기준 초과·성분미달·표시위반
  LOW   무신고·무등록·행정처분·중량미달 등 단순/절차 위반

━━━ 텍스트 ━━━
{truncated}
"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.0,   # hallucination 최소화
            max_tokens=500,
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)

        # ── violation_type ────────────────────────────────────────
        VALID_VTYPES = {
            'pesticide', 'microbe', 'heavy_metal', 'additive',
            'foreign_body', 'deficiency', 'labeling', 'admin',
            'import_ban', 'recall', 'other',
        }
        vtype = str(result.get('violation_type', 'other')).strip().lower()
        if vtype not in VALID_VTYPES:
            vtype = 'other'

        # ── substances ────────────────────────────────────────────
        raw_subs = result.get('substances', [])
        substances = (
            [str(s).strip() for s in raw_subs
             if isinstance(s, str) and len(str(s).strip()) >= 2]
            if isinstance(raw_subs, list) else []
        )

        # ── ingredients → issues (matcher 호환) ──────────────────
        raw_ings = result.get('ingredients', [])
        if not isinstance(raw_ings, list):
            raw_ings = []

        # admin / labeling 은 원재료 매칭 불필요 → 강제 비움
        if vtype in ('admin', 'labeling'):
            raw_ings = []

        ingredients = []
        for item in raw_ings:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '')).strip()
            if not name or len(name) < 2:
                continue
            ingredients.append({
                'name':         name,
                'origin':       str(item.get('origin', '') or '').strip() or None,
                'manufacturer': str(item.get('manufacturer', '') or '').strip() or None,
                'food_type':    str(item.get('food_type', '') or '').strip() or None,
            })

        # matcher 기존 필드명 호환 (ingredient = name)
        issues = [
            {
                'ingredient':   ing['name'],
                'origin':       ing['origin'],
                'manufacturer': ing['manufacturer'],
                'food_type':    ing['food_type'],
            }
            for ing in ingredients
        ]

        # UI 표시용 키워드 = 원재료명 + 검출물질명
        keywords = [ing['name'] for ing in ingredients] + substances

        summary = str(result.get('summary', '')).strip()[:200]
        risk_level = str(result.get('risk_level', 'MED')).strip().upper()
        if risk_level not in ('HIGH', 'MED', 'LOW'):
            risk_level = 'MED'

        return {
            'violation_type': vtype,
            'substances':     substances,
            'ingredients':    ingredients,
            'keywords':       keywords,
            'issues':         issues,
            'summary':        summary,
            'risk_level':     risk_level,
        }

    except Exception as exc:
        logger.error(f'[AI 파서] OpenAI 호출 오류: {exc}')
        return _default_result()


def _default_result() -> dict:
    """AI 파싱 실패 시 기본값 — 모두 빈 값 (오탐지 방지)"""
    return {
        'violation_type': 'other',
        'substances':     [],
        'ingredients':    [],
        'keywords':       [],
        'issues':         [],
        'summary':        '',
        'risk_level':     'MED',
    }



