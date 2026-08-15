"""
AI검증(OpenAI 호출) 비용 관리 — 동일 요청 캐싱 + 계정별 요청 제한.

두 가지 메커니즘을 분리해서 둔다:
  1. 콘텐츠 해시 캐싱: 라벨 내용이 그대로인데 다시 누르면 OpenAI를
     재호출하지 않고 최근 결과를 그대로 반환한다 — 사용자가 결과 보고
     그냥 다시 눌러보는 흔한 패턴에서 비용이 0이 된다.
  2. 계정별 rate limit: 분당/일일 한도로 연타·남용을 막는다.

기존 프로젝트 관례(MOBILE_MAX_NOTIFICATIONS 등, settings.py 상수 +
config() 환경변수 오버라이드)를 그대로 따랐고, 저장소는 이미 설정된
파일 기반 캐시(CACHES['default'])를 재사용해 별도 인프라가 필요 없다.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

# 기본값은 settings.py에서 오버라이드 가능 (AI_VALIDATION_MINUTE_LIMIT,
# AI_VALIDATION_DAILY_LIMIT, AI_VALIDATION_RESULT_CACHE_TTL)
_DEFAULT_MINUTE_LIMIT = 5
_DEFAULT_DAILY_LIMIT = 30
_DEFAULT_RESULT_CACHE_TTL = 60 * 15  # 15분


def _minute_limit() -> int:
    return getattr(settings, 'AI_VALIDATION_MINUTE_LIMIT', _DEFAULT_MINUTE_LIMIT)


def _daily_limit() -> int:
    return getattr(settings, 'AI_VALIDATION_DAILY_LIMIT', _DEFAULT_DAILY_LIMIT)


def _result_cache_ttl() -> int:
    return getattr(settings, 'AI_VALIDATION_RESULT_CACHE_TTL', _DEFAULT_RESULT_CACHE_TTL)


def check_rate_limit(user_id) -> tuple[bool, str]:
    """
    계정별 AI검증 요청 한도를 확인하고, 통과하면 카운터를 증가시킨다.

    Returns: (허용 여부, 차단 시 사용자에게 보여줄 메시지)
    """
    now = timezone.now()
    minute_key = f'ai_validation:rl:min:{user_id}:{now.strftime("%Y%m%d%H%M")}'
    day_key = f'ai_validation:rl:day:{user_id}:{now.strftime("%Y%m%d")}'

    minute_count = cache.get(minute_key) or 0
    if minute_count >= _minute_limit():
        return False, '짧은 시간에 AI검증 요청이 너무 많았습니다. 1분 후 다시 시도해주세요.'

    day_count = cache.get(day_key) or 0
    if day_count >= _daily_limit():
        return False, f'오늘의 AI검증 요청 한도({_daily_limit()}회)에 도달했습니다. 내일 다시 이용해주세요.'

    # 통과 — 카운터 증가 (완벽한 원자성은 아니지만 rate limit 용도로는 충분)
    cache.set(minute_key, minute_count + 1, timeout=70)
    cache.set(day_key, day_count + 1, timeout=60 * 60 * 26)  # 자정 경계 여유
    return True, ''


def _content_fingerprint(label) -> str:
    """
    검증 결과에 실제로 영향을 주는 필드만 모아 해시. 저장 시각처럼
    무관한 필드는 넣지 않아, 내용이 안 바뀌었으면 캐시가 항상 맞는다.
    """
    fields = [
        label.rawmtrl_nm_display or '', label.rawmtrl_nm or '',
        label.prdlst_nm or '', label.content_weight or '',
        label.ingredient_info or '', label.cautions or '',
        label.additional_info or '', label.allergens or '',
        label.frmlc_mtrqlt or '', label.prv_recycling_mark_type or '',
    ]
    raw = '\x1f'.join(fields)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _result_cache_key(label) -> str:
    return f'ai_validation:result:{label.pk}:{_content_fingerprint(label)}'


def get_cached_result(label) -> dict | None:
    """라벨 내용이 그대로라면 최근 AI검증 결과를 반환 (없으면 None)."""
    return cache.get(_result_cache_key(label))


def set_cached_result(label, result: dict) -> None:
    cache.set(_result_cache_key(label), result, timeout=_result_cache_ttl())
