"""
식약처 등록 품목을 사람이 **고를 수 있게** 찾아 준다.

지금까지 등록 정보로 가는 길은 하나뿐이었다 — 품목보고번호가 저장된 문자열과
글자 하나까지 똑같아야 했다. 두 가지 이유로 그 길은 자주 막힌다.

  1. 하이픈    같은 번호가 "20220460436160" 으로도 "19980448010-697" 으로도
               등록돼 있다. 사람은 라벨에 인쇄된 대로 치는데, 저장된 꼴과
               다르면 조회는 통째로 실패한다. 사용자에게는 "없는 번호" 로 보인다.
  2. 한 자리   사진에서 읽은 번호는 열대여섯 자리 중 한 자리만 어긋나도 못 찾는다.

못 찾았을 때 "없습니다" 로 끝내지 않는다. **비슷한 것을 늘어놓고 고르게 한다.**
번호가 아니라 제품명·제조사로도 찾을 수 있어야 한다 — 수입식품처럼 품목보고번호
자체가 없거나, 라벨의 번호 자리가 아예 안 읽히는 경우가 있다.

여기서 하는 일은 찾아서 늘어놓는 것까지다. 무엇을 쓸지는 화면이 정한다.
"""
import logging

logger = logging.getLogger(__name__)

# 후보를 몇 개까지 보여 줄지. 스무 개를 넘기면 고르는 일이 다시 찾는 일이 된다.
MAX_CANDIDATES = 20


def as_fields(item):
    """
    FoodItem 을 화면이 쓰는 dict 로. 조회 결과와 후보가 같은 모양이어야 한다.

    **다섯 칸만 넘기고 있었다.** 그런데 FoodItem 은 소비기한·포장재질·업종명
    까지 들고 있다 — 식약처가 준 것을 우리가 안 쓰고 버린 것이다. 번호를 넣은
    사람은 "이 번호로 아는 것은 다 채워 달라" 고 말한 것인데, 다섯 칸만 채우면
    나머지를 손으로 적게 된다.

    **없는 것을 지어내지 않는다.** 빈 칸은 빈 채로 넘긴다 — 화면이 "비어 있음
    → 새로 채움" 으로 보여 주므로, 빈 값을 넘기면 멀쩡한 값을 지우자고 말하는
    셈이 된다(그래서 아래 apply 쪽이 빈 값을 거른다).

    food_type(식품 소분류)에 같은 값을 함께 넣는 까닭은 **표시사항 검증이 그
    칸을 보기 때문**이다. 비어 있으면 그 유형에만 있는 의무 표시사항 검사가
    통째로 빠지는데, 그건 통과한 것이 아니라 안 본 것이다.
    """
    return {
        'prdlst_report_no': item.prdlst_report_no or '',
        'prdlst_nm': item.prdlst_nm or '',
        'prdlst_dcnm': item.prdlst_dcnm or '',
        'food_type': item.prdlst_dcnm or '',
        'rawmtrl_nm': item.rawmtrl_nm or '',
        'bssh_nm': item.bssh_nm or '',
        'pog_daycnt': item.pog_daycnt or '',
        'frmlc_mtrqlt': item.frmlc_mtrqlt or '',
    }


def find_exact(text):
    """
    번호로 딱 맞는 품목 하나. 하이픈이 있고 없고는 따지지 않는다.

    Returns: (FoodItem 또는 None, 실제로 맞은 번호)
    """
    from v1.label.models import FoodItem
    from v1.label.services.ocr_reconcile import report_no_tries

    tries = report_no_tries(text)
    if not tries:
        return None, ''
    try:
        found = {f.prdlst_report_no: f
                 for f in FoodItem.objects.filter(prdlst_report_no__in=tries)}
    except Exception:
        logger.exception('품목보고번호 조회 실패 (%s)', tries[:3])
        return None, ''
    for form in tries:            # 원문에 가까운 꼴을 먼저 채택한다
        if form in found:
            return found[form], form
    return None, ''


def near_by_number(text, limit=MAX_CANDIDATES):
    """
    한 자리가 어긋난 번호로 등록된 품목들.

    사진 판독 쪽(ocr_reconcile.find_near_miss)은 제품명·제조사로 교차 검증해
    **하나로 좁혀질 때만** 채택한다. 여기는 사람이 고르는 자리라 반대다 —
    좁히지 않고 통째로 보여 준다. 어느 것인지는 사진을 든 사람이 안다.
    """
    from v1.label.models import FoodItem
    from v1.label.services.ocr_reconcile import near_report_nos, report_no_tries

    candidates = near_report_nos(report_no_tries(text))
    if not candidates:
        return []
    try:
        return list(FoodItem.objects.filter(
            prdlst_report_no__in=candidates).order_by('prdlst_report_no')[:limit])
    except Exception:
        logger.exception('품목보고번호 근사 조회 실패')
        return []


def by_name(text, limit=MAX_CANDIDATES):
    """제품명·식품유형·제조사로 찾는다. 검색 화면과 같은 조건을 쓴다."""
    from v1.label.models import FoodItem
    from v1.label.services import product_search

    text = (text or '').strip()
    if len(text) < 2:
        # 한 글자로 찾으면 183만 행에서 수만 건이 나온다. 고르는 데 도움이 안 된다.
        return []
    try:
        return list(FoodItem.objects
                    .filter(product_search.domestic_q(text))
                    .only('prdlst_report_no', 'prdlst_nm', 'prdlst_dcnm',
                          'bssh_nm', 'rawmtrl_nm')[:limit])
    except Exception:
        logger.exception('품목 이름 조회 실패 (%s)', text[:30])
        return []


def search(text, limit=MAX_CANDIDATES):
    """
    한 칸으로 번호와 이름을 모두 받는다.

    사용자는 자기가 가진 것이 번호인지 이름인지 알지만, 그것을 **어느 칸에
    넣어야 하는지**까지 고민하게 만들 이유가 없다.

    Returns: [FoodItem…] — 정확히 맞은 것이 있으면 맨 앞에 온다.
    """
    text = (text or '').strip()
    if not text:
        return []

    out, seen = [], set()

    def add(items):
        for item in items:
            if item.prdlst_report_no in seen:
                continue
            seen.add(item.prdlst_report_no)
            out.append(item)

    # 번호로 걸리면 거기서 멈춘다. 이름 조회는 183만 행에 LIKE 를 거는 일이라
    # (product_search 의 주석 참고) 번호가 답을 준 뒤에까지 부를 이유가 없다.
    item, _ = find_exact(text)
    if item is not None:
        add([item])
    if not out:
        add(near_by_number(text, limit))
    if not out:
        add(by_name(text, limit))
    return out[:limit]
