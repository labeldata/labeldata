# -*- coding: utf-8 -*-
"""
적재한 식약처 영양성분DB 에서 **이상해 보이는 행**을 찾는다.

왜 이렇게 찾나
──────────────
배합비를 모른다. 공공DB 는 성분 값만 주고, 품목보고는 원재료를 **순서대로만**
준다(많이 쓴 것부터 적게 되어 있다). 그래서 "이 값이 맞다" 는 증명할 수 없고,
**"이 값은 그럴 수가 없다" 를 찾는 것이 최선**이다.

두 갈래로 잰다.

  A. 성분끼리의 모순   원재료가 없어도 성립한다. 당류가 탄수화물보다 많을
                       수는 없다 — 부분집합이기 때문이다. 오탐이 거의 없다.
  B. 상위 원료와 0     설탕이 1순위인데 당류가 0 이면 둘 중 하나는 틀렸다.
  C. 열량과 성분       성분으로 **낼 수 있는 범위** 안에 열량이 있는가.

**"틀렸다" 가 아니라 "봐야 한다" 다.** 원본이 부실한 것일 수도, 우리 매핑이
밀린 것일 수도 있다. `mfds_nutrition.verify_row` 가 같은 교훈을 적어 두었다 —
폭을 좁게 잡았더니 멀쩡한 행이 무더기로 걸렸다.

못 잡는 것
──────────
순서는 알아도 **비율은 모른다.** "설탕 1순위인데 당류 5 g" 은 못 잡는다
(빵류는 실제로 그럴 수 있다). 잡는 것은 0 에 가까운 극단뿐이다.
"""

from v1.label.constants import (
    NUTRITION_CALORIE_TOLERANCE,
    NUTRITION_ORGANIC_ACID_SLACK_KCAL,
)
from v1.label.services.nutrition_calc import _number

# 재는 여유. 소수 둘째 자리 반올림과 원본의 자릿수 차이를 이것으로 흡수한다.
# 좁게 잡으면 멀쩡한 행이 걸린다.
SLACK_G = 0.5

# 상위 몇 순위까지를 "상위" 로 보는가. 넷째부터는 향료·첨가물이 흔하다.
TOP_N = 3

HIGH = 'high'     # 그럴 수가 없다
WATCH = 'watch'   # 봐야 한다

# 어긋난 폭이 이보다 작으면 '봐야 함' 으로 내린다. 물리적으로 불가능한 것은
# 맞지만 그 표를 써도 표시가 크게 틀어지지는 않는다 — 같은 무게로 세우면
# 진짜 큰 어긋남(당류 104 > 탄수화물 7)이 그 안에 묻힌다.
SMALL_GAP_G = 2.0


def _num(value):
    """
    숫자로 읽는다. **적재 쪽과 같은 함수를 쓴다.**

    예전에는 여기서 float() 만 썼다. 그런데 이 원본은 '1,670.000' 처럼 쉼표가
    섞여 온다(mfds_nutrition 이 표본 1,500 건에서 1,665 개를 셌다). float() 이
    None 을 돌려주면 check_energy 는 `return []` 로 **행 전체를 조용히 검사
    면제**한다 — 예외도 로그도 없어 밖에서는 '이상 없음' 과 구분되지 않는다.
    """
    return _number(value)


def _get(row, key):
    return _num(row.get(key) if isinstance(row, dict) else getattr(row, key, None))


# ── A. 성분끼리의 모순 ─────────────────────────────────────────────────
#
# 부분집합·합계 관계는 **어떤 식품이든 성립한다.** 배합을 몰라도 되고
# 원재료가 없어도 된다. 그래서 여기가 가장 확실하다.
SUBSET_RULES = (
    ('A1', 'sugars', 'carbohydrates', '당류가 탄수화물보다 많다'),
    ('A2', 'dietary_fiber', 'carbohydrates', '식이섬유가 탄수화물보다 많다'),
)

# g 으로 오는 성분. 기준량(대개 100 g)을 넘을 수 없다.
GRAM_FIELDS = ('proteins', 'fats', 'carbohydrates', 'sugars',
               'dietary_fiber', 'saturated_fats', 'trans_fats', 'moisture', 'ash')

# mg 으로 오는 성분 — 여기서는 음수만 본다(상한은 성분마다 달라 따로 잰다).
MG_FIELDS = ('natriums', 'cholesterols', 'calcium', 'iron', 'potassium')


