"""
인쇄된 원재료명 한 줄을 원료 목록으로 쪼갠다.

    "새송이버섯(국산)57.64%,과·채가공품/표고버섯채(중국산)21.63%(표고버섯,정제수,
     정제소금,구연산),애느타리버섯(국산)17.28%,콩기름(대두:외국산),천일염(국산),흑후추"

        -> 새송이버섯        국산        57.64%
           과·채가공품/표고버섯채  중국산  21.63%  (표고버섯, 정제수, 정제소금, 구연산)
           애느타리버섯      국산        17.28%
           콩기름            대두:외국산
           천일염            국산
           흑후추

이 저장소는 "자유서식 원재료 텍스트는 정규식으로 못 판다" 고 보고 순서 검증에
AI 를 쓴다(ai_validation_service). 그 판단은 **판정**에 대한 것이라 여기에는
그대로 적용되지 않는다. 여기서 하는 일은 두 가지뿐이다.

  1. 괄호 깊이를 세며 최상위 쉼표에서 자른다 - 괄호 짝 맞추기 문제라 정확하다
  2. 잘린 조각에서 함량·원산지·하위원료를 떼어낸다 - 자리에 규칙이 있다

그리고 **결과를 바로 쓰지 않는다.** 화면이 목록을 보여 주고 사용자가 고친 뒤에
저장한다. 그래서 애매한 표기를 만나도 조용히 틀리지 않는다.
"""
import re

# 「식품등의 표시기준」 알레르기 유발물질. 뒤에 붙은 선언을 떼어낼 때 쓴다.
ALLERGENS = [
    '알류', '난류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우',
    '돼지고기', '복숭아', '토마토', '아황산류', '호두', '닭고기', '쇠고기',
    '오징어', '조개류', '잣',
]

# 원재료명 뒤에 붙는 알레르기 선언. 원료가 아니므로 자르기 전에 떼어낸다.
#   "... 카로틴 알류(계란), 대두 함유"
#   "... [알레르기 성분: 밀, 우유 함유]"
_ALLERGEN_BRACKET = re.compile(r'\[\s*알레르기[^\]]*\]')
_HAS_TAIL = re.compile(r'함유\s*\.?\s*$')
_CUT_TAIL = re.compile(r'\s*함유\s*\.?\s*$')
# 조각의 **끝**이 알레르기명인가 (뒤에 "(계란)" 같은 부연이 붙어도 된다)
_ALLERGEN_END = re.compile(
    r'(' + '|'.join(sorted(ALLERGENS, key=len, reverse=True)) + r')'
    r'\s*(?:[(（][^)）]*[)）])?\s*$')

# 함량. 괄호 앞뒤 어디에 붙어도 잡는다.
_RATIO = re.compile(r'(\d+(?:\.\d+)?)\s*%')

# 원산지로 볼 괄호 내용.
#   국산 · 국내산 · 수입산 · 외국산 · 중국산 · 제주산 · "대두:외국산" · "국산:제주산"
_ORIGIN_WORD = re.compile(r'^(?:국내산|국산|수입산|외국산|[가-힣]{2,5}산)$')

# 끝이 '산' 이라 원산지로 헷갈리는 첨가물·원료들. 이들이 괄호에 홀로 있으면
# 원산지가 아니라 하위 원료다.
_NOT_ORIGIN = {
    '구연산', '젖산', '초산', '사과산', '주석산', '인산', '탄산', '황산', '염산',
    '아스코르브산', '글루탐산', '소브산', '푸마르산', '글루콘산', '올레산',
    '리놀레산', '스테아르산', '팔미트산', '아세트산', '피로인산', '메타인산',
}


