"""
이론치로 영양성분표를 만드는 세 가지 계산.

공인기관 성적서 없이 표를 만드는 일이 흔하다. 그때 현장에서 쓰는 엑셀은
이렇게 생겼다.

    프로그램 100g   오차    오차범위 100g   환산값(g)   결과
    열량   299.87           300.325         300.325     299.40
    당류    33.74   15%      38.801          38.801      39
    나트륨 242.12   15%     278.438         278.438     280

세 걸음이다. **계산값**(레시피로 뽑은 이론치)에 **오차**를 성분별 방향대로
곱하고, 표시 단위로 반올림해 **적용값**을 얻는다. 열량은 반올림한 탄단지로
다시 계산해 표 안이 서로 맞게 한다.

이 파일은 그 세 걸음과, 그렇게 만든 표가 고열량·저영양 식품에 걸리는지를
본다. 규정 숫자는 전부 constants.py 에 있다 — 여기서는 그 숫자를 쓰기만 한다.

화면(nutrition_calc.js)도 같은 계산을 한다. 사용자가 값을 넣는 동안 서버를
부를 수는 없어서다. 둘이 어긋나지 않는지는 시험이 지킨다.
"""
from v1.label.constants import (
    CALORIE_FACTORS,
    HIENG_LNTRT_CRITERIA,
    HIENG_LNTRT_KIND_NAMES,
    HIENG_LNTRT_SODIUM_NOODLE,
    NUTRITION_TOLERANCE_UP,
)


