"""
모바일 앱 AlertRule 기반 푸시 알림 서비스.

수집된 RegulatoryNews와 각 AppDevice의 활성 AlertRule을 매칭하여
PushNotificationLog를 생성한다.

FCM 실제 발송은 send_pending_alerts 커맨드(일 3회: 10시·14시·17시 KST)에서
일괄 처리한다. 수거검사 판정변동(PHASE_JUDGMENT)만 예외로 즉시 발송한다.
"""
import logging

logger = logging.getLogger(__name__)


def _matches_rule(rule, product_name: str, company_name: str,
                  ai_keywords: list, violation_reason: str) -> bool:
    """
    AlertRule 하나가 뉴스 데이터와 매칭되는지 확인.

    CONTAINS는 순수 문자열 포함 검사 외에 regulatory.matcher와 동일한
    RapidFuzz 퍼지매칭(_fuzzy_score, MATCH_THRESHOLD=72)도 함께 적용한다.
    BOM/원료 보관함 매칭은 오탈자·표기 변이("고추가루"↔"고춧가루")를 잡아내는데
    앱 키워드 매칭만 완전 문자열 비교여서 놓치는 비대칭을 없애기 위함.
    EXACT는 사용자가 명시적으로 정확한 표기를 원한 것이므로 그대로 둔다.
    """
    from v1.regulatory.services.matcher import _fuzzy_score, MATCH_THRESHOLD

    keyword = rule.keyword.lower().strip()
    if not keyword:
        return False

    def _fuzzy_any(targets: list) -> bool:
        return any(_fuzzy_score(keyword, t) >= MATCH_THRESHOLD for t in targets if t)

    if rule.category == 'INGREDIENT':
        targets = [product_name] + ai_keywords
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets) or _fuzzy_any(targets)
        else:
            return keyword == product_name or keyword in ai_keywords

    elif rule.category == 'COMPANY':
        if rule.match_type == 'CONTAINS':
            return keyword in company_name or _fuzzy_any([company_name])
        else:
            return keyword == company_name

    elif rule.category == 'ORIGIN':
        targets = ai_keywords + [violation_reason]
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets) or _fuzzy_any(targets)
        else:
            return any(keyword == t for t in targets)

    return False


def send_mobile_alerts_for_news(news) -> int:
    """
    수집된 뉴스에 대해 PushNotificationLog만 생성한다. FCM은 발송하지 않는다.
    실제 FCM 발송은 send_pending_alerts 커맨드에서 배치로 처리한다.

    Returns: 신규 생성된 로그 수
    """
    saved = 0
    # **제품·원료를 먼저 남긴다.**
    #
    # 두 함수 다 `(device, news)` 가 이미 있으면 건너뛴다 — 한 뉴스에 한
    # 사람당 알림은 하나면 되기 때문이다. 그런데 키워드를 먼저 돌리면,
    # 같은 뉴스가 등록해 둔 키워드에도 걸릴 때(흔한 낱말 하나면 그렇게 된다)
    # **내 제품이 걸렸다는 알림이 아예 안 만들어졌다.** 이 앱이 파는 것이
    # 바로 그 알림이고, `_trim_notifications` 의 티어 설계도 그것을 가장
    # 마지막까지 지키게 되어 있다.
    saved += _save_product_ingredient_logs(news)
    saved += _save_keyword_logs(news)
    return saved


def news_fields_for_matching(news) -> tuple:
    """_matches_rule 이 보는 네 가지를 한 번만 소문자로 만들어 둔다."""
    return (
        (news.product_name or '').lower(),
        (news.company_name or '').lower(),
        [kw.lower() for kw in (news.ai_keywords or [])],
        (news.violation_reason or '').lower(),
    )


def matching_rules_for_news(news, rules) -> list:
    """주어진 규칙 중 이 뉴스에 걸리는 것만 고른다."""
    fields = news_fields_for_matching(news)
    return [r for r in rules if _matches_rule(r, *fields)]


def save_keyword_match(news, rule) -> bool:
    """
    키워드 매칭을 **사용자**에 남긴다 (regulatory.NewsKeywordMatch).

    이것이 웹 화면이 보는 진짜 기록이다. 기기별 푸시 로그와 달리 앱을 깐 적이
    없어도 남는다 — 예전에는 이 표가 없어서, 앱을 안 쓰는 사용자에게는 키워드
    알림이 통째로 없는 것과 같았다(등록해도 "일치하는 정보가 없습니다").

    Returns: 새로 만들었으면 True
    """
    from v1.regulatory.models import NewsKeywordMatch

    if not rule.user_id:
        return False          # 비회원(기기) 규칙은 푸시 로그로만 남는다
    _, created = NewsKeywordMatch.objects.get_or_create(
        news=news, user_id=rule.user_id, rule=rule,
        defaults={
            'matched_keyword': rule.keyword,
            'category':        rule.category,
            'match_type':      rule.match_type,
        },
    )
    return created


