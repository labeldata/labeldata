"""
표시사항(MyLabel) 서버측 검증 서비스.

지금까지 검증(label_preview.js, ~4,500줄)이 브라우저 JS에만 있어서
사용자가 API를 직접 호출하면 검증을 건너뛰고 저장할 수 있는 신뢰
경계 문제가 있었다. 이 모듈은 그중 핵심 규칙을 서버에서 재실행해
검증 API(v1/label/views.py의 validate_label_server)로 노출한다.

클라이언트 검증(label_preview.js)은 즉각적인 UX 피드백용으로 계속
쓰고, 이 모듈은 "신뢰할 수 있는 최종 판정"용이다 — 클라이언트 로직을
전부 대체하는 게 아니라, 우회 가능한 지점을 서버에서 다시 확인한다.

포팅 범위 (1차): 내용량 단위, 농수산물 함량 표시, 금지 문구,
알레르기 표시, 분리배출마크 호환성, 원산지 미표시.
미포함(추후 별도 작업): 식품유형별 필수문구(냉동/냉장 조건 등),
소비기한 권장값 비교 — DOM/window 전역 상태에 강하게 결합돼 있어
서버 로직으로 안전하게 재현하려면 별도 검증이 필요하다.
"""
import re

from django.core.cache import cache

from v1.label.constants import (
    FARM_SEAFOOD_ITEMS,
    FORBIDDEN_PHRASES,
    ALLERGEN_KEYWORDS,
    RECYCLING_MARK_MATERIAL_KEYWORDS,
)

_FARM_SEAFOOD_CACHE_KEY = 'label_validation:farm_seafood_items'
_FARM_SEAFOOD_CACHE_TTL = 60 * 60 * 6  # 6시간 — 매 검증마다 DB를 안 때리기 위한 캐시


def _get_farm_seafood_items() -> list[str]:
    """
    원산지 표시대상 판정용 농수산물 명칭 목록.

    AgriculturalProduct DB(9천여 건, 수시 갱신)와 constants.py의
    FARM_SEAFOOD_ITEMS(하드코딩)를 합집합으로 병합해서 쓴다 — 실제
    데이터를 대조해보니 DB 테이블은 이름과 달리 "농산물"(작물)
    위주이고 쇠고기·돼지고기·닭고기 같은 축산물 항목이 전혀 없어서,
    DB로 통째 교체하면 육류 원산지 검증이 조용히 빠지는 회귀가
    생긴다. 하드코딩 목록이 커버하는 축산물·건해산물 등을 안전망으로
    유지하면서 DB의 훨씬 넓은 작물 커버리지를 추가로 얻는 방식.
    DB 조회 실패 시에는 하드코딩 목록만으로 폴백.
    """
    cached = cache.get(_FARM_SEAFOOD_CACHE_KEY)
    if cached is not None:
        return cached

    items = set(FARM_SEAFOOD_ITEMS)
    try:
        from v1.label.models import AgriculturalProduct
        db_names = (
            AgriculturalProduct.objects
            .exclude(rprsnt_rawmtrl_nm__isnull=True)
            .exclude(rprsnt_rawmtrl_nm='')
            .values_list('rprsnt_rawmtrl_nm', flat=True)
            .distinct()
        )
        items.update(db_names)
    except Exception:
        pass  # DB 미연결/테이블 없음 등 — 하드코딩 목록만으로 유지

    items = list(items)
    cache.set(_FARM_SEAFOOD_CACHE_KEY, items, _FARM_SEAFOOD_CACHE_TTL)
    return items

_CONTENT_WEIGHT_UNIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s?(mg|g|kg|ml|l)(?![a-zA-Z])', re.IGNORECASE)

_FIELD_LABELS = {
    'prdlst_nm': '제품명',
    'ingredient_info': '특정성분 함량',
    'rawmtrl_nm_display': '원재료명',
    'cautions': '주의사항',
    'additional_info': '기타표시사항',
}

