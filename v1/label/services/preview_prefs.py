# -*- coding: utf-8 -*-
"""
미리보기 화면을 **그 사람이 어떻게 보는가**.

제품마다가 아니라 계정에 남긴다. 미리보기의 가로·글꼴·자간은 제품마다
따로다(`MyLabel.prv_*`) — 그것은 **그 제품의 인쇄물이 어떻게 생겼는가**
이기 때문이다. 여기 있는 것은 인쇄물을 바꾸지 않는다. 화면에서 무엇을
접어 두고 일하느냐이고, 그것은 제품이 아니라 사람에게 붙는다. 제품이
이백 개면 이백 번 켜야 하는 설정은 아무도 쓰지 않는다.

같은 자리를 쓰는 선례 — 원료 목록의 칸 순서(`common.views.grid_order_save`),
디자인 의뢰서의 규정 메모(`design_request.save_notes`). 셋 다
`UserProfile.list_prefs` 안에서 화면 이름으로 나뉜다.
"""

SCREEN = 'label_preview'
HIDE_NUTRITION = 'hide_nutrition'


def hide_nutrition(user):
    """이 사람이 화면에서 영양정보 표를 접어 두었나."""
    try:
        prefs = (getattr(user, 'profile', None).list_prefs or {})
        return bool((prefs.get(SCREEN) or {}).get(HIDE_NUTRITION))
    except Exception:
        # 프로필이 없거나 값이 깨져 있어도 미리보기는 떠야 한다.
        return False


def save_hide_nutrition(user, hidden):
    """
    접어 둘지를 계정에 남긴다.

    Returns: 남긴 값(bool). 프로필이 없으면 None — 부를 쪽이 구분해야 한다.
    """
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    value = bool(hidden)
    prefs = dict(profile.list_prefs or {})
    prefs[SCREEN] = dict(prefs.get(SCREEN) or {}, **{HIDE_NUTRITION: value})
    profile.list_prefs = prefs
    profile.save(update_fields=['list_prefs'])
    return value
