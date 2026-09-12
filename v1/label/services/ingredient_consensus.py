# -*- coding: utf-8 -*-
"""
같은 품목보고번호를 쓰는 다른 곳이 **같게 적었는가.** 개수만 말한다.

같은 번호는 법적으로 같은 품목이다. 그러니 표시명·알레르기·GMO·식품유형은
어느 회사가 적어도 같아야 하고, 다르다면 **한쪽이 잘못 적었을 가능성**이 있다.
지금은 같은 조사를 회사 수만큼 반복하면서 서로 다르게 적고 있다.

값을 보여 준다 — 다를 때만
─────────────────────────
처음에는 개수만 말하려 했다. 값을 보이면 베낄 테고, 베낀 값이 틀렸으면 우리
책임이 된다고 봤기 때문이다.

그런데 **개수만으로는 판단할 수가 없다.** "다수는 다르게 적었습니다" 를 본
사람이 할 수 있는 일이 없다 — 무엇이 다른지 모르니 고칠지 말지를 정할 수 없고,
결국 규격서를 처음부터 다시 찾아야 한다. 그러면 이 기능이 없는 것과 같다.

그리고 여기서 견주는 것들은 **라벨에 인쇄되는 공개 정보**다. 원재료 표시명·
알레르기·GMO·식품유형은 제품을 사면 누구나 읽는다. 배합비·거래처·단가와는
성격이 전혀 다르다 — 그쪽은 이 표에 있지도 않다.

그래서 **다를 때만 값을 보이고, 건수를 함께 붙인다.** 같으면 "같습니다" 로
끝낸다. 판단의 재료는 주되 판단은 하지 않는 자리는 그대로다 — 다수가 옳다는
말은 어디에도 적지 않는다.

**누가 적었는지는 끝까지 보여 주지 않는다.** 값은 라벨에 인쇄되지만 "어느
회사가 이 원료를 쓰는가" 는 인쇄되지 않는다.

번호는 맞는데 **딴 원료를 적어 둔 줄**이 있다
────────────────────────────────────────────
운영에서 이런 것이 나왔다. 번호 198301900201248 은 식약처에 **밀가루**(강력
밀가루 제빵용)로 등록돼 있는데, 같은 번호를 쓰는 다른 줄들이 이랬다.

    원재료 표시명   대두 100% · 설탕 · 밀(밀/미국산, 호주산)
    식품유형        설탕 · 혼합간장
    알레르기        대두 · 밀 · 밀, 고등어

**혼합간장과 설탕은 밀가루가 아니다.** 번호를 잘못 넣은 줄이고, 그것을 "다른
곳은 이렇게 적었습니다" 로 보이면 밀가루를 등록한 사람에게 **간장의 알레르기**를
권하는 셈이 된다.

번호가 식약처에 있는지만 보는 것으로는 못 막는다. 번호 자체는 실재하기
때문이다. **그 줄이 정말 그 품목인지**를 봐야 한다 — 식약처 등록 정보가
그 잣대다. 식품유형이 어긋나거나 원료명이 딴판인 줄은 집계에서 뺀다.

빼는 쪽으로 기운다. 잘못 낀 줄 하나가 남는 것보다 멀쩡한 줄 하나가 빠지는
편이 낫다 — 앞은 틀린 근거를 주고, 뒤는 근거가 조금 적어질 뿐이다.

잘못된 번호를 걸러야 말이 된다
──────────────────────────────
이 기능을 처음 재 봤을 때(measure_ingredient_pool) 이런 것이 나왔다.

    198301900201248
      식품유형  밀가루 | 설탕 | **혼합간장**
      알레르기  대두 | 땅콩 | 밀

같은 품목을 다르게 적은 것이 아니라 **그 번호가 식약처에 아예 없었다.**
그때는 이것 때문에 기능을 접었다. 지금은 번호 검증(report_no_check)이 생겨서,
**식약처에 실재하는 번호로 한정**하면 그 오염이 빠진다.

그 조건이 이 기능의 전제다. 빼면 안 된다.
"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# 견주는 항목. **공시 정보이거나 그 파생**뿐이다.
# 배합비·거래처·단가는 영업비밀이라 이 표에 있지도 않고 여기 들어올 일도 없다.
FIELDS = (
    ('ingredient_display_name', '원재료 표시명'),
    ('allergens', '알레르기'),
    ('gmo', 'GMO'),
    ('prdlst_dcnm', '식품유형'),
)

# 이만큼은 돼야 "다른 곳" 이라고 말할 수 있다. 한 곳뿐이면 견줄 것이 없다.
MIN_OWNERS = 2

# 다른 값을 몇 가지까지 보일까. 늘어놓으면 고르는 일이 되고, 그건 이
# 화면이 할 일이 아니다 — 규격서를 보고 정하는 것이 맞다.
MAX_VARIANTS = 3

# 너무 긴 값은 줄인다. 원재료명은 300 자가 넘는다.
MAX_LEN = 120


def _display(rows, field, key):
    """견주기용으로 눌러 둔 값을 **원래 글자**로 되돌린다."""
    for r in rows:
        raw = str(r.get(field) or '').strip()
        if raw and _key(raw) == key:
            return raw[:MAX_LEN] + ('…' if len(raw) > MAX_LEN else '')
    return key[:MAX_LEN]


def _key(value):
    """견줄 때만 쓰는 형태. 공백·대소문자 차이로 갈렸다고 하면 안 된다."""
    return ' '.join(str(value or '').split()).lower()


def _registered(report_no):
    """식약처 등록 정보. 없으면 None — 그때는 이 기능을 돌리지 않는다."""
    from v1.label.services import item_lookup

    try:
        item, _matched = item_lookup.find_exact(report_no)
    except Exception:
        logger.exception('[원료 합치] 번호 조회 실패 (%s)', str(report_no)[:20])
        return None
    return item


# 원료명이 이만큼은 닮아야 같은 품목으로 본다. 표기가 흔들리는 것은 흔하지만
# ('강력밀가루 제빵용' ↔ '강력분'), 밀가루와 혼합간장은 닮을 수가 없다.
NAME_FLOOR = 45


def _same_item(row, item):
    """
    이 줄이 정말 그 품목인가. 식약처 등록 정보와 견준다.

    **식품유형이 어긋나면 뺀다.** 같은 번호는 같은 품목이고, 품목이 같으면
    유형도 같다. 부기는 같은 말로 본다(빵류 ↔ 빵류[가열하여…]).

    **원료명이 딴판이면 뺀다.** 다만 이름은 거래처마다 다르게 적으므로
    문턱을 낮게 둔다 — 여기서 거르려는 것은 '조금 다른 이름' 이 아니라
    '다른 제품' 이다.
    """
    from v1.label.services import value_match as vm

    mine_type = str(row.get('prdlst_dcnm') or '').strip()
    ref_type = str(getattr(item, 'prdlst_dcnm', '') or '').strip()
    if mine_type and ref_type:
        _score, verdict = vm.compare(mine_type, ref_type, 'prefix')
        if verdict == 'conflict':
            return False

    mine_name = str(row.get('prdlst_nm') or '').strip()
    ref_name = str(getattr(item, 'prdlst_nm', '') or '').strip()
    if mine_name and ref_name:
        if vm.ratio(mine_name, ref_name, 'loose') < NAME_FLOOR:
            return False

    return True


def for_ingredient(ingredient):
    """
    {owners, fields: [...]} 또는 None.

    owners   같은 번호를 쓰는 **곳의 수** (나를 포함)
    fields   항목마다
        same    나와 같게 적은 곳의 수
        differ  다르게 적은 곳의 수
        agreed  내가 적은 값이 가장 많은 쪽인가
        others_values  **다를 때만** [{value, owners}] — 많이 적힌 순서

    **누가 적었는지는 돌려주지 않는다.** 값은 라벨에 인쇄되는 공개 정보이지만
    "어느 회사가 이 원료를 쓰는가" 는 인쇄되지 않는다.
    """
    from v1.label.models import MyIngredient

    no = (getattr(ingredient, 'prdlst_report_no', '') or '').strip()
    if not no or not no.isdigit():
        return None
    item = _registered(no)
    if item is None:
        # 식약처에 없는 번호다. 여기서 모은 것은 "같은 품목" 이 아닐 수 있다.
        return None

    rows = list(MyIngredient.objects
                .filter(prdlst_report_no=no)
                .exclude(delete_YN='Y')
                .exclude(user_id__isnull=True)
                .values('my_ingredient_id', 'user_id', 'prdlst_nm',
                        *[f for f, _ko in FIELDS]))

    # 번호를 잘못 넣은 줄을 뺀다. **내 줄은 빼지 않는다** — 내가 적은 값은
    # 내가 책임질 일이고, 여기서 거르려는 것은 남의 잘못 낀 줄이다.
    mine_pk = getattr(ingredient, 'pk', None)
    rows = [r for r in rows
            if r['my_ingredient_id'] == mine_pk or _same_item(r, item)]

    owners = {r['user_id'] for r in rows}
    if len(owners) < MIN_OWNERS:
        return None

    mine_id = getattr(ingredient, 'pk', None)
    out = []
    for field, label in FIELDS:
        mine = _key(getattr(ingredient, field, ''))
        if not mine:
            continue        # 내가 안 적은 항목은 견줄 것이 없다

        # **곳 단위로 센다.** 한 회사가 같은 원료를 여러 줄 넣어 두었다고
        # 그 회사 의견이 여러 표가 되면 안 된다.
        by_owner = defaultdict(set)
        for r in rows:
            if r['my_ingredient_id'] == mine_id:
                continue
            v = _key(r[field])
            if v:
                by_owner[r['user_id']].add(v)

        same = differ = 0
        tally = defaultdict(int)
        for uid, values in by_owner.items():
            if mine in values:
                same += 1
            else:
                differ += 1
            for v in values:
                tally[v] += 1
        if not (same or differ):
            continue        # 다른 곳이 아무도 안 적은 항목

        top = max(tally.values()) if tally else 0
        # 값이 곳마다 다 다르면 '다수' 라는 말 자체가 성립하지 않는다.
        # 화면이 그것을 알아야 "다수는 다르게 적었습니다" 라고 말하지 않는다.
        has_majority = top >= 2

        # 다를 때만 값을 담는다. 같으면 보여 줄 것이 없다 — "같습니다" 면 끝이다.
        # 많이 적힌 순서로, 내 값은 뺀다(내가 적은 것은 화면에 이미 있다).
        variants = []
        if differ:
            pairs = sorted(((v, n) for v, n in tally.items() if v != mine),
                           key=lambda kv: (-kv[1], kv[0]))
            for value, n in pairs[:MAX_VARIANTS]:
                variants.append({'value': _display(rows, field, value), 'owners': n})

        out.append({
            'key': field,
            'label': label,
            'same': same,
            'differ': differ,
            'others': same + differ,
            # 내가 적은 값이 가장 많은 쪽인가. 아니면 한 번 더 보라는 신호다.
            'agreed': tally.get(mine, 0) >= top,
            'has_majority': has_majority,
            'others_values': variants,
        })

    if not out:
        return None
    return {'owners': len(owners), 'fields': out}
