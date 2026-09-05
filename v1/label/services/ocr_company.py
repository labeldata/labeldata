"""
제조원·유통전문판매원·소분원·수입원을 가른다.

이 넷은 **거의 언제나 다른 회사**다. 만드는 곳과 파는 곳이 같으면 라벨에
"제조원 및 유통전문판매원" 처럼 한 줄로 묶어 적지, 칸을 나눠 같은 값을 두 번
적지 않는다. 그런데 판독은 이 넷을 자주 헷갈린다. 이유가 셋이다.

  1. 인쇄물에서 네 줄이 **붙어 있다.** 표의 한 칸 안에 세로로 이어 적히는
     일이 흔해서, 한 칸을 읽으면 다음 회사까지 딸려 들어온다.
         제조원 (주)가나다식품 경기도 …  유통전문판매원 (주)라마바 서울 …
     이게 통째로 bssh_nm 하나에 들어온다.

  2. 넷이 **똑같이 생겼다.** 전부 "업체명 + 주소" 다. 값만 보고는 어느
     칸의 것인지 알 수 없어서, 모델이 한 줄을 두 칸에 옮겨 적어도 그 자리에서는
     아무도 이상한 것을 모른다.

  3. 항목 이름이 값에 섞여 들어온다. "제조원 : (주)가나다" 처럼.

여기서는 **값을 지어내지 않는다.** 붙어 온 것을 제자리로 나누고, 나눌 수 없는
것은 짚어 알린다. 어느 쪽이 맞는지 모르는 자리는 후보로만 올린다.

식약처 등록 정보와의 관계도 여기서 정한다. 등록된 **업소명은 제조원**이다.
유통전문판매원도 소분원도 아니다. 그래서 등록 업소명은
  - 제조원 칸하고만 견주고,
  - 견줄 때는 **업체명 부분만** 본다. 등록 정보에 주소는 없다.
주소까지 통째로 견주면 회사 이름과 상관없는 지명이 우연히 맞아 "일치" 가 된다.
"""
import re
import unicodedata

# 이 넷이 역할 칸이다. 순서는 라벨에 적히는 순서.
ROLE_FIELDS = ('bssh_nm', 'distributor_address', 'repacker_address',
               'importer_address')

ROLE_LABELS = {
    'bssh_nm': '제조원',
    'distributor_address': '유통전문판매원',
    'repacker_address': '소분원',
    'importer_address': '수입원',
}

# 라벨마다 부르는 이름이 다르다. 긴 것부터 찾아야 "유통전문판매원" 이
# "판매원" 으로 잘리지 않는다.
_ROLE_WORDS = {
    'bssh_nm': ('제조원', '제조사', '제조자', '제조업소명', '제조업소',
                '제조가공업소', '제조판매원', '생산자', '업소명및소재지'),
    'distributor_address': ('유통전문판매원', '유통전문판매업소', '유통전문판매',
                            '유통판매원', '유통업소', '판매원', '판매업소'),
    'repacker_address': ('소분원', '소분업소', '소분판매원', '소분처'),
    'importer_address': ('수입원', '수입판매원', '수입판매업소', '수입업소',
                         '수입자'),
}

_WORD_TO_FIELD = {}
for _field, _words in _ROLE_WORDS.items():
    for _w in _words:
        _WORD_TO_FIELD[_w.replace(' ', '')] = _field


def _spaced(word):
    """인쇄물은 "제 조 원" 처럼 자간을 벌려 찍는다. 그것도 같은 말이다."""
    return r'\s*'.join(re.escape(ch) for ch in word)


# 뒤에 한글이 이어지면 항목 이름이 아니다 — "제조원료" 의 "제조원" 을 걸러 낸다.
_ROLE_RE = re.compile(
    '(?:' + '|'.join(_spaced(w) for w in
                     sorted(_WORD_TO_FIELD, key=len, reverse=True)) + ')'
    r'(?![가-힣])')

# 항목 이름 뒤에 붙는 것들. 콜론도 있고 아무것도 없기도 하다.
_SEP_RE = re.compile(r'^[\s:：·\-/|,]*')

_SIDO = ('강원특별자치도', '제주특별자치도', '전북특별자치도', '충청북도',
         '충청남도', '전라북도', '전라남도', '경상북도', '경상남도',
         '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
         '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주')
_SIDO_RE = re.compile('|'.join(sorted(_SIDO, key=len, reverse=True)))

