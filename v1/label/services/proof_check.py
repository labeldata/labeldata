# -*- coding: utf-8 -*-
"""
시안에서 읽은 값 **그 자체**를 규정에 대고 본다.

지금까지 규정 검증(validate_label)은 DB 에 저장된 라벨만 봤다. 시안은 읽어
놓고도 "내 값과 같은가"(design_match) 만 물었다. 그래서 **시안에만 있는
위반은 아무도 안 봤다** — 특히 금지문구는 일괄표시면이 아니라 앞면 카피에
있고("천연", "무첨가", "면역력"), 라벨에는 앞면 카피를 담는 칸이 없다.
판독기는 그 글을 extra_texts 로 모아 오는데, 금지문구 표를 아는 엔진은 그
글자를 한 번도 못 봤다.

어떻게 하나
───────────
검사 29개는 전부 `getattr(label, 칸)` 으로 값을 읽는다. 그래서 **시안 값을
입힌 라벨 사본**을 만들어 넣으면 29개가 그대로 돈다. 검사를 새로 쓰지 않는다.

  - 시안이 담을 수 있는 칸은 **먼저 비운다.** DB 값을 물려받으면 "시안에
    없는데 DB 에 있어서" 통과하는 일이 생긴다. 시안을 보는 검사에서는 시안에
    없는 것은 없는 것이다.
  - pk 는 그대로 둔다. 배합표·문서함을 보는 검사가 함께 돈다(시안의 원재료
    순서가 배합비와 맞는가 같은 것). 제품이 없는 라벨(pk 없음)로도 돈다 —
    실측했다: 29개 가운데 문서함 검사 하나만 터졌고 그것은 pk 빗장으로 막았다.
  - **절대 저장하지 않는다.** save 를 막아 둔다(시험이 지킨다).

"읽지 못함" 과 "위반" 은 다른 말이다
──────────────────────────────────
required_missing("품목보고번호가 비어 있습니다")은 시안 검사에서 뜻이 갈린다 —
시안에 그 표시가 정말 없는지, 판독이 놓쳤는지 **판독기도 모른다**(둘 다
confidence none). 위반으로 세면 사진이 조금 흐린 날 "위반 12건" 이 뜨고 그
다음부터 아무도 이 기능을 안 쓴다. 따로 적어 사람이 사진에서 확인하게 한다.
"""
import copy
import logging

from v1.label.services.validation_service import (
    forbidden_issue,
    scan_forbidden,
    validate_label,
)

logger = logging.getLogger(__name__)

# 시안에서 읽어 라벨에 입힐 수 있는 칸. 판독 프롬프트(ocr_service.SYSTEM_PROMPT)
# 의 키와 같다. recycling_mark·nutrition_basis 는 라벨에 칸이 없어 뺀다 —
# 앞엣것은 미리보기 설정(prv_recycling_mark_text)으로, 뒤엣것은 100 g 환산에만
# 쓰고 저장하지 않는다.
PROOF_FIELDS = (
    'prdlst_nm', 'prdlst_dcnm', 'content_weight', 'weight_calorie',
    'prdlst_report_no', 'country_of_origin', 'bssh_nm', 'distributor_address',
    'repacker_address', 'importer_address', 'storage_method',
    'rawmtrl_nm', 'rawmtrl_nm_display', 'allergens', 'ingredient_info',
    'frmlc_mtrqlt', 'pog_daycnt', 'cautions', 'additional_info',
    'calories', 'natriums', 'carbohydrates', 'sugars', 'fats', 'trans_fats',
    'saturated_fats', 'cholesterols', 'proteins',
)

# 시안의 그 밖 문구를 지적에 적을 때 이만큼만 — 앞면 카피는 길다
_TEXT_SHOWN = 40


def _never_save(*args, **kwargs):
    raise RuntimeError('시안 라벨은 저장하지 않는다 — 검사용 사본이다')


def split_reading(data):
    """
    판독 결과를 세 갈래로 가른다 → (values, confidence, extra_texts).

    판독기는 칸마다 {value, confidence} 를 준다. 평평한 {칸: 값} 도 받는다 —
    시험과 재검증(저장해 둔 값으로 다시 보기)이 그렇게 부른다.
    confidence 가 none 이거나 값이 비면 **읽지 못한 칸**이다.
    """
    values, confidence, extras = {}, {}, []
    if not isinstance(data, dict):
        return values, confidence, extras

    for key, item in data.items():
        if key == 'extra_texts':
            if isinstance(item, (list, tuple)):
                seen = set()
                for text in item:
                    text = str(text or '').strip()
                    if text and text not in seen:
                        seen.add(text)
                        extras.append(text)
            continue
        if key not in PROOF_FIELDS:
            continue
        if isinstance(item, dict):
            value, conf = item.get('value'), (item.get('confidence') or '')
        else:
            value, conf = item, ('high' if item else 'none')
        text = '' if value is None else str(value).strip()
        if conf == 'none' or not text:
            confidence[key] = 'none'
            continue
        values[key] = text
        confidence[key] = str(conf)
    return values, confidence, extras


