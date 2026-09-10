"""
배합(BOM)으로 100 g 당 영양성분 **계산값**을 낸다.

    원료 100 g 당 값 × 배합비  →  합계  →  100 g 당 계산값

여기서 멈춘다. 허용오차도 반올림도 물리지 않는다
──────────────────────────────────────────────────
이 파일이 내놓는 것은 **계산값**뿐이고, 그 뒤 세 걸음(오차 → 표시 단위 반올림
→ 적용값)은 이미 nutrition_calc 가 한다. 여기서 오차까지 물리면 화면이 다시
물려 두 번 곱해진다 — 영양성분 계산기가 겪은 사고가 그것이다(309 를 두 번
저장해 475 가 되고 731 이 됐다). 계산값과 적용값을 갈라 두는 규칙은 이미
있으므로 새 규칙을 만들지 않고 그 앞자리에 붙는다.

열량은 원료 열량의 합이 아니다
──────────────────────────────
규정이 열량을 계수로 정의한다(탄수 4 · 단백 4 · 지방 9 · 식이섬유 2 · 당알콜
2.4). 그래서 합계 탄단지로 **다시 계산한다**(calories_from_macros). 원료 열량을
그냥 더하면 표 안에서 열량과 탄단지가 서로 맞지 않게 된다.

둘이 크게 벌어지면 원료 데이터가 어긋났다는 신호이므로 함께 알린다 — 예를
들어 어떤 원료의 열량만 1 회 제공량 기준이고 나머지는 100 g 기준일 때 이렇게
나타난다.

모르는 원료를 0 으로 세지 않는다
────────────────────────────────
영양성분이 없는 원료를 0 으로 두면 합계가 조용히 낮아진다. 그것은 "없다" 가
아니라 "모른다" 다. 모르는 원료는 따로 모아, 그것이 **표시값을 흔들 수 있는지**
를 nutrition_contrib 이 판정한다. 흔들지 못하면 물어볼 필요가 없다.

아직 없는 것: 수율
──────────────────
굽기·건조로 수분이 날아가면 완제품 100 g 의 농도가 달라진다. 이 파일은 아직
투입 기준으로만 센다. 수율을 붙일 자리는 apply_yield() 로 비워 두었다 —
수분(AMT_NUM2)을 적재해 두었으므로 수분 수지로 검산할 수 있다.
"""
from v1.label.services import nutrition_contrib
from v1.label.services.nutrition_calc import _number, calories_from_macros

# 배합 계산에서 더하는 성분. 표시 아홉에 열량 재계산용 둘을 더한 것이다.
SUM_FIELDS = (
    'calories', 'carbohydrates', 'sugars', 'proteins', 'fats',
    'saturated_fats', 'trans_fats', 'cholesterols', 'natriums',
    'dietary_fiber', 'sugar_alcohols',
)

# 원료 열량 합과 재계산 열량이 이만큼 넘게 벌어지면 원료 데이터를 의심한다
CALORIE_MISMATCH_RATE = 0.05


def nutrition_of_label(label):
    """
    표시사항(MyLabel)이 원료로 쓰일 때 그 100 g 당 값.

    MyLabel 의 성분 칸은 100 g 당으로 저장된다(constants.py 의 고열량·저영양
    주석이 그 전제를 적어 두었다). 숫자로 못 읽는 칸('5kcal 미만' 같은 표기)은
    None 이 되고, 그러면 그 성분은 모르는 것으로 다뤄진다.
    """
    if label is None:
        return None
    values = {f: _number(getattr(label, f, None)) for f in SUM_FIELDS}
    return values if any(v is not None for v in values.values()) else None


def collect_items(bom_rows):
    """
    BOM 줄을 (이름, 배합비, 영양성분 또는 None) 으로 편다.

    영양성분을 어디서 얻는가는 줄마다 다르다.
      child_label       내 표시사항을 원료로 쓴 것 — 그 라벨의 값이 있다
      source_ingredient 내 원료 보관함 — 아직 영양성분 칸이 없다(1 단계 과제)
      shared_receipt    공유받은 제품 — 영양성분 칸이 없다
    """
    items = []
    for row in bom_rows:
        name = row.ingredient_name or getattr(row.child_label, 'my_label_name', '') or ''
        ratio = _number(row.usage_ratio)
        values = nutrition_of_label(getattr(row, 'child_label', None))
        why = ''
        if values is None:
            if getattr(row, 'source_ingredient_id', None):
                why = '원료 보관함에 영양성분 칸이 아직 없다'
            elif getattr(row, 'shared_receipt_id', None):
                why = '공유받은 제품에 영양성분이 없다'
            else:
                why = '영양성분을 등록하지 않았다'
        items.append({'name': name, 'ratio': ratio, 'values': values, 'why': why})
    return items