# 시·도가 안 적힌 주소도 흔하다("안성시 …"). 그 경우의 시작점.
_CITY_RE = re.compile(r'[가-힣]{2,5}(?:시|군|구)(?=[\s,]|$)')

# 주소가 맞다고 볼 흔적. 하나라도 있으면 소재지가 적힌 것이다.
_ADDR_HINT = re.compile(
    r'(?:[가-힣0-9]+(?:로|길)\s*\d)'        # 도로명 + 번호
    r'|(?:[가-힣]{1,6}(?:읍|면|동|리)\s)'    # 법정동
    r'|(?:\d+\s*(?:번지|호))'
    r'|(?:\d{2,4}-\d{1,4})')               # 지번

# 회사임을 알리는 꼬리표.
_COMPANY_RE = re.compile(
    r'㈜|\(\s*주\s*\)|\(\s*유\s*\)|주식회사|유한회사|유한책임회사|합자회사'
    r'|합명회사|농업회사법인|영농조합법인|협동조합|[Cc]o\.|[Ii]nc\.?|[Ll]td')


def _nfkc(text):
    return unicodedata.normalize('NFKC', str(text or ''))


def key(value):
    """
    견줄 때만 쓰는 형태.

    공백과 법인격 표기를 지운다. "(주)가나다" 와 "가나다(주)" 와 "주식회사
    가나다" 는 같은 회사이고, 라벨·등록 정보·사람이 저마다 다르게 적는다.
    """
    s = _nfkc(value)
    s = _COMPANY_RE.sub('', s)
    s = re.sub(r'[\s,.\-·/()\[\]]', '', s)
    return s.lower()


def strip_role_label(value):
    """맨 앞에 붙어 온 항목 이름을 뗀다. ("제조원 : (주)가나다" → "(주)가나다")"""
    text = _nfkc(value).strip()
    m = _ROLE_RE.match(text)
    if not m:
        return text
    rest = _SEP_RE.sub('', text[m.end():]).strip()
    # 이름만 있고 값이 없으면 뗄 것이 아니다 — 그 값 자체가 "제조원" 이었다.
    return rest if rest else text


def find_roles(text):
    """
    글 안에 적힌 항목 이름의 자리. [(필드, 이름 시작, 값 시작)…]

    맨 앞의 것도 포함한다 — 부르는 쪽이 "이 값은 제 이름으로 시작한다" 를
    알아야 하기 때문이다.
    """
    text = _nfkc(text)
    out = []
    for m in _ROLE_RE.finditer(text):
        field = _WORD_TO_FIELD.get(re.sub(r'\s+', '', m.group(0)))
        if not field:
            continue
        value_at = m.end() + len(_SEP_RE.match(text[m.end():]).group(0))
        out.append((field, m.start(), value_at))
    return out


def split_roles(text):
    """
    한 칸에 뭉쳐 온 여러 회사를 항목별로 가른다.

    Returns: {필드: 값} — 항목 이름이 하나도 없으면 빈 사전.
    """
    text = _nfkc(text).strip()
    marks = find_roles(text)
    if not marks:
        return {}
    out = {}
    for i, (field, _, value_at) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        value = text[value_at:end].strip(' \t,·/|-')
        if value and field not in out:
            out[field] = value
    return out


def address_start(value):
    """주소가 시작하는 자리. 못 찾으면 None."""
    text = _nfkc(value)
    m = _SIDO_RE.search(text)
    if m:
        return m.start()
    m = _CITY_RE.search(text)
    if m:
        return m.start()
    return None


def split_company_address(value):
    """
    "업체명 + 주소" 를 둘로 가른다.

    주소를 못 찾으면 전부 업체명으로 본다 — 등록 업소명과 견주는 쪽에서는
    그게 안전하다. 주소를 업체명으로 잘못 보면 점수가 떨어질 뿐이지만,
    업체명을 주소로 잘못 보면 견줄 것이 사라진다.
    """
    text = strip_role_label(value)
    at = address_start(text)
    if at is None:
        return text, ''
    return text[:at].strip(' ,·/'), text[at:].strip()


def company_part(value):
    """업체명 부분만. 등록 업소명과 견줄 때 쓴다."""
    return split_company_address(value)[0]


def has_address(value):
    text = _nfkc(value)
    return bool(_SIDO_RE.search(text) or _ADDR_HINT.search(text)
                or _CITY_RE.search(text))


def has_company(value):
    return bool(_COMPANY_RE.search(_nfkc(value)))


def _value_of(item):
    if isinstance(item, dict):
        return str(item.get('value') or '').strip()
    return str(item or '').strip()


