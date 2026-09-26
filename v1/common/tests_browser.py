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

from v1.common.browser_checks import chrome_path, kill_stray_chromes, websocket


class 브라우저_시험을_따로_돌린다(SimpleTestCase):
    def test_배합표_등_화면을_그려_본다(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        root = Path(settings.BASE_DIR).parent          # manage.py 가 있는 곳
        try:
            out = subprocess.run(
                [sys.executable, 'manage.py', 'test', 'v1.common.browser_checks',
                 '--settings=v1.config.settings_browser', '--noinput'],
                # 화면 시험이 일곱 건이다(각각 크롬을 띄우고 여러 번 다시 읽는다).
                # 600 초는 실측 바로 위라, 기계가 조금 바쁘면 여기서 끊기고
                # **시험 내용과 무관하게** 붉어졌다.
                cwd=root, capture_output=True, timeout=1800)
        except subprocess.TimeoutExpired:
            # **끊긴 자리를 치운다.** 하위 프로세스를 죽이면 그 안의
            # `chrome.close()` 가 돌지 않아 헤드리스 크롬이 남는다. 남은 것들이
            # 기계를 붙들면 **뒤에 오는 tests_js 가 줄줄이 시간 초과로 붉어진다**
            # — 실제로 그렇게 다섯 건이 한꺼번에 무너졌고, 붉은 문장은 전부
            # 엉뚱한 곳을 가리켰다.
            kill_stray_chromes()
            self.fail('브라우저 시험이 시간 안에 끝나지 않았다(남은 크롬은 닫았다).')
        tail = out.stderr.decode('utf-8', 'replace')[-3000:]
        if out.returncode != 0:
            kill_stray_chromes()
        self.assertEqual(out.returncode, 0, '브라우저 시험이 실패했다:\n' + tail)
        self.assertIn('OK', tail)
