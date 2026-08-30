"""
DB 를 파일로 덤프한다. Django 설정의 접속 정보를 그대로 쓴다.

손으로 mysqldump 를 치면 두 가지가 계속 어긋난다.

  - 접속 정보. .env 를 셸에서 source 하면 값에 따라 조용히 빈 문자열이 되고,
    mysqldump 는 호스트가 비면 TCP 가 아니라 유닉스 소켓으로 붙으려 한다.
    실제로 "Can't connect to local MySQL server through socket" 이 났다.
  - 실패를 놓친다. `mysqldump ... | gzip > out.gz` 는 mysqldump 가 죽어도
    gzip 이 성공하므로 종료 코드가 0 이다. 20바이트짜리 빈 파일이 남고
    백업을 받은 줄 안다.

여기서는 settings.DATABASES 를 읽어 그대로 넘기고, 실패하면 파일을 지우고
오류를 그대로 보여준다. 비밀번호는 MYSQL_PWD 로 넘겨 명령줄(ps)에 안 남는다.

    python manage.py dump_db
    python manage.py dump_db --out ~/backup.sql.gz
    python manage.py dump_db --schema-only     # 구조만 (데이터 없이)

    # 마이그레이션 상태만 맞출 때 - 운영 데이터를 옮기지 않는다
    python manage.py dump_db --schema-only --data-for django_migrations
"""
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'DB 를 gzip 으로 덤프한다 (Django 설정의 접속 정보를 사용)'

    def add_arguments(self, parser):
        parser.add_argument('--out', default=None, help='저장 경로 (기본: ~/<DB이름>_<날짜>.sql.gz)')
        parser.add_argument('--schema-only', action='store_true', help='구조만, 데이터 제외')
        parser.add_argument('--data-for', action='append', default=[], metavar='TABLE',
                            help='--schema-only 일 때 이 테이블의 데이터만 포함 (여러 번 지정 가능)')
        parser.add_argument('--database', default='default', help='DATABASES 별칭')
        parser.add_argument('--mysqldump', default=None,
                            help='mysqldump 경로 (PATH 에 없을 때. 윈도우 개발 환경 등)')

    def handle(self, *args, **options):
        db = settings.DATABASES[options['database']]
        if 'mysql' not in db['ENGINE']:
            raise CommandError(f'MySQL 전용이다 (ENGINE={db["ENGINE"]})')

        name = db['NAME']
        host = db.get('HOST') or '127.0.0.1'
        port = str(db.get('PORT') or '3306')
        user = db['USER']

        # 접속 정보를 먼저 보여준다. 어디에 붙는지 모르고 백업하면 안 된다.
        self.stdout.write(f'  DB   : {name}')
        self.stdout.write(f'  호스트: {host}:{port}')
        self.stdout.write(f'  사용자: {user}')

        dump = options['mysqldump'] or shutil.which('mysqldump')
        if not dump or not Path(dump).exists():
            raise CommandError(
                'mysqldump 를 찾을 수 없다. MySQL 클라이언트가 필요하다.\n'
                '경로를 직접 줄 수도 있다: --mysqldump "C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqldump.exe"')

        out = Path(options['out'] or
                   Path.home() / f'{name.replace("$", "_")}_{datetime.now():%Y%m%d_%H%M}.sql.gz')
        out = out.expanduser()

        base = [
            dump, '-h', host, '-P', port, '-u', user,
            '--single-transaction',
            '--no-tablespaces',      # PythonAnywhere 는 PROCESS 권한이 없다
            '--default-character-set=utf8mb4',
        ]

        # 실행할 mysqldump 를 순서대로 모은다.
        # 구조만 받으면서 특정 테이블의 데이터만 넣으려면 두 번 돌려 이어붙여야
        # 한다 - --no-data 는 DB 전체에 걸리기 때문이다.
        passes = []
        if options['schema_only']:
            passes.append(base + ['--no-data', name])
            for table in options['data_for']:
                passes.append(base + ['--no-create-info', name, table])
        else:
            passes.append(base + [name])

        env = dict(os.environ)
        if db.get('PASSWORD'):
            env['MYSQL_PWD'] = db['PASSWORD']   # 명령줄에 안 남는다

        self.stdout.write(f'  저장  : {out}')
        if options['schema_only']:
            extra = (', 데이터 포함: ' + ', '.join(options['data_for'])
                     if options['data_for'] else '')
            self.stdout.write(f'  범위  : 구조만{extra}')
        self.stdout.write('  덤프 중...')

        stderr, code = '', 0
        try:
            with gzip.open(out, 'wb') as fh:
                for cmd in passes:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, env=env)
                    shutil.copyfileobj(proc.stdout, fh)
                    proc.stdout.close()
                    stderr += proc.stderr.read().decode('utf-8', 'replace')
                    code = proc.wait()
                    if code != 0:
                        break
        except Exception as exc:
            out.unlink(missing_ok=True)
            raise CommandError(f'덤프 실패: {exc}')

        if code != 0:
            # 파이프로 넘기면 여기서 조용히 성공해 버린다. 파일을 지워야
            # "백업 받았다" 고 착각하지 않는다.
            out.unlink(missing_ok=True)
            raise CommandError(f'mysqldump 가 {code} 로 끝났다. 파일을 지웠다.\n{stderr.strip()}')

        size = out.stat().st_size
        if size < 512:
            out.unlink(missing_ok=True)
            raise CommandError(f'덤프가 {size} 바이트뿐이다. 뭔가 잘못됐다. 파일을 지웠다.\n{stderr.strip()}')

        if stderr.strip():
            self.stdout.write(self.style.WARNING(f'  경고: {stderr.strip()}'))
        self.stdout.write(self.style.SUCCESS(f'  완료: {out} ({size / 1024 / 1024:.1f} MB)'))
