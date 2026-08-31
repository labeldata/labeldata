"""
판독이 **어디에서** 읽었는지를 다룬다 — 좌표를 받고, 되돌리고, 채점한다.

지금까지 응답에는 값만 있었다. 그래서 값이 틀렸을 때 알 수 있는 것은 "틀렸다"
뿐이고, **왜** 틀렸는지 — 옆 칸을 읽었는지, 작업지시서의 표를 읽었는지, 아예
못 찾았는지 — 는 알 수 없었다.

여기서 하는 일은 셋이다.

  1. 물어본다   항목마다 `bbox` 를 함께 달라고 한다. 조각을 보내므로 **어느
                이미지 기준인지**(`img`)도 같이 받는다.
  2. 되돌린다   조각 좌표를 원본 사진 좌표로 옮긴다. 조각을 어디서 잘랐는지는
                우리가 알고 있으니 계산으로 된다.
  3. 잰다       정답 위치와 겹치는 정도(IoU)로 채점한다.

**값과 위치는 따로 판정한다.** 좌표가 틀렸다고 값을 버리지 않는다 — 값이
본질이고 위치는 그 값을 확인하기 위한 편의다. 반대로 위치가 맞았다고 값을
믿지도 않는다.

**못 잡으면 null 이다.** 없는 좌표를 지어내면 사람을 엉뚱한 데로 보낸다.
값을 지어내는 것과 같은 병이고, 여기서는 "맞는 값에 틀린 상자" 라는 더 나쁜
모양으로 나온다 — 멀쩡한 값을 의심해서 지우게 된다.
"""
import logging

logger = logging.getLogger(__name__)

# 좌표는 0~1000 으로 정규화해서 받는다.
#
# 픽셀로 달라고 하면 모델이 이미지의 실제 크기를 알아야 하는데, 우리는 보내기
# 전에 리사이즈하므로 모델이 보는 크기와 원본 크기가 다르다. 정규화하면 그
# 차이가 사라진다. 그리고 소수점 대신 정수라 출력 토큰도 덜 쓴다.
SCALE = 1000

# 잘라 다시 읽을 때 상자 둘레에 붙이는 여백(상자 크기 대비).
#
# 모델이 준 상자는 글자에 딱 붙어 있기 쉽다. 딱 잘라 보내면 항목명이 잘려
# 나가서 "이게 무슨 항목인지" 를 모델이 알 수 없다 — 값만 덩그러니 보인다.
REREAD_PAD = 0.12


PROMPT_ADDENDUM = """

읽은 자리도 함께 알려주시오 (위치 표시용).

  항목마다 값 옆에 두 가지를 더 적는다.
    "img"  그 값을 읽은 이미지의 번호. 첫 장(전체 사진)이 0, 조각은 1, 2, 3, 4
    "bbox" 그 이미지 안에서의 위치 [x, y, 너비, 높이]
           **0~1000 으로 정규화한 정수**다. 이미지 왼쪽 끝이 0, 오른쪽 끝이 1000,
           위쪽 끝이 0, 아래쪽 끝이 1000 이다. 픽셀이 아니다.

  예: {"value": "별도표기일까지", "confidence": "high", "img": 2, "bbox": [420, 610, 260, 40]}

  상자는 **그 항목의 값이 적힌 글자만** 감싼다. 항목명("소비기한")은 넣지 않는다.
  값이 여러 줄이면(원재료명·주의사항) 그 여러 줄 전체를 감싸는 하나의 상자다.

  **위치를 짚을 수 없으면 bbox 를 넣지 마시오.** 값은 읽혔는데 어디였는지
  자신이 없으면 값만 적고 bbox 는 빼면 된다. 대충 찍은 상자는 없는 것만
  못하다 — 사람을 엉뚱한 자리로 보낸다.

  **위치 때문에 값을 흐리게 하지 마시오.** 값이 먼저다. 위치를 맞추느라 값을
  덜 읽는 것은 완전히 잘못된 맞바꿈이다.
"""


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_box(raw):
    """
    모델이 준 bbox 를 정규화 좌표 (x, y, w, h) 로. 못 읽으면 None.

    dict 로 주는 경우가 있어 함께 받는다 — 형식을 하나로 못 박아도 가끔 다르게
    온다. 여기서 거절하면 위치가 통째로 사라진다.
    """
    if isinstance(raw, dict):
        raw = [raw.get('x'), raw.get('y'),
               raw.get('w', raw.get('width')), raw.get('h', raw.get('height'))]
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None

    values = [_num(v) for v in raw]
    if any(v is None for v in values):
        return None
    x, y, w, h = values
    if w <= 0 or h <= 0:
        return None
    # 1000 을 넘겨 오거나 음수로 시작하는 상자가 있다. 이미지 밖은 잘라 낸다.
    x, y = max(0.0, x), max(0.0, y)
    w = min(w, SCALE - x)
    h = min(h, SCALE - y)
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def to_original(box, region):
    """
    조각 안의 정규화 좌표를 **원본 사진의 픽셀 좌표**로 옮긴다.

    region 은 그 조각을 원본에서 어디서 잘랐는지다: (left, top, right, bottom).
    조각을 우리가 잘랐으니 이 값은 확실하다 — 여기서 틀릴 일은 없다.

    Returns: [x, y, w, h] (원본 픽셀, 정수)
    """
    if not box or not region:
        return None
    left, top, right, bottom = region
    span_x, span_y = right - left, bottom - top
    if span_x <= 0 or span_y <= 0:
        return None

    x, y, w, h = box
    return [
        int(round(left + x / SCALE * span_x)),
        int(round(top + y / SCALE * span_y)),
        max(1, int(round(w / SCALE * span_x))),
        max(1, int(round(h / SCALE * span_y))),
    ]


