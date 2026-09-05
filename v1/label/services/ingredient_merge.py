"""
같은 원료가 여러 벌 쌓인 것을 하나로 합친다.

운영 실측(2026-08-30): 한 계정의 원료 548건 중 겹치는 그룹이 40개, 여분이
108건 — **다섯에 하나**가 같은 것의 사본이었다.

왜 쌓였나. 검색에 상한도 정렬도 없어서 "가" 같은 넓은 말로 찾으면 목록이
그대로 쏟아졌고, 순서도 DB 마음이라 같은 검색을 두 번 하면 결과가 달랐다.
사용자는 없는 원료라고 생각하고 또 등록했다. 그쪽은 막았다 —
`INGREDIENT_SEARCH_LIMIT` 과 "N건 중 앞 50건만 보여줍니다" 안내.

**그런데 이미 쌓인 것은 그대로다.** 지우면 배합비가 끊기니 사용자는 손을 못
댄다. 합치는 도구가 있어야 정리가 시작된다.

여기서 하는 일은 둘이다.

  찾기   같은 원료로 볼 것들을 묶어 보여 준다. **고치지 않는다.**
  합치기 사용자가 고른 한 벌로 나머지를 옮기고, 나머지는 지운 표시를 한다.

**어느 것을 남길지는 사람이 정한다.** 이름이 같아도 제조사가 다르면 다른
원료이고, 배합비가 물려 있는 쪽이 정본일 때도, 나중에 만든 쪽이 정확할 때도
있다. 우리가 고르면 틀린 쪽을 정본으로 삼을 수 있다.
"""
import logging

from django.db import transaction

from v1.label.models import LabelIngredientRelation, MyIngredient
from v1.label.services.ingredient_matching import normalize_name

logger = logging.getLogger(__name__)


def group_key(ingredient):
    """
    같은 원료로 볼 기준.

    이름만으로 묶지 않는다. **제조사가 다르면 다른 원료다** — "정제소금" 은
    회사마다 규격서가 다르고 그것이 곧 다른 서류다. 품목보고번호가 있으면
    그것이 가장 확실하니 먼저 본다.
    """
    report_no = (ingredient.prdlst_report_no or '').strip()
    if report_no:
        return ('report', report_no)
    name = normalize_name(ingredient.prdlst_nm or '')
    if not name:
        return None
    return ('name', name, normalize_name(ingredient.bssh_nm or ''))


# 이름이 이만큼 닮았으면 같은 것으로 본다.
#
# 낮추면 "정제소금" 과 "정제설탕" 이 묶이고, 높이면 "강력밀가루 제빵용2" 와
# "제빵용3" 이 갈린다. 실제 데이터에서 뒤엣것이 진짜 사본이었다.
NAME_SAME = 80


def _same_name(a, b):
    """두 원료 이름이 같은 것을 말하는가."""
    x, y = normalize_name(a), normalize_name(b)
    if not x or not y:
        return False
    if x == y or x in y or y in x:
        return True
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return False
    return fuzz.ratio(x, y) >= NAME_SAME


def _split_by_name(items):
    """
    같은 통 안의 것들을 이름으로 다시 가른다.

    품목보고번호가 같다는 것만으로 묶으면 이런 것이 한 통에 들어온다 —
    실제 운영에서 나왔다.

        설탕              대한제분(주) · 198301900201248
        강력밀가루 제빵용3  대한제분(주) · 198301900201248
        강력밀가루 제빵용2  대한제분(주) · 198301900201248

    번호가 잘못 붙은 것이지 같은 원료가 아니다. 여기서 설탕과 밀가루를 합치면
    배합비가 통째로 엉킨다. 이름이 딴판이면 가른다.
    """
    clusters = []
    for item in items:
        name = item.prdlst_nm or ''
        for cluster in clusters:
            if _same_name(cluster[0].prdlst_nm or '', name):
                cluster.append(item)
                break
        else:
            clusters.append([item])
    return clusters


