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
