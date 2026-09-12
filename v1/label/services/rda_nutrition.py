# -*- coding: utf-8 -*-
"""
농촌진흥청 국가표준식품성분표 제10개정(DB 10.4)을 우리 표로 옮긴다.

왜 이 데이터인가
────────────────
식약처 적재본으로는 **원재료성 식품에 닿을 수 없다.** 실측이 그렇다.

    가공식품  294,238건   보고번호 76.3%
    음식       20,676건   보고번호  0.0%
    원재료성    4,146건   보고번호  0.0%   ← 밀가루·설탕·소금·양파

품목보고번호가 없으니 번호로는 영영 못 붙고, 적재본은 '수집'(업체 신고값)이
97 % 라 이름으로 찾아도 값이 흔들린다. 농진청 10.4 는 **3,366 건이 전부
분석값**이고, 식품군 분포가 어패류 683 · 채소 613 · 곡류 446 · 육류 436 …
으로 정확히 그 빈 구간이다.

엑셀에서 오는 것이라 API 도, 639 회 호출도, 일 한도도 없다.

두 가지가 식약처 API 보다 낫다
──────────────────────────────
  기준량   **전부 가식부 100g 당.** 식약처 적재본은 100mL 가 15.3 % 섞여 있어
           중량 배합에 그대로 쓸 수 없는 행을 골라내야 했다. 여기는 그 분기가 없다.
  열 이름  AMT_NUM1~157 번호가 아니라 **글자로 온다.** 명세를 옮겨 적다 한 칸
           밀려 엉뚱한 값이 조용히 들어가는 사고가 원천에서 사라진다.

없는 것도 적어 둔다
───────────────────
  **콜레스테롤이 없다.** 표시 아홉 중 여덟만 채운다. 나머지는 식약처 DB 나
  시험성적서로 채워야 한다.
  포화·트랜스지방은 '총 포화/트랜스 **지방산**' 열이다. 표시기준의 포화지방은
  지방산 합으로 계산하므로 대체로 맞지만, 같은 말은 아니다.
"""
import logging
import re

logger = logging.getLogger(__name__)

SHEET_MAIN = '국가표준식품성분 Database 10.4'
SHEET_NAMES = '부록2)식품코드,국문명,영문명,학명 정보 '

# 엑셀 열 머리글 → 우리 칸. 머리글은 공백을 지우고 견준다(줄바꿈이 섞여 있다).
#
# 없는 것을 억지로 채우지 않는다. 콜레스테롤은 이 표에 아예 없으므로 빈 채로
# 두고, 그 사실을 적재 결과에서 알린다.
COLUMNS = {
    '에너지':       'calories',
    '수분':         'moisture',
    '단백질':       'proteins',
    '지방':         'fats',
    '회분':         'ash',
    '탄수화물':     'carbohydrates',
    '당류':         'sugars',
    '총식이섬유':   'dietary_fiber',
    '칼슘':         'calcium',
    '철':           'iron',
    '마그네슘':     'magnesium',
    '인':           'phosphorus',
    '칼륨':         'potassium',
    '나트륨':       'natriums',
    '아연':         'zinc',
    '셀레늄':       'selenium',
    '총포화지방산': 'saturated_fats',
    '총트랜스지방산': 'trans_fats',
}

_WS = re.compile(r'\s+')


def _key(text):
    return _WS.sub('', str(text or ''))


