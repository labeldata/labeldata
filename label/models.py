from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class FoodType(models.Model):
    name = models.CharField(max_length=200, unique=True)  # 식품유형명
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(auto_now=True)      # 수정일시

    def __str__(self):
        return self.name

class Post(models.Model):
    title = models.CharField(max_length=200)  # 제품명
    food_type = models.CharField(max_length=100)  # 식품유형
    manufacturer = models.CharField(max_length=100)  # 제조사
    ingredients = models.TextField()  # 원재료명
    storage_conditions = models.CharField(max_length=100)  # 보관조건
    precautions = models.TextField(blank=True)  # 기타 주의사항
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)
    likers = models.ManyToManyField(User, related_name='liked_posts', blank=True)  # 좋아요 관계

    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)
    likers = models.ManyToManyField(User, related_name='liked_comments', blank=True)  # 좋아요 관계