def _number(value):
    """숫자로 읽을 수 있으면 숫자, 아니면 None. '5kcal 미만' 같은 표기는 None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(',', '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def tolerance_direction(field):
    """
    이 성분은 오차를 **어느 쪽으로** 물려야 안전한가.

        +1  높여 적는다 (실측이 표시량의 120% 미만이어야 하는 성분)
        -1  낮춰 적는다 (실측이 표시량의 80% 이상이어야 하는 성분)
    """
    return 1 if field in NUTRITION_TOLERANCE_UP else -1


# 열량은 오차를 직접 곱하지 않는다. 아래 apply_tolerance 주석을 보라.
TOLERANCE_SKIP = ('calories',)


def apply_tolerance(values, rate, mode='up'):
    """
    계산값에 오차를 물려 표시할 값을 만든다.

    values  {성분: 계산값}
    rate    보정폭(%). 0 이면 그대로 둔다.
    mode    'up'   실측 120% 무리만 높인다 (현장에서 쓰는 방식)
            'both' 실측 80% 무리도 함께 낮춘다 (규정이 정한 두 방향 모두)

    **열량에는 곱하지 않는다.** 열량은 탄수화물·단백질·지방이 정하는 값이라,
    따로 부풀리면 표 안이 서로 맞지 않게 된다. 보정한 탄단지로 다시 계산하는
    것이 맞다(calories_from_macros). 현장 엑셀도 그렇게 한다 — 오차 열이
    열량 줄에만 비어 있고, 결과는 보정된 탄단지의 합이다.

    Returns: {성분: 보정값}  숫자로 못 읽은 값은 그대로 돌려준다.

    **두 번 물리면 두 번 곱해진다.** 이 함수는 그것을 막지 못한다 — 계산값을
    따로 들고 있다가 늘 계산값에서 출발하는 것은 부르는 쪽의 몫이다.
    (영양성분 계산기가 입력 기준 환산에서 겪은 사고가 그것이다. 309 를 총량당
    으로 두 번 저장해 475 가 되고 731 이 됐다.)
    """
    try:
        percent = float(rate)
    except (TypeError, ValueError):
        return dict(values)
    if not percent:
        return dict(values)

    out = {}
    for field, raw in values.items():
        number = _number(raw)
        if number is None or field in TOLERANCE_SKIP:
            out[field] = raw
            continue
        way = tolerance_direction(field)
        if way < 0 and mode != 'both':
            out[field] = raw       # 낮추는 쪽은 골랐을 때만 건드린다
            continue
        out[field] = round(number * (1 + way * percent / 100.0), 6)
    return out


def calories_from_macros(values):
    """
    탄수화물·단백질·지방으로 열량을 계산한다. 규정이 정한 계수를 쓴다.

    **식이섬유와 당알코올은 탄수화물 안에 들어 있으면서 계수가 다르다.**
    탄수화물에서 그만큼을 빼고 각자의 계수로 센다. 이걸 빼먹으면 식이섬유가
    많은 제품에서 열량이 실제보다 높게 나온다.

    Returns: 열량(float) 또는 None (탄단지 중 하나라도 못 읽으면)
    """
    macros = {}
    for field in ('carbohydrates', 'proteins', 'fats'):
        number = _number(values.get(field))
        if number is None:
            return None
        macros[field] = number

    fiber = _number(values.get('dietary_fiber')) or 0.0
    alcohols = _number(values.get('sugar_alcohols')) or 0.0
    # 뺀 값이 음수가 되면 적은 값이 서로 어긋난 것이다. 그대로 두면 열량이
    # 줄어드는 이상한 계산이 되므로 0 에서 멈춘다.
    rest = max(macros['carbohydrates'] - fiber - alcohols, 0.0)

    total = (rest * CALORIE_FACTORS['carbohydrates']
             + fiber * CALORIE_FACTORS['dietary_fiber']
             + alcohols * CALORIE_FACTORS['sugar_alcohols']
             + macros['proteins'] * CALORIE_FACTORS['proteins']
             + macros['fats'] * CALORIE_FACTORS['fats'])
    for field in ('organic_acids', 'alcohol'):
        number = _number(values.get(field))
        if number:
            total += number * CALORIE_FACTORS[field]
    return round(total, 4)


def per_serving(values, per_100, serving):
    """
    100 g 당 값을 1회 제공량 기준으로 바꾼다.

    고열량·저영양 판정은 1회 제공량 기준인데 우리 저장값은 언제나 100 g 당이다.
    기준량을 모르면 판정하지 않는다 — 분모를 모르면서 곱하면 모든 수치의 뜻이
    바뀐다.

    per_100  값들이 몇 g 당인가 (보통 100)
    serving  1회 제공량(1회 섭취참고량)

    Returns: {성분: 환산값} 또는 None
    """
    base = _number(per_100)
    amount = _number(serving)
    if not base or not amount or base <= 0 or amount <= 0:
        return None
    factor = amount / base
    out = {}
    for field, raw in values.items():
        number = _number(raw)
        if number is not None:
            out[field] = round(number * factor, 6)
    return out


def hieng_lntrt(values, kind, noodle=False):
    """
    고열량·저영양 식품인가. **값은 1회 제공량 기준이어야 한다.**

    values  {성분: 1회 제공량 기준 값}
    kind    'snack'(간식용) | 'meal'(식사대용)
    noodle  용기면 중 유탕면·국수류인가 (나트륨 기준이 다르다)

    Returns: {'verdict': bool, 'kind': '간식용', 'hits': [사람이 읽을 줄 …]}
             판정할 수 없으면 verdict 는 None 이다 — **모르는 것과 아닌 것은
             다르다.** 아니라고 말해 놓고 실제로는 걸리는 제품이 나오면
             그 말을 믿은 사람이 다친다.
    """
    rules = HIENG_LNTRT_CRITERIA.get(kind)
    if not rules:
        return {'verdict': None, 'kind': '', 'hits': [],
                'why': '간식용인지 식사대용인지 정해야 판정할 수 있습니다.'}

    known = {}
    for field in ('calories', 'proteins', 'saturated_fats', 'sugars', 'natriums'):
        number = _number(values.get(field))
        if number is not None:
            known[field] = number
    if 'calories' not in known:
        return {'verdict': None, 'kind': HIENG_LNTRT_KIND_NAMES[kind], 'hits': [],
                'why': '열량이 없어 판정할 수 없습니다.'}

    from v1.label.constants import NUTRITION_DATA

    def limit_of(field, value):
        if field == 'natriums' and noodle and value == 600:
            return HIENG_LNTRT_SODIUM_NOODLE
        return value

    hits = []
    unknown = False
    for rule in rules:
        met = True
        words = []
        for field, sign, value in rule:
            if field not in known:
                met = False
                unknown = True
                break
            bound = limit_of(field, value)
            ok = known[field] > bound if sign == '>' else known[field] < bound
            label = NUTRITION_DATA.get(field, {}).get('label', field)
            unit = NUTRITION_DATA.get(field, {}).get('unit', '')
            words.append(f'{label} {known[field]:g}{unit} '
                         f'({"초과" if sign == ">" else "미만"} 기준 {bound:g}{unit})')
            if not ok:
                met = False
                break
        if met:
            hits.append(' + '.join(words))

    if hits:
        return {'verdict': True, 'kind': HIENG_LNTRT_KIND_NAMES[kind], 'hits': hits}
    if unknown:
        return {'verdict': None, 'kind': HIENG_LNTRT_KIND_NAMES[kind], 'hits': [],
                'why': '단백질·포화지방·당류·나트륨 중 비어 있는 값이 있어 '
                       '모든 기준을 다 보지 못했습니다.'}
    return {'verdict': False, 'kind': HIENG_LNTRT_KIND_NAMES[kind], 'hits': []}