def _save_keyword_logs(news) -> int:
    """
    AlertRule 키워드 매칭.

    판정은 한 번이고, 남기는 것은 둘이다.
      · NewsKeywordMatch — 사용자에 붙는다. 웹 화면(목록 배지·상세 구역)이 본다.
      · PushNotificationLog — 기기에 붙는다. FCM 발송 대기 줄이다.
    앱을 안 쓰는 사용자는 두 번째가 안 생기지만 첫 번째는 생긴다.
    """
    from django.conf import settings
    from v1.mobile.models import AppDevice, AlertRule, PushNotificationLog

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)
    fields = news_fields_for_matching(news)

    saved = 0

    # ── 1. 유저 기반 규칙 (로그인 사용자) ───────────────────────────────────
    user_rules = (
        AlertRule.objects
        .filter(user__isnull=False, is_active=True)
        .select_related('user')
    )

    # 사용자별로 **걸린 규칙을 모두** 모은다. 예전에는 첫 규칙 하나만 보고
    # 넘어갔는데, 그러면 상세에서 "무엇 때문에 왔는지" 를 한 개밖에 못 보여 준다.
    matched_by_user: dict = {}
    for rule in user_rules:
        if _matches_rule(rule, *fields):
            matched_by_user.setdefault(rule.user_id, []).append(rule)

    for user_id, rules in matched_by_user.items():
        for rule in rules:
            if save_keyword_match(news, rule):
                saved += 1

        # 푸시는 사용자당 한 건이면 된다 — 기기 알림함이 같은 뉴스로 도배되지 않게
        first_rule = rules[0]
        for device in AppDevice.objects.filter(user_id=user_id):
            if PushNotificationLog.objects.filter(device=device, news=news).exists():
                continue
            _trim_notifications(device, max_noti)
            PushNotificationLog.objects.create(
                device=device,
                news=news,
                rule_triggered=first_rule,
                trigger_type='keyword',
                trigger_label=first_rule.keyword,
                sent_at=None,
            )
            saved += 1

    # ── 2. 기기 기반 규칙 (비회원 게스트) ────────────────────────────────────
    guest_devices = (
        AppDevice.objects
        .prefetch_related('rules')
        .filter(user__isnull=True, rules__is_active=True, rules__user__isnull=True)
        .distinct()
    )

    for device in guest_devices:
        matched_rule = None
        for rule in device.rules.filter(is_active=True, user__isnull=True):
            if _matches_rule(rule, *fields):
                matched_rule = rule
                break

        if matched_rule is None:
            continue
        if PushNotificationLog.objects.filter(device=device, news=news).exists():
            continue

        _trim_notifications(device, max_noti)
        PushNotificationLog.objects.create(
            device=device,
            news=news,
            rule_triggered=matched_rule,
            trigger_type='keyword',
            trigger_label=matched_rule.keyword,
            sent_at=None,
        )
        saved += 1

    return saved


def _save_product_ingredient_logs(news) -> int:
    """제품/원료 보관함 매칭 — PushNotificationLog 저장 (FCM 발송 없음)."""
    from django.conf import settings
    from v1.mobile.models import AppDevice, PushNotificationLog
    from v1.regulatory.models import NewsProductMatch, NewsIngredientMatch

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)

    product_match_users = (
        NewsProductMatch.objects
        # 지운 제품으로는 알리지 않는다. 만드는 쪽(matcher)은 이 조건을
        # 거는데 여기는 안 걸어서, 소프트 삭제된 제품이 알림을 냈다.
        .filter(news=news, false_positive_yn=False, product__delete_YN='N')
        .values_list('product__user_id', 'product__prdlst_nm')
    )
    ingredient_match_users = (
        NewsIngredientMatch.objects
        .filter(news=news, dismissed_yn=False)
        .values_list('user_id', 'ingredient__prdlst_nm')
    )

    # 사람마다 걸린 것을 **전부** 모은다. 예전에는 `not in user_trigger` 로
    # 첫 건만 잡아서, 제품 셋이 걸려도 알림에는 하나만 적혔다 — 나머지 둘은
    # 없는 셈이 됐다.
    by_user = {}
    for user_id, product_name in product_match_users:
        if user_id:
            by_user.setdefault(user_id, {'product': [], 'ingredient': []})
            by_user[user_id]['product'].append(product_name or '내 제품')
    for user_id, ingr_name in ingredient_match_users:
        if user_id:
            by_user.setdefault(user_id, {'product': [], 'ingredient': []})
            by_user[user_id]['ingredient'].append(ingr_name or '원료')

    user_trigger = {}
    for user_id, found in by_user.items():
        # 제품이 원료보다 급하다 — 내 제품이 걸린 것은 바로 조치할 일이다.
        kind = 'product' if found['product'] else 'ingredient'
        names = found[kind]
        label = names[0]
        if len(names) > 1:
            label = '%s 외 %d건' % (label, len(names) - 1)
        user_trigger[user_id] = (kind, label)

    if not user_trigger:
        return 0

    devices = (
        AppDevice.objects
        .filter(user_id__in=user_trigger.keys())
        .select_related('user')
    )

    saved = 0
    for device in devices:
        trigger_type, trigger_label = user_trigger[device.user_id]

        if PushNotificationLog.objects.filter(device=device, news=news).exists():
            continue

        _trim_notifications(device, max_noti)

        PushNotificationLog.objects.create(
            device=device,
            news=news,
            rule_triggered=None,
            trigger_type=trigger_type,
            trigger_label=trigger_label,
            sent_at=None,   # 배치 발송 대기
        )
        saved += 1

    return saved


