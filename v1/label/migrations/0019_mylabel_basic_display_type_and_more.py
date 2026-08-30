# 서버 전용 no-op stub — git으로 관리되지 않음(.gitignore 대상)
# label 앱 마이그레이션 0002~0020 실제 파일이 서버에서 유실된 상태라,
# regulatory 0002가 참조하는 이 노드만 채워서 마이그레이션 그래프를 복구한다.
# operations가 비어있어 실행돼도 DB에는 아무 영향이 없다.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('label', '0001_initial'),
    ]

    operations = []
