"""
표시사항(label) 앱 회귀 테스트.

눈으로는 회귀를 잡기 어려운 것들만 고정해 둔다.
  - 수거검사 소급 매칭 트리거(MyLabel post_save): 화면에 아무것도 드러내지 않으면서
    알림 데이터를 지우고 FCM을 발송한다.
  - 식품유형 검색 API: 이름이 겹치는 항목의 판정 순서가 조용히 뒤집힐 수 있다.
  - 표시사항 검증 규칙: 판정이 조용히 느슨해져도 화면은 "적합"으로 보인다.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from v1.label.models import (
    AgriculturalProduct,
    FoodAdditive,
    FoodType,
    LabelIngredientRelation,
    MyIngredient,
    MyLabel,
)
from v1.regulatory.models import InspectionMatch, InspectionResult

BACKFILL = 'v1.regulatory.services.collector.backfill_inspection_matches'


class InspectionBackfillTriggerTests(TestCase):
    """
    MyLabel 저장 시 수거검사 소급 매칭이 언제 도는지 / 무엇을 지우는지.

    과거 이 시그널은 update_fields 가 없는 저장(= 폼 전체 저장, 실제 경로 전부)에서
    항상 실행되면서 사용자의 InspectionMatch 를 전량 삭제했다. 그 결과
      - 재생성되지 않는 PHASE_JUDGMENT(부적합 판정 알림)가 영구 소실됐고
      - collector 의 중복 검사(already)가 무력화되어 저장할 때마다 FCM 이 재발송됐다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.user,
            my_label_name='테스트 라벨',
            prdlst_report_no='19990101000001',
        )

    # ── 트리거 조건 ──────────────────────────────────────────────────────────

    def test_품목보고번호가_그대로면_소급매칭을_돌리지_않는다(self):
        """폼 전체 저장(update_fields 없음)이라도 번호가 안 바뀌면 실행되면 안 된다."""
        with patch(BACKFILL) as mock_backfill:
            self.label.my_label_name = '이름만 바꿈'
            self.label.save()
        mock_backfill.assert_not_called()

    def test_DB에서_다시_읽어_저장해도_돌지_않는다(self):
        """뷰의 실제 경로 — get() 후 폼 값을 얹어 save() 하는 형태."""
        fresh = MyLabel.objects.get(pk=self.label.pk)
        with patch(BACKFILL) as mock_backfill:
            fresh.prv_recycling_mark_enabled = 'Y'
            fresh.save()
        mock_backfill.assert_not_called()

    def test_품목보고번호가_바뀌면_소급매칭을_돌린다(self):
        with patch(BACKFILL) as mock_backfill:
            self.label.prdlst_report_no = '19990101000002'
            self.label.save()
        self.assertEqual(mock_backfill.call_count, 1)

    def test_FCM_발송은_요청_스레드에서_돌리지_않는다(self):
        """
        저장은 웹 요청 안이므로 FCM 왕복(timeout 5초)이 응답에 얹히면 안 된다.
        push_async 를 빠뜨리면 저장이 그만큼 느려지는데 화면에는 아무 표시도 없다.
        """
        with patch(BACKFILL) as mock_backfill:
            self.label.prdlst_report_no = '19990101000005'
            self.label.save()
        self.assertIs(mock_backfill.call_args.kwargs.get('push_async'), True)

    def test_품목보고번호를_처음_입력하면_돌린다(self):
        blank = MyLabel.objects.create(user_id=self.user, my_label_name='번호 없는 라벨')
        with patch(BACKFILL) as mock_backfill:
            blank.prdlst_report_no = '19990101000003'
            blank.save()
        self.assertEqual(mock_backfill.call_count, 1)

    def test_삭제된_라벨은_건너뛴다(self):
        with patch(BACKFILL) as mock_backfill:
            self.label.delete_YN = 'Y'
            self.label.prdlst_report_no = '19990101000004'
            self.label.save()
        mock_backfill.assert_not_called()

    # ── 삭제 범위 ────────────────────────────────────────────────────────────

    def _make_match(self, label, phase, inspection):
        return InspectionMatch.objects.create(
            inspection=inspection,
            user=self.user,
            label=label,
            alert_phase=phase,
            match_reason=InspectionMatch.REASON_LABEL,
            matched_value='19990101000001',
            prev_judgment='',
            notified_at=timezone.now(),
            read_yn=True,
        )

    def test_번호_변경시_해당_라벨의_수거감지_매칭만_지운다(self):
        inspection = InspectionResult.objects.create(
            tkawyprno='T-1', bssh_nm='테스트업소',
            prdlst_report_no='19990101000001', tkawydtm='19990101',
        )
        other_label = MyLabel.objects.create(
            user_id=self.user, my_label_name='다른 라벨',
            prdlst_report_no='19990101000009',
        )

        target    = self._make_match(self.label,  InspectionMatch.PHASE_COLLECTION, inspection)
        judgment  = self._make_match(self.label,  InspectionMatch.PHASE_JUDGMENT,   inspection)
        other     = self._make_match(other_label, InspectionMatch.PHASE_COLLECTION, inspection)
        unlinked  = self._make_match(None,        InspectionMatch.PHASE_COLLECTION, inspection)

        with patch(BACKFILL):
            self.label.prdlst_report_no = '19990101000002'
            self.label.save()

        exists = lambda m: InspectionMatch.objects.filter(pk=m.pk).exists()
        self.assertFalse(exists(target),   '번호가 바뀐 라벨의 수거감지 매칭은 정리되어야 한다')
        self.assertTrue(exists(judgment),  '부적합 판정 알림은 재생성되지 않으므로 보존되어야 한다')
        self.assertTrue(exists(other),     '다른 라벨의 매칭은 건드리면 안 된다')
        self.assertTrue(exists(unlinked),  '인허가번호·회사명으로 잡힌 매칭은 건드리면 안 된다')


