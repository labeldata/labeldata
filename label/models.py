from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


class FoodType(models.Model):
    """식품유형을 관리하는 모델"""
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    """제품 정보를 관리하는 모델"""
    title = models.CharField(max_length=200)
    api_data = models.JSONField(null=True, blank=True)  # API 호출 데이터 저장
    is_api_data = models.BooleanField(default=False)  # API 데이터 여부
    food_type = models.ForeignKey(
        FoodType, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts'
    )
    manufacturer = models.CharField(max_length=100)
    ingredients = models.TextField()
    storage_conditions = models.CharField(max_length=100)
    precautions = models.TextField(blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)
    likers = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    def __str__(self):
        return self.title


class Comment(models.Model):
    """게시글의 댓글을 관리하는 모델"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)
    likers = models.ManyToManyField(User, related_name='liked_comments', blank=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"


class FoodItem(models.Model):
    """식약처 품목 정보를 관리하는 모델"""
    product_name = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    report_date = models.DateField()
    category = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.product_name
