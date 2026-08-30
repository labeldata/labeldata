"""
제품 조회 검색용 FULLTEXT(ngram) 인덱스를 생성한다.

마이그레이션이 아니라 관리 명령으로 둔 이유:
인덱스 생성이 테이블을 잠그기 때문이다. 로컬 18,857행 기준 3.5초인데 운영은
더 걸린다. migrate 안에 있으면 배포가 그만큼 멈추므로, 한가한 시간에 따로 돌릴
수 있도록 떼어 뒀다. 검색 코드가 인덱스 유무를 보고 없으면 LIKE 로 폴백하므로
아직 안 돌린 상태로도 동작한다.

(Django 모델의 Index 로는 ngram 파서를 지정할 수 없다는 점도 있다.)

    python manage.py ensure_search_indexes            # 생성 (있으면 건너뜀)
    python manage.py ensure_search_indexes --dry-run

중복 인덱스 정리는 여기 있었지만 label/0020 마이그레이션으로 옮겼다.
마이그레이션을 못 돌리던 시절의 임시 조치였다.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from v1.label.services.product_search import FULLTEXT_INDEXES, invalidate_index_cache


class Command(BaseCommand):
    help = '제품 조회 검색용 FULLTEXT(ngram) 인덱스 생성'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='실행할 SQL 만 출력하고 적용하지 않음')

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

        if changed:
            invalidate_index_cache()
            self.stdout.write(self.style.SUCCESS('완료: 검색 백엔드 캐시를 갱신했습니다.'))
        elif dry_run:
            self.stdout.write('dry-run 종료 (변경 없음)')
        else:
            self.stdout.write('변경 사항 없음')
