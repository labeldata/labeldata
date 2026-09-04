"""
같은 값이 도안 안에서 두 번 적히는 자리를 대조한다.

디자인 시안은 표시사항 표 하나로 끝나지 않는다. 내용량과 열량은 보통 세 곳에
따로 적힌다.

    표시사항 표      내용량   65 g
    영양정보 머리    총 내용량 65 g / 309 kcal
    앞면·측면 박스   -18℃ 이하 냉동보관  65 g (309 kcal)

표를 고치면서 박스를 안 고치는 일이 잦고, 인쇄 뒤에야 사람 눈에 걸린다.
판독은 표 쪽 값만 뽑아 오므로 그 어긋남을 알 방법이 없었다 — 사진 원문에는
셋 다 들어 있는데도.

그래서 **원문에 남은 다른 숫자**를 찾아 알린다. 고치지는 않는다. 어느 쪽이
맞는지는 사람이 봐야 아는 일이고, 우리가 고르면 틀린 쪽을 고를 수도 있다.
"""
import re

# 무게·부피. 단위를 붙여 세는 이유는 "65 g" 과 "65 mL" 가 다른 값이기 때문이다.
_AMOUNT_RE = re.compile(
    r'(\d[\d,]*(?:\.\d+)?)\s*(mg|kg|ml|mL|g|L|l)(?![a-zA-Z가-힣])')

# 열량. 인쇄물에는 조판용 조합 문자 ㎉ 도 흔하다.
_KCAL_RE = re.compile(
    r'(\d[\d,]*(?:\.\d+)?)\s*(?:k\s*cal|㎉|㎈|킬로\s*칼로리)', re.IGNORECASE)

# 이 단위들은 같은 것을 말한다. "65 g" 과 "65 G" 를 다른 값으로 세지 않는다.
_UNIT_CANON = {'mg': 'mg', 'kg': 'kg', 'ml': 'mL', 'g': 'g', 'l': 'L'}

# 내용량으로 볼 수 있는 단위. 나트륨 30 mg 이나 지방 4.5 g 까지 세면
# 영양성분 표의 모든 줄이 "다른 내용량" 이 된다.
_AMOUNT_UNITS = ('g', 'kg', 'mL', 'L')

# 영양성분 표의 줄. 이 말 뒤에 붙는 숫자는 내용량이 아니다.
_NUTRIENT_WORDS = (
    '나트륨', '탄수화물', '당류', '지방', '트랜스지방', '포화지방',
    '콜레스테롤', '단백질', '식이섬유', '칼슘', '철', '비타민',
)


def _number(text):
    try:
        return float(str(text).replace(',', ''))
    except (TypeError, ValueError):
        return None


def _near_nutrient(text: str, at: int) -> bool:
    """그 숫자 바로 앞이 영양성분 이름인가. 표의 줄은 내용량이 아니다."""
    head = text[max(0, at - 12):at]
    return any(word in head for word in _NUTRIENT_WORDS)


def amounts_in(text: str) -> set:
    """원문에 적힌 내용량 후보. {(값, 단위)}"""
    found = set()
    for match in _AMOUNT_RE.finditer(text or ''):
        unit = _UNIT_CANON.get(match.group(2).lower())
        if unit not in _AMOUNT_UNITS:
            continue
        if _near_nutrient(text, match.start()):
            continue
        value = _number(match.group(1))
        if value is None or value <= 0:
            continue
        found.add((value, unit))
    return found


# 영양정보 표에 늘 붙는 문구의 숫자. 이 제품의 값이 아니다.
#
#   "1일 영양성분 기준치에 대한 비율(%)은 2000 kcal 기준이므로 …"
#
# 이걸 세면 모든 라벨이 "앞면 박스와 열량이 다릅니다" 로 지적된다. 실제로
# 그랬다 — 대조 결과 여덟 줄 중 하나가 이 문구였다.
_BOILERPLATE_KCAL = frozenset({2000.0, 2500.0})


def calories_in(text: str) -> set:
    """원문에 적힌 열량 후보. 상용 문구의 숫자는 세지 않는다."""
    found = set()
    for match in _KCAL_RE.finditer(text or ''):
        value = _number(match.group(1))
        if value is None or value <= 0:
            continue
        if value in _BOILERPLATE_KCAL and _near_daily_value(text, match.start()):
            continue
        found.add(value)
    return found


def _near_daily_value(text: str, at: int) -> bool:
    """그 숫자 둘레가 1일 기준치 안내인가."""
    around = text[max(0, at - 40):at + 20]
    return ('기준치' in around) or ('기준이' in around) or ('1일' in around)


def _fmt_amount(pair) -> str:
    value, unit = pair
    return f'{value:g} {unit}'


def repeated_conflicts(data: dict, text: str) -> dict:
    """
    판독한 값과 **원문에 남은 다른 값**을 견준다.

    Returns: {필드: [사람이 읽을 문장 …]}  어긋난 것이 없으면 빈 사전.
    """
    if not text:
        return {}

    notes = {}

    # ── 내용량 ────────────────────────────────────────────────────────────
    printed = ' '.join(str((data.get(f) or {}).get('value') or '')
                       for f in ('content_weight', 'weight_calorie', 'nutrition_basis'))
    read_amounts = amounts_in(printed)
    others = {a for a in amounts_in(text) if a not in read_amounts}
    # 단위가 같은 것만 견준다 — 65 g 과 1 L 는 서로 다른 것을 말할 수 있다
    if read_amounts:
        units = {unit for _, unit in read_amounts}
        others = {a for a in others if a[1] in units}
        if others:
            listed = ', '.join(sorted(_fmt_amount(a) for a in others))
            mine = ', '.join(sorted(_fmt_amount(a) for a in read_amounts))
            notes.setdefault('content_weight', []).append(
                f'사진의 다른 자리에 {listed} 이(가) 적혀 있습니다 — 여기서 읽은 것은 {mine} 입니다. '
                f'앞면 박스나 영양정보 머리의 내용량이 표와 다른지 확인하세요.')

    # ── 열량 ──────────────────────────────────────────────────────────────
    read_kcal = calories_in(printed)
    other_kcal = {k for k in calories_in(text) if k not in read_kcal}
    if read_kcal and other_kcal:
        listed = ', '.join(f'{k:g} kcal' for k in sorted(other_kcal))
        mine = ', '.join(f'{k:g} kcal' for k in sorted(read_kcal))
        notes.setdefault('content_weight', []).append(
            f'사진의 다른 자리에 {listed} 이(가) 적혀 있습니다 — 여기서 읽은 것은 {mine} 입니다. '
            f'표와 앞면 박스의 열량이 서로 다른지 확인하세요.')

    return notes


def attach(data: dict, text: str) -> dict:
    """
    어긋난 것을 그 항목의 warnings 에 붙인다. **값은 고치지 않는다.**

    어느 쪽이 맞는지는 사진을 봐야 아는 일이다. 우리가 고르면 틀린 쪽을 고를
    수도 있고, 그러면 사용자는 자기가 넣지 않은 값을 확인 없이 저장하게 된다.
    """
    if not isinstance(data, dict):
        return data
    for field, messages in repeated_conflicts(data, text).items():
        item = data.get(field)
        if not isinstance(item, dict):
            item = {'value': None, 'confidence': 'none'}
            data[field] = item
        item['warnings'] = list(item.get('warnings') or []) + messages
    return data
