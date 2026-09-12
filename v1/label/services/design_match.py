# -*- coding: utf-8 -*-
"""
시안에서 읽은 값과 우리가 확정한 값을 **항목마다 다른 자로** 견준다.

왜 서버로 옮겼나
────────────────
이 판정은 `basic_info_ocr.js` 안에 있었고, `compareGrade` 하나가 **모든 항목에
같은 규칙**을 썼다. 그래서 이런 것들이 전부 '다름' 으로 떨어졌다.

    빵류        ↔  빵류 [가열하여 섭취하는 냉동식품]   부기인데 다름
    (주)○○식품  ↔  주식회사 ○○식품                  같은 회사인데 다름
    12.5g       ↔  12.50g                          같은 값인데 다름
    주의사항     ↔  줄바꿈 자리만 다른 같은 문구        통째로 다름

셋 다 **순수한 오탐**이고 사용자가 가장 자주 만나는 것들이다. 그리고 오탐은
놓침보다 값이 비싸다 — 놓침은 한 번 겪으면 기능을 더 믿게 되지만, 오탐은
세 번 겪으면 기능을 닫는다. 닫힌 기능은 놓침도 못 막는다.

정책을 여기 두는 까닭은 `value_match` 를 검증·판독과 **같이 쓰기 위해서**다.
JS 에 규칙 표를 두면 파이썬 쪽과 두 벌이 되고, 두 벌은 언젠가 한쪽만 고쳐진다.

느슨해지는 방향이라는 것
────────────────────────
이 작업은 전부 "같다고 보는 범위를 넓히는" 일이다. 지나치면 놓침이 는다.
그래서 둘을 지킨다.

  - **수치는 눅이지 않는다.** 표기만 고르고 값이 다르면 12.5 와 12.6 도 다르다.
  - **같다고 본 까닭을 남긴다**(reason). 사람이 우리 판단을 되짚을 수 있어야
    한다. 조용히 넘어가는 것과 "부기라서 같게 봤다" 는 다른 일이다.
"""
from v1.label.services import value_match as vm

# 항목마다 견주는 법. 이름은 value_match 의 것을 그대로 쓴다.
#
#   exact     짧고 정형화된 값
#   prefix    앞이 같고 뒤가 괄호 부기면 같은 말
#   company   법인격 표기를 지우고 이름만
#   period    글자가 아니라 기간
#   number    표기를 고른 뒤 **수치로**
#   sentence  문장 단위 집합
#   loose     길고 자유로운 값
FIELD_MODE = {
    'prdlst_nm':           'strict',
    'prdlst_dcnm':         'prefix',     # 빵류 ↔ 빵류[가열하여…]
    'content_weight':      'number',     # 12.5g ↔ 12.50g
    'prdlst_report_no':    'strict',
    'country_of_origin':   'strict',
    'bssh_nm':             'company',    # (주)○○ ↔ 주식회사 ○○
    'distributor_address': 'company',
    'repacker_address':    'company',
    'importer_address':    'company',
    'storage_method':      'sentence',
    'rawmtrl_nm':          'strict',     # 라벨에 인쇄되는 글자 그 자체다
    'allergens':           'sentence',
    'ingredient_info':     'number',     # 특정성분 함량 — 수치가 핵심이다
    'frmlc_mtrqlt':        'strict',
    'pog_daycnt':          'period',
    'cautions':            'sentence',
    'additional_info':     'sentence',
}
DEFAULT_MODE = 'strict'

# 눅여도 되는 자는 이것뿐이다. 나머지는 **글자가 같아야 같다.**
#
# 여기가 검증·판독과 갈리는 자리다. 그쪽은 식약처 등록 정보와 견주므로
# 표기가 흔들리는 것이 정상이라 유사도(AGREE_SCORE 88)로 봐준다. 그런데
# 시안 대조가 묻는 것은 **"인쇄물이 우리가 확정한 값 그대로인가"** 다.
#
# 실제로 유사도를 쓰게 했더니 이런 것이 '같음' 으로 떨어졌다.
#
#     초코쿠키  ↔  초코칩쿠키      유사도 88.9 — 다른 제품이다
#
# 원재료명은 더 위험하다. 300 자 중 한 원료가 빠져도 유사도는 거의 안
# 떨어지는데, 그 한 원료가 알레르기 유발물질일 수 있다. 놓침은 눈에 안
# 보이므로 이런 자리는 아예 유사도를 들이지 않는다.
_FORGIVING = ('prefix', 'company', 'number', 'period', 'sentence')

# 화면이 쓰는 등급. 판정을 바꾸는 것이 아니라 **부르는 이름**을 맞춘 것이다.
SAME, SPACING, PARTIAL, DIFF = 'same', 'spacing', 'partial', 'diff'
# 시안 원문에서 그 글자를 못 찾은 값. '다름' 과 같은 칸에 두면 안 된다 —
# 아래 grade_field 주석 참고.
UNREAD = 'unread'

