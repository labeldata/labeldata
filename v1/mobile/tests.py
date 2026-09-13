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
