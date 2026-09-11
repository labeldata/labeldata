"""
**어느 원료의 원산지를 표시해야 하는가.**

지금까지 우리 원산지 검사(`check_origin_missing`)는 우리 편집기가 넣는
`(원산지 미표시)` 자리표시자가 남았는지만 봤다. 순위 산정도, 제외 목록도,
표시 대상 판정도 없었다 — 사실상 원산지를 보지 않았다.

「농수산물의 원산지 표시 등에 관한 법률」 시행령이 정하는 범위는 이렇다.

    배합비율이 높은 순으로 **3순위**까지
    다만 어느 한 원료가 **98% 이상**이면 그 원료만
    상위 **두 원료의 합이 98% 이상**이면 그 둘만

제외: 물 · 식품첨가물 · 주정 · 당류.

**제외 목록이 결과를 뒤집는다.** 밖에서 본 시스템의 판정 하나를 손으로 따라가
봤다 — 밀가루 44 / 정제수 25 / 마가린 20 / 설탕 4.4 / 전란액 2.2 인 제품에서
정제수(물)와 설탕(당류)을 빼야 3순위가 밀가루·마가린·전란액이 되고, 셋 다
표시돼 있어 적합이 된다. 제외를 안 보면 없는 위반을 만든다.

**모르면 대상으로 넣지 않는다.** 원료가 당류인지 첨가물인지 확신이 없을 때
대상에 넣으면 "표시하라" 는 지적이 나가고, 사용자는 고칠 방법이 없다.
"""
import logging
import re

logger = logging.getLogger(__name__)

# 물. 이름이 몇 가지로 적힌다.
_WATER = ('정제수', '음용수', '물')

# 당류 — 원산지 표시 대상에서 빠진다. 식품유형 이름과 흔한 원료명을 함께 본다.
_SUGARS = (
    '설탕', '백설탕', '갈색설탕', '흑설탕', '정백당', '원당',
    '과당', '결정과당', '액상과당', '포도당', '물엿',
    '올리고당', '전화당', '유당', '맥아당', '자일로스',
    '벌꿀', '당시럽', '시럽', '당류', '기타당류',
)

# 주정
_ALCOHOL = ('주정', '에탄올', '발효주정')


def _norm(text) -> str:
    return re.sub(r'\s+', '', str(text or '')).lower()


def _is_excluded(ingredient) -> tuple[bool, str]:
    """
    원산지 표시 대상에서 빠지는 원료인가. (빠지는가, 이유) 를 돌려준다.

    확신이 없으면 **빠지지 않는다고 본다** — 대상에서 함부로 빼면 진짜 누락을
    놓친다. 반대 방향(대상에 함부로 넣는 것)은 아래 부르는 쪽이 막는다.
    """
    name = _norm(getattr(ingredient, 'prdlst_nm', ''))
    category = (getattr(ingredient, 'food_category', '') or '').strip()
    food_type = _norm(getattr(ingredient, 'prdlst_dcnm', ''))

    if category == 'additive':
        return True, '식품첨가물'
    if any(_norm(w) == name for w in _WATER):
        return True, '물'
    if any(_norm(w) in name for w in _ALCOHOL):
        return True, '주정'
    for sugar in _SUGARS:
        if not _norm(sugar):
            continue
        # **무엇이 걸렸는지 말한다.**
        #
        # 운영에서 "마가린(당류)" 로 제외된 적이 있다. 마가린은 당류가 아니다 —
        # 그 원료의 **식품유형**이 당류로 적혀 있었던 것인데, 화면에는 '당류'
        # 세 글자만 나가서 왜 빠졌는지 알 길이 없었다. 사용자는 고칠 자리를
        # 찾지 못한다.
        if _norm(sugar) == name:
            return True, '당류'
        if _norm(sugar) == food_type:
            return True, "당류 — 식품유형이 '%s'" % (
                getattr(ingredient, 'prdlst_dcnm', '') or '').strip()
    return False, ''


def required_origins(label) -> dict:
    """
    원산지를 표시해야 하는 원료를 산정한다.

        {'items': [{'name', 'ratio'}, …],
         'basis': '왜 그 범위인가',
         'reason': 'ok' | 'no_ratio' | 'all_excluded'}

    `reason` 이 'ok' 가 아니면 `items` 는 비어 있고, 부르는 쪽은 **지적이 아니라
    "못 봤다"** 로 다뤄야 한다.
    """
    try:
        relations = list(label.ingredient_relations.select_related('ingredient').all())
    except Exception:
        logger.exception('원산지 순위 산정: BOM 을 읽지 못했다 (label=%s)',
                         getattr(label, 'pk', None))
        return {'items': [], 'basis': '', 'reason': 'no_ratio'}

    rows = []
    for rel in relations:
        ing = rel.ingredient
        ratio = rel.ingredient_ratio
        name = (getattr(ing, 'prdlst_nm', '') or '').strip()
        if ratio is None or not name:
            continue
        excluded, why = _is_excluded(ing)
        rows.append({'name': name, 'ratio': float(ratio), 'excluded': excluded,
                     'why': why})

    if not rows:
        return {'items': [], 'basis': '', 'reason': 'no_ratio'}

    ranked = sorted((r for r in rows if not r['excluded']),
                    key=lambda r: -r['ratio'])
    if not ranked:
        return {'items': [], 'basis': '', 'reason': 'all_excluded'}

    if ranked[0]['ratio'] >= 98:
        picked, basis = ranked[:1], '한 원료가 98% 이상이라 그 원료만 표시합니다.'
    elif len(ranked) >= 2 and (ranked[0]['ratio'] + ranked[1]['ratio']) >= 98:
        picked, basis = ranked[:2], '상위 두 원료의 합이 98% 이상이라 둘만 표시합니다.'
    else:
        picked, basis = ranked[:3], '배합비율이 높은 순으로 3순위까지 표시합니다.'

    dropped = [r for r in rows if r['excluded']]
    if dropped:
        basis += ' (제외: %s)' % ', '.join(
            '%s(%s)' % (r['name'], r['why']) for r in dropped)

    return {
        'items': [{'name': r['name'], 'ratio': r['ratio']} for r in picked],
        'basis': basis,
        'reason': 'ok',
    }
