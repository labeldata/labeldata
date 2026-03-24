"""
서버 DB 보정 migration
- 0002_combined 을 --fake 로 표시한 후 실제 누락된 DB 변경을 적용
- 모든 작업은 존재 여부를 확인 후 safe하게 실행
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# ── 헬퍼: 컬럼 존재 시에만 RENAME ──────────────────────────────────────────
def rename_col_if_needed(table, old_col, new_col):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
                [table, old_col],
            )
            if cursor.fetchone()[0]:
                cursor.execute(f'ALTER TABLE `{table}` RENAME COLUMN `{old_col}` TO `{new_col}`')
    return _runner


# ── 헬퍼: 컬럼 없을 때만 ADD COLUMN ───────────────────────────────────────
def add_col_if_missing(table, col, col_ddl):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
                [table, col],
            )
            if not cursor.fetchone()[0]:
                cursor.execute(f'ALTER TABLE `{table}` ADD COLUMN {col_ddl}')
    return _runner


# ── 헬퍼: 테이블 없을 때만 CREATE TABLE ───────────────────────────────────
def create_table_if_missing(table, create_ddl):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                [table],
            )
            if not cursor.fetchone()[0]:
                cursor.execute(create_ddl)
    return _runner


# ── 헬퍼: 테이블 있을 때만 DROP TABLE ─────────────────────────────────────
def drop_table_if_exists(table):
    def _runner(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS `{table}`')
    return _runner


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_combined'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],   # 상태는 0002_combined fake로 이미 최신
            database_operations=[

                # ── 0006: is_* → *_yn 컬럼명 변경 ──────────────────────────
                migrations.RunPython(rename_col_if_needed('v2_document_type',         'is_active',              'active_yn'),              migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_document_type',         'is_required',            'required_yn'),            migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_document_slot',         'is_hidden',              'hidden_yn'),              migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_document',      'is_active',              'active_yn'),              migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_comment',       'is_resolved',            'resolved_yn'),            migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_share',         'is_active',              'active_yn'),              migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_shared_product_receipt','is_accepted',            'accepted_yn'),            migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_shared_product_receipt','is_used_as_ingredient',  'used_as_ingredient_yn'),  migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_notification',  'is_read',                'read_yn'),                migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_metadata',      'is_starred',             'starred_yn'),             migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_metadata',      'is_deleted',             'deleted_yn'),             migrations.RunPython.noop),
                migrations.RunPython(rename_col_if_needed('v2_product_folder',        'is_system',              'system_yn'),              migrations.RunPython.noop),
                # DocumentSubmission: 테이블 자체가 새로 생성된 경우 active_yn으로 만들어져 있으므로 기존 테이블에만 rename
                migrations.RunPython(rename_col_if_needed('v2_document_request_submission', 'is_active',        'active_yn'),              migrations.RunPython.noop),
                # ProductMetadata: is_raw_material이 있다면 raw_material_yn으로
                migrations.RunPython(rename_col_if_needed('v2_product_metadata',      'is_raw_material',        'raw_material_yn'),        migrations.RunPython.noop),

                # ── 0004: 신규 컬럼 추가 (없을 때만) ────────────────────────
                migrations.RunPython(add_col_if_missing('v2_product_metadata', 'raw_material_yn', '`raw_material_yn` tinyint(1) NOT NULL DEFAULT 0'), migrations.RunPython.noop),
                migrations.RunPython(add_col_if_missing('v2_product_metadata', 'search_tags',     '`search_tags` varchar(500) NOT NULL DEFAULT ""'),   migrations.RunPython.noop),

                # ── 0008: ProductDocument.source_company_document_id ────────
                migrations.RunPython(add_col_if_missing('v2_product_document', 'source_company_document_id', '`source_company_document_id` int NULL'), migrations.RunPython.noop),

                # ── 0009: DocumentRequest 연결 필드 ─────────────────────────
                migrations.RunPython(add_col_if_missing('v2_document_request', 'linked_label_id',      '`linked_label_id` int NULL'),  migrations.RunPython.noop),
                migrations.RunPython(add_col_if_missing('v2_document_request', 'linked_ingredient_id', '`linked_ingredient_id` int NULL'), migrations.RunPython.noop),

                # ── 0011: ProductShare.recipient_license_no ─────────────────
                migrations.RunPython(add_col_if_missing('v2_product_share', 'recipient_license_no', '`recipient_license_no` varchar(100) NULL'), migrations.RunPython.noop),

                # ── 0002/0003: 테이블 생성 (없을 때만) ──────────────────────
                migrations.RunPython(create_table_if_missing('v2_document_request', """
                    CREATE TABLE `v2_document_request` (
                        `request_id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        `recipient_email` varchar(254) NOT NULL,
                        `recipient_name` varchar(100) NOT NULL DEFAULT '',
                        `recipient_company` varchar(200) NULL,
                        `target_product_name` varchar(200) NOT NULL DEFAULT '',
                        `requested_documents` json NOT NULL,
                        `message` longtext NOT NULL,
                        `status` varchar(20) NOT NULL DEFAULT 'PENDING',
                        `due_date` date NULL,
                        `upload_token` varchar(32) NOT NULL UNIQUE,
                        `email_sent` tinyint(1) NOT NULL DEFAULT 0,
                        `email_sent_datetime` datetime(6) NULL,
                        `attachment` varchar(100) NULL,
                        `created_datetime` datetime(6) NOT NULL,
                        `updated_datetime` datetime(6) NOT NULL,
                        `requester_id` int NOT NULL,
                        INDEX `v2_document_request_22c713_idx` (`requester_id`, `status`),
                        INDEX `v2_document_recipie_b3d91b_idx` (`recipient_email`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """), migrations.RunPython.noop),

                migrations.RunPython(create_table_if_missing('v2_document_request_submission', """
                    CREATE TABLE `v2_document_request_submission` (
                        `submission_id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        `document_type` varchar(100) NOT NULL,
                        `file` varchar(100) NOT NULL,
                        `original_filename` varchar(255) NOT NULL,
                        `file_size` bigint NOT NULL DEFAULT 0,
                        `submitted_by_email` varchar(255) NULL,
                        `submitted_by_name` varchar(100) NULL,
                        `notes` longtext NULL,
                        `active_yn` tinyint(1) NOT NULL DEFAULT 1,
                        `submitted_datetime` datetime(6) NOT NULL,
                        `request_id` int NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """), migrations.RunPython.noop),

                # ── 0012: user_contact 테이블 생성 (없을 때만) ───────────────
                migrations.RunPython(create_table_if_missing('user_contact', """
                    CREATE TABLE `user_contact` (
                        `id` bigint NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        `email` varchar(255) NOT NULL,
                        `name` varchar(100) NULL,
                        `company` varchar(200) NULL,
                        `license_no` varchar(100) NULL,
                        `created_at` datetime(6) NOT NULL,
                        `updated_at` datetime(6) NOT NULL,
                        `owner_id` int NOT NULL,
                        UNIQUE KEY `user_contact_owner_id_email_uniq` (`owner_id`, `email`),
                        KEY `user_contact_email_idx` (`email`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """), migrations.RunPython.noop),

                # ── 0005/0010: 불필요 테이블 삭제 ───────────────────────────
                migrations.RunPython(drop_table_if_exists('v2_share_access_log'),  migrations.RunPython.noop),
                migrations.RunPython(drop_table_if_exists('v2_comment_mention'),   migrations.RunPython.noop),
                migrations.RunPython(drop_table_if_exists('v2_suggestion_mode'),   migrations.RunPython.noop),
            ],
        ),
    ]
