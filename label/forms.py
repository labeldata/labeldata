from django import forms
from .models import Post, Comment, FoodType

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'food_type', 'manufacturer', 'ingredients', 'storage_conditions', 'precautions']
        labels = {
            'title': '제품명',
            'food_type': '식품유형',
            'manufacturer': '제조사',
            'ingredients': '원재료명',
            'storage_conditions': '보관조건',
            'precautions': '기타 주의사항',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['food_type'] = forms.ChoiceField(
            choices=[(ft.name, ft.name) for ft in FoodType.objects.all()],
            required=True
        )

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': '댓글 내용',
        }