def check_internal(row):
    """성분끼리 어긋난 것. [(규칙, 심각도, 설명)]"""
    found = []

    for code, part, whole, why in SUBSET_RULES:
        a, b = _get(row, part), _get(row, whole)
        if a is None or b is None:
            continue
        if a > b + SLACK_G:
            # 어긋난 폭이 작으면 '봐야 함' 이다. 갈비탕의 식이섬유 1.9 >
            # 탄수화물 0.4 는 물리적으로 불가능하지만, 그 표를 그대로 써도
            # 표시가 크게 틀어지지는 않는다. 같은 무게로 세우면 진짜 큰
            # 어긋남이 그 안에 묻힌다.
            gap = a - b
            found.append((code, HIGH if gap >= SMALL_GAP_G else WATCH,
                          '%s (%.2f > %.2f)' % (why, a, b)))

    # 지방 ≥ 트랜스지방 + 포화지방 + 콜레스테롤
    #
    # 식약처 「영양성분 등록 요령」의 검토 규칙이 그대로 이것이다. **콜레스테롤이
    # 빠져 있었다.** 단위가 달라서(mg) 그냥 더하면 1,000 배 틀리므로 g 으로
    # 환산해 넣는다 — 요령도 '/1,000' 을 괄호에 적어 둔다.
    #
    # 콜레스테롤은 지방산이 아니라 스테롤이라 화학적으로는 '지방' 의 부분집합이
    # 아니지만, 요령이 이 셋을 함께 세라고 정했고 등록 화면이 그 잣대로 막는다.
    # 우리가 더 느슨하면 여기서는 통과한 표가 등록에서 거절된다.
    fats = _get(row, 'fats')
    sat, trans = _get(row, 'saturated_fats'), _get(row, 'trans_fats')
    chol = _get(row, 'cholesterols')
    if fats is not None and (sat is not None or trans is not None
                             or chol is not None):
        part = (sat or 0) + (trans or 0) + (chol or 0) / 1000.0
        if part > fats + SLACK_G:
            found.append(('A3', HIGH,
                          '포화+트랜스+콜레스테롤이 지방보다 많다 (%.2f > %.2f)'
                          % (part, fats)))

    # 기준량을 넘는 성분. 100 g 짜리 행에 지방 120 g 은 있을 수 없다.
    #
    # **g 기준일 때만 잰다.** 100 mL 기준 행에서는 비중이 1 보다 크면 성분
    # 무게가 그 숫자를 넘는 것이 정상이다 — 꿀 100 mL 는 140 g 쯤 되고,
    # 그러면 탄수화물만으로도 100 을 넘는다. 부피와 무게를 같은 자로 재면
    # 멀쩡한 행이 무더기로 걸린다.
    basis = _get(row, 'basis_amount')
    unit = (row.get('basis_unit') if isinstance(row, dict)
            else getattr(row, 'basis_unit', '')) or ''
    if basis and basis > 0 and str(unit).lower() == 'g':
        for field in GRAM_FIELDS:
            value = _get(row, field)
            if value is not None and value > basis + SLACK_G:
                found.append(('A4', HIGH,
                              '%s 이 기준량을 넘는다 (%.2f > %.0f)'
                              % (name_of(field), value, basis)))

    for field in GRAM_FIELDS + MG_FIELDS:
        value = _get(row, field)
        if value is not None and value < 0:
            found.append(('A5', HIGH,
                          '%s 이 음수다 (%.2f)' % (name_of(field), value)))

    return found