def cancel_pending_logs(user=None, news_ids=None, rule=None, device=None) -> dict:
    """
    아직 안 나간 푸시를 거두고, 이미 나간 것은 읽음으로 내린다.

    FCM 은 수집 즉시 나가지 않는다 — 로그만 먼저 쌓고 일 3회(10·14·17시)
    배치로 내보낸다(send_regulatory_batch_alerts). 그래서 03시에 걸린 알림을
    사용자가 09시에 끄면, 웹 목록에서는 사라졌는데 10시에 **푸시는 그대로**
    울린다. "껐는데 또 온다" 가 여기서 나온다.

    그래서 웹에서 끄거나 키워드를 지울 때 이 함수를 함께 부른다.
      • 아직 안 나간 로그(sent_at IS NULL) → 삭제. 보낸 적이 없으니 이력도 아니다.
      • 이미 나간 로그 → 읽음 처리. 앱 알림 탭에 남기되 배지는 내린다.
        (지우면 "어제 받은 그 알림" 을 다시 찾을 수 없다)

    news_ids: 이 뉴스들로 생긴 제품·원료 매칭 푸시를 거둔다 (알림 끄기)
    rule:     이 키워드 규칙으로 생긴 푸시를 거둔다 (키워드 삭제)
    user / device: 누구 것을 거둘지. 로그인 사용자는 user(기기 여러 대를 함께),
                   비회원은 device 하나. 앱의 키워드 삭제가 비회원에도 있어서
                   두 갈래를 다 받는다.

    Returns: {'cancelled': int, 'read': int}
    """
    from v1.mobile.models import PushNotificationLog

    if user is not None:
        qs = PushNotificationLog.objects.filter(device__user=user)
        owner = 'user=%s' % user.pk
    elif device is not None:
        qs = PushNotificationLog.objects.filter(device=device)
        owner = 'device=%s' % device.pk
    else:
        return {'cancelled': 0, 'read': 0}

    if rule is not None:
        qs = qs.filter(rule_triggered=rule)
    elif news_ids is not None:
        if not news_ids:
            return {'cancelled': 0, 'read': 0}
        qs = qs.filter(news_id__in=list(news_ids),
                       trigger_type__in=('product', 'ingredient'))
    else:
        return {'cancelled': 0, 'read': 0}

    cancelled, _ = qs.filter(sent_at__isnull=True).delete()
    read = qs.filter(sent_at__isnull=False, is_read=False).update(is_read=True)
    if cancelled or read:
        logger.info('[푸시 거두기] %s 예약취소=%s 읽음=%s', owner, cancelled, read)
    return {'cancelled': cancelled, 'read': read}


# 키워드를 새로 등록했을 때 **거슬러 맞춰 보는 기간**과 **한 번에 만드는 상한**.
#
# 예전에는 둘 다 없었다. 등록 한 번이 RegulatoryNews 전체를 한 줄씩 RapidFuzz 로
# 돌려 보고, 걸리는 족족 미확인 알림을 만들었다. 그것도 HTTP 요청 안에서 동기로.
# 수집이 쌓일수록 등록이 느려지고, 몇 해 전 처분까지 전부 알림함을 뒤덮었다.
#
# 사람이 키워드를 넣는 까닭은 "앞으로 이게 걸리면 알려 달라" 이지 "지난 5년치를
# 지금 다 읽겠다" 가 아니다. 옛 건은 알림이 아니라 검색으로 찾는 것이다.
# 수거검사 쪽이 이미 같은 판단을 했다 — `INSPECTION_BACKFILL_DAYS`.
#
# 부적합·처분은 수거검사보다 발생 빈도가 낮아 30일로 자르면 새로 등록한 사람이
# 빈 화면을 보기 쉽다. 그래서 세 배로 잡았다.
NEWS_BACKFILL_DAYS = 90
# 기기 알림함 상한(MOBILE_MAX_NOTIFICATIONS)과 같은 수. 그보다 많이 만들어 봐야
# 어차피 _trim_notifications 가 도로 지운다.
NEWS_BACKFILL_MAX = 100


