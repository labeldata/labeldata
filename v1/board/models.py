from django.db import models
from django.contrib.auth.models import User

class Board(models.Model):
    CATEGORY_CHOICES = [
        ('공지사항', '공지사항'),
        ('문의하기', '문의하기'),
        ('요청하기', '요청하기'),
    ]

    title = models.CharField(max_length=100)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='문의하기')
    is_public = models.BooleanField(default=True)
    password = models.CharField(max_length=4, blank=True, null=True)
    attachment = models.FileField(upload_to='attachments/', blank=True, null=True)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

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