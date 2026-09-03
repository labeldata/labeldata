"""
알레르기 표시 명칭을 하나로 판정한다.

**같은 물질이 여러 표기로 돌아다닌다.**

    알류  /  알류(달걀)  /  달걀  /  알류 함유  /  난류

라벨에는 이 중 어떤 것이 적혀도 이상하지 않다. 표시기준이 정한 명칭은 "알류"
이고, 괄호는 무엇을 넣었는지 밝히는 부연이다("알류(달걀)"). 그런데 이 값을
다루는 자리가 다섯이었고 — 사진 판독, 원재료명 자동 감지, 손으로 고르는 칩,
저장값 로드, 규정 검증 — **전부 문자열을 그대로 키로 썼다.**

그래서 운영에서 이렇게 나왔다.

    저장값     "알류(달걀),우유,대두,밀"      -> 키 네 개
    자동 감지  원재료명에서 "달걀" 을 찾음   -> 키 "알류" 하나 더
    화면       알류(달걀), 우유, 대두, 밀, 알류      <- 같은 것이 둘

여기서 판정을 한 번만 한다. 다른 모듈은 이 함수를 부른다 — 규칙을 여러 벌로
만들면 어느 날 한쪽만 고쳐진다. 화면도 같은 규칙을 써야 해서
`static/js/label/allergen_names.js` 에 같은 함수가 있다(브라우저에서 태그를
그리는 자리라 서버를 부를 수가 없다). 둘이 어긋나지 않는지는 시험이 지킨다.
"""
import re

from v1.label.constants import ALLERGEN_KEYWORDS

# 표시기준이 정한 표시 명칭. 사전의 키가 곧 그 목록이다.
CANONICAL_NAMES = tuple(ALLERGEN_KEYWORDS.keys())

# 값 뒤에 붙는 꼬리말. 물질 이름이 아니다.
_TAIL = re.compile(r'\s*(함유|포함|사용|들어있음|등)\s*$')

# 괄호 부연. "알류(달걀)" 의 "(달걀)", "대두[콩]" 의 "[콩]".
_PAREN = re.compile(r'[(\[（【][^)\]）】]*[)\]）】]')


def _squeeze(text):
    return ''.join(str(text or '').split()).lower()


def _keyword_index():
    """키워드 -> 표시 명칭. 사전은 상수라 한 번만 만든다."""
    global _KEYWORD_INDEX
    if _KEYWORD_INDEX is None:
        index = {}
        for name, keywords in ALLERGEN_KEYWORDS.items():
            index[_squeeze(name)] = name
            for keyword in keywords:
                index.setdefault(_squeeze(keyword), name)
        _KEYWORD_INDEX = index
    return _KEYWORD_INDEX


_KEYWORD_INDEX = None


def canonical(token):
    """
    표기 하나를 표시 명칭으로. 모르면 빈 문자열.

        "알류(달걀)" -> "알류"      괄호는 부연이다
        "달걀"       -> "알류"      키워드는 그 물질에 속한다
        "알류 함유"  -> "알류"      꼬리말을 뗀다
        "난류"       -> "알류"      옛 이름도 키워드에 있다
        "홍삼"       -> ""          목록 밖 — 판정하지 않는다

    **모르면 빈 문자열이다.** 억지로 가장 닮은 것을 골라 주면, 목록 밖의 문구를
    적어 둔 라벨의 값을 엉뚱한 물질로 바꿔 버린다.
    """
    text = _TAIL.sub('', str(token or '').strip()).strip(' ·,')
    if not text:
        return ''

    index = _keyword_index()

    # 통째로 아는 이름인가 ("알류", "달걀")
    hit = index.get(_squeeze(text))
    if hit:
        return hit

    # 괄호를 떼면 아는 이름인가 ("알류(달걀)" -> "알류")
    base = _TAIL.sub('', _PAREN.sub('', text)).strip(' ·,')
    if base:
        hit = index.get(_squeeze(base))
        if hit:
            return hit

    # 괄호 안이 아는 이름인가 ("(달걀)" 만 남은 표기)
    for inner in _PAREN.findall(text):
        hit = index.get(_squeeze(inner.strip('()[]（）【】')))
        if hit:
            return hit

    # 한 글자 차이 정도는 맞춰 준다 ("대두류" -> "대두"). 사전이 없으면 건너뛴다.
    try:
        from v1.label.services.ocr_snap import snap_one
        snapped, _score, verdict = snap_one(base or text, list(CANONICAL_NAMES))
        if verdict in ('exact', 'snapped'):
            return snapped
    except Exception:
        pass
    return ''


