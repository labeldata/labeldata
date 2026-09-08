"""
부당한 표시·광고 키워드 목록을 한 벌로 모은다.

두 곳에서 온다.

    법정 금지어   `constants.AD_KEYWORDS_BUILTIN` — **코드에 있다**
    사내 기준     `AdKeyword` 테이블 — 회사(계정)마다 다르다

**법정 금지어를 코드에 두는 이유**가 있다. 데이터로만 두면 행이 지워졌을 때
검사가 조용히 죽는다. 검사가 죽어도 화면은 "적합" 이라고 말하므로 아무도
모른다 — 우리가 방금 고친 그 실패 방식이다. 시험도 마이그레이션을 끄고 돌아서
씨앗 데이터가 없다.

**사내 기준을 코드에 두지 않는 이유**도 같은 무게다. 회사마다 기준이 다르고,
법에 없는 말까지 막는 목록이 흔하다("NON-GMO 는 법적으로 가능해도 Risk 가
있어 불가"). 그런 것을 공용 기본으로 깔면 다른 회사에 **틀린 규칙**이 된다.
"""
import logging

from v1.label.constants import AD_KEYWORDS_BUILTIN

logger = logging.getLogger(__name__)

_GRADES = ('RED', 'YELLOW', 'GREEN')


def _split(raw: str) -> list[str]:
    """매칭 문자열을 가운뎃점으로 가른다. 빈 것은 버린다."""
    return [part.strip() for part in (raw or '').split('·') if part.strip()]


def keywords_for(label) -> dict:
    """
    이 라벨에 적용할 키워드를 등급별로 돌려준다.

        {'RED': [{'keyword', 'match', 'note'}, …], 'YELLOW': [...], 'GREEN': [...]}

    사내 기준은 **라벨 주인의 것만** 본다. 공용(owner 가 빈 행)은 모두에게
    적용된다.
    """
    graded = {grade: [] for grade in _GRADES}

    for row in AD_KEYWORDS_BUILTIN:
        grade = row.get('grade')
        if grade in graded:
            graded[grade].append({
                'keyword': row.get('keyword', ''),
                'match': list(row.get('match') or [row.get('keyword', '')]),
                'note': row.get('note', ''),
            })

    owner = getattr(label, 'user_id', None)
    try:
        from django.db.models import Q

        from v1.label.models import AdKeyword

        visible = Q(owner__isnull=True)
        if owner is not None:
            visible |= Q(owner=owner)
        for row in AdKeyword.objects.filter(visible, active_yn=True):
            if row.grade in graded:
                graded[row.grade].append({
                    'keyword': row.keyword,
                    'match': _split(row.match_strings) or [row.keyword],
                    'note': row.note or '',
                })
    except Exception:
        # **조용히 넘기지 않는다.** 사내 기준을 못 읽었다는 것은 그 회사의
        # 검사가 절반만 돌았다는 뜻이다. 다만 법정 금지어까지 버릴 이유는
        # 없으므로 기본 목록은 그대로 돌려준다.
        logger.exception('사내 부당표시 키워드를 읽지 못했다 (owner=%s)', owner)

    # 긴 말을 먼저 본다 — '천연향료' 를 지우기 전에 '천연' 이 걸리면 안 된다.
    for grade in _GRADES:
        for row in graded[grade]:
            row['match'].sort(key=len, reverse=True)
        graded[grade].sort(key=lambda r: max((len(w) for w in r['match']), default=0),
                           reverse=True)
    return graded
