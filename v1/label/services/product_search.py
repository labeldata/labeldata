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

from . import list_sort
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


def counterpart_count(category: str, search_q: str, search_field: str = 'all', conditions=None):
    """
    탭 배지용 — 지금 보고 있지 않은 쪽 탭의 결과 건수. (건수, 정확여부) 를 돌려준다.
    한 번 검색하면 국내·수입 양쪽 건수를 모두 보여주기 위해 필요하다.

    다중 조건은 탭마다 컬럼 이름이 달라 CONDITION_TWINS 로 옮긴다(제품명·식품유형·
    만든 곳·원재료명). 대응이 없는 조건은 버리므로 배지 숫자가 실제보다 커질 수 있고,
    그때는 정확여부를 False 로 알려 화면에서 '~' 를 붙인다.
    옮길 조건이 하나도 없으면 건수 대신 None(모름) 을 돌려준다.
    """
    from v1.label.models import FoodItem, ImportedFood

    other = 'imported' if category == 'domestic' else 'domestic'
    kept, exact = translate_conditions(conditions, other)

    if not search_q and not kept:
        # 옮길 수 있는 조건이 하나도 없다 — 반대쪽 건수를 말할 근거가 없다.
        # 0 이라고 하면 "없다" 는 거짓말이 되므로 모른다고 답한다.
        return (None, False) if conditions else (0, True)

    if other == 'imported':
        qs = ImportedFood.objects.filter(imported_q(search_q, search_field))
    else:
        qs = FoodItem.objects.filter(domestic_q(search_q, search_field))
    if kept:
        qs = qs.filter(conditions_q(other, kept))
    return qs.count(), exact


# ─────────────────────────────────────────────────────────────────────────────
# 다중 조건 검색
#
# 통합검색(q)은 "한 단어를 여러 컬럼에서 OR" 이고, 여기는 "여러 조건을 AND" 다.
# 조건은 (key, value) 쌍의 목록으로 들어오고, 카탈로그가 key -> 실제 컬럼/룩업을 정한다.
#
# 성능이 핵심이다. 운영 데이터는 국내 183만 / 수입 59만 행이라 icontains 를 그냥
# AND 로 쌓으면 풀스캔이다. FULLTEXT 인덱스가 덮는 컬럼에 걸린 조건들은 검색어를
# 하나의 BOOLEAN MODE 구문(+"a" +"b")으로 합쳐 인덱스로 후보를 먼저 좁히고,
# 그 뒤에 컬럼별 LIKE 로 정확히 거른다.
#
#   MATCH(제품명, 식품유형, 제조사명) AGAINST ('+"우유" +"서울"')   ← 인덱스로 좁히고
#   AND 제품명 LIKE '%우유%' AND 제조사명 LIKE '%서울%'              ← 컬럼을 정확히 맞춘다
#
# MATCH 는 세 컬럼을 묶어 보므로 그 결과는 항상 LIKE 조건의 상위집합이다.
# 좁힌 뒤 LIKE 로 거르므로 결과는 LIKE 만 쓴 것과 같고 속도만 빨라진다.
# ─────────────────────────────────────────────────────────────────────────────