def _as_item(item, value):
    out = dict(item) if isinstance(item, dict) else {}
    out['value'] = value
    if not out.get('confidence'):
        out['confidence'] = 'medium' if value else 'none'
    return out


def _warn(item, message):
    item['warnings'] = list(item.get('warnings') or []) + [message]
    return item


def _add_candidate(item, value):
    cands = [c for c in (item.get('candidates') or []) if c]
    if value and value not in cands:
        cands.append(value)
    item['candidates'] = cands
    return item


def tidy(data):
    """
    네 역할 칸을 제자리에 돌려놓는다. **새 dict 를 돌려준다.**

    하는 일은 넷이다.

      1. 값에 섞여 온 항목 이름을 뗀다.
      2. 한 칸에 뭉쳐 온 다른 회사를 그 회사의 칸으로 옮긴다. 그 칸이 이미 차
         있으면 옮기지 않고 후보로만 올린다 — 덮어쓰면 제대로 읽힌 값이 사라진다.
      3. 두 칸에 같은 회사가 들어온 것을 짚는다. 대개 한 줄을 두 번 옮겨 적은
         것이다. **지우지는 않는다** — 정말 같은 회사인 제품도 있다.
      4. 업체명이나 주소 한쪽이 빠진 것을 짚는다.
    """
    if not isinstance(data, dict):
        return data
    out = dict(data)

    # ── 1·2. 이름을 떼고, 뭉쳐 온 것을 가른다 ────────────────────────────────
    for field in ROLE_FIELDS:
        raw = _value_of(out.get(field))
        if not raw:
            continue
        item = _as_item(out.get(field), raw)

        parts = split_roles(raw)
        marks = find_roles(raw)
        mine = strip_role_label(raw)
        foreign = [(f, at) for f, at, _ in marks if f != field]

        if foreign:
            # 내 값은 첫 번째 남의 이름 앞까지다. 그 앞에 내 이름이 있었다면
            # 그 뒤부터, 없었다면 처음부터.
            head_at = marks[0][2] if marks[0][0] == field else 0
            mine = _nfkc(raw)[head_at:foreign[0][1]].strip(' \t,·/|-')
            moved, kept = [], []
            for other, _ in foreign:
                value = parts.get(other, '')
                if not value:
                    continue
                if _value_of(out.get(other)):
                    kept.append(other)
                    out[other] = _add_candidate(
                        _as_item(out.get(other), _value_of(out.get(other))), value)
                else:
                    moved.append(other)
                    moved_item = _as_item(out.get(other), value)
                    moved_item['confidence'] = 'medium'
                    out[other] = _warn(
                        moved_item,
                        f'{ROLE_LABELS[field]} 칸에서 붙어 온 것을 여기로 옮겼습니다 — '
                        f'사진에서 두 줄이 한 칸에 이어 적혀 있었습니다.')
            if moved or kept:
                names = ', '.join(ROLE_LABELS[f] for f in moved + kept)
                item = _warn(
                    item,
                    f'이 칸에 {names}까지 함께 읽혔습니다 — 서로 다른 회사이므로 '
                    f'갈라 놓았습니다. 사진과 맞는지 확인하세요.')
                item['confidence'] = 'low'

        item['value'] = mine
        out[field] = item

    # ── 3. 두 칸에 같은 회사 ────────────────────────────────────────────────
    seen = {}
    for field in ROLE_FIELDS:
        value = _value_of(out.get(field))
        if not value:
            continue
        k = key(company_part(value)) or key(value)
        if k:
            seen.setdefault(k, []).append(field)
    for fields in seen.values():
        if len(fields) < 2:
            continue
        names = ' · '.join(ROLE_LABELS[f] for f in fields)
        for field in fields:
            out[field] = _warn(
                _as_item(out.get(field), _value_of(out.get(field))),
                f'{names} 이(가) 같은 회사로 읽혔습니다. 이 항목들은 대개 서로 다른 '
                f'회사입니다 — 사진의 한 줄을 두 칸에 옮겨 적었을 수 있습니다. '
                f'정말 같은 회사라면 그대로 두세요.')

    # ── 4. 한쪽이 빠졌다 ────────────────────────────────────────────────────
    for field in ROLE_FIELDS:
        value = _value_of(out.get(field))
        if not value:
            continue
        item = _as_item(out.get(field), value)
        if not has_address(value):
            item = _warn(
                item,
                f'{ROLE_LABELS[field]}에 소재지가 안 보입니다 — 업체명과 주소를 '
                f'함께 적어야 합니다. 주소 줄이 잘려 읽혔는지 확인하세요.')
        elif not company_part(value):
            item = _warn(
                item,
                f'{ROLE_LABELS[field]}에 주소만 읽히고 업체명이 없습니다 — '
                f'앞줄이 잘려 읽혔는지 확인하세요.')
        out[field] = item

    return out


