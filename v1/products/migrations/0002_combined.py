"""
0002~0012 통합 migration
- 서버에는 0001_initial 만 적용된 상태에서 이 파일 하나로 나머지 변경사항을 모두 적용
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# ── 0007: 인덱스 safe rename 헬퍼 ───────────────────────────────────────────
def drop_index_if_exists(table, index_name):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() "
                "AND table_name = %s AND index_name = %s",
                [table, index_name],
            )
            if cursor.fetchone()[0]:
                cursor.execute(f'ALTER TABLE `{table}` DROP INDEX `{index_name}`')
    return _runner


def create_index_if_not_exists(table, index_name, columns_sql):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() "
                "AND table_name = %s AND index_name = %s",
                [table, index_name],
            )
            if not cursor.fetchone()[0]:
                cursor.execute(f'CREATE INDEX `{index_name}` ON `{table}` ({columns_sql})')
    return _runner


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('label', '__first__'),
        ('user_management', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 0002: DocumentRequest 생성 ──────────────────────────────────────
        migrations.CreateModel(
            name='DocumentRequest',
            fields=[
                ('request_id', models.AutoField(primary_key=True, serialize=False, verbose_name='요청 ID')),
                ('recipient_email', models.EmailField(max_length=254, verbose_name='수신자 이메일')),
                ('recipient_name', models.CharField(blank=True, max_length=100, verbose_name='수신자 이름')),
                ('recipient_company', models.CharField(blank=True, max_length=200, null=True, verbose_name='수신자 회사')),
                ('target_product_name', models.CharField(blank=True, default='', max_length=200, verbose_name='대상 제품명')),
                ('requested_documents', models.JSONField(default=list, verbose_name='요청 문서 목록')),
                ('message', models.TextField(blank=True, verbose_name='요청 메시지')),
                ('status', models.CharField(choices=[('PENDING', '요청 중'), ('ACCEPTED', '수락'), ('REJECTED', '거절'), ('CANCELLED', '취소')], db_index=True, default='PENDING', max_length=20, verbose_name='상태')),
                ('due_date', models.DateField(blank=True, null=True, verbose_name='제출 기한')),
                ('upload_token', models.CharField(max_length=32, unique=True, verbose_name='업로드 토큰')),
                ('email_sent', models.BooleanField(default=False, verbose_name='이메일 발송 여부')),
                ('email_sent_datetime', models.DateTimeField(blank=True, null=True, verbose_name='이메일 발송 일시')),
                ('attachment', models.FileField(blank=True, null=True, upload_to='doc_requests/%Y/%m/', verbose_name='첨부 파일')),
                ('created_datetime', models.DateTimeField(auto_now_add=True, verbose_name='요청일시')),
                ('updated_datetime', models.DateTimeField(auto_now=True, verbose_name='최종수정일시')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_doc_requests', to=settings.AUTH_USER_MODEL, verbose_name='요청자')),
            ],
            options={
                'verbose_name': '문서 요청',
                'verbose_name_plural': '문서 요청 목록',
                'db_table': 'v2_document_request',
                'ordering': ['-created_datetime'],
                'indexes': [
                    models.Index(fields=['requester', 'status'], name='v2_document_request_22c713_idx'),
                    models.Index(fields=['recipient_email'], name='v2_document_recipie_b3d91b_idx'),
                ],
            },
        ),

        # ── 0003: DocumentSubmission 생성 (active_yn 으로 직접 생성) ─────────
        migrations.CreateModel(
            name='DocumentSubmission',
            fields=[
                ('submission_id', models.AutoField(primary_key=True, serialize=False)),
                ('document_type', models.CharField(max_length=100, verbose_name='문서 종류')),
                ('file', models.FileField(upload_to='doc_submissions/%Y/%m/', verbose_name='파일')),
                ('original_filename', models.CharField(max_length=255, verbose_name='원본 파일명')),
                ('file_size', models.BigIntegerField(default=0, verbose_name='파일 크기')),
                ('submitted_by_email', models.CharField(blank=True, max_length=255, null=True, verbose_name='제출자 이메일')),
                ('submitted_by_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='제출자 이름')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='메모')),
                ('active_yn', models.BooleanField(default=True)),
                ('submitted_datetime', models.DateTimeField(auto_now_add=True, verbose_name='제출일시')),
                ('request', models.ForeignKey(db_column='request_id', on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='products.documentrequest')),
            ],
            options={
                'verbose_name': '문서 제출',
                'verbose_name_plural': '문서 제출 목록',
                'db_table': 'v2_document_request_submission',
                'ordering': ['-submitted_datetime'],
            },
        ),

        # ── 0004: ProductMetadata 필드 추가 (raw_material_yn 으로 직접 추가) ─
        migrations.AddField(
            model_name='productmetadata',
            name='raw_material_yn',
            field=models.BooleanField(default=False, help_text='체크 시 원료 관리에 자동 등록됩니다', verbose_name='원료로 사용'),
        ),
        migrations.AddField(
            model_name='productmetadata',
            name='search_tags',
            field=models.CharField(blank=True, default='', help_text='#태그1 #태그2 또는 쉼표로 구분', max_length=500, verbose_name='검색 태그'),
        ),

        # ── 0005: ShareAccessLog 삭제 ────────────────────────────────────────
        migrations.DeleteModel(
            name='ShareAccessLog',
        ),

        # ── 0006: 기존 테이블 필드명 변경 (is_* → *_yn) ──────────────────────
        migrations.RenameField(model_name='productmetadata',      old_name='is_starred',              new_name='starred_yn'),
        migrations.RenameField(model_name='productmetadata',      old_name='is_deleted',              new_name='deleted_yn'),
        migrations.RenameField(model_name='productfolder',        old_name='is_system',               new_name='system_yn'),
        migrations.RenameField(model_name='documenttype',         old_name='is_required',             new_name='required_yn'),
        migrations.RenameField(model_name='documenttype',         old_name='is_active',               new_name='active_yn'),
        migrations.RenameField(model_name='documentslot',         old_name='is_hidden',               new_name='hidden_yn'),
        migrations.RenameField(model_name='productdocument',      old_name='is_active',               new_name='active_yn'),
        migrations.RenameField(model_name='productcomment',       old_name='is_resolved',             new_name='resolved_yn'),
        migrations.RenameField(model_name='productshare',         old_name='is_active',               new_name='active_yn'),
        migrations.RenameField(model_name='sharedproductreceipt', old_name='is_accepted',             new_name='accepted_yn'),
        migrations.RenameField(model_name='sharedproductreceipt', old_name='is_used_as_ingredient',   new_name='used_as_ingredient_yn'),
        migrations.RenameField(model_name='productnotification',  old_name='is_read',                 new_name='read_yn'),

        # ── 0007: 인덱스명 변경 (safe – 존재 여부 확인 후 처리) ──────────────
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(create_index_if_not_exists('v2_product_comment',      'v2_product__resolve_76b00a_idx', '`resolved_yn`'),              migrations.RunPython.noop),
                migrations.RunPython(create_index_if_not_exists('v2_product_document',     'v2_product__active__5cd8bf_idx', '`active_yn`'),                 migrations.RunPython.noop),
                migrations.RunPython(create_index_if_not_exists('v2_product_metadata',     'v2_product__my_labe_5afc3d_idx', '`my_label_id`, `deleted_yn`'), migrations.RunPython.noop),
                migrations.RunPython(create_index_if_not_exists('v2_product_metadata',     'v2_product__starred_0ae996_idx', '`starred_yn`'),                migrations.RunPython.noop),
                migrations.RunPython(create_index_if_not_exists('v2_product_notification', 'v2_product__recipie_aed6c6_idx', '`recipient_id`, `read_yn`'),   migrations.RunPython.noop),
                migrations.RunPython(create_index_if_not_exists('v2_product_share',        'v2_product__active__38109d_idx', '`active_yn`'),                  migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_comment',      'v2_product__is_reso_d4cdc8_idx'), migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_document',     'v2_product__is_acti_4372ec_idx'), migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_metadata',     'v2_product__my_labe_7ee7d1_idx'), migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_metadata',     'v2_product__is_star_0dc9b1_idx'), migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_notification', 'v2_product__recipie_1760a7_idx'), migrations.RunPython.noop),
                migrations.RunPython(drop_index_if_exists('v2_product_share',        'v2_product__is_acti_59fda3_idx'), migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveIndex(model_name='productcomment',     name='v2_product__is_reso_d4cdc8_idx'),
                migrations.RemoveIndex(model_name='productdocument',    name='v2_product__is_acti_4372ec_idx'),
                migrations.RemoveIndex(model_name='productmetadata',    name='v2_product__my_labe_7ee7d1_idx'),
                migrations.RemoveIndex(model_name='productmetadata',    name='v2_product__is_star_0dc9b1_idx'),
                migrations.RemoveIndex(model_name='productnotification', name='v2_product__recipie_1760a7_idx'),
                migrations.RemoveIndex(model_name='productshare',       name='v2_product__is_acti_59fda3_idx'),
                migrations.AddIndex(model_name='productcomment',      index=models.Index(fields=['resolved_yn'],         name='v2_product__resolve_76b00a_idx')),
                migrations.AddIndex(model_name='productdocument',     index=models.Index(fields=['active_yn'],            name='v2_product__active__5cd8bf_idx')),
                migrations.AddIndex(model_name='productmetadata',     index=models.Index(fields=['label', 'deleted_yn'],  name='v2_product__my_labe_5afc3d_idx')),
                migrations.AddIndex(model_name='productmetadata',     index=models.Index(fields=['starred_yn'],           name='v2_product__starred_0ae996_idx')),
                migrations.AddIndex(model_name='productnotification', index=models.Index(fields=['recipient', 'read_yn'], name='v2_product__recipie_aed6c6_idx')),
                migrations.AddIndex(model_name='productshare',        index=models.Index(fields=['active_yn'],            name='v2_product__active__38109d_idx')),
            ],
        ),

        # ── 0008: ProductDocument ← CompanyDocument FK 추가 ─────────────────
        migrations.AddField(
            model_name='productdocument',
            name='source_company_document',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='고정 서류 관리에서 불러온 경우 원본 서류를 참조합니다',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='linked_product_documents',
                to='user_management.companydocument',
                verbose_name='출처 고정 서류',
            ),
        ),

        # ── 0009: DocumentRequest 연결 필드 추가 ────────────────────────────
        migrations.AddField(
            model_name='documentrequest',
            name='linked_label',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='자료 요청과 연결된 제품(표시사항)',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='doc_requests',
                to='label.mylabel',
                verbose_name='연결된 제품',
            ),
        ),
        migrations.AddField(
            model_name='documentrequest',
            name='linked_ingredient',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='자료 요청과 연결된 원료',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='doc_requests',
                to='label.myingredient',
                verbose_name='연결된 원료',
            ),
        ),

        # ── 0010: CommentMention, SuggestionMode 삭제 ───────────────────────
        migrations.DeleteModel(name='CommentMention'),
        migrations.DeleteModel(name='SuggestionMode'),

        # ── 0011: ProductShare 인허가번호 필드 추가 ──────────────────────────
        migrations.AddField(
            model_name='productshare',
            name='recipient_license_no',
            field=models.CharField(blank=True, help_text='영업허가번호 또는 품목제조보고번호', max_length=100, null=True, verbose_name='수신자 인허가번호'),
        ),

        # ── 0012: UserContact 생성 ───────────────────────────────────────────
        migrations.CreateModel(
            name='UserContact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=255, verbose_name='이메일')),
                ('name', models.CharField(blank=True, max_length=100, null=True, verbose_name='이름')),
                ('company', models.CharField(blank=True, max_length=200, null=True, verbose_name='회사명')),
                ('license_no', models.CharField(blank=True, max_length=100, null=True, verbose_name='인허가번호')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_contacts', to=settings.AUTH_USER_MODEL, verbose_name='소유자')),
            ],
            options={
                'verbose_name': '연락처',
                'verbose_name_plural': '연락처 목록',
                'db_table': 'user_contact',
                'unique_together': {('owner', 'email')},
            },
        ),
    ]