def calculate(items):
    """
    배합으로 100 g 당 계산값을 낸다.

    items  collect_items() 가 만든 목록

    Returns
        values        {성분: 계산값}      아는 원료들만 더한 값
        ratio_total   배합비 합계(%)      100 이 아니면 알린다
        known_ratio   영양성분을 아는 원료의 배합비 합
        unknown       [{name, ratio, why}, ...]
        contribution  모르는 원료가 표시를 흔드는가 (nutrition_contrib)
        needed        {원료명: [모자란 성분, ...]}
        warnings      [문구, ...]
    """
    values = {f: 0.0 for f in SUM_FIELDS}
    seen = {f: False for f in SUM_FIELDS}
    ratio_total = 0.0
    known_ratio = 0.0
    unknown = []
    warnings = []
    ratio_missing = False

    for item in items:
        ratio = item['ratio']
        if ratio is None:
            ratio_missing = True
        else:
            ratio_total += ratio

        if item['values'] is None:
            unknown.append({'name': item['name'], 'ratio': ratio, 'why': item['why']})
            continue

        if ratio is None:
            # 값은 아는데 얼마나 넣는지 모른다 — 더할 수 없다
            unknown.append({'name': item['name'], 'ratio': None,
                            'why': '배합비를 모른다'})
            continue

        known_ratio += ratio
        for field in SUM_FIELDS:
            v = item['values'].get(field)
            if v is None:
                continue
            values[field] += v * ratio / 100.0
            seen[field] = True

    # 아무 원료도 준 적 없는 성분은 0 이 아니라 모르는 것이다
    for field in SUM_FIELDS:
        if not seen[field]:
            values[field] = None

    if ratio_missing:
        warnings.append('배합비가 빈 줄이 있어 합계에 넣지 못했다')
    if ratio_total and abs(ratio_total - 100.0) > 0.5:
        warnings.append('배합비 합계가 %.2f %% 다 (100 %% 가 아니면 100 g 당 값이 아니다)'
                        % ratio_total)

    # 열량은 합이 아니라 계수로 다시 센다
    summed_calories = values.get('calories')
    recalculated = calories_from_macros(values)
    if recalculated is not None:
        values['calories'] = recalculated
        if summed_calories:
            gap = abs(recalculated - summed_calories)
            if gap > max(summed_calories * CALORIE_MISMATCH_RATE, 5.0):
                warnings.append(
                    '원료 열량 합 %.1f kcal 과 탄단지로 잰 %.1f kcal 이 벌어진다 '
                    '— 원료 중 기준량이 다른 것이 섞였을 수 있다'
                    % (summed_calories, recalculated))

    contribution = nutrition_contrib.assess(
        values, [u['ratio'] for u in unknown])
    needed = nutrition_contrib.needed_fields(
        values, [(u['name'], u['ratio']) for u in unknown])

    return {'values': values, 'ratio_total': ratio_total, 'known_ratio': known_ratio,
            'unknown': unknown, 'contribution': contribution,
            'needed': needed, 'warnings': warnings}


def apply_yield(values, input_weight, output_weight):
    """
    수율을 반영한다 — **아직 쓰지 않는다.** 자리만 잡아 둔다.

    굽기·건조처럼 수분만 날아가는 공정은 고형분이 보존되므로 단순 환산이
    맞다. 유탕(기름이 들어온다)·착즙(고형분이 나간다)은 그렇지 않아 같은
    식으로 계산하면 지방이 실제보다 낮게 나온다.

    적재해 둔 수분(AMT_NUM2)으로 어느 쪽인지 **물어보지 않고 판정**할 수 있다.

        완제품 수분(가정) = 투입 수분 − (투입중량 − 완제품중량)
          ≥ 0  수분만 날아간 공정 → 환산이 옳다
          < 0  물리적으로 불가능 → 수분 외의 것이 드나들었다. 계산을 멈춘다

    그 판정을 붙이기 전에는 부르지 않는다.
    """
    raise NotImplementedError('수율은 아직 붙이지 않았다 — 수분 수지 판정이 먼저다')
