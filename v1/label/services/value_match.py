"""
두 값이 **같은 말인가**. 항목마다 견주는 법이 다르다.

이 정책은 원래 `ocr_reconcile` 안에만 있었다 — 사진에서 읽은 값과 식약처
등록 정보를 대조할 때 쓰려고 만든 것이다. 그런데 "항목마다 비교 방식이
다르다" 는 판독만의 사정이 아니다. 검증도 값 둘을 견주는 자리가 있고, 거기서
완전일치를 요구하면 규정을 지킨 라벨을 탓하게 된다.

    빵류  ↔  빵류 [가열하여 섭취하는 냉동식품]     같은 말이다 (부기)
    빵류  ↔  과자                                   다른 말이다

그래서 견주는 법만 여기로 옮긴다. `ocr_reconcile` 은 그대로 이 모듈을 부른다 —
두 벌로 두면 어느 날 한쪽만 고쳐진다.

    exact     짧고 정형화된 값. 표기 흔들림만 감안해 곧이곧대로
    prefix    앞이 같고 뒤가 괄호 부기면 같은 말 (식품유형 · 유형명)
    contains  짧은 쪽이 긴 쪽에 담기면 같은 말 (제조원 = 회사명 + 주소)
    company   법인격 표기를 지우고 이름만 (ocr_company 가 본다)
    period    글자가 아니라 **기간**을 견준다 (소비기한)
    loose     길고 자유로운 값. 다르다고 곧장 단정하지 않는다
"""
import re
import unicodedata

# 두 값이 "같은 말" 이라고 볼 점수. 완전일치를 요구하면 띄어쓰기·괄호 차이로
# 전부 불일치가 되고, 너무 낮추면 다른 제품을 같다고 한다.
AGREE_SCORE = 88
# 이보다 낮으면 "다르다" 고 짚는다. 사이 구간은 판단을 보류한다(비슷하긴 하다).
CONFLICT_SCORE = 60

_WS = re.compile(r'\s+')

# 부기를 여는 괄호. "빵류 [가열하여…]" 의 대괄호가 그것이다.
_BRACKETS = '([{'


def squeeze(text):
    """
    비교할 때만 쓰는 형태. 공백과 흔한 구분기호를 지운다.

    NFKC 로 호환 문자를 펼친다 — ℃ 와 °C, ㎖ 와 ml 은 같은 값이다.
    """
    s = _WS.sub('', unicodedata.normalize('NFKC', str(text or '')))
    for a, b in (('（', '('), ('）', ')'), ('［', '['), ('］', ']'), ('，', ',')):
        s = s.replace(a, b)
    return s.lower()


# 소비기한은 표기가 자유롭지만 **뜻은 기간 하나**다. 라벨에 "제조일로부터
# 12개월", 등록 정보에 "제조일로부터 5일" 이면 글자는 비슷해도(66점) 완전히 다른
# 제품이다. 반대로 라벨의 "별도표기일까지" 와 등록 정보의 "제조일로부터 12개월" 은
# 어긋난 게 아니다 — 라벨은 날짜를 따로 찍는다고 말하고 있을 뿐이다.
# 글자만 견주면 앞은 놓치고 뒤는 잘못 짚는다. 기간을 읽어 견준다.
_PERIOD_RE = re.compile(r'(\d+)\s*(년|개월|달|주일|주|일)')
_PERIOD_DAYS = {'년': 365, '개월': 30, '달': 30, '주일': 7, '주': 7, '일': 1}


def parse_period_days(text):
    """소비기한 문구에서 기간을 일수로. 기간이 안 적혀 있으면 None."""
    m = _PERIOD_RE.search(str(text or ''))
    if not m:
        return None
    return int(m.group(1)) * _PERIOD_DAYS[m.group(2)]


