"""
협력업체가 남의 서류를 전부 내려받을 수 있던 것을 막는다.

권한은 제품 단위였고 다섯 역할이 전부 `can_download_documents=True` 였다.
내려받기 검사는 문서를 아예 보지 않았다. 그래서 시험성적서 하나 내라고 부른
협력업체가 그 제품 문서함의 **모든 것**을 받을 수 있었다.

새 칸의 기본값은 True 다 — 내부 팀(편집·검토·승인)과 뷰어는 지금까지처럼
전부 본다. **이미 맺어 둔 자료 제출(UPLOADER) 공유만 꺼 준다.** 그쪽이
바깥 사람이고, 이 구멍이 열려 있던 자리다.

되돌릴 때는 다시 켠다. 칸이 사라지므로 어차피 전부 보이던 상태로 돌아간다.
"""
from django.db import migrations, models


def close_uploader_shares(apps, schema_editor):
    SharePermission = apps.get_model('products', 'SharePermission')
    SharePermission.objects.filter(role_code='UPLOADER').update(
        can_view_all_documents=False)


def open_uploader_shares(apps, schema_editor):
    SharePermission = apps.get_model('products', 'SharePermission')
    SharePermission.objects.filter(role_code='UPLOADER').update(
        can_view_all_documents=True)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_alter_productactivitylog_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharepermission',
            name='can_view_all_documents',
            field=models.BooleanField(default=True, help_text='끄면 본인이 올린 문서만 보이고 받을 수 있다. 자료 제출(협력업체)의 기본값이 꺼짐이다', verbose_name='문서함 전체 보기'),
        ),
        migrations.RunPython(close_uploader_shares, open_uploader_shares),
    ]
