"""
덤프 파일을 DB 에 되돌린다. **개발 DB 를 통째로 갈아엎는 명령이다.**

dump_db 와 짝이다. 손으로 하면 같은 함정에 빠진다.

    gunzip -c dump.sql.gz | mysql -u ... dbname

mysql 이 중간에 죽어도 gunzip 이 성공하면 종료 코드가 0 이라, 절반만 들어간 DB 를
두고 "복원했다" 고 여기게 된다. 여기서는 mysql 의 종료 코드와 stderr 를 본다.

기본으로 **아무것도 하지 않는다.** 무엇을 지우고 무엇을 넣을지 보여주고 멈춘다.
실제로 실행하려면 --yes 를 붙여야 한다.

운영 DB 로는 못 돌린다. 호스트에 pythonanywhere 가 들어 있으면 거부한다 -
개발 DB 를 맞추려다 운영을 덮어쓰는 사고는 되돌릴 수 없다.

    python manage.py restore_db ~/labeldb.sql.gz            # 미리보기
    python manage.py restore_db ~/labeldb.sql.gz --yes      # 실행
"""
import gzip
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = '덤프 파일을 DB 에 되돌린다 (개발 DB 전용, 기존 데이터를 지운다)'

    def add_arguments(self, parser):
        parser.add_argument('dump', help='덤프 파일 (.sql 또는 .sql.gz)')
        parser.add_argument('--yes', action='store_true',
                            help='실제로 실행한다 (없으면 미리보기만)')
        parser.add_argument('--database', default='default', help='DATABASES 별칭')
        parser.add_argument('--mysql', default=None,
                            help='mysql 실행 파일 경로 (PATH 에 없을 때)')

    def handle(self, *args, **options):
        db = settings.DATABASES[options['database']]
        if 'mysql' not in db['ENGINE']:
            raise CommandError(f'MySQL 전용이다 (ENGINE={db["ENGINE"]})')

        name, user = db['NAME'], db['USER']
        host = db.get('HOST') or '127.0.0.1'
        port = str(db.get('PORT') or '3306')

        if 'pythonanywhere' in host.lower():
            raise CommandError(
                f'운영 DB 로 보인다 ({host}). 이 명령은 개발 DB 전용이다.\n'
                '운영 복원이 정말 필요하면 손으로, 백업을 먼저 받고 하라.')

        dump = Path(options['dump']).expanduser()
        if not dump.is_file():
            raise CommandError(f'파일이 없다: {dump}')

        mysql = options['mysql'] or shutil.which('mysql')
        if not mysql or not Path(mysql).exists():
            raise CommandError(
                'mysql 을 찾을 수 없다.\n'
                '경로를 직접 줄 수도 있다: --mysql "C:/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe"')

        tables = len(connection.introspection.table_names())
        size_mb = dump.stat().st_size / 1024 / 1024

        self.stdout.write('  대상 DB : %s @ %s:%s (%s)' % (name, host, port, user))
        self.stdout.write('  현재 테이블 %d개 - 전부 지워진다' % tables)
        self.stdout.write('  덤프 파일: %s (%.1f MB)' % (dump, size_mb))

        if not options['yes']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '  미리보기다. 실제로 갈아엎으려면 --yes 를 붙여라.'))
            return

        env = dict(os.environ)
        if db.get('PASSWORD'):
            env['MYSQL_PWD'] = db['PASSWORD']
        base = [mysql, '-h', host, '-P', port, '-u', user]

        # 남아 있는 테이블이 덤프에 없으면 그대로 살아남는다. 통째로 다시 만든다.
        self.stdout.write('  스키마 재생성...')
        self._run(base + ['--execute',
                          f'DROP DATABASE IF EXISTS `{name}`; '
                          f'CREATE DATABASE `{name}` '
                          f'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'],
                  env, None)

        self.stdout.write('  덤프 적용...')
        opener = gzip.open if dump.suffix == '.gz' else open
        with opener(dump, 'rb') as fh:
            self._run(base + ['--default-character-set=utf8mb4', name], env, fh)

        connection.close()
        after = len(connection.introspection.table_names())
        self.stdout.write(self.style.SUCCESS(f'  완료: 테이블 {after}개'))
        self.stdout.write('  다음: python manage.py check_migration_state')

    @staticmethod
    def _run(cmd, env, stdin):
        proc = subprocess.Popen(cmd, stdin=(subprocess.PIPE if stdin else None),
                                stderr=subprocess.PIPE, env=env)
        if stdin is not None:
            shutil.copyfileobj(stdin, proc.stdin)
            proc.stdin.close()
        err = proc.stderr.read().decode('utf-8', 'replace')
        if proc.wait() != 0:
            # 파이프로 넘기면 여기서 조용히 넘어가 절반만 들어간 DB 가 남는다.
            raise CommandError(f'mysql 이 실패했다.\n{err.strip()}')
        if err.strip() and 'Using a password' not in err:
            print(f'  경고: {err.strip()}')