def _usage_counts(ids):
    """원료마다 배합비에 몇 번 물려 있는지. 한 번에 세어 온다."""
    from django.db.models import Count

    rows = (LabelIngredientRelation.objects
            .filter(ingredient_id__in=ids)
            .values('ingredient_id')
            .annotate(n=Count('relation_id')))
    return {row['ingredient_id']: row['n'] for row in rows}


def duplicate_groups(user):
    """
    이 사용자의 원료 중 겹치는 것들. **아무것도 고치지 않는다.**

    Returns: [{'key', 'label', 'items': [{'id','name','maker','report_no',
               'used','updated'}…]}…]  많이 쓰인 그룹부터.
    """
    rows = list(MyIngredient.objects
                .filter(user_id=user, delete_YN='N')
                .order_by('my_ingredient_id'))
    buckets = {}
    for row in rows:
        key = group_key(row)
        if key:
            buckets.setdefault(key, []).append(row)

    dupes = {}
    for key, items in buckets.items():
        if len(items) < 2:
            continue
        for i, cluster in enumerate(_split_by_name(items)):
            if len(cluster) > 1:
                dupes[key + (i,)] = cluster
    if not dupes:
        return []

    used = _usage_counts([r.my_ingredient_id for v in dupes.values() for r in v])

    groups = []
    for key, items in dupes.items():
        groups.append({
            'key': '|'.join(str(part) for part in key),
            'label': items[0].prdlst_nm or '(이름 없음)',
            'items': [{
                'id': r.my_ingredient_id,
                'name': r.prdlst_nm or '',
                'maker': r.bssh_nm or '',
                'report_no': r.prdlst_report_no or '',
                'used': used.get(r.my_ingredient_id, 0),
                'updated': r.update_datetime,
            } for r in sorted(items,
                              key=lambda x: (-used.get(x.my_ingredient_id, 0),
                                             x.my_ingredient_id))],
        })
    # 배합비에 많이 물린 그룹이 먼저다 — 정리 효과가 큰 순서
    groups.sort(key=lambda g: (-sum(i['used'] for i in g['items']),
                               -len(g['items'])))
    return groups


def summary(user):
    """몇 그룹에 여분이 몇 건인가. 화면 머리에 한 줄로 쓴다."""
    groups = duplicate_groups(user)
    return {
        'groups': len(groups),
        'extra': sum(len(g['items']) - 1 for g in groups),
        'total': MyIngredient.objects.filter(user_id=user, delete_YN='N').count(),
    }


