from django import forms
from .models import MyLabel, MyIngredient

class LabelCreationForm(forms.ModelForm):
    """표시사항 작성 폼"""
    # 체크박스 상태 필드들을 CharField에서 BooleanField로 변경
    chk_label_nm = forms.BooleanField(required=False, initial=False)
    chk_prdlst_dcnm = forms.BooleanField(required=False, initial=False)
    chk_prdlst_nm = forms.BooleanField(required=False, initial=True)  # 기본값 True
    chk_ingredients_info = forms.BooleanField(required=False, initial=False)
    chk_content_weight = forms.BooleanField(required=False, initial=True)  # 기본값 True
    chk_weight_calorie = forms.BooleanField(required=False, initial=False)
    chk_prdlst_report_no = forms.BooleanField(required=False, initial=False)
    chk_country_of_origin = forms.BooleanField(required=False, initial=False)
    chk_storage_method = forms.BooleanField(required=False, initial=False)
    chk_frmlc_mtrqlt = forms.BooleanField(required=False, initial=False)
    chk_manufacturer_info = forms.BooleanField(required=False, initial=True)  # 기본값 True
    chk_distributor_address = forms.BooleanField(required=False, initial=False)
    chk_repacker_address = forms.BooleanField(required=False, initial=False)
    chk_importer_address = forms.BooleanField(required=False, initial=False)
    chk_date_info = forms.BooleanField(required=False, initial=True)  # 기본값 True
    chk_rawmtrl_nm = forms.BooleanField(required=False, initial=False)
    chk_rawmtrl_nm_display = forms.BooleanField(required=False, initial=False)
    chk_cautions = forms.BooleanField(required=False, initial=False)
    chk_additional_info = forms.BooleanField(required=False, initial=False)
    chk_calories = forms.BooleanField(required=False, initial=False)

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
            # 체크박스 필드를 모델 필드와 일치하도록 수정
            'chk_label_nm',
            'chk_prdlst_dcnm',
            'chk_prdlst_nm',
            'chk_ingredients_info',
            'chk_content_weight',
            'chk_weight_calorie',
            'chk_prdlst_report_no',
            'chk_country_of_origin',
            'chk_storage_method',
            'chk_frmlc_mtrqlt',
            'chk_manufacturer_info',
            'chk_distributor_address',
            'chk_repacker_address',
            'chk_importer_address',
            'chk_date_info',
            'chk_rawmtrl_nm',
            'chk_rawmtrl_nm_display',
            'chk_cautions',
            'chk_additional_info',
            'chk_calories',
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
            'prms_dt', 'food_category', 'prdlst_dcnm', 'pog_daycnt',
            'frmlc_mtrqlt', 'rawmtrl_nm', 'allergens', 'gmo', 'ingredient_display_name'  # ingredient_display_name 필드 추가
        ]
        labels = {
            'prdlst_report_no': '품목제조번호',
            'prdlst_nm': '제품명',
            'bssh_nm': '제조사명',
            'prms_dt': '허가일자',
            'food_category': '식품 구분',
            'prdlst_dcnm': '식품유형',
            'pog_daycnt': '소비기한',
            'frmlc_mtrqlt': '포장재질',
            'rawmtrl_nm': '원재료명',
            'allergens': '알레르기',
            'gmo': 'GMO',
            'ingredient_display_name': '원재료 표시명'  # 레이블 추가
        }
        widgets = {
            'prdlst_report_no': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'prdlst_nm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'bssh_nm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'prms_dt': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'food_category': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'prdlst_dcnm': forms.TextInput(attrs={'readonly': True, 'class': 'form-control'}),
            'pog_daycnt': forms.TextInput(attrs={'class': 'form-control'}),
            'frmlc_mtrqlt': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'rawmtrl_nm': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'allergens': forms.Textarea(attrs={'class': 'form-control'}),
            'gmo': forms.TextInput(attrs={'class': 'form-control'}),
            'ingredient_display_name': forms.Textarea(attrs={'class': 'form-control'})  # 위젯 추가
        }
