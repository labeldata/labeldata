from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    """사용자 추가 정보를 관리하는 모델"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=15, blank=True, help_text="사용자 전화번호")
    address = models.TextField(blank=True, help_text="사용자 주소")
    birth_date = models.DateField(null=True, blank=True, help_text="사용자 생년월일")
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True, help_text="사용자 프로필 이미지")

    def __str__(self):
        return f"Profile of {self.user.username}"
