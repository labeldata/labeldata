"""
비고 한 칸에 **여러 값을 넣고도 표로 볼 수 있게** 한다.

원료마다 챙겨야 할 것이 회사마다 다르다 — 거래처, 규격, 로트, 단가, 인증.
칸을 그만큼 만들면 대부분의 회사에 빈 칸이 되고, 안 만들면 사람들이 비고에
몰아 적는다. 실제로 몰아 적고 있었다.

**저장은 그대로 두고, 보여 줄 때만 가른다.**

    저장   "거래처: 대상㈜ · 규격: 25kg 포대 · 로트: L2409"
    표시   거래처 | 규격      | 로트
           대상㈜ | 25kg 포대 | L2409

이 방향이 중요하다. 형식을 강요하면 그 형식에 안 맞는 것을 적을 데가 없어지고,
칸을 새로 만들면 마이그레이션이 따라온다. 비고는 자유 칸으로 남고, **양식에
맞게 적은 줄만** 열로 선다. 양식에 안 맞는 줄은 통째로 "비고" 에 남는다 —
버려지지 않는다.

엑셀로 내보낼 때도 같은 규칙을 쓴다. 기본 항목이 아닌 것은 이 양식으로 비고에
담기므로, 다시 읽어 들이면 그대로 열로 돌아온다.
"""
import re

# 항목을 가르는 글자. 사람들이 실제로 쓰는 것들이다.
SEPARATORS = ('·', '|', ';', '\n')

# "이름: 값" 을 알아본다. 이름에 콜론이 들어가는 일은 없다고 본다.
_PAIR = re.compile(r'^\s*([^:：]{1,20})\s*[:：]\s*(.*)$')

# 값이 없는 이름만 적힌 줄은 항목이 아니다 — 그냥 메모다.
MIN_VALUE_LEN = 1


def parse(note: str) -> tuple[dict, str]:
    """
    비고를 (항목, 남은 말) 로 가른다.

        "거래처: 대상㈜ · 25kg 포대"
        -> ({'거래처': '대상㈜'}, '25kg 포대')

    **가르지 못한 말은 버리지 않는다.** 두 번째 값으로 돌려주고, 화면은 그것을
    "비고" 열에 그대로 둔다. 사람이 적은 것을 우리가 이해 못 했다고 지울 수는
    없다.
    """
    text = str(note or '').strip()
    if not text:
        return {}, ''

    pattern = '[' + re.escape(''.join(SEPARATORS)) + ']'
    fields, leftovers = {}, []
    for chunk in re.split(pattern, text):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _PAIR.match(chunk)
        if m and len(m.group(2).strip()) >= MIN_VALUE_LEN:
            name = m.group(1).strip()
            value = m.group(2).strip()
            if name in fields:            # 같은 이름이 두 번이면 이어 붙인다
                fields[name] += ' ' + value
            else:
                fields[name] = value
        else:
            leftovers.append(chunk)
    return fields, ' · '.join(leftovers)


def format(fields: dict, leftover: str = '') -> str:
    """
    항목들을 비고 한 줄로. `parse` 의 반대다.

    엑셀에서 읽어 들일 때 쓴다 — 기본 항목이 아닌 열은 이 꼴로 비고에 담기고,
    다시 열어 보면 `parse` 가 그대로 열로 돌려놓는다.
    """
    parts = ['%s: %s' % (name, value)
             for name, value in (fields or {}).items()
             if str(value).strip()]
    if leftover and str(leftover).strip():
        parts.append(str(leftover).strip())
    return ' · '.join(parts)


def columns(notes) -> list[str]:
    """
    이 비고들에 들어 있는 항목 이름을 **처음 나온 순서대로**.

    가나다순으로 세우지 않는다 — 사람이 적은 순서가 그 사람이 중요하게 보는
    순서다(배합비 엑셀 붙여넣기에서 배운 것과 같다).
    """
    seen = []
    for note in notes or ():
        for name in parse(note)[0]:
            if name not in seen:
                seen.append(name)
    return seen


def table(notes) -> dict:
    """
    화면이 표로 그릴 재료.

        {'columns': ['거래처', '규격'],
         'rows': [{'거래처': '대상㈜', '규격': '25kg', '비고': '남은 말'}, …]}
    """
    names = columns(notes)
    rows = []
    for note in notes or ():
        fields, leftover = parse(note)
        row = {name: fields.get(name, '') for name in names}
        row['비고'] = leftover
        rows.append(row)
    return {'columns': names, 'rows': rows}


def search_terms(query: str) -> list[str]:
    """
    비고를 뒤질 때 실제로 찾아볼 문자열들.

    사람은 "거래처: 대상" 이라고도 "거래처:대상" 이라고도 친다. 우리가 적어
    넣은 꼴은 `이름: 값`(콜론 뒤 한 칸) 하나뿐이라, 띄어쓰기를 안 쓰면 안
    찾힌다 — **적어 놨는데 못 찾겠다** 가 그렇게 난다.

    항목 이름만 치면(`거래처`) 그 항목이 적힌 줄을 모두 찾는다.
    """
    text = str(query or '').strip()
    if not text:
        return []

    for mark in (':', '：'):
        if mark in text:
            name, _, value = text.partition(mark)
            name, value = name.strip(), value.strip()
            if not name:
                break
            if not value:
                return ['%s:' % name]          # 이름만 — 그 항목이 있는 줄
            # 우리가 적는 꼴이 먼저다
            return ['%s: %s' % (name, value), '%s:%s' % (name, value)]
    return [text]