def strip_allergen_tail(text):
    """
    끝에 붙은 알레르기 선언을 떼어낸다.

    Returns: (원재료 부분, 떼어낸 알레르기 문구)
    """
    raw = (text or '').strip()
    if not raw:
        return '', ''

    taken = []

    def grab(m):
        taken.append(m.group(0))
        return ''

    body = _ALLERGEN_BRACKET.sub(grab, raw).strip()

    # "... 알류(계란), 대두 함유" 처럼 괄호 밖에서 끝나는 형태.
    # 괄호 안에서 끝나면(예: "...(대두 함유)") 원료 설명이므로 두 손 뗀다.
    #
    # 뒤에서부터 알레르기 이름인 동안 계속 떼어낸다. 한 조각만 보면
    # "카로틴 알류(계란), 대두 함유" 에서 "대두 함유" 만 떨어지고 "알류(계란)" 이
    # 카로틴에 붙어 원료가 하나 잘못 생긴다.
    if _HAS_TAIL.search(body) and _balanced(body):
        work = _CUT_TAIL.sub('', body).rstrip(' ,')
        picked = []
        while work:
            segments = split_top_level(work)
            if not segments:
                break
            last = segments[-1]
            m = _ALLERGEN_END.search(last)
            if not m:
                break
            if m.start() == 0:
                # 조각 전체가 알레르기명이다
                picked.insert(0, last)
                work = ','.join(segments[:-1])
                continue
            # 앞에 원료가 붙어 있다 (OCR 이 쉼표를 놓친 경우). 이름만 뗀다.
            picked.insert(0, last[m.start():].strip())
            segments[-1] = last[:m.start()].rstrip(' ,')
            work = ','.join(s for s in segments if s)
            break
        if picked:
            taken.append(', '.join(picked) + ' 함유')
            body = work

    return body.strip().strip(','), ' '.join(t.strip() for t in taken if t.strip())


def _balanced(text):
    """괄호가 모두 닫혔는지."""
    depth = 0
    for ch in text:
        if ch in '(（':
            depth += 1
        elif ch in ')）':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def split_top_level(text):
    """
    괄호 밖의 쉼표에서만 자른다.

    "혼합제제(초산전분, 히드록시프로필인산이전분), 정제소금" 을 두 조각으로 만든다.
    안쪽 쉼표에서 자르면 첨가물 하나가 여러 원료로 쪼개진다.
    """
    parts, buf, depth = [], [], 0
    for ch in (text or ''):
        if ch in '(（[':
            depth += 1
        elif ch in ')）]':
            depth = max(0, depth - 1)
        if ch in ',，' and depth == 0:
            parts.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append(''.join(buf))
    return [p.strip() for p in parts if p.strip()]


def _paren_groups(text):
    """최상위 괄호 묶음을 (내용, 시작, 끝) 으로 돌려준다."""
    groups, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch in '(（':
            if depth == 0:
                start = i
            depth += 1
        elif ch in ')）':
            depth -= 1
            if depth == 0 and start is not None:
                groups.append((text[start + 1:i], start, i + 1))
                start = None
            depth = max(0, depth)
    return groups


def looks_like_origin(content):
    """이 괄호 내용이 원산지 표기인가."""
    body = (content or '').strip()
    if not body or ',' in body or '，' in body:
        return False          # 쉼표가 있으면 하위 원료 목록이다
    # "대두:외국산" · "국산:제주산" 은 뒷부분으로 판단한다
    tail = body.split(':')[-1].split('/')[-1].strip()
    if tail in _NOT_ORIGIN:
        return False
    return bool(_ORIGIN_WORD.match(tail))


def parse_item(chunk):
    """조각 하나에서 이름·함량·원산지·하위원료를 떼어낸다."""
    text = (chunk or '').strip()
    if not text:
        return None

    ratio = None
    m = _RATIO.search(text)
    if m:
        try:
            ratio = float(m.group(1))
        except ValueError:
            ratio = None
        text = (text[:m.start()] + ' ' + text[m.end():])

    origin, subs = '', ''
    # 뒤에서부터 본다 - 원산지는 이름 바로 뒤, 하위원료는 그보다 뒤에 온다
    for content, start, end in reversed(_paren_groups(text)):
        if looks_like_origin(content):
            if not origin:
                origin = content.strip()
                text = text[:start] + ' ' + text[end:]
        else:
            if not subs:
                subs = ', '.join(x.strip() for x in re.split(r'[,，]', content) if x.strip())
                text = text[:start] + ' ' + text[end:]

    name = re.sub(r'\s+', ' ', text).strip(' ,·/')
    if not name:
        return None
    return {
        'name': name,
        'ratio': ratio,
        'origin': origin,
        'sub_ingredients': subs,
    }


def parse_ingredient_list(text):
    """
    원재료명 한 줄 -> 원료 목록.

    Returns: {'items': [ {name, ratio, origin, sub_ingredients}, ... ],
              'allergen_note': 떼어낸 알레르기 문구}
    """
    body, allergen_note = strip_allergen_tail(text)
    items = []
    for chunk in split_top_level(body):
        item = parse_item(chunk)
        if item:
            items.append(item)
    return {'items': items, 'allergen_note': allergen_note}
