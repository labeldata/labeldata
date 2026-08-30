"""
제품(products) 앱 회귀 테스트.

지금은 "확정(승인 완료) 직전 표시사항 검증" 한 가지만 다룬다. 이 경로는
화면에서 눈으로 확인하기 번거롭고(상태 전이 + 권한 + 검증이 한 번에 얽힌다),
조용히 느슨해지면 필수 항목이 빈 제품이 그대로 확정된다.
"""

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
