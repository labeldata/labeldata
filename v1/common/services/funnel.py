# -*- coding: utf-8 -*-
"""
사용자가 어디까지 오고 어디서 새는가.

**지금까지 아무것도 재지 않았다.** 기능을 고치고 "좋아졌을 것" 이라고 말해
왔는데, 좋아졌는지 나빠졌는지 알 방법이 없었다. 넷만 정한다 — 늘리면 아무도
안 본다.

    ① 첫 검증까지 걸린 시간    이 값이 곧 "쓸모를 느낀 시점" 이다
    ② 단계별 이탈률            구멍이 제품인지 BOM 인지 검증인지 가른다
    ③ 7일 / 28일 재방문        돌아올 이유가 듣는지
    ④ 원료당 영양성분 보유율   영양성분 쪽 일이 듣는지

넷 다 **지금 데이터로 낼 수 있다.** 새로 심을 것이 없다 — UserActivityLog 가
이미 제품 생성·BOM 저장·검증을 적고 있다.

세는 법에 대하여
────────────────
**사람 수를 센다. 행동 수가 아니다.** 제품을 백 개 만든 한 사람과 한 개씩
만든 백 사람은 전혀 다른 이야기인데, 행동을 세면 둘이 같아 보인다.

**게스트는 뺀다.** 둘러보는 사람은 24 시간 뒤에 사라지고, 그 계정이 재방문할
길은 없다. 섞으면 재방문율이 영문 모르게 낮아진다.
"""
import logging

logger = logging.getLogger(__name__)

# 깔때기의 단계. 순서가 곧 사용자가 지나는 길이다.
STEPS = (
    ('가입',     None),
    ('첫 제품',  'product_create'),
    ('첫 BOM',   'bom_save'),
    ('첫 검증',  'validation_nutrition'),
)


def _human_users():
    """게스트를 뺀 사람들."""
    from django.contrib.auth.models import User

    from v1.common.guest import GUEST_PREFIX, LEGACY_GUEST_EMAIL

    return (User.objects.exclude(username__startswith=GUEST_PREFIX)
                        .exclude(username=LEGACY_GUEST_EMAIL))


def funnel(days=90):
    """
    단계마다 **몇 사람이 닿았는가.**

    기준은 가입한 사람이다. 가입일이 기간 안인 사람만 센다 — 안 그러면 옛
    사용자가 분모에 쌓여 최근에 무엇이 달라졌는지 안 보인다.
    """
    from django.utils import timezone

    from v1.activity_log.models import UserActivityLog

    since = timezone.now() - timezone.timedelta(days=days)
    joined = set(_human_users().filter(date_joined__gte=since)
                 .values_list('id', flat=True))
    base = len(joined)

    out = []
    prev = base
    for name, action in STEPS:
        if action is None:
            n = base
        else:
            n = len(set(UserActivityLog.objects
                        .filter(user_id__in=joined, action=action)
                        .values_list('user_id', flat=True)))
        # 앞 단계에서 여기로 못 온 비율. 구멍이 어디인지는 이 수가 말한다.
        #
        # **음수가 나올 수 있다.** 뒷 단계 사람이 앞 단계보다 많을 때다 —
        # 실제로 '첫 제품 4명, 첫 BOM 5명' 이 나왔다. 제품 생성이 기록되기
        # 전에 만들어진 제품이 있거나, 공유받은 제품에 BOM 만 넣은 경우다.
        # "-25% 이탈" 은 아무 뜻이 없으므로 0 으로 눕히고, 그런 일이 있었다는
        # 사실은 gained 로 따로 남긴다 — 숨기면 다음 사람이 같은 것을 또 본다.
        gap = prev - n
        out.append({
            'name': name,
            'users': n,
            'of_base': round(n * 100.0 / base, 1) if base else 0.0,
            'dropped': round(gap * 100.0 / prev, 1) if prev and gap > 0 else 0.0,
            'gained': gap < 0,
        })
        prev = n or prev
    return {'days': days, 'base': base, 'steps': out}


