from django import forms
from .models import MyLabel, MyIngredient

class LabelCreationForm(forms.ModelForm):
    """표시사항 작성 폼"""
    class Meta:
        model = MyLabel
        fields = [
            'my_label_name',
            'food_group',
            'food_type',
            'prdlst_dcnm',
            'prdlst_nm',
            'preservation_type',
            'processing_method',
            'processing_condition',
            'ingredient_info',
            'content_weight',
            'weight_calorie',
            'prdlst_report_no',
            'country_of_origin',
            'storage_method',
            'frmlc_mtrqlt',
            'bssh_nm',
            'distributor_address',
            'repacker_address',
            'importer_address',
            'pog_daycnt',
            'rawmtrl_nm',
            'rawmtrl_nm_display',
            'cautions',
            'additional_info',
            'nutrition_text',
            'calories', 'calories_unit',
            'natriums', 'natriums_unit',
            'carbohydrates', 'carbohydrates_unit',
            'sugars', 'sugars_unit',
            'fats', 'fats_unit',
            'trans_fats', 'trans_fats_unit',
            'saturated_fats', 'saturated_fats_unit',
            'cholesterols', 'cholesterols_unit',
            'proteins', 'proteins_unit',
            'serving_size', 'serving_size_unit',
            'units_per_package', 'nutrition_display_unit',
        ]
        widgets = {
            'rawmtrl_nm': forms.Textarea(attrs={'rows': 2, 'class': 'auto-expand form-control'}),
            'cautions': forms.Textarea(attrs={'rows': 2, 'class': 'auto-expand form-control'}),
            'additional_info': forms.Textarea(attrs={'rows': 2, 'class': 'auto-expand form-control'}),
        }


class MyIngredientsForm(forms.ModelForm):
    """내 원료 저장 폼"""
    class Meta:
        model = MyIngredient
        fields = [
            'prdlst_report_no', 'prdlst_nm', 'bssh_nm',
            'prms_dt', 'prdlst_dcnm', 'pog_daycnt',
            'frmlc_mtrqlt', 'rawmtrl_nm', 'allergens', 'gmo'  # 필드 추가
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
            'allergens': '알레르기',  # 레이블 추가
            'gmo': 'GMO'  # 레이블 추가
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
            'allergens': forms.Textarea(attrs={'class': 'form-control'}),  # 위젯 추가
            'gmo': forms.TextInput(attrs={'class': 'form-control'})  # 위젯 추가
        }
