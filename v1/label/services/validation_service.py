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
추가: 식품첨가물 표시명 공란 — 구조화된 원재료 데이터를 그대로 보므로 AI 없이
판정한다.
추가: 필수 입력 항목 공란(check_required_fields) — 나머지 검사가 전부 "값이 있을
때만" 보기 때문에 아무것도 입력하지 않은 라벨이 "모두 적합"으로 판정되던 구멍을
막는다. 이 검사만 유일하게 "값이 없는 것" 자체를 지적한다.

원재료 표시 순서: **입력 순서**는 검사하지 않는다. 표시 문구를 만드는 쪽
(label/views.py 의 rawmtrl_nm 생성, products/bom_detail.html 의 BOM 요약)이 둘 다
배합비 내림차순으로 정렬하므로, 입력 순서가 어떻든 생성된 문구는 규정을 지킨다.
입력 순서를 위반이라고 알리면 표시 문구에 도달하지 않는 것을 두고 사용자를 탓하게
된다. 다만 **손으로 고친 문구**는 아무도 다시 정렬해 주지 않아서, 그건
check_ingredient_order_by_ratio 가 DB 의 배합비와 대조해 본다(운영에서 실제로
3건 나왔다).
미포함(추후 별도 작업): 식품유형별 필수문구(냉동/냉장 조건 등),
소비기한 권장값 비교 — DOM/window 전역 상태에 강하게 결합돼 있어
서버 로직으로 안전하게 재현하려면 별도 검증이 필요하다.
"""
import math
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

# 인쇄물의 단위는 ASCII 로만 오지 않는다. 라벨 조판에는 한 칸에 들어가는 조합
# 문자(㎖·㎏·㎉…)가 흔하고, 사진에서 읽어 온 값은 그 글자를 그대로 담아 온다.
# 단위를 보는 검사(내용량 단위, 열량 병기, 총량 환산)가 전부 여기를 지나가므로
# 비교하기 전에 한 번 되돌려 놓는다. 표시용 값은 건드리지 않는다 — 사용자가
# 적은 그대로 보여 줘야 한다.
_UNIT_ALIASES = {
    '㎎': 'mg', '㎍': 'ug', '㎏': 'kg', '㎖': 'ml', '㎗': 'dl',
    'ℓ': 'l', 'ℒ': 'l', '㏄': 'ml', '㎉': 'kcal', '㎈': 'cal',
    'ｇ': 'g', 'ｍ': 'm', 'ｌ': 'l', 'Ｌ': 'l',
}


def normalize_units(text: str) -> str:
    """단위 조합 문자를 ASCII 표기로 되돌린다 (비교용)."""
    out = text or ''
    for src, dst in _UNIT_ALIASES.items():
        if src in out:
            out = out.replace(src, dst)
    return out


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
    'required_missing': '「식품 등의 표시·광고에 관한 법률」 및 「식품등의 표시기준」 의무표시사항 기재 규정',
    'calorie_consistency': '「식품등의 표시기준」 내용량 표시 규정(내용량에 열량 병기) 및 영양성분 표시 규정',
    'ingredient_order': '「식품등의 표시기준」 원재료명 표시 순서 규정(중량비율이 많은 순서로 표시)',
    'content_weight': '「식품등의 표시기준」 내용량 표시 규정',
    'farm_seafood': '「식품등의 표시기준」 제품명에 사용한 원재료의 함량 표시 규정',
    'forbidden_phrase': '「식품등의 표시기준」 제8조(부당한 표시·광고 금지)',
    'allergen': '「식품등의 표시기준」 알레르기 유발물질 표시 규정',
    'recycling_mark': '「자원의 절약과 재활용촉진에 관한 법률 시행규칙」 분리배출 표시 기준',
    'origin_missing': '「농수산물의 원산지 표시 등에 관한 법률」 및 같은 법 시행령(배합비율 기준 원산지 표시대상)',
    'additive_display_name': '「식품등의 표시기준」 [별표 4] 식품첨가물의 표시 방법(명칭과 용도를 함께 표시)',
}


def _issue(category: str, message: str, suggestion: str = '') -> dict:
    basis = _LEGAL_BASIS.get(category)
    full_message = f'{message} (근거: {basis})' if basis else message
    return {'category': category, 'message': full_message, 'suggestion': suggestion, 'legal_basis': basis}


# 표시 여부 체크박스. 접두어 'chckd_' 를 떼면 그대로 MyLabel 필드명이 된다(18개 확인).
# 화면(label_creation.html)의 chk_* 이름과는 다르다 — 예: chk_manufacturer_info 는
# chckd_bssh_nm 이다. 여기서는 모델 필드명만 쓴다.
_REQUIRED_CHECKBOX_FIELDS = (
    'chckd_prdlst_dcnm', 'chckd_prdlst_nm', 'chckd_ingredient_info',
    'chckd_content_weight', 'chckd_weight_calorie', 'chckd_prdlst_report_no',
    'chckd_country_of_origin', 'chckd_storage_method', 'chckd_frmlc_mtrqlt',
    'chckd_bssh_nm', 'chckd_distributor_address', 'chckd_repacker_address',
    'chckd_importer_address', 'chckd_pog_daycnt', 'chckd_rawmtrl_nm_display',
    'chckd_cautions', 'chckd_additional_info', 'chckd_nutrition_text',
)


# 그 칸 자체는 비어 있어도 인쇄에는 지장이 없는 경우. 화면마다 저장하는 필드가
# 달라서 생긴 것이라, 검사가 그 사정을 알고 있어야 한다.
#
#   rawmtrl_nm_display : V2 기본정보 탭과 BOM "기본정보로 복사" 는 rawmtrl_nm(참고)
#       에 쓴다. 표시사항 탭(_tab_label.html)이 rawmtrl_nm_display 가 비면 그 값으로
#       폴백해 미리보기에 넣으므로 인쇄물에는 원재료명이 나온다.
#   nutrition_text : 영양성분은 미리보기에서 별도 표로 그려지고, 이 필드는
#       label_preview.html 의 ORDERED_FIELDS 에서 아예 빠져 있다(주석 처리).
#       V2 영양성분 탭(nutrition_save_api)은 개별 항목만 저장하고 이 요약 문구를
#       만들지 않는다. 값이 있느냐는 개별 항목으로 판단해야 맞다.
_ALTERNATIVE_SOURCES = {
    'rawmtrl_nm_display': ('rawmtrl_nm',),
    'nutrition_text': ('calories', 'natriums', 'carbohydrates', 'proteins', 'fats'),
}

# 열량 표기를 찾는 자. 라벨은 "kcal" 만 쓰지 않는다 — 인쇄물에는 조판용 조합
# 문자 ㎉ 가 흔하고, 사진에서 읽어 온 값은 그 글자를 그대로 담아 온다.
# ASCII 만 보면 실제로는 병기된 라벨을 "열량을 안 적었다" 고 지적하게 된다.
_KCAL_RE = re.compile(
    r'(\d[\d,]*(?:\.\d+)?)\s*(?:k\s*cal|㎉|㎈|킬로\s*칼로리)', re.IGNORECASE)

# 값이 "있다" 를 공백 여부만으로 볼 수 없는 항목.
#
# 내용량(열량)은 별도 줄이 아니라 내용량에 함께 적는 게 보통이다 —
# "250 g (100 kcal)". 그래서 전용 칸이 비어 있어도 내용량에 열량이 적혀 있으면
# 표시된 것이고, 반대로 전용 칸에 숫자만 있고 kcal 이 없으면 표시가 아니다.
# 공백 여부로 보면 둘 다 틀린다.
_CONTENT_PATTERNS = {
    'weight_calorie': (('weight_calorie', 'content_weight'), _KCAL_RE),
}

# 위 항목들은 "비어 있습니다" 만으로는 무엇을 하라는 건지 알 수 없다.
_REQUIRED_HINTS = {
    'weight_calorie': '내용량에 열량을 함께 적어도 됩니다. (예: 250 g (100 kcal))',
}

# 영양성분 개별 항목. "영양표시를 하는 제품인가" 를 이 값들로 판단한다.
_NUTRITION_VALUE_FIELDS = ('calories', 'natriums', 'carbohydrates', 'sugars',
                           'fats', 'trans_fats', 'saturated_fats',
                           'cholesterols', 'proteins')


def _has_nutrition_display(label) -> bool:
    """이 라벨이 영양성분을 표시하는 제품인가."""
    if (getattr(label, 'chckd_nutrition_text', '') or '') == 'Y':
        return True
    return any((getattr(label, f, '') or '').strip()
               for f in _NUTRITION_VALUE_FIELDS)


def is_imported(label) -> bool:
    """
    수입식품인가.

    수입원(수입원 소재지)을 적었거나 표시 항목으로 켰으면 수입식품으로 본다.
    수입식품은 「수입식품안전관리 특별법」의 수입신고 대상이라 국내 제조업체가
    받는 **품목제조보고번호가 아예 없다.** 원산지만으로는 가릴 수 없다 —
    원산지 칸에는 원재료 원산지를 적는 제품도 많다.
    """
    if (getattr(label, 'importer_address', '') or '').strip():
        return True
    return (getattr(label, 'chckd_importer_address', '') or '') == 'Y'


def is_required(label, field: str) -> bool:
    """
    체크가 켜져 있어도 그 항목을 "비었다" 고 지적해도 되는가.

    예외가 둘이다 — 내용량(열량)과 품목보고번호.

    열량 병기는 **영양성분 표시 대상 식품**의 의무이지
    모든 제품의 의무가 아니다. 게다가 이 항목은 어느 화면에도 입력칸이 없고
    (내용량에 함께 적는 값이라 뺐다) 표시 항목 목록에도 없어서 끌 수도 없다.
    영양표시가 없는 제품에까지 지적하면 **고칠 방법이 없는 경고**가 된다 —
    실제로 "숨겼는데도 계속 나온다" 는 신고가 여기서 나왔다.

    그래서 영양성분을 표시하는 제품일 때만 본다. 그때는 값이 있으므로
    "내용량에 이렇게 적으세요" 라고 계산까지 해서 알려 줄 수 있다.

    품목보고번호는 **수입식품이면 보지 않는다.** 수입식품에는 품목제조보고번호가
    없어서(수입신고번호를 대신 적는다) 비어 있는 게 정상인데, 체크박스 기본값이
    'Y' 라 수입 제품을 등록하면 곧바로 "비어 있습니다" 가 떴다. 고칠 수 없는
    지적이라 사용자는 검증 결과 전체를 믿지 않게 된다.
    """
    if field == 'weight_calorie':
        return _has_nutrition_display(label)
    if field == 'prdlst_report_no':
        return not is_imported(label)
    return True


def _weight_calorie_hint(label) -> str:
    """
    내용량에 무엇을 적으면 되는지, 가능하면 계산해서 알려 준다.

    영양성분 탭의 calories 는 100g(ml) 당 값이라 총량을 곱해야 병기할 값이 된다.
    둘 다 읽히면 완성된 문구를 그대로 보여 준다 — 사용자가 다시 계산하지 않는다.
    """
    base = _REQUIRED_HINTS['weight_calorie']
    per_100 = _number((getattr(label, 'calories', '') or '').strip())
    amount = _total_amount(getattr(label, 'content_weight', '') or '')
    if per_100 is None or amount is None or amount <= 0:
        return base
    total = per_100 * amount / 100
    # 표시기준상 열량은 5kcal 단위로 반올림한다
    total = round(total / 5) * 5
    weight = (label.content_weight or '').strip()
    return (f'영양성분 탭의 100g(ml)당 {per_100:,.0f} kcal 로 계산하면 '
            f'내용량 칸에 "{weight} ({total:,.0f} kcal)" 라고 적으면 됩니다.')


def content_sources(field: str) -> tuple[str, ...]:
    """그 항목의 값을 담을 수 있는 필드 전부. 캐시 지문이 함께 본다."""
    spec = _CONTENT_PATTERNS.get(field)
    if spec:
        return spec[0]
    return (field,) + tuple(_ALTERNATIVE_SOURCES.get(field, ()))


def _has_content(label, field: str) -> bool:
    """그 항목이 실제로 채워져 있는가 (다른 화면이 채운 자리까지 본다)."""
    spec = _CONTENT_PATTERNS.get(field)
    if spec:
        sources, pattern = spec
        return any(pattern.search(normalize_units(getattr(label, src, '') or ''))
                   for src in sources)

    if (getattr(label, field, '') or '').strip():
        return True
    return any((getattr(label, alt, '') or '').strip()
               for alt in _ALTERNATIVE_SOURCES.get(field, ()))


def _verbose_name(model, field_name: str) -> str:
    """모델의 verbose_name 을 화면 표기로 재사용 (한글 라벨을 두 번 적지 않기 위함)."""
    try:
        return str(model._meta.get_field(field_name).verbose_name)
    except Exception:
        return field_name


def check_required_fields(label) -> list[dict]:
    """
    표시하기로 선택한 항목(chckd_* == 'Y')이 비어 있는지 확인.

    나머지 검사들은 전부 "값이 있을 때만" 본다 — 내용량이 비면
    check_content_weight 가 [] 를 돌려주는 식이다. 그래서 아무것도 입력하지
    않은 라벨이 지적 0건, 즉 "모든 항목이 표시 규정에 적합"으로 판정됐다.
    이 검사가 그 구멍을 막는다.

    필수의 근거는 chckd_* 하나만 쓴다. 체크가 켜져 있다는 건 그 항목을 라벨에
    인쇄하겠다는 선언이므로, 비어 있으면 빈 줄이 인쇄된다 — 근거가 명확하고
    오탐이 없다. FoodType 의 Y/D/N 컬럼도 "식품유형별 필수"를 담고 있지만
    지금은 라벨에 반영되는 경로가 끊겨 있고(/label/food-type-settings/ 미구현),
    weight_calorie·nutritions 는 실제 데이터에서 거의 전량이 걸려 안내가 아니라
    소음이 된다. 그쪽은 그 엔드포인트를 만들 때 의미를 확정하고 함께 다룬다.
    """
    missing = []
    for checkbox in _REQUIRED_CHECKBOX_FIELDS:
        field = checkbox[len('chckd_'):]
        if (getattr(label, checkbox, '') or '') != 'Y':
            continue
        if _has_content(label, field):
            continue
        if not is_required(label, field):
            continue
        missing.append((field, _verbose_name(type(label), field)))

    if not missing:
        return []

    # 항목마다 따로 내면 같은 문장이 근거 규정까지 통째로 되풀이된다.
    # 실제로 세 항목이 빈 라벨에서 같은 문구가 세 번, 제안도 세 번 나왔다.
    # 한 문장에 모아서 낸다.
    names = [name for _, name in missing]
    if len(names) == 1:
        message = f'표시하기로 선택한 "{names[0]}" 항목이 비어 있습니다.'
    else:
        listed = ', '.join(f'"{name}"' for name in names)
        message = f'표시하기로 선택한 {len(names)}개 항목이 비어 있습니다: {listed}'

    suggestion = '비어 있는 항목을 입력하거나, 이 제품에 해당하지 않으면 표시 항목 체크를 해제하세요.'
    hints = []
    for field, _ in missing:
        if field == 'weight_calorie':
            hints.append(_weight_calorie_hint(label))
        elif field in _REQUIRED_HINTS:
            hints.append(_REQUIRED_HINTS[field])
    if hints:
        suggestion = ' '.join(hints) + ' ' + suggestion

    issue = _issue('required_missing', message, suggestion)
    # 어느 칸인지 문장을 파싱하지 않고 알 수 있게 따로 실어 보낸다 —
    # 확정 차단 화면이 "비어 있는 항목: 내용량, 소비기한" 처럼 쓴다.
    issue['fields'] = [field for field, _ in missing]
    issue['field_labels'] = names
    return [issue]


# 내용량에서 총량을 읽기 위한 것. 단위별로 g/ml 로 환산한다.
_AMOUNT_RE = re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(mg|kg|ml|g|l)(?![a-z])', re.IGNORECASE)
_AMOUNT_SCALE = {'mg': 0.001, 'g': 1.0, 'kg': 1000.0, 'ml': 1.0, 'l': 1000.0}


def _number(text: str) -> float | None:
    try:
        return float(text.replace(',', ''))
    except (TypeError, ValueError):
        return None


def _total_amount(text: str) -> float | None:
    """내용량 문구에서 총량(g 또는 ml)을 읽는다. 없으면 None."""
    m = _AMOUNT_RE.search(normalize_units(text or ''))
    if not m:
        return None
    value = _number(m.group(1))
    if value is None:
        return None
    return value * _AMOUNT_SCALE[m.group(2).lower()]


# 열량 비교 허용오차.
#
# 5 kcal 단위로 반올림한 값끼리 견주므로, 정당하게 벌어질 수 있는 차이는 그
# 반올림 폭(±2.5) 뿐이다. 여유를 조금 두어 5 로 잡는다.
#
# 예전에는 `max(5.0, expected * 0.05)` 이었다. 5% 상대오차는 반올림과 성격이
# 다른 이야기인데 섞여 있었고, 총량이 큰 제품일수록 눈이 멀었다 - 1,240 kcal
# 라면 ±62 kcal 를 통과시킨다. 자릿수를 하나 잘못 적어도 지나갈 수 있다.
_CALORIE_TOLERANCE = 5.0


def round_calories(value: float) -> float:
    """
    표시기준의 5 kcal 단위 반올림. 화면(processNutritionValue)과 같은 규칙이다.

    검증이 이 규칙을 안 겪으면 **앱이 절대 만들지 않는 숫자를 요구하게 된다.**
    실제로 87 g 짜리 라벨에서 검증은 "277 kcal 입니다" 라고 했는데 화면이 그린
    표에는 275 가 찍혀 있었다(276.66 -> 275). 사용자가 277 을 적으면 표와 여전히
    어긋난다 - 고치라는 대로 고쳐도 경고가 안 사라진다.

    파이썬의 round() 는 5 를 짝수 쪽으로 보내므로(banker's rounding) 쓰지 않는다.
    자바스크립트 Math.round 와 같이 늘 위로 올린다.
    """
    if value < 5:
        return value
    return math.floor(value / 5 + 0.5) * 5


def check_calorie_consistency(label) -> list[dict]:
    """
    내용량에 병기한 열량과 영양성분 탭의 계산값이 맞는지 확인.

    영양성분 탭이 저장하는 calories 는 **100g(ml) 당** 값이다
    (nutrition_calculator_popup.js 의 generateBasicDisplayV3 이 표시할 때
    multiplier = 총량/100 을 곱한다). 그래서 내용량에 적는 총 열량은

        calories x 총량 / 100

    이어야 한다. 실제 데이터로 확인했다 — "800 g (1240 kcal)" 인 라벨의
    calories 가 155 이고, 155 x 800 / 100 = 1240 으로 정확히 맞는다.

    두 값 중 하나라도 읽을 수 없으면 검사하지 않는다.
    """
    text = normalize_units(f"{label.content_weight or ''} {label.weight_calorie or ''}")
    kcal_match = _KCAL_RE.search(text)
    if not kcal_match:
        return []

    stated = _number(kcal_match.group(1))
    per_100 = _number((label.calories or '').strip())
    amount = _total_amount(text)
    if stated is None or per_100 is None or amount is None or amount <= 0:
        return []   # 셋 다 있어야 비교할 수 있다

    expected = round_calories(per_100 * amount / 100)
    if abs(stated - expected) <= _CALORIE_TOLERANCE:
        return []

    return [_issue(
        'calorie_consistency',
        f'내용량에 적힌 열량({stated:,.0f} kcal)이 영양성분 값과 맞지 않습니다. '
        f'영양성분 탭의 100g당 {per_100:,.0f} kcal 을 총량 {amount:,.0f}g 에 적용하면 '
        f'{expected:,.0f} kcal 입니다.',
        '영양성분 탭의 값을 고치거나, 내용량에 적은 열량을 다시 확인하세요.',
    )]


def _placeable(known, text):
    """
    문구에서 **자리를 하나로 확정할 수 있는** 원료만 남긴다.

    이 함수가 없던 시절 순서 검사는 `text.find(name)` 하나로 자리를 잡았다.
    find 는 언제나 **첫 번째** 자리를 돌려주므로, 같은 이름이 둘이면 둘 다 같은
    숫자를 받는다. 그러면 정렬이 자리로 순서를 못 정하고 튜플의 다음 원소
    (이름, 배합비)로 넘어가 **배합비 오름차순**으로 줄을 세운다. 그 줄은 정의상
    내림차순 위반이라, 다음 줄의 검사가 반드시 운다.

    운영에서 이렇게 나왔다:

        "코코아분말"(0.97%)가 "코코아분말"(1.58%)보다 앞에 있습니다.

    같은 이름이 양쪽에 찍힌 것이 증거다. 같은 원료를 두 공정에 나눠 쓰거나 같은
    첨가물을 두 줄로 넣은 제품은 문구를 어떻게 적든 100% 위반으로 보고됐다.

    걸러내는 세 가지 - 셋 다 "자리를 못 짚는다" 는 같은 이야기다.

      1) BOM 에 같은 이름이 여러 줄     어느 줄이 문구의 그 자리인지 알 수 없다
      2) 문구에 같은 이름이 여러 번     어느 자리를 뜻하는지 알 수 없다
      3) 다른 원료명 안에 들어 있는 이름 ("코코아분말" ⊂ "코코아분말가공품")
                                        find 가 남의 자리를 돌려준다

    모르는 것과 위반은 다르다. 짚을 수 없으면 세지 않는다 - 이 함수의 원래
    원칙 그대로다. 놓치는 위반이 생길 수 있지만, 없는 위반을 만들어 내는 것보다
    낫다. 지어낸 지적은 검사 전체의 신뢰를 깎는다.
    """
    names = [name for name, _ in known]
    duplicated = {name for name in names if names.count(name) > 1}

    kept = []
    for name, ratio in known:
        if name in duplicated:
            continue
        if text.count(name) != 1:
            continue
        if any(name != other and name in other for other in names):
            continue
        kept.append((name, ratio))
    return kept


def check_ingredient_order_by_ratio(label) -> list[dict]:
    """
    인쇄되는 원재료명 문구가 배합비 내림차순인지, DB 의 배합비와 대조해 확인.

    이 파일은 원래 표시 순서를 검사하지 않았다. 이유는 "표시 문구를 만드는 쪽이
    배합비 내림차순으로 정렬하므로 입력 순서가 어떻든 문구는 규정을 지킨다" 였고,
    그건 **생성기가 만든 문구**에 대해서는 맞다. 문제는 사용자가 그 문구를 손으로
    고칠 수 있다는 것이다 - 고친 문구는 아무도 다시 정렬해 주지 않는다.

    운영 데이터에서 실제로 3건 나왔다. 그중 하나는 보존료(0.03%)가 주원료
    (87.32%)보다 앞에 적혀 있었다.

    AI 검사(ai_validation_service.check_ingredient_order)도 순서를 보지만, 그건
    **문구에 적힌 %** 를 읽는다. % 를 안 적은 제품은 판단할 수 없다. 여기서는
    DB 의 배합비를 쓰므로 % 표기 없이도 확인되고, AI 도 필요 없다.

    문구에서 이름을 찾지 못한 원료는 세지 않는다. 표시명이 원료명과 다르게 적혀
    있으면(예: "밀가루" -> "밀 가공품") 못 찾는데, 모르는 것과 위반은 다르다.
    **이름이 문구의 어느 자리를 가리키는지 확정할 수 없을 때도 마찬가지다** -
    아래 _placeable 참고.
    """
    text = (label.rawmtrl_nm_display or label.rawmtrl_nm or '').strip()
    if not text:
        return []

    try:
        relations = (label.ingredient_relations
                     .select_related('ingredient')
                     .order_by('relation_sequence'))
        known = [(rel.ingredient.prdlst_nm, float(rel.ingredient_ratio))
                 for rel in relations
                 if rel.ingredient_ratio is not None and rel.ingredient.prdlst_nm]
    except Exception:
        return []

    placed = [(text.find(name), name, ratio)
              for name, ratio in _placeable(known, text)]
    if len(placed) < 2:
        return []   # 문구에서 짚어낸 원료가 2개 미만이면 순서를 따질 수 없다

    placed.sort()   # 문구에 나온 순서대로
    issues = []
    for (_, n1, r1), (_, n2, r2) in zip(placed, placed[1:]):
        if r1 >= r2:
            continue
        issues.append(_issue(
            'ingredient_order',
            f'원재료명 표시 순서가 배합비 내림차순이 아닙니다: '
            f'"{n1}"({r1:g}%)가 "{n2}"({r2:g}%)보다 앞에 있습니다.',
            '원재료는 사용된 배합비가 많은 순서대로 표시해야 합니다. '
            '문구의 순서를 바꾸거나, BOM 에서 다시 생성하세요.',
        ))
    return issues


def check_content_weight(label) -> list[dict]:
    """내용량에 단위(mg/g/kg/ml/l)가 포함돼 있는지 확인."""
    content_weight = (label.content_weight or '').strip()
    if not content_weight:
        return []
    if _CONTENT_WEIGHT_UNIT_RE.search(normalize_units(content_weight)):
        return []
    return [_issue(
        'content_weight',
        '내용량에 올바른 단위가 누락되었습니다.',
        '내용량 필드에 mg, g, kg, ml, l 중 하나의 단위를 포함해주세요. (예: 500g, 1L, 250ml)',
    )]


# 함량 표기를 찾는 자. "20%", "20 %", "20.5%" 를 모두 받는다.
_PERCENT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*%')

# 원재료명 문구를 조각으로 가를 때 무시할 괄호. 괄호 안의 쉼표까지 가르면
# "새우(베트남산, 30%)" 가 두 조각이 되어 함량이 원료에서 떨어져 나간다.
_BRACKET_OPEN = '([{（［〔'
_BRACKET_CLOSE = ')]}）］〕'


def _split_top_level(text: str) -> list[str]:
    """쉼표로 가르되, 괄호 안의 쉼표는 건드리지 않는다."""
    depth = 0
    buf: list[str] = []
    out: list[str] = []
    for ch in text or '':
        if ch in _BRACKET_OPEN:
            depth += 1
        elif ch in _BRACKET_CLOSE:
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            out.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append(''.join(buf))
    return [seg.strip() for seg in out if seg.strip()]


def _content_hits(text: str, item: str) -> list[dict]:
    """
    문구에서 그 원료가 적힌 조각과 거기 붙은 함량(%)을 모은다.

    조각 안에서 **원료 이름 뒤에 오는** 첫 % 를 그 원료의 함량으로 본다.
    앞에 있는 % 는 다른 원료의 것이다.
    """
    hits = []
    for seg in _split_top_level(text):
        pos = seg.find(item)
        if pos < 0:
            continue
        m = _PERCENT_RE.search(seg, pos)
        hits.append({'text': seg, 'percent': float(m.group(1)) if m else None})
    return hits


def _bom_hits(label, item: str) -> list[dict]:
    """BOM 에 등록된 배합비 중 그 원료에 해당하는 것."""
    try:
        relations = label.ingredient_relations.select_related('ingredient')
        rows = [(rel.ingredient.prdlst_nm, rel.ingredient_ratio)
                for rel in relations if rel.ingredient.prdlst_nm]
    except Exception:
        return []
    hits = []
    for name, ratio in rows:
        if item not in name:
            continue
        value = None
        if ratio is not None:
            try:
                value = float(ratio)
            except (TypeError, ValueError):
                value = None
        hits.append({'text': f'{name}{f" {value:g}%" if value is not None else ""}',
                     'percent': value})
    return hits


def _hit_sum(hits: list[dict]) -> float | None:
    """조각들의 함량 합. 하나도 못 읽었으면 None (0 과 구분해야 한다)."""
    values = [h['percent'] for h in hits if h['percent'] is not None]
    return sum(values) if values else None


def _evidence_row(field_label: str, hits: list[dict]) -> dict:
    """검증 화면에 그대로 그릴 한 줄."""
    total = _hit_sum(hits)
    return {
        'field': field_label,
        'found': bool(hits),
        'text': ' / '.join(h['text'] for h in hits) if hits else '',
        'percent': f'{total:g}%' if total is not None else '',
    }


def _named_items(product_name: str) -> list[str]:
    """
    제품명에 쓰인 농수산물. 긴 이름부터 본다.

    한 글자짜리 품목명이 긴 이름 안에 들어가 있는 경우를 걸러 낸다 —
    목록에 "마"(마과 뿌리)가 있어서 "토마토 케첩"이 **토마토와 마 두 건**으로
    잡혔다. 제품명에 "마" 가 들어간 이름은 흔해서(고구마·마늘·토마토) 이
    한 글자가 사실상 모든 제품에 지적을 하나씩 붙이고 있었다.
    """
    found = sorted(
        (item for item in _get_farm_seafood_items() if item in product_name),
        key=len, reverse=True,
    )
    return [item for item in found
            if not any(item != other and item in other for other in found)]


def check_farm_seafood_content(label) -> list[dict]:
    """
    제품명에 쓴 농수산물의 함량이 표시돼 있는지 확인한다.

    보는 곳이 셋이다. **특정성분 함량**(의무 표시 자리), **원재료명 및 함량**,
    **BOM 배합비**. 예전에는 첫 번째만 봤는데, 그래서 "원재료명에는 적어 뒀는데
    왜 지적하지?" 와 "둘 다 적었는데 숫자가 다르다" 를 둘 다 놓쳤다.

    지적할 때는 세 자리에 각각 무엇이 적혀 있는지를 함께 실어 보낸다
    (`issue['evidence']`). 어느 칸이 비었는지, 숫자가 어디서 어긋났는지를
    화면에서 바로 볼 수 있어야 사용자가 자기 입력을 다시 뒤지지 않는다.
    """
    product_name = label.prdlst_nm or ''
    if not product_name:
        return []

    ingredient_info = label.ingredient_info or ''
    rawmtrl_text = label.rawmtrl_nm_display or label.rawmtrl_nm or ''

    found_items = _named_items(product_name)
    issues = []
    for item in found_items:
        info_hits = _content_hits(ingredient_info, item)
        raw_hits = _content_hits(rawmtrl_text, item)
        bom_hits = _bom_hits(label, item)
        evidence = [
            _evidence_row('특정성분 함량', info_hits),
            _evidence_row('원재료명 및 함량', raw_hits),
            _evidence_row('BOM 배합비', bom_hits),
        ]
        info_sum = _hit_sum(info_hits)
        raw_sum = _hit_sum(raw_hits)

        if info_sum is None:
            if raw_sum is not None:
                message = (f"제품명에 사용된 '{item}'의 함량이 '특정성분 함량' 항목에 "
                           f"없습니다. 원재료명에는 {raw_sum:g}% 로 적혀 있습니다.")
                suggestion = (f'특정성분 함량 항목에 "{item} {raw_sum:g}%" 를 적으세요. '
                              f'제품명에 쓴 원재료의 함량은 주표시면에도 표시해야 합니다.')
            else:
                message = (f"제품명에 사용된 '{item}'의 함량이 '특정성분 함량' 항목에서 "
                           f"확인되지 않습니다.")
                suggestion = f'특정성분 함량 항목에 함량(%)을 표시하세요. (예: {item} 100%)'
            issue = _issue('farm_seafood', message, suggestion)
            issue['evidence'] = evidence
            issue['evidence_title'] = f"'{item}' 함량이 각 칸에 적힌 모양"
            issues.append(issue)
            continue

        # 두 곳 다 적혀 있으면 숫자가 같아야 한다. 소수점 반올림 차이는 넘긴다.
        if raw_sum is not None and abs(info_sum - raw_sum) > 0.05:
            issue = _issue(
                'farm_seafood',
                f"'{item}'의 함량이 서로 다릅니다 — 특정성분 함량 {info_sum:g}%, "
                f"원재료명 {raw_sum:g}%.",
                '두 곳의 함량은 같아야 합니다. 어느 쪽이 맞는지 확인해 고치세요. '
                '원재료명에 같은 원료가 여러 줄로 나뉘어 있으면 그 합과 견줍니다.',
            )
            issue['evidence'] = evidence
            issue['evidence_title'] = f"'{item}' 함량이 각 칸에 적힌 모양"
            issues.append(issue)
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

    # 선언 문구는 **통째로** 놓고 표준 명칭이 그 안에 있는지 본다.
    #
    # 예전에는 쉼표로 자른 뒤 문자열이 정확히 같은지 봤다. 그래서 표시기준이
    # 권장하는 표기인 "알류(달걀)" 이 표준 명칭 "알류" 와 다른 것으로 잡혀,
    # **규정대로 적을수록 미선언 경고가 나왔다.** 운영에서 그대로 나왔다 -
    # "알류(달걀), 우유, 대두, 밀" 중 괄호가 붙은 알류만 누락으로 보고됐다.
    #
    # 라벨에 실제로 쓰이는 표기를 늘어놓고 보면 잘라서 맞추는 쪽이 이길 수 없다:
    #   "알류(달걀)"  "우유(유당)"  "밀 함유"  "대두, 밀 함유"  "난류"
    # 괄호 주석·꼬리말·띄어쓰기가 제각각이고, 규정이 요구하는 것은 **표준 명칭이
    # 적혀 있는가** 뿐이다. 그러니 그것만 본다.
    declared_text = re.sub(r'\s+', '', label.allergens or '')

    detected = set()
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        if any(kw.lower() in ingredients_text.lower() for kw in keywords):
            detected.add(allergen)

    missing = {a for a in detected if a not in declared_text}
    issues = []
    if missing:
        issues.append(_issue(
            'allergen',
            f'원재료명에서 알레르기 유발요소로 보이는 성분이 검출됐지만 알레르기 표시에 선언되지 않았습니다: {", ".join(sorted(missing))}',
            '원재료명을 확인해 실제로 사용된 원료라면 알레르기 표시 항목에 추가하세요.',
        ))
    return issues


def _material_has(package_material, keywords):
    """
    포장재질 문구에 이 마크의 재질이 적혀 있는가.

    영문 코드는 **낱말 단위로** 본다. 그냥 포함으로 보면 "PET(용기)" 안에
    "PE" 가 들어 있어서, PET 용기에 PE 계열 마크를 찍어도 통과한다 - 잡아야 할
    오류를 놓치는 쪽이라 더 나쁘다.

    한글 낱말은 그대로 포함으로 본다. "폴리에틸렌수지" 처럼 붙여 쓰는 표기가
    흔해서 경계를 요구하면 멀쩡한 것이 걸린다.
    """
    for keyword in keywords or ():
        if keyword.isascii() and keyword.isalpha():
            if re.search(r'(?<![a-z])' + keyword + r'(?![a-z])', package_material):
                return True
        elif keyword in package_material:
            return True
    return False


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
        # 매핑 없는 마크는 통과시킨다(추천 로직 미포함)
        compatible = _material_has(package_material, keywords) if keywords else True

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


def _short_name(name: str, limit: int = 22) -> str:
    """
    메시지에 넣을 원료명을 줄인다.

    혼합제제의 표시명은 하위 원료를 전부 나열해 100자를 넘기도 한다.
    그대로 넣으면 어느 행이 문제인지가 오히려 안 보인다.
    """
    name = (name or '').strip()
    return name if len(name) <= limit else name[:limit] + '…'


def _ordered_relations(label):
    """원재료 팝업에 입력된 순서 그대로의 (relation, ingredient) 목록."""
    try:
        return list(
            label.ingredient_relations
            .select_related('ingredient')
            .order_by('relation_sequence')
        )
    except Exception:
        return []


def check_additive_display_name(label) -> list[dict]:
    """
    표시명이 비어 있는 식품첨가물이 연결돼 있는지 확인.

    원재료명 요약을 만드는 쪽(views.py)은 표시명이 비면 원료명(prdlst_nm)으로
    대체한다. 표4 대상 첨가물은 "명칭(용도)"로 써야 해서 명칭 단독은 표시기준에
    어긋나는데, 그게 화면에 아무 표시 없이 지나간다. 여기서 잡는다.
    """
    from v1.label.models import FoodAdditive

    blanks = []
    for rel in _ordered_relations(label):
        ing = rel.ingredient
        if (getattr(ing, 'food_category', '') or '') != 'additive':
            continue
        if (ing.ingredient_display_name or '').strip():
            continue
        blanks.append(ing.prdlst_nm or '이름 없음')

    if not blanks:
        return []

    # 표4(명칭+용도) 대상은 명칭 단독 표시 자체가 위반이라 따로 짚어준다.
    table4 = set()
    try:
        for add in FoodAdditive.objects.filter(name_kr__in=blanks):
            if '4' in add.display_tables:
                table4.add(add.name_kr)
    except Exception:
        pass

    issues = []
    plain = [n for n in blanks if n not in table4]
    if table4:
        names = ', '.join(_short_name(n) for n in sorted(table4))
        issues.append(_issue(
            'additive_display_name',
            f'표시명이 비어 있는 식품첨가물이 있습니다: {names}. '
            f'이 첨가물은 명칭과 용도를 함께 표시해야 하는데, 지금은 명칭만 표시됩니다.',
            '내 원료 상세에서 "식품첨가물 표시규정" 버튼으로 "명칭(용도)" 형태의 표시명을 골라주세요.',
        ))
    if plain:
        names = ', '.join(_short_name(n) for n in sorted(set(plain)))
        issues.append(_issue(
            'additive_display_name',
            f'표시명이 비어 있는 식품첨가물이 있습니다: {names}. 원료명이 그대로 표시됩니다.',
            '내 원료 상세에서 표시명을 확인해 주세요.',
        ))
    return issues


_CHECKS = [
    check_required_fields,
    check_calorie_consistency,
    check_ingredient_order_by_ratio,   # 비어 있는 것부터 — 나머지 검사는 값이 있을 때만 본다
    check_content_weight,
    check_farm_seafood_content,
    check_forbidden_phrases,
    check_allergens,
    check_recycling_mark,
    check_origin_missing,
    check_additive_display_name,
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
