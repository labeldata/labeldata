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
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from django.utils import timezone

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
                   AND table_name IN %s
                   AND index_type = 'FULLTEXT'
                   AND index_name IN %s
                """,
                [
                    tuple(FULLTEXT_INDEXES),
                    tuple(v['name'] for v in FULLTEXT_INDEXES.values()),
                ],
            )
            found = {row[0] for row in cur.fetchall()}
    except Exception:
        # 정보 조회 실패 시에는 LIKE 폴백으로 동작한다 (검색이 멈추면 안 된다)
        logger.exception('[제품 조회] FULLTEXT 인덱스 확인 실패 — LIKE 폴백 사용')

    cache.set(_CACHE_KEY, list(found), _CACHE_TTL)
    return found


def warm_index_cache() -> set:
    """
    FULLTEXT 인덱스 존재 여부 캐시를 미리 채운다 (배치에서 호출).
    이 조회도 6시간 TTL + 캐시 cull 대상이라, 비어 있으면 그날 첫 검색자가 부담한다.
    """
    invalidate_index_cache()
    return _existing_fulltext_indexes()


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
# 검색 전 안내 화면 데이터 (스냅샷)
#
# 이 화면은 COUNT(*) 2개 + GROUP BY 2개로 만들어진다. 행 수에 선형으로 비싸져
# 운영 데이터에서는 초 단위가 되는데, 요청 경로에서 계산하면 캐시가 비어 있는
# 첫 사용자가 그 비용을 전부 부담한다("메뉴 최초 클릭이 느리다").
#
# 그래서 계산은 새벽 배치(refresh_product_intro)가 하고, 요청은 배치가 찍어둔
# JSON 스냅샷을 읽기만 한다. 품목제조보고는 하루 1회 수집이라 하루 지난 숫자로
# 충분하다.
#
# 저장소를 캐시가 아니라 파일로 둔 이유:
#   - FileBasedCache 는 MAX_ENTRIES(500)에 닿으면 남은 항목의 1/3을 무작위로
#     지운다(_cull). TTL 과 무관하고 키를 고를 수도 없어, 배치로 채워둬도 낮에
#     날아가고 증상이 재발한다.
#   - DB 요약 테이블이 정석이지만 이 저장소는 migrate 를 돌릴 수 없다
#     (ensure_search_indexes 를 관리 명령으로 둔 것과 같은 이유).
# ─────────────────────────────────────────────────────────────────────────────

SNAPSHOT_PATH = Path(settings.BASE_DIR).parent / 'data' / 'product_search_intro.json'

# 파일 내용을 프로세스 안에 들고 있다가 mtime 이 바뀌면 다시 읽는다.
# (두 번째 요청부터는 os.stat 한 번 말고는 I/O 가 없다)
_snapshot_memo = {'mtime': None, 'data': None}


def build_intro_data() -> dict:
    """
    안내 화면 데이터를 실제로 집계한다. 비싸다 — 배치에서만 호출할 것.
    요청 처리 중에는 get_intro_data() 를 쓴다.
    """
    from django.db.models import Count
    from v1.label.models import FoodItem, ImportedFood

    # 최신 날짜는 표시하지 않는다. prms_dt 는 허가일자라 "데이터 최신성"을 뜻하지 않는데다,
    # 원본에 5015-07-10 처럼 오신고된 건이 섞여 있어 MAX() 가 그 값에 끌려간다.
    return {
        'generated_at': timezone.localtime().isoformat(timespec='seconds'),
        'domestic_total': FoodItem.objects.count(),
        'imported_total': ImportedFood.objects.count(),
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


def save_intro_snapshot(data: dict) -> Path:
    """
    스냅샷을 원자적으로 기록한다.
    같은 디렉터리에 임시 파일을 쓰고 os.replace 로 갈아끼우므로,
    배치가 쓰는 도중에 읽는 요청이 깨진 JSON 을 보는 일이 없다.
    """
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(SNAPSHOT_PATH.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SNAPSHOT_PATH)
    except Exception:
        # 실패한 임시 파일을 남기지 않는다
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    _snapshot_memo.update(mtime=None, data=None)   # 같은 프로세스가 바로 새 값을 보도록
    return SNAPSHOT_PATH


def load_intro_snapshot():
    """스냅샷을 읽는다. 없거나 깨졌으면 None."""
    try:
        mtime = os.stat(SNAPSHOT_PATH).st_mtime
    except OSError:
        return None

    if _snapshot_memo['mtime'] == mtime:
        return _snapshot_memo['data']

    try:
        with open(SNAPSHOT_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        logger.exception('[제품 조회] 안내 데이터 스냅샷을 읽지 못했다 — %s', SNAPSHOT_PATH)
        return None

    _snapshot_memo.update(mtime=mtime, data=data)
    return data


def get_intro_data() -> dict:
    """
    검색어를 넣기 전에 보여줄 정보. 요청 경로에서 호출된다.

    스냅샷을 읽기만 한다. 낡았다고 다시 계산하지 않는다 —
    하루 지난 숫자는 문제가 아니지만 느린 화면은 문제다.
    파일이 아예 없을 때(최초 배포 직후, 크론 누락)만 한 번 계산해 굳힌다.
    """
    data = load_intro_snapshot()
    if data is not None:
        return data

    logger.warning(
        '[제품 조회] 안내 데이터 스냅샷이 없어 요청 중에 집계한다. '
        'refresh_product_intro 배치가 등록돼 있는지 확인할 것 — %s', SNAPSHOT_PATH
    )
    try:
        data = build_intro_data()
    except Exception:
        logger.exception('[제품 조회] 안내 데이터 집계 실패')
        return {}

    try:
        save_intro_snapshot(data)
    except Exception:
        # 기록에 실패해도 이번 화면은 정상으로 보여준다
        logger.exception('[제품 조회] 안내 데이터 스냅샷 기록 실패 — %s', SNAPSHOT_PATH)
    return data


def intro_generated_date(data: dict) -> str:
    """템플릿 표기용 'YYYY-MM-DD'. 값이 없으면 빈 문자열."""
    raw = (data or {}).get('generated_at')
    if not raw:
        return ''
    try:
        return datetime.fromisoformat(raw).strftime('%Y-%m-%d')
    except ValueError:
        return ''
