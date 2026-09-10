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
