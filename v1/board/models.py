from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class Board(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_hidden = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='board_files/', blank=True, null=True)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # 필수 필드
    is_notice = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Comment(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Comment by {self.author} on {self.board}'

    def clean(self):
        if not self.content.strip():
            raise ValidationError('댓글 내용은 비어 있을 수 없습니다.')