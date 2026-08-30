"""
마이그레이션 상태 점검 — 읽기 전용.

`manage.py migrate` 가 InconsistentMigrationHistory 로 죽어서 신규 배포도 DB
재구축도 못 하는 상태다. 고치려면 먼저 **무엇이 어긋났는지** 정확히 알아야 하는데,
migrate 가 죽어버려서 Django 의 기본 도구로는 볼 수가 없다.

이 커맨드는 아무것도 바꾸지 않는다. 다음을 보여준다.

  1. 기록만 있고 파일이 없는 것(유령) — 파일을 지우거나 합칠 때 django_migrations
     를 안 치운 흔적이다.
  2. 파일은 있는데 미적용인 것 — 그리고 그게 만들려는 테이블이 **이미 있는지**.
     이미 있으면 --fake 로 기록만 맞추면 되고, 없으면 실제로 적용해야 한다.
  3. 의존성이 어긋난 지점 — migrate 가 죽는 바로 그 이유.

    python manage.py check_migration_state
    python manage.py check_migration_state --sql   # 고칠 때 쓸 명령을 함께 출력
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = '마이그레이션 상태 점검 (읽기 전용)'

    def add_arguments(self, parser):
        parser.add_argument('--sql', action='store_true',
                            help='상태를 맞출 때 쓸 명령을 함께 보여준다 (실행하지는 않는다)')

    def handle(self, *args, **options):
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        applied = set(loader.applied_migrations)
        disk = set(loader.disk_migrations)

        self.stdout.write(self.style.MIGRATE_HEADING('── 요약 ──'))
        self.stdout.write(f'  마이그레이션 파일 {len(disk)}개 / DB 적용 기록 {len(applied)}개')

        ghosts = sorted(applied - disk)
        pending = sorted(disk - applied)

        self._report_ghosts(ghosts)
        existing = self._report_pending(loader, pending)
        self._report_inconsistency(loader, applied)

        if options['sql']:
            self._report_fix(pending, existing)

    # ── 유령 기록 ────────────────────────────────────────────────────────────

    def _report_ghosts(self, ghosts):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('── 기록만 있고 파일이 없는 것 ──'))
        if not ghosts:
            self.stdout.write('  없음')
            return
        self.stdout.write(f'  {len(ghosts)}개. 파일을 지우거나 합칠 때 django_migrations 를 안 치운 흔적이다.')
        for app, count in Counter(a for a, _ in ghosts).most_common():
            names = [n for a, n in ghosts if a == app]
            self.stdout.write(f'    {app:<16} {count:2}개  {", ".join(names[:4])}'
                              + (' …' if len(names) > 4 else ''))
        self.stdout.write('  Django 는 이걸 무시하므로 당장 해가 되지는 않는다. 정리는 나중 문제다.')

    # ── 미적용 ───────────────────────────────────────────────────────────────

    def _report_pending(self, loader, pending):
        """미적용 마이그레이션이 만들려는 테이블이 이미 있는지 본다."""
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('── 파일은 있는데 미적용 ──'))
        if not pending:
            self.stdout.write('  없음')
            return {}

        tables = set(connection.introspection.table_names())
        existing = {}
        for app, name in pending:
            migration = loader.disk_migrations[(app, name)]
            created = self._created_tables(migration, app)
            have = sorted(t for t in created if t in tables)
            missing = sorted(t for t in created if t not in tables)
            existing[(app, name)] = (have, missing)

            if not created:
                mark, note = '?', '테이블을 만들지 않는 마이그레이션(필드 변경 등)'
            elif not missing:
                mark, note = self.style.SUCCESS('있음'), f'만들려는 테이블이 이미 다 있다: {", ".join(have)}'
            elif not have:
                mark, note = self.style.ERROR('없음'), f'테이블이 없다 — 실제로 적용해야 한다: {", ".join(missing)}'
            else:
                mark, note = self.style.WARNING('일부'), f'있음 {", ".join(have)} / 없음 {", ".join(missing)}'
            self.stdout.write(f'  [{mark}] {app}.{name}')
            self.stdout.write(f'         {note}')

        self.stdout.write('')
        self.stdout.write('  "있음" = 스키마가 마이그레이션 밖에서 이미 만들어졌다는 뜻이다.')
        self.stdout.write('  그런 건 --fake 로 기록만 맞추면 되고, "없음" 은 실제로 적용해야 한다.')
        return existing

    @staticmethod
    def _created_tables(migration, app_label):
        """이 마이그레이션이 CreateModel 로 만드는 테이블 이름들."""
        from django.db.migrations.operations.models import CreateModel

        names = []
        for op in migration.operations:
            if not isinstance(op, CreateModel):
                continue
            db_table = (op.options or {}).get('db_table')
            names.append(db_table or f'{app_label}_{op.name.lower()}')
        return names

    # ── 의존성 불일치 ────────────────────────────────────────────────────────

    def _report_inconsistency(self, loader, applied):
        """migrate 가 죽는 바로 그 이유를 짚는다."""
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('── 의존성이 어긋난 지점 ──'))

        broken = []
        for (app, name) in sorted(applied):
            migration = loader.disk_migrations.get((app, name))
            if migration is None:
                continue   # 유령은 위에서 따로 봤다
            for dep in migration.dependencies:
                if dep[0] == '__setting__' or dep[1] == '__first__':
                    continue
                if dep in loader.disk_migrations and dep not in applied:
                    broken.append((app, name, dep))

        if not broken:
            self.stdout.write('  없음. migrate 가 이 이유로 죽지는 않는다.')
            return

        self.stdout.write(self.style.ERROR(
            f'  {len(broken)}건. migrate 는 첫 번째 것에서 멈춘다.'))
        for app, name, dep in broken:
            self.stdout.write(f'    {app}.{name} (적용됨)')
            self.stdout.write(f'      -> {dep[0]}.{dep[1]} 에 의존하는데 그건 미적용')

    # ── 고치는 법 ────────────────────────────────────────────────────────────

    def _report_fix(self, pending, existing):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('── 상태를 맞추는 명령 (실행하지 않았다) ──'))
        fakeable, real = [], []
        for key in pending:
            have, missing = existing.get(key, ([], []))
            (real if missing else fakeable).append(key)

        if fakeable:
            self.stdout.write('  스키마가 이미 있는 것 - 기록만 맞춘다:')
            for app, name in fakeable:
                self.stdout.write(f'    python manage.py migrate {app} {name} --fake')
        if real:
            self.stdout.write('  실제로 적용해야 하는 것:')
            for app, name in real:
                self.stdout.write(f'    python manage.py migrate {app} {name}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            '  migrate 가 InconsistentMigrationHistory 로 죽는 동안에는 위 명령도 안 먹는다.\n'
            '  --fake 로 기록을 먼저 맞춰야 하는데 그것조차 막히면 django_migrations 에\n'
            '  직접 넣어야 한다. 반드시 백업 후에.'))
