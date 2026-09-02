"""
사진에서 읽은 값 중 **기본 정보 탭 밖으로 가는 것**을 라벨에 반영한다.

기본 정보 탭의 칸들은 화면이 직접 채우고 사용자가 저장 버튼을 누른다. 그런데
영양성분과 분리배출은 그 탭에 칸이 없다 - 영양성분은 별도 탭(iframe)이고,
분리배출은 미리보기 설정이다. 화면에서 채울 수가 없어 서버가 맡는다.

여기서도 **확인 없이 쓰지 않는다.** 화면이 읽은 값을 보여 주고, 사용자가 고른
것만 넘어온다.
"""
import re

# 표에 적힌 값을 숫자와 단위로 가른다. "630 mg" -> ("630", "mg")
_VALUE_UNIT = re.compile(r'^\s*([\d.,]+)\s*([a-zA-Z가-힣㎎㎍μµ]*)\s*$')

# 영양성분마다 규정이 정한 단위. 사진에서 단위를 못 읽었을 때 쓴다.
DEFAULT_UNITS = {
    'calories': 'kcal',
    'natriums': 'mg',
    'carbohydrates': 'g',
    'sugars': 'g',
    'fats': 'g',
    'trans_fats': 'g',
    'saturated_fats': 'g',
    'cholesterols': 'mg',
    'proteins': 'g',
}

NUTRITION_LABELS = {
    'calories': '열량',
    'natriums': '나트륨',
    'carbohydrates': '탄수화물',
    'sugars': '당류',
    'fats': '지방',
    'trans_fats': '트랜스지방',
    'saturated_fats': '포화지방',
    'cholesterols': '콜레스테롤',
    'proteins': '단백질',
}

# 분리배출 마크 표기 -> MyLabel.prv_recycling_mark_type 의 값.
#
# 라벨에는 "비닐류 / PP" 처럼 큰 구분과 재질 코드가 나뉘어 찍힌다. 저장은 그
# 조합 하나(비닐(PP))로 하므로 둘을 합쳐 고른다. 검증(check_recycling_mark)이
# 이 값을 포장재질과 대조하므로, 자유 문구로 두면 검증이 계속 눈을 감는다.
_MARK_GROUPS = [
    ('비닐', {'pet': '비닐(PET)', 'hdpe': '비닐(HDPE)', 'ldpe': '비닐(LDPE)',
              'pp': '비닐(PP)', 'ps': '비닐(PS)', 'other': '비닐(기타)'}),
    ('플라스틱', {'pet': '플라스틱(PET)', 'hdpe': '플라스틱(HDPE)',
                  'ldpe': '플라스틱(LDPE)', 'pp': '플라스틱(PP)',
                  'ps': '플라스틱(PS)', 'other': '기타플라스틱'}),
]
_SIMPLE_MARKS = {
    '유리': '유리', '알미늄': '캔류(알미늄)', '알루미늄': '캔류(알미늄)',
    '철': '캔류(철)', '복합재질': '복합재질',
}


def split_value_unit(text, field=''):
    """
    "630 mg" -> ("630", "mg"). 못 가르면 (원문, 기본 단위).

    숫자만 오면(단위를 못 읽었으면) 규정 단위를 붙인다. 단위가 틀리면 표시가
    통째로 틀리므로 비워 두는 것보다 규정값이 낫다.
    """
    raw = (text or '').strip()
    if not raw:
        return '', ''
    m = _VALUE_UNIT.match(raw)
    if not m:
        return raw, DEFAULT_UNITS.get(field, '')
    number = m.group(1).replace(',', '')
    unit = m.group(2) or DEFAULT_UNITS.get(field, '')
    # ㎎ 같은 조합 문자를 흔한 표기로 되돌린다
    unit = unit.replace('㎎', 'mg').replace('㎍', 'µg').replace('μ', 'µ')
    return number, unit


def parse_nutrition(data):
    """
    OCR 결과에서 영양성분만 골라 (필드, 값, 단위) 목록으로.

    data 는 {키: {'value':…, 'confidence':…}} 꼴이다.
    """
    rows = []
    for field, label in NUTRITION_LABELS.items():
        item = data.get(field)
        text = (item or {}).get('value') if isinstance(item, dict) else item
        value, unit = split_value_unit(text, field)
        if value == '':
            continue
        rows.append({'field': field, 'label': label, 'value': value, 'unit': unit})
    return rows


def _trim_number(value: float) -> str:
    """소수점 뒤 군더더기를 뗀 짧은 표기. 저장 칸이 10자다."""
    text = f'{value:.2f}'.rstrip('0').rstrip('.')
    return text or '0'