# ── B. 상위 원료와 0 ───────────────────────────────────────────────────
#
# 표시 순서는 **많이 쓴 순**이다(식품등의 표시기준). 그래서 앞자리에 있다는
# 것은 "이 제품의 상당 부분" 이라는 뜻이고, 그 원료가 반드시 가진 성분이
# 0 이면 둘 중 하나가 틀렸다.
#
# 이름은 **부분 일치**로 본다. '정제소금' · '천일염' 처럼 앞뒤가 붙어 오고,
# '설탕' 은 '흑설탕' 안에도 들어 있다.
MARKERS = (
    # (규칙, 성분, 쓰이면 반드시 있는 원료들, 몇 순위까지, 이 값 이하면 이상)
    ('B1', 'sugars', ('설탕', '백설탕', '흑설탕', '정백당', '과당', '물엿',
                      '올리고당', '꿀', '포도당', '액상과당', '자당'), 2, 0.5),
    ('B2', 'fats', ('식용유', '대두유', '옥수수유', '해바라기유', '팜유', '버터',
                    '마가린', '쇼트닝', '유지', '참기름', '들기름'), 3, 0.5),
    # **소금은 1순위일 때만 본다.**
    #
    # 다른 원료와 다르다. 설탕·유지·곡분은 앞자리면 상당량이지만, 소금은
    # 2순위여도 0.1 % 인 일이 흔하다 — 곡물 하나에 미량 첨가물 여럿인
    # 뻥튀기가 그렇다. 가짓수를 다섯으로 올려도 그 구조는 그대로라 832 건이
    # 남았고, 표본은 전부 나트륨 38~62 mg 인 뻥튀기였다(정상이다).
    #
    # 소금이 1순위인 제품은 소금 자체이거나 조미료류다. 그때 나트륨이
    # 100 mg 도 안 되면 그것은 확실히 이상하다.
    ('B3', 'natriums', ('정제소금', '천일염', '소금', '간장', '된장', '고추장'),
     1, 100.0),
    # 원물 이름('쌀'·'옥수수'·'감자')은 뺐다. 그 원물로 **기름을 짜면**
    # 탄수화물이 0 인 것이 정상인데, 부분 일치라 "옥수수배아" 가 걸렸다
    # (딱한번만짜서만든옥수수유). 가공된 곡분·전분·당류만 본다.
    ('B4', 'carbohydrates', ('밀가루', '쌀가루', '전분', '설탕', '물엿'), 1, 0.5),
    ('B5', 'proteins', ('돼지고기', '쇠고기', '닭고기', '대두', '분리대두단백',
                        '유청단백', '계란', '난백', '탈지분유'), 3, 0.5),
)

UNIT = {'natriums': 'mg'}

# 목록은 **사람이 읽는다.** 'sugars 가 기준량을 넘는다' 로 적어 두면 그 칸이
# 무엇인지 알아야 읽히는데, 관리자 화면에서 이것을 보는 사람이 우리 칸 이름을
# 알아야 할 까닭이 없다.
NAMES = {
    'calories': '열량', 'proteins': '단백질', 'fats': '지방',
    'carbohydrates': '탄수화물', 'sugars': '당류', 'dietary_fiber': '식이섬유',
    'saturated_fats': '포화지방', 'trans_fats': '트랜스지방',
    'natriums': '나트륨', 'cholesterols': '콜레스테롤',
    'moisture': '수분', 'ash': '회분',
    'calcium': '칼슘', 'iron': '철', 'potassium': '칼륨',
}


def name_of(field):
    return NAMES.get(field, field)


# 2순위 이상을 "상위" 로 보려면 원재료가 이만큼은 있어야 한다.
#
# **순위는 비율을 말해 주지 않는다.** 원재료가 셋뿐인 뻥과자에서 천일염이
# 2순위여도 실제로는 0.1 % 일 수 있다 — 나트륨 10 mg 이 정상인 것이다.
# 운영에서 B3(소금) 1,877 건의 상당수가 그런 행이었다. 스무 가지가 들어간
# 과자에서 2순위면 이야기가 다르다.
#
# 1순위는 개수와 상관없이 본다 — 제일 많이 쓴 것이므로.
RANK2_MIN_ITEMS = 5


def top_ingredients(sorted_text, count=TOP_N):
    """
    정렬해 둔 원재료 문구에서 앞자리 몇 개.

    **괄호 안의 쉼표로 자르면 안 된다.** "혼합제제(설탕, 향료), 밀가루" 를
    그냥 쉼표로 자르면 둘째 자리가 "향료)" 가 되어, 있지도 않은 원료가
    2순위로 올라간다. 괄호 깊이를 세면서 자른다.

    괄호 안은 그 원료의 **하위 원료**라 이름에서 뗀다 — 우리가 보는 것은
    "이 제품이 무엇을 많이 썼나" 이지 그 원료가 무엇으로 만들어졌나가 아니다.
    """
    if not sorted_text:
        return []

    out, current, depth = [], [], 0
    for char in str(sorted_text):
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth = max(0, depth - 1)
        elif char == ',' and depth == 0:
            name = ''.join(current).split('(')[0].strip()
            if name:
                out.append(name)
                if len(out) >= count:
                    return out
            current = []
            continue
        current.append(char)

    name = ''.join(current).split('(')[0].strip()
    if name and len(out) < count:
        out.append(name)
    return out


