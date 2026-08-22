"""
제품 조회(국내·수입) 검색 백엔드.

기존 구현은 모든 검색을 icontains(LIKE '%…%')로 처리해 인덱스를 전혀 쓰지 못했다.
(EXPLAIN → type=ALL, key=None. 18,857행 기준 풀스캔 9~16ms, 운영 데이터에서는 훨씬 느림)

여기서는 MySQL FULLTEXT + ngram 파서를 쓴다.
  - 2글자 이상  : MATCH ... AGAINST (BOOLEAN MODE)  → 인덱스 사용
  - 1글자       : ngram token_size=2 라 매칭되지 않으므로 LIKE 폴백
  - 인덱스 없음 : LIKE 폴백 (배포 순서에 관계없이 항상 동작한다)

인덱스는 마이그레이션이 아니라 `manage.py ensure_search_indexes` 로 생성한다.
이 저장소는 마이그레이션 그래프가 정리되기 전이라 migrate 를 돌릴 수 없다.

로컬 실측(18,857행): "우유" 9.4ms → 0.2ms, "초콜릿" 9.4ms → 1.2ms.
LIKE 결과 집합과 FULLTEXT 결과 집합이 동일함을 5개 검색어로 확인했다.
"""
import logging
import re

from django.core.cache import cache
from django.db import connection
from django.db.models import Q

logger = logging.getLogger(__name__)

# ngram token_size=2 — 이보다 짧으면 FULLTEXT 로 찾을 수 없다
MIN_FULLTEXT_LEN = 2

# 테이블별 FULLTEXT 인덱스 정의 (관리 명령과 공유)
FULLTEXT_INDEXES = {
    'food_item': {
        'name': 'ft_food_item_search',
        'columns': ('prdlst_nm', 'prdlst_dcnm', 'bssh_nm'),
    },
    'imported_food': {
        'name': 'ft_imported_food_search',
        'columns': ('prduct_korean_nm', 'itm_nm', 'bsn_ofc_name', 'ovsmnfst_nm', 'xport_ntncd_nm'),
    },
}

_CACHE_KEY = 'product_search_ft_indexes'
_CACHE_TTL = 60 * 60 * 6


