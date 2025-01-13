from django import forms
from .models import AdministrativeAction

class ActionForm(forms.ModelForm):
    class Meta:
        model = AdministrativeAction
        fields = ['company_name', 'registration_number', 'action_name', 'action_date', 'details']
        labels = {
            'company_name': '업체명',
            'registration_number': '인허가번호',
            'action_name': '행정처분명',
            'action_date': '행정처분일',
            'details': '기타 내용',
        }
        widgets = {
            'action_date': forms.DateInput(attrs={'type': 'date'}),
            'details': forms.Textarea(attrs={'rows': 4}),
        }
