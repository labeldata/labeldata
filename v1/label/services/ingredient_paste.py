"""
엑셀에서 붙여넣은 표를 원료로 만든다.

배합비 화면에서 하던 것을 원료 관리로 옮긴다. 사람들은 원료 목록을 엑셀로
관리하다가 필요할 때 우리 화면에 옮겨 적고 있었다.

**부담은 붙여넣기가 아니라 줄마다 도는 쿼리였다.**

옛 엑셀 업로드(`upload_my_ingredients_excel`)는 줄마다 `exists()` 로 묻고
줄마다 `create()` 했다. 1000줄이면 DB 왕복 2000번이다. DB 가 프로세스 밖에
있으니 왕복 하나가 몇 ms 만 되어도 수십 초가 되고, 요청 시간 제한에 걸리면
**절반만 들어간 채로 끊긴다** — 트랜잭션이 없어 되돌릴 수도 없었다.

여기서는 이렇게 한다.

    이미 있는 것의 열쇠를 한 번에 가져온다      1쿼리
    bulk_create (500개씩)                        몇 쿼리
                                                ─────
                                                 3~7쿼리

한 번에 받는 줄 수에는 상한을 둔다(`PASTE_MAX_ROWS`). 등급과 무관한
**서버 보호 한도**다 — 돈을 낸다고 서버가 더 견디지는 않는다. 요금과 걸린
한도는 `v1/common/quota.py` 가 따로 본다.

**같은 것인지 보는 기준은 중복 정리와 한 벌을 쓴다**(`ingredient_merge`).
품목보고번호가 있으면 그것, 없으면 이름+제조사. 옛 업로드는 여섯 칸이 전부
같아야 같은 것으로 봐서, 식품구분 한 글자만 달라도 사본이 새로 생겼다.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from v1.label.models import MyIngredient
from v1.label.services.ingredient_matching import normalize_name

logger = logging.getLogger(__name__)

# 한 번에 받는 줄 수. 서버 보호 한도라 등급과 무관하다.
DEFAULT_MAX_ROWS = 2000


def max_rows():
    return int(getattr(settings, 'PASTE_MAX_ROWS', DEFAULT_MAX_ROWS))


# 붙여넣기 열 이름 -> MyIngredient 필드. 화면의 머리글이자 저장할 자리다.
COLUMNS = [
    ('원료명',       'prdlst_nm'),
    ('원료 표시명',  'ingredient_display_name'),
    ('식품유형',     'prdlst_dcnm'),
    ('식품구분',     'food_category'),
    ('제조사',       'bssh_nm'),
    ('품목보고번호', 'prdlst_report_no'),
    ('알레르기 성분', 'allergens'),
    ('GMO',          'gmo'),
    ('하위 원료',    'rawmtrl_nm'),
]
HEADERS = [name for name, _ in COLUMNS]
FIELDS = [field for _, field in COLUMNS]

# 화면에서 고른 말이 DB 코드와 다르다. 옛 업로드가 쓰던 표를 그대로 쓴다.
FOOD_CATEGORY_CODE = {
    '가공식품': 'processed',
    '식품첨가물': 'additive',
    '농수산물': 'agricultural',
    '정제수': 'water',
}


def row_key(report_no, name, maker):
    """
    같은 원료로 볼 기준. `ingredient_merge.group_key` 와 같은 규칙이되,
    모델 객체가 아니라 붙여넣은 글자에서 만든다.
    """
    report_no = (report_no or '').strip()
    if report_no:
        return ('report', report_no)
    clean = normalize_name(name or '')
    if not clean:
        return None
    return ('name', clean, normalize_name(maker or ''))


def _existing_keys(user):
    """이미 있는 것의 열쇠. 줄마다 묻지 않고 한 번에 가져온다."""
    rows = (MyIngredient.objects
            .filter(user_id=user, delete_YN='N')
            .values_list('prdlst_report_no', 'prdlst_nm', 'bssh_nm'))
    keys = set()
    for report_no, name, maker in rows:
        key = row_key(report_no, name, maker)
        if key:
            keys.add(key)
    return keys


def _clean(value):
    if value is None:
        return ''
    return str(value).strip()


def plan(user, rows):
    """
    무엇이 들어가고 무엇이 걸러지는지 세어 본다. **아무것도 만들지 않는다.**

    말없이 1000건을 밀어 넣으면 중복 정리를 다시 해야 한다. 저장 전에
    사용자가 이 숫자를 보고 누른다.

    Returns: {'fresh': [rowdict…], 'existing': int, 'repeated': int,
              'blank': int, 'total': int}
    """
    seen = _existing_keys(user)
    added = set()          # 이 붙여넣기에서 새로 잡은 열쇠
    fresh, existing, repeated, blank = [], 0, 0, 0

    for raw in rows:
        item = {field: _clean(raw.get(field)) for field in FIELDS}
        if not item['prdlst_nm']:
            blank += 1
            continue
        key = row_key(item['prdlst_report_no'], item['prdlst_nm'],
                      item['bssh_nm'])
        if key is None:
            blank += 1
            continue
        # 이미 있는 것과 붙여넣기 안에서 겹친 것을 나눠 센다. 사용자가
        # 보기에 다른 일이다 — 앞엣것은 예전에 넣은 것, 뒤엣것은 지금
        # 붙여넣은 표 자체에 사본이 있다는 뜻이다.
        if key in added:
            repeated += 1
            continue
        if key in seen:
            existing += 1
            continue
        added.add(key)
        fresh.append(item)

    return {'fresh': fresh, 'existing': existing, 'repeated': repeated,
            'blank': blank, 'total': len(rows)}


@transaction.atomic
def create(user, rows):
    """
    새 것만 만든다. 이미 있는 것은 건드리지 않는다 — 덮어쓰면 손으로 고쳐 둔
    표시명이나 알레르기가 엑셀의 옛 값으로 돌아간다.

    묶음 하나가 트랜잭션 하나다. 중간에 끊겨도 그 묶음은 통째로 들어갔거나
    통째로 안 들어갔다.
    """
    made = plan(user, rows)
    now = timezone.now()
    objs = []
    for item in made['fresh']:
        category = item['food_category']
        objs.append(MyIngredient(
            user_id=user,
            prdlst_nm=item['prdlst_nm'],
            ingredient_display_name=(item['ingredient_display_name']
                                     or item['prdlst_nm']),
            prdlst_dcnm=item['prdlst_dcnm'],
            food_category=FOOD_CATEGORY_CODE.get(category, category),
            bssh_nm=item['bssh_nm'],
            prdlst_report_no=item['prdlst_report_no'],
            allergens=item['allergens'],
            gmo=item['gmo'],
            rawmtrl_nm=item['rawmtrl_nm'],
            delete_YN='N',
            update_datetime=now,
        ))

    if objs:
        MyIngredient.objects.bulk_create(objs, batch_size=500)

    return {'created': len(objs), 'existing': made['existing'],
            'repeated': made['repeated'], 'blank': made['blank'],
            'total': made['total']}
