from django import forms
from .models import Product, FoodType, CountryList
import json


class ProductForm(forms.ModelForm):
    """제품 생성/수정 폼 (V1 표시사항 작성 페이지 기준)"""
    
    # 식품유형 선택 (FoodType 모델 참조)
    food_group_select = forms.ModelChoiceField(
        queryset=FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group'),
        required=False,
        widget=forms.Select(attrs={'class': 'gd-input gd-select'}),
        label='식품 대분류'
    )
    
    food_type_select = forms.ModelChoiceField(
        queryset=FoodType.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'gd-input gd-select'}),
        label='식품 소분류',
        to_field_name='food_type'
    )
    
    # 원산지 선택 (CountryList 모델 참조)
    country_select = forms.ModelChoiceField(
        queryset=CountryList.objects.all().order_by('country_name_ko'),
        required=False,
        widget=forms.Select(attrs={'class': 'gd-input gd-select'}),
        label='원산지 선택',
        to_field_name='country_code2'
    )
    
    class Meta:
        model = Product
        fields = [
            # V1 표시사항 작성 페이지 순서대로
            'my_label_name',
            'prdlst_nm',
            'ingredient_info',
            'prdlst_dcnm',
            'prdlst_report_no',
            'content_weight',
            'country_of_origin',
            'storage_method',
            'frmlc_mtrqlt',
            'bssh_nm',
            'pog_daycnt',
            'additional_info',
        ]
        widgets = {
            'my_label_name': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '라벨명을 입력하세요'
            }),
            'prdlst_nm': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '제품명을 입력하세요'
            }),
            'ingredient_info': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '제품명에 표시한 경우: 예) 레몬즙 5%'
            }),
            'prdlst_dcnm': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '식품유형을 입력하세요'
            }),
            'prdlst_report_no': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '품목보고번호를 입력하세요'
            }),
            'content_weight': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '내용량을 입력하세요 (예: 500g, 1L)'
            }),
            'country_of_origin': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '원산지를 입력하세요'
            }),
            'storage_method': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '보관방법을 입력하세요'
            }),
            'frmlc_mtrqlt': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '용기·포장재질을 입력하세요'
            }),
            'bssh_nm': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '제조원 소재지를 입력하세요'
            }),
            'pog_daycnt': forms.TextInput(attrs={
                'class': 'gd-input',
                'placeholder': '소비기한을 입력하세요'
            }),
            'additional_info': forms.Textarea(attrs={
                'class': 'gd-input',
                'placeholder': '기타 표시사항을 입력하세요'
            }),
        }
        labels = {
            'my_label_name': '라벨명',
            'prdlst_nm': '제품명',
            'ingredient_info': '특정성분 함량',
            'prdlst_dcnm': '식품유형',
            'prdlst_report_no': '품목보고번호',
            'content_weight': '내용량',
            'country_of_origin': '원산지',
            'storage_method': '보관방법',
            'frmlc_mtrqlt': '용기·포장재질',
            'bssh_nm': '제조원',
            'pog_daycnt': '소비기한',
            'additional_info': '기타 표시사항',
        }
    
    def __init__(self, *args, **kwargs):
        print("!!! v2/products/forms.py ProductForm이 실행되고 있습니다 !!!")
        super().__init__(*args, **kwargs)
        
        # 식품유형 초기값 설정
        if self.instance.pk:
            if self.instance.food_group:
                self.initial['food_group_select'] = self.instance.food_group
            if self.instance.food_type:
                try:
                    food_type_obj = FoodType.objects.get(food_type=self.instance.food_type)
                    self.initial['food_type_select'] = food_type_obj
                except FoodType.DoesNotExist:
                    pass
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # 식품유형 선택값 저장
        food_type_select = self.cleaned_data.get('food_type_select')
        if food_type_select:
            instance.food_type = food_type_select.food_type
            instance.food_group = food_type_select.food_group
        
        # 원산지 선택값 저장
        country_select = self.cleaned_data.get('country_select')
        if country_select:
            country_name = country_select.country_name_ko
            # "산" 붙이기
            if not country_name.endswith('산'):
                country_name += '산'
            instance.country_of_origin = country_name
        
        if commit:
            instance.save()
        return instance