def to_per_100(rows, basis_amount):
    """
    사진에서 읽은 표의 값을 **100 g(mL) 당** 으로 환산한다.

    라벨의 영양성분표는 그 표가 밝힌 기준(총 내용량 / 1회 제공량 / 100 g)으로
    인쇄돼 있다. 그런데 MyLabel 의 영양성분 칸이 담는 값은 **언제나 100 g 당**
    이다 - 영양성분 계산기(nutrition_calculator_popup.js)가 그렇게 넣고, 표를
    그릴 때 generateBasicDisplayV3 이 `값 x 표시량/100` 으로 되돌린다.

    사진에서 읽은 값을 환산 없이 그대로 넣으면 그 약속이 깨진다. 실제로 이렇게
    났다 - "총 내용량 87 g / 318 kcal" 로 인쇄된 라벨을 판독해 넣었더니

        표시:   318 x 87/100 = 276.66 -> 5 kcal 단위 반올림 -> **275 kcal**
        검증:   318 x 87/100 = 277 != 318  -> "열량이 맞지 않습니다"

    사진에도 318, 내용량 칸에도 318 로 **맞게** 적혀 있는데 화면은 275 로 바꿔
    보여 주고 검증은 틀렸다고 했다. 기준을 읽어 serving_size 는 87 로 맞추면서
    **분자는 인쇄된 값 그대로 두어**, 분모만 바뀐 셈이었다.

    basis_amount 가 없거나(기준을 못 읽음) 100 이면 그대로 둔다. 기준을
    모르면서 환산하면 모든 수치의 뜻이 바뀐다 - 그건 더 나쁘다.
    """
    try:
        basis = float(basis_amount)
    except (TypeError, ValueError):
        return rows
    if basis <= 0 or basis == 100:
        return rows

    factor = 100.0 / basis
    converted = []
    for row in rows:
        value = row.get('value')
        try:
            number = float(str(value).replace(',', ''))
        except (TypeError, ValueError):
            converted.append(row)   # 숫자가 아니면 손대지 않는다
            continue
        converted.append(dict(row, value=_trim_number(number * factor)))
    return converted


def apply_nutrition(label, rows):
    """
    고른 영양성분만 라벨에 쓴다. 안 고른 것은 건드리지 않는다.

    각 행은 {'field': …, 'raw': '630 mg'} 또는 {'field': …, 'value': …, 'unit': …}.
    숫자와 단위를 가르는 일은 서버가 한다 - 규정 단위 표를 서버가 갖고 있다.

    **여기 오는 값은 이미 100 g 당이어야 한다.** 사진에서 읽은 값은 to_per_100
    으로 환산해서 넘긴다 - 그 이유는 to_per_100 주석에 있다.

    **nutrition_save_api 를 쓰지 않는 이유**: 그 API 는 넘어오지 않은 항목을 빈
    값으로 덮는다. 사진에 없던 성분(식이섬유·칼슘 등)이 지워진다.
    """
    changed = []
    for row in rows:
        field = row.get('field')
        if field not in NUTRITION_LABELS:
            continue
        if row.get('raw') is not None and not row.get('value'):
            value, unit = split_value_unit(row.get('raw'), field)
            row = dict(row, value=value, unit=unit)
        value = str(row.get('value') or '').strip()
        if not value:
            continue
        setattr(label, field, value)
        changed.append(field)
        unit_field = f'{field}_unit'
        if hasattr(label, unit_field):
            unit = str(row.get('unit') or '').strip() or DEFAULT_UNITS.get(field, '')
            if unit:
                setattr(label, unit_field, unit)
                changed.append(unit_field)
    if changed:
        # update_fields 를 준다 - 전체 save 는 수거검사 소급 매칭 시그널을 깨운다
        label.save(update_fields=sorted(set(changed)))
    return changed


def parse_nutrition_basis(text):
    """
    "총 내용량 139 g" -> ('139', 'g'). 표의 기준이 1회 제공량이면 그 값을 쓴다.

    못 읽으면 (None, None). 그때는 기존 값을 그대로 둔다 - 기준을 잘못 바꾸면
    모든 수치의 뜻이 달라진다.
    """
    raw = (text or '').strip()
    if not raw:
        return None, None
    # \b 를 쓰면 "100 g당" 이 안 잡힌다 - 한글은 단어 문자라 g 와 당 사이에
    # 경계가 없다. 뒤에 영문이 이어지지만 않으면 된다.
    # kg 를 g 보다, mL 를 L 보다 먼저 본다.
    m = re.search(r'([\d.,]+)\s*(kg|mL|ml|㎖|g|L)(?![a-zA-Z])', raw)
    if not m:
        return None, None
    unit = m.group(2)
    return m.group(1).replace(',', ''), 'mL' if unit.lower() in ('ml', '㎖') else unit


