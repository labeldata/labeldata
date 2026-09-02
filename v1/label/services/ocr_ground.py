"""
판독값이 **사진에 실제로 있던 글자인가** — OCR 원문으로 대조한다.

    규칙   모델이 낸 값은 OCR 원문에 있는 문자열이어야 한다
    검증   원문에 (유사) 부분문자열로 있는가? 없으면 지어냈을 가능성이 크다

VLM 은 값을 지어낸다. 전통 OCR 은 글자를 보고 글자를 내므로 지어낼 수가 없다.
그래서 원문을 **정답이 아니라 증인**으로 쓴다.

**값을 고치지 않는다.** confidence 를 내리고 표시만 한다. 이유는 둘이다.

  - OCR 도 틀린다. 원문을 정답으로 삼으면 OCR 의 오독이 그대로 굳는다.
    원문은 강제가 아니라 우선이어야 하고, 둘이 다르면 어느 쪽도 고르지 말고
    **불일치를 짚는** 쪽이 안전하다.
  - 이 결과는 법적 표시물에 들어간다. 조용히 바꾸는 것보다 "여기를 보라" 고
    말하는 편이 낫다.

지금까지 지어냄을 잡는 수단은 원재료명의 등록 정보 대조 하나뿐이었다.
주의사항에는 아무 수단이 없어서 두 칸을 통째로 뺐다(ocr_service.drop_freetext).
원문이 있으면 **모든 칸에 같은 검사**를 걸 수 있고, 그러면 두 칸을 되살릴
근거가 생긴다.

**어디에 꽂느냐가 중요하다.** 판독 결과는 이 순서로 손질된다.

    json.loads -> strip_design_suffix -> drop_freetext -> ocr_snap -> ocr_reconcile
                  제품명 "_후면" 제거    표시 안 함      표준목록 맞춤  등록정보로 채움

가운데 넷은 **원문과 달라지는 것이 정상인** 단계다. 대조를 그 뒤에 놓으면
우리가 일부러 바꾼 값이 전부 "원문에 없음 = 지어냄" 으로 잡힌다. 그래서
`json.loads` 직후, 어떤 변형보다 **앞에서** 돈다.
"""
import logging

logger = logging.getLogger(__name__)

# 이 점수 아래면 "원문에서 못 찾았다" 로 본다.
#
# 정답지 측정에서 실제 값들은 98~99.5 점이 나왔다(OCR_UPGRADE_PLAN.md §13
# 1단계). 진짜 값이 80 아래로 떨어지는 일은 드물다는 뜻이라, 그 아래를
# 의심스럽다고 부르면 헛경보가 적다.
#
# 재현율만 재고 정밀도는 아직 안 쟀다. 그래서 문턱을 넉넉히 잡는다 - 지금
# 목적은 지어냄을 남김없이 잡는 것이 아니라 **틀림없는 것만 짚는** 것이다.
GROUND_THRESHOLD = 80

# 대조하지 않는 칸.
#
#   recycling_mark  도형이다. 글자로 찾을 수 없다
#   nutrition_basis "총 내용량 87 g" 처럼 우리가 표기를 다듬어 넣는다
#
# 영양성분 수치는 대조한다 - 표에 숫자로 찍혀 있으므로 원문에 있어야 맞다.
SKIP_FIELDS = ('recycling_mark', 'nutrition_basis')

# 확신도를 내릴 때 쓰는 값. 원래 등급이 무엇이든 여기로 내린다.
LOWERED = 'low'


def _value_of(item):
    """{'value': ..., 'confidence': ...} 또는 값 그대로에서 값만 꺼낸다."""
    if isinstance(item, dict):
        return item.get('value')
    return item


def ground(data: dict, text: str) -> tuple[dict, dict]:
    """
    판독 결과의 각 값을 원문과 대조한다.

    Returns: (표시가 붙은 결과, 요약)

      결과   값이 원문에서 안 나온 항목에 grounded=False, ground_score,
             ground_note 가 붙고 confidence 가 low 로 내려간다.
             **값 자체는 그대로다.**
      요약   {'checked': n, 'ungrounded': [항목...], 'scores': {항목: 점수}}

    원문이 없으면 아무것도 하지 않는다. 원문은 곁들이는 것이지 있어야 하는
    것이 아니다 - 없다고 판독 결과가 달라지면 안 된다.
    """
    if not text or not isinstance(data, dict):
        return data, {'checked': 0, 'ungrounded': [], 'scores': {}}

    from v1.label.services.ocr_text import ASSEMBLED_FIELDS, match_score

    result = dict(data)
    scores, ungrounded = {}, []

    for field, item in data.items():
        if field in SKIP_FIELDS:
            continue
        value = _value_of(item)
        if not str(value or '').strip():
            continue   # 안 읽은 항목이다. 지어낸 것이 아니다

        try:
            # 측정(ocr_text.field_recall)과 **같은 규칙**으로 센다. 두 곳이
            # 갈라지면 "측정에서는 괜찮았는데 실제로는 경고가 뜬다" 가 된다.
            score = match_score(value, text, assembled=field in ASSEMBLED_FIELDS)
        except Exception:
            logger.exception('[판독 대조] 점수를 못 냈다 (항목=%s)', field)
            continue

        scores[field] = score
        if score >= GROUND_THRESHOLD:
            continue

        ungrounded.append(field)
        marked = dict(item) if isinstance(item, dict) else {'value': value}
        marked['grounded'] = False
        marked['ground_score'] = score
        marked['ground_note'] = ('사진의 글자에서 이 값을 찾지 못했습니다. '
                                 '지어낸 값일 수 있으니 사진과 견주어 확인하세요.')
        marked['confidence'] = LOWERED
        result[field] = marked

    if ungrounded:
        logger.info('[판독 대조] 원문에서 못 찾은 항목 %s개: %s',
                    len(ungrounded), ', '.join(ungrounded))

    return result, {'checked': len(scores), 'ungrounded': ungrounded, 'scores': scores}


def summary_text(report: dict) -> str:
    """확인 창에 한 줄로 띄울 말. 짚을 게 없으면 빈 문자열."""
    ungrounded = (report or {}).get('ungrounded') or []
    if not ungrounded:
        return ''
    return (f'{len(ungrounded)}개 항목을 사진의 글자에서 찾지 못했습니다 '
            f'({", ".join(ungrounded)}). 사진과 견주어 확인하세요.')
