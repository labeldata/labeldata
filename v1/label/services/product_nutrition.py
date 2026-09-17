"""
완제품 영양성분 — **품목보고번호가 같으면 같은 품목이다.**

제품 조회(FoodItem)와 식약처 영양성분DB(PublicFoodNutrition)를 잇는 자리.
새 표도 새 API 도 없다 — 적재할 때 이미 넣어 둔 `item_report_no` 가
`FoodItem.prdlst_report_no` 와 같은 번호라, 조인 하나면 닿는다.

    FoodItem.prdlst_report_no  ──  PublicFoodNutrition.item_report_no
         (PK)                            (db_index)

**이 파일은 번호로 붙는 길만 다룬다.** 이름으로 찾는 길(제조사+제품명, 유사도
후보)은 여기 없다. 번호가 맞으면 고를 것이 없지만 이름은 사람이 골라야 하고
(`nutrition_candidates` 가 그 일을 한다), 둘을 한 함수에 섞으면 화면이
"확정된 값" 과 "골라야 하는 후보" 를 같은 얼굴로 내보이게 된다.

번호가 같은 행이 여럿일 때
──────────────────────────
같은 품목을 여러 해에 조사하면 행이 여럿 생긴다. 고르는 규칙은 하나다 —
**어떻게 만든 값인가 → 언제 것인가 → 스스로 검산했는가.**

주의: `crt_mth_nm` 을 SQL 에서 `-crt_mth_nm` 으로 정렬하면 **거꾸로 선다.**
한글 코드값 차례가 수집(U+C218) > 산출(U+C0B0) > 분석(U+BD84) 이라
내림차순이면 가장 못 믿을 '수집' 이 1 위가 된다. 그래서 여기서는 SQL 정렬에
맡기지 않고 파이썬에서 **뜻으로** 세운다(_METHOD_RANK).

100 mL 기준을 빼지 않는다
─────────────────────────
원료 배합(`nutrition_candidates`)은 부피 기준 행을 뺀다 — 비중을 모르면
중량 배합에 못 쓰기 때문이다. 그런데 **완제품 표시는 다르다.** 음료는 애초에
"100 mL 당" 으로 표시하는 물건이라, 여기서 빼면 음료가 통째로 사라진다.
대신 기준량을 **늘 함께 내보낸다** — 100 g 인지 100 mL 인지 모르는 채로
숫자만 보면 안 된다.
"""
import logging

from v1.label.constants import NUTRITION_DATA
from v1.label.models import PublicFoodNutrition
from v1.label.services.nutrition_calc import _number, display_value

logger = logging.getLogger(__name__)

# 화면에 내보이는 성분. 순서는 표시기준의 차례(NUTRITION_DATA['order'])를 따른다 —
# 영양성분표를 눈으로 대조하는 사람이 같은 줄에서 같은 것을 보게 한다.
#
# 식약처 DB 가 실제로 들고 있는 칸만 든다. 비타민류는 적재본에 없다
# (mfds_nutrition.NUTRIENT_MAP 참고).
DISPLAY_FIELDS = (
    'calories', 'natriums', 'carbohydrates', 'sugars', 'fats',
    'trans_fats', 'saturated_fats', 'cholesterols', 'proteins',
    'dietary_fiber', 'calcium', 'iron', 'magnesium', 'phosphorus',
    'potassium', 'zinc', 'selenium',
)

# 내 표시사항으로 옮기는 칸. **표시 필수 아홉만 옮긴다.**
#
# 성적서 판독이 제품에 값을 넣는 자리(products.views._LABEL_NUTRITION_FIELDS)와
# 같은 아홉이다. 두 경로가 다른 칸을 채우면 "어디서 넣었느냐" 에 따라 라벨의
# 모양이 달라진다. 무기질까지 옮기면 쓸 생각이 없던 줄이 표에 생긴다 —
# 필요하면 계산기에서 사람이 더한다.
COPY_FIELDS = (
    'calories', 'carbohydrates', 'sugars', 'proteins', 'fats',
    'saturated_fats', 'trans_fats', 'cholesterols', 'natriums',
)