# 등록 업소명과 "같은 회사" 라고 볼 점수.
SAME_COMPANY = 85


def _similar(a, b):
    x, y = key(a), key(b)
    if not x or not y:
        return 0
    if x == y or x in y or y in x:
        return 100
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return 0
    return int(fuzz.ratio(x, y))


def match_registered_name(value, api_name):
    """
    등록 업소명과 한 칸의 값을 견준다. **업체명 부분만** 본다.

    주소까지 넣고 견주면 "충청남도 대한로" 같은 지명이 "(주)대한" 에 우연히
    맞아 일치가 된다. 등록 정보에는 애초에 주소가 없다.
    """
    return _similar(company_part(value), api_name)


def misplaced_registered_name(data, api_name):
    """
    등록 업소명이 **제조원이 아닌 칸**에 들어갔는가.

    등록된 업소명은 제조원이다. 유통전문판매원도 소분원도 아니다. 그것이
    유통전문판매원 칸에서 발견되면 두 줄이 자리를 바꿔 읽힌 것이다 — 값만
    봐서는 알 수 없고, 등록 정보가 있어야 비로소 드러난다.

    Returns: 자리를 바꿔 들어간 것으로 보이는 필드, 없으면 None.
    """
    if not api_name:
        return None
    mine = _value_of((data or {}).get('bssh_nm'))
    if mine and match_registered_name(mine, api_name) >= SAME_COMPANY:
        return None
    for field in ROLE_FIELDS:
        if field == 'bssh_nm':
            continue
        value = _value_of((data or {}).get(field))
        if value and match_registered_name(value, api_name) >= SAME_COMPANY:
            return field
    return None


# ── 다시 봐야 할 때 ────────────────────────────────────────────────────────
#
# 첨부된 실제 라벨이 왜 틀렸는지가 여기 다 들어 있다.
#
#     ┌──────────┬───────────────────────────────────┐
#     │ 유통전문 │ [오뚜기 로고]  주식회사 오뚜기      │
#     │ 판매원   │                경기도 안양시 동안   │
#     │          │                구 흥안대로 405     │
#     ├──────────┼───────────────────────────────────┤
#     │ 제조원   │ ㈜샤니                             │
#     │          │ 경기도 성남시 중원구 둔촌대        │
#     │          │ 로457번길 13(상대원동)             │
#     └──────────┴───────────────────────────────────┘
#
#   - 항목 이름이 **왼쪽 칸**에 있고 칸이 좁아 두 줄로 접힌다("유통전문/판매원")
#   - 로고 그림이 항목 이름과 회사 이름 사이에 끼어 있다
#   - **유통전문판매원이 제조원보다 위**에 있다 (순서가 정해져 있지 않다)
#   - 오뚜기 쪽이 로고에 굵은 글씨라 눈에 먼저 들어온다
#   - 주소가 줄 끝에서 단어 중간에 끊긴다("동안 / 구", "둔촌대 / 로457번길")
#
# 그래서 판독이 "제조원" 을 보고도 가장 도드라진 회사(오뚜기)를 집어 두 칸에
# 같은 회사를 넣었다. 값만 보고는 알 수 없다 — 둘 다 멀쩡한 "업체명 + 주소" 다.
#
# 이럴 때는 **그 네 줄만 다시 본다.** 서른 항목을 한 번에 읽는 프롬프트에서는
# 이 네 줄에 갈 주의가 얼마 없지만, 네 줄만 물으면 전부가 거기로 간다.

