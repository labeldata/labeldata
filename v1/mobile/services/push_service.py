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
    """AlertRule 하나가 뉴스 데이터와 매칭되는지 확인."""
    keyword = rule.keyword.lower().strip()
    if not keyword:
        return False

    if rule.category == 'INGREDIENT':
        targets = [product_name] + ai_keywords
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets)
        else:
            return keyword == product_name or keyword in ai_keywords

    elif rule.category == 'COMPANY':
        if rule.match_type == 'CONTAINS':
            return keyword in company_name
        else:
            return keyword == company_name

    elif rule.category == 'ORIGIN':
        targets = ai_keywords + [violation_reason]
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets)
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
    saved += _save_keyword_logs(news)
    saved += _save_product_ingredient_logs(news)
    return saved


def _save_keyword_logs(news) -> int:
    """AlertRule 키워드 매칭 — PushNotificationLog 저장 (FCM 발송 없음)."""
    from django.conf import settings
    from v1.mobile.models import AppDevice, PushNotificationLog

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)

    product_name    = (news.product_name or '').lower()
    company_name    = (news.company_name or '').lower()
    ai_keywords     = [kw.lower() for kw in (news.ai_keywords or [])]
    violation_reason = (news.violation_reason or '').lower()

    devices = (
        AppDevice.objects
        .prefetch_related('rules')
        .filter(rules__is_active=True)
        .distinct()
    )

    saved = 0
    for device in devices:
        matched_rule = None
        for rule in device.rules.filter(is_active=True):
            if _matches_rule(rule, product_name, company_name, ai_keywords, violation_reason):
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
            sent_at=None,   # 배치 발송 대기
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
        .filter(news=news, false_positive_yn=False)
        .select_related('product')
        .values_list('product__user_id', 'product__prdlst_nm')
    )
    ingredient_match_users = (
        NewsIngredientMatch.objects
        .filter(news=news, dismissed_yn=False)
        .select_related('ingredient')
        .values_list('user_id', 'ingredient__prdlst_nm')
    )

    user_trigger = {}
    for user_id, product_name in product_match_users:
        if user_id and user_id not in user_trigger:
            user_trigger[user_id] = ('product', product_name or '내 제품')
    for user_id, ingr_name in ingredient_match_users:
        if user_id and user_id not in user_trigger:
            user_trigger[user_id] = ('ingredient', ingr_name or '원료')

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


def backfill_alerts_for_rule(rule) -> dict:
    """
    새로 등록된 AlertRule에 대해 기존 수집 데이터 전체를 소급 매칭.
    소급분은 과거 데이터이므로 sent_at을 즉시 설정해 배치 발송 대상에서 제외한다.

    Returns: {'created': int, 'previews': list[dict]}
    """
    from django.conf import settings
    from django.utils import timezone
    from v1.mobile.models import PushNotificationLog
    from v1.regulatory.models import RegulatoryNews

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)
    device = rule.device

    if rule.category == 'COMPANY':
        qs = RegulatoryNews.objects.all().order_by('-event_date', '-collected_date')
    else:
        qs = RegulatoryNews.objects.filter(ai_parsed=True).order_by('-event_date', '-collected_date')

    created_count = 0
    previews = []
    to_create = []

    for news in qs:
        product_name     = (news.product_name or '').lower()
        company_name     = (news.company_name or '').lower()
        ai_keywords      = [kw.lower() for kw in (news.ai_keywords or [])]
        violation_reason = (news.violation_reason or '').lower()

        if not _matches_rule(rule, product_name, company_name, ai_keywords, violation_reason):
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

        if PushNotificationLog.objects.filter(device=device, news=news).exists():
            continue

        to_create.append(news)

    created_ids = []
    if to_create:
        target = max(1, max_noti - len(to_create))
        _trim_notifications(device, target)
        now = timezone.now()
        for news in to_create:
            log = PushNotificationLog.objects.create(
                device=device,
                news=news,
                rule_triggered=rule,
                trigger_type='keyword',
                trigger_label=rule.keyword,
                sent_at=now,  # 소급 데이터 — 배치 발송 대상 제외 (즉시 발송은 호출부에서 처리)
            )
            created_ids.append(log.pk)
            created_count += 1

    return {'created': created_count, 'previews': previews, 'log_ids': created_ids}


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
        if not token:
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


def _trim_notifications(device, max_count: int) -> None:
    """기기의 알림 수가 max_count 이상이면 가장 오래된 것부터 삭제."""
    from v1.mobile.models import PushNotificationLog

    current = PushNotificationLog.objects.filter(device=device).count()
    if current < max_count:
        return

    excess = current - max_count + 1

    non_kw_ids = list(
        PushNotificationLog.objects
        .filter(device=device)
        .exclude(trigger_type='keyword')
        .order_by('created_at')
        .values_list('id', flat=True)[:excess]
    )
    if non_kw_ids:
        PushNotificationLog.objects.filter(id__in=non_kw_ids).delete()
        excess -= len(non_kw_ids)

    if excess <= 0:
        return

    kw_ids = list(
        PushNotificationLog.objects
        .filter(device=device, trigger_type='keyword')
        .order_by('created_at')
        .values_list('id', flat=True)[:excess]
    )
    if kw_ids:
        PushNotificationLog.objects.filter(id__in=kw_ids).delete()


# ── FCM 공통 유틸 ─────────────────────────────────────────────────────────────

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

            if not token:
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
