"""
제품(products) 앱 회귀 테스트.

지금은 "확정(승인 완료) 직전 표시사항 검증" 한 가지만 다룬다. 이 경로는
화면에서 눈으로 확인하기 번거롭고(상태 전이 + 권한 + 검증이 한 번에 얽힌다),
조용히 느슨해지면 필수 항목이 빈 제품이 그대로 확정된다.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from v1.label.models import MyLabel
from v1.products.models import (
    ProductActivityLog,
    ProductMetadata,
    ProductShare,
    SharePermission,
)


class ConfirmValidationGateTests(TestCase):
    """
    확정 단계의 검증 게이트.

    무엇을 요구하느냐가 "이 제품에 검토·승인 역할이 배정돼 있는가"로 갈린다.
      - 배정돼 있다: 확정하는 사람과 작성한 사람이 다르다 → 예외 승인 사유를 받는다
      - 배정돼 있지 않다: 혼자 쓰는 제품 → 무엇이 비었는지 보여주고 확인만 받는다
    어느 쪽이든 첫 요청은 목록을 돌려주고 멈춰야 한다. 못 본 채로 확정되는
    경로가 있으면 안 된다.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='owner', password='x', email='owner@example.com')
        # chckd_* 기본값이 'Y' 인 항목들이 비어 있는 상태 — 필수 미입력이 잡힌다
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='확정 테스트')
        self.metadata = ProductMetadata.objects.create(
            label=self.label, status=ProductMetadata.Status.DRAFT)
        self.url = reverse('products:product_update_status',
                           args=[self.label.my_label_id])
        self.client.force_login(self.user)

    def _post(self, **extra):
        data = {'status': ProductMetadata.Status.CONFIRMED}
        data.update(extra)
        return self.client.post(self.url, data)

    def _assign_approver(self):
        share = ProductShare.objects.create(
            label=self.label, recipient_email='approver@example.com',
            created_by=self.user, active_yn=True,
        )
        SharePermission.objects.create(share=share, role_code='APPROVER')

    def _status(self):
        self.metadata.refresh_from_db()
        return self.metadata.status

    def _log_details(self):
        log = ProductActivityLog.objects.filter(
            label=self.label, action='STATUS_CHANGED').order_by('-pk').first()
        return (log.details or {}) if log else {}

    # ── 검토·승인 역할이 없는 제품 ──────────────────────────────────────────

    def test_필수_미입력이면_먼저_무엇이_비었는지_돌려주고_멈춘다(self):
        resp = self._post()

        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertTrue(data['validation_blocked'])
        self.assertFalse(data['requires_reason'], '혼자 쓰는 제품에 사유까지 받지는 않는다')
        self.assertIn('내용량', data['missing_required'])
        self.assertIn('소비기한', data['missing_required'])
        self.assertEqual(self._status(), ProductMetadata.Status.DRAFT)

    def test_확인만_받으면_확정되고_무엇을_넘겼는지_남는다(self):
        resp = self._post(validation_ack='1')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self._status(), ProductMetadata.Status.CONFIRMED)

        details = self._log_details()
        self.assertTrue(details['validation_override'])
        self.assertTrue(details['override_acknowledged'])
        self.assertNotIn('override_reason', details)
        self.assertIn('내용량', details['override_missing_required'])

    # ── 검토·승인 역할이 배정된 제품 ────────────────────────────────────────

    def test_승인자가_있으면_확인만으로는_확정되지_않는다(self):
        self._assign_approver()
        resp = self._post(validation_ack='1')

        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertTrue(data['validation_blocked'])
        self.assertTrue(data['requires_reason'], '담당자가 있으면 사유를 받아야 한다')
        self.assertEqual(self._status(), ProductMetadata.Status.DRAFT)

    def test_사유를_적으면_확정되고_사유가_로그에_남는다(self):
        self._assign_approver()
        resp = self._post(override_reason='인쇄 도안에는 반영됨')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._status(), ProductMetadata.Status.CONFIRMED)

        details = self._log_details()
        self.assertEqual(details['override_reason'], '인쇄 도안에는 반영됨')
        self.assertNotIn('override_acknowledged', details)

    def test_만료된_공유의_담당자는_배정된_것으로_보지_않는다(self):
        """
        공유가 끝난 담당자까지 세면, 아무도 없는 제품이 영원히 사유를 요구한다.
        """
        from django.utils import timezone
        from datetime import timedelta

        share = ProductShare.objects.create(
            label=self.label, recipient_email='approver@example.com',
            created_by=self.user, active_yn=True,
            share_end_date=timezone.now() - timedelta(days=1),
        )
        SharePermission.objects.create(share=share, role_code='APPROVER')

        self.assertFalse(self._post().json()['requires_reason'])

    # ── 검증을 통과하는 제품 ────────────────────────────────────────────────

    def test_필수_항목이_채워져_있으면_그냥_확정된다(self):
        for field in ('prdlst_dcnm', 'prdlst_nm', 'prdlst_report_no',
                      'frmlc_mtrqlt', 'bssh_nm', 'pog_daycnt',
                      'rawmtrl_nm_display', 'cautions'):
            setattr(self.label, field, '값')
        self.label.content_weight = '500g'   # 단위 검사도 통과해야 한다
        self.label.save()

        resp = self._post()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._status(), ProductMetadata.Status.CONFIRMED)
        self.assertNotIn('validation_override', self._log_details())


