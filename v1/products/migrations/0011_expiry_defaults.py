# -*- coding: utf-8 -*-
"""
문서 구분별 **기본 유효기간**을 다시 정한다.

지금까지는 구분마다 그럴듯한 기간이 박혀 있었다 — 원산지증명서 365일,
HACCP인증서 1095일, 할랄 730일. 그런데 그 날짜들은 **우리가 지어낸 것**이다.
인증서에는 저마다 실제 만료일이 찍혀 있고, 그것과 우리가 더한 날짜가 맞을
까닭이 없다. 틀린 날짜는 없는 날짜보다 나쁘다 — 사용자는 화면에 적힌 날짜를
보고 아직 여유가 있다고 믿는다.

그래서 **모르는 것은 모른다고 둔다**(무기한). 인증서를 올린 사람이 문서에
적힌 진짜 날짜를 넣으면 된다.

예외는 자가품질검사성적서 하나다. **발행일로부터 6개월**이라는 관행이 있고
문서 자체에 만료일이 안 적혀 있는 일이 흔해서, 그때는 기본값이 실제로 쓸모가
있다. 영양성분분석서도 처음에는 여기 넣었는데 뺐다 — 분석서는 성분이 바뀌지
않으면 계속 쓰는 자료라 '6개월 뒤 만료' 가 사실이 아니다.
"""
from django.db import migrations

# 6개월짜리는 이것 하나다. 앱이 영양성분분석서도 '성적서' 라고 부르지만
# (영양성분 탭의 「성적서 판독」), 그 자료는 성분이 바뀌지 않으면 계속 쓴다.
SIX_MONTHS = ('TEST_QUALITY',)
DAYS = 180


def apply(apps, schema_editor):
    DocumentType = apps.get_model('products', 'DocumentType')
    DocumentType.objects.filter(type_code__in=SIX_MONTHS).update(
        default_validity_days=DAYS, requires_expiry=True)
    DocumentType.objects.exclude(type_code__in=SIX_MONTHS).update(
        default_validity_days=0)


class Migration(migrations.Migration):

    dependencies = [('products', '0010_documentrequest_reminded_on')]

    # 되돌리지 않는다. 옛 값은 구분마다 제각각이라 되살릴 근거가 없고,
    # 되살려 봐야 지어낸 날짜로 돌아갈 뿐이다.
    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