class FoodTypeOptionsApiTests(TestCase):
    """
    식품유형 선택용 검색 API(/label/food-type-options/).

    농수축산물 1만 건을 화면에 통째로 싣던 것을 이 API 로 대체했다. 화면 쪽
    판정 로직을 서버로 옮긴 것이라, 겹치는 이름의 우선순위가 예전과 같아야 한다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='searcher', password='x')
        self.client.force_login(self.user)

        FoodType.objects.create(food_group='과자류', food_type='과자')
        FoodType.objects.create(food_group='곡류가공품', food_type='밀가루')

        # 밀가루는 가공식품과, 차추출물은 첨가물과 이름이 겹친다 (실제 데이터에도 있는 상황)
        for name in ('밀가루', '차추출물', '사과', '사과주스', '사과칩'):
            AgriculturalProduct.objects.create(rprsnt_rawmtrl_nm=name)

        FoodAdditive.objects.create(name_kr='차추출물')
        FoodAdditive.objects.create(name_kr='치자황색소')

    def _get(self, **params):
        return self.client.get('/label/food-type-options/', params).json()

    # ── 검색 ────────────────────────────────────────────────────────────────

    def test_구분을_지정하면_그_구분만_돌려준다(self):
        data = self._get(category='agricultural', q='사과')
        names = sorted(r['text'] for r in data['results'])
        self.assertEqual(names, ['사과', '사과주스', '사과칩'])
        self.assertTrue(all(r['category'] == 'agricultural' for r in data['results']))

    def test_구분을_비우면_세_종류를_모두_찾는다(self):
        data = self._get(q='차추출물')
        found = {(r['text'], r['category']) for r in data['results']}
        self.assertIn(('차추출물', 'agricultural'), found)
        self.assertIn(('차추출물', 'additive'), found)

    def test_limit_을_넘으면_more_가_참이다(self):
        data = self._get(category='agricultural', q='사과', limit=2)
        self.assertEqual(len(data['results']), 2)
        self.assertTrue(data['more'])

    def test_limit_이_충분하면_more_가_거짓이다(self):
        data = self._get(category='agricultural', q='사과', limit=10)
        self.assertEqual(len(data['results']), 3)
        self.assertFalse(data['more'])

    def test_limit_상한은_100이다(self):
        """호출부가 limit 을 크게 넣어도 서버가 잘라야 한다."""
        AgriculturalProduct.objects.bulk_create(
            [AgriculturalProduct(rprsnt_rawmtrl_nm='대량원료%04d' % i) for i in range(150)]
        )
        data = self._get(category='agricultural', q='대량원료', limit=9999)
        self.assertEqual(len(data['results']), 100)
        self.assertTrue(data['more'])

    def test_알_수_없는_구분은_전체_검색으로_처리한다(self):
        data = self._get(category='존재하지않음', q='차추출물')
        cats = {r['category'] for r in data['results']}
        self.assertEqual(cats, {'agricultural', 'additive'})

    # ── 역방향 조회 ─────────────────────────────────────────────────────────

    def test_판정_순서는_가공식품_농수축산물_첨가물_이다(self):
        """
        이름이 겹칠 때 어느 구분으로 볼지는 화면에서 쓰던 순서를 그대로 지켜야 한다.
        순서를 바꾸면 '차추출물' 같은 원료의 식품구분이 조용히 뒤집힌다.
        """
        self.assertEqual(self._get(exact='밀가루')['category'], 'processed')
        self.assertEqual(self._get(exact='차추출물')['category'], 'agricultural')
        self.assertEqual(self._get(exact='치자황색소')['category'], 'additive')

    def test_어디에도_없는_이름은_None_을_돌려준다(self):
        self.assertIsNone(self._get(exact='없는이름입니다')['category'])

    # ── 접근 제어 ───────────────────────────────────────────────────────────

    def test_로그인하지_않으면_접근할_수_없다(self):
        self.client.logout()
        resp = self.client.get('/label/food-type-options/', {'q': '사과'})
        self.assertIn(resp.status_code, (302, 403))


class IngredientRatioOrderCheckTests(TestCase):
    """
    배합비 내림차순 검사(validation_service.check_ingredient_ratio_order).

    같은 규정을 보는 AI 검사가 따로 있지만 그쪽은 표시 문구에 %가 적혀 있어야만
    판정한다. 이 검사는 원재료 팝업에 입력된 배합비를 그대로 보므로 AI 없이,
    무료로, 언제나 판정한다. 실제 데이터에서도 AI 검사가 놓치던 건을 잡았다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='ratio', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='검사용 라벨')

    def _add(self, name, ratio, sequence, display_name='', category='processed'):
        ing = MyIngredient.objects.create(
            user_id=self.user,
            prdlst_nm=name,
            ingredient_display_name=display_name,
            food_category=category,
            delete_YN='N',
        )
        return LabelIngredientRelation.objects.create(
            label=self.label,
            ingredient=ing,
            relation_sequence=sequence,
            ingredient_ratio=ratio,
        )

    def _messages(self):
        from v1.label.services.validation_service import check_ingredient_ratio_order
        return [i['message'] for i in check_ingredient_ratio_order(self.label)]

    def test_내림차순이면_지적하지_않는다(self):
        self._add('밀가루', 50, 1)
        self._add('설탕', 30, 2)
        self._add('소금', 5, 3)
        self.assertEqual(self._messages(), [])

    def test_역순이면_어느_행인지_짚어준다(self):
        self._add('밀가루', 30, 1)
        self._add('설탕', 50, 2)
        msgs = self._messages()
        self.assertEqual(len(msgs), 1)
        self.assertIn('밀가루', msgs[0])
        self.assertIn('설탕', msgs[0])
        self.assertIn('30%', msgs[0])
        self.assertIn('50%', msgs[0])

    def test_배합비가_빈_행은_비교에서_뺀다(self):
        """모르는 값을 추측해서 위반이라고 하면 안 된다."""
        self._add('밀가루', 50, 1)
        self._add('향료', None, 2)
        self._add('설탕', 30, 3)
        self.assertEqual(self._messages(), [])

    def test_비교할_값이_하나뿐이면_판정하지_않는다(self):
        self._add('밀가루', 50, 1)
        self._add('향료', None, 2)
        self.assertEqual(self._messages(), [])

    def test_같은_값은_위반이_아니다(self):
        self._add('밀가루', 30, 1)
        self._add('설탕', 30, 2)
        self.assertEqual(self._messages(), [])

    def test_역순이_여러_번이면_각각_짚는다(self):
        self._add('가', 10, 1)
        self._add('나', 20, 2)
        self._add('다', 30, 3)
        self.assertEqual(len(self._messages()), 2)

    def test_긴_원료명은_줄여서_보여준다(self):
        """혼합제제 표시명은 100자를 넘기도 해서, 그대로 넣으면 메시지를 못 읽는다."""
        long_name = '산성피로인산나트륨, 옥수수전분(옥수수-외국산:러시아,헝가리), 탄산수소나트륨, 제일인산칼슘'
        self._add('정제소금', 10, 1)
        self._add(long_name, 20, 2, display_name=long_name)
        msg = self._messages()[0]
        self.assertIn('…', msg)
        self.assertNotIn('제일인산칼슘', msg)


