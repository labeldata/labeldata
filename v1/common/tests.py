"""
오류 페이지는 아무것도 조회하지 않아야 한다.

DB 커넥션 한도를 넘겨 500 이 났는데, 그 500 페이지가 컨텍스트 프로세서를 통해
세션을 또 DB 에서 읽다가 같은 이유로 죽었다. 사용자는 오류 페이지 대신 서버
원시 오류("Error running WSGI application")를 봤다. 그 조합을 막는다.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from v1.common.context_processors import board_notifications, regulatory_alerts
from v1.common.views import custom_500

User = get_user_model()


class ErrorPageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_500_페이지는_DB_없이_뜬다(self):
        request = self.factory.get('/아무데나')
        # 세션·인증 미들웨어가 붙지 않은 request 다. 컨텍스트 프로세서를 태우면
        # request.user 에서 터진다 - 그러지 않아야 한다.
        response = custom_500(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn('서버 오류', response.content.decode('utf-8'))

    def test_500_페이지는_컨텍스트_프로세서를_태우지_않는다(self):
        request = self.factory.get('/아무데나')
        with patch('v1.common.context_processors.board_notifications') as proc:
            custom_500(request)
        proc.assert_not_called()


class NotificationContextGuardTests(TestCase):
    """
    알림 개수 하나 때문에 모든 화면이 500 이 되면 안 된다.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.factory = RequestFactory()

    def _request_with_broken_user(self):
        request = self.factory.get('/')

        class _Boom:
            @property
            def is_authenticated(self):
                raise RuntimeError('DB 끊김')

        request.user = _Boom()
        return request

    def test_사용자_조회가_터져도_게시판_알림은_0을_준다(self):
        result = board_notifications(self._request_with_broken_user())
        self.assertEqual(result, {'board_notification_count': 0})

    def test_사용자_조회가_터져도_규제_알림은_0을_준다(self):
        result = regulatory_alerts(self._request_with_broken_user())
        self.assertEqual(result, {'regulatory_alert_count': 0})

    def test_게시판_조회가_터져도_0을_준다(self):
        user = User.objects.create_user(username='guard', password='x')
        request = self.factory.get('/')
        request.user = user
        request.session = {}
        with patch('v1.board.models.Board.objects.filter',
                   side_effect=RuntimeError('DB 끊김')):
            result = board_notifications(request)
        self.assertEqual(result, {'board_notification_count': 0})
