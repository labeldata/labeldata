"""
판독 고도화 화면 (관리자 전용).

사진 판독은 지금까지 "이번엔 잘 읽네" 라는 인상으로만 굴러갔다. 프롬프트를
고쳐도 나아졌는지 알 수 없었고, 모델을 바꿔 볼 근거도 없었다. 재는 자
(management/commands/ocr_benchmark.py)는 만들어 뒀지만 서버에 파일을 올릴 수
있는 사람만 쓸 수 있었다.

이 화면이 그 고리를 닫는다.

    정답지를 쌓는다 -> 잰다 -> 약한 곳을 본다 -> 프롬프트를 고친다 -> 다시 잰다

정답은 세 곳에서 온다. 손으로 적거나, 판독 초안을 고치거나, **사람이 검증하고
판정까지 낸 표시사항에서 그대로 가져온다.** 마지막 것이 가장 믿을 만하다 —
판독값이 아니라 실제로 인쇄에 쓰인 값이고, 검토·승인을 거치며 여러 번 본 값이다.

**자동으로 만든 프롬프트는 절대 바로 쓰이지 않는다.** 초안으로 저장되고, 사람이
내용을 읽고 켜야 판독에 쓰인다. 판독 결과는 법적 표시물에 그대로 들어간다.
"""
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

# 한 번에 부를 수 있는 판독 횟수의 상한.
#
# 재기는 사진 한 장에 5~15초 걸린다. 정답지 열 장을 다섯 번 돌리면 오십 번,
# 십 분이 넘는데 웹 요청이 그 전에 끊긴다(PythonAnywhere 는 5분). 끊기면 돈만
# 쓰고 결과가 안 남는다. 열두 번이면 최악에도 3분 안쪽이다.
# 상한을 두고 "나눠 돌리세요" 라고 말하는 편이 낫다.
MAX_CALLS_PER_RUN = 12


def _json_body(request):
    try:
        return json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return {}


@staff_member_required
@require_GET
def ocr_lab(request):
    """판독 고도화 화면."""
    from django.conf import settings

    from v1.common.models import OcrBenchmarkRun, OcrCorrection, OcrPromptVersion, OcrTruthCase
    from v1.label.services.ocr_learning import accuracy_stats

    cases = list(OcrTruthCase.objects.all()[:100])
    prompts = list(OcrPromptVersion.objects.all()[:50])
    runs = list(OcrBenchmarkRun.objects.select_related('prompt_version')[:20])

    # 실제 사용에서의 정답률. 정답지 채점과는 다른 각도다 — 정답지는 우리가 고른
    # 사진이고, 이쪽은 사용자가 실제로 올린 사진이다. 둘 다 봐야 한다.
    live = {
        'field': accuracy_stats(group='field'),
        'source': accuracy_stats(group='source'),
        'variant': accuracy_stats(group='variant'),
        'model': accuracy_stats(group='model'),
    }
    totals = OcrCorrection.objects.aggregate(
        total=Count('id'), wrong=Count('id', filter=Q(corrected=True)))
    total, wrong = totals['total'] or 0, totals['wrong'] or 0

    return render(request, 'label/ocr_lab.html', {
        'cases': cases,
        'prompts': prompts,
        'runs': runs,
        'live': live,
        'live_total': total,
        'live_rate': round((total - wrong) / total * 100, 1) if total else None,
        'current_model': getattr(settings, 'OCR_MODEL', 'gpt-4o-mini'),
        'verified_count': sum(1 for c in cases if c.verified),
        'max_calls': MAX_CALLS_PER_RUN,
    })


