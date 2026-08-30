"""
식품유형 -> 표시 항목(체크박스) 결정.

"이 식품유형은 무엇을 표시해야 하는가" 를 정하는 곳이다. 지금까지 이 판단이
세 군데에 흩어져 있었다.

  - 가공식품: FoodType 테이블에 Y/D/N 이 293행 들어 있는데 **쓰는 코드가 없었다**.
    label_creation.js:1448 이 /label/food-type-settings/ 를 부르지만 그 URL 이
    urls.py 에 없어 404 -> .catch(console.error) 로 삼켜졌다.
  - 식품첨가물/혼합제제/농수축산물: views.get_additive_field_settings 안에
    하드코딩. 이건 살아 있었다.
  - 그 외: MyLabel 의 chckd_* 모델 기본값(9개 'Y').

그래서 식품유형을 무엇으로 고르든 새 라벨은 항상 같은 9개로 시작했다.
필수 입력 검사(validation_service.check_required_fields)가 붙으면서 이게
그대로 "무엇이 필수인가" 가 됐기 때문에, 이제 실제 식품유형을 반영해야 한다.

값의 뜻 (label_creation.js 가 원래 쓰던 규약 그대로):
    'Y' 표시 대상        -> 체크 켬
    'D' 해당 없음        -> 체크 끄고 비활성 (그 유형에는 쓸 수 없는 항목)
    'N' 사용자 재량      -> 기본 끔, 사용자가 켤 수 있음
"""
from v1.label.models import FoodType

# API 가 쓰는 필드 키 -> MyLabel 의 체크박스 컬럼.
# 이름이 곧이곧대로 이어지지 않는 것이 셋 있다.
#   rawmtrl_nm  -> chckd_rawmtrl_nm_display (표시용 원재료명이 인쇄 대상이다)
#   nutritions  -> chckd_nutrition_text
#   bssh_nm     -> chckd_bssh_nm            (화면 쪽 이름은 chk_manufacturer_info)
FIELD_TO_CHECKBOX = {
    'prdlst_dcnm':       'chckd_prdlst_dcnm',
    'prdlst_nm':         'chckd_prdlst_nm',
    'ingredient_info':   'chckd_ingredient_info',
    'content_weight':    'chckd_content_weight',
    'weight_calorie':    'chckd_weight_calorie',
    'prdlst_report_no':  'chckd_prdlst_report_no',
    'country_of_origin': 'chckd_country_of_origin',
    'storage_method':    'chckd_storage_method',
    'frmlc_mtrqlt':      'chckd_frmlc_mtrqlt',
    'bssh_nm':           'chckd_bssh_nm',
    'pog_daycnt':        'chckd_pog_daycnt',
    'rawmtrl_nm':        'chckd_rawmtrl_nm_display',
    'nutritions':        'chckd_nutrition_text',
    'cautions':          'chckd_cautions',
}

# FoodType 에 컬럼이 없어 유형별로 갈리지 않는 항목들. 가공식품에서는 항상 이 값.
_PROCESSED_FIXED = {
    'prdlst_nm':       'Y',   # 제품명은 어떤 유형이든 필수
    'content_weight':  'Y',   # 내용량도 마찬가지 (FoodType 에 컬럼이 없다)
    'ingredient_info': 'N',   # 특정성분 함량은 제품명에 원료를 강조할 때만
    'bssh_nm':         'Y',   # 제조원 소재지
}

_ADDITIVE_SETTINGS = {
    'prdlst_nm': 'Y', 'ingredient_info': 'N', 'prdlst_dcnm': 'Y',
    'content_weight': 'Y', 'weight_calorie': 'Y', 'prdlst_report_no': 'Y',
    'country_of_origin': 'N', 'frmlc_mtrqlt': 'Y', 'pog_daycnt': 'Y',
    'rawmtrl_nm': 'Y', 'storage_method': 'Y', 'bssh_nm': 'Y',
    'nutritions': 'D', 'cautions': 'Y',
}

_AGRICULTURAL_BASE = {
    'prdlst_nm': 'Y', 'ingredient_info': 'D', 'prdlst_dcnm': 'D',
    'content_weight': 'Y', 'weight_calorie': 'D', 'prdlst_report_no': 'D',
    'country_of_origin': 'Y', 'frmlc_mtrqlt': 'D', 'pog_daycnt': 'N',
    'rawmtrl_nm': 'N', 'storage_method': 'N', 'bssh_nm': 'Y',
    'nutritions': 'D', 'cautions': 'D',
}

_AGRICULTURAL_BY_TYPE = {
    '농산물': ({'pog_daycnt': 'N', 'rawmtrl_nm': 'D', 'storage_method': 'N'}, [
        '생산연도 (또는 생산연월일)', '포장일', '품종', '등급 (표준규격품인 경우)',
    ]),
    '수산물': ({'pog_daycnt': 'N', 'rawmtrl_nm': 'D', 'storage_method': 'N'}, [
        '생산연월일', '포장일', '등급', '마릿수',
    ]),
    '축산물': ({'pog_daycnt': 'Y', 'rawmtrl_nm': 'Y', 'storage_method': 'N'}, [
        '이력관리번호', '등급', '부위', '도축일', '포장일', '도축장명',
        '보관방법 (냉장/냉동)',
    ]),
}

