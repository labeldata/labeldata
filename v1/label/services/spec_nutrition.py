"""
**영양성분 성적서** 사진에서 값을 읽는다.

왜 VLM 이 아니라 OCR 인가
─────────────────────────
성적서는 **인쇄된 표**다. 항목 | 결과 | 단위 | 시험방법 이 줄지어 선 정형이고,
손글씨도 곡면도 없다. 그러면 전통 OCR 이 더 낫다 — 측정이 이미 그렇게 말했다
(ocr_text 주석).

    VLM      레이아웃 이해는 탁월하고 **긴 문자열 축자 전사를 못 한다.**
             다음 토큰을 확률로 뽑으니 그럴듯한 쪽으로 흐른다.
    OCR      글자를 보고 글자를 내므로 **지어낼 수가 없다.** 대신 어느 칸인지
             모른다.

성적서에서 우리가 원하는 것은 **숫자를 정확히 옮기는 것**이다. 어느 칸인지는
항목 이름이 바로 옆에 적혀 있어 규칙으로 가를 수 있다. VLM 이 잘하는 쪽은
필요 없고, 못하는 쪽이 정확히 우리가 필요한 것이다.

값이 싸고 빠른 것은 덤이다 — 호출 하나가 줄고, 판독 한도(quota)도 덜 먹는다.

기준량을 반드시 읽는다
──────────────────────
성적서는 100 g 당으로만 오지 않는다. 1 회 제공량당·1 kg 당·제품 전체당이
섞여 있다. **기준량을 모르면 그 값은 쓸 수 없다** — 100 g 당으로 바꿔야
배합 계산에 들어간다. 못 읽으면 비워 두고 사람에게 묻는다. 100 으로
가정하면 조용히 몇 배씩 틀린다.

왜 이것이 값진가
────────────────
원료 영양성분의 출처에는 등급이 있고 **공공 DB 로 채운 값은 영원히 C** 다.
식약처 DB 의 밀가루는 "일반적인 밀가루" 이지 "우리가 쓰는 그 밀가루" 가
아니기 때문이다. A 를 만들 수 있는 경로는 성적서뿐이고, 그 종이는 이미 우리
문서함에 쌓이고 있다.
"""
import base64
import io as _io
import json
import logging
import re

logger = logging.getLogger(__name__)

# 읽어 올 성분. MyIngredientNutrition.VALUE_FIELDS 와 같아야 한다 — 여기서
# 늘리면 저장이 못 받고, 저기서 늘리면 여기가 못 읽는다.
FIELDS = (
    ('calories', '열량', 'kcal'),
    ('carbohydrates', '탄수화물', 'g'),
    ('sugars', '당류', 'g'),
    ('proteins', '단백질', 'g'),
    ('fats', '지방', 'g'),
    ('saturated_fats', '포화지방', 'g'),
    ('trans_fats', '트랜스지방', 'g'),
    ('cholesterols', '콜레스테롤', 'mg'),
    ('natriums', '나트륨', 'mg'),
    ('dietary_fiber', '식이섬유', 'g'),
    ('sugar_alcohols', '당알콜', 'g'),
)

# 항목을 알아보는 말. 성적서마다 이름이 조금씩 다르다.
ALIASES = {
    'calories':      ('열량', '에너지', 'energy', 'calorie'),
    'carbohydrates': ('탄수화물', 'carbohydrate'),
    'sugars':        ('당류', 'sugar'),
    'proteins':      ('단백질', 'protein'),
    'fats':          ('지방', '조지방', 'fat'),
    'saturated_fats': ('포화지방', '포화 지방', 'saturated'),
    'trans_fats':    ('트랜스지방', '트랜스 지방', 'trans'),
    'cholesterols':  ('콜레스테롤', 'cholesterol'),
    'natriums':      ('나트륨', 'sodium'),
    'dietary_fiber': ('식이섬유', 'fiber', 'fibre'),
    'sugar_alcohols': ('당알콜', '당알코올'),
}

# 긴 이름을 먼저 본다. '지방' 이 '포화지방' 줄을 채 가면 안 된다.
_ORDER = sorted(ALIASES, key=lambda k: -max(len(a) for a in ALIASES[k]))

# 값이 없다는 말들. **0 으로 적으면 거짓말이 된다.**
_ABSENT = ('불검출', 'nd', 'n.d', 'n/d', '-', '--', '해당없음', 'tr')

# 기준량. "100g당", "100 g 당", "1회 제공량(30g)당", "per 100g"
#
# **당·기준 을 단위 뒤에 반드시 요구한다.** 없으면 "당류 12.5 g" 줄이
# 기준량으로 잡힌다 — 실제로 그랬다. 성분 이름에도 '당' 이 들어간다.
_BASIS = re.compile(
    r'(\d+(?:\.\d+)?)\s*(g|kg|mg|mL|ml|밀리리터|그램)\s*\)?\s*(?:당|기준|Per|per)\b',
    re.IGNORECASE)

# 한 줄에서 숫자를 찾는다. 단위가 붙어 있으면 함께 본다.
_VALUE = re.compile(r'(-?\d+(?:[,.]\d+)?)\s*(kcal|mg|g|%)?', re.IGNORECASE)

# 단위를 우리 기준으로 맞춘다 (열량 kcal · 나트륨/콜레스테롤 mg · 나머지 g)
_TO_UNIT = {'natriums': 'mg', 'cholesterols': 'mg', 'calories': 'kcal'}


