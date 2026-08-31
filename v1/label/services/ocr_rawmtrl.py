"""
원재료명 한 줄을 다룬다 — 괄호 짝 검사와 등록 정보 순서 맞추기.

원재료명은 판독에서 가장 길고 가장 자주 틀리는 항목이다. 두 가지를 한다.

**① 괄호 짝 검사.**
    모델이 대괄호와 소괄호를 자주 혼동한다. "정제소금[국산]" 을 "정제소금(국산]"
    으로 읽는 식이다. 그런데 괄호는 반드시 **열림과 닫힘이 짝**이고 순서가 있다 —
    그 규칙이 깨졌다는 것은 그 자리를 잘못 읽었다는 뜻이다. 값을 하나하나 눈으로
    대조하지 않고도 **어디를 다시 봐야 하는지** 짚을 수 있다.

    짝이 맞는지만 본다. 고치지는 않는다 — 어느 쪽을 잘못 읽었는지는 사진을
    봐야 알고, 임의로 닫아 주면 틀린 자리를 덮어 버린다.

**② 등록 정보 순서 맞추기.**
    식약처 등록 정보(`FoodItem.rawmtrl_nm`)의 원재료는 **원산지와 복합원재료를
    뺀 채, 라벨과 같은 순서**로 적혀 있다. 그러니까 등록 정보는 이 제품 원재료의
    "뼈대" 다 — OCR 을 거치지 않았으니 이름과 순서가 틀릴 이유가 없다.

    사진에서 읽은 것은 반대로 원산지·복합원재료·함량이 붙어 있지만 이름이
    흔들린다. 그래서 **뼈대는 등록 정보에서, 살은 사진에서** 가져와 합친다.

        등록 정보  돼지고기, 정제소금, 백설탕
        사진 판독  돼지고가(국내산), 정재소금(국산), 백설탕 2%
        합친 결과  돼지고기(국내산), 정제소금(국산), 백설탕 2%

    **확신이 없으면 손대지 않는다.** 등록 정보의 원재료 중 사진에서 찾은 것이
    너무 적으면 다른 제품이거나 판독이 무너진 것이다. 그때 합치면 사진에 없는
    원재료를 인쇄하게 된다.
"""
import logging
import re

logger = logging.getLogger(__name__)

# 여는 괄호 -> 닫는 괄호. 라벨에는 전각과 반각이 섞여 들어온다.
PAIRS = {
    '(': ')', '[': ']', '{': '}',
    '（': '）', '［': '］', '｛': '｝',
    '〔': '〕', '「': '」', '『': '』', '《': '》', '〈': '〉',
}
CLOSERS = {close: open_ for open_, close in PAIRS.items()}

# 괄호 이름. 경고 문구에 쓴다 - "짝이 안 맞습니다" 만으로는 어디를 볼지 모른다.
_BRACKET_NAMES = {
    '(': '소괄호 ( )', '（': '소괄호 ( )',
    '[': '대괄호 [ ]', '［': '대괄호 [ ]',
    '{': '중괄호 { }', '｛': '중괄호 { }',
}

_WS = re.compile(r'\s+')
_SPLIT = re.compile(r'[,，、]')
# 함량은 이름이 아니다. 등록 정보에는 없고 라벨에만 붙는다.
_AMOUNT = re.compile(r'\s*\d+(?:\.\d+)?\s*%\s*$')

# 사진의 원재료 하나를 등록 정보의 원재료와 "같은 것" 이라고 보는 기준.
#
# 비율(fuzz.ratio)만 쓰면 짧은 이름에서 무너진다 — "돼지고기"→"돼지고가" 는 한
# 글자 차이인데 네 글자 중 하나라 75점밖에 안 나온다. 원재료 이름은 대개 서너
# 글자라 이 구간이 그대로 급소다. 그래서 **고친 글자 수**를 기준으로 하고,
# 이름이 길수록 예산을 늘린다(ocr_snap 과 같은 방식).
MATCH_MIN_SCORE = 55     # 거리는 가까운데 뜻이 전혀 다른 경우를 거르는 하한


def _edit_budget(length):
    if length <= 4:
        return 1
    if length <= 10:
        return 2
    return 3


def _distance(a, b):
    """고쳐야 하는 글자 수. rapidfuzz 가 없으면 같은지 여부만 본다."""
    try:
        from rapidfuzz.distance import Levenshtein
    except ImportError:
        return 0 if a == b else 99
    return Levenshtein.distance(a, b)


