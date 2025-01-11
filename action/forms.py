from django import forms
from .models import AdministrativeAction

class ActionForm(forms.ModelForm):
    class Meta:
        model = AdministrativeAction
        fields = ['name', 'registration_number', 'action_name', 'action_date', 'details']
        labels = {
            'name': '업체명',
            'registration_number': '인허가번호',
            'action_name': '행정처분명',
            'action_date': '행정처분일',
            'details': '기타 내용',
        }
