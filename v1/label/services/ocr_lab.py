"""
정답지로 판독 정확도를 재고, 그 결과를 남긴다.

파일로 재는 길(management/commands/ocr_benchmark.py)이 이미 있다. 채점 규칙은
그쪽과 **같은 모듈**(ocr_benchmark.py)을 쓴다 — 두 벌로 만들면 어느 날 한쪽만
고쳐져서 두 숫자가 어긋난다. 여기서 새로 하는 일은 셋이다.

  1. 정답지를 DB 에서 읽는다      서버에 파일을 올릴 수 있는 사람만 쓰던 것을
                                  화면에서 쓰게 한다.
  2. 무엇을 바꿔 가며 잰다        프롬프트 판 / 모델 / 영역선택 / 등록 정보 대조
  3. 결과를 남긴다                전후를 견주려면 예전 숫자가 남아 있어야 한다.

**한 번 돌린 결과로 판단하지 마시오.** 같은 사진도 매번 다르게 읽힌다. runs 를
올려 평균과 편차를 함께 본다.
"""
import logging
import statistics

logger = logging.getLogger(__name__)

# 등록 정보 대조의 효과를 따로 재기 위해, 대조가 손댈 수 있는 항목만 추린다.
# 전체 평균으로만 보면 대조와 무관한 항목이 숫자를 희석해 차이가 안 보인다.
from v1.label.services.ocr_reconcile import _FIELD_POLICY as _API_FIELDS  # noqa: E402

API_TOUCHED_FIELDS = tuple(_API_FIELDS.keys())


def _open_source(case):
    """
    이 정답지를 읽을 때 모델에 넘길 파일.

    정답지에 영역(crop_box)이 적혀 있으면 그 부분만 잘라 넘긴다 — 화면의
    자르기 기능과 같은 일을 코드로 해서, 방식 비교를 사람 손 없이 돌린다.
    """
    from v1.label.services.ocr_benchmark import crop_image

    box = case.crop_box
    if box and len(box) == 4 and any(int(v) for v in box):
        return crop_image(case.image.path, box), True
    return case.image.open('rb'), False


def measure_case(case, runs=1, model=None, prompt_version=None,
                 use_crop=False, use_api=False, use_hints=True):
    """
    정답지 한 장을 여러 번 읽어 채점한다.

    Returns: {'name', 'runs', 'mean', 'fields', 'last', 'api': {...}, 'errors': [...]}
    """
    from v1.label.services.ocr_benchmark import compare, summarize
    from v1.label.services.ocr_service import extract_label_from_image

    results = []
    api_results = []
    errors = []
    last_data = None

    for i in range(max(1, runs)):
        source = None
        try:
            if use_crop:
                source, cropped = _open_source(case)
                if not cropped:
                    # 영역이 안 적혀 있으면 전체를 읽은 것이다. 그걸 "영역 선택"
                    # 결과로 세면 두 방식의 비교가 거짓말이 된다.
                    errors.append('읽을 영역이 지정돼 있지 않아 사진 전체로 읽었습니다.')
            else:
                source = case.image.open('rb')

            out = extract_label_from_image(
                source, model=model, prompt_version=prompt_version,
                use_hints=use_hints)
        except Exception as exc:
            logger.exception('정답지 판독 실패 (case=%s)', case.pk)
            errors.append(f'{i + 1}회 실패: {exc}')
            continue
        finally:
            if source is not None and hasattr(source, 'close'):
                try:
                    source.close()
                except Exception:
                    pass

        if not out.get('success'):
            errors.append(f'{i + 1}회 실패: {out.get("error")}')
            continue

        data = out.get('data') or {}
        results.append(compare(case.expected, data))

        if use_api:
            # 대조는 판독 결과에 얹는 것이라, 같은 판독을 두 번 채점해 순수한
            # 기여분을 본다 — 사진을 다시 읽으면 회차 간 흔들림과 섞인다.
            try:
                from v1.label.services.ocr_reconcile import merge
                api_results.append(compare(case.expected, merge(data)))
            except Exception:
                logger.exception('등록 정보 대조 채점 실패 (case=%s)', case.pk)
        last_data = data

    if not results:
        return {'name': case.name, 'case_id': case.pk, 'runs': 0, 'mean': 0.0,
                'fields': [], 'last': {}, 'api': None, 'errors': errors}

    row = {
        'name': case.name,
        'case_id': case.pk,
        'runs': len(results),
        'mean': round(statistics.mean(r['mean'] for r in results), 1),
        'fields': summarize(results),
        'last': results[-1]['fields'],
        'errors': errors,
        'api': None,
    }
    if api_results:
        api_mean = round(statistics.mean(r['mean'] for r in api_results), 1)
        row['api'] = {
            'mean': api_mean,
            'gain': round(api_mean - row['mean'], 1),
            'fields': summarize(api_results),
            'touched': _api_field_gain(results, api_results),
        }
    row['_raw'] = last_data
    return row


