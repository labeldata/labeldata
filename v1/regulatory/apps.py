from django.apps import AppConfig


class RegulatoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.regulatory'
    verbose_name = '부적합.처분 알림'

    def ready(self):
        import v1.regulatory.signals  # noqa: F401 — signal 등록
