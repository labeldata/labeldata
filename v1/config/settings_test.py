"""
테스트 전용 설정.

    python manage.py test --settings=v1.config.settings_test

기본 설정으로는 테스트가 돌지 않는다. 두 가지 이유가 있고 둘 다 여기서 우회한다.

1. 운영 DB 계정(labeldata)에 test_labeldb 생성 권한이 없다 → 메모리 SQLite 사용.
2. 마이그레이션 그래프가 깨져 있다 → 마이그레이션을 건너뛰고 모델에서 직접
   스키마를 만든다. (regulatory 앱의 리프가 0004_alter_inspectionresult_tkawyprno_and_more
   와 0010_remove_false_positive_pattern 둘로 갈라져 있고, 운영 DB에는
   user_management.0004 가 의존 대상인 products.0002_combined 보다 먼저 적용돼 있어
   manage.py migrate 자체가 InconsistentMigrationHistory 로 실패한다.
   스키마는 마이그레이션 밖에서 관리되고 있는 상태 — 별도로 정리해야 할 사안이고,
   테스트는 모델 정의만 있으면 되므로 여기서는 관여하지 않는다.)

그 외 설정은 전부 settings.py 를 그대로 따른다.
"""

from .settings import *  # noqa: F401,F403


class _SkipMigrations:
    """모든 앱의 마이그레이션을 무시하고 모델 정의로 테이블을 만들게 한다."""

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _SkipMigrations()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# 테스트가 운영 캐시 디렉터리(django_cache/)를 오염시키지 않게 한다.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# 비밀번호 해싱은 테스트 속도에만 영향을 준다.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