def backfill_alerts_for_rule(rule) -> dict:
    """
    새로 등록된 AlertRule 에 대해 **최근 NEWS_BACKFILL_DAYS 일**의 수집 데이터를
    소급 매칭한다. 소급분은 과거 데이터이므로 sent_at 을 즉시 설정해 배치 발송
    대상에서 제외한다.

    'created' 는 **걸린 부적합 건수**다.
    예전에는 만들어진 푸시 로그 수였는데, 그 수는 기기 수에 따라 달라졌다.
    기기가 둘이면 한 건이 두 건으로 세어졌고, 앱을 안 쓰는 사용자는 아무리 많이
    걸려도 0 이었다 — 화면에는 "일치하는 정보가 없습니다" 가 뜨면서 그 아래
    미리보기가 다섯 건 보이는 모순이 여기서 나왔다.
    지금은 사용자 매칭(NewsKeywordMatch)을 세므로 화면 문구와 어긋나지 않는다.

    Returns: {'created': int, 'previews': list[dict], 'log_ids': list[int],
              'window_days': int, 'capped': bool}
    """
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Q
    from django.utils import timezone
    from v1.mobile.models import AppDevice, PushNotificationLog
    from v1.regulatory.models import RegulatoryNews

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)
    cutoff = timezone.now().date() - timedelta(days=NEWS_BACKFILL_DAYS)

    # 이 규칙이 푸시를 보낼 기기 (없어도 된다 — 웹 매칭은 기기와 무관하다)
    if rule.user:
        target_devices = list(AppDevice.objects.filter(user=rule.user))
    else:
        target_devices = [rule.device] if rule.device_id else []

    qs = RegulatoryNews.objects.all()
    if rule.category != 'COMPANY':
        qs = qs.filter(ai_parsed=True)
    # 기간은 **DB 에서** 자른다. Python 매칭(RapidFuzz)까지 끌고 오면 상한을
    # 둔 의미가 없다 — 진짜 비용은 만든 행 수가 아니라 읽어서 돌려 본 행 수다.
    # event_date 는 null 이 허용되므로 그때는 수집일로 본다.
    qs = qs.filter(Q(event_date__gte=cutoff)
                   | Q(event_date__isnull=True, collected_date__gte=cutoff))
    qs = qs.order_by('-event_date', '-collected_date')

    created_count = 0
    previews = []
    log_ids = []
    to_create = []
    capped = False

    for news in qs.iterator(chunk_size=200):
        if len(to_create) >= NEWS_BACKFILL_MAX:
            capped = True
            break
        if not _matches_rule(rule, *news_fields_for_matching(news)):
            continue

        if len(previews) < 5:
            previews.append({
                'id': news.pk,
                'product_name': news.product_name or '',
                'company_name': news.company_name or '',
                'event_date': str(news.event_date) if news.event_date else str(news.collected_date or ''),
                'violation_reason': (news.violation_reason or '')[:80],
                'source': news.source,
            })

        to_create.append(news)

    created_ids = []
    if to_create:
        now = timezone.now()

        # ① 사용자 매칭 — 웹 화면이 보는 기록. 기기가 없어도 남는다.
        for news in to_create:
            if save_keyword_match(news, rule):
                created_count += 1

        # ② 기기 푸시 로그 — 앱 알림함용. 기기가 없으면 이 단계는 통째로 건너뛴다.
        for device in target_devices:
            # **알림함을 통째로 비우지 않는다.**
            #
            # 예전에는 `max(1, max_noti - len(to_create))` 였다. 소급이 100건
            # 걸리면 그 값이 1 이 되어 `_trim_notifications(device, 1)` 이
            # 기존 알림을 **0개까지** 지웠다. 흔한 낱말("우유")을 키워드로
            # 넣는 순간, 안 읽은 "내 제품 부적합" 을 포함한 알림 100건이
            # 알린 적 없이 사라졌다.
            #
            # 상한은 상한이다. 넘치면 그때 오래된 것부터 밀리면 된다.
            #
            # **다 만든 뒤에 한 번 더 맞춘다.** 여기서만 잘라 두면 한 자리만
            # 비워지고(reserve=1) 그 뒤로 최대 100건이 들어와, 이미 100건이던
            # 기기가 99 → 199 가 됐다. MOBILE_MAX_NOTIFICATIONS 가 다음
            # 수집 때까지 두 배로 깨져 있었다.
            _trim_notifications(device, max_noti)
            for news in to_create:
                if PushNotificationLog.objects.filter(device=device, news=news).exists():
                    continue
                log = PushNotificationLog.objects.create(
                    device=device,
                    news=news,
                    rule_triggered=rule,
                    trigger_type='keyword',
                    trigger_label=rule.keyword,
                    sent_at=now,  # 소급 데이터 — 배치 발송 대상 제외
                )
                created_ids.append(log.pk)

            # 만든 뒤 상한을 정확히 맞춘다(reserve=0 — 더 만들 것이 없다).
            _trim_notifications(device, max_noti, reserve=0)

    return {'created': created_count, 'previews': previews, 'log_ids': created_ids,
            'window_days': NEWS_BACKFILL_DAYS, 'capped': capped}


