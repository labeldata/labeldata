"""
모르는 원료가 **표시값을 바꿀 수 있는가**를 가른다.

배합에 향료 0.05 % 가 들어간다. 그 향료의 영양성분을 우리는 모른다. 그러면
영양성분표를 못 만드는가? 아니다 — 그 양으로는 **무엇이 들어 있든** 표에 적히는
숫자가 달라지지 않는 경우가 대부분이다. 그것을 증명해서 묻지 않는 것이 이 파일의
일이다.

원료 보관함 172 개 중 향료·색소·첨가물이 절반 가까이인데, 식약처 DB 에는 그런
부원료가 없다. 하나씩 성적서를 받는 수밖에 없다고 결론 내리기 전에, **애초에
필요 없는 것**을 걷어낸다.

정적 임계값은 틀린다
────────────────────
처음에는 "열량 반올림 폭이 5 kcal 이니 기여가 5 kcal 미만이면 안전" 으로 잡으려
했다. 틀렸다. 반올림 경계에 앉아 있으면 폭보다 작은 기여도 표시를 바꾼다.

    287.0 kcal → '285'      287.6 kcal → '290'     (기여 0.6 kcal)
      7.4 kcal → '5'          8.0 kcal → '10'      (기여 0.6 kcal)

그래서 폭을 견주지 않고 **표시값을 직접 견준다.** 아는 값으로 한 번, 아는 값에
모르는 원료의 최대 기여를 더해서 한 번 — display_value() 가 같은 글자를 내놓으면
그 원료는 몰라도 된다. 근사가 아니라 증명이다.

최대 기여는 어떻게 아는가
─────────────────────────
성분마다 물리적으로 넘을 수 없는 상한이 있다. 지방은 100 g/100 g 을 넘지
못하고, 열량은 그 지방이 전부여도 900 kcal 을 넘지 못한다. 나트륨의 상한은
정제소금 그 자체다(100 g 중 나트륨분 39.3 g).

원료가 배합비 r % 로 들어가면 100 g 당 최대 기여는 상한 × r/100 이다. 이보다
많이 들어올 수는 없다. 그래서 "최악의 원료였어도 표시가 같다" 를 말할 수 있다.
"""
from v1.label.services.nutrition_calc import _number, display_value

# ─────────────────────────────────────────────────────────────────────────────
# 성분별 상한 (100 g 당)
#
# 'physical' 은 넘을 수 없는 값이고 'practical' 은 식품 원료로 쓰이는 범위의
# 상한이다. 둘을 갈라 두는 이유는, practical 을 근거로 "몰라도 된다" 고 할 때는
# 그 가정이 무엇인지 화면에서 말할 수 있어야 하기 때문이다.
# ─────────────────────────────────────────────────────────────────────────────
NUTRIENT_MAX = {
    # 질량 성분 — 100 g 안에 100 g 을 넘게 들어갈 수 없다
    'carbohydrates':  (100.0, 'physical'),
    'proteins':       (100.0, 'physical'),
    'fats':           (100.0, 'physical'),
    'sugars':         (100.0, 'physical'),
    'dietary_fiber':  (100.0, 'physical'),
    'sugar_alcohols': (100.0, 'physical'),
    'saturated_fats': (100.0, 'physical'),   # 지방의 부분집합이라 지방 상한과 같다
    'trans_fats':     (100.0, 'physical'),

    # 열량 — 100 g 이 전부 지방이어도 9 kcal/g × 100 g
    'calories':       (900.0, 'physical'),

    # 나트륨 — 정제소금(NaCl) 100 g 의 나트륨분.
    # 22.99 / 58.44 × 100 g = 39.34 g = 39,340 mg
    'natriums':       (39340.0, 'physical'),

    # 콜레스테롤 — 물리 상한(순 콜레스테롤 100 g)은 식품 원료로 의미가 없다.
    # 실제로 가장 높은 축인 난황 분말이 2,000 mg/100 g 대이므로 그 위로 잡는다.
    # **가정이다.** 순 콜레스테롤을 원료로 쓰는 배합에서는 이 판정을 믿으면 안 된다.
    'cholesterols':   (3000.0, 'practical'),
}

# 영양성분표에 적는 것들. 여기 없는 성분은 표시 대상이 아니므로 판정하지 않는다.
DISPLAY_FIELDS = (
    'calories', 'carbohydrates', 'sugars', 'proteins', 'fats',
    'saturated_fats', 'trans_fats', 'cholesterols', 'natriums',
)


