"""
테스트 전용 설정.

    python manage.py test --settings=v1.config.settings_test

기본 설정으로는 테스트가 돌지 않는다. 두 가지 이유가 있고 둘 다 여기서 우회한다.

1. 운영 DB 계정(labeldata)에 test_labeldb 생성 권한이 없다 → 메모리 SQLite 사용.
2. 마이그레이션 중에 **MySQL 에서만 도는 SQL** 이 있다 → 마이그레이션을
   건너뛰고 모델 정의에서 직접 스키마를 만든다. 세 곳이 인덱스 존재 여부를
   `information_schema.statistics` 에서 읽는데(`products/0002_combined`,
   `products/0003_server_fix`, `label/0020_remove_fooditem_idx_lcns_no_and_more`)
   SQLite 에는 그런 표가 없어 `OperationalError: no such table` 로 죽는다.
   테스트는 모델 정의만 있으면 되므로 여기서는 관여하지 않는다.

   **여기 적혀 있던 "마이그레이션 그래프가 깨져 있다" 는 이제 사실이 아니다.**
   `96c1b08`(2026-08-30)에서 풀렸다 — 서버의 `migrate --plan` 이 "No planned
   migration operations." 를 냈고 미적용 0건·의존성 어긋남 0건이었다. 그
   설명에 적혀 있던 `regulatory.0010_remove_false_positive_pattern` 은 지금
   저장소에 없는 이름이고, `user_management.0004` 는 `products.0002_combined`
   를 의존하지 않는다. **모델을 고칠 수 있다** — 배포 절차는 README 를 본다.

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
    },
    # 속도 제한이 세는 자리. 운영은 파일 캐시지만 시험에서는 메모리로 둔다 —
    # 이 별칭이 없으면 @ratelimit 이 붙은 뷰가 시험에서 전부 터진다.
    'ratelimit': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

# 비밀번호 해싱은 테스트 속도에만 영향을 준다.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# regulatory/signals.py 는 원료 저장 때마다 백그라운드 스레드로 규제뉴스 재매칭을
# 돌린다. 테스트에서는 그 스레드가 롤백되는 트랜잭션 밖의 커넥션을 보게 되어
# "database table is locked" / "User matching query does not exist" 를 로그로
# 쏟아낸다(시그널이 예외를 삼키므로 테스트는 통과한다). 실제 검사 결과가 그
# 소음에 묻히지 않게 이 로거만 끈다.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'loggers': {
        'v1.regulatory.signals': {'handlers': ['null'], 'propagate': False},
    },
}