_NATURAL_CONDITIONS_KO = (
    '사용 조건: '
    '① 원료 중에 합성향료·합성착색료·방부제 등 어떠한 인공 화학 성분도 전혀 포함되어 있지 않아야 함 '
    '② 최소한의 물리적 가공(세척·절단·동결·건조 등)만 거친 상태여야 함 '
    '③ "천연"과 유사한 의미로 오인될 수 있는 "자연산(naturel)" 등의 외국어 사용도 동일 기준 적용 '
    '④ 식품유형별로 별도 금지 사항(「식품등의 표시기준」의 개별 고시 규정)이 있는 경우, 그 규정에 따라 추가 제한이 있음 '
    '⑤ 예: 설탕에는 "천연설탕"이라는 표현이 불가 '
    '⑥ 영업소 명칭 또는 등록상표에 포함된 경우는 허용 '
    '⑦ "천연향료" 등 고시된 허용 목록 내 용어만 예외적으로 허용'
)
_NATURE_CONDITIONS_KO = (
    '사용 조건: '
    '① "자연"이라는 용어는 가공되지 않은 농산물·임산물·수산물·축산물에 대해서만 허용 '
    '② 수확하여 세척·포장만 거친 원물(raw agricultural/seafood/livestock products)에만 허용 '
    '③ 이미 "가공식품"으로 분류된 상태라면 "자연" 표기가 불가능 '
    '④ 유전자변형식품, 나노식품 등은 "자연" 표기가 금지됨 '
    '⑤ 영업소 명칭 또는 등록상표에 포함된 경우는 허용 '
    '⑥ 단, 제품명(product name) 자체에 "천연"·"자연"을 붙일 수는 없음'
)


# 검증 항목별 법적 근거. 정확성이 확인된 조항 번호(제4조/제6조/제8조)는 이 파일이
# 아니라 label_preview.js에 원래 있던 것을 그대로 재사용한 값이고, 나머지는 조항
# 번호까지 특정하면 오히려 틀릴 위험이 있어 법령명 단위로만 인용한다(2026-08 확인).
_LEGAL_BASIS = {
    'content_weight': '「식품등의 표시기준」 내용량 표시 규정',
    'farm_seafood': '「식품등의 표시기준」 제품명에 사용한 원재료의 함량 표시 규정',
    'forbidden_phrase': '「식품등의 표시기준」 제8조(부당한 표시·광고 금지)',
    'allergen': '「식품등의 표시기준」 알레르기 유발물질 표시 규정',
    'recycling_mark': '「자원의 절약과 재활용촉진에 관한 법률 시행규칙」 분리배출 표시 기준',
    'origin_missing': '「농수산물의 원산지 표시 등에 관한 법률」 및 같은 법 시행령(배합비율 기준 원산지 표시대상)',
}


def _issue(category: str, message: str, suggestion: str = '') -> dict:
    basis = _LEGAL_BASIS.get(category)
    full_message = f'{message} (근거: {basis})' if basis else message
    return {'category': category, 'message': full_message, 'suggestion': suggestion, 'legal_basis': basis}


def check_content_weight(label) -> list[dict]:
    """내용량에 단위(mg/g/kg/ml/l)가 포함돼 있는지 확인."""
    content_weight = (label.content_weight or '').strip()
    if not content_weight:
        return []
    if _CONTENT_WEIGHT_UNIT_RE.search(content_weight):
        return []
    return [_issue(
        'content_weight',
        '내용량에 올바른 단위가 누락되었습니다.',
        '내용량 필드에 mg, g, kg, ml, l 중 하나의 단위를 포함해주세요. (예: 500g, 1L, 250ml)',
    )]


def check_farm_seafood_content(label) -> list[dict]:
    """제품명에 포함된 농수산물의 함량이 특정성분 함량 항목에 표시돼 있는지 확인."""
    product_name = label.prdlst_nm or ''
    ingredient_info = label.ingredient_info or ''
    if not product_name:
        return []

    found_items = sorted(
        (item for item in _get_farm_seafood_items() if item in product_name),
        key=len, reverse=True,
    )
    issues = []
    for item in found_items:
        pattern = re.compile(re.escape(item) + r'[^,]*\d+(?:\.\d+)?\s*%')
        if not pattern.search(ingredient_info):
            issues.append(_issue(
                'farm_seafood',
                f"제품명에 사용된 '{item}'의 함량이 '특정성분 함량' 항목에서 확인되지 않습니다.",
                f'특정성분 함량 항목에 함량(%)을 표시하세요. (예: {item} 100%)',
            ))
    return issues