# ── 정답지 ──────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def truth_create(request):
    """
    사진을 올려 정답지를 만든다.

    draft=1 이면 바로 읽어 초안을 채운다. **초안은 판독 결과다** — 그대로 두고
    채점하면 자기 답을 자기가 채점하는 꼴이라, verified 는 켜지 않는다.
    """
    from v1.common.models import OcrTruthCase
    from v1.label.services.ocr_lab import draft_expected

    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'success': False, 'error': '사진을 올려주세요.'}, status=400)
    if image.size > 10 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': '사진은 10MB 이하여야 합니다.'},
                            status=400)

    name = (request.POST.get('name') or '').strip() or image.name
    case = OcrTruthCase.objects.create(
        name=name[:120],
        image=image,
        report_no=(request.POST.get('report_no') or '').strip()[:32],
        expected={},
        source=OcrTruthCase.Source.MANUAL,
        created_by=request.user,
    )

    warning = ''
    if request.POST.get('draft') == '1':
        case.image.open('rb')
        try:
            expected, error = draft_expected(case.image)
        finally:
            case.image.close()
        if expected:
            case.expected = {k: v for k, v in expected.items() if str(v or '').strip()}
            case.source = OcrTruthCase.Source.DRAFT
            case.save(update_fields=['expected', 'source'])
            warning = ('판독 결과로 초안을 채웠습니다. **이대로 두면 자기 답을 자기가 '
                       '채점하는 꼴입니다.** 사진을 보며 틀린 값을 고친 뒤 "정답 확인" 을 '
                       '켜 주세요.')
        else:
            warning = f'초안을 만들지 못했습니다: {error}'

    return JsonResponse({'success': True, 'case': _case_json(case), 'warning': warning})


@staff_member_required
@require_POST
def truth_from_label(request):
    """
    사람이 검증하고 판정까지 낸 표시사항을 정답으로 가져온다.

    사진은 따로 받는다 — 표시사항에는 값만 있고 그 값이 찍힌 사진이 없다.
    값은 손으로 옮기지 않는다. 옮겨 적다 틀리면 정답지가 틀린다.
    """
    from v1.common.models import OcrTruthCase
    from v1.label.models import MyLabel
    from v1.label.services.ocr_lab import expected_from_label

    label_id = (request.POST.get('label_id') or '').strip()
    image = request.FILES.get('image')
    if not label_id or not image:
        return JsonResponse(
            {'success': False, 'error': '표시사항 번호와 사진이 모두 필요합니다.'},
            status=400)

    label = get_object_or_404(MyLabel, pk=label_id)
    expected = expected_from_label(label)
    if not expected:
        return JsonResponse(
            {'success': False,
             'error': '그 표시사항에는 채워진 항목이 없어 정답으로 쓸 수 없습니다.'},
            status=400)

    case = OcrTruthCase.objects.create(
        name=(label.my_label_name or label.prdlst_nm or f'표시사항 {label.pk}')[:120],
        image=image,
        report_no=(label.prdlst_report_no or '')[:32],
        expected=expected,
        source=OcrTruthCase.Source.LABEL,
        # 검토·승인을 거친 값이라 사람이 이미 여러 번 봤다. 다만 **사진과 그
        # 표시사항이 같은 제품인지**는 아무도 확인하지 않았으므로 켜 두지 않는다.
        verified=False,
        note=f'표시사항 #{label.pk} 에서 가져옴',
        created_by=request.user,
    )
    return JsonResponse({
        'success': True, 'case': _case_json(case),
        'warning': ('표시사항의 값을 그대로 가져왔습니다. 올린 사진이 그 제품의 '
                    '표시사항이 맞는지 확인한 뒤 "정답 확인" 을 켜 주세요.'),
    })


@staff_member_required
@require_GET
def truth_detail(request, case_id):
    """정답 전문. 목록에는 값까지 실지 않는다 - 원재료명 한 줄이 300자를 넘는다."""
    from v1.common.models import OcrTruthCase

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    return JsonResponse({'success': True, 'case': _case_json(case)})


@staff_member_required
@require_POST
def truth_update(request, case_id):
    """정답·영역·확인 여부를 고친다."""
    from v1.common.models import OcrTruthCase

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    payload = _json_body(request)

    if 'expected' in payload:
        expected = payload['expected']
        if not isinstance(expected, dict):
            return JsonResponse({'success': False, 'error': '정답 형식이 잘못됐습니다.'},
                                status=400)
        case.expected = {k: str(v or '').strip()
                         for k, v in expected.items() if str(v or '').strip()}
    if 'name' in payload:
        case.name = (payload['name'] or '').strip()[:120] or case.name
    if 'report_no' in payload:
        case.report_no = (payload['report_no'] or '').strip()[:32]
    if 'note' in payload:
        case.note = payload['note'] or ''
    if 'crop_box' in payload:
        box = payload['crop_box']
        try:
            case.crop_box = [int(v) for v in box][:4] if box else None
        except (TypeError, ValueError):
            return JsonResponse({'success': False,
                                 'error': '읽을 영역은 숫자 네 개여야 합니다.'}, status=400)
    if 'expected_boxes' in payload:
        boxes = payload['expected_boxes']
        if not isinstance(boxes, dict):
            return JsonResponse({'success': False, 'error': '정답 위치 형식이 잘못됐습니다.'},
                                status=400)
        # 위치는 값과 따로 둔다. 빈 상자·형식이 깨진 상자는 버린다 - 반쯤 적힌
        # 위치를 채점에 쓰면 "위치를 못 찾았다" 와 "위치를 안 적었다" 가 섞인다.
        from v1.label.services.ocr_boxes import clamp_free
        cleaned = {}
        for key, box in boxes.items():
            fixed = clamp_free(box)
            if fixed:
                cleaned[key] = fixed
        case.expected_boxes = cleaned
    if 'verified' in payload:
        if payload['verified'] and not case.expected:
            return JsonResponse(
                {'success': False, 'error': '정답이 비어 있어 확인 처리를 할 수 없습니다.'},
                status=400)
        case.verified = bool(payload['verified'])

    case.save()
    return JsonResponse({'success': True, 'case': _case_json(case)})


