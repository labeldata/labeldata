"""
돈이 드는 기능의 한도를 한곳에서 정한다.

판독(OpenAI 호출)과 저장 용량은 쓸수록 돈이 나가는데, 지금까지 한도는 AI
규정 검증 하나에만 걸려 있었다. 사진으로 읽기도, 시안 대조도, 원료를 몇 건
쌓든 아무 제한이 없었다. 나중에 유료로 돌릴 때 기능마다 다른 곳에 다른
방식으로 한도가 박혀 있으면 요금제를 만들 수가 없다.

**한도는 두 가지다. 섞으면 안 된다.**

    흐름(FLOW)   하루에 몇 번   — 판독처럼 부를 때마다 돈이 나가는 것
    저량(STOCK)  통틀어 몇 건   — 원료처럼 쌓여 있는 동안 자리를 차지하는 것

흐름은 날마다 0 으로 돌아가고, 저량은 지우기 전에는 줄지 않는다. 같은
"한도" 라는 말을 쓰지만 세는 법도, 다 썼을 때 할 말도 다르다 — 흐름은
"내일 다시", 저량은 "지우거나 올리세요" 다.

**서버 보호 한도는 여기 없다.** 한 번에 붙여넣을 수 있는 줄 수 같은 것은
등급과 무관하다 — 돈을 낸다고 서버가 더 견디지는 않는다. 그런 값은
settings 의 상수로 따로 둔다(PASTE_MAX_ROWS).

등급은 `UserProfile.paid_yn` 하나뿐이다. 요금제가 여러 층으로 갈리면
`_tier()` 만 고치면 된다 — 부르는 쪽은 이름으로만 묻는다.
"""
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

FLOW = 'flow'
STOCK = 'stock'


class Feature:
    """한 기능의 한도. free/paid 는 등급별 상한이다."""

    def __init__(self, kind, label, free, paid, unit='회', counter=None):
        self.kind = kind
        self.label = label
        self.free = free
        self.paid = paid
        self.unit = unit
        # 저량은 세는 법이 기능마다 다르다. 흐름은 FeatureUsage 가 센다.
        self.counter = counter


def _count_ingredients(user):
    """등록해 둔 원료 수. 지운 것은 빼고 센다."""
    from v1.label.models import MyIngredient
    return MyIngredient.objects.filter(user_id=user, delete_YN='N').count()


def _count_storage(user):
    """올려 둔 파일의 합(MB). 성적서·시안·사진이 다 여기 쌓인다."""
    from v1.common.uploads import stored_bytes
    return int(round(stored_bytes(user) / 1024.0 / 1024.0))


# 지금 넣는 숫자는 **넉넉하게** 잡는다.
#
# 한도를 거는 목적은 나중에 유료로 돌릴 자리를 만들어 두는 것이지, 오늘
# 쓰는 사람을 막는 것이 아니다. 실측(2026-08-30)으로 한 계정에 원료가 548건
# 있었는데 무료 한도를 500 으로 두면 배포하는 순간 그 사람은 원료를 하나도
# 못 넣는다. 요금제를 실제로 열 때 이 숫자를 내리면 된다 — 코드를 고치지
# 않고 settings.QUOTA_LIMITS 로도 내릴 수 있다.
FEATURES = {
    # ── 흐름: 부를 때마다 돈이 나간다 ──────────────────────────────────
    'ai_validation': Feature(
        FLOW, '규정 검증(AI)', free=10, paid=50),
    'ocr_label': Feature(
        FLOW, '표시사항 사진 읽기', free=30, paid=300),
    'ocr_compare': Feature(
        FLOW, '디자인 시안 대조', free=10, paid=100),
    'ocr_ingredient': Feature(
        FLOW, '원료 사진 읽기', free=20, paid=200),

    # ── 저량: 쌓여 있는 동안 자리를 차지한다 ───────────────────────────
    'ingredient': Feature(
        STOCK, '등록한 원료', free=2000, paid=20000, unit='건',
        counter=_count_ingredients),
    # 파일은 올린 순간부터 디스크를 차지한다. 한 파일의 상한(30 MB)은 등급과
    # 무관한 서버 보호 값이라 여기 없다 — common/uploads.MAX_UPLOAD_MB 다.
    'storage': Feature(
        STOCK, '올린 파일', free=2000, paid=20000, unit='MB',
        counter=_count_storage),
}


def feature(key):
    f = FEATURES.get(key)
    if f is None:
        raise KeyError('모르는 기능입니다: %s' % key)
    return f


# ── 등급과 한도 ───────────────────────────────────────────────────────────

def is_paid(user):
    """UserProfile 이 없는 예외적 계정도 있어 안전하게 본다."""
    try:
        return bool(getattr(getattr(user, 'profile', None), 'paid_yn', False))
    except Exception:
        return False