# 어떻게 만든 값인가. 작을수록 앞선다.
# 적재본 분포는 수집 310,488 · 분석 5,355 · 산출 3,153 이다.
_METHOD_RANK = {'분석': 0, '산출': 1, '수집': 2}

# 표시에 쓸 수 있는 기준 단위. 빈 값(기준량을 못 읽은 행)은 쓰지 않는다 —
# 기준량을 모르는 채 숫자를 보이면 100 배 틀린 표가 화면에 뜬다.
USABLE_BASIS = (PublicFoodNutrition.BASIS_G, PublicFoodNutrition.BASIS_ML)


def normalize(report_no):
    """
    조인 키로 쓸 수 있는 모양인가. 아니면 빈 문자열.

    `mfds_nutrition.normalize_report_no` 와 같은 규칙이다 — 적재할 때 숫자가
    아닌 번호('2020_DNSP_04044')를 빈 값으로 두었으므로, 찾는 쪽도 숫자일
    때만 묻는다. 사용자가 넣은 하이픈은 지운다.
    """
    text = (report_no or '').strip().replace('-', '').replace(' ', '')
    return text if text.isdigit() else ''


def _usable_rows():
    """표시에 쓸 수 있는 행만. 이 조건은 한 곳에서만 정한다."""
    return (PublicFoodNutrition.objects
            .filter(basis_unit__in=USABLE_BASIS)
            .exclude(calories__isnull=True)
            .exclude(verify_status=PublicFoodNutrition.VERIFY_FAIL))


def _sort_key(row):
    """
    같은 번호의 행들을 세우는 차례. 작을수록 앞선다.

        ① 어떻게 만든 값인가   분석 > 산출 > 수집
        ② 언제 것인가         최근 조사가 앞선다
        ③ 검산했는가          통과한 행이 앞선다
    """
    method = _METHOD_RANK.get((row.crt_mth_nm or '').strip(), 9)

    year = (row.research_ymd or '')[:4]
    recency = -int(year) if year.isdigit() else 0

    verified = 0 if row.verify_status == PublicFoodNutrition.VERIFY_PASS else 1
    return (method, recency, verified, row.pk)


def best_row(rows):
    """행 여럿 중 하나를 고른다. 비면 None."""
    rows = [r for r in rows if r is not None]
    return min(rows, key=_sort_key) if rows else None


def for_report_no(report_no):
    """
    이 품목보고번호의 영양성분 행. 없으면 None.

    번호가 맞으면 사람에게 묻지 않는다 — 같은 번호는 같은 품목이라 고를 것이
    없다. 여러 해 조사분이 겹칠 때만 _sort_key 가 하나를 세운다.
    """
    key = normalize(report_no)
    if not key:
        return None
    return best_row(list(_usable_rows().filter(item_report_no=key)))


def for_report_nos(report_nos):
    """
    여러 번호를 **한 번의 질의로** 찾는다. {번호: 행} 을 돌려준다.

    목록 화면이 쓴다. 한 쪽이 20~100 행인데 행마다 묻게 두면 그만큼 질의가
    나간다(N+1). `item_report_no` 에 인덱스가 있어 IN 한 번이면 끝난다.
    """
    keys = {normalize(no) for no in (report_nos or [])}
    keys.discard('')
    if not keys:
        return {}

    grouped = {}
    for row in _usable_rows().filter(item_report_no__in=keys):
        grouped.setdefault(row.item_report_no, []).append(row)
    return {no: best_row(rows) for no, rows in grouped.items()}


