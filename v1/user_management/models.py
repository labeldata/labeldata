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
    # 이메일 인증 및 유료 서비스 관련 필드 추가
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=128, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    password_reset_token = models.CharField(max_length=128, blank=True, null=True)
    password_reset_sent_at = models.DateTimeField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    subscription_type = models.CharField(max_length=20, blank=True, null=True)
    subscription_expiry = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance,
            is_email_verified=False,
            email_verification_token='',
            password_reset_token=''
        )
