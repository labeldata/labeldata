"""
오류 페이지는 아무것도 조회하지 않아야 한다.

DB 커넥션 한도를 넘겨 500 이 났는데, 그 500 페이지가 컨텍스트 프로세서를 통해
세션을 또 DB 에서 읽다가 같은 이유로 죽었다. 사용자는 오류 페이지 대신 서버
원시 오류("Error running WSGI application")를 봤다. 그 조합을 막는다.
"""
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
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
        # 받지 않기(앱) — 데코레이터는 AllowAny 지만 **뷰 안에서 막는다.**
        # 기기가 계정에 묶여 있지 않으면 403 "로그인이 필요합니다. 받지 않기는
        # 계정에 저장됩니다" 로 돌려보낸다(mobile/views.py 의 _device_user).
        # 앱은 로그인 없이도 알림을 받으므로 주소 자체는 열려 있어야 하고,
        # 권한은 device_id 가 아니라 **그 기기에 묶인 계정**이 가른다.
        'alert_mutes_list', 'alert_mute_detail',
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


class 배포본에서만_주석을_걷어낸다(SimpleTestCase):
    """
    우리 JS·CSS 주석은 **왜 그렇게 했는지**를 적어 둔 팀의 자산이다. 그런데
    /static/ 은 로그인 없이 누구나 받는다 — 재 보니 JS 2.6 MB 에 주석이
    156 KB(13%)였고, 압축도 안 된 원본이 그대로 나가고 있었다.

    주석을 지우자는 것이 아니다. **소스에는 그대로 두고 배포본에서만** 지운다.

    직접 정규식으로 지우면 반드시 틀린다 — 문자열 안의 "http://", 정규식
    리터럴 안의 "/*", 템플릿 리터럴 안의 "//" 를 주석으로 착각한다.
    여기서 지키는 것이 그것이다.
    """

    def _js(self, source):
        from rjsmin import jsmin

        return jsmin(source)

    def test_주석은_사라진다(self):
        out = self._js("""/* 왜 이렇게 했는가 */
var a = 1;  // 꼬리 주석
""")
        self.assertNotIn('왜 이렇게', out)
        self.assertNotIn('꼬리 주석', out)
        self.assertIn('a=1', out.replace(' ', ''))

    def test_문자열_안의_슬래시는_주석이_아니다(self):
        out = self._js('var u = "http://example.com/a";')
        self.assertIn('http://example.com/a', out)

    def test_정규식_안의_별표는_주석이_아니다(self):
        out = self._js(r'var re = /\/\* keep \*\//;' + chr(10) + 'var b = 2;')
        self.assertIn('keep', out)
        self.assertIn('b=2', out.replace(' ', ''))

    def test_템플릿_리터럴_안은_건드리지_않는다(self):
        out = self._js('var t = `줄 // 안쪽`;')
        self.assertIn('줄 // 안쪽', out)

    def test_한글_문자열은_그대로다(self):
        """화면에 나가는 말이라 한 글자만 달라져도 사용자가 본다."""
        out = self._js('showSnackbar("표시사항을 저장했습니다.");')
        self.assertIn('표시사항을 저장했습니다.', out)

    def test_return_뒤_줄바꿈은_지킨다(self):
        """
        여기를 틀리면 조용히 undefined 를 돌려준다. 줄바꿈을 지워
        `return` 과 `1` 을 한 줄로 붙이면 **동작이 바뀐다.**
        """
        out = self._js("""function f() {
  return
  1;
}""")
        self.assertNotIn('return 1', out)

    def test_CSS_주석도_사라지고_값은_남는다(self):
        from rcssmin import cssmin

        out = cssmin('/* 왜 470px 인가 */ .settings-panel { width: 470px; }')
        self.assertNotIn('왜 470px', out)
        self.assertIn('470px', out)

    def test_진짜_우리_파일로_한_번_돌려_본다(self):
        """만든 예제만 통과하고 정작 우리 파일에서 깨지면 소용없다."""
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_preview.js'
              ).read_text(encoding='utf-8-sig')
        out = self._js(js)
        self.assertLess(len(out), len(js))
        self.assertNotIn('두 벌로 두면', out)              # 주석은 갔다
        self.assertIn('runRuleOnlyValidation', out)         # 코드는 남았다
        self.assertIn('previewCheckedFields', out)
        self.assertIn('표시사항', out)                       # 화면 글도 남았다