class DisplayItemSaveTests(TestCase):
    """
    V2 기본정보 탭의 표시 항목(chckd_*) 저장.

    지금까지 이 화면에는 표시 항목을 볼 수도 바꿀 수도 없었다. 필수 입력 검사가
    chckd_* 를 근거로 삼으면서 "해당하지 않으면 표시 항목 체크를 해제하세요" 라는
    안내가 나가는데, V2 에는 그럴 UI 가 없어 따를 방법이 없었다.
    """

    def setUp(self):
        from v1.label.models import FoodType

        self.user = User.objects.create_user(username='disp', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='표시항목 테스트')
        ProductMetadata.objects.create(label=self.label)
        FoodType.objects.create(
            food_group='과자류', food_type='과자',
            prdlst_dcnm='Y', nutritions='Y', country_of_origin='Y',
            prdlst_report_no='D', cautions='N', pog_daycnt='소비기한',
        )
        self.url = reverse('products:product_update_fields',
                           args=[self.label.my_label_id])
        self.client.force_login(self.user)

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def _reload(self):
        self.label.refresh_from_db()
        return self.label

    def test_체크를_켜고_끈_것이_저장된다(self):
        resp = self._post({'chckd_cautions': False, 'chckd_storage_method': True})

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self._reload().chckd_cautions, 'N')
        self.assertEqual(self.label.chckd_storage_method, 'Y')

    def test_보내지_않은_체크는_건드리지_않는다(self):
        """켠 것만 보내는 화면이 생기면 나머지가 조용히 꺼진다."""
        before = self._reload().chckd_frmlc_mtrqlt
        self._post({'prdlst_nm': '이름만 바꿈'})
        self.assertEqual(self._reload().chckd_frmlc_mtrqlt, before)

    def test_식품유형을_바꾸면_그_유형의_필수가_켜진다(self):
        self.label.chckd_nutrition_text = 'N'
        self.label.chckd_country_of_origin = 'N'
        self.label.save()

        self._post({'food_type': '과자', 'food_group': '과자류'})

        self.assertEqual(self._reload().chckd_nutrition_text, 'Y')
        self.assertEqual(self.label.chckd_country_of_origin, 'Y')

    def test_해당없음은_값이_비어_있을_때만_꺼진다(self):
        self.label.chckd_prdlst_report_no = 'Y'
        self.label.prdlst_report_no = '19950000000000'
        self.label.save()

        self._post({'food_type': '과자', 'food_group': '과자류'})

        # 값이 들어 있으므로 끄지 않는다 — 끄면 인쇄물에서 줄이 사라진다
        self.assertEqual(self._reload().chckd_prdlst_report_no, 'Y')

    def test_식품유형이_그대로면_자동_적용이_돌지_않는다(self):
        """저장할 때마다 사용자가 끈 항목이 다시 켜지면 끌 수가 없다."""
        self.label.food_type = '과자'
        self.label.food_group = '과자류'
        self.label.chckd_nutrition_text = 'N'
        self.label.save()

        self._post({'food_type': '과자', 'food_group': '과자류',
                    'chckd_nutrition_text': False})

        self.assertEqual(self._reload().chckd_nutrition_text, 'N')

    def test_표시_항목_목록이_식품유형_규칙을_함께_준다(self):
        from v1.products.views import _build_display_items

        self.label.food_type = '과자'
        self.label.food_group = '과자류'
        self.label.save()

        by_field = {i['field']: i for i in _build_display_items(self.label)}
        self.assertEqual(by_field['nutrition_text']['rule'], 'Y')
        self.assertEqual(by_field['prdlst_report_no']['rule'], 'D')
        self.assertEqual(by_field['prdlst_nm']['label'], '제품명')


