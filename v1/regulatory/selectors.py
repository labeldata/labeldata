"""
규제 모니터링 건수 산출 단일 소스.

사이드바 배지 / 홈 대시보드 / 목록 탭 배지 / 목록 헤더 / 카운트 API 가
모두 같은 규칙으로 같은 숫자를 보여주도록 집계 로직을 이 모듈에 모은다.
(이전에는 context_processors, views.news_list, unread_count_api, mark_as_read 에
 같은 쿼리가 조금씩 다르게 복제되어 있어 화면마다 숫자가 어긋났다.)

집계 규칙
─────────
actionable (조치 대상) — 모든 건수의 모수
    내 제품 매칭 + 원료 보관함 매칭.
    조치 이력(RegulatoryMatchAction)과 읽음 상태(read_yn)는 이 두 매칭에만 붙일 수 있다.
    키워드 푸시 매칭은 읽음 상태가 앱(PushNotificationLog.is_read)에 있어서 제외한다.
    포함하면 웹에서 지울 수 없는 숫자가 배지에 영구히 남는다.
    ※ 목록에서 "내 매칭"으로 상단 고정·강조되는 대상은 여기에 키워드 푸시 매칭까지
      더한 집합이며, 그쪽은 news_list 의 SQL 어노테이션(match_priority)으로 표현한다.

unread (미확인)
    actionable 중 read_yn=False.

no_action (미조치)
    actionable 중 monitoring/resolved 조치 이력이 하나도 없는 건.

수거검사 판정
    PENDING_JUDGMENTS  = 아직 판정이 확정되지 않은 상태(접수/검토중)
    FINAL_JUDGMENTS    = 확정 판정(적합/부적합)
    수집기(services/collector.py)의 알림 발송 기준과 동일한 값을 사용한다.
"""
from v1.regulatory.models import (
    NewsIngredientMatch, NewsProductMatch, RegulatoryMatchAction,
)

# 조치로 인정하는 action_type (memo/dismissed 는 "조치함"으로 보지 않는다)
ACTION_STATUSES = ('monitoring', 'resolved')


# ─────────────────────────────────────────────────────────────────────────────
# 뉴스(부적합·행정처분) 매칭 집계
# ─────────────────────────────────────────────────────────────────────────────

def actionable_news_ids(user) -> set:
    """읽음·조치 처리가 가능한 매칭 뉴스 ID — 제품 + 원료 보관함"""
    return (
        set(
            NewsProductMatch.objects
            .filter(product__user_id=user, false_positive_yn=False)
            .values_list('news_id', flat=True)
        )
        | set(
            NewsIngredientMatch.objects
            .filter(user=user, dismissed_yn=False)
            .values_list('news_id', flat=True)
        )
    )


def unread_news_ids(user) -> set:
    """미확인 뉴스 ID — actionable 중 아직 읽지 않은 건"""
    return (
        set(
            NewsProductMatch.objects
            .filter(product__user_id=user, false_positive_yn=False, read_yn=False)
            .values_list('news_id', flat=True)
        )
        | set(
            NewsIngredientMatch.objects
            .filter(user=user, dismissed_yn=False, read_yn=False)
            .values_list('news_id', flat=True)
        )
    )


def unread_news_count(user) -> int:
    """사이드바·홈 배지에 쓰는 미확인 건수"""
    return len(unread_news_ids(user))


def actioned_news_ids(user) -> set:
    """monitoring/resolved 조치 이력이 있는 뉴스 ID"""
    return (
        set(
            RegulatoryMatchAction.objects
            .filter(
                product_match__product__user_id=user,
                product_match__false_positive_yn=False,
                action_type__in=ACTION_STATUSES,
            )
            .values_list('product_match__news_id', flat=True)
        )
        | set(
            RegulatoryMatchAction.objects
            .filter(
                ingredient_match__user=user,
                ingredient_match__dismissed_yn=False,
                action_type__in=ACTION_STATUSES,
            )
            .values_list('ingredient_match__news_id', flat=True)
        )
    )


