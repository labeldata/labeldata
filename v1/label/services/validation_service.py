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
import logging
import math
import re

from django.core.cache import cache

logger = logging.getLogger(__name__)

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
    'content_weight_basis': '「식품등의 표시기준」 내용량 표시 규정 및 영양성분 표시 규정(총 내용량 기준)',
    'rawmtrl_bracket': '「식품등의 표시기준」 원재료명 표시 규정(복합원재료의 하위 원료 표시)',
    'food_type_unknown': '「식품등의 표시기준」 식품유형별 표시사항 규정',
    'allergen_vocabulary': '「식품등의 표시기준」 알레르기 유발물질 표시 규정(표시 명칭)',
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
#   cautions / additional_info : **두 칸의 경계는 사람마다 다르다.** 표시기준이
#       "주의사항" 과 "기타표시사항" 을 칼같이 가르지 않아서, 같은 문구를 한
#       사람은 주의사항에, 다른 사람은 기타표시사항에 적는다. 실제 라벨에서도
#       혼입가능 문구·보관 주의·고객상담실 번호가 양쪽에 섞여 나온다.
#       인쇄물에는 두 칸이 나란히 찍히므로 어느 쪽에 있든 표시는 온전하다.
#       한쪽이 비었다고 "미입력" 이라 하면, 규정을 지킨 라벨을 탓하게 된다.
_ALTERNATIVE_SOURCES = {
    'rawmtrl_nm_display': ('rawmtrl_nm',),
    'nutrition_text': ('calories', 'natriums', 'carbohydrates', 'proteins', 'fats'),
    'cautions': ('additional_info',),
    'additional_info': ('cautions',),
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

    # **두 칸이 담는 것이 다르다는 말부터 한다.**
    #
    # 예전 문구는 "맞지 않습니다 / 값을 고치거나 다시 확인하세요" 로 끝나서,
    # 어느 쪽을 어떻게 고쳐야 하는지가 없었다. 실제로 이 경고를 받은 사용자가
    # 영양성분 탭에 총 열량을 넣어 보고, 내용량에 100g당 열량을 넣어 보다가
    # 두 값이 계속 어긋났다. 규칙을 문장으로 적어 준다.
    #
    # 두 자리에 들어가는 것은 이렇다.
    #     내용량 칸     총 내용량과 **그 전체의 열량**       "65 g (200 kcal)"
    #     영양성분 탭   언제나 **100 g(mL) 당** 값          "309"
    per_total = round_calories(per_100 * amount / 100)
    back = stated * 100 / amount

    # **라벨 값을 그대로 옮겨 적은 흔적**을 알아본다.
    #
    # 라벨의 영양성분표가 "총 내용량 65 g / 65 g 당 309 kcal" 이면, 표의 숫자는
    # 65 g 당이다. 그걸 그대로 영양성분 탭에 넣으면 두 값이 똑같아진다
    # (내용량의 병기 열량 = 탭의 열량). 그때는 "값이 틀렸다" 가 아니라
    # "기준이 다르다" 고 말해야 고칠 데를 찾는다.
    #
    # 실제로 이 경고를 받은 사용자가 단위량을 100 으로 바꿔 표를 맞췄고,
    # 그러면 총 내용량이 100 g 으로 찍혔다 — 한 오류를 다른 오류로 바꾼 셈이다.
    if abs(stated - per_100) <= _CALORIE_TOLERANCE and abs(amount - 100) > 0.5:
        return [_issue(
            'calorie_consistency',
            f'영양성분 탭에 라벨에 인쇄된 값({stated:,.0f} kcal)을 그대로 넣으신 것 같습니다. '
            f'이 제품의 표는 총 내용량 {_format_amount(text, amount)} 당으로 인쇄돼 있는데, '
            f'영양성분 탭은 100 g(mL) 당 값을 담습니다. '
            f'지금 값으로는 표가 {per_total:,.0f} kcal 로 그려집니다.',
            f'영양성분 계산기의 "아래 값은" 을 <총 내용량당> 으로 두고 라벨의 숫자를 '
            f'그대로 다시 넣으면 저장할 때 환산합니다. 손으로 넣으려면 열량을 '
            f'{round_calories(back):,.0f}(100 g 당)으로 고치세요. '
            f'단위량을 100 으로 바꾸는 것은 표는 맞아 보여도 총 내용량이 '
            f'100 으로 찍혀 내용량 칸과 어긋납니다.',
        )]

    return [_issue(
        'calorie_consistency',
        f'내용량에 병기한 열량({stated:,.0f} kcal)과 영양성분 탭의 값이 서로 다른 총량을 '
        f'말하고 있습니다. 내용량 칸의 열량은 총 내용량 {_format_amount(text, amount)} '
        f'전체의 열량이고, '
        f'영양성분 탭의 값은 100 g(mL) 당입니다. '
        f'탭의 {per_100:,.0f} kcal 로는 총 {per_total:,.0f} kcal 이 됩니다.',
        f'둘 중 하나를 고르세요 — 내용량을 "{_format_amount(text, amount)} '
        f'({per_total:,.0f} kcal)" 로 고치거나, 영양성분 탭의 열량을 '
        f'{round_calories(back):,.0f}(100 {_amount_unit(text)} 당)으로 고치세요.',
    )]


def _amount_unit(text):
    """내용량 글자에 적힌 단위. 임의로 g 를 붙이면 음료(mL)에 g 라고 말하게 된다."""
    m = _AMOUNT_RE.search(text or '')
    return m.group(2) if m else 'g'


def _format_amount(text, amount):
    """경고 문구에 쓸 "65 g" 꼴. 단위는 내용량 글자에서 그대로 가져온다."""
    return f'{amount:,.0f} {_amount_unit(text)}'


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


# 원료 이름 뒤에 붙어 **그 원료의 형태**를 말하는 꼬리말.
#
# 한국어에는 낱말 경계가 없어서 "오리" 가 "오리엔탈소스" 안에도 들어 있다.
# 그냥 포함으로 보면 원료가 아닌 것을 원료로 세게 된다. 그렇다고 이름이 정확히
# 같을 때만 인정하면 "오리고기 45%" 를 못 찾는다 — 그건 분명히 오리다.
#
# 그래서 **원료의 형태를 말하는 꼬리말이 붙은 경우만** 같은 원료로 본다.
# 목록에 없는 글자가 붙으면 다른 낱말이다("오리엔탈", "무염").
_FORM_SUFFIXES = (
    '고기', '살', '육', '알', '즙', '유', '분말', '가루', '분',
    '엑기스', '추출물', '추출액', '농축액', '농축물', '페이스트', '퓨레',
    '잼', '청', '차', '유래', '박', '씨', '순', '잎', '뿌리', '껍질',
    '통조림', '건조', '건조물', '액', '油',
)

# 원재료명 조각을 원료 이름 단위로 더 가르는 자리.
# "쇠고기(한우, 국산) 20%" -> 쇠고기 / 한우 / 국산
_TOKEN_SPLIT = re.compile(r'[,()\[\]{}（）［］〔〕/·|]+')

# 이름 뒤에 붙는 군더더기. 함량·원산지 표기는 이름이 아니다.
_TOKEN_TAIL = re.compile(r'(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|l))\s*$',
                         re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    """문구를 원료 이름 후보로 가른다."""
    out = []
    for raw in _TOKEN_SPLIT.split(text or ''):
        token = _TOKEN_TAIL.sub('', raw).strip()
        token = re.sub(r'\s+', '', token)
        if token:
            out.append(token)
    return out


def _is_same_item(token: str, item: str) -> bool:
    """
    이 원료 이름이 그 품목인가. **낱말로** 본다.

        "오리"        == "오리"     그대로
        "오리고기"    == "오리"     형태 꼬리말이 붙은 것
        "오리엔탈소스" != "오리"     다른 낱말이다
        "단무지"      != "무"       품목명으로 시작하지도 않는다
        "무염버터"    != "무"       "염버터" 는 형태 꼬리말이 아니다
    """
    if token == item:
        return True
    if not token.startswith(item):
        return False
    tail = token[len(item):]
    return tail in _FORM_SUFFIXES


def _segment_has_item(seg: str, item: str) -> bool:
    """조각 안에 그 원료가 낱말로 적혀 있는가."""
    return any(_is_same_item(token, item) for token in _tokens(seg))


def _content_hits(text: str, item: str) -> list[dict]:
    """
    문구에서 그 원료가 적힌 조각과 거기 붙은 함량(%)을 모은다.

    조각 안에서 **원료 이름 뒤에 오는** 첫 % 를 그 원료의 함량으로 본다.
    앞에 있는 % 는 다른 원료의 것이다.

    이름은 낱말로 견준다(_is_same_item). 그냥 포함으로 보면 "무" 를 찾다가
    "무염버터" 를 집어, 엉뚱한 조각의 함량을 그 원료의 것으로 더한다.
    """
    hits = []
    for seg in _split_top_level(text):
        if not _segment_has_item(seg, item):
            continue
        pos = seg.find(item)
        m = _PERCENT_RE.search(seg, pos if pos >= 0 else 0)
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
        if not _segment_has_item(name, item):
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
    제품명에 쓰인 것으로 **보이는** 농수산물. 긴 이름부터 본다.

    한 글자짜리 품목명이 긴 이름 안에 들어가 있는 경우를 걸러 낸다 —
    목록에 "마"(마과 뿌리)가 있어서 "토마토 케첩"이 **토마토와 마 두 건**으로
    잡혔다. 제품명에 "마" 가 들어간 이름은 흔해서(고구마·마늘·토마토) 이
    한 글자가 사실상 모든 제품에 지적을 하나씩 붙이고 있었다.

    여기서 걸러도 남는 것이 있다. 제품명은 자유 문구라 낱말 경계가 없어서,
    목록의 이름이 다른 낱말 안에 그대로 들어간다.

        오리지널 타코    -> 오리      오리엔탈 드레싱 -> 오리
        굴소스 볶음밥    -> 굴        무스케이크      -> 무

    그건 이 함수 혼자서는 가릴 수 없다. 부르는 쪽(_used_named_items)이 원재료명
    과 대조해 가린다.
    """
    found = sorted(
        (item for item in _get_farm_seafood_items() if item in product_name),
        key=len, reverse=True,
    )
    return [item for item in found
            if not any(item != other and item in other for other in found)]


def _used_named_items(label, product_name: str, rawmtrl_text: str) -> list[str]:
    """
    제품명에 쓴 농수산물 중 **그 제품에 실제로 들어 있는 것**만.

    규정이 요구하는 것은 「제품명에 **사용한** 원재료의 함량 표시」다. 그러니
    제품명의 그 글자가 그 원재료를 가리키는지는 **그 원재료가 들어 있는가**로
    가린다. 안 들어 있으면 제품명이 그 원료를 쓴 것이 아니다 — 글자가 겹쳤을 뿐이다.

        "오리지널 타코"  원재료명에 오리가 없다 -> 제품명의 "오리" 는 오리가 아니다
        "오리불고기"     원재료명에 오리고기 45% -> 진짜다

    **여기서 놓치는 경우가 하나 있다.** 제품명에는 썼는데 원재료명에 안 적은
    라벨은 조용히 넘어간다. 그건 함량 미표시가 아니라 원재료 누락(또는 허위표시)
    이고, "함량이 확인되지 않습니다" 라고 말하면 사용자를 엉뚱한 칸으로 보낸다.
    지적하려면 그 뜻으로 따로 말해야 하는데, 그러려면 "오리지널" 을 가려낼 수
    있어야 한다 — 지금은 못 가린다. 잘못 지적하는 쪽보다 침묵을 고른다.
    """
    return [item for item in _named_items(product_name)
            if _content_hits(rawmtrl_text, item) or _bom_hits(label, item)]


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

    found_items = _used_named_items(label, product_name, rawmtrl_text)
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


# 금지 문구를 글자로 품고 있지만 **고시된 표준 용어**라 쓸 수 있는 말.
#
# "자연치즈" 는 식품유형 이름이고 "천연향료" 는 식품첨가물 공전의 명칭이다.
# 규정대로 적은 라벨이 금지 문구로 지적되면, 고치라는 대로 고칠 수가 없다.
#
# **여기 없는 말은 예전처럼 지적한다.** 확실한 것만 넣는다 — "자연산" 처럼
# 규정이 명시적으로 막은 말을 여기 넣으면 잡아야 할 것을 놓친다.
_FORBIDDEN_EXCEPTIONS = ('자연치즈', '천연향료')


def _without_exceptions(text: str) -> str:
    """고시된 표준 용어를 지운 문구. 그 안의 금지 글자는 세지 않는다."""
    out = text or ''
    for word in _FORBIDDEN_EXCEPTIONS:
        out = out.replace(word, ' ')
    return out


def check_forbidden_phrases(label) -> list[dict]:
    """제품명/원재료명 등 5개 필드에서 사용 금지 문구('천연', '자연' 등) 검출."""
    issues = []
    for field, field_label in _FIELD_LABELS.items():
        value = getattr(label, field, '') or ''
        scanned = _without_exceptions(value)
        for phrase in FORBIDDEN_PHRASES:
            if not re.search(re.escape(phrase), scanned, re.IGNORECASE):
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


# 알레르기 키워드를 글자로 품고 있지만 **그 물질이 아닌** 원료 이름.
#
# 원재료명은 자유 문구라 낱말 경계가 없다. 한 글자 키워드("밀", "게")가 긴
# 이름 안에 그대로 들어가 있으면 그냥 포함으로는 가릴 수가 없다.
#
#     아밀라아제 -> 효소다. 밀이 아니다
#     밀랍       -> 벌집에서 나온 왁스다
#     당밀       -> 사탕수수 부산물이다
#     게르마늄   -> 원소 이름이다
#
# **여기 없는 것은 예전처럼 관대하게 잡는다.** 알레르기는 놓치는 쪽이 훨씬
# 나쁘므로, 확실히 아닌 것만 하나씩 적는다. 예를 들어 "대두레시틴" 은 빼지
# 않는다 — 그건 정말 대두다.
_ALLERGEN_FALSE_FRIENDS = {
    '밀': ('아밀라아제', '아밀레이스', '아밀로스', '아밀로펙틴', '밀랍', '당밀'),
    '게': ('게르마늄',),
}


def _drop_false_friends(text: str, allergen: str) -> str:
    """그 물질이 아닌 이름을 지운 문구. 그 안의 글자는 세지 않는다."""
    out = text or ''
    for word in _ALLERGEN_FALSE_FRIENDS.get(allergen, ()):
        out = out.replace(word, ' ')
    return out


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

    # 선언 문구를 **표시 명칭으로 풀어** 둔다. 글자만 보면 "달걀" 이라고만 적힌
    # 라벨을 "알류 미선언" 으로 지적하게 된다 — 같은 물질인데.
    try:
        from v1.label.services.allergen_names import canonical
        declared_names = {canonical(t) for t in re.split(r'[,、，/·]', label.allergens or '')}
        declared_names.discard('')
    except Exception:
        logger.exception('알레르기 선언 명칭 판정 실패 — 글자 대조만 한다')
        declared_names = set()

    detected = set()
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        scanned = _drop_false_friends(ingredients_text, allergen).lower()
        if any(kw.lower() in scanned for kw in keywords):
            detected.add(allergen)

    missing = {a for a in detected
               if a not in declared_text and a not in declared_names}
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


# ─────────────────────────────────────────────────────────────────────────────
# 내용량·영양성분의 총량이 서로 맞는가
#
# 이 화면에는 "총 내용량" 이 **두 군데** 적힌다.
#
#   내용량 칸        "65 g (200 kcal)"   ← 인쇄되는 값
#   영양성분 탭      단위량 × 포장개수    ← 표를 그리는 값
#
# 둘이 어긋나면 인쇄된 내용량과 영양정보 표의 머리가 서로 다른 총량을 말한다.
# 그런데 예전에는 열량만 견주고 총량은 안 봐서, 사용자가 열량을 고쳐도 표는
# 여전히 다른 총량을 그렸다 — 고치라는 대로 고쳐도 라벨이 안 맞았다.
# ─────────────────────────────────────────────────────────────────────────────

# 총량 비교 허용오차(g·mL). 반올림해 적는 관행을 감안한 폭이다.
_AMOUNT_TOLERANCE = 0.5


def _nutrition_total(label):
    """영양성분 탭이 말하는 총 내용량 = 단위량 × 포장개수. 못 읽으면 None."""
    unit_amount = _number((label.serving_size or '').strip())
    if unit_amount is None or unit_amount <= 0:
        return None
    count = _number((label.units_per_package or '').strip())
    if count is None or count <= 0:
        count = 1.0
    return unit_amount * count


def check_content_weight_basis(label) -> list[dict]:
    """
    내용량 칸의 총량과 영양성분 탭의 총량(단위량 × 포장개수)이 같은지 본다.

    영양성분 탭을 아직 안 채웠으면 검사하지 않는다 — 그건 다른 검사(필수항목)가
    할 말이다.

    **표를 안 그리는 라벨은 건너뛴다.** 단위량은 여러 곳에서 기본값 100 으로
    채워지므로, 영양성분을 한 번도 안 넣은 65 g 짜리 제품은 "100 != 65" 로 늘
    걸린다. 표가 인쇄되지 않는데 총량이 어긋난다고 말해 봐야 고칠 것이 없다.
    """
    if not (label.calories or '').strip():
        return []

    text = normalize_units(label.content_weight or '')
    stated = _total_amount(text)
    nutrition = _nutrition_total(label)
    if stated is None or nutrition is None or stated <= 0:
        return []
    if abs(stated - nutrition) <= _AMOUNT_TOLERANCE:
        return []

    unit_amount = _number((label.serving_size or '').strip())
    count = _number((label.units_per_package or '').strip()) or 1
    return [_issue(
        'content_weight_basis',
        f'내용량({_format_amount(text, stated)})과 영양성분 탭의 총 내용량'
        f'({nutrition:,.0f} {_amount_unit(text)})이 다릅니다. '
        f'영양성분 탭은 단위량 {unit_amount:,.0f} × 포장개수 {count:,.0f} 로 계산합니다.',
        '내용량 칸에는 포장 전체의 양을 적습니다. 영양성분 탭의 단위량·포장개수를 '
        '그 값에 맞추거나(한 개짜리면 단위량 = 총 내용량, 포장개수 = 1), '
        '내용량 칸을 고치세요.',
    )]


# ─────────────────────────────────────────────────────────────────────────────
# 판독에서 하던 검사를 저장된 라벨에도 적용한다
#
# 사진 판독은 값을 넣기 전에 두 가지를 본다 — 원재료명의 괄호 짝이 맞는지
# (ocr_rawmtrl.bracket_problems), 식품유형이 표시기준 목록에 있는 이름인지
# (ocr_snap). 둘 다 **사진에서 왔든 손으로 넣었든 똑같이 틀린 것**인데, 판독을
# 거치지 않고 손으로 채운 라벨에는 아무도 그 말을 해 주지 않았다.
#
# 검사 자체는 그쪽 모듈을 그대로 부른다. 규칙을 두 벌로 만들면 어느 날 한쪽만
# 고쳐진다.
# ─────────────────────────────────────────────────────────────────────────────

def check_rawmtrl_brackets(label) -> list[dict]:
    """
    원재료명의 괄호 짝이 맞는지.

    괄호는 복합원재료와 그 하위 원료를 가르는 표시 장치다. 짝이 깨지면 어디부터
    어디까지가 하위 원료인지 읽을 수 없고, 인쇄물에 그대로 나간다.
    """
    text = (label.rawmtrl_nm_display or label.rawmtrl_nm or '').strip()
    if not text:
        return []
    try:
        from v1.label.services.ocr_rawmtrl import bracket_problems
        problems = bracket_problems(text)
    except Exception:      # 검사를 못 하는 것뿐이다 — 나머지 검증은 계속돼야 한다
        logger.exception('원재료명 괄호 검사 실패')
        return []

    return [_issue('rawmtrl_bracket', f'원재료명의 괄호가 맞지 않습니다: {p}',
                   '여는 괄호와 닫는 괄호의 짝을 맞추세요. 복합원재료의 하위 원료는 '
                   '괄호 안에 넣습니다.')
            for p in problems]


def check_food_type_known(label) -> list[dict]:
    """
    식품유형(소분류)이 표시기준 목록에 있는 이름인가.

    이 값은 **유형별 표시항목 규칙을 찾는 키**다. 한 글자가 어긋나면 규칙을
    통째로 못 찾고, 화면은 그것을 조용히 "규칙 없음" 으로 넘긴다. 그러면 그
    유형에만 있는 의무 표시사항이 검사조차 되지 않는다.
    """
    food_type = (label.food_type or '').strip()
    if not food_type:
        return []
    try:
        from v1.label.services.ocr_snap import food_type_vocabulary, snap_one
        snapped, score, verdict = snap_one(food_type, food_type_vocabulary())
    except Exception:
        logger.exception('식품유형 목록 대조 실패')
        return []

    if verdict == 'exact' or not verdict:
        return []
    if verdict == 'snapped' and snapped:
        return [_issue(
            'food_type_unknown',
            f'식품유형 "{food_type}" 이(가) 표시기준 목록에 없습니다. '
            f'"{snapped}" 을(를) 뜻하는 것으로 보입니다.',
            f'소분류를 "{snapped}" 로 고르면 그 유형의 의무 표시사항까지 함께 검사합니다.',
        )]
    return [_issue(
        'food_type_unknown',
        f'식품유형 "{food_type}" 이(가) 표시기준 목록에 없습니다.',
        '소분류를 목록에서 골라 주세요. 목록 밖의 이름은 유형별 의무 표시사항을 '
        '찾지 못해 그 항목들이 검사에서 통째로 빠집니다.',
    )]


def check_allergen_vocabulary(label) -> list[dict]:
    """
    알레르기 표시가 표시기준의 22종 이름으로 적혀 있는가.

    이 칸은 뒤에서 **키로 쓰인다**(원재료명 대조). "쇠고기 함유" 처럼 꼬리말이
    붙거나 목록에 없는 이름이 적히면 어느 목록에서도 안 찾히고, 이미 선언한
    물질을 "선언 안 됨" 으로 지적하게 된다.
    """
    declared = (label.allergens or '').strip()
    if not declared:
        return []
    try:
        from v1.label.services.allergen_names import normalize
        snapped, changes = normalize(declared)
    except Exception:
        logger.exception('알레르기 표기 대조 실패')
        return []

    # 띄어쓰기만 다른 것은 지적하지 않는다. 예전에는 그 차이로도 경고가 떠서,
    # 제안이 원문과 똑같아 보이는 쪽지를 사용자가 계속 받았다.
    if not snapped or _squeeze(snapped) == _squeeze(declared):
        return []

    # 같은 물질이 두 번 적힌 것은 표기 문제가 아니라 중복이다. 그렇게 말해 준다.
    dupes = [c for c in changes if canonical_of(c) and c['kept'] != c['dropped']
             and _squeeze(c['kept']).startswith(_squeeze(c['name']))
             and _squeeze(c['dropped']).startswith(_squeeze(c['name']))]
    if dupes:
        names = ', '.join(sorted({c['name'] for c in dupes}))
        return [_issue(
            'allergen_vocabulary',
            f'같은 알레르기 물질이 두 번 적혀 있습니다: {names} '
            f'(적힌 값: "{declared}")',
            f'"{snapped}" 로 적으면 됩니다. 괄호는 무엇을 넣었는지 밝히는 부연이라 '
            f'"알류" 와 "알류(달걀)" 은 같은 물질입니다.',
        )]
    return [_issue(
        'allergen_vocabulary',
        f'알레르기 표시가 표시기준 명칭과 다릅니다: "{declared}"',
        f'"{snapped}" 로 적으면 원재료명 대조가 정확해집니다. '
        f'("함유" 같은 꼬리말은 빼고 물질 이름만 적습니다)',
    )]


def canonical_of(change):
    """merge 가 남긴 변경 기록에서 표시 명칭. 없으면 빈 문자열."""
    return (change or {}).get('name') or ''


def _squeeze(text):
    return ''.join(str(text or '').split()).lower()


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
    # 판독이 값을 넣기 전에 하던 검사. 손으로 채운 라벨에도 같은 잣대를 댄다.
    check_content_weight_basis,
    check_rawmtrl_brackets,
    check_food_type_known,
    check_allergen_vocabulary,
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
