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
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# 등록 정보 대조의 효과를 따로 재기 위해, 대조가 손댈 수 있는 항목만 추린다.
# 전체 평균으로만 보면 대조와 무관한 항목이 숫자를 희석해 차이가 안 보인다.
from v1.label.services.ocr_reconcile import _FIELD_POLICY as _API_FIELDS  # noqa: E402

API_TOUCHED_FIELDS = tuple(_API_FIELDS.keys())


# 판독 한 번이 쓰는 입력 토큰의 어림값.
#
# 사진은 조각까지 다섯 장을 detail:high 로 보낸다. gpt-4o-mini 는 이미지
# 토큰 배수가 커서 한 장이 2만 안팎이고, 실측(§11)에서 한 번에 6~7만이었다.
# 원문을 함께 넣으면(use_hybrid) 조각을 빼므로 전체 한 장 + 원문 2천자다.
_TOKENS_PER_CALL = 65_000
_TOKENS_PER_CALL_HYBRID = 18_000


def pace_seconds(use_hybrid=False) -> float:
    """
    다음 판독까지 쉴 시간.

    **분당 토큰 한도를 판독 한 번의 토큰으로 나누면 분당 몇 번이 한계인지
    나온다.** 그보다 빨리 부르면 429 다. 기다리는 것 말고 할 수 있는 일이 없다.

        한도 200,000 / 한 번 65,000 = 분당 3번 -> 20초 간격
        원문을 넣으면 18,000     = 분당 11번 -> 하한(12초)이 이긴다

    예전에는 12초 고정이었다. 그것도 회차 사이에만 쉬고 **정답지 사이에는 안
    쉬었다.** 정답지 다섯 장을 3회씩 재는 A/B 를 돌렸더니 첫 회차부터 429 가
    났다 - 12초 간격이면 분당 다섯 번, 32만 토큰이라 한도의 1.6배다.

    한도를 올렸으면(OpenAI 사용 등급이 오르면 열 배가 된다) OCR_TPM_LIMIT 에
    적어 준다. 그만큼 측정이 빨라진다.
    """
    limit = getattr(settings, 'OCR_TPM_LIMIT', 200_000)
    cost = _TOKENS_PER_CALL_HYBRID if use_hybrid else _TOKENS_PER_CALL
    needed = 60.0 * cost / max(1, limit)
    return max(getattr(settings, 'OCR_RUN_PAUSE_SEC', 12), needed)


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
                 use_crop=False, use_api=False, use_hints=True, use_boxes=False,
                 layout='grid', read_freetext=None, use_ground=None,
                 use_hybrid=None):
    """
    정답지 한 장을 여러 번 읽어 채점한다.

    use_boxes=True 면 **읽은 자리도 함께 받아 채점한다.** 정답 위치를 적어 둔
    항목만 센다 - 안 적어 둔 항목은 "위치를 모른다" 는 뜻이지 "틀렸다" 가 아니다.
    값 점수와 위치 점수는 **따로** 낸다. 좌표를 요구하면 값이 흐려질 수 있어서,
    그 대가를 보려면 두 숫자가 갈라져 있어야 한다.

    Returns: {'name', 'runs', 'mean', 'fields', 'last', 'api': {...},
              'boxes': {...} 또는 None, 'errors': [...]}
    """
    from v1.label.services.ocr_benchmark import compare, summarize
    from v1.label.services.ocr_service import extract_label_from_image

    results = []
    api_results = []
    box_results = []
    errors = []
    last_data = None

    for i in range(max(1, runs)):
        # 회차 사이에 숨을 돌린다.
        #
        # 잇달아 부르면 뒤 회차가 429 로 죽고, 그러면 편차가 0 으로 나와
        # "안정적" 으로 읽힌다. 재시도만으로는 모자랐다 - 창이 아직 안 열렸는데
        # 다시 두드리는 것이라, 아예 창이 열릴 때까지 기다리는 편이 확실하다.
        # 얼마나 쉬어야 하는지는 pace_seconds 가 토큰으로 계산한다.
        if i:
            time.sleep(pace_seconds(use_hybrid))

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
                use_hints=use_hints, want_boxes=use_boxes, layout=layout,
                read_freetext=read_freetext, use_ground=use_ground,
                use_hybrid=use_hybrid)
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

        if not out.get('success') and _is_rate_limited(out):
            # 분당 토큰 한도다. 창이 열릴 때까지 한 번 더 기다렸다 해 본다 -
            # 여기서 포기하면 회차가 조용히 줄고, 편차가 0 으로 나와
            # "안정적" 으로 읽힌다.
            time.sleep(getattr(settings, 'OCR_RATE_LIMIT_WAIT_SEC', 25))
            try:
                source = case.image.open('rb')
                out = extract_label_from_image(
                    source, model=model, prompt_version=prompt_version,
                    use_hints=use_hints, want_boxes=use_boxes, layout=layout,
                    read_freetext=read_freetext, use_ground=use_ground,
                    use_hybrid=use_hybrid)
            except Exception as exc:
                logger.exception('정답지 재판독 실패 (case=%s)', case.pk)
                from v1.label.services.ocr_service import failure
                out = failure(exc)
            finally:
                if source is not None and hasattr(source, 'close'):
                    try:
                        source.close()
                    except Exception:
                        pass

        if not out.get('success'):
            # 여기는 관리자 측정 화면이다. 무엇이 왜 실패했는지 봐야 하므로
            # 다듬은 문구가 아니라 기술적인 원문을 남긴다.
            errors.append(f'{i + 1}회 실패: '
                          f'{out.get("error_detail") or out.get("error")}')
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

        if use_boxes and (case.expected_boxes or {}):
            try:
                from v1.label.services.ocr_boxes import score as score_boxes
                box_results.append(score_boxes(case.expected_boxes, data))
            except Exception:
                logger.exception('위치 채점 실패 (case=%s)', case.pk)
        last_data = data

    if not results:
        return {'name': case.name, 'case_id': case.pk, 'runs': 0, 'mean': 0.0,
                'fields': [], 'last': {}, 'api': None, 'boxes': None,
                'errors': errors}

    row = {
        'name': case.name,
        'case_id': case.pk,
        'runs': len(results),
        'mean': round(statistics.mean(r['mean'] for r in results), 1),
        'fields': summarize(results),
        'last': results[-1]['fields'],
        'errors': errors,
        'api': None,
        'boxes': _box_summary(box_results),
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


def _is_rate_limited(out):
    """
    분당 토큰 한도에 걸린 실패인가.

    ocr_service 가 error_kind 를 붙여 준다. 화면에 보이는 문구는 사람이 읽을
    말로 다듬여 있어서, 그 글자를 뒤지면 문구를 손볼 때마다 이 판단이 조용히
    깨진다. 옛 응답(문구뿐인 dict, 문자열)도 그대로 받아 준다.
    """
    if isinstance(out, dict):
        if out.get('error_kind'):
            return out['error_kind'] == 'rate_limit'
        out = out.get('error_detail') or out.get('error')
    text = str(out or '').lower()
    return '429' in text or 'rate limit' in text or 'rate_limit' in text


def _box_summary(box_results):
    """
    회차별 위치 채점을 한 줄로 합친다. 잰 게 없으면 None.

    마지막 회차의 항목별 겹침을 그대로 남긴다 - 평균만 보면 "어느 항목의
    자리를 못 찾는가" 를 알 수 없고, 그게 정작 고쳐야 할 것이다.
    """
    rows = [r for r in box_results if r and r['fields']]
    if not rows:
        return None
    return {
        'mean': round(statistics.mean(r['mean'] for r in rows), 1),
        'hit_rate': round(statistics.mean(r['hit_rate'] for r in rows), 1),
        'graded': len(rows[-1]['fields']),
        'fields': rows[-1]['fields'],
        'missing': rows[-1]['missing'],
    }


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
                  use_crop=False, use_api=False, use_hints=True,
                  use_boxes=False, layout='grid', read_freetext=None,
                  use_ground=None, use_hybrid=None, user=None):
    """
    정답지 여러 장을 재고 결과를 OcrBenchmarkRun 으로 남긴다.

    남기지 않으면 "고치기 전엔 몇 점이었지" 를 아무도 답할 수 없다.
    """
    from django.conf import settings

    from v1.common.models import OcrBenchmarkRun

    model = model or getattr(settings, 'OCR_MODEL', 'gpt-4o-mini')
    case_rows = []
    for index, case in enumerate(cases):
        # **정답지 사이에도 쉰다.** 예전에는 회차 사이에만 쉬어서, 앞 정답지의
        # 마지막 회차와 다음 정답지의 첫 회차가 붙어 나갔다. 정답지가 여러
        # 장이면 그 자리에서 429 가 난다.
        if index:
            time.sleep(pace_seconds(use_hybrid))
        case_rows.append(measure_case(
            case, runs=runs, model=model, prompt_version=prompt_version,
            use_crop=use_crop, use_api=use_api, use_hints=use_hints,
            use_boxes=use_boxes, layout=layout, read_freetext=read_freetext,
            use_ground=use_ground, use_hybrid=use_hybrid))

    scored = [r for r in case_rows if r['runs']]
    mean = round(statistics.mean(r['mean'] for r in scored), 1) if scored else 0.0

    # **부탁한 회차가 아니라 실제로 성공한 회차를 남긴다.**
    # 429(분당 토큰 한도)로 두 번이 죽고 한 번만 돌았는데 표에 "3회" 라고 뜨면,
    # 편차 0 을 보고 "안정적이다" 라고 읽게 된다. 측정이 거짓말을 하는 것이다.
    done = max((r['runs'] for r in case_rows), default=0)

    # 판독 원본은 남기지 않는다. 사진 한 장에 수 KB 씩 쌓이는데 화면이 쓰지
    # 않고, 이 표는 오래 남는다.
    for row in case_rows:
        row.pop('_raw', None)

    detail = {
        'cases': case_rows,
        'fields': _merge_field_rows(case_rows),
        'api_mean': _api_overall(case_rows),
        'box_mean': _box_overall(case_rows),
        'runs_asked': runs,
        'read_freetext': bool(read_freetext),
        'ground': bool(use_ground),
        'hybrid': bool(use_hybrid),
        # 조각을 어느 방향으로 잘랐는가. 모델을 안 바꿔도 이것만으로 긴 항목의
        # 점수가 크게 움직인다 - 남기지 않으면 어느 판이 어느 방식이었는지
        # 나중에 알 수 없다.
        'tiling': layout,
    }

    run = OcrBenchmarkRun.objects.create(
        prompt_version=prompt_version,
        model=model,
        variant='crop' if use_crop else 'whole',
        use_api=use_api,
        case_count=len(case_rows),
        runs=done or runs,
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


def _box_overall(case_rows):
    """위치를 켜고 잰 경우의 전체 평균."""
    rows = [c['boxes'] for c in case_rows if c.get('boxes')]
    if not rows:
        return None
    return {
        'mean': round(statistics.mean(r['mean'] for r in rows), 1),
        'hit_rate': round(statistics.mean(r['hit_rate'] for r in rows), 1),
        'graded': sum(r['graded'] for r in rows),
    }


def draft_expected(image_file, model=None):
    """
    사진을 읽어 정답지 초안을 만든다.

    **초안은 판독 결과다.** 그대로 확인 처리하면 자기 답을 자기가 채점하는 꼴이
    되므로, 화면은 verified=False 로 두고 사람이 고친 뒤에야 채점에 쓴다.

    **주의사항·기타표시사항도 읽는다**(read_freetext=True). 평소 판독은 이 두
    칸을 읽지 않는다 - 무엇을 해도 흔들려서(25~52점, 편차 80) 지어낸 문구가
    법적 표시물에 들어가는 위험이 크기 때문이다. 그런데 그건 **인쇄로 나가는
    값**에 대한 판단이고, 정답지는 사람이 사진을 보며 고치는 초안이다.

    오히려 여기서 안 읽으면 두 칸이 빈 채로 정답지에 쌓이고, 그러면 그 칸의
    정확도를 **영원히 잴 수 없다.** 지금 하는 일(OCR 원문 대조)이 바로 그 두
    칸을 되살리려는 것인데, 재는 자에 그 칸이 없으면 되살렸는지 알 방법이 없다.
    """
    from v1.label.services.ocr_benchmark import flatten
    from v1.label.services.ocr_service import extract_label_from_image

    out = extract_label_from_image(image_file, model=model, read_freetext=True)
    if not out.get('success'):
        return None, out.get('error') or '사진을 읽지 못했습니다.'
    return flatten(out.get('data')), ''


# 정답지가 담는 항목과 그 값을 가져올 MyLabel 필드.
#
# **화면의 입력 칸 목록도 이것이다.** 예전에는 화면이 "이미 값이 있는 항목" 만
# 입력 줄로 그렸다. 그래서 판독이 못 읽었거나 일부러 안 읽은 칸은 줄 자체가
# 안 생겨, 손으로 채워 넣을 방법이 없었다 - 주의사항·기타표시사항이 정확히
# 그 경우였다. 정답지에 그 두 칸이 영영 안 쌓이니 그 칸의 정확도도 잴 수
# 없었다. 빈 칸이라도 **늘 보여야** 사람이 채울 수 있다.
#
# 순서가 곧 화면 순서다. 라벨을 읽는 순서(제품 -> 업체 -> 원재료 -> 문구 ->
# 영양성분)로 둔다.
TRUTH_FIELDS = (
    ('prdlst_nm', 'prdlst_nm'),
    ('prdlst_dcnm', 'prdlst_dcnm'),
    ('content_weight', 'content_weight'),
    ('weight_calorie', 'weight_calorie'),
    ('prdlst_report_no', 'prdlst_report_no'),
    ('country_of_origin', 'country_of_origin'),
    ('bssh_nm', 'bssh_nm'),
    ('distributor_address', 'distributor_address'),
    ('repacker_address', 'repacker_address'),
    ('importer_address', 'importer_address'),
    ('storage_method', 'storage_method'),
    ('pog_daycnt', 'pog_daycnt'),
    ('rawmtrl_nm', 'rawmtrl_nm_display'),
    ('allergens', 'allergens'),
    ('ingredient_info', 'ingredient_info'),
    ('frmlc_mtrqlt', 'frmlc_mtrqlt'),
    ('recycling_mark', 'prv_recycling_mark_type'),
    ('cautions', 'cautions'),
    ('additional_info', 'additional_info'),
    ('nutrition_basis', 'serving_size'),
    ('calories', 'calories'),
    ('natriums', 'natriums'),
    ('carbohydrates', 'carbohydrates'),
    ('sugars', 'sugars'),
    ('fats', 'fats'),
    ('trans_fats', 'trans_fats'),
    ('saturated_fats', 'saturated_fats'),
    ('cholesterols', 'cholesterols'),
    ('proteins', 'proteins'),
)

TRUTH_FIELD_KEYS = tuple(key for key, _ in TRUTH_FIELDS)


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
    out = {}
    for key, attr in TRUTH_FIELDS:
        value = str(getattr(label, attr, '') or '').strip()
        if key == 'rawmtrl_nm' and not value:
            value = str(getattr(label, 'rawmtrl_nm', '') or '').strip()
        if value:
            out[key] = value
    return out


# ── 읽은 자리 ────────────────────────────────────────────────────────────────
#
# 값이 틀렸을 때 지금까지 알 수 있는 것은 "틀렸다" 뿐이었다. 어디를 읽고 그
# 답을 냈는지 보이면 **왜** 틀렸는지가 보인다 — 옆 칸을 읽었는지, 작업지시서의
# 표를 읽었는지, 아예 못 찾았는지.
#
# 그리고 자리를 알면 고칠 수 있다. 자리를 고쳐 그 영역만 다시 읽히고, 그 자리를
# 정답 위치로 적어 두면 다음 측정부터 **위치도 채점 대상**이 된다.
#
# 이건 관리자 화면에만 있다. 좌표가 맞는지 재려면 정답이 필요하고, 정답은
# 여기에만 있기 때문이다.

def locate_case(case, model=None, prompt_version=None, use_hints=True):
    """
    정답지 사진을 한 번 읽어 **값과 읽은 자리**를 함께 가져온다.

    Returns: {'fields': {항목: {'value','box','box_from','confidence'}},
              'found': 자리를 짚은 항목 수, 'error': ''}
    """
    from v1.label.services.ocr_service import extract_label_from_image

    source = None
    try:
        source = case.image.open('rb')
        # 정답지 화면이라 주의사항·기타표시사항의 자리도 짚어야 한다
        # (draft_expected 주석 참고).
        out = extract_label_from_image(
            source, model=model, prompt_version=prompt_version,
            use_hints=use_hints, want_boxes=True, read_freetext=True)
    except Exception as exc:
        logger.exception('위치 판독 실패 (case=%s)', case.pk)
        return {'fields': {}, 'found': 0, 'error': str(exc)}
    finally:
        if source is not None and hasattr(source, 'close'):
            try:
                source.close()
            except Exception:
                pass

    if not out.get('success'):
        return {'fields': {}, 'found': 0,
                'error': out.get('error') or '사진을 읽지 못했습니다.'}

    fields = {}
    for key, item in (out.get('data') or {}).items():
        if not isinstance(item, dict):
            continue
        value = str(item.get('value') or '').strip()
        box = item.get('box')
        if not value and not box:
            continue
        fields[key] = {
            'value': value,
            'box': box,
            'box_from': item.get('box_from') or '',
            'confidence': item.get('confidence') or '',
        }
    return {'fields': fields, 'found': out.get('boxes_found') or 0, 'error': ''}


def reread_region(case, field, box, model=None, prompt_version=None,
                  use_hints=True):
    """
    사람이 고친 영역만 잘라 다시 읽는다 (표적 재질의).

    전체를 다시 읽는 것보다 훨씬 싸고, 그 영역에 해상도가 전부 배정되므로 잘
      읽힌다 — 화면의 "영역 선택" 판독이 통하는 이유와 같다.

    **평소 판독 경로를 그대로 쓴다.** 잘라 낸 조각을 같은 함수에 넣을 뿐이라,
    활성 프롬프트도 사전 스냅도 그대로 걸린다. 그 항목만 따로 묻는 전용
    프롬프트를 새로 만들면 두 벌이 되고, 어느 날 한쪽만 고쳐진다.

    영역이 작으면 조각내기(TILE_MIN_SIDE)가 안 걸려 이미지 한 장만 나간다.

    Returns: {'value', 'confidence', 'others': {항목: 값}, 'error': ''}
             others 는 그 영역에서 함께 읽힌 다른 항목들이다 — 영역을 잘못
             잡았을 때 "여기엔 이게 적혀 있다" 를 보여 준다.
    """
    from io import BytesIO

    from PIL import Image, ImageOps

    from v1.label.services.ocr_boxes import pad
    from v1.label.services.ocr_service import extract_label_from_image

    try:
        img = Image.open(case.image.path)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode != 'RGB':
            img = img.convert('RGB')

        area = pad(box, img.width, img.height)
        if not area:
            return {'value': '', 'confidence': '', 'others': {},
                    'error': '영역이 사진 밖이거나 크기가 0 입니다.'}

        x, y, w, h = area
        buf = BytesIO()
        img.crop((x, y, x + w, y + h)).save(buf, format='JPEG', quality=95)
        buf.seek(0)

        # 정답지를 만드는 자리라 주의사항·기타표시사항도 읽는다
        # (draft_expected 주석 참고). 안 읽으면 그 두 칸은 영역을 지정해도
        # 빈 값만 돌아와, 왜 안 되는지 알 수 없다.
        out = extract_label_from_image(
            buf, model=model, prompt_version=prompt_version, use_hints=use_hints,
            read_freetext=True)
    except Exception as exc:
        logger.exception('영역 재판독 실패 (case=%s, field=%s)', case.pk, field)
        return {'value': '', 'confidence': '', 'others': {}, 'error': str(exc)}

    if not out.get('success'):
        return {'value': '', 'confidence': '', 'others': {},
                'error': out.get('error') or '영역을 읽지 못했습니다.'}

    data = out.get('data') or {}
    item = data.get(field) if isinstance(data.get(field), dict) else {}
    others = {}
    for key, row in data.items():
        if key == field or not isinstance(row, dict):
            continue
        value = str(row.get('value') or '').strip()
        if value:
            others[key] = value

    return {
        'value': str((item or {}).get('value') or '').strip(),
        'confidence': (item or {}).get('confidence') or '',
        'others': others,
        'error': '',
    }