# 등록 정보의 원재료 중 이만큼은 사진에서 찾아야 합친다. 그보다 적으면
# 다른 제품이거나 판독이 무너진 것이다.
ALIGN_MIN_COVERAGE = 0.6


def _name(text):
    return _BRACKET_NAMES.get(text, '괄호')


def bracket_problems(text):
    """
    괄호 짝을 검사한다. 문제가 없으면 빈 목록.

    Returns: ['…' …]  사람이 읽을 문장들
    """
    value = str(text or '')
    stack = []
    problems = []

    for index, char in enumerate(value):
        if char in PAIRS:
            stack.append((char, index))
            continue
        if char not in CLOSERS:
            continue
        if not stack:
            problems.append(
                '%d번째 글자에서 열린 적 없는 "%s" 가 닫힙니다.' % (index + 1, char))
            continue
        opened, at = stack.pop()
        if PAIRS[opened] != char:
            problems.append(
                '%d번째 글자의 "%s" 를 "%s" 로 닫았습니다 — %s 와 %s 를 혼동한 것으로 보입니다.'
                % (at + 1, opened, char, _name(opened), _name(CLOSERS[char])))

    for opened, at in stack:
        problems.append(
            '%d번째 글자의 "%s" 가 닫히지 않았습니다.' % (at + 1, opened))
    return problems


def split_top_level(text):
    """
    쉼표로 가르되 **괄호 안의 쉼표는 세지 않는다.**

    "면류(밀가루(밀:미국산), 정제수), 소스" 를 셋으로 가르면 복합원재료가
    통째로 부서진다.
    """
    value = str(text or '')
    depth = 0
    out, buf = [], []
    for char in value:
        if char in PAIRS:
            depth += 1
        elif char in CLOSERS and depth > 0:
            depth -= 1
        if depth == 0 and _SPLIT.match(char):
            out.append(''.join(buf).strip())
            buf = []
            continue
        buf.append(char)
    tail = ''.join(buf).strip()
    if tail:
        out.append(tail)
    return [token for token in out if token]


def split_token(token):
    """
    원재료 하나를 (이름, 함량, 원산지·하위원료) 으로 가른다.

        "돼지고기 30%(국내산)"   ->  ("돼지고기", "30%", "(국내산)")
        "면류(밀가루(밀:미국산))" ->  ("면류", "", "(밀가루(밀:미국산))")
        "돼지고기 95.36 %/국산"  ->  ("돼지고기", "95.36 %", "/국산")

    **원산지를 괄호로만 쓰는 게 아니다.** "소콜라겐/네덜란드산" 처럼 빗금으로
    붙이는 라벨이 흔하다. 괄호만 보면 이런 라벨에서 이름과 원산지가 한 덩어리로
    묶여, 등록 정보(원산지가 없다)와 아무것도 맞출 수 없게 된다.

    이름만 등록 정보와 견주고, 함량과 원산지는 사진에서 읽은 것을 그대로
    옮긴다 — 등록 정보에는 없는 정보다.
    """
    text = str(token or '').strip()
    head, extra = text, ''
    for index, char in enumerate(text):
        # 빗금은 괄호와 같은 일을 한다 — 뒤쪽이 원산지다.
        if char in PAIRS or char == '/':
            head, extra = text[:index].strip(), text[index:].strip()
            break

    amount = ''
    found = _AMOUNT.search(head)
    if found:
        amount = found.group(0).strip()
        head = head[:found.start()].strip()
    return head, amount, extra


def join_token(name, amount, extra):
    parts = name
    if amount:
        parts += ' ' + amount
    if extra:
        # 빗금 표기는 이름에 바로 붙는다("소콜라겐/네덜란드산"). 괄호도 마찬가지다.
        parts += extra
    return parts


def _ratio(a, b):
    try:
        from rapidfuzz import fuzz
    except ImportError:      # 순서 맞추기만 못 할 뿐, 판독은 계속돼야 한다
        return 100 if a == b else 0
    return int(fuzz.ratio(a, b))


def _squeeze(text):
    return _WS.sub('', str(text or '')).lower()


