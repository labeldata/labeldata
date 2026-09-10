"""
원료에 붙일 식약처 DB 행을 **고르게 한다.** 자동으로 정하지 않는다.

왜 자동 확정이 안 되는가
────────────────────────
'버터' 라는 이름으로 동명 항목이 열두 건인데 열량이 이렇게 갈린다.

    164 kcal · 지방  2.69 g · 수집 · 2025    ← 이걸 집으면 열량이 1/4.6 로 틀린다
    761 kcal · 지방 82.04 g · 분석 · 2014    ← 진짜 버터

이름이 **완전히 같다.** 어떤 유사도 알고리즘도 둘을 가르지 못한다. 유사도를
정교하게 만드는 것으로는 풀리지 않는 문제라, 사람이 한 번 고르게 하고 그
선택을 남긴다(MyIngredientNutrition.picked).

한 번만 묻는다. 원료 보관함 172 개 중 보고번호로 이미 붙은 것과, 배합비가
작아 물어볼 필요가 없는 것(nutrition_contrib)을 빼면 실제로 물을 것은 훨씬
적다.

순위는 이름이 먼저고 근거가 나중이다
────────────────────────────────────
이름 척도를 잘못 고르면 나머지가 다 무너진다. token_set_ratio 로 시작했다가
'버터' 1 위가 '사탕, 버터' 로, '밀가루' 1 위가 '밀가루 0 % 쌀국수' 로 나왔다
(name_score 의 주석 참고). 모든 후보가 100 점이라 이름이 순위에 아무 말도
하지 못한 탓이었다.

이름이 순위를 정하고, 아래 근거는 **동점을 가르는 데만** 쓴다. 적재본
319,060 건에 이미 들어와 있는 것들이다.

    데이터생성방법   수집 310,488 · 분석 5,355 · 산출 3,153
    출처명          식약처 314,852 · 수과원 1,094 · 농진청 약 1,400 · USDA/JAPAN 약 400
    생성일자        2019 ~ 2026

'버터' 는 동명이 열두 건이라 이름으로는 전부 100 점이다. 그때 '분석'(761 kcal)
이 '수집'(164 kcal) 보다 앞서게 하는 것이 이 가점의 일이다.
"""
import re

from django.db.models import Q
from rapidfuzz import fuzz

from v1.label.models import PublicFoodNutrition

# 규격·로트로 보이는 꼬리를 뗀다 ('한라봉향 FAC-HMT4733012', '모카향 2111041').
#
# 코드는 글자와 숫자가 섞인 **한 덩어리**다. 숫자 부분만 떼면 '한라봉향 FAC'
# 처럼 앞글자가 남아 견줄 때 방해가 된다. 그래서 덩어리째 문다.
#
# 숫자를 세 자리 넘게 요구하는 것이 안전장치다 — '비타민 B12'·'오메가3' 처럼
# 이름의 일부인 짧은 숫자는 건드리지 않는다.
_TAIL = re.compile(r'[\s\-_/]*[A-Za-z0-9][A-Za-z0-9\-_]*\d{3,}[A-Za-z0-9\-_]*\s*$')
_SPACE = re.compile(r'\s+')

# 후보를 몇 개까지 보여 줄 것인가. 많으면 고르는 일이 도로 일이 된다.
TOP_N = 5

# 후보를 추리는 1 차 그물. 이름에 이 조각이 들어간 행만 유사도를 잰다 —
# 319,060 건에 전부 유사도를 매기면 한 원료에 수 초가 걸린다.
_MIN_TOKEN = 2

# 이름 점수 문턱. ratio 는 군더더기를 깎으므로 token_set 보다 낮게 잡아야 한다
# ('설탕' vs '설탕_백설탕' 이 50 점이다 — 이건 붙어야 하는 짝이다).
_NAME_CUTOFF = 45

# 열량이 이 배 이상 벌어지는 후보가 섞여 있으면 경고한다.
# 버터가 4.6 배였고, 생크림 1.3 · 물엿 1.1 · 밀가루 1.0 은 조용하다.
SPREAD_WARN = 2.0


def normalize(name):
    """규격 꼬리를 떼고 견줄 수 있는 모양으로."""
    text = (name or '').strip()
    if not text:
        return ''
    for _ in range(3):
        stripped = _TAIL.sub('', text).strip()
        if stripped == text or not stripped:
            break
        text = stripped
    return _SPACE.sub(' ', text).lower()


