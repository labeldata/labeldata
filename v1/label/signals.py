# -*- coding: utf-8 -*-
"""
원료를 저장하는 순간 영양성분을 붙여 본다.

왜 신호인가
───────────
원료를 만들고 고치는 자리가 여덟 곳이 넘는다(붙여넣기, 사진 판독, 표시사항에서
만들기, 공동 작업에서 가져오기, 첨가물에서 복사…). 그 자리마다 한 줄씩 넣으면
언젠가 하나를 빠뜨리고, 빠뜨린 자리는 **조용히** 값이 안 붙는다 — 터지지
않으므로 아무도 모른다.

왜 저장하는 순간인가
────────────────────
품목보고번호가 맞으면 **고를 것이 없다.** 같은 번호는 법적으로 같은 품목이다.
그런데 지금까지는 원료 상세를 하나씩 열어 눌러야 저장되는 구조였고, 실서버에서
값이 정해진 원료가 **0 개**였다. 고를 것이 없는데 손을 기다리고 있었다.

무엇을 하지 않는가
──────────────────
- **사람이 정한 값을 덮지 않는다.** 이미 값이 있으면 지나간다.
- **저장을 망치지 않는다.** 붙이다 실패해도 원료 저장은 끝난 상태다.
- **묶음 등록에는 안 걸린다.** bulk_create 는 post_save 를 부르지 않는다.
  엑셀 수백 줄을 붙여넣을 때 줄마다 질의를 더하지 않겠다는 뜻이고, 그건
  주기적으로 도는 `link_ingredient_nutrition` 이 나중에 훑는다.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='label.MyIngredient',
          dispatch_uid='label.link_ingredient_nutrition')
def link_nutrition_on_save(sender, instance, **kwargs):
    from v1.label.services import nutrition_candidates as ncd

    ncd.try_link_quietly(instance)