# key     : 쿼리스트링에 실리는 이름 (f=key&v=value)
# label   : 화면에 보이는 이름
# field   : 실제 모델 필드
# lookup  : icontains(포함) / exact(일치) / gte,lte(날짜 범위)
# type    : text | choice | date  — 값 입력 위젯을 고른다
# choices : type=choice 일 때 고를 값
DOMESTIC_CONDITIONS = [
    {'key': 'prdlst_nm', 'label': '제품명', 'field': 'prdlst_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'prdlst_dcnm', 'label': '식품유형', 'field': 'prdlst_dcnm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'bssh_nm', 'label': '제조사명', 'field': 'bssh_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'prdlst_report_no', 'label': '품목보고번호', 'field': 'prdlst_report_no', 'lookup': 'startswith', 'type': 'text', 'fast': True},
    {'key': 'lcns_no', 'label': '인허가번호', 'field': 'lcns_no', 'lookup': 'startswith', 'type': 'text', 'fast': True},
    {'key': 'induty_cd_nm', 'label': '업종명', 'field': 'induty_cd_nm', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'rawmtrl_nm', 'label': '원재료명', 'field': 'rawmtrl_nm', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'frmlc_mtrqlt', 'label': '포장재질', 'field': 'frmlc_mtrqlt', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'pog_daycnt', 'label': '소비기한', 'field': 'pog_daycnt', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'qlity_mntnc_tmlmt_daycnt', 'label': '품질유지기한', 'field': 'qlity_mntnc_tmlmt_daycnt', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'dispos', 'label': '제품형태', 'field': 'dispos', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'usages', 'label': '용법', 'field': 'usages', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'prms_dt_from', 'label': '허가일자(부터)', 'field': 'prms_dt', 'lookup': 'gte', 'type': 'date', 'fast': True},
    {'key': 'prms_dt_to', 'label': '허가일자(까지)', 'field': 'prms_dt', 'lookup': 'lte', 'type': 'date', 'fast': True},
    {'key': 'production', 'label': '생산종료여부', 'field': 'production', 'lookup': 'exact', 'type': 'choice',
     'choices': ['예', '아니오']},
    {'key': 'hieng_lntrt_dvs_yn', 'label': '고열량·저영양', 'field': 'hieng_lntrt_dvs_yn', 'lookup': 'exact', 'type': 'choice',
     'choices': ['예', '아니오', '해당없음']},
    {'key': 'child_crtfc_yn', 'label': '어린이기호식품 인증', 'field': 'child_crtfc_yn', 'lookup': 'exact', 'type': 'choice',
     'choices': ['Y']},
]

# 제조국(mnf_ntncn_nm)·용도(prpos)는 원본 API 가 값을 내려주지 않아 전량 비어 있다.
# 고르면 항상 0건이 나오는 함정이라 목록에서 뺐다.
IMPORTED_CONDITIONS = [
    {'key': 'prduct_korean_nm', 'label': '제품명(한글)', 'field': 'prduct_korean_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'prduct_nm', 'label': '제품명(영문)', 'field': 'prduct_nm', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'itm_nm', 'label': '식품유형', 'field': 'itm_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'xport_ntncd_nm', 'label': '수출국', 'field': 'xport_ntncd_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'bsn_ofc_name', 'label': '수입업체명', 'field': 'bsn_ofc_name', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'ovsmnfst_nm', 'label': '해외제조업소', 'field': 'ovsmnfst_nm', 'lookup': 'icontains', 'type': 'text', 'fast': True},
    {'key': 'irdnt_nm', 'label': '원재료명', 'field': 'irdnt_nm', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'korlabel', 'label': '한글표시사항', 'field': 'korlabel', 'lookup': 'icontains', 'type': 'text'},
    {'key': 'dcl_prduct_se_cd_nm', 'label': '제품구분', 'field': 'dcl_prduct_se_cd_nm', 'lookup': 'exact', 'type': 'choice',
     'choices': ['가공식품', '식품첨가물']},
    {'key': 'procs_dtm_from', 'label': '수입신고일자(부터)', 'field': 'procs_dtm', 'lookup': 'gte', 'type': 'date'},
    {'key': 'procs_dtm_to', 'label': '수입신고일자(까지)', 'field': 'procs_dtm', 'lookup': 'lte', 'type': 'date'},
    {'key': 'expirde_end_dtm_from', 'label': '소비기한(부터)', 'field': 'expirde_end_dtm', 'lookup': 'gte', 'type': 'date', 'fast': True},
    {'key': 'expirde_end_dtm_to', 'label': '소비기한(까지)', 'field': 'expirde_end_dtm', 'lookup': 'lte', 'type': 'date', 'fast': True},
]

CONDITION_CATALOG = {
    'domestic': {c['key']: c for c in DOMESTIC_CONDITIONS},
    'imported': {c['key']: c for c in IMPORTED_CONDITIONS},
}

# 국내 ↔ 수입 대응 필드.
# 두 카탈로그는 컬럼 이름이 전혀 겹치지 않아서(제품명만 해도 prdlst_nm vs prduct_korean_nm)
# 이 표가 없으면 반대쪽 탭 배지가 조건을 전부 버리고 세게 된다.
# 뜻이 같은 것만 넣는다 — 국내 제조사명(bssh_nm)과 수입 해외제조업소(ovsmnfst_nm)처럼
# "만든 곳" 으로 대응되는 것까지가 한계다.
CONDITION_TWINS = {
    'prdlst_nm': 'prduct_korean_nm',   # 제품명
    'prdlst_dcnm': 'itm_nm',           # 식품유형
    'bssh_nm': 'ovsmnfst_nm',          # 만든 곳
    'rawmtrl_nm': 'irdnt_nm',          # 원재료명
}
CONDITION_TWINS.update({v: k for k, v in list(CONDITION_TWINS.items())})


def translate_conditions(conditions, target_category):
    """
    조건을 반대쪽 탭의 필드로 옮긴다. 대응이 없는 조건은 버린다.
    (옮긴 조건 목록, 하나도 안 버렸는지) 를 돌려준다.
    """
    catalog = CONDITION_CATALOG.get(target_category, {})
    moved = []
    for cond in conditions or []:
        key = cond['key'] if cond['key'] in catalog else CONDITION_TWINS.get(cond['key'])
        spec = catalog.get(key)
        if spec is None:
            continue
        moved.append({
            'key': spec['key'], 'label': spec['label'], 'value': cond['value'],
            'type': spec['type'], 'choices': spec.get('choices', []),
            'fast': bool(spec.get('fast')),
        })
    return moved, len(moved) == len(conditions or [])

_TABLE_BY_CATEGORY = {'domestic': 'food_item', 'imported': 'imported_food'}

# 한 번에 걸 수 있는 조건 수 상한. UI 로는 넘길 수 없지만 URL 을 손으로 만들 수 있어
# 서버에서도 막는다. 조건이 늘수록 LIKE 필터가 쌓여 느려진다.
MAX_CONDITIONS = 10


def parse_conditions(category, keys, values):
    """
    f=key&v=value 쌍을 카탈로그로 검증해 [{key,label,value,type,choices}] 로 만든다.
    모르는 key, 빈 값, 상한 초과분은 조용히 버린다.
    """
    catalog = CONDITION_CATALOG.get(category, {})
    parsed = []
    for key, raw in zip(keys, values):
        spec = catalog.get((key or '').strip())
        if spec is None:
            continue
        value = (raw or '').strip()
        if spec['type'] == 'date':
            # <input type="date"> 는 yyyy-mm-dd 로 보내는데 DB 는 yyyymmdd 로 들고 있다
            value = value.replace('-', '')
        elif spec['key'] == 'prdlst_report_no':
            value = normalize_report_no(value)
        if not value:
            continue
        parsed.append({
            'key': spec['key'], 'label': spec['label'], 'value': value,
            'type': spec['type'], 'choices': spec.get('choices', []),
            'fast': bool(spec.get('fast')),
        })
        if len(parsed) >= MAX_CONDITIONS:
            break
    return parsed


def conditions_q(category, conditions):
    """파싱된 조건들을 AND 로 묶은 Q. FULLTEXT 로 후보를 먼저 좁힌다."""
    if not conditions:
        return Q()

    catalog = CONDITION_CATALOG.get(category, {})
    table = _TABLE_BY_CATEGORY.get(category)
    ft_columns = set(FULLTEXT_INDEXES.get(table, {}).get('columns', ()))

    q = Q()
    ft_terms = []
    for cond in conditions:
        spec = catalog[cond['key']]
        value = cond['value']
        q &= Q(**{"%s__%s" % (spec['field'], spec['lookup']): value})
        # 포함검색이면서 FULLTEXT 가 덮는 컬럼일 때만 인덱스로 좁힐 수 있다
        if spec['lookup'] == 'icontains' and spec['field'] in ft_columns and len(value) >= MIN_FULLTEXT_LEN:
            ft_terms.append(value)

    narrowed = _fulltext_and_q(table, ft_terms)
    return (narrowed & q) if narrowed is not None else q


def _fulltext_and_q(table, terms):
    """여러 검색어를 모두 포함(AND)하는 MATCH 조건. 쓸 수 없으면 None."""
    if not terms or not table or not has_fulltext(table):
        return None
    phrases = [p for p in (_boolean_phrase(t) for t in terms) if p]
    if not phrases:
        return None
    columns = ', '.join(FULLTEXT_INDEXES[table]['columns'])
    joined = ' '.join('+%s' % p for p in phrases)
    return Q(**{'pk__in': _matched_pk_subquery(table, columns, joined)})


# ─────────────────────────────────────────────────────────────────────────────
# "빠른 조건" 강제
#
# 인덱스를 타는 조건이 하나도 없으면 183만 행 풀스캔이라 검색이 수 초씩 걸린다.
# 그래서 조건 검색에는 빠른 조건(카탈로그의 fast=True)을 최소 하나 요구한다.
#
#   FULLTEXT 컬럼   제품명·식품유형·제조사명 등 — 2글자 이상이어야 인덱스를 탄다
#                   (ngram token_size=2)
#   번호 컬럼       품목보고번호(PK)·인허가번호 — startswith 라 범위 탐색이 된다
#   날짜 컬럼       허가일자·소비기한 — 인덱스 범위 탐색
#
# 통합검색어(q)가 있으면 그 자체가 FULLTEXT 를 타므로 조건 제한을 걸지 않는다.
# ─────────────────────────────────────────────────────────────────────────────


def fast_condition_keys(category):
    """이 탭에서 '빠른 조건'으로 인정되는 key 목록 (안내 문구용)"""
    specs = IMPORTED_CONDITIONS if category == 'imported' else DOMESTIC_CONDITIONS
    return [c['key'] for c in specs if c.get('fast')]


def has_fast_condition(category, conditions) -> bool:
    """빠른 조건이 하나라도 실제로 값과 함께 걸려 있는지."""
    table = _TABLE_BY_CATEGORY.get(category)
    ft_columns = set(FULLTEXT_INDEXES.get(table, {}).get('columns', ()))
    catalog = CONDITION_CATALOG.get(category, {})
    for cond in conditions or []:
        spec = catalog.get(cond['key'])
        if not spec or not spec.get('fast'):
            continue
        # FULLTEXT 로 좁히려면 ngram token_size 이상이어야 한다.
        # "김" 한 글자는 fast 로 표시돼 있어도 실제로는 인덱스를 못 탄다.
        if spec['field'] in ft_columns and len(cond['value']) < MIN_FULLTEXT_LEN:
            continue
        return True
    return False


def search_allowed(category, conditions, search_q='') -> bool:
    """검색을 실행해도 되는지. 조건만으로 검색할 때는 빠른 조건이 하나는 있어야 한다."""
    if search_q:
        return True
    if not conditions:
        return True
    return has_fast_condition(category, conditions)


# ─────────────────────────────────────────────────────────────────────────────
# 목록 컬럼 / 정렬
#
# 정렬 가능한 컬럼만 화이트리스트로 둔다. 이유가 두 가지다.
#   - sort 파라미터가 그대로 order_by() 로 들어가면 없는 필드일 때 500 이 난다
#   - 원재료명·포장재질 같은 TEXT 컬럼 정렬은 filesort 라 결과가 많으면 매우 느리다
# (field 가 None 인 컬럼은 표시만 하고 정렬 링크를 걸지 않는다)
# ─────────────────────────────────────────────────────────────────────────────

DOMESTIC_COLUMNS = [
    {'field': 'prdlst_report_no', 'label': '품목보고번호', 'width': '15%', 'align': 'left'},
    {'field': 'prdlst_nm', 'label': '제품명', 'width': '18%', 'align': 'left'},
    {'field': 'prdlst_dcnm', 'label': '식품유형', 'width': '10%', 'align': 'center'},
    {'field': 'bssh_nm', 'label': '제조사명', 'width': '12%', 'align': 'center'},
    {'field': 'pog_daycnt', 'label': '소비기한', 'width': '10%', 'align': 'center'},
    {'field': None, 'label': '포장재질', 'width': '10%', 'align': 'center'},
    {'field': None, 'label': '원재료명', 'width': '12%', 'align': 'center'},
    {'field': 'prms_dt', 'label': '허가일자', 'width': '10%', 'align': 'center'},
]

# 수입일(procs_dtm)은 인덱스가 없어 정렬을 걸지 않는다
IMPORTED_COLUMNS = [
    {'field': 'prduct_korean_nm', 'label': '제품명', 'width': '15%', 'align': 'left'},
    {'field': 'itm_nm', 'label': '식품유형', 'width': '10%', 'align': 'center'},
    {'field': 'xport_ntncd_nm', 'label': '수출국', 'width': '10%', 'align': 'center'},
    {'field': 'bsn_ofc_name', 'label': '수입업체명', 'width': '12%', 'align': 'center'},
    {'field': 'ovsmnfst_nm', 'label': '제조사명', 'width': '15%', 'align': 'center'},
    {'field': None, 'label': '원재료명', 'width': '15%', 'align': 'center'},
    {'field': 'expirde_dtm', 'label': '소비기한', 'width': '10%', 'align': 'center'},
    {'field': None, 'label': '수입일', 'width': '8%', 'align': 'center'},
]

# 목록 화면이 실제로 읽는 컬럼.
# 이걸 지정하지 않으면 usages(4000자)·rawmtrl_ordno·korlabel 같은 TEXT 까지
# 매 행마다 함께 실려온다. 한 페이지 100행이면 그대로 낭비다.
#
# 주의: 여기 없는 필드를 템플릿에서 읽으면 행마다 추가 쿼리가 나간다(deferred).
# 목록 템플릿을 고칠 때 이 목록도 같이 맞출 것.
DOMESTIC_LIST_FIELDS = (
    'prdlst_report_no', 'prdlst_nm', 'prdlst_dcnm', 'bssh_nm',
    'pog_daycnt', 'frmlc_mtrqlt', 'rawmtrl_nm', 'rawmtrl_nm_sorted', 'prms_dt',
)
IMPORTED_LIST_FIELDS = (
    'id', 'prduct_korean_nm', 'itm_nm', 'xport_ntncd_nm', 'bsn_ofc_name',
    'ovsmnfst_nm', 'irdnt_nm', 'expirde_dtm', 'procs_dtm',
)

DEFAULT_SORT = {'domestic': ('prms_dt', 'desc'), 'imported': ('expirde_dtm', 'desc')}


def _columns_for(category):
    return IMPORTED_COLUMNS if category == 'imported' else DOMESTIC_COLUMNS


def resolve_sort(category, sort_param, order_param):
    """sort/order 를 화이트리스트로 검증 → (order_by 문자열, 활성 필드, 방향)"""
    return list_sort.resolve(
        _columns_for(category), DEFAULT_SORT.get(category, ('prms_dt', 'desc')),
        sort_param, order_param,
    )


def list_columns(category, active_field, active_order):
    """헤더 렌더링용 — 정렬 링크와 화살표 상태"""
    return list_sort.columns(_columns_for(category), active_field, active_order)
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
