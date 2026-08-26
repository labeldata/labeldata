"""
부적합·처분 알림 다중 조건 검색.

제품 조회·식품첨가물과 같은 f=key&v=value 규약을 쓰고, 같은 조건 패널 템플릿
(label/_condition_panel.html)을 공유한다. 화면마다 필터 생김새가 달라
"지금 뭐가 걸려 있는지" 알기 어렵던 것을 조건 한 줄로 통일하기 위한 것이다.

빠른 조건 강제는 걸지 않는다. RegulatoryNews 는 5천 행 수준이라 어떤 조합도
즉시 끝난다 (183만 행인 품목보고와 다른 점).

조건 대부분은 컬럼을 그대로 거르지만 세 가지는 다르다.
  분야(cat)      api_source 묶음을 Q 로 펼쳐야 한다
  위험도(risk)   뉴스가 아니라 "내 제품·원료와의 매칭" 에 매겨진 등급이다
  조치상태(status) 매칭에 남긴 조치 이력에서 계산한다
앞의 둘은 여기서, 조치상태는 사용자별 계산이라 뷰가 처리한다.
"""
import logging

from django.db.models import Q

logger = logging.getLogger(__name__)

MAX_CONDITIONS = 10

# 위반유형 코드 → 화면 문구 (_news_detail_panel.html 의 배지와 같은 이름을 쓴다)
VIOLATION_TYPES = [
    ('pesticide', '잔류농약'),
    ('microbe', '미생물'),
    ('heavy_metal', '중금속'),
    ('additive', '식품첨가물'),
    ('foreign_body', '이물혼입'),
    ('deficiency', '성분미달'),
    ('labeling', '표시위반'),
    ('admin', '행정처분'),
    ('import_ban', '수입금지'),
    ('recall', '회수·폐기'),
    ('other', '기타'),
]

RISK_LEVELS = [('HIGH', '중요'), ('MED', '관심'), ('LOW', '일반')]

ACTION_STATUS_OPTIONS = [
    ('no_action', '미조치'),
    ('monitoring', '모니터링'),
    ('resolved', '조치완료'),
]


def _category_options():
    """분야 체크박스 — 기존 카테고리 정의를 그대로 쓴다 (수거검사 탭은 제외)"""
    from v1.regulatory.views import API_CATEGORIES
    return [{'value': c['key'], 'label': c['label']}
            for c in API_CATEGORIES if c.get('group') != 'insp46']


def conditions_catalog():
    """
    조건 카탈로그.
    API_CATEGORIES 를 읽어야 해서 호출 시점에 만든다 (순환 import 회피).
    """
    return [
        {'key': 'product_name', 'label': '제품명', 'field': 'product_name',
         'lookup': 'icontains', 'type': 'text'},
        {'key': 'company_name', 'label': '업체명', 'field': 'company_name',
         'lookup': 'icontains', 'type': 'text'},
        {'key': 'violation_reason', 'label': '부적합 사유', 'field': 'violation_reason',
         'lookup': 'icontains', 'type': 'text'},
        # 지금까지 검색할 수 없던 항목들
        {'key': 'raw_detail_text', 'label': '상세 원문', 'field': 'raw_detail_text',
         'lookup': 'icontains', 'type': 'text'},
        {'key': 'ai_substances', 'label': '검출 물질', 'field': 'ai_substances',
         'lookup': 'icontains', 'type': 'text'},
        {'key': 'ai_summary', 'label': 'AI 요약', 'field': 'ai_summary',
         'lookup': 'icontains', 'type': 'text'},
        # event_date 는 4,750건 중 4,728건이 비어 있다(99.5%). 그대로 거르면 거의 0건이라
        # 기존 기간 필터와 같은 대표 날짜(_eff)를 쓴다.
        #   _eff = Greatest(COALESCE(event_date, collected_date), collected_date)
        # 뷰가 항상 이 이름으로 annotate 해 둔다.
        {'key': 'event_date_from', 'label': '발생·처분일(부터)', 'field': '_eff',
         'lookup': 'gte', 'type': 'date'},
        {'key': 'event_date_to', 'label': '발생·처분일(까지)', 'field': '_eff',
         'lookup': 'lte', 'type': 'date'},
        {'key': 'cat', 'label': '분야', 'type': 'checkgroup', 'custom': 'cat',
         'options': _category_options()},
        {'key': 'violation_type', 'label': '위반유형', 'type': 'checkgroup',
         'field': 'violation_type',
         'options': [{'value': v, 'label': l} for v, l in VIOLATION_TYPES]},
        {'key': 'risk', 'label': '위험도(내 제품 기준)', 'type': 'checkgroup', 'custom': 'risk',
         'options': [{'value': v, 'label': l} for v, l in RISK_LEVELS]},
        {'key': 'status', 'label': '조치상태', 'type': 'checkgroup', 'custom': 'status',
         'options': [{'value': v, 'label': l} for v, l in ACTION_STATUS_OPTIONS]},
    ]


