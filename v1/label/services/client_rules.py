# -*- coding: utf-8 -*-
"""
화면에 내려 줄 규정값 — **그 라벨에 해당하는 것만.**

지금까지 이 값들은 static/js/label/constants.js 안에 통째로 박혀 있었다.
/static/ 은 로그인 없이 누구나 받으므로, 면적 임계값·글꼴 최소 크기·자간
범위·**식품유형별 필수 문구 표 전체**가 그대로 공개돼 있었다. 그 파일 주석에
이미 "백엔드에서 전달받을 예정" 이라고 적혀 있었다.

두 가지가 같이 해결된다.

  1. 표 전체가 나가지 않는다. 화면이 실제로 필요로 하는 건 **이 라벨의
     식품유형에 걸리는 문구 몇 줄**이지 표 전체가 아니다.
  2. 기준값이 한 곳이 된다. 서버 LABEL_REGULATIONS 와 constants.js 에 같은
     숫자가 두 벌 있었고, 두 벌로 두면 어느 날 한쪽만 고쳐진다.

내려 주는 방법은 fetch 가 아니라 **페이지에 심는 것**이다. 검증이 첫 렌더에
바로 돌기 때문에, 비동기로 받으면 아직 안 온 사이에 빈 표로 판정한다.
이미 쓰고 있는 방식이 있다 — expiry-recommendation-data 와 같은 자리.
"""
from v1.label.constants import LABEL_REGULATIONS


def phrases_for(food_type):
    """
    이 식품유형에 걸리는 필수 표시 문구만.

    화면 쪽 판정은 `foodType.includes(key)` 다 — 표 전체를 훑어 부분 문자열로
    맞춘다. 그 판정을 여기로 옮겨 온다. 맞는 것이 없으면 빈 표가 나가고,
    그러면 밖에서는 이 제품에 걸리는 문구가 없다는 것만 알 수 있다.
    """
    table = LABEL_REGULATIONS.get('food_type_phrases') or {}
    name = str(food_type or '')
    return {key: list(value) for key, value in table.items() if key and key in name}


def for_label(food_type=None):
    """
    미리보기 화면이 읽는 것만 담아서 돌려준다.

    지금 화면이 실제로 읽는 키는 셋뿐이다(REGULATIONS.font_size,
    .food_type_phrases, .expiry_recommendation). spacing·area_thresholds·font
    는 constants.js 에 있었지만 아무도 읽지 않았다 — 안 쓰는 것을 내보낼
    이유가 없다. expiry_recommendation 은 예전부터 뷰가 따로 심는다.
    """
    return {
        'font_size': {
            kind: dict(rule)
            for kind, rule in (LABEL_REGULATIONS.get('font_size') or {}).items()
        },
        'food_type_phrases': phrases_for(food_type),
    }
