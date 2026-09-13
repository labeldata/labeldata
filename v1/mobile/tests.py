"""
앱 API — 알림 받지 않기(뮤트).

웹에는 '받지 않기' 가 있는데 앱에는 없어서, 앱에서 끄려면 웹으로 와야 했다.
서버 규칙은 regulatory.services.mute 한 곳에 있으므로 앱 API 는 기기→사용자를
풀어 주고 그 서비스를 부르기만 한다. 이 시험이 확인하는 것은 **웹과 같은
결과가 나오는가** 와 **기기 갈래를 옳게 가르는가** 두 가지다.
"""
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from v1.label.models import MyLabel
from v1.mobile.models import AlertRule, AppDevice
from v1.regulatory.models import AlertMute, NewsProductMatch, RegulatoryNews

User = get_user_model()


class AppAlertMuteTest(TestCase):

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='appmute', password='x')
        self.device = AppDevice.objects.create(device_id='dev-member', user=self.user)
        self.guest = AppDevice.objects.create(device_id='dev-guest', user=None)

        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')
        self.news = RegulatoryNews.objects.create(
            external_id='appmute-1', api_source='I2620', source='domestic',
            product_name='정제수 부적합', company_name='(주)어떤식품',
            ai_keywords=['대장균'], ai_parsed=True, collected_date='2026-08-01')
        self.match = NewsProductMatch.objects.create(
            news=self.news, product=self.label, matched_keyword='대장균',
            matched_ingredient='정제수', match_score=90, risk_score=50)

    def _url(self, device_id='dev-member'):
        return '/api/mobile/devices/%s/alert-mutes/' % device_id

    def _mute(self, scope, value, device_id='dev-member'):
        return self.client.post(self._url(device_id),
                                data=json.dumps({'scope': scope, 'value': value}),
                                content_type='application/json')

    # ── 끄기 ────────────────────────────────────────────────────────────────

    def test_앱에서_끄면_기존_알림도_함께_치운다(self):
        """웹에서 끈 것과 같은 결과여야 한다 — 규칙이 두 벌이면 안 된다."""
        r = self._mute('keyword', '대장균')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['hidden'], 1)
        self.match.refresh_from_db()
        self.assertTrue(self.match.false_positive_yn)
        self.assertTrue(self.match.read_yn)

    def test_내_원료로도_끌_수_있다(self):
        self.assertEqual(self._mute('ingredient', '정제수').data['hidden'], 1)

    def test_띄어쓰기가_달라도_같은_것으로_본다(self):
        self.assertEqual(self._mute('keyword', '대장 균').data['hidden'], 1)

    def test_끈_뒤에는_다시_매칭되지_않는다(self):
        from v1.bom.models import ProductBOM
        from v1.regulatory.services import matcher

        self._mute('keyword', '대장균')
        ProductBOM.objects.create(parent_label=self.label, ingredient_name='정제수')
        self.assertEqual(matcher.find_affected_products(self.news, self.user), [])

    # ── 기기 갈래 ───────────────────────────────────────────────────────────

    def test_비회원_기기는_끄지_못한다(self):
        """AlertMute 는 user 에만 붙는다. 붙일 자리가 없으면 받지 않는다."""
        r = self._mute('keyword', '대장균', device_id='dev-guest')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(AlertMute.objects.exists())

    def test_없는_기기는_404(self):
        self.assertEqual(self._mute('keyword', 'x', device_id='no-such').status_code, 404)

    def test_웹에서_끈_것이_앱_목록에_보인다(self):
        """같은 표를 보므로 따로 맞출 것이 없다."""
        self.client.force_login(self.user)
        self.client.post('/regulatory/api/alert-mutes/',
                         data=json.dumps({'scope': 'keyword', 'value': '대장균'}),
                         content_type='application/json')
        self.client.logout()

        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual([m['value'] for m in r.data['mutes']], ['대장균'])

    # ── AlertRule 과의 충돌 ─────────────────────────────────────────────────

    def test_직접_등록한_키워드는_끄지_않고_지우게_한다(self):
        rule = AlertRule.objects.create(user=self.user, category='INGREDIENT',
                                        keyword='대장균', match_type='CONTAINS')
        r = self._mute('keyword', '대장균')
        self.assertEqual(r.status_code, 409)
        self.assertIn(rule.id, r.data['conflict_rule_ids'])

    # ── 값 검사 ─────────────────────────────────────────────────────────────

    def test_유효하지_않은_기준과_빈_값은_받지_않는다(self):
        self.assertEqual(self._mute('nope', '대장균').status_code, 400)
        self.assertEqual(self._mute('keyword', '   ').status_code, 400)
        self.assertEqual(self._mute('keyword', '가' * 201).status_code, 400)

    # ── 해제 ────────────────────────────────────────────────────────────────

    def test_해제해도_치운_알림은_되살리지_않는다(self):
        mute_id = self._mute('keyword', '대장균').data['mute']['id']
        r = self.client.delete(self._url() + '%d/' % mute_id)
        self.assertEqual(r.status_code, 204)
        self.assertFalse(AlertMute.objects.filter(pk=mute_id).exists())
        self.match.refresh_from_db()
        self.assertTrue(self.match.false_positive_yn)

    def test_남의_규칙은_지울_수_없다(self):
        other = User.objects.create_user(username='other', password='x')
        mute = AlertMute.objects.create(user=other, scope='keyword',
                                        value='대장균', value_norm='대장균')
        r = self.client.delete(self._url() + '%d/' % mute.id)
        self.assertEqual(r.status_code, 404)
        self.assertTrue(AlertMute.objects.filter(pk=mute.id).exists())


