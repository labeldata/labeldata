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


def apply_nutrition(label, rows):
    """
    고른 영양성분만 라벨에 쓴다. 안 고른 것은 건드리지 않는다.

    각 행은 {'field': …, 'raw': '630 mg'} 또는 {'field': …, 'value': …, 'unit': …}.
    숫자와 단위를 가르는 일은 서버가 한다 - 규정 단위 표를 서버가 갖고 있다.

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

    # 마크 자체의 재질은 앞부분에 적힌다. 뒤에 오는 "띠지:PP, 리드지:PET" 는
    # 다른 부속의 재질이라, 문자열 전체에서 찾으면 그쪽을 집는다.
    # 실제로 "비닐류 PP / 띠지:PP, 리드지:PET" 가 비닐(PET) 로 잡혔다.
    head = re.split(r'[/|]', raw)[0]

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


def apply_recycling_mark(label, mark_type, text):
    """
    분리배출 표시를 라벨에 쓴다.

    종류를 못 정했으면 켜지 않는다. 미리보기에 마크를 그리는 설정이라, 종류
    없이 켜면 무엇을 그릴지 모른다.
    """
    changed = []
    text = (text or '').strip()
    if text:
        label.prv_recycling_mark_text = text[:200]
        changed.append('prv_recycling_mark_text')
    if mark_type:
        label.prv_recycling_mark_type = mark_type
        label.prv_recycling_mark_enabled = 'Y'
        changed += ['prv_recycling_mark_type', 'prv_recycling_mark_enabled']
    if changed:
        label.save(update_fields=sorted(set(changed)))
    return changed
