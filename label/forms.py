from django import forms
from .models import Post, Comment, FoodType, Label


class PostForm(forms.ModelForm):
    """게시글 등록/수정 폼"""
    food_type = forms.ModelChoiceField(
        queryset=FoodType.objects.all(),
        empty_label="--- 선택하세요 ---",
        required=True,
        label="식품유형",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Post
        fields = ['title', 'food_type', 'manufacturer', 'ingredients', 'storage_conditions', 'precautions']
        labels = {
            'title': '제품명',
            'manufacturer': '제조사',
            'ingredients': '원재료명',
            'storage_conditions': '보관조건',
            'precautions': '기타 주의사항',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'ingredients': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'storage_conditions': forms.TextInput(attrs={'class': 'form-control'}),
            'precautions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class CommentForm(forms.ModelForm):
    """댓글 작성 폼"""
    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': '댓글 내용',
        }
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '댓글을 입력하세요.'
            }),
        }


class LabelForm(forms.ModelForm):
    """라벨 등록/수정 폼"""
    class Meta:
        model = Label
        exclude = ['food_item']  # food_item은 폼에서 제외
        fields = ['content_weight', 'manufacturer_address', 'storage_method']
        labels = {
            'content_weight': '내용량 (열량)',
            'manufacturer_address': '제조원 소재지',
            'storage_method': '보관방법',
        }
        widgets = {
            'content_weight': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer_address': forms.TextInput(attrs={'class': 'form-control'}),
            'storage_method': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