# ── 사진값에서 화면 버튼 상태를 유도한다 ────────────────────────────────────
#
# 기본정보 탭에는 글자 칸 말고도 **눌러서 고르는 것**이 셋 있다.
#
#   장기보존식품   냉동(가열)·냉동(비가열)·통병조림·레토르트   (배타 선택)
#   제조방법       살균·멸균·유탕유처리·비살균                 (배타 선택)
#   보관방법       냉동·냉장·실온·상온 배지                    (여러 개 가능)
#
# 사진에는 그 정보가 **글자로** 적혀 있다 - 식품유형에 "레토르트식품", 보관방법에
# "냉동(-18 ℃ 이하)", 주의사항에 "살균제품" 같은 식이다. 사람이 그걸 읽고 다시
# 버튼을 누르게 두면, 사진으로 불러오는 의미가 절반으로 준다.
#
# **판정은 서버가 한다.** 화면이 둘(표시사항 작성 / 제품 기본정보)이라 여기서
# 하지 않으면 같은 규칙을 두 벌로 만들게 되고, 어느 날 한쪽만 고쳐진다.

# 긴 말부터 본다. "비살균" 은 "살균" 을 품고 있어서 순서를 바꾸면 늘 살균으로
# 잡힌다. 같은 이유로 "멸균" 도 "살균" 보다 앞이다.
_PROCESSING_RULES = (
    ('unsanitized', ('비살균',)),
    ('aseptic',     ('멸균',)),
    ('yutang',      ('유탕', '유처리')),
    ('sanitized',   ('살균',)),
)

_PRESERVATION_RULES = (
    ('retort',           ('레토르트',)),
    ('canned',           ('통조림', '병조림', '통·병조림')),
    ('frozen_nonheated', ('비가열',)),
    ('frozen_heated',    ('가열하여 섭취', '가열하여섭취')),
)

# 보관방법 배지. 화면의 data-storage-value 와 같아야 한다.
_STORAGE_BADGES = ('냉동', '냉장', '실온', '상온')


def _haystack(data, *fields) -> str:
    """고른 항목들의 값을 한 덩어리로. 판정은 여러 칸에 흩어진 단서를 함께 본다."""
    parts = []
    for field in fields:
        item = (data or {}).get(field)
        value = item.get('value') if isinstance(item, dict) else item
        if value:
            parts.append(str(value))
    return ' '.join(parts)


def derive_basics(data) -> dict:
    """
    판독값에서 화면 버튼 상태를 유도한다.

    Returns: {'preservation_type': str, 'processing_method': str,
              'storage_badges': [str, ...]}
      값이 없으면 빈 문자열 / 빈 목록이다. **모르면 비운다** - 틀린 버튼을
      눌러 두면 사용자가 그걸 알아채고 되돌려야 하는데, 그건 안 누른 것보다
      나쁘다.

    냉동 판정만 두 갈래다. 라벨은 "가열하여 섭취하는 냉동식품" / "비가열"
    로 그 구분을 적어 두는데, 둘 다 없으면 냉동인 것만 알고 어느 쪽인지는
    모른다. 그때는 비운다.
    """
    text = _haystack(data, 'prdlst_dcnm', 'storage_method', 'cautions',
                     'additional_info', 'prdlst_nm')
    storage = _haystack(data, 'storage_method')

    processing = ''
    for value, needles in _PROCESSING_RULES:
        if any(n in text for n in needles):
            processing = value
            break

    preservation = ''
    for value, needles in _PRESERVATION_RULES:
        if any(n in text for n in needles):
            preservation = value
            break

    return {
        'preservation_type': preservation,
        'processing_method': processing,
        # 배지는 보관방법 칸의 글자만 본다. 주의사항에 "냉장 보관하십시오" 가
        # 있다고 보관방법 배지를 누르면, 정작 실온 제품에 냉장이 켜진다.
        'storage_badges': [b for b in _STORAGE_BADGES if b in storage],
    }


def _mark_segment(segments):
    """
    구분(비닐류·플라스틱 …)이 적힌 도막을 고른다. 없으면 None.

    부속 표기는 "띠지:PP" 처럼 부위 이름이 붙고 구분이 안 붙는다. 그래서
    구분이 있는 도막이 마크 자체다.
    """
    for segment in segments:
        for group, _table in _MARK_GROUPS:
            if group in segment:
                return segment
        for word in _SIMPLE_MARKS:
            if word in segment:
                return segment
    return None