@staff_member_required
@require_POST
def truth_ocr_text(request, case_id):
    """
    이 정답지 사진의 **글자 원문**을 뽑고, 정답을 얼마나 담고 있는지 잰다.

    판독이 아니다. 어느 글자가 어느 항목인지는 보지 않는다 - 사진에 적힌 글자를
    그대로 받아 와서, 정답지의 값들이 그 안에 실제로 있는지만 센다.

    이게 OCR 원문 도입의 1단계이고 **여기서 가부가 갈린다.** 우리 라벨(6pt 원형
    스티커, 곡면 용기)을 OCR 이 못 읽으면 그 다음이 전부 무의미하다.
    자세한 것은 services/ocr_text.py 와 OCR_UPGRADE_PLAN.md §13.

    한 번 읽은 원문은 정답지에 붙어 있어 다시 부르지 않는다. 다시 읽히려면
    refresh 를 준다.
    """
    from v1.common.models import OcrTruthCase
    from v1.label.services.ocr_text import measure_case

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    payload = _json_body(request)

    try:
        result = measure_case(case, refresh=bool(payload.get('refresh')))
    except Exception as exc:
        logger.exception('[OCR 원문] 측정 실패 (case=%s)', case_id)
        return JsonResponse({'success': False,
                             'error': f'원문을 뽑지 못했습니다: {exc}'}, status=500)

    if not result['chars']:
        return JsonResponse({
            'success': False,
            'error': ('원문이 비었습니다. 서비스 계정 설정'
                      '(GOOGLE_VISION_SERVICE_ACCOUNT_JSON)이나 사진을 확인하세요 — '
                      '자세한 이유는 서버 로그에 있습니다.'),
        }, status=502)

    return JsonResponse({'success': True, 'result': result})


@staff_member_required
@require_POST
def truth_delete(request, case_id):
    from v1.common.models import OcrTruthCase

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    case.delete()
    return JsonResponse({'success': True})


def _image_size(case):
    """
    사진의 원본 크기. 화면이 상자를 그리려면 이게 있어야 한다.

    화면에서는 사진이 줄어들어 보이므로, 원본 픽셀 좌표를 화면 좌표로 옮기려면
    원본이 몇 픽셀인지 알아야 한다. 못 읽으면 (0, 0) 이고 화면은 상자 기능을
    끈다 - 어림한 크기로 그리면 상자가 엉뚱한 데 얹힌다.
    """
    try:
        return [case.image.width, case.image.height]
    except Exception:
        logger.exception('정답지 사진 크기를 읽지 못했다 (case=%s)', case.pk)
        return [0, 0]


def _case_json(case):
    return {
        'id': case.pk,
        'name': case.name,
        'image_url': case.image.url if case.image else '',
        'image_size': _image_size(case),
        'report_no': case.report_no,
        'crop_box': case.crop_box,
        'expected': case.expected or {},
        'expected_boxes': case.expected_boxes or {},
        'source': case.get_source_display(),
        'verified': case.verified,
        'note': case.note,
        'field_count': case.field_count,
    }


