"""
판독값을 **정해진 목록**에 맞춰 준다.

식품유형과 알레르기 유발물질은 아무 말이나 쓸 수 있는 값이 아니다. 식품유형은
「식품의 기준 및 규격」이 정한 목록이고, 알레르기는 표시기준이 정한 22종이다.
주의사항과 기타표시사항도 대부분 우리가 만들어 둔 상용 문구다
(`label_phrases.py`). 그런데 지금까지는 판독 결과를 자유 문구 그대로 받았다.

그래서 한 글자 차이가 그대로 남는다.

    판독 "즉석섭취식품류"  ->  실제 유형 "즉석섭취식품"
    판독 "대두류"          ->  알레르기 "대두"

이 값들은 뒤에서 **키로 쓰인다.** 식품유형은 유형별 표시항목 규칙을 찾는 키이고,
알레르기는 원재료에서 검출한 것과 대조하는 키다. 한 글자가 어긋나면 규칙을 못
찾고, 못 찾은 것을 화면은 "해당 규칙 없음" 으로 조용히 넘긴다.

**모호하면 손대지 않는다.** 1등과 2등이 엇비슷하면 사람이 골라야 한다 — 틀린
쪽으로 스냅하면 판독이 맞았을 때보다 더 나쁘다. 무엇을 바꿨는지는 언제나
snapped_from 에 남겨 확인 창이 보여 준다.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# 몇 글자까지 고쳐서 맞출 것인가. 이름 길이에 따라 다르다.
#
# 비율(fuzz.ratio)만 쓰면 짧은 이름에서 무너진다 — "대두류"→"대두" 는 한 글자
# 차이인데 세 글자 중 하나라 80점밖에 안 나온다. 반대로 긴 이름은 두세 글자가
# 달라도 비율이 높게 나와서 다른 유형으로 끌려간다.
# 그래서 **고친 글자 수**를 기준으로 하고, 이름이 길수록 예산을 늘린다.
def _edit_budget(length):
    if length <= 4:
        return 1
    if length <= 10:
        return 2
    return 3


# 후보가 둘 이상 같은 거리에 있으면 손대지 않는다. 어느 쪽인지 알 수 없다.
SNAP_MIN_SCORE = 60      # 거리는 가까운데 뜻이 전혀 다른 경우를 거르는 하한

_FOOD_TYPE_CACHE_KEY = 'ocr_snap:food_types'
_FOOD_TYPE_CACHE_TTL = 60 * 60 * 6


def _ratio(a, b):
    try:
        from rapidfuzz import fuzz
    except ImportError:      # 사전 대조를 못 할 뿐, 판독은 계속돼야 한다
        return 100 if a == b else 0
    return fuzz.ratio(a, b)


def _distance(a, b):
    """고쳐야 하는 글자 수. rapidfuzz 가 없으면 같은지 여부만 본다."""
    try:
        from rapidfuzz.distance import Levenshtein
    except ImportError:
        return 0 if a == b else 99
    return Levenshtein.distance(a, b)


def _squeeze(text):
    return ''.join(str(text or '').split()).lower()


def food_type_vocabulary():
    """
    식품유형 목록. FoodType 마스터를 쓰고, 비었으면 등록 품목에서 캔다.

    조회에 실패하면 빈 목록이다 — 사전이 없으면 스냅을 안 할 뿐, 판독은 그대로
    돌아야 한다.
    """
    cached = cache.get(_FOOD_TYPE_CACHE_KEY)
    if cached is not None:
        return cached

    names = set()
    try:
        from v1.label.models import FoodItem, FoodType
        names.update(
            FoodType.objects.exclude(food_type__isnull=True)
            .exclude(food_type='').values_list('food_type', flat=True))
        if not names:
            names.update(
                FoodItem.objects.exclude(prdlst_dcnm__isnull=True)
                .exclude(prdlst_dcnm='')
                .values_list('prdlst_dcnm', flat=True).distinct())
    except Exception:
        logger.exception('식품유형 사전 조회 실패 — 스냅 없이 계속한다')

    names = sorted(n.strip() for n in names if n and n.strip())
    cache.set(_FOOD_TYPE_CACHE_KEY, names, _FOOD_TYPE_CACHE_TTL)
    return names


def allergen_vocabulary():
    """표시기준이 정한 알레르기 유발물질 22종."""
    from v1.label.constants import ALLERGEN_KEYWORDS
    return sorted(ALLERGEN_KEYWORDS.keys())


def snap_one(value, vocabulary):
    """
    값 하나를 목록에 맞춰 본다.

    Returns: (맞춘 값, 점수, 판정)
        'exact'     이미 목록에 있다 (건드리지 않는다)
        'snapped'   한 글자 차이 정도라 맞췄다
        'ambiguous' 두 후보가 엇비슷하다 — 손대지 않는다
        'unknown'   목록에 비슷한 것이 없다 — 손대지 않는다
    """
    text = str(value or '').strip()
    if not text or not vocabulary:
        return text, 0, 'unknown'

    squeezed = _squeeze(text)
    scored = sorted(
        ((_distance(squeezed, _squeeze(name)), name) for name in vocabulary),
        key=lambda pair: (pair[0], len(pair[1]), pair[1]),
    )
    best_distance, best = scored[0]
    if best_distance == 0:
        return best, 100, 'exact'

    budget = _edit_budget(max(len(squeezed), len(_squeeze(best))))
    score = _ratio(squeezed, _squeeze(best))
    if best_distance > budget or score < SNAP_MIN_SCORE:
        return text, score, 'unknown'

    # 같은 거리에 후보가 둘 이상이면 어느 쪽인지 알 수 없다. "곡류가공품" 과
    # "곡류가공품류" 처럼 목록 안에도 닮은 이름이 있어서, 임의로 고르면 규칙을
    # 엉뚱한 유형에서 찾아온다.
    if len(scored) > 1 and scored[1][0] == best_distance:
        return text, score, 'ambiguous'
    return best, score, 'snapped'


def snap_allergens(value):
    """
    "우유, 대두류, 밀 함유" -> ("우유, 대두, 밀", [바꾼 것])

    쉼표로 갈라 하나씩 맞춘다. 목록에 없는 것은 지우지 않고 그대로 둔다 —
    표시기준 22종 밖의 문구를 적어 두는 라벨이 있고, 지우면 정보가 사라진다.
    """
    import re

    text = str(value or '').strip()
    if not text:
        return '', []

    vocabulary = allergen_vocabulary()
    changes = []
    out = []
    for token in re.split(r'[,、，/]', text):
        token = re.sub(r'\s*함유\s*$', '', token).strip()
        if not token:
            continue
        snapped, score, verdict = snap_one(token, vocabulary)
        if verdict == 'snapped':
            changes.append({'from': token, 'to': snapped, 'score': score})
            out.append(snapped)
        else:
            out.append(token)

    # 같은 물질이 두 번 들어오는 일이 있다("대두류, 대두"). 스냅하면 겹치므로
    # 순서를 지키며 중복만 지운다.
    seen, unique = set(), []
    for name in out:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return ', '.join(unique), changes


def snap(ocr_data):
    """
    판독 결과에서 **정해진 목록을 가진 항목**만 맞춰 준다.

    원본은 건드리지 않고 새 dict 를 돌려준다. 바꾼 값에는 snapped_from 을 남겨
    확인 창이 "판독은 이랬는데 목록의 이것으로 맞췄다" 를 보여 줄 수 있게 한다.

    Returns: (새 data, [{'field','label','from','to','score'} …])
    """
    data = dict(ocr_data or {})
    report = []

    def value_of(key):
        item = data.get(key)
        if isinstance(item, dict):
            return str(item.get('value') or '').strip()
        return str(item or '').strip()

    def write(key, new_value, note):
        item = data.get(key)
        item = dict(item) if isinstance(item, dict) else {'value': new_value,
                                                          'confidence': 'high'}
        item['snapped_from'] = note['from']
        if note.get('note'):
            item['snapped_note'] = note['note']
        item['value'] = new_value
        data[key] = item

    # 식품유형 — 유형별 표시항목 규칙을 찾는 키다. 한 글자가 어긋나면 규칙을
    # 통째로 못 찾고, 화면은 그것을 "규칙 없음" 으로 조용히 넘긴다.
    current = value_of('prdlst_dcnm')
    if current:
        snapped, score, verdict = snap_one(current, food_type_vocabulary())
        if verdict == 'snapped':
            note = {'field': 'prdlst_dcnm', 'label': '식품유형',
                    'from': current, 'to': snapped, 'score': score}
            write('prdlst_dcnm', snapped, note)
            report.append(note)

    # 알레르기 — 원재료에서 검출한 것과 대조하는 키다. 표기가 어긋나면 이미
    # 선언한 물질을 "선언 안 됨" 으로 지적하게 된다.
    current = value_of('allergens')
    if current:
        snapped, changes = snap_allergens(current)
        # **changes 를 조건으로 걸면 안 된다.** snap_allergens 는 목록에 맞추는
        # 일 말고도 "○○ 함유" 의 "함유" 를 떼고 중복을 지운다. 그 둘만 일어난
        # 경우 changes 가 비는데, 예전에는 그때 결과를 통째로 버려서
        # "돼지고기, 쇠고기 함유" 가 그대로 저장됐다. 알레르기는 뒤에서 키로
        # 쓰이므로 "쇠고기 함유" 는 어느 목록에서도 안 찾힌다.
        if snapped != current:
            note = {'field': 'allergens', 'label': '알레르기 유발물질',
                    'from': current, 'to': snapped,
                    'score': min((c['score'] for c in changes), default=100)}
            write('allergens', snapped, note)
            report.append(note)

    # 주의사항·기타표시사항 — 대부분 우리가 만들어 둔 상용 문구로 되어 있다.
    # 문장이 길어서 한두 글자가 뭉개져도 "그 문장" 인 것은 확실한데, 그 한두
    # 글자가 그대로 인쇄물에 들어간다. 문장이 거의 같으면 원문으로 확정한다.
    #
    # 여기서 확정하는 것은 **읽은 문장뿐**이다. 목록에 있다는 이유로 없는 문구를
    # 채우지는 않는다 - 그건 지어낸 값이다.
    from v1.label.services.label_phrases import FIELD_LABELS, snap_text

    for key, label in FIELD_LABELS.items():
        current = value_of(key)
        if not current:
            continue
        snapped, changes = snap_text(key, current)
        if changes and snapped != current:
            note = {'field': key, 'label': label,
                    'from': changes[0]['from'], 'to': changes[0]['to'],
                    'score': min(c['score'] for c in changes),
                    'note': f'자주 쓰는 {label} 문구 {len(changes)}건을 원문 그대로 맞췄습니다.'}
            write(key, snapped, note)
            report.append(note)

    return data, report


def _short(text, limit=28):
    """긴 문구는 잘라 보여 준다. 주의사항 한 문장이 80자를 넘는다."""
    text = str(text or '')
    return text if len(text) <= limit else text[:limit] + '…'


def summary(report):
    """확인 창 위에 한 줄로 띄울 문장. 바꾼 게 없으면 빈 문자열."""
    if not report:
        return ''
    parts = [f'{row["label"]} "{_short(row["from"])}" → "{_short(row["to"])}"'
             for row in report]
    return ('표시기준·상용 문구에 맞춰 고쳤습니다: ' + ', '.join(parts)
            + '. 잘못 맞췄다면 값을 직접 고쳐 주세요.')