class DisplayItemPanelTests(TestCase):
    """
    우측 패널의 표시 항목 목록.

    본문 카드로 두면 식품유형을 고른 뒤 한참 아래로 내려가야 보이고, 다른 항목을
    입력하는 동안에는 안 보인다. 무엇이 인쇄되는지와 어디로 가는지를 항상 보이는
    한 자리에 뒀다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='panel', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='패널')

    def test_내용량_열량은_목록에_없다(self):
        """
        별도로 입력하는 칸이 아니라 내용량에 병기하는 값이라("250 g (100 kcal)")
        켜고 끌 대상이 아니다. 표시 여부는 식품유형이 정하고, 값이 적혔는지는
        내용량의 kcal 표기로 판정한다.
        """
        from v1.products.views import _build_display_items

        fields = {i['field'] for i in _build_display_items(self.label)}
        self.assertNotIn('weight_calorie', fields)
        self.assertIn('content_weight', fields)

    def test_목록에서_빠진_항목은_저장에서도_건드리지_않는다(self):
        """화면이 안 보내면 서버가 기존 값을 그대로 둬야 한다."""
        self.label.chckd_weight_calorie = 'Y'
        self.label.save()

        ProductMetadata.objects.create(label=self.label)
        self.client.force_login(self.user)
        self.client.post(
            reverse('products:product_update_fields', args=[self.label.my_label_id]),
            data=json.dumps({'prdlst_nm': '이름'}), content_type='application/json')

        self.label.refresh_from_db()
        self.assertEqual(self.label.chckd_weight_calorie, 'Y')

    def test_탭으로_보내는_항목은_목록_끝에_둔다(self):
        """흐름이 끊기는 항목이라 입력을 다 마친 뒤 보이는 게 낫다."""
        from v1.products.views import _build_display_items

        items = _build_display_items(self.label)
        tabbed = [i for i in items if i['tab']]
        self.assertTrue(tabbed)
        for item in tabbed:
            self.assertGreaterEqual(items.index(item), len(items) - len(tabbed))
            self.assertTrue(item['tab_label'], '어느 탭으로 가는지 이름이 있어야 한다')

    def test_패널_순서가_폼_순서와_같다(self):
        """
        목록이 곧 목차 역할을 한다. 화면을 훑는 순서와 어긋나면 찾기 어려워진다.
        영양성분은 다른 탭으로 넘어가는 항목이라 순서 비교에서 뺀다.
        """
        import re
        from pathlib import Path
        from django.conf import settings as dj
        from v1.products.views import _build_display_items

        html = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                ).read_text(encoding='utf-8')
        form_order = [m.group(1) for m in re.finditer(r'id="(field-[a-z-]+)"', html)]

        panel = [i['anchor'] for i in _build_display_items(self.label)
                 if not i['tab'] and i['anchor'] in form_order]
        expected = sorted(panel, key=form_order.index)
        self.assertEqual(panel, expected, '우측 패널 순서가 폼 순서와 다르다')

    def test_이동_대상이_템플릿에_실제로_있다(self):
        """
        없는 id 를 가리키면 그 항목만 눌러도 아무 일이 안 일어난다.
        label_creation.js 의 chk_calories 가 정확히 그랬다.
        """
        import re
        from pathlib import Path
        from django.conf import settings as dj
        from v1.products.views import _build_display_items

        base = Path(dj.BASE_DIR)
        html = (base / 'templates/products/_tab_basic_info.html').read_text(encoding='utf-8')
        detail = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')
        ids = set(re.findall(r'id="(field-[a-z-]+)"', html))
        tabs = set(re.findall(r'id="(tab-[a-z-]+)"', detail))

        for item in _build_display_items(self.label):
            if item['tab']:
                self.assertIn(item['tab'], tabs, f"{item['label']} 의 탭 {item['tab']} 없음")
            else:
                self.assertIn(item['anchor'], ids,
                              f"{item['label']} 의 이동 대상 {item['anchor']} 없음")


class BasicInfoChoiceTests(TestCase):
    """
    장기보존식품·제조방법 선택지.

    템플릿이 preservation_choices 로 루프를 돌면서 {% empty %} 에 같은 목록을
    손으로 또 적어 뒀는데, 그 변수를 넘기는 뷰가 하나도 없어서 **항상 폴백만**
    그려지고 있었다. 목록을 뷰로 올려 한 곳에서만 관리한다.
    """

    def _render(self):
        from django.template.loader import render_to_string
        from v1.products.views import PRESERVATION_CHOICES, PROCESSING_CHOICES

        return render_to_string('products/_tab_basic_info.html', {
            'product': self.label, 'can_edit': True,
            'food_types': [], 'food_groups': [], 'countries': [],
            'display_items': [], 'custom_fields_json': '[]',
            'preservation_choices': PRESERVATION_CHOICES,
            'processing_choices': PROCESSING_CHOICES,
        })

    def setUp(self):
        self.user = User.objects.create_user(username='choice', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='선택지')

    def test_선택지가_빠짐없이_그려진다(self):
        import re
        from v1.products.views import PRESERVATION_CHOICES, PROCESSING_CHOICES

        html = self._render()
        for value, label in PRESERVATION_CHOICES:
            self.assertIn(f'id="field-preservation-{value}"', html, label)
        for value, label in PROCESSING_CHOICES:
            self.assertIn(f'id="field-processing-{value}"', html, label)
        # 폴백이 함께 그려져 id 가 겹치면 라벨 클릭이 엉뚱한 칸을 켠다
        ids = re.findall(r'id="(field-[a-z-]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), '중복 id 가 있다')

    def test_저장되는_값을_바꾸지_않았다(self):
        """value 는 DB 에 그대로 들어가는 문자열이라 바꾸면 기존 데이터와 어긋난다."""
        from v1.products.views import PRESERVATION_CHOICES, PROCESSING_CHOICES

        self.assertEqual([v for v, _ in PRESERVATION_CHOICES],
                         ['frozen_heated', 'frozen_nonheated', 'canned', 'retort'])
        self.assertEqual([v for v, _ in PROCESSING_CHOICES],
                         ['sanitized', 'aseptic', 'yutang', 'unsanitized'])

    def test_값을_읽는_클래스가_그대로다(self):
        """칩으로 바꿔도 :checked 로 값을 읽는 코드가 계속 동작해야 한다."""
        html = self._render()
        self.assertIn('grp-preservation', html)
        self.assertIn('grp-processing', html)

    def test_칩을_쓰는_화면_모두에_선택지를_넘긴다(self):
        """뷰가 안 넘기면 칩이 하나도 안 그려진다 — 예전에 그래서 폴백이 필요했다."""
        import inspect
        from v1.products import views

        src = inspect.getsource(views)
        self.assertEqual(src.count("'preservation_choices': PRESERVATION_CHOICES"), 3)
        self.assertEqual(src.count("'processing_choices': PROCESSING_CHOICES"), 3)


class RawmtrlDisplayFieldTests(TestCase):
    """
    V2 기본정보 탭의 "원재료명 표시명" 칸.

    이름과 달리 rawmtrl_nm(참고)에 쓰고 있었다. 라벨에 인쇄되는 값은
    rawmtrl_nm_display 라, 여기서 고쳐도 인쇄물은 그대로였다 — 사용자는 자기
    수정이 반영되지 않았다는 걸 알 방법이 없었다. 실제로 두 값이 완전히 다른
    라벨이 로컬에만 4건 있었다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='rawmtrl', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='원재료명')
        ProductMetadata.objects.create(label=self.label)
        self.url = reverse('products:product_update_fields',
                           args=[self.label.my_label_id])
        self.client.force_login(self.user)

    def _render(self):
        from django.template.loader import render_to_string
        from v1.products.views import PRESERVATION_CHOICES, PROCESSING_CHOICES

        return render_to_string('products/_tab_basic_info.html', {
            'product': self.label, 'can_edit': True,
            'food_types': [], 'food_groups': [], 'countries': [],
            'display_items': [], 'custom_fields_json': '[]',
            'preservation_choices': PRESERVATION_CHOICES,
            'processing_choices': PROCESSING_CHOICES,
        })

    def test_인쇄되는_필드를_편집한다(self):
        self.assertIn('name="rawmtrl_nm_display"', self._render())

    def test_저장하면_인쇄되는_필드에_들어간다(self):
        resp = self.client.post(
            self.url, data=json.dumps({'rawmtrl_nm_display': '밀가루(밀:미국산), 설탕'}),
            content_type='application/json')

        self.assertEqual(resp.status_code, 200)
        self.label.refresh_from_db()
        self.assertEqual(self.label.rawmtrl_nm_display, '밀가루(밀:미국산), 설탕')

    def test_표시_필드가_비면_참고_값을_채워_보여준다(self):
        """
        미리보기가 쓰는 폴백과 같은 규칙이다. 안 그러면 V2 로만 작업하던 제품이
        갑자기 빈 칸으로 보인다.
        """
        self.label.rawmtrl_nm = '정제수, 가공두유'
        self.label.save()
        self.assertIn('정제수, 가공두유', self._render())

    def test_표시_필드가_있으면_그것을_보여준다(self):
        """둘이 다를 때 인쇄되는 쪽을 보여줘야 한다."""
        self.label.rawmtrl_nm = '참고용 문구'
        self.label.rawmtrl_nm_display = '실제 인쇄 문구'
        self.label.save()

        html = self._render()
        self.assertIn('실제 인쇄 문구', html)
        self.assertNotIn('참고용 문구', html)

    def test_참고_필드는_건드리지_않는다(self):
        """relation 에서 다시 만들어지는 파생값이다. 저장이 덮어쓰면 안 된다."""
        self.label.rawmtrl_nm = '참고용 문구'
        self.label.save()

        self.client.post(self.url, data=json.dumps({'rawmtrl_nm_display': '새 문구'}),
                         content_type='application/json')

        self.label.refresh_from_db()
        self.assertEqual(self.label.rawmtrl_nm, '참고용 문구')
        self.assertEqual(self.label.rawmtrl_nm_display, '새 문구')