class 남의_토큰으로_남의_기기를_만지지_못한다(TestCase):
    """
    `login` 이 JWT 를 발급하는데 **어느 뷰도 그것을 검사하지 않았다** —
    `request.user` 가 mobile/views.py 에 한 번도 나오지 않았다. 소유자
    판정을 URL 의 `device_id` 하나로만 했다.

    `device_id` 는 경로에 들어 있어 로그에 그대로 남고, 값을 클라이언트가
    정하며, 일부 기기는 같은 모델끼리 겹치는 Android Build.ID 를 쓴다.

    **앱이 헤더를 보내는 판을 배포하기 전에는 전면 차단을 켤 수 없다**
    (MOBILE_REQUIRE_AUTH). 다만 토큰을 보낸 요청은 지금도 검사한다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice

        self.owner = User.objects.create_user(username='mown', password='pw12345!')
        self.other = User.objects.create_user(username='moth', password='pw12345!')
        self.device = AppDevice.objects.create(
            device_id='owner-device', user=self.owner, fcm_token='t1')
        self.guest_device = AppDevice.objects.create(
            device_id='guest-device', user=None, fcm_token='t2')

    def _rules(self, device_id, token=None):
        kw = {}
        if token:
            kw['HTTP_AUTHORIZATION'] = 'Bearer ' + token
        return self.client.get('/api/mobile/devices/%s/rules/' % device_id, **kw)

    def _token(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        return str(RefreshToken.for_user(user).access_token)

    def test_남의_토큰이면_막는다(self):
        r = self._rules('owner-device', self._token(self.other))
        self.assertEqual(r.status_code, 403)

    def test_제_토큰이면_연다(self):
        r = self._rules('owner-device', self._token(self.owner))
        self.assertEqual(r.status_code, 200)

    def test_비회원_기기는_토큰_없이도_연다(self):
        """기기 자체가 신원인 게스트를 막으면 둘러보기가 통째로 죽는다."""
        self.assertEqual(self._rules('guest-device').status_code, 200)

    def test_플래그를_켜면_토큰_없는_요청을_막는다(self):
        from django.test import override_settings

        with override_settings(MOBILE_REQUIRE_AUTH=True):
            # **401 이다.** 자격증명이 아예 없는 것이라 앱이 토큰을 새로 받아
            # 다시 시도할 수 있다 — api_client.dart 의 onError 는 401 에서만
            # _tryRefreshToken 을 부르고, 실패하면 로그인 화면으로 돌린다.
            self.assertEqual(self._rules('owner-device').status_code, 401)
            # 게스트 기기는 그때도 열려 있어야 한다
            self.assertEqual(self._rules('guest-device').status_code, 200)

    def test_버전_비교가_자리_수에_흔들리지_않는다(self):
        from v1.mobile.models import AppVersion

        AppVersion.objects.create(platform='android', min_version='1.2',
                                  latest_version='1.3.0', store_url='x')
        # 1.2.0 은 1.2 와 같다 — 강제 업데이트가 뜨면 안 된다
        r = self.client.get('/api/mobile/version-check/?platform=android&version=1.2.0')
        self.assertFalse(r.json()['force_update'])
        # 낮은 판은 걸린다
        r = self.client.get('/api/mobile/version-check/?platform=android&version=1.1.9')
        self.assertTrue(r.json()['force_update'])

    def test_빌드_번호가_붙어도_판정한다(self):
        from v1.mobile.models import AppVersion

        AppVersion.objects.create(platform='android', min_version='1.2.0',
                                  latest_version='1.3.0', store_url='x')
        # Flutter 의 x.y.z+build — 예전에는 int() 가 던져 조용히 무력화됐다
        r = self.client.get('/api/mobile/version-check/?platform=android&version=1.1.0%2B17')
        self.assertTrue(r.json()['force_update'])
        r = self.client.get('/api/mobile/version-check/?platform=android&version=1.2.0%2B17')
        self.assertFalse(r.json()['force_update'])

    def test_기본값은_꺼짐이다(self):
        """앱이 헤더를 싣기 전에 켜면 모든 사용자가 그 자리에서 못 쓴다."""
        from django.conf import settings

        self.assertFalse(getattr(settings, 'MOBILE_REQUIRE_AUTH', False))

    def test_기기를_다루는_모든_뷰가_그_문을_지난다(self):
        """새 엔드포인트가 생겼을 때 여기서 걸린다."""
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'mobile/views.py').read_text(encoding='utf-8')
        # 정의부(`def device_access_error(request, device):`)는 빼고 센다
        calls = text.count('device_access_error(request, device)')
        calls -= text.count('def device_access_error(request, device)')
        self.assertEqual(text.count('device = _get_device_or_404(device_id)'), calls)


class 로그아웃이_계정_키워드를_지우지_않는다(TestCase):
    """
    로그아웃이 `AlertRule.objects.filter(user=user_obj)` 로 **그 계정의
    키워드 전체**를 훑어 비회원 한도(5개)를 넘는 것을 껐다.

    · 범위가 계정이라 폰 두 대 쓰는 사람이 한 대에서 로그아웃하면
      다른 폰과 웹의 키워드까지 꺼졌다
    · 다시 켜 주는 코드가 앱에도 웹에도 없다 — 25개가 사실상 사라졌다
    · 목록에는 남아 있고 알림만 안 온다. 원인을 짐작할 수 없다
    """

    def setUp(self):
        import json

        from v1.mobile.models import AlertRule, AppDevice

        self._json = json
        self.user = User.objects.create_user(username='lo', password='pw12345!')
        self.device = AppDevice.objects.create(
            device_id='lo-device', user=self.user)
        for i in range(12):
            AlertRule.objects.create(
                user=self.user, category='INGREDIENT', keyword='kw%d' % i,
                match_type='CONTAINS', is_active=True)

    def _logout(self):
        return self.client.post(
            '/api/mobile/logout/',
            data=self._json.dumps({'device_id': 'lo-device'}),
            content_type='application/json')

    def test_회원_키워드는_그대로_남는다(self):
        from v1.mobile.models import AlertRule

        self.assertEqual(self._logout().status_code, 200)
        self.assertEqual(
            AlertRule.objects.filter(user=self.user, is_active=True).count(), 12)

    def test_기기_연결은_끊긴다(self):
        from v1.mobile.models import AppDevice

        self._logout()
        self.device.refresh_from_db()
        self.assertIsNone(self.device.user_id)
        self.assertTrue(AppDevice.objects.filter(device_id='lo-device').exists())

    def test_비회원_규칙은_한도까지만_남는다(self):
        """그 규칙들은 기기에 매달려 있으므로 한도가 뜻을 갖는다."""
        from django.conf import settings

        from v1.mobile.models import AlertRule

        for i in range(8):
            AlertRule.objects.create(
                device=self.device, user=None, category='INGREDIENT',
                keyword='guest%d' % i, match_type='CONTAINS', is_active=True)
        self._logout()
        left = AlertRule.objects.filter(
            device=self.device, user__isnull=True, is_active=True).count()
        self.assertEqual(left, settings.MOBILE_GUEST_MAX_RULES)


class 키워드_한도에_우회로가_없다(TestCase):
    """
    한도 검사가 POST 에만 있었다. 30개를 만들고 전부 끈 뒤 또 30개를 만들고…
    를 반복한 다음 전부 PATCH 로 켜면 **활성 규칙 수에 상한이 사라진다.**
    활성 규칙은 수집 때마다 전건 RapidFuzz 매칭을 도므로 서버 부하와 직결된다.
    """

    def setUp(self):
        import json

        from django.test import override_settings

        from v1.mobile.models import AppDevice

        self._json = json
        self.user = User.objects.create_user(username='qa', password='pw12345!')
        self.device = AppDevice.objects.create(device_id='qa-device', user=self.user)
        self._ov = override_settings(MOBILE_MEMBER_MAX_RULES=3)
        self._ov.enable()
        self.addCleanup(self._ov.disable)

    def _post(self, keyword):
        return self.client.post(
            '/api/mobile/devices/qa-device/rules/',
            data=self._json.dumps({'category': 'INGREDIENT', 'keyword': keyword,
                                   'match_type': 'CONTAINS'}),
            content_type='application/json')

    def _patch(self, rule_id, body):
        return self.client.patch(
            '/api/mobile/devices/qa-device/rules/%d/' % rule_id,
            data=self._json.dumps(body), content_type='application/json')

    def test_끄고_만들고_다시_켜는_길이_막힌다(self):
        from v1.mobile.models import AlertRule

        first = [self._post('a%d' % i).json()['id'] for i in range(3)]
        # 셋을 끄고 셋을 더 만든다 — 여기까지는 정상
        for rid in first:
            self.assertEqual(self._patch(rid, {'is_active': False}).status_code, 200)
        for i in range(3):
            self.assertEqual(self._post('b%d' % i).status_code, 201)

        # 이제 껐던 것을 다시 켜려 하면 막혀야 한다
        blocked = self._patch(first[0], {'is_active': True})
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(
            AlertRule.objects.filter(user=self.user, is_active=True).count(), 3)

    def test_한도_안이면_다시_켤_수_있다(self):
        rid = self._post('one').json()['id']
        self.assertEqual(self._patch(rid, {'is_active': False}).status_code, 200)
        self.assertEqual(self._patch(rid, {'is_active': True}).status_code, 200)

    def test_중복_키워드로_바꾸면_500_이_아니다(self):
        a = self._post('alpha').json()['id']
        self._post('beta')
        r = self._patch(a, {'keyword': 'beta'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('이미', r.json()['error'])


class 앱_API_가_이상한_입력에_500_을_내지_않는다(TestCase):
    """
    `int('abc')` 가 그대로 올라가면 DRF 가 잡지 않아 **HTML 500** 이 나가고,
    JSON 을 기대하는 앱은 파싱에서 죽는다. 웹에서 같은 자리를 고쳤는데
    (`?id=abc`) 앱은 안 봤다.
    """

    def test_이상한_page_에도_200(self):
        for q in ('abc', '-5', '', '9999999999999999999999'):
            r = self.client.get('/api/mobile/news/?page=' + q)
            self.assertEqual(r.status_code, 200, q)

    def test_로그인에_횟수_제한이_걸려_있다(self):
        """웹 로그인은 막혀 있는데 같은 자격증명을 쓰는 앱은 안 막혀 있었다."""
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'mobile/views.py').read_text(encoding='utf-8')
        i = text.index('def login(request)')
        self.assertIn('@ratelimit', text[max(0, i - 400):i])


class 알림함을_통째로_비우지_않는다(TestCase):
    """
    · 소급이 100건 걸리면 `_trim_notifications(device, 1)` 이 되어 기존
      알림을 **0개까지** 지웠다. 흔한 낱말을 키워드로 넣는 순간, 안 읽은
      "내 제품 부적합" 을 포함한 100건이 알린 적 없이 사라졌다.
    · 지우는 차례도 거꾸로였다 — `trigger_type='keyword'` 가 **아닌 것을
      먼저** 지워, 가장 중요한 알림이 몇 달 된 키워드 알림보다 먼저 갔다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice
        from v1.regulatory.models import RegulatoryNews

        self.user = User.objects.create_user(username='tr', password='x')
        self.device = AppDevice.objects.create(device_id='tr-device', user=self.user)
        self.news = [
            RegulatoryNews.objects.create(
                external_id='tn%d' % i, api_source='I2620', source='domestic',
                product_name='n%d' % i, ai_parsed=True, collected_date='2026-09-01')
            for i in range(6)
        ]

    def _log(self, news, trigger_type, is_read):
        from v1.mobile.models import PushNotificationLog

        return PushNotificationLog.objects.create(
            device=self.device, news=news, trigger_type=trigger_type,
            trigger_label='x', is_read=is_read)

    def test_안_읽은_제품_알림이_마지막까지_남는다(self):
        from v1.mobile.models import PushNotificationLog
        from v1.mobile.services.push_service import _trim_notifications

        keep = self._log(self.news[0], 'product', False)
        self._log(self.news[1], 'keyword', True)
        self._log(self.news[2], 'keyword', True)
        self._log(self.news[3], 'product', True)

        _trim_notifications(self.device, 2)          # 둘만 남긴다
        left = set(PushNotificationLog.objects
                   .filter(device=self.device).values_list('pk', flat=True))
        self.assertIn(keep.pk, left)

    def test_상한_안이면_아무것도_안_지운다(self):
        from v1.mobile.models import PushNotificationLog
        from v1.mobile.services.push_service import _trim_notifications

        self._log(self.news[0], 'product', False)
        _trim_notifications(self.device, 10)
        self.assertEqual(
            PushNotificationLog.objects.filter(device=self.device).count(), 1)

    def test_소급이_알림함을_비우지_않는다(self):
        from pathlib import Path

        from django.conf import settings as dj

        import re

        text = (Path(dj.BASE_DIR) / 'mobile/services/push_service.py'
                ).read_text(encoding='utf-8')
        # 왜 그랬는지 적은 주석에도 그 식이 나온다 — 코드만 본다
        code = re.sub(r'^\s*#.*$', '', text, flags=re.M)
        self.assertNotIn('max(1, max_noti - len(to_create))', code)
        self.assertIn('_trim_notifications(device, max_noti)', code)


