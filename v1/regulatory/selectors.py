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