# 수치 범위로 찾을 수 있는 성분. **표시 필수 아홉만 연다.**
#
# 적재본이 들고 있는 칸은 스무 개가 넘지만, 무기질은 빈 칸이 흔해서 범위를
# 걸면 "값이 없는 행" 까지 조용히 걸러 낸다 — 찾는 사람은 "그런 제품이 없다"
# 로 읽지만 실제로는 "그 칸을 안 잰 제품이 빠진 것" 이다. 아홉은 표시 의무가
# 있어 채움률이 높다.
#
#   field  : PublicFoodNutrition 의 칸
#   label  : 화면에 보이는 이름
#   unit   : 기준량(100g·100mL)당 단위
RANGE_FIELDS = (
    {'field': 'calories',       'label': '열량',     'unit': 'kcal'},
    {'field': 'natriums',       'label': '나트륨',   'unit': 'mg'},
    {'field': 'carbohydrates',  'label': '탄수화물', 'unit': 'g'},
    {'field': 'sugars',         'label': '당류',     'unit': 'g'},
    {'field': 'fats',           'label': '지방',     'unit': 'g'},
    {'field': 'saturated_fats', 'label': '포화지방', 'unit': 'g'},
    {'field': 'trans_fats',     'label': '트랜스지방', 'unit': 'g'},
    {'field': 'cholesterols',   'label': '콜레스테롤', 'unit': 'mg'},
    {'field': 'proteins',       'label': '단백질',   'unit': 'g'},
)

RANGE_FIELD_NAMES = tuple(spec['field'] for spec in RANGE_FIELDS)


def matching_report_nos(filters=()):
    """
    조건에 맞는 영양성분 행의 **품목보고번호**만 뽑는 하위질의.

    filters 는 (칸, 룩업, 값) 의 목록이다 — [('calories', 'gte', 100.0), ...].

    **한 번에 걸어야 한다.** 조건마다 따로 하위질의를 만들어 AND 로 묶으면
    "열량 100 이상인 행이 있고, 나트륨 200 이하인 행도 있다" 가 되어 **서로
    다른 행**으로 맞아도 통과한다. 같은 제품의 여러 해 조사분이 갈리는 순간
    엉뚱한 결과가 나온다. 그래서 filters 를 한 질의 안에서 모두 건다.

    **빠른 조건과 함께 쓸 때만 안전하다.** 이것만으로 거르면 국내 183 만 행에
    24 만 개짜리 반조인이 걸린다. 제품 조회는 이미 빠른 조건을 하나 요구하므로
    (product_search.search_allowed) 바깥이 먼저 좁혀진 뒤에 붙는다.

    빈 칸(NULL)은 걸리지 않는다. `calories__gte=0` 도 NULL 은 통과하지 못하는
    것이 SQL 의 규칙이고, 여기서는 그것이 맞다 — 안 잰 값을 0 으로 볼 수 없다.
    """
    qs = (_usable_rows()
          .exclude(item_report_no='')
          .exclude(item_report_no__isnull=True))
    for field, lookup, value in (filters or ()):
        if field not in RANGE_FIELD_NAMES:
            # 카탈로그에 없는 칸은 걸지 않는다. 조용히 버리지 말고 알린다 —
            # 오타 하나로 조건이 사라지면 결과가 넓어진 줄을 아무도 모른다.
            raise ValueError('영양성분 검색에 쓸 수 없는 칸: %s' % field)
        qs = qs.filter(**{'%s__%s' % (field, lookup): value})
    return qs.values('item_report_no')


def has_nutrition_subquery():
    """'영양성분이 있는 제품' — 범위 조건이 없는 matching_report_nos."""
    return matching_report_nos()


# ─────────────────────────────────────────────────────────────────────────────
# 화면이 쓰는 모양
# ─────────────────────────────────────────────────────────────────────────────

def basis_text(row):
    """'100g당' / '100mL당'. 기준량을 모르면 빈 문자열."""
    if not row or not row.basis_unit:
        return ''
    amount = row.basis_amount
    if amount is None:
        return ''
    whole = int(amount) if float(amount).is_integer() else amount
    return '%s%s당' % (whole, row.basis_unit)


def _percent(field, value):
    """1일 영양성분 기준치에 대한 비율(%). 기준치가 없는 성분은 None."""
    spec = NUTRITION_DATA.get(field) or {}
    daily = spec.get('daily_value')
    number = _number(value)
    if not daily or number is None:
        return None
    return int(round(number / float(daily) * 100))


