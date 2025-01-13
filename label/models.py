from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class FoodType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="활성 상태")

    def __str__(self):
        return self.name

class Post(models.Model):
    title = models.CharField(max_length=200)
    api_data = models.JSONField(null=True, blank=True, help_text="API에서 가져온 데이터")
    is_api_data = models.BooleanField(default=False, help_text="이 데이터가 API에서 가져온 데이터인지 여부")
    food_type = models.ForeignKey(FoodType, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    manufacturer = models.CharField(max_length=100, db_index=True)
    ingredients = models.TextField()
    storage_conditions = models.CharField(max_length=100)
    precautions = models.TextField(blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000, help_text="댓글 내용 (최대 1000자)")
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"

class FoodItem(models.Model):
    product_name = models.CharField(max_length=255, help_text="제품 이름", db_index=True)
    manufacturer_name = models.CharField(max_length=255, help_text="제조사 이름", db_index=True)
    report_date = models.DateField(help_text="신고일")
    category = models.CharField(max_length=255, help_text="카테고리")
    additional_details = models.JSONField(blank=True, null=True, help_text="추가 세부사항 (JSON 형식)")

    def __str__(self):
        return self.product_name

class Label(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="labels", null=False)
    content_weight = models.CharField(max_length=50, help_text="내용량(열량)")
    manufacturer_address = models.CharField(max_length=255, help_text="제조원 소재지")
    storage_method = models.TextField(help_text="보관방법")

    def __str__(self):
        return f"Label for {self.food_item.product_name}"