class 압축은_배포본에만_적용된다(SimpleTestCase):
    """
    소스는 손대지 않는다. 무언가 깨지면 STATIC_MINIFY=0 한 줄로 원본이
    그대로 나가고, 되돌릴 것이 없다.
    """

    def _mod(self):
        from v1.common import staticfiles

        return staticfiles

    def test_이미_압축된_것과_남의_코드는_건드리지_않는다(self):
        skip = self._mod()._should_skip
        for path in ('js/vendor/x.js', 'css/bootstrap.min.css',
                     'js/lib/a.js', 'js/label/x.min.js'):
            self.assertTrue(skip(path), path)
        for path in ('js/label/label_preview.js', 'css/label_preview.css'):
            self.assertFalse(skip(path), path)

    def test_끄는_길이_있다(self):
        from pathlib import Path

        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'config' / 'settings.py'
               ).read_text(encoding='utf-8-sig')
        self.assertIn("config('STATIC_MINIFY', default=not DEBUG, cast=bool)", src)
        self.assertIn('v1.common.staticfiles.CommentStrippingStaticFilesStorage', src)

    def test_압축기가_없어도_배포는_멈추지_않는다(self):
        """주석이 남을 뿐 화면은 돈다 — 배포를 세우는 쪽이 더 나쁘다."""
        from pathlib import Path

        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'common' / 'staticfiles.py'
               ).read_text(encoding='utf-8')
        self.assertIn('except ImportError:', src)
        self.assertIn('logger.warning', src)

    def test_소스는_주석을_그대로_지킨다(self):
        """배포본에서만 지운다 — 소스에서 지우면 우리가 손해다."""
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_preview.js'
              ).read_text(encoding='utf-8-sig')
        self.assertIn('두 벌로 두면', js)


class 긁는_속도를_끊는다(TestCase):
    """
    막을 수 없는 것이 있다 — 공개 데모가 부르는 엔드포인트는 로그인을 걸 수
    없다. 그런 문은 **속도로** 끊는다. 사람이 화면에서 식품유형을 고르는
    속도와 훑어 가는 속도는 자릿수가 다르다.

    AI 판독은 다른 이유다. 호출마다 돈이 나가므로, 실수로 몰아쳐도 그대로
    청구서가 된다.

    파일 캐시라 증가가 원자적이지 않아 몇 번은 흘린다. 정확한 회계가 목적이
    아니라 무제한을 없애는 것이 목적이다.
    """

    def _src(self, rel):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8-sig')

    def test_공개로_남는_문에는_제한이_붙어_있다(self):
        label = self._src('label/views.py')
        for name in ('get_additive_field_settings', 'verify_report_no'):
            at = label.index('def %s(request)' % name)
            head = label[max(0, at - 400):at]
            self.assertIn('@ratelimit', head, '%s 에 제한이 없다' % name)

    def test_돈이_나가는_판독에_제한이_붙어_있다(self):
        at = self._src('label/views.py').index('def ocr_extract(request)')
        self.assertIn('@ratelimit', self._src('label/views.py')[at - 400:at])
        products = self._src('products/views.py')
        at2 = products.index('def document_ai_extract_api(request')
        self.assertIn('@ratelimit', products[at2 - 300:at2])

    def test_로그인_무차별_대입도_끊는다(self):
        users = self._src('user_management/views.py')
        at = users.index('def login_view(request)')
        self.assertIn('@ratelimit', users[at - 400:at])

    def test_세는_자리를_따로_둔다(self):
        """
        default 캐시는 MAX_ENTRIES 가 500 이라 자리가 차면 버린다. 세는 값이
        버려지면 제한이 조용히 풀린다 — 있다고 믿는데 없는 것이 제일 나쁘다.
        """
        from django.conf import settings as dj

        # 시험 설정은 캐시를 메모리로 갈아 끼우므로 운영 설정 파일을 직접 본다
        self.assertEqual(getattr(dj, 'RATELIMIT_USE_CACHE', None), 'ratelimit')
        src = self._src('config/settings.py')
        self.assertIn("RATELIMIT_USE_CACHE = 'ratelimit'", src)
        self.assertIn("'ratelimit': {", src)
        self.assertIn("'MAX_ENTRIES': 20000", src)

    def test_제한에_걸리면_막는다(self):
        """block=True — 세기만 하고 통과시키면 제한이 아니다."""
        for rel in ('label/views.py', 'products/views.py',
                    'user_management/views.py'):
            src = self._src(rel)
            for at in range(len(src)):
                at = src.find('@ratelimit(', at)
                if at < 0:
                    break
                self.assertIn('block=True', src[at:at + 120], rel)
                at += 1