def check_top_ingredients(row, sorted_text):
    """상위 원료가 있어야 할 성분을 안 들고 있는 것. [(규칙, 심각도, 설명)]"""
    names = top_ingredients(sorted_text)
    if not names:
        return []
    # 몇 가지가 들어갔는지. 2순위부터는 이 수에 따라 뜻이 달라진다.
    total = len(top_ingredients(sorted_text, count=99))

    found = []
    for code, field, markers, rank, floor in MARKERS:
        value = _get(row, field)
        if value is None or value > floor:
            continue
        for order, name in enumerate(names[:rank], start=1):
            if order > 1 and total < RANK2_MIN_ITEMS:
                break        # 가짓수가 적으면 2순위도 미량일 수 있다
            hit = next((m for m in markers if m in name), None)
            if not hit:
                continue
            found.append((code, HIGH if order == 1 else WATCH,
                          '%d순위가 "%s" 인데 %s 이 %.2f%s' % (
                              order, name, name_of(field), value,
                              UNIT.get(field, 'g'))))
            break
    return found


def check(row, sorted_text=None):
    """
    한 행을 다 잰다. 원재료 문구가 없으면 원재료가 필요 없는 규칙만 잰다.

    **C 를 빠뜨렸던 자리다.** '다 잰다' 고 적어 두고 A(+B)만 불렀다. 지금은
    명령이 규칙을 하나씩 직접 부르고 있어 드러나지 않았지만, 화면이나 다른
    서비스가 이 진입점을 쓰는 순간 열량 규칙이 조용히 빠진다 — 터지지 않으므로
    아무도 모른다. 이 저장소가 AMT_NUM 매핑에서 거듭 경고한 실패 모양이다.
    """
    found = check_internal(row)
    found.extend(check_energy(row))
    if sorted_text:
        found.extend(check_top_ingredients(row, sorted_text))
    return found


# ── C. 열량이 성분과 맞는가 ────────────────────────────────────────────
#
# 식약처 「영양성분 등록 요령」의 검토 규칙 1 이다. 요령이 정한 폭이 ±20 %
# 이고, 그 수는 constants 에 한 번만 적혀 있다.
#
# 왜 이 규칙이 필요한가 — 나머지가 거의 아무것도 못 재기 때문이다
# ─────────────────────────────────────────────────────────────────
# `mfds_nutrition.verify_row` 는 질량 합(수분+단백질+지방+회분+탄수화물)을
# 본다. 그런데 **수분·회분은 실험실이 잰 행에만 있다.** 가공식품 행은 제조사
# 신고값이라 표시 9 종밖에 없다. 34 만 건 적재에서 실제로 이렇게 나왔다.
#
#     검산 통과     10,815 ( 3.2 %)
#     검산 어긋남      846 ( 0.2 %)
#     못 잼        328,894 (96.6 %)   ← 여기가 통째로 비어 있었다
#
# 이 규칙은 **표시 9 종만으로 성립한다.** 가공식품 행이 가진 것이 정확히
# 그것이고, 우리 원료에 붙는 행도 100 % 아홉 항목을 다 들고 있다.
#
# 기준량이 g 이든 mL 이든 잰다
# ────────────────────────────
# A4 는 g 일 때만 쟀다. 100 mL 를 g 자로 재면 비중 때문에 멀쩡한 행이 걸려서다.
# 이 규칙은 다르다 — **같은 기준량 안에서 성분과 열량을 견주는 것**이라
# 그 기준량이 무엇이든 관계가 성립한다. 부피 기준 5 만 행도 잴 수 있다.

# 상한을 넘은 폭이 상한의 이만큼이면 '그럴 수가 없다' 로 본다.
ENERGY_HIGH_RATIO = 0.5

# 보이지 않는 유기산 몫은 constants 에 한 번만 적혀 있다 — 적재 검산
# (mfds_nutrition.verify_row)도 같은 이유로 같은 수를 쓴다.
ORGANIC_ACID_SLACK_KCAL = NUTRITION_ORGANIC_ACID_SLACK_KCAL

# 알코올이 든 식품. **이름으로 가릴 수밖에 없다** — 컬럼이 없기 때문이다.
# 놓친 이름이 있으면 그 행은 오탐으로 남는다. 완전하지 않다는 것을 알고 쓴다.
ALCOHOL_WORDS = ('주류', '소주', '맥주', '막걸리', '탁주', '약주', '청주',
                 '위스키', '와인', '포도주', '사케', '청하', '고량주',
                 '증류주', '발효주', '리큐르', '브랜디', '보드카', '럼',
                 '진로', '하이볼', '칵테일', '과실주', '살균탁주')


