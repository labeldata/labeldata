"""
원재료 표를 문구로 만든다.

두 가지를 만든다. 쓰임이 다르다.

  build_reference_text(label)  -> label.rawmtrl_nm         (참고용)
      화면 상단에 "이렇게 잡혀 있다" 고 보여 주는 요약. 식품유형 위주로 적고
      혼합제제·향료 번호 같은 관례를 따른다. 원래 label_creation 뷰 안에
      인라인으로 있던 것을 그대로 옮겼다 — 동작을 바꾸지 않았다.

  build_display_text(label)    -> label.rawmtrl_nm_display (인쇄되는 문구)
      실제로 라벨에 찍히는 원재료명. 여기가 법적 리스크가 가장 큰 산출물인데
      여태 자동화가 없어서, 사용자가 참고용 문구를 "복사하기" 로 옮긴 뒤 손으로
      다듬고 있었다.

**AI 는 쓰지 않는다.** 필요한 규칙이 전부 결정론적이고, 판단 근거가 이미 DB 에
있기 때문이다 — 배합비는 relation 에, 첨가물 간략명 규칙은
FoodAdditive.display_name_options() 에, 하위 원료는 MyIngredient.rawmtrl_nm 에.
이 프로젝트의 원칙("AI 는 추출만, 판정은 결정론적 로직")을 생성에도 적용한다.

만든 문구를 바로 저장하지는 않는다. 화면이 받아서 사용자가 확인하고 저장한다.
"""
import re

from v1.label.models import FoodAdditive, LabelIngredientRelation

_SHELLFISH = re.compile(r'^조개류\(([^)]+)\)$')
_PARENS = re.compile(r'[(（][^)）]*[)）]')


def ordered_relations(label):
    """
    배합비 내림차순. 「식품등의 표시기준」이 요구하는 순서다.

    배합비가 없는 행은 0 으로 보아 뒤로 보낸다. 값이 같으면 입력 순서를 지킨다
    — 파이썬 sort 는 안정 정렬이다. BOM 에디터(generateBomSummary)와 같은 규칙.
    """
    return sorted(
        LabelIngredientRelation.objects
        .filter(label_id=label.my_label_id)
        .select_related('ingredient')
        .order_by('relation_sequence'),
        key=lambda rel: -float(rel.ingredient_ratio or 0),
    )


def _ratio_of(relation):
    try:
        return float(relation.ingredient_ratio) if relation.ingredient_ratio is not None else None
    except (TypeError, ValueError):
        return None


def collect_allergens_and_gmo(relations):
    """원료들에서 알레르기·GMO 를 모은다. (알레르기 목록, GMO 목록)"""
    allergens, gmo, shellfish = set(), set(), set()
    for relation in relations:
        ingredient = relation.ingredient
        for raw in (ingredient.allergens or '').split(','):
            item = (raw or '').strip()
            if not item:
                continue
            m = _SHELLFISH.match(item)
            if m:
                shellfish.update(x.strip() for x in m.group(1).split(',') if x.strip())
            else:
                allergens.add(item)
        for raw in (ingredient.gmo or '').split(','):
            item = (raw or '').strip()
            if item:
                gmo.add(item)
    if shellfish:
        # 조개류는 종류를 괄호에 모아 한 항목으로 적는다
        allergens.add(f"조개류({', '.join(sorted(shellfish))})")
    return sorted(a for a in allergens if a), sorted(g for g in gmo if g)


# ─────────────────────────────────────────────────────────────────────────────
# 참고용 요약 (기존 동작 그대로)
# ─────────────────────────────────────────────────────────────────────────────

