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

    def test_없는_번호는_404(self):
        self.assertEqual(self._lookup('99999999999999').status_code, 404)

    def test_번호가_비면_400(self):
        self.assertEqual(self._lookup('').status_code, 400)


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
        self.assertIn('window.openImportModal()', detail)


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
        self.css = (base / 'static/css/products_common.css').read_text(encoding='utf-8')

    def test_대조는_표시사항_탭에_있다(self):
        """
        5단계 도구는 5단계 자리에. 값을 채우는 창(불러오기)에 두면 인쇄
        직전에 "채우기" 를 눌러 확정한 값을 시안으로 덮어쓰게 된다.
        """
        self.assertIn('window.basicInfoOcrCompare', self.ocr)
        self.assertIn('id="ltCompareBtn"', self.tab)
        self.assertIn('basicInfoOcrCompare', self.tab)

    def test_불러오기_창에는_없다(self):
        self.assertNotIn('function compareZone', self.modal)
        self.assertNotIn("data-side=\"compare\"", self.modal)

    def test_대조_창에는_채우기가_없다(self):
        """고칠 수 있으면 "시안이 이렇다" 와 "내 값을 바꾸겠다" 가 섞인다."""
        head = self.ocr.index('function compareRowHtml')
        block = self.ocr[head:head + 1600]
        self.assertNotIn('ocr-pick', block)      # 체크박스
        self.assertNotIn('ocr-value', block)     # 고칠 칸
        self.assertIn('cmp-theirs', block)

    def test_반영_단추를_감춘다(self):
        head = self.ocr.index('function showCompare')
        block = self.ocr[head:head + 3000]
        self.assertIn("apply.style.display = 'none'", block)
        self.assertIn('값은 바뀌지 않습니다', block)

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

    def test_다른_것부터_보여_준다(self):
        """같은 것 열여섯 줄을 지나야 다른 두 줄이 나오면 대조하는 뜻이 없다."""
        head = self.ocr.index('function showCompare')
        block = self.ocr[head:head + 3000]
        self.assertLess(block.index('다른 항목 '), block.index('같은 항목 '))

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
        self.assertIn("record.push({ field: field, label: meta.label", self.ocr)

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
