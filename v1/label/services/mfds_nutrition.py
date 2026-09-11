"""
식약처 식품영양성분DB 를 우리 성분 이름으로 옮긴다.

    data.go.kr / 1471000 / FoodNtrCpntDbInfo02 / getFoodNtrCpntDbInq02

이 API 는 성분 이름을 주지 않는다. **AMT_NUM1 ~ AMT_NUM157 번호만 온다.**
어느 번호가 무엇인지는 명세 문서에만 있고, 번호를 하나 밀려 읽으면 표에
엉뚱한 값이 조용히 들어간다 — 터지지 않으므로 아무도 모른다.

그래서 명세를 옮겨 적는 것으로 끝내지 않고 **데이터로 검산한다**(verify_row).
100 g 기준 행이라면 두 가지가 동시에 맞아야 한다.

    수분 + 단백질 + 지방 + 회분 + 탄수화물  ≈ 100 g
    탄수화물×4 + 단백질×4 + 지방×9         ≈ 에너지

'국밥_돼지머리' 한 건으로 재 보면 100.03 g / 137.0 kcal 로 둘 다 맞는다.
번호가 밀리면 둘 다 어긋나므로, 이 검산은 매핑이 맞다는 증거가 된다.

기준량이 100 g 만 있는 것이 아니다
────────────────────────────────
표본 1,500 건에서 100g 1,210 · **100mL 289** · 오염값('4㎍ RAE') 1 이었다.
100 mL 는 부피 기준이라 **중량 배합에 그대로 쓸 수 없다.** 물은 1.0 이라 넘어
가지만 식용유(0.92)·시럽(1.3)은 10~30 % 어긋난다. 비중을 모르는 채 1.0 으로
가정하면 조용히 틀리므로, 적재는 하되 자동 채움에서는 빼고 이유를 남긴다
(basis_unit). 모르는 것과 아닌 것은 다르다.
"""
import logging

from v1.label.services.nutrition_calc import _number

logger = logging.getLogger(__name__)

API_URL = ('https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02'
           '/getFoodNtrCpntDbInq02')

# 한 번에 받을 수 있는 최대 — 500 을 넘기면 numOfRows maximum is =[500] 로 거절된다
MAX_ROWS = 500


# ─────────────────────────────────────────────────────────────────────────────
# AMT_NUM → 우리 성분 이름
#
# 왼쪽이 우리 이름(nutrition_calc·constants 가 쓰는 것)이고 오른쪽이 번호다.
# 157 개를 다 옮기지 않는다 — 표시에 쓰는 것과 계산에 필요한 것만 든다.
# 나머지(아미노산·지방산 90여 종)는 원문 JSON 에 그대로 남겨 두었다가
# 필요해지면 그때 꺼낸다.
# ─────────────────────────────────────────────────────────────────────────────
NUTRIENT_MAP = {
    # 표시 필수 — display_value() 가 다루는 것
    'calories':        1,    # 에너지(kcal)
    'proteins':        3,    # 단백질(g)
    'fats':            4,    # 지방(g)
    'carbohydrates':   6,    # 탄수화물(g)
    'sugars':          7,    # 당류(g)
    'natriums':        13,   # 나트륨(mg)
    'cholesterols':    23,   # 콜레스테롤(mg)
    'saturated_fats':  24,   # 포화지방산(g)
    'trans_fats':      25,   # 트랜스지방산(g)

    # 열량 재계산에 필요 — CALORIE_FACTORS 가 탄수화물에서 빼고 따로 센다.
    # 이 둘이 없으면 식이섬유가 많은 제품에서 열량이 실제보다 높게 나온다.
    'dietary_fiber':   8,    # 식이섬유(g)
    'sugar_alcohols':  53,   # 당알콜(g)

    # 무기질 — display_value 의 _ROUND_WHOLE 무리
    'calcium':         9,
    'iron':            10,
    'phosphorus':      11,
    'potassium':       12,
    'magnesium':       111,
    'selenium':        115,
    'zinc':            116,

    # 표시 성분은 아니지만 계산에 쓴다
    'moisture':        2,    # 수분(g) — 수율 검산의 근거
    'ash':             5,    # 회분(g) — 질량 검산에 필요
    'refuse_rate':     157,  # 폐기율(%) — 원재료 실투입량 보정
}

# CALORIE_FACTORS 에는 있는데 이 DB 에는 컬럼 자체가 없는 것.
# 주류·발효식품에서만 문제가 되고, 그건 성적서 영역이다.
NOT_IN_SOURCE = ('organic_acids', 'alcohol')

# 질량 검산에 쓰는 다섯 — 이 합이 기준량이어야 한다
_MASS_FIELDS = ('moisture', 'proteins', 'fats', 'ash', 'carbohydrates')


def parse_basis(serving_size):
    """
    SERVING_SIZE('100g' / '100mL' / 드물게 오염값)를 (수량, 단위)로 가른다.

    단위를 못 읽으면 (None, '') 을 돌려준다 — 0 이나 100 으로 메우지 않는다.
    기준량을 모르는 채 값을 쓰면 100 배 틀린 표가 나온다.
    """
    text = (serving_size or '').strip()
    if not text:
        return None, ''

    for unit, key in (('mL', 'mL'), ('ml', 'mL'), ('g', 'g')):
        if text.endswith(unit):
            amount = _number(text[: -len(unit)])
            if amount:
                return amount, key
            return None, ''
    return None, ''


def extract_nutrients(item):
    """
    한 행에서 우리 이름의 성분 값을 뽑는다.

    숫자는 '1,670.000' 처럼 쉼표가 섞여 온다(표본 1,500 건에 1,665 개).
    float() 이 그대로 터지므로 _number() 를 쓴다 — 계산 쪽과 같은 함수라
    읽는 규칙이 두 벌이 되지 않는다.
    """
    out = {}
    for field, num in NUTRIENT_MAP.items():
        out[field] = _number(item.get('AMT_NUM%d' % num))
    return out