def _existing_fulltext_indexes() -> set:
    """FULLTEXT 인덱스가 실제로 만들어진 테이블 집합 (6시간 캐시)"""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return set(cached)

    found = set()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT table_name FROM information_schema.statistics
                 WHERE table_schema = DATABASE()
                   AND index_type = 'FULLTEXT'
                   AND index_name IN %s
                """,
                [tuple(v['name'] for v in FULLTEXT_INDEXES.values())],
            )
            found = {row[0] for row in cur.fetchall()}
    except Exception:
        # 정보 조회 실패 시에는 LIKE 폴백으로 동작한다 (검색이 멈추면 안 된다)
        logger.exception('[제품 조회] FULLTEXT 인덱스 확인 실패 — LIKE 폴백 사용')

    cache.set(_CACHE_KEY, list(found), _CACHE_TTL)
    return found


def invalidate_index_cache():
    """인덱스를 만들거나 지운 뒤 호출 (관리 명령에서 사용)"""
    cache.delete(_CACHE_KEY)


def has_fulltext(table: str) -> bool:
    return table in _existing_fulltext_indexes()


# 검색어에서 BOOLEAN MODE 연산자로 해석될 문자 제거
_BOOLEAN_OPERATORS = re.compile(r'[+\-><()~*"@]')


def _boolean_phrase(term: str) -> str:
    """
    검색어를 BOOLEAN MODE 구문(phrase)으로 감싼다.
    연산자 문자를 지우고 따옴표로 묶어 "포함 검색"과 같은 의미가 되게 한다.
    """
    cleaned = _BOOLEAN_OPERATORS.sub(' ', term).strip()
    return f'"{cleaned}"' if cleaned else ''


def fulltext_q(table: str, term: str):
    """
    MATCH ... AGAINST 조건을 Q 로 반환. 사용할 수 없으면 None.
    호출부는 None 일 때 LIKE 조건으로 폴백해야 한다.
    """
    if len(term) < MIN_FULLTEXT_LEN or not has_fulltext(table):
        return None
    phrase = _boolean_phrase(term)
    if not phrase:
        return None

    columns = ', '.join(FULLTEXT_INDEXES[table]['columns'])
    # extra() 는 비권장이지만 MATCH ... AGAINST 를 표현할 ORM 문법이 없다.
    # 컬럼 목록은 위 상수에서만 오고 검색어는 파라미터로 바인딩되므로 주입 위험이 없다.
    return Q(**{'pk__in': _matched_pk_subquery(table, columns, phrase)})


def _matched_pk_subquery(table: str, columns: str, phrase: str):
    """MATCH 로 걸린 PK 목록 (FULLTEXT 는 서브쿼리로 한 번만 평가된다)"""
    from django.db.models.expressions import RawSQL
    pk_col = 'prdlst_report_no' if table == 'food_item' else 'id'
    return RawSQL(
        f'SELECT {pk_col} FROM {table} '
        f'WHERE MATCH({columns}) AGAINST (%s IN BOOLEAN MODE)',
        (phrase,),
    )


def normalize_report_no(term: str) -> str:
    """
    품목보고번호 검색어 정규화.
    DB 의 prdlst_report_no 에는 하이픈이 없지만(전수 확인) 사용자는 하이픈을 넣어 입력한다.
    이전 구현은 반대로 컬럼에 REPLACE() 를 걸어 모든 행에 함수를 실행했다 —
    검색어 쪽에서 지우면 인덱스를 그대로 쓸 수 있다.
    """
    return term.replace('-', '').replace(' ', '')


def looks_like_report_no(term: str) -> bool:
    """
    검색어가 품목보고번호처럼 보이는지.

    통합검색에서 품목보고번호까지 OR 로 묶으면 인덱스를 못 쓰는 LIKE 가 끼어들어
    FULLTEXT 이득이 사라진다(실측 0.5ms -> 8.7ms). 품목보고번호는 숫자로만 이뤄지므로,
    숫자 검색어일 때만 조건을 추가한다. "우유"를 품목보고번호에서 찾을 이유도 없다.
    """
    normalized = normalize_report_no(term)
    return bool(normalized) and normalized.isdigit()


# ─────────────────────────────────────────────────────────────────────────────
# 통합검색 조건 생성 (국내·수입 공통 진입점)
# 뷰와 탭 배지 건수 계산이 같은 조건을 쓰도록 여기 한 곳에서 만든다.
# ─────────────────────────────────────────────────────────────────────────────

DOMESTIC_FIELDS = {
    'prdlst_nm': 'prdlst_nm',
    'prdlst_report_no': 'prdlst_report_no',
    'prdlst_dcnm': 'prdlst_dcnm',
    'bssh_nm': 'bssh_nm',
}
IMPORTED_FIELDS = {
    'prduct_korean_nm': 'prduct_korean_nm',
    'itm_nm': 'itm_nm',
    'xport_ntncd_nm': 'xport_ntncd_nm',
    'bsn_ofc_name': 'bsn_ofc_name',
    'ovsmnfst_nm': 'ovsmnfst_nm',
}


def domestic_q(search_q: str, search_field: str = 'all'):
    """국내 제품 통합검색 조건"""
    if not search_q:
        return Q()

    normalized = normalize_report_no(search_q)
    if search_field != 'all' and search_field in DOMESTIC_FIELDS:
        if search_field == 'prdlst_report_no':
            return Q(prdlst_report_no__icontains=normalized)
        return Q(**{f'{DOMESTIC_FIELDS[search_field]}__icontains': search_q})

    # 품목보고번호는 숫자 검색어일 때만 OR 로 붙인다.
    # 인덱스를 못 쓰는 LIKE 를 항상 OR 하면 FULLTEXT 이득이 사라진다(실측 0.5ms -> 8.7ms).
    report_no_q = Q(prdlst_report_no__icontains=normalized) if looks_like_report_no(search_q) else None

    ft = fulltext_q('food_item', search_q)
    if ft is not None:
        return (ft | report_no_q) if report_no_q else ft

    like_q = (
        Q(prdlst_nm__icontains=search_q) |
        Q(prdlst_dcnm__icontains=search_q) |
        Q(bssh_nm__icontains=search_q)
    )
    return (like_q | report_no_q) if report_no_q else like_q


def imported_q(search_q: str, search_field: str = 'all'):
    """수입 제품 통합검색 조건"""
    if not search_q:
        return Q()

    if search_field != 'all' and search_field in IMPORTED_FIELDS:
        return Q(**{f'{IMPORTED_FIELDS[search_field]}__icontains': search_q})

    ft = fulltext_q('imported_food', search_q)
    if ft is not None:
        return ft   # 수출국까지 인덱스에 포함돼 있다

    return (
        Q(prduct_korean_nm__icontains=search_q) |
        Q(itm_nm__icontains=search_q) |
        Q(xport_ntncd_nm__icontains=search_q) |
        Q(bsn_ofc_name__icontains=search_q) |
        Q(ovsmnfst_nm__icontains=search_q)
    )


def counterpart_count(category: str, search_q: str, search_field: str = 'all') -> int:
    """
    탭 배지용 — 지금 보고 있지 않은 쪽 탭의 결과 건수.
    한 번 검색하면 국내·수입 양쪽 건수를 모두 보여주기 위해 필요하다.
    """
    if not search_q:
        return 0
    from v1.label.models import FoodItem, ImportedFood
    if category == 'domestic':
        return ImportedFood.objects.filter(imported_q(search_q, search_field)).count()
    return FoodItem.objects.filter(domestic_q(search_q, search_field)).count()


# ─────────────────────────────────────────────────────────────────────────────
# 검색 전 안내 화면 데이터
# ─────────────────────────────────────────────────────────────────────────────

_INTRO_CACHE_KEY = 'product_search_intro_v1'
_INTRO_TTL = 60 * 60 * 12


def get_intro_data() -> dict:
    """
    검색어를 넣기 전에 보여줄 정보.
    데이터 규모·최신 수집일과 상위 식품유형(클릭하면 바로 검색)을 담는다.
    전량 집계라 비싸므로 12시간 캐시한다.
    """
    cached = cache.get(_INTRO_CACHE_KEY)
    if cached is not None:
        return cached

    from django.db.models import Count, Max
    from v1.label.models import FoodItem, ImportedFood

    def _fmt_date(v):
        v = (v or '').strip()
        return f'{v[:4]}.{v[4:6]}.{v[6:8]}' if len(v) >= 8 else ''

    try:
        data = {
            'domestic_total': FoodItem.objects.count(),
            'imported_total': ImportedFood.objects.count(),
            'domestic_latest': _fmt_date(FoodItem.objects.aggregate(m=Max('prms_dt'))['m']),
            'imported_latest': _fmt_date(ImportedFood.objects.aggregate(m=Max('procs_dtm'))['m']),
            'domestic_types': [
                r['prdlst_dcnm'] for r in FoodItem.objects
                .exclude(prdlst_dcnm='').exclude(prdlst_dcnm=None)
                .values('prdlst_dcnm').annotate(n=Count('pk')).order_by('-n')[:12]
            ],
            'imported_types': [
                r['itm_nm'] for r in ImportedFood.objects
                .exclude(itm_nm='').exclude(itm_nm=None)
                .values('itm_nm').annotate(n=Count('id')).order_by('-n')[:12]
            ],
        }
    except Exception:
        logger.exception('[제품 조회] 안내 데이터 집계 실패')
        return {}

    cache.set(_INTRO_CACHE_KEY, data, _INTRO_TTL)
    return data
