"""
서류에서 뽑은 원재료 문자열을 "내 원료" 에 붙이는 부분.

vision_service 가 성적서·품목제조보고서에서 raw_materials / blend_ratios /
origins / allergens 를 구조화해서 돌려준다. 그 결과가 여태 표시사항 원재료로
들어가지 못한 이유는 두 가지였다.

  1. 뽑은 이름이 "내 원료" 에 이미 있는 원료와 같은 것인지 판단하지 못했다.
     그래서 붙일 원료를 못 정하고, 붙일 원료가 없으면 relation 도 못 만든다.
  2. 서류의 원재료명은 표기가 흔들린다 — "탈지분유(우유)", "정제소금 2%",
     "히드록시프로필전분 87%" 처럼 괄호와 함량이 섞여 온다.

여기서는 이름을 씻어 내고(normalize_name), 사용자의 기존 원료와 견줘
(match_my_ingredient) 충분히 비슷하면 그것을 쓰고, 아니면 새로 만든다.

**판정은 사람이 한다.** 점수가 낮으면 새로 만들되 어떤 후보가 있었는지 함께
돌려준다. BOM 편집 화면에서 확인·수정하는 것이 원래 흐름이다.
"""
import re
import unicodedata

from rapidfuzz import fuzz, process

from v1.label.models import MyIngredient

# 이 점수 이상이면 같은 원료로 본다. 100 점 만점.
# 90 은 "정제소금" vs "정제 소금" 같은 표기 흔들림은 묶고,
# "대두유" vs "대두단백" 같은 다른 원료는 가르는 선이다.
MATCH_THRESHOLD = 90

# 이름 뒤에 붙어 오는 함량 표기: "정제소금 2%", "전분 87 %"
_TRAILING_RATIO = re.compile(r'[\s,]*\d+(?:\.\d+)?\s*%\s*$')
# 괄호 안 부연: "탈지분유(우유)" -> 괄호 내용은 하위원료/알레르기라 이름에서 뺀다
_PARENS = re.compile(r'[(（][^)）]*[)）]')
_SPACES = re.compile(r'\s+')


def parse_ratio(value):
    """'87%' · '87' · 87 -> 87.0. 못 읽으면 None."""
    if value is None or value == '':
        return None
    try:
        return float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def split_name_and_ratio(text):
    """
    "히드록시프로필전분 87%" -> ("히드록시프로필전분", 87.0)

    blend_ratios 에 따로 오지 않고 원재료명에 붙어 오는 경우가 많다.
    """
    raw = (text or '').strip()
    if not raw:
        return '', None
    m = _TRAILING_RATIO.search(raw)
    if not m:
        return raw, None
    return raw[:m.start()].strip(' ,'), parse_ratio(m.group(0))


def clean_material_name(text):
    """
    "탈지분유(우유) 30%" -> "탈지분유"

    괄호 안은 하위 원료·알레르기 설명이라 sub_ingredients_of() 가 따로 가져간다.
    이름에까지 남겨 두면 "탈지분유" 와 "탈지분유(우유)" 가 서로 다른 원료로
    쌓인다. 괄호를 떼서 아무것도 안 남으면(이름 전체가 괄호였으면) 원문을 쓴다.
    """
    name, _ = split_name_and_ratio(text)
    stripped = _SPACES.sub(' ', _PARENS.sub('', name)).strip(' ,')
    return stripped or name


def normalize_name(text):
    """비교용으로만 쓰는 형태. 화면에는 원문을 그대로 보여준다."""
    s = unicodedata.normalize('NFKC', text or '')
    s = _TRAILING_RATIO.sub('', s)
    s = _PARENS.sub('', s)
    s = _SPACES.sub('', s)
    return s.strip().lower()


def sub_ingredients_of(text):
    """"탈지분유(우유, 유당)" -> "우유, 유당". 괄호가 없으면 빈 문자열."""
    found = _PARENS.findall(text or '')
    inner = ', '.join(f.strip('()（） ') for f in found)
    return inner.strip()


def attributed_allergens(material_text, allergens):
    """
    서류의 알레르기 목록 중 **이 원재료 안에 실제로 이름이 보이는 것**만 준다.

    allergens 는 제품 전체 목록이라, 예전처럼 모든 행에 통째로 붙이면
    "정제수" 에까지 우유·대두가 달린다. 표시 문구와 알레르기 요약이 그대로
    틀어지므로 근거가 보이는 것만 붙인다. 나머지는 사람이 BOM 에서 채운다.
    """
    if not allergens:
        return ''
    haystack = normalize_name(material_text) + normalize_name(sub_ingredients_of(material_text))
    # 괄호를 지우기 전 원문도 본다 — 알레르기는 보통 괄호 안에 적힌다
    haystack += _SPACES.sub('', (material_text or '')).lower()
    hits = [a for a in allergens if a and normalize_name(a) and normalize_name(a) in haystack]
    return ', '.join(dict.fromkeys(hits))


def get_or_create_my_ingredient(user, *, prdlst_nm, prdlst_report_no, prdlst_dcnm,
                                **defaults):
    """
    같은 원료를 두 번 만들지 않는다.

    지금까지 라벨마다 새 MyIngredient 를 만들어서, 운영 데이터에 같은 원료가
    13개씩 쌓여 있었다(548건 중 여분 108건, 19.7%). 원료 검색 결과가 같은 이름으로
    도배되고, 하나를 고쳐도 다른 라벨은 옛 값을 본다.

    키는 (사용자, 원료명, 품목보고번호, 식품유형) 이다 — 이름만으로는 제조사가
    다른 같은 이름을 하나로 묶어 버린다.

    **이미 있으면 그대로 쓴다. 넘어온 값으로 덮어쓰지 않는다.**
    MyIngredient 는 여러 라벨이 함께 쓰는 레코드라, 한 라벨에서 저장했다고 다른
    라벨이 보던 값이 바뀌면 안 된다. 원료 자체를 고칠 곳은 "내 원료 상세" 다.

    Returns: (ingredient, created)
    """
    return MyIngredient.objects.get_or_create(
        user_id=user,
        prdlst_nm=prdlst_nm or '',
        prdlst_report_no=prdlst_report_no or '',
        prdlst_dcnm=prdlst_dcnm or '',
        delete_YN='N',
        defaults=defaults,
    )


def match_my_ingredient(user, name, *, threshold=MATCH_THRESHOLD, pool=None):
    """
    사용자의 기존 원료 중 가장 비슷한 것을 찾는다.

    Returns: (MyIngredient 또는 None, 점수 0~100, 후보 이름 목록)

    pool 을 넘기면 그것을 쓴다 — 여러 원재료를 한 번에 붙일 때 사용자 원료를
    매번 다시 읽지 않기 위해서다.
    """
    key = normalize_name(name)
    if not key:
        return None, 0, []

    if pool is None:
        pool = load_pool(user)
    if not pool:
        return None, 0, []

    keys = list(pool.keys())
    best = process.extract(key, keys, scorer=fuzz.WRatio, limit=3)
    if not best:
        return None, 0, []

    top_key, top_score, _ = best[0]
    candidates = [pool[k][0].prdlst_nm for k, s, _ in best if s >= 60]
    if top_score >= threshold:
        return pool[top_key][0], int(top_score), candidates
    return None, int(top_score), candidates


def load_pool(user):
    """비교용 사용자 원료 사전: {정규화 이름: [MyIngredient, ...]}"""
    pool = {}
    for ing in MyIngredient.objects.filter(user_id=user, delete_YN='N'):
        key = normalize_name(ing.prdlst_nm)
        if key:
            pool.setdefault(key, []).append(ing)
    return pool
