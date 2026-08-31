"""
사진에서 읽은 값을 식약처 품목보고 정보와 대조한다.

사진에서 품목보고번호가 읽히면 그 번호로 등록된 정보를 그대로 가져올 수 있다.
그쪽은 OCR 을 거치지 않으므로 **틀릴 이유가 없는 값**이다. 그런데 지금까지
두 입구(사진 판독 / 번호 조회)는 서로를 몰랐다 — 사진으로 들어오면 번호가
읽혔는데도 등록 정보를 한 번도 보지 않았다.

여기서 하는 일은 셋이다.

  1. 채운다   사진에서 못 읽은 항목을 등록 정보로 메운다.
  2. 굳힌다   두 쪽이 같은 값을 말하면 확신도를 올린다 — 사용자가 눈으로
              다시 확인해야 할 항목이 줄어든다.
  3. 짚는다   두 쪽이 다르면 **어느 쪽도 고르지 않고** 둘 다 보여 준다.
              사진이 틀렸을 수도, 등록 정보가 오래됐을 수도 있다.

**말없이 덮어쓰지 않는다.** 결과는 확인 창의 재료일 뿐이고, 무엇을 쓸지는
사용자가 고른다. 등록 정보라고 무조건 맞는 것도 아니다 — 포장을 바꾸고 변경
보고를 안 한 제품이 흔하다.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# 두 값이 "같은 말" 이라고 볼 점수. 완전일치를 요구하면 띄어쓰기·괄호 차이로
# 전부 불일치가 되고, 너무 낮추면 다른 제품을 같다고 한다.
AGREE_SCORE = 88
# 이보다 낮으면 "다르다" 고 짚는다. 사이 구간은 판단을 보류한다(비슷하긴 하다).
CONFLICT_SCORE = 60

_WS = re.compile(r'\s+')

# 대조할 항목과 비교 방식.
#
#   exact     짧고 정형화된 값. 표기 흔들림만 감안해 곧이곧대로 견준다.
#   contains  한쪽이 다른 쪽을 품는다. 사진의 제조원은 "회사명 + 주소" 인데
#             등록 정보에는 회사명만 있다. 곧이곧대로 견주면 늘 불일치가 난다.
#   loose     길고 표기가 자유로운 값. 다르다고 곧장 단정하지 않고 참고로만 둔다.
#             원재료명은 인쇄물에 원산지·함량이 붙고 등록 정보에는 없다.
_FIELD_POLICY = {
    'prdlst_report_no': ('prdlst_report_no', '품목보고번호', 'exact'),
    'prdlst_nm':        ('prdlst_nm',        '제품명',       'exact'),
    'prdlst_dcnm':      ('prdlst_dcnm',      '식품유형',     'exact'),
    'bssh_nm':          ('bssh_nm',          '제조원',       'contains'),
    'pog_daycnt':       ('pog_daycnt',       '소비기한',     'period'),
    'frmlc_mtrqlt':     ('frmlc_mtrqlt',     '포장재질',     'loose'),
    'rawmtrl_nm':       ('rawmtrl_nm',       '원재료명',     'loose'),
}


def _squeeze(text):
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


def _ratio(a, b, mode):
    """두 값의 닮은 정도(0~100). rapidfuzz 가 없으면 완전일치만 본다."""
    x, y = _squeeze(a), _squeeze(b)
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


def _compare(ocr_value, api_value, mode):
    """
    한 항목을 견줘 (점수, 판정) 을 낸다.

    'period' 는 글자가 아니라 뜻을 본다. 나머지는 닮은 정도로 판정한다.
    """
    if mode == 'period':
        a, b = parse_period_days(ocr_value), parse_period_days(api_value)
        if a is not None and b is not None:
            if a == b:
                return 100, 'agree'
            # 개월/일 환산의 어림(30일) 때문에 하루 이틀은 어긋난다.
            near = abs(a - b) <= max(2, min(a, b) * 0.05)
            return (95, 'agree') if near else (0, 'conflict')
        # 한쪽이 "별도표기일까지" 처럼 기간을 안 적은 경우. 어긋난 게 아니다.
        return _ratio(ocr_value, api_value, 'loose'), 'unsure'

    score = _ratio(ocr_value, api_value, mode)
    if score >= AGREE_SCORE:
        return score, 'agree'
    if score < CONFLICT_SCORE and mode != 'loose':
        # 길고 자유로운 값(원재료명·포장재질)은 표기 차이만으로도 크게 벌어진다.
        # 그걸 "틀렸다" 고 하면 매번 울리는 경고가 된다.
        return score, 'conflict'
    return score, 'unsure'


def normalize_report_no(text):
    """
    품목보고번호에서 붙어 온 군더더기를 뗀다.

    사진에서는 "품목보고번호: 2024 0123 456789" 처럼 항목명·띄어쓰기가 섞여
    오고, 하이픈이 있는 번호("20170415080-1271")도 있다. 조회 대상은 저장된
    문자열 그대로이므로 몇 가지 꼴을 만들어 차례로 시도한다.

    Returns: 시도할 문자열들 (중복 없이, 원문에 가까운 순서)
    """
    raw = str(text or '').strip()
    if not raw:
        return []
    # 항목명이 앞에 붙어 온 경우를 떼어 낸다
    raw = re.sub(r'^\s*(품목\s*보고\s*번호|보고번호)\s*[:：]?\s*', '', raw)
    packed = _WS.sub('', raw)
    digits_and_dash = re.sub(r'[^0-9\-]', '', packed)
    digits = re.sub(r'\D', '', packed)

    out = []
    for candidate in (raw, packed, digits_and_dash, digits):
        candidate = candidate.strip('-')
        # 품목보고번호는 최소 열 자리는 된다. 그보다 짧으면 잘못 읽은 것이다.
        if len(candidate) >= 10 and candidate not in out:
            out.append(candidate)
    return out


def _value_of(item):
    """{'value':…, 'confidence':…} 또는 맨 값에서 값만 꺼낸다."""
    if isinstance(item, dict):
        return str(item.get('value') or '').strip()
    return str(item or '').strip()


def _candidates_of(item):
    if isinstance(item, dict):
        return [str(c).strip() for c in (item.get('candidates') or []) if str(c).strip()]
    return []


def find_food_item(ocr_data):
    """
    판독 결과의 품목보고번호로 등록 품목을 찾는다.

    확신도가 낮아 후보만 온 경우도 시도한다 — 후보 중 하나가 실제로 등록돼
    있으면 그게 정답일 가능성이 높고, 이 조회 자체가 번호를 검증해 준다.

    Returns: (FoodItem 또는 None, 실제로 맞은 번호)
    """
    from v1.label.models import FoodItem

    item = (ocr_data or {}).get('prdlst_report_no')
    tries = []
    for text in [_value_of(item)] + _candidates_of(item):
        for form in normalize_report_no(text):
            if form not in tries:
                tries.append(form)
    if not tries:
        return None, ''

    try:
        found = {f.prdlst_report_no: f
                 for f in FoodItem.objects.filter(prdlst_report_no__in=tries)}
    except Exception:
        logger.exception('품목보고번호 조회 실패 (%s)', tries[:3])
        return None, ''

    for form in tries:                 # 원문에 가까운 꼴을 먼저 채택한다
        if form in found:
            return found[form], form
    return None, ''


def reconcile(ocr_data):
    """
    판독 결과를 등록 정보와 대조한 결과를 만든다. **원본은 건드리지 않는다.**

    Returns: {
        'matched': bool,
        'report_no': '조회에 쓴 번호',
        'source': '식약처 품목보고',
        'fields': {항목: {'api_value', 'ocr_value', 'score', 'verdict', 'label'}},
        'agreed': [항목…], 'filled': [항목…], 'conflicts': [항목…],
        'summary': '사람이 읽을 한 줄',
    }

    verdict 는 넷 중 하나다.
        'filled'    사진이 못 읽은 자리를 등록 정보로 채울 수 있다
        'agree'     두 쪽이 같은 말을 한다 — 확신해도 된다
        'conflict'  두 쪽이 다르다 — 사람이 골라야 한다
        'unsure'    비슷하긴 한데 단정할 수 없다 (참고만)
    """
    empty = {'matched': False, 'report_no': '', 'source': '식약처 품목보고',
             'fields': {}, 'agreed': [], 'filled': [], 'conflicts': [],
             'summary': ''}

    item, report_no = find_food_item(ocr_data)
    if item is None:
        return empty

    fields = {}
    agreed, filled, conflicts = [], [], []
    for key, (attr, label, mode) in _FIELD_POLICY.items():
        api_value = str(getattr(item, attr, '') or '').strip()
        if not api_value:
            continue
        ocr_value = _value_of((ocr_data or {}).get(key))
        row = {'label': label, 'api_value': api_value,
               'ocr_value': ocr_value, 'score': 0, 'verdict': ''}

        if not ocr_value:
            row['verdict'] = 'filled'
            filled.append(key)
        else:
            row['score'], row['verdict'] = _compare(ocr_value, api_value, mode)
            if row['verdict'] == 'agree':
                agreed.append(key)
            elif row['verdict'] == 'conflict':
                conflicts.append(key)
        fields[key] = row

    parts = [f'품목보고번호 {report_no} 로 등록 정보를 찾았습니다.']
    if agreed:
        parts.append(f'{len(agreed)}개 항목이 등록 정보와 일치합니다.')
    if filled:
        names = ', '.join(fields[k]['label'] for k in filled)
        parts.append(f'사진에서 못 읽은 {names} 을(를) 등록 정보로 채울 수 있습니다.')
    if conflicts:
        names = ', '.join(fields[k]['label'] for k in conflicts)
        parts.append(f'{names} 은(는) 사진과 등록 정보가 다릅니다 — 확인이 필요합니다.')

    return {
        'matched': True,
        'report_no': report_no,
        'source': '식약처 품목보고',
        'fields': fields,
        'agreed': agreed,
        'filled': filled,
        'conflicts': conflicts,
        'summary': ' '.join(parts),
    }


def _flag_truncated_rawmtrl(data, row):
    """
    합치지 못했을 때 **왜 못 했는지**를 짚는다.

    등록 정보의 원재료를 사진에서 거의 못 찾으면 합치지 않는다 — 그때 합치면
    사진에 없는 원재료를 인쇄한다. 그런데 **판독이 중간에서 끊겼을 때가 바로
    그 경우**이고, 하필 그때가 등록 정보가 가장 필요한 순간이다.

    그래서 값은 그대로 두되, 등록 정보 쪽이 훨씬 길면 "끊긴 것 같다" 고 알리고
    등록 정보를 후보로 올린다. 고를지는 확인 창에서 사람이 정한다.

    실제로 원재료 15개짜리 라벨에서 6개만 읽힌 적이 있다. 그때 화면에는
    "대조하면 +0점" 만 떴고, 무엇이 잘못됐는지는 아무 데도 안 적혔다.
    """
    try:
        from v1.label.services.ocr_rawmtrl import split_top_level
        ocr_count = len(split_top_level(row['ocr_value']))
        api_count = len(split_top_level(row['api_value']))
    except Exception:
        logger.exception('원재료 개수를 세지 못했다')
        return

    if api_count < 2 or ocr_count >= api_count * 0.8:
        return

    item = dict(data.get('rawmtrl_nm') or {})
    item['warnings'] = list(item.get('warnings') or []) + [
        f'사진에서 읽은 원재료가 {ocr_count}개인데 등록 정보에는 {api_count}개입니다 — '
        f'목록이 중간에서 끊겼을 수 있습니다. 원재료명 영역만 잘라 다시 읽어 보세요.'
    ]
    candidates = [c for c in (item.get('candidates') or []) if c]
    for value in (row['ocr_value'], row['api_value']):
        if value and value not in candidates:
            candidates.append(value)
    item['candidates'] = candidates
    item['confidence'] = 'low'
    data['rawmtrl_nm'] = item


def merge(ocr_data, result=None):
    """
    대조 결과를 판독 결과에 반영한 **새 dict** 를 만든다.

    반영이라고 해도 값을 갈아치우는 것은 사진이 아예 못 읽은 자리뿐이다.
    나머지는 확신도와 후보만 손댄다 — 무엇을 쓸지는 확인 창에서 사람이 고른다.

      못 읽은 자리   등록 정보를 값으로 넣고 confidence='high', source='api'
      일치           confidence='high' 로 올리고 source='both'
      불일치         값은 사진 것을 그대로 두되 confidence='low' 로 내리고
                     등록 정보를 후보에 넣는다 — 확인 창이 고르게 한다
    """
    data = dict(ocr_data or {})
    if result is None:
        result = reconcile(data)
    if not result.get('matched'):
        return data

    for key, row in result['fields'].items():
        item = data.get(key)
        item = dict(item) if isinstance(item, dict) else {
            'value': str(item or '') or None,
            'confidence': 'high' if item else 'none',
        }
        verdict = row['verdict']

        if verdict == 'filled':
            item['value'] = row['api_value']
            item['confidence'] = 'high'
        elif verdict == 'agree':
            item['confidence'] = 'high'
        elif verdict == 'conflict':
            item['confidence'] = 'low'
            candidates = [c for c in (item.get('candidates') or []) if c]
            for value in (row['ocr_value'], row['api_value']):
                if value and value not in candidates:
                    candidates.append(value)
            item['candidates'] = candidates

        if verdict in ('filled', 'agree', 'conflict', 'unsure'):
            item['api_value'] = row['api_value']
            item['api_verdict'] = verdict
            item['api_score'] = row['score']
            item['source'] = {'filled': 'api', 'agree': 'both',
                              'conflict': 'conflict'}.get(verdict, 'photo')
        data[key] = item

    _align_rawmtrl(data, result)
    return data


def _align_rawmtrl(data, result):
    """
    원재료명은 등록 정보를 **뼈대**로 쓴다.

    등록 정보의 원재료는 원산지와 복합원재료를 뺀 채 라벨과 같은 순서로 적혀
    있다 — OCR 을 거치지 않았으니 이름과 순서가 틀릴 이유가 없다. 사진에서 읽은
    쪽은 반대로 원산지·복합원재료·함량이 붙어 있지만 이름이 흔들린다.
    그래서 **이름과 순서는 등록 정보에서, 나머지는 사진에서** 가져와 합친다.

    'loose' 판정이라 지금까지 원재료명은 대조해도 아무 일도 일어나지 않았다 —
    표기가 달라 점수가 낮게 나오는 게 정상이라 'unsure' 로 끝났다.

    합친 값은 확인 창이 무엇을 어떻게 바꿨는지 보여 준다. **말없이 고치지
    않는다.**
    """
    row = (result.get('fields') or {}).get('rawmtrl_nm')
    if not row or row['verdict'] == 'filled':
        return
    ocr_value = row['ocr_value']
    if not ocr_value or not row['api_value']:
        return

    try:
        from v1.label.services.ocr_rawmtrl import align_summary, align_with_api
        aligned = align_with_api(ocr_value, row['api_value'])
    except Exception:
        logger.exception('원재료명 순서 맞추기 실패')
        return

    if not aligned:
        _flag_truncated_rawmtrl(data, row)
        return
    if aligned['text'].strip() == ocr_value.strip():
        return

    item = dict(data.get('rawmtrl_nm') or {})
    item['value'] = aligned['text']
    item['snapped_from'] = ocr_value
    item['snapped_note'] = (align_summary(aligned)
                            or '등록 정보의 원재료 순서·명칭에 맞췄습니다.')
    item['aligned'] = {
        'renamed': aligned['renamed'],
        'reordered': aligned['reordered'],
        'api_only': aligned['api_only'],
        'ocr_only': aligned['ocr_only'],
    }
    data['rawmtrl_nm'] = item
