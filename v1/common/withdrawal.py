# -*- coding: utf-8 -*-
"""
회원 탈퇴 — **즉시 익명화하고, 정해진 기간 뒤에 지운다.**

왜 두 단계인가
─────────────
개인정보처리방침이 "회원 탈퇴 시 수집된 개인정보 및 기기 식별 정보는 즉시
파기됩니다" 라고 약속한다. 그런데 계정 행 자체를 그 자리에서 지우면 그 사람이
만든 표시사항·제품·원료가 CASCADE 로 함께 사라진다 — 잘못 눌렀을 때 되돌릴
방법이 없고, 지우는 도중 실패하면 절반만 지워진 상태가 남는다.

그래서 나눈다.

    1. 탈퇴하는 순간 — **개인을 가리키는 것을 전부 지운다.**
       이메일·이름·전화·주소·생년월일·회사·인허가번호·제조원, 그리고 앱이
       들고 있던 기기·보관함·알림 내역·알림 키워드. 계정은 비활성이 되어
       웹으로도 앱으로도 다시 들어올 수 없다. 이 시점에 남는 것은 **누구인지
       알 수 없는 껍데기**다.

    2. 그 뒤 정해진 기간이 지나면 — 껍데기와 그가 만든 것을 완전히 지운다.

파기 기간을 왜 5일로 두는가
─────────────────────────
「개인정보 보호법」 제21조 제1항은 보유 목적이 끝나면 **지체 없이** 파기하라고
하고, 같은 법 시행령 제16조 제1항은 그 '지체 없이' 를 **정당한 사유가 없으면
5일 이내**로 정한다. 그것이 이 서비스에 걸리는 일반 기준이다.

더 긴 법정 보존이 걸리는 것들 — 「전자상거래 등에서의 소비자보호에 관한 법률」
시행령 제6조의 계약·청약철회 기록 5년, 대금결제·재화공급 기록 5년, 소비자
불만·분쟁처리 기록 3년 — 은 **이 저장소에 해당 데이터가 없다.** 결제·주문·
구독 모델이 없고(`paid_yn` 플래그 하나뿐이다) 따라서 보존할 거래 기록이
생기지 않는다. 그런 기록을 다루기 시작하면 그때 이 기간을 나눠야 한다.

운영에서 더 길게 두어야 하면 `settings.ACCOUNT_PURGE_DAYS` 로 늘린다.
코드를 고치지 않고 바꿀 수 있게 둔 이유가 그것이다.

username 으로 안다 — 마이그레이션을 넣지 않는다
──────────────────────────────────────────────
탈퇴 여부와 탈퇴 날짜를 담을 새 칸을 두면 운영 DB 를 건드려야 하는데, 이
저장소는 마이그레이션 그래프가 이미 갈라져 있다(settings_test 주석 참고).
게스트 계정이 같은 이유로 username 접두어를 쓰고 있으므로 같은 방식을 쓴다.

    withdrawn_20260913_a1b2c3d4@labeasylabel.com

날짜가 고정 자릿수로 앞에 있으므로 문자열 비교가 곧 시간 비교다 — 지울 것을
고를 때 인덱스를 그대로 쓴다.
"""
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

WITHDRAWN_PREFIX = 'withdrawn_'
WITHDRAWN_DOMAIN = '@labeasylabel.com'

# 개인정보 보호법 시행령 제16조 제1항 — 정당한 사유가 없으면 5일 이내.
DEFAULT_PURGE_DAYS = 5

# 계정에서 지우는 개인 식별 정보. **여기 없는 칸은 남는다** — 새 칸이
# 생기면 이 목록에 올려야 한다. 시험이 그것을 센다.
_PROFILE_BLANK_FIELDS = (
    'phone_number', 'address', 'company_name', 'license_number',
    'manufacturer_name', 'manufacturer_address',
)
_PROFILE_NULL_FIELDS = (
    'birth_date', 'email_verification_token', 'email_verification_sent_at',
    'password_reset_token', 'password_reset_sent_at',
)


def purge_days() -> int:
    return int(getattr(settings, 'ACCOUNT_PURGE_DAYS', DEFAULT_PURGE_DAYS))


def is_withdrawn(user) -> bool:
    if not user:
        return False
    return (getattr(user, 'username', '') or '').startswith(WITHDRAWN_PREFIX)


def _withdrawn_username(when=None) -> str:
    when = when or timezone.now()
    return '%s%s_%s%s' % (WITHDRAWN_PREFIX, when.strftime('%Y%m%d'),
                          uuid.uuid4().hex[:8], WITHDRAWN_DOMAIN)


@transaction.atomic
def withdraw(user) -> User:
    """
    탈퇴 처리. **개인을 가리키는 것을 지금 지운다.**

    돌려주는 것은 익명화된 같은 계정이다. 그가 만든 표시사항·제품·원료는
    아직 남아 있고, `purge_withdrawn` 이 기간이 지난 뒤 함께 지운다.
    """
    from v1.mobile.models import AlertRule, AppDevice

    # 앱이 들고 있던 것 — 기기를 지우면 보관함·알림 내역이 함께 간다(CASCADE)
    AlertRule.objects.filter(user=user).delete()
    AppDevice.objects.filter(user=user).delete()

    profile = getattr(user, 'profile', None)
    if profile is not None:
        for field in _PROFILE_BLANK_FIELDS:
            if hasattr(profile, field):
                setattr(profile, field, '')
        for field in _PROFILE_NULL_FIELDS:
            if hasattr(profile, field):
                setattr(profile, field, None)
        if getattr(profile, 'profile_image', None):
            profile.profile_image = None
        profile.save()

    user.username = _withdrawn_username()
    user.email = ''
    user.first_name = ''
    user.last_name = ''
    user.is_active = False
    user.set_unusable_password()
    user.save()
    return user


def stale_withdrawn(days: int = None):
    """파기할 때가 된 탈퇴 계정.

    username 앞머리에 날짜가 고정 자릿수로 들어 있으므로 문자열 비교가 곧
    시간 비교다.
    """
    days = purge_days() if days is None else days
    cutoff = (timezone.now() - timezone.timedelta(days=days)).strftime('%Y%m%d')
    return (User.objects
            .filter(username__startswith=WITHDRAWN_PREFIX)
            .filter(username__lt='%s%s' % (WITHDRAWN_PREFIX, cutoff)))