# ── 측정 ────────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def run_benchmark(request):
    """
    고른 정답지로 정확도를 잰다.

    **확인된 정답지만 쓴다.** 판독 초안을 그대로 둔 정답지로 채점하면 자기 답을
    자기가 채점하는 꼴이라, 점수가 높게 나오고 그 숫자가 아무 뜻도 없다.
    """
    from v1.common.models import OcrPromptVersion, OcrTruthCase
    from v1.label.services.ocr_lab import run_benchmark as run_it
    from v1.label.services.ocr_service import TILE_LAYOUTS

    payload = _json_body(request)
    case_ids = payload.get('case_ids') or []
    runs = max(1, min(int(payload.get('runs') or 1), 10))

    cases = list(OcrTruthCase.objects.filter(pk__in=case_ids, verified=True)
                 if case_ids else
                 OcrTruthCase.objects.filter(verified=True))
    if not cases:
        return JsonResponse({
            'success': False,
            'error': ('정답 확인된 정답지가 없습니다. 정답지를 열어 값을 확인하고 '
                      '"정답 확인" 을 켜 주세요 — 확인 전 초안으로 채점하면 자기 답을 '
                      '자기가 채점하는 꼴이 됩니다.'),
        }, status=400)

    calls = len(cases) * runs
    if calls > MAX_CALLS_PER_RUN:
        return JsonResponse({
            'success': False,
            'error': (f'한 번에 {calls}번을 읽게 됩니다(정답지 {len(cases)}장 x {runs}회). '
                      f'{MAX_CALLS_PER_RUN}번을 넘으면 웹 요청이 먼저 끊겨 결과가 남지 '
                      f'않습니다. 정답지를 나눠 고르거나 회차를 줄여 주세요.'),
        }, status=400)

    version = None
    if payload.get('prompt_version_id'):
        version = OcrPromptVersion.objects.filter(pk=payload['prompt_version_id']).first()

    try:
        run = run_it(
            cases,
            runs=runs,
            model=(payload.get('model') or '').strip() or None,
            prompt_version=version,
            use_crop=bool(payload.get('use_crop')),
            use_api=bool(payload.get('use_api')),
            use_hints=payload.get('use_hints', True),
            use_boxes=bool(payload.get('use_boxes')),
            layout=(payload.get('layout') if payload.get('layout') in TILE_LAYOUTS
                    else 'grid'),
            read_freetext=bool(payload.get('read_freetext')),
            # 판독값을 사진의 글자 원문과 대조할 것인가. 켜면 판독 한 번에
            # Vision 호출이 하나 더 붙는다 - 여기서 앞뒤를 재 보고 켠다.
            use_ground=bool(payload.get('use_ground')),
            user=request.user,
        )
    except Exception as exc:
        logger.exception('정확도 측정 실패')
        return JsonResponse({'success': False, 'error': f'측정 중 오류: {exc}'}, status=500)

    return JsonResponse({'success': True, 'run': _run_json(run)})


@staff_member_required
@require_GET
def run_detail(request, run_id):
    from v1.common.models import OcrBenchmarkRun

    run = get_object_or_404(OcrBenchmarkRun, pk=run_id)
    return JsonResponse({'success': True, 'run': _run_json(run, full=True)})


def _run_json(run, full=False):
    out = {
        'id': run.pk,
        'created_at': run.created_at.strftime('%Y-%m-%d %H:%M'),
        'model': run.model,
        'variant': '영역 선택' if run.variant == 'crop' else '사진 전체',
        'use_api': run.use_api,
        'case_count': run.case_count,
        'runs': run.runs,
        'mean_score': run.mean_score,
        'prompt': run.prompt_version.name if run.prompt_version else '기본 프롬프트',
        'prompt_version_id': run.prompt_version_id,
        'fields': (run.detail or {}).get('fields', []),
        'api_mean': (run.detail or {}).get('api_mean'),
        'box_mean': (run.detail or {}).get('box_mean'),
        'tiling': (run.detail or {}).get('tiling') or 'grid',
        'runs_asked': (run.detail or {}).get('runs_asked') or run.runs,
        'read_freetext': (run.detail or {}).get('read_freetext', False),
        'ground': (run.detail or {}).get('ground', False),
    }
    if full:
        out['cases'] = (run.detail or {}).get('cases', [])
    return out


# ── 프롬프트 판 ─────────────────────────────────────────────────────────────

