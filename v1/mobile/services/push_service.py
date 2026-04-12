"""
모바일 앱 AlertRule 기반 푸시 알림 서비스.

수집된 RegulatoryNews와 각 AppDevice의 활성 AlertRule을 매칭하여
PushNotificationLog를 생성하고 FCM으로 알림을 발송한다.
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
        # 제품명 + ai_keywords 대상
        targets = [product_name] + ai_keywords
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets)
        else:  # EXACT
            return keyword == product_name or keyword in ai_keywords

    elif rule.category == 'COMPANY':
        # 업체명 대상
        if rule.match_type == 'CONTAINS':
            return keyword in company_name
        else:
            return keyword == company_name

    elif rule.category == 'ORIGIN':
        # 위반 사유 + ai_keywords 대상
        targets = ai_keywords + [violation_reason]
        if rule.match_type == 'CONTAINS':
            return any(keyword in t for t in targets)
        else:
            return any(keyword == t for t in targets)

    return False


def send_mobile_alerts_for_news(news) -> int:
    """
    수집된 뉴스와 활성 AlertRule을 매칭하여
    PushNotificationLog 생성 + FCM 발송.

    Returns: 신규 생성된 알림 수
    """
    from django.conf import settings
    from v1.mobile.models import AppDevice, PushNotificationLog

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)

    product_name = (news.product_name or '').lower()
    company_name = (news.company_name or '').lower()
    ai_keywords = [kw.lower() for kw in (news.ai_keywords or [])]
    violation_reason = (news.violation_reason or '').lower()

    # 활성 규칙이 있는 기기만 조회
    devices = (
        AppDevice.objects
        .prefetch_related('rules')
        .filter(rules__is_active=True)
        .distinct()
    )

    sent = 0
    for device in devices:
        # 기기의 활성 규칙 순서대로 첫 번째 매칭 규칙 찾기
        matched_rule = None
        for rule in device.rules.filter(is_active=True):
            if _matches_rule(rule, product_name, company_name, ai_keywords, violation_reason):
                matched_rule = rule
                break

        if matched_rule is None:
            continue

        # 중복 방지: 이미 이 기기+뉴스 조합의 알림이 있으면 스킵
        if PushNotificationLog.objects.filter(device=device, news=news).exists():
            continue

        # 알림 수 초과 시 가장 오래된 것 삭제
        _trim_notifications(device, max_noti)

        PushNotificationLog.objects.create(
            device=device,
            news=news,
            rule_triggered=matched_rule,
        )
        sent += 1

        # FCM 푸시 발송
        if device.fcm_token:
            _send_fcm(device.fcm_token, news, matched_rule.keyword)

    return sent


def backfill_alerts_for_rule(rule) -> int:
    """
    새로 등록된 AlertRule에 대해 기존 수집 데이터 전체를 대상으로 즉시 매칭.
    이미 알림이 존재하는 (device+news) 쌍은 건너뛴다.

    Returns: 신규 생성된 알림 수
    """
    from django.conf import settings
    from v1.mobile.models import PushNotificationLog
    from v1.regulatory.models import RegulatoryNews

    max_noti = getattr(settings, 'MOBILE_MAX_NOTIFICATIONS', 100)
    device = rule.device

    # AI 파싱 완료된 것만 대상
    qs = RegulatoryNews.objects.filter(ai_parsed=True).order_by('created_at')

    created_count = 0
    for news in qs:
        product_name = (news.product_name or '').lower()
        company_name = (news.company_name or '').lower()
        ai_keywords = [kw.lower() for kw in (news.ai_keywords or [])]
        violation_reason = (news.violation_reason or '').lower()

        if not _matches_rule(rule, product_name, company_name, ai_keywords, violation_reason):
            continue

        # 해당 기기+뉴스 조합 알림이 이미 있으면 스킵
        if PushNotificationLog.objects.filter(device=device, news=news).exists():
            continue

        # 알림 수 초과 시 가장 오래된 것 삭제
        _trim_notifications(device, max_noti)

        PushNotificationLog.objects.create(
            device=device,
            news=news,
            rule_triggered=rule,
        )
        created_count += 1

    return created_count


def _trim_notifications(device, max_count: int) -> None:
    """기기의 알림 수가 max_count 이상이면 가장 오래된 것부터 삭제."""
    from v1.mobile.models import PushNotificationLog

    current = PushNotificationLog.objects.filter(device=device).count()
    if current >= max_count:
        # 초과 개수만큼 오래된 것 삭제
        excess = current - max_count + 1  # +1: 새로 추가될 자리 확보
        old_ids = (
            PushNotificationLog.objects
            .filter(device=device)
            .order_by('created_at')
            .values_list('id', flat=True)[:excess]
        )
        PushNotificationLog.objects.filter(id__in=list(old_ids)).delete()


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

        # 환경변수가 JSON 문자열이면 파싱, 파일 경로면 파일 읽기
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


def _send_fcm(token: str, news, keyword: str) -> None:
    """FCM HTTP v1 API로 푸시 알림 발송."""
    import requests
    from django.conf import settings

    project_id = getattr(settings, 'FCM_PROJECT_ID', '')
    if not project_id:
        logger.debug('[FCM] FCM_PROJECT_ID 미설정 — 푸시 발송 생략')
        return

    access_token = _get_fcm_access_token()
    if not access_token:
        return

    product_or_company = (news.product_name or news.company_name or '부적합 정보')[:40]
    violation_type_map = {
        'admin': '행정처분',
        'recall': '회수',
        'labeling': '표시위반',
    }
    vtype = violation_type_map.get(getattr(news, 'violation_type', ''), '부적합')

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
                    'notification': {
                        'title': f'⚠️ 알림 키워드 매칭: {keyword}',
                        'body': f'[{vtype}] {product_or_company} 관련 새 정보가 있습니다.',
                    },
                    'data': {
                        'news_id': str(news.pk),
                        'keyword': keyword,
                        'type': 'regulatory_alert',
                    },
                    'android': {'priority': 'high'},
                    'apns': {
                        'payload': {'aps': {'sound': 'default'}},
                    },
                },
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(f'[FCM] 발송 실패 {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        logger.warning(f'[FCM] 발송 실패 (token={token[:20]}...): {e}')
