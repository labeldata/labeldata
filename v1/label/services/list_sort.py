"""
목록 화면 정렬 공용 헬퍼.

원래는 process_sorting() 이 request.GET['sort'] 를 그대로 order_by() 에 넘겼다.
없는 필드를 주면 FieldError 로 500 이 나고(?sort=user__password 로 재현됨),
인덱스 없는 TEXT 컬럼으로 정렬하면 결과가 많을 때 filesort 로 매우 느려진다.

여기서는 화면마다 정렬 가능한 컬럼을 화이트리스트로 선언하고, 그 밖의 값은
조용히 기본 정렬로 되돌린다. 헤더 렌더링에 필요한 링크·화살표 상태도 같이 만든다.

컬럼 선언 형식:
    {'field': 'prdlst_nm',          # URL 의 sort= 값이자 모델 필드 (None 이면 정렬 불가)
     'db': 'report_no_verify_YN',   # 실제 DB 필드가 다를 때만 (선택)
     'label': '제품명', 'width': '16%', 'align': 'left'}
"""


def sortable_fields(specs):
    return {c['field'] for c in specs if c.get('field')}


def db_field(specs, field):
    for c in specs:
        if c.get('field') == field:
            return c.get('db') or field
    return field


def resolve(specs, default, sort_param, order_param):
    """
    sort/order 를 화이트리스트로 검증한다.
    (order_by 에 넣을 문자열, 활성 필드, 활성 방향) 을 돌려준다.

    default 는 (필드, 'asc'|'desc') 튜플.
    """
    default_field, default_order = default
    field = (sort_param or '').strip().lstrip('-')
    if field not in sortable_fields(specs):
        field, order = default_field, default_order
    else:
        order = 'desc' if (order_param or '').strip().lower() == 'desc' else 'asc'
    column = db_field(specs, field)
    return ('-' + column if order == 'desc' else column), field, order


def columns(specs, active_field, active_order):
    """
    헤더 렌더링용 — 정렬 링크와 화살표 상태를 미리 계산해 둔다.
    같은 컬럼을 다시 누르면 방향이 뒤집힌다(토글).
    """
    out = []
    for spec in specs:
        col = dict(spec)
        if spec.get('field'):
            active = spec['field'] == active_field
            col['active'] = active
            col['next_order'] = 'desc' if (active and active_order == 'asc') else 'asc'
            col['icon'] = ('bi-caret-up-fill' if active_order == 'asc' else 'bi-caret-down-fill') \
                if active else 'bi-arrow-down-up'
        else:
            col['active'] = False
            col['icon'] = ''
        out.append(col)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 화면별 컬럼 선언
# (제품 조회·식품첨가물은 각자 서비스 모듈에 있다 — 조건 카탈로그와 함께 두는 게 맞아서)
# ─────────────────────────────────────────────────────────────────────────────

# 표시사항 관리 (MyLabel)
# 품보신고는 URL 키가 소문자 report_no_verify_yn 이고 실제 컬럼은 대문자 YN 이다.
# 기존 링크·북마크가 그대로 동작하도록 URL 키는 그대로 두고 db 로만 옮긴다.
MY_LABEL_COLUMNS = [
    {'field': 'report_no_verify_yn', 'db': 'report_no_verify_YN', 'label': '품보신고', 'width': '9%', 'align': 'center'},
    {'field': 'my_label_name', 'label': '라벨명', 'width': '16%', 'align': 'left'},
    {'field': 'prdlst_nm', 'label': '제품명', 'width': '16%', 'align': 'left'},
    {'field': 'prdlst_dcnm', 'label': '식품유형', 'width': '9%', 'align': 'center'},
    {'field': 'prdlst_report_no', 'label': '품목보고번호', 'width': '12%', 'align': 'center'},
    {'field': 'bssh_nm', 'label': '제조사명', 'width': '11%', 'align': 'center'},
    {'field': 'storage_method', 'label': '보관조건', 'width': '9%', 'align': 'center'},
    {'field': 'frmlc_mtrqlt', 'label': '포장재질', 'width': '9%', 'align': 'center'},
    {'field': 'update_datetime', 'label': '작성일', 'width': '10%', 'align': 'center'},
]
MY_LABEL_DEFAULT = ('update_datetime', 'desc')

# 내원료 관리 (MyIngredient)
MY_INGREDIENT_COLUMNS = [
    {'field': 'food_category', 'label': '분류', 'width': '12%', 'align': 'center'},
    {'field': 'prdlst_report_no', 'label': '품목보고번호', 'width': '20%', 'align': 'left'},
    {'field': 'prdlst_nm', 'label': '원재료명', 'width': '35%', 'align': 'left'},
    {'field': 'prdlst_dcnm', 'label': '식품유형', 'width': '28%', 'align': 'left'},
]
MY_INGREDIENT_DEFAULT = ('prdlst_nm', 'asc')


def my_label(sort_param, order_param):
    return resolve(MY_LABEL_COLUMNS, MY_LABEL_DEFAULT, sort_param, order_param)


def my_ingredient(sort_param, order_param):
    return resolve(MY_INGREDIENT_COLUMNS, MY_INGREDIENT_DEFAULT, sort_param, order_param)
