"""
부적합·처분 알림 목록 — 내 알림 / 일반 알림 가르기.

매칭된 건을 전부 위로 고정하던 시절에는, 매칭이 수십 건인 사용자에게 목록 앞
몇 페이지가 통째로 내 알림이었다. 일반 알림에 닿으려면 몇 장을 넘겨야 하는지
알 방법이 없었다 — 개발자도 못 찾았다는 신고가 여기서 나왔다.

아래쪽 AutoRematchTriggerTests 는 다른 사고를 지킨다. 자동 재매칭이 저장마다
스레드를 띄우고 커넥션을 안 닫아 계정 한도(79)를 넘겼고, 사이트 전체가 500 이
났다. 그 재발을 막는 조건들이라 지우지 말 것.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from v1.label.models import MyLabel
from v1.regulatory.models import NewsProductMatch, RegulatoryNews

User = get_user_model()


class NewsListScopeSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='scope', password='x')
        self.client.force_login(self.user)
        label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                       prdlst_nm='내 제품')
        for i in range(12):
            news = RegulatoryNews.objects.create(
                external_id=f'x{i}', api_source='I2620', source='domestic',
                product_name=f'매칭 {i}', collected_date='2026-08-01')
            NewsProductMatch.objects.create(news=news, product=label,
                                            match_score=90, risk_score=50)
        for i in range(30):
            RegulatoryNews.objects.create(
                external_id=f'y{i}', api_source='I2620', source='domestic',
                product_name=f'일반 {i}', collected_date='2026-08-01')

    def test_기본_화면은_내_알림을_다섯_건만_고정한다(self):
        r = self.client.get('/regulatory/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['pinned_news']), 5)
        self.assertEqual(r.context['mine_total'], 12)
        self.assertEqual(r.context['other_total'], 30)
        names = [n.product_name for n in r.context['news_list']]
        self.assertTrue(all(n.startswith('일반') for n in names), names[:5])

    def test_내_알림만_보기(self):
        r = self.client.get('/regulatory/?scope=mine')
        names = [n.product_name for n in r.context['news_list']]
        self.assertEqual(len(names), 12)
        self.assertTrue(all(n.startswith('매칭') for n in names))
        self.assertEqual(r.context['pinned_news'], [])

    def test_일반_알림만_보기(self):
        r = self.client.get('/regulatory/?scope=others')
        names = [n.product_name for n in r.context['news_list']]
        self.assertEqual(len(names), 30)
        self.assertTrue(all(n.startswith('일반') for n in names))

    def test_두_번째_페이지에는_고정_블록이_없다(self):
        r = self.client.get('/regulatory/?per_page=20&page=2')
        self.assertEqual(r.context['pinned_news'], [])

    def test_매칭이_적으면_가르지_않는다(self):
        NewsProductMatch.objects.all().delete()
        news = RegulatoryNews.objects.first()
        label = MyLabel.objects.first()
        NewsProductMatch.objects.create(news=news, product=label,
                                        match_score=90, risk_score=50)
        r = self.client.get('/regulatory/')
        self.assertEqual(r.context['pinned_news'], [])
        self.assertEqual(r.context['mine_total'], 1)
        self.assertEqual(r.context['news_list'][0].product_name, news.product_name)


class AutoRematchTriggerTests(TestCase):
    """
    자동 재매칭이 **언제 도는가.**

    예전에는 MyLabel 이 저장될 때마다 돌았다. 화면의 자동 저장이 30초 유휴마다
    도니, 원재료명 한 글자를 고쳐도 180일치 뉴스를 통째로 다시 훑는 작업이
    떴다. 그것들이 저마다 DB 커넥션을 잡아 계정 한도를 넘겼고 사이트가 멈췄다.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(username='rematch', password='x')

    def _label(self):
        return MyLabel.objects.create(
            user_id=self.user, my_label_name='제품', prdlst_nm='제품',
            bssh_nm='(주)가나다', rawmtrl_nm='정제수, 설탕')

    def test_새_제품은_재매칭한다(self):
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            self._label()
        self.assertEqual(trigger.call_count, 1)

    def test_매칭에_안_쓰는_필드만_바뀌면_돌지_않는다(self):
        label = self._label()
        label = MyLabel.objects.get(pk=label.pk)   # 화면이 하듯 다시 읽어 온다
        label.rawmtrl_nm = '정제수, 설탕, 소금'
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            label.save()
        trigger.assert_not_called()

    def test_업체명이_바뀌면_돈다(self):
        label = self._label()
        label = MyLabel.objects.get(pk=label.pk)
        label.bssh_nm = '(주)라마바'
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            label.save()
        self.assertEqual(trigger.call_count, 1)

    def test_update_fields_로_알려_주면_그대로_믿는다(self):
        label = self._label()
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            label.save(update_fields=['rawmtrl_nm'])
        trigger.assert_not_called()
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            label.save(update_fields=['bssh_nm'])
        self.assertEqual(trigger.call_count, 1)

    def test_일부_필드만_읽어_온_인스턴스는_추가_질의를_하지_않는다(self):
        """
        post_init 는 인스턴스 하나마다 돈다. 거기서 미조회 필드를 건드리면
        목록 한 번에 쿼리가 행 수만큼 붙는다 - 지금 고치는 것과 같은 사고다.
        """
        self._label()
        with self.assertNumQueries(1):
            labels = list(MyLabel.objects.only('my_label_id', 'user_id'))
        self.assertEqual(len(labels), 1)

    def test_일부만_읽어_온_인스턴스도_바뀐_필드로_판단한다(self):
        """
        Django 는 deferred 인스턴스를 저장할 때 읽어 온 필드로 update_fields 를
        스스로 채운다. 그래서 스냅샷을 못 만들어도 판단은 정확하다.
        """
        label = self._label()
        partial = MyLabel.objects.only('my_label_id', 'user_id').get(pk=label.pk)
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            partial.save()
        trigger.assert_not_called()

        partial = MyLabel.objects.only('my_label_id', 'user_id', 'bssh_nm').get(pk=label.pk)
        partial.bssh_nm = '(주)라마바'
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            partial.save()
        self.assertEqual(trigger.call_count, 1)

    def test_스냅샷이_없으면_예전처럼_돈다(self):
        """
        판단할 근거가 없을 때는 놓치는 것보다 한 번 더 도는 편이 낫다.
        """
        from v1.regulatory import signals

        label = MyLabel.objects.get(pk=self._label().pk)
        delattr(label, signals._SNAPSHOT_ATTR)
        with patch('v1.regulatory.signals._trigger_rematch') as trigger:
            label.save()
        self.assertEqual(trigger.call_count, 1)

    def test_한_번_예약되면_뒤따르는_저장은_묻어_간다(self):
        """
        BOM 은 한 번에 여러 행이 저장된다. 행마다 스레드를 띄우던 것이
        커넥션 고갈의 직접 원인이었다 — 예약은 하나로 합쳐져야 한다.
        """
        from v1.regulatory import signals

        with patch.object(signals._POOL, 'submit') as submit:
            for i in range(10):
                signals._trigger_rematch(self.user.pk, f'BOM #{i}')
        self.assertEqual(submit.call_count, 1)
        # 묻어 간 저장들은 사라지지 않는다 — 끝난 뒤 한 번 더 돌 표시가 남는다
        self.assertTrue(cache.get(signals._dirty_key(self.user.pk)))

    def test_재매칭이_끝나면_커넥션을_닫는다(self):
        """
        요청 밖에서 연 커넥션은 아무도 닫아 주지 않는다. 이걸 빠뜨려
        커넥션이 쌓였고 계정 한도(79)를 넘긴 순간 사이트 전체가 500 이 났다.
        """
        from v1.regulatory import signals

        with patch('v1.regulatory.signals.connections') as conns:
            signals._run_rematch_for_user(self.user.pk, '테스트')
        conns.close_all.assert_called_once()

    def test_재매칭이_터져도_커넥션은_닫는다(self):
        from v1.regulatory import signals

        with patch('v1.regulatory.services.matcher.build_match_cache_for_user',
                   side_effect=RuntimeError('DB 끊김')), \
             patch('v1.regulatory.signals.connections') as conns:
            signals._run_rematch_for_user(self.user.pk, '테스트')
        conns.close_all.assert_called_once()


