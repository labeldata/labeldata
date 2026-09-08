"""
오류 페이지는 아무것도 조회하지 않아야 한다.

DB 커넥션 한도를 넘겨 500 이 났는데, 그 500 페이지가 컨텍스트 프로세서를 통해
세션을 또 DB 에서 읽다가 같은 이유로 죽었다. 사용자는 오류 페이지 대신 서버
원시 오류("Error running WSGI application")를 봤다. 그 조합을 막는다.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase

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


class 로그인_없이_열려_있던_문(TestCase):
    """
    URL 에 걸린 뷰를 AST 로 훑어 인증 데코레이터가 없는 것을 센다.

    사람이 눈으로 세면 못 센다 — 데코레이터가 여러 줄이거나 사이에 빈 줄이
    끼면 놓친다. 실제로 놓쳐서 이런 것들이 열려 있었다.

        /label/duplicate/<id>/            인증도 소유자 확인도 없음
        /common/api-endpoint/<pk>/call/   외부 API 를 대신 호출해 줌

    열어 두는 것이 **맞는** 문이 있다(로그인·가입·공개 데모 등). 그건 아래
    목록에 적어 두고, 목록에 없는 것이 새로 생기면 시험이 잡는다.
    """

    # 열려 있어야 하는 문. 각각 왜 열려 있는지가 적혀 있어야 한다.
    PUBLIC = {
        # 로그인·가입·비밀번호 — 로그인해야 볼 수 있으면 로그인을 못 한다
        'login_view', 'logout_view', 'signup', 'signup_done_view',
        'verify_email', 'resend_verification_email',
        'password_reset_request', 'password_reset_confirm',
        # 약관·개인정보 — 가입 전에 읽는 것이다
        'terms_of_service', 'privacy_policy',
        # 홈 — 로그인 전 안내 화면
        'home', 'home_dashboard', 'home_v1',
        # 공개 데모가 부른다(익명 사용자가 쓴다)
        'get_additive_field_settings',
        # 공유 링크 — share_token 이 열쇠다
        'public_share_view',
        # API 키(hmac 비교)로 막는다
        'product_export_api', 'inspection_export_api',
        # 모바일 앱 — DRF permission_classes 로 따로 막는다
        'login', 'logout', 'register_device', 'version_check',
        'news_list', 'news_detail', 'rules_list', 'rule_detail',
        'bookmarks_list', 'bookmark_detail', 'notifications_list',
        'notification_read', 'notification_read_all', 'notification_delete',
        # 안쪽에서 request.user 로 직접 막는다
        'save_label', 'download_file', 'document_ai_extract_api',
        # 익명이면 로그인으로 되돌려 보낸다(next 를 붙여서). AJAX 면 JSON
        'create_new_label',
        # 공개 데모가 부른다. 로그인했을 때만 라벨에 손을 댄다
        'verify_report_no',
    }

    AUTH = ('login_required', 'staff_member_required', 'permission_required',
            'user_passes_test', 'admin_required')

    def _open_views(self):
        import ast
        import re
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        exposed = set()
        for path in base.rglob('urls.py'):
            text = path.read_text(encoding='utf-8-sig')
            for m in re.finditer(r"path\(\s*'[^']*'\s*,\s*(?:views\.)?(\w+)", text):
                exposed.add(m.group(1))

        found = []
        for path in base.rglob('views.py'):
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name not in exposed:
                    continue
                names = []
                for deco in node.decorator_list:
                    target = deco.func if isinstance(deco, ast.Call) else deco
                    if isinstance(target, ast.Attribute):
                        names.append(target.attr)
                    elif isinstance(target, ast.Name):
                        names.append(target.id)
                if not any(a in n for n in names for a in self.AUTH):
                    found.append(node.name)
        return set(found)

    def test_새로_열린_문이_없다(self):
        extra = self._open_views() - self.PUBLIC
        self.assertEqual(
            extra, set(),
            '인증 없이 열려 있다. 막든지, 왜 열어 두는지를 PUBLIC 에 적어라: %s'
            % sorted(extra))

    def test_막은_문이_다시_열리지_않았다(self):
        """한 번 막은 것이 조용히 풀리는 일이 실제로 있었다."""
        closed = {'duplicate_label', 'delete_label', 'call_api_endpoint',
                  'ingredient_popup', 'fetch_food_item', 'food_item_list_domestic'}
        self.assertEqual(self._open_views() & closed, set())


class 남의_표시사항은_복사되지_않는다(TestCase):
    """
    /label/duplicate/<id>/ 는 아무나 두드릴 수 있었다. 복사본이 원본 주인
    소유로 저장되니 읽어 가지는 못했지만, id 가 있는지 없는지가 새고(있으면
    돌려보내고 없으면 404) 남의 목록에 쓰레기가 쌓였다.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        from v1.label.models import MyLabel

        User = get_user_model()
        self.mine = User.objects.create_user('mine', 'mine@t.com', 'pw12345!')
        self.other = User.objects.create_user('other', 'other@t.com', 'pw12345!')
        self.label = MyLabel.objects.create(user_id=self.other,
                                            my_label_name='남의 라벨')

    def _count(self):
        from v1.label.models import MyLabel

        return MyLabel.objects.count()

    def test_로그인하지_않으면_복사되지_않는다(self):
        before = self._count()
        res = self.client.get('/label/duplicate/%d/' % self.label.my_label_id)
        self.assertIn(res.status_code, (302, 301))
        self.assertIn('/login', res['Location'])
        self.assertEqual(self._count(), before)

    def test_남의_것은_있는지_없는지도_알려_주지_않는다(self):
        """404 와 403 이 다르면 그 자체가 'id 가 있다' 는 신호다."""
        self.client.force_login(self.mine)
        before = self._count()
        res = self.client.get('/label/duplicate/%d/' % self.label.my_label_id)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self._count(), before)

    def test_내_것은_복사된다(self):
        from v1.label.models import MyLabel

        ours = MyLabel.objects.create(user_id=self.mine, my_label_name='내 라벨')
        self.client.force_login(self.mine)
        before = self._count()
        res = self.client.get('/label/duplicate/%d/' % ours.my_label_id)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self._count(), before + 1)
        copy = MyLabel.objects.exclude(pk=ours.pk).filter(user_id=self.mine).last()
        self.assertIn('복사본', copy.my_label_name)


