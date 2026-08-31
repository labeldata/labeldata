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
# 프롬프트에 넣을 글자 혼동 쌍의 수. 너무 많으면 "이 글자를 저 글자로 바꿔라" 로
# 읽혀서 오히려 멀쩡한 글자를 고치게 된다.
MAX_CONFUSIONS = 12

_CACHE_KEY = 'ocr:correction_hints'
_CACHE_TTL = 60 * 30      # 교정은 천천히 쌓인다. 30분이면 충분하다.


def record(user, field, ocr_value, final_value, confidence='', model='',
           variant='', source=''):
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
            variant=(variant or '')[:20],
            source=(source or '')[:20],
        )
    except Exception:
        logger.exception('판독 교정 이력 기록 실패 (field=%s)', field)
        return None


def _normalize(text):
    return ' '.join((text or '').split())


def _squeeze(text):
    """비교용. 띄어쓰기 하나 차이로 다른 사례가 되면 아무것도 안 묶인다."""
    return ''.join((text or '').split()).lower()


def _correction_rows(limit=600):
    """최근 교정 이력 (판독값, 고친값) 원본. 묶는 일은 파이썬에서 한다."""
    from v1.common.models import OcrCorrection

    try:
        return list(
            OcrCorrection.objects
            .filter(corrected=True)
            .exclude(ocr_value='').exclude(final_value='')
            .order_by('-created_at')
            .values('field', 'ocr_value', 'final_value')[:limit])
    except Exception:
        logger.exception('판독 교정 이력 조회 실패')
        return []


def build_hints():
    """
    자주 틀리는 패턴을 프롬프트에 넣을 문장으로 만든다.

    **묶어서 센다.** 예전에는 (항목, 판독값, 고친값) 세 값이 **완전히 같은** 교정만
    2회 이상일 때 힌트가 됐다. 그런데 실제 오독은 매번 조금씩 다르다 — "송정동" 을
    한 번은 "성정동", 한 번은 "송전동" 으로 읽으면 각각 1회라 영영 힌트가 안 된다.
    운영에서 힌트가 거의 안 붙던 이유가 이것이다.

    그래서 **같은 항목에서 같은 정답으로 고쳐진 것**을 한 덩어리로 본다. 판독값이
    서로 달라도 "이 자리에서 이 값을 자꾸 틀린다" 는 같은 사실이다. 덩어리의 합이
    2회 이상이면 힌트로 쓰고, 판독값은 대표 두 개만 보여 준다.
    """
    clusters = {}
    for row in _correction_rows():
        before, after = _normalize(row['ocr_value']), _normalize(row['final_value'])
        if not before or not after or _squeeze(before) == _squeeze(after):
            continue
        if len(before) > MAX_HINT_LEN or len(after) > MAX_HINT_LEN:
            continue
        key = (row['field'], _squeeze(after))
        bucket = clusters.setdefault(
            key, {'field': row['field'], 'after': after, 'befores': [], 'count': 0})
        bucket['count'] += 1
        if before not in bucket['befores']:
            bucket['befores'].append(before)

    hints = []
    for bucket in sorted(clusters.values(), key=lambda b: -b['count']):
        if bucket['count'] < 2:
            continue
        hints.append({
            'field': bucket['field'],
            'before': ' / '.join(bucket['befores'][:2]),
            'after': bucket['after'],
            'count': bucket['count'],
        })
        if len(hints) >= MAX_HINTS:
            break
    return hints


def char_confusions(min_count=2, limit=MAX_CONFUSIONS):
    """
    글자 단위로 무엇을 무엇과 헷갈리는지 센다 (문자 혼동 행렬).

    값 전체를 통으로 세면 사례마다 달라 아무것도 안 남지만, **바뀐 글자만** 떼어
    모으면 같은 혼동이 반복된다. 실제로 라벨에서는 획 하나 차이가 흔하다 —
    립/집, 송/성, 0/O, ㎖/㎗.

    한 글자 치환만 센다. 여러 글자가 통째로 바뀐 것은 오독이 아니라 다른 값을
    읽은 것이라, 글자 혼동으로 일반화하면 엉뚱한 것을 가르치게 된다.

    Returns: [{'from', 'to', 'count'} …] 잦은 순
    """
    try:
        from rapidfuzz.distance import Levenshtein
    except ImportError:
        return []

    pairs = {}
    for row in _correction_rows():
        before, after = _normalize(row['ocr_value']), _normalize(row['final_value'])
        if not before or not after:
            continue
        if len(before) > MAX_HINT_LEN or len(after) > MAX_HINT_LEN:
            continue
        try:
            ops = Levenshtein.opcodes(before, after)
        except Exception:
            continue

        edits = [op for op in ops if op.tag != 'equal']
        # 고친 자리가 너무 많으면 값을 통째로 갈아 끼운 것이다. 그런 사례에서
        # 글자 혼동을 캐면 우연히 겹친 글자쌍을 배우게 된다.
        if not edits or len(edits) > 3:
            continue
        for op in edits:
            if op.tag != 'replace':
                continue
            src = before[op.src_start:op.src_end]
            dst = after[op.dest_start:op.dest_end]
            if len(src) != 1 or len(dst) != 1 or src == dst:
                continue
            if src.isspace() or dst.isspace():
                continue
            pairs[(src, dst)] = pairs.get((src, dst), 0) + 1

    out = [{'from': src, 'to': dst, 'count': n}
           for (src, dst), n in pairs.items() if n >= min_count]
    return sorted(out, key=lambda r: -r['count'])[:limit]


