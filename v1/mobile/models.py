from django.conf import settings
from django.db import models


class AppDevice(models.Model):
    PLATFORM_CHOICES = [('android', 'Android'), ('ios', 'iOS')]

    device_id = models.CharField('기기 ID', max_length=255, unique=True, help_text='Flutter에서 생성한 UUID')
    fcm_token = models.CharField('FCM 토큰', max_length=500, blank=True, null=True, help_text='Firebase 푸시 알림 발송용 토큰')
    platform = models.CharField('플랫폼', max_length=10, choices=PLATFORM_CHOICES, default='android')
    app_version = models.CharField('앱 버전', max_length=20, blank=True)
    created_at = models.DateTimeField('최초 등록일', auto_now_add=True)
    last_active_at = models.DateTimeField('마지막 활동일', auto_now=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='app_devices',
        verbose_name='연결된 유저',
    )

    class Meta:
        db_table = 'mobile_app_device'
        verbose_name = '앱 기기'
        verbose_name_plural = '앱 기기 목록'

    def __str__(self):
        return f'{self.platform} / {self.device_id[:8]}'


class AlertRule(models.Model):
    CATEGORY_CHOICES = [
        ('INGREDIENT', '원료/제품명'),
        ('COMPANY', '업체명'),
        ('ORIGIN', '원산지'),
    ]
    MATCH_CHOICES = [('EXACT', '일치'), ('CONTAINS', '포함')]

    device = models.ForeignKey(AppDevice, on_delete=models.CASCADE, related_name='rules', verbose_name='기기')
    category = models.CharField('분류', max_length=20, choices=CATEGORY_CHOICES)
    keyword = models.CharField('키워드', max_length=100)
    match_type = models.CharField('매칭 방식', max_length=20, choices=MATCH_CHOICES, default='CONTAINS')
    is_active = models.BooleanField('활성 여부', default=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)

    class Meta:
        db_table = 'mobile_alert_rule'
        verbose_name = '알림 키워드'
        verbose_name_plural = '알림 키워드 목록'
        ordering = ['-created_at']
        unique_together = [('device', 'category', 'keyword', 'match_type')]

    def __str__(self):
        return f'[{self.category}] {self.keyword}'


class PushNotificationLog(models.Model):
    device = models.ForeignKey(AppDevice, on_delete=models.CASCADE, related_name='notifications', verbose_name='기기')
    news = models.ForeignKey('regulatory.RegulatoryNews', on_delete=models.CASCADE, related_name='push_logs', verbose_name='관련 부적합 정보')
    rule_triggered = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, related_name='notifications', verbose_name='트리거된 키워드 규칙')
    is_read = models.BooleanField('읽음 여부', default=False, db_index=True)
    created_at = models.DateTimeField('발송일시', auto_now_add=True)

    class Meta:
        db_table = 'mobile_push_notification_log'
        verbose_name = '푸시 알림 이력'
        verbose_name_plural = '푸시 알림 이력 목록'
        ordering = ['-created_at']


class Bookmark(models.Model):
    device = models.ForeignKey(AppDevice, on_delete=models.CASCADE, related_name='bookmarks', verbose_name='기기')
    news = models.ForeignKey('regulatory.RegulatoryNews', on_delete=models.CASCADE, related_name='bookmarks', verbose_name='부적합 정보')
    memo = models.TextField('메모', blank=True)
    created_at = models.DateTimeField('스크랩일', auto_now_add=True)

    class Meta:
        db_table = 'mobile_bookmark'
        verbose_name = '스크랩'
        verbose_name_plural = '스크랩 목록'
        ordering = ['-created_at']


class AppVersion(models.Model):
    PLATFORM_CHOICES = [('android', 'Android'), ('ios', 'iOS')]

    platform = models.CharField('플랫폼', max_length=10, choices=PLATFORM_CHOICES, unique=True)
    min_version = models.CharField('최소 허용 버전', max_length=20, help_text='이 버전 미만이면 강제 업데이트 팝업 표시 (예: 1.2.0)')
    latest_version = models.CharField('최신 버전', max_length=20, help_text='현재 스토어에 배포된 최신 버전 (예: 1.3.0)')
    store_url = models.URLField('스토어 URL', help_text='Google Play 또는 App Store 링크')
    force_message = models.CharField('강제 업데이트 메시지', max_length=200, default='새로운 버전이 출시되었습니다. 업데이트 후 이용해주세요.')
    updated_at = models.DateTimeField('최종 수정일시', auto_now=True)

    class Meta:
        db_table = 'mobile_app_version'
        verbose_name = '앱 버전 관리'
        verbose_name_plural = '앱 버전 관리'

    def __str__(self):
        return f'{self.platform} {self.latest_version}'


class AnalyticsEvent(models.Model):
    EVENT_CHOICES = [
        ('click_v2_banner', 'V2 배너 클릭'),
        ('add_alert_rule', '알림 키워드 추가'),
        ('share_news', '부적합 정보 공유'),
        ('bookmark_news', '부적합 정보 스크랩'),
        ('login_from_app', '앱 로그인'),
        ('notification_open', '알림 열람'),
    ]

    device = models.ForeignKey(AppDevice, on_delete=models.CASCADE, related_name='events', verbose_name='기기')
    event_name = models.CharField('이벤트명', max_length=50, choices=EVENT_CHOICES, db_index=True)
    params = models.JSONField('파라미터', default=dict, blank=True, help_text='추가 정보 (예: {"news_id": 12, "category": "INGREDIENT"})')
    created_at = models.DateTimeField('발생일시', auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'mobile_analytics_event'
        verbose_name = '앱 이벤트 로그'
        verbose_name_plural = '앱 이벤트 로그 목록'
        ordering = ['-created_at']
