"""
"원료 표시사항" 문서 타입을 더한다.

원료 봉지 사진을 문서함에 붙이면 그 원료를 BOM 에 등록하는 기능이 이 타입을
표식으로 쓴다. 다른 타입(품목제조보고서·성적서 등)은 완제품 서류라, 같은 버튼을
아무 문서에나 달면 무엇을 읽어야 하는지가 흐려진다.

required_yn 은 False 다 — 원료가 없는 제품도 있고, 필수 문서로 잡으면 모든 제품의
문서 준수율이 떨어진다.
"""
from django.db import migrations

TYPE_CODE = 'INGREDIENT_LABEL'


def add_type(apps, schema_editor):
    DocumentType = apps.get_model('products', 'DocumentType')
    DocumentType.objects.update_or_create(
        type_code=TYPE_CODE,
        defaults={
            'type_name': '원료 표시사항',
            'description': '원료 포장의 표시사항 사진. 읽어서 BOM 에 원료로 등록할 수 있다.',
            'detection_keywords': '원료,원재료,부원료,원료표시사항,원료라벨',
            'requires_expiry': False,
            'default_validity_days': 0,
            'expiry_alert_days': 30,
            'required_yn': False,
            'display_order': 11,
            'icon': 'bi-box-seam',
            'active_yn': True,
        },
    )


def remove_type(apps, schema_editor):
    DocumentType = apps.get_model('products', 'DocumentType')
    # 이 타입으로 올린 문서가 있으면 지우지 않는다 - PROTECT 로 걸려 있고,
    # 지우면 사용자가 올린 파일이 갈 곳을 잃는다.
    qs = DocumentType.objects.filter(type_code=TYPE_CODE)
    if not qs.filter(documents__isnull=False).exists():
        qs.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_alter_documentrequest_requested_documents'),
    ]

    operations = [
        migrations.RunPython(add_type, remove_type),
    ]
