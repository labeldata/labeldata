# -*- coding: utf-8 -*-
"""
브라우저 시험(browser_checks.py)을 **따로 띄운 프로세스**에서 돌린다.

같은 프로세스에서 돌리면 라이브 서버가 시험 스위트의 공유 메모리 SQLite 를
같이 쓰는데, 앞선 3,400 건 가운데 어딘가가 열어 둔 트랜잭션이 표를 잠가
`database table is locked` 가 났다. 새 프로세스는 제 DB 로 시작한다.
크롬·websocket-client 가 없으면 건너뛴다(운영 서버).
"""
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from v1.common.browser_checks import chrome_path, websocket


class 브라우저_시험을_따로_돌린다(SimpleTestCase):
    def test_배합표_등_화면을_그려_본다(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        root = Path(settings.BASE_DIR).parent          # manage.py 가 있는 곳
        out = subprocess.run(
            [sys.executable, 'manage.py', 'test', 'v1.common.browser_checks',
             '--settings=v1.config.settings_test', '--noinput'],
            cwd=root, capture_output=True, timeout=600)
        tail = out.stderr.decode('utf-8', 'replace')[-3000:]
        self.assertEqual(out.returncode, 0, '브라우저 시험이 실패했다:\n' + tail)
        self.assertIn('OK', tail)