class 자리만_채운_비밀로는_운영에_뜨지_않는다(TestCase):
    """
    settings 의 try/except UndefinedValueError 는 "환경변수가 없으면 뜨지
    마라" 는 뜻으로 쓴 그물이었다. 그런데 같은 줄의 `default=` 가 그 그물을
    무력화하고 있었다 — .env 가 통째로 빠져도 예외가 나지 않고 **소스에 적힌
    값으로 그냥 뜬다.**

    SECRET_KEY 는 세션·CSRF·비밀번호 재설정 토큰이 전부 딛고 선 값이고,
    DB_PASSWORD 는 말 그대로 DB 다. 둘 다 저장소를 볼 수 있으면 아는 값이었다.

    기본값을 그냥 지우지 않은 까닭은 개발 PC 를 멈추지 않기 위해서다. 로컬
    .env 에는 DB_ 항목이 없다. 그래서 **DEBUG 가 꺼진 곳에서만** 거부한다.
    """

    def _settings_source(self):
        from pathlib import Path
        import v1.config.settings as st
        return Path(st.__file__).read_text(encoding='utf-8')

    def test_운영에서는_기본값을_거부한다(self):
        from v1.config import settings as st

        for name in ('DJANGO_SECRET_KEY', 'DB_PASSWORD'):
            with self.subTest(name):
                bad = st._PLACEHOLDER_SECRETS[name]
                with patch.object(st, 'DEBUG', False):
                    with self.assertRaises(Exception) as caught:
                        st._reject_placeholder(name, bad)
                self.assertIn(name, str(caught.exception))

    def test_개발에서는_막지_않는다(self):
        """로컬 .env 에 DB_ 항목이 없다. 여기서 막으면 개발이 멈춘다."""
        from v1.config import settings as st

        with patch.object(st, 'DEBUG', True):
            got = st._reject_placeholder('DB_PASSWORD',
                                         st._PLACEHOLDER_SECRETS['DB_PASSWORD'])
        self.assertEqual(got, st._PLACEHOLDER_SECRETS['DB_PASSWORD'])

    def test_제대로_된_값은_그냥_지나간다(self):
        from v1.config import settings as st

        with patch.object(st, 'DEBUG', False):
            self.assertEqual(st._reject_placeholder('DB_PASSWORD', '진짜비밀'), '진짜비밀')

    def test_두_비밀_다_이_그물을_지난다(self):
        """
        한쪽만 거치면 나머지 하나가 조용히 남는다. 실제로 DB_PASSWORD 쪽이
        DATABASES 안에 따로 떨어져 있어 놓치기 쉬운 자리다.
        """
        src = self._settings_source()
        self.assertIn("_reject_placeholder('DJANGO_SECRET_KEY', SECRET_KEY)", src)
        self.assertIn("'DB_PASSWORD', config('DB_PASSWORD'", src)


