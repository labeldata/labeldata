from django import forms
from .models import AdministrativeDisposition

class DispositionForm(forms.ModelForm):
    class Meta:
        model = AdministrativeDisposition
        fields = [
            'disposition_date',
            'business_type',
            'business_name',
            'road_address',
            'lotno_addr',
            'disposition_details',
            'administrative_id',
            'licence_no',
            'representative_name',
            'disposition_period',
            'notice_details',
            'violation_details',
            'processing_department',
            'manager_name',
            'contact_number',
            'email',
            'location'
        ]
        labels = {
            'disposition_date': '처분 확정일자',
            'business_type': '업종명',
            'business_name': '업소명',
            'road_address': '도로명주소',
            'lotno_addr': '지번주소',
            'disposition_details': '처분사항',
            'administrative_id': '행정처분번호',
            'licence_no': '인허가번호',
            'representative_name': '대표자명',
            'disposition_period': '처분기간',
            'notice_details': '안내사항',
            'violation_details': '위반내용',
            'processing_department': '처리부서',
            'manager_name': '담당자명',
            'contact_number': '전화번호',
            'email': '이메일',
            'location': '지역'
        }