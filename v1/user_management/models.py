from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """사용자 추가 정보를 관리하는 모델"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=15, blank=True, help_text="사용자 전화번호")
    address = models.TextField(blank=True, help_text="사용자 주소")
    birth_date = models.DateField(null=True, blank=True, help_text="사용자 생년월일")
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True, help_text="사용자 프로필 이미지")
    # 이메일 인증 및 유료 서비스 관련 필드
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=128, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    password_reset_token = models.CharField(max_length=128, blank=True, null=True)
    password_reset_sent_at = models.DateTimeField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    subscription_type = models.CharField(max_length=20, blank=True, null=True)
    subscription_expiry = models.DateTimeField(blank=True, null=True)

    # ── 내 정보 수정: 회사 기본 정보 ──────────────────────────────────
    company_name = models.CharField(max_length=100, blank=True, verbose_name="회사명")
    license_number = models.CharField(max_length=100, blank=True, verbose_name="인허가번호",
                                      help_text="영업허가번호 또는 품목제조보고번호")
    manufacturer_name = models.CharField(max_length=200, blank=True, verbose_name="제조원")
    manufacturer_address = models.CharField(max_length=300, blank=True, verbose_name="제조원 소재지")

    def __str__(self):
        return f"Profile of {self.user.username}"


class CompanyDocument(models.Model):
    """회사 고정 서류 — 제품 등록 시 불러오기 사용"""
    DOC_TYPE_CHOICES = [
        ('business_report', '영업신고증'),
        ('haccp', 'HACCP 인증서'),
        ('manufacture_license', '제조업 영업등록증'),
        ('iso', 'ISO 인증서'),
        ('organic', '유기농인증서'),
        ('etc', '기타'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, verbose_name="서류 종류")
    doc_name = models.CharField(max_length=200, blank=True, verbose_name="서류명",
                                help_text="비워두면 서류 종류 이름으로 자동 저장됩니다")
    doc_file = models.FileField(upload_to='company_documents/%Y/', verbose_name="파일")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=300, blank=True, verbose_name="메모")

    class Meta:
        ordering = ['doc_type', '-uploaded_at']
        verbose_name = '회사 고정 서류'
        verbose_name_plural = '회사 고정 서류'

    def save(self, *args, **kwargs):
        if not self.doc_name:
            self.doc_name = self.get_doc_type_display()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} — {self.doc_name}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance,
            is_email_verified=False,
            email_verification_token='',
            password_reset_token=''
        )
