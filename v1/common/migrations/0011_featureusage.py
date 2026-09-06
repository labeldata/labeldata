"""
사용량 표를 기능 하나짜리에서 여럿으로 넓힌다.

행을 옮기지 않고 **이름만 바꾼다.** 새 표를 만들고 복사한 뒤 옛 표를 지우면
중간에 무엇 하나 어긋났을 때 되돌릴 자리가 없다. 여기서는 ALTER TABLE
RENAME 이라 담긴 값이 그대로 따라온다 — 옛 행은 전부 AI 검증이므로
`feature` 의 기본값이 곧 맞는 값이다.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('common', '0010_ocrtruthcase_ocr_engine_ocrtruthcase_ocr_fetched_at_and_more'),
    ]

    operations = [
        # 이름부터 바꾼다. 제약·인덱스를 먼저 손대면 옛 이름을 가리키게 된다.
        migrations.RenameModel(
            old_name='AiValidationUsage',
            new_name='FeatureUsage',
        ),
        migrations.RemoveConstraint(
            model_name='featureusage',
            name='uniq_ai_usage_user_date',
        ),
        migrations.RemoveIndex(
            model_name='featureusage',
            name='idx_ai_usage_date',
        ),
        migrations.AddField(
            model_name='featureusage',
            name='feature',
            field=models.CharField(default='ai_validation', max_length=32,
                                   verbose_name='기능'),
        ),
        migrations.AlterField(
            model_name='featureusage',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='feature_usage',
                to=settings.AUTH_USER_MODEL,
                verbose_name='사용자'),
        ),
        migrations.AlterModelTable(
            name='featureusage',
            table='feature_usage',
        ),
        migrations.AlterModelOptions(
            name='featureusage',
            options={'verbose_name': '기능 사용량',
                     'verbose_name_plural': '기능 사용량'},
        ),
        migrations.AddConstraint(
            model_name='featureusage',
            constraint=models.UniqueConstraint(
                fields=('user', 'feature', 'used_date'),
                name='uniq_feature_usage'),
        ),
        migrations.AddIndex(
            model_name='featureusage',
            index=models.Index(fields=['used_date'],
                               name='idx_feature_usage_date'),
        ),
    ]