@staff_member_required
@require_GET
def prompt_detail(request, version_id=0):
    """
    판 하나의 전문. version_id 가 0 이면 코드에 박힌 기본 프롬프트를 보여 준다 —
    새 판을 만들 때 그것을 바탕으로 고치게 하기 위해서다.
    """
    from v1.common.models import OcrPromptVersion
    from v1.label.services.ocr_prompt import base_prompt

    if not version_id:
        return JsonResponse({'success': True, 'version': {
            'id': 0, 'name': '기본 프롬프트 (코드)', 'prompt': base_prompt(),
            'note': '배포된 코드에 들어 있는 프롬프트입니다. 켜져 있는 판이 없으면 이것을 씁니다.',
            'active': False, 'auto_generated': False, 'read_only': True,
        }})

    version = get_object_or_404(OcrPromptVersion, pk=version_id)
    return JsonResponse({'success': True, 'version': _prompt_json(version, full=True)})


@staff_member_required
@require_POST
def prompt_save(request):
    """새 판을 만들거나 기존 판의 내용을 고친다. 켜는 것은 따로 한다."""
    from v1.common.models import OcrPromptVersion
    from v1.label.services.ocr_prompt import invalidate

    payload = _json_body(request)
    prompt = (payload.get('prompt') or '').strip()
    if not prompt:
        return JsonResponse({'success': False, 'error': '프롬프트가 비어 있습니다.'},
                            status=400)

    # 응답 스키마를 지우면 판독 결과를 아무도 못 읽는다. 켠 뒤에야 알게 되면
    # 그 사이의 판독이 전부 헛돈다.
    missing = [key for key in ('prdlst_nm', 'rawmtrl_nm', 'pog_daycnt', 'confidence')
               if f'"{key}"' not in prompt]
    if missing:
        return JsonResponse({
            'success': False,
            'error': (f'응답 형식이 빠졌습니다: {", ".join(missing)}. '
                      f'이 키가 없으면 판독 결과를 화면이 읽지 못합니다.'),
        }, status=400)

    version_id = payload.get('id')
    if version_id:
        version = get_object_or_404(OcrPromptVersion, pk=version_id)
        version.prompt = prompt
        version.name = (payload.get('name') or version.name).strip()[:80]
        version.note = payload.get('note', version.note) or ''
        version.save(update_fields=['prompt', 'name', 'note'])
        if version.active:
            invalidate()
    else:
        version = OcrPromptVersion.objects.create(
            name=(payload.get('name') or '새 판').strip()[:80],
            prompt=prompt,
            note=payload.get('note') or '',
            created_by=request.user,
        )
    return JsonResponse({'success': True, 'version': _prompt_json(version)})


@staff_member_required
@require_POST
def prompt_activate(request, version_id):
    """이 판을 켠다. 켜져 있는 판은 언제나 하나뿐이다."""
    from v1.common.models import OcrPromptVersion
    from v1.label.services.ocr_prompt import invalidate

    version = get_object_or_404(OcrPromptVersion, pk=version_id)
    version.activate()
    invalidate()
    return JsonResponse({
        'success': True,
        'message': f'"{version.name}" 을(를) 켰습니다. 다음 판독부터 이 프롬프트를 씁니다.',
    })


@staff_member_required
@require_POST
def prompt_deactivate(request):
    """전부 끄고 코드의 기본 프롬프트로 돌아간다 (되돌리는 길)."""
    from v1.common.models import OcrPromptVersion
    from v1.label.services.ocr_prompt import invalidate

    OcrPromptVersion.objects.filter(active=True).update(active=False)
    invalidate()
    return JsonResponse({'success': True,
                         'message': '기본 프롬프트로 돌아갔습니다.'})


@staff_member_required
@require_POST
def prompt_suggest(request, run_id):
    """
    측정 결과를 근거로 다음 판의 **초안**을 만든다.

    만들어진 판은 꺼진 채로 저장된다. 사람이 내용을 읽고 재 본 뒤 켜야 쓰인다.
    """
    from v1.common.models import OcrBenchmarkRun
    from v1.label.services.ocr_prompt import suggest_revision

    run = get_object_or_404(OcrBenchmarkRun, pk=run_id)
    version, message = suggest_revision(run, user=request.user)
    if version is None:
        return JsonResponse({'success': False, 'error': message}, status=400)
    return JsonResponse({'success': True, 'version': _prompt_json(version),
                         'message': message})


@staff_member_required
@require_GET
def revision_brief(request, run_id):
    """무엇을 고쳐야 하는지 — 자동 초안에 넘기는 재료를 사람도 그대로 본다."""
    from v1.common.models import OcrBenchmarkRun
    from v1.label.services.ocr_prompt import build_revision_brief

    run = get_object_or_404(OcrBenchmarkRun, pk=run_id)
    brief, weak = build_revision_brief(run.detail or {})
    return JsonResponse({'success': True, 'brief': brief,
                         'weak': [r['field'] for r in weak]})