def align_with_api(ocr_text, api_text):
    """
    사진에서 읽은 원재료명을 등록 정보의 **순서와 이름**에 맞춰 다시 쓴다.

    Returns: None (손대지 않는 편이 낫다) 또는 {
        'text':     합친 원재료명,
        'renamed':  [{'from','to','score'} …]  이름을 등록 정보로 바로잡은 것
        'reordered': bool                      순서가 바뀌었는가
        'api_only': [이름 …]   등록 정보에는 있는데 사진에서 못 찾은 것
        'ocr_only': [원문 …]   사진에만 있는 것 (뒤에 그대로 붙인다)
    }
    """
    api_tokens = split_top_level(api_text)
    ocr_tokens = split_top_level(ocr_text)
    if len(api_tokens) < 2 or not ocr_tokens:
        return None

    api_names = [split_token(token)[0] for token in api_tokens]
    api_names = [name for name in api_names if name]
    if len(api_names) < 2:
        return None

    parsed = [split_token(token) for token in ocr_tokens]
    used = [False] * len(parsed)

    out, renamed, api_only = [], [], []
    order_of_match = []
    for name in api_names:
        target = _squeeze(name)
        best_index, best_distance, best_score = -1, 99, 0
        for index, (head, _amount, _extra) in enumerate(parsed):
            if used[index]:
                continue
            squeezed = _squeeze(head)
            distance = _distance(target, squeezed)
            if distance < best_distance:
                best_index = index
                best_distance = distance
                best_score = _ratio(target, squeezed)

        budget = _edit_budget(max(len(target), 1))
        if best_index < 0 or best_distance > budget or best_score < MATCH_MIN_SCORE:
            api_only.append(name)
            continue

        used[best_index] = True
        order_of_match.append(best_index)
        head, amount, extra = parsed[best_index]
        if _squeeze(head) != target:
            renamed.append({'from': head, 'to': name, 'score': best_score})
        out.append(join_token(name, amount, extra))

    if len(out) < len(api_names) * ALIGN_MIN_COVERAGE:
        # 등록 정보의 원재료를 사진에서 거의 못 찾았다. 다른 제품이거나 판독이
        # 무너진 것이다 — 여기서 합치면 사진에 없는 원재료를 인쇄한다.
        return None

    # 사진에만 있는 것은 버리지 않는다. 등록 정보가 오래됐을 수도 있고,
    # 복합원재료를 따로 떼어 적은 라벨일 수도 있다. 뒤에 그대로 붙이고 알린다.
    ocr_only = [ocr_tokens[i] for i, taken in enumerate(used) if not taken]
    out.extend(ocr_only)

    return {
        'text': ', '.join(out),
        'renamed': renamed,
        'reordered': order_of_match != sorted(order_of_match),
        'api_only': api_only,
        'ocr_only': ocr_only,
    }


def align_summary(result):
    """확인 창에 띄울 한 줄. 바꾼 게 없으면 빈 문자열."""
    if not result:
        return ''
    parts = []
    if result['renamed']:
        names = ', '.join('"%s" → "%s"' % (row['from'], row['to'])
                          for row in result['renamed'][:4])
        parts.append('원재료 이름을 등록 정보에 맞췄습니다: ' + names)
    if result['reordered']:
        parts.append('등록 정보의 순서(함량 순)로 다시 늘어놓았습니다')
    if result['api_only']:
        parts.append('등록 정보에는 있는데 사진에서 못 읽은 원재료가 있습니다: '
                     + ', '.join(result['api_only'][:5]))
    if not parts:
        return ''
    return ' · '.join(parts) + '. 사진과 다르면 값을 직접 고쳐 주세요.'


def inspect(ocr_data):
    """
    판독 결과의 원재료명에 괄호 문제가 있으면 그 항목에 경고를 남긴다.

    **원본은 건드리지 않고** 새 dict 를 돌려준다. 값은 고치지 않는다 — 어느
    쪽을 잘못 읽었는지는 사진을 봐야 안다. 다시 볼 자리를 짚어 줄 뿐이다.

    Returns: (새 data, [경고 문장 …])
    """
    data = dict(ocr_data or {})
    item = data.get('rawmtrl_nm')
    value = item.get('value') if isinstance(item, dict) else item
    problems = bracket_problems(value)
    if not problems:
        return data, []

    item = dict(item) if isinstance(item, dict) else {
        'value': str(value or '') or None,
        'confidence': 'high' if value else 'none',
    }
    item['warnings'] = list(item.get('warnings') or []) + problems
    # 괄호가 깨진 값은 그 자리를 잘못 읽은 것이다. 확신도를 내려 확인 창이
    # "확인" 으로 표시하게 한다.
    if item.get('confidence') == 'high':
        item['confidence'] = 'low'
    data['rawmtrl_nm'] = item
    return data, problems
