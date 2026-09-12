# -*- coding: utf-8 -*-
"""
시안 대조 판정을 정답지로 채점한다. **오탐과 놓침을 따로 낸다.**

왜 따로 내는가
──────────────
두 실패는 값이 전혀 다르다.

    놓침(miss)   다른데 같다고 했다    → 인쇄 사고. 치명적이지만 **안 보인다**
    오탐(false)  같은데 다르다고 했다  → 매번 보인다. **기능을 안 쓰게 만든다**

하나로 합쳐 "정확도 92%" 라고 하면 어느 쪽이 나빠졌는지 알 수 없다. 작업 3·4
에서 오탐을 줄이려고 판정을 눅였는데, 그러다 **놓침을 하나 들여왔다가 시험이
우연히 잡았다**(초코쿠키 ↔ 초코칩쿠키가 '같음' 으로 떨어졌다). 잡은 것은 운이
좋았던 것이고, 지금도 놓침이 늘었는지 잴 방법이 없다.

오탐은 사용자가 말해 준다. **놓침은 아무도 말해 주지 않는다** — 인쇄가 나온
뒤에야 안다. 그래서 재야 한다.

무엇을 재는가
─────────────
판독까지 다시 돌리지 않는다. 정답지의 `expected`(시안에 인쇄된 값)를 시안
쪽으로 두고 `label_values`(내 표시사항)와 견준다. **재려는 것은 판정 규칙**
(design_match)이고, 그 규칙이 작업 3·4 에서 바뀐 것이다.

판독까지 함께 재려면 Vision 을 매번 불러야 해서 값이 비싸다. 판독 정확도는
이미 따로 재고 있다(ocr_lab) — 두 물음을 섞지 않는다.
"""
import logging

logger = logging.getLogger(__name__)

# '다르다' 고 본 등급. same·spacing 은 같다고 본 것이고, unread 는
# **판정을 보류한 것**이라 어느 쪽으로도 세지 않는다.
FLAGGED = ('diff', 'partial')


def grade_case(case):
    """
    정답지 한 건을 채점한다. 쓸 수 없으면 None.

    {name, hits, misses, falses, fields:[...]}
      hits    정말 다른 것을 다르다고 했다
      misses  정말 다른데 **같다고 했다**          ← 인쇄 사고
      falses  같은데 **다르다고 했다**             ← 기능을 닫게 만든다
    """
    from v1.label.services import design_match, ocr_lab

    mine = dict(getattr(case, 'label_values', None) or {})
    theirs = dict(getattr(case, 'expected', None) or {})
    if not mine or not theirs:
        return None       # 시안 대조용으로 채워 두지 않은 정답지

    # expected 는 판독 결과 모양({'value':…})으로 저장되기도 한다
    def plain(v):
        if isinstance(v, dict):
            return str(v.get('value') or '')
        return str(v or '')

    truth = set(getattr(case, 'expected_diff', None) or [])
    pairs = {}
    for key in set(mine) | set(theirs):
        a, b = plain(mine.get(key)), plain(theirs.get(key))
        # **내 표시사항을 안 적은 칸은 채점하지 않는다.**
        #
        # 처음에는 빈 칸도 견주었다. 그랬더니 사람이 '다른 것 몇 개' 만
        # 적어 넣은 정답지에서 나머지 스무 칸이 전부 '빈 값 ↔ 인쇄된 값' 이
        # 되어 오탐으로 잡혔다. 안 적은 것은 **같다는 뜻도 다르다는 뜻도
        # 아니다** — 재지 않는 것이 맞다.
        if not a.strip():
            continue
        if not b.strip():
            continue
        pairs[key] = {'mine': a, 'design': b}

    grades = design_match.grade_all(pairs)

    rows, hits, misses, falses = [], 0, 0, 0
    for key, got in grades.items():
        flagged = got['grade'] in FLAGGED
        should = key in truth
        if should and flagged:
            verdict, hits = 'hit', hits + 1
        elif should and not flagged:
            verdict, misses = 'miss', misses + 1
        elif not should and flagged:
            verdict, falses = 'false', falses + 1
        else:
            verdict = 'ok'
        rows.append({'field': key, 'label': ocr_lab.label_of(key),
                     'grade': got['grade'],
                     'reason': got.get('reason') or '', 'verdict': verdict})

    rows.sort(key=lambda r: {'miss': 0, 'false': 1, 'hit': 2, 'ok': 3}[r['verdict']])
    return {
        'case_id': case.pk,
        'name': case.name,
        'hits': hits, 'misses': misses, 'falses': falses,
        'checked': len(rows),
        'fields': rows,
    }


def run(cases):
    """여러 건을 채점하고 합을 낸다."""
    scored = [g for g in (grade_case(c) for c in cases) if g]
    hits = sum(g['hits'] for g in scored)
    misses = sum(g['misses'] for g in scored)
    falses = sum(g['falses'] for g in scored)
    checked = sum(g['checked'] for g in scored)

    real = hits + misses          # 정말 다른 항목의 수
    same = checked - real         # 같은 항목의 수
    return {
        'cases': scored,
        'usable': len(scored),
        'hits': hits, 'misses': misses, 'falses': falses, 'checked': checked,
        # 놓침률 — 정말 다른 것 중 몇 %를 놓쳤나. **낮을수록 좋다.**
        'miss_rate': round(misses * 100.0 / real, 1) if real else None,
        # 오탐률 — 같은 것 중 몇 %를 다르다고 했나. **낮을수록 좋다.**
        'false_rate': round(falses * 100.0 / same, 1) if same else None,
    }