class IngredientPhotoParseTests(TestCase):
    """
    원료 표시사항 사진을 BOM 원료 한 건으로 옮기는 규칙.

    완제품 사진에 쓰던 OCR 을 그대로 쓰되 값의 뜻이 다르다 — 제품명은 원료명이고,
    원재료명은 그 원료의 하위 원료(복합원재료)다.
    """

    def _parse(self, **fields):
        from v1.products.services.ingredient_photo import parse_ingredient_photo
        return parse_ingredient_photo(
            {k: {'value': v, 'confidence': 'high'} for k, v in fields.items()})

    def test_제품명은_원료명이_된다(self):
        row = self._parse(prdlst_nm='탈지분유')
        self.assertEqual(row['ingredient_name'], '탈지분유')

    def test_원재료명은_하위원료가_된다(self):
        row = self._parse(prdlst_nm='빵가루', rawmtrl_nm='밀가루, 정제소금')
        self.assertEqual(row['sub_ingredients'], '밀가루, 정제소금')

    def test_주의사항에서_알레르기를_찾는다(self):
        row = self._parse(prdlst_nm='탈지분유',
                          cautions='우유를 함유하고 있습니다. 대두 혼입 가능')
        self.assertIn('우유', row['allergens'])
        self.assertIn('대두', row['allergens'])

    def test_알류와_난류가_같이_잡히면_하나만_남긴다(self):
        row = self._parse(prdlst_nm='전란액', cautions='알류(난류) 함유')
        self.assertEqual(row['allergens'], '알류')

    def test_알레르기가_없으면_빈_문자열(self):
        row = self._parse(prdlst_nm='정제소금', cautions='직사광선을 피해 보관')
        self.assertEqual(row['allergens'], '')

    def test_값이_없어도_깨지지_않는다(self):
        from v1.products.services.ingredient_photo import parse_ingredient_photo
        row = parse_ingredient_photo(None)
        self.assertEqual(row['ingredient_name'], '')