def _plain_energy(values):
    """단순 4·4·9. 원본의 절반쯤은 이 계산으로 만들어져 있다."""
    carb = values.get('carbohydrates')
    protein = values.get('proteins')
    fat = values.get('fats')
    if None in (carb, protein, fat):
        return None
    return float(carb) * 4 + float(protein) * 4 + float(fat) * 9


def verify_row(values, basis_amount, basis_unit, mass_tol=10.0, energy_tol=0.15):
    """
    이 행이 매핑대로 읽혔는가를 데이터 자신에게 물어본다.

    돌려주는 것: (판정, 사유)
        True,  ''            두 검산 모두 통과
        False, '...'         어긋남 — 번호가 밀렸거나 원본이 부실한 행
        None,  '...'         잴 수 없음 (값이 비어 있거나 기준량이 g 이 아님)

    **경고이지 배제가 아니다.** 원본에 빈 칸이 많아 못 재는 행이 흔하고,
    그것과 "재 봤더니 틀렸다" 는 전혀 다르다. 부르는 쪽이 셋을 갈라 센다.

    폭을 좁게 잡으면 안 된다
    ────────────────────────
    이 검산이 잡으려는 것은 **자릿수가 밀렸는가** 이지 측정 오차가 아니다.
    처음에 질량 3 g · 열량 5 % 로 잡았더니 멀쩡한 행이 무더기로 걸렸다.

        크림땅콩버터   표기 598 kcal · 규정 계수로 재계산하면 630 (5.4 % 차)
        골뱅이통조림   질량 합 92.86 g
        고등어구이     질량 합 103.40 g

    실제 식품 데이터는 이만큼 흔들린다. 반면 번호가 밀리면 두 배씩 어긋난다
    ('미역 튀각' 283 → 566). 그래서 폭을 넓히고 큰 어긋남만 잡는다. 좁게
    잡으면 쓸 수 있는 행을 못 쓰게 막는다(usable_for_recipe 가 fail 을 뺀다).

    열량은 **두 계산 중 하나라도 맞으면** 통과로 본다. 원본이 규정 계수
    (식이섬유 2.0 · 당알콜 2.4)와 단순 4·4·9 를 섞어 쓰기 때문이다 — 아래
    주석에 6 만 행으로 잰 수가 있다.
    """
    from v1.label.services.nutrition_calc import calories_from_macros

    if basis_unit != 'g' or not basis_amount:
        return None, '기준량이 g 이 아니다'

    mass = [values.get(f) for f in _MASS_FIELDS]
    if any(v is None for v in mass):
        return None, '질량 성분에 빈 칸이 있다'

    total = sum(mass)
    if abs(total - basis_amount) > mass_tol:
        return False, '질량 합 %.2f g (기준 %.0f g)' % (total, basis_amount)

    energy = values.get('calories')
    if energy is None or energy <= 0:
        return None, '에너지가 비어 있다'

    calc = calories_from_macros(values)
    if calc is None:
        return None, '열량을 재계산할 값이 없다'

    # 5 kcal 아래에서는 비율로 재면 작은 차이도 크게 보인다
    allowed = max(energy * energy_tol, 5.0)

    # **원본이 두 규칙을 섞어 쓴다.** 6 만 행을 재 보고 알았다.
    #
    #     표기 51.0  ->  규정 43.03 / 단순 51.23   이 행은 단순 4·4·9 다
    #     표기 37.0  ->  규정 38.92 / 단순 44.92   이 행은 규정 계수다
    #
    # 어느 쪽으로 만든 행인지는 우리가 알 수 없다. 한 규칙으로만 재면 다른
    # 규칙으로 만든 행이 억울하게 걸린다. 그래서 **둘 중 하나라도 맞으면
    # 통과**로 본다 — 이 검산이 잡으려는 것은 계수 다툼이 아니라 자릿수가
    # 밀린 행이고, 그런 행은 두 규칙 모두에서 어긋난다.
    #
    #     규정만      어긋남 894 (1.49 %)
    #     단순만      어긋남 1110 (1.85 %)
    #     둘 중 하나  어긋남 848 (1.41 %)   ← 46 행이 돌아온다
    #
    # 크게 줄지는 않는다. 남은 848 행은 15~25 % 어긋난 **진짜 이상한 행**이다.
    plain = _plain_energy(values)
    fits = abs(calc - energy) <= allowed or (
        plain is not None and abs(plain - energy) <= allowed)
    if not fits:
        return False, '열량 재계산 %.1f kcal (표기 %.1f)' % (calc, energy)

    return True, ''


def normalize_report_no(value):
    """
    품목제조보고번호를 조인할 수 있는 모양으로 다듬는다.

    '202509629419' 옆에 '2020_DNSP_04044' 같은 값이 섞여 온다. 우리
    MyIngredient.prdlst_report_no 는 숫자만 들고 있으므로, 숫자가 아닌 것이
    섞인 값은 조인 키로 쓰지 않는다 — 억지로 맞추면 엉뚱한 원료에 붙는다.
    """
    text = (value or '').strip()
    if not text:
        return ''
    return text if text.isdigit() else ''


def build_params(service_key, page_no, num_of_rows=MAX_ROWS):
    """API 질의 파라미터. serviceKey 는 인코딩된 채로 쓴다."""
    return {
        'serviceKey': service_key,
        'pageNo': page_no,
        'numOfRows': min(num_of_rows, MAX_ROWS),
        'type': 'json',
    }