def panel(row):
    """
    영양성분 한 판. 값이 있는 성분만 표시 차례대로 돌려준다.

    **빈 칸을 0 으로 채우지 않는다.** 모르는 것과 없는 것은 다르다 — 적재본에
    빈 칸이 흔한데 0 으로 메우면 "이 제품에는 나트륨이 없다" 는 거짓말이 된다.

    표시값(display)은 `nutrition_calc.display_value` 를 통과시킨다. 계산기와
    반올림 규칙이 한 벌이어야 같은 제품이 화면마다 다른 숫자를 갖지 않는다.
    """
    if row is None:
        return []

    out = []
    for field in DISPLAY_FIELDS:
        raw = getattr(row, field, None)
        if _number(raw) is None:
            continue
        spec = NUTRITION_DATA.get(field) or {}
        out.append({
            'field': field,
            'label': spec.get('label', field),
            'unit': spec.get('unit', ''),
            'raw': _number(raw),
            'display': display_value(field, raw),
            'percent': _percent(field, raw),
            'indent': bool(spec.get('indent')),
            'required': bool(spec.get('required')),
            'copied': field in COPY_FIELDS,
        })
    return out


def origin(row):
    """
    이 값이 어디서 왔는가. **값만큼 중요하다.**

    "이 숫자 어디서 왔죠" 에 답하지 못하는 표는 감사에서 설명할 수 없다.
    """
    if row is None:
        return None
    return {
        'food_cd': row.food_cd,
        'food_nm': row.food_nm_kr,
        'maker': row.maker_nm or '',
        'group': row.db_grp_nm or '',
        'method': row.crt_mth_nm or '',
        'source': row.sub_ref_name or '',
        'year': (row.research_ymd or '')[:4],
        'basis': basis_text(row),
        'verify': row.verify_status,
        'verify_note': row.verify_note or '',
        'imported': (row.imp_yn or '').strip() in ('Y', '수입'),
        'nation': row.nation_nm or '',
    }


def source_note(row):
    """
    `MyLabel.nutrition_source_note` 에 남길 한 줄.

    성적서 판독이 남기는 것('영양성분 성적서 판독 - 파일명')과 같은 자리다.
    나중에 이 값을 누가 보더라도 **어느 행을 보고 정했는지** 되짚을 수 있어야
    한다 — 식품코드까지 적는 까닭이다.
    """
    if row is None:
        return ''
    bits = ['식약처 식품영양성분DB', '품목보고번호 일치']
    if row.food_cd:
        bits.append('식품코드 %s' % row.food_cd)
    if row.crt_mth_nm:
        bits.append(row.crt_mth_nm)
    year = (row.research_ymd or '')[:4]
    if year:
        bits.append('%s 조사' % year)
    basis = basis_text(row)
    if basis:
        bits.append(basis)
    return ' · '.join(bits)


def _as_field_text(value):
    """MyLabel 의 성분 칸은 CharField(10) 이다. 숫자를 짧게 담는다."""
    number = _number(value)
    if number is None:
        return None
    if float(number).is_integer():
        return str(int(number))
    return ('%.2f' % number).rstrip('0').rstrip('.')


def label_values(row):
    """
    내 표시사항에 그대로 넣을 값. {필드: 문자열}.

    **값이 없는 칸은 담지 않는다.** None 을 넣어 지우면 사람이 넣어 둔 값이
    조용히 사라진다 — 성적서 판독 저장이 같은 규칙을 쓴다.

    기준은 100 g(mL) 당이다. 적재본의 기준량이 그렇고, 라벨 쪽 계산기도
    100 g(mL) 당을 기본으로 받는다(nutrition_input_basis='per_100').
    """
    if row is None:
        return {}
    out = {}
    for field in COPY_FIELDS:
        text = _as_field_text(getattr(row, field, None))
        if text is not None:
            out[field] = text
    return out