def _num(v):
    """숫자만 꺼낸다. 못 꺼내면 None — 0 으로 적으면 거짓말이 된다."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    text = str(v).strip()
    if not text or _absent_in(text):
        return None
    m = _VALUE.search(text.replace(",", ""))
    return float(m.group(1)) if m else None


def _absent_in(text):
    """이 조각이 '값이 없다' 고 말하는가."""
    low = str(text or '').strip().lower()
    if not low:
        return False
    if low.startswith('<'):
        return True
    for mark in _ABSENT:
        if low.startswith(mark) or (' ' + mark) in (' ' + low):
            return True
    return False


def parse_basis(text):
    """원문에서 기준량을 찾는다. (숫자, 단위) — 못 찾으면 (None, '')."""
    for line in str(text or '').splitlines():
        m = _BASIS.search(line)
        if not m:
            continue
        amount = float(m.group(1))
        unit = m.group(2).lower()
        if unit == 'kg':
            amount, unit = amount * 1000, 'g'
        elif unit == 'mg':
            amount, unit = amount / 1000.0, 'g'
        elif unit == '밀리리터':
            unit = 'ml'
        elif unit == '그램':
            unit = 'g'
        if amount > 0:
            return amount, unit
    return None, ''


def _name_at(line):
    """이 줄이 말하는 성분과 이름이 끝나는 자리. 없으면 (None, 0)."""
    low = line.lower()
    for key in _ORDER:
        for alias in ALIASES[key]:
            at = low.find(alias.lower())
            if at >= 0:
                return key, at + len(alias)
    return None, 0


def parse_values(text):
    """
    원문에서 성분별 값을 뽑는다. 단위는 우리 기준으로 맞춘다.

    **없다고 적힌 줄에서 다음 줄 값을 빌려 오지 않는다.** 처음에 그렇게
    했더니 '콜레스테롤 ND' 가 바로 아래 '나트륨 420' 을 가져갔다 —
    없는 값이 남의 값으로 채워지는 것이 이 파서가 낼 수 있는 가장 나쁜
    실수다. 없다고 적혀 있으면 **거기서 끝낸다.**
    """
    lines = [ln.strip() for ln in str(text or '').splitlines() if ln.strip()]
    out = {}
    for i, line in enumerate(lines):
        key, after = _name_at(line)
        if key is None or key in out:
            continue

        tail = line[after:]
        if _absent_in(tail):
            out[key] = None          # 읽었고, 없다고 적혀 있었다
            continue

        m = _VALUE.search(tail)
        if m is None:
            # 이름만 있는 줄. 다음 줄에 값이 있을 수 있다 — 다만 그 줄이
            # 다른 성분 이름을 달고 있으면 남의 값이므로 건드리지 않는다.
            if i + 1 < len(lines) and _name_at(lines[i + 1])[0] is None:
                nxt = lines[i + 1]
                if _absent_in(nxt):
                    out[key] = None
                    continue
                m = _VALUE.search(nxt)
            if m is None:
                continue

        value = float(m.group(1).replace(',', ''))
        unit = (m.group(2) or '').lower()
        want = _TO_UNIT.get(key, 'g')
        if want == 'mg' and unit == 'g':
            value *= 1000
        elif want == 'g' and unit == 'mg':
            value /= 1000.0
        out[key] = value
    return out


def to_per_100(values, basis_amount, basis_unit):
    """
    기준량을 100 으로 맞춘다. 맞출 수 없으면 (None, 까닭).

    **기준량을 모르면 손대지 않는다.** 100 으로 가정하면 1 회 제공량 30 g
    성적서가 그대로 들어와 값이 3.3 배 낮아지는데, 터지지 않으니 아무도 모른다.
    """
    if basis_amount is None or not basis_unit:
        return None, '성적서의 기준량(100g당 등)을 읽지 못했습니다.'
    try:
        amount = float(basis_amount)
    except (TypeError, ValueError):
        return None, '기준량을 숫자로 읽지 못했습니다.'
    if amount <= 0:
        return None, '기준량이 0 이하입니다.'
    if str(basis_unit).strip().lower() not in ('g', 'ml', 'mL'.lower()):
        return None, '기준 단위가 g·mL 이 아닙니다 (%s).' % basis_unit

    factor = 100.0 / amount
    out = {}
    for key, _ko, _unit in FIELDS:
        v = _num(values.get(key))
        out[key] = None if v is None else round(v * factor, 3)
    return out, ''


def read(image_fh, tag='spec_nutrition'):
    """
    성적서 사진 하나를 읽어 {values, basis_amount, basis_unit, error, text} 를 낸다.

    값은 **100 g(mL) 당으로 환산해서** 낸다. 환산할 수 없으면 values 는 비고
    error 에 까닭이 담긴다 — 사람이 기준량을 알려 주면 다시 부르면 된다.
    """
    from v1.label.services.ocr_text import extract_text

    empty = {'values': {}, 'basis_amount': None, 'basis_unit': '', 'text': ''}
    try:
        raw = image_fh.read()
    except Exception as exc:
        return dict(empty, error='파일을 읽지 못했습니다: %s' % exc)
    if not raw:
        return dict(empty, error='빈 파일입니다.')

    try:
        text = extract_text(raw)
    except Exception as exc:
        logger.exception('[%s] 원문 추출 실패', tag)
        return dict(empty, error='글자를 읽지 못했습니다: %s' % exc)
    if not (text or '').strip():
        return dict(empty, error='사진에서 글자를 찾지 못했습니다.')

    amount, unit = parse_basis(text)
    values, why = to_per_100(parse_values(text), amount, unit)
    return {
        'values': values or {},
        'basis_amount': amount,
        'basis_unit': unit,
        'text': text,
        'error': why,
    }
