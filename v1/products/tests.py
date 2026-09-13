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
from django.utils import timezone

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
        # 주의사항에 교환 안내가 없지만 그것은 권고라 길을 막지 않는다

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

    def test_규칙표에_없는_체크도_저장된다(self):
        """
        유통전문판매원·소분원·수입원·기타표시사항은 식품유형 규칙표
        (FIELD_TO_CHECKBOX)에 없다. 그 표를 저장 대상으로 삼는 바람에, 넷 다
        오른쪽 패널에 있고 규정 검증의 근거인데도 껐다 켠 것이 저장되지 않았다.
        """
        self.label.chckd_additional_info = 'Y'
        self.label.chckd_importer_address = 'N'
        self.label.save()

        self._post({'chckd_additional_info': False,
                    'chckd_distributor_address': True,
                    'chckd_repacker_address': True,
                    'chckd_importer_address': True})

        self.assertEqual(self._reload().chckd_additional_info, 'N')
        self.assertEqual(self.label.chckd_distributor_address, 'Y')
        self.assertEqual(self.label.chckd_repacker_address, 'Y')
        self.assertEqual(self.label.chckd_importer_address, 'Y')

    def test_규칙이_켠_항목을_응답이_알려_준다(self):
        """조용히 켜 두면 켠 적 없는 체크를 근거로 한 지적을 받게 된다."""
        self.label.chckd_nutrition_text = 'N'
        self.label.save()

        resp = self._post({'food_type': '과자', 'food_group': '과자류'})

        on = {i['checkbox']: i['label'] for i in resp.json()['rule_applied']['turned_on']}
        self.assertIn('chckd_nutrition_text', on)
        self.assertEqual(on['chckd_nutrition_text'], '영양성분 표시')

    def test_규칙이_손대지_않으면_알릴_것도_없다(self):
        resp = self._post({'prdlst_nm': '이름만 바꿈'})
        self.assertEqual(resp.json()['rule_applied'],
                         {'turned_on': [], 'turned_off': []})

    def test_저장_응답이_바뀐_표시_항목을_돌려준다(self):
        """
        식품유형을 바꾸면 서버가 그 유형의 규칙으로 체크를 켠다. 돌려주지 않으면
        오른쪽 패널은 사용자가 켠 적 없는 체크를 꺼진 채로 계속 보여 주고,
        규정 검증만 "표시하기로 선택했는데 비어 있습니다" 라고 말하게 된다.
        """
        self.label.chckd_nutrition_text = 'N'
        self.label.save()

        resp = self._post({'food_type': '과자', 'food_group': '과자류'})

        items = {i['checkbox']: i for i in resp.json()['display_items']}
        self.assertTrue(items['chckd_nutrition_text']['checked'])
        self.assertFalse(items['chckd_nutrition_text']['filled'])

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

    def test_미입력_표시는_그려_두고_숨긴다(self):
        """
        느낌표를 조건부로 **그리면** 페이지를 그릴 때의 상태에 못 박힌다.
        사진으로 열여섯 칸을 채워도 느낌표가 그대로 남아, 다 채운 화면이
        전부 미입력으로 보였다. 늘 그려 두고 보이고 숨기는 일만 JS 가 한다.
        """
        from pathlib import Path
        from django.conf import settings as dj

        detail = (Path(dj.BASE_DIR) / 'templates/products/product_detail.html'
                  ).read_text(encoding='utf-8')
        self.assertIn('function refreshDisplayItemFlags', detail)
        # 값을 비우면 체크는 그대로 두고 느낌표로 알린다. 체크를 대신 꺼 주면
        # 인쇄물에서 줄이 조용히 사라져, 지우려던 것이 아니라 고쳐 쓰려던
        # 사용자가 그 사실을 모른 채 확정하게 된다.
        self.assertIn('mark.hidden = !(box.checked && !filled)', detail)
        self.assertNotIn('box.checked = false', detail)
        # 값·체크가 바뀌면 다시 계산한다
        self.assertIn("document.addEventListener('input', refreshDisplayItemFlags)", detail)
        self.assertIn("document.addEventListener('change', refreshDisplayItemFlags)", detail)
        # 저장 응답이 돌려준 상태를 패널에 반영한다
        self.assertIn('applyDisplayItems(data.display_items)', detail)

    def test_미입력_판정이_검증과_같은_자리를_본다(self):
        """
        주의사항과 기타표시사항은 한쪽에만 적어도 표시가 온전하다
        (validation_service 의 _ALTERNATIVE_SOURCES). 화면이 자기 규칙을 따로
        가지면 패널은 "미입력", 검증은 "괜찮다" 라고 서로 다른 말을 한다.
        """
        import re
        from pathlib import Path
        from django.conf import settings as dj
        from v1.products.views import _build_display_items

        html = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                ).read_text(encoding='utf-8')
        ids = set(re.findall(r'id="(field-[a-z-]+)"', html))

        by_field = {i['field']: i['sources'].split(',') for i in _build_display_items(self.label)}
        self.assertEqual(sorted(by_field['cautions']),
                         ['field-additional-info', 'field-cautions'])
        # 영양성분은 이 탭에 칸이 없다 — 화면이 읽을 자리가 없으므로
        # 서버가 계산해 준 값을 그대로 쓰게 둔다
        self.assertFalse([s for s in by_field['nutrition_text'] if s in ids])

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
        """
        뷰가 안 넘기면 칩이 하나도 안 그려진다 - 예전에 그래서 폴백이 필요했다.

        개수를 못 박지 않는다. 기본 정보 탭을 그리는 화면은 이제 제품 상세
        하나지만(등록·수정 폼을 워크스페이스로 합쳤다), 나중에 늘 수 있다.
        두 선택지를 짝으로 넘기는지, 하나라도 넘기는지를 본다.
        """
        import inspect
        from v1.products import views

        src = inspect.getsource(views)
        preservation = src.count("'preservation_choices': PRESERVATION_CHOICES")
        processing = src.count("'processing_choices': PROCESSING_CHOICES")
        self.assertGreaterEqual(preservation, 1)
        self.assertEqual(preservation, processing,
                         '두 선택지는 같은 곳에서 함께 넘겨야 한다')


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

    def test_불러오기_입구가_있다(self):
        # 사진 입력칸은 불러오기 모달 안으로 옮겼다(import_modal.js).
        self.assertIn('openImportModal()', self.tab)
        self.assertIn('basic_info_ocr.js', self.detail)

    def test_제품이_없으면_불러오기를_숨긴다(self):
        """
        신규 등록 화면에는 아직 제품이 없다. 읽어낸 원료를 붙일 곳(BOM·문서함)이
        없으므로 버튼이 보이면 눌러도 아무 일도 일어나지 않는다.
        """
        from django.template.loader import render_to_string

        html = render_to_string('products/_tab_basic_info.html',
                                {'product': None, 'can_edit': True})
        self.assertNotIn('openImportModal()', html)

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


class IngredientPhotoDisplayNameTests(TestCase):
    """
    원료 사진으로 만든 BOM 행의 "원재료 표시명".

    원료명을 그대로 복사하면 BOM 표의 앞 두 칸이 똑같아 보여 "원재료명을 못
    읽었다" 로 읽힌다. 실제로 읽은 원재료명은 표에 컬럼이 없는 sub_ingredients
    에만 들어가 보이지 않았다. 표시명에는 사진의 원재료명과 함량이 들어간다.
    """

    RAWMTRL = ('새송이버섯(국산)57.64%, 표고버섯채(중국산)21.63%, '
               '애느타리버섯(국산)17.28%, 콩기름(대두:외국산)')

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='photodisp', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='만두')
        self.doc = ProductDocument.objects.create(
            label=self.label,
            document_type=DocumentType.objects.create(
                type_code='INGREDIENT_LABEL', type_name='원료 표시사항'),
            file='v2/product_documents/ing.jpg',
            original_filename='표고버섯볶음.jpg',
        )

    def _apply(self, **over):
        fields = {
            'ingredient_name': '표고버섯볶음(라그릴리아)',
            'sub_ingredients': self.RAWMTRL,
            'food_type': '조림류',
        }
        fields.update(over)
        url = reverse('products:document_ingredient_photo_to_bom',
                      kwargs={'document_id': self.doc.pk})
        return self.client.post(url, data=json.dumps({'fields': fields}),
                                content_type='application/json')

    def test_표시명에_사진의_원재료명과_함량이_들어간다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        bom = ProductBOM.objects.get(parent_label=self.label)
        self.assertEqual(bom.ingredient_name, '표고버섯볶음(라그릴리아)')
        self.assertEqual(bom.raw_material_name, self.RAWMTRL)
        self.assertNotEqual(bom.raw_material_name, bom.ingredient_name)

    def test_원재료명을_못_읽으면_원료명을_쓴다(self):
        from v1.bom.models import ProductBOM

        self._apply(sub_ingredients='')
        bom = ProductBOM.objects.get(parent_label=self.label)
        self.assertEqual(bom.raw_material_name, '표고버섯볶음(라그릴리아)')

    def test_다시_읽으면_행을_늘리지_않고_갱신한다(self):
        from v1.bom.models import ProductBOM

        self._apply(sub_ingredients='옛 원재료명')
        self._apply()
        boms = ProductBOM.objects.filter(parent_label=self.label)
        self.assertEqual(boms.count(), 1)
        self.assertEqual(boms.first().raw_material_name, self.RAWMTRL)


class ProductCreatePageTests(TestCase):
    """
    신규 제품 등록 화면이 열리는가.

    _tab_basic_info.html 은 product_detail(제품이 있다)과 product_form(없다)이
    함께 쓴다. 그래서 "{{ product.a|default:product.b }}" 처럼 **필터 인자**로
    product 를 다시 읽으면, 신규 등록 화면에서 VariableDoesNotExist 로 500 이
    난다 - 필터 인자는 조용히 넘어가지 않는다.

    실제로 그렇게 깨진 적이 있다. 좌측 "새로 만들기" 와 대시보드 "신규 제품 등록"
    이 둘 다 이 화면으로 온다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='newproduct', password='x')
        self.client.force_login(self.user)

    def test_신규_등록은_제품을_만들고_워크스페이스로_보낸다(self):
        before = MyLabel.objects.filter(user_id=self.user).count()
        res = self.client.get(reverse('products:product_create'))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MyLabel.objects.filter(user_id=self.user).count(), before + 1)

        label = MyLabel.objects.filter(user_id=self.user).latest('my_label_id')
        self.assertIn(str(label.my_label_id), res['Location'])
        # cleanup_temp_labels 가 치울 수 있는 이름이어야 한다
        self.assertTrue(label.my_label_name.startswith('임시 - 제품명 - '))

    def test_만들어진_제품에_메타데이터가_붙는다(self):
        from v1.products.models import ProductMetadata

        self.client.get(reverse('products:product_create'))
        label = MyLabel.objects.filter(user_id=self.user).latest('my_label_id')
        self.assertTrue(ProductMetadata.objects.filter(label=label).exists())

    def test_제품_코드가_겹치지_않는다(self):
        from v1.products.models import ProductMetadata

        for _ in range(3):
            self.client.get(reverse('products:product_create'))
        codes = list(ProductMetadata.objects
                     .filter(label__user_id=self.user)
                     .values_list('product_code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    def test_제품_없이도_기본정보_조각이_그려진다(self):
        from django.template.loader import render_to_string

        html = render_to_string('products/_tab_basic_info.html',
                                {'product': None, 'can_edit': True})
        self.assertIn('field-rawmtrl-nm', html)

    def test_필터_인자로_product_를_다시_읽지_않는다(self):
        """이 패턴이 다시 들어오면 신규 등록 화면이 500 이 된다."""
        import re
        from pathlib import Path
        from django.conf import settings as dj

        html = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                ).read_text(encoding='utf-8')
        bad = re.findall(r'\|\s*default:\s*(?:product|label|form)\.[\w.]+', html)
        self.assertEqual(bad, [], f'필터 인자에서 객체를 다시 읽는 곳: {bad}')


class ReportNoLookupTests(TestCase):
    """품목보고번호로 등록 정보를 불러온다. OCR 을 거치지 않아 가장 정확하다."""

    def setUp(self):
        from v1.label.models import FoodItem

        self.user = User.objects.create_user(username='lookup', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='만두')
        FoodItem.objects.create(
            prdlst_report_no='20220460436160',
            prdlst_nm='표고버섯볶음',
            prdlst_dcnm='조림류',
            rawmtrl_nm='새송이버섯(국산)57.64%, 표고버섯채(중국산)21.63%',
            bssh_nm='하늘농가(주)',
        )

    def _lookup(self, no):
        url = reverse('products:report_no_lookup',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps({'report_no': no}),
                                content_type='application/json')

    def test_등록_정보를_돌려준다(self):
        body = self._lookup('20220460436160').json()
        self.assertTrue(body['success'])
        self.assertEqual(body['fields']['prdlst_nm'], '표고버섯볶음')
        self.assertIn('새송이버섯', body['fields']['rawmtrl_nm'])

    def test_공백이_섞여도_찾는다(self):
        self.assertTrue(self._lookup(' 2022046 0436160 ').json()['success'])

    def test_하이픈을_넣어_쳐도_찾는다(self):
        # 라벨에는 "2022-0460436160" 처럼 끊어 인쇄돼 있기도 하다. 저장된 꼴과
        # 다르다고 멀쩡한 품목을 "없는 번호" 라고 답하면 안 된다.
        self.assertTrue(self._lookup('2022-0460436160').json()['success'])
        self.assertTrue(self._lookup('2022046043-6160').json()['success'])

    def test_저장된_쪽에_하이픈이_있어도_찾는다(self):
        # 반대 방향. 등록된 번호에 하이픈이 있고 사용자는 숫자만 친 경우다.
        from v1.label.models import FoodItem
        FoodItem.objects.create(prdlst_report_no='19980448010-697',
                                prdlst_nm='옛날간장', prdlst_dcnm='간장')
        body = self._lookup('19980448010697').json()
        self.assertTrue(body['success'])
        self.assertEqual(body['fields']['prdlst_nm'], '옛날간장')

    def test_없는_번호는_404(self):
        self.assertEqual(self._lookup('99999999999999').status_code, 404)

    def test_한_자리_틀리면_후보를_돌려준다(self):
        # 못 찾았다고 거기서 끝내지 않는다. 고를 수 있게 늘어놓는다.
        res = self._lookup('20220460436161')
        self.assertEqual(res.status_code, 404)
        nos = [c['prdlst_report_no'] for c in res.json()['candidates']]
        self.assertIn('20220460436160', nos)

    def test_제품명으로도_후보를_찾는다(self):
        res = self._lookup('표고버섯')
        nos = [c['prdlst_report_no'] for c in res.json()['candidates']]
        self.assertIn('20220460436160', nos)

    def test_번호가_비면_400(self):
        self.assertEqual(self._lookup('').status_code, 400)


class FoodItemSearchTests(TestCase):
    """번호를 모를 때 — 제품명·제조사로 품목을 찾아 고른다."""

    def setUp(self):
        from v1.label.models import FoodItem

        self.user = User.objects.create_user(username='itemsearch', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='만두')
        FoodItem.objects.create(
            prdlst_report_no='20220460436160',
            prdlst_nm='표고버섯볶음', prdlst_dcnm='조림류',
            bssh_nm='하늘농가(주)',
            rawmtrl_nm='새송이버섯(국산)57.64%',
        )

    def _search(self, q):
        url = reverse('products:food_item_search',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps({'q': q}),
                                content_type='application/json')

    def test_제품명으로_찾는다(self):
        body = self._search('표고버섯').json()
        self.assertTrue(body['success'])
        self.assertEqual(body['items'][0]['prdlst_report_no'], '20220460436160')

    def test_번호로_찾으면_맨_앞에_온다(self):
        body = self._search('20220460436160').json()
        self.assertEqual(body['items'][0]['prdlst_nm'], '표고버섯볶음')

    def test_한_글자는_400(self):
        self.assertEqual(self._search('표').status_code, 400)


class OcrRelinkTests(TestCase):
    """
    사용자가 고른 품목으로 판독 결과를 다시 대조한다.

    자동 조회는 번호가 정확할 때만 걸린다. 번호가 아예 안 읽힌 사진에서도
    등록 정보를 쓸 수 있어야 한다 - 그 문을 사람이 연다.
    """

    def setUp(self):
        from v1.label.models import FoodItem

        self.user = User.objects.create_user(username='relink', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='만두')
        FoodItem.objects.create(
            prdlst_report_no='20220460436160',
            prdlst_nm='표고버섯볶음', prdlst_dcnm='조림류',
            bssh_nm='하늘농가(주)',
            rawmtrl_nm='새송이버섯(국산)57.64%',
        )

    def _relink(self, report_no, data):
        url = reverse('products:ocr_relink',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(
            url, data=json.dumps({'report_no': report_no, 'data': data}),
            content_type='application/json')

    def test_못_읽은_자리를_채운다(self):
        # 번호는 아예 안 읽혔고 제품명만 읽힌 사진
        data = {'prdlst_nm': {'value': '표고버섯볶음', 'confidence': 'high'}}
        body = self._relink('20220460436160', data).json()
        self.assertTrue(body['success'])
        self.assertTrue(body['api_match']['matched'])
        self.assertEqual(body['data']['prdlst_dcnm']['value'], '조림류')
        self.assertEqual(body['data']['bssh_nm']['api_value'], '하늘농가(주)')

    def test_고른_품목은_번호를_고쳤다고_하지_않는다(self):
        data = {'prdlst_report_no': {'value': '11112222333344', 'confidence': 'low'},
                'prdlst_nm': {'value': '표고버섯볶음', 'confidence': 'high'}}
        match = self._relink('20220460436160', data).json()['api_match']
        self.assertTrue(match['picked'])
        self.assertFalse(match['corrected_report_no'])

    def test_없는_품목은_404(self):
        self.assertEqual(self._relink('99999999999999', {}).status_code, 404)

    def test_판독_결과가_없으면_400(self):
        url = reverse('products:ocr_relink',
                      kwargs={'label_id': self.label.my_label_id})
        res = self.client.post(url, data=json.dumps({'report_no': '20220460436160'}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)


class IngredientToBomTests(TestCase):
    """
    사진 없이 원료를 BOM 에 넣는다 (품목보고번호로 불러온 경우).
    첨부 파일이 없으므로 문서함에는 아무것도 남기지 않는다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='ing2bom', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='만두')

    def _apply(self, **over):
        fields = {
            'ingredient_name': '표고버섯볶음',
            'food_type': '조림류',
            'sub_ingredients': '새송이버섯(국산)57.64%, 표고버섯채(중국산)21.63%',
            'report_no': '20220460436160',
        }
        fields.update(over)
        url = reverse('products:ingredient_to_bom',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps({'fields': fields}),
                                content_type='application/json')

    def test_BOM_원료만_만든다(self):
        from v1.bom.models import ProductBOM
        from v1.products.models import ProductDocument

        body = self._apply().json()
        self.assertTrue(body['created'])
        bom = ProductBOM.objects.get(parent_label=self.label)
        self.assertEqual(bom.ingredient_name, '표고버섯볶음')
        self.assertIn('새송이버섯', bom.raw_material_name)
        self.assertEqual(bom.report_no, '20220460436160')
        # 문서함에는 아무것도 남기지 않는다
        self.assertEqual(ProductDocument.objects.filter(label=self.label).count(), 0)

    def test_배합비는_비워_둔다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        self.assertIsNone(ProductBOM.objects.get(parent_label=self.label).usage_ratio)

    def test_두_번_넣어도_행이_늘지_않는다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        self._apply()
        self.assertEqual(ProductBOM.objects.filter(parent_label=self.label).count(), 1)

    def test_원료명이_없으면_400(self):
        self.assertEqual(self._apply(ingredient_name='').status_code, 400)

    def test_남의_라벨은_못_건드린다(self):
        other = User.objects.create_user(username='ing2bom2', password='x')
        self.client.force_login(other)
        self.assertEqual(self._apply().status_code, 404)


class ImportModalWiringTests(TestCase):
    """
    불러오기 모달의 배선.

    모달(import_modal.js)과 실제 처리(basic_info_ocr.js)가 나뉘어 있어, 한쪽이
    부르는 이름이 다른 쪽에 없으면 버튼만 조용히 죽는다. 눈으로는 "안 눌린다"
    로 보인다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.modal = (base / 'static/js/products/import_modal.js').read_text(encoding='utf-8')
        self.ocr = (base / 'static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.tab = (base / 'templates/products/_tab_basic_info.html').read_text(encoding='utf-8')
        self.detail = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')
        self.docs = (base / 'templates/products/_tab_documents.html').read_text(encoding='utf-8')

    def test_모달이_부르는_함수가_모두_있다(self):
        import re
        called = set(re.findall(r'window\.(basicInfoOcr\w+|ingredient\w+)\(', self.modal))
        defined = set(re.findall(r'window\.(\w+)\s*=', self.ocr))
        missing = sorted(called - defined)
        self.assertEqual(missing, [], f'정의되지 않은 함수: {missing}')

    def test_불러오기_버튼이_모달을_연다(self):
        self.assertIn('openImportModal()', self.tab)
        self.assertIn('window.openImportModal', self.modal)

    def test_두_스크립트가_모두_실린다(self):
        self.assertIn('basic_info_ocr.js', self.detail)
        self.assertIn('import_modal.js', self.detail)

    def test_원료_확인창을_문서함_탭과_함께_쓴다(self):
        """확인 창을 두 벌로 만들지 않는다."""
        self.assertIn('ingredientPhotoModal', self.docs)
        self.assertIn('ingredientPhotoModal', self.ocr)


class PhotoViewerWiringTests(TestCase):
    """
    확인 창 옆의 사진 뷰어.

    읽어낸 값이 맞는지는 결국 사진을 봐야 안다. 값만 늘어놓으면 "이게 정말 저기
    적힌 값인가" 를 확인할 방법이 없어서, 창을 닫고 사진을 따로 열어야 했다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.viewer = (base / 'static/js/products/photo_viewer.js').read_text(encoding='utf-8')
        self.ocr = (base / 'static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.detail = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')
        self.docs = (base / 'templates/products/_tab_documents.html').read_text(encoding='utf-8')

    def test_뷰어가_먼저_실린다(self):
        """basic_info_ocr 가 부를 때 이미 정의돼 있어야 한다."""
        self.assertLess(self.detail.index('photo_viewer.js'),
                        self.detail.index('basic_info_ocr.js'))

    def test_두_확인창이_같은_뷰어를_쓴다(self):
        self.assertIn('window.photoViewerLayout', self.viewer)
        self.assertIn('photoViewerLayout(', self.ocr)
        self.assertIn('photoViewerLayout(', self.docs)

    def test_회전과_확대가_있다(self):
        for act in ['rot-left', 'rot-right', 'zoom-in', 'zoom-out', 'reset']:
            self.assertIn(act, self.viewer, f'{act} 버튼이 없다')
        self.assertIn("addEventListener('wheel'", self.viewer)

    def test_문서함_사진_주소를_넘긴다(self):
        """서버에 이미 있는 사진은 주소로 띄운다."""
        self.assertIn('mediaUrl', self.detail)
        self.assertIn('mediaUrl', self.docs)

    def test_objectURL_을_놓아_준다(self):
        """창을 닫아도 안 풀면 사진이 메모리에 남는다."""
        self.assertIn('revokeObjectURL', self.viewer)


class OcrApplyExtrasEndpointTests(TestCase):
    """사진에서 읽은 영양성분·분리배출을 저장하는 경로."""

    def setUp(self):
        self.user = User.objects.create_user(username='extras', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='샐러드')

    def _post(self, **body):
        url = reverse('products:ocr_apply_extras',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps(body),
                                content_type='application/json')

    def test_영양성분이_저장된다(self):
        res = self._post(nutrition=[
            {'field': 'natriums', 'raw': '630 mg'},
            {'field': 'proteins', 'raw': '13 g'},
            {'field': 'calories', 'raw': '182 kcal'},
        ])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['nutrition_applied'], 3)

        self.label.refresh_from_db()
        self.assertEqual(self.label.natriums, '630')
        self.assertEqual(self.label.natriums_unit, 'mg')
        self.assertEqual(self.label.calories, '182')

    def test_표의_기준이_1회_제공량에_들어간다(self):
        self._post(nutrition=[{'field': 'calories', 'raw': '182 kcal'}],
                   nutrition_basis='총 내용량 139 g')
        self.label.refresh_from_db()
        self.assertEqual(self.label.serving_size, '139')
        self.assertEqual(self.label.serving_size_unit, 'g')

    def test_기준을_못_읽으면_건드리지_않는다(self):
        """기준을 잘못 바꾸면 모든 수치의 뜻이 달라진다."""
        self.label.serving_size = '100'
        self.label.save(update_fields=['serving_size'])
        self._post(nutrition=[{'field': 'calories', 'raw': '182 kcal'}],
                   nutrition_basis='알 수 없음')
        self.label.refresh_from_db()
        self.assertEqual(self.label.serving_size, '100')

    def test_무엇_당인지도_함께_저장된다(self):
        """
        값만 옮기고 **표시기준을 안 옮기면** 다시 표를 그릴 때 인쇄된 값과
        다른 숫자가 나온다. 저장값은 100 g 당인데, 표는 표시기준의 배수를
        곱해 그리기 때문이다.
        """
        self._post(nutrition=[{'field': 'calories', 'raw': '96 kcal'}],
                   nutrition_basis='총 내용량 100 g 당')
        self.label.refresh_from_db()
        self.assertEqual(self.label.basic_display_type, 'total')
        self.assertEqual(self.label.serving_size, '100')
        # 표의 기준이 총 내용량이면 단위량이 곧 총량이다
        self.assertEqual(self.label.units_per_package, '1')

    def test_100g당_표는_100을_내용량에_넣지_않는다(self):
        """
        "100 g당" 의 100 은 표를 읽는 잣대일 뿐 내용량이 아니다. 단위량에
        넣으면 65 g 짜리 제품에 "총 내용량 100 g" 이 인쇄된다 — 한 오류를
        다른 오류로 바꾸는 셈이다.
        """
        self.label.serving_size = '65'
        self.label.save(update_fields=['serving_size'])
        self._post(nutrition=[{'field': 'calories', 'raw': '96 kcal'}],
                   nutrition_basis='총 내용량 500 g / 100 g당')
        self.label.refresh_from_db()
        self.assertEqual(self.label.serving_size, '65')       # 그대로다
        self.assertEqual(self.label.basic_display_type, '100g')
        # 이미 100 g 당인 값이라 환산하지 않는다
        self.assertEqual(self.label.calories, '96')

    def test_분리배출_문구가_종류로_바뀌어_저장된다(self):
        res = self._post(recycling_mark_text='비닐류 PP / 띠지:PP, 리드지:PET')
        self.assertEqual(res.json()['recycling_type'], '비닐(PP)')
        self.label.refresh_from_db()
        self.assertEqual(self.label.prv_recycling_mark_type, '비닐(PP)')
        self.assertEqual(self.label.prv_recycling_mark_enabled, 'Y')

    def test_아무것도_안_보내도_깨지지_않는다(self):
        self.assertEqual(self._post().status_code, 200)

    def test_남의_라벨은_못_건드린다(self):
        other = User.objects.create_user(username='extras2', password='x')
        self.client.force_login(other)
        self.assertEqual(self._post(nutrition=[]).status_code, 404)


class PhotoCropperWiringTests(TestCase):
    """
    파일 -> 영역 선택 -> 판독 순서.

    판독이 틀리는 가장 큰 이유는 해상도다. detail:high 는 짧은 변을 768px 로
    맞추므로, 작업지시서처럼 라벨이 사진의 일부이면 본문이 몇 픽셀로 줄어
    읽히지 않고 모델이 지어낸다. 읽을 곳만 잘라 보내면 그 해상도가 전부
    라벨에 배정된다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.cropper = (base / 'static/js/products/photo_cropper.js').read_text(encoding='utf-8')
        self.modal = (base / 'static/js/products/import_modal.js').read_text(encoding='utf-8')
        self.detail = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')

    def test_불러오기가_자르기를_먼저_부른다(self):
        self.assertIn('window.cropPhoto', self.cropper)
        self.assertIn('window.cropPhoto(file)', self.modal)

    def test_자르기가_없어도_판독은_된다(self):
        """스크립트 로드가 실패해도 불러오기가 멈추면 안 된다."""
        self.assertIn("typeof window.cropPhoto !== 'function'", self.modal)

    def test_취소하면_아무것도_하지_않는다(self):
        self.assertIn('if (!parts || !parts.length) return;', self.modal)

    def test_표시면마다_영역을_고를_수_있다(self):
        """
        포장 사진에는 주표시면과 일괄표시면이 따로 떨어져 있다. 하나로 다
        담으려면 사이의 빈 곳까지 들어와 해상도가 다시 낮아지고, 어느 값이
        어느 면에서 나온 것인지도 알 수 없다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        self.assertIn('var ROLES', self.cropper)
        self.assertIn('주표시면', self.cropper)
        self.assertIn('일괄표시면', self.cropper)
        # 고를 때 그 면에서 무엇을 읽는지 알려 준다
        self.assertIn('crop-pick-hint', self.cropper)
        # 여러 장을 표시면 이름과 짝지어 보낸다
        ocr = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
               ).read_text(encoding='utf-8')
        self.assertIn("form.append('role'", ocr)

    def test_영역마다_따로_잘라낸다(self):
        self.assertIn('picks.map(cutOut)', self.cropper)

    def test_스크립트가_실린다(self):
        self.assertIn('photo_cropper.js', self.detail)

    def test_원본_해상도로_잘라낸다(self):
        """화면에 줄여 그린 것이 아니라 원본에서 잘라야 해상도가 남는다."""
        self.assertIn('naturalWidth', self.cropper)
        self.assertIn('sel.w / scale', self.cropper)

    def test_회전이_있다(self):
        """눕혀 찍힌 사진은 세워야 영역을 고를 수 있다."""
        self.assertIn('rot-left', self.cropper)
        self.assertIn('rot-right', self.cropper)

    def test_전체_사용도_고를_수_있다(self):
        self.assertIn("'whole'", self.cropper)

    def test_너무_작은_선택을_막는다(self):
        self.assertIn('MIN_SIDE', self.cropper)

    def test_선택_상자가_캔버스에_맞물린다(self):
        """
        스테이지 기준으로 놓으면 캔버스가 가운데 정렬된 만큼 상자가 통째로
        밀린다. 실제로 오른쪽 끝을 고를 수 없었다.
        """
        from pathlib import Path
        from django.conf import settings as dj

        self.assertIn('crop-frame', self.cropper)
        css = (Path(dj.BASE_DIR) / 'static/css/products_common.css'
               ).read_text(encoding='utf-8')
        self.assertIn('.crop-frame', css)
        self.assertIn('position:    relative', css)

    def test_표시_크기와_내부_픽셀을_환산한다(self):
        """
        캔버스가 CSS 로 줄어들면 화면 좌표와 내부 픽셀이 어긋난다.
        환산하지 않으면 오른쪽 끝에 닿지 못한다.
        """
        self.assertIn('canvas.width / r.width', self.cropper)
        self.assertIn('r.width / canvas.width', self.cropper)


class UnsavedBeforeValidationTests(TestCase):
    """
    검증·확정은 서버가 **저장된 라벨**을 다시 읽어 판정한다. 화면에만 있는 값은
    서버가 모른다.

    사진에서 소비기한을 채운 뒤 저장하지 않고 표시사항 탭에서 검증하면
    "소비기한이 비어 있습니다" 가 나왔다. 사용자에게는 분명히 적혀 있으니 영문을
    알 수 없는 지적이 된다. 플로팅 저장 바를 없앤 뒤로는 저장하라는 안내조차
    눈에 띄지 않는다.

    그래서 기본 정보 탭을 떠날 때와 확정 직전에 먼저 저장한다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.detail = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')

    def test_저장을_기다릴_수_있다(self):
        """saveBasicInfo 가 프라미스를 돌려주지 않으면 아무도 기다릴 수 없다."""
        self.assertIn('return fetch(UPDATE_URL', self.detail)

    def test_기본정보_탭을_떠날_때_저장한다(self):
        head = self.detail.index("hide.bs.tab")
        tail = self.detail.index("leavingId === '#tab-bom'")
        self.assertIn('flushBasicInfo', self.detail[head:tail],
                      '기본 정보 탭 이탈 시 저장이 걸려 있어야 한다')

    def test_확정_전에_저장을_기다린다(self):
        head = self.detail.index('async function changeStatus')
        self.assertIn('await flushBasicInfo()', self.detail[head:head + 800])

    def test_표시_항목_체크박스도_변경으로_친다(self):
        """
        .display-item-check 는 오른쪽 목차에 있어 폼 밖이다. 폼만 훑으면 체크를
        켜고 끈 것이 "저장하지 않은 변경" 으로 잡히지 않아 조용히 사라진다.
        """
        self.assertIn('function trackedFormElements', self.detail)
        self.assertIn(".display-item-check'),", self.detail)
        # 폼만 훑는 자리는 trackedFormElements 안의 한 곳뿐이어야 한다.
        # 다른 곳에 남아 있으면 그쪽에서 체크박스가 다시 새어 나간다.
        self.assertEqual(
            self.detail.count("basicInfoForm.querySelectorAll('input, textarea, select')"), 1)


class OcrApiMatchWiringTests(TestCase):
    """
    사진에서 품목보고번호가 읽히면 식약처 등록 정보와 대조한다.

    확인 창이 그 결과를 보여 주지 않으면 확신도가 왜 올라갔는지 알 수 없고,
    사용자는 여전히 열여섯 줄을 전부 눈으로 봐야 한다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.ocr = (base / 'static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_대조_결과를_확인창에_넘긴다(self):
        self.assertIn('result.api_match', self.ocr)
        self.assertIn('apiMatchHtml', self.ocr)

    def test_항목마다_어디서_온_값인지_보인다(self):
        for key in ('both', 'api', 'conflict'):
            self.assertIn(key, self.ocr, f'{key} 뱃지가 없다')
        for cls in ('.ocr-flag-ok', '.ocr-flag-api', '.ocr-api-note'):
            self.assertIn(cls, self.css, f'{cls} 스타일이 없다')

    def test_출처를_교정_이력에_남긴다(self):
        """
        나눠 재지 않으면 "등록 정보 대조가 정확도를 올렸는가" 를 영영 답할 수 없다.
        """
        self.assertIn("source: row.dataset.source", self.ocr)
        self.assertIn('data-source=', self.ocr)


class HomePhotoEntryTests(TestCase):
    """
    홈에서 "사진으로 시작하기" 를 누르면 제품이 만들어지고 불러오기 창이 바로 열린다.

    표시를 안 넘기면 사용자는 빈 제품 화면에 떨어져서 어느 버튼이 사진 읽기인지
    다시 찾아야 한다. 홈에서 광고해 놓고 도착지에서 길을 잃게 하면 안 된다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='homeuser', password='x')
        self.client.force_login(self.user)

    def test_사진으로_시작하면_불러오기_표시를_달고_이동한다(self):
        res = self.client.get(reverse('products:product_create') + '?import=1')
        self.assertEqual(res.status_code, 302)
        self.assertIn('import=1', res['Location'])

    def test_그냥_만들면_표시가_붙지_않는다(self):
        """평소 신규 등록에서 창이 튀어나오면 방해가 된다."""
        res = self.client.get(reverse('products:product_create'))
        self.assertEqual(res.status_code, 302)
        self.assertNotIn('import=1', res['Location'])

    def test_제품_화면이_그_표시를_보고_창을_연다(self):
        from pathlib import Path

        from django.conf import settings as dj

        detail = (Path(dj.BASE_DIR) / 'templates/products/product_detail.html'
                  ).read_text(encoding='utf-8')
        self.assertIn("get('import') === '1'", detail)
        # 새 제품('start')도 같은 창을 쓰므로 인자를 하나 받게 됐다.
        # 홈에서 온 경우에는 start 가 꺼져 '직접 입력하기' 띠가 안 뜬다.
        self.assertIn('window.openImportModal({start: __start})', detail)


class HomeUpdateStripTests(TestCase):
    """
    홈의 "최신 업데이트" 안내.

    새 기능은 만들어 두는 것으로 끝나지 않는다. 쓰는 사람이 있는 자리에서
    보이지 않으면 없는 기능이다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='stripuser', password='x')

    def _html(self, logged_in):
        if logged_in:
            self.client.force_login(self.user)
        return self.client.get(reverse('main:home_dashboard')).content.decode()

    def test_로그인_홈에_안내가_있다(self):
        html = self._html(True)
        self.assertIn('updStrip', html)
        self.assertIn('최신 업데이트', html)
        self.assertIn('사진으로 시작하기', html)

    def test_안내가_사진으로_시작하기로_이어진다(self):
        self.assertIn(reverse('products:product_create') + '?import=1', self._html(True))

    def test_닫으면_기억한다(self):
        """같은 안내가 매번 뜨면 배너가 아니라 소음이 된다."""
        html = self._html(True)
        self.assertIn('updStripClose', html)
        self.assertIn('ez_upd_strip_dismissed_v1', html)

    def test_앱_안내도_함께_동작한다(self):
        """
        닫기 처리를 함수 하나로 합쳤다. 합치면서 기존 앱 스트립이 안 뜨게 되는
        일이 실제로 흔하다.
        """
        html = self._html(True)
        self.assertIn('appStrip', html)
        self.assertIn('ez_app_strip_dismissed_v1', html)

    def test_비로그인_표지에도_기능이_보인다(self):
        html = self._html(False)
        self.assertIn('사진으로 등록', html)
        self.assertIn('최신 업데이트', html)

class OcrPickBarTests(TestCase):
    """
    확인 창의 선택 상태를 사용자가 알아볼 수 있어야 한다.

    이미 값이 있는 칸은 덮어쓰지 않으려고 체크를 꺼 둔다. 그런데 그걸 못 보고
    "선택 항목 채우기" 를 누르면 **아무것도 안 채워진 채 창이 닫혔다.** 사용자는
    반영된 줄 알고 저장을 누르고, 사진을 읽느라 들인 시간과 비용이 통째로
    날아갔다. 운영에서 실제로 나온 신고다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.ocr = (base / 'static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_일괄_선택_버튼이_있다(self):
        for mode in ("data-pick=\"all\"", "data-pick=\"empty\"", "data-pick=\"none\""):
            self.assertIn(mode, self.ocr, f'{mode} 버튼이 없다')
        self.assertIn('전체 선택', self.ocr)
        self.assertIn('전체 해제', self.ocr)

    def test_줄마다_무슨_일이_일어나는지_남긴다(self):
        """배지와 색이 어긋나지 않으려면 판단을 한 곳에서 해야 한다."""
        self.assertIn("data-state=", self.ocr)
        self.assertIn("row.dataset.state === 'replace'", self.ocr)
        self.assertIn("row.dataset.state === 'new'", self.ocr)

    def test_덮어쓰는_줄을_눈에_띄게_표시한다(self):
        self.assertIn('ocr-row-danger', self.ocr)
        self.assertIn('.ocr-row-danger', self.css)
        # 지워질 값에 취소선을 그어 무엇이 사라지는지 보여 준다
        self.assertIn('line-through', self.css)

    def test_선택_개수를_실시간으로_보여준다(self):
        self.assertIn('ocrPickCount', self.ocr)
        self.assertIn('refreshPickState', self.ocr)
        # 체크가 바뀔 때마다 다시 그린다
        self.assertIn("classList.contains('ocr-pick')", self.ocr)

    def test_덮어쓰기가_섞이면_경고한다(self):
        self.assertIn('기존 값을 덮어씁니다', self.ocr)
        self.assertIn('ocr-note-warn', self.css)

    def test_하나도_안_고르면_창을_닫지_않는다(self):
        """
        닫혀 버리면 사용자는 반영된 줄 알고 저장을 누른다. 무엇이 잘못됐는지
        알려 주고 창을 열어 둬야 한다.
        """
        self.assertIn('if (!state.picked)', self.ocr)
        self.assertIn('ocr-note-shake', self.ocr)
        self.assertIn('ocr-note-danger', self.css)
        # 움직임을 줄인 환경에서도 무언가는 보여야 한다
        self.assertIn('prefers-reduced-motion', self.css)

    def test_반영_버튼에_개수를_적는다(self):
        self.assertIn("apply.innerHTML = ", self.ocr)
        self.assertIn("' (' + picked + ')'", self.ocr)


class PhotoCropperZoomTests(TestCase):
    """
    확대·축소.

    4000px 짜리 사진이 화면에 900px 로 줄어 보인다. 일괄표시면의 위아래 끝이
    몇 픽셀 안에 뭉쳐서, 어디가 경계인지 짚을 수가 없었다.

    확대는 **보는 배율만** 바꾼다 — 자를 때는 언제나 원본에서 잘라내므로
    확대해서 골랐다고 화질이 달라지지 않는다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.cropper = (base / 'static/js/products/photo_cropper.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_확대_축소_맞춤_단추가_있다(self):
        for what in ('zoom-in', 'zoom-out', 'zoom-fit'):
            self.assertIn(what, self.cropper)

    def test_확대해도_고른_영역이_남는다(self):
        """확대할 때마다 다시 고르게 하면 확대가 아무 쓸모가 없다."""
        # 좌표계가 통째로 바뀌는 회전(refit)에서만 비운다
        head = self.cropper.index('if (refit) {')
        block = self.cropper[head:head + 400]
        self.assertIn('picks = [];', block)
        # 배율만 바뀌었으면 바뀐 만큼 늘려 준다
        self.assertIn('var k = scale / prev;', self.cropper)

    def test_확대해도_창이_늘어나지_않는다(self):
        """스테이지 안에서 스크롤해 훑는다 — 아래의 영역 목록이 밀려나면 안 된다."""
        self.assertIn('stage.style.maxHeight', self.cropper)
        head = self.css.index('.crop-stage {')
        self.assertIn('overflow:   auto', self.css[head:head + 300])

    def test_확대하면_CSS_가_도로_줄이지_않는다(self):
        """max-width 가 남아 있으면 캔버스를 키워도 화면에서는 그대로다."""
        head = self.css.index('.crop-canvas {')
        self.assertNotIn('max-width', self.css[head:head + 200])

    def test_자를_때는_배율과_무관하게_원본에서_자른다(self):
        self.assertIn('sel.w / scale', self.cropper)
        self.assertIn('naturalWidth', self.cropper)


class PhotoCropperMaskTests(TestCase):
    """
    제외할 영역.

    일괄표시면 옆에 작업지시서 표나 다른 제품의 라벨이 같이 찍혀 있으면
    사각형 하나로는 피해 갈 수가 없다. 빼고 싶은 자리를 덮어 두면 그 자리는
    흰색으로 지워 보낸다 — 모델이 아예 못 본다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.cropper = (base / 'static/js/products/photo_cropper.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_제외_모드로_바꿀_수_있다(self):
        self.assertIn('mode-mask', self.cropper)
        self.assertIn('제외할 영역', self.cropper)

    def test_제외한_자리를_흰색으로_지워_보낸다(self):
        head = self.cropper.index('function cutOut')
        block = self.cropper[head:self.cropper.index('modalEl.querySelector(\'.modal-body\')')]
        self.assertIn("octx.fillStyle = '#ffffff'", block)
        self.assertIn('masks.forEach', block)

    def test_전체_사용도_제외를_반영한다(self):
        """제외만 골랐으면 원본을 그대로 보내면 안 된다."""
        self.assertIn("deg % 360 === 0 && !masks.length", self.cropper)

    def test_모두_지우기가_제외도_지운다(self):
        head = self.cropper.index("if (what === 'clear')")
        self.assertIn('masks = []', self.cropper[head:head + 120])

    def test_제외_상자는_색만으로_구분하지_않는다(self):
        """색각 이상에서도 갈려야 한다 — 빗금을 깐다."""
        self.assertIn('.crop-box--mask', self.css)
        self.assertIn('repeating-linear-gradient', self.css)

    def test_작은_제외도_받는다(self):
        """바코드 한 줄, 도장 하나를 가리는 일이 실제로 많다."""
        self.assertIn('MIN_MASK_SIDE', self.cropper)


class LabelPhotoToDocumentTests(TestCase):
    """
    사진으로 불러오기에 쓴 원본 사진을 문서함에 남긴다.

    판독값은 사진에서 나온 것이고, 그 사진이 없으면 나중에 "이 값이 어디서
    왔는지" 를 되짚을 수가 없다. 표시사항은 법적 표시물이라 근거가 남아야 한다.

    문서 종류는 사용자가 찾는 자리(한글표시사항도안)와 같게 두되, **도안을
    만든 것과는 구분한다** — 사진 한 장 올린 것이 "표시사항 완료" 가 되면 안 되고,
    확정 통보 메일에 PDF 대신 JPG 가 붙어도 안 된다.
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from v1.label.models import MyLabel

        self.user = User.objects.create_user(username='photo', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='제품', prdlst_nm='제품')
        self.photo = lambda: SimpleUploadedFile(
            '표시면.jpg', b'\xff\xd8\xff\xe0fake', content_type='image/jpeg')

    def _post(self):
        return self.client.post(
            f'/products/labels/{self.label.my_label_id}/label-photo/',
            {'image': self.photo()})

    def test_문서함에_한글표시사항도안으로_남는다(self):
        from v1.products.models import ProductDocument

        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

        doc = ProductDocument.objects.get(label=self.label)
        self.assertEqual(doc.document_type.type_code, 'LABEL_DESIGN')
        self.assertEqual(doc.metadata.get('source'), 'ocr_import')
        self.assertEqual(doc.file_extension, '.jpg')

    def test_다시_올리면_판이_올라간다(self):
        from v1.products.models import ProductDocument

        self.assertEqual(self._post().json()['version'], 1)
        self.assertEqual(self._post().json()['version'], 2)
        self.assertEqual(ProductDocument.objects.filter(label=self.label).count(), 2)

    def test_사진만_올려서는_표시사항_완료가_아니다(self):
        """
        제품 목록의 표시사항 체크는 "도안을 만들었다" 는 뜻이다. 사진 한 장을
        올린 것과는 다르다.
        """
        self._post()
        r = self.client.get('/products/explorer/')
        if r.status_code != 200:      # 화면 경로가 다르면 질의만 직접 확인한다
            from v1.products.models import ProductDocument
            self.assertEqual(
                ProductDocument.objects
                .filter(label=self.label, document_type__type_code='LABEL_DESIGN',
                        active_yn=True)
                .exclude(metadata__source='ocr_import').count(), 0)
            return
        item = next(i for i in r.context['products_data']
                    if i['label'].my_label_id == self.label.my_label_id)
        self.assertFalse(item['label_checked'])

    def test_확정_통보에는_PDF_만_붙인다(self):
        """
        이 자리에는 사진(JPG)도 들어간다. 확장자를 안 보면 그 사진을 집어
        application/pdf 로 붙이게 되고, 받는 쪽에서는 열리지 않는 첨부가 된다.
        """
        from v1.products.views import _latest_label_pdf

        self._post()
        self.assertIsNone(_latest_label_pdf(self.label))

    def test_남의_제품에는_못_넣는다(self):
        from v1.label.models import MyLabel

        other = User.objects.create_user(username='photo2', password='x')
        theirs = MyLabel.objects.create(user_id=other, my_label_name='남의 제품',
                                        prdlst_nm='남의 제품')
        r = self.client.post(f'/products/labels/{theirs.my_label_id}/label-photo/',
                             {'image': self.photo()})
        self.assertIn(r.status_code, (403, 404))

    def test_사진이_없으면_400(self):
        r = self.client.post(f'/products/labels/{self.label.my_label_id}/label-photo/', {})
        self.assertEqual(r.status_code, 400)

    def test_판독_직후_보내되_기다리지_않는다(self):
        """문서 저장이 늦거나 실패해도 판독 결과를 보는 일이 막히면 안 된다."""
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
              ).read_text(encoding='utf-8')
        self.assertIn('function saveSourcePhoto', js)
        self.assertIn('saveSourcePhoto(sourceFile || parts[0].file);', js)
        # showModal 앞에서 부르되 await/then 으로 묶지 않는다
        at = js.index('saveSourcePhoto(sourceFile || parts[0].file);')
        self.assertLess(at, js.index('showModal(result.data || {}, file,'))

class DesignCompareModeTests(TestCase):
    """
    ② 대조 모드 — 채우지 않고 다른 곳만 보여 준다.

    같은 판독을 두 가지 뜻으로 쓴다.

        채우기   빈 제품에 값을 넣는다 (표시사항을 만드는 단계)
        대조     확정한 값과 디자인 시안이 같은지 본다 (인쇄 전 검증 단계)

    뒤엣것에 앞엣것을 쓰면 위험하다. 확인 창이 빈 칸을 미리 체크해 두므로,
    무심코 "채우기" 를 누르면 확정한 값 위에 시안에서 읽은 값이 덮인다.
    시안이 틀려서 대조하는 것인데 틀린 쪽을 정본으로 삼게 되는 셈이다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.ocr = (base / 'static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.modal = (base / 'static/js/products/import_modal.js').read_text(encoding='utf-8')
        self.tab = (base / 'templates/products/_tab_label.html').read_text(encoding='utf-8')
        self.preview = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_대조는_표시사항_탭에_있다(self):
        """
        5단계 도구는 5단계 자리에. 값을 채우는 창(불러오기)에 두면 인쇄
        직전에 "채우기" 를 눌러 확정한 값을 시안으로 덮어쓰게 된다.
        """
        self.assertIn('window.basicInfoOcrCompare', self.ocr)
        # 단추는 미리보기 쪽 설정 패널로 옮겼지만, **판독은 여전히 여기서**
        # 한다 — 시안 파일 고르기·자르기가 여기 있고 옮기면 두 벌이 된다.
        self.assertIn('id="ltCompareBtn"', self.preview)
        self.assertIn('window.ltStartCompare', self.tab)
        self.assertIn('basicInfoOcrCompare', self.tab)

    def test_불러오기_창에는_없다(self):
        self.assertNotIn('function compareZone', self.modal)
        self.assertNotIn("data-side=\"compare\"", self.modal)

    def test_대조_창에는_채우기가_없다(self):
        """고칠 수 있으면 "시안이 이렇다" 와 "내 값을 바꾸겠다" 가 섞인다."""
        # 길이로 자르면 함수가 자랄 때마다 끊긴다. '어디서?' 단추를 더하자
        # 1,600 자를 넘어 cmp-theirs 가 잘려 나갔다 — 함수 끝까지 본다.
        head = self.ocr.index('function compareRowHtml')
        block = self.ocr[head:self.ocr.index(chr(10) + '  }', head)]
        self.assertNotIn('ocr-pick', block)      # 체크박스
        self.assertNotIn('ocr-value', block)     # 고칠 칸
        self.assertIn('cmp-theirs', block)

    def compare_body(self):
        """
        대조 화면을 **그리는** 한 덩이. 길이로 자르면 함수가 자랄 때마다 끊긴다.

        한때 showCompare 하나였다. 판정을 서버로 옮기면서 showCompare 는
        "값을 모아 묻는" 일만 하고, 그리는 일은 drawCompare 로 갈라졌다.
        여기서 보려는 것은 그리는 쪽이다.
        """
        head = self.ocr.index('function drawCompare')
        return self.ocr[head:self.ocr.index(chr(10) + '  }', head)]

    def test_반영_단추를_감춘다(self):
        block = self.compare_body()
        self.assertIn("apply.style.display = 'none'", block)
        self.assertIn('값을 고치지 않습니다', block)

    def test_채우기_창은_원래대로_돌아온다(self):
        """창이 한 벌이라, 되돌리지 않으면 다음 채우기에서 단추가 사라진다."""
        self.assertIn("applyBtn.style.display = ''", self.ocr)
        self.assertIn('체크한 항목만 채웁니다', self.ocr)

    def test_깃발은_한_번만_쓴다(self):
        """남겨 두면 다음에 채우기로 연 창이 대조 화면으로 뜬다."""
        head = self.ocr.index('var comparing = compareMode;')
        block = self.ocr[head:head + 300]
        self.assertIn('compareMode = false;', block)

    def test_읽지_못하면_깃발을_내린다(self):
        head = self.ocr.index('window.basicInfoOcrCompare')
        block = self.ocr[head:head + 500]
        self.assertIn('compareMode = false;', block)

    def test_확인할_것부터_보여_준다(self):
        """같은 것 열여섯 줄을 지나야 다른 두 줄이 나오면 대조하는 뜻이 없다."""
        block = self.compare_body()
        self.assertLess(block.index("'확인할 항목'"), block.index("'같은 항목'"))

    def test_띄어쓰기만_다른_것은_따로_센다(self):
        """
        여덟 줄이 "다름" 으로 나왔는데 절반이 쉼표 뒤 공백 차이였다. 인쇄물에서
        그것은 조판이 정하는 것이지 표시 내용이 아니다. 같은 무게로 쌓이면
        진짜 다른 줄이 그 안에 묻힌다.
        """
        self.assertIn('function compareGrade', self.ocr)
        self.assertIn('function compareKey', self.ocr)
        head = self.ocr.index('function compareGrade')
        block = self.ocr[head:head + 900]
        self.assertIn("return 'spacing'", block)
        self.assertIn("return 'partial'", block)

    def test_어디가_다른지_짚어_준다(self):
        """300자짜리 원재료명 두 줄을 눈으로 대조하게 두지 않는다."""
        self.assertIn('function markDifference', self.ocr)
        self.assertIn('cmp-mark', self.ocr)

    def test_덜_읽힌_것을_다르다고_말하지_않는다(self):
        """
        시안은 표시사항이 그림 한구석에 작게 들어 있다. 전체를 올리면 절반만
        읽히는데, 그건 시안이 틀린 것이 아니라 우리가 덜 읽은 것이다.
        """
        head = self.ocr.index('var thin = record.filter')
        block = self.ocr[head:head + 900]
        self.assertIn('cmp-advice', block)
        self.assertIn('잘라', block)

    def test_다른_줄이_눈에_띈다(self):
        self.assertIn('.cmp-row.cmp-diff', self.css)
        self.assertIn('.lt-toolbar', self.css)

    def test_대조를_문서함에_남긴다(self):
        """
        대조만 하고 아무것도 안 남기면 "확인했다" 는 말만 남는다. 누가 언제
        어느 시안과 맞춰 봤고 무엇이 달랐는지가 있어야 절차가 된다.
        """
        self.assertIn('function recordCompare', self.ocr)
        self.assertIn('/design-compare/', self.ocr)
        # 화면 HTML 이 아니라 값 자체를 남긴다
        head = self.ocr.index('record.push({')
        self.assertIn('label: meta.label', self.ocr[head:head + 200])
        self.assertIn('design: theirs', self.ocr[head:head + 200])

class DesignCompareRecordTests(TestCase):
    """
    ③ 대조 기록 + ④ 도안 슬롯.

    대조만 하고 아무것도 안 남기면 "확인했다" 는 말만 남는다. 누가 언제 어느
    시안과 맞춰 봤고 무엇이 달랐는지가 있어야 절차가 된다 — 인쇄가 나온 뒤에
    "그때 뭘 봤더라" 를 다시 세지 않아도 된다.
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.upload = SimpleUploadedFile
        self.user = User.objects.create_user(username='cmp', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='대조')
        ProductMetadata.objects.create(label=self.label)
        self.client.force_login(self.user)
        self.url = reverse('products:design_compare_record', args=[self.label.my_label_id])

    def _post(self, diff=None, same=3, with_file=True):
        data = {'result': json.dumps({'diff': diff or [], 'same': same})}
        if with_file:
            data['design_file'] = self.upload('시안.png', b'fake-image', content_type='image/png')
        return self.client.post(self.url, data)

    def test_시안이_문서함에_들어간다(self):
        from v1.products.models import ProductDocument

        resp = self._post(diff=[{'field': 'prdlst_nm', 'label': '제품명',
                                 'mine': '브라우니 케이크', 'design': '브라우니케이크'}])
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        doc = ProductDocument.objects.get(label=self.label)
        self.assertEqual(doc.document_type.type_code, 'DESIGN_PROOF')
        self.assertEqual(doc.version, 1)

    def test_대조_결과가_그_파일에_붙는다(self):
        """파일과 결과가 따로 놀면 "이 시안을 본 결과인가" 를 알 수 없다."""
        from v1.products.models import ProductDocument

        self._post(diff=[{'field': 'content_weight', 'label': '내용량',
                          'mine': '65 g', 'design': '70 g'}], same=5)
        compare = ProductDocument.objects.get(label=self.label).metadata['compare']
        self.assertEqual(compare['diff_count'], 1)
        self.assertEqual(compare['same_count'], 5)
        self.assertEqual(compare['diff'][0]['label'], '내용량')
        self.assertEqual(compare['checked_by'], 'cmp')
        self.assertTrue(compare['checked_at'])

    def test_활동_로그에도_남는다(self):
        from v1.products.models import ProductActivityLog

        self._post(diff=[{'field': 'prdlst_nm', 'label': '제품명',
                          'mine': 'A', 'design': 'B'}])
        log = ProductActivityLog.objects.get(label=self.label, action='DESIGN_COMPARED')
        self.assertEqual(log.details['diff_count'], 1)
        self.assertEqual(log.details['fields'], ['제품명'])
        self.assertEqual(log.details['file_name'], '시안.png')

    def test_같은_제품을_다시_대조하면_버전이_오른다(self):
        from v1.products.models import ProductDocument

        self._post()
        self._post()
        versions = sorted(ProductDocument.objects.filter(label=self.label)
                          .values_list('version', flat=True))
        self.assertEqual(versions, [1, 2])

    def test_우리가_낸_도안과_다른_칸에_쌓인다(self):
        """
        하나는 우리가 낸 것(한글표시사항도안)이고 하나는 받은 것이다.
        같은 칸에 쌓으면 어느 것이 정본인지 알 수 없다.
        """
        from v1.products.models import DocumentType

        self._post()
        self.assertNotEqual(
            DocumentType.objects.get(type_code='DESIGN_PROOF').type_code, 'LABEL_DESIGN')

    def test_파일_없이도_기록은_남는다(self):
        from v1.products.models import ProductActivityLog, ProductDocument

        resp = self._post(with_file=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['document_id'])
        self.assertFalse(ProductDocument.objects.filter(label=self.label).exists())
        self.assertTrue(ProductActivityLog.objects.filter(
            label=self.label, action='DESIGN_COMPARED').exists())

    def test_남의_제품에는_남길_수_없다(self):
        other = User.objects.create_user(username='other', password='x')
        self.client.force_login(other)
        self.assertEqual(self._post().status_code, 404)


class WorkflowStepTabsTests(TestCase):
    """
    탭이 업무 순서라는 것을 화면이 드러내야 한다.

    기본 정보 → BOM → 영양성분 → 표시사항. 나란한 탭으로만 두면 처음 쓰는
    사람은 어디부터 손대야 하는지 알 수 없었다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='wf', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='순서')
        ProductMetadata.objects.create(label=self.label)

    def test_네_단계에_번호와_설명이_붙는다(self):
        from v1.products.views import _build_workflow_steps

        steps = _build_workflow_steps(self.label)
        self.assertEqual([s['no'] for s in steps], [1, 2, 3, 4])
        self.assertEqual([s['tab'] for s in steps],
                         ['tab-info', 'tab-bom', 'tab-nutrition', 'tab-label'])
        for step in steps:
            self.assertTrue(step['hint'], f"{step['name']} 에 설명이 없다")

    def test_채운_단계는_마친_것으로_보인다(self):
        from v1.products.views import _build_workflow_steps

        done = {s['tab']: s['done'] for s in _build_workflow_steps(self.label)}
        self.assertFalse(done['tab-info'])

        self.label.prdlst_nm = '브라우니'
        self.label.content_weight = '65 g'
        self.label.calories = '475'
        self.label.save()
        done = {s['tab']: s['done'] for s in _build_workflow_steps(self.label)}
        self.assertTrue(done['tab-info'])
        self.assertTrue(done['tab-nutrition'])

    def test_문서함과_권한은_단계가_아니다(self):
        from v1.products.views import _build_workflow_steps

        tabs = [s['tab'] for s in _build_workflow_steps(self.label)]
        self.assertNotIn('tab-docs', tabs)
        self.assertNotIn('tab-share', tabs)

    def test_화면이_번호와_화살표를_그린다(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        html = (base / 'templates/products/product_detail.html').read_text(encoding='utf-8')
        css = (base / 'static/css/products_detail.css').read_text(encoding='utf-8')

        self.assertIn('workflow_steps', html)
        self.assertIn('wf-no', html)
        self.assertIn('#workspaceTab .wf-step + .wf-step::before', css)
        self.assertIn('#workspaceTab .wf-aside', css)


class DocumentVersionStackTests(TestCase):
    """
    같은 문서가 목록에 세 번 나오는 것은 세 개의 문서가 아니라 한 문서의 세
    판이다. 줄이 늘어날수록 "무슨 문서를 갖고 있는가" 가 판 수에 묻힌다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument
        self.DocumentType, self.ProductDocument = DocumentType, ProductDocument
        self.user = User.objects.create_user(username='docstack', password='x')
        self.label = MyLabel.objects.create(user_id=self.user,
                                            my_label_name='브라우니')
        self.dtype = self.DocumentType.objects.create(
            type_code='KR_LABEL', type_name='한글표시사항도안')

    def _doc(self, name, version=1, parent=None):
        return self.ProductDocument.objects.create(
            label=self.label, document_type=self.dtype,
            file='v2/product_documents/%s' % name,
            original_filename=name, version=version, parent_document=parent)

    def test_판이_쌓여도_줄은_하나다(self):
        """
        새 판은 **바로 앞 판**을 가리킨다. 뿌리가 아니다.

            v1 <- v2 <- v3

        한 칸만 보고 묶으면 v1·v2 만 한 묶음이 되고 v3 은 새 문서로 선다.
        실제로 그렇게 나왔다 - 다섯 판짜리 도안이 목록에 네 줄로 있었다.
        """
        from v1.products.views import version_stacks
        v1 = self._doc('도안.jpg', 1)
        v2 = self._doc('도안.jpg', 2, v1)
        self._doc('도안.jpg', 3, v2)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['count'], 3)
        self.assertEqual(groups[0]['latest'].version, 3)
        self.assertEqual([d.version for d in groups[0]['older']], [2, 1])

    def test_뿌리를_가리키는_옛_자료도_묶는다(self):
        # 예전에 올린 것들은 전부 뿌리를 가리킨다. 둘 다 한 묶음이어야 한다.
        from v1.products.views import version_stacks
        root = self._doc('도안.jpg', 1)
        self._doc('도안.jpg', 2, root)
        self._doc('도안.jpg', 3, root)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['count'], 3)

    def test_사라진_조상을_가리켜도_형제는_한_묶음이다(self):
        from v1.products.views import version_stacks
        gone = self._doc('없어질것.jpg', 1)
        a = self._doc('도안.jpg', 2, gone)
        b = self._doc('도안.jpg', 3, gone)
        groups = version_stacks([b, a])          # 조상은 목록에 없다
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['latest'].document_id, b.document_id)

    def test_다른_문서는_따로_센다(self):
        from v1.products.views import version_stacks
        root = self._doc('도안.jpg', 1)
        self._doc('도안.jpg', 2, root)
        self._doc('시안.jpg', 1)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(g['count'] for g in groups), [1, 2])

    def test_판이_하나면_묶을_것도_없다(self):
        from v1.products.views import version_stacks
        self._doc('혼자.jpg', 1)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(groups[0]['older'], [])

    def test_들어온_순서를_지킨다(self):
        # 최신 판이 나왔을 자리에 그 묶음이 선다
        from v1.products.views import version_stacks
        first = self._doc('가.jpg', 1)
        self._doc('나.jpg', 1)
        self._doc('가.jpg', 2, first)
        docs = list(self.ProductDocument.objects.filter(label=self.label)
                    .order_by('document_id'))
        groups = version_stacks(docs)
        self.assertEqual([g['latest'].original_filename for g in groups],
                         ['가.jpg', '나.jpg'])

    def test_사슬이_끊긴_판도_이어_붙인다(self):
        """
        판 번호는 (제품, 문서 종류) 안에서 하나의 줄로 매겨진다. 그러니 판 2
        이상인데 위로 이어진 데가 없는 것은 홀로 선 문서가 아니라 사슬이 끊긴
        판이다. 옛 자료나 이어 달기 전에 들어온 것이 그렇게 남아 있다.
        """
        from v1.products.views import version_stacks
        self._doc('도안.jpg', 1)
        self._doc('도안.jpg', 2)      # 이어진 데가 없다
        self._doc('도안.jpg', 3)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['count'], 3)
        self.assertEqual(groups[0]['latest'].version, 3)

    def test_판_1_은_따로_선다(self):
        # 판 1 은 정말 새 문서일 수 있다. 번호로 넘겨짚지 않는다.
        from v1.products.views import version_stacks
        self._doc('가.jpg', 1)
        self._doc('나.jpg', 1)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(len(groups), 2)

    def test_종류가_다르면_번호가_겹쳐도_안_섞인다(self):
        from v1.products.views import version_stacks
        other = self.DocumentType.objects.create(type_code='PROOF',
                                                 type_name='포장지 시안')
        self._doc('도안.jpg', 1)
        self._doc('도안.jpg', 2)
        self.ProductDocument.objects.create(
            label=self.label, document_type=other,
            file='v2/product_documents/s.jpg', original_filename='시안.jpg',
            version=2)
        groups = version_stacks(
            self.ProductDocument.objects.filter(label=self.label))
        self.assertEqual(sorted(g['count'] for g in groups), [1, 2])

    def test_빈_목록도_받는다(self):
        from v1.products.views import version_stacks
        self.assertEqual(version_stacks([]), [])


class DocumentTabLooksLikeTheRestTests(TestCase):
    """
    준수율 바가 도넛에 두 줄짜리 칩이라 이 줄 하나가 60px 을 넘게 먹었고,
    구분·상태·버전이 저마다 색 있는 배지라 표가 알록달록했다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.html = (Path(dj.BASE_DIR) / 'templates/products/_tab_documents.html'
                     ).read_text(encoding='utf-8')

    def test_도넛_차트는_없앴다(self):
        self.assertNotIn('circular-chart', self.html)
        self.assertNotIn('compliance-dial', self.html)
        self.assertNotIn('compliance-strip', self.html)

    def test_한_줄짜리_현황_바를_쓴다(self):
        self.assertIn('doc-status-bar', self.html)
        self.assertIn('doc-progress-bar', self.html)
        self.assertIn('min-height: 40px', self.html)

    def test_갖춘_칩은_조용하다(self):
        # 다섯이 다 색을 쓰면 어느 것이 문제인지 알 수 없다
        head = self.html.index("{% if slot.status != 'VALID' %}")
        self.assertIn('없음', self.html[head:head + 260])

    def test_목록은_묶음을_돈다(self):
        self.assertIn('{% for group in document_groups %}', self.html)
        self.assertNotIn('{% for doc in documents %}', self.html)

    def test_이전_판은_접혀_있다(self):
        self.assertIn('.doc-version-row { display: none; }', self.html)
        self.assertIn('.doc-version-row.open { display: table-row; }', self.html)
        self.assertIn('function toggleDocVersions', self.html)

    def test_걸러낼_때_판_줄도_같이_감춘다(self):
        self.assertIn('function showDocRow', self.html)
        self.assertIn('showDocRow(row, shouldShow)', self.html)
        self.assertNotIn("row.style.display = shouldShow ? '' : 'none';", self.html)


class DocumentTabRendersTests(TestCase):
    """탭이 실제로 그려지는가. 틀만 고쳐 놓고 깨뜨리면 아무 소용이 없다."""

    def test_판이_쌓인_제품_화면이_열린다(self):
        from v1.products.models import DocumentType, ProductDocument
        user = User.objects.create_user(username='docrender', password='x')
        self.client.force_login(user)
        label = MyLabel.objects.create(user_id=user, my_label_name='브라우니')
        dtype = DocumentType.objects.create(type_code='KR_LABEL',
                                            type_name='한글표시사항도안')
        # 실제 화면에서 나온 모양 그대로: 판이 줄로 이어진다 (v1 <- v2 <- v3 <- v4)
        prev = None
        for n in range(1, 5):
            prev = ProductDocument.objects.create(
                label=label, document_type=dtype,
                file='v2/product_documents/%d.jpg' % n,
                original_filename='도안.jpg', version=n,
                parent_document=prev, uploaded_by=user)

        res = self.client.get(reverse('products:product_detail',
                                      args=[label.my_label_id]))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode('utf-8')
        self.assertIn('doc-status-bar', body)
        # 두 판이 한 줄로 묶여 이전 판 줄이 하나 따라붙는다
        self.assertEqual(body.count('class="document-row cursor-pointer"'), 1)
        self.assertEqual(body.count('class="doc-version-row"'), 1)
        self.assertIn('toggleDocVersions', body)
        self.assertIn('>4</span>', body)      # 판 수


class DocumentModalsShareOneSkinTests(TestCase):
    """
    문서 모달 넷이 저마다 달랐다. 모서리가 16px·14px·기본으로 셋, 머리글이
    회색 바탕인 것과 아닌 것, 제목이 h5 16px·h6·h5 굵게로 셋, 단추가
    v2-btn·v2-btn-sm·rounded-pill px-4 fw-bold 로 셋.

    같은 문서함에서 열리는 창들인데 열 때마다 다른 화면처럼 보였다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.upload = (base / 'templates/products/_modal_upload.html'
                       ).read_text(encoding='utf-8')
        self.docs = (base / 'templates/products/_tab_documents.html'
                     ).read_text(encoding='utf-8')
        self.detail = (base / 'templates/products/product_detail.html'
                       ).read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css'
                    ).read_text(encoding='utf-8')

    def test_넷_다_같은_껍데기를_쓴다(self):
        self.assertIn('smart-upload-modal doc-modal', self.upload)
        for html, modal in ((self.docs, 'editDocumentModal'),
                            (self.docs, 'importCompanyDocModal'),
                            (self.docs, 'ingredientPhotoModal'),
                            (self.detail, 'addSlotModal')):
            head = html.index('id="%s"' % modal)
            self.assertIn('doc-modal', html[head - 90:head], modal)

    def test_껍데기가_한_곳에_있다(self):
        for rule in ('.doc-modal .modal-content',
                     '.doc-modal .modal-header',
                     '.doc-modal .modal-footer',
                     '.doc-modal .form-label'):
            self.assertIn(rule, self.css)

    def test_모서리를_저마다_정하지_않는다(self):
        self.assertNotIn('border-radius: 16px;', self.upload)
        for html in (self.docs, self.detail):
            self.assertNotIn('style="border-radius: 16px;"', html)
            self.assertNotIn('style="border-radius: 14px; overflow: hidden;"', html)

    def test_단추는_v2_하나로(self):
        self.assertNotIn('rounded-pill px-4 fw-bold', self.upload)
        self.assertNotIn('btn btn-primary rounded-pill px-4"', self.detail)

    def test_업로드_창의_제목은_머리에_있다(self):
        head = self.upload.index('id="smartUploadModal"')
        block = self.upload[head:head + 1800]
        self.assertLess(block.index('class="modal-header"'),
                        block.index('class="modal-body'))
        self.assertIn('id="upload-modal-title"', block)


class DropKeepsTheChosenTypeTests(TestCase):
    """
    문서 종류를 고른 뒤 파일을 끌어다 놓으면 고른 종류가 지워졌다.

    끌기 시작하면 화면 전체를 덮는 오버레이가 뜨는 탓에 창 안의 드롭 영역이
    파일을 받을 수 없어서, 창 안에 놓아도 늘 window 의 drop 으로 왔다. 거기서
    openUploadModal 을 다시 부르는데 그 함수가 폼을 초기화한다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.html = (Path(dj.BASE_DIR) / 'templates/products/_tab_documents.html'
                     ).read_text(encoding='utf-8')
        self.js = (Path(dj.BASE_DIR) / 'static/js/smart_upload.js'
                   ).read_text(encoding='utf-8')

    def test_이미_열려_있으면_다시_열지_않는다(self):
        head = self.html.index("window.addEventListener('drop'")
        block = self.html[head:head + 1600]
        self.assertIn("querySelector('#smartUploadModal.show')", block)
        self.assertLess(block.index('alreadyOpen'), block.index('openUploadModal('))

    def test_그래도_파일은_받는다(self):
        head = self.html.index('const alreadyOpen')
        self.assertIn('handleFileSelect(files[0])', self.html[head:head + 320])

    def test_여는_함수가_폼을_초기화한다는_사실은_그대로다(self):
        # 이 전제가 깨지면 위 우회가 필요 없어진다 - 그때 같이 지워야 한다
        head = self.js.index('function openUploadModal')
        self.assertIn('resetUploadForm();', self.js[head:head + 400])


class TypeScaleIsOneScaleTests(TestCase):
    """
    9px·10px 글씨가 하필 **가장 먼저 읽어야 하는 것**에 쓰이고 있었다.

    권한 탭은 역할 이름이 9px 였고(열일곱 군데), 연락처 화면은 인라인
    font-size 가 백 군데 가까이 흩어져 같은 성격의 글씨가 자리마다 달랐다.
    이 저장소가 스스로 정해 둔 본문 최소치는 12px 이다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.perm = (base / 'templates/products/_tab_permissions.html'
                     ).read_text(encoding='utf-8')
        self.contacts = (base / 'templates/products/contacts.html'
                         ).read_text(encoding='utf-8')
        self.css = (base / 'static/css/contacts.css').read_text(encoding='utf-8')

    def test_9px_글씨는_없앴다(self):
        self.assertNotIn('font-size: 9px', self.perm)
        self.assertNotIn('font-size:9px', self.perm)

    def test_10px_도_없앴다(self):
        for html in (self.perm, self.contacts):
            self.assertNotIn('font-size:10px', html)
            self.assertNotIn('font-size: 10px', html)

    def test_눈금은_한_벌이다(self):
        for rule in ('.pw-xs', '.pw-sm', '.pw-md', '.pw-lg'):
            self.assertIn(rule, self.perm)
        for rule in ('.ct-xs', '.ct-sm', '.ct-md', '.ct-lg'):
            self.assertIn(rule, self.css)

    def test_class_가_두_번_붙은_태그가_없다(self):
        # 두 번 붙으면 HTML 은 앞의 것만 본다 — 뒤에 넣은 것이 조용히 사라진다
        import re
        pat = re.compile(r'<[a-zA-Z][^>]*?class="[^"]*"[^>]*?\sclass="')
        for name, html in (('권한', self.perm), ('연락처', self.contacts)):
            self.assertEqual(pat.findall(html), [], name)

    def test_역할_뱃지는_문서함과_같은_결이다(self):
        # 부트스트랩의 채운 색 다섯을 쓰다가 이 탭만 알록달록하게 남았다
        self.assertIn('.role-tag', self.perm)
        for role in ('role-owner', 'role-uploader', 'role-editor',
                     'role-reviewer', 'role-approver', 'role-viewer'):
            self.assertIn(role, self.perm)

    def test_연락처_모달도_같은_껍데기를_쓴다(self):
        self.assertIn('class="modal fade doc-modal" id="submitDocModal"',
                      self.contacts)


class SupplierSeesOnlyOwnDocumentsTests(TestCase):
    """
    시험성적서 하나 내라고 부른 협력업체가 그 제품 문서함의 **모든 것**을
    받을 수 있었다 — 다른 협력업체의 규격서, 아직 안 나온 포장지 도안,
    품목제조보고서, HACCP 인증서.

    권한은 제품 단위였고 다섯 역할이 전부 can_download_documents=True 였다.
    내려받기 검사는 문서를 아예 보지 않았다.
    """

    def setUp(self):
        from v1.products.models import (DocumentType, ProductDocument,
                                        ProductShare, SharePermission)
        self.Doc, self.Share, self.Perm = ProductDocument, ProductShare, SharePermission
        self.owner = User.objects.create_user(username='주인', password='x',
                                              email='owner@x.com')
        self.supplier = User.objects.create_user(username='협력사', password='x',
                                                 email='sup@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner,
                                            my_label_name='브라우니')
        dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.mine = ProductDocument.objects.create(
            label=self.label, document_type=dtype, file='v2/product_documents/a.pdf',
            original_filename='내가올린것.pdf', uploaded_by=self.supplier)
        self.theirs = ProductDocument.objects.create(
            label=self.label, document_type=dtype, file='v2/product_documents/b.pdf',
            original_filename='남의규격서.pdf', uploaded_by=self.owner)

    def _share(self, role):
        share = self.Share.objects.create(
            label=self.label, recipient_email=self.supplier.email,
            recipient_user=self.supplier, share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        perm = self.Perm.objects.create(share=share)
        perm.apply_role_defaults(role_code=role, save=True)
        return share, perm

    def test_자료_제출자는_자기_것만_받는다(self):
        from v1.common.media_access import user_can_download_label_files
        self._share('UPLOADER')
        self.assertTrue(user_can_download_label_files(
            self.supplier, self.label, self.mine))
        self.assertFalse(user_can_download_label_files(
            self.supplier, self.label, self.theirs))

    def test_목록에서도_남의_것은_안_보인다(self):
        # 파일을 못 받아도 목록에 보이면 거래처와 서류 종류가 드러난다
        from v1.common.media_access import visible_documents
        self._share('UPLOADER')
        seen = visible_documents(self.supplier, self.label,
                                 self.Doc.objects.filter(label=self.label))
        self.assertEqual([d.document_id for d in seen], [self.mine.document_id])

    def test_내부_팀은_전부_본다(self):
        from v1.common.media_access import (user_can_download_label_files,
                                            visible_documents)
        for role in ('EDITOR', 'REVIEWER', 'APPROVER'):
            self.Share.objects.filter(label=self.label).delete()
            self._share(role)
            self.assertTrue(user_can_download_label_files(
                self.supplier, self.label, self.theirs), role)
            self.assertEqual(visible_documents(
                self.supplier, self.label,
                self.Doc.objects.filter(label=self.label)).count(), 2, role)

    def test_주인은_언제나_전부_본다(self):
        from v1.common.media_access import user_can_download_label_files
        self.assertTrue(user_can_download_label_files(
            self.owner, self.label, self.theirs))

    def test_문서를_안_주면_전체_보기가_아닌_사람에게는_거짓이다(self):
        # "이 제품에서 무엇이든 받을 수 있는가" 를 묻는 것이라 참이면 안 된다
        from v1.common.media_access import user_can_download_label_files
        self._share('UPLOADER')
        self.assertFalse(user_can_download_label_files(self.supplier, self.label))

    def test_소유자가_켜_주면_전부_본다(self):
        from v1.common.media_access import user_can_download_label_files
        share, perm = self._share('UPLOADER')
        perm.can_view_all_documents = True
        perm.save()
        self.assertTrue(user_can_download_label_files(
            self.supplier, self.label, self.theirs))

    def test_공유가_없으면_아무것도_못_받는다(self):
        from v1.common.media_access import user_can_download_label_files
        stranger = User.objects.create_user(username='남', password='x',
                                            email='no@x.com')
        self.assertFalse(user_can_download_label_files(
            stranger, self.label, self.mine))


class SeeAllDefaultsMatchTests(TestCase):
    """역할 기본값이 서버와 화면 두 곳에 있다. 어긋나면 화면이 거짓말을 한다."""

    def test_협력업체만_꺼짐이다(self):
        from v1.products.models import SharePermission
        for role, defaults in SharePermission.ROLE_DEFAULTS.items():
            self.assertIn('can_view_all_documents', defaults, role)
            self.assertEqual(defaults['can_view_all_documents'],
                             role != 'UPLOADER', role)

    def test_화면도_같은_규칙을_쓴다(self):
        from pathlib import Path
        from django.conf import settings as dj
        html = (Path(dj.BASE_DIR) / 'templates/products/_tab_permissions.html'
                ).read_text(encoding='utf-8')
        head = html.index('function _seeAllDefault')
        self.assertIn("return role !== 'UPLOADER';", html[head:head + 200])

    def test_모든_호출처가_문서를_넘긴다(self):
        # 문서를 안 넘기면 예전과 똑같이 통째로 열린다
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        for rel in ('products/views.py', 'common/media_access.py'):
            src = (base / rel).read_text(encoding='utf-8')
            for line in src.splitlines():
                if 'user_can_download_label_files(' not in line:
                    continue
                if 'def user_can_download_label_files' in line:
                    continue
                if 'document.label)' in line or ', doc.label)' in line:
                    self.fail('%s: 문서를 안 넘긴다 — %s' % (rel, line.strip()))


class ColoursComeFromTokensTests(TestCase):
    """
    variables.css 머리에 "개별 파일에서 동일한 값을 하드코딩하지 마세요" 라고
    적혀 있는데 지켜지지 않았다. 열한 개 CSS 중 여덟이 토큰을 한 번도 쓰지
    않고 같은 회색을 저마다 적어 두고 있었다 — #5f6368 이 서른다섯 개 파일에.

    한 색을 바꾸려면 서른 곳을 고쳐야 했다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.dir = Path(dj.BASE_DIR) / 'static' / 'css'
        self.tokens = dict(__import__('re').findall(
            r'(--ez-[\w-]+):\s*(#[0-9a-fA-F]{3,6})',
            (self.dir / 'variables.css').read_text(encoding='utf-8')))

    #  :root 블록은 세지 않는다. 화면별 CSS 가 제 변수를 선언해 두고 쓰는
    #  자리인데, 그 선언을 ez 토큰으로 갈아 끼우는 것은 값이 아니라 **구조**를
    #  바꾸는 일이라 따로 봐야 한다(계획서 G-2 다음 걸음).
    _ROOT = r':root[^{]*\{[^}]*\}'
    _VAR = r'var\(\s*--[\w-]+\s*(?:,[^()]*)?\)'

    def _bare_colours(self, path):
        import re
        text = re.sub(self._ROOT, '', path.read_text(encoding='utf-8'), flags=re.S)
        return {c.lower() for c in re.findall(r'#[0-9a-fA-F]{6}', re.sub(self._VAR, '', text))}

    def test_토큰이_있는_색은_토큰으로_적는다(self):
        known = {v.lower() for v in self.tokens.values()}
        offenders = []
        for path in sorted(self.dir.glob('*.css')):
            if path.name in ('variables.css', 'bootstrap.min.css',
                             'label_creation_modern.css'):
                continue      # 4,651줄짜리는 무엇이 살아 있는지부터 재야 한다
            hits = self._bare_colours(path) & known
            if hits:
                offenders.append('%s: %s' % (path.name, ', '.join(sorted(hits))))
        self.assertEqual(offenders, [], '토큰이 있는데 직접 적었다')

    def test_대체값은_토큰_값과_같아야_한다(self):
        """
        var(--ez-gray-700, #444746) 처럼 대체값이 토큰과 다르면 파일이 거짓말을
        한다 — 토큰이 정의돼 있으니 실제로 쓰이는 것은 토큰 값이다.
        """
        import re
        wrong = []
        for path in sorted(self.dir.glob('*.css')):
            if path.name == 'label_creation_modern.css':
                # 이 파일은 ez 토큰 이름에 제 팔레트를 대체값으로 달아 뒀다.
                # 토큰이 정의돼 있으니 실제로는 ez 색이 나간다 — 뜻하지 않은
                # 일이지만 4,651줄을 훑어야 정리된다(계획서 G-4).
                continue
            text = path.read_text(encoding='utf-8')
            for name, fallback in re.findall(
                    r'var\(\s*(--ez-[\w-]+)\s*,\s*(#[0-9a-fA-F]{6})\s*\)', text):
                real = self.tokens.get(name)
                if real and real.lower() != fallback.lower():
                    wrong.append('%s: %s -> %s (토큰은 %s)'
                                 % (path.name, name, fallback, real))
        self.assertEqual(wrong, [])


class RepeatedInlineStylesAreClassesTests(TestCase):
    """
    같은 선언이 템플릿 곳곳에 흩어져 있으면 크기 하나 바꾸는 데 열 곳을
    고쳐야 하고, 어느 날 한쪽만 고쳐진다.

    폭(width)처럼 그 자리에서만 쓰는 배치값은 그대로 둔다 — 클래스로 옮겨
    봐야 이름만 늘어난다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)

    def _read(self, rel):
        return (self.base / rel).read_text(encoding='utf-8')

    def test_되풀이되던_선언이_사라졌다(self):
        gone = {
            'templates/products/product_explorer.html': [
                'style="font-size:11px;"', 'style="cursor:pointer;"',
                'style="cursor: pointer;"', 'style="padding:2px 8px;font-size:11px;"'],
            'templates/regulatory/_news_detail_panel.html': [
                'style="font-size:7px;vertical-align:middle;"'],
            'templates/regulatory/news_list.html': [
                'style="font-size:10px;color:#bbb;"'],
            'templates/products/contacts.html': [
                'style="flex-shrink:0"', 'style="flex-shrink:0;"',
                'style="color:#5f6368;text-transform:uppercase;letter-spacing:.5px"',
                'style="color:#bdc1c6;"', 'style="cursor:pointer;"'],
        }
        for rel, patterns in gone.items():
            html = self._read(rel)
            for pattern in patterns:
                self.assertNotIn(pattern, html, '%s: %s' % (rel, pattern))

    def test_대신_클래스가_있다(self):
        explorer = self._read('static/css/product_explorer.css')
        for rule in ('.pe-meta', '.pe-chip', '.pe-click'):
            self.assertIn(rule, explorer)
        reg = self._read('static/css/regulatory.css')
        for rule in ('.rg-dot', '.rg-note'):
            self.assertIn(rule, reg)
        contacts = self._read('static/css/contacts.css')
        for rule in ('.ct-eyebrow', '.ct-fix', '.ct-faint', '.ct-click'):
            self.assertIn(rule, contacts)

    def test_class_가_두_번_붙은_태그가_없다(self):
        # 두 번 붙으면 HTML 은 앞의 것만 본다 — 뒤에 넣은 것이 조용히 사라진다
        import re
        pat = re.compile(r'<[a-zA-Z][^>]*?class="[^"]*"[^>]*?\sclass="')
        for rel in ('templates/products/contacts.html',
                    'templates/products/product_explorer.html',
                    'templates/regulatory/_news_detail_panel.html'):
            self.assertEqual(pat.findall(self._read(rel)), [], rel)

    def test_7px_는_글자가_아니라_표시다(self):
        # 등급 앞의 점. 열여덟 군데에 7px 로 적혀 있었다.
        reg = self._read('static/css/regulatory.css')
        head = reg.index('.rg-dot')
        self.assertIn('font-size: 7px', reg[head:head + 120])
        # class 가 이미 있던 태그라 그 뒤에 붙었다
        self.assertIn('rg-dot"',
                      self._read('templates/regulatory/_news_detail_panel.html'))


class BootstrapGreysAreGoneTests(TestCase):
    """
    부트스트랩 회색이 구글 팔레트와 섞여 있었다. 값이 달라서 기계적으로는
    못 바꾸고, 쓰임에 따라 잣대를 나눠 정했다.

      테두리·배경   사람 눈 기준 차이(CIE ΔE*ab)가 4 아래면 바꾼다
      글자          ΔE 로 정하지 않는다. **같은 방향으로 진해져 대비가
                    오르는** 토큰을 고른다 — 바뀌는 것이 "더 잘 읽힌다"
                    쪽이면 되돌릴 이유가 없다
      넓은 면       손대지 않는다. 단추 바탕은 글자용 잣대가 안 맞는다
    """

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        self.dir = Path(dj.BASE_DIR) / 'static' / 'css'
        self._var = re.compile(r'var\(\s*--[\w-]+\s*(?:,[^()]*)?\)')

    def _bare(self, path):
        return self._var.sub('', path.read_text(encoding='utf-8')).lower()

    def test_테두리와_글자의_부트스트랩_회색은_사라졌다(self):
        import re
        root = re.compile(r':root[^{]*\{[^}]*\}', re.S)
        left = {}
        for path in sorted(self.dir.glob('*.css')):
            if path.name == 'bootstrap.min.css':
                continue
            text = root.sub('', self._bare(path))
            for colour in ('#dee2e6', '#495057', '#e0e2e0', '#f0f0f0'):
                if colour in text:
                    left.setdefault(colour, []).append(path.name)
        self.assertEqual(left, {})

    def test_부트스트랩_회색이_하나도_안_남았다(self):
        """
        넓은 면을 칠하는 두 곳은 잣대가 달라 미뤄 뒀다가, 하나씩 보고 정했다.

          단추 바탕      흰 글자를 얹는다 -> --ez-gray-700 (대비 4.69 -> 6.05)
                         바로 아래 테두리와 같은 색이 된다
          스크롤 손잡이   글자가 안 얹힌다 -> 옆 회색과 같은 계열로
        """
        left = []
        for path in sorted(self.dir.glob('*.css')):
            if path.name == 'bootstrap.min.css':
                continue
            if '#6c757d' in self._bare(path):
                left.append(path.name)
        self.assertEqual(left, [])

    def test_글자는_대비가_오르는_쪽으로_갔다(self):
        """#6c757d 는 흰 바탕 대비 4.69 로 본문 기준(4.5)에 아슬아슬했다."""
        import re
        tokens = dict(re.findall(r'(--ez-[\w-]+):\s*(#[0-9a-fA-F]{6})',
                      (self.dir / 'variables.css').read_text(encoding='utf-8')))

        def lum(h):
            def lin(c):
                c = int(h.lstrip('#')[c:c + 2], 16) / 255
                return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
            return .2126 * lin(0) + .7152 * lin(2) + .0722 * lin(4)

        def contrast(fg):
            a, b = sorted((lum(fg), lum('#ffffff')), reverse=True)
            return (a + .05) / (b + .05)

        for old, token in (('#6c757d', '--ez-gray-700'), ('#495057', '--ez-gray-800')):
            self.assertGreater(contrast(tokens[token]), contrast(old), old)


class SheetPasteIsOneRuleTests(TestCase):
    """
    배합비도 연락처도 엑셀로 관리하다 여기로 온다. 두 화면 모두 표로 만들어
    뒀는데 붙여넣기가 **자리로만** 들어갔다.

      1. 머리글까지 긁어 오면 "원료명" 이라는 원료가 한 줄 생긴다
      2. 연락처 표는 첫 칸이 체크박스라 왼쪽 끝에 붙이면 전부 한 칸씩 밀린다
      3. 안 쓰는 열이 딸려 오면 마지막 칸을 덮는다
      4. 몇 줄이 들어갔는지 아무 말이 없다
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)
        self.js = (self.base / 'static/js/sheet_paste.js').read_text(encoding='utf-8')

    def _read(self, rel):
        return (self.base / rel).read_text(encoding='utf-8')

    def test_규칙은_한_곳에_있다(self):
        # 두 벌로 두면 어느 날 한쪽만 고쳐진다
        self.assertIn('window.attachSheetPaste', self.js)
        for rel in ('templates/products/bom_detail.html',
                    'templates/products/contacts.html'):
            html = self._read(rel)
            self.assertIn("js/sheet_paste.js", html, rel)
            self.assertIn('window.attachSheetPaste(hot', html, rel)

    def test_머리글로_열을_맞춘다(self):
        """
        쓰던 양식은 열 순서가 다르고 우리에게 없는 열도 있다. 자리로만 넣으면
        배합비 자리에 식품유형이 들어간다. 머리글 줄은 어차피 버리려고 이미
        읽고 있었으니, 버리는 대신 쓴다.
        """
        self.assertIn('function planColumns', self.js)
        # 두 칸 이상 짝이 지어져야 머리글이다 — 한 칸만 보면 "원료명" 이라는
        # 이름의 원료를 머리글로 오해한다
        self.assertIn('names.length < 2', self.js)

    def test_AI_를_쓰지_않는다(self):
        """
        이름을 견주는 사전 대조다. 결과가 늘 같고 호출 비용이 없다.

        열을 짝짓는 자리에는 **바깥을 부르는 것이 하나도 없어야** 한다.
        (칸 순서를 계정에 남기는 fetch 는 짝짓기와 무관한 다른 일이다.)
        """
        for word in ('openai', 'gpt', 'anthropic', '/ai'):
            self.assertNotIn(word, self.js.lower())
        head = self.js.index('function matchColumn')
        block = self.js[head:self.js.index('window.attachSheetPaste', head)]
        for word in ('fetch', 'XMLHttpRequest', 'await'):
            self.assertNotIn(word, block)
        self.assertIn('aliases', self.js)

    def test_긴_이름이_이긴다(self):
        """
        "원재료명 및 함량 / 성분" 에는 "원재료명"(원료명)도
        "원재료명및함량"(원재료 표시명)도 들어 있다. 긴 쪽이 더 구체적이다.
        """
        head = self.js.index('function matchColumn')
        block = self.js[head:head + 800]
        self.assertIn('score > best.score', block)
        self.assertIn('1000 + a.length', block)   # 글자까지 같으면 그것으로

    def test_체크박스_칸으로_밀리지_않는다(self):
        self.assertIn('firstCol', self.js)
        contacts = self._read('templates/products/contacts.html')
        head = contacts.index('window.attachSheetPaste(hot')
        self.assertIn('firstCol: 1', contacts[head:head + 400])

    def test_무엇을_어떻게_맞췄는지_말해_준다(self):
        self.assertIn('window.sheetPasteMessage', self.js)
        head = self.js.index('window.sheetPasteMessage')
        block = self.js[head:head + 700]
        self.assertIn('줄을 넣었습니다', block)
        self.assertIn('열을 머리글로 맞췄습니다', block)
        self.assertIn('쓰지 않았습니다', block)      # 버린 열
        for rel in ('templates/products/bom_detail.html',
                    'templates/products/contacts.html'):
            self.assertIn('window.sheetPasteMessage(info', self._read(rel), rel)

    def test_실제_쓰는_양식이_제자리를_찾는다(self):
        """
        쓰시는 열 순서 —
          순서 · 원재료/원료명 · 배합비율/원료함량 · 식품유형 · 업체명 ·
          원재료명 및 함량 / 성분 · 비고
        """
        bom = self._read('templates/products/bom_detail.html')
        head = bom.index('const BOM_SHEET_ALIASES')
        block = bom[head:bom.index('};', head)]
        for name in ('원재료/원료명', '배합비율/원료함량', '업체명',
                     '원재료명 및 함량 / 성분'):
            self.assertIn(name, block, name)
        # "순서" 는 어느 칸에도 없다 — 버려야 한다
        self.assertNotIn("'순서'", block)

    def test_머리글은_한_곳에서만_정한다(self):
        """화면 머리글이자 엑셀 양식의 머리글이고, 머리글 줄을 알아보는 잣대다."""
        from v1.common import sheet_template
        bom = self._read('templates/products/bom_detail.html')
        self.assertIn('const BOM_SHEET_HEADERS', bom)
        # 감춘 칸을 뺀 목록을 쓰지만, 그 목록은 BOM_SHEET_HEADERS 에서 나온다.
        # 머리글을 정하는 곳은 여전히 하나다.
        self.assertIn('colHeaders: SHOWN_HEADERS', bom)
        self.assertIn('SHOWN_HEADERS = BOM_SHEET_HEADERS.filter(', bom)
        for name in sheet_template.BOM_HEADERS:
            self.assertIn("'%s'" % name, bom)

        contacts = self._read('templates/products/contacts.html')
        self.assertIn('const CONTACT_SHEET_HEADERS', contacts)
        for name in sheet_template.CONTACT_HEADERS:
            self.assertIn("'%s'" % name, contacts)


class SheetTemplateDownloadTests(TestCase):
    """
    붙여넣기는 열 순서를 맞춰 와야 하는데, 사용자 엑셀의 열 순서를 우리가 알
    방법이 없다. 그래서 양식을 우리가 준다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='sheet', password='x')
        self.client.force_login(self.user)

    def _open(self, url):
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])
        import io
        from openpyxl import load_workbook
        return load_workbook(io.BytesIO(res.content)).active

    def test_배합비_양식(self):
        from v1.common.sheet_template import BOM_HEADERS
        sheet = self._open(reverse('bom:bom_sheet_template'))
        head = [c.value for c in sheet[2]]
        self.assertEqual(head, BOM_HEADERS)

    def test_연락처_양식(self):
        from v1.common.sheet_template import CONTACT_HEADERS
        sheet = self._open(reverse('products:contact_sheet_template'))
        head = [c.value for c in sheet[2]]
        self.assertEqual(head, CONTACT_HEADERS)

    def test_안내와_보기_줄이_있다(self):
        # 파일만 보고도 쓰는 법을 알아야 한다
        from v1.common.sheet_template import BOM_SAMPLE
        sheet = self._open(reverse('bom:bom_sheet_template'))
        self.assertIn('붙여넣', sheet['A1'].value)
        self.assertEqual(sheet['A3'].value, BOM_SAMPLE[0])
        # 알레르기를 열로 나눠 O 로 체크한 표도 받는다는 것을 파일이 말해 준다
        self.assertIn('O 로 체크', sheet['A1'].value)

    def test_자료는_세_번째_줄부터다(self):
        sheet = self._open(reverse('products:contact_sheet_template'))
        self.assertEqual(sheet.freeze_panes, 'A3')


class GridFollowsThePastedOrderTests(TestCase):
    """
    쓰던 엑셀의 열 순서는 그 사람이 일하는 순서다. 값만 제자리에 들어가고
    화면은 우리 순서로 남아 있으면, 붙여넣은 것을 눈으로 견주기가 어렵다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)
        self.js = (self.base / 'static/js/sheet_paste.js').read_text(encoding='utf-8')

    def _read(self, rel):
        return (self.base / rel).read_text(encoding='utf-8')

    def test_붙여넣은_순서대로_늘어놓는다(self):
        self.assertIn('window.sheetPasteReorder', self.js)
        for rel in ('templates/products/bom_detail.html',
                    'templates/products/contacts.html'):
            html = self._read(rel)
            self.assertIn('window.sheetPasteReorder(hot', html, rel)
            self.assertIn('manualColumnMove: true', html, rel)

    def test_엑셀에_없던_칸은_뒤로_보낸다(self):
        # 지우지 않는다 — 그 칸을 안 쓰는 것과 그 엑셀에 없던 것은 다른 일이다
        head = self.js.index('window.sheetPasteReorder')
        block = self.js[head:head + 1200]
        self.assertIn('if (wanted.indexOf(c) < 0) wanted.push(c);', block)

    def test_이미_그_순서면_건드리지_않는다(self):
        head = self.js.index('window.sheetPasteReorder')
        self.assertIn("now.join() === wanted.join()", self.js[head:head + 1400])

    def test_값은_화면에_보이는_자리로_들어간다(self):
        """칸을 옮겨 둔 뒤에는 논리 자리와 화면 자리가 다르다."""
        head = self.js.index('var seat = {}')
        block = self.js[head:head + 500]
        self.assertIn('hot.toVisualColumn(logical)', block)

    def test_손으로_옮긴_것도_남긴다(self):
        for rel in ('templates/products/bom_detail.html',
                    'templates/products/contacts.html'):
            self.assertIn("afterColumnMove", self._read(rel), rel)


class GridOrderIsRememberedTests(TestCase):
    """
    회사 엑셀의 열 순서는 그 사람이 일하는 방식이라 자리를 옮긴다고 달라지지
    않는다. 브라우저가 아니라 계정에 남긴다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='grid', password='x')
        self.client.force_login(self.user)

    def _save(self, screen, order):
        return self.client.post(
            reverse('v1.common:grid_order_save'),
            data=json.dumps({'screen': screen, 'order': order}),
            content_type='application/json')

    def test_계정에_남는다(self):
        res = self._save('bom_grid', ['원료명', '배합비(%)', '식품유형'])
        self.assertEqual(res.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.list_prefs['bom_grid']['order'],
                         ['원료명', '배합비(%)', '식품유형'])

    def test_화면마다_따로_남는다(self):
        self._save('bom_grid', ['원료명'])
        self._save('contact_grid', ['이메일'])
        self.user.profile.refresh_from_db()
        prefs = self.user.profile.list_prefs
        self.assertEqual(prefs['bom_grid']['order'], ['원료명'])
        self.assertEqual(prefs['contact_grid']['order'], ['이메일'])

    def test_빈_요청은_거절한다(self):
        self.assertEqual(self._save('bom_grid', []).status_code, 400)
        self.assertEqual(self._save('', ['원료명']).status_code, 400)

    def test_터무니없이_긴_것은_받지_않는다(self):
        # 화면이 보내는 것은 칸 이름 몇 개뿐이다
        self.assertEqual(self._save('bom_grid', ['x'] * 100).status_code, 400)
        self.assertEqual(self._save('bom_grid', ['x' * 200]).status_code, 400)

    def test_다음에_열_때_그대로_연다(self):
        from v1.common.views import grid_order
        self._save('bom_grid', ['비고', '원료명'])
        self.user.profile.refresh_from_db()
        self.assertEqual(grid_order(self.user, 'bom_grid'), ['비고', '원료명'])

    def test_남긴_적이_없으면_기본_순서다(self):
        from v1.common.views import grid_order
        self.assertEqual(grid_order(self.user, 'bom_grid'), [])


class AllergenMarksAreGatheredTests(TestCase):
    """
    엑셀로 배합비를 관리하는 사람들은 알레르기를 이렇게 적는다.

        계란  우유  밀  대두
         O    X    X   O

    열 이름 자체가 값이다. 그대로 붙여넣으면 "계란" 이라는 칸이 우리 표에
    없으니 통째로 버려진다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)
        self.js = (self.base / 'static/js/sheet_paste.js').read_text(encoding='utf-8')
        self.bom = (self.base / 'templates/products/bom_detail.html'
                    ).read_text(encoding='utf-8')

    def test_체크_열을_모아_한_칸으로(self):
        self.assertIn('checks[j] = { col: marks.into', self.js)
        self.assertIn('BOM_SHEET_MARKS', self.bom)
        self.assertIn("into: '알레르기 성분'", self.bom)

    def test_애매한_것은_없다로_본다(self):
        """없는 알레르기를 적으면 라벨이 틀린다. 빠뜨린 것은 요약이 잡아 준다."""
        head = self.js.index('var MARK_ON')
        block = self.js[head:head + 400]
        for on in ("'o'", "'○'", "'v'", "'예'", "'1'"):
            self.assertIn(on, block)
        for off in ("'x'", "'무'", "'0'", "'no'"):
            self.assertNotIn(off, block)

    def test_이름_목록은_판정과_같은_자리에서_온다(self):
        """
        판정용 키워드 전체를 쓰면 "간장"·"두부" 같은 원료 이름까지 알레르기
        열로 오해한다. 열 머리에 실제로 적는 말만 추린 목록이 따로 있다.
        """
        from v1.label.services.allergen_names import CANONICAL_NAMES, HEADER_NAMES
        self.assertEqual(set(HEADER_NAMES), set(CANONICAL_NAMES))
        self.assertIn('계란', HEADER_NAMES['알류'])
        # 원료 이름은 없어야 한다
        flat = [name for names in HEADER_NAMES.values() for name in names]
        for wrong in ('간장', '두부', '레시틴', '젤라틴', '분유'):
            self.assertNotIn(wrong, flat)
        self.assertIn('allergen_header_names', self._views())

    def _views(self):
        return (self.base / '..' / 'v1' / 'bom' / 'views.py').read_text(encoding='utf-8')

    def test_사람이_적은_것을_덮지_않는다(self):
        # 알레르기 칸을 따로 채워 왔으면 그쪽이 더 확실하다
        head = self.js.index('if (checkSeat >= 0')
        self.assertIn('!row[checkSeat]', self.js[head:head + 200])

    def test_같은_물질은_한_번만(self):
        head = self.js.index('found.indexOf(plan.checks[j].value)')
        self.assertIn('< 0', self.js[head:head + 80])


class BomGridHasTheRestTests(TestCase):
    """
    알레르기·GMO·품목보고번호는 오른쪽 상세 패널에서만 넣을 수 있었다.
    원료를 하나씩 골라 들어가야 해서, 엑셀로 관리하던 사람은 옮길 방법이
    없었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.bom = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                    ).read_text(encoding='utf-8')

    def test_표에_칸이_있다(self):
        for name in ('알레르기 성분', 'GMO', '품목보고번호'):
            self.assertIn("'%s'" % name, self.bom)
        for field in ("data: 'allergens'", "data: 'gmo'", "data: 'report_no'"):
            self.assertIn(field, self.bom)

    def test_머리글_이름과_칸_수가_맞는다(self):
        """
        너비는 자리가 아니라 **이름**에 붙어 있다. 붙여넣기가 칸을 엑셀 순서로
        옮겨 놓으면 자리로 정한 너비는 엉뚱한 칸에 남는다 — 배합비가 넓어지고
        원재료 표시명이 좁아졌다.
        """
        import re
        head = self.bom.index('const BOM_SHEET_HEADERS')
        names = re.findall(r"'([^']+)'", self.bom[head:self.bom.index('];', head)])
        self.assertEqual(len(names), 9)

        head = self.bom.index('const BOM_COL_WIDTH')
        block = self.bom[head:self.bom.index('};', head)]
        for name in names:
            self.assertIn("'%s':" % name, block, name)
        # 성격이 다른 칸은 폭도 달라야 한다
        self.assertIn('max: 108', block)      # 배합비는 숫자 네 자리면 끝이다
        self.assertIn('min: 220', block)      # 원재료 표시명은 문장이 온다

    def test_너비는_공용_규칙으로_간다(self):
        """배합비·원료 붙여넣기·연락처·영양성분이 같은 규칙으로 움직여야 한다."""
        self.assertIn('sheet_widths.js', self.bom)
        self.assertIn('window.attachSheetWidths(hot', self.bom)
        # 자리 비율로 정하던 것은 걷었다
        self.assertNotIn('function getBomColWidths', self.bom)
        self.assertNotIn('const ratios', self.bom)

    def test_늘려도_다른_칸이_줄지_않는다(self):
        """stretchH: 'all' 이면 한 칸을 넓힐 때 고르지도 않은 칸이 따라 준다."""
        self.assertIn("stretchH: 'none'", self.bom)
        self.assertNotIn("stretchH: 'all'", self.bom)

    def test_붙여넣기도_그_칸을_안다(self):
        head = self.bom.index('const BOM_SHEET_ALIASES')
        block = self.bom[head:self.bom.index('};', head)]
        for name in ('알레르기', 'gmo', '품목보고번호'):
            self.assertIn(name, block.lower())


class BomLayoutFollowsTheWorkTests(TestCase):
    """
    세 가지가 어긋나 있었다.

      1. 요약이 표 아래라 스크롤해야 보였다. 요약은 이 화면의 결과물이라
         표를 고치는 내내 봐야 한다.
      2. 오른쪽 탭 둘의 성격이 다르다. 보관함은 가져오는 곳이라 늘 열려
         있어야 하는데, 상세와 탭을 나눠 써서 상세를 보면 보관함이 사라졌다.
      3. 표에 칸을 아홉 개 넣고 나니 오른쪽 상세와 겹친다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_요약이_표_위에_있다(self):
        self.assertLess(self.html.index('id="bom-summary-panel"'),
                        self.html.index('id="bom-grid"'))

    def test_접혀도_알레르기가_보인다(self):
        # 이 화면에서 가장 자주 확인하는 값이다
        self.assertIn('id="bom-summary-peek"', self.html)
        head = self.html.index("getElementById('bom-summary-peek')")
        self.assertIn('알레르기', self.html[head:head + 600])

    def test_오른쪽은_보관함만이다(self):
        self.assertNotIn('data-bs-target="#side-detail"', self.html)
        self.assertIn('side-panel-head', self.html)
        self.assertIn('원료 보관함', self.html)

    def test_상세는_고른_줄_아래에_있다(self):
        self.assertIn('id="bom-rowdetail"', self.html)
        self.assertIn('id="context-panel"', self.html)
        self.assertLess(self.html.index('id="bom-rowdetail"'),
                        self.html.index('bom-right-panel'))
        self.assertIn('.bom-rowdetail.is-open', self.css)

    def test_고른_줄_바로_아래에_뜬다(self):
        """
        표 밑에 따로 두었더니 줄을 고르면 화면 맨 아래로 내려가서, 어느 줄의
        상세인지 눈으로 이어 보기가 어려웠다.
        """
        self.assertIn('function openRowDetail', self.html)
        head = self.html.index('function openRowDetail')
        block = self.html[head:head + 900]
        self.assertIn('hot.getCell(rowIndex, 0)', block)
        self.assertIn("panel.style.top", block)
        self.assertIn('.bom-grid-card { position: relative; }', self.css)
        self.assertIn('position: absolute', self.css)

    def test_고르는_칸에서만_편다(self):
        # 모든 칸에서 펴면 셀 하나 누를 때마다 아래 줄들이 가려진다
        self.assertIn("PICKER_PROPS = new Set(['allergens', 'gmo'])", self.html)
        self.assertIn('PICKER_PROPS.has(this.colToProp(col))', self.html)

    def test_어느_줄의_것인지_적혀_있다(self):
        # 표 위에 떠 있으니 이름이 없으면 헷갈린다
        self.assertIn('id="bom-rowdetail-name"', self.html)
        self.assertIn('closeRowDetail()', self.html)

    def test_밖을_누르거나_Esc_로_닫는다(self):
        self.assertIn("if (e.key === 'Escape') closeRowDetail();", self.html)
        self.assertIn('card.contains(e.target)', self.html)

    def test_품목보고번호를_두_곳에서_고치지_않는다(self):
        # 표에 칸이 있다. 두 곳에서 고치면 어느 쪽이 맞는지 알 수 없다
        self.assertIn('<input type="hidden" id="field-report-no">', self.html)

    def test_요약은_표의_칸을_먼저_본다(self):
        """알레르기·GMO 에 칸이 생겼으니 표가 먼저다."""
        head = self.html.index('allergens: (row.allergens')
        block = self.html[head:head + 200]
        self.assertIn('meta.allergens', block)      # 옛 자료는 뒤에서 받쳐 준다
        self.assertIn('row.gmo || meta.gmo', block)


class 고르는_자리를_낮춘다(TestCase):
    """
    알레르기·GMO 가 각각 라벨 한 줄, 테두리 상자, 그 안의 "선택된 항목 없음"
    한 줄을 따로 차지했다. 같은 모양이 셋 쌓이니 창이 길어져서, 고른 줄
    아래에 띄우면 표를 통째로 가렸다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def _form(self):
        head = self.html.index('id="context-form"')
        return self.html[head:self.html.index('id="field-summary-type"', head)]

    def test_상자_안에_상자를_두지_않는다(self):
        # 창 자체가 이미 상자다
        self.assertNotIn('background-color: #f8f9fa;', self._form())
        self.assertNotIn('border: 1px solid #dadce0;', self._form())

    def test_항목명과_칩과_전체선택이_한_줄이다(self):
        """
        항목명이 제 줄을 차지하면 세 덩이가 여섯 줄이 되고, 줄 아래에 뜨는
        창이 그만큼 표를 가린다.
        """
        form = self._form()
        for chips, toggle in (('allergen-quick-buttons', 'allergenToggleBtn'),
                              ('gmoBtnList', 'gmoToggleBtn')):
            head = form.index('class="pick-group pick-row"')
            block = form[head:form.index('id="' + toggle + '"', head) + 40]
            self.assertIn('pick-label', block)
            self.assertIn(chips, block)
            # 전체선택은 공용 단추다
            self.assertIn('v2-btn-sm', block)
            form = form[head + 20:]
        self.assertIn('.pick-row {', self.css)
        self.assertIn('.pick-row .pick-chips { flex: 1 1 auto; min-width: 0; }',
                      self.css)
        # 전체선택은 공용 단추다. 크기를 여기서 다시 적지 않는다
        self.assertNotIn('.pick-all {', self.css)

    def test_고른_것이_없으면_적지_않는다(self):
        # 칩이 그대로 보여 준다. 자리만 차지하는 말이었다
        self.assertNotIn('선택된 항목 없음', self.html)

    def test_칩_간격은_한_곳에서_준다(self):
        # 낱개 margin 을 걷고 .pick-chips 의 gap 하나로 모은다
        head = self.css.index('.quick-allergen-btn {')
        self.assertNotIn('margin-bottom', self.css[head:head + 260])
        self.assertIn('gap:       3px;', self.css)


class 표의_칸이_반쪽이었다(TestCase):
    """
    알레르기·GMO·품목보고번호에 표의 칸을 만들어 놓고, 불러오는 쪽도
    저장하는 쪽도 고치지 않았다. 칸은 늘 비어 있었고, 칸에 친 값은
    저장되지 않고 사라졌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_불러올_때_칸을_채운다(self):
        head = self.html.index('const data = (result.data || []).map')
        block = self.html[head:head + 900]
        for line in ("allergens: item.allergens || item.allergen || ''",
                     "gmo: item.gmo || ''",
                     "report_no: item.report_no || ''"):
            self.assertIn(line, block)

    def test_저장할_때_칸을_먼저_본다(self):
        """
        `row.allergens || metadata.allergens` 였다. 칸을 **비우면** '' 가
        falsy 라 옛 값으로 떨어져, 잘못 들어간 알레르기를 지워도 새로고침하면
        되살아났다. 빈 값과 값 없음을 구분해야 한다(pick).
        """
        head = self.html.index('const rowAllergens =')
        block = self.html[head:head + 1400]
        self.assertIn('pick(row.allergens', block)
        self.assertIn('allergens: rowAllergens,', block)
        self.assertIn('gmo: rowGmo,', block)
        self.assertIn('pick(row.report_no', block)
        self.assertNotIn('row.allergens || metadata', block)

    def test_칩을_누르면_칸에_들어간다(self):
        # gridColumnProps 에 없으면 rowMetadata 로만 가고 표는 비어 있다
        head = self.html.index('const gridColumnProps = new Set([')
        block = self.html[head:head + 400]
        for prop in ("'allergens'", "'gmo'", "'report_no'"):
            self.assertIn(prop, block)

    def test_표시명_기준은_칸이_없다(self):
        """
        Handsontable 은 columns 에 없는 prop 의 자리를 찾지 못한다.
        summary_type 은 rowMetadata 에만 둔다.
        """
        head = self.html.index('const gridColumnProps = new Set([')
        self.assertNotIn("'summary_type'", self.html[head:head + 400])


class 비고에_적어_온_성분(TestCase):
    """
    엑셀에서 알레르기·GMO 를 따로 두지 않고 비고에 "밀,우유,대두" 처럼 몰아
    적어 오는 곳이 많다. 그대로 두면 요약에도 표시사항에도 들어가지 않는다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.html = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                     ).read_text(encoding='utf-8')

    def test_비고를_고치면_떼어_낸다(self):
        self.assertIn("if (prop === 'notes' && source !== 'remark-split')", self.html)
        self.assertIn('spillRemark(row, value);', self.html)

    def test_알아본_것이_없으면_건드리지_않는다(self):
        # "대두유 사용" 같은 말까지 옮기면 비고가 사라진다
        head = self.html.index('function splitRemark(text)')
        block = self.html[head:self.html.index('function spillRemark')]
        self.assertIn('if (!allergens.length && !gmo.length) return null;', block)
        self.assertIn('rest.push(t);', block)

    def test_이름표로_대두를_가른다(self):
        # 대두는 알레르기이면서 GMO 다. "GMO:" 가 앞에 붙으면 GMO 로 본다
        head = self.html.index('function splitRemark(text)')
        block = self.html[head:self.html.index('function spillRemark')]
        self.assertIn("if (/알레르기|알러지/.test(head)) {", block)
        self.assertIn("} else if (/gmo|유전자/i.test(head)) {", block)
        self.assertIn("if (bucket === 'gmo' && g) {", block)

    def test_모르는_이름표는_건드리지_않는다(self):
        """
        "ERP 원재료: SPC삼립전용분" 처럼 우리 표에 자리가 없어 비고로 옮겨
        둔 값이다. 성분으로 보면 알레르기 칸으로 새고 비고에서는 사라진다.
        """
        head = self.html.index('function splitRemark(text)')
        block = self.html[head:self.html.index('function spillRemark')]
        self.assertIn('const label = t.match(/^([^:：]{1,24})[:：]', block)
        self.assertIn('rest.push(t);', block)

    def test_GMO_이름을_화면으로_넘긴다(self):
        self.assertIn('{{ gmo_list|json_script:"gmo-name-data" }}', self.html)
        self.assertIn('window.GMO_NAMES', self.html)

    def test_이미_있는_것은_그대로_둔다(self):
        head = self.html.index('function spillRemark')
        block = self.html[head:head + 1200]
        self.assertIn('if (had.indexOf(n) < 0) had.push(n);', block)


class 표시명_기준을_위에서_고른다(TestCase):
    """
    원료마다 따로 두는 값이지만 한 배합비 안에서는 대개 하나로 간다.
    줄을 고를 때마다 상세를 열어 다시 누르게 하지 않는다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_표보다_위에_있다(self):
        self.assertLess(self.html.index('id="sheet-summary-type"'),
                        self.html.index('id="bom-grid"'))
        # 세그먼트 토글은 공용으로 올렸다 (products_common.css)
        from pathlib import Path
        from django.conf import settings as dj
        common = (Path(dj.BASE_DIR) / 'static/css/products_common.css'
                  ).read_text(encoding='utf-8')
        self.assertIn('.v2-seg-btn.is-on', common)

    def test_한_번_누르면_모든_줄에_들어간다(self):
        head = self.html.index('function bindSheetSummaryType')
        block = self.html[head:head + 1200]
        self.assertIn('const rows = hot.countRows();', block)
        self.assertIn("setRowProp(r, 'summary_type', value, 'syncPanel');", block)

    def test_그_줄만_다르게_할_수_있다(self):
        # 상세의 토글은 남는다. 위에서 고른 것과 다르게 갈 때 쓴다
        self.assertIn('>이 원료만</span>', self.html)
        self.assertIn("setRowProp(currentRowIndex, 'summary_type', value, 'syncPanel');",
                      self.html)


class 상세가_행_번호에_가렸다(TestCase):
    """
    Handsontable 은 행 번호 열을 본체 위에 겹쳐 그린다(z-index 100~180).
    상세를 30 으로 두었더니 그 겹침판이 왼쪽 52px 을 덮어서, 원료 이름도
    첫 칩도 잘려 보였다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.css = (Path(dj.BASE_DIR) / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_겹침판보다_위에_그린다(self):
        head = self.css.index('.bom-rowdetail {')
        block = self.css[head:head + 800]
        self.assertIn('z-index: 200;', block)
        self.assertNotIn('z-index: 30;', block)


class 화면_최대화(TestCase):
    """
    왼쪽 메뉴(250px)와 위쪽 띠(64px)가 늘 펼쳐져 있었다. 표가 넓은 화면에서는
    그 314px 이 아깝다. base_v2 를 쓰는 모든 화면이 함께 얻는다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.base = (base / 'templates/base_v2.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_모든_v2_화면이_함께_얻는다(self):
        # 화면마다 따로 달면 어느 날 한쪽만 남는다
        self.assertIn('id="v2MaxToggle"', self.base)

    def test_첫_그림부터_접힌_채로_연다(self):
        """
        #v2Wrapper 는 <head> 시점에 아직 없다. 거기 걸면 펼친 화면이 한 번
        그려졌다가 접힌다.
        """
        head = self.base.index("localStorage.getItem('v2Maximized')")
        self.assertLess(head, self.base.index('<body>'))
        self.assertIn("document.documentElement.classList.add('v2-max')", self.base)
        self.assertIn('html.v2-max .v2-sidebar', self.css)
        self.assertIn('html.v2-max .v2-topbar { display: none; }', self.css)

    def test_되돌릴_자리를_남긴다(self):
        # 최대화하면 위쪽 띠와 함께 그 단추도 사라진다
        self.assertIn('id="v2MaxExit"', self.base)
        self.assertIn('html.v2-max .v2-max-exit { display: flex; }', self.css)
        self.assertIn('.v2-max-exit {', self.css)
        self.assertIn("if (e.key !== 'Escape') return;", self.base)

    def test_창이_떠_있으면_Esc_가_창을_먼저_닫는다(self):
        head = self.base.index("if (e.key !== 'Escape') return;")
        self.assertIn("document.querySelector('.modal.show')",
                      self.base[head:head + 400])

    def test_다음_화면도_접힌_채로_열린다(self):
        # 화면마다 다시 누르게 하면 최대화가 아니라 그냥 접기다
        self.assertIn("localStorage.setItem(KEY, on ? '1' : '0')", self.base)

    def test_표가_칸_너비를_다시_잡는다(self):
        head = self.base.index('function apply(on)')
        self.assertIn("window.dispatchEvent(new Event('resize'))",
                      self.base[head:head + 500])


class 원료_보관함을_접는다(TestCase):
    """
    가져오는 곳이라 탭 뒤에 숨기지는 않지만, 원료를 다 넣고 표를 고치는
    동안에는 280px 이 자리만 차지한다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_머리에_접는_단추가_있다(self):
        head = self.html.index('class="side-panel-head"')
        block = self.html[head:head + 500]
        self.assertIn('id="paletteToggle"', block)
        self.assertIn('side-panel-title', block)

    def test_접히면_세로_글씨만_남는다(self):
        # 무엇이 접혀 있는지 모르면 다시 펴지 못한다
        self.assertIn('.bom-right-panel.is-closed .side-tab-body { display: none; }', self.css)
        self.assertIn('writing-mode: vertical-rl;', self.css)

    def test_다음에_열_때도_접힌_채로(self):
        head = self.html.index('function bindPaletteToggle')
        block = self.html[head:head + 1200]
        self.assertIn("const KEY = 'bomPaletteClosed';", block)
        self.assertIn("localStorage.setItem(KEY, next ? '1' : '0')", block)

    def test_표가_칸_너비를_다시_잡는다(self):
        head = self.html.index('function bindPaletteToggle')
        self.assertIn("window.dispatchEvent(new Event('resize'))",
                      self.html[head:head + 1200])

    def test_세로로_쌓이는_폭에서는_접지_않는다(self):
        # 되찾을 자리가 없다
        head = self.css.index('@media (max-width: 991px)')
        block = self.css[head:head + 900]
        self.assertIn('.side-panel-toggle { display: none; }', block)


class 머리글이_두_줄인_양식(TestCase):
    """
    회사 양식은 위 칸을 병합해 큰 이름을 쓰고 아래 줄에 낱개 이름을 적는 일이
    흔하다.

        ├──────────── 알레르기 ────────────┤
        │ 알류 │ 우유 │ 메밀 │ 대두 │ 밀 │ … │

    병합한 칸은 붙여넣으면 첫 칸에만 글자가 있고 나머지는 빈칸이다. 위 줄만
    보면 O/X 열 열아홉 개가 통째로 버려지고 "알류 우유 메밀 …" 이라는 원료가
    한 줄 생긴다. 실제 양식에서 그렇게 났다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.js = (Path(dj.BASE_DIR) / 'static/js/sheet_paste.js').read_text(
            encoding='utf-8')

    def test_두_줄을_합쳐_읽는다(self):
        self.assertIn('function mergeHeader(top, sub)', self.js)
        self.assertIn('function readHeader(data, headers, aliases, marks)', self.js)
        head = self.js.index('var head = readHeader(')
        block = self.js[head:head + 400]
        self.assertIn('for (var h = 0; h < head.rows; h++) data.shift();', block,
                      '두 줄을 읽었으면 두 줄을 버려야 한다')

    def test_아래_줄이_더_구체적이다(self):
        # "알레르기"(병합) 보다 "알류"(낱개)가 맞는 이름이다
        head = self.js.index('function mergeHeader')
        block = self.js[head:head + 500]
        self.assertIn("out[i] = below || (top && top[i] != null ? top[i] : '');",
                      block)

    def test_자료_줄을_머리글로_보지_않는다(self):
        """
        "밀가루" 는 알레르기 "밀" 을 품는다. 자료 줄을 합치면 없는 체크 열이
        생긴다. 가르는 자리는 위 줄의 빈칸이다.
        """
        head = self.js.index('function looksLikeSubHeader')
        block = self.js[head:head + 700]
        self.assertIn('underGap >= filled * 0.6', block)
        self.assertIn('filled >= 2 && underGap >= 2', block)

    def test_짝이_더_많이_지어질_때만_합친다(self):
        head = self.js.index('function readHeader')
        block = self.js[head:head + 500]
        self.assertIn('planSize(two) > planSize(one)', block)

    def test_합쳤다고_말해_준다(self):
        # 무엇을 어떻게 맞췄는지 말하지 않으면 틀렸을 때 알 수 없다
        self.assertIn("matched = matched.concat(['머리글 두 줄을 합쳐 읽었습니다'])",
                      self.js)


class 배합비는_소수점_세_자리다(TestCase):
    """
    44.528 처럼 적어 온다. 두 자리로 자르면 44.53 이 되고, 열 줄이면 합계가
    100 에서 눈에 띄게 어긋난다. DB(usage_ratio)는 원래 네 자리였다 —
    자르고 있던 것은 화면뿐이었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.html = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                     ).read_text(encoding='utf-8')

    def test_표의_칸이_세_자리를_보여_준다(self):
        self.assertIn("numericFormat: { pattern: '0.000' }", self.html)
        self.assertNotIn("numericFormat: { pattern: '0.00' }", self.html)

    def test_합계도_세_자리다(self):
        self.assertIn('${total.toFixed(3)}%', self.html)
        self.assertNotIn('${total.toFixed(2)}%', self.html)

    def test_처음_그릴_때도_같은_자리다(self):
        # 0.00% 로 그려 두면 값이 들어오는 순간 자릿수가 바뀐다
        self.assertNotIn('>0.00%<', self.html)
        self.assertIn('>0.000%<', self.html)

    def test_DB_는_이미_네_자리였다(self):
        from v1.bom.models import ProductBOM
        self.assertEqual(
            ProductBOM._meta.get_field('usage_ratio').decimal_places, 4)


class 요약이_화면_밖으로_사라졌다(TestCase):
    """
    요약은 이 화면의 결과물인데, 표를 내리면 위로 사라졌다. 만드는 동안
    보이지 않으면 무엇을 만들고 있는지 알 수 없다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_요약만_붙여_둔다(self):
        self.assertIn('class="bom-summary is-stuck"', self.html)
        head = self.css.index('.bom-summary.is-stuck')
        block = self.css[head:head + 260]
        self.assertIn('position: sticky;', block)

    def test_표의_머리글보다_위에_그린다(self):
        import re
        # Handsontable 이 제 머리글을 z-index 101 로 띄운다
        head = self.css.index('.bom-summary.is-stuck')
        block = self.css[head:head + 260]
        z = int(re.search(r'z-index:\s*(\d+)', block).group(1))
        self.assertGreater(z, 101)


class 왜_안_바뀌는지_말해_준다(TestCase):
    """
    표시명 기준을 눌러도 요약이 그대로일 때가 있다 — 식품유형 칸이 비어
    있으면 두 기준의 결과가 같기 때문이다. 화면이 아무 말도 하지 않으면
    단추가 고장 난 것으로 보인다. 실제로 그렇게 신고가 왔다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_같아지는_줄을_세어_알린다(self):
        self.assertIn('id="bom-summary-note"', self.html)
        head = self.html.index("getElementById('bom-summary-note')")
        block = self.html[head:head + 700]
        self.assertIn('r.byFoodType && !r.foodType', block)
        self.assertIn('원재료명으로 표시됩니다', block)

    def test_할_말이_없으면_자리를_차지하지_않는다(self):
        self.assertIn('.bom-summary-note:empty { display: none; }', self.css)


class 무엇을_하는_화면인가(TestCase):
    """
    안내가 두 곳에 흩어져 있었고 둘 다 "셀 더블클릭" 같은 조작법이었다.
    처음 여는 사람이 알아야 하는 것은 조작법이 아니라 순서다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')

    def test_네_걸음이_순서대로_있다(self):
        head = self.html.index('class="bom-steps"')
        block = self.html[head:self.html.index('</ol>', head)]
        for step in ('원료를 넣습니다', '표를 채웁니다',
                     '요약을 확인합니다', '기본정보로 보냅니다'):
            self.assertIn(step, block)

    def test_걸음마다_어떻게_하는지_적는다(self):
        head = self.html.index('class="bom-steps"')
        block = self.html[head:self.html.index('</ol>', head)]
        # 이름만 있으면 순서는 알아도 방법을 모른다
        self.assertGreaterEqual(block.count('<span>'), 4)
        self.assertIn('Ctrl+V', block)
        self.assertIn('기본정보로 복사', block)

    def test_안내가_한_곳에_모였다(self):
        # 두 곳에 흩어져 있으면 어느 날 한쪽만 고쳐진다
        self.assertEqual(
            self.html.count('셀 더블 클릭해 수정할 수 있고'), 0)
        self.assertIn('.bom-steps', self.css)

    def test_고르는_자리마다_무엇인지_적는다(self):
        for tip in ('이 원료에 든 알레르기 물질을 누릅니다',
                    '유전자변형 농산물을 원료로 쓴 경우에 누릅니다',
                    '위쪽 표시명 기준과 다르게 가고 싶을 때만 씁니다'):
            self.assertIn(tip, self.html)


class 새_단추를_만들지_않는다(TestCase):
    """
    공용 3단계가 있는데도 새 단추를 만들었다 — BOM 의 "전체선택"(.pick-all)과
    화면 되돌리기(.v2-max-exit). W001 은 인라인 크기와 btn-sm 만 보므로 그냥
    통과했다. **검사를 통과한 것과 결이 맞는 것은 다른 일이다.**
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.bom = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.base_v2 = (base / 'templates/base_v2.html').read_text(encoding='utf-8')
        self.bom_css = (base / 'static/css/bom.css').read_text(encoding='utf-8')
        self.common = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_전체선택은_공용_단추다(self):
        self.assertNotIn('class="pick-all"', self.bom)
        self.assertEqual(self.bom.count('v2-btn-sm"' + chr(10)
                                        + ' ' * 48 + 'id="allergenToggleBtn"'), 1)
        self.assertIn('id="gmoToggleBtn"', self.bom)
        self.assertNotIn('.pick-all {', self.bom_css)

    def test_되돌리기는_사이드바_단추와_같은_모양이다(self):
        # 크기와 색을 다시 적으면 둘이 갈라진다
        self.assertIn('class="v2-sidebar-toggle v2-max-exit"', self.base_v2)
        head = self.common.index('.v2-max-exit {')
        block = self.common[head:head + 400]
        self.assertNotIn('cursor:', block, '모양은 물려받는다')
        self.assertIn('position:      fixed;', block, '자리만 정한다')

    def test_세그먼트_토글은_공용이다(self):
        """
        BOM 에만 두면 같은 모양이 필요한 다음 화면이 또 제 이름으로 만든다.
        """
        self.assertIn('.v2-seg-btn {', self.common)
        self.assertIn('.v2-seg-btn.is-on', self.common)
        self.assertNotIn('.sheet-pick-btn', self.bom_css)
        self.assertIn('class="v2-seg"', self.bom)
        self.assertIn("querySelectorAll('#sheet-summary-type .v2-seg-btn')", self.bom)


class 단추_명부(TestCase):
    """
    새로 만든 단추를 사람이 아니라 검사가 잡게 한다. 여기 적는 일이 번거로운
    것이 명부의 목적이다 — 새 단추를 만들 때 "공용으로 되나?" 를 한 번 묻게
    한다.
    """

    def test_지금은_한_건도_안_걸린다(self):
        # 켤 때 기존 것을 전부 쏟으면 아무도 안 본다
        from v1.common.checks import check_button_component_registry
        found = check_button_component_registry(None)
        self.assertEqual([w.msg for w in found], [])

    def test_명부에_없는_단추를_잡는다(self):
        from unittest.mock import patch
        from v1.common import checks

        fake = [('products/시험.html', 'C:/x/시험.html',
                 '<button class="my-shiny-new-btn">시험</button>')]
        with patch.object(checks, '_v2_templates', return_value=fake):
            found = checks.check_button_component_registry(None)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, 'products.W002')
        self.assertIn('my-shiny-new-btn', found[0].msg)
        self.assertIn('_OWN_SIZED_BUTTONS', found[0].hint)

    def test_공용_단추는_그냥_지나간다(self):
        from unittest.mock import patch
        from v1.common import checks

        ok = ('<button class="btn btn-primary v2-btn-sm">저장</button>'
              '<button class="v2-seg-btn is-on">식품유형</button>'
              '<button class="v2-sidebar-toggle v2-max-exit"></button>')
        with patch.object(checks, '_v2_templates',
                          return_value=[('a.html', 'C:/a.html', ok)]):
            self.assertEqual(checks.check_button_component_registry(None), [])

    def test_클래스_안의_장고_태그에_속지_않는다(self):
        # class="pv-chip {% if x %}pv-chip--on{% endif %}" 같은 것이 실제로 있다
        # (예전 예시는 rs-vtab 이었는데, 그 이름은 공용 pv-tab 으로 옮겨 가며 사라졌다)
        from unittest.mock import patch
        from v1.common import checks

        html = '<button class="pv-chip {% if x %}pv-chip--on{% endif %}">가</button>'
        with patch.object(checks, '_v2_templates',
                          return_value=[('a.html', 'C:/a.html', html)]):
            self.assertEqual(checks.check_button_component_registry(None), [])

    def test_이름이_없으면_보지_않는다(self):
        # 무엇을 등록하라고 할지가 없다
        from unittest.mock import patch
        from v1.common import checks

        with patch.object(checks, '_v2_templates',
                          return_value=[('a.html', 'C:/a.html',
                                         '<button onclick="x()">가</button>')]):
            self.assertEqual(checks.check_button_component_registry(None), [])

    def test_두_검사가_한_명부를_본다(self):
        # 두 벌로 두면 어느 날 한쪽만 고쳐진다
        from v1.common import checks
        for name in ('quick-allergen-btn', 'gmo-btn', 'summary-type-btn'):
            self.assertIn(name, checks._OWN_SIZED_BUTTONS)
            self.assertIn(name, checks._SIZED_BY_CLASS)


class 함유는_한_번만_쓴다(TestCase):
    """
    물질마다 "밀 함유" "우유 함유" 로 따로 적고 있었다. 표시사항에 들어가는
    문구는 그렇게 쓰지 않는다 — 물질을 모두 늘어놓고 함유는 맨 뒤에 한 번이다.

        밀 함유  우유 함유  대두 함유
        →  알류(달걀), 우유, 대두, 밀 함유

    그래야 여기 보이는 것과 라벨에 인쇄될 것이 같아진다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/bom.css').read_text(encoding='utf-8')
        self.tokens = (base / 'static/css/variables.css').read_text(encoding='utf-8')

    def test_물질을_모두_늘어놓고_끝에_한_번(self):
        head = self.html.index('const allergenText = Array.from(allergenSet)')
        block = self.html[head:head + 500]
        self.assertIn("Array.from(allergenSet).join(', ')", block)
        self.assertIn('${allergenText} 함유', block)

    def test_물질마다_따로_적지_않는다(self):
        # 옛 모습: .map(a => `… ${a} 함유`)
        self.assertNotIn('${a} \uD568\uC720', self.html)
        self.assertNotIn('${a} 함유', self.html)

    def test_복사에도_같은_문구가_간다(self):
        # 두 벌로 두면 화면과 복사본이 갈라진다
        self.assertIn('window._bomSummaryAllergenText', self.html)
        head = self.html.index('window._bomSummaryAllergenText')
        self.assertIn("allergenText + ' 함유'", self.html[head:head + 200])

    def test_알레르기와_GMO_가_자리를_덜_쓴다(self):
        """
        둘을 한 줄에 붙여 둔 적이 있다. 요약이 표 **위**에 붙어 있어 그 높이가
        곧 표가 밀리는 만큼이라, 짧은 값 둘이 줄을 하나씩 차지하는 것이
        아까웠기 때문이다.

        이제 **탭**이 그 일을 더 잘한다 — 값이 없으면 아예 서지 않는다.
        한 줄에 붙이는 것은 '없음' 두 개를 나란히 보여 주는 일이었다.
        """
        self.assertIn('id="bsum-pane-allergens"', self.html)
        self.assertIn('id="bsum-pane-gmo"', self.html)
        self.assertIn('.bsum-tab', self.css)
        # 옛 한 줄 배치는 남아 있지 않다
        self.assertNotIn('bom-summary-pair', self.html)
        self.assertNotIn('.bom-summary-pair', self.css)

    def test_한_덩이로_보여_준다(self):
        # 조각조각 뱃지로 흩으면 인쇄될 문구가 안 보인다
        self.assertIn('.bom-tag--allergen', self.css)
        self.assertNotIn('badge bg-warning text-dark me-1 mb-1', self.html)

    def test_옅은_바탕_위의_글자색이_토큰이다(self):
        """
        파랑에는 --ez-info-on-bg 가 있는데 노랑·초록에는 없어서 fallback 으로만
        살아 있었다 — 토큰을 고쳐도 안 따라온다.
        """
        self.assertIn('--ez-warning-on-bg:', self.tokens)
        self.assertIn('--ez-success-on-bg:', self.tokens)

    def test_대비를_재_보고_골랐다(self):
        """#e67700 도 #b06000 도 옅은 노랑 위에서 4.5:1 에 모자랐다."""
        import re

        def lum(hexcolor):
            parts = [int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            parts = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
                     for x in parts]
            return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

        def ratio(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + 0.05) / (lo + 0.05)

        def token(name):
            return re.search(r'--%s:\s*(#[0-9a-f]{6})' % name, self.tokens).group(1)

        self.assertGreaterEqual(
            ratio(token('ez-warning-on-bg'), token('ez-warning-bg')), 4.5)
        self.assertGreaterEqual(
            ratio(token('ez-success-on-bg'), token('ez-success-bg')), 4.5)

    def test_공통_영역이_좁아졌다(self):
        # 요약은 표 위에 붙어 있다. 여기서 쓰는 높이가 곧 표가 잃는 높이다
        self.assertIn('.bom-summary-body { padding: 0 10px 6px; }', self.css)
        head = self.css.index('.bom-summary-head {')
        self.assertIn('padding: 5px 10px;', self.css[head:head + 200])


class 붙여넣는_도중에_칸을_옮겼다(TestCase):
    """
    배합비 열의 값이 알레르기 칸으로 들어가고, 짝 못 지은 열은 사라졌다.

    beforePaste 안에서 곧바로 알리면, 그 말을 들은 화면이 칸을 옮긴다. 그런데
    Handsontable 은 그 함수가 **끝난 뒤에** 값을 써 넣는다. 값은 옮기기 전
    자리를 기준으로 만들어 놓고, 쓰기는 옮긴 뒤 자리에 들어간다 — 옮긴 만큼
    통째로 어긋난다.

    지난번 붙여넣기와 열 이름이 같을 때는 옮길 것이 없어(moveColumns 가 돌지
    않아) 멀쩡했다. 그래서 한동안 안 드러났다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/sheet_paste.js').read_text(encoding='utf-8')
        self.bom = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')

    def test_값이_다_들어간_뒤에_알린다(self):
        self.assertIn("hot.addHook('afterPaste', function () {", self.js)
        head = self.js.index("hot.addHook('afterPaste'")
        block = self.js[head:head + 300]
        self.assertIn('report(info);', block)

    def test_beforePaste_안에서는_알리지_않는다(self):
        # 여기서 알리면 화면이 칸을 옮기고, 값은 그 뒤에 들어간다
        head = self.js.index("hot.addHook('beforePaste'")
        block = self.js[head:self.js.index('function aim(wantCol)', head)]
        self.assertIn('pending = { added: data.length', block)
        self.assertEqual(block.count('report({ added: data.length'), 0)

    def test_넣을_것이_없으면_바로_알린다(self):
        # 표를 건드리지 않으면 afterPaste 가 오지 않는다
        head = self.js.index('if (!data.length) {')
        block = self.js[head:head + 400]
        self.assertIn('report({ added: 0', block)
        self.assertIn('return false;', block)


class 자리가_없는_열을_버리지_않는다(TestCase):
    """
    ERP 원재료·원료코드·품목제조보고서 기타설명처럼 우리 표에 자리가 없는
    열이 그 회사에서는 원료를 찾는 열쇠다. 지우면 어디서 온 원료인지 알 수
    없어진다.

        비고  ERP 원재료: SPC삼립전용분(20kg) · 원료코드: 250521
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/sheet_paste.js').read_text(encoding='utf-8')
        self.bom = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')
        self.ing = (base / 'templates/label/my_ingredient_list_combined.html'
                    ).read_text(encoding='utf-8')

    def test_어느_열이었는지_기억한다(self):
        # 이름만 알면 값을 못 찾는다. 자리도 같이 남긴다
        self.assertIn('unusedCols.push({ j: j, label:', self.js)
        self.assertIn('unusedCols: unusedCols', self.js)

    def test_이름을_달아_모은다(self):
        head = self.js.index('if (carrySeat >= 0) {')
        block = self.js[head:head + 700]
        self.assertIn("u.label + ': '", block)
        self.assertIn("extra.join(' · ')", block)

    def test_원래_비고를_덮지_않는다(self):
        head = self.js.index('if (carrySeat >= 0) {')
        block = self.js[head:head + 700]
        self.assertIn('[row[carrySeat], extra.join', block)
        self.assertIn('.filter(Boolean).join', block)

    def test_두_화면_모두_옮길_곳을_정해_뒀다(self):
        self.assertIn("carry: '비고',", self.bom)
        self.assertIn("carry: '하위 원료',", self.ing)

    def test_버린_것이_아니라_옮겼다고_말한다(self):
        head = self.js.index('if (carrySeat >= 0 && carryCols.length) {')
        block = self.js[head:head + 400]
        self.assertIn("+ ' 은 ' + options.carry + ' 로'", block)
        self.assertIn('unused = [];', block)

    def test_자리를_잃은_열도_옮긴다(self):
        """
        짝을 못 지은 열만 옮기고 있었다. 그런데 실제 양식에서 사라진 열들은
        **짝을 짓고도 진** 열이다.

            품목제조보고서 원재료명       -> 원료명   (이겼다)
            품목제조보고서 원재료 기타설명 -> 원료명   (졌다 — "원재료" 를 품어서)
            ERP 원재료                   -> 원료명   (졌다)
            원료코드                     -> 원료명   (졌다)

        진 쪽은 이름만 "쓰지 않았습니다" 로 적히고 값은 사라졌다. 하필 그
        회사에서 원료를 찾는 열쇠들 — carry 를 만든 바로 그 열들이다.
        """
        head = self.js.index('function planColumns')
        block = self.js[head:self.js.index('function mergeHeader', head)]
        # 이름과 자리를 한 곳에서 남긴다. 세 갈래가 따로 적으면 또 어긋난다
        self.assertIn('function lose(j, label)', block)
        self.assertEqual(block.count('unusedCols.push('), 1)
        self.assertEqual(block.count('unused.push('), 1)
        self.assertIn('lose(taken[col].j, taken[col].label);', block)


class 붙여넣은_것이_줄_수와_자리를_정한다(TestCase):
    """
    열여덟 줄을 붙였는데 스물한 줄이 들어갔다. 열여덟 줄 뒤로는 **앞 줄들이
    되풀이돼서** 붙었다.

    Handsontable 은 잡아 둔 자리의 왼쪽 위부터 넣고, 넣을 것이 그 자리보다
    작으면 모자란 만큼 앞에서부터 되풀이해 채운다(populateValues 의
    `o.length % n`). 그리고 붙여넣고 나면 들어간 자리를 통째로 잡아 준다.

    우리는 머리글 줄과 빈 줄과 합계 줄을 덜어 낸다. 그래서 **두 번째
    붙여넣기부터는 잡힌 자리가 넣을 것보다 늘 크다.**

    beforePaste 가 받는 coords 로는 못 고친다. 그것은 복사용 자리
    (CopyPaste.copyableRanges)이고, 붙는 자리는 그때 잡혀 있는 선택 영역에서
    온다 — 고쳐 봐야 아무 일도 일어나지 않는다. 잡아 둔 자리를 한 칸으로
    좁힌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.js = (Path(dj.BASE_DIR) / 'static/js/sheet_paste.js').read_text(
            encoding='utf-8')

    def test_잡아_둔_자리를_한_칸으로_좁힌다(self):
        head = self.js.index('function aim(wantCol)')
        block = self.js[head:head + 800]
        self.assertIn('hot.getSelectedRangeLast()', block)
        self.assertIn('hot.selectCell(row, col, row, col)', block)

    def test_coords_를_고치지_않는다(self):
        # 복사용 자리다. 고쳐도 붙는 자리는 꿈쩍하지 않는다
        self.assertNotIn('range.startCol = firstCol;', self.js)
        self.assertNotIn('range.endCol +=', self.js)

    def test_머리글로_맞춘_줄은_커서가_어디_있든_첫_칸부터(self):
        head = self.js.index('var startCol = aim(')
        self.assertIn('aim(plan ? firstCol : -1)', self.js[head:head + 120])

    def test_자료가_시작하는_칸보다_왼쪽에는_붙지_않는다(self):
        # 연락처 표는 첫 칸이 체크박스다
        head = self.js.index('function aim(wantCol)')
        self.assertIn('Math.max(at ? at.col : firstCol, firstCol)',
                      self.js[head:head + 800])

    def test_넣을_것이_없으면_자리를_건드리지_않는다(self):
        # 표를 안 건드리는데 커서만 옮길 이유가 없다
        self.assertLess(self.js.index('return false;'),
                        self.js.index('var startCol = aim('))


class 합계_줄은_원료가_아니다(TestCase):
    """
    회사 배합비 엑셀은 맨 아래에 마무리 줄을 둔다.

             정제수         0.000    5.342
                  합  계  100.000  100.000

    그대로 넣으면 원료가 한 줄 늘고 **배합비 합계가 200% 가 된다.** 열여덟
    줄을 붙였는데 열아홉 줄이 들어갔다.

    "합계" 는 우리 표에 자리가 없는 열에 적혀 있는 일이 흔하다(위 예에서는
    ERP 원재료 칸이다). 한 칸만 보지 않고 줄 전체를 본다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.js = (Path(dj.BASE_DIR) / 'static/js/sheet_paste.js').read_text(
            encoding='utf-8')

    def test_합계_소계_총계를_안다(self):
        head = self.js.index('var TOTAL_WORDS')
        block = self.js[head:head + 200]
        for word in ('합계', '소계', '총계', 'total'):
            self.assertIn(word, block, word)

    def test_이름이_있는_줄은_건드리지_않는다(self):
        """이름이 있는데 버리면 원료 한 줄이 소리 없이 사라진다."""
        head = self.js.index('function isTotalRow')
        block = self.js[head:head + 500]
        self.assertIn("if (name != null && String(name).trim() !== '') return false;",
                      block)

    def test_이름_칸을_모르면_버리지_않는다(self):
        head = self.js.index('var totals = 0;')
        block = self.js[head:head + 400]
        self.assertIn('nameCols.length ? data.length - 1 : -1', block)

    def test_가져온_칸_그대로일_때_본다(self):
        # 우리 양식으로 옮기고 나면 "합  계" 가 비고 뒤에 붙어 안 보인다
        self.assertLess(self.js.index('var totals = 0;'),
                        self.js.index('var seat = {};'))

    def test_몇_줄을_뺐는지_말해_준다(self):
        self.assertIn("why.push('합계 줄 ' + totals + '개')", self.js)
        self.assertIn('dropped: blanks + totals', self.js)


class BOM을_통째로_지운다(TestCase):
    """
    잘못 붙여넣었을 때 되돌릴 길이 우클릭 → 행 삭제뿐이었다. 스무 줄이면
    스무 번이다. 사람들은 표 왼쪽 위 모서리를 눌러 전체를 고르고 DEL 을
    누른다 — 엑셀에서 그렇게 하기 때문이다.

    **칸만 비우면 반이 남는다.** 알레르기·GMO·어디서 온 원료인지는 표에 칸이
    없어 rowMetadata 에만 있다. 칸을 지워도 그것들은 그대로 남아 다음 저장에
    다시 실려 간다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.bom = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                    ).read_text(encoding='utf-8')

    def test_단추가_있다(self):
        self.assertIn('onclick="clearAllRows()"', self.bom)
        self.assertIn('전체 지우기', self.bom)
        # 읽기 전용으로 열린 사람에게는 보이지 않는다
        head = self.bom.index('onclick="clearAllRows()"')
        self.assertIn('{% if can_edit %}', self.bom[head - 400:head])

    def test_전체를_고르고_DEL_로도_지운다(self):
        head = self.bom.index("hot.addHook('beforeKeyDown'")
        block = self.bom[head:head + 900]
        self.assertIn("event.key !== 'Delete' && event.key !== 'Backspace'", block)
        # 전체를 골랐을 때만이다. 칸 하나를 지우는 것은 그대로 둔다
        self.assertIn('to.row < hot.countRows() - 1', block)
        self.assertIn('clearAllRows({ ask: false })', block)

    def test_붙여넣기가_없어도_지울_수_있다(self):
        """sheet_paste.js 를 못 실어도 지우기는 살아 있어야 한다."""
        self.assertLess(self.bom.index('if (window.attachSheetPaste)'),
                        self.bom.index("hot.addHook('beforeKeyDown'"))
        # 여덟 칸 들여쓰기 = 붙여넣기 if 문 밖이다
        self.assertIn("\n        hot.addHook('beforeKeyDown'", self.bom)

    def test_숨은_것도_함께_지운다(self):
        """
        예전에는 rowMetadata(Map<행번호, …>)를 따로 비웠다. 그 Map 을
        걷어냈으므로(행 번호는 영구 키가 아니다) 메타데이터는 행 객체의
        _meta 에 붙어 loadData 로 함께 사라진다. 따로 비울 것이 없다.
        """
        head = self.bom.index('function clearAllRows(options)')
        block = self.bom[head:head + 1600]
        self.assertIn('currentRowIndex = null;', block)
        self.assertIn('hot.loadData(', block)
        self.assertNotIn('rowMetadata', block)

    def test_합계와_요약을_다시_그린다(self):
        """loadData 로 넣은 값은 afterChange 가 무시한다(source === 'loadData')."""
        head = self.bom.index('function clearAllRows(options)')
        block = self.bom[head:head + 1600]
        self.assertIn('calculateTotal();', block)

    def test_묻고_지운다(self):
        head = self.bom.index('function clearAllRows(options)')
        block = self.bom[head:head + 1600]
        self.assertIn('confirm(', block)
        # DEL 은 묻지 않는다 — 엑셀에서 그렇게 하기 때문이다
        self.assertIn('options.ask !== false', block)

    def test_저장_전에는_서버_자료가_그대로다(self):
        """지우는 것은 화면뿐이다. 그 말을 해 주지 않으면 겁이 난다."""
        head = self.bom.index('function clearAllRows(options)')
        self.assertIn('저장하기를 누르기 전에는', self.bom[head:head + 1600])


class 걷어도_되는_것과_아닌_것(TestCase):
    """
    옛 화면으로 가는 길이 위(홈 전환)와 아래(기존 사이트 이동) 두 곳에 있었다.
    아래 하나로 모았다. 공지사항은 메뉴의 게시판과 겹쳐서 걷었다.

    **개인정보처리방침·이용약관은 남긴다.** 가입 화면에도 링크가 있지만 그건
    가입할 때 한 번 보는 자리이고, 로그인한 뒤에 다시 찾아볼 길은 여기뿐이다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.base_v2 = (base / 'templates/base_v2.html').read_text(encoding='utf-8')
        self.topbar = (base / 'templates/includes/_topbar_account.html'
                       ).read_text(encoding='utf-8')

    def test_홈_전환은_걷었다(self):
        self.assertNotIn('home-switch-btn', self.topbar)

    def test_옛_화면으로_가는_길은_한_곳이다(self):
        self.assertEqual(self.base_v2.count("url 'main:home_v1'"), 1)

    def test_공지사항은_메뉴의_게시판과_겹쳤다(self):
        head = self.base_v2.index('v2-sidebar-footer')
        block = self.base_v2[head:self.base_v2.index('</nav>', head)]
        self.assertNotIn('공지사항', block)

    def test_약관은_상시로_볼_수_있어야_한다(self):
        head = self.base_v2.index('v2-sidebar-footer')
        block = self.base_v2[head:self.base_v2.index('</nav>', head)]
        self.assertIn('개인정보처리방침', block)
        self.assertIn('이용약관', block)


class 몇_줄이_필요한지_묻지_않는다(TestCase):
    """
    연락처 표에는 "행 추가" 단추가 있었고, 누르면 **몇 줄을 만들지 물었다.**

        prompt('추가할 행 수를 입력하세요', '1')

    엑셀에서는 그냥 다음 줄에 치면 늘어난다. 몇 줄이 필요한지 미리 아는
    사람은 없다. minSpareRows 가 같은 일을 한다 — 마지막 줄을 채우면 아래에
    빈 줄이 다시 생긴다. 필터 중에는 단추를 잠가야 했던 예외도 사라진다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.contacts = (base / 'templates/products/contacts.html').read_text(encoding='utf-8')
        self.bom = (base / 'templates/products/bom_detail.html').read_text(encoding='utf-8')

    def test_행_추가_단추가_없다(self):
        self.assertNotIn('addRowBtn', self.contacts)
        self.assertNotIn('추가할 행 수를 입력하세요', self.contacts)

    def test_줄이_저절로_늘어난다(self):
        self.assertIn('minSpareRows: 3,', self.contacts)

    def test_배합비도_같다(self):
        # 두 표가 다르게 굴면 쓰는 사람이 매번 다시 배운다
        self.assertIn('minSpareRows: 3,', self.bom)

    def test_사이에_끼워_넣는_길은_남긴다(self):
        # 맨 아래에 붙이는 것과 사이에 끼우는 것은 다른 일이다
        self.assertIn("row_above:  { name: '위에 행 추가' }", self.contacts)


class 연락처에도_비고를_둔다(TestCase):
    """
    엑셀에는 전화번호·주소·부서처럼 우리 표에 자리가 없는 열이 늘 따라온다.
    자리가 없다고 지우면 그 연락처가 누구인지 알 길이 없어진다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.contacts = (base / 'templates/products/contacts.html').read_text(encoding='utf-8')

    def test_표에_칸이_있다(self):
        self.assertIn("'인허가번호', '비고']", self.contacts)
        self.assertIn("{ data: 'memo', type: 'text', className: 'htMiddle' },", self.contacts)

    def test_자리_없는_열이_비고로_간다(self):
        self.assertIn("carry: '비고',", self.contacts)

    def test_고치면_서버에_저장된다(self):
        # infoProps 에 없으면 화면에만 남고 새로고침하면 사라진다
        self.assertIn("new Set(['email', 'name', 'company', 'license_no', 'memo'])",
                      self.contacts)

    def test_모델에도_자리가_있다(self):
        from v1.products.models import UserContact
        self.assertTrue(UserContact._meta.get_field('memo').null)

    def test_엑셀_양식에도_있다(self):
        from v1.common.sheet_template import CONTACT_HEADERS, CONTACT_SAMPLE
        self.assertEqual(CONTACT_HEADERS[-1], '비고')
        self.assertEqual(len(CONTACT_SAMPLE), len(CONTACT_HEADERS))

    def test_저장하고_다시_읽는다(self):
        from django.contrib.auth.models import User
        from v1.products.models import UserContact

        user = User.objects.create_user(username='ct1', password='x')
        self.client.force_login(user)
        res = self.client.post('/products/contacts/api/add/', {
            'email': 'a@b.com', 'name': '홍길동',
            'memo': '품질팀 · 02-000-0000',
        })
        self.assertTrue(res.json()['success'])
        self.assertEqual(
            UserContact.objects.get(owner=user, email='a@b.com').memo,
            '품질팀 · 02-000-0000')


class 통째로_읽으면_무엇을_잃는가(TestCase):
    """
    detail:high 는 사진을 2048 상자에 맞춘 뒤 **짧은 변을 768px 로** 맞춘다.
    짧은 변이 3000px 인 사진을 통째로 보내면 라벨 글자가 1/4 로 줄고, 12pt
    한 줄이 5px 가 된다. 읽을 수 없는 자리를 모델은 **지어낸다.**

    그런데 "전체 사용" 을 누르면 아무 말 없이 그대로 갔다. 그 선택이 무엇을
    잃는지 화면 어디에도 없었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.js = (Path(dj.BASE_DIR) / 'static/js/products/photo_cropper.js'
                   ).read_text(encoding='utf-8')

    def test_모델이_보는_크기를_잣대로_쓴다(self):
        self.assertIn('var MODEL_SHORT_SIDE = 768;', self.js)
        self.assertIn('function shrinkOf(w, h)', self.js)

    def test_얼마나_줄어드는지_숫자로_말한다(self):
        # "면마다 고르세요" 라고만 하면 왜인지 모른다
        self.assertIn("'글자가 약 1/' + (1 / r).toFixed(1)", self.js)

    def test_전체_사용을_한_번_말린다(self):
        head = self.js.index("if (btn.dataset.crop === 'whole')")
        block = self.js[head:head + 1400]
        self.assertIn('btn.dataset.warned', block)
        self.assertIn('그래도 전체로 읽기', block)
        self.assertIn('지어낼 수 있습니다', block)

    def test_막지는_않는다(self):
        # 한 면짜리 사진도 있다. 한 번 말하고, 다시 누르면 보낸다
        head = self.js.index("if (btn.dataset.crop === 'whole')")
        block = self.js[head:head + 1400]
        self.assertIn('&& !btn.dataset.warned', block)

    def test_작은_사진은_말리지_않는다(self):
        # 이미 768px 안팎이면 잘라 봐야 나아지지 않는다
        head = self.js.index("if (btn.dataset.crop === 'whole')")
        block = self.js[head:head + 1400]
        self.assertIn('big < SHRINK_WARN', block)

    def test_고른_영역도_재_준다(self):
        self.assertIn('worst = Math.min(worst, shrinkOf(', self.js)
        self.assertIn('더 좁게 잘라 주세요', self.js)

    def test_왜_나눠_고르는지_창에_적혀_있다(self):
        self.assertIn('crop-why', self.js)
        self.assertIn('<b>면마다 하나씩</b>', self.js)


class 홈은_순서를_먼저_말한다(TestCase):
    """
    홈에 기능이 아홉 장 카드로 늘어서 있었고, 로그인하면 여섯 개짜리 단추
    줄이 있었다. 무엇이 되는지는 알겠는데 **어디서 시작해 어디서 끝나는지**가
    안 보였다. 단추 줄은 왼쪽 메뉴를 한 번 더 적은 것이었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.home = (base / 'templates/main/home_v2_dashboard.html').read_text(encoding='utf-8')
        self.steps = (base / 'templates/includes/_workflow_steps.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/home_v2_dashboard.css').read_text(encoding='utf-8')

    def test_다섯_걸음이_순서대로_있다(self):
        for step in ('원료·제품 입력', '배합비 구성', '원재료명 자동 표시',
                     '규정 검증', '시안 검증'):
            self.assertIn(step, self.steps)

    def test_손님과_회원이_같은_흐름을_본다(self):
        """가입 전에 본 순서와 가입 뒤에 쓰는 순서가 다르면 안 된다."""
        self.assertEqual(
            self.home.count('{% include "includes/_workflow_steps.html" %}'), 2)

    def test_손님은_가입으로_보낸다(self):
        self.assertIn("{% if is_guest %}{% url 'user_management:signup' %}", self.steps)

    def test_흐름이_기능_목록보다_먼저_온다(self):
        self.assertLess(self.home.index('wf-band--guest'),
                        self.home.index('features-section'))

    def test_메뉴를_한_번_더_적지_않는다(self):
        # 왼쪽 메뉴에 다 있는 이름이 순서 없이 늘어서 있었다
        head = self.home.index('class="dash-hero-right"')
        block = self.home[head:self.home.index('</div>' + chr(10) + '    </div>', head)]
        self.assertNotIn('제품 목록', block)
        self.assertNotIn('표시사항 생성', block)
        self.assertNotIn('원료 관리', block)
        # 시작하는 단추는 남는다
        self.assertIn('신규 제품 등록', block)

    def test_걸음마다_무엇을_하는지_적는다(self):
        # 이름만 있으면 순서는 알아도 방법을 모른다
        self.assertGreaterEqual(self.steps.count('<em>'), 5)
        self.assertIn('엑셀', self.steps)

    def test_좁아지면_세로로_선다(self):
        head = self.css.index('.wf-steps {')
        block = self.css[head:]
        self.assertIn('@media (max-width: 1100px)', block)
        self.assertIn('.wf-arrow { display: none; }', block)


class 게시판도_같은_목록_껍데기를_쓴다(TestCase):
    """
    게시판만 글자 13px 에 머리글이 대문자였고 줄 높이도 달라서, 같은 성격의
    목록이 화면마다 다르게 보였다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.html = (base / 'templates/board/list.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/board.css').read_text(encoding='utf-8')

    def test_공용_껍데기를_싣는다(self):
        self.assertIn("css/list_common.css", self.html)
        self.assertIn('class="board-table ez-list-table"', self.html)
        self.assertIn('board-table-wrapper ez-list-wrap', self.html)

    def test_표_규칙을_두_벌로_두지_않는다(self):
        # 글자 크기·머리글 밑줄·줄 높이는 공용이 한 번만 정한다
        self.assertNotIn('.board-table thead th {', self.css)
        self.assertNotIn('text-transform:  uppercase;', self.css)

    def test_게시판에만_있는_것은_남긴다(self):
        self.assertIn('.board-table .row-notice', self.css)

    def test_도구_단추도_공용이다(self):
        self.assertNotIn('class="toolbar-btn', self.html)
        self.assertNotIn('.toolbar-btn {', self.css)
        self.assertIn('v2-btn-icon', self.html)

    def test_명부에서도_지웠다(self):
        from v1.common import checks
        self.assertNotIn('toolbar-btn', checks._OWN_SIZED_BUTTONS)


class 안내_문구가_말이_되어야_한다(TestCase):
    """"그 면에 주의가 전부 갑니다" 는 우리끼리 쓰던 말이다."""

    def test_영역_안내를_사람_말로_적는다(self):
        from pathlib import Path
        from django.conf import settings as dj
        js = (Path(dj.BASE_DIR) / 'static/js/products/photo_cropper.js'
              ).read_text(encoding='utf-8')
        self.assertNotIn('주의가 전부 갑니다', js)
        self.assertIn('표시된 항목의 인식률이 높아집니다', js)


class 칸_너비는_한_규칙으로(TestCase):
    """
    표 쓰는 화면 넷이 저마다 너비를 정했고 셋이 `stretchH: 'all'` 이었다.

      1. 끌어서 넓히면 **고르지도 않은 칸이 따라 줄었다.** stretch 가 칸 전체를
         컨테이너 폭에 맞춰 다시 나눠 주기 때문이다.
      2. 여러 칸을 골라 함께 조절해도 그 자리에서 되돌아갔다.
      3. 자리로 정한 너비는 붙여넣기가 칸을 옮기면 엉뚱한 칸에 남았다.
      4. 너비가 바뀌었는데 줄 높이를 다시 재지 않아 행 번호와 내용이 어긋났다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/sheet_widths.js').read_text(encoding='utf-8')
        self.screens = {
            '배합비': base / 'templates/products/bom_detail.html',
            '연락처': base / 'templates/products/contacts.html',
            '원료 붙여넣기': base / 'templates/label/my_ingredient_list_combined.html',
            '영양성분': base / 'templates/products/nutrition_editor.html',
        }

    def test_네_화면이_같은_파일을_쓴다(self):
        for name, path in self.screens.items():
            text = path.read_text(encoding='utf-8')
            self.assertIn('sheet_widths.js', text, name)
            self.assertIn('attachSheetWidths', text, name)

    def test_어디에도_stretch_가_남지_않았다(self):
        for name, path in self.screens.items():
            self.assertNotIn("stretchH: 'all'", path.read_text(encoding='utf-8'), name)

    def test_너비는_이름에_붙는다(self):
        """칸을 옮겨도 그 칸의 너비여야 한다."""
        head = self.js.index('function nameAt')
        self.assertIn('hot.toPhysicalColumn', self.js[head:head + 300])
        # 훅 안에서 다시 그리면 Handsontable 이 이동 뒤에 하려던 render 를
        # 못 한다 — 끌어다 놓은 칸이 제자리로 돌아간 것처럼 보인다
        self.assertIn("hot.addHook('afterColumnMove', later_redraw)", self.js)
        self.assertIn('function later_redraw', self.js)
        self.assertIn('setTimeout(redraw, 0)', self.js)

    def test_끌어서_정한_것이_가장_세다(self):
        head = self.js.index('function compute')
        block = self.js[head:head + 1400]
        self.assertIn('overrides[name]', block)

    def test_여러_칸을_함께_조절해도_남는다(self):
        """
        인자로 온 칸 하나만 보면 함께 조절한 나머지가 빠진다. 지금 그려진
        너비를 통째로 읽어 이름에 붙인다.
        """
        head = self.js.index("hot.addHook('afterColumnResize'")
        block = self.js[head:head + 700]
        self.assertIn('for (var v = firstCol;', block)
        self.assertIn('hot.getColWidth(v)', block)

    def test_내용이_없으면_최소로_접는다(self):
        self.assertIn('function hasContent', self.js)
        head = self.js.index('function compute')
        self.assertIn('hasContent(hot, firstCol + i)', self.js[head:head + 1400])

    def test_너비가_바뀌면_줄_높이를_다시_잰다(self):
        """재 둔 값이 남아 있으면 행 번호와 내용이 어긋난 채로 그려진다."""
        head = self.js.index('function redraw')
        block = self.js[head:head + 500]
        self.assertIn("getPlugin('autoRowSize')", block)
        self.assertIn('clearCache', block)
        self.assertIn('hot.render()', block)

    def test_계정에_남는다(self):
        """브라우저가 아니라 계정이다 — 다른 자리에서 열어도 같은 표여야 한다."""
        self.assertIn("'/common/grid-order/'", self.js)
        from pathlib import Path
        from django.conf import settings as dj
        common = (Path(dj.BASE_DIR) / 'common/views.py').read_text(encoding='utf-8')
        self.assertIn('def grid_widths(user, screen)', common)
        self.assertIn("saved['widths'] = clean", common)
        # 화면이 보내는 것은 칸 몇 개의 픽셀 수뿐이다
        self.assertIn('20 <= px <= 1200', common)


class 화면이_부르는_도우미는_그_화면에_있다(TestCase):
    """
    BOM 화면이 `getCsrfToken()` 을 부르는데 그 함수가 없었다. 부모 화면
    (product_detail.html)에 같은 이름이 있어서 있는 줄 알았는데, BOM 은
    iframe 안에서 돌고 iframe 은 제 창을 쓴다.

    없는 함수를 부른 자리가 셋이었고 그 하나가 initGrid 안이라 **초기화가
    통째로 멈췄다** — 원료 보관함 접기, 칸 너비, 붙여넣기 안내가 다 같이
    죽었고, 칸을 끌어다 옮기면 제자리로 돌아간 것처럼 보였다(afterColumnMove
    에서 예외가 나면 Handsontable 이 그 뒤의 render 를 건너뛴다).
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.bom = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                    ).read_text(encoding='utf-8')

    def test_csrf_도우미가_이_화면에_있다(self):
        self.assertIn('getCsrfToken()', self.bom)
        self.assertIn('function getCsrfToken()', self.bom)

    def test_붙여넣기_안내는_무슨_일이_나도_나온다(self):
        """몇 줄이 들어갔는지 못 보면 붙여넣기가 안 된 줄 알게 된다."""
        head = self.bom.index("onReport: function (info)")
        block = self.bom[head:head + 1400]
        self.assertIn('try {', block)
        self.assertLess(block.index('try {'), block.index('sheetPasteSaveOrder'))
        self.assertIn('showSnackbar(', block)

    def test_칸을_옮기는_훅이_통째로_죽지_않는다(self):
        head = self.bom.index("hot.addHook('afterColumnMove'")
        block = self.bom[head:head + 700]
        self.assertIn('try {', block)
        self.assertIn('catch (e) {}', block)


class 파일_크기는_한곳에서_정한다(TestCase):
    """
    한도가 화면마다 달랐다 — 문서함 50 MB, 표시사항 사진 10 MB, 원료 사진
    10 MB, 시안 20 MB, 판독 실험실 10 MB. 같은 성적서를 문서함에는 올릴 수
    있는데 사진으로는 못 올렸고, 왜 안 되는지 화면마다 다른 말을 했다.

    한 파일의 상한은 서버 보호 값이라 등급과 무관하고(30 MB), 한 사람이
    통틀어 쓰는 용량은 쌓여 있는 동안 자리를 차지하므로 저량 한도로 센다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='uploader', password='x')

    def test_한_파일은_30MB_까지(self):
        from v1.common.uploads import MAX_UPLOAD_MB

        self.assertEqual(MAX_UPLOAD_MB, 30)

    def test_큰_파일은_왜_안_되는지_말해_준다(self):
        """"파일이 큽니다" 만으로는 무엇을 해야 하는지 모른다."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from v1.common.uploads import check

        big = SimpleUploadedFile('big.pdf', b'x')
        big.size = 40 * 1024 * 1024
        message = check(self.user, big, '파일')
        self.assertIn('30 MB', message)
        self.assertIn('40.0 MB', message)
        self.assertIn('나눠', message)

    def test_한도_안이면_받는다(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from v1.common.uploads import check

        ok = SimpleUploadedFile('ok.pdf', b'x')
        ok.size = 12 * 1024 * 1024
        self.assertIsNone(check(self.user, ok, '파일'))

    def test_한_사람이_쓰는_용량도_센다(self):
        from v1.common import quota

        usage = quota.usage(self.user, 'storage')
        self.assertEqual(usage['unit'], 'MB')
        self.assertEqual(usage['kind'], quota.STOCK)
        self.assertGreater(usage['limit'], 0)

    def test_화면마다_다른_숫자를_적어_두지_않는다(self):
        from pathlib import Path
        from django.conf import settings as dj

        for rel in ('products/views.py', 'label/views.py', 'label/views_ocr_lab.py'):
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            self.assertNotIn('10 * 1024 * 1024', text, rel)
            self.assertNotIn('50 * 1024 * 1024', text, rel)


class 쓰고_있는_양을_올리기_전에_보여_준다(TestCase):
    """
    한도가 있다는 것을 **다 쓰고 나서 알면 화가 난다.** 파일을 올리려는데
    "한도에 닿았습니다" 만 나오면, 얼마나 썼는지도 무엇을 지워야 하는지도
    모른 채 막힌다.

    요금제를 여는 날 이 자리가 그대로 안내가 된다 — 등급은 UserProfile.paid_yn
    하나뿐이고, 한도는 quota.FEATURES 한 곳에 있다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='usage', password='x',
                                             email='usage@example.com')
        self.client.force_login(self.user)

    def test_내_정보에_사용량이_있다(self):
        res = self.client.get('/user-management/profile/')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('사용량', html)
        self.assertIn('올린 파일', html)      # 저장 용량
        self.assertIn('등록한 원료', html)     # 저량 한도
        self.assertIn('30 MB', html)          # 한 파일 상한

    def test_흐름과_저량을_가려_말한다(self):
        """
        하루에 몇 번(판독)과 통틀어 몇 건(원료·파일)은 세는 법도 다 썼을 때
        할 말도 다르다 — "내일 다시" 와 "지우거나 올리세요".
        """
        res = self.client.get('/user-management/profile/')
        html = res.content.decode('utf-8')
        self.assertIn('(오늘)', html)
        self.assertIn('지우면 그만큼 자리가 돌아옵니다', html)

    def test_한도는_한_곳에서_온다(self):
        """요금제를 손볼 때 코드를 고치지 않고 settings 로도 내릴 수 있어야 한다."""
        from django.test import override_settings

        from v1.common import quota

        with override_settings(QUOTA_LIMITS={'storage': {'free': 100}}):
            self.assertEqual(quota.limit_for(self.user, 'storage'), 100)


class 끼워_넣다_남의_규칙을_가르지_않는다(TestCase):
    """
    내 문구 조각의 CSS 를 넣다가 하필 이 자리를 갈랐다.

        .btn-storage-badge,
        .v2-chip-check > label { … }      <- 두 줄이 한 규칙이다

    가운데에 새 규칙을 끼우니 `.btn-storage-badge` 가 엉뚱한 규칙에 붙었고,
    보관방법 버튼(냉동·냉장·실온·상온)이 칩 모양을 잃었다. 쉼표로 이어진
    선택자 사이는 **한 규칙의 한가운데**다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.tab = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                    ).read_text(encoding='utf-8')

    def test_보관방법_버튼이_칩_규칙을_그대로_쓴다(self):
        self.assertIn('.btn-storage-badge,\n.v2-chip-check > label {', self.tab)

    def test_내_문구_규칙은_그_뒤에_있다(self):
        self.assertLess(self.tab.index('.btn-storage-badge,\n.v2-chip-check > label {'),
                        self.tab.index('.my-phrase-chip {'))

    def test_같은_칩_모양을_쓴다(self):
        """여기만 각지고 회색이면 같은 줄에 선 기본 문구 버튼과 따로 논다."""
        head = self.tab.index('.my-phrase-act:last-child')
        self.assertIn('border-radius: 0 16px 16px 0', self.tab[head:head + 200])


class 코치마크는_그_화면만_짚는다(TestCase):
    """
    예전 튜토리얼은 모달을 연속으로 넘기는 전체 투어였고 버려졌다. 한 번 보고
    끝나는 데다, 사람이 막히는 순간은 가입 첫날이 아니라 **지금 이 칸**이다.

    그래서 화면마다 [튜토리얼] 을 두고 그 화면만 서너 걸음으로 짚는다. 여기서
    지키려는 것은 셋이다 — 문구가 엔진이 아니라 화면에 있을 것, 가리킬 것이
    없으면 걸음을 뺄 것, iframe 안을 가리키지 않을 것.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        base = Path(dj.BASE_DIR) / 'templates'
        self.engine = (base / 'includes/_coachmark.html').read_text(encoding='utf-8')
        self.product = (base / 'products/product_detail.html').read_text(encoding='utf-8')
        self.basic = (base / 'products/_tab_basic_info.html').read_text(encoding='utf-8')
        self.ingredient = (base / 'label/my_ingredient_detail_partial.html'
                           ).read_text(encoding='utf-8')

    def _steps(self, html):
        import re
        block = re.search('<div class="ezc-steps".*?' + chr(10) + '</div>',
                          html, re.S)
        self.assertIsNotNone(block, '걸음 목록이 없다')
        return re.findall(r'data-sel="([^"]+)"', block.group(0))

    def test_두_화면이_각각_서너_걸음을_갖는다(self):
        """
        여섯을 넘으면 투어다 — 한 번에 읽히는 분량이 그쯤이다.

        제품 상세만 예외로 길다. 탭이 여섯이고 그 여섯이 저마다 다른 일을 해서,
        "한 화면" 으로 세면 여섯 화면을 겹쳐 둔 것과 같다. 게다가 BOM·영양성분·
        미리보기가 iframe 이라 안쪽을 못 가리키므로, 탭 단추 하나를 여러 걸음이
        거듭 가리키며 그 안에서 할 일을 나눠 말한다.
        """
        sels = self._steps(self.ingredient)
        self.assertGreaterEqual(len(sels), 3, '원료 상세')
        self.assertLessEqual(len(sels), 6, '원료 상세: 여섯 걸음을 넘으면 투어다')

        sels = self._steps(self.product)
        self.assertGreaterEqual(len(sels), 12, '제품 상세: 탭마다 한 걸음은 있어야 한다')
        self.assertLessEqual(len(sels), 20, '제품 상세: 이보다 길면 탭 설명이 아니다')

    def test_문구는_엔진이_아니라_화면에_있다(self):
        """
        엔진에 문구를 두면 화면마다 엔진을 고쳐야 하고, 자바스크립트 문자열에
        든 한국어 한 줄이 끊기면 그 script 블록 전체가 죽는다(templates.E006).
        """
        script = self.engine[self.engine.index('<script>'):]
        # 엔진이 제 입으로 말하는 것은 단추 이름뿐이다
        self.assertIn("'다음'", script)
        self.assertIn("'닫기'", script)      # '그만두기' 에서 바꿨다
        for word in ('품목보고번호', '알레르기', '배합비'):
            self.assertNotIn(word, script, '화면 문구가 엔진에 새어 들어갔다')

    def test_가리킬_것이_없으면_그_걸음을_건너뛴다(self):
        """새 원료에는 영양성분 칸이 아직 없다. 빈 곳을 가리키면 안 된다."""
        # 다만 탭을 적어 둔 걸음은 빼지 않는다 — 그 탭을 열면 보이기 때문이다
        self.assertIn('if (sel && !tab) {', self.engine)
        self.assertIn('if (!shown(now)) return;', self.engine)
        self.assertIn('r.width > 0 && r.height > 0', self.engine)
        # 새 원료에 없는 그 칸이 실제로 걸음에 들어 있다 — 건너뛰기가 도는 자리
        self.assertIn('#ingNutrition', self._steps(self.ingredient))

    def test_가리키는_것이_실제로_그_화면에_있다(self):
        """
        선택자가 틀리면 걸음이 조용히 사라진다 — 건너뛰기와 구별이 안 된다.
        그래서 여기서 대조한다.
        """
        from v1.products.views import _WORKFLOW_STEPS
        tabs = {'#' + tab for tab, _name, _hint in _WORKFLOW_STEPS}

        for sel in self._steps(self.product):
            if sel.startswith('[data-bs-target'):
                # 네 단계 탭은 _WORKFLOW_STEPS 로 찍히고, 곁에 두는 문서함·권한은
                # 화면이 직접 적는다. 둘 중 한쪽에는 있어야 한다.
                target = sel[sel.index('#'):sel.rindex('&quot;')]
                self.assertTrue(
                    target in tabs
                    or ('data-bs-target="%s"' % target) in self.product,
                    sel)
                continue
            mark = ('id="%s"' % sel[1:]) if sel.startswith('#') else ('class="%s' % sel[1:])
            self.assertTrue(mark in self.product or mark in self.basic, sel)

        for sel in self._steps(self.ingredient):
            self.assertIn('id="%s"' % sel[1:], self.ingredient, sel)

    def test_iframe_안은_가리키지_않는다(self):
        """
        BOM·영양성분·미리보기는 iframe 이다. 안쪽 좌표를 얻으려면 postMessage
        가 필요한데 그만한 얼개를 지금 들이지 않았다 — 탭 단추까지만 가리킨다.
        """
        import re
        inner = set()
        for frame in re.findall(r'<iframe[^>]*id="([^"]+)"', self.product):
            inner.add('#' + frame)
        for sel in self._steps(self.product):
            self.assertNotIn(sel, inner)
        self.assertIn('postMessage', self.engine)   # 왜 안 하는지 적어 두었다

    def test_본_것은_기억해서_다시_권하지_않는다(self):
        self.assertIn("localStorage.setItem(KEY", self.engine)
        self.assertIn('if (seen(key)) return;', self.engine)
        # 막혀 있는 브라우저에서 읽기만 해도 예외가 난다. 화면이 죽으면 안 된다.
        self.assertIn('catch (e) { return false; }', self.engine)

    def test_신규_사용자에게는_제품_화면에서_한_번_권한다(self):
        self.assertIn('data-coach-offer="1"', self.product)
        # 원료 화면은 권하지 않는다 — 스스로 [튜토리얼] 을 누를 때만 연다
        self.assertNotIn('data-coach-offer', self.ingredient)

    def test_저절로_시작하지_않는다(self):
        """가로막고 시작하는 것이 예전 투어가 버려진 까닭이다."""
        import re
        offer = self.engine[self.engine.index('function offer()'):]
        offer = offer[:offer.index('window.ezCoach =')]
        self.assertIsNone(re.search(r'^\s*start\(\);', offer, re.M))

    def base(self):
        import io
        return io.open('v1/templates/base_v2.html', encoding='utf-8').read()

    def test_들어가는_자리는_떠_있는_단추다(self):
        """
        자리를 두 번 옮겼다.

            ① 화면 머리의 행동 단추들 사이  -> 못 찾았다. 저장·삭제·공유 옆이라
                                              도움을 찾는 눈이 가는 자리가 아니다
            ② 사이드바의 '새로 만들기' 옆   -> 사이드바는 **접힌다**(아이콘만
                                              남는다). 게다가 제품 상세는
                                              사이드바를 접고 시작한다

        오른쪽 아래 동그란 단추는 어느 화면에서나 같은 자리이고 접히지 않는다.
        """
        engine = self.engine
        self.assertIn("fab.className = 'ezc-fab'", engine)
        self.assertIn('.ezc-fab', engine)
        self.assertIn('position: fixed', engine[engine.index('.ezc-fab {'):])
        # 화면이 제 단추를 따로 만들지 않는다 — 같은 일에 단추가 둘이면 묻게 된다
        for html in (self.product, self.ingredient):
            self.assertNotIn('ezCoach.start()', html)
        self.assertNotIn('ezCoachNavBtn', self.base())

    def test_묻는_것이_둘이라_갈래도_둘이다(self):
        """
        한때 셋이었다. 가운데에 '핵심기능 보기' 를 두어 "그래서 뭘 할 수
        있는데" 에 답하게 했는데, **전체 둘러보기와 거의 같은 말을 하고
        있었다** — 메뉴를 짚으면서 그 메뉴가 무슨 일을 하는지 말하면 그게 곧
        기능 소개다.
        """
        engine = self.engine
        for scope in ('tour', 'detail'):
            self.assertIn("usable('%s')" % scope, engine, scope)
        self.assertIn('전체 둘러보기', engine)
        self.assertIn('이 화면 사용법', engine)
        # 한때 가운데에 '핵심기능 보기' 가 있었다 — 전체 둘러보기와 거의 같은
        # 말을 하고 있어서 걷었다. 되살아나면 또 겹친다.
        self.assertNotIn('핵심기능 보기', engine)

    def test_가리킬_것이_없어도_말은_한다(self):
        """
        게시판에서 "BOM 은 엑셀에서 붙여 넣을 수 있습니다" 를 말하려면 가리킬
        요소가 없다. 없는 자리를 억지로 가리키느니 말만 하는 편이 낫다.
        """
        engine = self.engine
        self.assertIn('if (!el) {', engine)
        # 0 크기 테두리에 큰 box-shadow 가 남으면 이상한 자국이 된다
        self.assertIn("spot.style.display = 'none'", engine)
        self.assertIn('if (seat) {', engine)      # 화면 안으로 끌어오는 것도 막는다

    def test_메뉴_둘러보기는_한_곳에만_적는다(self):
        """어느 화면에서나 같은 걸음이다. 화면마다 적으면 곧 갈라진다."""
        base = self.base()
        self.assertIn('data-coach-scope="tour"', base)
        for html in (self.product, self.ingredient):
            self.assertNotIn('data-coach-scope="tour"', html)

    def test_메뉴를_이름표로_짚는다(self):
        """
        href 로 짚으면 주소가 바뀔 때 **조용히** 어긋난다 — 걸음이 사라지고
        건너뛴 것과 구별이 안 된다.
        """
        base = self.base()
        self.assertIn('data-nav="products"', base)
        self.assertIn('data-nav="ingredients"', base)
        tour = base[base.index('data-coach-scope="tour"'):]
        tour = tour[:tour.index('</div>' + chr(10) + '    </div>')]
        for key in ('products', 'ingredients', 'lookup', 'additives',
                    'collab', 'contacts', 'regulatory', 'board'):
            self.assertIn("data-sel=\"[data-nav='%s']\"" % key, tour, key)
            self.assertIn('data-nav="%s"' % key, base, key)

    def test_엔진은_모든_화면에_실린다(self):
        """
        예전에는 화면 둘에만 include 해 두어 나머지 메뉴에서는 도움말이 아예
        없었다.
        """
        base = self.base()
        self.assertIn('includes/_coachmark.html', base)
        for html in (self.product, self.ingredient):
            self.assertNotIn('includes/_coachmark.html', html)

    def test_갈_곳이_없으면_단추도_없다(self):
        """
        눌러도 아무 일이 없는 단추를 어느 화면에나 띄워 두면 곧 안 보게 되고,
        정작 걸음이 있는 화면에서도 안 누른다.
        """
        engine = self.engine
        self.assertIn("var any = usable('tour') || usable('detail');", engine)
        self.assertIn('if (!any)', engine)

    def test_게스트에게도_보인다(self):
        """게스트는 둘러보러 온 사람이다 — 설명이 가장 필요한 쪽이다."""
        engine = self.engine
        self.assertNotIn('is_guest', engine)


class 코치마크는_화면마다_제_것을_짚는다(TestCase):
    """
    걸음이 제품·원료 두 화면에만 있어서, 나머지 메뉴에서는 [?] 를 눌러도
    "이 화면은 아직 안내가 없습니다" 만 떴다. 메뉴를 여덟 개 만들어 놓고
    둘만 설명하면 나머지 여섯은 알아서 익히라는 말이 된다.

    여기서 지키려는 것은 하나다 — **선택자가 그 화면에 실제로 있을 것.**
    엔진은 가리킬 것이 없으면 그 걸음을 조용히 건너뛴다. 그래서 선택자를
    잘못 적어도 화면은 멀쩡해 보이고, 걸음만 소리 없이 사라진다. 일부러
    건너뛴 것과 오타를 눈으로는 구별할 수 없으므로 여기서 대조한다.
    """

    # 화면 → (걸음이 적힌 템플릿, 요소를 찾아도 되는 템플릿들)
    #
    # 제품 상세만 둘을 본다 — 기본 정보 탭은 include 로 들어오는 딴 파일이다.
    화면들 = {
        '제품 상세': ('products/product_detail.html',
                   ('products/product_detail.html', 'products/_tab_basic_info.html')),
        '원료 상세': ('label/my_ingredient_detail_partial.html',
                   ('label/my_ingredient_detail_partial.html',)),
        '원료 관리': ('label/my_ingredient_list_combined.html',
                   ('label/my_ingredient_list_combined.html',)),
        '제품 관리': ('products/product_explorer.html',
                   ('products/product_explorer.html',)),
        '제품 조회': ('label/food_item_list.html',
                   ('label/food_item_list.html',)),
        '식품첨가물 DB': ('label/food_additive_search.html',
                      ('label/food_additive_search.html',)),
        '공동 작업': ('products/sharing/inbox.html',
                   ('products/sharing/inbox.html',)),
        '연락처 관리': ('products/contacts.html',
                    ('products/contacts.html',)),
        '부적합·처분 알림': ('regulatory/news_list.html',
                        ('regulatory/news_list.html',)),
        '게시판': ('board/list.html', ('board/list.html',)),
    }

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR) / 'templates'
        self._cache = {}

    def _read(self, name):
        if name not in self._cache:
            self._cache[name] = (self.base / name).read_text(encoding='utf-8')
        return self._cache[name]

    def _block(self, name):
        import re
        html = self._read(name)
        found = re.search('<div class="ezc-steps".*?' + chr(10) + '</div>', html, re.S)
        self.assertIsNotNone(found, '%s 에 걸음 목록이 없다' % name)
        return found.group(0)

    def _steps(self, name):
        import re
        return re.findall(r'data-sel="([^"]+)"', self._block(name))

    def _있는가(self, sel, html):
        """
        엔진은 querySelector 로 찾는다. 여기서 그 셋을 흉내 낸다 —
        #아이디, .클래스, [속성="값"].

        클래스는 문자열 포함으로 보면 안 된다. class="board-table-wrapper" 가
        `.board-table` 로 잡혀 버려서, 정작 없는 선택자를 있다고 통과시킨다.
        그래서 class 값을 공백으로 갈라 낱말로 맞춘다.
        """
        import re
        if sel.startswith('#'):
            return ('id="%s"' % sel[1:]) in html
        if sel.startswith('.'):
            want = sel[1:]
            for attr in re.findall(r'class="([^"]*)"', html):
                if want in attr.split():
                    return True
            return False
        found = re.match(r'^\[([a-z-]+)=(?:&quot;|\')?([^\]\'&]+)(?:&quot;|\')?\]$', sel)
        self.assertIsNotNone(found, '흉내 낼 수 없는 선택자다: %s' % sel)
        attr, value = found.groups()
        return ('%s="%s"' % (attr, value)) in html or \
               ("%s='%s'" % (attr, value)) in html

    def test_가리키는_것이_실제로_그_화면에_있다(self):
        """
        선택자가 틀리면 걸음이 조용히 사라진다 — 건너뛴 것과 구별이 안 된다.
        """
        from v1.products.views import _WORKFLOW_STEPS
        탭들 = {'#' + tab for tab, _name, _hint in _WORKFLOW_STEPS}

        for 화면, (걸음템플릿, 볼곳들) in self.화면들.items():
            for sel in self._steps(걸음템플릿):
                # 네 단계 탭 단추는 _WORKFLOW_STEPS 로 찍혀 나와서 화면에
                # 글자 그대로 있지 않다.
                if sel.startswith('[data-bs-target') and \
                        sel[sel.index('#'):sel.rindex('&quot;')] in 탭들:
                    continue
                self.assertTrue(
                    any(self._있는가(sel, self._read(곳)) for 곳 in 볼곳들),
                    '%s: %s 를 가리키는데 그 화면에 없다' % (화면, sel))

    def test_메뉴마다_걸음이_있다(self):
        """
        사이드바에 메뉴를 여덟 개 걸어 두고 둘만 설명하면, 나머지에서 [?] 를
        누른 사람은 "안내가 없습니다" 를 보고 다시는 안 누른다.
        """
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            sels = self._steps(걸음템플릿)
            self.assertGreaterEqual(len(sels), 3, '%s: 세 걸음은 있어야 한다' % 화면)

    def test_걸음_이름이_겹치지_않는다(self):
        """
        본 것은 data-coach-key 로 기억한다. 두 화면이 같은 이름을 쓰면 한쪽을
        본 것만으로 다른 쪽까지 본 것이 되어 권하기가 영영 안 뜬다.
        """
        import re
        본것 = {}
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            found = re.search(r'data-coach-key="([^"]+)"', self._block(걸음템플릿))
            self.assertIsNotNone(found, '%s: 걸음 이름이 없다' % 화면)
            key = found.group(1)
            self.assertNotIn(key, 본것,
                             '%s 와 %s 가 같은 이름을 쓴다: %s'
                             % (화면, 본것.get(key), key))
            본것[key] = 화면

    def test_문구가_비어_있지_않다(self):
        """
        제목만 있고 본문이 없으면 상자가 한 줄짜리로 뜬다. 짚어 놓고 아무 말도
        안 하는 셈이라 차라리 그 걸음이 없는 편이 낫다.
        """
        import re
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            for title, body in re.findall(
                    r'data-title="([^"]*)"\s*>(.*?)</div>',
                    self._block(걸음템플릿), re.S):
                self.assertTrue(title.strip(), '%s: 제목이 비었다' % 화면)
                말 = re.sub(r'<[^>]+>', '', body).strip()
                self.assertGreater(len(말), 20,
                                   '%s: "%s" 에 할 말이 없다' % (화면, title))

    def test_화면이_엔진을_들이지_않는다(self):
        """엔진은 base_v2 에 한 번만 실린다. 화면이 또 include 하면 두 벌이 된다."""
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            self.assertNotIn('includes/_coachmark.html',
                             self._read(걸음템플릿), 화면)

    def test_화면이_제_단추를_만들지_않는다(self):
        """
        도움말로 들어가는 자리는 오른쪽 아래 동그란 [?] 하나다. 화면마다 제
        단추를 두면 같은 일을 하는 단추가 둘이 되어 어느 것을 눌러야 하는지
        묻게 된다.
        """
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            self.assertNotIn('ezCoach.start(', self._read(걸음템플릿), 화면)

    def test_여러_줄_주석은_comment_태그로_적는다(self):
        """
        {# #} 는 한 줄짜리다. 여러 줄에 걸치면 뒷줄이 그대로 화면에 인쇄된다 —
        자체 검사(checks.py)가 잡는 그 사고다.
        """
        for 화면, (걸음템플릿, _볼곳들) in self.화면들.items():
            앞 = self._read(걸음템플릿)
            at = 앞.index('<div class="ezc-steps"')
            머리 = 앞[max(0, at - 1200):at]
            self.assertIn('{% comment %}', 머리,
                          '%s: 왜 이 걸음인지 적어 두지 않았다' % 화면)

    def test_탭마다_거기서_하는_일을_말한다(self):
        """
        BOM·영양성분·미리보기는 iframe 이라 안쪽 칸을 못 가리킨다. 그래서 탭
        단추만 짚게 되는데, 그때 "BOM 탭입니다" 로 그치면 짚으나 마나다 —
        탭 이름은 이미 화면에 적혀 있다.

        가리킬 수 없으니 **말로는 더 구체적이어야 한다.** 그 탭에서 실제로
        할 수 있는 일이 문구에 들어 있는지 여기서 확인한다. 없는 기능을 지어
        쓰는 것도 이 목록이 막는다 — 넣으려면 먼저 코드에 있어야 한다.
        """
        block = self._block('products/product_detail.html')
        해야할말 = [
            ('BOM 붙여넣기', '붙여넣으면'),
            ('BOM 머리글 인식', '머리글'),
            ('BOM 행 자동 확장', '자동으로 추가됩니다'),
            ('영양성분 자동 계산', '배합비'),
            ('영양성분 기여도', '영향을 주지 않는 원료는 비어 있어도'),
            ('검증 표 설정', '자간'),
            ('검증 항목 순서', '항목 순서'),
            ('검증 분리배출마크', '분리배출마크'),
            ('1차 문구 검증', '번호가 붙고'),
            ('2차 시안 대조', '올려 둔 시안'),
            ('내보내기 PDF', '한 장'),
            ('내보내기 문서함', '문서함에도 등록'),
        ]
        for 이름, 말 in 해야할말:
            self.assertIn(말, block, '%s 을(를) 말하지 않는다' % 이름)


class 갈래를_적어_둔다(TestCase):
    """
    엔진은 `data-coach-scope` 를 안 적으면 detail 로 본다. 옛 화면이 갑자기
    멈추지 않게 하는 그물인데, 한때 **모든 화면이 그 기본값에 기대고 있었다.**

    그러면 왜 detail 인지가 코드에 안 남고, 명시하는 쪽이 오히려 이상해 보인다.
    그물은 쓰는 방법이 아니다.
    """

    SCREENS = (
        'v1/templates/products/product_detail.html',
        'v1/templates/label/my_ingredient_detail_partial.html',
        'v1/templates/label/my_ingredient_list_combined.html',
        'v1/templates/products/product_explorer.html',
        'v1/templates/label/food_item_list.html',
        'v1/templates/label/food_additive_search.html',
        'v1/templates/products/sharing/inbox.html',
        'v1/templates/products/contacts.html',
        'v1/templates/regulatory/news_list.html',
        'v1/templates/board/list.html',
    )

    def test_화면마다_detail_이라고_적는다(self):
        import io
        for path in self.SCREENS:
            text = io.open(path, encoding='utf-8').read()
            at = text.index('class="ezc-steps"')
            head = text[at:at + 160]
            self.assertIn('data-coach-scope="detail"', head, path)

    def test_그물은_남겨_둔다(self):
        """
        지우면 옛 화면이 조용히 멈춘다 — 걸음이 하나도 안 잡혀 단추부터
        안 뜨고, 그건 "안내가 없는 화면" 과 구별이 안 된다.
        """
        import io
        engine = io.open('v1/templates/includes/_coachmark.html',
                         encoding='utf-8').read()
        self.assertIn("var want = scope || 'detail';", engine)
        self.assertIn("all[i].getAttribute('data-coach-scope') || 'detail'", engine)


class 틀_안에서는_돌지_않는다(TestCase):
    """
    BOM 탭에 **도움말 단추가 둘** 나타났다. 위치도 살짝 어긋나 보였다.

    제품 상세의 BOM 탭은 `bom_detail.html` 을 iframe 으로 띄우는데, 그 문서가
    `base_v2` 를 상속한다 — 그래서 엔진이 **한 벌 더** 돌았다. 바깥 단추와
    안쪽 단추가 겹쳐 둘로 보이고, 안쪽 것은 **iframe 좌표계**라 자리도
    어긋난다.

    도움말은 사람이 보고 있는 **바깥 창**의 일이다.
    """

    def engine(self):
        import io
        return io.open('v1/templates/includes/_coachmark.html',
                       encoding='utf-8').read()

    def test_틀_안이면_아무것도_안_한다(self):
        engine = self.engine()
        self.assertIn('if (window.self !== window.top) return;', engine)

    def test_바깥을_못_읽어도_안_돈다(self):
        """출처가 다르면 접근 자체가 던진다 — 남의 사이트에 끼워진 것이다."""
        engine = self.engine()
        at = engine.index('if (window.self !== window.top) return;')
        self.assertIn('catch', engine[at:at + 200])

    def test_그_까닭이_실제로_있다(self):
        """고친 이유가 사라지지 않았는지 본다."""
        import io
        bom = io.open('v1/templates/products/bom_detail.html', encoding='utf-8').read()
        self.assertIn("{% extends 'base_v2.html' %}", bom)


class 말만_하지_않고_데려간다(TestCase):
    """
    '핵심기능 보기' 는 처음에 가운데 카드로 **말만** 했다. 그랬더니 "내용이
    눈에 안 들어온다" 는 말이 나왔다 — 당연하다. 기능을 글로 읽는 것과 그
    화면을 보는 것은 다른 일이고, 이 물건은 원래 **가리켜서** 말하는 것이다.
    """

    def engine(self):
        import io
        return io.open('v1/templates/includes/_coachmark.html',
                       encoding='utf-8').read()

    def base(self):
        import io
        return io.open('v1/templates/base_v2.html', encoding='utf-8').read()

    def product(self):
        import io
        return io.open('v1/templates/products/product_detail.html',
                       encoding='utf-8').read()

    def test_다른_화면으로_옮겨_간다(self):
        engine = self.engine()
        self.assertIn("step.go && step.go !== location.pathname", engine)
        self.assertIn('location.href = step.go', engine)

    def test_옮겨_간_뒤_그_자리에서_이어_간다(self):
        """화면이 새로 뜨므로 어디까지 갔는지를 남겨야 한다."""
        engine = self.engine()
        self.assertIn('function saveResume', engine)
        self.assertIn('function takeResume', engine)
        self.assertIn('start(back.scope, back.at)', engine)

    def test_브라우저를_닫으면_사라진다(self):
        """
        다음에 열었을 때 하던 튜토리얼이 되살아나면 놀란다. localStorage 가
        아니라 sessionStorage 다.
        """
        engine = self.engine()
        at = engine.index('function saveResume')
        body = engine[at:at + 400]
        self.assertIn('sessionStorage', body)
        self.assertNotIn('localStorage', body)

    def test_한_번만_쓴다(self):
        """지우지 않으면 새로고침할 때마다 튜토리얼이 다시 열린다."""
        engine = self.engine()
        at = engine.index('function takeResume')
        self.assertIn('removeItem', engine[at:at + 400])

    def test_제품_상세_걸음이_제_탭을_연다(self):
        """
        탭 단추만 가리키면 기본 정보를 배경에 둔 채 "BOM 은 …" 이라고 말하게
        되어 무슨 말인지 눈에 안 들어온다.
        """
        html = self.product()
        # **모든** 걸음이 제 탭을 적는다. 기본 정보 걸음까지 적어야 BOM 탭에서
        # 튜토리얼을 열어도 같은 열일곱 걸음이 나온다 — 예전에는 기본 정보
        # 걸음이 안 보인다는 이유로 잘려 나가 열 걸음만 나왔다.
        block = html[html.index('class="ezc-steps"'):]
        block = block[:block.index('</div>' + chr(10) + '</div>')]
        self.assertEqual(block.count('data-title='), block.count('data-tab="tab-'))
        self.assertIn('data-tab="tab-info"', block)
        engine = self.engine()
        self.assertIn("document.querySelector('[data-bs-target=\"#' + step.tab + '\"]')",
                      engine)

    def test_어느_탭에서_열어도_같은_걸음이_나온다(self):
        """
        기본 정보에서 열면 열일곱, BOM 에서 열면 열이 나왔다. 같은 화면인데
        묻는 자리에 따라 안내가 달라졌다.

        까닭은 걸음을 모을 때 지금 안 보이는 요소를 잘라 낸 것이었다. 탭 속
        요소는 그 탭을 열면 보이므로 잘라 낼 것이 아니다. 이제 자리는 **그릴
        때** 찾는다.
        """
        engine = self.engine()
        self.assertIn('function target(step)', engine)
        # 모을 때가 아니라 그릴 때 찾는다
        self.assertNotIn('step.el', engine)
        self.assertIn('var el = target(step);', engine)

    def test_탭이_자리를_잡은_뒤에_그린다(self):
        """바로 재면 크기가 0 이라 걸음이 조용히 빠진다."""
        engine = self.engine()
        at = engine.index('if (step && step.tab) {')
        self.assertIn('setTimeout(draw', engine[at:at + 500])


class 네비_순서는_튜토리얼_차례와_같다(TestCase):
    """
    둘러보기가 "제품 조회" 를 짚는데 사이드바에서는 그것이 다섯 번째면, 보는
    사람의 눈이 오르내린다. 순서가 같아야 따라가진다.
    """

    def test_사이드바와_둘러보기가_같은_차례다(self):
        import io
        import re
        base = io.open('v1/templates/base_v2.html', encoding='utf-8').read()

        nav = re.findall(r'data-nav="([a-z]+)"', base)
        tour = base[base.index('data-coach-scope="tour"'):]
        tour = tour[:tour.index('</div>' + chr(10) + '    </div>')]
        steps = re.findall(r"data-sel=\"\[data-nav='([a-z]+)'\]\"", tour)

        self.assertEqual(nav, steps)
        self.assertEqual(nav, ['products', 'ingredients', 'lookup', 'additives',
                               'collab', 'contacts', 'regulatory', 'board'])


class 시안_대조_판정은_서버가_한다(TestCase):
    """
    규칙 표를 화면에 베껴 두면 파이썬 쪽과 두 벌이 되고, 두 벌은 언젠가
    한쪽만 고쳐진다. 이 저장소가 실제로 여러 번 당한 실패다.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        from v1.label.models import MyLabel

        self.me = User.objects.create_user(username='me@example.com', password='pw12345!')
        self.other = User.objects.create_user(username='you@example.com', password='pw12345!')
        self.label = MyLabel.objects.create(user_id=self.me, prdlst_nm='제품')
        self.url = reverse('products:design_compare_grade', args=[self.label.pk])

    def _post(self, fields):
        return self.client.post(self.url, data=json.dumps({'fields': fields}),
                                content_type='application/json')

    def test_항목마다_다른_자로_판정해_돌려준다(self):
        self.client.force_login(self.me)
        resp = self._post({
            'prdlst_dcnm':    {'mine': '빵류', 'design': '빵류 [가열하여 섭취하는 냉동식품]'},
            'content_weight': {'mine': '12.5g', 'design': '12.50g'},
            'bssh_nm':        {'mine': '(주)○○식품', 'design': '주식회사 ○○식품'},
        })
        self.assertEqual(resp.status_code, 200)
        grades = resp.json()['grades']
        for field in ('prdlst_dcnm', 'content_weight', 'bssh_nm'):
            self.assertNotEqual(grades[field]['grade'], 'diff', field)

    def test_수치가_다르면_다르다고_한다(self):
        self.client.force_login(self.me)
        grades = self._post({'content_weight': {'mine': '12.5g', 'design': '12.6g'}}).json()['grades']
        self.assertEqual(grades['content_weight']['grade'], 'diff')

    def test_남의_라벨은_404(self):
        """403 은 그 id 가 있다고 알려 준다."""
        self.client.force_login(self.other)
        self.assertEqual(self._post({}).status_code, 404)

    def test_로그인하지_않으면_못_부른다(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp['Location'])

    def test_GET_으로는_안_된다(self):
        self.client.force_login(self.me)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_망가진_요청에도_터지지_않는다(self):
        self.client.force_login(self.me)
        resp = self.client.post(self.url, data='{{{', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_아무것도_저장하지_않는다(self):
        """기록은 사람이 결과를 보고 확인을 눌렀을 때 design_compare_record 가 남긴다."""
        from v1.products.models import ProductDocument

        self.client.force_login(self.me)
        before = ProductDocument.objects.count()
        self._post({'prdlst_nm': {'mine': 'A', 'design': 'B'}})
        self.assertEqual(ProductDocument.objects.count(), before)

    def test_화면이_서버에_묻는다(self):
        """
        묻지 않고 제 안에서 판정하면 이 작업 전으로 되돌아간 것이다.
        화면에 남은 compareGrade 는 **서버가 답하지 않았을 때의 버팀목**이라
        그 자리에만 있어야 한다.
        """
        from pathlib import Path

        js = Path('v1/static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.assertIn("design-compare/grade/", js)
        self.assertIn('grades[field] ||', js)
        # 판정을 곧바로 쓰는 자리가 남아 있으면 안 된다
        self.assertNotIn('var grade = compareGrade(', js)


class 눌러도_아무_일이_없으면_안_된다(TestCase):
    """
    '처음이신가요?' 띠의 [보기] 가 안 눌렸다. button() 이 addEventListener 로
    매는 순간 **첫 인자는 클릭 이벤트**가 되는데, start(scope, from) 을 그대로
    넘겨서 scope 자리에 MouseEvent 가 들어갔다. holder(scope) 가 아무것도 못
    찾고 조용히 돌아서므로 **터지지도 않는다.** 그래서 오래 몰랐다.
    """

    def engine(self):
        from pathlib import Path
        return Path('v1/templates/includes/_coachmark.html').read_text(encoding='utf-8')

    def test_보기는_갈래를_적어_부른다(self):
        engine = self.engine()
        self.assertIn("start('detail');", engine)
        # 함수를 그대로 넘기면 이벤트가 첫 인자가 된다
        self.assertNotIn("button('보기', 'ezc-btn primary', start)", engine)

    def test_핸들러로_함수를_그대로_넘기지_않는다(self):
        """
        같은 사고가 날 수 있는 자리를 통째로 막는다. button(...) 의 세 번째
        인자는 **이름 없는 함수**이거나 인자를 안 받는 함수여야 한다.
        """
        import re

        engine = self.engine()
        bad = re.findall(r"button\([^,]+,[^,]+,\s*(start|go|place|draw)\s*\)", engine)
        self.assertEqual(bad, [], '인자를 받는 함수를 핸들러로 그대로 넘겼다: %s' % bad)


class 새_제품은_빈_양식으로_시작하지_않는다(TestCase):
    """
    [새로 만들기] 를 누르면 빈 칸 서른 개짜리 기본 정보 탭이 나왔다. 사람은
    빈 양식을 받으면 닫는다. 번호로 채우는 길과 사진으로 읽는 길이 **둘 다
    이미 있었는데 첫 화면에 안 보였을 뿐**이다.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='u@example.com', password='pw12345!')
        self.client.force_login(self.user)

    def test_새로_만들면_시작_방법을_먼저_묻는다(self):
        resp = self.client.get(reverse('products:product_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('start=1', resp['Location'])

    def test_사진으로_시작은_곧바로_사진_칸으로(self):
        """홈에서 '사진으로 시작' 을 누른 사람에게 다시 묻는 것은 군말이다."""
        resp = self.client.get(reverse('products:product_create') + '?import=1')
        self.assertIn('import=1', resp['Location'])
        self.assertNotIn('start=1', resp['Location'])

    def test_가두지_않는다(self):
        """번호도 사진도 없는 사람이 갇히면 그게 더 나쁘다."""
        from pathlib import Path

        js = Path('v1/static/js/products/import_modal.js').read_text(encoding='utf-8')
        self.assertIn('직접 입력하기', js)
        self.assertIn('import-start', js)
        self.assertIn("opts && opts.start", js)


class 손대지_않은_제품은_떠날_때_치운다(TestCase):
    """
    [새로 만들기] 는 그 순간 제품을 만든다. 열어만 보고 닫으면 빈 제품이
    목록에 남고, 쌓이면 제 목록이 쓰레기로 보인다. 배치가 30 일 뒤에 치웠는데
    그동안 보이는 것이 문제다.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        from v1.label.models import MyLabel
        from v1.label.services.temp_label import TEMP_PREFIX

        self.user = User.objects.create_user(username='u@example.com', password='pw12345!')
        self.other = User.objects.create_user(username='x@example.com', password='pw12345!')
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name=TEMP_PREFIX + '1', delete_YN='N')
        self.url = reverse('products:discard_if_untouched', args=[self.label.pk])

    def _refresh(self):
        from v1.label.models import MyLabel
        return MyLabel.objects.get(pk=self.label.pk)

    def test_빈_제품은_목록에서_사라진다(self):
        self.client.force_login(self.user)
        from v1.label.models import MyLabel

        resp = self.client.post(self.url)
        self.assertTrue(resp.json()['discarded'])
        self.assertFalse(MyLabel.objects.filter(pk=self.label.pk).exists())

    def test_정말로_지운다(self):
        """
        처음에는 숨기기만 했다(delete_YN='Y'). MyLabel 을 지우면 BOM·문서함·
        공유까지 CASCADE 로 함께 사라지기 때문이었다. 그런데 **여기서 지우는
        것은 그 조건을 이미 통과한 것들**이라 딸려 갈 것이 없다. 숨기기만
        하면 휴지통에 빈 제품이 쌓이는데, 열어만 보고 닫은 것을 되살릴 일은
        없다.
        """
        from v1.label.models import MyLabel

        self.client.force_login(self.user)
        self.client.post(self.url)
        self.assertFalse(MyLabel.objects.filter(pk=self.label.pk).exists())

    def test_한_글자라도_넣었으면_남긴다(self):
        self.client.force_login(self.user)
        self.label.prdlst_nm = '초코쿠키'
        self.label.save()
        self.assertFalse(self.client.post(self.url).json()['discarded'])
        self.assertEqual(self._refresh().delete_YN, 'N')

    def test_이름을_바꿨으면_남긴다(self):
        self.client.force_login(self.user)
        self.label.my_label_name = '내 제품'
        self.label.save()
        self.assertFalse(self.client.post(self.url).json()['discarded'])

    def test_BOM_에_원료가_있으면_남긴다(self):
        """표시사항 칸은 비었어도 배합을 붙여 넣었을 수 있다. 그건 손댄 것이다."""
        from v1.bom.models import ProductBOM

        self.client.force_login(self.user)
        ProductBOM.objects.create(parent_label=self.label)
        self.assertFalse(self.client.post(self.url).json()['discarded'])

    def test_남의_제품은_404(self):
        """403 은 그 id 가 있다고 알려 준다."""
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_GET_으로는_안_된다(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_배치와_같은_기준을_쓴다(self):
        """
        둘이 갈라지면 한쪽이 지운 것을 다른 쪽이 안 지우거나 그 반대가 된다.
        """
        from pathlib import Path

        cmd = Path('v1/label/management/commands/cleanup_temp_labels.py').read_text(
            encoding='utf-8')
        self.assertIn('from v1.label.services.temp_label import', cmd)
        self.assertNotIn('SKIP_FIELDS = {', cmd)      # 두 벌로 적지 않는다


class 번호로_찾으면_아는_것을_다_채운다(TestCase):
    """
    품목보고번호로 조회하면 다섯 칸만 채웠다. 그런데 FoodItem 은 소비기한·
    포장재질까지 들고 있다 — **식약처가 준 것을 우리가 안 쓰고 버린 것**이다.
    번호를 넣은 사람은 "이 번호로 아는 것은 다 채워 달라" 고 말한 것인데,
    다섯 칸만 채우면 나머지를 손으로 적게 된다.
    """

    def _item(self, **kw):
        from v1.label.models import FoodItem

        base = dict(prdlst_report_no='1971027500346', prdlst_nm='단팥빵',
                    prdlst_dcnm='빵류', bssh_nm='(주)샤니',
                    rawmtrl_nm='밀가루, 설탕, 팥앙금',
                    pog_daycnt='제조일로부터 3일', frmlc_mtrqlt='폴리프로필렌',
                    induty_cd_nm='식품제조가공업', prms_dt='19971027')
        base.update(kw)
        return FoodItem.objects.create(**base)

    def test_소비기한과_포장재질도_넘긴다(self):
        from v1.label.services import item_lookup

        f = item_lookup.as_fields(self._item())
        self.assertEqual(f['pog_daycnt'], '제조일로부터 3일')
        self.assertEqual(f['frmlc_mtrqlt'], '폴리프로필렌')

    def test_검증이_보는_칸도_함께_채운다(self):
        """
        food_type 이 비어 있으면 그 유형에만 있는 의무 표시사항 검사가 통째로
        빠진다. 통과한 것이 아니라 안 본 것이다.
        """
        from v1.label.services import item_lookup

        f = item_lookup.as_fields(self._item())
        self.assertEqual(f['food_type'], '빵류')

    def test_없는_것을_지어내지_않는다(self):
        from v1.label.services import item_lookup

        f = item_lookup.as_fields(self._item(pog_daycnt='', frmlc_mtrqlt=None))
        self.assertEqual(f['pog_daycnt'], '')
        self.assertEqual(f['frmlc_mtrqlt'], '')



class 고를_것이_하나뿐이면_묻지_않는다(TestCase):
    """
    새 제품 화면에서 품목을 고르는 것은 곧 "이 제품으로 하겠다" 는 뜻이다.
    그런데 고른 뒤에 사진 칸 아래의 '조회한 품목보고번호로 등록' 을 한 번 더
    눌러야 했다. 그 단추는 사진 칸에 붙어 있어 번호로 찾은 사람 눈에는 잘
    띄지도 않는다 — 다 골라 놓고 아무 일도 안 일어나는 것처럼 보인다.
    """

    def js(self):
        from pathlib import Path
        return Path('v1/static/js/products/import_modal.js').read_text(encoding='utf-8')

    def test_새_제품이면_고르는_즉시_등록한다(self):
        js = self.js()
        self.assertIn("if (startMode) {", js)
        self.assertIn("useLookup('product', modalEl)", js)

    def test_새_제품이면_원료_쪽을_감춘다(self):
        """고를 것이 하나뿐인데 고르라고 하면 오히려 뭘 눌러야 할지 모르게 된다."""
        js = self.js()
        self.assertIn("[data-side=\"ingredient\"]", js)
        self.assertIn("classList.toggle('d-none', startMode)", js)

    def test_원래_화면에서는_그대로_묻는다(self):
        """이미 만들던 제품에서 부른 경우에는 제품/원료를 골라야 한다."""
        js = self.js()
        self.assertIn('아래에서 제품으로 등록할지, 원료로 등록할지 고르세요', js)


class 뒤로_가기로_돌아와도_목록이_참말을_한다(TestCase):
    """
    손대지 않은 새 제품은 떠날 때 치워진다. 그런데 **뒤로 가기는 서버에 묻지
    않는다** — 브라우저가 떠나기 전 화면을 그대로 되살린다(bfcache). 그래서
    이미 치워진 제품이 목록에 남아 보였고 새로 고치면 사라졌다.
    """

    def test_되살린_화면은_다시_읽는다(self):
        from pathlib import Path

        html = Path('v1/templates/products/product_explorer.html').read_text(
            encoding='utf-8')
        self.assertIn("addEventListener('pageshow'", html)
        self.assertIn('ev.persisted', html)


class 탭을_옮겨도_도움말_단추가_남는다(TestCase):
    """
    '핵심기능 보기' 를 걷으면서 showNavButton() 껍데기를 지웠는데, **관찰자가
    부르는 자리 한 곳을 놓쳤다.** DOM 이 바뀔 때마다(탭 전환·iframe 로드)
    없는 함수를 불러 거기서 예외가 났고, 그래서 BOM 탭으로 옮기면 단추가
    사라졌다.
    """

    def test_없는_함수를_부르지_않는다(self):
        from pathlib import Path

        engine = Path('v1/templates/includes/_coachmark.html').read_text(encoding='utf-8')
        self.assertNotIn('showNavButton', engine)
        self.assertIn('setTimeout(mountFab, 120)', engine)


class 소분류를_넣으면_대분류도_함께_맞춘다(TestCase):
    """
    품목보고번호 조회와 사진 판독은 **소분류(식품유형) 하나만** 준다. 식약처가
    그것만 갖고 있기 때문이다. 그런데 이 화면의 소분류 목록은 **대분류로
    걸러져 있다.** 대분류가 다른 값으로 남아 있으면 그 소분류는 목록에 없어서
    조용히 지워지고, 대분류가 빈 채로 저장되면 사용자는 나중에 대분류를 고르는
    순간 제 소분류를 잃는다.
    """

    def _read(self, path):
        from pathlib import Path
        return Path(path).read_text(encoding='utf-8')

    def test_소분류에서_대분류를_거꾸로_찾는다(self):
        html = self._read('v1/templates/products/_tab_basic_info.html')
        self.assertIn('window.syncFoodGroupFromType', html)
        # 짝은 옵션의 data-group 이 이미 알고 있다
        self.assertIn('data-group="{{ ft.food_group }}"', html)

    def test_대분류를_먼저_바꾸고_소분류를_넣는다(self):
        """순서를 뒤집으면 목록이 다시 그려지면서 방금 넣은 값이 지워진다."""
        html = self._read('v1/templates/products/_tab_basic_info.html')
        block = html[html.index('window.syncFoodGroupFromType'):]
        block = block[:block.index('};')]
        self.assertLess(block.index('filterFoodTypes(opt.group)'),
                        block.index('_ftTypeSel.value = want'))

    def test_판독도_그_길을_탄다(self):
        js = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn('window.syncFoodGroupFromType(derived.food_type)', js)

    def test_조회도_그_길을_탄다(self):
        """
        조회는 사진을 읽지 않아 derived 가 없다. 소분류만이라도 흘려보내지
        않으면 칸에는 들어가도 대분류가 빈 채로 남는다.
        """
        js = self._read('v1/static/js/products/import_modal.js')
        self.assertIn('{food_type: lookupFields.food_type}', js)
        ocr = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn('function showModal(data, photoFile, apiMatch, snapInfo, derivedIn)', ocr)

    def test_표시용은_건드리지_않는다(self):
        """부기가 붙는 자리라, 덮으면 사람이 적어 둔 부기가 사라진다."""
        html = self._read('v1/templates/products/_tab_basic_info.html')
        block = html[html.index('window.syncFoodGroupFromType'):]
        block = block[:block.index('};')]
        self.assertNotIn('_ftPrdlstDcnm', block)


class 떠날_때_치우는_주소는_url_태그로_만든다(TestCase):
    """
    주소를 손으로 이어 붙였더니 변수명을 틀려도 템플릿이 **조용히 빈 문자열**을
    넣었다. 이 화면의 컨텍스트는 product 인데 label 로 적어서
    '/products//discard-if-untouched/' 가 나갔고, 그래서 뒤로 가기를 해도
    빈 제품이 그대로 남았다. 시험이 화면 문자열만 보고 실제 주소는 안 봐서
    놓쳤다.
    """

    def test_주소를_손으로_잇지_않는다(self):
        from pathlib import Path

        html = Path('v1/templates/products/product_detail.html').read_text(encoding='utf-8')
        self.assertIn("products:discard_if_untouched", html)
        self.assertNotIn("'/products/{{ label", html)

    def test_실제로_그_제품_번호가_들어간다(self):
        """렌더링해서 본다 — 문자열만 보면 빈 주소를 못 잡는다."""
        from django.contrib.auth.models import User

        from v1.label.models import MyLabel

        user = User.objects.create_user(username='u@example.com', password='pw12345!')
        label = MyLabel.objects.create(user_id=user, my_label_name='제품', delete_YN='N')
        self.client.force_login(user)

        resp = self.client.get(reverse('products:product_detail', args=[label.pk]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('PRODUCT_DISCARD_URL = "/products/%d/discard-if-untouched/"' % label.pk,
                      body)
        # 빈 주소가 실제로 나가지는 않는지. 주석에 적어 둔 예시 문자열과
        # 섞이지 않게 **정의문 그대로** 견준다 — 앞의 assertIn 과 짝이다.
        self.assertNotIn('PRODUCT_DISCARD_URL = "/products//', body)


class 정리_요청이_실제로_나간다(TestCase):
    """
    서버는 끝에서 끝까지 멀쩡했는데 빈 제품이 남았다. 화면이 요청을 **아예
    안 보내고 있었다** — CSRF 토큰을 [name=csrfmiddlewaretoken] 입력칸에서
    찾았는데 이 화면에는 그 칸이 늘 있는 것이 아니다. querySelector 가 null 을
    주고 그 자리에서 예외가 났으며, try/catch 가 그것을 조용히 삼켰다.

    조용히 실패하는 것이 가장 오래 간다. 그래서 시험은 **렌더링해서** 본다.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        from v1.label.models import MyLabel

        self.user = User.objects.create_user(username='u@example.com', password='pw12345!')
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='제품', delete_YN='N')
        self.client.force_login(self.user)

    def _body(self):
        resp = self.client.get(reverse('products:product_detail', args=[self.label.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def test_화면에_늘_있는_토큰을_쓴다(self):
        body = self._body()
        self.assertIn("fd.append('csrfmiddlewaretoken', CSRF_TOKEN)", body)
        self.assertNotIn("fd.append('csrfmiddlewaretoken', document.querySelector", body)

    def test_그_토큰이_실제로_값을_갖는다(self):
        import re

        body = self._body()
        m = re.search(r"const CSRF_TOKEN = '([^']*)'", body)
        self.assertIsNotNone(m, 'CSRF_TOKEN 정의를 못 찾았다')
        self.assertTrue(m.group(1), 'CSRF_TOKEN 이 비어 있다')


class 시안의_어디에서_읽었는지_보여_준다(TestCase):
    """
    대조는 "시안에 이렇게 적혀 있습니다" 라고 **단정**한다. 그런데 사용자가
    그 말을 확인할 길이 없으면 믿거나 말거나가 되고, 우리가 엉뚱한 칸을
    읽었어도 알 수 없다 — 그러면 멀쩡한 시안을 고치러 간다.

    좌표(ocr_boxes)는 처음부터 있었다. **대조에서 켜지 않았을 뿐이다.**
    """

    def _read(self, path):
        from pathlib import Path
        return Path(path).read_text(encoding='utf-8')

    def test_대조에서만_좌표를_켠다(self):
        """
        상자를 달라고 하면 프롬프트가 길어지고 응답도 커진다. 채우기는 사람이
        한 칸씩 보며 적용하므로 그 자리가 이미 확인 절차다.
        """
        src = self._read('v1/label/views.py')
        self.assertIn("boxes = (purpose == 'compare')", src)
        self.assertIn('want_boxes=boxes', src)

    def test_조각으로_올린_시안도_좌표를_받는다(self):
        """
        예전에는 한 장짜리 경로에만 want_boxes 가 있었다. 시안은 면을 나눠
        올리는 일이 흔하다.
        """
        src = self._read('v1/label/services/ocr_service.py')
        head = src.index('def extract_label_from_parts')
        block = src[head:src.index('def extract_label_from_image')]
        self.assertIn('want_boxes=False', block)
        self.assertIn('PROMPT_ADDENDUM', block)
        self.assertIn('attach(result, regions)', block)

    def test_사진_뷰어에_상자를_겹치지_않는다(self):
        """
        뷰어는 확대·회전 변환이 걸려 있다. 좌표를 따라가려면 그 변환을
        뒤집어야 하는데, 계산이 틀리면 **맞는 값에 틀린 상자**가 된다 —
        없느니만 못하다. 원본에서 잘라 내는 쪽은 계산이 한 번뿐이다.
        """
        js = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn('function cropBox', js)
        self.assertIn('drawImage(whereImage', js)

    def test_상자가_있는_줄에만_단추가_붙는다(self):
        """못 잡은 자리에 '어디서?' 를 달면 눌러도 아무 일이 없다."""
        js = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn("(box ? '<button type=\"button\" class=\"cmp-where\"", js)

    def test_읽히는_크기로_키운다(self):
        """6pt 글자를 원본 크기로 보면 못 읽는다. 확인하라고 보여 주는 것이다."""
        js = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn('420 / (x2 - x1)', js)

    def test_어느_면에서_읽었는지도_말한다(self):
        js = self._read('v1/static/js/products/basic_info_ocr.js')
        self.assertIn('item.box_from', js)


class 성적서는_어디서_넣느냐에_따라_다른_곳에_붙는다(TestCase):
    """
    문서함은 **제품에 딸린다**(ProductDocument.label). 거기 올라온 성적서는
    대개 완제품을 시험한 것이라 배합으로 계산할 것이 없다 — 시험한 값이
    계산한 값을 이긴다.

    원료 성적서는 다르다. 원료는 여러 제품이 함께 쓰는 것이라 한 제품의
    문서함에 매다는 것이 맞지 않고, **그 원료를 쓰는 다른 제품에서는 안 보인다.**
    그래서 원료 쪽은 값만 받고 파일을 남기지 않는다.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        from v1.label.models import MyIngredient, MyLabel
        from v1.products.models import DocumentType, ProductDocument

        self.me = User.objects.create_user(username='me@example.com', password='pw12345!')
        self.other = User.objects.create_user(username='you@example.com', password='pw12345!')
        self.label = MyLabel.objects.create(
            user_id=self.me, my_label_name='제품', delete_YN='N')
        dt, _ = DocumentType.objects.get_or_create(
            type_code='SPEC', defaults={'type_name': '영양성분 성적서'})
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dt, original_filename='성적서.jpg')
        self.ing = MyIngredient.objects.create(
            user_id=self.me, prdlst_nm='밀가루', delete_YN='N')
        self.client.force_login(self.me)

    VALUES = {'calories': 380, 'natriums': 420, 'proteins': 8.1}

    # ── 제품 쪽 ────────────────────────────────────────────────────────
    def test_문서함_성적서는_제품_영양성분이_된다(self):
        from v1.label.models import MyLabel

        resp = self.client.post(
            reverse('products:document_spec_nutrition_save', args=[self.doc.pk]),
            data=json.dumps({'values': self.VALUES}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertEqual(str(label.calories), '380')
        self.assertEqual(str(label.natriums), '420')

    def test_성적서에_없는_칸은_지우지_않는다(self):
        """모르는 것과 없는 것은 다르다. 빈 값으로 덮으면 있던 값을 잃는다."""
        from v1.label.models import MyLabel

        MyLabel.objects.filter(pk=self.label.pk).update(sugars='12')
        self.client.post(
            reverse('products:document_spec_nutrition_save', args=[self.doc.pk]),
            data=json.dumps({'values': {'calories': 380}}),
            content_type='application/json')
        self.assertEqual(MyLabel.objects.get(pk=self.label.pk).sugars, '12')

    def test_제품_값은_배합_계산을_거치지_않는다(self):
        """
        산출하는 길과 섞이면 어느 값이 표시되는지 알 수 없게 된다.
        """
        from pathlib import Path

        src = Path('v1/products/views.py').read_text(encoding='utf-8')
        block = src[src.index('def document_spec_nutrition_save'):]
        block = block[:block.index('def ingredient_spec_nutrition')]
        self.assertIn('계산을 거치지 않는다', block)
        self.assertNotIn('nutrition_calc', block)

    # ── 원료 쪽 ────────────────────────────────────────────────────────
    def test_원료_성적서는_파일을_남기지_않는다(self):
        from v1.label.models import MyIngredientNutrition

        resp = self.client.post(
            reverse('label:ingredient_spec_nutrition_save', args=[self.ing.pk]),
            data=json.dumps({'values': self.VALUES, 'filename': '밀가루성적서.jpg'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        nut = MyIngredientNutrition.objects.get(ingredient=self.ing)
        self.assertEqual(nut.source_kind, MyIngredientNutrition.SOURCE_SPEC_OCR)
        self.assertIsNone(nut.source_document)          # 파일을 안 남긴다
        self.assertIn('밀가루성적서.jpg', nut.source_note)   # 무엇을 봤는지는 남는다

    def test_사람이_승인한_것으로_남는다(self):
        """자동 판단이 아니다. 등급 A 는 사람이 봤다는 뜻이기도 하다."""
        from v1.label.models import MyIngredientNutrition

        self.client.post(
            reverse('label:ingredient_spec_nutrition_save', args=[self.ing.pk]),
            data=json.dumps({'values': self.VALUES}), content_type='application/json')
        nut = MyIngredientNutrition.objects.get(ingredient=self.ing)
        self.assertEqual(nut.picked_by, self.me)

    def test_남의_원료에는_못_붙인다(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            reverse('label:ingredient_spec_nutrition_save', args=[self.ing.pk]),
            data=json.dumps({'values': self.VALUES}), content_type='application/json')
        self.assertEqual(resp.status_code, 404)      # 403 은 그 id 가 있다고 알려 준다

    def test_남의_문서에는_못_붙인다(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            reverse('products:document_spec_nutrition_save', args=[self.doc.pk]),
            data=json.dumps({'values': self.VALUES}), content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_값이_하나도_없으면_저장하지_않는다(self):
        resp = self.client.post(
            reverse('label:ingredient_spec_nutrition_save', args=[self.ing.pk]),
            data=json.dumps({'values': {}}), content_type='application/json')
        self.assertEqual(resp.status_code, 400)


class 스타일은_마크업보다_먼저_온다(TestCase):
    """
    캐시를 비우고 기본 정보 탭에 들어가면 **알레르기 패널만** 잠깐 맨몸으로
    보였다가 정상으로 돌아왔다. 그 규칙 176 줄이 **패널 마크업 뒤에** 있었기
    때문이다 — 브라우저는 위에서 아래로 읽으며 그리므로 규칙을 만나기 전에
    이미 한 번 그린다.

    화면의 다른 곳이 멀쩡했던 까닭은 나머지 규칙이 전부 마크업보다 앞에
    있었기 때문이다. 그 패널만 예외였다.
    """

    def tpl(self):
        from pathlib import Path
        return Path('v1/templates/products/_tab_basic_info.html').read_text(
            encoding='utf-8')

    def test_스타일_블록이_마크업_뒤에_있지_않다(self):
        html = self.tpl()
        last_style = html.rindex('<style>')
        first_markup = html.index('<div')
        self.assertLess(last_style, first_markup,
                        '마크업 뒤에 <style> 이 있다 — 그 부분만 맨몸으로 그려진다')

    def test_알레르기_패널_규칙이_남아_있다(self):
        """옮기면서 잃으면 안 된다."""
        html = self.tpl()
        self.assertIn('.allergen-panel-root', html)
        self.assertIn('.allergen-panel-header', html)


class 어디서_단추는_대조_창에서만_듣는다(TestCase):
    """
    단추는 보이는데 눌러도 아무 일이 없었다. 클릭을 받는 코드를 **채우기
    창(showModal)** 에 붙였기 때문이다 — 거기에는 대조 줄(cmp-row)이 없다.
    듣는 사람이 없는 단추였다.
    """

    def js(self):
        from pathlib import Path
        return Path('v1/static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')

    def test_대조_함수_안에서_듣는다(self):
        js = self.js()
        block = js[js.index('function drawCompare'):]
        block = block[:block.index(chr(10) + '  }')]
        self.assertIn("closest('[data-where]')", block)
        self.assertIn('loadWhereImage(photoFile)', block)

    def test_채우기_창에서는_듣지_않는다(self):
        js = self.js()
        block = js[js.index('function showModal'):js.index('function drawCompare')]
        self.assertNotIn("closest('[data-where]')", block)

    def test_한_번만_맨다(self):
        """표는 매번 다시 그려진다. 줄마다 매면 다시 그릴 때 다 끊긴다."""
        self.assertIn('body.dataset.whereBound', self.js())


class 원_표시사항에_없는_문구를_모아_보여_준다(TestCase):
    """
    인쇄물에는 우리가 칸을 두지 않은 문구가 얹힌다 — 수상 내역, 이벤트 안내,
    다른 제품에서 복사해 온 문장. **근거 없이 인쇄되는 것이 위험하다.**

    판독 결과만 봐서는 못 찾는다. 거기에는 **우리가 칸을 둔 것**만 들어 있고
    칸이 없는 문구는 애초에 담기지 않는다. 그래서 OCR 원문을 본다.
    """

    def test_원문을_화면까지_보낸다(self):
        from pathlib import Path

        src = Path('v1/label/services/ocr_service.py').read_text(encoding='utf-8')
        self.assertEqual(src.count("out['ocr_text']"), 2)   # 두 경로 모두

    def test_대조에서만_온다(self):
        """채우기 응답이 무거워질 이유가 없다."""
        from pathlib import Path

        src = Path('v1/label/services/ocr_service.py').read_text(encoding='utf-8')
        at = src.index("out['ocr_text']")
        before = src[:at]
        self.assertIn('if ground_report:', before[-400:])

    def test_원문에서_짝_없는_줄을_모은다(self):
        from pathlib import Path

        js = Path('v1/static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.assertIn('function groundlessFromText', js)
        self.assertIn('lastOcrText', js)

    def test_틀렸다고_말하지_않는다(self):
        """우리가 칸을 안 둔 정당한 표시일 수 있다(인증 마크, 바코드 아래 안내)."""
        from pathlib import Path

        js = Path('v1/static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.assertIn('원 표시사항에 없는 문구가 확인되었습니다', js)
        self.assertIn('근거가 있는 표시인지', js)

    def test_너무_많이_늘어놓지_않는다(self):
        """짚어 주는 것이 목적이지 나열이 아니다."""
        from pathlib import Path

        js = Path('v1/static/js/products/basic_info_ocr.js').read_text(encoding='utf-8')
        self.assertIn('GROUNDLESS_MAX', js)
        self.assertIn('GROUNDLESS_MIN', js)


# ─────────────────────────────────────────────────────────────────────────────
# 권한 설정 · 공동 작업 · 연락처 관리
#
# 이 세 화면은 "누가 무엇을 볼 수 있는가" 를 정하는 자리인데, 시험이 모델
# 헬퍼(media_access)까지만 닿아 있었고 HTTP 문 앞은 비어 있었다. 그 틈에서
# 여덟 건이 나왔다. 여기 있는 것은 전부 실제로 재현됐던 것들이다.
# ─────────────────────────────────────────────────────────────────────────────

class SharingWorkspaceBase(TestCase):
    def setUp(self):
        from django.core.files.base import ContentFile
        from v1.products.models import DocumentType, ProductDocument

        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.sup = User.objects.create_user('협력사', password='x', email='sup@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.mine = ProductDocument.objects.create(
            label=self.label, document_type=dtype,
            file=ContentFile(b'mine', name='a.pdf'),
            original_filename='내가올린것.pdf', uploaded_by=self.sup)
        self.theirs = ProductDocument.objects.create(
            label=self.label, document_type=dtype,
            file=ContentFile(b'secret', name='b.pdf'),
            original_filename='남의규격서.pdf', uploaded_by=self.owner)

    def share(self, role, user=None, email=None):
        u = user if user is not None else self.sup
        s = ProductShare.objects.create(
            label=self.label, recipient_email=email or u.email,
            recipient_user=u, share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        p = SharePermission.objects.create(share=s)
        p.apply_role_defaults(role_code=role, save=True)
        return s, p


class BulkDownloadRespectsDocumentScopeTests(SharingWorkspaceBase):
    """
    단건 내려받기는 문서까지 넘겨 검사했는데 일괄받기는 제품만 확인했다.
    문서함 전체 보기가 통째로 무시돼, 협력업체가 document_id 만 찍어 넣으면
    남의 규격서를 ZIP 으로 받아 갔다. 목록에는 안 보이지만 ID 는 연속된 정수다.
    """

    def _zip_names(self, response):
        import io
        import zipfile
        return zipfile.ZipFile(io.BytesIO(response.content)).namelist()

    def test_자료_제출자는_자기_것만_받는다(self):
        self.share('UPLOADER')
        self.client.force_login(self.sup)
        r = self.client.post(reverse('products:bulk_download'), {
            'document_ids': '%s,%s' % (self.mine.document_id, self.theirs.document_id),
            'organize_by': 'flat'})
        self.assertEqual(r.status_code, 200)
        joined = ' '.join(self._zip_names(r))
        self.assertIn('내가올린것.pdf', joined)
        self.assertNotIn('남의규격서.pdf', joined)

    def test_내부_팀은_전부_받는다(self):
        self.share('REVIEWER')
        self.client.force_login(self.sup)
        r = self.client.post(reverse('products:bulk_download'), {
            'document_ids': '%s,%s' % (self.mine.document_id, self.theirs.document_id),
            'organize_by': 'flat'})
        self.assertEqual(len(self._zip_names(r)), 2)

    def test_주인은_전부_받는다(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse('products:bulk_download'), {
            'document_ids': '%s,%s' % (self.mine.document_id, self.theirs.document_id),
            'organize_by': 'flat'})
        self.assertEqual(len(self._zip_names(r)), 2)

    def test_남은_아무것도_못_받는다(self):
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        self.client.force_login(stranger)
        r = self.client.post(reverse('products:bulk_download'), {
            'document_ids': str(self.theirs.document_id), 'organize_by': 'flat'})
        self.assertEqual(r.status_code, 404)


class SeeAllSurvivesRoleChangeTests(SharingWorkspaceBase):
    """
    소유자가 "이 사람은 외부인이니 문서함 전체는 안 된다" 고 끈 것은 역할이
    아니라 **사람**에 대한 판단이다. 역할만 옮겼다고 그것이 풀려서는 안 된다.
    예전에는 끌어다 놓기 한 번에 조용히 도로 켜졌고 화면에 표시도 없었다.
    """

    def _move(self, share, role, **extra):
        payload = {'role': role}
        payload.update(extra)
        return self.client.post(
            reverse('products:share_update_permission', args=[share.share_id]), payload)

    def test_꺼_둔_것은_역할을_옮겨도_꺼져_있다(self):
        s, p = self.share('VIEWER')
        p.can_view_all_documents = False
        p.save()
        self.client.force_login(self.owner)
        self._move(s, 'REVIEWER')
        p.refresh_from_db()
        self.assertFalse(p.can_view_all_documents)

    def test_좁아지는_쪽은_역할_기본값을_따른다(self):
        s, p = self.share('REVIEWER')
        self.assertTrue(p.can_view_all_documents)
        self.client.force_login(self.owner)
        self._move(s, 'UPLOADER')
        p.refresh_from_db()
        self.assertFalse(p.can_view_all_documents)

    def test_손으로_켜면_켜진다(self):
        s, p = self.share('UPLOADER')
        self.client.force_login(self.owner)
        self._move(s, 'UPLOADER', see_all_documents='true')
        p.refresh_from_db()
        self.assertTrue(p.can_view_all_documents)

    def test_결과를_응답에_실어_화면이_알_수_있게_한다(self):
        s, p = self.share('REVIEWER')
        self.client.force_login(self.owner)
        body = self._move(s, 'UPLOADER').json()
        self.assertFalse(body['see_all_documents'])
        self.assertTrue(body['see_all_changed'])


class OnlyOwnerGrantsHighRolesTests(SharingWorkspaceBase):
    """
    역할 변경 문은 "자신의 권한은 변경할 수 없습니다" 로 자기 승격을 막았는데,
    공유를 새로 만드는 문에는 역할 제한이 없었다. 공동 편집자가 자기 다른
    이메일을 승인자로 초대하면 그대로 우회됐다.
    """

    def setUp(self):
        super().setUp()
        self.share('EDITOR')
        self.client.force_login(self.sup)

    def _invite(self, role, email='buddy@x.com'):
        return self.client.post(
            reverse('products:share_create', args=[self.label.my_label_id]),
            {'email': email, 'role': role, 'share_mode': 'PRIVATE'})

    def test_공동편집자는_승인자를_만들_수_없다(self):
        self.assertEqual(self._invite('APPROVER').status_code, 403)
        self.assertFalse(ProductShare.objects.filter(recipient_email='buddy@x.com').exists())

    def test_공동편집자는_공동편집자를_만들_수_없다(self):
        self.assertEqual(self._invite('EDITOR').status_code, 403)

    def test_공동편집자도_검토자까지는_부를_수_있다(self):
        for role in ('VIEWER', 'UPLOADER', 'REVIEWER'):
            r = self._invite(role, email='%s@x.com' % role.lower())
            self.assertEqual(r.status_code, 200, role)

    def test_주인은_승인자를_만들_수_있다(self):
        self.client.force_login(self.owner)
        self.assertEqual(self._invite('APPROVER').status_code, 200)

    def test_기존_공유를_승인자로_올리는_것도_막는다(self):
        target, _ = self.share('VIEWER', email='third@x.com', user=None)
        r = self.client.post(
            reverse('products:share_update_permission', args=[target.share_id]),
            {'role': 'APPROVER'})
        self.assertEqual(r.status_code, 403)


class CommentsFollowPermissionFlagsTests(SharingWorkspaceBase):
    """
    댓글 작성은 역할 이름을 하드코딩해 검사했고 그 목록에 자료 제출이 들어
    있었다 — ROLE_DEFAULTS 는 can_comment=False 인데 서버가 뒤집고 있었다.
    목록 쪽은 아예 거르지 않아 내부 검토 댓글이 협력사에게 그대로 보였다.
    """

    def setUp(self):
        super().setUp()
        from v1.products.models import ProductComment
        self.Comment = ProductComment
        self.internal = ProductComment.objects.create(
            label=self.label, author=self.owner,
            content='A사 성적서 수치가 이상함. 거래 끊는 것 검토')

    def test_자료_제출자는_댓글을_못_단다(self):
        self.share('UPLOADER')
        self.client.force_login(self.sup)
        r = self.client.post(
            reverse('products:comment_create', args=[self.label.my_label_id]),
            {'content': '외부인이 남기는 글'})
        self.assertEqual(r.status_code, 403)

    def test_검토자는_댓글을_단다(self):
        self.share('REVIEWER')
        self.client.force_login(self.sup)
        r = self.client.post(
            reverse('products:comment_create', args=[self.label.my_label_id]),
            {'content': '이 값 확인 부탁드립니다'})
        self.assertEqual(r.status_code, 200)

    def test_자료_제출자에게_내부_검토_댓글은_안_보인다(self):
        self.share('UPLOADER')
        self.client.force_login(self.sup)
        r = self.client.get(
            reverse('products:comment_list', args=[self.label.my_label_id]))
        self.assertEqual([c['content'] for c in r.json()['comments']], [])

    def test_자기_글에_달린_답글은_보인다(self):
        s, p = self.share('UPLOADER')
        p.can_comment = True          # 소유자가 손으로 열어 준 경우
        p.save()
        mine = self.Comment.objects.create(
            label=self.label, author=self.sup, content='성적서 올렸습니다')
        self.Comment.objects.create(
            label=self.label, author=self.owner, parent=mine, content='확인했습니다')
        self.client.force_login(self.sup)
        r = self.client.get(
            reverse('products:comment_list', args=[self.label.my_label_id]))
        got = sorted(c['content'] for c in r.json()['comments'])
        self.assertEqual(got, ['성적서 올렸습니다', '확인했습니다'])

    def test_내부_팀은_전부_본다(self):
        self.share('REVIEWER')
        self.client.force_login(self.sup)
        r = self.client.get(
            reverse('products:comment_list', args=[self.label.my_label_id]))
        self.assertEqual(len(r.json()['comments']), 1)


class ContactEmailChangeTransfersAccessTests(SharingWorkspaceBase):
    """
    담당자가 바뀌어 연락처 이메일을 고치는 것은 흔한 일이다. 그런데
    recipient_email 만 바꾸고 recipient_user 는 그대로 뒀다. 공유 조회가
    recipient_user 또는 recipient_email 로 찾기 때문에 접근이 **옮겨 가는 게
    아니라 복제됐다** — 전임자는 계속 받고, 고친 사람은 끊긴 줄 안다.
    """

    def _rename(self, old, new, **extra):
        payload = {'old_email': old, 'email': new}
        payload.update(extra)
        return self.client.post(reverse('products:contacts_api_update'), payload)

    def test_전임자_접근이_끊긴다(self):
        from v1.common.media_access import user_can_download_label_files
        self.share('EDITOR')
        self.client.force_login(self.owner)
        self._rename('sup@x.com', 'newguy@x.com', name='새담당')
        self.assertFalse(
            user_can_download_label_files(self.sup, self.label, self.theirs))

    def test_새_담당자가_회원이면_계정으로_다시_잇는다(self):
        newbie = User.objects.create_user('새담당', password='x', email='newguy@x.com')
        self.share('EDITOR')
        self.client.force_login(self.owner)
        self._rename('sup@x.com', 'newguy@x.com')
        self.assertEqual(ProductShare.objects.get(label=self.label).recipient_user, newbie)

    def test_회원이_아니면_계정을_끊어_둔다(self):
        self.share('EDITOR')
        self.client.force_login(self.owner)
        self._rename('sup@x.com', 'nobody@x.com')
        self.assertIsNone(ProductShare.objects.get(label=self.label).recipient_user)

    def test_이미_있는_연락처로_합쳐도_터지지_않는다(self):
        from v1.products.models import UserContact
        UserContact.objects.create(owner=self.owner, email='sup@x.com', name='구담당')
        UserContact.objects.create(owner=self.owner, email='dup@x.com', name='중복')
        self.client.force_login(self.owner)
        r = self._rename('sup@x.com', 'dup@x.com', name='합침')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            UserContact.objects.filter(owner=self.owner, email='dup@x.com').count(), 1)
        self.assertFalse(
            UserContact.objects.filter(owner=self.owner, email='sup@x.com').exists())


class ContactMemoSurvivesTests(SharingWorkspaceBase):
    """
    비고는 0008 로 막 넣은 칸인데, 목록 API 가 공유에서 온 행에는 memo 키를
    아예 담지 않았다. 한 번이라도 공유한 연락처는 비고가 빈 칸으로 내려갔고,
    화면이 그 행을 그대로 되돌려 보내면서 적어 둔 비고를 지웠다.
    """

    def setUp(self):
        super().setUp()
        from v1.products.models import UserContact
        self.UserContact = UserContact
        UserContact.objects.create(owner=self.owner, email='sup@x.com',
                                   name='협력사', memo='전화 010-1234, 담당 김대리')
        self.share('UPLOADER')
        self.client.force_login(self.owner)

    def _row(self):
        return self.client.get(reverse('products:contacts_api_list')).json()['contacts'][0]

    def _page_row(self):
        """화면이 실제로 쓰는 것은 API 가 아니라 서버가 렌더한 초기 데이터다."""
        ctx = self.client.get(reverse('products:contacts')).context['contacts_list']
        return ctx[0]

    def test_공유_이력이_있어도_비고가_목록에_실린다(self):
        self.assertEqual(self._row()['memo'], '전화 010-1234, 담당 김대리')

    def test_화면이_받는_초기_데이터에도_비고가_있다(self):
        # 한때 API 쪽만 고쳐 두고 화면 경로에는 같은 버그가 남아 있었다.
        self.assertEqual(self._page_row()['memo'], '전화 010-1234, 담당 김대리')

    def test_화면과_API_가_같은_것을_준다(self):
        page = {k: v for k, v in self._page_row().items()}
        api = self._row()
        for key in ('email', 'name', 'company', 'license_no', 'memo',
                    'doc_sent', 'doc_pending', 'doc_overdue', 'doc_received'):
            self.assertEqual(page.get(key), api.get(key), key)

    def test_회사명만_고쳐도_비고가_살아남는다(self):
        row = self._row()
        self.client.post(reverse('products:contacts_api_update'), {
            'old_email': row['email'], 'email': row['email'], 'name': row['name'],
            'company': '새회사', 'license_no': row['license_no'], 'memo': row['memo']})
        uc = self.UserContact.objects.get(owner=self.owner, email='sup@x.com')
        self.assertEqual(uc.memo, '전화 010-1234, 담당 김대리')
        self.assertEqual(uc.company, '새회사')

    def test_손으로_비우면_지워진다(self):
        self.client.post(reverse('products:contacts_api_update'), {
            'old_email': 'sup@x.com', 'email': 'sup@x.com', 'memo': ''})
        self.assertIsNone(
            self.UserContact.objects.get(owner=self.owner, email='sup@x.com').memo)


class UploaderCanRemoveOwnUploadTests(SharingWorkspaceBase):
    """
    올릴 권한은 줬는데 취소할 권한이 없었다. 협력사가 잘못 올렸다고 연락하면
    소유자가 대신 지워 줘야 했다.
    """

    def _delete(self, doc):
        return self.client.post(
            reverse('products:document_delete_api', args=[doc.document_id]))

    def test_자기가_올린_것은_지운다(self):
        self.share('UPLOADER')
        self.client.force_login(self.sup)
        self.assertEqual(self._delete(self.mine).status_code, 200)
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.active_yn)

    def test_남이_올린_것은_못_지운다(self):
        self.share('UPLOADER')
        self.client.force_login(self.sup)
        self.assertEqual(self._delete(self.theirs).status_code, 403)
        self.theirs.refresh_from_db()
        self.assertTrue(self.theirs.active_yn)

    def test_올릴_권한이_없으면_못_지운다(self):
        self.share('VIEWER')
        self.client.force_login(self.sup)
        self.assertEqual(self._delete(self.mine).status_code, 403)

    def test_주인은_남이_올린_것도_지운다(self):
        self.client.force_login(self.owner)
        self.assertEqual(self._delete(self.mine).status_code, 200)


class TemplateColoursComeFromTokensTests(TestCase):
    """
    토큰 규율이 **템플릿 문턱에서 멈춰 있었다.**

    ColoursComeFromTokensTests 는 static/css/*.css 만 본다. 그런데 이 앱은
    화면 스타일의 상당 부분을 템플릿 안 <style> 블록에 두고 있어서, CSS 에서
    금지한 하드코딩이 템플릿에서는 그대로 통과했다 — 권한 설정 11개, 문서함
    9개, 자료요청 12개. 색 하나 바꾸려면 여전히 여러 곳을 고쳐야 했다.
    """

    #  인라인 style= 속성은 아직 세지 않는다. 연락처 한 화면에만 77곳이 있고,
    #  그것은 값이 아니라 **구조**를 옮기는 일이라 따로 봐야 한다.
    GUARDED = [
        'templates/products/_tab_permissions.html',
        'templates/products/_tab_documents.html',
        'templates/products/doc_requests.html',
    ]

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)
        self.tokens = {
            v.lower(): k for k, v in re.findall(
                r'(--ez-[\w-]+):\s*(#[0-9a-fA-F]{3,6})',
                (self.base / 'static' / 'css' / 'variables.css').read_text(encoding='utf-8'))}

    def _bare_in_style_blocks(self, rel):
        import re
        text = (self.base / rel).read_text(encoding='utf-8')
        found = set()
        for block in re.findall(r'<style[^>]*>.*?</style>', text, re.S):
            stripped = re.sub(r'var\([^()]*\)', '', block)
            found |= {c.lower() for c in re.findall(r'#[0-9a-fA-F]{6}', stripped)}
        return found

    def test_토큰이_있는_색은_템플릿에서도_토큰으로_적는다(self):
        offenders = []
        for rel in self.GUARDED:
            hits = sorted(self._bare_in_style_blocks(rel) & set(self.tokens))
            if hits:
                offenders.append('%s: %s' % (rel.split('/')[-1], ', '.join(hits)))
        self.assertEqual(offenders, [], '토큰이 있는데 <style> 안에 직접 적었다')


class PaleBackgroundTextIsReadableTests(TestCase):
    """
    variables.css 가 재서 적어 둔 것 — "#1a73e8 은 옅은 파랑 바탕 위에서 대비가
    모자란다". 그래서 --ez-info-on-bg(#1967d2)를 따로 뒀는데, 정작 옅은 바탕
    칩을 그리는 자리들이 #1a73e8 을 그대로 쓰고 있었다.
    """

    RISKY = {
        '#1a73e8': '--ez-info-on-bg',
        '#1e8e3e': '--ez-success-on-bg',
        '#e67700': '--ez-warning-on-bg',
    }
    SCREENS = [
        'templates/products/contacts.html',
        'templates/products/doc_requests.html',
        'templates/products/_tab_permissions.html',
    ]

    def test_옅은_바탕_위_글자색은_on_bg_토큰을_쓴다(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj

        offenders = []
        for rel in self.SCREENS:
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            for chunk in re.findall(r'[^;{}"\']*background[^;{}"\']*[;\s][^{}"\']*', text):
                for bad, token in self.RISKY.items():
                    if bad in chunk and re.search(r'color\s*:\s*%s' % bad, chunk):
                        offenders.append('%s: %s → var(%s)'
                                         % (rel.split('/')[-1], bad, token))
        self.assertEqual(sorted(set(offenders)), [])


class OneWayToTellTheUserTests(TestCase):
    """
    같은 제품 관리 안에서 저장 결과를 알리는 방식이 둘로 갈려 있었다 —
    권한 설정은 스낵바 19번, 연락처는 브라우저 alert() 14번. alert 은 화면을
    멈춰 세우고, 생김새가 브라우저마다 다르고, 여러 건을 잇달아 알릴 수 없다.

    showSnackbar 는 base_v2.html 이 전역으로 띄워 두므로 연락처도 이미 쓸 수
    있었다 — 안 쓰고 있었을 뿐이다.
    """

    #  전역 스낵바(base_v2.html)가 닿는 화면들. 여기서 alert 이 다시 나오면 실패한다.
    SCREENS = [
        'templates/products/contacts.html',
        'templates/products/_tab_permissions.html',
        'templates/products/_tab_documents.html',
        'templates/products/doc_requests.html',
        'templates/products/_tab_basic_info.html',
        'templates/products/_bom_nutrition_summary.html',
        'templates/products/_nutrition_from_bom.html',
        'templates/products/document_ai_review_v2.html',
        'templates/label/_ingredient_nutrition.html',
        'templates/label/my_ingredient_list_combined.html',
        'templates/regulatory/news_list.html',
        'templates/user_management/user_profile.html',
    ]

    #  아직 alert 을 쓰는 곳 — **전역 스낵바가 닿지 않는 화면들이다.**
    #  base.html(V1) 을 타거나 단독으로 뜨는 문서라 window.showSnackbar 가 없다.
    #  옮기려면 그 화면들을 V2 로 올리거나 스낵바를 따로 실어야 하므로, 색을
    #  바꾸는 일과 성격이 다르다. 목록으로 남겨 두어 늘어나는지를 지켜본다.
    SNACKBAR_OUT_OF_REACH = {
        'templates/includes/navbar.html',
        'templates/includes/navbar_v1.html',
        'templates/label/food_additive_search_v1.html',
        'templates/label/label_preview.html',
    }

    def test_스낵바가_안_닿는_화면이_늘지_않았다(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj

        root = Path(dj.BASE_DIR) / 'templates'
        using = set()
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            # 주석 안의 언급은 세지 않는다
            code = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
            if re.search(r'(?<![\w.])alert\s*\(', code):
                using.add('templates/' + str(path.relative_to(root)).replace(chr(92), '/'))
        self.assertEqual(using - self.SNACKBAR_OUT_OF_REACH, set(),
                         'showSnackbar 를 쓰거나, 왜 못 쓰는지 명부에 적으세요')

    def test_알림은_alert_이_아니라_스낵바로_한다(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj

        offenders = []
        for rel in self.SCREENS:
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            hits = len(re.findall(r'(?<![\w.])alert\s*\(', text))
            if hits:
                offenders.append('%s: alert() %d곳' % (rel.split('/')[-1], hits))
        self.assertEqual(offenders, [], 'showSnackbar 를 쓰세요 (base_v2.html 전역)')

    #  base_v2.html 을 타지 않는 독립 페이지만 제 사본을 가질 수 있다.
    #  nutrition_editor 는 iframe 으로 뜨므로 여기 해당한다.
    STANDALONE = {'products/nutrition_editor.html'}

    def _definers(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj

        root = Path(dj.BASE_DIR) / 'templates'
        return sorted(
            str(p.relative_to(root)).replace(chr(92), '/')
            for p in root.rglob('*.html')
            if re.search(r'window\.showSnackbar\s*=', p.read_text(encoding='utf-8')))

    def test_스낵바를_다시_정의하는_것은_독립_페이지뿐이다(self):
        extra = set(self._definers()) - {'base_v2.html'} - self.STANDALONE
        self.assertEqual(extra, set(),
                         'base_v2.html 을 타는 화면은 전역 스낵바를 쓰세요')

    def test_사본은_본판과_같은_종류를_안다(self):
        """
        사본이 낡아 'info' 를 모르면, info 로 부른 알림이 성공처럼 보인다.
        실제로 nutrition_editor 사본이 그랬다.
        """
        from pathlib import Path
        from django.conf import settings as dj

        root = Path(dj.BASE_DIR) / 'templates'
        for rel in self._definers():
            text = (root / rel).read_text(encoding='utf-8')
            for kind in ('snack-error', 'snack-warning', 'snack-info'):
                self.assertIn(kind, text, '%s 가 %s 를 모른다' % (rel, kind))


# ─────────────────────────────────────────────────────────────────────────────
# 넘겨받는 자리 — 상태 전이 · 반려 · 기한 · 초대 착지점
#
# 기능은 갖춰져 있었는데 **사람이 넘겨받는 지점**에서 끊겼다. 부르기만 하고
# 문이 잠겨 있거나, 문구로만 약속하고 길이 없거나, 적히기만 하고 아무 일도
# 안 하거나. 아래는 전부 실제로 그랬던 것들이다.
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowHandoffBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.reviewer = User.objects.create_user('검토자', password='x', email='rv@x.com')
        self.approver = User.objects.create_user('승인자', password='x', email='ap@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        self.meta = ProductMetadata.objects.create(
            label=self.label, product_code='PRD-T-1',
            status=ProductMetadata.Status.DRAFT)
        self._share('REVIEWER', self.reviewer)
        self._share('APPROVER', self.approver)

    def _share(self, role, user):
        s = ProductShare.objects.create(
            label=self.label, recipient_email=user.email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        p = SharePermission.objects.create(share=s)
        p.apply_role_defaults(role_code=role, save=True)
        return s, p

    def _at(self, status):
        self.meta.status = status
        self.meta.save(update_fields=['status'])

    def _post(self, status, **extra):
        payload = {'status': status}
        payload.update(extra)
        return self.client.post(
            reverse('products:product_update_status', args=[self.label.my_label_id]),
            payload)


class ReviewerPicksUpTheWorkTests(WorkflowHandoffBase):
    """
    제출 완료가 되면 세 곳에서 검토자를 부른다 — 이메일("검토하고 피드백을
    남겨주세요"), 인앱 알림("귀하의 작업이 필요합니다"), 인박스("검토 필요").
    그런데 서버는 그 상태에서 검토자에게 아무 행동도 주지 않았다. 소유자가
    문을 열어 줄 때까지 서 있었고, 소유자에게는 그러라는 말이 가지 않았다.
    """

    def test_검토자가_제출_완료에서_검토를_시작한다(self):
        self._at(ProductMetadata.Status.SUBMITTED)
        self.client.force_login(self.reviewer)
        r = self._post(ProductMetadata.Status.REVIEW)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.status, ProductMetadata.Status.REVIEW)

    def test_검토_권한이_없으면_시작할_수_없다(self):
        share = ProductShare.objects.get(recipient_user=self.reviewer)
        share.permission.can_review = False
        share.permission.save()
        self._at(ProductMetadata.Status.SUBMITTED)
        self.client.force_login(self.reviewer)
        self.assertEqual(self._post(ProductMetadata.Status.REVIEW).status_code, 403)

    def test_인박스가_말하는_것과_실제로_되는_것이_같다(self):
        self._at(ProductMetadata.Status.SUBMITTED)
        self.client.force_login(self.reviewer)
        page = self.client.get(reverse('products:inbox'))
        self.assertContains(page, '검토 시작')
        self.assertEqual(self._post(ProductMetadata.Status.REVIEW).status_code, 200)


class RejectionExistsTests(WorkflowHandoffBase):
    """
    초대 메일과 상태 알림이 승인자에게 "최종 승인 또는 **반려**해 주세요" 라고
    두 곳에서 말하는데 그 길이 없었다. 문제를 본 승인자가 할 수 있는 것은
    승인하거나, 아무것도 안 하고 전화하는 것뿐이었고 후자는 흔적이 안 남았다.
    """

    def test_승인자가_반려한다(self):
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        r = self._post(ProductMetadata.Status.REVIEW, reject_reason='알레르기 표시 누락')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.status, ProductMetadata.Status.REVIEW)

    def test_검토자가_반려한다(self):
        self._at(ProductMetadata.Status.REVIEW)
        self.client.force_login(self.reviewer)
        r = self._post(ProductMetadata.Status.SUBMITTED, reject_reason='성적서가 옛 버전')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_사유_없이는_반려할_수_없다(self):
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        r = self._post(ProductMetadata.Status.REVIEW)
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json().get('need_reject_reason'))
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.status, ProductMetadata.Status.PENDING)

    def test_사유가_댓글로_남는다(self):
        from v1.products.models import ProductComment
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        self._post(ProductMetadata.Status.REVIEW, reject_reason='알레르기 표시 누락')
        self.assertEqual(
            [c.content for c in ProductComment.objects.filter(label=self.label)],
            ['[반려] 알레르기 표시 누락'])

    def test_사유가_활동_로그에_남는다(self):
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        self._post(ProductMetadata.Status.REVIEW, reject_reason='알레르기 표시 누락')
        log = ProductActivityLog.objects.filter(
            label=self.label, action='STATUS_CHANGED').latest('log_id')
        self.assertTrue(log.details.get('rejected'))
        self.assertEqual(log.details.get('reject_reason'), '알레르기 표시 누락')

    def test_검토자가_없어도_승인자는_반려할_수_있다(self):
        # 검토 단계를 건너뛴 제품에서 "검토자가 필요합니다" 로 막히면
        # 되돌릴 길이 아예 없어진다.
        ProductShare.objects.filter(recipient_user=self.reviewer).delete()
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        r = self._post(ProductMetadata.Status.REVIEW, reject_reason='되돌립니다')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_소유자에게_반려_소식이_간다(self):
        from v1.products.models import ProductNotification
        self._at(ProductMetadata.Status.PENDING)
        self.client.force_login(self.approver)
        self._post(ProductMetadata.Status.REVIEW, reject_reason='알레르기 표시 누락')
        msgs = [n.message for n in ProductNotification.objects.filter(recipient=self.owner)]
        self.assertTrue(any('반려' in m and '알레르기 표시 누락' in m for m in msgs), msgs)


class DocRequestStatusIsHonestTests(TestCase):
    """
    '수락' 이 두 가지를 뜻했다 — 받는 사람이 "하겠다" 고 누른 것과, 협력사가
    파일을 낸 것. 대기 집계는 PENDING 만 세므로 수락만 하고 안 낸 건이
    대기에서 빠졌다. 목록상 처리된 것처럼 보이는데 파일은 오지 않았다.
    """

    def setUp(self):
        from v1.products.models import DocumentRequest
        self.DR = DocumentRequest
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.client.force_login(self.owner)

    def _req(self, email, status, due=None):
        # 연락처 목록은 '활성 공유 ∪ 주소록' 이다. 자료 요청만으로는 행이 안 생긴다.
        from v1.products.models import UserContact
        UserContact.objects.get_or_create(owner=self.owner, email=email)
        return self.DR.objects.create(
            requester=self.owner, recipient_email=email, status=status, due_date=due)

    def _row(self, email):
        rows = self.client.get(reverse('products:contacts')).context['contacts_list']
        return next(r for r in rows if r['email'] == email)

    def test_하겠다고만_한_건은_여전히_대기다(self):
        self._req('sup@x.com', self.DR.STATUS_ACCEPTED)
        self.assertEqual(self._row('sup@x.com')['doc_pending'], 1)

    def test_실제로_낸_건은_대기에서_빠진다(self):
        self._req('sup@x.com', self.DR.STATUS_SUBMITTED)
        self.assertEqual(self._row('sup@x.com')['doc_pending'], 0)

    def test_기한이_지난_건을_따로_센다(self):
        from datetime import timedelta
        from django.utils import timezone
        yesterday = timezone.localdate() - timedelta(days=1)
        self._req('sup@x.com', self.DR.STATUS_ACCEPTED, due=yesterday)
        self._req('sup@x.com', self.DR.STATUS_PENDING)
        row = self._row('sup@x.com')
        self.assertEqual((row['doc_pending'], row['doc_overdue']), (2, 1))

    def test_기한_판정은_모델이_한다(self):
        from datetime import timedelta
        from django.utils import timezone
        dr = self._req('sup@x.com', self.DR.STATUS_ACCEPTED,
                       due=timezone.localdate() - timedelta(days=3))
        self.assertTrue(dr.is_outstanding)
        self.assertTrue(dr.is_overdue)
        self.assertEqual(dr.days_left, -3)
        dr.status = self.DR.STATUS_SUBMITTED
        self.assertFalse(dr.is_overdue, '이미 낸 건은 늦은 것이 아니다')

    def test_하겠다고만_한_건도_취소할_수_있다(self):
        dr = self._req('sup@x.com', self.DR.STATUS_ACCEPTED)
        r = self.client.post(reverse('products:doc_request_cancel', args=[dr.request_id]))
        self.assertEqual(r.status_code, 200)
        dr.refresh_from_db()
        self.assertEqual(dr.status, self.DR.STATUS_CANCELLED)


class DueDateRemindersTests(TestCase):
    """
    due_date 는 적히기만 했다 — 협력사 링크 만료 판정과 빨간 글씨, 두 군데.
    기한 전에도 후에도 아무 일이 없어서 "그거 아직 안 왔어요" 를 사람이
    기억해서 챙기고 있었다.
    """

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from v1.products.models import DocumentRequest
        self.DR = DocumentRequest
        self.today = timezone.localdate()
        self.delta = timedelta
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')

    def _req(self, days, status=None):
        return self.DR.objects.create(
            requester=self.owner, recipient_email='sup@x.com',
            status=status or self.DR.STATUS_PENDING,
            due_date=self.today + self.delta(days=days))

    def _run(self, **kw):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('remind_doc_requests', stdout=out, **kw)
        return out.getvalue()

    def test_기한_임박과_초과를_센다(self):
        self._req(1)      # 내일
        self._req(-2)     # 이틀 지남
        self._req(30)     # 아직 멀었다
        out = self._run()
        self.assertIn('기한 임박 1건, 기한 초과 1건', out)

    def test_이미_낸_것은_챙기지_않는다(self):
        self._req(-2, status=self.DR.STATUS_SUBMITTED)
        self.assertIn('기한 임박 0건, 기한 초과 0건', self._run())

    def test_기본은_미리보기라_보내지_않는다(self):
        from django.core import mail
        self._req(-1)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_보내면_받는_사람과_요청자_둘_다_받는다(self):
        from django.core import mail
        self._req(-1)
        self._run(send=True)
        to = sorted(sum((m.to for m in mail.outbox), []))
        self.assertEqual(to, ['owner@x.com', 'sup@x.com'])

    def test_같은_날_두_번_보내지_않는다(self):
        from django.core import mail
        self._req(-1)
        self._run(send=True)
        first = len(mail.outbox)
        self._run(send=True)
        self.assertEqual(len(mail.outbox), first)


class VendorCanResubmitTests(TestCase):
    """
    한 번 내면 토큰이 즉시 만료돼 다시 낼 수 없었다. 파일을 잘못 냈거나
    스캔이 잘렸으면 요청자에게 연락해 새 요청을 받아야 했다.
    """

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from v1.products.models import DocumentRequest
        self.DR = DocumentRequest
        owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.dr = DocumentRequest.objects.create(
            requester=owner, recipient_email='sup@x.com',
            due_date=timezone.localdate() + timedelta(days=7))

    def _open(self):
        return self.client.get(
            reverse('vendor:upload_form', args=[self.dr.upload_token]))

    def test_이미_낸_뒤에도_기한_안이면_다시_연다(self):
        self.dr.status = self.DR.STATUS_SUBMITTED
        self.dr.save()
        self.assertEqual(self._open().status_code, 200)

    def test_기한이_지나면_닫힌다(self):
        from datetime import timedelta
        from django.utils import timezone
        self.dr.due_date = timezone.localdate() - timedelta(days=1)
        self.dr.save()
        self.assertEqual(self._open().status_code, 410)

    def test_취소된_요청은_닫힌다(self):
        self.dr.status = self.DR.STATUS_CANCELLED
        self.dr.save()
        self.assertEqual(self._open().status_code, 410)


class InviteLandsSomewhereTests(TestCase):
    """
    초대 메일은 회원 여부와 무관하게 /products/inbox/ 로 보냈다. 비회원이
    누르면 로그인 화면으로 떨어지고, 가입 안내도 "초대받은 그 이메일로
    가입해야 연결된다" 는 말도 없었다. 자료 요청은 이미 매직링크로 로그인
    없이 받고 있었는데 초대에만 그 패턴이 없었다.
    """

    def setUp(self):
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        self.share = ProductShare.objects.create(
            label=self.label, recipient_email='newbie@x.com',
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        p = SharePermission.objects.create(share=self.share)
        p.apply_role_defaults(role_code='REVIEWER', save=True)

    def _url(self):
        return reverse('products:share_invite_landing', args=[self.share.public_token])

    def test_로그인_없이_열린다(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_누가_무엇을_어떤_역할로_주었는지_말한다(self):
        r = self.client.get(self._url())
        self.assertContains(r, '브라우니')
        self.assertContains(r, '검토자')
        self.assertContains(r, 'newbie@x.com')

    def test_그_이메일로_가입하라고_말한다(self):
        r = self.client.get(self._url())
        self.assertContains(r, '로 가입해야 이 제품과 연결됩니다')

    def test_초대받은_계정으로_들어오면_인박스로_보낸다(self):
        newbie = User.objects.create_user('새사람', password='x', email='newbie@x.com')
        self.client.force_login(newbie)
        self.assertRedirects(self.client.get(self._url()), reverse('products:inbox'))

    def test_다른_계정이면_조용히_넘기지_않는다(self):
        self.client.force_login(self.owner)
        r = self.client.get(self._url())
        self.assertContains(r, '초대받은 주소와 다릅니다')

    def test_공유가_끊기면_닫힌다(self):
        self.share.active_yn = False
        self.share.save()
        self.assertEqual(self.client.get(self._url()).status_code, 410)

    def test_기한이_지나면_닫힌다(self):
        from datetime import timedelta
        from django.utils import timezone
        self.share.share_end_date = timezone.now() - timedelta(days=1)
        self.share.save()
        self.assertEqual(self.client.get(self._url()).status_code, 410)

    def test_제품_내용은_보여주지_않는다(self):
        # 착지점은 안내판이지 열람 화면이 아니다
        from v1.products.models import ProductComment
        ProductComment.objects.create(
            label=self.label, author=self.owner, content='내부 검토 메모')
        r = self.client.get(self._url())
        self.assertNotContains(r, '내부 검토 메모')


class RoleSummaryIsShownTests(TestCase):
    """
    '공동 편집' 은 이름과 실질이 다르다 — EDITOR 는 상태 전이에서 소유자와
    같은 권한을 받아 혼자 승인 완료까지 보낼 수 있다. 외부 사람을 거기 넣는
    순간 무슨 일이 벌어지는지 화면에서 알 방법이 없었다.
    """

    def test_모든_역할에_설명이_있다(self):
        for code, _ in SharePermission.ROLE_CHOICES:
            self.assertIn(code, SharePermission.ROLE_SUMMARY)
            self.assertTrue(SharePermission.ROLE_SUMMARY[code].strip())

    def test_공동_편집이_무엇인지_숨기지_않는다(self):
        self.assertIn('부소유자', SharePermission.ROLE_SUMMARY['EDITOR'])
        self.assertIn('승인 완료', SharePermission.ROLE_SUMMARY['EDITOR'])

    def test_화면과_서버가_같은_문장을_쓴다(self):
        """두 곳에 있는 문장이 갈라지면 화면이 거짓말을 한다."""
        import re
        from pathlib import Path
        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'templates' / 'products'
              / '_tab_permissions.html').read_text(encoding='utf-8')
        block = re.search(r'var ROLE_SUMMARY = \{(.*?)\};', js, re.S)
        self.assertIsNotNone(block, '화면에 ROLE_SUMMARY 가 없다')
        for code, text in SharePermission.ROLE_SUMMARY.items():
            # 서버 쪽은 강조용 ** 를 쓰므로 걷고 견준다
            plain = text.replace('**', '')
            self.assertIn(plain, block.group(1), code)


class RejectReasonUiExistsTests(TestCase):
    """
    서버가 need_reject_reason 을 돌려주는데 화면이 그 창을 안 띄우면,
    반려를 누른 사람은 스낵바 한 줄만 보고 왜 안 되는지 모른 채 끝난다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'product_detail.html').read_text(encoding='utf-8')

    def test_서버_신호를_받아_창을_띄운다(self):
        self.assertIn('result.need_reject_reason', self.src)
        self.assertIn('showRejectReason(newStatus)', self.src)

    def test_창과_입력칸이_있다(self):
        for piece in ('id="rejectReasonModal"', 'id="rejectReason"',
                      'id="rejectConfirm"', 'id="rejectReasonError"'):
            self.assertIn(piece, self.src, piece)

    def test_사유를_서버로_보낸다(self):
        self.assertIn("formData.append('reject_reason', rejectReason)", self.src)
        self.assertIn('changeStatus(newStatus, null, false, reason)', self.src)

    def test_어디에_남는지_알려_준다(self):
        self.assertIn('댓글과 활동 로그', self.src)

    def test_스타일은_템플릿이_아니라_css_에_있다(self):
        """
        표시 항목 패널의 규칙이 이 템플릿 맨 아래 <style> 블록에 있었다.
        마크업은 297줄인데 규칙은 3,894줄 — 3,600줄 아래다. 브라우저는 패널을
        **스타일 없이 한 번 그린 뒤** 문서 끝의 <style> 을 만나 다시 그렸고,
        화면을 열 때마다 그 사이가 눈에 보였다.

        products_detail.css 는 head 에서 불린다. 거기에 있어야 한다.
        """
        self.assertNotIn('<style', self.src,
                         'products_detail.css 로 옮기세요 (head 에서 불립니다)')

    def test_색은_토큰에서_온다(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        css = (Path(dj.BASE_DIR) / 'static' / 'css'
               / 'products_detail.css').read_text(encoding='utf-8')
        block = re.search(r'\.rj-icon.*?\.rj-error[^\n]*\n', css, re.S)
        self.assertIsNotNone(block, 'products_detail.css 에 반려 모달 규칙이 없다')
        self.assertNotRegex(block.group(0), r'#[0-9a-fA-F]{6}')


class SizeDeclarationsLiveInCssTests(TestCase):
    """
    같은 글씨 크기 선언이 세 화면에 **198곳** 인라인으로 흩어져 있었다 —
    home · label_creation · label_creation_v1 의 알레르기·문구 빠른 선택 단추.
    크기 하나 바꾸려면 198곳을 고쳐야 했고, 어느 날 한쪽만 고쳐진다.

    요소에는 이미 클래스가 붙어 있었다. 새 체계를 세운 것이 아니라 이미 있던
    이름으로 선언을 옮긴 것뿐이다.

    폭·간격(width·gap·flex)처럼 그 자리에서만 쓰는 배치값은 그대로 둔다 —
    클래스로 옮겨 봐야 이름만 늘어난다.
    """

    SCREENS = ['templates/main/home.html',
               'templates/label/label_creation.html',
               'templates/label/label_creation_v1.html']

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.base = Path(dj.BASE_DIR)

    def _texts(self):
        return [(rel, (self.base / rel).read_text(encoding='utf-8'))
                for rel in self.SCREENS]

    #  뽑아낸 선언들. 이것이 인라인으로 다시 나타나면 실패한다.
    EXTRACTED = [
        'font-size: 0.7rem',
        'font-size: 0.7rem; padding: 0.2rem 0.6rem',
        'font-size: 0.7rem; padding: 0.2rem 0.5rem',
        'font-size: 0.8rem; padding: 0.25rem 0.3rem',
        'font-size:0.8rem',
    ]

    def test_뽑아낸_선언이_인라인으로_돌아오지_않았다(self):
        import re
        want = {re.sub(r'\s+', ' ', d).lower() for d in self.EXTRACTED}
        for rel, text in self._texts():
            for raw in re.findall(r'style="([^"]+)"', text):
                key = '; '.join(x.strip() for x in raw.split(';') if x.strip())
                self.assertNotIn(re.sub(r'\s+', ' ', key).lower(), want,
                                 '%s: %s 는 CSS 에 있다' % (rel, key))

    def test_되풀이되는_크기_선언이_남지_않았다(self):
        """
        같은 크기 선언이 세 번 넘게 되풀이되면 클래스로 뽑을 때다.

        남아 있는 것들(0.75em·0.78rem·0.85rem·0.875rem·0.9rem·0.95rem…)은
        **저마다 다른 값**이라 뽑는 문제가 아니라 눈금을 정하는 문제다 —
        그건 화면이 어떻게 보일지를 바꾸는 결정이라 따로 다룬다.
        """
        import re
        from collections import Counter
        for rel, text in self._texts():
            c = Counter()
            for raw in re.findall(r'style="([^"]+)"', text):
                if 'font-size' not in raw:
                    continue
                c[';'.join(sorted(x.strip() for x in raw.split(';') if x.strip()))] += 1
            worst = [(n, k) for k, n in c.items() if n > 3]
            self.assertEqual(worst, [], '%s 에서 되풀이된다' % rel)

    def test_선언은_css_한_곳에_있다(self):
        css = (self.base / 'static/css/label_creation.css').read_text(encoding='utf-8')
        for rule in ('.quick-text-toggle', '.quick-allergen-btn', '.allergen-toggle',
                     '.quick-allergen-btn-label', '.allergen-toggle-label',
                     '.quick-text-toggle-label', '.lc-btn-xs',
                     '.lc-input-sm', '.lc-label-sm'):
            self.assertIn(rule, css, rule)

    def test_class_가_두_번_붙은_태그가_없다(self):
        # 두 번 붙으면 HTML 은 앞의 것만 본다 — 뒤에 넣은 것이 조용히 사라진다
        import re
        pat = re.compile(r'<[a-zA-Z][^>]*?class="[^"]*"[^>]*?\sclass="')
        for rel, text in self._texts():
            self.assertEqual(pat.findall(text), [], rel)

    def test_빈_style_속성이_남지_않았다(self):
        for rel, text in self._texts():
            self.assertNotIn('style=""', text, rel)


class StylesComeBeforeMarkupTests(TestCase):
    """
    스타일이 마크업 **뒤**에 있으면 브라우저는 화면을 한 번 스타일 없이 그린
    뒤 다시 그린다. 화면을 열 때마다 그 사이가 눈에 보인다.

    제품 상세의 표시 항목 패널이 그랬다 — 마크업은 297줄, 규칙은 3,894줄.
    3,600줄 아래였다. 체크박스와 글자가 제자리를 못 찾고 흩어졌다가 들어갔다.
    여덟 화면이 같은 모양이었다.

    base 를 타는 문서만 본다. 단독 문서는 head 가 자기 안에 있어 판정 기준이
    다르다.
    """

    #  앞선 태그가 이만큼 쌓인 뒤의 <style> 은 깜빡임이 눈에 보인다.
    LIMIT = 40

    def _late_styles(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        root = Path(dj.BASE_DIR) / 'templates'
        found = []
        for path in sorted(root.rglob('*.html')):
            text = path.read_text(encoding='utf-8')
            if '{% extends' not in text:
                continue
            start = text.find('{% block content %}')
            if start < 0:
                continue
            for m in re.finditer(r'<style[^>]*>', text[start:]):
                at = start + m.start()
                before = len(re.findall(r'<(?!/|!|style|script)[a-z]', text[start:at]))
                if before >= self.LIMIT:
                    rel = str(path.relative_to(root)).replace(chr(92), '/')
                    found.append('%s:%d (앞선 태그 %d개)'
                                 % (rel, text.count(chr(10), 0, at) + 1, before))
        return found

    def test_마크업_뒤에_오는_스타일이_없다(self):
        self.assertEqual(
            self._late_styles(), [],
            '스타일을 마크업 앞이나 head 에서 불리는 CSS 로 옮기세요')


class ContactsAppearInPermissionPaletteTests(TestCase):
    """
    "연락처에 등록했는데 권한 설정에서 검색도 안 되고 목록에도 없다."

    권한 탭의 검색은 서버를 부르지 않는다 — 이미 그려진 카드를 걸러내는 DOM
    필터다. 그래서 **카드로 그려지지 않은 사람은 검색으로도 나올 수 없다.**
    팔레트 목록(all_shared_users)이 ProductShare 만 보고 있어서, 연락처
    화면에서 직접 추가한 사람(UserContact 만 있고 공유는 없다)은 한 번도
    오르지 않았다.

    공유 → 연락처 방향은 이미 흐른다(share_create 가 UserContact 를 만든다).
    그 반대만 빠져 있었다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata, UserContact
        self.UserContact = UserContact
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        ProductMetadata.objects.create(label=self.label, product_code='PRD-T-1')
        self.client.force_login(self.owner)

    def _palette(self):
        page = self.client.get(
            reverse('products:product_detail', args=[self.label.my_label_id]))
        return page.context['all_shared_users']

    def test_주소록에만_있는_사람도_팔레트에_오른다(self):
        self.UserContact.objects.create(owner=self.owner, email='sup@x.com',
                                        name='협력사', company='A식품')
        rows = {c.recipient_email: c for c in self._palette()}
        self.assertIn('sup@x.com', rows)
        card = rows['sup@x.com']
        self.assertEqual(card.display_name, '협력사')
        self.assertEqual(card.recipient_company, 'A식품')

    def test_아직_공유_안_된_카드는_share_id_가_없다(self):
        """화면의 dropPerson 이 share_id 없는 카드를 초대로 보낸다."""
        self.UserContact.objects.create(owner=self.owner, email='sup@x.com')
        card = next(c for c in self._palette() if c.recipient_email == 'sup@x.com')
        self.assertIsNone(card.share_id)
        self.assertIsNone(card.permission_record)

    def test_이미_공유된_사람은_두_번_오르지_않는다(self):
        share = ProductShare.objects.create(
            label=self.label, recipient_email='sup@x.com', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share)
        self.UserContact.objects.create(owner=self.owner, email='sup@x.com')
        emails = [c.recipient_email for c in self._palette()]
        self.assertEqual(emails.count('sup@x.com'), 1)

    def test_대소문자가_달라도_두_번_오르지_않는다(self):
        share = ProductShare.objects.create(
            label=self.label, recipient_email='Sup@X.com', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share)
        self.UserContact.objects.create(owner=self.owner, email='sup@x.com')
        self.assertEqual(len(self._palette()), 1)

    def test_남의_주소록은_올라오지_않는다(self):
        other = User.objects.create_user('남', password='x', email='other@x.com')
        self.UserContact.objects.create(owner=other, email='secret@x.com')
        self.assertEqual(
            [c.recipient_email for c in self._palette()], [])


class PaletteSearchLooksAtWhatIsShownTests(TestCase):
    """
    화면에 보이는 이름은 display_name(이름 → 계정명 → 이메일)인데 검색은
    data-name(recipient_name)만 봤다. 이름을 안 적어 둔 멤버는 **보이는 그
    이름으로 찾아도** 걸러졌다. 소유자 카드는 data-name 이 없어 무엇을
    입력하든 사라졌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_permissions.html').read_text(encoding='utf-8')

    def test_계정명도_찾는다(self):
        self.assertIn('card.dataset.username', self.src)

    def test_인허가번호도_찾는다(self):
        self.assertIn('card.dataset.licenseNo', self.src)

    def test_소유자는_검색으로_사라지지_않는다(self):
        self.assertIn("card.dataset.isOwner === 'true'", self.src)


class SelfIsNotInMyOwnContactsTests(TestCase):
    """
    share_create 가 공유를 만들 때 UserContact 도 함께 만든다. 그래서 자기
    이메일로 한 번 공유해 보면 **자기가 자기 주소록에 들어앉고**, 권한 설정
    팔레트에도 소유자 카드와 같은 사람이 두 번 나온다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata, UserContact
        self.UserContact = UserContact
        self.owner = User.objects.create_user('주인', password='x', email='me@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        ProductMetadata.objects.create(label=self.label, product_code='PRD-T-1')
        self.client.force_login(self.owner)

    def test_주소록_목록에_내가_없다(self):
        self.UserContact.objects.create(owner=self.owner, email='me@x.com', name='나')
        self.UserContact.objects.create(owner=self.owner, email='sup@x.com', name='협력사')
        rows = self.client.get(reverse('products:contacts')).context['contacts_list']
        self.assertEqual([r['email'] for r in rows], ['sup@x.com'])

    def test_내_이메일로_된_공유도_주소록에_안_올린다(self):
        share = ProductShare.objects.create(
            label=self.label, recipient_email='me@x.com', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share)
        rows = self.client.get(reverse('products:contacts')).context['contacts_list']
        self.assertEqual(rows, [])

    def test_권한_팔레트에도_내가_두_번_안_나온다(self):
        self.UserContact.objects.create(owner=self.owner, email='me@x.com')
        page = self.client.get(
            reverse('products:product_detail', args=[self.label.my_label_id]))
        emails = [c.recipient_email for c in page.context['all_shared_users']]
        self.assertNotIn('me@x.com', emails)


class DragGhostIsTheCardTests(TestCase):
    """
    카드를 끌면 카드만 따라와야 하는데 **화면 전체가 흐릿하게** 같이 잡혀
    움직였다.

    dragstart 안에서 곧바로 card.style.opacity 를 바꾼 것이 원인이다.
    브라우저는 dragstart 직후 끌림 그림을 스냅샷하는데, 그 순간 요소가
    반투명해지면 카드만 따로 뜨지 않고 합성 레이어 전체가 잡힌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_permissions.html').read_text(encoding='utf-8')

    def test_끌림_그림을_카드로_못박는다(self):
        self.assertIn('setDragImage(', self.src)

    def test_반투명은_스냅샷_뒤에_건다(self):
        import re
        i = self.src.index('function dragStart')
        j = self.src.index('function dragEnd')
        body = self.src[i:j]
        # dragstart 안에서 곧바로 opacity 를 건드리면 안 된다
        self.assertNotRegex(body, r"style\.opacity\s*=")
        self.assertIn('is-dragging', body)
        self.assertIn('setTimeout(', body)

    def test_끌림_중_모양은_css_에_있다(self):
        self.assertIn('.person-card.is-dragging', self.src)

    def test_드롭_강조가_남지_않는다(self):
        """드롭이 일어난 요소에는 dragleave 가 오지 않는다 — 끝날 때 걷는다."""
        self.assertIn('_clearDropHighlight', self.src)
        i = self.src.index('function dragEnd')
        j = self.src.index('function _clearDropHighlight')
        self.assertIn('_clearDropHighlight()', self.src[i:j])

    def test_인허가번호도_들고_간다(self):
        i = self.src.index('_draggedPersonData = {')
        self.assertIn('licenseNo', self.src[i:i + 600])


class ActionButtonsActuallyRenderTests(TestCase):
    """
    앞서 검토 시작·반려를 넣었는데 **POST 만 고쳤다.** 단추를 그리는 GET 쪽
    available_actions 는 예전 그대로여서, 서버는 허용하는데 화면에 단추가
    없었다 — 이메일·알림·인박스 세 곳이 부르는데 들어가면 누를 것이 없던
    그 증상이 그대로 남아 있었다.

    표가 두 곳에 있었던 것이 원인이다. 이 시험은 **화면을 열어** 단추 글자가
    나오는지 본다 — POST 만 보는 시험으로는 이 종류가 다시 잡히지 않는다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata
        self.Meta = ProductMetadata
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        self.meta = ProductMetadata.objects.create(
            label=self.label, product_code='PRD-T-1',
            status=ProductMetadata.Status.DRAFT)

    def _member(self, role, email):
        user = User.objects.create_user(role, password='x', email=email)
        share = ProductShare.objects.create(
            label=self.label, recipient_email=email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        perm = SharePermission.objects.create(share=share)
        perm.apply_role_defaults(role_code=role, save=True)
        return user, perm

    def _page(self, user, status):
        self.meta.status = status
        self.meta.save(update_fields=['status'])
        self.client.force_login(user)
        return self.client.get(
            reverse('products:product_detail', args=[self.label.my_label_id]))

    def test_검토자가_제출_완료에서_검토_시작_단추를_본다(self):
        rv, _ = self._member('REVIEWER', 'rv@x.com')
        page = self._page(rv, self.Meta.Status.SUBMITTED)
        self.assertIn('review', page.context['available_actions'])
        self.assertContains(page, '검토 시작')

    def test_검토자가_검토_중에서_반려_단추를_본다(self):
        rv, _ = self._member('REVIEWER', 'rv@x.com')
        page = self._page(rv, self.Meta.Status.REVIEW)
        self.assertIn('submitted', page.context['available_actions'])
        self.assertContains(page, '재검토')

    def test_승인자가_승인_대기에서_반려_단추를_본다(self):
        ap, _ = self._member('APPROVER', 'ap@x.com')
        page = self._page(ap, self.Meta.Status.PENDING)
        self.assertIn('review', page.context['available_actions'])
        self.assertContains(page, '반려')

    def test_검토_권한을_끄면_단추가_사라진다(self):
        """화면이 플래그를 무시하면 눌러 놓고 403 을 받는다."""
        rv, perm = self._member('REVIEWER', 'rv@x.com')
        perm.can_review = False
        perm.save()
        page = self._page(rv, self.Meta.Status.SUBMITTED)
        self.assertEqual(page.context['available_actions'], [])

    def test_화면과_서버가_같은_표를_쓴다(self):
        """GET 과 POST 가 갈라지면 한쪽만 고쳐진다 — 그래서 이 문제가 났다."""
        from v1.products.views import ROLE_STATUS_ACTIONS, role_actions
        for role, table in ROLE_STATUS_ACTIONS.items():
            for status, expected in table.items():
                self.assertEqual(role_actions(role, status), expected,
                                 '%s/%s' % (role, status))

    def test_자료_제출자에게_댓글창을_열어_주지_않는다(self):
        """can_comment=False 인데 입력창이 열려 있어 다 쓴 뒤에 막혔다."""
        up, perm = self._member('UPLOADER', 'up@x.com')
        self.assertFalse(perm.can_comment)
        page = self._page(up, self.Meta.Status.REQUESTING)
        self.assertFalse(page.context['can_comment'])

    def test_올릴_권한도_플래그를_따른다(self):
        rv, _ = self._member('REVIEWER', 'rv@x.com')
        page = self._page(rv, self.Meta.Status.REVIEW)
        self.assertFalse(page.context['can_upload_documents'])
        up, _ = self._member('UPLOADER', 'up2@x.com')
        page = self._page(up, self.Meta.Status.REQUESTING)
        self.assertTrue(page.context['can_upload_documents'])


class OneDefinitionPerPageTests(TestCase):
    """
    같은 페이지에 같은 이름의 function 이 둘 있으면 **뒤에 파싱된 것이 이긴다.**
    어느 쪽이 이기는지는 include 위치에만 달려 있어 아무도 의도하지 않는다.

    실제로 `deletePerson` 이 그랬다 — 이기는 판이 window.selectedShareId 를
    보는데 그 변수를 대입하는 코드가 저장소에 없었고, 어떤 멤버를 골라 삭제를
    눌러도 "이 사용자는 현재 제품에 공유되지 않았습니다." 만 떴다. 공유를
    지우는 길이 아예 없었다.

    toggleLeftPanel · toggleRightPanel · openQuickInvite 도 두 벌이었다. 지금
    이기는 판이 우연히 정상이라 동작하지만, include 위치가 바뀌면 죽는다.
    """

    #  구현만 다르고 동작이 같은 것들. 어느 판이 이겨도 결과가 같다.
    EQUIVALENT = {
        'esc',            # 같은 5글자를 이스케이프한다 (방식만 다름)
        'getCsrf',        # 쿠키에서 csrftoken — 세 판이 동일
        'getCsrfToken',   # 전역 우선 / input 우선. 둘 다 토큰을 돌려준다
    }

    def _duplicates(self):
        import re
        from collections import defaultdict
        from pathlib import Path

        from django.conf import settings as dj

        root = Path(dj.BASE_DIR) / 'templates'
        text = {str(p.relative_to(root)).replace(chr(92), '/'): p.read_text(encoding='utf-8')
                for p in root.rglob('*.html')}
        inc = re.compile(r'{%\s*include\s+["\']([^"\']+)["\']')
        fn = re.compile(r'^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(', re.M)

        def family(rel, seen=None):
            seen = seen if seen is not None else set()
            if rel in seen or rel not in text:
                return seen
            seen.add(rel)
            for child in inc.findall(text[rel]):
                family(child, seen)
            return seen

        found = defaultdict(set)
        for rel, t in text.items():
            if '{% extends' not in t or '{% block content %}' not in t:
                continue
            where = defaultdict(set)
            for member in family(rel):
                for name in set(fn.findall(text[member])):
                    where[name].add(member)
            for name, files in where.items():
                if len(files) > 1:
                    found[name] |= files
        return found

    def test_한_페이지에_같은_이름의_함수가_둘_있지_않다(self):
        extra = {n: sorted(f) for n, f in self._duplicates().items()
                 if n not in self.EQUIVALENT}
        self.assertEqual(extra, {},
                         '뒤에 파싱된 판이 이긴다 — 하나만 남기거나 '
                         '동작이 같음을 확인해 EQUIVALENT 에 적으세요')

    def test_삭제는_버튼의_share_id_를_읽는다(self):
        from pathlib import Path

        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'templates' / 'products'
               / '_tab_permissions.html').read_text(encoding='utf-8')
        self.assertIn("getElementById('delete-person-btn')", src)
        self.assertNotIn('window.selectedShareId', src)


class ContactSaveTouchesOnlySentFieldsTests(TestCase):
    """
    안 보낸 칸을 '빈 값' 으로 읽어 그대로 덮고 있었다. 격자 저장이 memo 를
    빠뜨리고 있었으므로 **회사명 한 글자만 고쳐도** 엑셀에서 옮겨 둔
    전화번호·부서(비고)가 통째로 지워졌다.

    앞서 목록 쪽(조회)만 고쳤고 저장 쪽은 그대로였다. 화면이 한 칸을
    빠뜨리는 일은 또 생긴다 — 그때 데이터가 사라지지 않는 쪽이 맞다.
    """

    def setUp(self):
        from v1.products.models import UserContact
        self.UserContact = UserContact
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.uc = UserContact.objects.create(
            owner=self.owner, email='sup@x.com', name='협력사',
            company='A식품', license_no='123', memo='전화 010-1234')
        self.client.force_login(self.owner)

    def _post(self, **kw):
        payload = {'old_email': 'sup@x.com', 'email': 'sup@x.com'}
        payload.update(kw)
        return self.client.post(reverse('products:contacts_api_update'), payload)

    def test_안_보낸_칸은_그대로_둔다(self):
        self._post(company='B식품')
        self.uc.refresh_from_db()
        self.assertEqual(self.uc.company, 'B식품')
        self.assertEqual(self.uc.memo, '전화 010-1234')
        self.assertEqual(self.uc.name, '협력사')
        self.assertEqual(self.uc.license_no, '123')

    def test_손으로_비운_칸은_지워진다(self):
        """안 온 것과 빈 것은 다르다."""
        self._post(memo='')
        self.uc.refresh_from_db()
        self.assertIsNone(self.uc.memo)

    def test_이메일만_바꿔도_터지지_않는다(self):
        r = self._post(old_email='sup@x.com', email='new@x.com')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            self.UserContact.objects.filter(owner=self.owner, email='new@x.com').exists())

    def test_공유_레코드도_안_보낸_칸을_안_덮는다(self):
        label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        share = ProductShare.objects.create(
            label=label, recipient_email='sup@x.com', recipient_name='협력사',
            recipient_license_no='123', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share)
        self._post(company='B식품')
        share.refresh_from_db()
        self.assertEqual(share.recipient_license_no, '123')
        self.assertEqual(share.recipient_name, '협력사')


class ContactGridSendsEveryEditableColumnTests(TestCase):
    """
    격자가 보내는 키와 열 목록이 어긋나면 안 보낸 칸이 지워진다(서버가
    막아 주지만, 화면도 제 몫을 해야 한다). 그리고 잠글 열은 인덱스가 아니라
    이름으로 골라야 한다 — 비고가 5번에 끼어들면서 인덱스가 밀려 **비고가
    잠기고** 자료요청이 편집 가능해졌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'contacts.html').read_text(encoding='utf-8')

    def test_저장에_memo_가_실린다(self):
        i = self.src.index('const body = new URLSearchParams({')
        self.assertIn('memo:', self.src[i:i + 700])

    def test_잠금은_이름으로_고른다(self):
        i = self.src.index('cells: function (row, col)')
        block = self.src[i:i + 700]
        self.assertNotIn('col === 5', block)
        self.assertIn("READ_ONLY = ['sent', 'doc_pending']", block)

    def test_편집_가능한_열이_전부_전송된다(self):
        import re
        cols = re.findall(r"\{ data: '(\w+)'", self.src)
        editable = [c for c in cols
                    if c not in ('_checked', 'sent', 'doc_pending')]
        i = self.src.index('const body = new URLSearchParams({')
        body = self.src[i:i + 700]
        for c in editable:
            self.assertIn(c, body, '%s 열이 저장에서 빠졌다' % c)


class DocRequestScreenTellsTheTruthTests(TestCase):
    """
    자료 요청 화면이 사실과 다른 것을 말하던 자리들.
    """

    def setUp(self):
        from v1.products.models import DocumentRequest
        from pathlib import Path
        from django.conf import settings as dj
        self.DR = DocumentRequest
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'contacts.html').read_text(encoding='utf-8')
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.client.force_login(self.owner)

    def test_제출_완료가_대기_중으로_보이지_않는다(self):
        """상태 표 두 곳에 SUBMITTED 가 없어 || PENDING 으로 떨어졌다."""
        self.assertEqual(self.src.count('SUBMITTED:'), 2)

    def test_수락은_제출_전임을_밝힌다(self):
        """'수락 완료' 는 다 끝난 것처럼 읽힌다 — 아직 자료가 안 왔다."""
        self.assertIn("label: '수락 (제출 전)'", self.src)
        self.assertNotIn("label: '수락 완료'", self.src)

    def test_메일_실패를_숨기지_않는다(self):
        self.assertIn('data.email_errors', self.src)
        self.assertIn('메일이 가지 않았습니다', self.src)

    def test_요청_전송_뒤_선택_바를_갱신한다(self):
        i = self.src.index('closeDocRequestPanel();')
        self.assertIn('updateSelectionUI()', self.src[max(0, i - 500):i])

    def test_연결_제품_해제가_500_이_아니다(self):
        """label 을 먼저 None 으로 두지 않아 UnboundLocalError 가 났다."""
        dr = self.DR.objects.create(requester=self.owner, recipient_email='sup@x.com')
        r = self.client.post(
            reverse('products:api_update_doc_request_label', args=[dr.request_id]),
            {'linked_label_id': ''})
        self.assertEqual(r.status_code, 200, r.content[:200])
        dr.refresh_from_db()
        self.assertIsNone(dr.linked_label)

    def test_연결_제품_지정도_된다(self):
        label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        dr = self.DR.objects.create(requester=self.owner, recipient_email='sup@x.com')
        r = self.client.post(
            reverse('products:api_update_doc_request_label', args=[dr.request_id]),
            {'linked_label_id': label.my_label_id})
        self.assertEqual(r.status_code, 200, r.content[:200])
        dr.refresh_from_db()
        self.assertEqual(dr.linked_label, label)


class EveryCardCarriesTheSameDataTests(TestCase):
    """
    같은 사람을 그리는 카드가 7종인데 실린 data-* 가 종류마다 달랐다.
    인허가번호는 전체 팔레트 카드에만 있었다.

    selectPerson 은 card.dataset.licenseNo → undefined → '' 로 입력칸을
    비우고, 저장은 그 빈 값을 보내고, 서버는 NULL 로 덮고 **같은 이메일의
    모든 공유 레코드에 전파**했다. 드롭존 카드(자기 역할 칸 — 가장 자연스러운
    클릭 위치)에서 회사명만 고치면 그 사람의 인허가번호가 모든 제품에서
    사라졌고, 지웠다는 말은 어디에도 없었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_permissions.html').read_text(encoding='utf-8')

    def test_모든_카드가_같은_것을_싣는다(self):
        import re
        cards = re.findall(r'<div class="person-card"[^>]*?>', self.src, re.S)
        self.assertGreaterEqual(len(cards), 7)
        for card in cards:
            if 'data-is-owner="true"' in card:
                continue          # 소유자 카드는 편집 대상이 아니다
            for attr in ('data-email', 'data-name', 'data-company',
                         'data-license-no'):
                self.assertIn(attr, card, '%s 가 없다: %s' % (attr, card[:90]))

    def test_클라이언트가_만든_카드도_같다(self):
        i = self.src.index('function _makeDropzoneCard')
        block = self.src[i:i + 1400]
        for key in ('licenseNo', 'seeAll'):
            self.assertIn(key, block)

    def test_클라이언트_카드도_같은_칩_체계를_쓴다(self):
        i = self.src.index('function _paintRoleTag')
        block = self.src[i:i + 900]
        self.assertIn("'role-tag role-'", block)
        self.assertNotIn("'badge '", block)

    def test_이름을_이스케이프한다(self):
        i = self.src.index('function _makeDropzoneCard')
        self.assertIn('_esc(', self.src[i:i + 1600])


class PaletteStateFollowsTheServerTests(TestCase):
    """
    역할 칩과 선택 표시가 화면에서 따라오지 않던 자리들.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_permissions.html').read_text(encoding='utf-8')

    def test_역할_칩을_실제_클래스로_찾는다(self):
        """`.badge:not(.bg-secondary)` 로 찾아 하나도 안 지워졌다."""
        i = self.src.index('function _paintRoleTag')
        self.assertIn('.role-tag', self.src[i:i + 400])

    def test_두_탭의_카드를_모두_갱신한다(self):
        """querySelector(단수)라 최근 탭은 옛 역할로 남았다."""
        i = self.src.index('function _updatePaletteBadge')
        block = self.src[i:i + 700]
        self.assertIn('querySelectorAll(', block)

    def test_고른_카드에_표시가_있다(self):
        self.assertIn('.person-card.selected {', self.src)

    def test_드롭_뒤_상세_패널의_역할도_맞춘다(self):
        """패널이 옛 역할을 들고 있어 저장하면 조용히 되돌아갔다."""
        self.assertIn('function _syncDetailRole', self.src)
        i = self.src.index('function dropPerson(event, role)')
        j = self.src.index(chr(10) + '}', i)
        self.assertIn('_syncDetailRole(', self.src[i:j])


class ShareInfoSaveTouchesOnlySentFieldsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        self.share = ProductShare.objects.create(
            label=self.label, recipient_email='sup@x.com', recipient_name='협력사',
            recipient_company='A식품', recipient_license_no='123',
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=self.share)
        self.client.force_login(self.owner)

    def test_안_보낸_칸은_그대로_둔다(self):
        r = self.client.post(
            reverse('products:share_update_info', args=[self.share.share_id]),
            {'company': 'B식품'})
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.share.refresh_from_db()
        self.assertEqual(self.share.recipient_company, 'B식품')
        self.assertEqual(self.share.recipient_license_no, '123')
        self.assertEqual(self.share.recipient_name, '협력사')

    def test_다른_제품의_같은_사람에게도_안_덮는다(self):
        other = MyLabel.objects.create(user_id=self.owner, my_label_name='쿠키')
        twin = ProductShare.objects.create(
            label=other, recipient_email='sup@x.com', recipient_license_no='123',
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=twin)
        self.client.post(
            reverse('products:share_update_info', args=[self.share.share_id]),
            {'company': 'B식품'})
        twin.refresh_from_db()
        self.assertEqual(twin.recipient_license_no, '123')
        self.assertEqual(twin.recipient_company, 'B식품')

    def test_손으로_비운_칸은_지워진다(self):
        self.client.post(
            reverse('products:share_update_info', args=[self.share.share_id]),
            {'license_no': ''})
        self.share.refresh_from_db()
        self.assertIsNone(self.share.recipient_license_no)


class PermissionChangesAreConfirmedOnceTests(TestCase):
    """
    카드를 놓는 순간 서버로 갔다. 그래서

      - 처음 놓는 사람은 이 제품에 공유가 없어 초대 경로를 타고 **새로고침**
        됐다. 그 다음부터는 역할 변경이라 바로 반영됐다 — 같은 동작인데
        첫 번만 화면이 튀었다.
      - 자리를 몇 번 옮겨 보는 동안 매번 이메일과 인앱 알림이 나갔다.
      - 되돌리려면 다시 끌어야 했고 그것도 또 알림이었다.

    놓는 것은 초안이고, 서버는 [권한 부여] 를 누를 때 한 번 부른다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_permissions.html').read_text(encoding='utf-8')

    def _body(self, name):
        i = self.src.index('function %s(' % name)
        j = self.src.index('\n}', i)
        return self.src[i:j]

    def test_드롭은_서버를_부르지_않는다(self):
        for fn in ('dropPerson', 'dropPersonToPalette'):
            self.assertNotIn('_permPost(', self._body(fn),
                             '%s 가 드롭 즉시 서버를 부른다' % fn)

    def test_드롭은_대기_목록에_담는다(self):
        for fn in ('dropPerson', 'dropPersonToPalette'):
            self.assertIn('_recordPending(', self._body(fn))

    def test_확정과_되돌리기가_있다(self):
        for piece in ('function commitPermissions', 'function discardPermissions',
                      'id="perm-pending-bar"', 'id="perm-commit-btn"',
                      'onclick="commitPermissions()"',
                      'onclick="discardPermissions()"'):
            self.assertIn(piece, self.src, piece)

    def test_확정_전에_한_번_묻는다(self):
        body = self._body('commitPermissions')
        self.assertIn('confirm(', body)
        self.assertIn('알림이 갑니다', body)

    def test_확정이_세_경로를_모두_보낸다(self):
        body = self.src[self.src.index('function commitPermissions'):]
        body = body[:body.index('function discardPermissions')]
        self.assertIn('share/create/', body)      # 새 초대
        self.assertIn('/revoke/', body)           # 해제
        self.assertIn('/update-permission/', body)  # 역할 변경

    def test_원래_자리로_되돌리면_변경이_아니다(self):
        body = self._body('_recordPending')
        self.assertIn('delete _pending[key]', body)

    def test_확정_전_카드는_다르게_보인다(self):
        self.assertIn('.person-card.is-pending', self.src)
        self.assertIn('_markPending(card, true)', self.src)

    def test_못_주는_역할은_먼저_막는다(self):
        """예전에는 옮겨 놓고 서버 403 의 JSON 덩어리를 스낵바에 찍었다."""
        self.assertIn('function _grantBlockedReason', self.src)
        self.assertIn('_grantBlockedReason(role)', self._body('dropPerson'))

    def test_확정_안_하고_떠나면_잡는다(self):
        self.assertIn("addEventListener('beforeunload'", self.src)

    def test_팔레트_안의_카드를_움직인_것은_해제가_아니다(self):
        """예전에는 팔레트 안에서 조금만 끌어도 확인창 없이 공유가 날아갔다."""
        body = self._body('dropPersonToPalette')
        self.assertIn('.dropzone-body .person-card[data-share-id=', body)


class ContactRowIdentityIsNotIndexTests(TestCase):
    """
    저장이 `allRows[rowIdx]` 로 '변경 전 이메일' 을 정했다. 격자 행 번호를
    원본 배열 인덱스로 쓴 것인데, 필터를 켜면 격자는 부분집합이고
    일괄삭제(splice)·행이동 뒤에는 번호가 밀린다.

    그래서 **엉뚱한 거래처의 이메일이 old_email 로 올라가** 그 사람의 공유
    수신자가 바뀌고 주소록 행이 삭제됐다. 고친 사람은 자기 줄만 손댄 줄 안다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'contacts.html').read_text(encoding='utf-8')

    def test_행_번호로_원본을_찾지_않는다(self):
        import re
        # 주석 안의 언급은 세지 않는다 (왜 그랬는지를 적어 두었다)
        code = re.sub(r'/\*.*?\*/|^\s*//.*$', '', self.src, flags=re.S | re.M)
        self.assertNotIn('allRows[rowIdx]', code)

    def test_기준은_행_객체가_든다(self):
        self.assertIn('rowData._origEmail', self.src)
        self.assertIn('_origEmail:', self.src)

    def test_저장_성공_뒤_기준을_갱신한다(self):
        self.assertIn('rowData._origEmail = newEmail', self.src)

    def test_새_행은_객체로_원본에_넣는다(self):
        self.assertIn('allRows.indexOf(rowData) === -1', self.src)

    def test_빈_줄은_한_곳에서_만든다(self):
        """두 곳에서 따로 만들다 한쪽에 memo 칸이 빠져 있었다."""
        self.assertEqual(self.src.count('const emptyRow = ()'), 1)
        self.assertGreaterEqual(self.src.count('push(emptyRow())'), 2)

    def test_자동_저장_실패를_말한다(self):
        """400·403·500·네트워크 끊김을 모두 무시하고 있었다."""
        self.assertIn('저장하지 못했습니다', self.src)
        self.assertIn('서버에 연결할 수 없어 저장되지 않았습니다', self.src)


class ContactDeleteReachesTheServerTests(TestCase):
    """
    일괄 삭제와 '행 삭제' 가 화면 배열에서만 뺐다. 새로고침하면 되살아났고,
    오타로 만들어진 연락처(@ 만 있으면 즉시 생성된다)를 없앨 방법이 없었다.

    **공유 이력은 건드리지 않는다.** 주소록에서 빼는 것과 권한을 빼앗는 것은
    다른 일이다 — 활성 공유가 있으면 목록에 다시 나타나고, 그 사실을 말해 준다.
    """

    def setUp(self):
        from v1.products.models import UserContact
        self.UserContact = UserContact
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.client.force_login(self.owner)

    def test_주소록에서_지운다(self):
        self.UserContact.objects.create(owner=self.owner, email='a@x.com')
        self.UserContact.objects.create(owner=self.owner, email='b@x.com')
        r = self.client.post(reverse('products:contacts_api_delete'),
                             {'emails': ['a@x.com']})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [c.email for c in self.UserContact.objects.filter(owner=self.owner)],
            ['b@x.com'])

    def test_공유가_있으면_알려_준다(self):
        label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        share = ProductShare.objects.create(
            label=label, recipient_email='a@x.com', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share)
        self.UserContact.objects.create(owner=self.owner, email='a@x.com')
        body = self.client.post(reverse('products:contacts_api_delete'),
                                {'emails': ['a@x.com']}).json()
        self.assertEqual(body['still_shared'], ['a@x.com'])
        share.refresh_from_db()
        self.assertTrue(share.active_yn, '주소록 삭제가 공유를 건드렸다')

    def test_남의_주소록은_못_지운다(self):
        other = User.objects.create_user('남', password='x', email='other@x.com')
        self.UserContact.objects.create(owner=other, email='a@x.com')
        self.client.post(reverse('products:contacts_api_delete'),
                         {'emails': ['a@x.com']})
        self.assertTrue(self.UserContact.objects.filter(owner=other).exists())

    def test_빈_요청은_막는다(self):
        r = self.client.post(reverse('products:contacts_api_delete'), {})
        self.assertEqual(r.status_code, 400)

    def test_화면이_그_api_를_부른다(self):
        from pathlib import Path
        from django.conf import settings as dj
        src = (Path(dj.BASE_DIR) / 'templates' / 'products'
               / 'contacts.html').read_text(encoding='utf-8')
        self.assertIn('CONTACTS_API_DELETE', src)
        self.assertIn('fetch(CONTACTS_API_DELETE', src)


class SpecNutritionCanBeSavedTests(TestCase):
    """
    "성적서에서 영양성분 읽기" 가 완전한 막다른 길이었다. 패널이 "확인 후
    저장하면 이 제품의 영양성분으로 들어갑니다" 라고 말하는데 누를 단추가
    없었다 — `window.openSpecNutritionPicker` 를 부르는데 **그 함수는 저장소
    어디에도 없었다.** 서버 뷰는 처음부터 있었다.

    붙일 자리도 틀렸다. `#documentEditPanel` / `.doc-edit-panel` 로 찾는데
    실제 요소는 `#doc-edit-panel` 이라, 둘 다 못 찾고 document.body 맨 앞 —
    문서함 탭 밖, 화면 최상단 — 에 초록 상자가 끼어들었다.
    """

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_documents.html').read_text(encoding='utf-8')
        # 주석 안의 언급(왜 그랬는지를 적어 두었다)은 세지 않는다
        self.code = re.sub(r'/\*.*?\*/|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}',
                           '', self.src, flags=re.S)

    def test_없는_함수를_부르지_않는다(self):
        self.assertNotIn('openSpecNutritionPicker', self.code)

    def test_저장_단추가_있다(self):
        self.assertIn('specNutSaveBtn', self.src)
        self.assertIn('/spec-nutrition/save/', self.src)

    def test_덮어쓰기_전에_묻는다(self):
        i = self.src.index('specNutSaveBtn')
        self.assertIn('confirm(', self.src[i:i + 1500])

    def test_붙일_자리가_실재한다(self):
        self.assertIn("getElementById('doc-edit-panel')", self.code)
        self.assertNotIn('documentEditPanel', self.code)


class DocumentTabRespectsPermissionTests(TestCase):
    """
    문서 패널이 권한과 무관하게 저장·업로드 단추를 그렸고, 서버는 소유자만
    조회했다. 두 쪽이 서로를 몰랐다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj
        from v1.products.models import DocumentType, ProductDocument
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / '_tab_documents.html').read_text(encoding='utf-8')
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dtype, original_filename='a.pdf')

    def _member(self, role, email):
        user = User.objects.create_user(role, password='x', email=email)
        share = ProductShare.objects.create(
            label=self.label, recipient_email=email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        perm = SharePermission.objects.create(share=share)
        perm.apply_role_defaults(role_code=role, save=True)
        return user

    def _save(self, user, **data):
        import json
        self.client.force_login(user)
        return self.client.post(
            reverse('products:document_update', args=[self.doc.document_id]),
            data=json.dumps(data or {'description': '메모'}),
            content_type='application/json')

    def test_올릴_권한이_있는_공유자는_고칠_수_있다(self):
        editor = self._member('EDITOR', 'ed@x.com')
        r = self._save(editor)
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_올릴_권한이_없으면_사람_말로_막는다(self):
        rv = self._member('REVIEWER', 'rv@x.com')
        r = self._save(rv)
        self.assertEqual(r.status_code, 403)
        self.assertIn('권한이 없습니다', r.json()['error'])

    def test_영어_원문을_사용자에게_보내지_않는다(self):
        """Http404 가 except Exception 에 삼켜져 영어가 스낵바에 떴다."""
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        r = self._save(stranger)
        self.assertIn(r.status_code, (403, 404))
        self.assertNotIn('ProductDocument', r.json().get('error', ''))

    def test_읽기_전용은_슬롯_칩으로_업로드_창을_열지_않는다(self):
        self.assertIn('window.CAN_UPLOAD_DOCUMENTS', self.src)
        i = self.src.index('window.handleSlotClick')
        j = self.src.index('window.openUploadForUpdate')
        self.assertIn('CAN_UPLOAD_DOCUMENTS', self.src[i:j])


class SlotsFollowDocumentVisibilityTests(TestCase):
    """
    문서 목록은 visible_documents 로 걸렀는데 **슬롯 목록은 안 걸렀다.**

    그래서 자료 제출(협력사, can_view_all_documents=False)에게 "시험성적서
    ✓ 갖춤" 칩이 보이는데 누르면 "문서 정보를 찾을 수 없습니다" 가 떴다.
    필수 문서 카운터도 자기가 못 보는 것까지 세어 목록(0건)과 어긋났다.
    """

    def setUp(self):
        from v1.products.models import (DocumentSlot, DocumentType,
                                        ProductDocument, ProductMetadata)
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.sup = User.objects.create_user('협력사', password='x', email='sup@x.com')
        self.label = MyLabel.objects.create(user_id=self.owner, my_label_name='브라우니')
        ProductMetadata.objects.create(label=self.label, product_code='PRD-T-1')
        dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        from django.core.files.base import ContentFile
        self.theirs = ProductDocument.objects.create(
            label=self.label, document_type=dtype,
            file=ContentFile(b'secret', name='b.pdf'),
            original_filename='남의규격서.pdf', uploaded_by=self.owner)
        self.slot = DocumentSlot.objects.create(
            label=self.label, document_type=dtype, current_document=self.theirs)
        share = ProductShare.objects.create(
            label=self.label, recipient_email='sup@x.com', recipient_user=self.sup,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        perm = SharePermission.objects.create(share=share)
        perm.apply_role_defaults(role_code='UPLOADER', save=True)

    def _page(self, user):
        self.client.force_login(user)
        return self.client.get(
            reverse('products:product_detail', args=[self.label.my_label_id]))

    def test_못_보는_문서를_가리키는_슬롯은_비어_있다(self):
        page = self._page(self.sup)
        slots = page.context['document_slots']
        self.assertTrue(all(s.current_document is None for s in slots))

    def test_카운터도_목록과_맞는다(self):
        page = self._page(self.sup)
        self.assertEqual(page.context['filled_slots'], 0)
        self.assertEqual(page.context['documents'].count(), 0)

    def test_주인에게는_그대로_보인다(self):
        page = self._page(self.owner)
        slots = list(page.context['document_slots'])
        self.assertEqual([s.current_document_id for s in slots],
                         [self.theirs.document_id])
        self.assertEqual(page.context['filled_slots'], 1)


class UseAsIngredientFollowsThePermissionTests(TestCase):
    """
    can_use_as_ingredient 를 어디서도 검사하지 않았다. 그런데 공유 알림
    메일은 "✗ 원료로 사용 가능" 이라고 적어 보낸다 — **안 된다고 통보받은
    사람이 단추를 누르면 그대로 됐다.** 화면이 이메일과 반대로 동작했다.
    """

    def setUp(self):
        from v1.products.models import SharedProductReceipt
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.sup = User.objects.create_user('협력사', password='x', email='sup@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', prdlst_nm='브라우니')
        self.share = ProductShare.objects.create(
            label=self.label, recipient_email='sup@x.com', recipient_user=self.sup,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        self.perm = SharePermission.objects.create(share=self.share)
        self.receipt = SharedProductReceipt.objects.create(
            share=self.share, receiver=self.sup)
        self.client.force_login(self.sup)

    def _post(self):
        return self.client.post(
            reverse('products:use_as_ingredient', args=[self.receipt.receipt_id]))

    def test_못_쓰게_공유했으면_막는다(self):
        from v1.label.models import MyIngredient
        self.perm.apply_role_defaults(role_code='REVIEWER', save=True)
        self.perm.can_use_as_ingredient = False
        self.perm.save()
        self._post()
        self.receipt.refresh_from_db()
        self.assertFalse(self.receipt.used_as_ingredient_yn)
        self.assertFalse(MyIngredient.objects.filter(user_id=self.sup).exists())

    def test_쓸_수_있게_공유했으면_된다(self):
        self.perm.apply_role_defaults(role_code='EDITOR', save=True)
        self.assertTrue(self.perm.can_use_as_ingredient)
        self._post()
        self.receipt.refresh_from_db()
        self.assertTrue(self.receipt.used_as_ingredient_yn)

    def test_화면도_같은_조건을_본다(self):
        from pathlib import Path
        from django.conf import settings as dj
        src = (Path(dj.BASE_DIR) / 'templates' / 'products' / 'sharing'
               / 'inbox.html').read_text(encoding='utf-8')
        self.assertIn('share.permission.can_use_as_ingredient', src)


class BomRowIdentityIsNotIndexTests(TestCase):
    """
    BOM 표의 메타데이터가 `rowMetadata: Map<행번호, {...}>` 에 있었다. 그런데
    행 번호는 영구 키가 아니다 — manualRowMove 로 옮기거나 우클릭으로 지우면
    번호가 밀리는데, 그 Map 을 다시 매기는 훅이 하나도 없었다.

    3번 줄을 지우고 저장하면 4번 줄이던 원료가 3번 줄의 bom_id 를 달고
    올라갔다. 서버는 그 bom_id 의 줄을 덮고, source_ingredient 로 **내 원료
    마스터까지 역동기화**하고, 같은 원료를 쓰는 **다른 제품의 BOM 행까지
    bulk_update** 한다. 한 줄 지우고 저장하면 다른 제품의 원료명·알레르기·
    제조사가 조용히 바뀌었다.
    """

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'bom_detail.html').read_text(encoding='utf-8')
        self.code = re.sub(r'/\*.*?\*/|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}',
                           '', self.src, flags=re.S)

    def test_행_번호를_영구_키로_쓰지_않는다(self):
        self.assertNotIn('rowMetadata', self.code)

    def test_메타데이터는_행_객체가_든다(self):
        self.assertIn('rowData._meta = {', self.code)
        self.assertIn('row._meta', self.code)

    def test_임시저장에_행번호_기준_배열을_싣지_않는다(self):
        """복원하면 오히려 어긋난다 — _meta 가 data 와 함께 실린다."""
        self.assertNotIn('metadataArray', self.code)
        self.assertNotIn('metadata: ', self.code)


class BomClearedFieldsStayClearedTests(TestCase):
    """
    `row.allergens || metadata.allergens` 였다. 칸을 비우면 `''` 는 falsy 라
    저장해 둔 옛 값으로 떨어졌다 — 잘못 들어간 알레르기 "우유" 를 지우고
    저장해도 새로고침하면 다시 있었다. **라벨에 인쇄될 문구가 안 지워졌다.**
    """

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        src = (Path(dj.BASE_DIR) / 'templates' / 'products'
               / 'bom_detail.html').read_text(encoding='utf-8')
        self.code = re.sub(r'/\*.*?\*/', '', src, flags=re.S)

    def test_빈_값과_값_없음을_구분한다(self):
        self.assertIn('const pick = (a, b) =>', self.code)
        self.assertIn('pick(row.allergens', self.code)
        self.assertIn('pick(row.gmo', self.code)
        self.assertIn('pick(row.report_no', self.code)

    def test_옛_값으로_떨어지지_않는다(self):
        for bad in ('row.allergens || metadata',
                    'row.gmo || metadata',
                    'row.report_no || metadata'):
            self.assertNotIn(bad, self.code, bad)

    def test_칸을_비우면_플래그도_내린다(self):
        self.assertNotIn('Boolean(rowGmo) || !!metadata.gmo_yn', self.code)


class AiExtractRequiresLoginTests(TestCase):
    """
    형제 뷰는 모두 @login_required 가 있는데 document_ai_extract_api 만
    없었다. 전역 로그인 강제 미들웨어도 없어, 비로그인 POST 가 로그인
    화면으로 가지 않고 label__user_id=AnonymousUser 조회로 들어갔다.
    게다가 이 경로는 호출마다 AI 비용이 나간다.
    """

    def test_비로그인은_로그인_화면으로_간다(self):
        r = self.client.post(
            reverse('products:document_ai_extract_api', args=[1]))
        self.assertIn(r.status_code, (302, 403))
        if r.status_code == 302:
            self.assertIn('login', r['Location'])

    def test_기존_가드의_명부에서_빠졌다(self):
        """
        common/tests.py 의 "인증 없이 열린 문" 가드에 이 뷰가 **명부로
        올라가 있어** 감사가 지나쳤다. 명부는 "왜 열어 두는지" 를 적는
        자리인데, 여기에는 그럴 이유가 없었다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'common' / 'tests.py').read_text(encoding='utf-8')
        self.assertNotIn("'document_ai_extract_api'", src)


class ContactSearchScopeIsUnambiguousTests(TestCase):
    """
    필드 지정 검색이 `searchPlugin.updatePlugin({queryMethod})` 로 설정을
    갈아 끼우려 했다. 이 격자는 `search: true` 로 켜 두어 플러그인 설정
    객체가 없으므로 그 값이 실릴 자리가 없다 — "이메일" 을 골라도 회사명·
    비고의 일치까지 함께 세었다.

    열 번호도 `{email: 1, name: 2, …}` 하드코딩이었다. 비고가 5번에
    끼어들면서 잠금 규칙이 밀렸던 것과 같은 함정이고, 이 격자는
    manualColumnMove 로 사용자가 열을 옮길 수도 있다.
    """

    def setUp(self):
        import re
        from pathlib import Path
        from django.conf import settings as dj
        self.src = (Path(dj.BASE_DIR) / 'templates' / 'products'
                    / 'contacts.html').read_text(encoding='utf-8')
        # 주석 안의 언급(왜 그랬는지를 적어 두었다)은 세지 않는다
        self.code = re.sub(
            r'/\*.*?\*/|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|\{#.*?#\}',
            '', self.src, flags=re.S)

    def test_query_에_직접_넘긴다(self):
        self.assertIn('searchPlugin.query(query, undefined, scoped)', self.code)
        self.assertNotIn('updatePlugin(', self.code)

    def test_열은_이름으로_찾는다(self):
        self.assertIn('function colIndexOf(prop)', self.code)
        self.assertNotIn('fieldColMap', self.code)

    def test_검색_항목이_격자_칸과_맞는다(self):
        import re
        opts = set(re.findall(r'<option value="(\w+)">', self.src))
        cols = set(re.findall(r"\{ data: '(\w+)'", self.src))
        searchable = cols - {'_checked', 'sent', 'doc_pending'}
        self.assertTrue(searchable <= opts,
                        '격자에 있는데 검색으로 못 고르는 칸: %s'
                        % sorted(searchable - opts))


class SharedEditorReachesEditPathsTests(TestCase):
    """
    `_resolve_editable_label` 은 이름과 docstring 이 "편집 권한이 있는 공유
    라벨" 을 포함한다고 말하는데 실제로는 **오너만** 봤다.

    표시사항 탭은 can_edit 이면 [2차 검증] 단추를 보여 주는데, 그 단추가
    부르는 design_compare_latest·record·grade 가 공동 편집자에게 조용히 404
    를 냈다. 화면은 열어 주고 서버가 막는 자리였다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', delete_YN='N')
        ProductMetadata.objects.create(label=self.label, product_code='PRD-T-1')

    def _member(self, role, email):
        user = User.objects.create_user(role, password='x', email=email)
        share = ProductShare.objects.create(
            label=self.label, recipient_email=email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        perm = SharePermission.objects.create(share=share)
        perm.apply_role_defaults(role_code=role, save=True)
        return user

    def _latest(self, user):
        self.client.force_login(user)
        return self.client.get(
            reverse('products:design_compare_latest', args=[self.label.my_label_id]))

    def test_공동_편집자는_들어간다(self):
        self.assertEqual(self._latest(self._member('EDITOR', 'ed@x.com')).status_code, 200)

    def test_주인은_들어간다(self):
        self.assertEqual(self._latest(self.owner).status_code, 200)

    def test_검토자는_못_들어간다(self):
        """검토자는 can_edit_label 이 꺼져 있다 — 제품 정보를 고치지 못한다."""
        self.assertEqual(self._latest(self._member('REVIEWER', 'rv@x.com')).status_code, 404)

    def test_남은_못_들어간다(self):
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        self.assertEqual(self._latest(stranger).status_code, 404)

    def test_공유가_끊기면_못_들어간다(self):
        ed = self._member('EDITOR', 'ed@x.com')
        ProductShare.objects.filter(label=self.label).update(active_yn=False)
        self.assertEqual(self._latest(ed).status_code, 404)

    def test_공동_편집자가_남의_제품을_지우지_못한다(self):
        """
        같은 함수를 discard_if_untouched 도 쓴다. 공유가 있는 제품은
        has_children 이 '손댄 것' 으로 보므로 지워지지 않는다 — 그 안전이
        우연이 아니라 규칙임을 여기서 잠근다.
        """
        temp = MyLabel.objects.create(
            user_id=self.owner, my_label_name='임시 - 제품명 - 1', delete_YN='N')
        share = ProductShare.objects.create(
            label=temp, recipient_email='ed@x.com', share_mode='PRIVATE',
            active_yn=True, created_by=self.owner)
        perm = SharePermission.objects.create(share=share)
        perm.apply_role_defaults(role_code='EDITOR', save=True)
        ed = User.objects.create_user('편집자', password='x', email='ed@x.com')
        share.recipient_user = ed
        share.save()

        self.client.force_login(ed)
        r = self.client.post(
            reverse('products:discard_if_untouched', args=[temp.my_label_id]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['discarded'])
        self.assertTrue(MyLabel.objects.filter(pk=temp.pk).exists())


class BomExcelSkipsInactiveRowsTests(TestCase):
    """
    bom_save_api 는 저장할 때마다 옛 행을 active_yn=False 로 눕힌다. 엑셀
    다운로드에 그 조건이 없어 재작성 전 행까지 나갔다 — 배합비 합과 원재료명이
    부풀려졌다. 화면의 BOM% 칸은 active_yn=True 만 센다. 둘이 다른 말을 했다.
    """

    def setUp(self):
        from v1.bom.models import ProductBOM
        from v1.products.models import ProductMetadata
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', delete_YN='N')
        ProductMetadata.objects.create(label=self.label, product_code='PRD-T-1')
        ProductBOM.objects.create(
            parent_label=self.label, level=1, ingredient_name='밀가루',
            usage_ratio=60, active_yn=True, created_by=self.owner)
        ProductBOM.objects.create(
            parent_label=self.label, level=1, ingredient_name='옛원료',
            usage_ratio=40, active_yn=False, created_by=self.owner)
        self.client.force_login(self.owner)

    def test_비활성_행은_안_나간다(self):
        import io as _io
        import json as _json

        import openpyxl

        r = self.client.post(
            reverse('products:bulk_export_products_excel'),
            data=_json.dumps({'product_ids': [self.label.my_label_id],
                              'tabs': ['bom']}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content[:200])
        wb = openpyxl.load_workbook(_io.BytesIO(r.content))
        names = [row[2] for row in wb['BOM'].iter_rows(min_row=2, values_only=True)]
        self.assertIn('밀가루', names)
        self.assertNotIn('옛원료', names)


class 대시보드_카드는_그_숫자의_목록으로_간다(TestCase):
    """
    홈 대시보드 통계 카드 넷 중 '즐겨찾기'·'승인 완료' 두 장과 '만료 임박'
    칩이 **거르지 않은 전체 목록**으로 갔다. 숫자는 맞는데 링크가 거짓말을
    한다 — "즐겨찾기 12" 를 눌렀는데 제품 300개가 그대로 나온다.

    옆의 '내 제품'·'협업 중' 두 장은 filter=MINE/COLLAB 로 제대로 걸러 왔다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata

        self.user = User.objects.create_user(username='dashu', password='x')
        self.client.force_login(self.user)

        self.starred = MyLabel.objects.create(
            user_id=self.user, prdlst_nm='별표 제품', delete_YN='N')
        self.confirmed = MyLabel.objects.create(
            user_id=self.user, prdlst_nm='승인 제품', delete_YN='N')
        self.plain = MyLabel.objects.create(
            user_id=self.user, prdlst_nm='그냥 제품', delete_YN='N')

        ProductMetadata.objects.create(
            label=self.starred, product_code='D-1', starred_yn=True)
        ProductMetadata.objects.create(
            label=self.confirmed, product_code='D-2',
            status=ProductMetadata.Status.CONFIRMED)
        ProductMetadata.objects.create(label=self.plain, product_code='D-3')

    def _ids(self, url):
        from django.utils import timezone as _tz          # noqa: F401

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return {row['label'].my_label_id for row in r.context['products_data']}

    def test_즐겨찾기_카드는_별표한_것만_보여_준다(self):
        self.assertEqual(self._ids('/products/explorer/?filter=ALL&starred=1'),
                         {self.starred.my_label_id})

    def test_승인_완료_카드는_그_상태만_보여_준다(self):
        self.assertEqual(self._ids('/products/explorer/?filter=MINE&status=CONFIRMED'),
                         {self.confirmed.my_label_id})

    def test_만료_임박_칩은_임박한_문서가_붙은_제품만_보여_준다(self):
        from datetime import timedelta

        from v1.products.models import (
            DocumentType, EXPIRING_SOON_DAYS, ProductDocument,
        )

        from django.utils import timezone

        dt = DocumentType.objects.create(type_name='성적서', type_code='SPEC')
        today = timezone.now().date()
        ProductDocument.objects.create(
            label=self.plain, document_type=dt, active_yn=True,
            expiry_date=today + timedelta(days=EXPIRING_SOON_DAYS - 1))
        # 기간 밖 — 걸리면 안 된다
        ProductDocument.objects.create(
            label=self.starred, document_type=dt, active_yn=True,
            expiry_date=today + timedelta(days=EXPIRING_SOON_DAYS + 30))
        # 이미 지난 것도 '임박' 이 아니다
        ProductDocument.objects.create(
            label=self.confirmed, document_type=dt, active_yn=True,
            expiry_date=today - timedelta(days=1))

        self.assertEqual(self._ids('/products/explorer/?filter=MINE&expiring=1'),
                         {self.plain.my_label_id})

    def test_조건이_걸리면_화면이_그렇다고_말한다(self):
        html = self.client.get(
            '/products/explorer/?filter=ALL&starred=1').content.decode()
        self.assertIn('필터 해제', html)
        self.assertIn('즐겨찾기', html)

    def test_이상한_status_는_조용히_무시한다(self):
        """주소창에 아무거나 넣어도 500 이 아니라 전체 목록이어야 한다."""
        r = self.client.get('/products/explorer/?status=NOPE')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['products_data']), 3)

    def test_대시보드가_내놓는_주소가_실제로_그_주소다(self):
        """카드 마크업이 정말 걸러진 주소를 들고 있는지 — 링크 자체를 본다."""
        html = self.client.get('/home/').content.decode()
        self.assertIn('?filter=ALL&amp;starred=1', html)
        self.assertIn('?filter=MINE&amp;status=CONFIRMED', html)


class 기본_정보_저장이_화면과_같은_말을_한다(TestCase):
    """
    제품 상세 · 기본 정보 탭의 저장 경로에 세 가지가 겹쳐 있었다.

    1. **포장 형태를 고르고 저장해도 저장되지 않는다.** 화면의 payload 목록
       (textFieldMap)에도, 뷰의 allowed_fields 에도 `package_form` 이 없다.
       그 값을 저장하는 코드는 어느 화면도 안 쓰는 레거시 뷰 한 줄뿐이었다.
       표시사항 검증은 계속 "포장 형태가 정해지지 않아…" 를 낸다.

    2. **고칠 수는 있는데 저장은 못 하는 사람이 있다.** 화면은 역할 이름 표로
       (UPLOADER@REQUESTING, APPROVER@PENDING 을 허용), 서버는 다른 표로
       판정했다. 정작 모델은 "정보 수정"(`can_edit_label`) 플래그를 두고
       EDITOR 에게만 기본 True 를 준다 — 세 벌 중 플래그가 맞다.
       바로 옆 댓글 권한이 이미 그 원칙으로 고쳐져 있다(views.py 의 주석).

    3. **실패 이유가 절대 안 나온다.** 뷰는 `error` 키로 주는데 화면은
       `data.message` 를 읽어 언제나 폴백 문구만 떴다.
    """

    def setUp(self):
        from v1.products.models import ProductMetadata

        self.owner = User.objects.create_user(username='biowner', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='기본정보', delete_YN='N')
        self.meta = ProductMetadata.objects.create(
            label=self.label, product_code='BI-1',
            status=ProductMetadata.Status.DRAFT)
        self.client.force_login(self.owner)

    def _save(self, payload):
        return self.client.post(
            reverse('products:product_update_fields', args=[self.label.my_label_id]),
            data=json.dumps(payload), content_type='application/json')

    # ── 1. 포장 형태 ────────────────────────────────────────────────────────
    def test_포장_형태가_저장된다(self):
        r = self._save({'package_form': 'box'})
        self.assertEqual(r.status_code, 200)
        self.label.refresh_from_db()
        self.assertEqual(self.label.package_form, 'box')

    def test_화면이_포장_형태를_실제로_보낸다(self):
        """뷰가 받아도 화면이 안 보내면 그대로다."""
        html = self.client.get(
            reverse('products:product_detail_new',
                    args=[self.label.my_label_id])).content.decode()
        i = html.index('const textFieldMap')
        self.assertIn("'package_form'", html[i:i + 2000])

    def test_안_보낸_칸은_덮지_않는다(self):
        """package_form 을 allowed_fields 에 넣었다고 빈 값으로 밀면 안 된다."""
        self.label.package_form = 'box'
        self.label.save(update_fields=['package_form'])
        self._save({'prdlst_nm': '이름만'})
        self.label.refresh_from_db()
        self.assertEqual(self.label.package_form, 'box')

    # ── 2. 화면과 서버가 같은 표를 본다 ──────────────────────────────────────
    def _share(self, role, status=None, **flags):
        from v1.products.models import (
            ProductMetadata, ProductShare, SharePermission,
        )

        other = User.objects.create_user(
            username='bi_' + role.lower(), password='x',
            email=f'{role.lower()}@example.com')
        share = ProductShare.objects.create(
            label=self.label, created_by=self.owner, recipient_user=other,
            recipient_email=other.email, active_yn=True)
        perm = SharePermission.objects.create(share=share, role_code=role)
        perm.apply_role_defaults(save=False)
        for k, v in flags.items():
            setattr(perm, k, v)
        perm.save()
        if status is not None:
            self.meta.status = status
            self.meta.save(update_fields=['status'])
        return other

    def _can_edit_on_screen(self, user):
        self.client.force_login(user)
        r = self.client.get(reverse('products:product_detail_new',
                                    args=[self.label.my_label_id]))
        return r.context['can_edit']

    def _can_save(self, user):
        self.client.force_login(user)
        return self._save({'prdlst_nm': '고침'}).status_code == 200

    def test_자료_제출자는_화면도_서버도_닫혀_있다(self):
        from v1.products.models import ProductMetadata

        u = self._share('UPLOADER', ProductMetadata.Status.REQUESTING)
        self.assertFalse(self._can_edit_on_screen(u))
        self.assertFalse(self._can_save(u))

    def test_최종_승인자도_마찬가지다(self):
        from v1.products.models import ProductMetadata

        u = self._share('APPROVER', ProductMetadata.Status.PENDING)
        self.assertFalse(self._can_edit_on_screen(u))
        self.assertFalse(self._can_save(u))

    def test_공동_작성자는_둘_다_열려_있다(self):
        from v1.products.models import ProductMetadata

        u = self._share('EDITOR', ProductMetadata.Status.REQUESTING)
        self.assertTrue(self._can_edit_on_screen(u))
        self.assertTrue(self._can_save(u))

    def test_공동_작성자도_제출_뒤에는_둘_다_닫힌다(self):
        from v1.products.models import ProductMetadata

        u = self._share('EDITOR', ProductMetadata.Status.SUBMITTED)
        self.assertFalse(self._can_edit_on_screen(u))
        self.assertFalse(self._can_save(u))

    def test_정보_수정을_켜_주면_그_사람도_고칠_수_있다(self):
        """
        판정 근거는 역할 이름이 아니라 '정보 수정' 플래그다 — 권한 설정에서
        그 칸을 켰다면 화면과 서버가 함께 열려야 한다.
        """
        from v1.products.models import ProductMetadata

        u = self._share('REVIEWER', ProductMetadata.Status.DRAFT,
                        can_edit_label=True)
        self.assertTrue(self._can_edit_on_screen(u))
        self.assertTrue(self._can_save(u))

    def test_주인은_어느_상태에서도_고친다(self):
        from v1.products.models import ProductMetadata

        self.meta.status = ProductMetadata.Status.CONFIRMED
        self.meta.save(update_fields=['status'])
        self.assertTrue(self._can_edit_on_screen(self.owner))
        self.assertTrue(self._can_save(self.owner))

    # ── 3. 실패 이유가 화면에 닿는다 ────────────────────────────────────────
    def test_거절_이유를_화면이_읽는_키로_준다(self):
        from v1.products.models import ProductMetadata

        u = self._share('VIEWER', ProductMetadata.Status.DRAFT)
        self.client.force_login(u)
        r = self._save({'prdlst_nm': '고침'})
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertTrue(body.get('message'), '화면은 data.message 를 읽는다')

    def test_예외_원문을_사용자에게_보내지_않는다(self):
        from unittest.mock import patch

        with patch('v1.products.views.MyLabel.save',
                   side_effect=RuntimeError('SELECT * FROM secret')):
            r = self._save({'prdlst_nm': 'x'})
        blob = r.content.decode()
        self.assertNotIn('secret', blob)
        self.assertNotIn('RuntimeError', blob)


class 코드로_넣은_값도_변경으로_잡힌다(TestCase):
    """
    변경 감지(checkFormChanges)는 폼 요소의 input/change 리스너로만 돈다.
    `el.value = …` 로만 바꾸는 네 곳은 그 리스너를 울리지 않아
      · 이탈 경고가 안 뜨고 (저장 안 한 채 닫으면 값이 사라진다)
      · 탭을 옮길 때 도는 자동 저장(flushBasicInfo)이 통째로 건너뛰어지고
      · 검증 전에 값을 밀어 넣는 일도 건너뛴다

    보관방법 배지로 "냉동" 을 고르고 바로 표시사항 검증을 누르면, 서버는
    저장 전 값을 보고 "보관방법이 비어 있습니다" 라고 답했다. 화면에는 분명히
    냉동이라고 적혀 있는데.

    같은 파일의 applyRawmtrlDisplay 가 이미 올바르게 하고 있었다.
    """

    TAB = 'templates/products/_tab_basic_info.html'

    def _tab(self):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / self.TAB).read_text(encoding='utf-8')

    def _fn(self, text, name):
        """함수 하나의 본문만 잘라 낸다 (다음 최상위 정의 전까지)."""
        import re

        m = re.search(r'\n(?:window\.)?(?:function\s+)?' + re.escape(name)
                      + r'\s*(?:=\s*function\s*)?\(', text)
        self.assertIsNotNone(m, name + ' 를 찾지 못했다')
        rest = text[m.end():]
        nxt = re.search(r'\n(?:function\s+\w|window\.\w+\s*=\s*function|/\* ──)', rest)
        return rest[:nxt.start()] if nxt else rest

    def test_공용_세터가_두_이벤트를_모두_울린다(self):
        body = self._fn(self._tab(), 'setFieldValue')
        self.assertIn("new Event('input'", body)
        self.assertIn("new Event('change'", body)
        self.assertIn('bubbles: true', body)

    def test_보관방법_배지가_공용_세터를_쓴다(self):
        self.assertIn('setFieldValue(', self._fn(self._tab(), 'syncStorageMethod'))

    def test_맞춤항목_json_이_공용_세터를_쓴다(self):
        self.assertIn('setFieldValue(', self._fn(self._tab(), 'syncCustomFieldsJson'))

    def test_알레르기_hidden_이_공용_세터를_쓴다(self):
        text = self._tab()
        i = text.index('// hidden input 업데이트')
        self.assertIn('setFieldValue(', text[i:i + 200])

    def test_복사하기가_공용_세터를_쓴다(self):
        body = self._fn(self._tab(), 'copyVerifiedDataInline')
        self.assertIn('setFieldValue(', body)
        self.assertNotIn('el.value = d[key]', body)

    def test_같은_값이면_변경으로_세지_않는다(self):
        """모든 재계산마다 '변경됨' 이 켜지면 이탈 경고가 늘 뜬다."""
        self.assertIn('if (el.value === value) return;',
                      self._fn(self._tab(), 'setFieldValue'))

    def test_대분류를_바꿔도_인쇄_문구를_지우지_않는다(self):
        """
        식품유형(표시용)은 라벨에 인쇄되고 부기를 손으로 다듬는 칸이다.
        대분류만 확인하려고 잠깐 바꿨다가 되돌려도 적어 둔 문구가 사라졌다.
        표시용을 정하는 규칙은 updatePrdlstDcnm 한 곳뿐이어야 한다 —
        그 함수는 자동 생성된 값만 덮고 사람이 쓴 것은 그대로 둔다.
        """
        text = self._tab()
        self.assertNotIn('_ftPrdlstDcnm', text)
        i = text.index("if (!found && currentVal)")
        block = text[i:i + 1200]
        self.assertIn('updatePrdlstDcnm(false)', block)
        self.assertIn('showSnackbar', block)   # 말없이 비우지 않는다

    def test_죽은_저장_바가_남아_있지_않다(self):
        from pathlib import Path

        from django.conf import settings as dj

        for rel in ('templates/products/product_detail.html',
                    'static/css/products_detail.css'):
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            self.assertNotIn('id="floating-save-bar"', text)
            self.assertNotIn('.floating-save-bar {', text)
        detail = (Path(dj.BASE_DIR) / 'templates/products/product_detail.html'
                  ).read_text(encoding='utf-8')
        self.assertNotIn('function discardChanges(', detail)


class 내_문구가_실패했을_때_말한다(TestCase):
    """
    담기·고치기·빼기 셋 다 `.catch(function () {})` 였고 success:false 도
    안 봤다. 서버는 이유를 제대로 준다 — '문구가 비어 있습니다.'·'없는
    문구입니다.'·'요청을 읽지 못했습니다.' — 전부 버려졌다.

    더 나쁜 쪽은 목록 조회 실패다. draw() 를 못 불러 그 줄이 통째로 비고,
    문구를 담는 [+ 내 문구 추가] 단추까지 사라져 복구할 길이 화면에 없었다.
    """

    JS = 'static/js/label/my_phrases.js'

    def _js(self):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / self.JS).read_text(encoding='utf-8')

    def test_조용히_삼키는_곳이_없다(self):
        self.assertNotIn('.catch(function () {});', self._js())

    def test_목록을_못_읽어도_담는_자리는_남는다(self):
        js = self._js()
        i = js.index('function load(')
        block = js[i:js.index('function draw(')]
        self.assertIn('draw(box, field, [], [], opts)', block)

    def test_거절_이유를_그대로_보여_준다(self):
        js = self._js()
        i = js.index('function sendThenReload(')
        block = js[i:i + 600]
        self.assertIn('data.error', block)
        self.assertIn('say(', block)


class 번호검증_복사가_검증의_기준값까지_채운다(TestCase):
    """
    품목보고번호 도움말은 "[복사하기] 로 제품명·**식품유형**·원재료명·
    제조사·용기포장재질이 한 번에 채워집니다" 라고 적어 두었다.

    실제로 채워지던 「식품유형」은 인쇄용(prdlst_dcnm)뿐이고, **검증이 규칙을
    고르는 키인 소분류(food_type)는 그대로 빈 칸**이었다. 소분류가 비면 그
    검사는 통과한 것이 아니라 안 본 것이다 — 화면의 도움말도 그렇게 적어
    놓았는데, 사용자는 복사가 다 해 준 줄 알고 넘어간다.
    """

    def setUp(self):
        from v1.label.models import FoodItem
        from v1.products.models import FoodType

        self.user = User.objects.create_user(username='vfy', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='검증', delete_YN='N')
        FoodType.objects.create(
            food_group='과자류', food_type='과자', prdlst_dcnm='과자')
        FoodItem.objects.create(
            prdlst_report_no='19990101010101', prdlst_nm='초코과자',
            prdlst_dcnm='과자', bssh_nm='○○식품', frmlc_mtrqlt='폴리프로필렌')

    def test_응답이_소분류를_함께_준다(self):
        r = self.client.post(
            reverse('label:verify_report_no'),
            data=json.dumps({'label_id': self.label.my_label_id,
                             'prdlst_report_no': '19990101010101'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['product_data']['food_type'], '과자')

    def test_짝을_못_찾으면_빈_문자열이다(self):
        """없는 값을 억지로 넣으면 select 가 조용히 안 맞는 값을 갖는다."""
        from v1.label.views import _food_type_for_dcnm

        self.assertEqual(_food_type_for_dcnm('있을 리 없는 유형'), '')
        self.assertEqual(_food_type_for_dcnm(''), '')
        self.assertEqual(_food_type_for_dcnm(None), '')

    def test_화면이_그_값을_쓴다(self):
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                ).read_text(encoding='utf-8')
        i = text.index('function copyVerifiedDataInline')
        block = text[i:i + 2500]
        self.assertIn('d.food_type', block)
        self.assertIn('syncFoodGroupFromType', block)


class 문서_타입_화면이_말한_일을_할_수_있다(TestCase):
    """
    이 화면은 대놓고 "문서 타입은 관리자 페이지에서 등록할 수 있습니다" 라고
    안내하고 [관리자 페이지로 이동] 을 준다. 그 링크가 **404** 였다.
    두 군데가 동시에 틀렸다 —
      · admin 은 `/admin/` 이 아니라 `/lbdt-manage/` 에 있다(URL 난독화)
      · DocumentType 은 `documents` 가 아니라 `products` 앱이다
    다른 길은 화면에 없으니, 시키는 일을 할 방법이 없었다.

    거기에 둘이 더 겹쳐 있었다.
      · 뷰가 `active_yn=True` 로만 뽑는데 화면은 활성/비활성 배지를 그렸다 —
        '비활성' 배지는 도달할 수 없고, 비활성을 찾으러 온 관리자는
        "하나도 없다" 로 잘못 읽는다
      · 이 화면으로 링크하는 곳이 저장소에 0곳이었다
    """

    def setUp(self):
        from v1.products.models import DocumentType

        self.staff = User.objects.create_user(
            username='dtstaff', password='x', is_staff=True)
        self.plain = User.objects.create_user(username='dtplain', password='x')
        DocumentType.objects.create(
            type_name='성적서', type_code='SPEC', active_yn=True, display_order=1)
        DocumentType.objects.create(
            type_name='옛 서식', type_code='OLD', active_yn=False, display_order=2)

    def test_관리자_페이지_링크가_살아_있다(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('products:document_type_list'))
        self.assertEqual(r.status_code, 200)
        url = r.context['admin_url']
        self.assertNotIn('/admin/', url)
        self.assertIn('documenttype', url)

        # 진짜로 열리는지 본다. 이 저장소는 403 을 404 로 위장하므로
        # (common.views.custom_403) 상태 코드만으로는 "주소가 없다" 와
        # "권한이 없다" 를 구분할 수 없다 — 권한을 주고 200 을 확인한다.
        from django.contrib.auth.models import Permission

        self.staff.user_permissions.add(
            Permission.objects.get(codename='view_documenttype'))
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_주소를_손으로_적어_두지_않았다(self):
        from pathlib import Path

        from django.conf import settings as dj

        for rel in ('templates/products/documents/type_list.html',
                    'products/views.py'):
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            self.assertNotIn('/admin/documents/documenttype', text)

    def test_비활성_타입도_보인다(self):
        self.client.force_login(self.staff)
        html = self.client.get(
            reverse('products:document_type_list')).content.decode()
        self.assertIn('옛 서식', html)
        self.assertIn('비활성', html)
        self.assertIn('성적서', html)

    def test_활성_수를_따로_말한다(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('products:document_type_list'))
        self.assertEqual(len(r.context['types']), 2)
        self.assertEqual(r.context['active_count'], 1)

    def test_staff_가_아니면_막힌다(self):
        """
        예전에는 **없는 주소로 리다이렉트**하면서 경고를 세션에 남겼다.
        404 페이지는 messages 를 그리지 않으므로, 그 경고는 나중에 엉뚱한
        화면에서 튀어나왔다.

        지금은 그 자리에서 막는다. 이 저장소는 403 을 404 로 위장하므로
        (common.views.custom_403) 화면에 보이는 것은 404 다 — 확인할 것은
        **리다이렉트가 아니라는 것**과 **떠도는 경고를 남기지 않는다는 것**이다.
        """
        self.client.force_login(self.plain)
        r = self.client.get(reverse('products:document_type_list'))
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(r.status_code, (301, 302))

        from django.contrib.messages import get_messages

        self.assertEqual(list(get_messages(r.wsgi_request)), [])

    def test_이_화면으로_들어올_길이_있다(self):
        """만들어 두고 아무도 링크하지 않으면 고쳐도 아무도 만나지 못한다."""
        self.client.force_login(self.staff)
        html = self.client.get('/home/').content.decode()
        self.assertIn(reverse('products:document_type_list'), html)

    def test_일반_사용자에게는_그_링크가_안_보인다(self):
        self.client.force_login(self.plain)
        html = self.client.get('/home/').content.decode()
        self.assertNotIn(reverse('products:document_type_list'), html)

    def test_admin_으로만_리다이렉트하던_죽은_뷰를_걷어냈다(self):
        from django.urls import NoReverseMatch

        for name in ('products:document_type_create',
                     'products:document_type_update'):
            with self.assertRaises(NoReverseMatch):
                reverse(name, args=[1])


class AI_문서_검토_저장이_실제로_된다(TestCase):
    """
    화면은 `FormData`(multipart)를 보내는데 뷰는 `json.loads(request.body)`
    를 한다 — **저장이 100% 실패**했다. 게다가 뷰는 error 키로 주는데 화면은
    `data.message` 를 읽어 "저장 실패: 오류" 한 줄만 떴다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='aiu', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='AI', delete_YN='N')
        dt = DocumentType.objects.create(type_name='성적서', type_code='SPEC')
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dt, active_yn=True,
            metadata={'ai_status': 'DONE', 'extracted_data': {'a': '1'}})

    def _url(self):
        return reverse('products:document_ai_review_save',
                       args=[self.doc.document_id])

    def test_json_으로_보내면_저장된다(self):
        from v1.products.models import ProductDocument

        r = self.client.post(
            self._url(),
            data=json.dumps({'extracted_data': {'a': '2', 'b': '3'}}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])
        doc = ProductDocument.objects.get(pk=self.doc.pk)
        self.assertEqual(doc.metadata['extracted_data'], {'a': '2', 'b': '3'})

    def test_화면이_json_으로_보낸다(self):
        """FormData 로 되돌아가면 다시 100% 실패한다."""
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/document_ai_review_v2.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        i = text.index("getElementById('aiReviewForm')")
        block = text[i:i + 1800]
        self.assertIn("'Content-Type': 'application/json'", block)
        self.assertIn('extracted_data', block)
        self.assertNotIn('new FormData(', block)

    def test_거절_이유를_화면이_읽는_키로_준다(self):
        r = self.client.post(self._url(), data='not json',
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json().get('error'))

    def test_보낼_것이_없으면_거절한다(self):
        r = self.client.post(self._url(), data=json.dumps({}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_남의_문서는_못_고친다(self):
        other = User.objects.create_user(username='aio', password='x')
        self.client.force_login(other)
        r = self.client.post(self._url(),
                             data=json.dumps({'extracted_data': {'a': 'x'}}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 404)

    def test_렌더되지_않는_템플릿을_걷어냈다(self):
        from pathlib import Path

        from django.conf import settings as dj

        for rel in ('templates/products/document_ai_review.html',
                    'templates/products/documents/document_ai_review.html'):
            self.assertFalse((Path(dj.BASE_DIR) / rel).exists(), rel)


class 문서_상세가_막다른_길이_아니다(TestCase):
    """
    · [문서 삭제] 가 평범한 <form> 으로 **JSON API** 에 보냈다. 브라우저는
      응답을 그대로 그리므로, 지우고 나면 {"success": true} 만 적힌 흰
      화면에 남았다 — 돌아갈 링크도 없다.
    · 삭제는 soft delete 인데 상세 뷰가 active_yn 을 안 봐서, 지운 문서의
      주소를 그대로 열 수 있었다. 목록에 없는 문서가 상세로는 멀쩡히 보이고
      [다운로드] 도 눌렸다.
    · 아이콘이 Font Awesome 인데 base_v2 는 Bootstrap Icons 만 싣는다 —
      빈 네모만 보인다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='ddu', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='문서', delete_YN='N')
        dt = DocumentType.objects.create(type_name='성적서', type_code='SPEC')
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dt, active_yn=True,
            original_filename='a.pdf')

    def test_지운_문서는_안_열린다(self):
        url = reverse('products:document_detail', args=[self.doc.document_id])
        self.assertEqual(self.client.get(url).status_code, 200)

        self.doc.active_yn = False
        self.doc.save(update_fields=['active_yn'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_삭제가_JSON_화면으로_가지_않는다(self):
        html = self.client.get(
            reverse('products:document_detail',
                    args=[self.doc.document_id])).content.decode()
        self.assertIn('id="docDeleteBtn"', html)
        # <form> 이 API 로 곧장 보내던 자리가 남아 있으면 안 된다
        self.assertNotIn('document_delete_api', html.split('docDeleteBtn')[0])

    def test_아이콘이_bootstrap_icons_다(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        for rel in ('templates/products/documents/document_detail.html',
                    'templates/products/documents/expired_documents.html',
                    'templates/products/documents/expiring_documents.html'):
            text = (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')
            self.assertEqual(re.findall(r'fa[srlb]* fa-[a-z0-9-]*', text), [], rel)


class 배합_저장이_실패해도_임시저장은_살아_있다(TestCase):
    """
    · `draftSaveDisabled` 를 저장 시작에 켜기만 하고 되돌리는 곳이 없었다 —
      한 번 실패하면 그 뒤로 무엇을 고쳐도 임시저장이 안 돌아, 새로고침·
      탭 닫기에 그대로 날아갔다. 저장이 실패한 뒤야말로 임시저장이 가장
      필요한 때다.
    · 저장 성공 뒤 loadBOMData() 를 안 불렀다. 서버는 저장할 때마다 옛 행을
      active_yn=False 로 눕히고 새로 만드는데, 화면은 죽은 bom_id 를 계속
      들고 다음 저장에 그대로 보냈다.
    """

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_실패하면_임시저장을_되살린다(self):
        js = self._js()
        i = js.index('async function saveData()')
        block = js[i:i + 6000]
        self.assertIn('finally {', block)
        self.assertIn('draftSaveDisabled = saved;', block)

    def test_저장_뒤_서버에서_다시_읽는다(self):
        js = self._js()
        i = js.index('async function saveData()')
        block = js[i:i + 6000]
        self.assertIn('await loadBOMData();', block)


class 배합_영양_요약이_지금_표를_본다(TestCase):
    """
    요약이 표의 배합비를 함께 보내려 했는데, 값을 **없는 자리에서** 꺼냈다 —
    bom_id 는 `row._meta.bom_id` 에 있고 배합비 칸 이름은 `mixing_ratio` 다.
    그래서 목록이 늘 비었고 서버는 저장된 옛 배합으로 계산했다. 표를 아무리
    고쳐도 요약이 그대로였다.
    """

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/_bom_nutrition_summary.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_meta_에서_bom_id_를_꺼낸다(self):
        js = self._js()
        i = js.index('function currentItems(')
        block = js[i:i + 1000]
        self.assertIn('row._meta && row._meta.bom_id', block)
        self.assertIn('row.mixing_ratio', block)

    def test_csrf_를_못_찾아_막히지_않는다(self):
        js = self._js()
        i = js.index('function csrf(')
        block = js[i:i + 600]
        self.assertIn('CSRF_TOKEN', block)
        self.assertIn('csrftoken=', block)


class 영양성분_편집기가_지금_값으로_판정한다(TestCase):
    """
    · 고열량·저영양 판정을 화면 열고 400ms 뒤 **딱 한 번** 불렀다. 그 뒤로는
      값을 아무리 고쳐도 그때의 판정이 그대로 남는다 — 결과를 보여 주는
      자리가 옛 값을 말하면 안 된다.
    · 불러오기가 실패하면 응답 **본문**을 error.message 에 담아 스낵바에
      띄웠다. 서버가 HTML 오류 페이지를 주면 그 태그가 통째로 흘렀다.
    """

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/nutrition_editor.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_값이_바뀌면_다시_판정한다(self):
        js = self._js()
        i = js.index('function calculateAndPreview()')
        self.assertIn('refreshHiengPanel()', js[i:i + 1200])

    def test_판정_기준이_바뀌어도_다시_한다(self):
        js = self._js()
        self.assertIn("['serving_reference', 'hieng_kind'].forEach", js)

    def test_응답_본문을_스낵바로_흘리지_않는다(self):
        js = self._js()
        i = js.index('const errorText = await response.text()')
        block = js[i:i + 500]
        self.assertIn('console.error(', block)
        self.assertNotIn('${errorText}', block)


class 최근_사용_API_를_걷어냈다(TestCase):
    """
    `/label/api/recent-usage/` 는 호출자가 0이었다 — 화면은 localStorage
    (phrase_autocomplete.js)를 쓴다. 고쳐도 아무 화면이 안 바뀐다.
    """

    def test_주소가_없다(self):
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse('label:recent_usage_api')


class BOM_적용이_죽은_줄에_매달리지_않는다(TestCase):
    """
    `get_or_create(parent_label, ingredient_name)` 이 active_yn 을 안 봤다.
    BOM 을 한 번이라도 저장하면 서버가 옛 줄을 전부 눕히는데(bom_save_api),
    그 죽은 줄에 걸려 "이미 있다" 로 넘어간다. 화면은 **"0종 추가"** 라고
    답하고 BOM 은 그대로 비어 있다 — 목록은 활성만 보여 주기 때문이다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='apu', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='적용', delete_YN='N')
        dt = DocumentType.objects.create(type_name='성적서', type_code='SPEC')
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dt, active_yn=True,
            metadata={'extracted_data': {'raw_materials': ['정제수', '설탕']}})

    def _apply(self):
        return self.client.post(
            reverse('products:document_ai_apply_to_bom',
                    args=[self.doc.document_id]),
            data=json.dumps({}), content_type='application/json')

    def _live(self):
        from v1.bom.models import ProductBOM

        return set(ProductBOM.objects
                   .filter(parent_label=self.label, active_yn=True)
                   .values_list('ingredient_name', flat=True))

    def test_처음_적용하면_들어간다(self):
        r = self._apply()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['created'], 2)
        self.assertEqual(self._live(), {'정제수', '설탕'})

    def test_저장으로_눕힌_뒤에도_다시_들어간다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        # bom_save_api 가 저장할 때마다 하는 일
        ProductBOM.objects.filter(parent_label=self.label).update(active_yn=False)
        self.assertEqual(self._live(), set())

        body = self._apply().json()
        self.assertEqual(body['created'], 2)
        self.assertEqual(self._live(), {'정제수', '설탕'})

    def test_되살릴_뿐_사본을_만들지_않는다(self):
        from v1.bom.models import ProductBOM

        self._apply()
        ProductBOM.objects.filter(parent_label=self.label).update(active_yn=False)
        self._apply()
        self.assertEqual(
            ProductBOM.objects.filter(parent_label=self.label).count(), 2)

    def test_이미_살아_있으면_또_넣지_않는다(self):
        self._apply()
        self.assertEqual(self._apply().json()['created'], 0)
        self.assertEqual(self._live(), {'정제수', '설탕'})
from v1.label.models import MyLabel


class 협력사가_붙인_파일이_사라지지_않는다(TestCase):
    """
    범용 업로드칸은 `multiple` 이라 한 번에 여러 개를 고를 수 있다. 그런데
    서버가 `request.FILES.items()` 로 돌았다 — `MultiValueDict.items()` 는
    키마다 **마지막 값 하나만** 돌려준다. 세 개를 붙이면 하나만 저장되고
    나머지 둘은 조용히 사라진다.

    화면은 더 나쁘게 굴었다. `showFileInfo` 가 고른 파일 **전부**를 초록
    체크와 함께 그려 주고, 제출하면 "서류 제출이 완료되었습니다!" 라고
    말한다. 협력사도 요청자도 두 개가 없어진 것을 알 수 없다.
    """

    def setUp(self):
        from datetime import timedelta
        from unittest.mock import patch

        from v1.products.models import DocumentRequest, DocumentType

        # Vision AI 는 백그라운드 스레드로 도는데 시험 DB(sqlite)를 잠근다
        p = patch('v1.products.services.vision_service.process_document_vision_async',
                  lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)

        self.owner = User.objects.create_user(username='vown', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='협력', delete_YN='N')
        DocumentType.objects.create(type_name='성적서', type_code='SPEC',
                                    active_yn=True, display_order=1)
        self.dr = DocumentRequest.objects.create(
            requester=self.owner, linked_label=self.label,
            recipient_email='v@example.com', recipient_name='협력사',
            due_date=timezone.now().date() + timedelta(days=7),
            status=DocumentRequest.STATUS_PENDING)

    def _url(self):
        return reverse('vendor:upload_submit', args=[self.dr.upload_token])

    def _file(self, name):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, b'%PDF-1.4 body', 'application/pdf')

    def test_한_칸에_여러_개를_붙이면_다_저장된다(self):
        from v1.products.models import DocumentSubmission

        r = self.client.post(self._url(), {
            'vendor_name': '협력사',
            'file_0': [self._file('a.pdf'), self._file('b.pdf'), self._file('c.pdf')],
        })
        self.assertIn(r.status_code, (200, 302))
        names = set(DocumentSubmission.objects
                    .filter(request=self.dr)
                    .values_list('original_filename', flat=True))
        self.assertEqual(names, {'a.pdf', 'b.pdf', 'c.pdf'})

    def test_한_개만_붙여도_그대로_저장된다(self):
        from v1.products.models import DocumentSubmission

        self.client.post(self._url(), {
            'vendor_name': '협력사', 'file_0': self._file('only.pdf')})
        self.assertEqual(
            DocumentSubmission.objects.filter(request=self.dr).count(), 1)


class 협력사_업로드가_화면이_약속한_한도를_지킨다(TestCase):
    """
    화면은 "PDF, JPG, PNG, DOCX (최대 20MB)" 라고 적어 두었는데 **서버에는
    크기 검사도 확장자 검사도 없었다.** 저장소 표준(common/uploads.py)의
    30MB 상한도, 요청자의 저장 할당량 검사도 부르지 않았다.

    로그인도 안 한 협력사가 요청자의 요금제 한도를 얼마든지 넘길 수 있었고,
    `.html`·`.svg` 도 그대로 받았다 — 그 파일을 여는 사람은 바로 요청자다.
    """

    def setUp(self):
        from datetime import timedelta
        from unittest.mock import patch

        from v1.products.models import DocumentRequest, DocumentType

        p = patch('v1.products.services.vision_service.process_document_vision_async',
                  lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)

        self.owner = User.objects.create_user(username='vq', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='한도', delete_YN='N')
        DocumentType.objects.create(type_name='성적서', type_code='SPEC',
                                    active_yn=True, display_order=1)
        self.dr = DocumentRequest.objects.create(
            requester=self.owner, linked_label=self.label,
            recipient_email='v@example.com',
            due_date=timezone.now().date() + timedelta(days=7),
            status=DocumentRequest.STATUS_PENDING)

    def _post(self, name, size=64, content_type='application/pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post(
            reverse('vendor:upload_submit', args=[self.dr.upload_token]),
            {'vendor_name': '협력사',
             'file_0': SimpleUploadedFile(name, b'x' * size, content_type)})

    def _saved(self):
        from v1.products.models import DocumentSubmission

        return DocumentSubmission.objects.filter(request=self.dr).count()

    def test_너무_큰_파일은_막는다(self):
        from v1.common.uploads import MAX_UPLOAD_MB

        self._post('big.pdf', size=(MAX_UPLOAD_MB * 1024 * 1024) + 1)
        self.assertEqual(self._saved(), 0)

    def test_허용하지_않는_확장자는_막는다(self):
        for name in ('x.html', 'x.svg', 'x.exe'):
            self._post(name)
        self.assertEqual(self._saved(), 0)

    def test_허용한_확장자는_받는다(self):
        self._post('ok.pdf')
        self.assertEqual(self._saved(), 1)

    def test_막았으면_왜_막았는지_말한다(self):
        r = self._post('x.exe')
        self.assertEqual(r.status_code, 200)
        self.assertIn('확장자', r.content.decode())


class 다른_계정으로_로그인_단추가_실제로_로그아웃한다(TestCase):
    """
    초대 착지점의 「다른 계정으로 로그인」이 `<a href>` 였다. GET 이므로
    `logout_view` 의 POST 분기를 타지 않고 **로그아웃 없이** 대시보드로
    떨어진다. 엉뚱한 계정으로 로그인한 채, 로그아웃됐다는 말도 없이.

    `wrong_account` 분기가 존재하는 이유가 바로 이 상황을 풀어 주려는
    것인데, 유일한 해결 단추가 아무 일도 안 했다.
    """

    def setUp(self):
        from datetime import timedelta

        from v1.products.models import ProductShare

        self.owner = User.objects.create_user(username='iown', password='x')
        self.invited = 'invited@example.com'
        self.wrong = User.objects.create_user(
            username='wrong@example.com', email='wrong@example.com', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='초대', delete_YN='N')
        self.share = ProductShare.objects.create(
            label=self.label, created_by=self.owner,
            recipient_email=self.invited, active_yn=True,
            share_mode='PRIVATE',
            share_end_date=timezone.now() + timedelta(days=7))

    def _landing(self):
        return self.client.get(
            reverse('products:share_invite_landing',
                    args=[self.share.public_token]))

    def test_엉뚱한_계정이면_그렇다고_말한다(self):
        self.client.force_login(self.wrong)
        r = self._landing()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['wrong_account'])

    def test_그_단추가_POST_폼이다(self):
        """<a href> 는 GET 이라 logout_view 의 POST 분기를 안 탄다."""
        self.client.force_login(self.wrong)
        html = self._landing().content.decode()
        i = html.index('다른 계정으로 로그인')
        block = html[max(0, i - 600):i + 100]
        self.assertIn('<form', block)
        self.assertIn('method="post"', block)
        self.assertIn('csrfmiddlewaretoken', block)

    def test_눌렀을_때_정말_로그아웃된다(self):
        self.client.force_login(self.wrong)
        self.client.post(reverse('user_management:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_GET_으로는_로그아웃되지_않는다(self):
        """CSRF 보호를 GET 으로 우회하지 못하게 — 그 성질은 그대로 둔다."""
        self.client.force_login(self.wrong)
        self.client.get(reverse('user_management:logout'))
        self.assertIn('_auth_user_id', self.client.session)


class 배합표가_화면_좌표와_데이터_좌표를_섞지_않는다(TestCase):
    """
    Handsontable 에서 `getSourceDataAtRow` 는 **물리(데이터) 좌표**를 받고,
    `setDataAtRowProp`·`getCell`·`afterChange`·`afterSelectionEnd` 는 전부
    **화면 좌표**를 준다. 이 표는 `manualRowMove` 가 켜져 있어 그 둘이 갈라진다.

    예전에는 같은 정수를 양쪽에 그대로 넣었다. 특히 `setRowProp` 이 나빴다 —
    표에 칸이 있는 값은 **옳은 줄**로, `_meta`(bom_id·source_type·source_id)는
    **다른 줄**로 갔다. 저장은 행 객체의 `_meta.bom_id` 를 그대로 보내므로,
    잘못 붙은 번호로 **엉뚱한 DB 행을 덮고**, 서버는 그 행의 source_ingredient
    로 내 원료 마스터를 역동기화하고, 같은 원료를 쓰는 **다른 제품의 BOM
    까지** 함께 고친다.
    """

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_데이터를_직접_읽는_곳이_한_곳뿐이다(self):
        js = self._js()
        # 변환을 거치지 않은 raw 접근이 남아 있으면 다시 갈라진다
        self.assertEqual(js.count('getSourceDataAtRow('), 1)
        self.assertIn('function rowObjectAt(', js)

    def test_그_한_곳이_좌표를_바꾼다(self):
        js = self._js()
        i = js.index('function rowObjectAt(')
        block = js[i:i + 500]
        self.assertIn('toPhysicalRow', block)

    def test_자기를_다시_부르지_않는다(self):
        """치환하다 무한 재귀를 만들기 쉬운 자리다."""
        js = self._js()
        i = js.index('function rowObjectAt(')
        block = js[i:js.index('const gridColumnProps')]
        self.assertNotIn('return rowObjectAt(', block)

    def test_화면에_보이는_순서로_저장한다(self):
        js = self._js()
        i = js.index('async function saveData()')
        block = js[i:i + 1200]
        self.assertIn('rowObjectAt(index)', block)
        self.assertNotIn('sourceData[index]', block)


class 표에서_친_값이_저장_때_되돌아가지_않는다(TestCase):
    """
    알레르기·GMO·품목보고번호·요약구분은 **표에도 칸이 있고 패널에도 숨은
    칸이 있다.** 그런데 표를 직접 고쳐도 패널은 갱신되지 않았다.

    그 뒤 줄을 옮기거나 [저장하기] 를 누르면 `syncContextPanelToRow()` 가
    **패널의 옛 값을 표에 도로 쓴다** — 방금 친 값이 사라진다. saveData 의
    첫 줄이 바로 그 함수라 **저장 경로에서도 그대로 소실됐다.**
    """

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'templates/products/bom_detail.html'
                ).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_표를_고치면_패널이_따라온다(self):
        js = self._js()
        i = js.index('afterChange: function(changes, source)')
        block = js[i:i + 1600]
        self.assertIn('PANEL_MIRRORED[prop]', block)
        self.assertIn('currentRowIndex', block)

    def test_두_자리를_가진_값이_명부에_있다(self):
        js = self._js()
        i = js.index('const PANEL_MIRRORED')
        block = js[i:i + 400]
        for prop in ('allergens', 'gmo', 'report_no', 'summary_type'):
            self.assertIn(prop, block)

    def test_그_넷은_표에도_칸이_있다(self):
        """표에 칸이 없으면 애초에 덮어쓸 일이 없다 — 명부가 맞는지 본다."""
        js = self._js()
        i = js.index('const gridColumnProps')
        grid = js[i:i + 400]
        for prop in ('allergens', 'gmo', 'report_no'):
            self.assertIn(prop, grid)


class 성적서_판독이_서버에서_죽지_않는다(TestCase):
    """
    영양성분 A등급을 만드는 유일한 경로가 **양쪽 다** 막혀 있었다.

    · 화면: 파일 고르개를 만들자마자 `load()` 의 `innerHTML` 이 지웠다 (고침)
    · 서버: `quota.consume(...)` 을 부르는데 **그런 함수가 없다.** 게다가
      `quota` 라는 이름 자체가 그 함수 스코프에 없었다 — `v1/products/views.py`
      는 `quota` 를 모듈 최상단이 아니라 **다른 함수 안에서만** 들여왔다.
      그래서 두 경로 모두 `NameError` 로 500 이었다.

    화면을 되살린 뒤에야 서버 쪽이 드러났다. 되살린 단추가 500 에 닿는
    상태였으므로 여기서 함께 잠근다.
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from v1.label.models import MyIngredient
        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='spec', password='pw12345!')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='성적서제품', delete_YN='N')
        dtype = DocumentType.objects.create(
            type_name='자가품질검사성적서', type_code='SPEC',
            active_yn=True, display_order=1)
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dtype,
            file=SimpleUploadedFile('spec.pdf', b'%PDF-1.4 body', 'application/pdf'),
            original_filename='spec.pdf', file_size=13, uploaded_by=self.user)
        self.ingredient = MyIngredient.objects.create(
            user_id=self.user, prdlst_nm='성적서원료', delete_YN='N')

    def _fake_read(self):
        from unittest.mock import patch

        return patch(
            'v1.label.services.spec_nutrition.read',
            return_value={'values': {'calories': 100}, 'basis_amount': 100,
                          'basis_unit': 'g', 'text': '열량 100kcal', 'error': ''})

    def test_문서함_성적서_판독이_200_이다(self):
        with self._fake_read():
            r = self.client.post(reverse('products:document_spec_nutrition',
                                         args=[self.doc.pk]))
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(r.json()['success'])

    def test_원료_성적서_판독이_200_이다(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with self._fake_read():
            r = self.client.post(
                reverse('label:ingredient_spec_nutrition', args=[self.ingredient.pk]),
                {'file': SimpleUploadedFile('s.pdf', b'%PDF-1.4', 'application/pdf')})
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_한도를_넘기면_429_와_한국어_안내를_준다(self):
        from unittest.mock import patch

        with patch('v1.common.quota.limit_for', return_value=0):
            with self._fake_read():
                r = self.client.post(reverse('products:document_spec_nutrition',
                                             args=[self.doc.pk]))
        self.assertEqual(r.status_code, 429)
        self.assertIn('한도', r.json()['error'])

    def test_판독이_한도를_실제로_깎는다(self):
        """`consume` 은 없는 함수였다 — 깎는지 실제로 확인한다."""
        from v1.common import quota

        before = quota.used(self.user, 'ocr_label')
        with self._fake_read():
            self.client.post(reverse('products:document_spec_nutrition',
                                     args=[self.doc.pk]))
        self.assertEqual(quota.used(self.user, 'ocr_label'), before + 1)


class 고정_서류_불러오기가_슬롯을_잇는다(TestCase):
    """
    `auto_slot.status = DocumentSlot.SlotStatus.ACTIVE` — **`ACTIVE` 라는 값이
    없다.** 선택지는 EMPTY/VALID/EXPIRING/EXPIRED 넷뿐이라 `AttributeError`
    가 나고, 그 자리는 try 밖이라 그대로 500 이다.

    그런데 `ProductDocument` 는 이미 만들어진 **뒤**라 파일은 들어가 있다.
    사용자는 "일부 서류를 불러오지 못했습니다" 를 보고 다시 누르고,
    **중복 문서가 쌓인다.**

    상태는 손으로 정할 값이 아니다 — 만료일에서 나온다(`update_status`).
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from v1.products.models import DocumentSlot, DocumentType
        from v1.user_management.models import CompanyDocument

        self.user = User.objects.create_user(username='imp', password='pw12345!')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='불러오기제품', delete_YN='N')
        self.dtype = DocumentType.objects.create(
            type_name='HACCP인증서', type_code='HACCP',
            active_yn=True, display_order=1)
        self.slot = DocumentSlot.objects.create(
            label=self.label, document_type=self.dtype, hidden_yn=False)
        self.company_doc = CompanyDocument.objects.create(
            user=self.user, doc_type='haccp', doc_name='HACCP',
            doc_file=SimpleUploadedFile('haccp.pdf', b'%PDF-1.4 x', 'application/pdf'))

    def _import(self):
        return self.client.post(
            reverse('products:company_document_import_api', args=[self.label.my_label_id]),
            {'company_document_id': self.company_doc.pk,
             'document_type_id': self.dtype.type_id})

    def test_불러오면_200_이고_슬롯이_이어진다(self):
        from v1.products.models import DocumentSlot

        r = self._import()
        self.assertEqual(r.status_code, 200, r.content[:300])
        slot = DocumentSlot.objects.get(pk=self.slot.pk)
        self.assertIsNotNone(slot.current_document)

    def test_슬롯_상태가_선택지_안의_값이다(self):
        from v1.products.models import DocumentSlot

        self._import()
        slot = DocumentSlot.objects.get(pk=self.slot.pk)
        self.assertIn(slot.status, dict(DocumentSlot.SlotStatus.choices))

    def test_한_번_불러오면_문서가_하나만_생긴다(self):
        from v1.products.models import ProductDocument

        self._import()
        self.assertEqual(
            ProductDocument.objects.filter(label=self.label).count(), 1)


class 자료_요청_제출이_협력사_경로와_같은_문을_지난다(TestCase):
    """
    비로그인 협력사 경로(`vendor_views`)에는 크기·확장자·할당량 검사를
    넣었는데, **로그인한 수신자가 연락처 화면에서 내는 같은 기능**에는
    하나도 없었다.

    `.html`·`.svg` 는 미디어가 `Content-Disposition` 없이 내려주므로 같은
    오리진에서 inline 으로 실행된다 — 그 파일을 여는 사람은 바로 요청자다.

    그리고 두 가지가 더 있었다.
    · `request.FILES.items()` 는 키마다 **마지막 하나만** 준다 — 한 칸에
      여러 개를 붙이면 나머지가 조용히 사라진다(협력사 쪽에서 고친 것과 같은 꼴)
    · 제품 문서함 복사가 그 요청의 **활성 제출 전체**를 돌아, 두 번째 제출 때
      첫 번째 파일이 한 번 더 들어갔다
    """

    def setUp(self):
        from datetime import timedelta

        from v1.products.models import DocumentRequest, DocumentType

        self.requester = User.objects.create_user(username='req', password='x')
        self.sender = User.objects.create_user(
            username='snd@example.com', email='snd@example.com', password='x')
        self.client.force_login(self.sender)
        self.label = MyLabel.objects.create(
            user_id=self.requester, my_label_name='요청제품', delete_YN='N')
        DocumentType.objects.create(type_name='성적서', type_code='SPEC',
                                    active_yn=True, display_order=1)
        self.dr = DocumentRequest.objects.create(
            requester=self.requester, linked_label=self.label,
            recipient_email='snd@example.com',
            due_date=timezone.now().date() + timedelta(days=7),
            status=DocumentRequest.STATUS_PENDING)

    def _file(self, name, size=64):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, b'x' * size, 'application/pdf')

    def _submit(self, payload):
        return self.client.post(
            reverse('products:doc_request_submit', args=[self.dr.request_id]), payload)

    def _subs(self):
        from v1.products.models import DocumentSubmission

        return DocumentSubmission.objects.filter(request=self.dr)

    def test_실행되는_확장자는_막는다(self):
        r = self._submit({'성적서': self._file('x.html')})
        self.assertEqual(r.status_code, 400)
        self.assertIn('확장자', r.json()['error'])
        self.assertEqual(self._subs().count(), 0)

    def test_너무_큰_파일도_막는다(self):
        from v1.common.uploads import MAX_UPLOAD_MB

        r = self._submit({'성적서': self._file(
            'big.pdf', size=(MAX_UPLOAD_MB * 1024 * 1024) + 1)})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self._subs().count(), 0)

    def test_한_칸에_여러_개를_붙이면_다_저장된다(self):
        self._submit({'성적서': [self._file('a.pdf'),
                                 self._file('b.pdf'),
                                 self._file('c.pdf')]})
        names = set(self._subs().values_list('original_filename', flat=True))
        self.assertEqual(names, {'a.pdf', 'b.pdf', 'c.pdf'})

    def test_다시_제출해도_앞의_것이_또_들어가지_않는다(self):
        from v1.products.models import ProductDocument

        self._submit({'성적서': self._file('first.pdf')})
        self._submit({'성적서': self._file('second.pdf')})
        names = sorted(ProductDocument.objects
                       .filter(label=self.label)
                       .values_list('original_filename', flat=True))
        self.assertEqual(names, ['first.pdf', 'second.pdf'])


class 무기한을_고르면_만료일이_되살아나지_않는다(TestCase):
    """
    `ProductDocument.save()` 는 만료일이 비어 있으면 문서 종류의 기본
    유효기간을 **도로 채운다**(성적서 180일·원산지증명 365일·HACCP 1095일 …).
    그 자동 채움을 끄는 표시가 `metadata['expiry_unlimited']` 인데
    **업로드 경로만** 그것을 세웠다.

    편집 패널의 [무기한] → [저장] 은 `expiry_date: null` 을 보내고 뷰는
    `expiry_date = None` 후 `save()` 한다 → 그 자리에서 기본값이 다시 붙는다.
    화면에는 "저장했습니다" 가 뜨고 새로고침되는데 만료일은 그대로다.
    몇 번을 해도 같고, 왜 안 되는지 알 방법이 없다.
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from v1.products.models import DocumentType, ProductDocument

        self.user = User.objects.create_user(username='unlim', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='무기한', delete_YN='N')
        self.dtype = DocumentType.objects.create(
            type_name='자가품질검사성적서', type_code='SPEC', active_yn=True,
            display_order=1, default_validity_days=180)
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=self.dtype,
            file=SimpleUploadedFile('a.pdf', b'%PDF-1.4', 'application/pdf'),
            original_filename='a.pdf', file_size=8, uploaded_by=self.user)

    def _update(self, payload):
        return self.client.post(
            reverse('products:document_update', args=[self.doc.pk]),
            data=json.dumps(payload), content_type='application/json')

    def test_처음에는_기본_유효기간이_붙는다(self):
        """자동 채움 자체는 옳은 동작이다 — 그것까지 끄면 안 된다."""
        self.doc.refresh_from_db()
        self.assertIsNotNone(self.doc.expiry_date)

    def test_무기한으로_저장하면_비어_있다(self):
        r = self._update({'expiry_date': None})
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.expiry_date)

    def test_다시_저장해도_되살아나지_않는다(self):
        self._update({'expiry_date': None})
        self._update({'description': '메모만 고친다'})
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.expiry_date)

    def test_날짜를_다시_넣으면_그_날짜가_된다(self):
        self._update({'expiry_date': None})
        self._update({'expiry_date': '2027-01-31'})
        self.doc.refresh_from_db()
        self.assertEqual(str(self.doc.expiry_date), '2027-01-31')

    def test_날짜를_다시_넣으면_무기한_표시가_지워진다(self):
        """남아 있으면 그 뒤에 날짜를 비웠을 때 자동 채움이 또 안 돈다."""
        self._update({'expiry_date': None})
        self._update({'expiry_date': '2027-01-31'})
        self.doc.refresh_from_db()
        self.assertNotIn('expiry_unlimited', self.doc.metadata or {})


# ─────────────────────────────────────────────────────────────────────────────
# 제품 문서함(문서 관리) 회귀 시험
#
# 아래 여섯 벌은 모두 "화면은 열어 주고 서버가 막는다" 또는 "실패했는데
# 실패했다고 말하지 않는다" 는 한 가지 병의 변주다. 둘 다 사용자가 자기가
# 무엇을 잘못했는지 알 수 없게 만든다.
# ─────────────────────────────────────────────────────────────────────────────

def _doc_tab_source():
    """문서함 탭 템플릿(_tab_documents.html) 원문."""
    from pathlib import Path

    from django.conf import settings as dj
    return (Path(dj.BASE_DIR) / 'templates' / 'products'
            / '_tab_documents.html').read_text(encoding='utf-8')


def _js_body(src, marker):
    """`window.<이름> = …` 한 벌의 본문만 중괄호 짝을 세어 잘라낸다.

    옆 함수의 코드가 섞여 들어오면 "고쳤다" 는 거짓 통과가 난다 — 문서함
    탭은 한 <script> 안에 함수가 수십 개다.
    """
    if marker not in src:
        raise AssertionError(marker + ' 이(가) 템플릿에 없다')
    i = src.index(marker)
    depth = 0
    for k in range(src.index('{', i), len(src)):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError(marker + ' 의 끝(닫는 중괄호)을 찾지 못했다')


class 문서_일괄_삭제가_한_건_삭제와_같은_규칙을_쓴다(TestCase):
    """
    문서함의 [삭제] 단추는 `can_upload_documents` 로 열린다. 그런데 서버의
    일괄 삭제는 `label__user_id=request.user` — **제품 주인만** 골랐다.

    공유 편집자가 자기가 올린 파일을 골라 지우면 하나도 안 지워졌는데
    `success: true` 와 함께 "0개의 문서가 삭제되었습니다" 가 떴다. 화면은
    새로고침되고 파일은 그대로 남아 있다. 몇 번을 눌러도 같은 말을 한다 —
    실패를 성공이라고 말하니 사용자는 자기가 잘못 골랐다고 생각한다.

    한 건 삭제(document_delete_api)는 이미 "올린 사람 + 업로드 권한 공유자"
    를 허용한다. 같은 단추가 한 건이냐 여러 건이냐로 다른 규칙을 쓸 이유가
    없다.
    """

    def setUp(self):
        from v1.products.models import DocumentType, ProductDocument
        self.ProductDocument = ProductDocument
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', delete_YN='N')
        self.dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.editor = self._member('EDITOR', 'ed@x.com')
        self.mine = self._doc('편집자가올린것.pdf', self.editor)
        self.theirs = self._doc('주인이올린것.pdf', self.owner)

    def _member(self, role, email):
        user = User.objects.create_user(role, password='x', email=email)
        share = ProductShare.objects.create(
            label=self.label, recipient_email=email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share).apply_role_defaults(
            role_code=role, save=True)
        return user

    def _doc(self, name, uploader):
        from django.core.files.base import ContentFile
        return self.ProductDocument.objects.create(
            label=self.label, document_type=self.dtype,
            file=ContentFile(b'%PDF-1.4', name=name),
            original_filename=name, uploaded_by=uploader)

    def _delete(self, user, docs):
        self.client.force_login(user)
        return self.client.post(
            reverse('products:bulk_delete_documents'),
            data=json.dumps({'document_ids': [d.document_id for d in docs]}),
            content_type='application/json')

    def _alive(self, doc):
        doc.refresh_from_db()
        return doc.active_yn

    def test_공유_편집자가_자기가_올린_문서를_지운다(self):
        r = self._delete(self.editor, [self.mine])
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertTrue(r.json()['success'])
        self.assertFalse(self._alive(self.mine))

    def test_지운_것이_없으면_성공이라고_말하지_않는다(self):
        """0개를 지우고 `success: true` 를 돌려주던 바로 그 자리."""
        r = self._delete(self.editor, [self.theirs])
        self.assertFalse(r.json()['success'],
                         '아무것도 안 지우고 성공이라고 말했다')
        self.assertTrue(self._alive(self.theirs))

    def test_남이_올린_문서는_섞여_있어도_안_지워진다(self):
        self._delete(self.editor, [self.mine, self.theirs])
        self.assertFalse(self._alive(self.mine))
        self.assertTrue(self._alive(self.theirs), '남이 올린 문서까지 지웠다')

    def test_업로드_권한이_없으면_막는다(self):
        rv = self._member('REVIEWER', 'rv@x.com')
        theirs = self._doc('검토자가올린것.pdf', rv)
        r = self._delete(rv, [theirs])
        self.assertEqual(r.status_code, 403)
        self.assertTrue(self._alive(theirs))

    def test_공유가_없는_남은_못_지운다(self):
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        r = self._delete(stranger, [self.mine, self.theirs])
        self.assertFalse(r.json()['success'])
        self.assertTrue(self._alive(self.mine))
        self.assertTrue(self._alive(self.theirs))

    def test_공유가_끊기면_못_지운다(self):
        ProductShare.objects.filter(label=self.label).update(active_yn=False)
        r = self._delete(self.editor, [self.mine])
        self.assertFalse(r.json()['success'])
        self.assertTrue(self._alive(self.mine))

    def test_주인은_남이_올린_것도_지운다(self):
        r = self._delete(self.owner, [self.mine, self.theirs])
        self.assertTrue(r.json()['success'], r.content[:200])
        self.assertFalse(self._alive(self.mine))
        self.assertFalse(self._alive(self.theirs))

    def test_영어_원문을_사용자에게_보내지_않는다(self):
        stranger = User.objects.create_user('남2', password='x', email='no2@x.com')
        r = self._delete(stranger, [self.theirs])
        self.assertNotIn('matches the given query', r.json().get('error', ''))


class 필수_문서_관리가_공유_편집자를_영어로_막지_않는다(TestCase):
    """
    [필수 문서 관리] 단추는 `can_upload_documents` 로 열리는데, 슬롯 추가·
    제거 뷰는 `user_id=request.user` — 제품 주인만 받았다. 게다가
    `get_object_or_404` 가 던진 `Http404` 를 바로 아래 `except Exception` 이
    삼켜 500 으로 바꾸는 바람에, 공유 편집자에게
    `No MyLabel matches the given query.` 라는 **영어 원문**이 스낵바에 떴다.

    무엇을 잘못했는지도, 누구에게 물어야 하는지도 알 수 없는 문장이다.
    """

    def setUp(self):
        from v1.products.models import DocumentSlot, DocumentType
        self.DocumentSlot = DocumentSlot
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', delete_YN='N')
        self.dtype = DocumentType.objects.create(
            type_code='T', type_name='성적서', active_yn=True)
        self.other_type = DocumentType.objects.create(
            type_code='U', type_name='원산지증명', active_yn=True)
        self.slot = DocumentSlot.objects.create(
            label=self.label, document_type=self.dtype)
        self.editor = self._member('EDITOR', 'ed@x.com')

    def _member(self, role, email):
        user = User.objects.create_user(role, password='x', email=email)
        share = ProductShare.objects.create(
            label=self.label, recipient_email=email, recipient_user=user,
            share_mode='PRIVATE', active_yn=True, created_by=self.owner)
        SharePermission.objects.create(share=share).apply_role_defaults(
            role_code=role, save=True)
        return user

    def _add(self, user, type_id=None):
        self.client.force_login(user)
        return self.client.post(
            reverse('products:add_document_slot', args=[self.label.my_label_id]),
            data=json.dumps({'document_type_id': type_id or self.other_type.type_id}),
            content_type='application/json')

    def _remove(self, user, slot=None):
        self.client.force_login(user)
        return self.client.post(
            reverse('products:remove_document_slot',
                    args=[(slot or self.slot).slot_id]))

    def test_공유_편집자가_슬롯을_추가한다(self):
        r = self._add(self.editor)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertTrue(r.json()['success'], r.content[:200])
        self.assertTrue(self.DocumentSlot.objects.filter(
            label=self.label, document_type=self.other_type).exists())

    def test_공유_편집자가_슬롯을_제거한다(self):
        r = self._remove(self.editor)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertTrue(r.json()['success'], r.content[:200])
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.hidden_yn)

    def test_업로드_권한이_없으면_한국어로_막는다(self):
        rv = self._member('REVIEWER', 'rv@x.com')
        r = self._add(rv)
        self.assertEqual(r.status_code, 403)
        self.assertIn('권한이 없습니다', r.json()['error'])

    def test_제거도_업로드_권한을_본다(self):
        rv = self._member('REVIEWER', 'rv2@x.com')
        r = self._remove(rv)
        self.assertEqual(r.status_code, 403)
        self.assertIn('권한이 없습니다', r.json()['error'])
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.hidden_yn)

    def test_추가가_영어_원문을_스낵바로_보내지_않는다(self):
        """`No MyLabel matches the given query.` 가 그대로 떴다."""
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        r = self._add(stranger)
        self.assertNotEqual(r.status_code, 500)
        error = r.json().get('error', '')
        self.assertNotIn('MyLabel', error)
        self.assertNotIn('matches the given query', error)

    def test_제거가_영어_원문을_스낵바로_보내지_않는다(self):
        stranger = User.objects.create_user('남2', password='x', email='no2@x.com')
        r = self._remove(stranger)
        self.assertNotEqual(r.status_code, 500)
        error = r.json().get('error', '')
        self.assertNotIn('DocumentSlot', error)
        self.assertNotIn('matches the given query', error)

    def test_주인은_그대로_된다(self):
        self.assertTrue(self._add(self.owner).json()['success'])
        self.assertTrue(self._remove(self.owner).json()['success'])


class 편집_패널의_업로드가_읽기_전용_사용자를_파일_선택까지_보내지_않는다(TestCase):
    """
    바로 위 `handleSlotClick` 에는 `window.CAN_UPLOAD_DOCUMENTS` 확인이
    있는데 `openUploadForUpdate` 에는 없었다. 검토자·뷰어가 오른쪽 편집
    패널의 [업로드] 를 누르면 파일 선택 창이 열리고, 파일을 고르고 등록까지
    누른 뒤에야 "문서 업로드 권한이 없습니다" 로 되돌아왔다.

    패널의 [업로드]·[저장] 두 단추는 애초에 그려지지 않아야 한다 — 누를 수
    없는 단추를 보여 주는 것 자체가 거짓말이다.
    """

    def setUp(self):
        self.src = _doc_tab_source()
        self.panel = _js_body(self.src, 'window.openEditPanel')

    def _write_block(self):
        """권한이 있을 때만 만들어지는 조각(writeButtons)의 본문."""
        self.assertIn('const writeButtons', self.panel,
                      '패널이 권한에 따라 갈리는 조각을 갖고 있지 않다')
        self.assertIn('writeButtons 끝', self.panel)
        i = self.panel.index('const writeButtons')
        return self.panel[i:self.panel.index('writeButtons 끝', i)]

    def test_업로드_단추가_권한을_먼저_본다(self):
        body = _js_body(self.src, 'window.openUploadForUpdate')
        self.assertIn('CAN_UPLOAD_DOCUMENTS', body,
                      '읽기 전용 사용자를 파일 선택 창까지 보낸다')

    def test_업로드_저장_단추는_권한_안에서만_만들어진다(self):
        block = self._write_block()
        self.assertIn('CAN_UPLOAD_DOCUMENTS', block)
        self.assertIn('openUploadForUpdate()', block)
        self.assertIn('submitDocumentUpdate()', block)

    def test_권한_밖에는_그_단추가_없다(self):
        rest = self.panel.replace(self._write_block(), '')
        self.assertNotIn('openUploadForUpdate()', rest)
        self.assertNotIn('submitDocumentUpdate()', rest)

    def test_다운로드는_읽기_전용에게도_남는다(self):
        """볼 수 있는 사람은 받을 수 있다 — 막는 것은 쓰기뿐이다."""
        rest = self.panel.replace(self._write_block(), '')
        self.assertIn('doc.downloadUrl', rest)

    def test_전역_스낵바를_쓴다(self):
        self.assertNotIn('alert(', _js_body(self.src, 'window.openUploadForUpdate'))

    def test_읽기_전용_화면에는_권한_깃발이_꺼져_나간다(self):
        """JS 가 보는 깃발이 서버가 계산한 권한과 같은 값인지 — 끝에서 끝까지."""
        from v1.products.models import ProductMetadata
        owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        label = MyLabel.objects.create(
            user_id=owner, my_label_name='브라우니', delete_YN='N')
        ProductMetadata.objects.create(label=label, product_code='PRD-T-1')
        rv = User.objects.create_user('검토자', password='x', email='rv@x.com')
        share = ProductShare.objects.create(
            label=label, recipient_email='rv@x.com', recipient_user=rv,
            share_mode='PRIVATE', active_yn=True, created_by=owner)
        SharePermission.objects.create(share=share).apply_role_defaults(
            role_code='REVIEWER', save=True)

        self.client.force_login(rv)
        html = self.client.get(reverse(
            'products:product_detail', args=[label.my_label_id])).content.decode()
        self.assertIn('window.CAN_UPLOAD_DOCUMENTS = false', html)

        self.client.force_login(owner)
        html = self.client.get(reverse(
            'products:product_detail', args=[label.my_label_id])).content.decode()
        self.assertIn('window.CAN_UPLOAD_DOCUMENTS = true', html)


class 일괄_다운로드_실패가_보던_화면을_JSON_원문으로_바꾸지_않는다(TestCase):
    """
    `bulkDownloadCompact` 가 폼을 만들어 `form.submit()` 으로 POST 했다.
    성공하면 파일이 내려오지만 **실패하면 그 JSON 응답이 현재 창을 통째로
    대체한다** — 제품 상세 화면이 `{"success": false, "error": …}` 한 줄로
    바뀌고 열어 두었던 탭도, 입력하던 값도 사라진다. 뒤로 가기로 돌아와도
    작성 중이던 것은 없다.

    fetch 로 받아 실패는 스낵바로 말하고, 성공은 Blob 으로 받아 그대로
    내려받게 한다 — 파일 저장은 그대로 되어야 한다.
    """

    def setUp(self):
        from django.core.files.base import ContentFile

        from v1.products.models import DocumentType, ProductDocument
        self.src = _doc_tab_source()
        self.body = _js_body(self.src, 'window.bulkDownloadCompact')
        self.owner = User.objects.create_user('주인', password='x', email='owner@x.com')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='브라우니', delete_YN='N')
        dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.doc = ProductDocument.objects.create(
            label=self.label, document_type=dtype,
            file=ContentFile(b'%PDF-1.4', name='a.pdf'),
            original_filename='a.pdf', uploaded_by=self.owner)

    def test_현재_창을_대체하지_않는다(self):
        self.assertNotIn('form.submit()', self.body,
                         '오류 응답이 보던 화면을 덮어쓴다')

    def test_fetch_로_받는다(self):
        self.assertIn('fetch(', self.body)

    def test_성공하면_파일로_저장한다(self):
        self.assertIn('blob(', self.body)
        self.assertIn('createObjectURL', self.body)

    def test_실패는_스낵바로_말한다(self):
        self.assertIn('showSnackbar', self.body)
        self.assertNotIn('alert(', self.body)

    def test_통신이_끊겨도_말한다(self):
        self.assertIn('catch', self.body)

    def test_받을_수_있으면_zip_이_온다(self):
        """고치면서 성공 경로를 잃지 않았는지 — 서버 쪽 기준선."""
        self.client.force_login(self.owner)
        r = self.client.post(reverse('products:bulk_download'),
                             {'document_ids': str(self.doc.document_id)})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/zip')

    def test_받을_수_없으면_json_으로_거절한다(self):
        """이 응답이 예전에는 제품 상세 화면을 대체했다."""
        stranger = User.objects.create_user('남', password='x', email='no@x.com')
        self.client.force_login(stranger)
        r = self.client.post(reverse('products:bulk_download'),
                             {'document_ids': str(self.doc.document_id)})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(r.json()['success'])


class 성적서_판독_상자가_패널을_따라_사라진다(TestCase):
    """
    `#specNutritionResult` 는 `#doc-edit-panel` 의 첫 자식으로 붙는데
    `closeEditPanel` 도 `openEditPanel` 도 그것을 지우지 않았다.

    A 문서에서 [성적서에서 영양성분 읽기] → 패널 닫기 → B 문서 열기 를 하면
    **B 의 패널에 A 의 판독값**이 그대로 붙어 있다. 게다가 저장 핸들러는
    클로저로 A 의 docId 를 쥐고 있어서, B 를 보면서 [이 제품의 영양성분으로
    저장] 을 누르면 A 의 값이 저장된다. 어느 화면에도 A 라는 표시가 없으니
    잘못 저장된 것을 알아챌 방법이 없다.
    """

    def setUp(self):
        self.src = _doc_tab_source()

    def test_패널을_닫을_때_지운다(self):
        body = _js_body(self.src, 'window.closeEditPanel')
        self.assertIn('specNutritionResult', body,
                      '패널을 닫아도 판독 상자가 남는다')
        self.assertIn('remove()', body)

    def test_다른_문서를_열_때도_지운다(self):
        body = _js_body(self.src, 'window.openEditPanel')
        self.assertIn('specNutritionResult', body,
                      '앞 문서의 판독값이 다음 문서 패널에 그대로 붙는다')
        self.assertIn('remove()', body)


class 문서_일괄_삭제가_말없이_사라지지_않는다(TestCase):
    """
    `bulkDeleteCompact` 의 `fetch` 와 `response.json()` 이 try 밖에 있었다.
    서버가 JSON 이 아닌 것(500 HTML, 로그인 페이지)을 주거나 통신이 끊기면
    미처리 rejection 으로 조용히 사라진다 — 확인창에서 [확인] 을 눌렀는데
    스낵바도 없고 목록도 그대로다. 눌린 건지 아닌지조차 알 수 없다.
    """

    def setUp(self):
        self.body = _js_body(_doc_tab_source(), 'window.bulkDeleteCompact')

    def test_통신_실패를_붙잡는다(self):
        self.assertIn('catch', self.body, '미처리 rejection 으로 사라진다')

    def test_fetch_가_try_안에_있다(self):
        self.assertIn('try', self.body)
        self.assertLess(self.body.index('try'), self.body.index('fetch('),
                        'fetch 가 try 밖에 있다')

    def test_json_이_아닌_응답도_try_안에서_읽는다(self):
        self.assertLess(self.body.index('try'), self.body.index('.json()'),
                        'response.json() 이 try 밖에 있다')

    def test_실패를_사람_말로_알린다(self):
        self.assertIn('showSnackbar', self.body)
        self.assertNotIn('alert(', self.body)


# ─────────────────────────────────────────────────────────────────────────────
# 제품 문서함 화면 — 사용자가 운영 화면에서 알려 준 네 가지
#
# 아래 네 벌은 전부 "화면이 사용자에게 거짓말을 한다" 는 한 가지 병의 변주다.
# 열이 어긋나 보이고, 패널이 화면 밖으로 넘어가고, 받은 파일이 어느 제품
# 것인지 알 수 없고, 방금 올린 파일이 없는 것처럼 보인다.
# ─────────────────────────────────────────────────────────────────────────────

def _doc_tab_style():
    """문서함 탭 템플릿의 <style> 블록 전부."""
    import re as _re
    return '\n'.join(_re.findall(r'<style>(.*?)</style>', _doc_tab_source(), _re.S))


class 문서함_목록의_열_정렬이_한_규칙이다(TestCase):
    """
    '상태 / 만료일' 머리글은 칸 한가운데 있는데 `무기한`·`정상 27.03.12`
    배지는 왼쪽 끝에 붙어 있어 열이 어긋나 보였다.

    까닭은 두 군데다. `style.css` 의 `.table th` 가 머리글을 전부 가운데로
    밀고 `.table td` 는 왼쪽 그대로이며, 거기에 `.table td:nth-child(2)` 가
    `!important` 로 '구분' 칸만 다시 가운데로 당겼다. 그래서 어긋난 방향조차
    열마다 달랐다 — 구분은 둘 다 가운데, 나머지는 머리글만 가운데.

    한 규칙으로 맞춘다: **체크박스만 가운데, 나머지는 머리글도 내용도 왼쪽.**
    가장 넓은 '문서명' 열이 왼쪽 정렬이니 거기에 맞춘다.
    """

    def setUp(self):
        self.css = _doc_tab_style()
        self.assertIn('text-align: left !important;', self.css,
                      '열을 한 쪽으로 맞추는 규칙이 없다')
        head = self.css[:self.css.index('text-align: left !important;')]
        self.aligned = head[head.rindex('}') + 1:]

    def test_상태_만료일_열이_머리글과_같은_쪽에_붙는다(self):
        """사용자가 짚은 바로 그 열."""
        self.assertIn('.compact-doc-table th.col-status', self.aligned)
        self.assertIn('.compact-doc-table td.col-status', self.aligned)

    def test_구분_열도_같은_규칙을_쓴다(self):
        """`.table td:nth-child(2)` 의 `!important` 를 되받아야 한다."""
        self.assertIn('.compact-doc-table th.col-type', self.aligned)
        self.assertIn('.compact-doc-table td.col-type', self.aligned)

    def test_버전과_등록자도_같은_규칙을_쓴다(self):
        for col in ('col-version', 'col-uploader', 'col-name'):
            self.assertIn('.compact-doc-table th.%s' % col, self.aligned, col)
            self.assertIn('.compact-doc-table td.%s' % col, self.aligned, col)

    def test_체크박스만_가운데다(self):
        """예외는 하나뿐이고, 그것도 머리글과 내용이 같이 간다."""
        self.assertNotIn('col-checkbox', self.aligned,
                         '체크박스까지 왼쪽으로 밀면 칸 안에서 떠 보인다')
        self.assertIn('.compact-doc-table th.col-checkbox', self.css)
        self.assertIn('.compact-doc-table td.col-checkbox', self.css)

    def test_표에는_가운데_정렬이_체크박스_하나뿐이다(self):
        """열마다 다른 정렬을 새로 만들지 않는다 — 예외는 하나로 족하다."""
        import re as _re
        centered = [rule for rule in _re.findall(r'([^{}]*)\{([^{}]*)\}', self.css)
                    if 'compact-doc-table' in rule[0]
                    and 'text-align: center' in rule[1]]
        self.assertEqual(len(centered), 1,
                         '표에 가운데 정렬 규칙이 여럿이다: %s' % [r[0] for r in centered])
        self.assertIn('col-checkbox', centered[0][0])


class 문서_정보_패널이_한_화면에_들어온다(TestCase):
    """
    오른쪽 '문서 정보' 패널이 화면보다 길어서, 문서 하나 고치는데 [저장]도
    설명도 등록 정보도 스크롤해야 보였다.

    길이를 먹던 것은 셋이다.
      - [다운로드]·[업로드]·[저장] 이 `v2-btn-stack`(아이콘 위·글자 아래)라
        단추 하나가 두 줄치였다.
      - '문서 구분'·'발행일'·'유효기간' 이 항목명 한 줄, 입력칸 한 줄이었다.
      - 구역마다 `mb-3`(16px)에 설명은 세 줄, 안내문은 다섯 줄이었다.

    **줄이되 지우지 않는다** — 유효기간 빠른 선택 여섯 개도, 영양성분 읽기
    안내도 그대로 있다.
    """

    def setUp(self):
        self.src = _doc_tab_source()
        self.panel = _js_body(self.src, 'window.openEditPanel')

    def _wrapper_of(self, needle):
        """`needle` 을 감싼 바로 앞 <div …> 여는 태그."""
        i = self.panel.index(needle)
        j = self.panel.rindex('<div ', 0, i)
        return self.panel[j:self.panel.index('>', j) + 1]

    def _panel_classes(self):
        """패널이 실제로 붙이는 class 값만 — 주석에 적힌 이름은 세지 않는다."""
        import re as _re
        return ' '.join(_re.findall(r'class="([^"]*)"', self.panel))

    def test_단추_셋이_한_줄이다(self):
        self.assertNotIn('v2-btn-stack', self._panel_classes(),
                         '아이콘 위·글자 아래라 단추 하나가 두 줄을 먹는다')
        self.assertIn('doc-panel-actions', self._panel_classes())

    def test_단추_셋이_다_남아_있다(self):
        for onclick in ('doc.downloadUrl', 'openUploadForUpdate()',
                        'submitDocumentUpdate()'):
            self.assertIn(onclick, self.panel, onclick)

    def test_항목명과_입력칸이_한_줄에_있다(self):
        for field in ('id="edit-doc-type"', 'id="edit-issue-date"',
                      'id="edit-expiry-date"', 'id="edit-description"'):
            self.assertIn('doc-field', self._wrapper_of(field), field)

    def test_유효기간_빠른_선택을_지우지_않았다(self):
        for label in ('+1개월', '+3개월', '+6개월', '+1년', '+2년', '무기한'):
            self.assertIn('>%s</button>' % label, self.panel, label)

    def test_영양성분_읽기_안내를_지우지_않았다(self):
        self.assertIn('영양성분 읽기', self.panel)
        self.assertIn('readSpecNutrition(', self.panel)

    def test_안내가_길면_두_줄로_줄이고_나머지는_title_로_남긴다(self):
        self.assertIn('doc-panel-note', self.panel)
        self.assertIn('시험한 값이 계산한 값을 이깁니다', self.panel,
                      '잘라낸 설명이 어디에도 남아 있지 않다')

    def test_구역_간격을_줄였다(self):
        self.assertNotIn('mb-3', self.panel,
                         '구역마다 16px 씩 비우면 그만큼 아래가 밀린다')

    def test_설명_칸이_세_줄을_먹지_않는다(self):
        self.assertIn('rows="2"', self.panel)
        self.assertNotIn('rows="3"', self.panel)

    def test_한_줄짜리_단추_규칙이_CSS_에_있다(self):
        css = _doc_tab_style()
        self.assertIn('#doc-edit-panel .doc-panel-actions', css)
        self.assertIn('#doc-edit-panel .doc-field', css)
        self.assertIn('grid-template-columns', css,
                      '항목명 폭이 고정되지 않으면 입력칸 왼쪽이 들쭉날쭉하다')

    def test_전역_스낵바_규칙을_지킨다(self):
        self.assertNotIn('alert(', self.panel)


class 일괄_다운로드_ZIP_이름에_제품이_들어간다(TestCase):
    """
    받은 파일이 `documents_20260913_101500.zip` 이었다. 제품이 어디에도 없다.
    여러 제품에서 서류를 받아 두면 내려받기 폴더에 `documents_…` 만 늘어서서
    어느 제품 것인지 알려면 하나씩 열어 봐야 했다.

    그리고 이름을 한글로 지어 헤더에 그대로 넣으면 더 나빠진다. Django 는
    ASCII 가 아닌 헤더 값을 통째로 MIME 인코딩해 `=?utf-8?b?…?=` 한 덩어리로
    내보내는데, 화면은 fetch + Blob 으로 받으면서 `filename=` 을 정규식으로
    찾으므로 아무것도 못 찾고 대비용 `documents.zip` 으로 저장한다 —
    **서버가 지은 이름과 저장된 이름이 다르다.**
    """

    def setUp(self):
        from django.core.files.base import ContentFile

        from v1.products.models import DocumentType, ProductDocument
        self.ProductDocument = ProductDocument
        self.ContentFile = ContentFile
        self.owner = User.objects.create_user('주인', password='x', email='o@x.com')
        self.dtype = DocumentType.objects.create(type_code='T', type_name='성적서')
        self.label = MyLabel.objects.create(
            user_id=self.owner, my_label_name='초코 브라우니', delete_YN='N')
        self.doc = self._doc(self.label, 'a.pdf')

    def _doc(self, label, name):
        return self.ProductDocument.objects.create(
            label=label, document_type=self.dtype,
            file=self.ContentFile(b'%PDF-1.4', name=name),
            original_filename=name, uploaded_by=self.owner)

    def _download(self, docs):
        self.client.force_login(self.owner)
        return self.client.post(reverse('products:bulk_download'), {
            'document_ids': ','.join(str(d.document_id) for d in docs)})

    def _saved_name(self, response):
        """화면(fetch + Blob)이 `Content-Disposition` 에서 읽어 내는 이름.

        `_tab_documents.html` 의 `filenameFromDisposition` 과 같은 순서로 본다
        — `filename*` 먼저, 없으면 `filename=`.
        """
        import re as _re
        from urllib.parse import unquote
        header = response['Content-Disposition']
        star = _re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", header, _re.I)
        if star:
            return unquote(star.group(1).strip())
        plain = _re.search(r'filename\s*=\s*"?([^";]+)"?', header, _re.I)
        return plain.group(1).strip() if plain else 'documents.zip'

    def test_제품명이_들어간다(self):
        self.assertIn('초코_브라우니', self._saved_name(self._download([self.doc])))

    def test_날짜가_들어간다(self):
        name = self._saved_name(self._download([self.doc]))
        self.assertIn(timezone.localtime().strftime('%Y%m%d'), name)
        self.assertTrue(name.endswith('.zip'), name)

    def test_화면이_저장하는_이름과_서버가_지은_이름이_같다(self):
        """예전에는 화면이 이름을 못 읽어 `documents.zip` 으로 저장했다."""
        from v1.products.views import _documents_zip_filename
        response = self._download([self.doc])
        self.assertEqual(self._saved_name(response),
                         _documents_zip_filename(['초코 브라우니']))

    def test_헤더가_통째로_MIME_인코딩되지_않는다(self):
        header = self._download([self.doc])['Content-Disposition']
        self.assertTrue(header.startswith('attachment;'), header)
        self.assertNotIn('=?utf-8?', header)
        header.encode('ascii')   # 헤더는 ASCII 로만 나간다

    def test_여러_제품이면_외_N건을_붙인다(self):
        other = MyLabel.objects.create(
            user_id=self.owner, my_label_name='딸기 케이크', delete_YN='N')
        name = self._saved_name(self._download([self.doc, self._doc(other, 'b.pdf')]))
        self.assertIn('외1건', name)

    def test_같은_제품_문서_여럿은_외_N건이_아니다(self):
        name = self._saved_name(self._download([self.doc, self._doc(self.label, 'b.pdf')]))
        self.assertNotIn('외', name)

    def test_파일명에_못_쓰는_글자와_공백을_다듬는다(self):
        from v1.products.views import _documents_zip_filename
        name = _documents_zip_filename(['A/B:C*D?E"F<G>H|I\\J  K'])
        for bad in '\\/:*?"<>|':
            self.assertNotIn(bad, name, bad)
        self.assertNotIn(' ', name, '공백이 남으면 셸·메일 첨부에서 이름이 갈린다')

    def test_이름이_비면_대비할_이름을_쓴다(self):
        from v1.products.views import _documents_zip_filename
        for empty in ([], [''], [None], ['   '], ['///']):
            name = _documents_zip_filename(empty)
            self.assertTrue(name.startswith('제품문서_'), (empty, name))

    def test_이름_한_조각이_밑줄만_남지_않는다(self):
        from v1.products.views import _sanitize_filename_part
        self.assertEqual(_sanitize_filename_part('  ///  '), '')
        self.assertEqual(_sanitize_filename_part('초코 브라우니'), '초코_브라우니')

    def test_한_제품_전체_받기도_같은_이름_규칙을_쓴다(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse('products:bulk_download_version',
                                     args=[self.label.my_label_id]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('초코_브라우니', self._saved_name(r))

    def test_화면이_filename_별표를_먼저_본다(self):
        """이 순서가 뒤집히면 한글 이름이 대비용 ASCII 이름으로 저장된다."""
        body = _js_body(_doc_tab_source(), 'window.filenameFromDisposition')
        self.assertIn('filename\\*', body)
        self.assertIn('decodeURIComponent', body)
        self.assertLess(body.index('filename\\*'), body.index('filename\\s*='),
                        'filename= 를 먼저 보면 대비용 이름을 집어 든다')

    def test_다운로드_경로가_그_함수를_쓴다(self):
        body = _js_body(_doc_tab_source(), 'window.bulkDownloadCompact')
        self.assertIn('filenameFromDisposition', body)


class 업로드_뒤에도_문서함_탭에_남는다(TestCase):
    """
    문서를 올리면 화면이 세 번 바뀌었다.

      1. "등록된 문서가 없습니다" — 아직 예전 화면이다. 새로고침이 끝날
         때까지 브라우저는 예전 화면을 계속 보여 준다.
      2. **기본 정보 탭** — 새 화면이 떴는데 서버가 그린 기본 활성 탭이다.
      3. 그제야 문서함에 올린 파일이 보인다 — product_detail.html 의
         DOMContentLoaded 가 sessionStorage 의 returnToTab 을 읽고 탭을 켠다.

    2번은 탭 복원이 DOMContentLoaded 를 기다리기 때문이다. 이 화면은 탭
    여섯 개에 iframe 까지 달려 파싱이 한참 걸리는데 브라우저는 그 전에
    기본 정보 탭을 그려 버린다. 1번은 새로고침 동안 예전 목록이 그대로
    남아 있기 때문이다.

    올린 사람은 "잘못됐나" 하고 멈칫한다.
    """

    def setUp(self):
        self.src = _doc_tab_source()
        i = self.src.index('var wanted = null;')
        self.restore = self.src[i:self.src.index('})();', i)]

    def test_탭_복원이_DOMContentLoaded_를_기다리지_않는다(self):
        """기다리면 그 사이에 기본 정보 탭이 한 번 그려진다."""
        self.assertNotIn('DOMContentLoaded', self.restore)
        self.assertNotIn('addEventListener', self.restore)

    def test_문서함으로_돌아올_때만_손댄다(self):
        self.assertIn('returnToTab', self.restore)
        self.assertIn("!== 'docs'", self.restore)

    def test_기본_정보_탭의_active_를_걷어내고_문서함을_켠다(self):
        self.assertIn("classList.remove('show', 'active')", self.restore)
        self.assertIn("getElementById('tab-docs')", self.restore)
        self.assertIn("classList.add('show', 'active')", self.restore)
        self.assertIn('[data-bs-target="#tab-docs"]', self.restore)

    def test_저장된_값을_지우지_않는다(self):
        """원래 주인(product_detail.html)이 읽고 지운다 — 여기서 지우면
        그쪽이 URL 파라미터·해시를 보고 다른 탭을 켠다."""
        self.assertNotIn('removeItem', self.restore)

    def test_사생활_보호_모드에서_화면이_죽지_않는다(self):
        """sessionStorage 접근 자체가 던지는 브라우저 설정이 있다."""
        self.assertIn('catch', self.restore)

    def test_새로고침_동안_빈_목록_대신_새로_고치는_중을_보여_준다(self):
        self.assertIn('id="doc-refreshing"', self.src)
        self.assertIn('문서함을 새로 고치는 중', self.src)
        self.assertIn('.doc-refreshing', _doc_tab_style())

    def test_업로드가_남의_파일이라_떠나는_순간을_잡는다(self):
        """업로드는 smart_upload.js 가 하고 이 파일에서 손댈 수 없다."""
        body = _js_body(self.src, 'window.showDocListRefreshing')
        self.assertIn("getElementById('doc-refreshing')", body)
        self.assertIn("classList.remove('d-none')", body)
        self.assertIn("addEventListener('beforeunload'", self.src)

    def test_이_파일의_새로고침도_스스로_덮는다(self):
        """저장·삭제·필수문서관리 — 전부 location.reload() 로 끝난다."""
        for marker in ('window.submitDocumentUpdate', 'window.bulkDeleteCompact',
                       'window.submitSlotManager'):
            body = _js_body(self.src, marker)
            self.assertIn('showDocListRefreshing', body, marker)

    def test_상세_화면에_그대로_실려_나간다(self):
        """탭 단추와 기본 정보 칸이 **먼저** 그려져 있어야 손댈 수 있다."""
        owner = User.objects.create_user('주인', password='x', email='o@x.com')
        label = MyLabel.objects.create(
            user_id=owner, my_label_name='브라우니', delete_YN='N')
        ProductMetadata.objects.create(label=label, product_code='PRD-T-9')
        self.client.force_login(owner)
        html = self.client.get(reverse(
            'products:product_detail', args=[label.my_label_id])).content.decode()

        self.assertIn('var wanted = null;', html)
        mark = html.index('var wanted = null;')
        self.assertLess(html.index('data-bs-target="#tab-docs"'), mark,
                        '탭 단추보다 먼저 돌면 켤 것을 찾지 못한다')
        self.assertLess(html.index('id="tab-info"'), mark,
                        '기본 정보 칸보다 먼저 돌면 active 를 걷어내지 못한다')


class 괄호가_안_맞는_JS(TestCase):
    """
    미리보기 화면이 통째로 죽어 있었다. label_preview.js 에서 옛 함수를
    갈아 끼우면서 그 함수의 마지막 줄과 닫는 괄호를 지우지 않아
    DOMContentLoaded 콜백이 중간에 닫혔다. 파일이 파싱 단계에서 죽으니 그
    안의 전역 함수가 하나도 안 생겼고, 화면에서는 "2단 배치 단추가 안
    먹는다"(setAllFieldsWidth is not defined) 로만 보였다.

    재선언 검사(static.E001)는 괄호가 안 맞으면 **조용히 포기한다.** 그래서
    아무 검사에도 안 걸렸다.
    """

    def test_지금은_한_건도_안_걸린다(self):
        from v1.common.checks import check_js_bracket_balance
        found = check_js_bracket_balance(None)
        self.assertEqual([e.msg for e in found], [])

    def test_닫는_괄호가_하나_남으면_잡는다(self):
        from v1.common.checks import _bracket_balance
        result = _bracket_balance("""function f() {
    return 1;
}
}
""")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 4)

    def test_열린_괄호가_남으면_잡는다(self):
        from v1.common.checks import _bracket_balance
        self.assertEqual(_bracket_balance("""function f() {
    return 1;
"""), (None, 1))

    def test_문자열_주석_정규식_안의_괄호는_세지_않는다(self):
        from v1.common.checks import _bracket_balance
        self.assertIsNone(_bracket_balance("""var a = '}';
// }
/* } */
var re = /[}]/;
var t = `${a}}`;
"""))

    def test_번들은_건너뛴다(self):
        # 번들러가 뱉은 한 줄짜리 파일은 정규식 리터럴을 가려낼 수 없어
        # 거짓 경보만 낸다. 사람이 쓴 소스에는 이런 줄이 없다.
        from v1.common.checks import _is_built_bundle
        self.assertTrue(_is_built_bundle('var a=1;' * 400))
        self.assertFalse(_is_built_bundle("""var a = 1;
var b = 2;
"""))

    def test_미리보기_JS_의_전역이_최상위에_있다(self):
        # 파일이 파싱되지 않으면 이 이름들이 window 에 안 붙는다.
        from pathlib import Path
        from django.conf import settings
        js = (Path(settings.BASE_DIR) / 'static/js/label/label_preview.js'
              ).read_text(encoding='utf-8')
        for name in ('window.setAllFieldsWidth',
                     'window.toggleAllFieldsVisibility',
                     'window.resetFieldOrder'):
            self.assertIn(name + ' = ', js)
        self.assertIn('function getCookie(name)', js)


class 계산기_JS_를_빌려_쓰는_화면(TestCase):
    """
    nutrition_calculator_popup.js 는 계산기 팝업과 제품 영양성분 편집기가
    함께 읽는다. 편집기에는 계산기의 입력 표가 없는데, 팝업용 초기화가
    거기서도 돌면서 3초를 기다린 뒤 콘솔에
    "입력 표가 준비되지 않았습니다" 를 남기고 URL 파라미터를 읽으러 갔다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings
        self.js = (Path(settings.BASE_DIR)
                   / 'static/js/label/nutrition_calculator_popup.js'
                   ).read_text(encoding='utf-8')

    def test_입력_표가_없으면_초기화하지_않는다(self):
        head = self.js.index("document.addEventListener('DOMContentLoaded'")
        tail = self.js.index('buildInputForm();', head)
        self.assertIn("if (!document.getElementById('basic-nutrient-inputs')) return;",
                      self.js[head:tail])

    def test_편집기에는_그_컨테이너가_없다(self):
        # 이 전제가 깨지면 위의 방어가 무의미해진다.
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR) / 'templates'
        editor = (base / 'products/nutrition_editor.html').read_text(encoding='utf-8')
        popup = (base / 'label/nutrition_calculator_popup.html').read_text(encoding='utf-8')
        self.assertNotIn('basic-nutrient-inputs', editor)
        self.assertIn('basic-nutrient-inputs', popup)
        self.assertIn('nutrition_calculator_popup.js', editor)


class 영양성분_저장하면_단계_표시가_따라온다(TestCase):
    """
    탭 머리의 단계 번호는 서버가 그린다. 영양성분은 iframe 안에서 제 API 로
    저장하고 화면을 다시 읽지 않으니, 저장을 눌러도 번호가 그대로였다 —
    사용자는 저장이 안 된 줄 안다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR) / 'templates/products'
        self.editor = (base / 'nutrition_editor.html').read_text(encoding='utf-8')
        self.detail = (base / 'product_detail.html').read_text(encoding='utf-8')

    def test_편집기가_열량이_있는지_함께_보낸다(self):
        head = self.editor.index("type: 'nutritionSaved'")
        tail = self.editor.index("}, '*');", head)
        # 이름의 일부만 맞아도 통과하면 안 된다 — 키 자리에 있어야 한다
        self.assertRegex(self.editor[head:tail],
                         r'(?<![A-Za-z0-9_$])hasCalories\s*:')

    def test_부모가_그_값으로_단계_표시를_고친다(self):
        head = self.detail.index("event.data.type === 'nutritionSaved'")
        tail = self.detail.index('previewSettingsSaved', head)
        body = self.detail[head:tail]
        self.assertRegex(
            body, r"(?<![A-Za-z0-9_$])markWorkflowStep\('#tab-nutrition'")
        self.assertIn('event.data.hasCalories', body)

    def test_고치는_함수가_있다(self):
        self.assertIn('function markWorkflowStep(tabTarget, done)', self.detail)
        self.assertIn('wf-no-done', self.detail)

    def test_서버와_같은_기준이다(self):
        # 서버는 calories 가 채워졌는지로 판정한다 — 기준이 갈리면
        # 새로고침할 때마다 표시가 뒤집힌다.
        import inspect
        from v1.products.views import _build_workflow_steps
        src = inspect.getsource(_build_workflow_steps)
        self.assertIn("'tab-nutrition': bool((label.calories", src)
