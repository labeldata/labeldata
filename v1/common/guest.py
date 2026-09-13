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


# 이 브라우저가 이미 받은 게스트를 가리키는 쿠키.
#
# **한도가 방문마다 리셋되던 것을 막는다.** 흐름 한도(규정 검증 10/일,
# 표시사항 사진 읽기 30/일 …)는 부를 때마다 실제로 돈이 나가는 자리인데,
# 그 한도는 계정에 붙는다. 그런데 「둘러보기」를 누를 때마다 새 계정이
# 생겼으므로, 로그아웃하고 다시 누르면 한도가 그 자리에서 새것이 됐다.
# 막는 것은 로그인 자리의 IP당 20/분 하나뿐이었다.
#
# 세션에 담을 수 없다 — `login()` 이 사용자가 바뀔 때 세션을 비운다.
# 그래서 서명 쿠키에 담는다. 값은 게스트의 pk 뿐이고 서명이 붙으므로
# 남의 게스트를 가리키게 고칠 수 없다.
GUEST_COOKIE = 'guest_ref'
GUEST_COOKIE_SALT = 'v1.common.guest'


def guest_from_cookie(request):
    """
    이 브라우저가 이미 쓰던 게스트. 없거나 낡았으면 None.

    같은 사람이 다시 누른 것과 다른 사람이 처음 누른 것은 다르다 — 앞의
    것에까지 새 계정을 내주면 한도가 뜻을 잃는다. 격리는 그대로다:
    쿠키가 없는 방문자는 여전히 제 계정을 새로 받는다.
    """
    raw = None
    try:
        raw = request.get_signed_cookie(GUEST_COOKIE, default=None,
                                        salt=GUEST_COOKIE_SALT)
    except Exception:
        return None
    if not raw:
        return None
    try:
        user = User.objects.get(pk=int(raw))
    except (User.DoesNotExist, TypeError, ValueError):
        return None
    if not is_guest(user) or not user.is_active:
        return None
    # 치울 때가 지난 계정은 곧 지워진다 — 새로 내주는 편이 낫다
    cutoff = timezone.now() - timezone.timedelta(hours=GUEST_TTL_HOURS)
    if user.date_joined < cutoff:
        return None
    return user


def remember_guest(response, user):
    """다음에 눌렀을 때 같은 자리로 돌아오게 표시를 남긴다."""
    response.set_signed_cookie(
        GUEST_COOKIE, str(user.pk), salt=GUEST_COOKIE_SALT,
        max_age=GUEST_TTL_HOURS * 3600, httponly=True, samesite='Lax')
    return response


def stale_guests(hours: int = GUEST_TTL_HOURS):
    """치울 때가 된 게스트. 옛 공용 계정은 건드리지 않는다."""
    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    return (User.objects
            .filter(username__startswith=GUEST_PREFIX, date_joined__lt=cutoff)
            .exclude(username=LEGACY_GUEST_EMAIL))


# ─────────────────────────────────────────────────────────────────────────────
# 게스트가 만든 것을 회원 계정으로 옮긴다
#
# 격리는 끝냈는데 **승격 경로를 안 만들었다.** 그래서 지금 이런 일이 일어난다.
#
#     게스트로 들어옴 → 제품 만듦 → BOM 넣음 → 검증 돌림 → "쓸 만하네" → 가입
#     → 새 계정은 텅 비어 있다 → 게스트 계정은 stale_guests 가 지운다
#
# 가장 열심히 써 본 사람의 결과물을, 정확히 그 사람이 돈을 낼 마음이 든
# 순간에 버리고 있었다.
#
# **옮길 것은 다섯뿐이다.** User 를 가리키는 관계가 스물다섯쯤 있지만 전부
# 옮기면 안 된다. 옮기는 것은 "그 사람이 만든 결과물" 이고, 남기는 것은
# "그때 그 계정에 일어난 사실" 이다.
#
#     옮긴다   제품 · 원료 · 자주 쓰는 문구 · 폴더 · 문서 업로드자
#     안 옮긴다 활동 로그(그때의 사실) · 받은 공유(남이 그 게스트에게 준 것)
#               · 알림(옮겨도 의미가 없다)
#
# BOM 줄·영양성분·문서는 **따로 옮기지 않는다.** 제품과 원료에 FK 로 매달려
# 있어서 주인이 바뀌면 함께 따라온다. 이걸 모르고 하나씩 옮기려 들면 표를
# 열 개도 넘게 건드리게 된다.
# ─────────────────────────────────────────────────────────────────────────────

def _movable(guest):
    """(설명, 질의집합, 주인 칸) 세 쪽. 세는 것과 옮기는 것이 같은 목록을 본다."""
    from v1.label.models import MyIngredient, MyLabel, MyPhrase
    from v1.products.models import ProductDocument, ProductFolder

    return [
        ('제품',   MyLabel.objects.filter(user_id=guest),          'user_id'),
        ('원료',   MyIngredient.objects.filter(user_id=guest),     'user_id'),
        ('폴더',   ProductFolder.objects.filter(owner=guest),      'owner'),
        ('문구',   MyPhrase.objects.filter(user_id=guest),         'user_id'),
        # 문서는 제품에 매달려 따라온다. 업로드자 도장만 같은 사람으로 고친다 —
        # 안 고치면 게스트가 지워질 때 SET_NULL 로 "누가 올렸는지 모름" 이 된다.
        ('문서',   ProductDocument.objects.filter(uploaded_by=guest), 'uploaded_by'),
    ]


def promotable(guest):
    """
    옮길 것이 무엇이 얼마나 있나. **묻기 위해서** 센다.

    조용히 옮기면 안 된다. 남의 PC 에서 둘러본 것이 내 계정에 딸려 오면
    곤란하고, 무엇이 옮겨졌는지 모르면 빠진 것이 있어도 알 수 없다.
    """
    if not is_guest(guest):
        return {}
    counts = {}
    for label, qs, _field in _movable(guest):
        n = qs.count()
        if n:
            counts[label] = n
    return counts


@transaction.atomic
def promote(guest, user):
    """
    게스트가 만든 것을 `user` 에게 옮긴다. 옮긴 수를 돌려준다.

    **한 트랜잭션이다.** 다섯을 옮기다 가운데서 실패하면 절반만 옮겨진 채
    남는데, 그 상태는 게스트도 회원도 온전하지 않다.

    옮긴 뒤 게스트를 잠근다. 그 세션이 아직 살아 있어도 두 번 옮겨 가지
    못하게 하는 자물쇠다 — is_active 를 내리면 다음 요청에서 로그아웃된다.
    """
    if not is_guest(guest):
        raise ValueError('게스트가 아닌 계정에서는 옮기지 않는다')
    if is_guest(user):
        raise ValueError('게스트에게로는 옮기지 않는다')
    if guest.pk == user.pk:
        raise ValueError('제 자신에게로는 옮기지 않는다')

    moved = {}
    for label, qs, field in _movable(guest):
        n = qs.update(**{field: user})
        if n:
            moved[label] = n

    guest.is_active = False
    guest.save(update_fields=['is_active'])
    return moved