@transaction.atomic
def merge(user, keep_id, drop_ids):
    """
    drop 들을 keep 하나로 합친다.

    옮기는 것이 셋이다 — 배합비(LabelIngredientRelation), BOM 의 연동 원료,
    법령 뉴스 매칭. 남은 것은 지운 표시(delete_YN='Y')만 한다. **행을 지우지
    않는다** — 잘못 합쳤을 때 되돌릴 수 있어야 한다.

    한 라벨이 keep 과 drop 을 **둘 다** 갖고 있으면 배합비가 두 줄이 된다.
    그럴 때는 비율이 큰 쪽을 남기고 작은 쪽을 버린 뒤, 무엇을 버렸는지 알린다.
    합쳐서 더하지 않는다 — 같은 원료를 두 번 적은 것인지 정말 두 몫인지
    우리가 알 방법이 없고, 더하면 배합비가 조용히 늘어난다.

    Returns: {'moved', 'dropped', 'collisions': [{'label_id','kept','dropped'}…]}
    """
    keep = MyIngredient.objects.filter(
        user_id=user, my_ingredient_id=keep_id, delete_YN='N').first()
    if keep is None:
        raise ValueError('남길 원료를 찾을 수 없습니다.')

    losers = list(MyIngredient.objects.filter(
        user_id=user, my_ingredient_id__in=drop_ids, delete_YN='N')
        .exclude(my_ingredient_id=keep_id))
    if not losers:
        raise ValueError('합칠 원료가 없습니다.')

    moved, collisions = 0, []
    mine = {rel.label_id: rel for rel in
            LabelIngredientRelation.objects.filter(ingredient_id=keep_id)}

    for loser in losers:
        for rel in list(LabelIngredientRelation.objects
                        .filter(ingredient_id=loser.my_ingredient_id)):
            existing = mine.get(rel.label_id)
            if existing is None:
                # 자리를 비켜 준다. relation_id 가 label+ingredient 로 만들어져
                # 있어 갈아끼울 수 없다 - 새로 만들고 옛 줄을 지운다.
                fresh = LabelIngredientRelation(
                    label_id=rel.label_id, ingredient_id=keep.my_ingredient_id,
                    ingredient_ratio=rel.ingredient_ratio,
                    relation_sequence=rel.relation_sequence)
                rel.delete()
                fresh.save()
                mine[fresh.label_id] = fresh
                moved += 1
                continue

            # 한 라벨에 둘 다 있었다
            old = float(existing.ingredient_ratio or 0)
            new = float(rel.ingredient_ratio or 0)
            if new > old:
                existing.ingredient_ratio = rel.ingredient_ratio
                existing.relation_sequence = rel.relation_sequence
                existing.save()
                collisions.append({'label_id': rel.label_id,
                                   'kept': new, 'dropped': old})
            else:
                collisions.append({'label_id': rel.label_id,
                                   'kept': old, 'dropped': new})
            rel.delete()

        _repoint_others(loser, keep)
        loser.delete_YN = 'Y'
        loser.save(update_fields=['delete_YN'])

    logger.info('[원료 합치기] keep=%s drop=%s 배합비 %s건 이동, 충돌 %s건',
                keep_id, [l.my_ingredient_id for l in losers], moved, len(collisions))
    return {'moved': moved, 'dropped': len(losers), 'collisions': collisions}


def _repoint_others(loser, keep):
    """
    배합비 말고 이 원료를 가리키던 것들. 실패해도 합치기는 끝나야 한다.

    **각각을 세이브포인트로 감싼다.** 바깥이 atomic 인데 안에서 DB 오류를
    잡아 삼키면 트랜잭션이 깨진 채로 남고, 그다음 질의가 통째로
    TransactionManagementError 로 죽는다. 운영에서 그렇게 500 이 났다 —
    화면에는 "합치는 중 오류가 발생했습니다" 만 떴고 원인은 여기였다.
    """
    try:
        with transaction.atomic():
            from v1.bom.models import ProductBOM
            ProductBOM.objects.filter(source_ingredient=loser).update(
                source_ingredient=keep)
    except Exception:
        logger.exception('[원료 합치기] BOM 연동 원료 이동 실패 (%s)',
                         loser.my_ingredient_id)

    # 법령 매칭은 (뉴스, 사용자, 원료) 가 유일해야 한다. 같은 뉴스가 양쪽에
    # 걸려 있으면 그대로 옮길 수가 없다 - 겹치는 것은 버린다. 다시 만들어지는
    # 자료라 잃어도 큰일이 아니다.
    try:
        with transaction.atomic():
            from v1.regulatory.models import NewsIngredientMatch
            taken = set(NewsIngredientMatch.objects
                        .filter(ingredient=keep).values_list('news_id', 'user_id'))
            for row in NewsIngredientMatch.objects.filter(ingredient=loser):
                if (row.news_id, row.user_id) in taken:
                    row.delete()
                else:
                    row.ingredient = keep
                    row.save(update_fields=['ingredient'])
                    taken.add((row.news_id, row.user_id))
    except Exception:
        logger.exception('[원료 합치기] 법령 매칭 이동 실패 (%s)',
                         loser.my_ingredient_id)
