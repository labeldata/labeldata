# -*- coding: utf-8 -*-
"""
사용자가 넣은 품목보고번호가 **식약처에 실제로 있는 번호인가.**

왜 이것을 보게 됐나
───────────────────
공용 원료 풀을 만들지 정하려고 같은 번호를 여러 곳이 등록했는지 재 봤다
(measure_ingredient_pool). 갈린 표본을 열었더니 이랬다.

    198301900201248
      식품유형  밀가루 | 설탕 | **혼합간장**
      제조사    대두식품 | 대한제분(주)

같은 품목을 회사마다 다르게 적은 것이 아니었다. **그 번호 여섯 개가 전부
식약처에 없었다** — 애초에 품목보고번호가 아니었던 것이다.

잘못된 번호가 들어가면 무엇이 무너지나
──────────────────────────────────────
  - 영양성분 자동 연결이 안 된다(`nutrition_candidates.auto_link` 가 못 찾는다)
  - 표시사항 검증이 그 번호를 근거로 삼는다
  - 다른 회사의 다른 제품과 **같은 번호**가 된다

그런데 지금까지는 넣는 자리에서 아무 말도 하지 않았다. 조회 단추를 따로
누르지 않으면 틀린 채로 저장된다.

막지는 않는다
─────────────
번호가 없거나 다른 체계인 경우가 있다(수입 원료는 수입신고번호를 적는다).
적재본이 최신이 아닐 수도 있다. **짚되 단정하지 않는다** — 시안 대조에서
배운 것과 같다. 값을 고치지도, 저장을 막지도 않는다.
"""
import logging

logger = logging.getLogger(__name__)

# 판정. 화면이 이 이름으로 말투를 고른다.
OK = 'ok'                 # 그 번호가 있고, 적어 둔 것과도 맞는다
MISMATCH = 'mismatch'     # 번호는 있는데 제품명·유형이 다르다
UNKNOWN = 'unknown'       # 식약처 적재본에 없는 번호
SKIP = 'skip'             # 볼 것이 없다 (비었거나 숫자가 아니다)


def check(report_no, prdlst_nm='', prdlst_dcnm=''):
    """
    {status, message, item} 을 돌려준다. item 은 찾은 FoodItem (없으면 None).

    이름을 함께 받으면 **그 번호가 정말 그 제품인지**까지 본다. 번호는 맞는데
    다른 제품을 적어 둔 경우가 실제로 있었고, 그쪽이 더 위험하다 — 번호가
    없으면 자동 연결이 안 될 뿐이지만, 번호가 남의 것이면 **남의 값이 우리
    라벨에 붙는다.**
    """
    from v1.label.services import item_lookup, value_match

    no = (report_no or '').strip()
    if not no:
        return {'status': SKIP, 'message': '', 'item': None}
    # 숫자가 아닌 번호는 우리 조회 키로 쓸 수 없다('2020_DNSP_04044').
    # 틀렸다고 말할 근거도 없으므로 아무 말도 하지 않는다.
    if not no.replace('-', '').isdigit():
        return {'status': SKIP, 'message': '', 'item': None}

    try:
        item, _matched = item_lookup.find_exact(no)
    except Exception:
        # 조회가 실패해도 입력을 막지 않는다. 곁들이 때문에 본체를 잃을 이유가 없다.
        logger.exception('[번호 확인] 조회 실패 (%s)', no[:20])
        return {'status': SKIP, 'message': '', 'item': None}

    if item is None:
        return {
            'status': UNKNOWN,
            'message': '식약처에 등록된 번호를 찾지 못했습니다. '
                       '번호를 다시 확인해 주세요 — 수입 원료처럼 번호 체계가 '
                       '다른 경우에는 그대로 두셔도 됩니다.',
            'item': None,
        }

    # 번호는 있다. 적어 둔 이름과 견준다.
    for mine, theirs, mode in ((prdlst_nm, item.prdlst_nm, 'exact'),
                               (prdlst_dcnm, item.prdlst_dcnm, 'prefix')):
        if not (mine or '').strip() or not (theirs or '').strip():
            continue
        _score, verdict = value_match.compare(mine, theirs, mode)
        if verdict == 'conflict':
            return {
                'status': MISMATCH,
                'message': '이 번호는 식약처에 「%s」(%s)로 등록돼 있습니다.'
                           % (item.prdlst_nm or '-', item.prdlst_dcnm or '-'),
                'item': item,
            }

    return {'status': OK, 'message': '', 'item': item}
