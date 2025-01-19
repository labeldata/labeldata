from django.db import models


class AdministrativeAction(models.Model):
    """행정처분 관리 모델"""
    company_name = models.CharField(max_length=255, help_text="업체명")
    action_name = models.CharField(max_length=255, help_text="처분명")
    action_date = models.DateField(help_text="처분 확정일자")
    registration_number = models.CharField(max_length=100, null=True, blank=True, help_text="등록번호")  # 추가
    details = models.TextField(null=True, blank=True, help_text="세부사항")  # 추가

    def __str__(self):
        return f"{self.company_name} - {self.action_name}"


class CrawlingSetting(models.Model):
    local_gov_name = models.CharField(max_length=100, unique=True, help_text="지자체 이름")
    target_url = models.URLField(help_text="크롤링 대상 URL")
    crawling_period = models.IntegerField(default=1, help_text="크롤링 주기 (일 단위)")
    crawling_fields = models.JSONField(default=dict, help_text="크롤링 항목 (JSON 필드)")
    description = models.TextField(null=True, blank=True, help_text="설명")  # 추가 필드

    def __str__(self):
        return f"{self.local_gov_name} - {self.target_url}"