def hints_text(use_cache=True):
    """
    프롬프트에 붙일 문단. 쌓인 게 없으면 빈 문자열.

    두 종류를 붙인다.
      값 단위   "이 자리에서 이 값을 자꾸 틀린다"
      글자 단위 "이 글자를 저 글자로 자꾸 읽는다"

    둘은 겹치지 않는다. 값 단위는 같은 제품이 여러 번 올라와야 쌓이고, 글자
    단위는 서로 다른 제품에서도 쌓인다 — 데이터가 적을 때 먼저 힘을 낸다.

    매 판독마다 집계하지 않도록 캐시한다. 교정은 천천히 쌓이므로 30분이면 된다.
    """
    if use_cache:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached

    hints = build_hints()
    confusions = char_confusions()

    lines = []
    if hints:
        lines += ['', '지금까지 이 자리에서 자주 틀렸다. 같은 실수를 하지 마시오.']
        for h in hints:
            lines.append(f'- {h["field"]}: "{h["before"]}" 로 잘못 읽은 적이 '
                         f'{h["count"]}번 있다. 실제로는 "{h["after"]}" 였다.')
        lines.append('이 값을 그대로 쓰라는 뜻이 아니다. 이런 자리에서 이런 식으로 '
                     '틀린다는 것을 알고 더 주의 깊게 읽으라는 뜻이다.')

    if confusions:
        listed = ', '.join(f'"{c["from"]}"→"{c["to"]}"({c["count"]}회)'
                           for c in confusions)
        lines += [
            '',
            '아래 글자들을 실제로 자주 헷갈렸다. 이 글자가 나오면 획을 하나씩 '
            '확인하시오.',
            f'- {listed}',
            '왼쪽이 잘못 읽은 글자이고 오른쪽이 실제 글자다. 오른쪽으로 무조건 '
            '바꾸라는 뜻이 아니라, 그 자리를 더 크게 보고 판단하라는 뜻이다.',
        ]

    text = '\n'.join(lines) if lines else ''
    if use_cache:
        cache.set(_CACHE_KEY, text, _CACHE_TTL)
    return text


def invalidate():
    """새 교정이 들어오면 다음 판독부터 반영되게 한다."""
    cache.delete(_CACHE_KEY)


def accuracy_stats(days=None, group='field', **filters):
    """
    정답률 집계. 프롬프트·모델·방식을 바꾼 뒤 나아졌는지 재는 데 쓴다.

    group 으로 무엇을 기준으로 묶을지 정한다.
      'field'    항목별 (기본)
      'model'    모델별   — gpt-4o-mini 와 gpt-4o 비교
      'variant'  방식별   — 영역 선택(crop) 과 전체(whole) 비교
      'source'   출처별   — 사진만(photo) / 등록 정보로 채움(api) /
                            둘이 일치(both) / 둘이 다름(conflict) 비교

    Returns: [{key, total, corrected, rate}, ...] 정답률 낮은 순.
    """
    from datetime import timedelta

    from django.db.models import Count, Q
    from django.utils import timezone

    from v1.common.models import OcrCorrection

    qs = OcrCorrection.objects.all()
    if days:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
    for key, value in filters.items():
        if value:
            qs = qs.filter(**{key: value})

    rows = (qs.values(group)
            .annotate(total=Count('id'), wrong=Count('id', filter=Q(corrected=True)))
            .order_by())
    out = []
    for row in rows:
        total = row['total'] or 0
        wrong = row['wrong'] or 0
        out.append({
            'key': row[group] or '(없음)',
            'field': row[group] or '(없음)',   # 예전 이름도 남겨 둔다
            'total': total,
            'corrected': wrong,
            'rate': round((total - wrong) / total * 100, 1) if total else 0.0,
        })
    return sorted(out, key=lambda r: (r['rate'], -r['total']))


def image_fingerprint(data):
    """같은 사진을 여러 번 읽었는지 묶어 보기 위한 지문."""
    return hashlib.sha256(data).hexdigest()[:16]