class 게스트가_만든_것을_버리지_않는다(TestCase):
    """
    격리는 끝냈는데 **승격 경로를 안 만들었다.** 게스트로 제품을 만들고 BOM 을
    넣고 검증까지 돌려 본 사람이 가입하면, 그 전부가 남의 계정에 남고
    stale_guests 가 지운다. 가장 열심히 써 본 사람의 결과물을 정확히 그
    사람이 돈을 낼 마음이 든 순간에 버리고 있었다.
    """

    def setUp(self):
        from v1.common.guest import create_guest
        self.guest = create_guest()
        self.member = User.objects.create_user(
            username='real@example.com', email='real@example.com', password='x')

    def _label(self, owner, name='제품'):
        from v1.label.models import MyLabel
        return MyLabel.objects.create(user_id=owner, prdlst_nm=name)

    def _ingredient(self, owner, name='원료'):
        from v1.label.models import MyIngredient
        return MyIngredient.objects.create(user_id=owner, prdlst_nm=name, delete_YN='N')

    def test_제품과_원료가_따라온다(self):
        from v1.common.guest import promote
        from v1.label.models import MyIngredient, MyLabel

        label = self._label(self.guest)
        ing = self._ingredient(self.guest)

        moved = promote(self.guest, self.member)

        self.assertEqual(MyLabel.objects.get(pk=label.pk).user_id, self.member)
        self.assertEqual(MyIngredient.objects.get(pk=ing.pk).user_id, self.member)
        self.assertEqual(moved.get('제품'), 1)
        self.assertEqual(moved.get('원료'), 1)

    def test_BOM_과_영양성분은_따로_옮기지_않아도_따라온다(self):
        """
        제품과 원료에 FK 로 매달려 있다. 이걸 모르고 하나씩 옮기려 들면 표를
        열 개도 넘게 건드리게 된다 — 그러다 하나를 빠뜨린다.
        """
        from v1.common.guest import promote
        from v1.label.models import MyIngredientNutrition

        ing = self._ingredient(self.guest)
        MyIngredientNutrition.objects.create(ingredient=ing)

        promote(self.guest, self.member)

        nut = MyIngredientNutrition.objects.get(ingredient=ing)
        self.assertEqual(nut.ingredient.user_id, self.member)

    def test_남의_것은_건드리지_않는다(self):
        from v1.common.guest import create_guest, promote
        from v1.label.models import MyLabel

        other = create_guest()
        mine = self._label(self.guest, '내 것')
        theirs = self._label(other, '남의 것')

        promote(self.guest, self.member)

        self.assertEqual(MyLabel.objects.get(pk=mine.pk).user_id, self.member)
        self.assertEqual(MyLabel.objects.get(pk=theirs.pk).user_id, other)

    def test_옮긴_게스트는_잠근다(self):
        """세션이 아직 살아 있어도 두 번 가져가지 못하게 하는 자물쇠다."""
        from v1.common.guest import promote

        promote(self.guest, self.member)
        self.guest.refresh_from_db()
        self.assertFalse(self.guest.is_active)

    def test_게스트가_아닌_곳에서는_옮기지_않는다(self):
        """
        회원 A 의 것을 회원 B 로 옮기는 길이 생기면 안 된다. 이 함수는 게스트
        승격 하나에만 쓰인다.
        """
        from v1.common.guest import promote

        other = User.objects.create_user(username='b@example.com', password='x')
        with self.assertRaises(ValueError):
            promote(other, self.member)          # 출발지가 회원
        with self.assertRaises(ValueError):
            promote(self.guest, self.guest)      # 목적지가 게스트

    def test_빈손이면_묻지_않는다(self):
        """만든 것이 없는 사람에게 '가져올까요' 는 묻지 않느니만 못하다."""
        from v1.common.guest import promotable

        self.assertEqual(promotable(self.guest), {})
        self._label(self.guest)
        self.assertEqual(promotable(self.guest), {'제품': 1})


