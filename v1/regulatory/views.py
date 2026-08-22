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
from django.db.models import Case, CharField, Count, Exists, F, IntegerField, Max, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from v1.regulatory import selectors
from v1.regulatory.models import (
    NewsIngredientMatch, NewsProductMatch, RegulatoryMatchAction, RegulatoryNews,
    InspectionResult, InspectionMatch, judgment_status_of,
)
from v1.mobile.models import AlertRule, PushNotificationLog
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
    insp_status = request.GET.get('insp_status', '')  # '' (전체) | 'pending' | 'done'
    if insp_status not in ('pending', 'done'):
        insp_status = ''

    # 카테고리 체크박스 (cats_sent 센티넬로 명시적 제출 여부 판별)
    cats_submitted = 'cats_sent' in request.GET
    cats = request.GET.getlist('cat') if cats_submitted else _ALL_CAT_KEYS

    # 수거검사 탭 여부 (I0460이 cats에 포함되면 수거검사 목록 표시)
    show_inspection = 'I0460' in cats
    # 일반 cat 필터는 I0460 제외하고 처리
    regular_cats = [c for c in cats if c != 'I0460']

    qs = RegulatoryNews.objects.all()

    # 기간 필터 —
    # 대표 날짜: Greatest(COALESCE(event_date, collected_date), collected_date)
    # = event_date 가 있으면 max(event_date, collected_date), 없으면 collected_date
    # 이를 기준으로 필터링하면 "최근 수집된 구 사건 항목이 과거 검색에 잘못 포함되는" 버그 방지
    from django.db.models import ExpressionWrapper, DateField
    _eff_date = ExpressionWrapper(
        Greatest(Coalesce(F('event_date'), F('collected_date')), F('collected_date')),
        output_field=DateField(),
    )

    if date_from or date_to:
        qs = qs.annotate(_eff=_eff_date)
        if date_from:
            qs = qs.filter(_eff__gte=date_from)
        if date_to:
            qs = qs.filter(_eff__lte=date_to)
        days = 'all'  # 버튼 active 표시 없애는 용도
    elif days != 'all':
        try:
            cutoff = (timezone.now() - timedelta(days=int(days))).date()
            qs = qs.annotate(_eff=_eff_date).filter(_eff__gte=cutoff)
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

    # 미확인 집합 — 집계 규칙은 selectors 한 곳에서 관리한다 (탭 미확인 dot 표시용)
    my_unread_news_ids = selectors.unread_news_ids(request.user)

    # 목록 렌더에 쓰는 매칭 정보를 한 번에 모아 온다 (행별 서브쿼리 제거)
    match_ctx = selectors.user_match_context(request.user)

    # ── risk / status 필터 (부적합·행정처분 탭) ──────────────────────────────
    # 반드시 Paginator 생성 전에 적용해야 한다.
    # (이전에는 페이지네이션 뒤에서 qs 를 재할당해 필터가 목록에 반영되지 않았다)
    if risk:
        risk_from_product = (
            NewsProductMatch.objects
            .filter(product__user_id=request.user, false_positive_yn=False, risk_level=risk)
            .values_list('news_id', flat=True)
        )
        risk_from_ingredient = (
            NewsIngredientMatch.objects
            .filter(user=request.user, dismissed_yn=False, risk_level=risk)
            .values_list('news_id', flat=True)
        )
        qs = qs.filter(Q(id__in=risk_from_product) | Q(id__in=risk_from_ingredient))

    if status in selectors.ACTION_STATUSES or status == 'no_action':
        prod_act_qs = (
            RegulatoryMatchAction.objects
            .filter(
                product_match__product__user_id=request.user,
                product_match__false_positive_yn=False,
                action_type__in=selectors.ACTION_STATUSES,
            )
            .values('product_match__news_id', 'action_type')
            .annotate(max_dt=Max('created_at'))
        )
        ing_act_qs = (
            RegulatoryMatchAction.objects
            .filter(
                ingredient_match__user=request.user,
                ingredient_match__dismissed_yn=False,
                action_type__in=selectors.ACTION_STATUSES,
            )
            .values('ingredient_match__news_id', 'action_type')
            .annotate(max_dt=Max('created_at'))
        )
        news_latest_action: dict = {}
        for row in prod_act_qs:
            nid, at, dt = row['product_match__news_id'], row['action_type'], row['max_dt']
            if nid not in news_latest_action or dt > news_latest_action[nid][1]:
                news_latest_action[nid] = (at, dt)
        for row in ing_act_qs:
            nid, at, dt = row['ingredient_match__news_id'], row['action_type'], row['max_dt']
            if nid not in news_latest_action or dt > news_latest_action[nid][1]:
                news_latest_action[nid] = (at, dt)

        if status in selectors.ACTION_STATUSES:
            filtered_ids = [nid for nid, (at, _) in news_latest_action.items() if at == status]
            qs = qs.filter(id__in=filtered_ids)
        else:  # no_action — 조치 가능한 매칭 중 조치 이력이 없는 건
            qs = qs.filter(
                id__in=(selectors.actionable_news_ids(request.user)
                        - set(news_latest_action.keys()))
            )

    # 탭 배지 건수용 스냅샷 — 어노테이션(Exists/Subquery) 이 붙기 전 queryset 을 쓴다.
    # 어노테이션된 qs 로 COUNT 하면 불필요한 서브쿼리가 함께 실행될 수 있다.
    count_qs = qs

    # 정렬용 어노테이션.
    # 예전에는 Exists/Subquery 8개를 붙여 상관 서브쿼리가 행마다 실행됐다.
    # 매칭 정보는 selectors 에서 한 번에 모아 오고, 여기서는 상수 IN 목록만 쓴다.
    matched_ids = match_ctx['all_matched']

    qs = qs.annotate(
        # sort_date = GREATEST(COALESCE(event_date, collected_date), collected_date)
        # event_date 가 NULL 이면 collected_date, 아니면 둘 중 더 최근 날짜로 정렬한다
        # (오늘 수집된 구 event_date 항목도 상단에 오도록)
        sort_date=Greatest(
            Coalesce('event_date', 'collected_date'),
            'collected_date',
        ),
        # 매칭 그룹 우선순위: 0=매칭(상단), 1=일반(하단)
        match_priority=(
            Case(
                When(id__in=matched_ids, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ) if matched_ids else Value(1, output_field=IntegerField())
        ),
    )

    if sort == 'asc':
        qs = qs.order_by(
            'match_priority',
            'sort_date',
            'collected_date',
            'created_at',
        )
    else:
        qs = qs.order_by(
            'match_priority',
            '-sort_date',
            '-collected_date',
            '-created_at',
        )

    # ── 탭 배지 건수 ─────────────────────────────────────────────────────────
    # 규칙(3개 탭 공통): 배지 숫자 = 그 탭에서 실제로 보게 될 목록의 총 건수
    #                    (현재 검색·기간·분야·등급·상태 필터가 모두 적용된 값)
    #                    미확인 여부는 숫자가 아니라 빨간 점으로만 표시한다.
    _ADMIN_SOURCES = {'I0470', 'I0480', 'I0482', 'saol_admin'}
    tab_admin_total = count_qs.filter(api_source__in=_ADMIN_SOURCES).count()
    tab_insp_total  = count_qs.exclude(api_source__in=_ADMIN_SOURCES).count()

    # 미확인 dot — 필터와 무관한 전 기간 기준 (알림 표시등 성격)
    if my_unread_news_ids:
        _unread_src_map = dict(
            RegulatoryNews.objects.filter(id__in=my_unread_news_ids)
            .values_list('id', 'api_source')
        )
        tab_admin_unread = sum(1 for src in _unread_src_map.values() if src in _ADMIN_SOURCES)
        tab_insp_unread  = len(_unread_src_map) - tab_admin_unread
    else:
        tab_admin_unread = 0
        tab_insp_unread  = 0

    # 탭별 독립 검색: 건수 집계 완료 후 qs 범위 제한
    if tab == 'admin':
        qs = qs.filter(api_source__in=_ADMIN_SOURCES)
    elif tab in ('insp-news', ''):
        qs = qs.exclude(api_source__in=_ADMIN_SOURCES)
    # tab == 'insp': 수거검사 탭은 qs 미사용 — 제한 불필요

    # 페이지네이션
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(page_num)

    # 페이지 이동용 쿼리스트링 (page·선택 파라미터 제거, tab 파라미터는 유지)
    qp = request.GET.copy()
    qp.pop('page',      None)
    qp.pop('id',        None)
    qp.pop('insp_id',     None)
    qp.pop('pub_insp_id', None)
    qp.pop('insp_page',   None)
    qp.pop('pub_page',    None)
    page_query_string = qp.urlencode()
    current_tab = tab  # 상단에서 이미 읽은 값 재사용

    # 페이지에 실제로 보이는 행에만 매칭 정보를 붙인다 (보통 50건)
    selectors.attach_match_info(page_obj.object_list, match_ctx)

    # saol_admin 지자체명 추출 (목록 패널 표시용)
    for news_item in page_obj.object_list:
        if news_item.api_source == 'saol_admin' and news_item.raw_detail_text:
            first_part = news_item.raw_detail_text.split(' | ')[0]
            news_item.saol_location = first_part.split(': ', 1)[1].strip() if ': ' in first_part else first_part.strip()
        else:
            news_item.saol_location = ''

    # 미조치 건수 — 전 기간 기준 (사이드바·홈 배지와 동일한 selectors 규칙)
    no_action_count = len(selectors.no_action_news_ids(request.user))

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
    # 내 매칭 보유 여부 — 공개 목록(대체 화면) 노출 판단용. 필터와 무관하다.
    inspection_has_matches = ins_qs_base.exists()
    # 미확인 dot·"전체 읽음" 버튼은 필터와 무관한 전 기간 기준
    inspection_unread = ins_qs_base.filter(read_yn=False).count()

    # 공용 필터(검색어·기간)는 활성 탭과 무관하게 적용한다.
    # 부적합·행정처분 배지도 같은 필터를 반영하므로, 여기만 예외로 두면
    # 수거검사 탭을 누르는 순간 배지 숫자가 바뀌어 보인다.
    ins_qs = ins_qs_base
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

    # 탭 배지 = 목록 헤더 = 현재 필터가 적용된 총 건수 (부적합·행정처분 탭과 같은 규칙)
    inspection_total  = ins_qs.count()
    insp_page_num     = request.GET.get('insp_page', 1)
    insp_paginator    = Paginator(ins_qs, 20)
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
        pub_page_num = request.GET.get('pub_page', 1)
        _PUB_FIELDS = (
            'id', 'prdtnm', 'bssh_nm', 'tkawydtm', 'jdgmnt_cd_nm',
            'exc_instt_nm', 'plan_titl', 'tkawyprno',
        )

        # 날짜 범위 지정 시 캐시 우회 (사용자별 동적 조건)
        if date_from or date_to:
            pub_qs = InspectionResult.objects.order_by('-tkawydtm')
            if date_from:
                pub_qs = pub_qs.filter(tkawydtm__gte=date_from.replace('-', ''))
            if date_to:
                pub_qs = pub_qs.filter(tkawydtm__lte=date_to.replace('-', ''))
            cached = list(pub_qs.values(*_PUB_FIELDS))
        else:
            # days 파라미터 기준 캐시 — 스케줄러 실행 시 무효화
            cache_key = f'public_insp_list_{days}'
            cached = cache.get(cache_key)
            if cached is None:
                pub_qs = InspectionResult.objects.order_by('-tkawydtm')
                if days != 'all':
                    cutoff_str = (timezone.now() - timedelta(days=int(days))).strftime('%Y%m%d')
                    pub_qs = pub_qs.filter(tkawydtm__gte=cutoff_str)
                cached = list(pub_qs.values(*_PUB_FIELDS))
                cache.set(cache_key, cached, timeout=60 * 60 * 6)

        # 검색어 필터 (캐시 데이터를 Python에서 필터링)
        if q:
            q_lower = q.lower()
            cached = [
                r for r in cached
                if q_lower in (r['prdtnm'] or '').lower()
                or q_lower in (r['bssh_nm'] or '').lower()
            ]

        # 진행 중 / 완료 필터 — 내 목록과 같은 판정 기준을 적용
        if insp_status:
            want_pending = (insp_status == 'pending')
            cached = [
                r for r in cached
                if ((r['jdgmnt_cd_nm'] or '').strip()
                    in InspectionResult.PENDING_JUDGMENTS) == want_pending
            ]

        recent_insp_total = len(cached)
        recent_insp_paginator = Paginator(cached, 20)
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
    selected_kw_logs = []       # PushNotificationLog (키워드 매칭)
    if selected_id:
        try:
            selected_news = RegulatoryNews.objects.get(pk=selected_id)

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
            # 키워드 알림 매칭 로그 (중복 제거: category+keyword+match_type 기준)
            _kw_seen = set()
            _kw_logs_raw = (
                PushNotificationLog.objects
                .filter(news=selected_news, device__user=request.user, trigger_type='keyword')
                .select_related('rule_triggered')
                .order_by('rule_triggered__category', 'rule_triggered__keyword')
            )
            for log in _kw_logs_raw:
                rule = log.rule_triggered
                if rule is None:
                    key = ('', log.trigger_label, '')
                else:
                    key = (rule.category, rule.keyword, rule.match_type)
                if key not in _kw_seen:
                    _kw_seen.add(key)
                    selected_kw_logs.append(log)
        except RegulatoryNews.DoesNotExist:
            pass

    # 웹 전용 기기를 항상 보장 — 모바일 로그아웃으로 device.user=None이 돼도 웹 키워드 유지
    from v1.mobile.models import AppDevice as _AppDevice
    # 사용자의 AlertRule 목록 — user 기반으로 직접 조회
    unique_alert_rules = list(
        AlertRule.objects
        .filter(user=request.user, is_active=True)
        .order_by('category', 'keyword')
    )

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

    return render(request, 'regulatory/news_list.html', {
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
        'q':                  q,
        'cats':               cats,
        'days':               days,
        'date_from':          date_from,
        'date_to':            date_to,
        'risk_filter':        risk,
        'status_filter':      status,
        'sort':               sort,
        'today':              date.today(),
        'saol_site_url':      saol_site_url,
        'alert_rules':        unique_alert_rules,
        'show_inspection':    show_inspection,
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
    log_activity(request, 'regulatory', 'regulatory_detail', news.pk)
    return render(request, 'regulatory/news_detail.html', {
        'news':        news,
        'my_matches':  my_matches,
        'ing_matches': ing_matches,
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

    cache.delete(f'regulatory_alert_count_{request.user.id}')
    return JsonResponse({
        'success': True, 'created': created,
        'unread': selectors.unread_news_count(request.user),
    })


# ─────────────────────────────────────────────────────────────────────────────
# 수거검사(I0460) API
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def inspection_mark_all_read(request):
    """수거검사 전체 읽음 처리"""
    updated = InspectionMatch.objects.filter(
        user=request.user, read_yn=False
    ).update(read_yn=True, read_at=timezone.now())
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
    """
    from v1.mobile.models import AlertRule

    try:
        rule = AlertRule.objects.get(pk=rule_id, user=request.user)
    except AlertRule.DoesNotExist:
        return JsonResponse({'success': False, 'error': '규칙을 찾을 수 없습니다.'}, status=404)

    rule.delete()
    return JsonResponse({'success': True})


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
