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
# 원료 목록에 놓을 수 있는 칸 전부.
#
# 사용자들은 원료를 엑셀로 관리하다 여기로 온다. 그쪽에서는 필요한 열을 자기가
# 정해 놓고 보는데, 여기는 네 칸으로 고정이라 나머지를 보려면 **한 건씩 눌러야**
# 했다. 화면 절반을 목록에 쓰면서 정보는 엑셀보다 적었다.
#
# 무엇을 볼지는 사람마다 다르다. 고를 수 있게 하고 계정에 남긴다.
#
#   default  처음 열었을 때 보이는 칸
#   min      끌 수 없는 칸. 원재료명이 없으면 무엇을 고르는지 알 수가 없다
MY_INGREDIENT_ALL_COLUMNS = [
    {'field': 'food_category', 'label': '분류', 'width': '90px', 'align': 'center', 'default': True},
    {'field': 'prdlst_report_no', 'label': '품목보고번호', 'width': '150px', 'align': 'left', 'default': True},
    {'field': 'prdlst_nm', 'label': '원재료명', 'width': '220px', 'align': 'left', 'default': True, 'min': True},
    {'field': 'ingredient_display_name', 'label': '표시명', 'width': '200px', 'align': 'left'},
    {'field': 'prdlst_dcnm', 'label': '식품유형', 'width': '150px', 'align': 'left', 'default': True},
    {'field': 'bssh_nm', 'label': '제조사', 'width': '150px', 'align': 'left'},
    {'field': 'rawmtrl_nm', 'label': '하위 원료', 'width': '260px', 'align': 'left'},
    {'field': 'allergens', 'label': '알레르기', 'width': '130px', 'align': 'left'},
    {'field': 'gmo', 'label': 'GMO', 'width': '110px', 'align': 'left'},
    {'field': 'pog_daycnt', 'label': '소비기한', 'width': '130px', 'align': 'left'},
    {'field': 'frmlc_mtrqlt', 'label': '포장재질', 'width': '140px', 'align': 'left'},
    {'field': 'induty_cd_nm', 'label': '업종', 'width': '120px', 'align': 'left'},
    {'field': 'prms_dt', 'label': '허가일자', 'width': '100px', 'align': 'center'},
    {'field': 'update_datetime', 'label': '수정일', 'width': '100px', 'align': 'center'},
]

MY_INGREDIENT_DEFAULT_FIELDS = tuple(
    c['field'] for c in MY_INGREDIENT_ALL_COLUMNS if c.get('default'))
MY_INGREDIENT_REQUIRED_FIELDS = tuple(
    c['field'] for c in MY_INGREDIENT_ALL_COLUMNS if c.get('min'))


def ingredient_columns(chosen):
    """
    고른 칸을 **선언 순서대로** 돌려준다.

    사용자가 고른 순서가 아니라 선언 순서를 따른다. 목록의 칸 순서가 사람마다
    다르면 화면을 설명할 수가 없고, 순서를 바꾸고 싶다는 요구는 아직 없었다.

    끌 수 없는 칸은 무엇을 고르든 들어간다. 하나도 안 고르면 기본값으로.
    """
    picked = set(chosen or ())
    if not picked & set(MY_INGREDIENT_DEFAULT_FIELDS) and not picked:
        picked = set(MY_INGREDIENT_DEFAULT_FIELDS)
    picked |= set(MY_INGREDIENT_REQUIRED_FIELDS)
    return [c for c in MY_INGREDIENT_ALL_COLUMNS if c['field'] in picked]


MY_INGREDIENT_COLUMNS = [c for c in MY_INGREDIENT_ALL_COLUMNS if c.get('default')]
MY_INGREDIENT_DEFAULT = ('prdlst_nm', 'asc')


def my_label(sort_param, order_param):
    return resolve(MY_LABEL_COLUMNS, MY_LABEL_DEFAULT, sort_param, order_param)


def my_ingredient(sort_param, order_param):
    # 정렬은 **보이는 칸이 아니라 있는 칸 전부**로 받는다. 칸을 껐다고 그
    # 정렬로 들어온 주소가 깨지면 안 된다.
    return resolve(MY_INGREDIENT_ALL_COLUMNS, MY_INGREDIENT_DEFAULT,
                   sort_param, order_param)