class MarkAllNewsResolvedTests(TestCase):
    """
    "전체 알림" 일괄 확인은 **세 탭을 모두** 턴다.

    이 버튼은 부적합 탭 상세에 있지만 문구는 "전체 알림 일괄 처리" 다. 예전에는
    뉴스 매칭만 읽음 처리해서, 눌러 놓고 수거검사 탭으로 넘어가면 빨간 점과
    "전체 읽음" 칩이 그대로 남아 있었다. 무엇을 더 확인해야 하는지 알 수 없다는
    신고가 본서버 시험에서 나왔다.
    """

    def setUp(self):
        from v1.regulatory.models import InspectionMatch, InspectionResult

        cache.clear()
        self.user = User.objects.create_user(username='markall', password='x')
        self.client.force_login(self.user)

        label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                       prdlst_nm='내 제품')
        news = RegulatoryNews.objects.create(
            external_id='m1', api_source='I2620', source='domestic',
            product_name='부적합 알림', collected_date='2026-08-01')
        NewsProductMatch.objects.create(news=news, product=label,
                                        match_score=90, risk_score=50)

        insp = InspectionResult.objects.create(
            tkawyprno='1', bssh_nm='업소', prdtnm='제품',
            prdlst_report_no='20250101', tkawydtm='20260801')
        InspectionMatch.objects.create(
            inspection=insp, user=self.user, label=label,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)
        self.insp_match_ids = list(
            InspectionMatch.objects.filter(user=self.user).values_list('id', flat=True))

    def test_수거검사도_함께_확인_처리된다(self):
        from v1.regulatory.models import InspectionMatch

        r = self.client.post('/regulatory/api/mark-all-news-resolved/',
                             data='{}', content_type='application/json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['inspection_read'], 1)
        self.assertEqual(
            InspectionMatch.objects.filter(user=self.user, read_yn=False).count(), 0)

    def test_목록_화면의_수거검사_미확인이_0이_된다(self):
        """배지와 빨간 점은 이 숫자를 본다."""
        r = self.client.get('/regulatory/')
        self.assertEqual(r.context['inspection_unread'], 1)

        self.client.post('/regulatory/api/mark-all-news-resolved/',
                         data='{}', content_type='application/json')

        r = self.client.get('/regulatory/')
        self.assertEqual(r.context['inspection_unread'], 0)

    def test_남의_수거검사는_건드리지_않는다(self):
        from v1.regulatory.models import InspectionMatch, InspectionResult

        other = User.objects.create_user(username='markall2', password='x')
        insp = InspectionResult.objects.create(
            tkawyprno='2', bssh_nm='업소2', prdtnm='제품2',
            prdlst_report_no='20250102', tkawydtm='20260802')
        InspectionMatch.objects.create(
            inspection=insp, user=other,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_COMPANY)

        self.client.post('/regulatory/api/mark-all-news-resolved/',
                         data='{}', content_type='application/json')

        self.assertEqual(
            InspectionMatch.objects.filter(user=other, read_yn=False).count(), 1)


class 탭마다_모두_읽음(TestCase):
    """
    세 탭이 한 화면 안의 같은 '알림' 이므로, 터는 방법도 하나여야 한다.

    예전에는 '전체 읽음' 이 수거검사 탭에만 있었다. 부적합·행정처분 탭에서
    배지를 지우려면 상세 하단의 '전체 알림 일괄 처리' 를 눌러야 했는데, 그것은
    **되돌릴 수 없는 조치 완료 기록**을 남긴다. 그냥 훑고 넘기려던 사람이
    조치 이력을 남기게 되는 것이 문제였다.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='tabread', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')
        self.insp_news = self._news('t-insp', 'I2620')
        self.admin_news = self._news('t-admin', 'I0470')

    def _news(self, ext, src):
        news = RegulatoryNews.objects.create(
            external_id=ext, api_source=src, source='domestic',
            product_name=ext, collected_date='2026-08-01')
        NewsProductMatch.objects.create(news=news, product=self.label,
                                        match_score=90, risk_score=50)
        return news

    def _post(self, tab):
        import json
        return self.client.post('/regulatory/api/mark-tab-read/',
                                data=json.dumps({'tab': tab}),
                                content_type='application/json')

    def test_부적합_탭만_턴다(self):
        r = self._post('insp-news')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['news_updated'], 1)
        self.assertTrue(NewsProductMatch.objects.get(news=self.insp_news).read_yn)
        self.assertFalse(NewsProductMatch.objects.get(news=self.admin_news).read_yn)

    def test_행정처분_탭만_턴다(self):
        self._post('admin')
        self.assertFalse(NewsProductMatch.objects.get(news=self.insp_news).read_yn)
        self.assertTrue(NewsProductMatch.objects.get(news=self.admin_news).read_yn)

    def test_조치_이력을_남기지_않는다(self):
        """읽음(봤다)과 조치 완료(처리했다)는 다른 일이다."""
        from v1.regulatory.models import RegulatoryMatchAction

        self._post('all')
        self.assertEqual(RegulatoryMatchAction.objects.filter(user=self.user).count(), 0)
        # 미조치 건수는 그대로 — 아직 아무것도 처리하지 않았으므로
        r = self.client.get('/regulatory/')
        self.assertEqual(r.context['no_action_count'], 2)

    def test_수거검사_탭도_같은_주소를_쓴다(self):
        from v1.regulatory.models import InspectionMatch, InspectionResult

        insp = InspectionResult.objects.create(
            tkawyprno='9', bssh_nm='업소', prdtnm='제품',
            prdlst_report_no='20250109', tkawydtm='20260801')
        InspectionMatch.objects.create(
            inspection=insp, user=self.user, label=self.label,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)

        body = self._post('insp').json()
        self.assertEqual(body['inspection_read'], 1)
        self.assertEqual(body['news_updated'], 0)      # 뉴스 쪽은 건드리지 않는다

    def test_모르는_탭_이름은_거절한다(self):
        self.assertEqual(self._post('없는탭').status_code, 400)

    def test_남의_알림은_건드리지_않는다(self):
        other = User.objects.create_user(username='tabread2', password='x')
        other_label = MyLabel.objects.create(user_id=other, my_label_name='남 제품',
                                             prdlst_nm='남 제품')
        NewsProductMatch.objects.create(news=self.insp_news, product=other_label,
                                        match_score=90, risk_score=50)
        self._post('all')
        self.assertFalse(
            NewsProductMatch.objects.get(news=self.insp_news, product=other_label).read_yn)


class 알림_사유를_그_자리에서_끈다(TestCase):
    """
    알림이 많다고 느낀 사람이 원인을 끌 자리가 없었다.

    할 수 있는 일이 건건이 '해당 없음' 을 누르거나 원료 보관함에서 그 원료를
    지우는 것뿐이었는데, 둘 다 원하는 일이 아니다 — 원료는 실제로 쓰고 있고,
    다만 그 원료로 오는 부적합 소식이 필요 없을 뿐이다.
    """

    def setUp(self):
        import json
        cache.clear()
        self._json = json
        self.user = User.objects.create_user(username='mute', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')
        self.news = RegulatoryNews.objects.create(
            external_id='mute-1', api_source='I2620', source='domestic',
            product_name='정제수 부적합', company_name='(주)어떤식품',
            ai_keywords=['대장균'], ai_parsed=True, collected_date='2026-08-01')
        self.match = NewsProductMatch.objects.create(
            news=self.news, product=self.label, matched_keyword='대장균',
            matched_ingredient='정제수', match_score=90, risk_score=50)

    def _mute(self, scope, value):
        return self.client.post(
            '/regulatory/api/alert-mutes/',
            data=self._json.dumps({'scope': scope, 'value': value}),
            content_type='application/json')

    def test_키워드를_끄면_기존_알림도_함께_치운다(self):
        r = self._mute('keyword', '대장균')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['hidden'], 1)
        self.match.refresh_from_db()
        self.assertTrue(self.match.false_positive_yn)
        self.assertTrue(self.match.read_yn)

    def test_내_원료로도_끌_수_있다(self):
        self.assertEqual(self._mute('ingredient', '정제수').json()['hidden'], 1)
        self.match.refresh_from_db()
        self.assertTrue(self.match.false_positive_yn)

    def test_띄어쓰기가_달라도_같은_것으로_본다(self):
        self.assertEqual(self._mute('keyword', '대장 균').json()['hidden'], 1)

    def test_끈_뒤에는_다시_매칭되지_않는다(self):
        from v1.bom.models import ProductBOM
        from v1.regulatory.services import matcher

        self._mute('keyword', '대장균')
        ProductBOM.objects.create(parent_label=self.label, ingredient_name='정제수')
        self.assertEqual(matcher.find_affected_products(self.news, self.user), [])

    def test_직접_등록한_키워드는_끄지_않고_지우게_한다(self):
        """
        AlertRule(받겠다) 과 AlertMute(안 받겠다) 가 같은 말을 하면 어느 쪽이
        이겼는지 화면에서 설명할 수 없다. 되돌려 보내 키워드를 지우게 한다.
        """
        from v1.mobile.models import AlertRule

        rule = AlertRule.objects.create(user=self.user, category='INGREDIENT',
                                        keyword='대장균', match_type='CONTAINS')
        r = self._mute('keyword', '대장균')
        self.assertEqual(r.status_code, 409)
        self.assertIn(rule.id, r.json()['conflict_rule_ids'])

    def test_해제해도_치운_알림은_되살리지_않는다(self):
        mute_id = self._mute('keyword', '대장균').json()['mute']['id']
        self.client.post('/regulatory/api/alert-mutes/%d/delete/' % mute_id)
        self.match.refresh_from_db()
        self.assertTrue(self.match.false_positive_yn)

    def test_남의_규칙은_지울_수_없다(self):
        mute_id = self._mute('keyword', '대장균').json()['mute']['id']
        other = User.objects.create_user(username='mute2', password='x')
        self.client.force_login(other)
        r = self.client.post('/regulatory/api/alert-mutes/%d/delete/' % mute_id)
        self.assertEqual(r.status_code, 404)

    def test_알_수_없는_기준은_거절한다(self):
        self.assertEqual(self._mute('없는기준', '값').status_code, 400)

    def test_수거검사도_업체명으로_끈다(self):
        """수거검사 매칭은 업소명·번호로만 생긴다 — 끌 수 있는 것은 업소명이다."""
        from v1.regulatory.models import InspectionMatch, InspectionResult

        insp = InspectionResult.objects.create(
            tkawyprno='7', bssh_nm='(주)어떤식품', prdtnm='제품',
            prdlst_report_no='20250107', tkawydtm='20260801')
        InspectionMatch.objects.create(
            inspection=insp, user=self.user, label=self.label,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)

        self.assertGreaterEqual(self._mute('company', '(주)어떤식품').json()['hidden'], 1)
        self.assertEqual(InspectionMatch.objects.filter(user=self.user).count(), 0)


class 끄면_예약된_푸시도_거둔다(TestCase):
    """
    식품 안심 알리미(앱) 푸시는 수집 즉시 나가지 않는다.

    로그만 먼저 쌓고 일 3회(10·14·17시) 배치로 내보낸다. 그래서 03시에 걸린
    알림을 09시에 껐는데 10시에 푸시가 그대로 울리면, 웹에서 껐다는 사실
    자체를 못 믿게 된다 — "껐는데 또 온다".
    """

    def setUp(self):
        import json
        from v1.mobile.models import AppDevice, PushNotificationLog

        cache.clear()
        self._json = json
        self.user = User.objects.create_user(username='push', password='x')
        self.client.force_login(self.user)
        self.device = AppDevice.objects.create(device_id='dev-1', user=self.user,
                                               fcm_token='tok')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')
        self.news = RegulatoryNews.objects.create(
            external_id='push-1', api_source='I2620', source='domestic',
            product_name='정제수 부적합', ai_parsed=True, collected_date='2026-08-01')
        NewsProductMatch.objects.create(
            news=self.news, product=self.label, matched_keyword='대장균',
            matched_ingredient='정제수', match_score=90, risk_score=50)
        # 아직 안 나간 푸시 (배치 대기 중)
        self.pending = PushNotificationLog.objects.create(
            device=self.device, news=self.news, trigger_type='product',
            trigger_label='내 제품', sent_at=None)

    def _mute(self, scope, value):
        return self.client.post(
            '/regulatory/api/alert-mutes/',
            data=self._json.dumps({'scope': scope, 'value': value}),
            content_type='application/json')

    def test_안_나간_푸시는_취소된다(self):
        from v1.mobile.models import PushNotificationLog

        body = self._mute('ingredient', '정제수').json()
        self.assertEqual(body['push_cancelled'], 1)
        self.assertFalse(PushNotificationLog.objects.filter(pk=self.pending.pk).exists())

    def test_이미_나간_푸시는_지우지_않고_읽음으로_내린다(self):
        """앱 알림 탭에서 '어제 받은 그 알림' 을 다시 찾을 수 있어야 한다."""
        from django.utils import timezone
        from v1.mobile.models import PushNotificationLog

        self.pending.sent_at = timezone.now()
        self.pending.save(update_fields=['sent_at'])

        self._mute('ingredient', '정제수')
        log = PushNotificationLog.objects.get(pk=self.pending.pk)
        self.assertTrue(log.is_read)

    def test_남의_기기_푸시는_건드리지_않는다(self):
        from v1.mobile.models import AppDevice, PushNotificationLog

        other = User.objects.create_user(username='push2', password='x')
        other_dev = AppDevice.objects.create(device_id='dev-2', user=other)
        other_log = PushNotificationLog.objects.create(
            device=other_dev, news=self.news, trigger_type='product', sent_at=None)

        self._mute('ingredient', '정제수')
        self.assertTrue(PushNotificationLog.objects.filter(pk=other_log.pk).exists())

    def test_키워드를_지우면_그_키워드_푸시가_취소된다(self):
        from v1.mobile.models import AlertRule, PushNotificationLog

        rule = AlertRule.objects.create(user=self.user, category='INGREDIENT',
                                        keyword='대장균', match_type='CONTAINS')
        log = PushNotificationLog.objects.create(
            device=self.device, news=self.news, rule_triggered=rule,
            trigger_type='keyword', trigger_label='대장균', sent_at=None)

        r = self.client.post('/regulatory/api/alert-rules/%d/delete/' % rule.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['push_cancelled'], 1)
        self.assertFalse(PushNotificationLog.objects.filter(pk=log.pk).exists())

    def test_키워드_삭제가_다른_알림까지_거두지는_않는다(self):
        from v1.mobile.models import AlertRule, PushNotificationLog

        rule = AlertRule.objects.create(user=self.user, category='INGREDIENT',
                                        keyword='대장균', match_type='CONTAINS')
        self.client.post('/regulatory/api/alert-rules/%d/delete/' % rule.id)
        # 제품 매칭으로 걸린 대기 푸시는 그대로 남는다
        self.assertTrue(PushNotificationLog.objects.filter(pk=self.pending.pk).exists())


class 끄기가_오탐_학습을_오염시키지_않는다(TestCase):
    """
    '이 키워드 알림 끄기' 는 한 번에 수백 건을 오탐으로 표시한다.

    그것을 그대로 오탐 학습(Approach C)에 태우면 그 키워드의 FP 누적이
    폭증해, **다른 원료**에 걸린 정상 매칭까지 등급이 깎인다.
    정제수 알림을 껐다고 대장균 소식 전체가 '일반' 이 되면 안 된다.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='fp', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')

    def _fp_rows(self, keyword, ingredient, n):
        """오탐으로 표시된 매칭 n 건을 만든다."""
        for i in range(n):
            news = RegulatoryNews.objects.create(
                external_id='fp%s%d' % (ingredient, i), api_source='I2620',
                source='domestic', product_name='뉴스', collected_date='2026-08-01')
            NewsProductMatch.objects.create(
                news=news, product=self.label, matched_keyword=keyword,
                matched_ingredient=ingredient, match_score=90, risk_score=50,
                false_positive_yn=True)

    def test_뮤트로_치운_건은_학습에서_뺀다(self):
        from v1.regulatory.models import AlertMute
        from v1.regulatory.services import matcher

        self._fp_rows('대장균', '정제수', 10)
        AlertMute.objects.create(user=self.user, scope=AlertMute.SCOPE_INGREDIENT,
                                 value='정제수')

        fp = matcher._load_fp_patterns_for_user(self.user)
        self.assertEqual(fp.keyword_fp_count('대장균'), 0)

    def test_손으로_누른_오탐은_그대로_학습한다(self):
        """뮤트가 아니라 건건이 '오탐지' 를 누른 이력은 예전처럼 쓴다."""
        from v1.regulatory.services import matcher

        self._fp_rows('대장균', '정제수', 10)
        fp = matcher._load_fp_patterns_for_user(self.user)
        self.assertEqual(fp.keyword_fp_count('대장균'), 10)
        self.assertTrue(fp.is_fp('대장균', '정제수'))


class 수거검사_상세도_같은_흐름이다(TestCase):
    """
    세 탭이 "왜 나한테 왔는가 → 그 이유를 끈다" 라는 같은 흐름을 갖는다.

    수거검사는 업소명이 오탐의 주범이다 — 회사명이 짧으면('삼립') 남의
    업체('○○삼립식품')까지 걸린다. 예전에는 '해당 없음(삭제)' 뿐이라, 같은
    업소가 다음 주에 또 올라오면 또 지워야 했다.
    """

    def setUp(self):
        from v1.regulatory.models import InspectionMatch, InspectionResult

        cache.clear()
        self.user = User.objects.create_user(username='inspwhy', password='x')
        self.client.force_login(self.user)
        insp = InspectionResult.objects.create(
            tkawyprno='5', bssh_nm='(주)남의삼립식품', prdtnm='제품',
            prdlst_report_no='20250105', tkawydtm='20260801')
        self.match = InspectionMatch.objects.create(
            inspection=insp, user=self.user,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_COMPANY,
            matched_value='삼립')

    def _html(self):
        return self.client.get(
            '/regulatory/?tab=insp&insp_id=%d' % self.match.id).content.decode()

    def test_알림_사유라는_같은_이름을_쓴다(self):
        self.assertIn('알림 사유', self._html())

    def test_업소를_끌_수_있다(self):
        html = self._html()
        self.assertIn("muteAlert('company'", html)
        self.assertIn('남의삼립식품', html)

    def test_해당_없음은_이_건만_지운다고_말한다(self):
        """다음 건은 계속 온다는 사실을 문구가 밝혀야 '왜 또 오지' 가 없다."""
        self.assertIn('이 건만 삭제', self._html())

    def test_내_제품_번호로_걸린_건은_끄지_않는다(self):
        """내 제품이 맞는데 '이 업소 알림 끄기' 를 권하면 말이 안 맞는다."""
        from v1.regulatory.models import InspectionMatch

        self.match.match_reason = InspectionMatch.REASON_LABEL
        self.match.save(update_fields=['match_reason'])
        self.assertNotIn("muteAlert('company'", self._html())


class 끄는_단추는_한_벌만_둔다(TestCase):
    """
    같은 단추가 세 곳에 나온다 — 목록의 뉴스 상세, 목록의 수거검사 상세,
    상세 독립 페이지. 인라인 스크립트로 두면 뉴스가 선택됐을 때만 정의돼
    수거검사 패널에서는 죽은 단추가 된다. 그래서 정적 파일 하나로 둔다.
    """

    def test_상세_패널이_제_사본을_들고_있지_않다(self):
        from pathlib import Path
        from django.conf import settings

        for root in settings.TEMPLATES[0]['DIRS']:
            path = Path(root) / 'regulatory' / '_news_detail_panel.html'
            if path.exists():
                body = path.read_text(encoding='utf-8')
                self.assertNotIn('window.muteAlert', body)
                self.assertNotIn('window.deleteKeywordFromDetail', body)
                return
        self.fail('_news_detail_panel.html 을 찾지 못했다')

    def test_두_화면이_같은_파일을_부른다(self):
        from pathlib import Path
        from django.conf import settings

        for root in settings.TEMPLATES[0]['DIRS']:
            base = Path(root) / 'regulatory'
            if not base.exists():
                continue
            for name in ('news_list.html', 'news_detail.html'):
                self.assertIn('regulatory_alert_mute.js',
                              (base / name).read_text(encoding='utf-8'), name)
            return
        self.fail('regulatory 템플릿 폴더를 찾지 못했다')


class 상세가_왜_왔는지_말한다(TestCase):
    """
    '포함 원료: X' 한 줄로는, 부적합 정보의 **어떤 말**이 내 원료 X 를 끌어왔는지
    알 수 없었다. 알림이 많다고 느낀 사람이 손댈 곳을 못 찾은 이유다.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='why', password='x')
        self.client.force_login(self.user)
        label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                       prdlst_nm='내 제품')
        self.news = RegulatoryNews.objects.create(
            external_id='why-1', api_source='I2620', source='domestic',
            product_name='어떤 부적합', ai_parsed=True, collected_date='2026-08-01')
        NewsProductMatch.objects.create(
            news=self.news, product=label, matched_keyword='대장균',
            matched_ingredient='정제수', match_score=90, risk_score=50)

    def test_좌변과_우변을_나란히_보여_준다(self):
        html = self.client.get('/regulatory/?id=%d' % self.news.id).content.decode()
        self.assertIn('알림 사유', html)
        self.assertIn('대장균', html)      # 부적합 정보에서 뽑힌 말
        self.assertIn('정제수', html)      # 내 원료

    def test_그_자리에서_끌_수_있다(self):
        html = self.client.get('/regulatory/?id=%d' % self.news.id).content.decode()
        self.assertIn("muteAlert('keyword'", html)
        self.assertIn("muteAlert('ingredient'", html)

    def test_행정처분은_업체를_끄게_한다(self):
        """행정처분은 업체명 하나로 걸린다 — 원료를 끄라고 하면 말이 안 맞는다."""
        news = RegulatoryNews.objects.create(
            external_id='why-2', api_source='I0470', source='domestic',
            product_name='행정처분', company_name='(주)어떤식품',
            ai_parsed=True, collected_date='2026-08-01')
        label = MyLabel.objects.get(user_id=self.user)
        NewsProductMatch.objects.create(
            news=news, product=label, matched_keyword='(주)어떤식품',
            matched_ingredient='어떤식품', match_score=90, risk_score=50)

        html = self.client.get('/regulatory/?id=%d' % news.id).content.decode()
        self.assertIn("muteAlert('company'", html)
        self.assertNotIn("muteAlert('ingredient'", html)


class RegulatoryLayoutTests(TestCase):
    """
    부적합·처분 알림 화면의 뼈대 — 제품 관리 상단 + 원료 관리 본문.

    이 화면만 자기 팔레트(--c-*)와 자기 컴포넌트를 들고 있어서, 제품 관리·원료
    관리를 오가면 같은 뜻의 색과 같은 뜻의 컨트롤이 미묘하게 달라 보였다.
    아래 조건들은 그 통일을 지킨다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        from v1.regulatory.models import InspectionMatch, InspectionResult

        cache.clear()
        self.user = User.objects.create_user(username='layout', password='x')
        self.client.force_login(self.user)

        label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                       prdlst_nm='내 제품')
        for i in range(4):
            news = RegulatoryNews.objects.create(
                external_id=f'l{i}', api_source='I2620', source='domestic',
                product_name=f'제품 {i}', company_name=f'업체 {i}',
                violation_reason='대장균 기준 초과', collected_date='2026-08-01')
            if i < 2:
                NewsProductMatch.objects.create(news=news, product=label,
                                                match_score=90, risk_score=50,
                                                risk_level='HIGH')
        insp = InspectionResult.objects.create(
            tkawyprno='1', bssh_nm='업소', prdtnm='검사 제품',
            prdlst_report_no='20250101', tkawydtm='20260801',
            plan_titl='2026 상반기', exc_instt_nm='식약처')
        InspectionMatch.objects.create(
            inspection=insp, user=self.user, label=label,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)

        base = Path(dj.BASE_DIR)
        self.tpl = (base / 'templates/regulatory/news_list.html').read_text(encoding='utf-8')
        self.item = (base / 'templates/regulatory/_news_item.html').read_text(encoding='utf-8')
        self.css = (base / 'static/css/regulatory.css').read_text(encoding='utf-8')
        self.html = self.client.get('/regulatory/').content.decode('utf-8')

    # ── 상단: 제품 관리와 같은 통계 카드 줄 ──────────────────────────────
    def test_통계_카드_줄이_있다(self):
        """이 화면에 들어와 제일 먼저 묻는 것이 "지금 볼 게 몇 건인가" 다."""
        self.assertIn('class="reg-stats"', self.html)
        self.assertEqual(self.html.count('class="reg-stat-icon'), 5)
        for label in ('전체 알림', '내 알림', '일반', '미조치', '수거검사 미확인'):
            self.assertIn(label, self.html)

    def test_카드가_눌러서_거르는_지름길이다(self):
        """숫자만 보여 주면 그 숫자를 만든 목록으로 갈 방법이 없다."""
        self.assertIn('href="?scope=mine"', self.html)
        self.assertIn('href="?tab=insp"', self.html)

    def test_같은_것을_두_번_묻지_않는다(self):
        """
        예전에는 카드 줄이 '지표', 툴바의 칩 줄이 '스위치' 라고 갈라 놓았다.
        그런데 둘이 같은 곳으로 가는 같은 링크여서, 한 화면에서 같은 것을 두 번
        묻는 꼴이었고 어느 쪽을 눌러야 하는지가 오히려 헷갈렸다.
        범위와 미조치는 카드 한 벌로 합쳤다.
        """
        self.assertNotIn('rs-scope-chip', self.html)
        self.assertNotIn('미조치만', self.html)
        # 카드가 스위치를 겸하므로 켜짐 상태를 카드가 들고 있어야 한다
        r = self.client.get('/regulatory/?scope=others')
        self.assertIn('reg-stat--on', r.content.decode('utf-8'))

    def test_범위_셋이_모두_카드에_있다(self):
        """칩을 걷어내면서 '일반만 보기' 로 갈 길이 사라지면 안 된다."""
        for qs in ('scope=mine', 'scope=others'):
            self.assertIn(f'href="?{qs}"', self.html)

    # ── 본문: 원료 관리와 같은 좌 목록 / 우 상세 ─────────────────────────
    def test_목록이_표다(self):
        """제품 관리·원료 관리와 같은 44px 표 행 — 둘짜리 카드가 아니다."""
        self.assertIn('<table class="reg-table">', self.html)
        self.assertIn('<tr class="rs-item', self.html)
        self.assertIn('<td>', self.html)
        # 예전 카드 마크업의 두 줄 구조가 남아 있으면 안 된다
        self.assertNotIn('class="rs-row1"', self.html)
        self.assertNotIn('class="rs-row2"', self.html)

    def test_표가_한_번만_열리고_닫힌다(self):
        self.assertEqual(self.html.count('<table class="reg-table">'), 1)
        self.assertEqual(self.html.count('</table>'), 1)
        self.assertEqual(self.html.count('<tbody>'), 1)
        self.assertEqual(self.html.count('</tbody>'), 1)

    def test_페이지네이션이_표_밖에_있다(self):
        """
        <tbody> 안의 <div> 는 브라우저가 표 앞으로 끌어낸다. 예전 마크업에서는
        수거검사 페이지네이션이 실제로 목록 위에 떠 있었다.
        """
        body = self.html[self.html.index('<tbody>'):self.html.index('</tbody>')]
        self.assertNotIn('class="rs-pagination', body)
        self.assertNotIn('<div', body.replace('<div class="rs-name-cell">', '')
                                     .replace('<div class="reg-sep-line">', '')
                                     .replace('<div class="rs-empty">', ''))

    def test_세_탭이_한_표를_쓴다(self):
        """
        탭마다 목록을 따로 그리면 정렬·페이지네이션·선택 상태를 세 벌 맞춰야
        한다. 지금 탭에 없는 줄은 CSS 가 감춘다.
        """
        self.assertIn('reg-thead--news', self.html)
        self.assertIn('reg-thead--insp', self.html)
        self.assertIn('#regSidebar[data-view="insp"] .rs-item:not(.rs-item--insp)', self.css)

    def test_오른쪽은_읽는_자리다(self):
        """상세 검색 폼이 상세 패널을 밀어내던 것을 툴바 서랍으로 옮겼다."""
        self.assertIn('class="rd-panel-header"', self.html)
        self.assertNotIn('rd-cond-box', self.html)
        self.assertNotIn('id="condForm"', self.html)

    def test_폼이_하나다(self):
        """
        예전에는 검색 폼과 조건 폼이 따로라 같은 값(검색어·기간·정렬)을 두 벌
        hidden 으로 들고 다녔고, 한쪽만 고치면 조건이 조용히 사라졌다.
        """
        self.assertEqual(self.html.count('<form method="get"'), 1)
        self.assertIn('id="filterForm"', self.html)

    def test_상세_조건은_접어_둔다(self):
        self.assertIn('id="regCondDrawer"', self.html)
        self.assertIn('id="regCondToggle"', self.html)
        # 조건이 없으면 서랍은 닫혀 있다
        drawer = self.html[self.html.index('id="regCondDrawer"'):][:60]
        self.assertIn('hidden', drawer)

    # ── 색·규격을 공용 토큰에서 가져온다 ─────────────────────────────────
    def test_자체_팔레트를_두지_않는다(self):
        """
        같은 "빨강" 이 제품 관리에서는 #c5221f, 여기서는 #b31412 였다.
        :root 블록은 이제 variables.css 의 --ez-* 만 가리킨다.
        """
        head = self.css.index(':root {')
        block = self.css[head:self.css.index('}', head)]
        # 뜻이 있는 색(파랑·빨강·주황·초록·회색 계열)은 전부 공용 토큰이어야 한다.
        # 두 바닥색(--c-bg-surface / --c-bg-detail)은 예외다 — 원료 관리 패널의
        # 값을 그대로 맞춘 것이라, 공용 토큰이 아니라 그 화면이 기준이다.
        exempt = ('--c-bg-surface', '--c-bg-detail')
        checked = 0
        for line in block.split('\n'):
            if '--c-' not in line or ':' not in line or any(e in line for e in exempt):
                continue
            value = line.split(':', 1)[1].split(';')[0]
            if '#' in value:
                self.fail(f'토큰이 색을 직접 들고 있다: {line.strip()}')
            if 'var(--ez-' in value:
                checked += 1
        self.assertGreater(checked, 15, ':root 에서 공용 토큰을 거의 안 쓰고 있다')

    def test_수거검사_줄도_같은_표에_있다(self):
        r = self.client.get('/regulatory/?tab=insp')
        html = r.content.decode('utf-8')
        self.assertIn('<tr class="rs-item rs-item--insp', html)
        self.assertIn('rs-item--insp-unread', html)

    def test_상세가_카드로_쌓인다(self):
        """
        예전에는 패널 전체가 흰 종이 한 장이고 구역을 실선으로만 갈랐다.
        어디까지가 한 덩어리인지 눈으로 잡히지 않았다.
        """
        match = NewsProductMatch.objects.first()
        html = self.client.get(f'/regulatory/?id={match.news_id}').content.decode('utf-8')
        self.assertIn('class="rd-wrap"', html)
        self.assertIn('class="rd-sec-body"', html)
        # 카드 공통 규칙이 헤더·구역·접기를 한꺼번에 잡는다
        self.assertIn('.rd-hdr, .rd-sec, .rd-ai-details', self.css)

    def test_국기_이모지를_쓰지_않는다(self):
        """이모지는 OS마다 모양·너비가 달라 배지 높이가 들쭉날쭉했다."""
        from pathlib import Path

        from django.conf import settings as dj

        panel = (Path(dj.BASE_DIR) / 'templates/regulatory/_news_detail_panel.html'
                 ).read_text(encoding='utf-8')
        self.assertNotIn('🇰🇷', panel)
        self.assertNotIn('🇰🇷', self.item)

    def test_비어_있던_두_칸을_한_칸으로_합쳤다(self):
        """
        '등급' 과 '조치' 는 둘 다 내 매칭이 있을 때만 값이 있는데, 목록의
        압도적 다수는 일반 알림이라 74px 짜리 두 칸이 나란히 '—' 로 차 있었다.
        수거검사의 '판정'·'변동' 도 마찬가지였다(변동은 2차 알림에만 값이 있다).
        """
        self.assertIn('rs-mine-cell', self.item)
        self.assertIn('rs-mine-cell', self.html)
        # 표 머리도 한 칸씩 줄었다 — 줄과 머리의 칸 수가 어긋나면 표가 밀린다
        for thead in ('reg-thead--news', 'reg-thead--insp'):
            head = self.html[self.html.index(thead):]
            head = head[:head.index('</thead>')]
            self.assertEqual(head.count('<th'), 6, thead)

    def test_채울_것이_없으면_비워_둔다(self):
        """'—' 를 두 개 그리는 것보다 빈 칸이 조용하고, 값이 있는 줄이 눈에 띈다."""
        r = self.client.get('/regulatory/?scope=others')
        html = r.content.decode('utf-8')
        row_start = html.index('rs-mine-cell')
        cell = html[row_start:html.index('</td>', row_start)]
        self.assertNotIn('—', cell)

    def test_조치_칸을_통째로_다시_쓴다(self):
        """
        미조치 상태에는 배지가 없다(칸이 '—' 다). 예전 스크립트는 배지 요소를
        찾아 갈아 끼웠기 때문에, 첫 조치가 목록에 반영되지 않았다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        panel = (Path(dj.BASE_DIR) / 'templates/regulatory/_news_detail_panel.html'
                 ).read_text(encoding='utf-8')
        self.assertIn('rs-status-cell', self.item)
        for source in (self.tpl, panel):
            self.assertIn(".querySelector('.rs-status-cell')", source)
            self.assertNotIn('.badge-status-no', source)


class 탭_상태는_서버가_그린다(TestCase):
    """
    탭 전환은 곧 페이지 이동이다. 그런데 예전에는 템플릿이 data-view 를 늘
    'insp-news' 로 박아 놓고, 브라우저에서 스크립트가 주소의 tab 파라미터를
    읽어 뒤늦게 고쳐 주는 구조였다.

    그래서 스크립트가 한 번이라도 멈추면(오래된 캐시, 앞쪽 구문 오류, 정적 파일
    실패 어느 것이든) 주소는 ?tab=admin 인데 화면은 부적합 탭 그대로였다.
    하필 기본 탭인 부적합만 멀쩡해서, "행정처분·수거검사 탭은 클릭이 안 된다"
    로 나타났다. 본서버에서 실제로 나온 신고다.
    """

    def setUp(self):
        from v1.regulatory.models import InspectionMatch, InspectionResult

        cache.clear()
        self.user = User.objects.create_user(username='tabstate', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='내 제품',
                                            prdlst_nm='내 제품')
        RegulatoryNews.objects.create(
            external_id='ts-insp', api_source='I2620', source='domestic',
            product_name='부적합 건', collected_date='2026-08-01')
        RegulatoryNews.objects.create(
            external_id='ts-admin', api_source='I0470', source='domestic',
            product_name='행정처분 건', collected_date='2026-08-01')
        insp = InspectionResult.objects.create(
            tkawyprno='3', bssh_nm='업소', prdtnm='검사 제품',
            prdlst_report_no='20250103', tkawydtm='20260801')
        self.insp_match = InspectionMatch.objects.create(
            inspection=insp, user=self.user, label=self.label,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)

    def _view(self, url):
        html = self.client.get(url).content.decode('utf-8')
        marker = 'id="regSidebar" data-view="'
        start = html.index(marker) + len(marker)
        return html[start:html.index('"', start)], html

    def test_주소의_탭이_곧_화면의_탭이다(self):
        for url, expected in (('/regulatory/', 'insp-news'),
                              ('/regulatory/?tab=admin', 'admin'),
                              ('/regulatory/?tab=insp', 'insp')):
            view, _ = self._view(url)
            self.assertEqual(view, expected, url)

    def test_수거검사_상세를_열면_수거검사_탭이다(self):
        """탭 파라미터 없이 상세 주소만으로 들어오는 길이 있다."""
        view, _ = self._view(f'/regulatory/?insp_id={self.insp_match.id}')
        self.assertEqual(view, 'insp')

    def test_눌린_탭_단추도_서버가_표시한다(self):
        _, html = self._view('/regulatory/?tab=admin')
        admin_btn = html[html.index('id="vtabAdmin"') - 200:html.index('id="vtabAdmin"')]
        self.assertIn('rs-vtab--active', admin_btn)
        # 기본 탭이 함께 켜져 있으면 안 된다
        news_btn = html[html.index('id="vtabInspNews"') - 200:html.index('id="vtabInspNews"')]
        self.assertNotIn('rs-vtab--active', news_btn)

    def test_툴바_줄도_서버가_고른다(self):
        """수거검사 탭은 툴바 2행이 다르다 — 이것도 스크립트에 맡기지 않는다."""
        _, html = self._view('/regulatory/?tab=insp')
        page = html[html.index('id="regPage"') - 200:html.index('id="regPage"')]
        self.assertIn('reg-page--insp', page)

    def test_스크립트가_주소를_다시_읽지_않는다(self):
        """
        서버가 그린 값이 있는데 스크립트가 주소에서 다시 뽑아 쓰면, 두 곳이
        어긋날 여지가 남는다. 초기화는 서버가 그린 data-view 를 그대로 쓴다.
        """
        _, html = self._view('/regulatory/')
        self.assertIn("var initialTab = (sidebar && sidebar.dataset.view)", html)


class 등록했는데_안_걸렸을_때(TestCase):
    """
    수거검사 알림에 회사명을 넣어 둔 사람이 오른쪽 패널에서 이 말을 봤다.

        내 정보가 등록되지 않았습니다.

    등록은 돼 있었다. 그 회사명으로 최근 30일 안에 걸린 검사가 없었을 뿐이다.
    **등록을 안 한 것과 등록했는데 안 걸린 것은 다르다.** 같은 말을 하면
    사람은 저장이 안 된 줄 알고 같은 값을 다시 넣는다.
    """

    def setUp(self):
        from v1.user_management.models import UserProfile

        cache.clear()
        self.user = User.objects.create_user(username='insp-empty', password='x')
        self.client.force_login(self.user)
        self.profile = UserProfile.objects.filter(user=self.user).first()
        if self.profile is None:
            self.profile = UserProfile.objects.create(user=self.user)

    def _html(self):
        return self.client.get('/regulatory/?tab=insp').content.decode('utf-8')

    def test_아무것도_안_넣었으면_등록하라고_한다(self):
        html = self._html()
        self.assertIn('내 정보가 등록되지 않았습니다', html)
        self.assertIn('내 정보 등록하기', html)

    def test_넣어_뒀으면_등록됐다고_말한다(self):
        self.profile.company_name = '비알코리아'
        self.profile.save(update_fields=['company_name'])

        html = self._html()
        self.assertNotIn('내 정보가 등록되지 않았습니다', html)
        self.assertIn('등록은 되어 있습니다', html)
        # 무엇으로 맞춰 봤는지 그 값을 보여 준다
        self.assertIn('비알코리아', html)

    def test_어디까지_맞춰_봤는지_말한다(self):
        """
        거슬러 맞춰 보는 기간은 서버가 정한다. 화면이 다른 숫자를 적으면
        어느 날 한쪽만 고쳐진다.
        """
        from v1.regulatory.services.collector import INSPECTION_BACKFILL_DAYS

        self.profile.license_number = '19630364001'
        self.profile.save(update_fields=['license_number'])

        html = self._html()
        self.assertIn(f'최근 {INSPECTION_BACKFILL_DAYS}일치', html)
        self.assertIn('19630364001', html)

    def test_전체_목록에서_찾아볼_길을_준다(self):
        """소급 기간 밖의 것은 공개 목록에서 회사명으로 찾을 수 있다."""
        self.profile.company_name = '비알코리아'
        self.profile.save(update_fields=['company_name'])

        html = self._html()
        self.assertIn('tab=insp&amp;q=%EB%B9%84%EC%95%8C%EC%BD%94%EB%A6%AC%EC%95%84', html)


class AI_를_태우지_않는_것은_한_곳에서_정한다(TestCase):
    """
    같은 새올 파일을 어느 명령으로 넣느냐에 따라 결과가 달랐다.

        collect_regulatory_news : ('I0470-', 'I0480-', 'I0482-', 'saol-')
        sync_import_news        : ('I0470-', 'I0480-')

    행정처분은 업체 단위라("무신고 영업", "영업정지 7일") AI 가 뽑을 원재료도
    검출 물질도 없다. 그런데 sync 로 넣으면 새올 건이 ai_parsed=False 로 남고,
    다음 날 정기 수집이 **그걸 전부 OpenAI 로 보낸다.** 백필 한 번이 만 건을
    넘으니 조용히 큰돈이 나가는 종류다.
    """

    def test_새올은_AI_대상이_아니다(self):
        from v1.regulatory.services.ai_parser import is_admin_disposal

        self.assertTrue(is_admin_disposal('saol-namyangju-1a2b3c'))
        self.assertTrue(is_admin_disposal('I0470-123'))
        self.assertTrue(is_admin_disposal('I0482-123'))

    def test_검사부적합은_AI_대상이다(self):
        from v1.regulatory.services.ai_parser import is_admin_disposal

        self.assertFalse(is_admin_disposal('I2620-123'))
        self.assertFalse(is_admin_disposal('CFCEE01F01-9'))
        self.assertFalse(is_admin_disposal(''))
        self.assertFalse(is_admin_disposal(None))

    def test_목록을_두_벌로_두지_않는다(self):
        """두 벌이면 어느 날 한쪽만 고쳐진다 — 실제로 그렇게 갈렸다."""
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR) / 'regulatory'
        for name in ('collect_regulatory_news', 'sync_import_news'):
            path = base / 'management' / 'commands' / ('%s.py' % name)
            text = path.read_text(encoding='utf-8')
            self.assertNotIn("= ('I0470-", text, '%s 가 목록을 또 갖고 있다' % name)
            self.assertIn('is_admin_disposal', text)

    def test_두_명령이_같은_판정을_쓴다(self):
        import importlib

        one = importlib.import_module(
            'v1.regulatory.management.commands.collect_regulatory_news')
        two = importlib.import_module(
            'v1.regulatory.management.commands.sync_import_news')
        self.assertIs(one.is_admin_disposal, two.is_admin_disposal)


class 새올_파일도_같은_명령으로_넣는다(TestCase):
    """
    로컬에서 긁어 PA 서버에 올린 new_saol_data.json 을 서버가 읽는 길.

    정기 수집(collect_regulatory_news)은 파일을 **읽고 지운다.** 백필처럼 큰
    파일은 한 번 실패하면 되돌릴 수 없으므로, 파일만 넣고 싶을 때는 sync 에
    --keep-file 로 준다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        self.src = (Path(dj.BASE_DIR)
                    / 'regulatory/management/commands/sync_import_news.py'
                    ).read_text(encoding='utf-8')

    def test_새올_경로를_적어_둔다(self):
        self.assertIn('/home/labeldata/mysite/new_saol_data.json', self.src)

    def test_파일을_지키는_길이_설명에_있다(self):
        self.assertIn('--keep-file', self.src)

    def test_새올_건은_저장할_때부터_분석_완료로_들어간다(self):
        """ai_parsed=False 로 남기면 다음 정기 수집이 OpenAI 로 보낸다."""
        from v1.regulatory.models import RegulatoryNews
        from v1.regulatory.services.ai_parser import is_admin_disposal

        news = RegulatoryNews.objects.create(
            source=RegulatoryNews.SOURCE_DOMESTIC,
            external_id='saol-geoje-deadbeef',
            api_source='saol_admin',
            product_name='OO식당',
            ai_parsed=is_admin_disposal('saol-geoje-deadbeef'),
        )
        self.assertTrue(news.ai_parsed)