class IngredientPhotoToBomTests(TestCase):
    """
    원료 사진 → BOM 등록. 사진을 다시 읽지 않도록 화면이 고친 값을 받는다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='ingphoto', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user,
                                            my_label_name='초코쿠키')
        self.doc_type = DocumentType.objects.create(
            type_code='INGREDIENT_LABEL', type_name='원료 표시사항')
        self.doc = ProductDocument.objects.create(
            label=self.label,
            document_type=self.doc_type,
            file='v2/product_documents/ing.jpg',
            original_filename='탈지분유.jpg',
        )

    def _apply(self, **fields):
        payload = {'ingredient_name': '탈지분유', 'food_type': '유가공품'}
        payload.update(fields)
        url = reverse('products:document_ingredient_photo_to_bom',
                      kwargs={'document_id': self.doc.pk})
        return self.client.post(url, data=json.dumps({'fields': payload}),
                                content_type='application/json')

    def test_BOM_에_원료가_추가된다(self):
        from v1.bom.models import ProductBOM

        res = self._apply()
        self.assertEqual(res.status_code, 200, res.content[:300])
        body = res.json()
        self.assertTrue(body['created'])

        bom = ProductBOM.objects.get(parent_label=self.label)
        self.assertEqual(bom.ingredient_name, '탈지분유')
        self.assertEqual(bom.food_type, '유가공품')
        # 함량은 사진에 없다. 비어 있어야 한다.
        self.assertIsNone(bom.usage_ratio)
        self.assertIsNotNone(bom.source_ingredient_id)

    def test_내_원료가_함께_만들어진다(self):
        from v1.label.models import MyIngredient

        self._apply(sub_ingredients='우유', allergens='우유')
        ing = MyIngredient.objects.get(user_id=self.user, prdlst_nm='탈지분유')
        self.assertEqual(ing.rawmtrl_nm, '우유')
        self.assertEqual(ing.allergens, '우유')

    def test_이미_있는_원료에_붙는다(self):
        from v1.label.models import MyIngredient

        MyIngredient.objects.create(user_id=self.user, prdlst_nm='탈지분유',
                                    prdlst_report_no='', prdlst_dcnm='',
                                    delete_YN='N')
        body = self._apply().json()
        self.assertTrue(body['matched_existing'])
        self.assertEqual(
            MyIngredient.objects.filter(user_id=self.user,
                                        prdlst_nm='탈지분유').count(), 1)

    def test_두_번_눌러도_BOM_행이_늘지_않는다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        second = self._apply().json()
        self.assertFalse(second['created'])
        self.assertEqual(
            ProductBOM.objects.filter(parent_label=self.label).count(), 1)

    def test_원료명이_없으면_400(self):
        res = self._apply(ingredient_name='')
        self.assertEqual(res.status_code, 400)

    def test_등록하면_문서에_흔적이_남는다(self):
        self._apply()
        self.doc.refresh_from_db()
        self.assertIn('ingredient_bom_id', self.doc.metadata)

    def test_남의_문서는_못_건드린다(self):
        other = User.objects.create_user(username='ingphoto2', password='x')
        self.client.force_login(other)
        self.assertEqual(self._apply().status_code, 404)


class BasicInfoOcrWiringTests(TestCase):
    """
    표시사항 사진 → 기본 정보 탭 채우기의 배선.

    JS 의 FIELD_MAP 이 가리키는 입력칸 id 가 실제 화면에 있어야 한다. 하나라도
    어긋나면 그 항목만 조용히 안 채워지고, 눈으로는 "사진이 흐렸나" 로 보인다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        self.js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
                   ).read_text(encoding='utf-8')
        self.tab = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                    ).read_text(encoding='utf-8')
        self.detail = (Path(dj.BASE_DIR) / 'templates/products/product_detail.html'
                       ).read_text(encoding='utf-8')

    def _mapped_ids(self):
        import re
        return re.findall(r"id:\s*'([a-z-]+)'", self.js)

    def test_매핑한_입력칸이_전부_화면에_있다(self):
        html = self.tab + self.detail
        missing = [i for i in self._mapped_ids() if f'id="{i}"' not in html]
        self.assertEqual(missing, [], f'화면에 없는 입력칸: {missing}')

    def test_저장이_같은_칸을_읽는다(self):
        """채운 칸이 저장 대상이 아니면 사진에서 읽어도 저장되지 않는다."""
        missing = [i for i in self._mapped_ids() if f"'{i}'" not in self.detail]
        self.assertEqual(missing, [], f'saveBasicInfo 가 안 읽는 칸: {missing}')

    def test_사진_선택_입구가_있다(self):
        self.assertIn('basicInfoOcrInput', self.tab)
        self.assertIn('basic_info_ocr.js', self.detail)

    def test_스크립트가_고정_캐시버스터를_쓰지_않는다(self):
        self.assertIn("basic_info_ocr.js' %}?v={{ STATIC_BUILD_DATE }}", self.detail)


