"""
규제 모니터링 Views
- 목록: 전체 부적합 뉴스 (내 제품 매칭 우선 정렬)
- 상세: 뉴스 상세 + AI 분석 + 영향받는 내 제품 목록
- API: 알림 카운트 (JSON), 읽음 처리 (POST)
"""
import hmac
import json
import logging
import re as _re
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Max, Q, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from v1.regulatory import selectors
from v1.regulatory.services import news_search
from v1.regulatory.services.collector import INSPECTION_BACKFILL_DAYS
from v1.regulatory.models import (
    AlertMute, NewsIngredientMatch, NewsKeywordMatch, NewsProductMatch,
    RegulatoryMatchAction, RegulatoryNews, InspectionResult, InspectionMatch,
    judgment_status_of, normalize_mute_value,
)
from v1.mobile.models import AlertRule
from v1.user_management.models import UserProfile
from v1.regulatory.saol_url_map import SAOL_URLS
from v1.activity_log.utils import log_activity

logger = logging.getLogger(__name__)

# API 서비스별 카테고리 정의 — 4그룹: 부적합 / 행정처분 / 새올민원 / 수거검사
API_CATEGORIES = [
    # ─── 부적합 ───────────────────────────────────────────────────────────────
    {'key': 'insp',       'label': '국내 검사부적합',   'group': 'insp',  'api_sources': ['I2620', 'I2640']},
    {'key': 'I0490',      'label': '국내 회수·판매중지', 'group': 'insp',  'api_sources': ['I0490']},
    {'key': 'imp_insp',   'label': '수입 부적합',        'group': 'insp',  'api_sources': ['imp_insp']},
    {'key': 'import',     'label': '수입 회수·판매중지', 'group': 'insp',  'api_sources': ['import']},
    # ─── 행정처분 (중앙 OpenAPI) ──────────────────────────────────────────────
    {'key': 'admin',      'label': '국내 행정처분',      'group': 'admin', 'api_sources': ['I0470', 'I0480']},
    {'key': 'I0482',      'label': '수입 행정처분',       'group': 'admin', 'api_sources': ['I0482']},
    # ─── 새올민원 (지자체) ────────────────────────────────────────────────────
    {'key': 'saol_admin', 'label': '지자체 행정처분',    'group': 'saol',  'api_sources': ['saol_admin']},
    # ─── 수거검사 (I0460) — InspectionResult 별도 모델 ───────────────────────
    {'key': 'I0460',      'label': '내 수거검사 현황',   'group': 'insp46', 'api_sources': []},
]
_ALL_CAT_KEYS     = [c['key'] for c in API_CATEGORIES]
_REGULAR_CAT_KEYS = [c['key'] for c in API_CATEGORIES if c['group'] != 'insp46']

# 어떤 출처가 '행정처분' 탭에 속하는가 — 탭 배지·목록 범위·탭별 읽음 처리가
# 모두 이 한 줄을 본다. 예전에는 목록 뷰 안에만 있어서, 탭 단위 처리를 새로
# 붙일 때마다 같은 목록을 손으로 다시 적어야 했다.
ADMIN_API_SOURCES = {'I0470', 'I0480', 'I0482', 'saol_admin'}

# 화면의 탭 키 — 목록·읽음 처리·배지가 같은 이름을 쓴다
TAB_INSP_NEWS = 'insp-news'   # 부적합
TAB_ADMIN     = 'admin'       # 행정처분
TAB_INSPECTION = 'insp'       # 수거검사
NEWS_TABS = (TAB_INSP_NEWS, TAB_ADMIN)

# 기본 화면에서 목록 위에 고정해 보여 줄 '내 알림' 건수.
# 다섯 건이면 "새로 온 것이 있나" 를 확인하기에 충분하고, 목록의 나머지는
# 일반 알림에 남는다.
PINNED_MATCH_LIMIT = 5


class _CountedPaginator(Paginator):
    """
    총 건수를 이미 아는 목록용 Paginator.

    Paginator 는 페이지를 만들 때 COUNT(*) 를 스스로 한 번 더 돌린다.
    이 화면은 같은 조건의 건수를 탭 배지·목록 헤더용으로 이미 세어 두므로,
    그 값을 넘겨 같은 COUNT 를 두 번 돌지 않게 한다.
    """

    def __init__(self, object_list, per_page, count, **kwargs):
        self._known_count = count
        super().__init__(object_list, per_page, **kwargs)

    @property
    def count(self):
        return self._known_count


def _page_window(page_obj, radius=2):
    """
    페이지 단추에 실제로 그려질 것만 골라 둔다 — [1, …, 8, 9, 10, 11, 12, …, 120] 꼴.

    예전에는 템플릿이 paginator.page_range 를 통째로 돌면서 {% if %} 사슬로 대부분을
    버렸다. 수거검사 공개 목록은 원본 전체가 모수라 6만 건이면 3,000쪽이고, 단추
    일곱 개를 그리자고 3,000번을 돌며 |add 필터를 만 오천 번 태웠다. 실측으로 이
    화면 렌더 시간의 3분의 2가 여기였다(news_list.html 77ms 중 62ms). 원본은 계속
    쌓이므로 이 비용도 계속 는다.

    고르는 규칙은 예전 {% if %} 사슬과 같은 순서·같은 결과다.
      ① 현재 쪽  ② 현재 ±2  ③ 첫 쪽·끝 쪽  ④ 현재 ±3 자리에만 '…'
    """
    if page_obj is None:
        return []
    last = page_obj.paginator.num_pages
    cur  = page_obj.number
    candidates = {1, last, cur - radius - 1, cur + radius + 1}
    candidates.update(range(cur - radius, cur + radius + 1))

    window = []
    for n in sorted(c for c in candidates if 1 <= c <= last):
        if n == cur:
            window.append({'n': n, 'active': True})
        elif cur - radius <= n <= cur + radius:
            window.append({'n': n})
        elif n == 1 or n == last:
            window.append({'n': n})
        elif n in (cur - radius - 1, cur + radius + 1):
            window.append({'ellipsis': True})
    return window


def _scope_qs(request, scope):
    """내 알림 / 일반 알림 / 전체 를 오가는 주소."""
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('scope', None)
    if scope:
        params['scope'] = scope
    return params.urlencode()


def _tab_qs(request, tab):
    """
    탭을 옮기는 주소. 지금 보고 있는 조건은 그대로 들고 간다.

    탭이 <button onclick> 이던 시절에는 이 주소를 스크립트가 만들었다.
    탭 전환은 곧 페이지 이동이므로 링크여야 한다 — 가운데 클릭으로 새 탭에서
    열리고, 주소를 복사할 수 있고, 스크립트가 죽어도 눌린다.
    (실제로 스크립트가 한 번 죽어 "탭이 클릭되지 않는다" 는 신고가 나왔다)
    """
    params = request.GET.copy()
    for k in ('page', 'id', 'insp_id', 'pub_insp_id', 'insp_page', 'pub_page'):
        params.pop(k, None)
    params.pop('tab', None)
    if tab and tab != TAB_INSP_NEWS:
        params['tab'] = tab
    return params.urlencode()


def _toggle_condition_qs(request, conditions, key, value):
    """
    조건 하나(key=value)를 켜고 끄는 주소를 만든다 — '미조치만 보기' 같은 단축 버튼용.

    조건은 f/v 가 같은 순서로 짝지어 들어오므로, 통째로 다시 쓴다.
    이미 켜져 있으면 그 값만 빼고, 없으면 붙인다.
    """
    params = request.GET.copy()
    for k in ('f', 'v', 'page'):
        params.pop(k, None)

    for cond in conditions or []:
        picked = cond['value'].split(',')
        if cond['key'] == key:
            picked = [p for p in picked if p != value] if value in picked else picked + [value]
            if not picked:
                continue          # 마지막 값을 껐으면 조건 자체를 뺀다
        params.appendlist('f', cond['key'])
        params.appendlist('v', ','.join(picked))

    if not any(c['key'] == key for c in (conditions or [])):
        params.appendlist('f', key)
        params.appendlist('v', value)
    return params.urlencode()


def _cat_condition(cats):
    """체크박스 카테고리 목록(key들) → Q 객체 (api_source 기반)"""
    cond = Q()
    for cat in API_CATEGORIES:
        if cat['key'] in cats:
            cond |= Q(api_source__in=cat['api_sources'])
    return cond


# ─────────────────────────────────────────────────────────────────────────────
# 목록 뷰
# ─────────────────────────────────────────────────────────────────────────────

def _active_filter_labels(q, days, date_from, date_to, risk, status,
                          insp_status, cats_submitted, regular_cats):
    """
    지금 적용 중인 필터를 사람이 읽는 문구로 만든다.
    조건이 여기저기 흩어져 있어 "왜 이것만 보이지?" 하기 쉬워, 화면에 요약해 보여준다.
    """
    labels = []
    if q:
        labels.append(f'검색 "{q}"')
    if date_from or date_to:
        labels.append(f'기간 {date_from or "처음"}~{date_to or "오늘"}')
    elif days != 'all':
        labels.append({'3': '최근 3일', '7': '최근 1주', '30': '최근 1개월'}.get(days, f'최근 {days}일'))
    if risk:
        labels.append({'HIGH': '중요', 'MED': '관심', 'LOW': '일반'}.get(risk, risk))
    if status:
        labels.append({'no_action': '미조치', 'monitoring': '진행 중',
                       'resolved': '완료'}.get(status, status))
    if insp_status:
        labels.append({'pending': '검사 진행 중', 'done': '판정 완료'}.get(insp_status, insp_status))
    if cats_submitted and regular_cats and set(regular_cats) != set(_REGULAR_CAT_KEYS):
        labels.append(f'분야 {len(regular_cats)}개 선택')
    return labels