def build_reference_text(label):
    """label.rawmtrl_nm 에 넣던 요약을 만든다."""
    relations = ordered_relations(label)
    if not relations:
        return ''

    ingredients_info = []
    flavor_counter, purpose_counter = {}, {}

    for relation in relations:
        ingredient = relation.ingredient
        food_category = (getattr(ingredient, 'food_category', None)
                         or getattr(ingredient, 'food_group', None) or '')
        display_name = ingredient.ingredient_display_name or ingredient.prdlst_nm or ''
        # display_name 이 콤마로 여러 개일 때 최대 5개까지만 (팝업과 동일)
        if display_name and ',' in display_name:
            display_name = ', '.join([x.strip() for x in display_name.split(',')][:5])
        food_type = ingredient.prdlst_dcnm or ''
        ratio = _ratio_of(relation)

        # 혼합제제(식품첨가물)
        if food_category == 'additive' and '혼합제제' in display_name:
            ingredients_info.append(f'혼합제제[{display_name}]')
            continue

        # 향료 번호 붙이기
        if food_category == 'additive' and (display_name.startswith('향료')
                                            or re.match(r'^향료(\(.+\))?$', display_name)):
            flavor_counter[display_name] = flavor_counter.get(display_name, 0) + 1
            count = flavor_counter[display_name]
            suffix = f'{count}' if count > 1 else ''
            tail = display_name[2:] if display_name.startswith('향료') else ''
            ingredients_info.append(f'향료{suffix}{tail}')
            continue

        # 동일 용도(영양강화제·산화방지제 등) 번호 붙이기
        m = re.match(r'^([가-힣]+제)(\(.+\))?$', display_name)
        if food_category == 'additive' and m:
            purpose = m.group(1)
            purpose_counter[purpose] = purpose_counter.get(purpose, 0) + 1
            count = purpose_counter[purpose]
            suffix = f'{count}' if count > 1 else ''
            ingredients_info.append(f'{purpose}{suffix}{m.group(2) or ""}')
            continue

        if display_name == '정제수':
            summary_item = food_type or display_name
        elif (food_category == 'additive') or (ratio is not None and ratio >= 5):
            if food_type and display_name:
                summary_item = f'{food_type}[{display_name}]'
            elif food_type:
                summary_item = food_type
            else:
                summary_item = display_name
        else:
            summary_item = food_type or display_name
        if summary_item:
            ingredients_info.append(summary_item)

    text = ', '.join(ingredients_info)
    allergens, gmo = collect_allergens_and_gmo(relations)
    parts = []
    if allergens:
        parts.append(f"[알레르기 성분: {', '.join(allergens)}]")
    if gmo:
        parts.append(f"[GMO: {', '.join(gmo)}]")
    if parts:
        text += f"  {' '.join(parts)}"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# 인쇄되는 표시 문구
# ─────────────────────────────────────────────────────────────────────────────

def additive_display_name(ingredient):
    """
    식품첨가물의 표시명을 표4·5·6 규칙으로 정한다.

    표4 대상은 명칭만 적으면 표시기준 위반이라 "명칭(용도)" 여야 한다. 용도가
    여럿이면 어느 것인지 코드가 정할 수 없으므로(그건 배합 의도의 문제다)
    사용자가 원료 상세에서 고른 값을 그대로 쓴다.

    Returns: (표시명, 사용자가 직접 골라야 하는지)
    """
    chosen = (ingredient.ingredient_display_name or '').strip()
    name = (ingredient.prdlst_nm or '').strip()

    additive = FoodAdditive.objects.filter(name_kr=name).first()
    if additive is None:
        return chosen or name, False

    options = additive.display_name_options()
    if chosen and chosen in options:
        return chosen, False          # 사용자가 이미 규칙에 맞는 것을 골랐다

    default = additive.default_display_name()
    if default:
        return default, False
    # 표4인데 용도가 여럿 — 코드가 못 정한다
    return chosen or name, True


def compound_display(name, ingredient):
    """
    복합원재료는 괄호 안에 하위 원료를 적는다.

    "빵가루(밀가루, 정제소금)" 처럼. 하위 원료는 MyIngredient.rawmtrl_nm 에 있다.
    이름에 이미 괄호가 있으면 두 겹으로 만들지 않고 그대로 둔다.
    """
    subs = (ingredient.rawmtrl_nm or '').strip()
    if not subs or _PARENS.search(name):
        return name
    items = [x.strip() for x in subs.split(',') if x.strip()]
    if not items:
        return name
    return f"{name}({', '.join(items)})"


def build_display_text(label):
    """
    라벨에 인쇄되는 원재료명 문구를 만든다.

    Returns: {'text': str, 'needs_review': [원료명...], 'count': int}
    needs_review 는 코드가 표시명을 확정하지 못한 첨가물이다. 화면이 그것만
    짚어 주면 사용자가 전부 다시 볼 필요가 없다.
    """
    relations = ordered_relations(label)
    if not relations:
        return {'text': '', 'needs_review': [], 'count': 0}

    parts, needs_review = [], []
    for relation in relations:
        ingredient = relation.ingredient
        food_category = (getattr(ingredient, 'food_category', None)
                         or getattr(ingredient, 'food_group', None) or '')

        if food_category == 'additive':
            name, unsure = additive_display_name(ingredient)
            if unsure:
                needs_review.append(ingredient.prdlst_nm or name)
        else:
            name = (ingredient.ingredient_display_name
                    or ingredient.prdlst_nm or '').strip()
            name = compound_display(name, ingredient)

        if name:
            parts.append(name)

    text = ', '.join(parts)
    allergens, gmo = collect_allergens_and_gmo(relations)
    if allergens:
        # 인쇄되는 형태는 "밀, 우유 함유" 다 (label_preview.js 가 이 꼴을 읽는다)
        text += f"  [알레르기 성분: {', '.join(allergens)} 함유]"
    if gmo:
        text += f"  [GMO: {', '.join(gmo)}]"

    return {'text': text, 'needs_review': needs_review, 'count': len(parts)}