class RawmtrlToBomTests(TestCase):
    """
    표시사항의 원재료명 한 줄 → 원료별 BOM 행.

    사진에서 읽은 원재료명은 한 줄짜리 문자열이다. 그대로 두면 배합비 순서
    검사·알레르기 수집·표시 문구가 올라갈 자리가 없다.
    """

    TEXT = ('새송이버섯(국산)57.64%,과·채가공품/표고버섯채(중국산)21.63%'
            '(표고버섯,정제수,정제소금,구연산),애느타리버섯(국산)17.28%,'
            '콩기름(대두:외국산),천일염(국산),흑후추')

    def setUp(self):
        self.user = User.objects.create_user(username='r2b', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user,
                                            my_label_name='표고버섯볶음')

    def _preview(self, text=None):
        url = reverse('products:rawmtrl_to_bom_preview',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url,
                                data=json.dumps({'text': text or self.TEXT}),
                                content_type='application/json')

    def _apply(self, rows, replace=False):
        url = reverse('products:rawmtrl_to_bom_apply',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(
            url, data=json.dumps({'rows': rows, 'replace': replace}),
            content_type='application/json')

    def test_미리보기는_저장하지_않는다(self):
        from v1.bom.models import ProductBOM

        body = self._preview().json()
        self.assertTrue(body['success'])
        self.assertEqual(len(body['rows']), 6)
        self.assertEqual(body['rows'][0]['name'], '새송이버섯')
        self.assertEqual(body['rows'][0]['ratio'], 57.64)
        self.assertEqual(ProductBOM.objects.filter(parent_label=self.label).count(), 0)

    def test_BOM_행과_표시사항_원재료가_함께_생긴다(self):
        from v1.bom.models import ProductBOM
        from v1.label.models import LabelIngredientRelation

        rows = self._preview().json()['rows']
        body = self._apply(rows).json()
        self.assertEqual(body['created'], 6)
        self.assertEqual(body['linked_to_label'], 6)

        boms = ProductBOM.objects.filter(parent_label=self.label, active_yn=True)
        self.assertEqual(boms.count(), 6)
        self.assertEqual(
            LabelIngredientRelation.objects.filter(label=self.label).count(), 6)

    def test_배합비가_그대로_들어간다(self):
        from v1.bom.models import ProductBOM

        self._apply(self._preview().json()['rows'])
        bom = ProductBOM.objects.get(parent_label=self.label,
                                     ingredient_name='새송이버섯')
        self.assertEqual(float(bom.usage_ratio), 57.64)

    def test_함량이_없는_원료는_비워_둔다(self):
        """없는 값을 0 으로 채우면 순서 검사가 '함량 0' 을 사실로 받아들인다."""
        from v1.bom.models import ProductBOM

        self._apply(self._preview().json()['rows'])
        bom = ProductBOM.objects.get(parent_label=self.label, ingredient_name='흑후추')
        self.assertIsNone(bom.usage_ratio)

    def test_하위_원료가_보존된다(self):
        from v1.bom.models import ProductBOM

        self._apply(self._preview().json()['rows'])
        bom = ProductBOM.objects.get(parent_label=self.label,
                                     ingredient_name='과·채가공품/표고버섯채')
        self.assertEqual(bom.sub_ingredients, '표고버섯, 정제수, 정제소금, 구연산')
        self.assertEqual(bom.origin, '중국산')

    def test_두_번_등록해도_행이_늘지_않는다(self):
        from v1.bom.models import ProductBOM

        rows = self._preview().json()['rows']
        self._apply(rows)
        self._apply(rows)
        self.assertEqual(
            ProductBOM.objects.filter(parent_label=self.label, active_yn=True).count(), 6)

    def test_replace_는_기존_BOM_을_비운다(self):
        from v1.bom.models import ProductBOM

        ProductBOM.objects.create(parent_label=self.label, ingredient_name='옛원료',
                                  created_by=self.user, active_yn=True)
        self._apply(self._preview().json()['rows'], replace=True)
        names = set(ProductBOM.objects.filter(
            parent_label=self.label, active_yn=True).values_list('ingredient_name', flat=True))
        self.assertNotIn('옛원료', names)

    def test_원재료명이_비면_400(self):
        self.assertEqual(self._preview(text=' ').status_code, 400)

    def test_남의_라벨은_못_건드린다(self):
        other = User.objects.create_user(username='r2b2', password='x')
        self.client.force_login(other)
        self.assertEqual(self._preview().status_code, 404)