def _prompt_json(version, full=False):
    out = {
        'id': version.pk,
        'name': version.name,
        'note': version.note,
        'active': version.active,
        'auto_generated': version.auto_generated,
        'last_score': version.last_score,
        'created_at': version.created_at.strftime('%Y-%m-%d %H:%M'),
    }
    if full:
        out['prompt'] = version.prompt
    return out


# ── 읽은 자리 ────────────────────────────────────────────────────────────────
#
# 여기가 관리자 화면에만 있는 이유.
#
# 좌표가 맞는지 재려면 **정답이 필요하고, 정답은 여기에만 있다.** 맞는지도
# 모르는 상자를 사용자 확인 창에 먼저 띄우면, 맞는 값에 틀린 상자가 붙는
# 순간 사용자가 멀쩡한 값을 의심해 지운다. 지금 없는 불신을 만드는 것이다.
#
# 그래서 순서가 이렇다.
#   1. 여기서 상자를 받아 본다        (locate)
#   2. 사람이 자리를 고친다            (save 의 expected_boxes)
#   3. 고친 자리만 다시 읽혀 본다      (reread)
#   4. 다음 측정부터 위치도 채점된다   (run 의 use_boxes)
# 이 넷이 돌고 나서야 사용자 화면 이야기를 할 수 있다.

@staff_member_required
@require_POST
def truth_locate(request, case_id):
    """
    정답지 사진을 한 번 읽어 **값과 읽은 자리**를 함께 가져온다.

    판독을 한 번 더 부르므로 돈이 든다. 그래서 화면이 자동으로 부르지 않고
    사람이 누를 때만 돈다.
    """
    from v1.common.models import OcrPromptVersion, OcrTruthCase
    from v1.label.services.ocr_lab import locate_case

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    payload = _json_body(request)

    version = None
    if payload.get('prompt_version_id'):
        version = OcrPromptVersion.objects.filter(
            pk=payload['prompt_version_id']).first()

    out = locate_case(
        case,
        model=(payload.get('model') or '').strip() or None,
        prompt_version=version,
        use_hints=payload.get('use_hints', True),
    )
    if out['error']:
        return JsonResponse({'success': False, 'error': out['error']}, status=500)

    return JsonResponse({
        'success': True,
        'fields': out['fields'],
        'found': out['found'],
        'message': (f"{out['found']}개 항목의 자리를 짚었습니다. "
                    '상자가 엉뚱하면 끌어서 고친 뒤 "이 영역만 다시 읽기" 를 눌러 보세요.'
                    if out['found'] else
                    '자리를 하나도 짚지 못했습니다. 이 모델이 좌표를 잘 못 내는 것이니 '
                    '값 판독만 믿고 쓰세요 — 위치는 직접 그려도 됩니다.'),
    })


@staff_member_required
@require_POST
def truth_reread(request, case_id):
    """
    사람이 고친 영역만 잘라 그 항목을 다시 읽는다 (표적 재질의).

    **값을 저장하지 않는다.** 읽어서 돌려줄 뿐이고, 정답으로 삼을지는 사람이
    보고 정한다 — 다시 읽은 값도 판독값이라 틀릴 수 있다.
    """
    from v1.common.models import OcrPromptVersion, OcrTruthCase
    from v1.label.services.ocr_lab import reread_region

    case = get_object_or_404(OcrTruthCase, pk=case_id)
    payload = _json_body(request)

    field = (payload.get('field') or '').strip()
    box = payload.get('box')
    if not field:
        return JsonResponse({'success': False, 'error': '어느 항목인지 알 수 없습니다.'},
                            status=400)
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return JsonResponse(
            {'success': False, 'error': '영역은 숫자 네 개(x, y, 너비, 높이)여야 합니다.'},
            status=400)

    version = None
    if payload.get('prompt_version_id'):
        version = OcrPromptVersion.objects.filter(
            pk=payload['prompt_version_id']).first()

    out = reread_region(
        case, field, box,
        model=(payload.get('model') or '').strip() or None,
        prompt_version=version,
        use_hints=payload.get('use_hints', True),
    )
    if out['error']:
        return JsonResponse({'success': False, 'error': out['error']}, status=500)
    return JsonResponse({'success': True, 'field': field, 'result': out})
