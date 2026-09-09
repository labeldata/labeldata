"""
알림 제외(뮤트) 처리.

화면에서 "이 키워드 때문에 오는 알림은 그만" 을 눌렀을 때 해야 할 일이 둘이다.

  ① 앞으로 안 생기게 — AlertMute 한 줄을 남긴다. 매칭 엔진(services/matcher.py)과
     수거검사 수집기(services/collector.py)가 이 표를 보고 매칭을 만들지 않는다.
  ② 이미 쌓인 것을 치우기 — 그러지 않으면 껐는데도 목록이 그대로라
     "안 먹었다" 고 판단하고 같은 것을 또 누른다.
  ③ 예약된 푸시 거두기 — FCM 은 일 3회 배치로 나간다. 03시에 걸린 알림을
     09시에 껐는데 10시에 푸시가 울리면, 웹에서 껐다는 사실 자체를 못 믿게 된다.
     식품 안심 알리미(앱) 쪽 로그도 여기서 함께 정리한다.

②는 기존의 '오탐지/해당 없음' 과 **같은 표시**를 쓴다(false_positive_yn /
dismissed_yn). 상태를 새로 만들면 배지·필터·오탐 학습이 저마다 다른 규칙을
갖게 된다. 껐다 켜도 이미 치운 것은 돌아오지 않는데, 이것도 오탐지 처리와
같은 성질이다 — 켜는 것은 '앞으로 받겠다' 는 뜻이다.
"""
import logging

from django.utils import timezone

from v1.mobile.services.push_service import cancel_pending_logs
from v1.regulatory.models import (
    AlertMute, InspectionMatch, NewsIngredientMatch, NewsProductMatch,
    normalize_mute_value,
)

logger = logging.getLogger(__name__)

VALID_SCOPES = {s for s, _ in AlertMute.SCOPE_CHOICES}


def apply_mute(user, scope: str, value: str, memo: str = '') -> dict:
    """
    제외 규칙을 등록하고, 그 규칙에 걸리는 기존 매칭을 함께 치운다.

    Returns: {'mute': AlertMute, 'created': bool, 'hidden': int}
    """
    value = (value or '').strip()
    norm  = normalize_mute_value(value)
    if scope not in VALID_SCOPES or not norm:
        raise ValueError('잘못된 제외 규칙')

    mute, created = AlertMute.objects.get_or_create(
        user=user, scope=scope, value_norm=norm,
        defaults={'value': value, 'memo': memo},
    )
    hidden, hidden_news_ids = _hide_existing(user, scope, norm)
    if hidden:
        mute.hidden_count = (mute.hidden_count or 0) + hidden
        mute.save(update_fields=['hidden_count'])

    # 앱(식품 안심 알리미)에 예약된 푸시도 함께 거둔다
    push = cancel_pending_logs(user, news_ids=hidden_news_ids)

    logger.info('[알림 제외] user=%s scope=%s value=%r 기존정리=%d 푸시취소=%d',
                user.pk, scope, value, hidden, push['cancelled'])
    return {'mute': mute, 'created': created, 'hidden': hidden,
            'push_cancelled': push['cancelled']}


def _hide_existing(user, scope: str, norm: str) -> tuple:
    """
    이 규칙에 걸리는 기존 매칭을 숨긴다.

    비교는 파이썬에서 한다 — 정규화가 공백 제거까지 하므로 SQL 의 iexact 로는
    '고춧 가루' 를 못 잡는다. 훑는 범위는 그 사용자의 매칭 행뿐이고, 이 버튼은
    자주 눌리는 것이 아니라 한 번 훑는 값이 충분하다.

    Returns: (숨긴 건수, 그 매칭들이 달려 있던 뉴스 id 집합)
             뉴스 id 는 앱에 예약된 푸시를 같은 기준으로 거두는 데 쓴다.
    """
    now = timezone.now()
    hidden = 0
    news_ids = set()

    if scope == AlertMute.SCOPE_KEYWORD:
        prod_field, ing_field = 'matched_keyword', 'matched_keyword'
    elif scope == AlertMute.SCOPE_INGREDIENT:
        prod_field, ing_field = 'matched_ingredient', 'ingredient__prdlst_nm'
    else:                                   # SCOPE_COMPANY
        prod_field, ing_field = 'news__company_name', None

    prod_hits = [
        (pk, nid) for pk, nid, val in (
            NewsProductMatch.objects
            .filter(product__user_id=user, false_positive_yn=False)
            .values_list('id', 'news_id', prod_field)
        )
        if normalize_mute_value(val or '') == norm
    ]
    if prod_hits:
        NewsProductMatch.objects.filter(id__in=[pk for pk, _ in prod_hits]).update(
            false_positive_yn=True, false_positive_at=now,
            read_yn=True, read_at=now,
        )
        hidden += len(prod_hits)
        news_ids.update(nid for _, nid in prod_hits)

    if ing_field:
        ing_hits = [
            (pk, nid) for pk, nid, val in (
                NewsIngredientMatch.objects
                .filter(user=user, dismissed_yn=False)
                .values_list('id', 'news_id', ing_field)
            )
            if normalize_mute_value(val or '') == norm
        ]
        if ing_hits:
            NewsIngredientMatch.objects.filter(id__in=[pk for pk, _ in ing_hits]).update(
                dismissed_yn=True, read_yn=True,
            )
            hidden += len(ing_hits)
            news_ids.update(nid for _, nid in ing_hits)

    if scope == AlertMute.SCOPE_COMPANY:
        # 수거검사는 '해당 없음' 이 곧 삭제다(inspection_dismiss 와 같은 처리).
        # 같은 업소가 계속 올라오므로 남겨 두면 목록이 그대로다.
        insp_ids = [
            pk for pk, val in (
                InspectionMatch.objects
                .filter(user=user)
                .values_list('id', 'inspection__bssh_nm')
            )
            if normalize_mute_value(val or '') == norm
        ]
        if insp_ids:
            InspectionMatch.objects.filter(id__in=insp_ids).delete()
            hidden += len(insp_ids)

    return hidden, news_ids


def mute_payload(mute: AlertMute) -> dict:
    """JSON 응답·화면 갱신용 한 줄."""
    return {
        'id':            mute.id,
        'scope':         mute.scope,
        'scope_display': mute.get_scope_display(),
        'value':         mute.value,
        'memo':          mute.memo,
        'hidden_count':  mute.hidden_count,
        'created_at':    mute.created_at.strftime('%Y-%m-%d %H:%M'),
    }