SPECIAL_GROUPS = ('식품첨가물', '혼합제제', '농수축산물')


def _pog_daycnt_options(raw: str) -> list[str]:
    """
    FoodType.pog_daycnt 는 Y/N/D 가 아니라 텍스트다
    ('소비기한', '제조연월일', '소비기한, 품질유지기한', '제조연월일, 품질유지기한').
    화면은 체크박스용 Y/N/D 와 드롭다운용 선택지를 따로 기대하므로 여기서 가른다.
    """
    return [part.strip() for part in (raw or '').split(',') if part.strip()]


def resolve_settings(food_group: str = '', food_type: str = '') -> dict:
    """
    (food_group, food_type) 에 대한 표시 항목 규칙.

    Returns:
        {
          'settings': {필드키: 'Y'|'D'|'N'},
          'custom_fields': [{'label': str, 'value': ''}],   # 농수축산물만
          'relevant_regulations': str,
          'pog_daycnt_options': [str],
          'found': bool,      # 가공식품인데 FoodType 에 그 유형이 없으면 False
        }
    """
    food_group = (food_group or '').strip()
    food_type = (food_type or '').strip()

    if food_group in ('식품첨가물', '혼합제제'):
        return {'settings': dict(_ADDITIVE_SETTINGS), 'custom_fields': [],
                'relevant_regulations': '', 'pog_daycnt_options': [], 'found': True}

    if food_group == '농수축산물':
        settings = dict(_AGRICULTURAL_BASE)
        overrides, labels = _AGRICULTURAL_BY_TYPE.get(food_type, ({}, []))
        settings.update(overrides)
        return {'settings': settings,
                'custom_fields': [{'label': l, 'value': ''} for l in labels],
                'relevant_regulations': '', 'pog_daycnt_options': [], 'found': True}

    # ── 가공식품: FoodType 테이블 ───────────────────────────────────────────
    row = FoodType.objects.filter(food_type=food_type).first() if food_type else None
    if row is None:
        return {'settings': {}, 'custom_fields': [], 'relevant_regulations': '',
                'pog_daycnt_options': [], 'found': False}

    settings = dict(_PROCESSED_FIXED)
    for field in ('prdlst_dcnm', 'weight_calorie', 'prdlst_report_no',
                  'country_of_origin', 'frmlc_mtrqlt', 'rawmtrl_nm',
                  'storage_method', 'nutritions', 'cautions'):
        value = (getattr(row, field, '') or '').strip().upper()
        settings[field] = value if value in ('Y', 'D', 'N') else 'N'

    options = _pog_daycnt_options(row.pog_daycnt)
    # 293행 전부 텍스트가 들어 있다 = 어떤 유형이든 날짜 표시는 한다.
    # 값이 비는 예외적인 행만 사용자 재량으로 넘긴다.
    settings['pog_daycnt'] = 'Y' if options else 'N'

    return {'settings': settings, 'custom_fields': [],
            'relevant_regulations': row.relevant_regulations or '',
            'pog_daycnt_options': options, 'found': True}


def apply_to_label(label, settings: dict) -> dict:
    """
    규칙을 MyLabel 의 chckd_* 에 반영한다. 저장은 하지 않는다.

    끄는 쪽을 일부러 보수적으로 잡았다. 규칙을 그대로 덮어쓰면 사용자가 켜 둔
    항목이 조용히 꺼지고 인쇄물에서 줄이 사라진다. 실제로 FoodType 의
    cautions 는 293행 중 288행이 'N' 이라, 그대로 적용하면 주의사항이 거의 모든
    라벨에서 빠진다.

        'Y' -> 켠다
        'D' -> 값이 비어 있을 때만 끈다 (값이 있으면 건드리지 않고 보고한다)
        'N' -> 그대로 둔다 (사용자 재량)

    Returns:
        {'turned_on': [체크박스명], 'turned_off': [...], 'kept_filled': [...]}
    """
    turned_on, turned_off, kept_filled = [], [], []

    for field, rule in settings.items():
        checkbox = FIELD_TO_CHECKBOX.get(field)
        if not checkbox or not hasattr(label, checkbox):
            continue
        current = (getattr(label, checkbox) or '').strip().upper()

        if rule == 'Y':
            if current != 'Y':
                setattr(label, checkbox, 'Y')
                turned_on.append(checkbox)
        elif rule == 'D':
            if current != 'Y':
                continue
            value_field = checkbox[len('chckd_'):]
            if (getattr(label, value_field, '') or '').strip():
                kept_filled.append(checkbox)   # 값이 있다 — 끄면 인쇄물에서 사라진다
            else:
                setattr(label, checkbox, 'N')
                turned_off.append(checkbox)
        # 'N' 은 사용자 재량이라 건드리지 않는다

    return {'turned_on': turned_on, 'turned_off': turned_off,
            'kept_filled': kept_filled}
