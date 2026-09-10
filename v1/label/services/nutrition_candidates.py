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


def variants(key):
    """
    견줄 이름을 여러 벌 만든다. **한국어 원료명은 뒷말이 품목을 말한다.**

    실제 원료명에는 브랜드가 앞에 붙는다('오늘좋은 생크림'). 전체 이름끼리만
    견주면 브랜드가 점수를 지배해 엉뚱한 것이 올라온다.

        '오늘좋은 생크림' vs '오늘좋은 생소면'   75 점
        '오늘좋은 생크림' vs '생크림'            54 점

    실제로 이 원료의 후보가 생소면·생칼국수·생와사비·두부로 나왔다. 브랜드가
    같은 다른 품목들이다.

    그래서 뒤에서부터 잘라 낸 조각도 함께 견준다. '생크림' 으로 견주면
    제자리를 찾는다. 앞말(브랜드)만 남는 조각은 만들지 않는다 — 그것으로
    견주면 다시 브랜드가 이긴다.
    """
    key = (key or '').strip()
    if not key:
        return []
    out = [key]
    parts = key.split()
    # 뒤에서부터 한 토막씩 (['가','나','다'] → '나 다', '다')
    for i in range(1, len(parts)):
        tail = ' '.join(parts[i:])
        if len(tail) >= _MIN_TOKEN:
            out.append(tail)
    return out


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

    query_key 는 한 벌이 아니라 여러 벌이 올 수 있다(variants). 브랜드가 앞에
    붙은 이름은 뒷말로 견줘야 제자리를 찾기 때문이다.
    """
    keys = query_key if isinstance(query_key, (list, tuple)) else [query_key]
    b = normalize(row_name)
    best = 0
    for a in keys:
        best = max(best, fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))
    return best


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


# 한 번에 훑어볼 최대 행 수. 이름이 흔하면(‘버터’ 는 3,999 건) 다 볼 필요가 없다.
_POOL_CAP = 800


def _pool(key):
    """
    이름으로 후보를 긁어 온다. **두 걸음으로 나눈다.**

    한 걸음으로 하면 13 초가 걸렸다. 이 표에는 원문을 통째로 담은 raw(JSON)
    칸이 있어 행 하나가 무겁고, LIKE '%…%' 는 인덱스를 못 타므로 표 전체를
    읽게 되기 때문이다. 재 보면 이렇다.

        contains + count()            0.19 초   ← 인덱스만 훑는다
        contains + 행 가져오기          9.8 초   ← raw 까지 읽는다

    그래서 먼저 **id 만** 뽑고(InnoDB 보조 인덱스는 PK 를 품고 있어 인덱스만
    읽으면 된다), 그 id 로 행을 가져온다. 0.2 초로 떨어진다.

    basis_unit·calories 같은 조건도 SQL 에 넣지 않는다. 넣는 순간 옵티마이저가
    계획을 바꿔 이름 인덱스를 버리고 9.5 초가 된다(같은 질의가 조건 하나에
    0.15 초 → 9.5 초로 뛴다). 800 행을 파이썬에서 거르는 편이 훨씬 싸다.

    **가까운 것부터 담는다.** 800 개로 끊을 것이므로 담는 순서가 곧 정확도다.
    '버터' 는 이름에 그 두 글자가 든 행이 3,999 건이라, 아무렇게나 800 개를
    담으면 정작 '버터' 라는 행이 안 들어와 1 위가 '땅콩버터' 가 된다.
    그래서 정확 일치 → 앞부분 일치 → 부분 일치 순으로 채운다.
    """
    keys = variants(key)

    contains_q = Q()
    for k in keys:
        contains_q |= Q(food_nm_kr__contains=k)

    conds = []
    for k in keys:                                # 짧은 뒷말일수록 나중에
        conds.append(Q(food_nm_kr=k))             # 정확히 같은 이름
    for k in keys:
        conds.append(Q(food_nm_kr__startswith=k))  # 앞부분이 같은 이름
    conds.append(contains_q)                       # 어딘가에 든 이름

    ids, seen = [], set()
    for cond in conds:
        if len(ids) >= _POOL_CAP:
            break
        room = _POOL_CAP - len(ids)
        for pk in (PublicFoodNutrition.objects.filter(cond)
                   .values_list('id', flat=True)[:room + len(seen)]):
            if pk in seen:
                continue
            seen.add(pk)
            ids.append(pk)
            if len(ids) >= _POOL_CAP:
                break

    if not ids:
        return []
    # raw 는 빼고 가져온다 — 후보를 고르는 데 원문은 쓰지 않는다
    return list(PublicFoodNutrition.objects.filter(id__in=ids).defer('raw'))


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

    pool = _pool(key)
    keys = variants(key)

    scored = []
    for row in pool:
        # 쓸 수 없는 행은 여기서 거른다. 이 조건들을 SQL 에 넣으면 안 된다
        # — 아래 _pool 의 주석 참고.
        if row.basis_unit != PublicFoodNutrition.BASIS_G:
            continue
        if row.calories is None:
            continue
        if row.verify_status == PublicFoodNutrition.VERIFY_FAIL:
            continue

        ns = name_score(keys, row.food_nm_kr)
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


def auto_link(ingredient):
    """
    품목제조보고번호로 딱 떨어지는 행을 찾는다. 없으면 None.

    번호가 맞으면 사람에게 묻지 않는다 — 같은 번호는 같은 품목이라 고를 것이
    없다. 실측으로는 원료 172 개 중 18 개가 이 길로 붙었다(고유번호 75 개 중
    24 %). 나머지는 번호가 아예 없거나 식약처 DB 에 그 품목이 없다.

    숫자가 아닌 번호('2020_DNSP_04044')는 조인 키로 쓰지 않는다 — 우리
    MyIngredient 쪽은 숫자만 들고 있어 억지로 맞추면 엉뚱한 원료에 붙는다.
    """
    no = (getattr(ingredient, 'prdlst_report_no', '') or '').strip()
    if not no or not no.isdigit():
        return None
    return (PublicFoodNutrition.objects
            .filter(item_report_no=no, basis_unit=PublicFoodNutrition.BASIS_G)
            .exclude(calories__isnull=True)
            .exclude(verify_status=PublicFoodNutrition.VERIFY_FAIL)
            .order_by('-crt_mth_nm', '-research_ymd')
            .first())


def for_ingredient(ingredient, limit=TOP_N):
    """
    원료 하나를 두고 화면이 필요한 것을 한 번에 모아 준다.

    Returns
        auto        보고번호로 찾은 행 (없으면 None)
        candidates  이름으로 추린 후보 (auto 가 있으면 비운다 — 물을 것이 없다)
        warning     후보끼리 값이 크게 갈릴 때의 경고
    """
    auto = auto_link(ingredient)
    if auto is not None:
        return {'auto': auto, 'candidates': [], 'warning': None}

    cands = candidates(getattr(ingredient, 'prdlst_nm', '') or '', limit=limit)
    return {'auto': None, 'candidates': cands, 'warning': spread_warning(cands)}


def row_values(row, fields):
    """식약처 행에서 우리 성분 이름으로 값을 뽑는다."""
    return {f: getattr(row, f, None) for f in fields}
