"""
판독 결과를 사용자가 어떻게 고쳤는지 모아, 다음 판독에 되먹인다.

튜닝(fine-tuning)을 하려면 원본과 정답의 쌍이 수백 건은 있어야 하는데, 지금은
그 쌍이 한 건도 안 쌓이고 있었다. 그래서 두 걸음으로 나눈다.

  1. 쌓는다   확인 창에서 사용자가 고친 값을 기록한다. 고치지 않은 것도 남긴다 -
              정답률을 재려면 맞은 것도 세야 한다.
  2. 쓴다     자주 틀리는 항목의 교정 쌍을 프롬프트에 예시로 넣는다.
              모델을 바꾸지 않고도 같은 실수를 덜 하게 만든다.

쌓인 데이터는 나중에 실제 튜닝을 할 때 그대로 학습셋이 된다.

**프롬프트에 넣는 것은 "고친 사실" 이지 "정답" 이 아니다.** 같은 라벨을 다시
읽으라는 뜻이 아니라, 이런 자리에서 이런 식으로 틀린다는 것을 알려 주는 것이다.
"""
import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# 프롬프트에 넣을 예시 수. 너무 많으면 지시가 묻히고 토큰만 먹는다.
MAX_HINTS = 8
# 이 길이를 넘는 값은 예시로 쓰지 않는다 - 원재료명 300자를 통째로 넣을 수 없다
MAX_HINT_LEN = 60

_CACHE_KEY = 'ocr:correction_hints'
_CACHE_TTL = 60 * 30      # 교정은 천천히 쌓인다. 30분이면 충분하다.


def record(user, field, ocr_value, final_value, confidence='', model=''):
    """
    한 항목의 판독 결과와 사용자가 실제로 쓴 값을 남긴다.

    실패해도 조용히 넘어간다 - 기록이 안 됐다고 불러오기가 멈추면 안 된다.
    """
    from v1.common.models import OcrCorrection

    ocr_value = (ocr_value or '').strip()
    final_value = (final_value or '').strip()
    if not ocr_value and not final_value:
        return None
    try:
        return OcrCorrection.objects.create(
            user=user,
            field=field[:40],
            ocr_value=ocr_value,
            final_value=final_value,
            corrected=(ocr_value != final_value),
            confidence=(confidence or '')[:10],
            model=(model or '')[:40],
        )
    except Exception:
        logger.exception('판독 교정 이력 기록 실패 (field=%s)', field)
        return None


def _normalize(text):
    return ' '.join((text or '').split())


def build_hints():
    """
    자주 틀리는 패턴을 프롬프트에 넣을 문장으로 만든다.

    같은 (항목, 판독값 -> 고친값) 쌍이 여러 번 나온 것만 쓴다. 한 번뿐인 교정은
    그 라벨 사정일 수 있어 일반화하면 오히려 해롭다.
    """
    from django.db.models import Count
    from v1.common.models import OcrCorrection

    try:
        rows = (OcrCorrection.objects
                .filter(corrected=True)
                .exclude(ocr_value='')
                .exclude(final_value='')
                .values('field', 'ocr_value', 'final_value')
                .annotate(n=Count('id'))
                .filter(n__gte=2)
                .order_by('-n')[:MAX_HINTS * 3])
    except Exception:
        logger.exception('판독 힌트 조회 실패')
        return []

    hints = []
    for row in rows:
        before, after = _normalize(row['ocr_value']), _normalize(row['final_value'])
        if len(before) > MAX_HINT_LEN or len(after) > MAX_HINT_LEN:
            continue
        if before == after:
            continue
        hints.append({'field': row['field'], 'before': before,
                      'after': after, 'count': row['n']})
        if len(hints) >= MAX_HINTS:
            break
    return hints


def hints_text(use_cache=True):
    """
    프롬프트에 붙일 문단. 쌓인 게 없으면 빈 문자열.

    매 판독마다 집계하지 않도록 캐시한다. 교정은 천천히 쌓이므로 30분이면 된다.
    """
    if use_cache:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached

    hints = build_hints()
    if not hints:
        text = ''
    else:
        lines = ['', '지금까지 이 자리에서 자주 틀렸다. 같은 실수를 하지 마시오.']
        for h in hints:
            lines.append(f'- {h["field"]}: "{h["before"]}" 로 잘못 읽은 적이 '
                         f'{h["count"]}번 있다. 실제로는 "{h["after"]}" 였다.')
        lines.append('이 값을 그대로 쓰라는 뜻이 아니다. 이런 자리에서 이런 식으로 '
                     '틀린다는 것을 알고 더 주의 깊게 읽으라는 뜻이다.')
        text = '\n'.join(lines)

    if use_cache:
        cache.set(_CACHE_KEY, text, _CACHE_TTL)
    return text


def invalidate():
    """새 교정이 들어오면 다음 판독부터 반영되게 한다."""
    cache.delete(_CACHE_KEY)


def accuracy_stats(days=None):
    """
    항목별 정답률. 프롬프트를 고친 뒤 나아졌는지 재는 데 쓴다.

    Returns: [{field, total, corrected, rate}, ...] 틀린 비율이 높은 순.
    """
    from datetime import timedelta

    from django.db.models import Count, Q
    from django.utils import timezone

    from v1.common.models import OcrCorrection

    qs = OcrCorrection.objects.all()
    if days:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

    rows = (qs.values('field')
            .annotate(total=Count('id'), wrong=Count('id', filter=Q(corrected=True)))
            .order_by())
    out = []
    for row in rows:
        total = row['total'] or 0
        wrong = row['wrong'] or 0
        out.append({
            'field': row['field'],
            'total': total,
            'corrected': wrong,
            'rate': round((total - wrong) / total * 100, 1) if total else 0.0,
        })
    return sorted(out, key=lambda r: (r['rate'], -r['total']))


def image_fingerprint(data):
    """같은 사진을 여러 번 읽었는지 묶어 보기 위한 지문."""
    return hashlib.sha256(data).hexdigest()[:16]
