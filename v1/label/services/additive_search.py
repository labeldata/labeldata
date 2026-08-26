"""
식품첨가물 다중 조건 검색.

제품 조회(product_search)와 같은 f=key&v=value 규약을 쓰고, 같은 조건 패널
템플릿(label/_condition_panel.html)을 공유한다.

다만 제품 조회에 있는 "빠른 조건 필수" 제한은 걸지 않는다.
식품첨가물은 662행짜리 참조 테이블이라 어떤 조합으로 훑어도 즉시 끝난다.
183만 행인 품목보고와 달리 인덱스를 강제할 이유가 없고, 강제하면 오히려
"CAS 번호만으로 찾기" 같은 정당한 검색을 막게 된다.
"""
import logging

from django.db.models import Q

from . import list_sort

logger = logging.getLogger(__name__)

MAX_CONDITIONS = 10

# 체크박스 묶음 안에서는 OR 로 묶는다 (자세한 이유는 _purpose_condition 참고)
_FLAG_VALUE = 'Y'


def _purpose_condition():
    """
    용도 플래그(착색료·감미료 등)를 체크박스 한 묶음으로 만든다.

    예전에는 용도마다 조건을 하나씩 뒀는데, 선택 목록에 비슷한 항목이 14개나
    늘어서 찾기 어려웠다. 게다가 조건끼리는 AND 라 "감미료 + 보존료" 를 고르면
    둘 다인 첨가물만 남아 항상 0건이었다(실제로 0건).
    한 묶음 안에서는 OR 로 묶어 "감미료 또는 보존료" 가 되게 한다.

    모델의 PURPOSE_FIELDS 를 그대로 쓰므로 용도가 추가돼도 여기만 따라온다.
    """
    from v1.label.models import FoodAdditive
    return {
        'key': 'purpose', 'label': '용도', 'type': 'checkgroup',
        'options': [{'value': f, 'label': l} for f, l in FoodAdditive.PURPOSE_FIELDS],
    }


def _display_table_condition():
    """
    표시기준 표4·5·6 대상 여부. 용도와 같은 이유로 체크박스 한 묶음이다.

    alias_4/5/6 은 이름이 아니라 "그 표의 대상인가" 를 뜻하는 Y 플래그다.
    (모델의 verbose_name 이 "표4 명칭+용도" 라 이름처럼 보이지만 값은 Y/null 뿐이다.
     실제 데이터: alias_4 Y 83건, alias_5 Y 155건, alias_6 Y 37건)
    """
    return {
        'key': 'display_table', 'label': '표시기준', 'type': 'checkgroup',
        'options': [
            {'value': 'alias_4', 'label': '표4 (명칭+용도)'},
            {'value': 'alias_5', 'label': '표5 (명칭·간략명)'},
            {'value': 'alias_6', 'label': '표6 (명칭·간략명·용도)'},
        ],
    }


def _base_conditions():
    # 대분류(category)는 혼합제제류를 뺀 649건이 전부 '식품첨가물' 한 값뿐이라 조건이 되지 못한다.
    # 비고(notes)도 649건 중 1건에만 있어 고르면 거의 항상 0건이다. 둘 다 뺐다.
    return [
        {'key': 'name_kr', 'label': '첨가물명(한글)', 'field': 'name_kr', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'name_en', 'label': '영문명', 'field': 'name_en', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'alias_name', 'label': '이명', 'field': 'alias_name', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'short_name', 'label': '간략명', 'field': 'short_name', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'main_purpose', 'label': '주용도', 'field': 'main_purpose', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'ins_no', 'label': 'INS No.', 'field': 'ins_no', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'e_no', 'label': 'E No.', 'field': 'e_no', 'lookup': 'icontains', 'type': 'text'},
        {'key': 'cas_no', 'label': 'CAS No.', 'field': 'cas_no', 'lookup': 'icontains', 'type': 'text'},
    ]


_conditions_cache = None


def conditions_catalog():
    """조건 카탈로그 (모델을 읽어야 해서 지연 생성한다)"""
    global _conditions_cache
    if _conditions_cache is None:
        _conditions_cache = (_base_conditions()
                             + [_display_table_condition(), _purpose_condition()])
    return _conditions_cache


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
            # 체크한 항목들이 "alias_4,alias_5" 처럼 쉼표로 이어져 온다.
            # 카탈로그에 없는 값은 버린다 (URL 을 직접 만들어도 안전하도록).
            allowed = {o['value'] for o in spec['options']}
            picked = [v for v in (x.strip() for x in value.split(',')) if v in allowed]
            if not picked:
                continue
            value = ','.join(picked)
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


def conditions_q(conditions) -> Q:
    """
    조건들을 AND 로 묶은 Q.
    체크박스 묶음(checkgroup) 안에서는 OR 다 — "감미료 또는 보존료" 가 되게 한다.
    """
    catalog = catalog_by_key()
    q = Q()
    for cond in conditions or []:
        spec = catalog[cond['key']]
        if spec['type'] == 'checkgroup':
            group = Q()
            for field in cond['value'].split(','):
                group |= Q(**{f'{field}__iexact': _FLAG_VALUE})
            q &= group
        else:
            q &= Q(**{f"{spec['field']}__{spec['lookup']}": cond['value']})
    return q


# ─────────────────────────────────────────────────────────────────────────────
# 목록 컬럼 / 정렬
#
# 정렬 가능한 컬럼만 화이트리스트로 둔다. 기존 코드는 sort 파라미터를 그대로
# order_by() 에 넘겨서, 없는 필드를 주면 FieldError 로 500 이 났다.
# 표시구분·원재료 표시명은 표4/5/6 을 조합해 만드는 값이라 DB 정렬 대상이 아니다.
# ─────────────────────────────────────────────────────────────────────────────

LIST_COLUMNS = [
    {'field': 'name_kr', 'label': '식품첨가물명', 'width': '16%', 'align': 'left'},
    {'field': None, 'label': '표시구분', 'width': '9%', 'align': 'center'},
    {'field': None, 'label': '원재료 표시명 (사용 가능)', 'width': '21%', 'align': 'left'},
    {'field': 'main_purpose', 'label': '주용도', 'width': '9%', 'align': 'center'},
    {'field': 'name_en', 'label': '영문명', 'width': '16%', 'align': 'left'},
    {'field': 'alias_name', 'label': '이명', 'width': '11%', 'align': 'left'},
    {'field': 'ins_no', 'label': 'INS', 'width': '6%', 'align': 'center'},
    {'field': 'e_no', 'label': 'E No.', 'width': '5%', 'align': 'center'},
    {'field': 'cas_no', 'label': 'CAS No.', 'width': '7%', 'align': 'center'},
]

DEFAULT_SORT = ('name_kr', 'asc')


def resolve_sort(sort_param, order_param):
    """sort/order 를 화이트리스트로 검증 → (order_by 문자열, 활성 필드, 방향)"""
    return list_sort.resolve(LIST_COLUMNS, DEFAULT_SORT, sort_param, order_param)


def list_columns(active_field, active_order):
    """헤더 렌더링용 — 정렬 링크와 화살표 상태"""
    return list_sort.columns(LIST_COLUMNS, active_field, active_order)