_WHY = {
    'prefix':   '부기라 같게 봤습니다',
    'company':  '법인격 표기 차이입니다',
    'number':   '수치가 같습니다',
    'period':   '기간이 같습니다',
    'sentence': '문장이 같습니다',
}


def grade_field(field, mine, theirs, grounded=True):
    """
    한 항목을 견줘 화면이 쓸 모양으로 낸다.

    {grade, mode, score, reason, missing}
      grade    same · spacing · partial · diff · unread
      reason   같다고 본 까닭 (사람이 되짚을 수 있게). 다를 때는 빈 값
      missing  sentence 에서 한쪽에만 있는 문장들

    grounded=False 는 **판독 모델이 낸 값을 OCR 원문에서 못 찾았다**는 뜻이다
    (ocr_ground). 그 값으로 "시안에 이렇게 적혀 있습니다" 라고 단정하면,
    사용자는 **멀쩡한 시안을 고치러 간다** — 이 기능이 낼 수 있는 가장 나쁜
    오탐이다.

    그렇다고 값을 고치거나 버리지도 않는다. OCR 도 틀리기 때문이다. 원문을
    정답으로 삼으면 OCR 의 오독이 그대로 굳는다. **다르다고 말하는 대신
    "확인하지 못했다" 고 말한다** — 짚되 단정하지 않는 자리다.
    """
    mine = (mine or '').strip()
    theirs = (theirs or '').strip()
    mode = FIELD_MODE.get(field, DEFAULT_MODE)

    if not mine and not theirs:
        return {'grade': SAME, 'mode': mode, 'score': 100, 'reason': '', 'missing': []}
    if not mine or not theirs:
        # 한쪽이 비어 있으면 견줄 것이 없다. 이건 표기 차이가 아니라 빠진 것이다.
        return {'grade': DIFF, 'mode': mode, 'score': 0, 'reason': '', 'missing': []}

    if not grounded:
        # 값은 그대로 보여 주되 "다르다" 고 단정하지 않는다.
        return {'grade': UNREAD, 'mode': mode, 'score': 0,
                'reason': '시안 원문에서 이 값을 찾지 못했습니다',
                'missing': []}

    if mine == theirs:
        return {'grade': SAME, 'mode': mode, 'score': 100, 'reason': '', 'missing': []}
    if vm.squeeze(mine) == vm.squeeze(theirs):
        # 글자는 같고 공백·기호만 다르다. 접어 두면 될 일이다.
        return {'grade': SPACING, 'mode': mode, 'score': 100, 'reason': '', 'missing': []}

    if mode == 'sentence':
        score, verdict, missing = vm.compare_sentences(mine, theirs)
        if verdict == 'agree':
            return {'grade': SPACING, 'mode': mode, 'score': score,
                    'reason': _WHY['sentence'], 'missing': []}
        if verdict == 'partial':
            return {'grade': PARTIAL, 'mode': mode, 'score': score,
                    'reason': '', 'missing': missing}
        return {'grade': DIFF, 'mode': mode, 'score': score,
                'reason': '', 'missing': missing}

    score = 0
    if mode in _FORGIVING:
        if mode == 'number':
            score, verdict = vm.compare_numbers(mine, theirs)
        else:
            score, verdict = vm.compare(mine, theirs, mode)
        if verdict == 'agree':
            return {'grade': SPACING, 'mode': mode, 'score': score,
                    'reason': _WHY.get(mode, ''), 'missing': []}

    # 한쪽이 다른 쪽에 통째로 들어 있으면 읽다 끊긴 것일 때가 많다. 시안이
    # 틀린 것이 아니라 우리가 덜 읽은 것이라, 같은 무게로 짚으면 안 된다.
    a, b = vm.squeeze(mine), vm.squeeze(theirs)
    if len(a) > 12 and len(b) > 12 and (a in b or b in a):
        return {'grade': PARTIAL, 'mode': mode, 'score': score,
                'reason': '', 'missing': []}

    return {'grade': DIFF, 'mode': mode, 'score': score, 'reason': '', 'missing': []}


def grade_all(pairs):
    """
    {field: {'mine': ..., 'design': ...}} 를 받아 항목마다 판정을 돌려준다.
    양쪽 다 빈 항목은 아예 빼서, 화면이 "대조할 것이 없는 줄" 을 그리지 않게 한다.
    """
    out = {}
    for field, pair in (pairs or {}).items():
        mine = (pair or {}).get('mine') or ''
        theirs = (pair or {}).get('design') or ''
        if not str(mine).strip() and not str(theirs).strip():
            continue
        # 안 적어 보내면 대조를 안 켠 것이다. 그때는 예전처럼 판정한다.
        grounded = (pair or {}).get('grounded')
        out[field] = grade_field(field, str(mine), str(theirs),
                                 grounded=(grounded is not False))
    return out
