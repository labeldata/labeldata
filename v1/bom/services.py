"""
BOM 과 표시사항 원재료(LabelIngredientRelation)를 잇는 부분.

BOM 표는 ProductBOM 에, 표시사항이 실제로 인쇄하는 원재료는
LabelIngredientRelation 에 있다. 둘을 잇는 것은 ProductBOM.source_ingredient
(-> MyIngredient) 하나뿐이라, 이 FK 가 비어 있는 BOM 행은 표시사항 쪽에서
아예 보이지 않는다.

이 동기화는 원래 bom_save_api 안에 인라인으로 있었다. 서류에서 뽑은 원재료를
BOM 에 넣는 경로(document_ai_apply_to_bom)에서도 같은 일이 필요해져서 꺼냈다.
그 경로는 source_ingredient 를 채우지 않아서, AI 가 원재료를 읽어와도 표시사항
원재료로는 한 줄도 들어가지 않았다.
"""
from v1.label.models import LabelIngredientRelation


def sync_relations_from_bom(label):
    """
    BOM(active) 을 표시사항 원재료에 반영한다.

    source_ingredient 가 없는 BOM 행은 건너뛴다 — 어떤 MyIngredient 를 가리키는지
    모르면 relation 을 만들 수 없다.

    Returns: (연결된 건수, source_ingredient 가 없어 건너뛴 건수)
    """
    from v1.bom.models import ProductBOM

    boms = (ProductBOM.objects
            .filter(parent_label=label, active_yn=True)
            .select_related('source_ingredient')
            .order_by('sort_order', 'bom_id'))

    linked = [b for b in boms if b.source_ingredient_id]
    skipped = boms.count() - len(linked)

    # BOM 에서 빠진 원료는 표시사항에서도 빠져야 한다
    LabelIngredientRelation.objects.filter(label=label).exclude(
        ingredient_id__in={b.source_ingredient_id for b in linked}
    ).delete()

    for seq, bom in enumerate(linked, start=1):
        LabelIngredientRelation.objects.update_or_create(
            label=label,
            ingredient_id=bom.source_ingredient_id,
            defaults={
                'ingredient_ratio': bom.usage_ratio,
                'relation_sequence': seq,
            },
        )
    return len(linked), skipped