def send_immediate_for_rule(rule, log_ids: list[int]) -> int:
    """
    신규/변경 키워드 등록 직후 해당 rule로 생성된 로그를 즉시 FCM 발송.
    배치 스케줄과 무관하게 즉시 실행된다.

    - 소급 매칭 건이 없으면(log_ids 빈 리스트) 발송 없이 0 반환
    - 웹 기기(fcm_token 없음)는 sent_at만 기록하고 FCM 스킵
    - 발송 후 해당 로그들의 sent_at을 현재 시각으로 업데이트

    Returns: FCM 발송 성공 수
    """
    if not log_ids:
        return 0

    from django.utils import timezone
    from v1.mobile.models import PushNotificationLog

    logs = list(
        PushNotificationLog.objects
        .filter(pk__in=log_ids, sent_at__isnull=True)
        .select_related('device', 'news')
    )
    if not logs:
        return 0

    total = len(logs)
    now   = timezone.now()
    sent  = 0

    # 기기 단위로 묶어 1건 FCM 발송
    device_logs: dict = {}
    for log in logs:
        device_logs.setdefault(log.device_id, []).append(log)

    for device_id, dlogs in device_logs.items():
        device = dlogs[0].device
        ids    = [l.pk for l in dlogs]

        # sent_at 기록 (FCM 여부 상관없이)
        PushNotificationLog.objects.filter(pk__in=ids).update(sent_at=now)

        token = device.fcm_token
        # 비로그인 기기 또는 FCM 토큰 없음 → 앱 내 알림 탭만 표시, FCM 미발송
        if not device.user_id or not token:
            continue

        title, body = _build_immediate_rule_message(rule, dlogs)
        ok = _send_fcm_raw(
            token=token,
            title=title,
            body=body,
            data={
                'type':    'keyword_immediate',
                'keyword': rule.keyword,
                'count':   str(len(dlogs)),
            },
            channel='food_safety_normal',
        )
        if ok:
            sent += 1

    return sent


def _build_immediate_rule_message(rule, logs: list) -> tuple[str, str]:
    """신규 키워드 즉시 알림 메시지 구성. logs는 항상 1건 이상."""
    cnt     = len(logs)
    keyword = rule.keyword
    sample  = logs[0].news
    product = (sample.product_name or sample.company_name or '부적합 정보')[:30] if sample else '부적합 정보'

    if cnt == 1:
        title = f'⚠️ 키워드 #{keyword} 매칭'
        body  = product
    else:
        title = f'⚠️ 키워드 #{keyword} — {cnt}건 매칭'
        body  = f'{product} 외 {cnt - 1}건'

    return title, body


