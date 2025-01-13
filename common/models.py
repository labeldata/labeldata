from django.db import models

class ApiKey(models.Model):
    """API 키를 관리하는 모델"""
    key = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="API 키 생성 시간")
    updated_at = models.DateTimeField(auto_now=True, help_text="API 키 갱신 시간")

    def __str__(self):
        return self.key

from django.db import models

class ApiEndpoint(models.Model):
    """API 엔드포인트를 관리하는 모델"""
    name = models.CharField(max_length=255, help_text="API 이름")
    url = models.URLField(max_length=500, help_text="API URL")
    service_name = models.CharField(max_length=50, help_text="서비스 이름", default='default_service')
    call_frequency_minutes = models.IntegerField(default=1440, help_text="호출 주기 (분 단위)")
    last_called_at = models.DateTimeField(null=True, blank=True, help_text="마지막 호출 시간")
    last_status = models.CharField(
        max_length=50,
        choices=[("success", "성공"), ("failure", "실패")],
        default="success",
        help_text="마지막 호출 상태"
    )
    api_key = models.ForeignKey(
        'ApiKey', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='endpoints',
        help_text="API 키"
    )
    service_name = models.CharField(max_length=50, help_text="서비스 이름 (예: I1250)")  # 추가 필드

    def __str__(self):
        return self.name

class AdministrativeAction(models.Model):
    """행정처분 정보"""
    company_name = models.CharField(max_length=255, help_text="업체명", default="Unknown Company")
    registration_number = models.CharField(max_length=100, help_text="인허가번호")
    action_name = models.CharField(max_length=255, help_text="행정처분명")
    action_date = models.DateField(help_text="행정처분일")
    details = models.TextField(blank=True, help_text="기타 세부 내용")

    def __str__(self):
        return f"{self.company_name} - {self.action_name} ({self.action_date})"