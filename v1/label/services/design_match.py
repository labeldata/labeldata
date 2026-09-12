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
    'prdlst_nm':           'exact',
    'prdlst_dcnm':         'prefix',     # 빵류 ↔ 빵류[가열하여…]
    'content_weight':      'number',     # 12.5g ↔ 12.50g
    'prdlst_report_no':    'exact',
    'country_of_origin':   'loose',
    'bssh_nm':             'company',    # (주)○○ ↔ 주식회사 ○○
    'distributor_address': 'company',
    'repacker_address':    'company',
    'importer_address':    'company',
    'storage_method':      'sentence',
    'rawmtrl_nm':          'loose',
    'allergens':           'sentence',
    'ingredient_info':     'number',     # 특정성분 함량 — 수치가 핵심이다
    'frmlc_mtrqlt':        'loose',
    'pog_daycnt':          'period',
    'cautions':            'sentence',
    'additional_info':     'sentence',
}
DEFAULT_MODE = 'exact'

# 화면이 쓰는 등급. 판정을 바꾸는 것이 아니라 **부르는 이름**을 맞춘 것이다.
SAME, SPACING, PARTIAL, DIFF = 'same', 'spacing', 'partial', 'diff'

_WHY = {
    'prefix':   '부기라 같게 봤습니다',
    'company':  '법인격 표기 차이입니다',
    'number':   '수치가 같습니다',
    'period':   '기간이 같습니다',
    'sentence': '문장이 같습니다',
}


def grade_field(field, mine, theirs):
    """
    한 항목을 견줘 화면이 쓸 모양으로 낸다.

    {grade, mode, score, reason, missing}
      grade    same · spacing · partial · diff
      reason   같다고 본 까닭 (사람이 되짚을 수 있게). 다를 때는 빈 값
      missing  sentence 에서 한쪽에만 있는 문장들
    """
    mine = (mine or '').strip()
    theirs = (theirs or '').strip()
    mode = FIELD_MODE.get(field, DEFAULT_MODE)

    if not mine and not theirs:
        return {'grade': SAME, 'mode': mode, 'score': 100, 'reason': '', 'missing': []}
    if not mine or not theirs:
        # 한쪽이 비어 있으면 견줄 것이 없다. 이건 표기 차이가 아니라 빠진 것이다.
        return {'grade': DIFF, 'mode': mode, 'score': 0, 'reason': '', 'missing': []}

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
        out[field] = grade_field(field, str(mine), str(theirs))
    return out