class 가져오기는_사람이_눌러야_한다(TestCase):
    """
    조용히 옮기면 안 된다. 남의 PC 에서 둘러본 것이 내 계정에 딸려 오면
    곤란하고, 무엇이 옮겨졌는지 모르면 빠진 것이 있어도 알 수 없다.
    """

    def setUp(self):
        from v1.common.guest import create_guest
        from v1.label.models import MyLabel

        self.guest = create_guest()
        self.member = User.objects.create_user(
            username='real@example.com', email='real@example.com', password='pw12345!')
        self.label = MyLabel.objects.create(user_id=self.guest, prdlst_nm='제품')

    def _sign_in_with_pending(self):
        self.client.force_login(self.member)
        session = self.client.session
        session['promote_guest_id'] = self.guest.pk
        session.save()

    def test_누르기_전에는_옮기지_않는다(self):
        from v1.label.models import MyLabel

        self._sign_in_with_pending()
        self.client.get('/')
        self.assertEqual(MyLabel.objects.get(pk=self.label.pk).user_id, self.guest)

    def test_누르면_옮긴다(self):
        from v1.label.models import MyLabel

        self._sign_in_with_pending()
        self.client.post(reverse('user_management:promote_guest_data'))
        self.assertEqual(MyLabel.objects.get(pk=self.label.pk).user_id, self.member)

    def test_아니요를_누르면_그대로_두고_다시_묻지_않는다(self):
        from v1.label.models import MyLabel

        self._sign_in_with_pending()
        self.client.post(reverse('user_management:promote_guest_data'), {'decline': '1'})
        self.assertEqual(MyLabel.objects.get(pk=self.label.pk).user_id, self.guest)
        self.assertNotIn('promote_guest_id', self.client.session)

    def test_두_번_눌러도_두_번째는_아무_일이_없다(self):
        self._sign_in_with_pending()
        self.client.post(reverse('user_management:promote_guest_data'))
        resp = self.client.post(reverse('user_management:promote_guest_data'))
        self.assertEqual(resp.status_code, 302)

    def test_남의_게스트_번호를_넣어_가져갈_수_없다(self):
        """
        **세션에 남은 id 로만 옮긴다.** 사용자가 보낸 id 를 받으면 남의 게스트
        계정 번호를 넣어 그 사람의 제품을 가져갈 수 있다.
        """
        from v1.common.guest import create_guest
        from v1.label.models import MyLabel

        victim = create_guest()
        theirs = MyLabel.objects.create(user_id=victim, prdlst_nm='남의 제품')

        self.client.force_login(self.member)      # 세션에 열쇠가 없다
        self.client.post(reverse('user_management:promote_guest_data'),
                         {'promote_guest_id': victim.pk, 'guest_id': victim.pk})

        self.assertEqual(MyLabel.objects.get(pk=theirs.pk).user_id, victim)

    def test_로그인하지_않으면_부를_수_없다(self):
        resp = self.client.post(reverse('user_management:promote_guest_data'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_GET_으로는_옮기지_않는다(self):
        """주소만 눌러도 데이터가 움직이면 안 된다."""
        self._sign_in_with_pending()
        resp = self.client.get(reverse('user_management:promote_guest_data'))
        self.assertEqual(resp.status_code, 405)


class 어디까지_오고_어디서_새는가(TestCase):
    """
    지금까지 **아무것도 재지 않았다.** 기능을 고치고 "좋아졌을 것" 이라고
    말해 왔는데, 좋아졌는지 나빠졌는지 알 방법이 없었다. 넷만 둔다 — 늘리면
    아무도 안 본다.
    """

    def setUp(self):
        from django.utils import timezone

        from v1.activity_log.models import UserActivityLog

        self.now = timezone.now()
        self.u = User.objects.create_user(username='a@example.com', password='x')
        User.objects.filter(pk=self.u.pk).update(
            date_joined=self.now - timezone.timedelta(days=40))
        self.u.refresh_from_db()
        self.log = UserActivityLog

    def _act(self, user, action, days_after=0):
        from django.utils import timezone

        row = self.log.objects.create(user=user, category='product', action=action)
        self.log.objects.filter(pk=row.pk).update(
            created_at=user.date_joined + timezone.timedelta(days=days_after))
        return row

    def test_단계마다_사람_수를_센다(self):
        """
        행동 수가 아니다. 제품을 백 개 만든 한 사람과 한 개씩 만든 백 사람은
        전혀 다른 이야기인데, 행동을 세면 둘이 같아 보인다.
        """
        from v1.common.services import funnel

        for _ in range(5):
            self._act(self.u, 'product_create')

        steps = {s['name']: s['users'] for s in funnel.funnel(90)['steps']}
        self.assertEqual(steps['첫 제품'], 1)

    def test_게스트는_빼고_센다(self):
        """24시간 뒤에 사라지는 계정이 재방문율을 영문 모르게 끌어내린다."""
        from v1.common.guest import create_guest
        from v1.common.services import funnel

        create_guest()
        self.assertEqual(funnel.funnel(90)['base'], 1)

    def test_가입_당일은_재방문이_아니다(self):
        """그날은 누구나 쓴다."""
        from v1.common.services import funnel

        self._act(self.u, 'product_create', days_after=0)
        self.assertEqual(funnel.return_rate(90)[7]['came'], 0)

        self._act(self.u, 'product_create', days_after=3)
        self.assertEqual(funnel.return_rate(90)[7]['came'], 1)

    def test_창이_안_닫힌_사람은_분모에서_뺀다(self):
        """
        가입 이틀째인 사람을 "28일 안에 안 왔다" 고 세면 비율이 영문 모르게
        낮아진다.
        """
        from django.utils import timezone

        from v1.common.services import funnel

        fresh = User.objects.create_user(username='new@example.com', password='x')
        User.objects.filter(pk=fresh.pk).update(
            date_joined=timezone.now() - timezone.timedelta(days=2))

        self.assertEqual(funnel.return_rate(90)[28]['base'], 1)   # 40일 된 사람만
        self.assertEqual(funnel.return_rate(90)[7]['base'], 1)

    def test_첫_검증까지는_중앙값으로_본다(self):
        """
        평균이면 한 사람이 반년 뒤에 들어와 검증할 때 통째로 끌려간다.
        """
        from pathlib import Path

        src = Path('v1/common/services/funnel.py').read_text(encoding='utf-8')
        self.assertIn('중앙값', src)
        self.assertNotIn('avg(', src.lower())

    def test_영양성분은_출처와_등급을_함께_본다(self):
        """
        공공 DB 로 채운 값은 영원히 C 등급이고, A 를 만드는 길은 성적서뿐이다.
        비율만 보면 그 차이가 안 보인다.
        """
        from v1.common.services import funnel

        got = funnel.nutrition_coverage()
        self.assertIn('by_source', got)
        self.assertIn('rate', got)

    def test_지표가_죽어도_대시보드는_뜬다(self):
        """곁들이 때문에 본체를 잃을 이유가 없다."""
        from unittest.mock import patch

        staff = User.objects.create_user(username='s@example.com', password='pw12345!',
                                         is_staff=True)
        self.client.force_login(staff)
        with patch('v1.common.services.funnel.snapshot', side_effect=RuntimeError('터짐')):
            resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 200)


class 대시보드는_한_화면에_중요한_것을_모은다(TestCase):
    """
    이 화면은 지금까지 쌓인 양을 길게 늘어놓았다. 덜 보는 묶음이 화면의 절반을
    먹으면서, 정작 고칠 곳을 알려 주는 것은 아래로 밀려 있었다.

    **지우지는 않는다.** 안 본다는 것과 필요 없다는 것은 다르다 — 접는다.
    """

    def setUp(self):
        self.staff = User.objects.create_user(
            username='s@example.com', password='pw12345!', is_staff=True)
        self.client.force_login(self.staff)

    def body(self):
        resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def test_화면이_뜬다(self):
        """지표를 얹은 뒤 로그인 직후 한 번 넘어갔다. 렌더링까지 본다."""
        self.assertIn('어디서 새는가', self.body())

    def test_덜_보는_묶음은_접혀_있다(self):
        body = self.body()
        self.assertIn('<details class="section dash-fold">', body)
        # 접힌 것이 셋 — UI 버전 · 기능별 통계 · 최근 활동
        self.assertGreaterEqual(body.count('<details class="section dash-fold">'), 3)

    def test_접어도_내용은_남는다(self):
        """접는 것과 지우는 것은 다르다."""
        body = self.body()
        self.assertIn('UI 버전 현황', body)
        self.assertIn('기능별 사용 통계', body)
        self.assertIn('최근 활동', body)

    def test_접힌_채로도_요약은_보인다(self):
        """펼치지 않고도 무엇이 들었는지 알아야 펼칠지 정한다."""
        self.assertIn('V2 ', self.body())

    def test_태그가_짝이_맞는다(self):
        """
        닫는 태그를 깊이로 찾아 바꿨다. 하나라도 어긋나면 이 아래가 통째로
        접힌 안으로 빨려 들어간다 — 눈으로는 '왜 안 보이지' 로만 보인다.
        """
        body = self.body()
        self.assertEqual(body.count('<details'), body.count('</details>'))

    def test_사람마다_한_번씩_묻지_않는다(self):
        """
        운영은 DB 가 별도 호스트라 사람 수만큼 왕복이 곱해진다. 대시보드가
        첫 요청에서 넘어간 까닭이다.
        """
        from pathlib import Path

        src = Path('v1/common/services/funnel.py').read_text(encoding='utf-8')
        block = src[src.index('def return_rate'):]
        self.assertNotIn('.exists()', block)
