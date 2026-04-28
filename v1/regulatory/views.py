"""
규제 모니터링 Views
- 목록: 전체 부적합 뉴스 (내 제품 매칭 우선 정렬)
- 상세: 뉴스 상세 + AI 분석 + 영향받는 내 제품 목록
- API: 알림 카운트 (JSON), 읽음 처리 (POST)
"""
import json
import logging
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, CharField, Count, Exists, F, IntegerField, Max, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from v1.regulatory.models import (
    NewsIngredientMatch, NewsProductMatch, RegulatoryMatchAction, RegulatoryNews,
    InspectionResult, InspectionMatch,
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

@login_required
def news_list(request):
    """
    부적합 뉴스 목록 (Split View 왼쪽 패널)
    - 카테고리 체크박스: 국내 부적합 / 수입 부적합 / 행정처분
    - 기간 필터: 3일 / 7일 / 30일 / 전체
    - 내 제품과 매칭된 뉴스 상단 고정
    """
    q      = request.GET.get('q', '').strip()
    risk   = request.GET.get('risk', '')    # 'HIGH' | 'MED' | 'LOW' | ''
    status = request.GET.get('status', '') # 'no_action' | 'monitoring' | 'resolved' | ''
    days   = request.GET.get('days', '30') # '3' | '7' | '30' | 'all'
    sort   = request.GET.get('sort', 'desc')  # 'desc' | 'asc'
    date_from = request.GET.get('date_from', '').strip()  # YYYY-MM-DD
    date_to   = request.GET.get('date_to',   '').strip()  # YYYY-MM-DD

    # 카테고리 체크박스 (cats_sent 센티넬로 명시적 제출 여부 판별)
    cats_submitted = 'cats_sent' in request.GET
    cats = request.GET.getlist('cat') if cats_submitted else _ALL_CAT_KEYS

    # 수거검사 탭 여부 (I0460이 cats에 포함되면 수거검사 목록 표시)
    show_inspection = 'I0460' in cats
    # 일반 cat 필터는 I0460 제외하고 처리
    regular_cats = [c for c in cats if c != 'I0460']

    qs = RegulatoryNews.objects.all()

    # 기간 필터 — 날짜 범위 우선, 없으면 days
    if date_from or date_to:
        # event_date OR collected_date 기준으로 days 필터와 동일한 로직 적용
        if date_from:
            qs = qs.filter(Q(event_date__gte=date_from) | Q(collected_date__gte=date_from))
        if date_to:
            qs = qs.filter(Q(event_date__lte=date_to) | Q(collected_date__lte=date_to))
        days = 'all'  # 버튼 active 표시 없애는 용도
    elif days != 'all':
        try:
            cutoff = (timezone.now() - timedelta(days=int(days))).date()
            # event_date OR collected_date 중 하나라도 기간 내이면 표시
            qs = qs.filter(
                Q(event_date__gte=cutoff) | Q(collected_date__gte=cutoff)
            )
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

    # 위험도 필터 — 현재 사용자의 매칭 등급 기준 (제품 OR 원료 매칭)
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
        qs = qs.filter(
            Q(id__in=risk_from_product) | Q(id__in=risk_from_ingredient)
        )

    # 진행상태 필터 — 뉴스별 최신 조치 기준
    _action_statuses = ('monitoring', 'resolved')
    if status in _action_statuses or status == 'no_action':
        # 뉴스별 최신 조치 타입 계산 (제품 매칭 + 원료 매칭 합산)
        prod_act_qs = (
            RegulatoryMatchAction.objects
            .filter(
                product_match__product__user_id=request.user,
                product_match__false_positive_yn=False,
                action_type__in=_action_statuses,
            )
            .values('product_match__news_id', 'action_type')
            .annotate(max_dt=Max('created_at'))
        )
        ing_act_qs = (
            RegulatoryMatchAction.objects
            .filter(
                ingredient_match__user=request.user,
                ingredient_match__dismissed_yn=False,
                action_type__in=_action_statuses,
            )
            .values('ingredient_match__news_id', 'action_type')
            .annotate(max_dt=Max('created_at'))
        )
        # 뉴스ID별 최신 조치 타입 dict 생성
        news_latest_action = {}  # {news_id: (action_type, max_dt)}
        for row in prod_act_qs:
            nid, at, dt = row['product_match__news_id'], row['action_type'], row['max_dt']
            if nid not in news_latest_action or dt > news_latest_action[nid][1]:
                news_latest_action[nid] = (at, dt)
        for row in ing_act_qs:
            nid, at, dt = row['ingredient_match__news_id'], row['action_type'], row['max_dt']
            if nid not in news_latest_action or dt > news_latest_action[nid][1]:
                news_latest_action[nid] = (at, dt)

        if status in _action_statuses:
            # 최신 조치가 해당 status인 뉴스만
            filtered_ids = [nid for nid, (at, _) in news_latest_action.items() if at == status]
            qs = qs.filter(id__in=filtered_ids)
        else:  # no_action
            # 매칭됐지만 조치 이력이 전혀 없는 뉴스
            matched_ids = set(
                list(NewsProductMatch.objects
                     .filter(product__user_id=request.user, false_positive_yn=False)
                     .values_list('news_id', flat=True)) +
                list(NewsIngredientMatch.objects
                     .filter(user=request.user, dismissed_yn=False)
                     .values_list('news_id', flat=True))
            )
            actioned_ids = set(news_latest_action.keys())
            qs = qs.filter(id__in=(matched_ids - actioned_ids))

    # 내 매칭 집합 (제품 매칭 + 원료 보관함 단독 매칭 + 키워드 알림 매칭 합산)
    my_matched_news_ids = set(
        NewsProductMatch.objects
        .filter(product__user_id=request.user, false_positive_yn=False)
        .values_list('news_id', flat=True)
    ) | set(
        NewsIngredientMatch.objects
        .filter(user=request.user, dismissed_yn=False)
        .values_list('news_id', flat=True)
    ) | set(
        PushNotificationLog.objects
        .filter(device__user=request.user, trigger_type='keyword', news__isnull=False)
        .values_list('news_id', flat=True)
    )
    my_unread_news_ids = set(
        NewsProductMatch.objects
        .filter(product__user_id=request.user, read_yn=False, false_positive_yn=False)
        .values_list('news_id', flat=True)
    ) | set(
        NewsIngredientMatch.objects
        .filter(user=request.user, read_yn=False, dismissed_yn=False)
        .values_list('news_id', flat=True)
    ) | set(
        PushNotificationLog.objects
        .filter(device__user=request.user, trigger_type='keyword', is_read=False, news__isnull=False)
        .values_list('news_id', flat=True)
    )

    # DB 레벨 어노테이션으로 정렬 (매칭→미읽음→최신)
    matched_subq = NewsProductMatch.objects.filter(
        news=OuterRef('pk'), product__user_id=request.user, false_positive_yn=False
    )
    unread_subq = NewsProductMatch.objects.filter(
        news=OuterRef('pk'), product__user_id=request.user,
        read_yn=False, false_positive_yn=False
    )
    ing_unread_subq = NewsIngredientMatch.objects.filter(
        news=OuterRef('pk'), user=request.user,
        read_yn=False, dismissed_yn=False
    )
    # 현재 사용자의 최고 등급 매칭 risk_level (제품 or 원료)
    my_risk_subq = (
        NewsProductMatch.objects
        .filter(news=OuterRef('pk'), product__user_id=request.user, false_positive_yn=False)
        .order_by('-risk_score')
        .values('risk_level')[:1]
    )
    # 키워드 알림 매칭 어노테이션
    kw_matched_subq = PushNotificationLog.objects.filter(
        news=OuterRef('pk'), device__user=request.user, trigger_type='keyword'
    )
    # 원료 보관함 단독 매칭 어노테이션
    ing_matched_subq = NewsIngredientMatch.objects.filter(
        news=OuterRef('pk'), user=request.user, dismissed_yn=False
    )
    ing_risk_subq = (
        NewsIngredientMatch.objects
        .filter(news=OuterRef('pk'), user=request.user, dismissed_yn=False)
        .order_by('-risk_score')
        .values('risk_level')[:1]
    )
    # 최근 조치 상태 서브쿼리 (제품 매칭 / 원료 매칭)
    latest_prod_action_subq = (
        RegulatoryMatchAction.objects
        .filter(
            product_match__news=OuterRef('pk'),
            product_match__product__user_id=request.user,
            product_match__false_positive_yn=False,
            action_type__in=('monitoring', 'resolved'),
        )
        .order_by('-created_at')
        .values('action_type')[:1]
    )
    latest_ing_action_subq = (
        RegulatoryMatchAction.objects
        .filter(
            ingredient_match__news=OuterRef('pk'),
            ingredient_match__user=request.user,
            ingredient_match__dismissed_yn=False,
            action_type__in=('monitoring', 'resolved'),
        )
        .order_by('-created_at')
        .values('action_type')[:1]
    )

    # sort_date = GREATEST(COALESCE(event_date, collected_date), collected_date)
    # event_date가 NULL이면 collected_date 사용, 아니면 둘 중 더 최근 날짜 기준 정렬
    # → 오늘 수집된 구 event_date 항목도 상단에 표시
    qs = qs.annotate(
        my_matched_yn=Exists(matched_subq),
        my_unread_yn=Exists(unread_subq),
        ing_unread_yn=Exists(ing_unread_subq),
        kw_matched_yn=Exists(kw_matched_subq),
        my_risk_level=Subquery(my_risk_subq, output_field=CharField()),
        ing_matched_yn=Exists(ing_matched_subq),
        ing_risk_level=Subquery(ing_risk_subq, output_field=CharField()),
        my_action_status=Subquery(latest_prod_action_subq, output_field=CharField()),
        my_ing_action_status=Subquery(latest_ing_action_subq, output_field=CharField()),
        sort_date=Greatest(
            Coalesce('event_date', 'collected_date'),
            'collected_date',
        ),
        # 매칭 그룹 우선순위: 0=매칭(상단), 1=일반(하단)
        match_priority=Case(
            When(my_matched_yn=True,  then=Value(0)),
            When(ing_matched_yn=True, then=Value(0)),
            When(kw_matched_yn=True,  then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
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

    # 페이지네이션
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(page_num)

    # 페이지 이동용 쿼리스트링 (page·선택 파라미터 제거)
    qp = request.GET.copy()
    qp.pop('page',    None)
    qp.pop('id',      None)
    qp.pop('insp_id', None)
    page_query_string = qp.urlencode()

    # saol_admin 지자체명 추출 (목록 패널 표시용)
    for news_item in page_obj.object_list:
        if news_item.api_source == 'saol_admin' and news_item.raw_detail_text:
            first_part = news_item.raw_detail_text.split(' | ')[0]
            news_item.saol_location = first_part.split(': ', 1)[1].strip() if ': ' in first_part else first_part.strip()
        else:
            news_item.saol_location = ''

    # 요약 통계 — 현재 기간·카테고리 필터 적용 기준
    total_count   = paginator.count
    matched_count = len(my_matched_news_ids)          # 이미 위에서 제품+원료 합산
    unread_count  = len(my_unread_news_ids)

    # 미조치 건수 — 전 기간, 사이드바·헤더 배지와 동일 기준
    _action_statuses = ('monitoring', 'resolved')
    _prod_actioned = set(
        RegulatoryMatchAction.objects.filter(
            product_match__product__user_id=request.user,
            product_match__false_positive_yn=False,
            action_type__in=_action_statuses,
        ).values_list('product_match__news_id', flat=True)
    )
    _ing_actioned = set(
        RegulatoryMatchAction.objects.filter(
            ingredient_match__user=request.user,
            ingredient_match__dismissed_yn=False,
            action_type__in=_action_statuses,
        ).values_list('ingredient_match__news_id', flat=True)
    )
    no_action_count = len(my_matched_news_ids - (_prod_actioned | _ing_actioned))

    # 카테고리별 건수 (api_source 기반)
    api_counts_qs = RegulatoryNews.objects.values('api_source').annotate(cnt=Count('id'))
    api_counts = {row['api_source']: row['cnt'] for row in api_counts_qs}
    categories_with_count = [
        {**cat, 'count': sum(api_counts.get(s, 0) for s in cat['api_sources'])}
        for cat in API_CATEGORIES
    ]
    insp_cats  = [c for c in categories_with_count if c.get('group') == 'insp']
    admin_cats = [c for c in categories_with_count if c.get('group') == 'admin']
    saol_cats  = [c for c in categories_with_count if c.get('group') == 'saol']

    # ── 수거검사(I0460) — 내 매칭 건수 및 목록 ───────────────────────────────
    ins_qs = (
        InspectionMatch.objects
        .filter(user=request.user)
        .select_related('inspection', 'label')
        .order_by('-inspection__tkawydtm', '-alert_phase')
    )
    inspection_unread = ins_qs.filter(read_yn=False).count()
    inspection_total  = ins_qs.count()
    inspection_list   = ins_qs[:100]   # 탭 UI: 항상 로드, 뷰 전환은 클라이언트 JS가 처리

    # 수거검사 카테고리 건수 주입
    insp46_cats = [
        {**c, 'count': inspection_total}
        for c in categories_with_count if c.get('group') == 'insp46'
    ]

    # 상세 패널: URL 파라미터로 선택된 뉴스
    selected_id = request.GET.get('id')
    selected_news = None
    selected_matches = []
    selected_ing_matches = []   # NewsIngredientMatch 인스턴스 목록
    selected_kw_logs = []       # PushNotificationLog (키워드 매칭)
    unlinked_ingredients = []   # 구 버전 호환 (이름만 - 미사용)
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

    # 사용자의 AlertRule 목록 — 여러 기기에 동일 규칙이 있을 경우 중복 제거
    seen = set()
    unique_alert_rules = []
    for r in AlertRule.objects.filter(device__user=request.user, is_active=True).order_by('category', 'keyword', '-created_at'):
        key = (r.category, r.keyword, r.match_type)
        if key not in seen:
            seen.add(key)
            unique_alert_rules.append(r)

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

    return render(request, 'regulatory/news_list.html', {
        'news_list':          page_obj,          # 페이지 객체 (이터러블)
        'page_obj':           page_obj,
        'paginator':          paginator,
        'page_query_string':  page_query_string,
        'selected_news':           selected_news,
        'selected_matches':        selected_matches,
        'selected_ing_matches':    selected_ing_matches,
        'selected_kw_logs':        selected_kw_logs,
        'unlinked_ingredients':    unlinked_ingredients,
        'total_count':             total_count,
        'categories':         categories_with_count,
        'insp_cats':          insp_cats,
        'admin_cats':         admin_cats,
        'saol_cats':          saol_cats,
        'matched_count':      matched_count,
        'unread_count':       unread_count,
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
        'insp46_cats':        insp46_cats,
        'show_inspection':    show_inspection,
        'inspection_list':    inspection_list,
        'inspection_total':   inspection_total,
        'inspection_unread':  inspection_unread,
        'selected_insp':      selected_insp,
        'user_profile':       UserProfile.objects.filter(user=request.user).first(),
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
    """미조치 매칭 알림 수 반환 (JSON) - 상단 네비게이션 배지용
    매칭된 뉴스 중 monitoring·resolved 조치 이력이 없는 고유 뉴스 건수
    (context_processors / 미조치 필터와 동일 기준)
    """
    _action_statuses = ('monitoring', 'resolved')
    prod_matched = set(
        NewsProductMatch.objects.filter(
            product__user_id=request.user,
            false_positive_yn=False,
        ).values_list('news_id', flat=True)
    )
    ing_matched = set(
        NewsIngredientMatch.objects.filter(
            user=request.user,
            dismissed_yn=False,
        ).values_list('news_id', flat=True)
    )
    prod_actioned = set(
        RegulatoryMatchAction.objects.filter(
            product_match__product__user_id=request.user,
            product_match__false_positive_yn=False,
            action_type__in=_action_statuses,
        ).values_list('product_match__news_id', flat=True)
    )
    ing_actioned = set(
        RegulatoryMatchAction.objects.filter(
            ingredient_match__user=request.user,
            ingredient_match__dismissed_yn=False,
            action_type__in=_action_statuses,
        ).values_list('ingredient_match__news_id', flat=True)
    )
    count = len((prod_matched | ing_matched) - (prod_actioned | ing_actioned))
    return JsonResponse({'unread': count})


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

    # 읽음 처리 후 남은 미확인 뉴스 건수 (context_processors 와 동일 기준)
    prod_news = set(
        NewsProductMatch.objects.filter(
            product__user_id=request.user, read_yn=False, false_positive_yn=False,
        ).values_list('news_id', flat=True)
    )
    ing_news = set(
        NewsIngredientMatch.objects.filter(
            user=request.user, read_yn=False, dismissed_yn=False,
        ).values_list('news_id', flat=True)
    )
    unread = len(prod_news | ing_news)

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

    unread = NewsProductMatch.objects.filter(
        product__user_id=request.user, read_yn=False, false_positive_yn=False
    ).count() + NewsIngredientMatch.objects.filter(
        user=request.user, read_yn=False, dismissed_yn=False
    ).count()
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

    # 남은 미확인 건수 (기존 mark_read 기준과 동일)
    prod_news = set(
        NewsProductMatch.objects.filter(
            product__user_id=request.user, read_yn=False, false_positive_yn=False,
        ).values_list('news_id', flat=True)
    )
    ing_news = set(
        NewsIngredientMatch.objects.filter(
            user=request.user, read_yn=False, dismissed_yn=False,
        ).values_list('news_id', flat=True)
    )
    unread = len(prod_news | ing_news)

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
    _actioned = ('monitoring', 'resolved')
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
    NewsIngredientMatch.objects.filter(id__in=[im.id for im in ing_matches]).update(read_yn=True)
    created += len(ing_actions)

    return JsonResponse({'success': True, 'created': created, 'unread': 0})


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
    GET  /regulatory/api/alert-rules/  — 로그인 사용자의 모든 기기 AlertRule 목록
    POST /regulatory/api/alert-rules/  — 새 AlertRule 등록 (모든 기기에 추가)
    Body(POST): {"category": "INGREDIENT", "keyword": "...", "match_type": "CONTAINS"}
    """
    from v1.mobile.models import AlertRule, AppDevice
    from v1.mobile.services.push_service import backfill_alerts_for_rule

    user_devices = AppDevice.objects.filter(user=request.user)

    if request.method == 'GET':
        rules = (
            AlertRule.objects
            .filter(device__user=request.user)
            .select_related('device')
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
                'device_id': str(r.device.device_id),
                'device_platform': r.device.platform,
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

    # 연결된 기기가 없으면 웹 전용 가상 기기를 자동 생성
    if not user_devices.exists():
        import uuid
        web_device, _ = AppDevice.objects.get_or_create(
            user=request.user,
            platform='web',
            defaults={'device_id': f'web-{uuid.uuid4()}'},
        )
        user_devices = AppDevice.objects.filter(pk=web_device.pk)

    from django.conf import settings
    max_rules = settings.MOBILE_MEMBER_MAX_RULES

    created_rules = []
    all_over_limit = True   # 모든 기기가 한도 초과인지

    for device in user_devices:
        active_count = device.rules.filter(is_active=True).count()
        if active_count >= max_rules:
            # 이 기기는 한도 초과 — 로그 기록
            logger.warning(
                'alert_rule limit reached: user=%s device=%s platform=%s active=%d max=%d',
                request.user.id, str(device.device_id)[:12], device.platform, active_count, max_rules,
            )
            continue

        all_over_limit = False
        rule, created = AlertRule.objects.get_or_create(
            device=device,
            category=category,
            keyword=keyword,
            match_type=match_type,
            defaults={'is_active': True},
        )
        if created:
            created_rules.append(rule)
            try:
                backfill_result = backfill_alerts_for_rule(rule)
            except Exception:
                backfill_result = {'created': 0, 'previews': []}
        elif not rule.is_active:
            rule.is_active = True
            rule.save(update_fields=['is_active'])
            created_rules.append(rule)
            try:
                backfill_result = backfill_alerts_for_rule(rule)
            except Exception:
                backfill_result = {'created': 0, 'previews': []}
        # else: 이미 활성 상태로 등록된 키워드 — created_rules에 추가하지 않음

    if not created_rules:
        if all_over_limit:
            # 등록된 고유 키워드 수 (중복 제거)
            unique_count = AlertRule.objects.filter(
                device__user=request.user, is_active=True
            ).values('category', 'keyword', 'match_type').distinct().count()
            return JsonResponse({
                'success': False,
                'error': f'등록 한도({max_rules}개)에 도달했습니다. 현재 고유 키워드: {unique_count}개',
                'debug': {'reason': 'limit', 'max': max_rules, 'unique_count': unique_count},
            }, status=400)
        return JsonResponse({
            'success': False,
            'error': '이미 등록된 키워드입니다.',
            'debug': {'reason': 'duplicate'},
        }, status=400)

    first = created_rules[0]
    return JsonResponse({
        'success': True,
        'rule': {
            'id': first.id,
            'category': first.category,
            'category_display': first.get_category_display(),
            'keyword': first.keyword,
            'match_type': first.match_type,
            'match_type_display': first.get_match_type_display(),
            'is_active': first.is_active,
            'created_at': first.created_at.strftime('%Y-%m-%d %H:%M'),
        },
        'matched_count': backfill_result.get('created', 0),
        'previews': backfill_result.get('previews', []),
    }, status=201)


@login_required
@require_POST
def alert_rule_delete_api(request, rule_id):
    """
    DELETE(POST) /regulatory/api/alert-rules/<id>/delete/
    사용자 기기의 해당 키워드 규칙을 모든 기기에서 삭제.
    """
    from v1.mobile.models import AlertRule

    # 대표 규칙으로 같은 (category, keyword, match_type) 조합을 모든 기기에서 삭제
    try:
        rule = AlertRule.objects.select_related('device').get(pk=rule_id, device__user=request.user)
    except AlertRule.DoesNotExist:
        return JsonResponse({'success': False, 'error': '규칙을 찾을 수 없습니다.'}, status=404)

    AlertRule.objects.filter(
        device__user=request.user,
        category=rule.category,
        keyword=rule.keyword,
        match_type=rule.match_type,
    ).delete()

    return JsonResponse({'success': True})


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