def proof_label(base, values):
    """
    시안 값을 입힌 라벨 사본. base 는 저장된 라벨이어도, 아직 저장하지 않은
    `MyLabel(user_id=…)` 이어도 된다.

    `copy.copy` 는 Django 모델의 __reduce__ 를 타서 `_state` 까지 새로 만든다 —
    얕은 복사가 아니다(실측했다). 원본은 어떤 경우에도 바뀌지 않는다.
    """
    proof = copy.copy(base)
    for field in PROOF_FIELDS:
        setattr(proof, field, '')
    for key, value in values.items():
        setattr(proof, key, value)
    # 검사들은 **인쇄될** 원재료명(rawmtrl_nm_display)을 먼저 본다. 시안에
    # 적힌 것이 곧 인쇄될 것이다.
    if values.get('rawmtrl_nm') and not values.get('rawmtrl_nm_display'):
        proof.rawmtrl_nm_display = values['rawmtrl_nm']
    proof.save = _never_save
    return proof


def _extra_text_issues(proof, extras):
    """앞면 카피 같은 '칸 밖의 글' 을 금지문구 표에 대고 본다."""
    if not extras:
        return []
    from v1.label.services.ad_keywords import keywords_for

    graded = keywords_for(proof)       # 사내 기준은 라벨 주인의 것을 본다
    issues = []
    for text in extras:
        shown = text if len(text) <= _TEXT_SHOWN else text[:_TEXT_SHOWN] + '…'
        for grade, hit, row in scan_forbidden(graded, text):
            issue = forbidden_issue(grade, hit, row, f'시안의 문구 "{shown}"',
                                    fields=(), source='extra_texts')
            issue['text'] = text
            issues.append(issue)
    return issues


def check_proof(base, data):
    """
    시안 판독 결과(data)를 규정에 대고 본 결과.

        ok           확정을 막는 지적이 없는가 (validate_label 과 같은 뜻)
        issues       규정에 어긋난 것. 각각 source='proof' | 'extra_texts'
        unread       시안에서 읽지 못한 필수 항목 — 위반이 아니다. 사람이 사진에서 본다
        unchecked    검사가 보지 못한 것 (배합비·영양성분·문서가 있어야 보는 것들)
        read_fields  값이 들어온 칸
        extra_texts  칸 밖의 글
    """
    values, confidence, extras = split_reading(data)
    proof = proof_label(base, values)
    result = validate_label(proof)

    issues, unread = [], []
    for issue in result['issues']:
        if issue.get('category') == 'required_missing':
            for field, name in zip(issue.get('fields') or (),
                                   issue.get('field_labels') or ()):
                unread.append({'field': field, 'label': name})
            continue
        issues.append({**issue, 'source': 'proof'})

    issues.extend(_extra_text_issues(proof, extras))

    return {
        'ok': not issues,
        'issue_count': len(issues),
        'issues': issues,
        'unread': unread,
        'unchecked': result['unchecked'],
        'read_fields': sorted(values),
        'extra_texts': extras,
    }


def note_for_record(data, checks, user=None, when=None):
    """
    문서함(포장지 시안)에 붙여 둘 만큼만 추린다 — 다시 볼 수 있을 만큼은 남기고,
    화면 HTML 은 남기지 않는다.

    **값을 남기는 것이 핵심이다.** 규칙을 고친 뒤 옛 시안을 다시 보려면 값만
    있으면 된다 — 사진을 다시 읽지 않는다(시간당 판독 한도, 비용).
    """
    from v1.label.services.ai_validation_service import name_issues

    values, _confidence, extras = split_reading(data)
    checks = checks or {}
    # 무엇이 걸렸는지 **이름으로** 남긴다. 목록 화면은 개수만 적고 이름은 곁말에
    # 쓴다 — 그러면 줄을 펼치지 않고도 "금지 문구, 원재료명 괄호" 를 알 수 있다.
    named = name_issues(checks.get('issues') or [])
    labels = []
    for row in named:
        label = row.get('label') or row.get('category') or ''
        if label and label not in labels:
            labels.append(label)
    return {
        'issue_labels': labels,
        'checked_at': when.isoformat(timespec='seconds') if when else None,
        'checked_by': user.get_username() if user else '',
        'values': values,
        'extra_texts': extras[:40],
        'issue_count': int(checks.get('issue_count') or 0),
        'issues': [{k: i.get(k) for k in ('category', 'label', 'message', 'advisory', 'source')}
                   for i in named[:40]],
        'unread': [u.get('label') or u.get('field') for u in (checks.get('unread') or [])],
        'unchecked_count': len(checks.get('unchecked') or []),
    }