RECHECK_PROMPT = """이 사진에서 **업소 항목만** 찾아 그대로 옮겨 적으세요.

찾을 항목: 제조원(제조사·제조업소·생산자), 유통전문판매원(판매원), 소분원, 수입원

규칙
1. 항목 이름은 대개 표의 **왼쪽 칸**에 있고, 칸이 좁아 두 줄로 접힙니다.
   "유통전문 / 판매원" 은 접힌 한 항목입니다. 이어서 읽으세요.
2. 각 항목의 값은 그 이름의 **오른쪽(또는 바로 아래)** 에서 시작해 다음 항목
   이름 전까지입니다.
3. **로고 그림은 값이 아닙니다.** 로고 옆이나 아래의 회사 이름이 값입니다.
4. **순서는 정해져 있지 않습니다.** 유통전문판매원이 제조원보다 위에 오기도
   합니다. 눈에 먼저 띄는 회사가 아니라 **그 항목 이름과 같은 칸**의 회사를
   적으세요.
5. 이 항목들은 **서로 다른 회사**입니다. 두 항목에 같은 회사를 적지 마세요.
   사진에 "제조원 및 유통전문판매원" 처럼 한 줄로 묶여 있을 때만 같습니다.
6. 주소가 줄 끝에서 단어 중간에 끊겨 있으면 이어 붙이세요("동안 / 구" →
   "동안구"). 사진에 없는 항목은 목록에서 빼세요. 지어내지 마세요.

아래 형식의 JSON 으로만 답하세요.
{"companies": [{"role": "제조원", "name": "㈜샤니", "address": "경기도 …"}]}"""


def needs_recheck(data):
    """
    업소 항목을 다시 봐야 하는가. 이유를 돌려준다. 없으면 ''.

    다시 보는 데는 호출이 하나 더 든다. **틀린 낌새가 보일 때만** 본다.
    """
    if not isinstance(data, dict):
        return ''
    filled = {f: _value_of(data.get(f)) for f in ROLE_FIELDS}
    filled = {f: v for f, v in filled.items() if v}
    if not filled:
        return ''

    # 두 칸에 같은 회사. 이 항목들은 대개 다른 회사이므로 적어도 한쪽은 틀렸다.
    keys = {}
    for field, value in filled.items():
        k = key(company_part(value)) or key(value)
        if k:
            keys.setdefault(k, []).append(field)
    for fields in keys.values():
        if len(fields) > 1:
            return '%s 이(가) 같은 회사로 읽혔습니다' % (
                ' · '.join(ROLE_LABELS[f] for f in fields))

    # 제조원은 거의 모든 라벨에 있다. 다른 역할만 읽혔다면 자리를 밀려 읽었을
    # 가능성이 높다.
    if 'bssh_nm' not in filled:
        return '제조원이 비어 있는데 %s 만 읽혔습니다' % (
            ', '.join(ROLE_LABELS[f] for f in filled))
    return ''


def _joined(entry):
    """다시 읽은 한 줄을 "업체명 주소" 로 잇는다."""
    name = str(entry.get('name') or '').strip()
    address = str(entry.get('address') or '').strip()
    return (name + ' ' + address).strip()


def apply_recheck(data, companies):
    """
    네 줄만 다시 읽은 결과를 반영한다. **새 dict 를 돌려준다.**

    다시 읽은 쪽이 반드시 옳다고 보지는 않는다. 다만 이 호출은 그 네 줄만
    물었으므로 서른 항목을 한꺼번에 읽은 쪽보다 그 자리에서는 낫다. 값이
    바뀌는 자리마다 무엇을 왜 바꿨는지 남기고 확신도를 내린다 — 확인 창이
    그 줄을 붉게 짚어 사람이 거기만 보게 한다.

    companies: [{'role': '제조원', 'name': …, 'address': …}, …]
    """
    if not isinstance(data, dict) or not companies:
        return data
    out = dict(data)

    fresh = {}
    for entry in companies:
        if not isinstance(entry, dict):
            continue
        marks = find_roles(str(entry.get('role') or ''))
        if not marks:
            continue
        value = _joined(entry)
        # 회사도 주소도 아닌 것은 안 받는다. 지어낸 값을 넣느니 그냥 둔다.
        if not value or not (has_company(value) or has_address(value)):
            continue
        fresh.setdefault(marks[0][0], value)

    if not fresh:
        return out

    for field, value in fresh.items():
        before = _value_of(out.get(field))
        if before and key(company_part(before)) == key(company_part(value)):
            continue          # 같은 회사다. 건드릴 것이 없다
        item = _as_item(out.get(field), value)
        item['confidence'] = 'medium'
        if before:
            # 처음 읽은 값은 후보로 남긴다. 확인 창에서 되돌릴 수 있어야 한다.
            #
            # **다시 읽었다는 말은 하지 않는다.** 그건 우리 사정이지 사용자가
            # 알아야 할 일이 아니다. 화면에 남아야 하는 것은 "이 칸에 무엇이
            # 들어갔고 다른 후보가 무엇인가" 뿐이다.
            item = _add_candidate(item, before)
        out[field] = item
    return out