def _text_of(row):
    """이름·분류를 한 줄로 이어 붙인다. 이름으로 가릴 때 쓴다."""
    parts = []
    for key in ('food_nm_kr', 'db_grp_nm', 'db_class_nm', 'food_cat1_nm'):
        value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
        if value:
            parts.append(str(value))
    return ' '.join(parts)


def has_alcohol(row):
    """알코올이 들었을 법한 행인가. 들었다면 상한을 잴 수 없다."""
    text = _text_of(row)
    return any(word in text for word in ALCOHOL_WORDS)


def energy_bounds(row):
    """
    이 행의 열량이 있을 수 있는 범위. (표기, 하한, 엄격한 하한, 상한)
    또는 잴 수 없으면 None.

    탄수화물 1 g 이 낼 수 있는 열량은 **0 에서 4 사이**다. 전분·당류는 4,
    식이섬유 2, 당알콜 2.4, 타가토스 1.5, 알룰로오스·에리스리톨 0. 어느 몫이
    무엇인지는 이 DB 가 말해 주지 않는다(컬럼이 없다). 그러니 알 수 있는 것은
    범위뿐이다.

    하한이 둘인 까닭
    ────────────────
    처음에는 "당류만은 반드시 4 니까 그 몫은 못 내려간다" 를 하한으로 삼았다.
    **그런데 같은 저장소의 CALORIE_FACTORS 가 그 말의 반례를 갖고 있다** —
    타가토스 1.5 · 알룰로오스 0 이고, 둘 다 단당류라 신고 당류에 합산된다.
    알룰로오스 시럽(당류 70 g · 표기 20 kcal)은 정상인데 하한 280 으로 걸렸다.

    그래서 하한을 둘로 나눈다.

        strict  단백질*4 + 지방*9          어떤 감미료를 써도 못 내려간다
        lower   strict + 당류*4            희소당을 안 썼다면 여기가 바닥

    strict 를 넘으면 '그럴 수가 없다', lower 만 넘으면 '봐야 함' 이다.
    """
    energy = _get(row, 'calories')
    if energy is None:
        return None

    values = {}
    for field in ('carbohydrates', 'proteins', 'fats'):
        value = _get(row, field)
        if value is None:
            return None     # 셋 중 하나라도 없으면 잴 수 없다
        values[field] = value

    sugars = _get(row, 'sugars')
    # 음수가 섞인 행은 A5 가 이미 잡는다. 여기서 또 재면 상·하한이 뒤집혀
    # '전부 당·전분으로 세도 -20.0 kcal' 같은 읽을 수 없는 문장이 남는다.
    if any(v < 0 for v in values.values()) or (sugars is not None and sugars < 0):
        return None

    carb = values['carbohydrates']
    strict = values['proteins'] * 4 + values['fats'] * 9
    lower = strict + (min(sugars, carb) if sugars is not None else 0.0) * 4
    return energy, lower, strict, carb * 4 + strict


def check_energy(row):
    """열량이 성분으로 낼 수 있는 범위 안에 있는가. [(규칙, 심각도, 설명)]"""
    bounds = energy_bounds(row)
    if bounds is None:
        return []
    energy, lower, strict, upper = bounds

    # 위쪽 담장 — 알코올이 든 행에는 담장을 세울 수 없다
    if not has_alcohol(row):
        room = max(upper * NUTRITION_CALORIE_TOLERANCE, ORGANIC_ACID_SLACK_KCAL)
        if energy > upper + room:
            gap = energy - upper
            return [('C1',
                     HIGH if gap >= max(upper * ENERGY_HIGH_RATIO,
                                        ORGANIC_ACID_SLACK_KCAL) else WATCH,
                     '성분이 이 열량을 설명하지 못한다 (표기 %.1f · 탄단지를 '
                     '전부 당·전분으로 세도 %.1f)' % (energy, upper))]

    # 아래쪽 담장 — 여기는 보이지 않는 성분이 도와줄 수 없다. 없는 열량을
    # 만들어 내는 성분은 없기 때문이다.
    if energy < lower - max(lower * NUTRITION_CALORIE_TOLERANCE, 5.0):
        beyond_strict = energy < strict - max(strict * NUTRITION_CALORIE_TOLERANCE, 5.0)
        return [('C2', HIGH if beyond_strict else WATCH,
                 '%s만으로도 이보다 높다 (표기 %.1f · 최소 %.1f)'
                 % ('단백질·지방' if beyond_strict else '당류·단백질·지방',
                    energy, strict if beyond_strict else lower))]

    return []
