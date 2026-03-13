from django.apps import AppConfig


class ActivityLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.activity_log'
    verbose_name = '사용자 활동 로그'