def _num(v):
    """'-' · 'Tr'(미량) · 빈 칸은 값이 없는 것이다. 0 으로 적으면 거짓말이 된다."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(',', '')
    if not s or s in ('-', 'N/A'):
        return None
    if s.lower() in ('tr', 'trace'):
        return 0.0        # 미량은 실제로 0 에 가깝다. 이것만은 0 으로 본다
    try:
        return float(s)
    except ValueError:
        return None


# ── 학명으로 식품원료(A코드) 목록과 잇는다 ──────────────────────────────────
#
# AgriculturalProduct 는 신규 원료 등록에서 농수산물을 고르면 나오는 그 목록이다.
# 사용자가 이미 고른 것에서 곧바로 농진청 행까지 갈 수 있으므로, 적재할 때 한 번
# 이어 두면 작업 6 이 후보를 보일 때 **이름과 독립된 근거**로 쓸 수 있다.
#
# **값을 정하는 근거로는 쓰지 않는다.** 실측에서 오연결이 보였다.
#
#     귀리, 쌀귀리, 도정, 생것   학명 Avena nuda  →  '큰쌀귀리씨앗'   ← 엉뚱하다
#
# 학명이 같아도 우리 목록의 다른 항목에 붙을 수 있다. 그래서 가점과 꼬리표로만 쓴다.

def species(text):
    """학명을 속+종 두 낱말로. 명명자(L., Radlk)와 괄호는 뗀다."""
    s = re.sub(r'\(.*?\)', ' ', str(text or ''))
    s = re.sub(r'[^A-Za-z ]', ' ', s)
    w = [x for x in s.split() if len(x) > 2]
    return ' '.join(w[:2]).lower() if len(w) >= 2 else ''


def base_name(food_nm):
    """'귀리, 겉귀리, 도정, 생것' → '귀리'. 농진청 이름은 쉼표로 갈라 적는다."""
    return str(food_nm or '').split(',')[0].strip()


def agri_index():
    """식품원료 목록을 학명·이름(이명 포함)으로 찾을 수 있게 편다."""
    from v1.label.models import AgriculturalProduct

    by_sci, by_name = {}, {}
    for a in AgriculturalProduct.objects.all().iterator(chunk_size=1000):
        k = species(a.scnm)
        if k:
            by_sci.setdefault(k, a.pk)
        for name in [a.rprsnt_rawmtrl_nm] + re.split(r'[,;/]', a.rawmtrl_ncknm or ''):
            name = (name or '').strip()
            if name:
                by_name.setdefault(name, a.pk)
    return by_sci, by_name


def read_workbook(path):
    """
    엑셀을 읽어 우리 칸에 맞춘 dict 목록을 낸다. 저장하지 않는다.

    머리글은 2행, 단위는 3행, 값은 4행부터다.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    # 부록2 — 색인 → (식품코드, 학명)
    names = {}
    for r in wb[SHEET_NAMES].iter_rows(min_row=2, values_only=True):
        if r[0] is not None and r[1]:
            names[r[0]] = (str(r[1]).strip(), r[4])

    ws = wb[SHEET_MAIN]
    rows = ws.iter_rows(values_only=True)
    next(rows)                         # 1행: 묶음 머리글
    header = [_key(h) for h in next(rows)]
    next(rows)                         # 3행: 단위

    # 머리글 → 열 번호. 같은 이름이 여럿이면 **앞엣것**을 쓴다.
    at = {}
    for i, h in enumerate(header):
        if h in COLUMNS and h not in at:
            at[h] = i
    missing = [h for h in COLUMNS if h not in at]
    if missing:
        logger.warning('[농진청] 못 찾은 열: %s', ', '.join(missing))

    out = []
    for r in rows:
        idx, group, food_nm, origin = r[0], r[2], r[3], r[4]
        if not food_nm:
            continue
        code, scnm = names.get(idx, ('', None))
        if not code:
            # 부록2 에 없으면 식품코드가 없다. 고유키가 없으면 넣지 않는다 —
            # 다시 적재할 때 같은 행이 쌓인다.
            continue
        item = {
            'food_cd': code,
            'food_nm_kr': str(food_nm).strip(),
            'db_grp_nm': str(group or '').strip() or None,
            'origin': str(origin or '').strip(),
            'scnm': scnm,
            'values': {COLUMNS[h]: _num(r[at[h]]) for h in at},
        }
        out.append(item)
    return out


def verify(values):
    """
    적재하면서 스스로 검산한다. (판정, 설명).

    열을 하나 밀려 읽어도 예외가 나지 않는다 — 조용히 엉뚱한 값이 들어가고
    그 표가 라벨에 실린다. 그래서 데이터 자신에게 물어본다.

    **검산식을 여기서 다시 쓰지 않는다.** `mfds_nutrition.verify_row` 가 이미
    같은 일을 하고, 거기에는 여기서 모르는 것이 들어 있다 — 식이섬유 2.0 ·
    당알콜 2.4 라는 **규정 계수**다. 단순 4·4·9 로 재면 곤약·돼지감자·
    무설탕껌처럼 식이섬유와 당알콜이 많은 식품이 통째로 "어긋남" 이 된다
    (실제로 그렇게 재 보니 9.6 % 가 걸렸고, 그 표본이 전부 그런 것들이었다).

    잡으려는 것은 **자릿수가 밀렸는가**이지 측정 오차가 아니다.
    """
    from v1.label.models import PublicFoodNutrition as P
    from v1.label.services.mfds_nutrition import verify_row

    ok, why = verify_row(values, 100.0, P.BASIS_G)
    if ok is True:
        return P.VERIFY_PASS, ''
    if ok is False:
        return P.VERIFY_FAIL, why
    return P.VERIFY_SKIP, why