def is_annotated(base, full):
    """
    `full` 이 `base` 로 시작하고 뒤가 괄호 부기인가.

        빵류  ↔  빵류 [가열하여 섭취하는 냉동식품 / 발효 제품]   -> True
        빵류  ↔  빵류과자                                        -> False
        빵류  ↔  과자                                            -> False

    **부기는 더 밝힌 것이지 다른 말이 아니다.** 표시기준이 유형명 뒤에 살균
    여부·섭취 방법을 괄호로 덧붙이라고 하는 자리가 여럿이라, 완전일치를
    요구하면 규정대로 적은 라벨이 어긋난 것으로 나온다.
    """
    a, b = squeeze(base), squeeze(full)
    if not a or not b or not b.startswith(a) or a == b:
        return False
    return b[len(a)] in _BRACKETS


def ratio(a, b, mode):
    """두 값의 닮은 정도(0~100). rapidfuzz 가 없으면 완전일치만 본다."""
    if mode == 'company':
        # 회사명은 법인격 표기가 저마다 다르다 — "(주)샤니", "샤니(주)",
        # "주식회사 샤니" 는 같은 회사다. 그 표기를 지우고 이름만 견준다.
        from v1.label.services.ocr_company import match_registered_name
        return match_registered_name(a, b)
    x, y = squeeze(a), squeeze(b)
    if not x or not y:
        return 0
    try:
        from rapidfuzz import fuzz
    except ImportError:      # 채점만 못 할 뿐, 대조 자체는 계속돼야 한다
        return 100 if x == y else 0
    if mode == 'contains':
        # 짧은 쪽이 긴 쪽 안에 있으면 같은 말이다 (제조원 = 회사명 + 주소)
        if x in y or y in x:
            return 100
        return int(fuzz.partial_ratio(x, y))
    return int(fuzz.ratio(x, y))


def compare(left, right, mode):
    """
    한 항목을 견줘 (점수, 판정) 을 낸다. 판정은 agree · conflict · unsure.

    'period' 는 글자가 아니라 뜻을 본다. 'prefix' 는 부기를 같은 말로 본다.
    나머지는 닮은 정도로 판정한다.
    """
    if mode == 'period':
        a, b = parse_period_days(left), parse_period_days(right)
        if a is not None and b is not None:
            if a == b:
                return 100, 'agree'
            # 개월/일 환산의 어림(30일) 때문에 하루 이틀은 어긋난다.
            near = abs(a - b) <= max(2, min(a, b) * 0.05)
            return (95, 'agree') if near else (0, 'conflict')
        # 한쪽이 "별도표기일까지" 처럼 기간을 안 적은 경우. 어긋난 게 아니다.
        return ratio(left, right, 'loose'), 'unsure'

    if mode == 'prefix':
        if squeeze(left) == squeeze(right):
            return 100, 'agree'
        if is_annotated(left, right) or is_annotated(right, left):
            return 100, 'agree'
        score = ratio(left, right, 'loose')
        return score, 'conflict' if score < CONFLICT_SCORE else 'unsure'

    score = ratio(left, right, mode)
    if score >= AGREE_SCORE:
        return score, 'agree'
    if score < CONFLICT_SCORE and mode != 'loose':
        # 길고 자유로운 값(원재료명·포장재질)은 표기 차이만으로도 크게 벌어진다.
        # 그걸 "틀렸다" 고 하면 매번 울리는 경고가 된다.
        return score, 'conflict'
    return score, 'unsure'


# ─────────────────────────────────────────────────────────────────────────────
# 수치 — 표기만 고르고, 값이 다르면 무조건 다르다
#
# 시안 대조에서 가장 자주 나오던 오탐이 이것이었다.
#
#     12.5g  ↔  12.50g       같은 값인데 "다름"
#     100 g  ↔  100그램       같은 값인데 "다름"
#     500mL  ↔  500㎖         같은 값인데 "다름"
#
# **느슨하게 만드는 것이 아니다.** 표기를 고르게 펼 뿐이고, 값이 다르면
# 12.5 와 12.6 처럼 한 끗이라도 "다르다" 로 간다. 인쇄물의 수치가 틀린 것이
# 이 기능이 막으려는 것 중 가장 나쁜 것이라, 여기만은 절대 눅이지 않는다.
# ─────────────────────────────────────────────────────────────────────────────

