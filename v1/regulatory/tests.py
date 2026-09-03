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
