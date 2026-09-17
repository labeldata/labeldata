"""
제품 조회에 붙는 완제품 영양성분 — 번호가 같으면 같은 품목이다.

눈으로는 잡히지 않는 것만 고정한다.

  - 같은 번호에 행이 여럿일 때 **무엇이 뽑히는가.** 틀리게 뽑아도 화면은
    멀쩡하다. 특히 SQL 의 `-crt_mth_nm` 은 거꾸로 선다 — 한글 코드값 차례가
    분석(U+BD84) < 산출 < 수집(U+C218) 이라, 내림차순이면 가장 못 믿을
    '수집' 이 1 위가 된다.
  - 수치 범위 조건이 **한 행 안에서** 함께 걸리는가. 조건마다 따로 걸면
    서로 다른 해의 조사분으로 맞아도 통과한다.
  - 복사할 때 근거가 값과 함께 남는가. 값만 남으면 감사에서 설명할 수 없다.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from v1.label.models import FoodItem, MyLabel, PublicFoodNutrition


class ProductNutritionPickTests(TestCase):
    """같은 번호에 행이 여럿일 때 무엇이 뽑히는가."""

    def setUp(self):
        self.user = User.objects.create_user(username='prodnutri', password='x')
        self.client.force_login(self.user)

        FoodItem.objects.create(
            prdlst_report_no='20220460436160',
            prdlst_nm='표고버섯볶음', prdlst_dcnm='조림류', bssh_nm='하늘농가(주)',
            rawmtrl_nm='새송이버섯(국산)57.64%',
        )
        # 같은 번호에 두 벌 — '수집'(최근) 과 '분석'(예전)
        PublicFoodNutrition.objects.create(
            food_cd='COLLECT1', food_nm_kr='표고버섯볶음', db_grp_nm='가공식품',
            item_report_no='20220460436160', crt_mth_nm='수집',
            research_ymd='20250101', basis_amount=100, basis_unit='g',
            calories=111, carbohydrates=10, sugars=2, proteins=3, fats=5,
            saturated_fats=1, trans_fats=0, cholesterols=0, natriums=300,
            verify_status=PublicFoodNutrition.VERIFY_SKIP,
        )
        PublicFoodNutrition.objects.create(
            food_cd='ANALYZE1', food_nm_kr='표고버섯볶음', db_grp_nm='가공식품',
            item_report_no='20220460436160', crt_mth_nm='분석',
            research_ymd='20190101', basis_amount=100, basis_unit='g',
            calories=222, carbohydrates=20, sugars=4, proteins=6, fats=10,
            saturated_fats=2, trans_fats=0, cholesterols=1, natriums=600,
            verify_status=PublicFoodNutrition.VERIFY_PASS,
        )

    def test_분석이_수집을_이긴다(self):
        from v1.label.services import product_nutrition

        row = product_nutrition.for_report_no('20220460436160')
        self.assertEqual(row.food_cd, 'ANALYZE1')

    def test_하이픈과_공백을_지우고_찾는다(self):
        from v1.label.services import product_nutrition

        self.assertIsNotNone(product_nutrition.for_report_no('2022046-0436160'))

    def test_숫자가_아닌_번호는_조인_키로_쓰지_않는다(self):
        from v1.label.services import product_nutrition

        self.assertEqual(product_nutrition.normalize('2020_DNSP_04044'), '')
        self.assertIsNone(product_nutrition.for_report_no('2020_DNSP_04044'))

    def test_기준량을_못_읽은_행은_쓰지_않는다(self):
        from v1.label.services import product_nutrition

        PublicFoodNutrition.objects.all().delete()
        PublicFoodNutrition.objects.create(
            food_cd='NOBASIS', food_nm_kr='기준량없음',
            item_report_no='20220460436160', basis_unit='', calories=100,
        )
        self.assertIsNone(product_nutrition.for_report_no('20220460436160'))

    def test_검산에서_어긋난_행은_쓰지_않는다(self):
        from v1.label.services import product_nutrition

        PublicFoodNutrition.objects.all().update(
            verify_status=PublicFoodNutrition.VERIFY_FAIL)
        self.assertIsNone(product_nutrition.for_report_no('20220460436160'))

    def test_음료의_100mL_기준은_빼지_않는다(self):
        from v1.label.services import product_nutrition

        PublicFoodNutrition.objects.all().delete()
        PublicFoodNutrition.objects.create(
            food_cd='DRINK1', food_nm_kr='오렌지주스',
            item_report_no='20220460436160', basis_amount=100, basis_unit='mL',
            calories=45, verify_status=PublicFoodNutrition.VERIFY_PASS,
        )
        row = product_nutrition.for_report_no('20220460436160')
        self.assertIsNotNone(row)
        self.assertEqual(product_nutrition.basis_text(row), '100mL당')

    def test_여러_번호를_한_번에_찾는다(self):
        from v1.label.services import product_nutrition

        found = product_nutrition.for_report_nos(
            ['20220460436160', '99999999999999', '', None])
        self.assertEqual(set(found), {'20220460436160'})

    # ── 조회 ─────────────────────────────────────────────────────────────
    def test_상세에_영양성분_탭이_뜬다(self):
        res = self.client.get(reverse(
            'label:food_item_detail',
            kwargs={'prdlst_report_no': '20220460436160'}))
        self.assertContains(res, 'id="nutrition-tab"')
        self.assertContains(res, 'id="copyNutrition"')

    def test_값이_없으면_탭도_없다(self):
        """눌러 보고 비어 있는 탭은 '고장' 으로 읽힌다."""
        PublicFoodNutrition.objects.all().delete()
        res = self.client.get(reverse(
            'label:food_item_detail',
            kwargs={'prdlst_report_no': '20220460436160'}))
        self.assertNotContains(res, 'id="nutrition-tab"')
        self.assertNotContains(res, 'id="copyNutrition"')

    def test_영양성분_JSON은_번호가_맞는_행만_준다(self):
        url = reverse('label:food_item_nutrition',
                      kwargs={'prdlst_report_no': '20220460436160'})
        body = self.client.get(url).json()
        self.assertTrue(body['found'])
        self.assertEqual(body['origin']['food_cd'], 'ANALYZE1')
        self.assertEqual(body['origin']['basis'], '100g당')

        fields = {r['field']: r for r in body['rows']}
        # 표시값은 규정 반올림을 거친다 — 계산기와 같은 규칙이어야 한다
        self.assertEqual(fields['natriums']['display'], '600')
        self.assertEqual(fields['calories']['display'], '220')   # 열량은 5 단위
        self.assertEqual(fields['natriums']['percent'], 30)      # 기준치 2,000mg

    def test_없는_번호면_found가_거짓이다(self):
        url = reverse('label:food_item_nutrition',
                      kwargs={'prdlst_report_no': '99999999999999'})
        body = self.client.get(url).json()
        self.assertTrue(body['success'])
        self.assertFalse(body['found'])

    def test_빈_칸은_0으로_채우지_않는다(self):
        """모르는 것과 없는 것은 다르다."""
        from v1.label.services import product_nutrition

        PublicFoodNutrition.objects.filter(food_cd='ANALYZE1').update(sugars=None)
        row = product_nutrition.for_report_no('20220460436160')
        got = {r['field'] for r in product_nutrition.panel(row)}
        self.assertNotIn('sugars', got)
        self.assertIn('calories', got)

    # ── 복사 ─────────────────────────────────────────────────────────────
    def _save_label(self, **body):
        url = reverse('label:save_to_my_label',
                      kwargs={'prdlst_report_no': '20220460436160'})
        return self.client.post(url, data=json.dumps(body),
                                content_type='application/json')

    def test_켜면_영양성분도_함께_담긴다(self):
        res = self._save_label(imported_mode=False, copy_nutrition=True)
        self.assertEqual(res.json()['nutrition_copied'], 9)

        label = MyLabel.objects.get(user_id=self.user)
        self.assertEqual(label.calories, '222')
        self.assertEqual(label.natriums, '600')

    def test_근거가_값과_함께_남는다(self):
        """'이 숫자 어디서 왔죠' 에 답하지 못하는 표는 감사에서 설명할 수 없다."""
        self._save_label(imported_mode=False, copy_nutrition=True)
        note = MyLabel.objects.get(user_id=self.user).nutrition_source_note
        self.assertIn('식약처 식품영양성분DB', note)
        self.assertIn('ANALYZE1', note)     # 어느 행을 보았는지
        self.assertIn('100g당', note)        # 어느 기준량인지

    def test_끄면_값이_들어가지_않는다(self):
        res = self._save_label(imported_mode=False, copy_nutrition=False)
        self.assertEqual(res.json()['nutrition_copied'], 0)
        label = MyLabel.objects.get(user_id=self.user)
        self.assertFalse(label.calories)
        self.assertFalse(label.nutrition_source_note)

    def test_기본은_복사하지_않는다(self):
        """플래그가 없으면 옮기지 않는다 — 말없이 남의 값을 넣지 않는다."""
        res = self._save_label(imported_mode=False)
        self.assertEqual(res.json()['nutrition_copied'], 0)

    def test_산출방법_칸은_건드리지_않는다(self):
        """
        nutrition_source 의 값은 'lab'(성적서) / 'theory'(이론치) 둘뿐이다.
        식약처 신고값은 둘 다 아니라, 억지로 고르면 계산기가 허용오차 칸을 연다.
        """
        self._save_label(imported_mode=False, copy_nutrition=True)
        self.assertFalse(MyLabel.objects.get(user_id=self.user).nutrition_source)


class IngredientAutoLinkOrderTests(TestCase):
    """
    원료 쪽 자동 연결도 같은 차례로 고른다.

    `auto_link` 는 `-crt_mth_nm` 으로 SQL 정렬을 걸고 있었다. 한글 코드값
    차례가 분석 < 산출 < 수집 이라 내림차순이면 **가장 못 믿을 '수집' 이
    1 위**가 된다 — `_rank_score` 가 분석에 +8 을 주는 뜻과 정반대다.

    적재본의 97 % 가 '수집' 이라 거의 늘 수집이 뽑혔고, 그래서 이 버그는
    화면에 아무 표도 내지 않았다.
    """

    def setUp(self):
        from v1.label.models import MyIngredient

        self.user = User.objects.create_user(username='autolink', password='x')
        self.ingredient = MyIngredient.objects.create(
            user_id=self.user, prdlst_nm='표고버섯볶음',
            prdlst_report_no='20220460436160', delete_YN='N')

        PublicFoodNutrition.objects.create(
            food_cd='COLLECT1', food_nm_kr='표고버섯볶음',
            item_report_no='20220460436160', crt_mth_nm='수집',
            research_ymd='20250101', basis_amount=100, basis_unit='g',
            calories=111, verify_status=PublicFoodNutrition.VERIFY_SKIP)
        PublicFoodNutrition.objects.create(
            food_cd='ANALYZE1', food_nm_kr='표고버섯볶음',
            item_report_no='20220460436160', crt_mth_nm='분석',
            research_ymd='20190101', basis_amount=100, basis_unit='g',
            calories=222, verify_status=PublicFoodNutrition.VERIFY_PASS)

    def test_분석이_수집을_이긴다(self):
        from v1.label.services import nutrition_candidates as ncd

        self.assertEqual(ncd.auto_link(self.ingredient).food_cd, 'ANALYZE1')

    def test_배합은_여전히_부피_기준을_뺀다(self):
        """
        완제품 표시와 달리 배합 계산은 100 mL 를 쓸 수 없다 — 비중을 모르면
        중량 배합에 넣지 못한다. 차례를 공유하되 거르는 조건은 그대로 둔다.
        """
        from v1.label.services import nutrition_candidates as ncd

        PublicFoodNutrition.objects.all().delete()
        PublicFoodNutrition.objects.create(
            food_cd='DRINK1', food_nm_kr='오렌지주스',
            item_report_no='20220460436160', basis_amount=100, basis_unit='mL',
            calories=45, verify_status=PublicFoodNutrition.VERIFY_PASS)

        self.assertIsNone(ncd.auto_link(self.ingredient))

    def test_확정한_값은_덮지_않는다(self):
        """사람이 고른 것을 자동 판단으로 덮으면 한 일이 조용히 사라진다."""
        from v1.label.models import MyIngredientNutrition
        from v1.label.services import nutrition_candidates as ncd

        MyIngredientNutrition.objects.create(
            ingredient=self.ingredient,
            source_kind=MyIngredientNutrition.SOURCE_MANUAL, calories=999)

        self.assertIsNone(ncd.link_by_report_no(self.ingredient))
        self.assertEqual(
            MyIngredientNutrition.objects.get(ingredient=self.ingredient).calories,
            999)


class ProductNutritionSearchTests(TestCase):
    """제품 조회의 영양성분 조건 — 보유 여부와 수치 범위."""

    def setUp(self):
        self.user = User.objects.create_user(username='nutrisearch', password='x')
        self.client.force_login(self.user)

        def make(no, name, calories, natriums):
            FoodItem.objects.create(
                prdlst_report_no=no, prdlst_nm=name,
                prdlst_dcnm='과자', bssh_nm='시험제과')
            PublicFoodNutrition.objects.create(
                food_cd='CD' + no, food_nm_kr=name, item_report_no=no,
                basis_amount=100, basis_unit='g',
                calories=calories, natriums=natriums,
                verify_status=PublicFoodNutrition.VERIFY_PASS)

        make('10000000000001', '저열량과자', 100, 100)
        make('10000000000002', '중간과자', 300, 400)
        make('10000000000003', '고열량과자', 500, 900)
        # 영양성분이 없는 제품
        FoodItem.objects.create(
            prdlst_report_no='10000000000004', prdlst_nm='값없는과자',
            prdlst_dcnm='과자', bssh_nm='시험제과')

    def _search(self, pairs):
        keys, values = [], []
        for key, value in pairs:
            keys.append(key)
            values.append(value)
        return self.client.get(
            reverse('label:food_item_list'),
            {'food_category': 'domestic', 'f': keys, 'v': values})

    def _names(self, res):
        return {i.prdlst_nm for i in res.context['page_obj']}

    def test_보유_조건이_없는_제품을_거른다(self):
        res = self._search([('bssh_nm', '시험제과'), ('has_nutrition', '있음')])
        self.assertNotIn('값없는과자', self._names(res))
        self.assertEqual(len(self._names(res)), 3)

    def test_열량_구간으로_찾는다(self):
        res = self._search([('bssh_nm', '시험제과'),
                            ('calories_from', '200'), ('calories_to', '400')])
        self.assertEqual(self._names(res), {'중간과자'})

    def test_한쪽만_열린_범위도_된다(self):
        res = self._search([('bssh_nm', '시험제과'), ('natriums_to', '500')])
        self.assertEqual(self._names(res), {'저열량과자', '중간과자'})

    def test_엇갈린_조건은_아무것도_안_나온다(self):
        res = self._search([('bssh_nm', '시험제과'),
                            ('calories_to', '150'), ('natriums_from', '800')])
        self.assertEqual(self._names(res), set())

    def test_같은_번호의_다른_행으로_맞으면_안_된다(self):
        """
        조건마다 따로 하위질의를 만들면 **서로 다른 해의 조사분**으로 맞아도
        통과한다. 어느 행도 두 조건을 함께 만족하지 않는데 결과에 들어온다.
        """
        # 같은 제품에 다른 조사분 — 열량만 높고 나트륨은 낮다
        PublicFoodNutrition.objects.create(
            food_cd='CDEXTRA', food_nm_kr='저열량과자',
            item_report_no='10000000000001', basis_amount=100, basis_unit='g',
            calories=900, natriums=10,
            verify_status=PublicFoodNutrition.VERIFY_PASS)

        # 열량 800 이상 & 나트륨 50 이상 — 두 행에 나눠서는 맞지만 한 행으로는 아니다
        res = self._search([('bssh_nm', '시험제과'),
                            ('calories_from', '800'), ('natriums_from', '50')])
        self.assertEqual(self._names(res), set())

    def test_숫자가_아니거나_음수면_버린다(self):
        from v1.label.services import product_search

        parsed = product_search.parse_conditions(
            'domestic', ['calories_from', 'calories_to'], ['abc', '-5'])
        self.assertEqual(parsed, [])

    def test_영양성분_조건만으로는_검색하지_않는다(self):
        """
        FoodItem 인덱스를 못 타는 조건이라, 이것만 걸면 183만 행 풀스캔이다.
        빠른 조건을 하나 더 요구한다.
        """
        from v1.label.services import product_search

        conds = product_search.parse_conditions(
            'domestic', ['calories_from'], ['200'])
        self.assertTrue(conds)
        self.assertFalse(product_search.search_allowed('domestic', conds))

    def test_목록에_보유_뱃지가_뜬다(self):
        res = self._search([('bssh_nm', '시험제과')])
        self.assertEqual(
            res.context['nutrition_report_nos'],
            {'10000000000001', '10000000000002', '10000000000003'})

    def test_수입_탭에는_영양성분_조건이_없다(self):
        """ImportedFood 에는 품목보고번호가 없다 — 조인할 키 자체가 없다."""
        from v1.label.services import product_search

        keys = {c['key'] for c in product_search.IMPORTED_CONDITIONS}
        self.assertNotIn('has_nutrition', keys)
        self.assertNotIn('calories_from', keys)
        self.assertEqual(
            product_search.parse_conditions('imported', ['calories_from'], ['200']),
            [])

    def test_모르는_칸은_거부한다(self):
        """오타 하나로 조건이 사라지면 결과가 넓어진 줄을 아무도 모른다."""
        from v1.label.services import product_nutrition

        with self.assertRaises(ValueError):
            list(product_nutrition.matching_report_nos([('moisture', 'gte', 1)]))