def check_forbidden_phrases(label) -> list[dict]:
    """제품명/원재료명 등 5개 필드에서 사용 금지 문구('천연', '자연' 등) 검출."""
    issues = []
    for field, field_label in _FIELD_LABELS.items():
        value = getattr(label, field, '') or ''
        for phrase in FORBIDDEN_PHRASES:
            if not re.search(re.escape(phrase), value, re.IGNORECASE):
                continue

            message = f'"{field_label}" 항목에 사용 금지 문구 "{phrase}"가 표시되어 있습니다.'
            if field == 'rawmtrl_nm_display' and phrase == '천연':
                suggestion = f'"{field_label}" 항목에 "{phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요. {_NATURAL_CONDITIONS_KO}'
            elif field == 'rawmtrl_nm_display' and phrase == '자연':
                suggestion = f'"{field_label}" 항목에 "{phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요. {_NATURE_CONDITIONS_KO}'
            else:
                suggestion = f'"{field_label}"에서 "{phrase}" 문구를 삭제하세요.'
            issues.append(_issue('forbidden_phrase', message, suggestion))
    return issues


def check_allergens(label) -> list[dict]:
    """
    원재료명(rawmtrl_nm_display)에서 검출되는 알레르기 성분과, 라벨에 실제로
    선언된 알레르기 성분(label.allergens)을 대조한다.
    - 원재료명에서 검출됐는데 선언 안 된 경우: 누락 경고
    - 선언은 했는데 원재료명에서 근거를 못 찾은 경우: 과다선언 안내(정보성, 낮은 확신도)
    """
    ingredients_text = label.rawmtrl_nm_display or label.rawmtrl_nm or ''
    if not ingredients_text:
        return []

    declared = {
        a.strip() for a in re.split(r'[,、，]', label.allergens or '')
        if a.strip()
    }

    detected = set()
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        if any(kw.lower() in ingredients_text.lower() for kw in keywords):
            detected.add(allergen)

    missing = detected - declared
    issues = []
    if missing:
        issues.append(_issue(
            'allergen',
            f'원재료명에서 알레르기 유발요소로 보이는 성분이 검출됐지만 알레르기 표시에 선언되지 않았습니다: {", ".join(sorted(missing))}',
            '원재료명을 확인해 실제로 사용된 원료라면 알레르기 표시 항목에 추가하세요.',
        ))
    return issues


def check_recycling_mark(label) -> list[dict]:
    """선택된 분리배출마크가 실제 포장재질과 호환되는지 확인."""
    package_material = (label.frmlc_mtrqlt or '').strip().lower()
    selected_mark = (label.prv_recycling_mark_type or '').strip()

    if not package_material or not selected_mark or selected_mark == '미표시':
        return []

    if selected_mark == '종이':
        compatible = ('종이' in package_material or 'paper' in package_material) and '팩' not in package_material
    elif selected_mark == '일반팩':
        compatible = '팩' in package_material and '멸균' not in package_material
    elif selected_mark == '멸균팩':
        compatible = '멸균' in package_material and '팩' in package_material
    else:
        keywords = RECYCLING_MARK_MATERIAL_KEYWORDS.get(selected_mark)
        compatible = any(kw in package_material for kw in keywords) if keywords else True  # 매핑 없는 마크는 통과(추천 로직 미포함)

    if compatible:
        return []
    return [_issue(
        'recycling_mark',
        f'포장재질("{label.frmlc_mtrqlt}")과 분리배출마크("{selected_mark}")가 일치하지 않습니다.',
        '사용된 포장재질과 분리배출마크를 재확인하세요.',
    )]


def check_origin_missing(label) -> list[dict]:
    """
    원재료명 초안 작성 시 자동 삽입되는 "(원산지 미표시)" placeholder가
    아직 남아있는지 확인 (ingredient_popup.js의 원산지 자리표시자 기능과 연동).
    """
    text = label.rawmtrl_nm_display or label.rawmtrl_nm or ''
    count = text.count('(원산지 미표시)')
    if count == 0:
        return []
    return [_issue(
        'origin_missing',
        f'원재료명에 원산지가 기재되지 않은 항목이 {count}건 있습니다.',
        '"(원산지 미표시)"로 표시된 위치에 실제 원산지를 입력하세요.',
    )]


_CHECKS = [
    check_content_weight,
    check_farm_seafood_content,
    check_forbidden_phrases,
    check_allergens,
    check_recycling_mark,
    check_origin_missing,
]


def validate_label(label) -> dict:
    """MyLabel 인스턴스에 대해 서버측 검증 전체를 실행하고 결과를 반환한다."""
    issues = []
    for check in _CHECKS:
        issues.extend(check(label))

    return {
        'ok': len(issues) == 0,
        'issue_count': len(issues),
        'issues': issues,
        # "무엇을 검증했는지"를 통과 여부와 무관하게 명시 (근거 규정 포함)
        'checked_regulations': list(_LEGAL_BASIS.values()),
    }