def map_recycling_mark(text):
    """
    분리배출 표기를 저장용 종류로 바꾼다.

    Returns: (종류 또는 '', 보조 텍스트)

    종류를 못 정하면 빈 문자열을 돌려준다. 그때는 사용자가 고르게 두고 보조
    텍스트만 남긴다 - 틀린 종류를 넣으면 포장재질 대조 검증이 엉뚱하게 운다.
    """
    raw = (text or '').strip()
    if not raw:
        return '', ''

    # 마크 자체의 재질이 어느 도막에 있는지는 라벨마다 다르다.
    #
    #   "비닐류 PP / 띠지:PP, 리드지:PET"   앞이 마크, 뒤가 부속
    #   "OTHER / 비닐류 PP"                 뒤가 마크
    #
    # 앞을 무조건 마크로 보면 두 번째가 비닐(기타)로 잡히고, 진짜 마크인
    # "비닐류 PP" 가 마크 옆에 인쇄할 문구로 밀려난다.
    #
    # 그래서 **구분(비닐류/플라스틱 …)이 적힌 도막**을 마크로 본다. 그런 도막이
    # 없으면 예전처럼 앞을 쓴다 - 부속 표기("띠지:PP")에는 구분이 안 붙는다.
    segments = [seg.strip() for seg in re.split(r'[/|]', raw) if seg.strip()]
    head = _mark_segment(segments) or (segments[0] if segments else raw)

    def find_code(segment):
        lowered = segment.lower()
        # OTHER 를 먼저 본다 (다른 코드가 그 안에 없도록)
        for key in ('other', 'hdpe', 'ldpe', 'pet', 'pp', 'ps'):
            if re.search(r'(?<![a-z])' + key + r'(?![a-z])', lowered):
                return key
        return ''

    code = find_code(head) or find_code(raw)

    for group, table in _MARK_GROUPS:
        if group in raw and code:
            return table.get(code, ''), raw

    for word, mark in _SIMPLE_MARKS.items():
        if word in raw:
            return mark, raw

    if '종이' in raw:
        return '종이', raw
    if '멸균' in raw and '팩' in raw:
        return '멸균팩', raw
    if '팩' in raw:
        return '일반팩', raw
    # 구분 없이 재질만 찍힌 경우 (예: "OTHER")
    if code:
        return {'other': '기타플라스틱', 'pet': '플라스틱(PET)',
                'hdpe': '플라스틱(HDPE)', 'ldpe': '플라스틱(LDPE)',
                'pp': '플라스틱(PP)', 'ps': '플라스틱(PS)'}[code], raw
    return '', raw


def extra_mark_text(text, mark_type):
    """
    마크 **옆에 덧붙일 문구**만 골라낸다.

    `prv_recycling_mark_text` 는 미리보기에서 마크 옆에 그대로 인쇄되는 글자다.
    그런데 지금까지 읽은 문구를 통째로 여기에 넣었다. 그래서 "비닐류 PP" 를
    읽으면 비닐(PP) 마크를 그려 놓고 그 옆에 "비닐류 PP" 를 또 적었다 —
    마크가 이미 하는 말을 글자로 한 번 더 쓴 것이다.

    종류를 정했으면 마크가 재질을 말한다. 덧붙일 것은 **마크 하나로 표현할 수
    없는 나머지**뿐이다: "비닐류 PP / 띠지:PP, 리드지:PET" 에서 "/" 뒤쪽,
    즉 부속의 재질이다.

    종류를 못 정했으면 읽은 문구를 그대로 남긴다 — 마크를 못 그리므로 사람이
    무엇을 봤는지 알아야 직접 고를 수 있다.
    """
    raw = (text or '').strip()
    if not raw:
        return ''
    if not mark_type:
        return raw
    segments = [seg.strip() for seg in re.split(r'[/|]', raw) if seg.strip()]
    mark_segment = _mark_segment(segments)
    if mark_segment is None:
        # 구분이 없다("OTHER / 띠지:PP"). 앞이 마크였으므로 나머지가 부속이다.
        return ', '.join(segments[1:])
    return ', '.join(seg for seg in segments if seg is not mark_segment)


def apply_recycling_mark(label, mark_type, text):
    """
    분리배출 표시를 라벨에 쓴다.

    종류를 못 정했으면 켜지 않는다. 미리보기에 마크를 그리는 설정이라, 종류
    없이 켜면 무엇을 그릴지 모른다.

    덧붙일 문구가 없으면 **기존 문구를 건드리지 않는다.** 사람이 적어 둔
    문구를 빈 값으로 밀어 버리면, 사진 한 장 읽었다고 이미 맞춰 둔 표시가
    사라진다.
    """
    changed = []
    extra = extra_mark_text(text, mark_type)
    if extra and extra != (label.prv_recycling_mark_text or '').strip():
        label.prv_recycling_mark_text = extra[:200]
        changed.append('prv_recycling_mark_text')
    if mark_type:
        label.prv_recycling_mark_type = mark_type
        label.prv_recycling_mark_enabled = 'Y'
        changed += ['prv_recycling_mark_type', 'prv_recycling_mark_enabled']
    if changed:
        label.save(update_fields=sorted(set(changed)))
    return changed