def _api_field_gain(before, after):
    """
    등록 정보 대조가 **어느 항목을** 얼마나 올렸는지.

    전체 평균만 보면 "조금 올랐다" 로 끝난다. 어느 자리에서 왔는지 알아야
    대조를 더 넓힐지 좁힐지 정할 수 있다.
    """
    def mean_of(runs, field):
        scores = [r['fields'][field]['score'] for r in runs if field in r['fields']]
        return round(statistics.mean(scores), 1) if scores else None

    out = []
    for field in API_TOUCHED_FIELDS:
        b, a = mean_of(before, field), mean_of(after, field)
        if b is None or a is None or a == b:
            continue
        out.append({'field': field, 'before': b, 'after': a,
                    'gain': round(a - b, 1)})
    return sorted(out, key=lambda r: r['gain'], reverse=True)


def run_benchmark(cases, runs=1, model=None, prompt_version=None,
                  use_crop=False, use_api=False, use_hints=True, user=None):
    """
    정답지 여러 장을 재고 결과를 OcrBenchmarkRun 으로 남긴다.

    남기지 않으면 "고치기 전엔 몇 점이었지" 를 아무도 답할 수 없다.
    """
    from django.conf import settings

    from v1.common.models import OcrBenchmarkRun

    model = model or getattr(settings, 'OCR_MODEL', 'gpt-4o-mini')
    case_rows = []
    for case in cases:
        case_rows.append(measure_case(
            case, runs=runs, model=model, prompt_version=prompt_version,
            use_crop=use_crop, use_api=use_api, use_hints=use_hints))

    scored = [r for r in case_rows if r['runs']]
    mean = round(statistics.mean(r['mean'] for r in scored), 1) if scored else 0.0

    # 판독 원본은 남기지 않는다. 사진 한 장에 수 KB 씩 쌓이는데 화면이 쓰지
    # 않고, 이 표는 오래 남는다.
    for row in case_rows:
        row.pop('_raw', None)

    detail = {
        'cases': case_rows,
        'fields': _merge_field_rows(case_rows),
        'api_mean': _api_overall(case_rows),
    }

    run = OcrBenchmarkRun.objects.create(
        prompt_version=prompt_version,
        model=model,
        variant='crop' if use_crop else 'whole',
        use_api=use_api,
        case_count=len(case_rows),
        runs=runs,
        mean_score=mean,
        detail=detail,
        created_by=user if (user and user.is_authenticated) else None,
    )

    # 판마다 최근 점수를 붙여 둔다. 목록에서 어느 판이 나았는지 바로 보인다.
    if prompt_version is not None and scored:
        from django.utils import timezone
        prompt_version.last_score = mean
        prompt_version.last_scored_at = timezone.now()
        prompt_version.save(update_fields=['last_score', 'last_scored_at'])

    return run


