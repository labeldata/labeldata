from django import forms
from .models import Post, Comment, FoodType, Label, FrequentlyUsedText, MyProduct, MyIngredients, Allergen


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
    frequently_used_texts = forms.ModelChoiceField(
        queryset=FrequentlyUsedText.objects.all(),
        required=False,
        label="자주 사용하는 문구",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Label
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

    def save(self, commit=True):
        instance = super().save(commit=False)
        # 자주 사용하는 문구를 선택한 경우 해당 데이터를 storage_method에 추가
        frequently_used_text = self.cleaned_data.get('frequently_used_texts')
        if frequently_used_text:
            instance.storage_method = f"{instance.storage_method}\n{frequently_used_text.text}".strip()
        if commit:
            instance.save()
        return instance


class LabelCreationForm(forms.ModelForm):
    """표시사항 작성 폼"""
    allergens = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="알레르기 물질"
    )
    ingredients = forms.ModelMultipleChoiceField(
        queryset=MyIngredients.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="원재료명"  # 추가됨
    )

    class Meta:
        model = Label
        fields = [
            'prdlst_report_no', 'prdlst_nm', 'prdlst_dcnm', 'bssh_nm',
            'rawmtrl_nm', 'content_weight', 'manufacturer_address',
            'storage_method', 'distributor_name', 'distributor_address',
            'warnings', 'additional_info', 'origin', 'importer_address', 
            'allergens', 'ingredients'  # 추가됨
        ]
        labels = {
            "prdlst_report_no": "품목제조번호",
            "prdlst_nm": "제품명",
            "prdlst_dcnm": "식품유형",
            "bssh_nm": "제조사명",
            "rawmtrl_nm": "원재료명",
            "content_weight": "내용량 (열량)",
            "manufacturer_address": "제조원 소재지",
            "storage_method": "보관방법",
            "distributor_name": "유통전문판매원",
            "distributor_address": "유통전문판매원 소재지",
            "warnings": "주의사항",
            "additional_info": "기타 표시사항",
            "origin": "원산지",
            "importer_address": "수입원 및 소재지",
            "allergens": "알레르기 물질",
            "ingredients": "원재료명"
        }
        

class MyIngredientsForm(forms.ModelForm):
    """내원료 저장 폼"""
    class Meta:
        model = MyIngredients
        fields = [
            'prdlst_report_no', 'prdlst_nm', 'bssh_nm',
            'prms_dt', 'prdlst_dcnm', 'pog_daycnt',
            'frmlc_mtrqlt', 'rawmtrl_nm'
        ]
        labels = {
            'prdlst_report_no': '품목제조번호',
            'prdlst_nm': '제품명',
            'bssh_nm': '제조사명',
            'prms_dt': '허가일자',
            'prdlst_dcnm': '식품유형',
            'pog_daycnt': '소비기한',
            'frmlc_mtrqlt': '포장재질',
            'rawmtrl_nm': '원재료명',
        }
        widgets = {
            'prdlst_report_no': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'prdlst_nm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'bssh_nm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'prms_dt': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'prdlst_dcnm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'pog_daycnt': forms.TextInput(attrs={'class': 'form-control'}),
            'frmlc_mtrqlt': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'rawmtrl_nm': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
