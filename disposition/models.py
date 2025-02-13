from django.db import models


class AdministrativeDisposition(models.Model):
    """행정처분 관리 모델"""
    disposition_date = models.CharField(max_length=10,verbose_name="처분 확정일자")
    business_type = models.CharField(max_length=60,verbose_name="업종명", null=True, blank=True)
    business_name = models.CharField(max_length=200,verbose_name="업소명")
    road_address = models.CharField(max_length=300,verbose_name="도로명주소", null=True, blank=True)
    lotno_addr = models.CharField(max_length=300,verbose_name="지번주소", null=True, blank=True)
    disposition_details = models.TextField(max_length=100,verbose_name="처분사항", null=True, blank=True)

    administrative_id = models.TextField(max_length=20, verbose_name="행정처분번호")
    licence_no = models.CharField(max_length=30, verbose_name="인허가번호")
    representative_name = models.CharField(max_length=50, verbose_name="대표자명", null=True, blank=True)
    disposition_period = models.CharField(max_length=30, verbose_name="처분기간", null=True, blank=True)
    notice_details = models.TextField(max_length=100, verbose_name="안내사항", null=True, blank=True)

    violation_details = models.TextField(max_length=3000, verbose_name="위반내용", null=True, blank=True)
    
    processing_department = models.CharField(max_length=20, verbose_name="처리부서", null=True, blank=True)
    manager_name = models.CharField(max_length=20, verbose_name="담당자명", null=True, blank=True )
    contact_number = models.CharField(max_length=20, verbose_name="전화번호", null=True, blank=True)
    email = models.EmailField(max_length=100, verbose_name="이메일", null=True, blank=True)

    location = models.CharField(max_length=100, verbose_name="지역")

    def __str__(self):
        return self.administrative_id
    
    class Meta:
        db_table = "administrative_disposition"
        indexes = [
            #models.Index(fields=["administrative_id"], name="idx_administrative_id"),
        ]


class CrawlingSetting(models.Model):

    location = models.CharField(max_length=100, unique=True, verbose_name="지역")
    target_url = models.URLField(verbose_name="크롤링 대상 URL")
    crawling_period = models.IntegerField(default=1, verbose_name="크롤링 주기 (일 단위)")
    description = models.TextField(null=True, blank=True, help_text="설명")  # 추가 필드

    def __str__(self):
        return self.location

    class Meta:
        db_table = "crawling_setting"
        indexes = [
            #models.Index(fields=["administrative_id"], name="idx_administrative_id"),
        ]