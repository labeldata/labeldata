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
    from v1.mobile.models import AppDevice, PushNotificationLog

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
        log, created = PushNotificationLog.objects.get_or_create(
            device=device,
            news=news,
            defaults={'rule_triggered': matched_rule},
        )
        if not created:
            continue

        sent += 1

        # FCM 푸시 발송
        if device.fcm_token:
            _send_fcm(device.fcm_token, news, matched_rule.keyword)

    return sent


def _send_fcm(token: str, news, keyword: str) -> None:
    """FCM Legacy HTTP API로 푸시 알림 발송."""
    import requests
    from django.conf import settings

    server_key = getattr(settings, 'FCM_SERVER_KEY', '')
    if not server_key:
        logger.debug('[FCM] FCM_SERVER_KEY 미설정 — 푸시 발송 생략')
        return

    product_or_company = (news.product_name or news.company_name or '부적합 정보')[:40]
    violation_type_map = {
        'admin': '행정처분',
        'recall': '회수',
        'labeling': '표시위반',
    }
    vtype = violation_type_map.get(getattr(news, 'violation_type', ''), '부적합')

    try:
        requests.post(
            'https://fcm.googleapis.com/fcm/send',
            headers={
                'Authorization': f'key={server_key}',
                'Content-Type': 'application/json',
            },
            json={
                'to': token,
                'notification': {
                    'title': f'⚠️ 알림 키워드 매칭: {keyword}',
                    'body': f'[{vtype}] {product_or_company} 관련 새 정보가 있습니다.',
                    'sound': 'default',
                },
                'data': {
                    'news_id': str(news.pk),
                    'keyword': keyword,
                    'type': 'regulatory_alert',
                },
                'priority': 'high',
            },
            timeout=5,
        )
    except Exception as e:
        logger.warning(f'[FCM] 발송 실패 (token={token[:20]}...): {e}')