# 같은 단위의 다른 표기. NFKC 가 ㎖→ml 은 펴 주지만 한글 표기는 못 편다.
_UNIT_ALIAS = {
    '그램': 'g', 'g': 'g', '밀리그램': 'mg', 'mg': 'mg', '킬로그램': 'kg', 'kg': 'kg',
    '밀리리터': 'ml', 'ml': 'ml', '리터': 'l', 'l': 'l',
    '킬로칼로리': 'kcal', 'kcal': 'kcal', '칼로리': 'kcal',
    '개': '개', '개입': '개', '매': '매', '%': '%', '인분': '인분',
}
_NUM_UNIT = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(밀리그램|킬로그램|킬로칼로리|밀리리터|그램|칼로리|리터|개입|인분|kcal|mg|kg|ml|개|매|[gl%])',
    re.IGNORECASE)


def numbers_with_units(text):
    """
    글에서 (값, 단위) 를 순서대로 뽑는다. 단위 표기는 하나로 모은다.

    값은 float 이 아니라 **문자열을 정규화**해 견준다 — 12.50 과 12.5 는 같고,
    0.1+0.2 같은 부동소수점 문제를 아예 만들지 않는다.
    """
    out = []
    for raw, unit in _NUM_UNIT.findall(unicodedata.normalize('NFKC', str(text or ''))):
        u = _UNIT_ALIAS.get(unit.lower(), unit.lower())
        # 12.50 -> 12.5, 100.0 -> 100
        v = raw.rstrip('0').rstrip('.') if '.' in raw else raw
        out.append((v or '0', u))
    return out


def compare_numbers(left, right):
    """(점수, 판정). 수치가 하나라도 다르면 conflict."""
    a, b = numbers_with_units(left), numbers_with_units(right)
    if not a and not b:
        return ratio(left, right, 'loose'), 'unsure'   # 잴 수치가 없다
    if a == b:
        return 100, 'agree'
    return 0, 'conflict'


# ─────────────────────────────────────────────────────────────────────────────
# 문장 — 줄바꿈 자리가 다르다고 통째로 "다름" 이 되면 안 된다
#
# 주의사항은 여러 문장이고, 시안은 폭에 맞춰 줄을 접는다. 글자로 견주면
# 문구가 다 맞는데도 통째로 "다름" 이 된다. 문장으로 쪼개 집합으로 보면
# **어느 문장이 빠졌는지**까지 짚을 수 있다 — 오탐이 줄면서 지적이 정확해진다.
# ─────────────────────────────────────────────────────────────────────────────

_SENT_SPLIT = re.compile(r'[\n\r]+|(?<=[.。])\s+|(?<=니다)\s+|(?<=하세요)\s+')


def sentences(text):
    """문장 단위로 쪼개 비교용 형태로. 빈 조각과 중복은 버린다."""
    out, seen = [], set()
    for part in _SENT_SPLIT.split(str(text or '')):
        key = squeeze(part)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def compare_sentences(left, right):
    """
    (점수, 판정, 빠진 문장들). 한쪽이 다른 쪽에 통째로 들어 있으면 '덜 읽힌' 것이다.
    """
    a, b = set(sentences(left)), set(sentences(right))
    if not a and not b:
        return 100, 'agree', []
    if a == b:
        return 100, 'agree', []
    if a and b and (a <= b or b <= a):
        # 시안이 작게 들어가 절반만 읽히는 일이 잦다. 그건 시안이 틀린 것이
        # 아니라 우리가 덜 읽은 것이라, 같은 무게로 짚으면 안 된다.
        return 90, 'partial', sorted(a ^ b)
    common = len(a & b)
    total = len(a | b) or 1
    score = int(common * 100 / total)
    return score, ('conflict' if score < CONFLICT_SCORE else 'unsure'), sorted(a ^ b)