def _trim_notifications(device, max_count: int, reserve: int = 1) -> None:
    """
    기기의 알림함이 `max_count` 를 넘지 않게 오래된 것부터 지운다.

    **무엇을 먼저 지우는가가 중요하다.** 예전에는 `trigger_type='keyword'`
    가 **아닌 것을 먼저** 지웠다. 그러면 나이와 무관하게 "내 제품이 부적합에
    걸렸다" 는 알림 — 이 앱에서 가장 중요한 것 — 이 몇 달 된 키워드 알림보다
    먼저 사라졌다. 독스트링은 "가장 오래된 것부터" 라고 적혀 있었는데 코드는
    반대였다.

    지우는 차례:
      1. 읽은 키워드 알림 (오래된 것부터)
      2. 읽은 그 밖의 알림
      3. 안 읽은 키워드 알림
      4. 안 읽은 제품·원료 알림  ← 마지막까지 지키는 것
    """
    from v1.mobile.models import PushNotificationLog

    # `reserve` 는 **곧 만들 것의 자리**다. 기본 1 은 "하나 만들 참이니
    # 한 자리 비워 달라" 는 뜻이고, 이미 만든 뒤에 상한만 맞추려면 0 을 준다.
    current = PushNotificationLog.objects.filter(device=device).count()
    excess = current - max_count + reserve
    if excess <= 0:
        return

    tiers = (
        {'is_read': True,  'trigger_type': 'keyword'},
        {'is_read': True},
        {'is_read': False, 'trigger_type': 'keyword'},
        {},
    )
    for tier in tiers:
        if excess <= 0:
            return
        ids = list(
            PushNotificationLog.objects
            .filter(device=device, **tier)
            .order_by('created_at')
            .values_list('id', flat=True)[:excess]
        )
        if not ids:
            continue
        PushNotificationLog.objects.filter(id__in=ids).delete()
        excess -= len(ids)


def _get_fcm_access_token() -> str:
    """Service Account JSON으로 FCM v1 API용 OAuth2 액세스 토큰 발급."""
    import json
    from django.conf import settings

    sa_json = getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', '')
    if not sa_json:
        logger.debug('[FCM] FCM_SERVICE_ACCOUNT_JSON 미설정')
        return ''

    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        if sa_json.strip().startswith('{'):
            sa_info = json.loads(sa_json)
        else:
            with open(sa_json, 'r', encoding='utf-8') as f:
                sa_info = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=['https://www.googleapis.com/auth/firebase.messaging'],
        )
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token or ''
    except Exception as e:
        logger.warning(f'[FCM] 토큰 발급 실패: {e}')
        return ''