@login_required
def news_list(request):
    """
    부적합 뉴스 목록 (Split View 왼쪽 패널)
    - 카테고리 체크박스: 국내 부적합 / 수입 부적합 / 행정처분
    - 기간 필터: 3일 / 7일 / 30일 / 전체
    - 내 제품과 매칭된 뉴스 상단 고정
    """
    q         = request.GET.get('q', '').strip()
    risk      = request.GET.get('risk', '')    # 'HIGH' | 'MED' | 'LOW' | ''
    status    = request.GET.get('status', '') # 'no_action' | 'monitoring' | 'resolved' | ''
    # 기본은 전체 기간. 예전 기본값(30일)에서는 처음 들어온 사용자가
    # "내 알림이 왜 안 보이지?" 하게 되는 경우가 많았다.
    days      = request.GET.get('days', 'all')  # '3' | '7' | '30' | 'all'
    sort      = request.GET.get('sort', 'desc')  # 'desc' | 'asc'
    date_from = request.GET.get('date_from', '').strip()  # YYYY-MM-DD
    date_to   = request.GET.get('date_to',   '').strip()  # YYYY-MM-DD
    tab       = request.GET.get('tab', '')    # 'insp-news' | 'admin' | 'insp' | ''
    # 내 알림 / 일반 알림 가르기. '' = 기본(내 알림 몇 건만 고정 + 일반 알림 목록)
    scope     = request.GET.get('scope', '')
    if scope not in ('mine', 'others'):
        scope = ''
    insp_status = request.GET.get('insp_status', '')  # '' (전체) | 'pending' | 'done'
    if insp_status not in ('pending', 'done'):
        insp_status = ''

    # ── 다중 조건 검색 ──────────────────────────────────────────────────────
    # 제품 조회·식품첨가물과 같은 f=키&v=값 규약. 흩어져 있던 분야·위험도·조치상태·
    # 날짜 필터를 조건 한 줄로 흡수한다. 옛 파라미터(cat/risk/status)로 들어와도
    # 동작하도록 아래에서 조건 값과 합쳐 쓴다.
    conditions = news_search.parse_conditions(
        request.GET.getlist('f'), request.GET.getlist('v')
    )

    # 조건으로 들어온 위험도·조치상태는 사용자별 계산이라 여기서 꺼내 쓴다
    cond_risks = news_search.picked(conditions, 'risk')
    cond_statuses = news_search.picked(conditions, 'status')
    if cond_risks and not risk:
        risk = cond_risks[0] if len(cond_risks) == 1 else ''
    if cond_statuses and not status:
        status = cond_statuses[0] if len(cond_statuses) == 1 else ''

    # ── 분야(카테고리) ──────────────────────────────────────────────────
    # 조건 패널의 '분야' 에서만 온다. 안 고르면 전부 본다.
    #
    # 예전에는 툴바에 '분야' 체크박스가 있었고 cats_sent=1 이 "체크박스를 실제로
    # 제출했다" 는 표시였다 — 아무것도 안 고른 채 제출하면 아무 분야도 안 본다는
    # 뜻이라 목록이 비는 것이 맞았다. 그 체크박스는 조건 패널로 옮겨 가며 화면
    # 에서 사라졌는데 hidden 센티넬만 남았다. 그래서 폼을 거치는 조작(기간 단추·
    # 검색·조건 제출)을 하는 순간 "아무 분야도 안 고름" 이 되어 목록이 통째로
    # 비었다. 껍데기를 걷어냈다.
    cond_cats = news_search.picked(conditions, 'cat')
    cats_submitted = bool(cond_cats)
    cats = cond_cats or _ALL_CAT_KEYS
    # 일반 cat 필터는 I0460(수거검사) 제외하고 처리 — 그쪽은 별도 모델이다
    regular_cats = [c for c in cats if c != 'I0460']
    if not regular_cats:
        # 분야를 골랐는데 수거검사 하나뿐이면, 뉴스 쪽은 볼 것이 없다
        regular_cats = []

    # 대표 날짜 _eff = Greatest(COALESCE(event_date, collected_date), collected_date)
    # = event_date 가 있으면 max(event_date, collected_date), 없으면 collected_date.
    # event_date 는 대부분 비어 있어(로컬 4,750건 중 4,728건) 이 값을 기준으로 잡아야
    # "최근 수집된 구 사건 항목이 과거 검색에 잘못 포함되는" 문제도 막을 수 있다.
    # 기간 필터·날짜 조건·날짜 정렬이 모두 이 이름을 쓰므로 항상 붙여 둔다.
    from django.db.models import ExpressionWrapper, DateField
    _eff_date = ExpressionWrapper(
        Greatest(Coalesce(F('event_date'), F('collected_date')), F('collected_date')),
        output_field=DateField(),
    )
    qs = RegulatoryNews.objects.annotate(_eff=_eff_date)

    # 기간 필터 (조건 패널의 날짜 조건과 별개로, 자주 쓰는 단축 버튼)
    if date_from or date_to:
        if date_from:
            qs = qs.filter(_eff__gte=date_from)
        if date_to:
            qs = qs.filter(_eff__lte=date_to)
        days = 'all'  # 버튼 active 표시 없애는 용도
    elif days != 'all':
        try:
            cutoff = (timezone.now() - timedelta(days=int(days))).date()
            qs = qs.filter(_eff__gte=cutoff)
        except (ValueError, TypeError):
            pass

    # 카테고리 필터 (수거검사 제외한 일반 카테고리)
    if regular_cats and set(regular_cats) != set(_REGULAR_CAT_KEYS):
        qs = qs.filter(_cat_condition(regular_cats))
    elif not regular_cats:
        qs = qs.none()

    # 검색
    if q:
        qs = (
            qs.filter(product_name__icontains=q) |
            qs.filter(company_name__icontains=q) |
            qs.filter(violation_reason__icontains=q)
        ).distinct()

    # 다중 조건 (분야·위반유형·날짜·텍스트). 위험도·조치상태는 아래에서 따로 처리한다.
    if conditions:
        qs = qs.filter(news_search.conditions_q(conditions))

    # 목록 렌더·배지·건수에 쓰는 매칭 정보를 한 번에 모아 온다 (행별 서브쿼리 제거).
    # 미확인·조치대상·미조치 집계도 여기서 함께 나오므로, 같은 행을 다시 읽지 않는다.
    match_ctx = selectors.user_match_context(request.user)

    # 미확인 집합 — 집계 규칙은 selectors 한 곳에서 관리한다 (탭 미확인 dot 표시용)
    my_unread_news_ids = match_ctx['unread']

    # ── risk / status 필터 (부적합·행정처분 탭) ──────────────────────────────
    # 반드시 Paginator 생성 전에 적용해야 한다.
    # (이전에는 페이지네이션 뒤에서 qs 를 재할당해 필터가 목록에 반영되지 않았다)
    # 조건 패널에서는 위험도를 여러 개 고를 수 있다 (묶음 안에서는 OR)
    risk_levels = cond_risks or ([risk] if risk else [])
    if risk_levels:
        risk_from_product = (
            NewsProductMatch.objects
            .filter(product__user_id=request.user, false_positive_yn=False,
                    risk_level__in=risk_levels)
            .values_list('news_id', flat=True)
        )
        risk_from_ingredient = (
            NewsIngredientMatch.objects
            .filter(user=request.user, dismissed_yn=False, risk_level__in=risk_levels)
            .values_list('news_id', flat=True)
        )
        qs = qs.filter(Q(id__in=risk_from_product) | Q(id__in=risk_from_ingredient))

    # 뉴스별 최신 조치(제품·원료 합산)와 미조치 집합은 match_ctx 가 이미 들고 있다.
    # 여기서 다시 조회하면 같은 조인을 두 번 돌게 된다.
    if status in selectors.ACTION_STATUSES:
        qs = qs.filter(id__in=[nid for nid, at in match_ctx['latest_action'].items()
                               if at == status])
    elif status == 'no_action':   # 조치 가능한 매칭 중 조치 이력이 없는 건
        qs = qs.filter(id__in=match_ctx['no_action'])

    # 탭 배지 건수용 스냅샷 — 어노테이션(Exists/Subquery) 이 붙기 전 queryset 을 쓴다.
    # 어노테이션된 qs 로 COUNT 하면 불필요한 서브쿼리가 함께 실행될 수 있다.
    count_qs = qs

    # 정렬용 어노테이션.
    # 예전에는 Exists/Subquery 8개를 붙여 상관 서브쿼리가 행마다 실행됐다.
    # 매칭 정보는 selectors 에서 한 번에 모아 오고, 여기서는 상수 IN 목록만 쓴다.
    matched_ids = match_ctx['all_matched']

    qs = qs.annotate(
        # 매칭 그룹 우선순위: 0=매칭(상단), 1=일반(하단)
        match_priority=(
            Case(
                When(id__in=matched_ids, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ) if matched_ids else Value(1, output_field=IntegerField())
        ),
    )

    # 정렬 — 화이트리스트로 검증한다 (다른 목록 화면과 같은 방식).
    # 날짜 기준은 _eff(대표 날짜)를 쓴다. event_date 만으로는 대부분 NULL 이라
    # 오늘 수집된 구 사건 항목이 아래로 밀린다.
    # 매칭된 뉴스를 위로 고정하는 규칙은 어떤 정렬에서도 유지한다.
    sort_field, active_sort, sort_order = news_search.resolve_sort(
        request.GET.get('sort'), request.GET.get('order')
    )
    tiebreak = '-created_at' if sort_order == 'desc' else 'created_at'
    qs = qs.order_by('match_priority', sort_field, tiebreak)

    # ── 탭 배지 건수 ─────────────────────────────────────────────────────────
    # 규칙(3개 탭 공통): 배지 숫자 = 그 탭에서 실제로 보게 될 목록의 총 건수
    #                    (현재 검색·기간·분야·등급·상태 필터가 모두 적용된 값)
    #                    미확인 여부는 숫자가 아니라 빨간 점으로만 표시한다.
    _ADMIN_SOURCES = ADMIN_API_SOURCES
    tab_admin_total = count_qs.filter(api_source__in=_ADMIN_SOURCES).count()
    tab_insp_total  = count_qs.exclude(api_source__in=_ADMIN_SOURCES).count()

    # 미확인 dot — **숫자와 같은 범위**로 센다.
    #
    # 예전에는 점만 조건과 무관한 전 기간 기준이었다. 그래서 조건이 좁혀지면
    # "0건인데 빨간 점" 이 됐다 — 한 배지 안에서 숫자와 점이 서로 다른 질문에
    # 답하니, 어느 쪽을 믿어야 할지 알 수 없다.
    # 지금은 둘 다 "지금 조건으로 이 탭에 보이는 것" 을 말한다.
    # 조건에 가려 못 보는 미확인은 네비바 배지(regAlertBadge)가 따로 말한다.
    if my_unread_news_ids:
        _unread_in_view = count_qs.filter(id__in=my_unread_news_ids)
        tab_admin_unread = _unread_in_view.filter(api_source__in=_ADMIN_SOURCES).count()
        tab_insp_unread  = _unread_in_view.exclude(api_source__in=_ADMIN_SOURCES).count()

        # '모두 읽음' 단추가 말할 숫자는 다르다. 그 단추는 조건과 무관하게 이 탭을
        # 통째로 읽음 처리하므로, 조건 안에서 센 값을 쓰면 "3건" 이라 해 놓고
        # 50건을 처리하게 된다. 점과 단추는 서로 다른 것을 말한다.
        _all_src = dict(
            RegulatoryNews.objects.filter(id__in=my_unread_news_ids)
            .values_list('id', 'api_source')
        )
        tab_admin_unread_all = sum(1 for src in _all_src.values() if src in _ADMIN_SOURCES)
        tab_insp_unread_all  = len(_all_src) - tab_admin_unread_all
    else:
        tab_admin_unread = tab_admin_unread_all = 0
        tab_insp_unread  = tab_insp_unread_all  = 0

    # 탭별 독립 검색: 건수 집계 완료 후 qs 범위 제한
    if tab == 'admin':
        qs = qs.filter(api_source__in=_ADMIN_SOURCES)
    elif tab in ('insp-news', ''):
        qs = qs.exclude(api_source__in=_ADMIN_SOURCES)
    # tab == 'insp': 수거검사 탭은 qs 미사용 — 제한 불필요

    # ── 내 알림 / 일반 알림 가르기 ───────────────────────────────────────────
    # 매칭된 건을 전부 위로 고정하면, 매칭이 수십 건인 사용자에게는 목록 앞
    # 몇 페이지가 통째로 내 알림이 된다. 일반 알림을 보려면 몇 페이지를 넘겨야
    # 하는지 알 방법이 없다 — 개발자도 못 찾았다는 신고가 여기서 나왔다.
    #
    # 그래서 기본 화면에서는 내 알림을 **위에 다섯 건만** 고정하고, 목록 본문은
    # 일반 알림으로 둔다. 내 알림 전체는 'scope=mine' 으로 따로 본다.
    # 정렬·페이지네이션이 어긋나지 않도록 서버에서 가른다.
    mine_total = qs.filter(id__in=matched_ids).count() if matched_ids else 0
    # 활성 탭 목록의 총 건수는 방금 센 탭 배지 숫자와 같다. 바로 위에서 qs 에
    # 건 것이 탭 범위 제한뿐이고, 그 제한이 count_qs 를 두 덩이로 정확히 가른다.
    if tab == 'admin':
        scope_all_total = tab_admin_total
    elif tab in ('insp-news', ''):
        scope_all_total = tab_insp_total
    else:                       # tab == 'insp' — qs 를 좁히지 않았다
        scope_all_total = tab_admin_total + tab_insp_total
    other_total = scope_all_total - mine_total

    pinned_news = []
    list_total = scope_all_total   # 아래에서 qs 를 가르면 그쪽 건수로 바뀐다
    if scope == 'mine':
        qs = qs.filter(id__in=matched_ids) if matched_ids else qs.none()
        list_total = mine_total
    elif matched_ids:
        if scope == '' and mine_total > PINNED_MATCH_LIMIT:
            # 다섯 건 이하면 굳이 가르지 않는다 — 목록이 두 덩이로 쪼개지기만 한다
            pinned_news = list(qs.filter(id__in=matched_ids)[:PINNED_MATCH_LIMIT])
            qs = qs.exclude(id__in=matched_ids)
            list_total = other_total
        elif scope == 'others':
            qs = qs.exclude(id__in=matched_ids)
            list_total = other_total

    # 페이지네이션 — 건수는 위에서 이미 셌으므로 같은 COUNT 를 다시 돌리지 않는다
    page_num = request.GET.get('page', 1)
    per_page = news_search.safe_per_page(request.GET.get('per_page'))
    paginator = _CountedPaginator(qs, per_page, list_total)
    page_obj  = paginator.get_page(page_num)

    # 페이지 이동용 쿼리스트링 (page·선택 파라미터 제거, tab 파라미터는 유지)
    qp = request.GET.copy()
    qp.pop('page',      None)
    qp.pop('id',        None)
    qp.pop('insp_id',     None)
    qp.pop('pub_insp_id', None)
    qp.pop('insp_page',   None)
    qp.pop('pub_page',    None)
    # '미조치만 보기' 단축 버튼용 주소.
    # 조치상태는 조건 패널의 체크박스 묶음으로 옮겼지만, 가장 자주 쓰는 조작이라
    # 목록 위에 한 번 누르면 켜지고 다시 누르면 꺼지는 버튼을 남긴다.
    # (같은 조건을 가리키는 지름길일 뿐, 별도의 필터가 아니다)
    no_action_on = 'no_action' in news_search.picked(conditions, 'status')
    no_action_qs = _toggle_condition_qs(request, conditions, 'status', 'no_action')

    page_query_string = qp.urlencode()
    current_tab = tab  # 상단에서 이미 읽은 값 재사용

    # 고정 블록은 첫 페이지에만 둔다. 뒤 페이지마다 같은 다섯 건이 다시 나오면
    # 스크롤한 만큼 나아가지 않는 것처럼 보인다.
    if page_obj.number != 1:
        pinned_news = []

    # 페이지에 실제로 보이는 행에만 매칭 정보를 붙인다 (보통 50건)
    selectors.attach_match_info(page_obj.object_list, match_ctx)
    selectors.attach_match_info(pinned_news, match_ctx)

    # saol_admin 지자체명 추출 (목록 패널 표시용)
    for news_item in list(page_obj.object_list) + pinned_news:
        if news_item.api_source == 'saol_admin' and news_item.raw_detail_text:
            first_part = news_item.raw_detail_text.split(' | ')[0]
            news_item.saol_location = first_part.split(': ', 1)[1].strip() if ': ' in first_part else first_part.strip()
        else:
            news_item.saol_location = ''

    # 미조치 건수 — **지금 탭 범위**로 센다.
    # 같은 줄의 전체·내 알림·일반이 모두 탭 범위 숫자라, 여기만 두 탭을 합쳐
    # 세면 눌렀을 때 그만큼 안 나온다("10건이라는데 목록엔 없다").
    _no_action_ids = match_ctx['no_action']
    if _no_action_ids:
        _tab_admin_q = Q(api_source__in=ADMIN_API_SOURCES)
        _scoped = RegulatoryNews.objects.filter(id__in=_no_action_ids)
        # active_tab 은 아직 정해지기 전이다(수거검사 상세 선택 여부를 봐야 한다).
        # 여기서 필요한 것은 부적합/행정처분 갈래뿐이라 tab 을 그대로 쓴다.
        if tab == TAB_ADMIN:
            _scoped = _scoped.filter(_tab_admin_q)
        elif tab in ('', TAB_INSP_NEWS):
            _scoped = _scoped.exclude(_tab_admin_q)
        no_action_count = _scoped.count()
    else:
        no_action_count = 0

    # 카테고리별 건수 (api_source 기반, 전체 DB 기준 — 필터 드로어 표시용)
    # 전체 테이블 GROUP BY 라 매 요청마다 돌리면 비싸다(로컬 4,750건에서 16ms).
    # 드로어에만 쓰는 참고 수치이므로 캐시한다. 수집 스케줄러가 돌면 자연히 갱신된다.
    api_counts = cache.get('regulatory_api_counts')
    if api_counts is None:
        api_counts = {
            row['api_source']: row['cnt']
            for row in RegulatoryNews.objects.values('api_source').annotate(cnt=Count('id'))
        }
        cache.set('regulatory_api_counts', api_counts, 60 * 60 * 3)
    categories_with_count = [
        {**cat, 'count': sum(api_counts.get(s, 0) for s in cat['api_sources'])}
        for cat in API_CATEGORIES
    ]
    insp_cats  = [c for c in categories_with_count if c.get('group') == 'insp']
    admin_cats = [c for c in categories_with_count if c.get('group') == 'admin']
    saol_cats  = [c for c in categories_with_count if c.get('group') == 'saol']

    # ── 수거검사(I0460) — 내 매칭 건수 및 목록 ───────────────────────────────
    ins_qs_base = (
        InspectionMatch.objects
        .filter(user=request.user)
        .select_related('inspection', 'label')
        .order_by('-inspection__tkawydtm', '-alert_phase')
    )
    # 내 매칭 보유 여부(공개 목록 대체 화면 노출 판단)와 미확인 건수(dot·"전체 읽음")는
    # 둘 다 필터와 무관한 전 기간 기준이라, exists()+count() 두 번 대신 한 번에 센다.
    _ins_stat = (
        InspectionMatch.objects
        .filter(user=request.user)
        .aggregate(total=Count('id'), unread=Count('id', filter=Q(read_yn=False)))
    )
    inspection_has_matches = bool(_ins_stat['total'])
    # 이 값은 전 기간 기준이다. 아래에서 조건이 걸리면 그 범위로 다시 센다
    # (탭 배지의 숫자·점이 같은 것을 말하도록).
    inspection_unread      = _ins_stat['unread']

    # 공용 필터(검색어·기간)는 활성 탭과 무관하게 적용한다.
    # 부적합·행정처분 배지도 같은 필터를 반영하므로, 여기만 예외로 두면
    # 수거검사 탭을 누르는 순간 배지 숫자가 바뀌어 보인다.
    ins_qs = ins_qs_base
    ins_filtered = bool(q or date_from or date_to or (days != 'all') or insp_status)
    if q:
        ins_qs = ins_qs.filter(
            Q(inspection__prdtnm__icontains=q) |
            Q(inspection__bssh_nm__icontains=q)
        )
    if date_from or date_to:
        df_str = date_from.replace('-', '') if date_from else ''
        dt_str = date_to.replace('-', '')   if date_to   else ''
        if df_str:
            ins_qs = ins_qs.filter(inspection__tkawydtm__gte=df_str)
        if dt_str:
            ins_qs = ins_qs.filter(inspection__tkawydtm__lte=dt_str)
    elif days != 'all':
        try:
            cutoff_str = (timezone.now() - timedelta(days=int(days))).strftime('%Y%m%d')
            ins_qs = ins_qs.filter(inspection__tkawydtm__gte=cutoff_str)
        except (ValueError, TypeError):
            pass

    # 진행 중 / 완료 필터 — 수거검사 탭 전용 칩이므로 이 탭에서만 적용된다.
    # 서버에서 처리해야 페이지네이션·건수가 어긋나지 않는다.
    # (이전에는 JS 가 현재 페이지의 DOM 만 숨겨서 다음 페이지에는 적용되지 않고,
    #  목록 헤더 숫자도 "현재 페이지에 보이는 개수"로 덮어써져 탭 배지와 달라졌다)
    if insp_status:
        _pending_q = Q(inspection__jdgmnt_cd_nm__in=InspectionResult.PENDING_JUDGMENTS)
        ins_qs = (ins_qs.filter(_pending_q) if insp_status == 'pending'
                  else ins_qs.exclude(_pending_q))

    # 탭 배지 = 목록 헤더 = 현재 필터가 적용된 총 건수 (부적합·행정처분 탭과 같은 규칙).
    # 필터가 하나도 안 걸렸으면 위에서 이미 센 전 기간 건수와 같은 값이다.
    inspection_total  = ins_qs.count() if ins_filtered else _ins_stat['total']
    inspection_unread_all = _ins_stat['unread']       # 단추가 실제로 처리할 건수
    if ins_filtered:
        inspection_unread = ins_qs.filter(read_yn=False).count()   # 점
    insp_page_num     = request.GET.get('insp_page', 1)
    insp_paginator    = _CountedPaginator(ins_qs, 20, inspection_total)
    insp_page_obj     = insp_paginator.get_page(insp_page_num)
    inspection_list   = insp_page_obj   # 하위 호환 — 템플릿 변수명 유지

    # 내 매칭이 없을 때 보여줄 전체 수거검사 공개 목록 (캐시 적용)
    # 상단 필터(days / date_from / date_to)를 그대로 사용
    recent_insp_list = []
    recent_insp_page_obj = None
    recent_insp_paginator = None
    recent_insp_total = 0
    # 필터 결과가 0건인 것과 매칭 자체가 없는 것은 다르다 — 후자일 때만 공개 목록으로 대체
    if not inspection_has_matches:
        # 예전에는 이 목록 전체(.values() 결과)를 파일 캐시에 통째로 넣고, 매 요청마다
        # 통째로 되읽어 Python 에서 거르고 잘랐다. 수거검사 원본은 전국 자료라 행이
        # 많아 캐시 적중 시에도 수만 건을 언피클해야 했고 — 매칭이 없는 사용자에게는
        # 이 화면이 다른 화면보다 몇 배 느린 주된 이유였다.
        # 지금은 필터·정렬·자르기를 모두 SQL 에 맡겨 한 페이지(20건)만 읽는다.
        pub_page_num = request.GET.get('pub_page', 1)
        _PUB_FIELDS = (
            'id', 'prdtnm', 'bssh_nm', 'tkawydtm', 'jdgmnt_cd_nm',
            'exc_instt_nm', 'plan_titl', 'tkawyprno',
        )

        pub_qs = InspectionResult.objects.order_by('-tkawydtm')
        if date_from or date_to:
            if date_from:
                pub_qs = pub_qs.filter(tkawydtm__gte=date_from.replace('-', ''))
            if date_to:
                pub_qs = pub_qs.filter(tkawydtm__lte=date_to.replace('-', ''))
        elif days != 'all':
            try:
                cutoff_str = (timezone.now() - timedelta(days=int(days))).strftime('%Y%m%d')
                pub_qs = pub_qs.filter(tkawydtm__gte=cutoff_str)
            except (ValueError, TypeError):
                pass

        if q:
            pub_qs = pub_qs.filter(Q(prdtnm__icontains=q) | Q(bssh_nm__icontains=q))

        # 진행 중 / 완료 필터 — 내 목록과 같은 판정 기준을 적용
        if insp_status:
            _pub_pending_q = Q(jdgmnt_cd_nm__in=InspectionResult.PENDING_JUDGMENTS)
            pub_qs = (pub_qs.filter(_pub_pending_q) if insp_status == 'pending'
                      else pub_qs.exclude(_pub_pending_q))

        # 건수만 캐시한다 — 목록과 달리 값 하나라 캐시가 커지지 않는다.
        # 검색어·판정·날짜 범위가 걸리면 사용자별 조건이라 그때만 직접 센다.
        if q or insp_status or date_from or date_to:
            recent_insp_total = pub_qs.count()
        else:
            _pub_count_key = f'public_insp_count_{days}'
            recent_insp_total = cache.get(_pub_count_key)
            if recent_insp_total is None:
                recent_insp_total = pub_qs.count()
                cache.set(_pub_count_key, recent_insp_total, timeout=60 * 60 * 6)

        recent_insp_paginator = _CountedPaginator(
            pub_qs.values(*_PUB_FIELDS), 20, recent_insp_total)
        recent_insp_page_obj = recent_insp_paginator.get_page(pub_page_num)
        # 목록 배지는 모델 프로퍼티와 같은 규칙으로 계산해 넣는다 (.values() 라 프로퍼티 사용 불가)
        recent_insp_list = [
            {**r, 'judgment_status': judgment_status_of(r['jdgmnt_cd_nm'])}
            for r in recent_insp_page_obj
        ]

    # 상세 패널: URL 파라미터로 선택된 뉴스
    selected_id = request.GET.get('id')
    selected_news = None
    selected_matches = []
    selected_ing_matches = []   # NewsIngredientMatch 인스턴스 목록
    selected_kw_logs = []       # NewsKeywordMatch (내 알림 키워드 매칭)
    if selected_id:
        try:
            selected_news = RegulatoryNews.objects.get(pk=selected_id)
            # 알림이 '왜' 왔는지를 상세 패널의 표준 항목으로 보여 준다.
            # 행정처분·지자체처분은 업체명 하나로 걸리고(원료 키워드를 보지 않는다),
            # 나머지 부적합은 뉴스 쪽 키워드 ↔ 내 원료명의 짝으로 걸린다.
            # 알림을 끄는 단추의 문구와 대상(scope)이 여기서 갈린다.
            selected_news.is_admin_source = (
                selected_news.api_source in ADMIN_API_SOURCES
            )

            # ━━ 온디맨드 재매칭 (제품 + 원료 보관함) ━━
            try:
                from v1.regulatory.services.matcher import (
                    find_affected_products,
                    find_matching_ingredients_unlinked,
                    save_ingredient_matches,
                    save_matches,
                )
                live_matches = find_affected_products(selected_news, request.user)
                if live_matches:
                    save_matches(selected_news, live_matches)
                live_ing_matches = find_matching_ingredients_unlinked(selected_news, request.user)
                if live_ing_matches:
                    save_ingredient_matches(selected_news, request.user, live_ing_matches)
            except Exception:
                logger.exception('[온디맨드 재매칭 오류]')

            selected_matches = (
                NewsProductMatch.objects
                .filter(news=selected_news, product__user_id=request.user,
                        false_positive_yn=False)
                .select_related('product', 'matched_bom')
                .order_by('-risk_score', '-match_score')
                .prefetch_related('actions')
            )
            # 원료 보관함 단독 매칭 (BOM 미연결)
            selected_ing_matches = (
                NewsIngredientMatch.objects
                .filter(news=selected_news, user=request.user, dismissed_yn=False)
                .select_related('ingredient')
                .prefetch_related(
                    'ingredient__bom_usages__parent_label',
                    'actions',
                )
                .order_by('-risk_score', '-match_score')
            )
            # 키워드 매칭 — 사용자에 붙는 표에서 읽는다.
            # 예전에는 기기별 푸시 로그를 봤기 때문에, 앱을 깐 적 없는 사용자
            # 에게는 이 구역이 한 번도 나온 적이 없다.
            selected_kw_logs = list(
                NewsKeywordMatch.objects
                .filter(news=selected_news, user=request.user, dismissed_yn=False)
                .select_related('rule')
                .order_by('category', 'matched_keyword')
            )
            # 열어 본 것은 읽음으로 — 제품·원료 매칭과 같은 결
            _unread_kw = [m.pk for m in selected_kw_logs if not m.read_yn]
            if _unread_kw:
                NewsKeywordMatch.objects.filter(pk__in=_unread_kw).update(
                    read_yn=True, read_at=timezone.now())
                cache.delete(f'regulatory_alert_count_{request.user.id}')
        except RegulatoryNews.DoesNotExist:
            pass

    # 사용자의 AlertRule 목록 — user 기반으로 직접 조회
    #
    # 여기 "웹 전용 기기를 항상 보장" 이라는 주석과 쓰이지 않는 AppDevice import 가
    # 있었다. 하려던 일(앱을 안 쓰는 사용자에게도 키워드 매칭을 남기는 것)은
    # 끝내 붙지 않았고, 그래서 웹 전용 사용자에게는 키워드 알림이 아무 일도 하지
    # 않는다. 지키지 못한 약속을 코드에 남겨 두면 다음 사람이 "이미 되어 있다" 고
    # 믿는다 — 걷어내고, 남은 문제는 REGULATORY_ALERT_PIPELINE.md 에 적어 둔다.
    unique_alert_rules = list(
        AlertRule.objects
        .filter(user=request.user, is_active=True)
        .order_by('category', 'keyword')
    )
    # 알림 제외(뮤트) 규칙 — 설정 모달의 '받지 않기' 목록에 쓴다.
    # 상세 패널에는 넘기지 않는다: 끈 규칙에 걸리는 매칭은 그 자리에서 함께
    # 치워지므로, 목록에 남아 있는 매칭은 정의상 꺼져 있지 않다.
    alert_mutes = list(AlertMute.objects.filter(user=request.user))

    # saol_admin 원본 사이트 URL 추출 (external_id: 'saol-{site_code}-{dup_key}')
    saol_site_url = ''
    if selected_news and selected_news.api_source == 'saol_admin':
        ext_parts = selected_news.external_id.split('-', 2)
        if len(ext_parts) >= 2:
            saol_site_url = SAOL_URLS.get(ext_parts[1], '')

    # ── 수거검사 상세 패널 (insp_id 파라미터) ────────────────────────────────
    selected_insp_id = request.GET.get('insp_id')
    selected_insp = None
    if selected_insp_id:
        try:
            selected_insp = (
                InspectionMatch.objects
                .select_related('inspection', 'label')
                .get(pk=selected_insp_id, user=request.user)
            )
            if not selected_insp.read_yn:
                selected_insp.read_yn = True
                selected_insp.read_at = timezone.now()
                selected_insp.save(update_fields=['read_yn', 'read_at'])
        except InspectionMatch.DoesNotExist:
            pass

    # ── 공개 수거검사 상세 패널 (pub_insp_id 파라미터) ───────────────────────
    selected_pub_insp_id = request.GET.get('pub_insp_id')
    selected_pub_insp = None
    if selected_pub_insp_id and not selected_insp:
        try:
            selected_pub_insp = InspectionResult.objects.get(pk=selected_pub_insp_id)
        except InspectionResult.DoesNotExist:
            pass

    # ── 지금 어느 탭인가 — **서버가 정한다** ────────────────────────────────
    # 예전에는 이 값을 화면이 몰랐다. 템플릿이 data-view 를 늘 'insp-news' 로
    # 박아 놓고, 브라우저에서 스크립트가 주소의 tab 파라미터를 읽어 뒤늦게
    # 고쳐 주는 구조였다. 탭 전환이 곧 페이지 이동인데도 그랬다.
    #
    # 그래서 스크립트가 한 번이라도 멈추면(오래된 캐시, 앞쪽 구문 오류, 정적
    # 파일 실패 어느 것이든) 주소는 ?tab=admin 인데 화면은 부적합 탭 그대로였다.
    # 눌러도 아무 일이 없는 것처럼 보이고, 하필 기본 탭인 부적합만 멀쩡해
    # "행정처분·수거검사 탭은 클릭이 안 된다" 로 나타났다.
    #
    # 서버가 이미 아는 값이므로 서버가 그린다. 이제 스크립트가 죽어도 탭은
    # 그냥 링크처럼 동작한다.
    if tab == TAB_ADMIN:
        active_tab = TAB_ADMIN
    elif tab == TAB_INSPECTION or selected_insp or selected_pub_insp:
        active_tab = TAB_INSPECTION
    else:
        active_tab = TAB_INSP_NEWS

    # '모두 읽음' 단추의 숫자 — **조건 밖까지** 센 값이다.
    # 그 단추는 조건과 무관하게 이 탭을 통째로 읽음 처리하므로, 조건 안에서 센
    # 값(=탭의 빨간 점)을 쓰면 단추가 거짓말을 한다.
    # 탭 상태와 같은 이유로 서버가 고른다(템플릿 주석 참고).
    tab_unread = {
        TAB_ADMIN:      tab_admin_unread_all,
        TAB_INSPECTION: inspection_unread_all,
    }.get(active_tab, tab_insp_unread_all)

    # ── 지금 탭의 페이지네이션 한 벌 ────────────────────────────────────────
    # 예전에는 세 벌을 다 그려 놓고 CSS 로 둘을 감췄다. 활성 탭은 서버가 이미
    # 아니까 그 탭 것만 그리면 된다 — 화면에 보이는 결과는 같고, 템플릿에서
    # 똑같이 생긴 덩어리 셋이 하나가 된다.
    if active_tab == TAB_INSPECTION:
        if inspection_has_matches:
            _pager = (insp_page_obj, insp_paginator, 'insp_page')
        else:
            _pager = (recent_insp_page_obj, recent_insp_paginator, 'pub_page')
    else:
        _pager = (page_obj, paginator, 'page')
    _pager_obj, _pager_paginator, _pager_param = _pager

    return render(request, 'regulatory/news_list.html', {
        'active_tab':         active_tab,
        'tab_unread':         tab_unread,
        # 페이지네이션 — 지금 탭 것 한 벌
        'pager':              _pager_obj,
        'pager_pages':        _pager_paginator.num_pages if _pager_paginator else 0,
        'pager_window':       _page_window(_pager_obj),
        'pager_param':        _pager_param,
        'news_list':          page_obj,          # 페이지 객체 (이터러블)
        'page_obj':           page_obj,
        'paginator':          paginator,
        'page_query_string':  page_query_string,
        'current_tab':        current_tab,
        'selected_news':           selected_news,
        'selected_matches':        selected_matches,
        'selected_ing_matches':    selected_ing_matches,
        'selected_kw_logs':        selected_kw_logs,
        'categories':         categories_with_count,
        # 탭 배지 = 해당 탭 목록의 총 건수(필터 적용) / *_unread = 빨간 점 표시용
        'tab_insp_total':     tab_insp_total,
        'tab_admin_total':    tab_admin_total,
        'tab_insp_unread':    tab_insp_unread,
        'tab_admin_unread':   tab_admin_unread,
        'insp_cats':          insp_cats,
        'admin_cats':         admin_cats,
        'saol_cats':          saol_cats,
        'no_action_count':    no_action_count,
        'no_action_on':       no_action_on,
        # ── 내 알림 / 일반 알림 가르기 ──────────────────────────────────
        'scope':              scope,
        'pinned_news':        pinned_news,
        'mine_total':         mine_total,
        'other_total':        other_total,
        'scope_all_total':    scope_all_total,
        'scope_qs_all':       _scope_qs(request, ''),
        'scope_qs_mine':      _scope_qs(request, 'mine'),
        'scope_qs_others':    _scope_qs(request, 'others'),
        # 탭 이동 주소 — 지금 조건을 그대로 들고 간다
        'tab_qs_insp_news':   _tab_qs(request, TAB_INSP_NEWS),
        'tab_qs_admin':       _tab_qs(request, TAB_ADMIN),
        'tab_qs_inspection':  _tab_qs(request, TAB_INSPECTION),
        # 알림 기준 요약에 "언제까지 모은 자료인지" 를 함께 보여준다
        'last_collected':     RegulatoryNews.objects.aggregate(m=Max('collected_date'))['m'],
        'no_action_qs':       no_action_qs,
        'q':                  q,
        'cats':               cats,
        'days':               days,
        'date_from':          date_from,
        'date_to':            date_to,
        'risk_filter':        risk,
        'status_filter':      status,
        'sort':               sort,
        # ── 조건 패널 (제품 조회·식품첨가물과 공용) ──────────────────────
        'conditions':         conditions,
        'condition_specs':    news_search.conditions_catalog(),
        'max_conditions':     news_search.MAX_CONDITIONS,
        'require_fast':       False,   # 5천 행이라 조건을 강제할 이유가 없다
        # 패널 자체는 늘 펼쳐 둔다. 접는 것은 그 바깥의 서랍(#regCondDrawer)이라
        # 여기서 접으면 서랍 안이 제출 단추만 남은 채 열린다.
        'panel_always_open':  True,
        'q_input_id':         'searchInput',
        # ── 정렬 / 페이지당 개수 ────────────────────────────────────────
        'sort_options':       news_search.SORT_OPTIONS,
        'active_sort':        active_sort,
        'sort_order':         sort_order,
        'per_page':           per_page,
        'per_page_choices':   news_search.PER_PAGE_CHOICES,
        'today':              date.today(),
        'saol_site_url':      saol_site_url,
        'alert_rules':        unique_alert_rules,
        'alert_mutes':        alert_mutes,
        'show_inspection':    active_tab == TAB_INSPECTION,
        'inspection_list':    inspection_list,
        'insp_page_obj':      insp_page_obj,
        'insp_paginator':     insp_paginator,
        'inspection_total':        inspection_total,
        'inspection_has_matches':  inspection_has_matches,
        'inspection_unread':       inspection_unread,
        'insp_status':             insp_status,
        'active_filters':          _active_filter_labels(
                                       q, days, date_from, date_to, risk, status,
                                       insp_status, cats_submitted, regular_cats),
        'selected_insp':           selected_insp,
        'selected_pub_insp':       selected_pub_insp,
        'recent_insp_list':        recent_insp_list,
        'recent_insp_page_obj':    recent_insp_page_obj,
        'recent_insp_paginator':   recent_insp_paginator,
        'recent_insp_total':       recent_insp_total,
        'user_profile':            UserProfile.objects.filter(user=request.user).first(),
        # 등록해 놓고 아무것도 안 뜰 때, 거슬러 맞춰 본 기간을 화면이 말해 준다
        'insp_backfill_days':      INSPECTION_BACKFILL_DAYS,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 상세 뷰 (독립 URL)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def news_detail(request, pk):
    """뉴스 상세 + 내 제품 매칭 결과 (독립 페이지)"""
    news = get_object_or_404(RegulatoryNews, pk=pk)
    my_matches = (
        NewsProductMatch.objects
        .filter(news=news, product__user_id=request.user, false_positive_yn=False)
        .select_related('product', 'matched_bom__parent_label')
        .prefetch_related('actions')
        .order_by('-risk_score', '-match_score')
    )
    ing_matches = (
        NewsIngredientMatch.objects
        .filter(news=news, user=request.user, dismissed_yn=False)
        .select_related('ingredient')
        .prefetch_related('ingredient__bom_usages__parent_label', 'actions')
        .order_by('-risk_score', '-match_score')
    )
    # 목록의 상세 패널과 같은 구역을 쓰므로 키워드 매칭도 같이 넘긴다.
    # (안 넘기면 이 페이지에서만 '알림 키워드 매칭' 이 통째로 빠진다)
    kw_matches = list(
        NewsKeywordMatch.objects
        .filter(news=news, user=request.user, dismissed_yn=False)
        .select_related('rule')
        .order_by('category', 'matched_keyword')
    )
    news.is_admin_source = news.api_source in ADMIN_API_SOURCES
    log_activity(request, 'regulatory', 'regulatory_detail', news.pk)
    return render(request, 'regulatory/news_detail.html', {
        'news':        news,
        'my_matches':  my_matches,
        'ing_matches': ing_matches,
        'kw_matches':  kw_matches,
    })


# ─────────────────────────────────────────────────────────────────────────────
# API 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def unread_count_api(request):
    """읽지 않은 매칭 알림 수 반환 (JSON) — 사이드바 배지와 동일 기준"""
    return JsonResponse({'unread': selectors.unread_news_count(request.user)})


@login_required
@require_POST
def mark_as_read(request):
    """
    읽음 처리 (JSON POST)
    Body: {"news_id": 123}  또는  {} (전체 읽음)
    """
    try:
        body = json.loads(request.body)
        news_id = body.get('news_id')
    except (ValueError, AttributeError):
        news_id = None

    qs = NewsProductMatch.objects.filter(product__user_id=request.user, read_yn=False)
    if news_id:
        qs = qs.filter(news_id=news_id)
    updated = qs.update(read_yn=True, read_at=timezone.now())

    # 원료 보관함 매칭도 읽음 처리
    ing_qs = NewsIngredientMatch.objects.filter(user=request.user, read_yn=False, dismissed_yn=False)
    if news_id:
        ing_qs = ing_qs.filter(news_id=news_id)
    ing_qs.update(read_yn=True)

    # 키워드 매칭도 같은 기준으로 (배지의 모수에 함께 들어간다)
    kw_qs = NewsKeywordMatch.objects.filter(user=request.user, read_yn=False, dismissed_yn=False)
    if news_id:
        kw_qs = kw_qs.filter(news_id=news_id)
    kw_qs.update(read_yn=True, read_at=timezone.now())

    # 읽음 처리 후 남은 미확인 뉴스 건수 (사이드바 배지와 동일 기준)
    cache.delete(f'regulatory_alert_count_{request.user.id}')
    unread = selectors.unread_news_count(request.user)

    return JsonResponse({'success': True, 'updated': updated, 'unread': unread})


@login_required
@require_POST
def save_match_action(request):
    """
    매칭(제품/원료)에 대한 조치 이력 기록 (JSON POST)

    Body: {
        "match_type":  "product" | "ingredient",
        "match_id":    123,
        "action_type": "dismissed" | "monitoring" | "resolved" | "memo",
        "memo":        "선택적 메모 텍스트"
    }
    """
    try:
        body       = json.loads(request.body)
        match_type = body.get('match_type', 'product')
        match_id   = int(body.get('match_id', 0))
        action_type = body.get('action_type', '')
        memo        = body.get('memo', '').strip()
    except (ValueError, AttributeError, TypeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    valid_actions = {c[0] for c in RegulatoryMatchAction.ACTION_CHOICES}
    if action_type not in valid_actions:
        return JsonResponse({'success': False, 'error': '유효하지 않은 조치 유형'}, status=400)

    if match_type == 'ingredient':
        try:
            ing_match = NewsIngredientMatch.objects.get(pk=match_id, user=request.user)
        except NewsIngredientMatch.DoesNotExist:
            return JsonResponse({'success': False, 'error': '원료 매칭 정보 없음'}, status=404)
        action = RegulatoryMatchAction.objects.create(
            user=request.user,
            ingredient_match=ing_match,
            action_type=action_type,
            memo=memo,
        )
        # "해당 없음" 선택 시 dismissed 플래그 설정
        if action_type == RegulatoryMatchAction.ACTION_DISMISSED:
            ing_match.dismissed_yn = True
            ing_match.save(update_fields=['dismissed_yn'])
    else:
        try:
            prod_match = NewsProductMatch.objects.get(pk=match_id, product__user_id=request.user)
        except NewsProductMatch.DoesNotExist:
            return JsonResponse({'success': False, 'error': '제품 매칭 정보 없음'}, status=404)
        action = RegulatoryMatchAction.objects.create(
            user=request.user,
            product_match=prod_match,
            action_type=action_type,
            memo=memo,
        )
        if action_type == RegulatoryMatchAction.ACTION_DISMISSED:
            prod_match.false_positive_yn = True
            prod_match.false_positive_at = timezone.now()
            prod_match.save(update_fields=['false_positive_yn', 'false_positive_at'])

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    log_activity(request, 'regulatory', 'regulatory_action')
    return JsonResponse({
        'success': True,
        'action_id': action.id,
        'action_label': action.get_action_type_display(),
        'created_at': action.created_at.strftime('%Y-%m-%d %H:%M'),
    })


@login_required
@require_POST
def mark_false_positive(request):
    """
    오탐지 신고 (JSON POST)
    Body: {"match_id": 123}  — 특정 매칭을 오탐지로 표시하여 목록에서 숨김
    """
    try:
        body    = json.loads(request.body)
        match_id = int(body.get('match_id', 0))
    except (ValueError, AttributeError, TypeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    try:
        match = NewsProductMatch.objects.get(
            pk=match_id, product__user_id=request.user
        )
        match.false_positive_yn = True
        match.false_positive_at = timezone.now()
        match.read_yn = True
        match.read_at = match.read_at or timezone.now()
        match.save(update_fields=['false_positive_yn', 'false_positive_at', 'read_yn', 'read_at'])
        RegulatoryMatchAction.objects.create(
            user=request.user,
            product_match=match,
            action_type=RegulatoryMatchAction.ACTION_DISMISSED,
            memo='오탐지 신고',
        )
    except NewsProductMatch.DoesNotExist:
        return JsonResponse({'success': False, 'error': '매칭 정보를 찾을 수 없습니다.'}, status=404)

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    # 고유 뉴스 건수 기준 (사이드바 배지와 동일) — 매칭 행 수를 세면 화면마다 숫자가 달라진다
    unread = selectors.unread_news_count(request.user)
    return JsonResponse({'success': True, 'unread': unread})


@login_required
@require_POST
def mark_all_resolved(request):
    """
    특정 뉴스의 모든 매칭(제품+원료)에 대해 일괄 조치 완료 처리 (JSON POST)
    Body: {"news_id": 123}

    - 각 매칭에 RegulatoryMatchAction(action_type='resolved') 레코드 생성
    - read_yn=True 처리 병행
    """
    try:
        body    = json.loads(request.body)
        news_id = int(body.get('news_id', 0))
    except (ValueError, AttributeError, TypeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    if not news_id:
        return JsonResponse({'success': False, 'error': 'news_id 필요'}, status=400)

    now = timezone.now()

    # ── 제품 매칭 일괄 처리 ──
    prod_matches = list(NewsProductMatch.objects.filter(
        news_id=news_id,
        product__user_id=request.user,
        false_positive_yn=False,
    ))
    prod_actions = [
        RegulatoryMatchAction(
            user=request.user,
            product_match=pm,
            action_type='resolved',
            memo='모두 확인 완료',
        )
        for pm in prod_matches
    ]
    RegulatoryMatchAction.objects.bulk_create(prod_actions, ignore_conflicts=True)
    NewsProductMatch.objects.filter(id__in=[pm.id for pm in prod_matches]).update(
        read_yn=True, read_at=now
    )
    created = len(prod_actions)

    # ── 원료 매칭 일괄 처리 ──
    ing_matches = list(NewsIngredientMatch.objects.filter(
        news_id=news_id,
        user=request.user,
        dismissed_yn=False,
    ))
    ing_actions = [
        RegulatoryMatchAction(
            user=request.user,
            ingredient_match=im,
            action_type='resolved',
            memo='모두 확인 완료',
        )
        for im in ing_matches
    ]
    RegulatoryMatchAction.objects.bulk_create(ing_actions, ignore_conflicts=True)
    NewsIngredientMatch.objects.filter(id__in=[im.id for im in ing_matches]).update(read_yn=True)
    created += len(ing_actions)

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    # 남은 미확인 건수 — 사이드바 배지와 동일 기준
    unread = selectors.unread_news_count(request.user)
    return JsonResponse({'success': True, 'created': created, 'unread': unread})


@login_required
@require_POST
def mark_all_news_resolved(request):
    """
    현재 사용자의 모든 미조치 매칭(제품+원료, 전체 뉴스)에 대해 일괄 조치 완료 처리 (JSON POST)
    Body: {}

    - false_positive_yn=False 인 제품 매칭 전체에 resolved 조치 기록
    - dismissed_yn=False 인 원료 매칭 전체에 resolved 조치 기록
    - 이미 resolved/monitoring 조치가 있는 매칭은 중복 생성하지 않음
    """
    _actioned = selectors.ACTION_STATUSES
    created = 0

    # 이미 조치된 제품 매칭 ID 제외
    already_prod = set(
        RegulatoryMatchAction.objects.filter(
            product_match__product__user_id=request.user,
            product_match__false_positive_yn=False,
            action_type__in=_actioned,
        ).values_list('product_match_id', flat=True)
    )
    prod_matches = list(NewsProductMatch.objects.filter(
        product__user_id=request.user,
        false_positive_yn=False,
    ).exclude(id__in=already_prod))
    prod_actions = [
        RegulatoryMatchAction(
            user=request.user,
            product_match=pm,
            action_type='resolved',
            memo='모든 알림 일괄 확인 완료',
        )
        for pm in prod_matches
    ]
    RegulatoryMatchAction.objects.bulk_create(prod_actions, ignore_conflicts=True)
    NewsProductMatch.objects.filter(id__in=[pm.id for pm in prod_matches]).update(
        read_yn=True, read_at=timezone.now()
    )
    created = len(prod_actions)

    # 이미 조치된 원료 매칭 ID 제외
    already_ing = set(
        RegulatoryMatchAction.objects.filter(
            ingredient_match__user=request.user,
            ingredient_match__dismissed_yn=False,
            action_type__in=_actioned,
        ).values_list('ingredient_match_id', flat=True)
    )
    ing_matches = list(NewsIngredientMatch.objects.filter(
        user=request.user,
        dismissed_yn=False,
    ).exclude(id__in=already_ing))

    ing_actions = [
        RegulatoryMatchAction(
            user=request.user,
            ingredient_match=im,
            action_type='resolved',
            memo='모든 알림 일괄 확인 완료',
        )
        for im in ing_matches
    ]
    RegulatoryMatchAction.objects.bulk_create(ing_actions, ignore_conflicts=True)
    created += len(ing_actions)

    # "모든 알림 확인" 이므로 이미 조치된 매칭까지 포함해 전부 읽음 처리한다.
    # (조치 이력이 있는 매칭을 빼두면 미확인이 남는데도 배지를 0으로 표시하게 된다)
    NewsProductMatch.objects.filter(
        product__user_id=request.user, false_positive_yn=False, read_yn=False,
    ).update(read_yn=True, read_at=timezone.now())
    NewsIngredientMatch.objects.filter(
        user=request.user, dismissed_yn=False, read_yn=False,
    ).update(read_yn=True)
    NewsKeywordMatch.objects.filter(
        user=request.user, dismissed_yn=False, read_yn=False,
    ).update(read_yn=True, read_at=timezone.now())

    # 수거검사 매칭도 함께 읽음 처리한다.
    #
    # 이 버튼은 부적합 탭에 있지만 문구는 "**전체 알림** 일괄 처리" 다. 눌러
    # 놓고 수거검사 탭으로 넘어가면 빨간 점과 "전체 읽음" 칩이 그대로 남아
    # 있어서, 무엇을 더 확인해야 하는지 알 수 없었다. 한 화면 안의 세 탭이
    # 같은 "알림" 이므로 여기서 같이 턴다.
    insp_updated = InspectionMatch.objects.filter(
        user=request.user, read_yn=False,
    ).update(read_yn=True, read_at=timezone.now())

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    return JsonResponse({
        'success': True, 'created': created, 'inspection_read': insp_updated,
        'unread': selectors.unread_news_count(request.user),
    })


# ─────────────────────────────────────────────────────────────────────────────
# 수거검사(I0460) API
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def inspection_mark_all_read(request):
    """
    수거검사 전체 읽음 — 옛 주소.

    지금은 세 탭이 mark_tab_read 하나를 쓴다. 이 주소는 밖에서 부르고 있을
    수 있어 남기되, 처리는 같은 함수에 맡긴다. 두 벌로 두면 한쪽만 고쳐져
    "수거검사 탭에서만 배지가 안 지워진다" 같은 어긋남이 다시 생긴다.
    """
    updated = InspectionMatch.objects.filter(
        user=request.user, read_yn=False
    ).update(read_yn=True, read_at=timezone.now())
    cache.delete(f'regulatory_alert_count_{request.user.id}')
    return JsonResponse({'success': True, 'updated': updated})


@login_required
@require_POST
def inspection_dismiss(request):
    """
    수거검사 매칭 1건 삭제 (오매칭·해당없음 처리)
    Body: {"insp_match_id": 123}
    """
    try:
        body = json.loads(request.body)
        match_id = int(body.get('insp_match_id', 0))
    except (ValueError, AttributeError, TypeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    try:
        match = InspectionMatch.objects.get(pk=match_id, user=request.user)
        match.delete()
    except InspectionMatch.DoesNotExist:
        return JsonResponse({'success': False, 'error': '항목을 찾을 수 없습니다.'}, status=404)

    remaining = InspectionMatch.objects.filter(user=request.user, read_yn=False).count()
    return JsonResponse({'success': True, 'remaining_unread': remaining})


# ─────────────────────────────────────────────────────────────────────────────
# 탭 단위 모두 읽음 (부적합 / 행정처분 / 수거검사 / 전체)
# ─────────────────────────────────────────────────────────────────────────────

def _mark_news_tab_read(user, tab: str) -> int:
    """
    부적합·행정처분 탭의 미확인 매칭을 읽음으로 바꾼다.

    '읽음' 과 '조치 완료' 는 다른 일이다. 읽음은 "봤다", 조치는 "처리했다".
    이 함수는 앞의 것만 한다 — 조치 이력(RegulatoryMatchAction)은 남기지 않는다.
    예전에는 화면에 '전체 알림 일괄 처리'(=조치 완료) 하나뿐이라, 그냥 배지를
    지우고 싶은 사람도 되돌릴 수 없는 조치 기록을 남겨야 했다.
    """
    now = timezone.now()
    news_ids = None
    if tab in NEWS_TABS:
        src_q = (Q(api_source__in=ADMIN_API_SOURCES) if tab == TAB_ADMIN
                 else ~Q(api_source__in=ADMIN_API_SOURCES))
        news_ids = list(RegulatoryNews.objects.filter(src_q).values_list('id', flat=True))

    prod_qs = NewsProductMatch.objects.filter(
        product__user_id=user, false_positive_yn=False, read_yn=False)
    ing_qs = NewsIngredientMatch.objects.filter(
        user=user, dismissed_yn=False, read_yn=False)
    kw_qs = NewsKeywordMatch.objects.filter(
        user=user, dismissed_yn=False, read_yn=False)
    if news_ids is not None:
        prod_qs = prod_qs.filter(news_id__in=news_ids)
        ing_qs  = ing_qs.filter(news_id__in=news_ids)
        kw_qs   = kw_qs.filter(news_id__in=news_ids)

    updated  = prod_qs.update(read_yn=True, read_at=now)
    updated += ing_qs.update(read_yn=True)
    updated += kw_qs.update(read_yn=True, read_at=now)
    return updated


@login_required
@require_POST
def mark_tab_read(request):
    """
    탭 하나(또는 전체)의 알림을 모두 읽음 처리 (JSON POST).
    Body: {"tab": "insp-news" | "admin" | "insp" | "all"}

    세 탭이 한 화면 안의 같은 '알림' 이므로 처리 방법도 하나로 둔다.
    (예전에는 수거검사에만 '전체 읽음' 이 있었고, 부적합·행정처분은 되돌릴 수
     없는 '조치 완료' 로만 배지를 지울 수 있었다)
    """
    try:
        tab = (json.loads(request.body or '{}').get('tab') or 'all').strip()
    except (ValueError, AttributeError):
        tab = 'all'
    if tab not in (TAB_INSP_NEWS, TAB_ADMIN, TAB_INSPECTION, 'all'):
        return JsonResponse({'success': False, 'error': '알 수 없는 탭'}, status=400)

    news_updated = insp_updated = 0
    if tab in NEWS_TABS or tab == 'all':
        news_updated = _mark_news_tab_read(request.user, tab)
    if tab in (TAB_INSPECTION, 'all'):
        insp_updated = InspectionMatch.objects.filter(
            user=request.user, read_yn=False,
        ).update(read_yn=True, read_at=timezone.now())

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    return JsonResponse({
        'success':         True,
        'tab':             tab,
        'news_updated':    news_updated,
        'inspection_read': insp_updated,
        'updated':         news_updated + insp_updated,
        'unread':          selectors.unread_news_count(request.user),
        'inspection_unread': InspectionMatch.objects.filter(
            user=request.user, read_yn=False).count(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# 알림 제외(뮤트) 관리 — "이 키워드 때문에 오는 알림은 그만"
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def alert_mutes_api(request):
    """
    GET  /regulatory/api/alert-mutes/  — 내 제외 규칙 목록
    POST /regulatory/api/alert-mutes/  — 제외 규칙 등록 + 기존 매칭 정리
    Body(POST): {"scope": "keyword|ingredient|company", "value": "...", "memo": ""}
    """
    from v1.regulatory.services import mute as mute_service

    if request.method == 'GET':
        return JsonResponse({'mutes': [
            mute_service.mute_payload(m)
            for m in AlertMute.objects.filter(user=request.user)
        ]})

    try:
        body  = json.loads(request.body)
        scope = (body.get('scope') or '').strip()
        value = (body.get('value') or '').strip()
        memo  = (body.get('memo')  or '').strip()[:200]
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    if scope not in mute_service.VALID_SCOPES:
        return JsonResponse({'success': False, 'error': '유효하지 않은 제외 기준'}, status=400)
    if not value:
        return JsonResponse({'success': False, 'error': '끌 값이 비어 있습니다'}, status=400)
    if len(value) > 200:
        return JsonResponse({'success': False, 'error': '200자 이내로 입력해주세요'}, status=400)

    # 직접 등록한 알림 키워드와 정면으로 부딪히면, 어느 쪽이 이겼는지 화면에서
    # 설명할 수 없다. 끄는 것이 아니라 그 키워드를 지우도록 되돌려 보낸다.
    conflict = [
        r for r in AlertRule.objects.filter(user=request.user, is_active=True)
        if normalize_mute_value(r.keyword) == normalize_mute_value(value)
    ]
    if conflict:
        return JsonResponse({
            'success': False,
            'error': f'"{value}" 은(는) 직접 등록한 알림 키워드입니다. '
                     f'알림 설정에서 키워드를 삭제해 주세요.',
            'conflict_rule_ids': [r.id for r in conflict],
        }, status=409)

    try:
        result = mute_service.apply_mute(request.user, scope, value, memo)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    log_activity(request, 'regulatory', 'regulatory_mute')
    return JsonResponse({
        'success': True,
        'created': result['created'],
        'hidden':  result['hidden'],
        # 앱(식품 안심 알리미)에 예약돼 있다가 함께 거둬진 푸시 건수
        'push_cancelled': result['push_cancelled'],
        'mute':    mute_service.mute_payload(result['mute']),
        'unread':  selectors.unread_news_count(request.user),
    }, status=201 if result['created'] else 200)


@login_required
@require_POST
def alert_mute_delete_api(request, mute_id):
    """
    제외 규칙 해제 — 앞으로는 다시 받는다.
    이미 치워 둔 기존 알림은 되살리지 않는다(오탐지 처리와 같은 성질).
    """
    try:
        mute = AlertMute.objects.get(pk=mute_id, user=request.user)
    except AlertMute.DoesNotExist:
        return JsonResponse({'success': False, 'error': '규칙을 찾을 수 없습니다.'}, status=404)
    mute.delete()
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
# AlertRule 관리 (웹에서 앱 알림 키워드 추가·수정·삭제)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def alert_rules_api(request):
    """
    GET  /regulatory/api/alert-rules/  — 로그인 사용자의 AlertRule 목록
    POST /regulatory/api/alert-rules/  — 새 AlertRule 등록 (user 기반)
    Body(POST): {"category": "INGREDIENT", "keyword": "...", "match_type": "CONTAINS"}
    """
    from v1.mobile.models import AlertRule
    from v1.mobile.services.push_service import backfill_alerts_for_rule, send_immediate_for_rule

    if request.method == 'GET':
        rules = (
            AlertRule.objects
            .filter(user=request.user)
            .order_by('-created_at')
        )
        data = [
            {
                'id': r.id,
                'category': r.category,
                'category_display': r.get_category_display(),
                'keyword': r.keyword,
                'match_type': r.match_type,
                'match_type_display': r.get_match_type_display(),
                'is_active': r.is_active,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for r in rules
        ]
        return JsonResponse({'rules': data})

    # POST — 새 키워드 등록
    try:
        body = json.loads(request.body)
        category   = body.get('category', '').strip()
        keyword    = body.get('keyword', '').strip()
        match_type = body.get('match_type', 'CONTAINS').strip()
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'error': '잘못된 요청'}, status=400)

    valid_categories = {'INGREDIENT', 'COMPANY', 'ORIGIN'}
    valid_match_types = {'EXACT', 'CONTAINS'}
    if category not in valid_categories:
        return JsonResponse({'success': False, 'error': '유효하지 않은 분류'}, status=400)
    if match_type not in valid_match_types:
        return JsonResponse({'success': False, 'error': '유효하지 않은 매칭 방식'}, status=400)
    if not keyword:
        return JsonResponse({'success': False, 'error': '키워드를 입력해주세요'}, status=400)
    if len(keyword) > 100:
        return JsonResponse({'success': False, 'error': '키워드는 100자 이내로 입력해주세요'}, status=400)

    from django.conf import settings
    max_rules = settings.MOBILE_MEMBER_MAX_RULES
    active_count = AlertRule.objects.filter(user=request.user, is_active=True).count()
    if active_count >= max_rules:
        return JsonResponse({
            'success': False,
            'error': f'등록 한도({max_rules}개)에 도달했습니다. 현재 {active_count}개 등록됨',
        }, status=400)

    rule, created = AlertRule.objects.get_or_create(
        user=request.user,
        category=category,
        keyword=keyword,
        match_type=match_type,
        defaults={'is_active': True, 'device': None},
    )
    if not created and not rule.is_active:
        rule.is_active = True
        rule.save(update_fields=['is_active'])
        created = True

    if not created:
        return JsonResponse({'success': False, 'error': '이미 등록된 키워드입니다.'}, status=400)

    backfill_result = {'created': 0, 'previews': []}
    try:
        backfill_result = backfill_alerts_for_rule(rule)
        send_immediate_for_rule(rule, backfill_result.get('log_ids', []))
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'rule': {
            'id': rule.id,
            'category': rule.category,
            'category_display': rule.get_category_display(),
            'keyword': rule.keyword,
            'match_type': rule.match_type,
            'match_type_display': rule.get_match_type_display(),
            'is_active': rule.is_active,
            'created_at': rule.created_at.strftime('%Y-%m-%d %H:%M'),
        },
        'matched_count': backfill_result.get('created', 0),
        'previews': backfill_result.get('previews', []),
    }, status=201)


@login_required
@require_POST
def alert_rule_delete_api(request, rule_id):
    """
    DELETE(POST) /regulatory/api/alert-rules/<id>/delete/
    로그인 사용자 소유 AlertRule 삭제 (user 기반 단건 삭제).

    지우기 전에 그 키워드로 **예약돼 있던 푸시를 거둔다**.
    FCM 은 수집 즉시 나가지 않고 일 3회 배치로 나가므로(push_service), 새벽에
    걸린 알림을 아침에 지워도 낮에 푸시가 그대로 울린다. 게다가
    PushNotificationLog.rule_triggered 는 SET_NULL 이라, 규칙을 지우면 로그는
    "누가 부른 알림인지" 만 잃은 채 그대로 발송 대기에 남는다.
    "지웠는데 또 온다" 가 여기서 나왔다.
    """
    from v1.mobile.models import AlertRule
    from v1.mobile.services.push_service import cancel_pending_logs

    try:
        rule = AlertRule.objects.get(pk=rule_id, user=request.user)
    except AlertRule.DoesNotExist:
        return JsonResponse({'success': False, 'error': '규칙을 찾을 수 없습니다.'}, status=404)

    push = cancel_pending_logs(request.user, rule=rule)
    rule.delete()
    cache.delete(f'regulatory_alert_count_{request.user.id}')
    return JsonResponse({'success': True, 'push_cancelled': push['cancelled']})


# ─────────────────────────────────────────────────────────────────────────────
# 수거검사(I0460) 외부 export API — 구글 스프레드시트(GAS, SPC 계열사 시트) 연동용
# ─────────────────────────────────────────────────────────────────────────────
# 아래 SPC_KEYWORDS / _refine_bssh_name 은 기존 GAS(Code.gs)에 있던 로직을
# 그대로 이식한 것입니다. InspectionResult.bssh_nm 원본은 건드리지 않고,
# 이 export 응답을 만들 때만 정제해서 내보냅니다 (다른 기능은 원본 그대로 사용).

INSPECTION_SPC_KEYWORDS = [
    "리바게", "삼립", "샤니", "던킨", "배스킨", "파스쿠", "빚은", "르뽀미에",
    "따삐오", "베이커리팩토리", "샌드팜", "잇투고", "파리크라상", "파리바게뜨",
    "비알코리아", "에스피엘",
]

_CORP_SUFFIX_RE = _re.compile(r'\(주\)\s?|주식회사\s?')


def _refine_bssh_name(raw_name: str, addr: str) -> str:
    """GAS refineBsshName() 이식 — 공장 주소 충돌 해결 및 표기 정규화."""
    raw_name = raw_name or ''
    addr = addr or ''

    # 1단계: 업소명 키워드 우선
    if any(k in raw_name for k in ("파리크라상", "파리바게뜨", "파스쿠", "리바게")):
        if "달서구" in addr or "달성군" in addr:
            return "파리크라상 대구공장"
        return _CORP_SUFFIX_RE.sub('', raw_name).strip()
    if any(k in raw_name for k in ("비알코리아", "던킨", "배스킨")):
        return _CORP_SUFFIX_RE.sub('', raw_name).strip()

    # 2단계: 주소 기반 정제 (구체적 패턴 우선)
    if "논공중앙로54길 7(A동" in addr: return "샌드팜 영남공장"
    if "논공중앙로54길 7" in addr:     return "샤니 대구공장"
    if "101(3층" in addr:              return "샌드팜"
    if "101(정왕동)" in addr:          return "삼립 시화공장"
    if "서천군 종천면 종천공단길" in addr:         return "삼립 서천공장"
    if "달서구 성서로 255" in addr:                return "삼립 대구공장"
    if "달서구 갈산동 969-3" in addr:              return "파리크라상 대구공장"
    if "광산구 하남산단5번로 67" in addr:          return "호남샤니"
    if "성남시 중원구 둔촌대로457번길 13" in addr: return "샤니 성남공장"
    if "청주시 흥덕구 산단로 88" in addr:          return "삼립 청주공장"
    if "팽성읍 추팔산단1길 157" in addr:           return "에스피엘"

    # 3단계: 업소명 표기 정규화
    if "주식회사 에스피씨삼립" in raw_name or "주식회사삼립" in raw_name:
        return "삼립"
    if "주식회사샤니" in raw_name:
        return "샤니"
    if "에스피엘" in raw_name:
        return "에스피엘"
    return _CORP_SUFFIX_RE.sub('', raw_name).strip()


def inspection_export_api(request):
    """
    수거검사 결과 중 SPC 계열사 데이터만 정제해서 JSON으로 export
    (GAS 등 외부 연동용, 읽기 전용).

    인증: X-Api-Key 헤더 또는 ?key= 쿼리파라미터 (settings.INSPECTION_EXPORT_API_KEY와 일치해야 함)
    쿼리파라미터:
      - days: 최근 N일만 조회 (미지정/'all'이면 기간 제한 없이 전체 조회)
      - since: YYYYMMDD 형식, tkawydtm(수거일자) 기준 이후 데이터만 조회 (days보다 우선)
    응답: {"data": [...], "count": N}
    """
    api_key = getattr(settings, 'INSPECTION_EXPORT_API_KEY', '')
    if not api_key:
        # 서버에 키가 설정 안 돼 있으면 export 자체를 비활성화 (안전 기본값)
        return JsonResponse({'error': 'API 미설정'}, status=503)

    req_key = request.headers.get('X-Api-Key') or request.GET.get('key', '')
    if not req_key or not hmac.compare_digest(req_key, api_key):
        return JsonResponse({'error': '인증 실패'}, status=401)

    qs = InspectionResult.objects.order_by('-tkawydtm')

    since = request.GET.get('since', '').strip()
    days  = request.GET.get('days', '').strip()
    if since:
        qs = qs.filter(tkawydtm__gte=since)
    elif days and days != 'all':
        try:
            cutoff_str = (timezone.now() - timedelta(days=int(days))).strftime('%Y%m%d')
            qs = qs.filter(tkawydtm__gte=cutoff_str)
        except (ValueError, TypeError):
            pass
    # days/since 미지정 시 기간 제한 없이 전체 조회

    # 중복 제거: (수거일자, 정제된 업소명, 보고번호, 수거증번호) 기준, LAST_UPDT_DTM 최신 것 채택
    dedup: dict = {}
    for row in qs:
        # SPC 계열사만 (raw 업소명 기준 — refine 전에 걸러야 원본 GAS 로직과 동일)
        # 소재지가 비어 있으면 업소명만으로는 자사 여부를 못 거를 수 있어 제품명도 함께 확인
        is_spc = any(k in (row.bssh_nm or '') for k in INSPECTION_SPC_KEYWORDS)
        if not is_spc and not (row.site_addr or '').strip():
            is_spc = any(k in (row.prdtnm or '') for k in INSPECTION_SPC_KEYWORDS)
        if not is_spc:
            continue
        refined_name = _refine_bssh_name(row.bssh_nm, row.site_addr)
        dup_key = (row.tkawydtm, refined_name, row.prdlst_report_no, row.tkawyprno)
        item = {
            'bssh_name':      refined_name,
            'prdt_nm':        row.prdtnm,
            'judgment':       row.jdgmnt_cd_nm,
            'induty_cd_nm':   row.induty_cd_nm,
            'tkawy_dtm':      row.tkawydtm,
            'spci_type_nm':   row.tkawyspci_typecd_nm,
            'exc_instt_nm':   row.exc_instt_nm,
            'report_no':      row.prdlst_report_no,
            'tkawy_prno':     row.tkawyprno,
            'plan_titl':      row.plan_titl,
            'site_addr':      row.site_addr,
            'last_updt_dtm':  row.last_updt_dtm,
        }
        existing = dedup.get(dup_key)
        if existing is None or item['last_updt_dtm'] > existing['last_updt_dtm']:
            dedup[dup_key] = item

    data = sorted(dedup.values(), key=lambda r: r['tkawy_dtm'], reverse=True)
    return JsonResponse({'data': data, 'count': len(data)})


@login_required
@require_POST
def save_insp_profile(request):
    """수거검사 모달에서 내정보(회사명·인허가번호) AJAX 저장"""
    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = request.POST
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.company_name    = (body.get('company_name', '') or '').strip()
    profile.license_number  = (body.get('license_number', '') or '').strip()
    profile.save(update_fields=['company_name', 'license_number'])
    return JsonResponse({'success': True,
                         'company_name':   profile.company_name,
                         'license_number': profile.license_number})
