# -*- coding: utf-8 -*-
"""인증·계정 — 로그인·가입·인증메일·비밀번호 재설정."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class 비밀번호_재설정_링크는_토큰이_있어야_연다(TestCase):
    """
    **계정 탈취가 됐다.**

    `password_reset_token` 의 기본값이 빈 문자열이다 — 시그널이 계정을 만들 때
    `''` 로 넣고(models.py), 재설정에 **성공한 뒤에도** `''` 로 되돌린다.
    그래서 "재설정을 요청한 적 없는 모든 계정" 과 "이미 재설정을 마친 모든
    계정" 의 저장값이 `''` 다.

    거기에 `?uid=1&token=` (토큰 값만 비움) 을 보내면
    `request.GET.get('token')` 이 `''` 를 돌려주므로 `'' != ''` 가 거짓이 되어
    가드가 통과한다. 메일을 받을 필요도, 그 계정을 알 필요도 없다 — uid 를
    1부터 훑으면 된다.

    같은 파일의 **이메일 인증에는 이 구멍이 없다.** 거기는
    `email_verification_token == token and token` 으로 빈 토큰을 걸러 낸다.
    재설정에만 그 `and token` 이 빠졌다.

    그리고 `password_reset_sent_at` 은 저장만 하고 **아무도 읽지 않았다.**
    반년 전 메일함에 남은 링크가 지금도 열렸다.
    """

    URL = '/user-management/password-reset-confirm/'

    def setUp(self):
        self.victim = User.objects.create_user(
            username='victim@example.com', email='victim@example.com',
            password='oldpw12345!')

    def _attack(self, token, uid=None):
        return self.client.post(
            '%s?uid=%s&token=%s' % (self.URL, uid or self.victim.id, token),
            {'password1': 'attacker!1234', 'password2': 'attacker!1234'})

    def _stolen(self):
        self.victim.refresh_from_db()
        return self.victim.check_password('attacker!1234')

    # ── 빈 토큰 ─────────────────────────────────────────────────────────────
    def test_빈_토큰으로는_바꿀_수_없다(self):
        """재설정을 요청한 적 없는 계정 — 저장값이 ''."""
        self.assertEqual(self.victim.profile.password_reset_token, '')
        self._attack('')
        self.assertFalse(self._stolen())

    def test_토큰_파라미터가_아예_없어도_못_바꾼다(self):
        self.client.post(self.URL + '?uid=%d' % self.victim.id,
                         {'password1': 'attacker!1234',
                          'password2': 'attacker!1234'})
        self.assertFalse(self._stolen())

    def test_한_번_쓴_뒤에는_그_링크가_죽는다(self):
        """성공하면 토큰을 '' 로 되돌린다 — 그 '' 가 다시 열쇠가 되면 안 된다."""
        p = self.victim.profile
        p.password_reset_token = 'realtoken'
        p.password_reset_sent_at = timezone.now()
        p.save()

        self.client.post(
            '%s?uid=%d&token=realtoken' % (self.URL, self.victim.id),
            {'password1': 'newpw!12345', 'password2': 'newpw!12345'})
        self.victim.refresh_from_db()
        self.assertTrue(self.victim.check_password('newpw!12345'))

        self._attack('')            # 같은 링크를 토큰만 비워 다시
        self.assertFalse(self._stolen())

    def test_남의_토큰으로는_못_바꾼다(self):
        other = User.objects.create_user(
            username='other@example.com', email='other@example.com',
            password='x12345678!')
        p = other.profile
        p.password_reset_token = 'otherstoken'
        p.password_reset_sent_at = timezone.now()
        p.save()

        self._attack('otherstoken')
        self.assertFalse(self._stolen())

    # ── 만료 ────────────────────────────────────────────────────────────────
    def test_오래된_링크는_만료된다(self):
        from datetime import timedelta

        p = self.victim.profile
        p.password_reset_token = 'oldtoken'
        p.password_reset_sent_at = timezone.now() - timedelta(hours=2)
        p.save()

        self._attack('oldtoken')
        self.assertFalse(self._stolen())

    def test_기간_안이면_열린다(self):
        from datetime import timedelta

        p = self.victim.profile
        p.password_reset_token = 'freshtoken'
        p.password_reset_sent_at = timezone.now() - timedelta(minutes=5)
        p.save()

        self.client.post(
            '%s?uid=%d&token=freshtoken' % (self.URL, self.victim.id),
            {'password1': 'brandnew!123', 'password2': 'brandnew!123'})
        self.victim.refresh_from_db()
        self.assertTrue(self.victim.check_password('brandnew!123'))

    def test_보낸_시각이_없으면_열지_않는다(self):
        """
        옛 계정처럼 sent_at 이 비어 있을 수 있다. 모르는 것을 '안 만료' 로
        보면 안 된다 — 만료 검사를 통째로 건너뛰는 뒷문이 된다.
        """
        p = self.victim.profile
        p.password_reset_token = 'notimestamp'
        p.password_reset_sent_at = None
        p.save()

        self._attack('notimestamp')
        self.assertFalse(self._stolen())

    # ── 죽은 링크로 들어왔을 때 ─────────────────────────────────────────────
    def test_링크가_죽었으면_폼을_그리지_않는다(self):
        """
        사용자는 새 비밀번호를 두 번 타이핑하고 누른 뒤에야 같은 오류를
        다시 봤다. 그리고 다시 받을 길이 화면에 없었다.
        """
        html = self.client.get(self.URL + '?uid=%d&token=' % self.victim.id
                               ).content.decode()
        self.assertNotIn('name="password1"', html)
        self.assertIn(reverse('user_management:password_reset_request'), html)

    def test_살아_있는_링크는_폼을_그린다(self):
        p = self.victim.profile
        p.password_reset_token = 'goodtoken'
        p.password_reset_sent_at = timezone.now()
        p.save()

        html = self.client.get(
            '%s?uid=%d&token=goodtoken' % (self.URL, self.victim.id)
        ).content.decode()
        self.assertIn('name="password1"', html)

    def test_없는_uid_에_500_이_아니다(self):
        for q in ('?uid=999999&token=x', '?uid=abc&token=x', '', '?uid=&token='):
            self.assertEqual(self.client.get(self.URL + q).status_code, 200, q)
