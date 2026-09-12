# -*- coding: utf-8 -*-
"""
만들어만 놓고 손대지 않은 제품을 가려낸다.

[새로 만들기] 를 누르면 **그 순간 MyLabel 이 만들어진다.** 등록 폼을 먼저
보여 주던 시절에는 저장해야 생겼는데, 그때는 붙일 제품이 없어서 사진 불러오기·
BOM·문서함이 아무것도 되지 않았다. 그래서 먼저 만드는 쪽으로 바꿨고,
**빈 제품이 쌓이는 것이 그 대가**다.

지금까지는 `cleanup_temp_labels` 가 30 일 뒤에 치웠다. 그동안 목록에 남아
있는 것이 문제다 — 열어만 보고 닫은 사용자에게 제 목록이 쓰레기로 보인다.

**떠날 때 그 자리에서 치운다.** 판정은 여기 한 곳에서만 한다 — 배치와 즉시
정리가 서로 다른 기준을 쓰면, 한쪽이 지운 것을 다른 쪽이 안 지우거나 그 반대가
된다.

무엇을 "손대지 않았다" 고 보는가
────────────────────────────────
필드를 나열하지 않고 **모델 기본값과 견준다.** 필드가 늘어도 여기를 고칠 일이
없고, 사용자가 뭐라도 입력했으면 기본값과 달라지므로 후보에서 빠진다.

여기에 **딸린 것까지 본다**. 표시사항 칸은 하나도 안 채웠지만 BOM 에 원료를
붙여 넣었거나 문서를 올렸을 수 있다. 그건 손댄 것이다.
"""
import logging

logger = logging.getLogger(__name__)

TEMP_PREFIX = '임시 - 제품명 - '

# 내용과 무관한 필드. 이것들이 달라도 "손댔다" 고 보지 않는다.
SKIP_FIELDS = {
    'my_label_id', 'user_id', 'my_label_name',
    'create_datetime', 'update_datetime',
    'delete_YN', 'delete_datetime',
    'display_order',
}


def fields_untouched(label, blank=None):
    """저장 안 한 기본값 인스턴스와 견줘 하나라도 다르면 False."""
    from v1.label.models import MyLabel

    if blank is None:
        blank = MyLabel()
    for field in MyLabel._meta.fields:
        if field.name in SKIP_FIELDS:
            continue
        if getattr(label, field.attname, None) != getattr(blank, field.attname, None):
            return False
    return True


def has_children(label):
    """BOM 줄·문서·공유 중 하나라도 있으면 손댄 것이다."""
    from v1.bom.models import ProductBOM
    from v1.products.models import ProductDocument, ProductShare

    if ProductBOM.objects.filter(parent_label=label).exists():
        return True
    if ProductDocument.objects.filter(label=label).exists():
        return True
    if ProductShare.objects.filter(label=label).exists():
        return True
    return False


def is_untouched(label):
    """
    이 제품을 지워도 되는가.

    이름이 아직 '임시 - 제품명 - N' 이고, 표시사항 칸이 전부 기본값이고,
    딸린 것도 없어야 한다. **셋 중 하나라도 아니면 남긴다** — 잘못 지우는 것이
    쓰레기가 남는 것보다 훨씬 나쁘다.
    """
    if not (label.my_label_name or '').startswith(TEMP_PREFIX):
        return False
    if not fields_untouched(label):
        return False
    return not has_children(label)


def discard(label):
    """
    **정말로 지운다.**

    처음에는 delete_YN 만 'Y' 로 바꿨다. MyLabel 을 지우면 BOM·문서함·공유·
    알림까지 CASCADE 로 함께 사라지기 때문이었다. 그런데 **여기서 지우는 것은
    그 조건을 이미 통과한 것들**이다 — is_untouched 가 BOM 줄도, 문서도,
    공유도 없다는 것을 보고 온다. 딸려 갈 것이 아무것도 없다.

    숨기기만 하면 휴지통에 빈 제품이 쌓인다. 열어만 보고 닫은 것을 되살릴
    일은 없는데, 되살릴 수 있게 두느라 쓰레기가 남는다.

    **반드시 is_untouched 를 통과한 것만 넘긴다.** 이 함수는 다시 묻지 않는다.
    """
    pk = label.pk
    label.delete()
    logger.info('빈 제품 삭제: label=%s', pk)