def catalog_by_key():
    return {c['key']: c for c in conditions_catalog()}


def parse_conditions(keys, values):
    """f=key&v=value 쌍을 검증해 조건 목록으로. 모르는 key·빈 값은 버린다."""
    catalog = catalog_by_key()
    parsed = []
    for key, raw in zip(keys, values):
        spec = catalog.get((key or '').strip())
        if spec is None:
            continue
        value = (raw or '').strip()
        if spec['type'] == 'checkgroup':
            allowed = {o['value'] for o in spec['options']}
            picked = [v for v in (x.strip() for x in value.split(',')) if v in allowed]
            if not picked:
                continue
            value = ','.join(picked)
        elif spec['type'] == 'date':
            # <input type="date"> 는 yyyy-mm-dd 로 보내고 DateField 도 같은 형식이라 그대로 쓴다
            pass
        if not value:
            continue
        parsed.append({
            'key': spec['key'], 'label': spec['label'], 'value': value,
            'type': spec['type'], 'choices': spec.get('choices', []),
            'options': spec.get('options', []),
        })
        if len(parsed) >= MAX_CONDITIONS:
            break
    return parsed


def picked(conditions, key):
    """특정 조건에서 고른 값 목록 (없으면 빈 리스트)"""
    for cond in conditions or []:
        if cond['key'] == key:
            return cond['value'].split(',')
    return []


def conditions_q(conditions) -> Q:
    """
    조건들을 AND 로 묶은 Q. 체크박스 묶음 안에서는 OR 다.

    사용자별 계산이 필요한 위험도·조치상태(custom risk/status)는 여기서 다루지 않는다.
    뷰가 picked() 로 값을 꺼내 매칭 테이블을 걸러야 한다.
    """
    catalog = catalog_by_key()
    q = Q()
    for cond in conditions or []:
        spec = catalog[cond['key']]
        custom = spec.get('custom')
        if custom in ('risk', 'status'):
            continue                      # 뷰가 처리한다
        if custom == 'cat':
            from v1.regulatory.views import _cat_condition
            q &= _cat_condition(cond['value'].split(','))
        elif spec['type'] == 'checkgroup':
            group = Q()
            for v in cond['value'].split(','):
                group |= Q(**{spec['field']: v})
            q &= group
        else:
            q &= Q(**{f"{spec['field']}__{spec['lookup']}": cond['value']})
    return q


# ─────────────────────────────────────────────────────────────────────────────
# 정렬
#
# 목록이 카드라 컬럼 헤더가 없다. 대신 "정렬: [기준] [방향]" 컨트롤을 쓴다.
# 화이트리스트로 검증하는 것은 다른 목록 화면과 같다.
# ─────────────────────────────────────────────────────────────────────────────

SORT_OPTIONS = [
    # 날짜 정렬도 대표 날짜(_eff)로 한다 — event_date 만으로는 대부분 null 이다
    {'field': 'event_date', 'db': '_eff', 'label': '발생·처분일'},
    {'field': 'collected_date', 'label': '수집일'},
    {'field': 'risk_level', 'label': '위험도'},
    {'field': 'company_name', 'label': '업체명'},
    {'field': 'product_name', 'label': '제품명'},
]
DEFAULT_SORT = ('event_date', 'desc')

PER_PAGE_CHOICES = (20, 50, 100)
DEFAULT_PER_PAGE = 50


def resolve_sort(sort_param, order_param):
    """
    sort/order 를 화이트리스트로 검증 → (order_by 문자열, 활성 필드, 방향)

    예전에는 sort 가 필드 이름이 아니라 방향('asc'|'desc')이었다.
    그때 만들어진 링크·북마크가 방향을 잃지 않도록 그 형태도 받아준다.
    """
    from v1.label.services import list_sort
    sort_param = (sort_param or '').strip()
    if sort_param in ('asc', 'desc'):
        sort_param, order_param = DEFAULT_SORT[0], sort_param
    return list_sort.resolve(SORT_OPTIONS, DEFAULT_SORT, sort_param, order_param)


def safe_per_page(value, default=DEFAULT_PER_PAGE):
    """페이지당 개수는 정해진 값만 허용한다 (?per_page=abc 로 500 이 나지 않도록)"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n in PER_PAGE_CHOICES else default