def _merge_field_rows(case_rows):
    """사진별 항목 점수를 항목 기준으로 합친다 (화면의 "항목별" 표)."""
    bucket = {}
    for case in case_rows:
        for row in case.get('fields', []):
            bucket.setdefault(row['field'], []).append(row)

    out = []
    for field, rows in bucket.items():
        means = [r['mean'] for r in rows]
        out.append({
            'field': field,
            'cases': len(rows),
            'runs': sum(r['runs'] for r in rows),
            'mean': round(statistics.mean(means), 1),
            'worst': round(min(r['worst'] for r in rows), 1),
            'best': round(max(r['best'] for r in rows), 1),
            'spread': round(max(r['spread'] for r in rows), 1),
        })
    return sorted(out, key=lambda r: r['mean'])


def _api_overall(case_rows):
    """등록 정보 대조를 켜고 잰 경우의 전체 평균과 이득."""
    rows = [c['api'] for c in case_rows if c.get('api')]
    if not rows:
        return None
    return {
        'mean': round(statistics.mean(r['mean'] for r in rows), 1),
        'gain': round(statistics.mean(r['gain'] for r in rows), 1),
    }


def draft_expected(image_file, model=None):
    """
    사진을 읽어 정답지 초안을 만든다.

    **초안은 판독 결과다.** 그대로 확인 처리하면 자기 답을 자기가 채점하는 꼴이
    되므로, 화면은 verified=False 로 두고 사람이 고친 뒤에야 채점에 쓴다.
    """
    from v1.label.services.ocr_benchmark import flatten
    from v1.label.services.ocr_service import extract_label_from_image

    out = extract_label_from_image(image_file, model=model)
    if not out.get('success'):
        return None, out.get('error') or '사진을 읽지 못했습니다.'
    return flatten(out.get('data')), ''


def expected_from_label(label):
    """
    사람이 검증하고 판정까지 낸 표시사항을 정답으로 가져온다.

    가장 믿을 만한 정답이다 — 판독값이 아니라 **실제로 인쇄에 쓰인 값**이고,
    검토·승인을 거치며 사람이 여러 번 본 값이다. 손으로 다시 옮겨 적을 이유가
    없다.

    빈 항목은 넣지 않는다. 채점기(score_one)는 정답이 빈 항목을 "그 라벨에
    없는 항목" 으로 보고 건너뛰므로, 빈 값을 넣어도 결과가 달라지지 않는데
    화면만 지저분해진다.
    """
    mapping = {
        'prdlst_nm': 'prdlst_nm',
        'prdlst_dcnm': 'prdlst_dcnm',
        'content_weight': 'content_weight',
        'weight_calorie': 'weight_calorie',
        'prdlst_report_no': 'prdlst_report_no',
        'country_of_origin': 'country_of_origin',
        'bssh_nm': 'bssh_nm',
        'distributor_address': 'distributor_address',
        'repacker_address': 'repacker_address',
        'importer_address': 'importer_address',
        'storage_method': 'storage_method',
        'rawmtrl_nm': 'rawmtrl_nm_display',
        'allergens': 'allergens',
        'ingredient_info': 'ingredient_info',
        'frmlc_mtrqlt': 'frmlc_mtrqlt',
        'pog_daycnt': 'pog_daycnt',
        'cautions': 'cautions',
        'additional_info': 'additional_info',
        'calories': 'calories',
        'natriums': 'natriums',
        'carbohydrates': 'carbohydrates',
        'sugars': 'sugars',
        'fats': 'fats',
        'trans_fats': 'trans_fats',
        'saturated_fats': 'saturated_fats',
        'cholesterols': 'cholesterols',
        'proteins': 'proteins',
    }
    out = {}
    for key, attr in mapping.items():
        value = str(getattr(label, attr, '') or '').strip()
        if key == 'rawmtrl_nm' and not value:
            value = str(getattr(label, 'rawmtrl_nm', '') or '').strip()
        if value:
            out[key] = value
    return out