def limit_for(user, key):
    """
    이 계정이 이 기능에 쓸 수 있는 한도.

    settings.QUOTA_LIMITS 로 덮어쓸 수 있다 — 요금제를 손보는 동안 코드를
    고치지 않고 서버 설정만으로 조절하려는 자리다.

        QUOTA_LIMITS = {'ocr_label': {'free': 5, 'paid': 500}}
    """
    f = feature(key)
    tier = 'paid' if is_paid(user) else 'free'
    override = (getattr(settings, 'QUOTA_LIMITS', {}) or {}).get(key, {})
    if tier in override:
        return int(override[tier])
    return f.paid if tier == 'paid' else f.free


# ── 지금까지 쓴 양 ────────────────────────────────────────────────────────

def used(user, key):
    """
    조회에 실패하면 0 을 돌려준다. 사용자를 막는 것보다 몇 번 더 나가는 쪽이
    낫다 — 대신 로그에 남긴다.
    """
    f = feature(key)
    if f.kind == STOCK:
        try:
            return int(f.counter(user))
        except Exception:
            logger.exception('[한도] %s 저량 조회 실패 (user=%s)', key,
                             getattr(user, 'id', None))
            return 0

    from v1.common.models import FeatureUsage
    try:
        row = (FeatureUsage.objects
               .filter(user=user, feature=key, used_date=timezone.localdate())
               .first())
        return row.count if row else 0
    except Exception:
        logger.exception('[한도] %s 사용량 조회 실패 (user=%s)', key,
                         getattr(user, 'id', None))
        return 0


def charge(user, key, amount=1):
    """
    쓴 만큼 적는다. 저량은 적을 것이 없다 — 실제로 만들어진 행이 곧 사용량이다.

    행을 읽어 +1 해서 저장하면 동시 요청에서 하나가 묻힌다. DB 가 더하게 한다.
    """
    if feature(key).kind == STOCK or amount <= 0:
        return

    from django.db import IntegrityError, transaction
    from django.db.models import F
    from v1.common.models import FeatureUsage

    today = timezone.localdate()
    updated = (FeatureUsage.objects
               .filter(user=user, feature=key, used_date=today)
               .update(count=F('count') + amount))
    if updated:
        return
    # 오늘 첫 사용. 동시에 둘이 들어오면 하나는 IntegrityError 가 나는데,
    # 그때는 이미 만들어진 행을 올리면 된다.
    try:
        with transaction.atomic():
            FeatureUsage.objects.create(user=user, feature=key,
                                        used_date=today, count=amount)
    except IntegrityError:
        (FeatureUsage.objects
         .filter(user=user, feature=key, used_date=today)
         .update(count=F('count') + amount))


# ── 물어보기 ──────────────────────────────────────────────────────────────

def usage(user, key):
    """차감하지 않고 지금 상태만 본다. 단추를 누르기 전에 보여 줄 값이다."""
    f = feature(key)
    now = used(user, key)
    limit = limit_for(user, key)
    return {
        'feature': key,
        'kind': f.kind,
        'label': f.label,
        'unit': f.unit,
        'used': now,
        'limit': limit,
        'left': max(0, limit - now),
        'is_paid': is_paid(user),
    }


def usage_all(user):
    return {key: usage(user, key) for key in FEATURES}


def _over_message(info, amount):
    if info['kind'] == STOCK:
        return ('%s 한도(%s%s)를 채웠습니다. 쓰지 않는 것을 지우거나 요금제를 '
                '올려 주세요.' % (info['label'], info['limit'], info['unit']))
    if amount > 1:
        return ('오늘 %s 한도(%s%s) 안에서 %s%s이 남았습니다.'
                % (info['label'], info['limit'], info['unit'],
                   info['left'], info['unit']))
    return ('오늘의 %s 한도(%s%s)를 모두 사용했습니다. 내일 다시 이용해 주세요.'
            % (info['label'], info['limit'], info['unit']))


def check(user, key, amount=1):
    """
    차감하지 않고 되는지만 본다.

    Returns: (되는가, usage 정보) — 안 되면 정보에 'message' 가 담긴다.
    """
    info = usage(user, key)
    if info['used'] + amount > info['limit']:
        info['message'] = _over_message(info, amount)
        return False, info
    info['message'] = ''
    return True, info


def check_and_charge(user, key, amount=1):
    """
    되면 그 자리에서 차감한다. 저량은 차감할 것이 없다 — 실제로 만든 행이
    곧 사용량이라, 만들기 **전에** 부르고 만든 뒤에는 부르지 않는다.
    """
    ok, info = check(user, key, amount)
    if not ok:
        return False, info
    charge(user, key, amount)
    info['used'] += amount if feature(key).kind == FLOW else 0
    info['left'] = max(0, info['limit'] - info['used'])
    return True, info
