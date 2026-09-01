"""
부적합·처분 알림 목록 — 내 알림 / 일반 알림 가르기.

매칭된 건을 전부 위로 고정하던 시절에는, 매칭이 수십 건인 사용자에게 목록 앞
몇 페이지가 통째로 내 알림이었다. 일반 알림에 닿으려면 몇 장을 넘겨야 하는지
알 방법이 없었다 — 개발자도 못 찾았다는 신고가 여기서 나왔다.
"""
from django.contrib.auth import get_user_model
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
