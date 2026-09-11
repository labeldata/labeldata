# -*- coding: utf-8 -*-
"""
둘러보는 사람에게 **저마다의 자리**를 준다.

지금까지 게스트는 계정 하나였다
────────────────────────────────
`guest@labeasylabel.com` 을 **모든 방문자가 같이 썼다.** 그래서 이렇게 된다.

    A 가 만든 제품을 B 가 본다
    B 가 그 위에 덮어쓴다
    지우는 것만 막혀 있어 쓰레기가 쌓인다

홍보를 하면 첫 화면이 **남의 실습 데이터**로 채워진다. 그리고 원료·배합의
소유권 검사를 아무리 촘촘히 해도 게스트끼리는 **의미가 없다** — 같은 user 다.

방문마다 새 계정을 내준다
────────────────────────
`guest_<열두 글자>@labeasylabel.com`. 그러면 이미 있는 소유권 규칙이 그대로
일한다 — 게스트를 위해 따로 거르는 코드를 심을 필요가 없다.

**마이그레이션을 넣지 않는다.** 새 칸(is_guest)을 두면 운영 DB 를 건드려야
하는데, 그만한 값이 없다. 게스트인지는 username 으로 안다 — 이 접두어로
만드는 곳이 여기 한 곳뿐이라 다른 데서 새지 않는다.

옛 공용 계정도 게스트로 본다
──────────────────────────
지금 그 계정으로 들어와 있는 사람이 있을 수 있다. 로그인 자리에서 더는 내주지
않지만, 판정은 계속 게스트로 한다 — 안 그러면 그 사람에게 갑자기 삭제 단추가
생긴다.
"""
import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

# 옛 공용 계정. 더는 새로 내주지 않지만 판정은 게스트로 한다.
LEGACY_GUEST_EMAIL = 'guest@labeasylabel.com'

GUEST_PREFIX = 'guest_'
GUEST_DOMAIN = '@labeasylabel.com'

# 이만큼 지나면 치운다. 둘러보기는 한 자리에서 끝나는 일이다.
GUEST_TTL_HOURS = 24


def is_guest(user) -> bool:
    """
    둘러보는 사람인가.

    **이 판정을 다른 데서 다시 적지 않는다.** 예전에는 이메일 문자열이 뷰와
    템플릿 열다섯 곳에 박혀 있었다 — 게스트를 늘리거나 규칙을 바꾸면 그 열다섯
    곳을 다 찾아야 했고, 언젠가 하나가 빠진다.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    name = (getattr(user, 'username', '') or '')
    return name == LEGACY_GUEST_EMAIL or name.startswith(GUEST_PREFIX)


def new_guest_username() -> str:
    return '%s%s%s' % (GUEST_PREFIX, uuid.uuid4().hex[:12], GUEST_DOMAIN)


@transaction.atomic
def create_guest() -> User:
    """
    이번 방문의 게스트를 만든다.

    비밀번호는 쓰지 않는다 — 로그인 자리에서 곧바로 `login()` 하므로 맞춰 볼
    일이 없다. `set_unusable_password()` 로 **아무도 이 계정에 로그인할 수
    없게** 둔다. 비밀번호가 있으면 그 값이 어딘가에 적히고, 적힌 것은 샌다.
    """
    from v1.user_management.models import UserProfile

    user = User.objects.create(
        username=new_guest_username(),
        email='',              # 보낼 곳이 없다. 있으면 메일이 나간다
        is_active=True,
    )
    user.set_unusable_password()
    user.save(update_fields=['password'])

    # 이메일 인증을 통과한 것으로 둔다 — 보낼 주소가 없으니 인증할 수도 없고,
    # 안 해 두면 로그인 직후 "인증하세요" 로 막힌다.
    UserProfile.objects.update_or_create(
        user=user, defaults={'email_verified_yn': True})
    return user


def stale_guests(hours: int = GUEST_TTL_HOURS):
    """치울 때가 된 게스트. 옛 공용 계정은 건드리지 않는다."""
    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    return (User.objects
            .filter(username__startswith=GUEST_PREFIX, date_joined__lt=cutoff)
            .exclude(username=LEGACY_GUEST_EMAIL))