def attach(data, regions):
    """
    판독 결과의 img/bbox 를 원본 좌표 `box` 로 바꿔 넣는다.

    **원본은 건드리지 않고** 새 dict 를 돌려준다. 좌표를 못 읽은 항목은 box 가
    없다 — 있는 척하지 않는다.

    Returns: (새 data, 좌표를 붙인 항목 수)
    """
    if not regions:
        return dict(data or {}), 0

    out = {}
    found = 0
    for key, item in (data or {}).items():
        if not isinstance(item, dict):
            out[key] = item
            continue

        row = dict(item)
        box = parse_box(row.pop('bbox', None))
        index = row.pop('img', 0)
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = 0

        if box is not None and 0 <= index < len(regions):
            mapped = to_original(box, regions[index]['box'])
            if mapped:
                row['box'] = mapped
                # 어느 조각에서 읽었는지도 남긴다. 조각에서만 읽히는 항목이
                # 무엇인지 알면 조각을 언제 붙여야 하는지 답할 수 있다.
                row['box_from'] = regions[index]['label']
                found += 1
        out[key] = row
    return out, found


def clamp(box, width, height):
    """상자를 사진 안으로 밀어 넣는다. 밖으로 나간 상자는 자를 수 없다."""
    if not box or len(box) != 4:
        return None
    try:
        x, y, w, h = (int(round(float(v))) for v in box)
    except (TypeError, ValueError):
        return None
    x = max(0, min(x, max(0, width - 1)))
    y = max(0, min(y, max(0, height - 1)))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return [x, y, w, h]


def pad(box, width, height, ratio=REREAD_PAD):
    """다시 읽을 영역에 여백을 붙인다. 항목명이 잘리면 무슨 항목인지 모른다."""
    box = clamp(box, width, height)
    if not box:
        return None
    x, y, w, h = box
    dx, dy = int(w * ratio), int(h * ratio)
    return clamp([x - dx, y - dy, w + dx * 2, h + dy * 2], width, height)


def iou(a, b):
    """
    두 상자가 얼마나 겹치는가 (0~100).

    IoU 를 쓴다 — 한쪽이 다른 쪽을 품기만 해도 100 이 되는 방식은 "사진 전체를
    상자로 준" 답에 만점을 준다.
    """
    a, b = (a or None), (b or None)
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0
    overlap = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - overlap
    if union <= 0:
        return 0
    return int(round(overlap / union * 100))


# 상자가 "맞았다" 고 볼 겹침.
#
# 사람이 손으로 그린 정답 상자는 여백이 제각각이라 0.5 를 요구하면 맞는 상자도
# 떨어진다. 여기서 재는 것은 "정확히 같은 상자인가" 가 아니라 **"같은 자리를
# 가리키는가"** 다 — 사람이 그 자리를 보러 갈 수 있으면 된 것이다.
BOX_HIT_IOU = 30


def score(expected_boxes, data):
    """
    위치를 채점한다. **값 채점과 섞지 않는다.**

    정답 위치가 적힌 항목만 센다. 안 적어 둔 항목은 "위치를 모른다" 는 뜻이지
    "위치가 틀렸다" 는 뜻이 아니다.

    Returns: {
        'fields': [{'field','iou','hit','expected','actual'} …],
        'mean': 평균 겹침,
        'hit_rate': 같은 자리를 가리킨 비율,
        'missing': [상자를 아예 못 준 항목 …],
    }
    """
    rows, missing = [], []
    for field, expected in (expected_boxes or {}).items():
        expected = clamp_free(expected)
        if not expected:
            continue
        item = (data or {}).get(field)
        actual = clamp_free(item.get('box')) if isinstance(item, dict) else None
        if not actual:
            missing.append(field)
        overlap = iou(expected, actual)
        rows.append({'field': field, 'iou': overlap,
                     'hit': overlap >= BOX_HIT_IOU,
                     'expected': expected, 'actual': actual})

    if not rows:
        return {'fields': [], 'mean': 0.0, 'hit_rate': 0.0, 'missing': []}
    hits = sum(1 for r in rows if r['hit'])
    return {
        'fields': sorted(rows, key=lambda r: r['iou']),
        'mean': round(sum(r['iou'] for r in rows) / len(rows), 1),
        'hit_rate': round(hits / len(rows) * 100, 1),
        'missing': missing,
    }


def clamp_free(box):
    """사진 크기를 모를 때 쓰는 형식 검사. 숫자 네 개가 아니면 None."""
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        values = [int(round(float(v))) for v in box]
    except (TypeError, ValueError):
        return None
    if values[2] <= 0 or values[3] <= 0:
        return None
    return values
