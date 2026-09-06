"""
AI검증(OpenAI 호출) 비용 관리 — 동일 요청 캐싱 + 계정별 요청 제한.

**일일 한도를 세는 일은 여기 없다.** `v1/common/quota.py` 가 한다 — 판독,
시안 대조, 원료 등록 건수도 같은 틀로 센다. 기능마다 세는 자리를 따로
만들면 요금제를 만들 수가 없다. 여기 남은 것은 이 기능에만 있는 두 가지다.

  1. 콘텐츠 해시 캐싱: 라벨 내용이 그대로인데 다시 누르면 OpenAI를
     재호출하지 않고 최근 결과를 그대로 반환한다 — 사용자가 결과 보고
     그냥 다시 눌러보는 흔한 패턴에서 비용이 0이 된다.
  2. 분당 한도: 사용자에게 직접 노출하는 지표는 아니고, 실수로 여러 번
     연타했을 때를 대비한 조용한 안전장치.

어디에 무엇을 두는지
    일일 한도 -> DB(FeatureUsage).  사라지면 안 된다.
    분당 한도 -> 캐시. 연타를 막는 안전장치라 사라져도 일일 한도가 남는다.
    검증 결과 -> 캐시. 사라져도 OpenAI 를 한 번 더 부를 뿐이다.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from v1.common import quota

logger = logging.getLogger(__name__)

FEATURE = 'ai_validation'

# 분당 한도는 사용자에게 노출하는 지표가 아니라 자동화 남용을 걸러내기
# 위한 조용한 안전장치라, 정상적인 사용(짧은 시간에 라벨 여러 개 검증)
# 에서는 절대 먼저 걸리지 않도록 일일 한도보다 넉넉하게 잡는다 — 실제로
# 이 값이 무료 일일 한도(10)보다 낮으면 "일일 10회"가 아니라 "요청이
# 너무 많다"는 엉뚱한 메시지가 먼저 뜨는 걸 테스트로 확인했음.
_DEFAULT_MINUTE_LIMIT = 15
_DEFAULT_RESULT_CACHE_TTL = 60 * 15  # 15분


def _minute_limit() -> int:
    return getattr(settings, 'AI_VALIDATION_MINUTE_LIMIT', _DEFAULT_MINUTE_LIMIT)


def _result_cache_ttl() -> int:
    return getattr(settings, 'AI_VALIDATION_RESULT_CACHE_TTL', _DEFAULT_RESULT_CACHE_TTL)


def is_paid_user(user) -> bool:
    """등급 판정도 한 곳에서만 한다."""
    return quota.is_paid(user)


def _daily_limit_for(user) -> int:
    return quota.limit_for(user, FEATURE)


def _daily_used(user) -> int:
    """오늘 실제로 차감된 횟수."""
    return quota.used(user, FEATURE)


def _charge(user) -> None:
    quota.charge(user, FEATURE)


def get_usage(user) -> dict:
    """
    현재 사용량을 차감 없이 조회한다. 버튼을 누르기 전에도 화면에
    "오늘 N/한도회 사용"을 보여줄 수 있게 별도로 분리해뒀다.
    """
    return {'daily_used': _daily_used(user), 'daily_limit': _daily_limit_for(user),
            'is_paid': is_paid_user(user)}


def check_rate_limit(user) -> tuple[bool, dict]:
    """
    계정별 AI검증 요청 한도를 확인하고, 통과하면 카운터를 증가시킨다.

    Returns: (허용 여부, usage 정보 dict)
      usage = {'daily_used': int, 'daily_limit': int, 'is_paid': bool, 'message': str}
      허용된 경우 daily_used는 "이번 요청 포함" 값이고 message는 빈 문자열,
      차단된 경우 daily_used는 이미 다 쓴 상태 그대로고 message에 사유가 담긴다.
    """
    limit = _daily_limit_for(user)
    now = timezone.now()
    minute_key = f'ai_validation:rl:min:{user.id}:{now.strftime("%Y%m%d%H%M")}'

    day_count = _daily_used(user)
    if day_count >= limit:
        return False, {
            'daily_used': day_count, 'daily_limit': limit, 'is_paid': is_paid_user(user),
            'message': f'오늘의 AI검증 요청 한도({limit}회)를 모두 사용했습니다. 내일 다시 이용해주세요.',
        }

    minute_count = cache.get(minute_key) or 0
    if minute_count >= _minute_limit():
        return False, {
            'daily_used': day_count, 'daily_limit': limit, 'is_paid': is_paid_user(user),
            'message': '짧은 시간에 요청이 너무 많았습니다. 1분 후 다시 시도해주세요.',
        }

    # 통과 — 소비 기록. 분당 한도는 연타를 막는 조용한 안전장치라 캐시로 충분하다
    # (사라져도 일일 한도가 남는다). 일일 한도만 DB 에 남긴다.
    cache.set(minute_key, minute_count + 1, timeout=70)
    _charge(user)
    return True, {
        'daily_used': day_count + 1, 'daily_limit': limit, 'is_paid': is_paid_user(user),
        'message': '',
    }


def _content_fingerprint(label) -> str:
    """
    검증 결과에 실제로 영향을 주는 필드만 모아 해시. 저장 시각처럼
    무관한 필드는 넣지 않아, 내용이 안 바뀌었으면 캐시가 항상 맞는다.

    필수 입력 검사(validation_service.check_required_fields)가 붙으면서 표시
    여부 체크박스와 그 대응 필드 전부가 판정에 영향을 준다. 여기에 넣지 않으면
    소비기한을 채우고 다시 검증해도 캐시 TTL(15분) 동안 "미입력" 결과가 그대로
    나온다.
    """
    from .validation_service import _REQUIRED_CHECKBOX_FIELDS, content_sources

    fields = [
        label.rawmtrl_nm_display or '', label.rawmtrl_nm or '',
        label.prdlst_nm or '', label.content_weight or '',
        label.ingredient_info or '', label.cautions or '',
        label.additional_info or '', label.allergens or '',
        label.frmlc_mtrqlt or '', label.prv_recycling_mark_type or '',
    ]
    for checkbox in _REQUIRED_CHECKBOX_FIELDS:
        fields.append(getattr(label, checkbox, '') or '')
        # 그 항목의 값을 담을 수 있는 자리 전부. 다른 탭이 채우는 곳(영양성분
        # 개별 항목, 내용량에 병기한 열량 등)을 빠뜨리면, 채우고 다시 검증해도
        # 캐시 TTL(15분) 동안 "미입력" 결과가 그대로 나온다.
        for src in content_sources(checkbox[len('chckd_'):]):
            fields.append(getattr(label, src, '') or '')

    raw = '\x1f'.join(fields)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _result_cache_key(label) -> str:
    return f'ai_validation:result:{label.pk}:{_content_fingerprint(label)}'


def get_cached_result(label) -> dict | None:
    """라벨 내용이 그대로라면 최근 AI검증 결과를 반환 (없으면 None)."""
    return cache.get(_result_cache_key(label))


def set_cached_result(label, result: dict) -> None:
    cache.set(_result_cache_key(label), result, timeout=_result_cache_ttl())