def _send_fcm_raw(token: str, title: str, body: str,
                  data: dict | None = None,
                  channel: str = 'food_safety_normal') -> bool:
    """
    FCM HTTP v1 API 공통 발송 헬퍼.

    channel:
      food_safety_critical — 수거검사 판정변동 (긴급, PRIORITY_MAX)
      food_safety_normal   — 부적합·처분·수거검사 신규 배치 (PRIORITY_DEFAULT)
    """
    import requests
    from django.conf import settings

    project_id = getattr(settings, 'FCM_PROJECT_ID', '')
    if not project_id:
        logger.debug('[FCM] FCM_PROJECT_ID 미설정 — 푸시 발송 생략')
        return False

    access_token = _get_fcm_access_token()
    if not access_token:
        return False

    priority = 'PRIORITY_MAX' if channel == 'food_safety_critical' else 'PRIORITY_DEFAULT'

    try:
        resp = requests.post(
            f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            json={
                'message': {
                    'token': token,
                    'notification': {'title': title, 'body': body},
                    'data': {k: str(v) for k, v in (data or {}).items()},
                    'android': {
                        'priority': 'high',
                        'notification': {
                            'channel_id': channel,
                            'notification_priority': priority,
                            'sound': 'default',
                            'default_vibrate_timings': channel == 'food_safety_critical',
                        },
                    },
                    'apns': {
                        'payload': {'aps': {'sound': 'default'}},
                        'headers': {'apns-priority': '10'},
                    },
                },
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(f'[FCM] 발송 실패 {resp.status_code}: {resp.text[:200]}')
            return False
        return True
    except Exception as e:
        logger.warning(f'[FCM] 발송 실패 (token={token[:20]}...): {e}')
        return False


# ── 배치 발송 (send_pending_alerts 커맨드에서 호출) ────────────────────────────

def send_regulatory_batch_alerts() -> dict:
    """
    sent_at IS NULL인 PushNotificationLog를 사용자별·유형별로 묶어 FCM 1건 발송.
    send_pending_alerts 커맨드에서 호출한다.

    Returns: {'users': int, 'fcm_sent': int, 'logs_marked': int}
    """
    from django.utils import timezone
    from v1.mobile.models import AppDevice, PushNotificationLog

    pending = (
        PushNotificationLog.objects
        .filter(sent_at__isnull=True)
        .select_related('device__user', 'news', 'rule_triggered')
        .order_by('device__user_id', 'trigger_type', 'created_at')
    )

    # device_id → [logs] 그룹핑
    device_logs: dict = {}
    for log in pending:
        device_logs.setdefault(log.device_id, []).append(log)

    if not device_logs:
        return {'users': 0, 'fcm_sent': 0, 'logs_marked': 0}

    now = timezone.now()
    fcm_sent = 0
    logs_marked = 0
    users_notified = set()

    for device_id, logs in device_logs.items():
        try:
            device = logs[0].device
            token = device.fcm_token

            # FCM 없어도 sent_at 기록 (앱 알림 탭 표시용)
            ids = [l.pk for l in logs]
            PushNotificationLog.objects.filter(pk__in=ids).update(sent_at=now)
            logs_marked += len(ids)

            # 비로그인 기기 또는 FCM 토큰 없음 → 앱 내 알림 탭만 표시, FCM 미발송
            if not device.user_id or not token:
                continue

            title, body = _build_regulatory_batch_message(logs)

            # 유형별 건수 data payload
            kw_cnt   = sum(1 for l in logs if l.trigger_type == 'keyword')
            prod_cnt = sum(1 for l in logs if l.trigger_type == 'product')
            ing_cnt  = sum(1 for l in logs if l.trigger_type == 'ingredient')

            ok = _send_fcm_raw(
                token=token,
                title=title,
                body=body,
                data={
                    'type':          'regulatory_batch',
                    'total':         str(len(logs)),
                    'keyword_count': str(kw_cnt),
                    'product_count': str(prod_cnt),
                    'ingredient_count': str(ing_cnt),
                },
                channel='food_safety_normal',
            )
            if ok:
                fcm_sent += 1
                if device.user_id:
                    users_notified.add(device.user_id)

        except Exception as exc:
            logger.warning(f'[batch] 배치 알림 발송 실패 device_id={device_id}: {exc}')

    return {'users': len(users_notified), 'fcm_sent': fcm_sent, 'logs_marked': logs_marked}


def _build_regulatory_batch_message(logs: list) -> tuple[str, str]:
    """logs 목록으로 FCM 제목·본문 생성."""
    total = len(logs)

    kw_logs   = [l for l in logs if l.trigger_type == 'keyword']
    prod_logs = [l for l in logs if l.trigger_type == 'product']
    ing_logs  = [l for l in logs if l.trigger_type == 'ingredient']

    # 제목
    if total == 1:
        log = logs[0]
        if log.trigger_type == 'keyword':
            title = f'⚠️ 키워드 알림: #{log.trigger_label}'
        elif log.trigger_type == 'product':
            title = '⚠️ 내 제품 관련 알림'
        else:
            title = '⚠️ 원료 보관함 관련 알림'
    else:
        title = f'⚠️ 오늘 알림 {total}건'

    # 본문
    parts = []
    if kw_logs:
        # 키워드별 묶기
        kw_counts: dict = {}
        for l in kw_logs:
            kw_counts[l.trigger_label] = kw_counts.get(l.trigger_label, 0) + 1
        kw_summary = ', '.join(
            f'#{kw} {cnt}건' if cnt > 1 else f'#{kw}'
            for kw, cnt in list(kw_counts.items())[:3]
        )
        if len(kw_counts) > 3:
            kw_summary += f' 외 {len(kw_counts)-3}개 키워드'
        parts.append(kw_summary)

    if prod_logs:
        names = list({l.trigger_label for l in prod_logs})
        if len(names) == 1:
            parts.append(f'내 제품 [{names[0]}]')
        else:
            parts.append(f'내 제품 {len(names)}종')

    if ing_logs:
        names = list({l.trigger_label for l in ing_logs})
        if len(names) == 1:
            parts.append(f'원료 [{names[0]}]')
        else:
            parts.append(f'원료 {len(names)}종')

    body = ' · '.join(parts) if parts else '새 부적합·처분 정보가 있습니다.'
    return title, body


# ── 수거검사 알림 (PHASE_JUDGMENT: 즉시 / PHASE_COLLECTION: 배치) ──────────────

def send_inspection_judgment_batch(inspections: list) -> int:
    """
    PHASE_JUDGMENT(판정결과 변동) InspectionMatch를 사용자별로 묶어 FCM 1건 즉시 발송.
    수집 루프가 끝난 뒤 변동된 전체 목록을 받아 1회 호출한다.

    Returns: FCM 발송 성공 수
    """
    from django.utils import timezone
    from v1.regulatory.models import InspectionMatch
    from v1.mobile.models import AppDevice

    if not inspections:
        return 0

    inspection_ids = [ins.pk for ins in inspections]
    pending = (
        InspectionMatch.objects
        .filter(
            inspection_id__in=inspection_ids,
            alert_phase=InspectionMatch.PHASE_JUDGMENT,
            notified_at__isnull=True,
        )
        .select_related('user', 'inspection')
    )

    # 사용자별 그룹핑
    user_matches: dict = {}
    for match in pending:
        user_matches.setdefault(match.user_id, []).append(match)

    if not user_matches:
        return 0

    now = timezone.now()
    sent = 0

    for user_id, matches in user_matches.items():
        try:
            # 로그인된(user_id 있는) 기기만 FCM 발송 대상
            device = (
                AppDevice.objects
                .filter(user_id=user_id)
                .exclude(fcm_token='')
                .filter(fcm_token__isnull=False)
                .order_by('-last_active_at')
                .first()
            )

            ids = [m.pk for m in matches]
            InspectionMatch.objects.filter(pk__in=ids).update(notified_at=now, fcm_sent_at=now)

            if not device:
                continue

            cnt = len(matches)
            first_ins = matches[0].inspection
            pname = (first_ins.prdtnm or first_ins.bssh_nm or '제품')[:30]
            judgment = first_ins.jdgmnt_cd_nm or '결과 변동'

            if cnt == 1:
                body = f'{pname} → {judgment}'
            else:
                body = f'{pname} 외 {cnt - 1}건 판정결과 변동'

            ok = _send_fcm_raw(
                token=device.fcm_token,
                title='⚠️ 수거검사 판정결과 변동',
                body=body,
                data={
                    'type':  'inspection_judgment',
                    'count': str(cnt),
                },
                channel='food_safety_critical',
            )
            if ok:
                sent += 1

        except Exception as exc:
            logger.warning(f'[I0460] 판정변동 배치 FCM 실패 user_id={user_id}: {exc}')

    return sent


def send_inspection_batch_alerts() -> int:
    """
    PHASE_COLLECTION(신규 수거) 미발송 InspectionMatch를 사용자별로 묶어
    notified_at만 기록한다. 실제 FCM은 send_pending_alerts 커맨드에서 처리한다.

    collect_inspection_data() 루프가 끝난 뒤 1회 호출.

    Returns: notified_at이 기록된 사용자 수
    """
    from datetime import timedelta
    from django.utils import timezone
    from v1.regulatory.models import InspectionMatch

    cutoff = timezone.now() - timedelta(days=3)

    pending = (
        InspectionMatch.objects
        .filter(
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            notified_at__isnull=True,
            inspection__collected_at__gte=cutoff,
        )
        .select_related('user', 'inspection')
        .order_by('user_id', '-inspection__collected_at')
    )

    now = timezone.now()
    user_ids = set()
    for m in pending:
        m.notified_at = now
        m.save(update_fields=['notified_at'])
        user_ids.add(m.user_id)

    return len(user_ids)


def send_inspection_fcm_batch() -> dict:
    """
    notified_at이 기록된 PHASE_COLLECTION InspectionMatch 중
    FCM 미발송(fcm_sent_at IS NULL)인 것을 사용자별로 묶어 FCM 발송.
    send_pending_alerts 커맨드에서 호출한다.

    Returns: {'users': int, 'fcm_sent': int}
    """
    from datetime import timedelta
    from django.utils import timezone
    from v1.regulatory.models import InspectionMatch

    cutoff = timezone.now() - timedelta(days=3)

    pending = (
        InspectionMatch.objects
        .filter(
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            notified_at__isnull=False,
            fcm_sent_at__isnull=True,
            inspection__collected_at__gte=cutoff,
        )
        .select_related('user', 'inspection')
        .order_by('user_id', '-inspection__collected_at')
    )

    user_matches: dict = {}
    for m in pending:
        user_matches.setdefault(m.user_id, []).append(m)

    if not user_matches:
        return {'users': 0, 'fcm_sent': 0}

    now = timezone.now()
    fcm_sent = 0

    for user_id, matches in user_matches.items():
        try:
            from v1.mobile.models import AppDevice
            device = (
                AppDevice.objects
                .filter(user_id=user_id)
                .exclude(fcm_token='')
                .filter(fcm_token__isnull=False)
                .order_by('-last_active_at')
                .first()
            )

            ids = [m.pk for m in matches]
            InspectionMatch.objects.filter(pk__in=ids).update(fcm_sent_at=now)

            if not device:
                continue

            first_ins = matches[0].inspection
            pname = (first_ins.prdtnm or first_ins.bssh_nm or '제품')[:30]
            cnt = len(matches)
            body = (
                f"'{pname}' 외 {cnt-1}건이 수거 대상입니다." if cnt > 1
                else f"'{pname}'이(가) 수거 대상입니다."
            )

            ok = _send_fcm_raw(
                token=device.fcm_token,
                title='🔍 수거검사 접수',
                body=body,
                data={
                    'type':  'inspection_batch',
                    'count': str(cnt),
                },
                channel='food_safety_normal',
            )
            if ok:
                fcm_sent += 1

        except Exception as exc:
            logger.warning(f'[I0460] 배치 FCM 발송 실패 user_id={user_id}: {exc}')

    return {'users': len(user_matches), 'fcm_sent': fcm_sent}
