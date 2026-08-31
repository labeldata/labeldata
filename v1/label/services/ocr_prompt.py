"""
판독 프롬프트를 DB 에서 고르고, 다음 판의 초안을 만든다.

프롬프트는 지금까지 ocr_service.py 안의 상수 하나였다. 고치려면 배포를 해야
했고, 고치고 나면 이전 것과 견줄 방법이 없었다 — 어느 판이 몇 점이었는지
아무 데도 남지 않는다.

여기서 두 가지를 한다.

  고르기   켜져 있는 판이 있으면 그것을, 없으면 코드에 박힌 기본 프롬프트를
           쓴다. 표가 비어 있어도, DB 조회가 실패해도 판독은 그대로 돈다.
  고치기   측정 결과에서 약한 항목과 실제 교정 이력을 모아, 그 자리를 겨냥한
           지시를 덧붙인 **초안**을 만든다.

**자동으로 만든 초안은 절대 바로 쓰이지 않는다.** active=False 로 저장되고,
사람이 화면에서 내용을 읽고 켜야 쓰인다. 판독 결과는 법적 표시물에 그대로
들어가므로, 아무도 안 본 프롬프트가 조용히 현업에 걸리는 일은 없어야 한다.
"""
import logging

logger = logging.getLogger(__name__)

_CACHE_KEY = 'ocr:active_prompt'
_CACHE_TTL = 60 * 5     # 판을 바꾸면 몇 분 안에 반영된다. 켤 때 바로 지우기도 한다.

# 초안에 넣을 항목 수. 전부 넣으면 지시가 길어져 오히려 묻힌다.
MAX_WEAK_FIELDS = 6
# 항목 하나에 붙일 실제 오독 사례 수.
MAX_EXAMPLES = 3


def base_prompt():
    """코드에 박힌 기본 프롬프트. 어떤 경우에도 이것만은 있다."""
    from v1.label.services.ocr_service import SYSTEM_PROMPT
    return SYSTEM_PROMPT


def active_version():
    """켜져 있는 판. 없거나 조회에 실패하면 None."""
    try:
        from v1.common.models import OcrPromptVersion
        return OcrPromptVersion.objects.filter(active=True).order_by('-created_at').first()
    except Exception:
        logger.exception('활성 프롬프트 조회 실패 — 기본 프롬프트로 계속한다')
        return None


def resolve(version=None, use_cache=True):
    """
    이번 판독에 쓸 프롬프트 본문.

    version 을 주면 그 판을 쓴다(측정에서 판끼리 견줄 때). 안 주면 켜져 있는
    판을, 그것도 없으면 기본 프롬프트를 쓴다.
    """
    if version is not None:
        return version.prompt or base_prompt()

    if use_cache:
        from django.core.cache import cache
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached or base_prompt()

    found = active_version()
    text = (found.prompt if found else '') or ''
    if use_cache:
        from django.core.cache import cache
        cache.set(_CACHE_KEY, text, _CACHE_TTL)
    return text or base_prompt()


def invalidate():
    """판을 켜거나 고쳤을 때 다음 판독부터 반영되게 한다."""
    try:
        from django.core.cache import cache
        cache.delete(_CACHE_KEY)
    except Exception:
        pass


def weak_fields(run_detail, limit=MAX_WEAK_FIELDS):
    """
    측정 결과에서 손봐야 할 항목을 고른다.

    평균이 낮은 것만 고르면 안 된다 — 늘 55점인 항목과 90점과 20점을 오가는
    항목은 전혀 다른 문제이고, 후자가 더 급하다(같은 사진을 매번 다르게 읽는다).
    둘 다 집는다.
    """
    rows = [r for r in (run_detail or {}).get('fields', []) if r.get('runs')]
    if not rows:
        return []

    def urgency(row):
        # 점수가 낮을수록, 편차가 클수록 급하다
        return (100 - row.get('mean', 0)) + row.get('spread', 0) * 0.5

    rows.sort(key=urgency, reverse=True)
    return [r for r in rows[:limit] if r.get('mean', 100) < 90 or r.get('spread', 0) >= 25]


def _field_examples(field, limit=MAX_EXAMPLES):
    """그 항목에서 실제로 어떻게 틀렸는지 (정답지 채점 + 사용자 교정 이력)."""
    from v1.common.models import OcrCorrection

    try:
        rows = (OcrCorrection.objects
                .filter(field=field, corrected=True)
                .exclude(ocr_value='').exclude(final_value='')
                .order_by('-created_at')[:limit * 3])
    except Exception:
        logger.exception('교정 사례 조회 실패 (field=%s)', field)
        return []

    out = []
    for row in rows:
        before = ' '.join(row.ocr_value.split())[:80]
        after = ' '.join(row.final_value.split())[:80]
        if before and after and before != after:
            out.append((before, after))
        if len(out) >= limit:
            break
    return out


