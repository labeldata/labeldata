"""
규제 모니터링 Views
- 목록: 전체 부적합 뉴스 (내 제품 매칭 우선 정렬)
- 상세: 뉴스 상세 + AI 분석 + 영향받는 내 제품 목록
- API: 알림 카운트 (JSON), 읽음 처리 (POST)
"""
import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import CharField, Count, Exists, F, Max, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from v1.regulatory.models import NewsIngredientMatch, NewsProductMatch, RegulatoryMatchAction, RegulatoryNews

logger = logging.getLogger(__name__)

# API 서비스별 카테고리 정의 (group: domestic=국내, import=수입)
# 순서: [국내] 검사부적합·회수판매중지·행정처분 → [수입] 검사부적합·회수판매중지·행정처분
API_CATEGORIES = [
    # ─── 국내 ───
    {'key': 'insp',   'label': '검사부적합',   'group': 'domestic', 'api_sources': ['I2620', 'I2640']},
    {'key': 'I0490',  'label': '회수·판매중지', 'group': 'domestic', 'api_sources': ['I0490']},
    {'key': 'admin',  'label': '행정처분',      'group': 'domestic', 'api_sources': ['I0470', 'I0480']},
    # ─── 수입 ───
    {'key': 'imp_insp', 'label': '수입부적합',  'group': 'import',   'api_sources': ['imp_insp']},
    {'key': 'import',   'label': '회수·판매중지','group': 'import',   'api_sources': ['import']},
    {'key': 'I0482',    'label': '행정처분',     'group': 'import',   'api_sources': ['I0482']},
]
_ALL_CAT_KEYS = [c['key'] for c in API_CATEGORIES]

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
    date_from = request.GET.get('date_from', '').strip()  # YYYY-MM-DD
    date_to   = request.GET.get('date_to',   '').strip()  # YYYY-MM-DD

    # 카테고리 체크박스 (cats_sent 센티넬로 명시적 제출 여부 판별)
    cats_submitted = 'cats_sent' in request.GET
    cats = request.GET.getlist('cat') if cats_submitted else _ALL_CAT_KEYS

    qs = RegulatoryNews.objects.all()

    # 기간 필터 — 날짜 범위 우선, 없으면 days
    if date_from or date_to:
        if date_from:
            qs = qs.filter(collected_date__gte=date_from)
        if date_to:
            qs = qs.filter(collected_date__lte=date_to)
        days = 'all'  # 버튼 active 표시 없애는 용도
    elif days != 'all':
        try:
            cutoff = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(collected_date__gte=cutoff)
        except (ValueError, TypeError):
            pass

    # 카테고리 필터
    if cats:
        qs = qs.filter(_cat_condition(cats))
    else:
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

    # 내 매칭 집합 (제품 매칭 + 원료 보관함 단독 매칭 합산)
    my_matched_news_ids = set(
        NewsProductMatch.objects
        .filter(product__user_id=request.user, false_positive_yn=False)
        .values_list('news_id', flat=True)
    ) | set(
        NewsIngredientMatch.objects
        .filter(user=request.user, dismissed_yn=False)
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

    qs = qs.annotate(
        my_matched_yn=Exists(matched_subq),
        my_unread_yn=Exists(unread_subq),
        ing_unread_yn=Exists(ing_unread_subq),
        my_risk_level=Subquery(my_risk_subq, output_field=CharField()),
        ing_matched_yn=Exists(ing_matched_subq),
        ing_risk_level=Subquery(ing_risk_subq, output_field=CharField()),
        my_action_status=Subquery(latest_prod_action_subq, output_field=CharField()),
        my_ing_action_status=Subquery(latest_ing_action_subq, output_field=CharField()),
    ).order_by(
        '-my_matched_yn', '-ing_matched_yn',
        '-my_unread_yn', '-ing_unread_yn',
        F('event_date').desc(nulls_last=True),
        '-collected_date',
        '-created_at',
    )

    # 페이지네이션
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(page_num)

    # 페이지 이동용 쿼리스트링 (page 파라미터 제거)
    qp = request.GET.copy()
    qp.pop('page', None)
    page_query_string = qp.urlencode()

    # 요약 통계 (전체 기준)
    total_count   = RegulatoryNews.objects.count()
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
    dom_cats = [c for c in categories_with_count if c.get('group') == 'domestic']
    imp_cats = [c for c in categories_with_count if c.get('group') == 'import']

    # 상세 패널: URL 파라미터로 선택된 뉴스
    selected_id = request.GET.get('id')
    selected_news = None
    selected_matches = []
    selected_ing_matches = []   # NewsIngredientMatch 인스턴스 목록
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
        except RegulatoryNews.DoesNotExist:
            pass

    return render(request, 'regulatory/news_list.html', {
        'news_list':          page_obj,          # 페이지 객체 (이터러블)
        'page_obj':           page_obj,
        'paginator':          paginator,
        'page_query_string':  page_query_string,
        'selected_news':           selected_news,
        'selected_matches':        selected_matches,
        'selected_ing_matches':    selected_ing_matches,
        'unlinked_ingredients':    unlinked_ingredients,
        'total_count':             total_count,
        'categories':         categories_with_count,
        'dom_cats':           dom_cats,
        'imp_cats':           imp_cats,
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
        product__user_id=request.user, read_yn=False
    ).count() + NewsIngredientMatch.objects.filter(
        user=request.user, read_yn=False, dismissed_yn=False
    ).count()
    return JsonResponse({'success': True, 'unread': unread})
