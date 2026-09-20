"""
브라우저 시험(v1/common/browser_checks.py) 전용 설정.

settings_test 는 메모리 SQLite 를 쓰는데, 라이브 서버 스레드가 시험 스레드와
**한 연결을 나눠 쓴다**(메모리 DB 는 그 길밖에 없다). 그러면 두 스레드가 같은
연결을 번갈아 써서 `database table is locked` 와 `bad parameter or other API
misuse` 가 난다. 파일 DB 면 스레드마다 제 연결을 갖고 잠금은 SQLite 가 푼다.
tests_browser.py 가 따로 띄우는 프로세스에서만 쓴다.
"""
import tempfile
from pathlib import Path

from .settings_test import *  # noqa: F401,F403

_DB = Path(tempfile.gettempdir()) / 'labeldata_browser_test.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(_DB),
        'TEST': {'NAME': str(_DB)},
        'OPTIONS': {'timeout': 20},
    }
}