def build_revision_brief(run_detail):
    """
    "무엇을 고쳐야 하는가" 를 사람이 읽을 수 있는 문단으로.

    자동 초안을 만들 때 모델에게 주는 재료이면서, 화면에도 그대로 보여 준다 —
    모델이 왜 그렇게 고쳤는지 사람이 판단할 수 있어야 한다.
    """
    weak = weak_fields(run_detail)
    if not weak:
        return '', []

    lines = []
    for row in weak:
        field = row['field']
        head = (f"- {field}: 평균 {row['mean']}점, 최저 {row['worst']}점, "
                f"편차 {row['spread']}점")
        if row.get('spread', 0) >= 25:
            head += ' (같은 사진을 매번 다르게 읽는다)'
        lines.append(head)
        for before, after in _field_examples(field):
            lines.append(f'    판독 "{before}" -> 실제 "{after}"')
    return '\n'.join(lines), weak


_REVISION_INSTRUCTION = """당신은 한국 식품 표시사항 판독 프롬프트를 개선하는 편집자입니다.

아래는 지금 쓰고 있는 프롬프트와, 정답을 적어 둔 사진으로 채점한 결과입니다.
점수가 낮거나 들쭉날쭉한 항목이 무엇이고 어떻게 틀렸는지 함께 드립니다.

이 프롬프트를 고쳐 주세요. 지켜야 할 것:

1. **전문을 그대로 돌려주시오.** 요약하거나 "…(생략)" 으로 줄이지 마시오.
   돌려준 글이 그대로 다음 판독에 쓰입니다.
2. 응답 JSON 스키마(맨 끝의 키 목록)와 응답 규칙은 **한 글자도 바꾸지 마시오.**
   화면과 저장 로직이 그 키를 그대로 읽습니다.
3. 잘 되고 있는 항목의 지시는 건드리지 마시오. 못 하는 항목만 손보시오.
4. 고치는 방향은 **더 자세한 판별 기준**이지 정답 예시가 아닙니다.
   특정 제품의 값을 그대로 적어 넣으면 다른 사진에서 그 값을 지어냅니다.
5. "지어내지 마시오" 계열의 안전 지시는 절대 약하게 만들지 마시오.

아래 JSON 으로만 답하시오.
{"prompt": "고친 프롬프트 전문", "note": "무엇을 왜 바꿨는지 3줄 이내"}
"""


def suggest_revision(run, user=None, model=None):
    """
    측정 결과를 근거로 다음 판의 **초안**을 만든다.

    만들어진 판은 active=False, auto_generated=True 로 저장된다. 사람이 화면에서
    읽고 켜야 쓰인다 — 아무도 안 본 프롬프트가 현업에 걸리면 안 된다.

    Returns: (OcrPromptVersion 또는 None, 사람에게 보여 줄 메시지)
    """
    from django.conf import settings

    from v1.common.models import OcrPromptVersion

    brief, weak = build_revision_brief(run.detail or {})
    if not brief:
        return None, ('고칠 곳을 찾지 못했습니다. 항목마다 점수가 충분히 높거나, '
                      '아직 측정 결과가 없습니다.')

    current = run.prompt_version.prompt if run.prompt_version else base_prompt()
    payload = (
        f'{_REVISION_INSTRUCTION}\n\n'
        f'=== 지금 쓰는 프롬프트 ===\n{current}\n\n'
        f'=== 채점 결과 (평균 {run.mean_score}점, {run.runs}회, '
        f'정답지 {run.case_count}장) ===\n{brief}\n'
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model or getattr(settings, 'OCR_REVISION_MODEL', 'gpt-4o'),
            messages=[{'role': 'user', 'content': payload}],
            max_tokens=8000,
            response_format={'type': 'json_object'},
        )
        import json
        data = json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.exception('프롬프트 초안 생성 실패')
        return None, f'초안을 만들지 못했습니다: {exc}'

    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return None, '초안이 비어 있습니다. 다시 시도해 주세요.'

    # 스키마를 지웠는지 확인한다. 응답 키가 빠지면 화면이 값을 못 읽는다 —
    # 그 판을 켜면 판독이 통째로 조용히 망가진다.
    missing = [key for key in ('prdlst_nm', 'rawmtrl_nm', 'pog_daycnt', 'confidence')
               if f'"{key}"' not in prompt]
    if missing:
        return None, (f'초안이 응답 형식을 훼손했습니다(빠진 키: {", ".join(missing)}). '
                      f'그대로 쓰면 판독 결과를 읽을 수 없어 저장하지 않았습니다.')

    version = OcrPromptVersion.objects.create(
        name=f'자동 초안 {run.created_at:%m-%d %H:%M} (기준 {run.mean_score}점)',
        prompt=prompt,
        note=((data.get('note') or '').strip()
              + f'\n\n[근거] 약한 항목: '
                f'{", ".join(r["field"] for r in weak)}'),
        auto_generated=True,
        active=False,
        based_on=run.prompt_version,
        created_by=user if (user and user.is_authenticated) else None,
    )
    return version, ('초안을 만들었습니다. 내용을 확인하고 정확도를 재 본 뒤에 '
                     '"사용" 으로 켜세요. 켜기 전에는 판독에 쓰이지 않습니다.')