def max_contribution(field, ratio_pct):
    """
    이 원료가 배합비 ratio_pct % 로 들어갈 때 100 g 당 최대 기여.

    배합비를 모르면 None 을 돌려준다 — 0 으로 메우지 않는다. 배합비를 모르는
    원료는 "영향이 없다" 가 아니라 "잴 수 없다" 이고, 둘은 전혀 다르다.
    """
    ratio = _number(ratio_pct)
    if ratio is None or ratio < 0:
        return None
    bound = NUTRIENT_MAX.get(field)
    if bound is None:
        return None
    return bound[0] * ratio / 100.0


def assess(known_values, unknown_ratios, fields=DISPLAY_FIELDS):
    """
    아는 값 + 모르는 원료들의 최대 기여로, 성분마다 표시가 흔들리는지 본다.

    known_values    {성분: 100g 당 값}   — 영양성분을 아는 원료들의 합
    unknown_ratios  [배합비(%), ...]      — 영양성분을 모르는 원료들

    Returns
        {
          'assessable': bool,          배합비를 다 알아서 판정할 수 있었는가
          'safe':     [성분, ...],     몰라도 표시값이 같다
          'blocking': [성분, ...],     모르면 표를 못 만든다
          'detail':   {성분: {...}},   근거 (아는 값 · 최대 기여 · 양끝 표시값)
        }

    **판정은 배합마다 다르다.** 같은 향료라도 다른 배합에서는 걸릴 수 있다 —
    아는 값이 반올림 경계 어디에 앉아 있느냐가 함께 정하기 때문이다. 그래서
    원료에 "안전" 을 새겨 두지 않고 배합을 계산할 때마다 다시 본다.
    """
    ratios = [_number(r) for r in (unknown_ratios or [])]
    assessable = all(r is not None and r >= 0 for r in ratios)

    safe, blocking, detail = [], [], {}

    for field in fields:
        known = _number(known_values.get(field)) or 0.0

        if not assessable:
            blocking.append(field)
            detail[field] = {'known': known, 'max_extra': None,
                             'low': display_value(field, known), 'high': None,
                             'reason': '배합비를 모르는 원료가 있다'}
            continue

        extra = 0.0
        for r in ratios:
            c = max_contribution(field, r)
            if c is None:
                extra = None
                break
            extra += c

        if extra is None:
            blocking.append(field)
            detail[field] = {'known': known, 'max_extra': None,
                             'low': display_value(field, known), 'high': None,
                             'reason': '상한을 모르는 성분이다'}
            continue

        low = display_value(field, known)
        high = display_value(field, known + extra)
        bound_kind = NUTRIENT_MAX[field][1]

        detail[field] = {'known': known, 'max_extra': extra,
                         'low': low, 'high': high, 'bound': bound_kind}

        if low == high:
            safe.append(field)
        else:
            blocking.append(field)
            detail[field]['reason'] = '최악이면 %s → %s 로 바뀐다' % (low, high)

    return {'assessable': assessable, 'safe': safe,
            'blocking': blocking, 'detail': detail}


def needed_fields(known_values, unknown_items, fields=DISPLAY_FIELDS):
    """
    원료마다 **무엇을 알아야 하는지**를 성분 단위로 돌려준다.

    unknown_items  [(키, 배합비), ...]
    Returns        {키: [모자란 성분, ...]}   빈 목록이면 아무것도 안 물어도 된다

    성분 단위여야 하는 이유
    ───────────────────────
    "이 원료를 알아야 하는가" 로 물으면 나트륨 때문에 거의 모두 '알아야 함' 이
    된다. 나트륨의 물리 상한이 정제소금(39,340 mg/100 g)이라, 배합비 0.05 %
    만 돼도 최대 19.7 mg 이고 반올림 폭 5 mg 을 넘기 때문이다.

        0.050 % → 19.670 mg   걸린다
        0.010 % →  3.934 mg   안전
        0.005 % →  1.967 mg   안전

    그런데 같은 향료가 열량·지방·단백질에서는 안전하다. 그래서 판정을 원료가
    아니라 성분에 붙인다 — 사용자는 규격서 한 장을 통째로 구하는 대신 **숫자
    하나(나트륨)** 만 넣으면 된다. 아홉 개를 여덟 개 줄이는 것이 이 함수다.

    상한을 낮춰 잡아 '안전' 을 늘리고 싶은 유혹이 있는데, 그러려면 "이 향료에는
    소금이 없다" 는 가정이 필요하다. 조미향료·시즈닝에는 실제로 소금이 들어
    있으므로 그 가정은 조용히 틀린다. 가정으로 덮지 않고 물어보는 쪽을 택한다.
    """
    out = {}
    for key, ratio in (unknown_items or []):
        out[key] = assess(known_values, [ratio], fields=fields)['blocking']
    return out