class 열어야_할_때만_연다(SimpleTestCase):
    """
    CORS 기본값이 True 였다. 환경변수를 안 넣은 서버는 모든 출처에 API 를
    열어 준 채로 돈다 — **없으면 열린다**는 기본값은 언젠가 반드시 문다.
    """

    def test_CORS_기본값은_닫힘이다(self):
        from pathlib import Path

        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'config' / 'settings.py'
               ).read_text(encoding='utf-8-sig')
        self.assertIn(
            "config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)", src)


class 남의_표시사항은_지워지지_않는다(TestCase):
    """
    /label/delete/<id>/ 가 로그인도 소유자 확인도 없이 열려 있었다.
    누구든, 로그인하지 않은 사람까지, 남의 표시사항을 지울 수 있었다.

    게스트 차단(request.user.username == 'guest@…')은 있었지만 익명 사용자는
    username 이 빈 문자열이라 그 검사도 그냥 지나갔다.

    GET 인 것도 문제였다 — <img src="/label/delete/1/"> 한 줄이 박힌 페이지를
    로그인한 사람이 열기만 해도 지워진다.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        from v1.label.models import MyLabel

        User = get_user_model()
        self.mine = User.objects.create_user('d_mine', 'dm@t.com', 'pw12345!')
        self.other = User.objects.create_user('d_other', 'do@t.com', 'pw12345!')
        self.theirs = MyLabel.objects.create(user_id=self.other,
                                             my_label_name='남의 라벨')
        self.ours = MyLabel.objects.create(user_id=self.mine,
                                           my_label_name='내 라벨')

    def _alive(self, label):
        from v1.label.models import MyLabel

        return MyLabel.objects.filter(pk=label.pk).exists()

    def test_로그인하지_않으면_지워지지_않는다(self):
        res = self.client.post('/label/delete/%d/' % self.theirs.my_label_id)
        self.assertIn(res.status_code, (301, 302))
        self.assertIn('/login', res['Location'])
        self.assertTrue(self._alive(self.theirs))

    def test_남의_것은_지워지지_않는다(self):
        self.client.force_login(self.mine)
        res = self.client.post('/label/delete/%d/' % self.theirs.my_label_id)
        self.assertEqual(res.status_code, 404)
        self.assertTrue(self._alive(self.theirs))

    def test_링크를_여는_것만으로는_지워지지_않는다(self):
        """GET 은 받지 않는다 — 이미지 태그 하나가 삭제 버튼이 되면 안 된다."""
        self.client.force_login(self.mine)
        res = self.client.get('/label/delete/%d/' % self.ours.my_label_id)
        self.assertEqual(res.status_code, 405)
        self.assertTrue(self._alive(self.ours))

    def test_내_것은_POST_로_지워진다(self):
        self.client.force_login(self.mine)
        res = self.client.post('/label/delete/%d/' % self.ours.my_label_id)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(self._alive(self.ours))

    def test_화면도_POST_로_보낸다(self):
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_creation.js'
              ).read_text(encoding='utf-8-sig')
        self.assertNotIn('window.location.href = `/label/delete/', js)
        self.assertIn("form.method = 'POST'", js)
        self.assertIn('csrfmiddlewaretoken', js)
