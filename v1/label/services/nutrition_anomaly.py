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

**"틀렸다" 가 아니라 "봐야 한다" 다.** 원본이 부실한 것일 수도, 우리 매핑이
밀린 것일 수도 있다. `mfds_nutrition.verify_row` 가 같은 교훈을 적어 두었다 —
폭을 좁게 잡았더니 멀쩡한 행이 무더기로 걸렸다.

못 잡는 것
──────────
순서는 알아도 **비율은 모른다.** "설탕 1순위인데 당류 5 g" 은 못 잡는다
(빵류는 실제로 그럴 수 있다). 잡는 것은 0 에 가까운 극단뿐이다.
"""

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
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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

    fats = _get(row, 'fats')
    sat, trans = _get(row, 'saturated_fats'), _get(row, 'trans_fats')
    if fats is not None and (sat is not None or trans is not None):
        part = (sat or 0) + (trans or 0)
        if part > fats + SLACK_G:
            found.append(('A3', HIGH,
                          '포화+트랜스가 지방보다 많다 (%.2f > %.2f)' % (part, fats)))

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
                              '%s 가 기준량을 넘는다 (%.2f > %.0f)' % (field, value, basis)))

    for field in GRAM_FIELDS + MG_FIELDS:
        value = _get(row, field)
        if value is not None and value < 0:
            found.append(('A5', HIGH, '%s 가 음수다 (%.2f)' % (field, value)))

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
                          '%d순위가 "%s" 인데 %s 가 %.2f%s' % (
                              order, name, field, value, UNIT.get(field, 'g'))))
            break
    return found


def check(row, sorted_text=None):
    """한 행을 다 잰다. 원재료 문구가 없으면 A 만 잰다."""
    found = check_internal(row)
    if sorted_text:
        found.extend(check_top_ingredients(row, sorted_text))
    return found
