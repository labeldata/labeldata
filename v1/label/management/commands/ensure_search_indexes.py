"""
제품 조회 검색용 FULLTEXT(ngram) 인덱스를 생성한다.

마이그레이션이 아니라 관리 명령으로 둔 이유:
이 저장소는 마이그레이션 이력이 정리되기 전이라 `migrate` 를 실행할 수 없다.
검색 코드는 인덱스 유무를 감지해 없으면 LIKE 로 폴백하므로,
배포 순서와 무관하게 아무 때나 한 번 실행하면 된다.

    python manage.py ensure_search_indexes            # 생성 (있으면 건너뜀)
    python manage.py ensure_search_indexes --drop-duplicates   # 중복 인덱스도 정리
    python manage.py ensure_search_indexes --dry-run

주의: 인덱스 생성은 테이블을 잠근다. 로컬 18,857행 기준 3.5초.
운영 데이터 규모에 따라 더 걸릴 수 있으니 한가한 시간에 실행할 것.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from v1.label.services.product_search import FULLTEXT_INDEXES, invalidate_index_cache

# 같은 컬럼에 인덱스가 두 벌씩 걸려 있어 쓰기 비용과 메모리만 낭비한다.
# (food_item 은 인덱스 16MB > 데이터 9.5MB)
# 각 항목: (테이블, 지울 인덱스, 남는 인덱스 — 확인용)
DUPLICATE_INDEXES = [
    ('food_item', 'idx_lcns_no', 'food_item_lcns_no_1e94cc47'),
    ('food_item', 'idx_prdlst_nm', 'food_item_prdlst_nm_2b626e08'),
    ('food_item', 'idx_prdlst_report_no', 'PRIMARY'),
    ('imported_food', 'idx_bsn_ofc_name', 'imported_food_bsn_ofc_name_4f34dd05'),
    ('imported_food', 'idx_itm_nm', 'imported_food_itm_nm_76398b54'),
]


class Command(BaseCommand):
    help = '제품 조회 검색용 FULLTEXT(ngram) 인덱스 생성 및 중복 인덱스 정리'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='실행할 SQL 만 출력하고 적용하지 않음')
        parser.add_argument('--drop-duplicates', action='store_true',
                            help='같은 컬럼에 중복으로 걸린 인덱스를 제거')

    # ── 조회 헬퍼 ────────────────────────────────────────────────────────────
    def _index_exists(self, cur, table, index_name):
        cur.execute(
            """SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s""",
            [table, index_name],
        )
        return cur.fetchone()[0] > 0

    def _index_columns(self, cur, table, index_name):
        """인덱스에 걸린 컬럼을 순서대로 반환"""
        cur.execute(
            """SELECT column_name FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s
                ORDER BY seq_in_index""",
            [table, index_name],
        )
        return tuple(row[0] for row in cur.fetchall())

    def _table_exists(self, cur, table):
        cur.execute(
            """SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = %s""",
            [table],
        )
        return cur.fetchone()[0] > 0

    # ── 실행 ─────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        changed = False

        with connection.cursor() as cur:
            if connection.vendor != 'mysql':
                self.stderr.write(self.style.ERROR(
                    f'MySQL 전용 명령입니다 (현재: {connection.vendor})'))
                return

            for table, spec in FULLTEXT_INDEXES.items():
                if not self._table_exists(cur, table):
                    self.stdout.write(self.style.WARNING(f'  건너뜀: {table} 테이블 없음'))
                    continue
                if self._index_exists(cur, table, spec['name']):
                    current = self._index_columns(cur, table, spec['name'])
                    if current == tuple(spec['columns']):
                        self.stdout.write(f"  이미 있음: {table}.{spec['name']}")
                        continue
                    # 정의가 바뀌었으면 다시 만든다 (컬럼을 추가·제거한 경우)
                    self.stdout.write(self.style.WARNING(
                        f"  컬럼 변경 감지: {table}.{spec['name']} {current} -> {tuple(spec['columns'])}"))
                    drop_sql = f"ALTER TABLE {table} DROP INDEX {spec['name']}"
                    if dry_run:
                        self.stdout.write(f'  [dry-run] {drop_sql}')
                    else:
                        cur.execute(drop_sql)
                        changed = True

                sql = (f"ALTER TABLE {table} ADD FULLTEXT INDEX {spec['name']} "
                       f"({', '.join(spec['columns'])}) WITH PARSER ngram")
                if dry_run:
                    self.stdout.write(f'  [dry-run] {sql}')
                    continue
                self.stdout.write(f"  생성 중: {table}.{spec['name']} ...")
                cur.execute(sql)
                changed = True
                self.stdout.write(self.style.SUCCESS(f"  생성 완료: {table}.{spec['name']}"))

            if options['drop_duplicates']:
                self.stdout.write('중복 인덱스 정리:')
                for table, dup, kept in DUPLICATE_INDEXES:
                    if not self._table_exists(cur, table):
                        continue
                    if not self._index_exists(cur, table, dup):
                        self.stdout.write(f'  이미 없음: {table}.{dup}')
                        continue
                    if not self._index_exists(cur, table, kept):
                        # 남겨둘 인덱스가 없으면 지우지 않는다 (커버리지 상실 방지)
                        self.stdout.write(self.style.WARNING(
                            f'  건너뜀: {table}.{dup} (대체 인덱스 {kept} 없음)'))
                        continue
                    sql = f'ALTER TABLE {table} DROP INDEX {dup}'
                    if dry_run:
                        self.stdout.write(f'  [dry-run] {sql}   (동일 컬럼 {kept} 유지)')
                        continue
                    cur.execute(sql)
                    changed = True
                    self.stdout.write(self.style.SUCCESS(
                        f'  제거: {table}.{dup}   (동일 컬럼 {kept} 유지)'))

        if changed:
            invalidate_index_cache()
            self.stdout.write(self.style.SUCCESS('완료: 검색 백엔드 캐시를 갱신했습니다.'))
        elif dry_run:
            self.stdout.write('dry-run 종료 (변경 없음)')
        else:
            self.stdout.write('변경 사항 없음')