def display_form(token, name):
    """
    라벨에 적을 표기. 표시 명칭이거나, 명칭에 괄호 부연이 붙은 꼴만 그대로 둔다.

        "알류(달걀)" -> "알류(달걀)"   명칭 + 부연. 무엇을 넣었는지까지 말한다
        "알류"       -> "알류"
        "대두류"     -> "대두"         명칭이 아니다. 규정이 요구하는 이름으로
        "달걀"       -> "알류"

    규정이 요구하는 것은 **명칭**이고, 뒤에서 이 값을 키로 쓰는 곳(원재료명
    대조)이 그 명칭을 찾는다. "대두류" 처럼 명칭을 품고는 있지만 명칭이 아닌
    표기를 남겨 두면, 어느 목록에서도 정확히 안 찾힌다.
    """
    text = _TAIL.sub('', str(token or '').strip()).strip(' ·,')
    if text == name:
        return name
    if re.fullmatch(re.escape(name) + r'\s*[(\[（【][^)\]）】]*[)\]）】]', text):
        return text
    return name


def _better_form(a, b, name):
    """같은 물질의 두 표기 중 자세한 쪽. 부연이 붙은 쪽을 남긴다."""
    return a if len(a) >= len(b) else b


def merge(tokens):
    """
    표기 목록을 물질 단위로 합친다.

    Returns: (합친 표기 목록, [{'kept', 'dropped', 'name'} …])

    목록 밖의 문구는 지우지 않고 그대로 둔다 — 그런 것을 적어 두는 라벨이 있고,
    지우면 정보가 사라진다. 중복만 지운다.
    """
    order = []          # 결과 순서 (표시 명칭 또는 원문)
    by_name = {}        # 표시 명칭 -> 지금 남아 있는 표기
    unknown = set()     # 목록 밖의 원문
    changes = []

    for raw in tokens:
        token = _TAIL.sub('', str(raw or '').strip()).strip(' ·,')
        if not token:
            continue
        name = canonical(token)
        if not name:
            if token in unknown:
                continue
            unknown.add(token)
            order.append(('raw', token))
            continue
        form = display_form(token, name)
        if name not in by_name:
            by_name[name] = form
            order.append(('name', name))
            if form != token:
                changes.append({'name': name, 'kept': form, 'dropped': token})
            continue
        # 이미 있는 물질이다. 둘 중 자세한 표기를 남긴다.
        kept = _better_form(by_name[name], form, name)
        by_name[name] = kept
        changes.append({'name': name, 'kept': kept, 'dropped': token})

    out = []
    for kind, key in order:
        out.append(by_name[key] if kind == 'name' else key)
    return out, changes


def normalize(text):
    """
    선언 문구 한 줄을 정리한다.

        "알류(달걀),우유,대두,밀,알류 함유" -> ("알류(달걀), 우유, 대두, 밀", [...])

    쉼표·가운뎃점으로 가르고, 꼬리말을 떼고, 같은 물질을 합친다.
    """
    raw = str(text or '').strip()
    if not raw:
        return '', []
    tokens = re.split(r'[,、，/·]', raw)
    merged, changes = merge(tokens)
    return ', '.join(merged), changes
