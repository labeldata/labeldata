from django.db import models


class ApiKey(models.Model):
    """API 키를 관리하는 모델"""
    key = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.key


class ApiEndpoint(models.Model):
    """API 엔드포인트를 관리하는 모델"""
    name = models.CharField(max_length=255, help_text="API 이름")
    url = models.URLField(max_length=500, help_text="API URL")
    call_frequency_minutes = models.IntegerField(default=1440, help_text="호출 주기 (분 단위)")
    last_called_at = models.DateTimeField(null=True, blank=True, help_text="마지막 호출 시간")

    def __str__(self):
        return self.name
