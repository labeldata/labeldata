"""
**주표시면과 정보표시면이 각각 어디인가.**

표시기준의 활자·표시 규정은 거의 전부 "어느 면에" 를 전제로 한다. 그런데 그
전제가 우리 코드 어디에도 없었다 — `design_request` 는 *무엇이* 주표시면에
가는지만 알고, `ocr_service` 는 사진에 면 이름표를 붙이지만 그 면이 *무엇이어야
하는지* 는 모른다.

밖에서 본 시스템은 이 표를 도표 한 장에서 뽑아 36개 항목 전부의 전제로 삼는다.
포장 형태가 정해지면 어느 면이 주표시면인지가 정해진다.

    봉지 (감자칩)          주=앞면            정보=뒷면
    용기·병 (컵라면·음료)   주=앞면·윗면       정보=뒷면
    용기 (즉석밥)          주=표시면적 2/3     정보=1/3
    스티커 (냉동새우)       주=스티커 1/2       정보=1/2
    상자 (오렌지주스)       주=앞면·윗면·뒷면   정보=양측면

**우리에겐 포장 형태 칸이 없다.** 그래서 이 표는 지금 두 곳에 쓰인다 —
디자인 의뢰서가 디자이너에게 알려 주는 문구, 그리고 활자 규칙의 근거.
칸이 생기면 판정에도 바로 물릴 수 있다.
"""

# 포장 형태별 표시면. 키는 화면에서 고를 값이다.
PACKAGE_FORMS = {
    'pouch': {'name': '봉지', 'example': '감자칩',
              'main': '앞면', 'info': '뒷면'},
    'cup': {'name': '용기·병', 'example': '컵라면·사과음료',
            'main': '앞면·윗면', 'info': '뒷면'},
    'tray': {'name': '용기(즉석밥류)', 'example': '즉석밥',
             'main': '표시면적의 2/3', 'info': '표시면적의 1/3'},
    'sticker': {'name': '스티커 부착', 'example': '냉동새우',
                'main': '스티커 면적의 1/2', 'info': '스티커 면적의 1/2'},
    'box': {'name': '상자', 'example': '오렌지주스',
            'main': '앞면·윗면·뒷면', 'info': '양측면'},
}

MAIN_PANEL_DEFINITION = (
    '용기·포장의 표시면 중 상표·로고 등이 인쇄되어 있어 소비자가 구매할 때 '
    '통상적으로 보게 되는 면')
INFO_PANEL_DEFINITION = (
    '용기·포장의 표시면 중 소비자가 쉽게 알아볼 수 있도록 표시사항을 모아서 '
    '표시하는 면')

# 주표시면에 인쇄되는 항목. `design_request` 가 갖고 있던 것을 여기로 옮겼다 —
# "어느 면에" 를 말하는 것이 여기 하나여야 한다.
MAIN_PANEL_FIELDS = ('prdlst_nm', 'content_weight', 'weight_calorie',
                     'ingredient_info')

# 정보표시면은 "표 또는 단락" 으로 모아 적는다. 다만 면적 100 cm² 미만은 뺀다 —
# 그 임계값은 constants.LABEL_REGULATIONS['area_thresholds']['small'] 과 같다.
INFO_PANEL_SHAPE = '표 또는 단락'

# 제품명의 일부로 쓴 원재료명·함량의 활자 하한은 **제품명 크기에 따라 갈린다.**
# 우리 LABEL_REGULATIONS 에는 이 조건부 규칙이 없었다.
NAME_FONT_PIVOT = 22.0      # 제품명 활자 크기 기준점(pt)
NAMED_INGREDIENT_MIN_LARGE = 14.0   # 제품명이 기준점 이상일 때
NAMED_INGREDIENT_MIN_SMALL = 7.0    # 미만일 때
# 주표시면에 쓴 특정 원재료명·함량(제품명의 일부가 아닌 경우)
MAIN_PANEL_INGREDIENT_MIN = 12.0


def named_ingredient_min(product_name_pt) -> float:
    """
    제품명 활자 크기로 정해지는 원재료명·함량 하한(pt).

    크기를 모르면 **작은 쪽 기준을 쓴다** — 큰 쪽(14pt)을 대면 모르는 것을 두고
    위반이라 말하게 된다.
    """
    if product_name_pt is None:
        return NAMED_INGREDIENT_MIN_SMALL
    return (NAMED_INGREDIENT_MIN_LARGE if product_name_pt >= NAME_FONT_PIVOT
            else NAMED_INGREDIENT_MIN_SMALL)


def describe(form_key: str) -> str:
    """의뢰서에 적을 한 줄. 모르는 형태면 빈 문자열."""
    form = PACKAGE_FORMS.get(form_key)
    if not form:
        return ''
    return '%s 포장 — 주표시면 %s / 정보표시면 %s' % (
        form['name'], form['main'], form['info'])


def form_choices() -> list[tuple]:
    """화면이 고르게 할 목록. (키, 보이는 이름)."""
    return [(key, '%s (예: %s)' % (form['name'], form['example']))
            for key, form in PACKAGE_FORMS.items()]