def time_to_first_validation(days=90, limit=400):
    """
    가입부터 첫 검증까지 며칠 걸렸나. (중앙값, 센 사람 수)

    평균이 아니라 **중앙값**이다. 한 사람이 반년 뒤에 들어와 검증하면 평균이
    통째로 끌려간다.
    """
    from django.db.models import Min
    from django.utils import timezone

    from v1.activity_log.models import UserActivityLog

    since = timezone.now() - timezone.timedelta(days=days)
    users = {u.id: u.date_joined
             for u in _human_users().filter(date_joined__gte=since)[:limit]}
    if not users:
        return None, 0

    first = (UserActivityLog.objects
             .filter(user_id__in=users, action='validation_nutrition')
             .values('user_id').annotate(at=Min('created_at')))
    spans = sorted((row['at'] - users[row['user_id']]).total_seconds() / 86400.0
                   for row in first if row['user_id'] in users)
    if not spans:
        return None, 0
    mid = len(spans) // 2
    median = spans[mid] if len(spans) % 2 else (spans[mid - 1] + spans[mid]) / 2
    return round(median, 1), len(spans)


def return_rate(days=90):
    """
    가입 뒤 7일·28일 안에 **다시 온** 사람의 비율.

    가입 당일의 활동은 재방문이 아니다. 그날은 누구나 쓴다.
    """
    from django.utils import timezone

    from v1.activity_log.models import UserActivityLog

    since = timezone.now() - timezone.timedelta(days=days)
    out = {}
    for window in (7, 28):
        # 창이 아직 안 닫힌 사람은 분모에서 뺀다. 가입 이틀째인 사람을
        # "28일 안에 안 왔다" 고 세면 비율이 영문 모르게 낮아진다.
        ripe = list(_human_users()
                    .filter(date_joined__gte=since,
                            date_joined__lte=timezone.now() - timezone.timedelta(days=window))
                    .values_list('id', 'date_joined'))
        if not ripe:
            out[window] = {'base': 0, 'came': 0, 'rate': 0.0}
            continue
        # **사람마다 한 번씩 묻지 않는다.**
        #
        # 처음에는 그렇게 썼다. 개발 PC 는 DB 가 같은 기계라 티가 안 났는데,
        # 운영은 DB 가 별도 호스트라 사람 수만큼 왕복이 곱해진다. 대시보드가
        # 첫 요청에서 넘어갔다.
        #
        # 한 번에 읽어 와서 파이썬에서 가른다. 창이 28일이라 줄 수가 뻔하고,
        # 사람별 가입일이 달라 SQL 한 방으로는 못 가른다.
        joined_at = dict(ripe)
        oldest = min(joined_at.values())
        rows = (UserActivityLog.objects
                .filter(user_id__in=joined_at,
                        created_at__gt=oldest,
                        created_at__lte=timezone.now())
                .values_list('user_id', 'created_at'))
        came_ids = set()
        for uid, at in rows.iterator(chunk_size=2000):
            j = joined_at.get(uid)
            if j is None or uid in came_ids:
                continue
            if j + timezone.timedelta(days=1) < at <= j + timezone.timedelta(days=window):
                came_ids.add(uid)
        came = len(came_ids)
        out[window] = {'base': len(ripe), 'came': came,
                       'rate': round(came * 100.0 / len(ripe), 1)}
    return out


def nutrition_coverage():
    """
    원료에 영양성분이 정해진 비율. 출처별로도 나눈다.

    등급이 붙는 자리라 출처를 함께 봐야 한다 — 공공 DB 로 채운 값은 영원히
    C 등급이고, A 를 만드는 길은 시험성적서뿐이다.
    """
    from django.db.models import Count

    from v1.label.models import MyIngredient, MyIngredientNutrition

    total = MyIngredient.objects.exclude(delete_YN='Y').count()
    rows = (MyIngredientNutrition.objects.values('source_kind')
            .annotate(n=Count('id')).order_by('-n'))
    by_source = {r['source_kind']: r['n'] for r in rows}
    have = sum(by_source.values())
    return {
        'total': total,
        'have': have,
        'rate': round(have * 100.0 / total, 1) if total else 0.0,
        'by_source': [
            {'kind': k,
             'label': dict(MyIngredientNutrition.SOURCE_CHOICES).get(k, k),
             'grade': MyIngredientNutrition.GRADE.get(k, '-'),
             'n': v}
            for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])
        ],
    }


def snapshot(days=90):
    """네 지표를 한 번에. 대시보드가 쓴다."""
    median, counted = time_to_first_validation(days)
    return {
        'days': days,
        'funnel': funnel(days),
        'first_validation_days': median,
        'first_validation_users': counted,
        'returns': return_rate(days),
        'nutrition': nutrition_coverage(),
    }
