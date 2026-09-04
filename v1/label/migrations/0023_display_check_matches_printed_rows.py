"""
지금까지 인쇄되던 줄을 표시 항목 체크에 옮겨 적는다.

표에 줄이 생기는 기준이 "값이 있는가" 에서 "표시 항목 체크가 켜졌는가" 로
바뀐다. 그런데 체크박스 기본값은 원산지·보관방법·유통전문판매원·소분원·
수입원·기타표시사항이 전부 'N' 이다. 그대로 두면 이미 만들어 둔 라벨에서
그 줄들이 **말없이 사라진다.**

그래서 값이 들어 있는데 체크가 꺼져 있던 항목을 켠다. 지금 인쇄되고 있는
모습을 그대로 체크 상태로 옮기는 것이라, 기존 라벨의 인쇄물은 하나도 달라지지
않는다. 반대 방향(체크는 켜졌는데 값이 없는 항목)은 건드리지 않는다 —
그쪽은 "아직 안 채웠다" 는 뜻이고, 미리보기가 빈 줄로 보여 줄 몫이다.
"""
from django.db import migrations

# v1/label/constants.py 의 PREVIEW_DISPLAY_FIELDS 와 같은 목록.
# 마이그레이션은 그때의 코드로 굳어 있어야 하므로 값을 복사해 둔다.
FIELDS = (
    'prdlst_dcnm', 'prdlst_nm', 'ingredient_info', 'content_weight',
    'weight_calorie', 'prdlst_report_no', 'country_of_origin',
    'storage_method', 'frmlc_mtrqlt', 'bssh_nm', 'distributor_address',
    'repacker_address', 'importer_address', 'pog_daycnt',
    'rawmtrl_nm_display', 'cautions', 'additional_info',
)

# 영양성분은 chckd_nutrition_text 로 켜지만, 값은 nutrition_text 가 아니라
# 개별 항목에 들어 있다(V2 영양성분 탭은 요약 문구를 만들지 않는다).
# validation_service._has_nutrition_display 도 이 항목들로 판정한다.
NUTRITION_VALUE_FIELDS = (
    'calories', 'natriums', 'carbohydrates', 'sugars', 'fats',
    'trans_fats', 'saturated_fats', 'cholesterols', 'proteins',
)


def turn_on_checks_for_filled_fields(apps, schema_editor):
    MyLabel = apps.get_model('label', 'MyLabel')
    checkboxes = [f'chckd_{f}' for f in FIELDS] + ['chckd_nutrition_text']

    batch = []
    columns = ['my_label_id', 'rawmtrl_nm', *FIELDS, *NUTRITION_VALUE_FIELDS, *checkboxes]
    for label in MyLabel.objects.only(*columns).iterator(chunk_size=500):
        touched = False
        for field in FIELDS:
            checkbox = f'chckd_{field}'
            value = getattr(label, field, '') or ''
            # 원재료명(표시)이 비어 있어도 참고 칸이 차 있으면 인쇄된다
            if field == 'rawmtrl_nm_display' and not value.strip():
                value = getattr(label, 'rawmtrl_nm', '') or ''
            if not value.strip():
                continue
            if (getattr(label, checkbox, '') or '') == 'Y':
                continue
            setattr(label, checkbox, 'Y')
            touched = True

        # 영양성분을 적어 둔 라벨은 켠다.
        #
        # 이쪽은 "지금 인쇄되던 것" 이 아니다 — 영양정보 표를 그릴 자리가 화면에
        # 아예 없어서 **어디에도 나오지 않고 있었다.** 값을 넣은 사람은 라벨에
        # 나올 것으로 알고 넣었고, 영양표시 대상 식품이면 규정상 필수이기도 하다.
        # 없던 줄이 사라지는 쪽이 아니라 생기는 쪽이라 눈에 띄고, 필요 없으면
        # 표시 항목에서 끄면 된다.
        if (getattr(label, 'chckd_nutrition_text', '') or '') != 'Y':
            if any(str(getattr(label, f, '') or '').strip() for f in NUTRITION_VALUE_FIELDS):
                label.chckd_nutrition_text = 'Y'
                touched = True

        if touched:
            batch.append(label)
        if len(batch) >= 500:
            MyLabel.objects.bulk_update(batch, checkboxes)
            batch = []
    if batch:
        MyLabel.objects.bulk_update(batch, checkboxes)


def noop(apps, schema_editor):
    """되돌리지 않는다 — 어느 체크가 원래 꺼져 있었는지 알 수 없다."""


class Migration(migrations.Migration):

    dependencies = [
        ('label', '0022_mylabel_prv_field_layout'),
    ]

    operations = [
        migrations.RunPython(turn_on_checks_for_filled_fields, noop),
    ]