def no_action_news_ids(user, actionable_ids=None) -> set:
    """미조치 뉴스 ID — 조치 대상 중 monitoring/resolved 이력이 없는 건"""
    base = actionable_news_ids(user) if actionable_ids is None else actionable_ids
    return base - actioned_news_ids(user)


# ─────────────────────────────────────────────────────────────────────────────
# 목록 렌더용 사용자 매칭 정보
# ─────────────────────────────────────────────────────────────────────────────

def user_match_context(user) -> dict:
    """
    목록을 그리는 데 필요한 '내 매칭' 정보를 한 번에 모아 온다.

    예전에는 목록 쿼리에 Exists/Subquery 어노테이션을 8개 붙여 상관 서브쿼리가
    행마다 실행됐다(EXPLAIN 기준 13개). 정렬 키까지 그 결과로 계산해 필터된 전체
    행에 대해 서브쿼리를 돌린 뒤 filesort 를 했다.
    사용자별 매칭 건수는 보통 수십 건 수준이라, 여기서 집합·사전으로 미리 만들어
    두고 목록 쿼리에서는 상수 IN 목록만 쓰는 편이 훨씬 싸다.
    """
    from v1.mobile.models import PushNotificationLog

    prod_qs = (NewsProductMatch.objects
               .filter(product__user_id=user, false_positive_yn=False)
               .values_list('news_id', 'read_yn', 'risk_level', 'risk_score'))
    ing_qs = (NewsIngredientMatch.objects
              .filter(user=user, dismissed_yn=False)
              .values_list('news_id', 'read_yn', 'risk_level', 'risk_score'))

    prod_matched, prod_unread, prod_risk = set(), set(), {}
    _prod_best = {}
    for nid, read_yn, risk, score in prod_qs:
        prod_matched.add(nid)
        if not read_yn:
            prod_unread.add(nid)
        if score is not None and score >= _prod_best.get(nid, -1):
            _prod_best[nid] = score
            prod_risk[nid] = risk

    ing_matched, ing_unread, ing_risk = set(), set(), {}
    _ing_best = {}
    for nid, read_yn, risk, score in ing_qs:
        ing_matched.add(nid)
        if not read_yn:
            ing_unread.add(nid)
        if score is not None and score >= _ing_best.get(nid, -1):
            _ing_best[nid] = score
            ing_risk[nid] = risk

    kw_matched = set(
        PushNotificationLog.objects
        .filter(device__user=user, trigger_type='keyword')
        .values_list('news_id', flat=True)
    )

    # 최신 조치 상태 (monitoring / resolved) — 조치 시각까지 남긴다.
    # 제품·원료 양쪽에 조치가 있으면 목록의 조치상태 필터가 더 나중 것을 따라야 하는데,
    # 여기서 시각을 버리면 뷰가 같은 조인을 한 번 더 돌려야 한다.
    def _latest_action(qs, news_field):
        latest = {}
        for nid, action, created in qs.values_list(news_field, 'action_type', 'created_at'):
            cur = latest.get(nid)
            if cur is None or created > cur[1]:
                latest[nid] = (action, created)
        return latest

    prod_action_at = _latest_action(
        RegulatoryMatchAction.objects.filter(
            product_match__product__user_id=user,
            product_match__false_positive_yn=False,
            action_type__in=ACTION_STATUSES),
        'product_match__news_id')
    ing_action_at = _latest_action(
        RegulatoryMatchAction.objects.filter(
            ingredient_match__user=user,
            ingredient_match__dismissed_yn=False,
            action_type__in=ACTION_STATUSES),
        'ingredient_match__news_id')

    latest_action = {}
    for src in (prod_action_at, ing_action_at):
        for nid, (action, created) in src.items():
            cur = latest_action.get(nid)
            if cur is None or created > cur[1]:
                latest_action[nid] = (action, created)

    actionable = prod_matched | ing_matched
    actioned   = set(prod_action_at) | set(ing_action_at)

    return {
        'prod_matched': prod_matched, 'prod_unread': prod_unread, 'prod_risk': prod_risk,
        'ing_matched': ing_matched,   'ing_unread': ing_unread,   'ing_risk': ing_risk,
        'kw_matched': kw_matched,
        'prod_action': {nid: a for nid, (a, _) in prod_action_at.items()},
        'ing_action':  {nid: a for nid, (a, _) in ing_action_at.items()},
        'all_matched': prod_matched | ing_matched | kw_matched,
        # ── 집계 ────────────────────────────────────────────────────────────
        # 위에서 이미 읽어 온 행으로 계산한다. 같은 값을 구하는 함수들
        # (unread_news_ids / actionable_news_ids / actioned_news_ids /
        #  no_action_news_ids) 을 목록 뷰에서 다시 부르면 매칭 테이블을
        #  세 번, 조치 조인을 두 번 더 돌게 된다 — 규칙은 같으니 여기서 낸다.
        'actionable':    actionable,
        'unread':        prod_unread | ing_unread,
        'actioned':      actioned,
        'no_action':     actionable - actioned,
        # 제품·원료를 합친 뉴스별 최신 조치 (목록의 조치상태 필터용)
        'latest_action': {nid: a for nid, (a, _) in latest_action.items()},
    }