class AdditiveDisplayNameCheckTests(TestCase):
    """
    식품첨가물 표시명 공란 검사(validation_service.check_additive_display_name).

    원재료명 요약을 만드는 쪽은 표시명이 비면 원료명으로 대체한다. 표4 대상
    첨가물은 "명칭(용도)"로 써야 해서 명칭 단독은 표시기준 위반인데, 그게
    화면에 아무 표시 없이 지나간다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='additive', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='첨가물 라벨')

    def _link(self, name, display_name='', category='additive'):
        ing = MyIngredient.objects.create(
            user_id=self.user,
            prdlst_nm=name,
            ingredient_display_name=display_name,
            food_category=category,
            delete_YN='N',
        )
        LabelIngredientRelation.objects.create(
            label=self.label, ingredient=ing, relation_sequence=1,
        )

    def _issues(self):
        from v1.label.services.validation_service import check_additive_display_name
        return check_additive_display_name(self.label)

    def test_표시명이_있으면_지적하지_않는다(self):
        self._link('아질산나트륨', display_name='아질산나트륨(발색제)')
        self.assertEqual(self._issues(), [])

    def test_표4_대상이_공란이면_명칭_용도를_함께_쓰라고_안내한다(self):
        FoodAdditive.objects.create(name_kr='아질산나트륨', alias_4='Y', color_fixative='Y')
        self._link('아질산나트륨')
        msgs = [i['message'] for i in self._issues()]
        self.assertEqual(len(msgs), 1)
        self.assertIn('아질산나트륨', msgs[0])
        self.assertIn('용도', msgs[0])

    def test_표4가_아닌_첨가물_공란은_원료명_대체만_알린다(self):
        FoodAdditive.objects.create(name_kr='구연산', alias_5='Y')
        self._link('구연산')
        msgs = [i['message'] for i in self._issues()]
        self.assertEqual(len(msgs), 1)
        self.assertIn('원료명이 그대로 표시', msgs[0])

    def test_첨가물이_아닌_원료는_보지_않는다(self):
        self._link('밀가루', category='processed')
        self.assertEqual(self._issues(), [])


class ValidateLabelWiringTests(TestCase):
    """새 검사가 실제로 '규정만 검증' 경로에 물려 있는지."""

    def test_새_검사가_무료_검증에_포함된다(self):
        from v1.label.services.validation_service import _CHECKS, validate_label

        names = {c.__name__ for c in _CHECKS}
        self.assertIn('check_ingredient_ratio_order', names)
        self.assertIn('check_additive_display_name', names)

        user = User.objects.create_user(username='wiring', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='빈 라벨')
        result = validate_label(label)
        # 근거 규정 목록에도 새 항목이 드러나야 한다 (검증 범위를 사용자에게 보여주는 값)
        joined = ' '.join(result['checked_regulations'])
        self.assertIn('원재료명 표시 순서', joined)
        self.assertIn('식품첨가물의 표시 방법', joined)