class 앱이_부르는_길이_서버에_실제로_있다(TestCase):
    """
    앱의 인터셉터는 **401 을 받으면 무조건** `POST /token/refresh/` 를 친다
    (`api_client.dart:80-96`). 그 경로가 서버에 없으면 Django 가 HTML 404 를
    주고, 앱의 `catch (_)` 가 그것을 잡아 **리프레시 토큰까지 지운다**
    (`clearTokens()`). 사용자는 조용히 로그아웃되고, 화면은 여전히 로그인한
    것처럼 보인다.

    그리고 이것 때문에 `MOBILE_REQUIRE_AUTH` 를 켤 수 없었다 — 켜는 순간
    액세스 토큰이 만료된(7일) 사용자가 전부 이 길로 튕긴다.

    `/account/delete/` 도 같다. 개인정보처리방침이 "[내 정보/설정 → 회원
    탈퇴] 기능을 통해 직접 계정 삭제 및 정보 파기를 요청할 수 있습니다" 라고
    적어 두었는데 서버에 그 경로가 없어 **버튼이 늘 '알 수 없는 오류' 로
    끝났다.**
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='rt@example.com', email='rt@example.com', password='pw12345!')
        self.device = AppDevice.objects.create(device_id='rt-device', user=self.user)

    def _refresh_token(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        return str(RefreshToken.for_user(self.user))

    # ── 토큰 재발급 ──────────────────────────────────────────────────────

    def test_리프레시_토큰으로_액세스_토큰을_받는다(self):
        r = self.client.post(
            '/api/mobile/token/refresh/',
            data=json.dumps({'refresh': self._refresh_token()}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get('access'))

    def test_받은_액세스_토큰이_실제로_통한다(self):
        """재발급만 되고 안 통하면 앱은 무한히 401 을 돈다."""
        access = self.client.post(
            '/api/mobile/token/refresh/',
            data=json.dumps({'refresh': self._refresh_token()}),
            content_type='application/json').json()['access']
        r = self.client.get(
            '/api/mobile/devices/rt-device/rules/',
            HTTP_AUTHORIZATION='Bearer ' + access)
        self.assertEqual(r.status_code, 200)

    def test_망가진_리프레시_토큰은_401_이고_JSON_이다(self):
        r = self.client.post(
            '/api/mobile/token/refresh/',
            data=json.dumps({'refresh': 'not-a-token'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 401)
        self.assertIn('error', r.json())

    def test_리프레시_토큰을_안_보내면_400(self):
        r = self.client.post(
            '/api/mobile/token/refresh/', data=json.dumps({}),
            content_type='application/json')
        self.assertEqual(r.status_code, 400)

    # ── 회원 탈퇴 ────────────────────────────────────────────────────────

    def _delete(self, password):
        return self.client.post(
            '/api/mobile/account/delete/',
            data=json.dumps({'device_id': 'rt-device', 'password': password}),
            content_type='application/json')

    def test_비밀번호가_맞으면_탈퇴된다(self):
        r = self._delete('pw12345!')
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_비밀번호가_틀리면_막고_한국어로_말한다(self):
        r = self._delete('wrong-password')
        self.assertEqual(r.status_code, 400)
        self.assertIn('비밀번호', r.json()['error'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_탈퇴하면_앱이_들고_있던_개인정보가_그_자리에서_지워진다(self):
        """
        개인정보처리방침이 "기기 식별 정보는 즉시 파기됩니다" 라고 적어 두었다.
        """
        from v1.mobile.models import Bookmark, PushNotificationLog

        news = RegulatoryNews.objects.create(
            external_id='del-1', api_source='I2620', source='domestic',
            product_name='n', ai_parsed=True, collected_date='2026-09-01')
        AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='우유',
            match_type='CONTAINS', is_active=True)
        Bookmark.objects.create(device=self.device, news=news)
        PushNotificationLog.objects.create(
            device=self.device, news=news, trigger_type='keyword',
            trigger_label='우유')

        self.assertEqual(self._delete('pw12345!').status_code, 200)
        self.assertFalse(AppDevice.objects.filter(device_id='rt-device').exists())
        self.assertFalse(AlertRule.objects.filter(user=self.user).exists())
        self.assertFalse(Bookmark.objects.filter(news=news).exists())
        self.assertFalse(PushNotificationLog.objects.filter(news=news).exists())

    def test_비회원_기기로는_탈퇴할_수_없다(self):
        AppDevice.objects.create(device_id='guest-del', user=None)
        r = self.client.post(
            '/api/mobile/account/delete/',
            data=json.dumps({'device_id': 'guest-del', 'password': 'x'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 403)


class 기기_등록이_안_보낸_칸을_지우지_않는다(TestCase):
    """
    앱은 이 엔드포인트를 **서로 다른 두 곳**에서 부르고, 보내는 칸이 겹치지
    않는다.

    · `auth_provider.dart:24-28` — 앱 켤 때마다 `platform`·`app_version`
    · `fcm_service.dart:109-112` — 토큰 갱신 때 `fcm_token`

    서버는 `update_or_create(defaults={세 칸 전부})` 였다. 그래서 한쪽이
    부를 때마다 **다른 쪽이 넣어 둔 값이 지워졌다.**

    · iPhone 의 `platform` 이 DB 에서 영구히 `'android'` 가 된다
    · `app_version` 이 늘 빈 문자열 — 어느 기기가 어느 판인지 서버가 모른다
    · 앱을 켤 때마다 `fcm_token` 이 한 번 NULL 이 된다. 그 틈에 발송 배치가
      돌면 **그 기기는 다음 실행까지 푸시를 못 받는다.**
    """

    URL = '/api/mobile/device/register/'

    def _post(self, payload):
        return self.client.post(self.URL, data=json.dumps(payload),
                                content_type='application/json')

    def test_토큰만_보내면_platform_과_버전이_남는다(self):
        self._post({'device_id': 'd1', 'platform': 'ios', 'app_version': '1.0.11'})
        self._post({'device_id': 'd1', 'fcm_token': 'tok-1'})
        d = AppDevice.objects.get(device_id='d1')
        self.assertEqual(d.platform, 'ios')
        self.assertEqual(d.app_version, '1.0.11')
        self.assertEqual(d.fcm_token, 'tok-1')

    def test_버전만_보내면_토큰이_남는다(self):
        self._post({'device_id': 'd2', 'fcm_token': 'tok-2'})
        self._post({'device_id': 'd2', 'platform': 'ios', 'app_version': '1.0.12'})
        d = AppDevice.objects.get(device_id='d2')
        self.assertEqual(d.fcm_token, 'tok-2')
        self.assertEqual(d.app_version, '1.0.12')

    def test_처음_만들_때는_기본값을_쓴다(self):
        self._post({'device_id': 'd3'})
        d = AppDevice.objects.get(device_id='d3')
        self.assertEqual(d.platform, 'android')
        self.assertEqual(d.app_version, '')

    def test_빈_값으로는_덮지_않는다(self):
        self._post({'device_id': 'd4', 'fcm_token': 'tok-4'})
        self._post({'device_id': 'd4', 'fcm_token': ''})
        self.assertEqual(AppDevice.objects.get(device_id='d4').fcm_token, 'tok-4')


class 알림_목록의_번호가_두_갈래에서_겹치지_않는다(TestCase):
    """
    `notifications_list` 는 `PushNotificationLog` 와 `InspectionMatch` 를
    **평평한 배열 하나로** 합쳐 준다. 두 테이블은 각자 1부터 도는 pk 를 쓰고
    직렬화 결과에서 둘 다 그냥 `id` 다 — **네임스페이스가 없다.**

    앱은 그 `id` 하나로 원소를 되찾아 `?type=` 을 정한다
    (`notifications_provider.dart:60, 88` 의 `firstWhere`). 번호가 겹치면
    **먼저 걸린 것**을 집으므로:

    · 수거검사 알림을 지웠는데 아무 상관 없는 부적합 알림이 사라진다
    · 화면에서는 두 건이 함께 없어지고, 새로고침하면 한 건이 되살아난다
    · 읽음 처리와 배지 숫자도 같은 방식으로 어긋난다

    두 테이블 다 1부터 시작하므로 신규 사용자에게는 겹치는 것이 **기본**이다.
    """

    def setUp(self):
        from v1.mobile.models import PushNotificationLog
        from v1.regulatory.models import InspectionMatch, InspectionResult

        self.user = User.objects.create_user(username='ni', password='pw12345!')
        self.device = AppDevice.objects.create(device_id='ni-device', user=self.user)
        news = RegulatoryNews.objects.create(
            external_id='ni-1', api_source='I2620', source='domestic',
            product_name='뉴스', ai_parsed=True, collected_date='2026-09-01')
        self.log = PushNotificationLog.objects.create(
            device=self.device, news=news, trigger_type='keyword',
            trigger_label='우유', sent_at='2026-09-02T00:00:00+09:00')
        insp = InspectionResult.objects.create(
            tkawyprno='ni-insp-1', prdtnm='검사제품', tkawydtm='20260902')
        self.match = InspectionMatch.objects.create(
            user=self.user, inspection=insp, alert_phase=1,
            match_reason='PRODUCT',
            matched_value='검사제품', notified_at='2026-09-02T00:00:00+09:00')

    def _list(self):
        r = self.client.get('/api/mobile/devices/ni-device/notifications/')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_두_갈래의_번호가_서로_다르다(self):
        ids = [n['id'] for n in self._list()]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2, '번호가 겹친다: %s' % ids)

    def test_목록이_준_번호로_지우면_그것이_지워진다(self):
        from v1.mobile.models import PushNotificationLog
        from v1.regulatory.models import InspectionMatch

        items = self._list()
        insp_item = [n for n in items if n['trigger_type'] == 'inspection'][0]
        r = self.client.delete(
            '/api/mobile/devices/ni-device/notifications/%d/?type=inspection'
            % insp_item['id'])
        self.assertEqual(r.status_code, 204)
        self.assertFalse(InspectionMatch.objects.filter(pk=self.match.pk).exists())
        self.assertTrue(PushNotificationLog.objects.filter(pk=self.log.pk).exists())

    def test_목록이_준_번호로_읽으면_그것이_읽힌다(self):
        items = self._list()
        insp_item = [n for n in items if n['trigger_type'] == 'inspection'][0]
        r = self.client.patch(
            '/api/mobile/devices/ni-device/notifications/%d/read/?type=inspection'
            % insp_item['id'])
        self.assertEqual(r.status_code, 200)
        self.match.refresh_from_db()
        self.assertTrue(self.match.read_yn)
        self.log.refresh_from_db()
        self.assertFalse(self.log.is_read)

    def test_옛_판_앱이_보내는_원래_pk_도_계속_받는다(self):
        """이미 깔려 있는 앱은 예전 번호를 보낸다 — 그것도 통해야 한다."""
        r = self.client.patch(
            '/api/mobile/devices/ni-device/notifications/%d/read/?type=inspection'
            % self.match.pk)
        self.assertEqual(r.status_code, 200)
        self.match.refresh_from_db()
        self.assertTrue(self.match.read_yn)


class 부적합_상세가_앱이_그리는_칸을_실제로_보낸다(TestCase):
    """
    앱 상세 화면에는 "검출 물질"·"관련 원재료"·"원문" 세 섹션이 구현돼 있다
    (`news_detail_screen.dart:151-234`, 80여 줄). 그런데 시리얼라이저의
    `fields` 에 그 셋이 **없어서** 값이 늘 null 이었다 — 세 섹션이 한 번도
    렌더된 적이 없다.

    지자체 행정처분처럼 원문에만 정보가 있는 건은 앱에서 볼 수 있는 것이
    사실상 없었다.
    """

    def setUp(self):
        self.news = RegulatoryNews.objects.create(
            external_id='nd-1', api_source='I2620', source='domestic',
            product_name='상세제품', ai_parsed=True, collected_date='2026-09-01',
            raw_detail_text='원문 전체 내용',
            ai_issues=[{'name': '우유'}],
            ai_substances=['대장균'],
        )

    def test_상세가_세_칸을_보낸다(self):
        r = self.client.get('/api/mobile/news/%d/' % self.news.pk)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['raw_detail_text'], '원문 전체 내용')
        self.assertEqual(body['ai_substances'], ['대장균'])
        self.assertEqual(body['ai_issues'], [{'name': '우유'}])

    def test_목록에는_원문을_싣지_않는다(self):
        """목록 20건마다 원문을 실으면 응답이 통째로 무거워진다."""
        r = self.client.get('/api/mobile/news/')
        self.assertEqual(r.status_code, 200)
        results = r.json()['results']
        self.assertTrue(results)
        self.assertNotIn('raw_detail_text', results[0])


class 앱을_지운_비회원_기기가_영원히_남지_않는다(TestCase):
    """
    개인정보처리방침이 "비회원은 모바일 앱을 삭제하는 즉시 기기 연동 데이터가
    파기됩니다" 라고 약속한다. 그런데 **서버는 앱이 지워진 것을 알 수 없다** —
    앱 삭제는 아무것도 보내지 않는다. `AppDevice` 와 거기 매달린 보관함·
    알림 내역·알림 키워드가 그대로 남았고, 지우는 코드가 저장소 어디에도
    없었다. 약속한 파기가 한 번도 일어나지 않았다.

    알 수 있는 것은 마지막으로 서버를 부른 때뿐이다. 오래 잠잠한 **비회원**
    기기를 치운다. 회원 기기는 계정에 매달려 있고 탈퇴 때 함께 지운다.
    """

    def setUp(self):
        from django.utils import timezone

        from v1.mobile.models import AppDevice, Bookmark
        from v1.regulatory.models import RegulatoryNews

        self.old = timezone.now() - timezone.timedelta(days=200)
        self.news = RegulatoryNews.objects.create(
            external_id='sd-1', api_source='I2620', source='domestic',
            product_name='n', ai_parsed=True, collected_date='2026-01-01')

        self.guest_old = AppDevice.objects.create(device_id='guest-old', user=None)
        self.guest_new = AppDevice.objects.create(device_id='guest-new', user=None)
        self.user = User.objects.create_user(username='keeper', password='x')
        self.member_old = AppDevice.objects.create(
            device_id='member-old', user=self.user)
        Bookmark.objects.create(device=self.guest_old, news=self.news)

        # auto_now 라 update() 로 직접 되돌린다
        AppDevice.objects.filter(
            pk__in=[self.guest_old.pk, self.member_old.pk]
        ).update(last_active_at=self.old)

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('purge_stale_devices', *args, stdout=out)
        return out.getvalue()

    def test_기본은_보여_주기만_한다(self):
        from v1.mobile.models import AppDevice

        text = self._run()
        self.assertIn('보여 주기만 했다', text)
        self.assertTrue(AppDevice.objects.filter(device_id='guest-old').exists())

    def test_잠잠한_비회원_기기를_지운다(self):
        from v1.mobile.models import AppDevice

        self._run('--apply')
        self.assertFalse(AppDevice.objects.filter(device_id='guest-old').exists())

    def test_그_기기의_보관함도_함께_간다(self):
        from v1.mobile.models import Bookmark

        self._run('--apply')
        self.assertFalse(Bookmark.objects.filter(news=self.news).exists())

    def test_최근에_쓴_기기는_건드리지_않는다(self):
        from v1.mobile.models import AppDevice

        self._run('--apply')
        self.assertTrue(AppDevice.objects.filter(device_id='guest-new').exists())

    def test_회원_기기는_잠잠해도_건드리지_않는다(self):
        from v1.mobile.models import AppDevice

        self._run('--apply')
        self.assertTrue(AppDevice.objects.filter(device_id='member-old').exists())

    def test_기기가_서버를_부르면_잠잠함이_풀린다(self):
        """`last_active_at` 이 안 올라가면 쓰는 기기를 지운다."""
        from v1.mobile.models import AppDevice

        self.client.post('/api/mobile/device/register/',
                         data=json.dumps({'device_id': 'guest-old'}),
                         content_type='application/json')
        self._run('--apply')
        self.assertTrue(AppDevice.objects.filter(device_id='guest-old').exists())


class 내_제품_알림이_키워드_알림에_가려지지_않는다(TestCase):
    """
    이 앱이 파는 것은 "**내 것**이 걸렸다" 를 알려 주는 일이다. 그런데 그
    알림이 만들어지지 않는 길이 있었다.

    `send_mobile_alerts_for_news` 가 키워드 로그를 **먼저** 만들고, 그 다음
    제품·원료 로그를 만든다. 둘 다 `(device, news)` 가 이미 있으면 건너뛴다.
    그래서 같은 뉴스가 등록해 둔 키워드에도 걸리면 — 흔한 낱말 하나만
    등록해 두어도 그렇게 된다 — **제품 매칭 로그가 아예 안 생긴다.**

    사용자가 보는 것: 내 제품이 실제로 부적합에 걸렸는데 알림 제목이
    `⚠️ 키워드 알림: #우유` 다. `⚠️ 내 제품 관련 알림` 은 오지 않는다.
    `_trim_notifications` 의 티어 설계가 "안 읽은 제품·원료 알림을 마지막까지
    지킨다" 고 명시할 만큼 중요하게 다루는 그 알림이, 애초에 만들어지지
    않았다.

    한 뉴스에 한 사람당 알림은 하나면 된다 — 그 하나가 **더 중요한 쪽**이어야
    한다.
    """

    def setUp(self):
        from v1.label.models import MyLabel
        from v1.mobile.models import AlertRule, AppDevice
        from v1.regulatory.models import NewsProductMatch, RegulatoryNews

        self.user = User.objects.create_user(username='ownprod', password='x')
        self.device = AppDevice.objects.create(device_id='prod-device', user=self.user)
        self.news = RegulatoryNews.objects.create(
            external_id='pk-1', api_source='I2620', source='domestic',
            product_name='우유식빵', company_name='어떤제과', ai_parsed=True,
            collected_date='2026-09-01', ai_keywords=['우유'])
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='내 우유식빵', delete_YN='N',
            prdlst_nm='내 우유식빵')
        NewsProductMatch.objects.create(
            news=self.news, product=self.label,
            matched_keyword='우유', matched_ingredient='우유',
            match_score=90, risk_score=50)
        AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='우유',
            match_type='CONTAINS', is_active=True)

    def _run(self):
        from v1.mobile.services.push_service import send_mobile_alerts_for_news

        return send_mobile_alerts_for_news(self.news)

    def _logs(self):
        from v1.mobile.models import PushNotificationLog

        return list(PushNotificationLog.objects.filter(device=self.device))

    def test_제품_매칭이_있으면_그것으로_알린다(self):
        self._run()
        logs = self._logs()
        self.assertEqual(len(logs), 1, '한 뉴스에 알림은 하나여야 한다')
        self.assertEqual(logs[0].trigger_type, 'product')
        self.assertIn('내 우유식빵', logs[0].trigger_label)

    def test_키워드_매칭_기록_자체는_그대로_남는다(self):
        """웹 목록의 '키워드' 배지가 그것을 본다 — 없애면 안 된다."""
        from v1.regulatory.models import NewsKeywordMatch

        self._run()
        self.assertTrue(
            NewsKeywordMatch.objects.filter(user=self.user, news=self.news).exists())

    def test_제품_매칭이_없으면_키워드로_알린다(self):
        from v1.mobile.models import PushNotificationLog
        from v1.regulatory.models import NewsProductMatch

        NewsProductMatch.objects.all().delete()
        self._run()
        logs = self._logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].trigger_type, 'keyword')
        self.assertEqual(logs[0].trigger_label, '우유')

    def test_두_번_돌려도_알림이_늘지_않는다(self):
        self._run()
        self._run()
        self.assertEqual(len(self._logs()), 1)

    def test_제품이_여럿이면_몇_건인지_말해_준다(self):
        """
        예전에는 첫 건만 이름을 남기고 나머지는 없는 셈이 됐다 —
        `if user_id not in user_trigger`.
        """
        from v1.label.models import MyLabel
        from v1.regulatory.models import NewsProductMatch

        second = MyLabel.objects.create(
            user_id=self.user, my_label_name='내 우유케이크', delete_YN='N',
            prdlst_nm='내 우유케이크')
        NewsProductMatch.objects.create(
            news=self.news, product=second,
            matched_keyword='우유', matched_ingredient='우유',
            match_score=80, risk_score=40)
        self._run()
        label = self._logs()[0].trigger_label
        self.assertIn('외 1건', label)

    def test_지운_제품은_알리지_않는다(self):
        from v1.regulatory.models import NewsProductMatch

        NewsProductMatch.objects.all().delete()
        self.label.delete_YN = 'Y'
        self.label.save(update_fields=['delete_YN'])
        NewsProductMatch.objects.create(
            news=self.news, product=self.label,
            matched_keyword='우유', matched_ingredient='우유',
            match_score=90, risk_score=50)
        self._run()
        logs = self._logs()
        # 지운 제품 때문에 '내 제품' 알림이 가지는 않는다 (키워드로는 갈 수 있다)
        self.assertTrue(all(l.trigger_type != 'product' for l in logs))


class 앱과_웹이_같은_알림을_두_번_읽게_하지_않는다(TestCase):
    """
    웹 사이드바 배지는 `NewsKeywordMatch.read_yn` 을 센다(selectors). 앱의
    읽음 처리는 `PushNotificationLog.is_read` 만 바꿨다 — **다른 표다.**

    그래서 앱에서 '모두 읽음' 을 눌러 알림함을 비워도 웹에 들어가면 배지
    숫자가 그대로다. 같은 알림을 두 화면에서 두 번 읽어야 한다. 60초 캐시도
    지우지 않아 그 위에 한 번 더 어긋난다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice, PushNotificationLog
        from v1.regulatory.models import NewsKeywordMatch, RegulatoryNews

        self.user = User.objects.create_user(username='rdsync', password='x')
        self.device = AppDevice.objects.create(device_id='rd-device', user=self.user)
        self.news = RegulatoryNews.objects.create(
            external_id='rd-1', api_source='I2620', source='domestic',
            product_name='뉴스', ai_parsed=True, collected_date='2026-09-01')
        self.rule = AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='우유',
            match_type='CONTAINS', is_active=True)
        self.match = NewsKeywordMatch.objects.create(
            user=self.user, news=self.news, rule=self.rule,
            matched_keyword='우유', read_yn=False, dismissed_yn=False)
        self.log = PushNotificationLog.objects.create(
            device=self.device, news=self.news, rule_triggered=self.rule,
            trigger_type='keyword', trigger_label='우유',
            sent_at='2026-09-02T00:00:00+09:00')
        cache.clear()

    def _web_unread(self):
        from v1.regulatory import selectors

        return selectors.unread_news_count(self.user)

    def test_처음에는_웹_배지가_센다(self):
        self.assertEqual(self._web_unread(), 1)

    def test_앱에서_한_건_읽으면_웹_배지가_내려간다(self):
        r = self.client.patch(
            '/api/mobile/devices/rd-device/notifications/%d/read/' % self.log.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._web_unread(), 0)

    def test_앱에서_모두_읽으면_웹_배지가_비워진다(self):
        r = self.client.post(
            '/api/mobile/devices/rd-device/notifications/read-all/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._web_unread(), 0)

    def test_배지_캐시도_함께_지운다(self):
        """60초 캐시가 남아 있으면 그동안은 여전히 어긋난다."""
        from django.core.cache import cache as dj_cache

        key = 'regulatory_alert_count_%s' % self.user.pk
        dj_cache.set(key, 7, 60)
        self.client.post('/api/mobile/devices/rd-device/notifications/read-all/')
        self.assertIsNone(dj_cache.get(key))

    def test_남의_알림까지_읽지는_않는다(self):
        from v1.regulatory.models import NewsKeywordMatch

        other = User.objects.create_user(username='rdother', password='x')
        other_rule = AlertRule.objects.create(
            user=other, category='INGREDIENT', keyword='우유',
            match_type='CONTAINS', is_active=True)
        other_match = NewsKeywordMatch.objects.create(
            user=other, news=self.news, rule=other_rule,
            matched_keyword='우유', read_yn=False, dismissed_yn=False)
        self.client.post('/api/mobile/devices/rd-device/notifications/read-all/')
        other_match.refresh_from_db()
        self.assertFalse(other_match.read_yn)


class 가입_직후_로그인이_막다른_길이_아니다(TestCase):
    """
    이메일 인증 전 계정은 `is_active=False` 라 `authenticate()` 가 None 을
    준다. 앱은 그것을 **"아이디 또는 비밀번호가 올바르지 않습니다"** 로
    옮겼다.

    방금 가입한 사람이 비밀번호를 틀린 줄 알고 계속 다시 친다. 20회/분에
    걸리면 그다음은 "시도가 너무 잦습니다" 라 원인에서 더 멀어진다.
    웹은 같은 자리에서 "이메일 인증이 완료되지 않았습니다" 라고 말한다.
    """

    def setUp(self):
        from v1.user_management.models import UserProfile

        self.user = User.objects.create_user(
            username='unv@example.com', email='unv@example.com',
            password='pw12345!', is_active=False)
        UserProfile.objects.update_or_create(
            user=self.user, defaults={'email_verified_yn': False})
        cache.clear()

    def _login(self, password):
        return self.client.post(
            '/api/mobile/login/',
            data=json.dumps({'username': 'unv@example.com', 'password': password}),
            content_type='application/json')

    def test_인증_전이면_그렇다고_말한다(self):
        r = self._login('pw12345!')
        self.assertEqual(r.status_code, 403)
        self.assertIn('인증', r.json()['error'])

    def test_비밀번호가_틀리면_여전히_401_이다(self):
        """인증 여부를 비밀번호 확인 없이 알려 주면 계정 존재가 샌다."""
        r = self._login('wrong-password')
        self.assertEqual(r.status_code, 401)
        self.assertNotIn('인증', r.json()['error'])

    def test_없는_계정도_401_이다(self):
        r = self.client.post(
            '/api/mobile/login/',
            data=json.dumps({'username': 'nobody@example.com', 'password': 'x'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_인증된_계정은_그대로_들어온다(self):
        from v1.user_management.models import UserProfile

        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        UserProfile.objects.update_or_create(
            user=self.user, defaults={'email_verified_yn': True})
        r = self._login('pw12345!')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['access'])


class 로그인_승격이_키워드_한도를_넘기지_않는다(TestCase):
    """
    비회원으로 5개를 만들고 로그인하면 그 5개가 계정으로 승격된다. 그런데
    승격 루프에 한도 검사가 없었다.

    회원 한도를 이미 채운 사람이 로그아웃 → 비회원으로 5개 추가 → 재로그인
    하면 **한도를 넘은 상태**가 만들어진다. 활성 규칙 수는 수집 때마다의
    전건 매칭 부하로 바로 이어진다.
    """

    def setUp(self):
        from django.test import override_settings

        from v1.mobile.models import AppDevice

        self.user = User.objects.create_user(username='promo', password='pw12345!')
        self.device = AppDevice.objects.create(device_id='promo-device')
        self._ov = override_settings(MOBILE_MEMBER_MAX_RULES=3)
        self._ov.enable()
        self.addCleanup(self._ov.disable)
        cache.clear()

    def _guest_rule(self, keyword):
        AlertRule.objects.create(
            device=self.device, user=None, category='INGREDIENT',
            keyword=keyword, match_type='CONTAINS', is_active=True)

    def _login(self):
        return self.client.post(
            '/api/mobile/login/',
            data=json.dumps({'username': 'promo', 'password': 'pw12345!',
                             'device_id': 'promo-device'}),
            content_type='application/json')

    def test_한도_안이면_다_올라간다(self):
        self._guest_rule('a')
        self._guest_rule('b')
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(
            AlertRule.objects.filter(user=self.user, is_active=True).count(), 2)

    def test_넘치는_것은_꺼진_채로_올라간다(self):
        """지우지는 않는다 — 사용자가 만든 것이다. 다만 한도를 넘겨 돌지 않는다."""
        for kw in ('a', 'b', 'c', 'd', 'e'):
            self._guest_rule(kw)
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(
            AlertRule.objects.filter(user=self.user, is_active=True).count(), 3)
        self.assertEqual(AlertRule.objects.filter(user=self.user).count(), 5)

    def test_이미_채운_계정에는_더_켜지_않는다(self):
        for kw in ('x', 'y', 'z'):
            AlertRule.objects.create(
                user=self.user, category='INGREDIENT', keyword=kw,
                match_type='CONTAINS', is_active=True)
        self._guest_rule('a')
        self._guest_rule('b')
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(
            AlertRule.objects.filter(user=self.user, is_active=True).count(), 3)


class 알림_카드에_개발자_값이_찍히지_않는다(TestCase):
    """
    앱 알림 카드가 `#마늘 · CONTAINS` 를 찍었다. 서버가 `match_type` 원본만
    보내서다. 같은 값을 설정 화면은 '포함' 이라고 잘 보여 준다 — 서버가
    사람이 읽는 값도 함께 보내면 두 화면이 같아진다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice, PushNotificationLog
        from v1.regulatory.models import RegulatoryNews

        self.user = User.objects.create_user(username='mtd', password='x')
        self.device = AppDevice.objects.create(device_id='mtd-device', user=self.user)
        news = RegulatoryNews.objects.create(
            external_id='mtd-1', api_source='I2620', source='domestic',
            product_name='뉴스', ai_parsed=True, collected_date='2026-09-01')
        rule = AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='마늘',
            match_type='CONTAINS', is_active=True)
        PushNotificationLog.objects.create(
            device=self.device, news=news, rule_triggered=rule,
            trigger_type='keyword', trigger_label='마늘',
            sent_at='2026-09-02T00:00:00+09:00')

    def test_사람이_읽는_값을_함께_보낸다(self):
        r = self.client.get('/api/mobile/devices/mtd-device/notifications/')
        self.assertEqual(r.status_code, 200)
        keyword = r.json()[0]['rule_keyword']
        self.assertEqual(keyword['match_type'], 'CONTAINS')
        self.assertEqual(keyword['match_type_display'], '포함')

    def test_분류도_함께_보낸다(self):
        r = self.client.get('/api/mobile/devices/mtd-device/notifications/')
        keyword = r.json()[0]['rule_keyword']
        self.assertTrue(keyword.get('category_display'))


class 소급이_알림함_상한을_넘기지_않는다(TestCase):
    """
    키워드를 새로 넣으면 최근 90일을 훑어 최대 100건까지 알림을 만든다.
    그 전에 `_trim_notifications(device, max_noti)` 로 자리를 비우는데, 그
    함수는 **한 자리만** 비운다(곧 하나 만들 참이라는 뜻이다).

    그래서 이미 상한만큼 차 있던 기기가 99 로 줄었다가 199 가 됐다.
    `MOBILE_MAX_NOTIFICATIONS` 가 다음 수집 때까지 두 배로 깨져 있었다.
    """

    def setUp(self):
        from django.test import override_settings

        from v1.mobile.models import AppDevice, PushNotificationLog
        from v1.regulatory.models import RegulatoryNews

        self.user = User.objects.create_user(username='cap', password='x')
        self.device = AppDevice.objects.create(device_id='cap-device', user=self.user)
        self._ov = override_settings(MOBILE_MAX_NOTIFICATIONS=10)
        self._ov.enable()
        self.addCleanup(self._ov.disable)

        # 이미 상한만큼 차 있다 (전부 읽은 키워드 알림 — 가장 먼저 밀리는 것)
        for i in range(10):
            news = RegulatoryNews.objects.create(
                external_id='old%d' % i, api_source='I2620', source='domestic',
                product_name='옛것 %d' % i, ai_parsed=True,
                collected_date='2026-08-01')
            PushNotificationLog.objects.create(
                device=self.device, news=news, trigger_type='keyword',
                trigger_label='옛키워드', is_read=True,
                sent_at='2026-08-02T00:00:00+09:00')

        # 소급에 걸릴 새 뉴스 다섯 건
        for i in range(5):
            RegulatoryNews.objects.create(
                external_id='new%d' % i, api_source='I2620', source='domestic',
                product_name='치즈케이크 %d' % i, ai_parsed=True,
                collected_date='2026-09-10', ai_keywords=['치즈'])

        self.rule = AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='치즈',
            match_type='CONTAINS', is_active=True)

    def _count(self):
        from v1.mobile.models import PushNotificationLog

        return PushNotificationLog.objects.filter(device=self.device).count()

    def test_소급_뒤에도_상한을_지킨다(self):
        from v1.mobile.services.push_service import backfill_alerts_for_rule

        self.assertEqual(self._count(), 10)
        backfill_alerts_for_rule(self.rule)
        self.assertLessEqual(self._count(), 10)

    def test_새로_걸린_것이_실제로_들어온다(self):
        """상한을 지키느라 아무것도 안 넣으면 그것대로 잘못이다."""
        from v1.mobile.models import PushNotificationLog
        from v1.mobile.services.push_service import backfill_alerts_for_rule

        backfill_alerts_for_rule(self.rule)
        fresh = PushNotificationLog.objects.filter(
            device=self.device, trigger_label='치즈').count()
        self.assertEqual(fresh, 5)

    def test_상한_안이면_아무것도_밀려나지_않는다(self):
        from django.test import override_settings

        from v1.mobile.services.push_service import backfill_alerts_for_rule

        with override_settings(MOBILE_MAX_NOTIFICATIONS=100):
            backfill_alerts_for_rule(self.rule)
        self.assertEqual(self._count(), 15)


class 키워드를_바꾸면_소급도_다시_돈다(TestCase):
    """
    POST 는 등록 직후 최근 90일을 훑는데 PATCH 는 **거두기만** 했다.

    '우유' 를 '치즈' 로 고치면 최근 90일에 치즈 부적합이 있어도 0건이 되고,
    같은 것을 지웠다 새로 등록하면 90일치가 다 걸린다 — 같은 결과를 얻는
    두 길이 다르게 동작했다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice
        from v1.regulatory.models import RegulatoryNews

        self.user = User.objects.create_user(username='rekw', password='x')
        self.device = AppDevice.objects.create(device_id='rekw-device', user=self.user)
        RegulatoryNews.objects.create(
            external_id='rk-1', api_source='I2620', source='domestic',
            product_name='치즈케이크', ai_parsed=True,
            collected_date='2026-09-10', ai_keywords=['치즈'])
        self.rule = AlertRule.objects.create(
            user=self.user, category='INGREDIENT', keyword='우유',
            match_type='CONTAINS', is_active=True)
        cache.clear()

    def _patch(self, body):
        return self.client.patch(
            '/api/mobile/devices/rekw-device/rules/%d/' % self.rule.pk,
            data=json.dumps(body), content_type='application/json')

    def test_바꾼_키워드로_지난_것을_훑는다(self):
        r = self._patch({'keyword': '치즈'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['matched_count'], 1)

    def test_몇_건_걸렸는지_함께_말해_준다(self):
        body = self._patch({'keyword': '치즈'}).json()
        for key in ('matched_count', 'previews', 'window_days',
                    'capped', 'backfill_failed'):
            self.assertIn(key, body)

    def test_켜고_끄기만_한_경우에는_소급하지_않는다(self):
        """매칭 대상이 그대로면 다시 훑을 이유가 없다."""
        body = self._patch({'is_active': False}).json()
        self.assertNotIn('matched_count', body)

    def test_꺼진_규칙은_바꿔도_소급하지_않는다(self):
        self.rule.is_active = False
        self.rule.save(update_fields=['is_active'])
        body = self._patch({'keyword': '치즈'}).json()
        self.assertNotIn('matched_count', body)

    def test_옛_키워드로_걸려_있던_예약_푸시는_거둔다(self):
        """이 성질은 원래 있던 것이다 — 소급을 붙이다 깨뜨리지 않았는지 본다."""
        from v1.mobile.models import PushNotificationLog
        from v1.regulatory.models import RegulatoryNews

        old_news = RegulatoryNews.objects.create(
            external_id='rk-old', api_source='I2620', source='domestic',
            product_name='우유빵', ai_parsed=True, collected_date='2026-09-01')
        PushNotificationLog.objects.create(
            device=self.device, news=old_news, rule_triggered=self.rule,
            trigger_type='keyword', trigger_label='우유', sent_at=None)
        self._patch({'keyword': '치즈'})
        self.assertFalse(
            PushNotificationLog.objects
            .filter(device=self.device, trigger_label='우유', sent_at__isnull=True)
            .exists())


class 수거검사_알림_기준을_앱에서도_켤_수_있다(TestCase):
    """
    수거검사 매칭은 세 규칙으로 돈다 — 품목보고번호 · 인허가번호 · 회사명.
    뒤의 둘은 `UserProfile` 에 값이 있어야 작동한다.

    웹에는 그 값을 넣는 자리가 있는데(부적합 화면의 알림 설정 모달) **앱에는
    없었고 API 도 없었다.** 앱의 알림 탭에 '수거검사' 탭이 버젓이 있는데,
    앱만 쓰는 사용자에게는 영영 비어 있을 수 있었다.
    """

    def setUp(self):
        from v1.mobile.models import AppDevice
        from v1.user_management.models import UserProfile

        self.user = User.objects.create_user(username='insp', password='x')
        UserProfile.objects.update_or_create(
            user=self.user, defaults={'company_name': '어떤식품'})
        self.device = AppDevice.objects.create(device_id='insp-device', user=self.user)
        AppDevice.objects.create(device_id='insp-guest', user=None)

    URL = '/api/mobile/devices/insp-device/inspection-profile/'

    def test_지금_값을_읽을_수_있다(self):
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['company_name'], '어떤식품')

    def test_고쳐서_저장한다(self):
        from v1.user_management.models import UserProfile

        r = self.client.put(
            self.URL,
            data=json.dumps({'company_name': '새이름', 'license_number': '12345'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.company_name, '새이름')
        self.assertEqual(profile.license_number, '12345')

    def test_보낸_칸만_고친다(self):
        """한 칸만 바꾸러 온 요청이 다른 칸을 지우면 안 된다."""
        from v1.user_management.models import UserProfile

        self.client.put(self.URL,
                        data=json.dumps({'license_number': '999'}),
                        content_type='application/json')
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.company_name, '어떤식품')
        self.assertEqual(profile.license_number, '999')

    def test_비우는_것은_할_수_있다(self):
        from v1.user_management.models import UserProfile

        self.client.put(self.URL,
                        data=json.dumps({'company_name': ''}),
                        content_type='application/json')
        self.assertEqual(
            UserProfile.objects.get(user=self.user).company_name, '')

    def test_너무_길면_막는다(self):
        r = self.client.put(self.URL,
                            data=json.dumps({'company_name': '가' * 101}),
                            content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_비회원_기기는_막고_까닭을_말한다(self):
        r = self.client.get('/api/mobile/devices/insp-guest/inspection-profile/')
        self.assertEqual(r.status_code, 403)
        self.assertIn('로그인', r.json()['error'])

    def test_웹과_같은_칸을_쓴다(self):
        """웹이 쓰는 자리와 다른 데 저장하면 두 화면이 갈린다."""
        from v1.user_management.models import UserProfile

        self.client.put(self.URL,
                        data=json.dumps({'company_name': '한곳', 'license_number': 'L1'}),
                        content_type='application/json')
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.company_name, profile.license_number), ('한곳', 'L1'))
