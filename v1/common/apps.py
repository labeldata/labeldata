from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.common'

    def ready(self):
        # 템플릿 정적 검사를 manage.py check 에 등록한다 (checks.py 참고)
        from . import checks  # noqa: F401