def attach_match_info(news_items, ctx) -> None:
    """
    페이지에 실제로 보이는 행에만 매칭 정보를 붙인다(보통 50건).
    템플릿이 쓰는 속성 이름은 기존 어노테이션과 동일하게 맞춘다.
    """
    for n in news_items:
        nid = n.id
        n.my_matched_yn       = nid in ctx['prod_matched']
        n.my_unread_yn        = nid in ctx['prod_unread']
        n.ing_matched_yn      = nid in ctx['ing_matched']
        n.ing_unread_yn       = nid in ctx['ing_unread']
        n.kw_matched_yn       = nid in ctx['kw_matched']
        n.my_risk_level       = ctx['prod_risk'].get(nid)
        n.ing_risk_level      = ctx['ing_risk'].get(nid)
        n.my_action_status    = ctx['prod_action'].get(nid)
        n.my_ing_action_status = ctx['ing_action'].get(nid)


# ─────────────────────────────────────────────────────────────────────────────
# 알림 제외(뮤트) 규칙
# ─────────────────────────────────────────────────────────────────────────────

def muted_values(user) -> dict:
    """
    사용자의 알림 제외 규칙을 scope 별 정규화 값 집합으로 모아 온다.

    알림을 **만드는 쪽**(services/matcher.py)과 **보여 주는 쪽**(views.news_list)
    이 같은 집합을 봐야 한다. 한쪽만 적용하면 "껐는데 목록에는 남아 있다"
    또는 "목록에서는 사라졌는데 푸시는 계속 온다" 가 된다.

    Returns: {'keyword': {...}, 'ingredient': {...}, 'company': {...}}
    """
    from v1.regulatory.models import AlertMute

    out = {s: set() for s, _ in AlertMute.SCOPE_CHOICES}
    if user is None or not getattr(user, 'is_authenticated', True):
        return out
    for scope, value_norm in (AlertMute.objects
                              .filter(user=user)
                              .values_list('scope', 'value_norm')):
        if scope in out and value_norm:
            out[scope].add(value_norm)
    return out


def is_muted(mutes: dict, scope: str, value: str) -> bool:
    """muted_values() 결과에 value 가 걸리는지 — 정규화 규칙은 모델 한 곳에서 온다."""
    from v1.regulatory.models import normalize_mute_value

    if not mutes:
        return False
    bucket = mutes.get(scope)
    if not bucket:
        return False
    return normalize_mute_value(value) in bucket
