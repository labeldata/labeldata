from django.apps import AppConfig


class UserManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.user_management'

    def ready(self):
        import v1.user_management.models  # noqa: F401 – signal 연결 보장