def name_score(query_key, row_name):
    """
    이름이 얼마나 같은가. **군더더기를 깎는 척도를 쓴다.**

    처음에 token_set_ratio 를 썼다가 순위가 통째로 망가졌다. 이 척도는 짧은
    쪽이 긴 쪽의 부분집합이면 100 점을 주기 때문이다.

        '버터'  vs '사탕, 버터'                     token_set 100 · ratio 50
        '밀가루' vs '밀가루 0% 파프리카 쌀국수 표고맛'   token_set 100 · ratio 27

    그래서 '버터' 를 찾으면 사탕이 1 위로, '밀가루' 를 찾으면 밀가루가 0 % 인
    쌀국수가 1 위로 올라왔다. 모든 후보가 100 점이라 이름이 순위에 아무 말도
    하지 못했고, 남은 가점이 아무 관련 없는 기준으로 순서를 정했다.

    ratio 와 token_sort_ratio 는 둘 다 길이를 셈에 넣는다. 어순이 뒤바뀐
    이름을 놓치지 않도록 둘 중 큰 값을 쓴다.
    """
    a, b = query_key, normalize(row_name)
    return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))


def _rank_score(row, name_pts):
    """
    후보 순위 점수 = 이름 유사도 + 근거 가점.

    **가점은 동점을 가르는 데만 쓴다.** 처음에는 분석 +25 · 국가기관 +15 처럼
    크게 줬는데, 그러면 이름이 50 점 뒤진 후보가 가점으로 뒤집는다. 이름이
    먼저고 근거가 나중이다.

    폭은 실측 분포에 근거한 **출발점이지 검증된 값이 아니다.** 몇십 개 골라
    보며 1 순위 적중률을 재서 조정해야 한다.
    """
    score = float(name_pts)

    # 어떻게 만든 값인가 — 분석이 수집보다 믿을 만하다
    method = (row.crt_mth_nm or '')
    if method == '분석':
        score += 8
    elif method == '산출':
        score += 3

    # 누가 낸 값인가 — 국가기관 성분표가 업체 신고값보다 앞선다
    ref = (row.sub_ref_name or '')
    if any(k in ref for k in ('농진청', '수산과학원', 'USDA', 'JAPAN', '농촌진흥청')):
        score += 5

    # 언제 것인가
    year = (row.research_ymd or '')[:4]
    if year.isdigit():
        y = int(year)
        if y >= 2023:
            score += 2
        elif y <= 2018:
            score -= 2

    # 스스로 검산한 결과. 어긋난 행은 애초에 후보에서 빼지만, 남더라도 밀어낸다.
    if row.verify_status == PublicFoodNutrition.VERIFY_PASS:
        score += 3
    elif row.verify_status == PublicFoodNutrition.VERIFY_FAIL:
        score -= 50

    return score


def _reason(row):
    """왜 이 순위인지를 화면이 말할 수 있게 한 줄로."""
    bits = [row.crt_mth_nm or '?', (row.sub_ref_name or '?')[:14]]
    if row.research_ymd:
        bits.append(row.research_ymd[:4])
    return ' · '.join(bits)


def candidates(name, limit=TOP_N):
    """
    이 이름으로 붙일 만한 식약처 행을 순위대로 돌려준다.

    Returns  [{row, name_score, rank_score, reason}, ...]

    100 mL 기준 행은 후보에서 뺀다. 부피 기준이라 비중을 모르면 중량 배합에
    쓸 수 없다 — 골라 봐야 계산에 못 넣는다.
    """
    key = normalize(name)
    if not key:
        return []

    # 1 차 그물: 이름 조각으로 좁힌다
    tokens = [t for t in key.split() if len(t) >= _MIN_TOKEN] or [key]
    q = Q()
    for t in tokens:
        q |= Q(food_nm_kr__contains=t)

    pool = (PublicFoodNutrition.objects
            .filter(q, basis_unit=PublicFoodNutrition.BASIS_G)
            .exclude(calories__isnull=True)
            .exclude(verify_status=PublicFoodNutrition.VERIFY_FAIL)[:400])

    scored = []
    for row in pool:
        ns = name_score(key, row.food_nm_kr)
        if ns < _NAME_CUTOFF:
            continue
        scored.append({'row': row, 'name_score': ns,
                       'rank_score': _rank_score(row, ns), 'reason': _reason(row)})

    scored.sort(key=lambda c: -c['rank_score'])
    return scored[:limit]


def spread_warning(cands):
    """
    후보끼리 값이 크게 갈리면 알린다.

    순위를 잘 매겨도 사람이 잘못 고를 수 있다. 마지막 안전장치다 —
    2 배를 넘을 때만 말한다. 경고가 흔하면 아무도 보지 않는다.
    """
    vals = [c['row'].calories for c in cands if c['row'].calories]
    if len(vals) < 2:
        return None
    lo, hi = min(vals), max(vals)
    if lo <= 0 or hi / lo < SPREAD_WARN:
        return None
    return ('후보끼리 열량이 %.1f 배 차이난다 (%.0f ~ %.0f kcal) — '
            '같은 이름이지만 다른 물건일 수 있다' % (hi / lo, lo, hi))
