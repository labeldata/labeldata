"""
사진에서 읽은 영양성분표의 **기준**을 다루는 규칙.

저장 칸(MyLabel.calories 등)은 **언제나 100 g(mL) 당**이다. 그런데 라벨에
인쇄된 표는 그 표가 밝힌 기준(총 내용량 / 1회 제공량 / 100 g)으로 적혀
있다. 둘 사이의 환산이 어긋나면 **터지지 않으면서 표만 틀린다.**

실제로 이렇게 났다 (2026-09-17, 총 내용량 90 g · 317 kcal 라벨)

    인쇄:  총 내용량 90 g · 317 kcal
    저장:  317 (환산 안 됨)  +  기준 '총 내용량당'
    표시:  317 x 90/100 = 285 kcal      <- 인쇄와 다르다

까닭은 **기준(kind)과 기준량(amount)이 따로 정해지는데 한쪽만 성공했기**
때문이다. 영양정보 표는 그 둘을 다른 줄에 적는다.

    영양정보      총 내용량 90 g      <- 양은 여기
    총 내용량당   1일 영양성분 …       <- 기준은 여기

판독이 열 머리만 집어 오면 `basis_kind` 는 'total' 을 내고
`parse_nutrition_basis` 는 None 을 낸다. 그러면 환산은 건너뛰면서
`basic_display_type` 만 '총 내용량당' 으로 세워져, 표를 그릴 때 총량/100 이
**한 번 더** 걸린다.
"""

import json

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from v1.label.models import MyLabel


class BasisResolveTests(SimpleTestCase):
    """기준과 기준량을 함께 정하는 규칙 — DB 가 필요 없다."""

    def test_양이_없는_열_머리만_와도_내용량에서_되찾는다(self):
        from v1.label.services.ocr_apply import resolve_basis

        kind, amount, unit = resolve_basis('총 내용량당', content_weight='90 g')
        self.assertEqual(kind, 'total')
        self.assertEqual(amount, '90')
        self.assertEqual(unit, 'g')

    def test_표에_양이_적혀_있으면_그것을_쓴다(self):
        """내용량 칸이 낡았을 수 있다. 표가 말한 양이 언제나 먼저다."""
        from v1.label.services.ocr_apply import resolve_basis

        kind, amount, _ = resolve_basis('총 내용량 87 g', content_weight='500 g')
        self.assertEqual((kind, amount), ('total', '87'))

    def test_1회_제공량은_내용량에서_가져오지_않는다(self):
        """
        90 g 봉지의 1회 제공량이 30 g 일 수 있다. 내용량과 아무 관계가 없는
        값이라, 가져오면 조용히 세 배 틀린다.
        """
        from v1.label.services.ocr_apply import resolve_basis

        kind, amount, _ = resolve_basis('1회 제공량당', content_weight='90 g')
        self.assertEqual(kind, 'unit')
        self.assertIsNone(amount)

    def test_100g당은_양을_몰라도_막지_않는다(self):
        from v1.label.services.ocr_apply import basis_blocks_apply, resolve_basis

        kind, amount, _ = resolve_basis('100 g당')
        self.assertEqual(kind, 'per_100')
        self.assertFalse(basis_blocks_apply(kind, amount))

    def test_기준은_아는데_양을_모를_때만_막는다(self):
        from v1.label.services.ocr_apply import basis_blocks_apply

        self.assertTrue(basis_blocks_apply('total', None))
        self.assertTrue(basis_blocks_apply('unit', None))
        self.assertTrue(basis_blocks_apply('total', '0'))
        self.assertFalse(basis_blocks_apply('total', '90'))

    def test_기준을_아예_못_읽었으면_막지_않는다(self):
        """
        오래된 계약이다 — `nutrition_basis` 없이 부르는 길이 있다. 넓히면
        기준을 한 번도 안 적어 온 사용자의 판독이 통째로 막힌다. 여기서
        잡으려는 것은 **둘이 어긋나는 자리**이지 "모르는 것 전부" 가 아니다.
        """
        from v1.label.services.ocr_apply import basis_blocks_apply

        self.assertFalse(basis_blocks_apply('', None))


class ToPer100RowShapeTests(SimpleTestCase):
    """
    환산 함수가 **화면이 실제로 보내는 모양**을 받는가.

    줄은 두 모양으로 온다.

        {'field': …, 'value': '318', 'unit': 'kcal'}    갈라 놓은 것
        {'field': …, 'raw': '318 kcal'}                 원문 그대로

    화면이 보내는 것은 뒤쪽인데(basic_info_ocr.applyExtras) `to_per_100` 은
    앞쪽만 읽고 있었다. **그래서 사진 판독으로 들어온 값은 한 번도 환산되지
    않았다.** 기존 시험이 전부 앞쪽 모양으로 쓰여 있어 아무도 못 봤다 —
    함수도 맞고 시험도 통과하는데 실제 경로만 비껴간 자리였다.
    """

    def test_원문_줄도_환산한다(self):
        from v1.label.services.ocr_apply import to_per_100

        out = to_per_100([{'field': 'calories', 'raw': '317 kcal'}], '90')
        self.assertAlmostEqual(float(out[0]['value']), 352.22, places=1)
        self.assertEqual(out[0]['unit'], 'kcal')

    def test_갈라_놓은_줄도_그대로_환산한다(self):
        """기존 계약이다. 두 모양을 함께 받아야 한다."""
        from v1.label.services.ocr_apply import to_per_100

        out = to_per_100(
            [{'field': 'calories', 'value': '318', 'unit': 'kcal'}], '87')
        self.assertEqual(out[0]['value'], '365.52')
        self.assertEqual(out[0]['unit'], 'kcal')

    def test_환산한_줄에는_원문을_남기지_않는다(self):
        """
        둘 다 남기면 apply_nutrition 이 무엇을 믿을지 정해야 하고, 그 판단이
        두 곳에 생긴다. 실제로 raw 를 남기면 환산 전 값이 다시 쓰인다.
        """
        from v1.label.services.ocr_apply import to_per_100

        out = to_per_100([{'field': 'natriums', 'raw': '200 mg'}], '90')
        self.assertNotIn('raw', out[0])
        self.assertAlmostEqual(float(out[0]['value']), 222.22, places=1)

    def test_숫자가_아닌_원문은_손대지_않는다(self):
        from v1.label.services.ocr_apply import to_per_100

        rows = [{'field': 'calories', 'raw': '5kcal 미만'}]
        self.assertEqual(to_per_100(rows, '90'), rows)


class StaleCalcValuesTests(TestCase):
    """
    **옛 계산값이 방금 저장한 값을 이겼다.**

    편집기는 저장 칸을 그대로 보여 주지 않는다 — `nutrition_calc_values`
    (오차 물리기 전 계산값)가 있으면 그것으로 표를 채운다. 저장 칸에는
    적용값이 들어 있어서, 다시 열 때마다 사람이 넣은 값이 부푼 값으로
    바뀌지 않게 하려는 설계다.

    그런데 판독은 성분 칸만 쓰고 이 JSON 을 건드리지 않았다.

        DB.calories               352.22   <- 판독이 제대로 썼다
        DB.nutrition_calc_values     317   <- 옛 값이 남아 있다
        화면                         317   <- 이쪽이 이긴다

    **신규 제품은 이 JSON 이 비어 있어 멀쩡했고, 기존 제품에서만 났다.**
    """

    def setUp(self):
        self.user = User.objects.create_user(username='stalecalc', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='과자', content_weight='90 g',
            calories='317', natriums='200',
            nutrition_calc_values='{"calories": "317", "natriums": "200",'
                                  ' "dietary_fiber": "3"}')

    def _apply(self, **body):
        url = reverse('products:ocr_apply_extras',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps(body),
                                content_type='application/json')

    def test_쓴_칸의_옛_계산값을_치운다(self):
        self._apply(nutrition=[{'field': 'calories', 'raw': '317 kcal'}],
                    nutrition_basis='총 내용량당', content_weight='90 g')

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertAlmostEqual(float(label.calories), 352.22, places=1)
        saved = json.loads(label.nutrition_calc_values)
        self.assertNotIn('calories', saved)

    def test_손대지_않은_칸의_계산값은_남긴다(self):
        """식이섬유는 판독이 건드리지 않았다. 그 칸의 계산값은 여전히 맞다."""
        self._apply(nutrition=[{'field': 'calories', 'raw': '317 kcal'}],
                    nutrition_basis='총 내용량당', content_weight='90 g')

        saved = json.loads(
            MyLabel.objects.get(pk=self.label.pk).nutrition_calc_values)
        self.assertEqual(saved['dietary_fiber'], '3')
        self.assertEqual(saved['natriums'], '200')

    def test_전부_치우면_빈_문자열로_둔다(self):
        """'{}' 를 남기면 편집기가 그것을 진짜 계산값으로 읽고 한 겹 더 돈다."""
        self.label.nutrition_calc_values = '{"calories": "317"}'
        self.label.save(update_fields=['nutrition_calc_values'])

        self._apply(nutrition=[{'field': 'calories', 'raw': '317 kcal'}],
                    nutrition_basis='총 내용량당', content_weight='90 g')

        self.assertEqual(
            MyLabel.objects.get(pk=self.label.pk).nutrition_calc_values, '')

    def test_깨진_JSON은_건드리지_않는다(self):
        """화면도 못 읽는 값이다(그쪽도 try/catch 로 넘긴다). 손대면 더 나쁘다."""
        from v1.label.services.ocr_apply import drop_calc_values

        self.label.nutrition_calc_values = '{깨진'
        self.assertEqual(drop_calc_values(self.label, ['calories']), [])
        self.assertEqual(self.label.nutrition_calc_values, '{깨진')


class PrintedValueColumnTests(SimpleTestCase):
    """
    `인쇄될 값` 칸은 **표에 찍히는 그 글자**여야 한다.

    예전에는 적용값(계산값+오차)을 소수 둘째 자리로 자르기만 했다. 그래서 칸
    이름은 "인쇄될 값" 인데 미리보기와 다른 숫자가 떴다.

        입력값 352.22  ->  인쇄될 값 352.22   <- 이 칸
        미리보기                      315     <- 실제로 인쇄되는 값

    표시기준 환산(총내용량당이면 총량/100 배)과 규정 반올림(열량 5 단위)이
    빠져 있었다. 그 둘을 여기서 다시 구현하지 않고 미리보기를 그리는
    함수와 **같은 것**을 부른다.
    """

    def source(self):
        import io
        return io.open('v1/templates/products/nutrition_editor.html',
                       encoding='utf-8').read()

    def block(self):
        html = self.source()
        at = html.index('function refreshApplied()')
        return html[at:at + 3200]

    def test_미리보기와_같은_함수를_쓴다(self):
        block = self.block()
        self.assertIn('window.processNutritionValue', block)
        self.assertIn('normalizeBasicDisplayType', block)

    def test_표시기준별_배수가_미리보기와_같다(self):
        """generateBasicDisplayV3 의 switch 와 같은 값이어야 한다."""
        block = self.block()
        self.assertIn('multiplier = baseAmount / 100', block)
        self.assertIn("case '100g': multiplier = 1;", block)
        self.assertIn('multiplier = (baseAmount * perPackage) / 100', block)

    def test_기준이_바뀌면_다시_그린다(self):
        html = self.source()
        at = html.index('function setBasicDisplayType')
        self.assertIn('refreshApplied', html[at:at + 600])

    def test_단위량이_바뀌면_다시_그린다(self):
        html = self.source()
        at = html.index("['serving_size', 'units_per_package'].forEach")
        self.assertIn('refreshApplied', html[at:at + 700])

    def test_화살표는_오차를_뜻한다(self):
        """
        표시기준 환산은 모든 칸에 똑같이 걸린다. 그것까지 세면 화살표가 늘
        켜져서 "오차가 물렸다" 는 뜻이 사라진다 — 환산 전 값끼리 견준다.
        """
        block = self.block()
        self.assertIn(
            'const moved = Math.abs(value - (base[nutrient.field] || 0)) > 1e-9;',
            block)


class OcrPickWiringTests(SimpleTestCase):
    """
    확인 창에서 **고르는 줄**이 무엇인가.

    영양성분·분리배출도 체크박스가 있는 고르는 줄이다. 기본 정보 탭에 칸이
    없어 서버가 바로 저장할 뿐, 사용자에게는 똑같은 한 줄이다.

    그 셋을 갈라 두었더니 이렇게 났다 — 영양성분표만 찍은 사진에서는
    `[data-field]` 줄이 내용량 하나뿐인데, 그 하나를 체크 해제하면 picked 가
    0 이 되어 적용 단추의 가드에 걸린다. **체크해 둔 영양성분 아홉 줄까지
    통째로 버려졌다.** 화면은 "1개 중 0개 선택" 이라고 적고 있었지만 눈앞에는
    체크된 줄이 아홉이었다.
    """

    def source(self):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
                ).read_text(encoding='utf-8')

    def test_고르는_줄에_영양성분과_분리배출이_들어간다(self):
        js = self.source()
        at = js.index('var PICKABLE')
        block = js[at:at + 400]
        self.assertIn('[data-field]', block)
        self.assertIn('[data-nutri]', block)
        self.assertIn('[data-recycle]', block)

    def test_세는_곳과_고르는_곳이_같은_목록을_쓴다(self):
        """
        하나만 고치면 "전체 선택" 을 눌러도 숫자가 안 움직이는 화면이 된다.
        둘 다 PICKABLE 을 보게 묶어 둔다.
        """
        js = self.source()
        for fn in ('function refreshPickState', 'function applyPickPreset'):
            at = js.index(fn)
            self.assertIn('PICKABLE', js[at:at + 400],
                          '%s 가 PICKABLE 을 쓰지 않는다' % fn)

    def test_영양성분_줄이_현재_값을_받아_채운다(self):
        """
        예전에는 '영양성분 탭' 이라는 글자를 박아 두어, 이미 값이 있는 칸을
        덮어쓰는 줄인지 화면이 말하지 못했다.
        """
        js = self.source()
        self.assertIn('data-nutri-current', js)
        self.assertIn('/products/api/nutrition/', js)
        self.assertNotIn("<span class=\"ocr-empty\">영양성분 탭</span>", js)

    def test_현재_값을_못_받으면_비어_있다고_적지_않는다(self):
        """'비어 있음' 으로 적으면 덮어쓰는 줄을 안 덮어쓰는 줄로 보이게 한다."""
        js = self.source()
        at = js.index('function fillCurrentNutrition')
        self.assertIn('확인 못 함', js[at:at + 2600])


class OcrNutritionBasisApplyTests(TestCase):
    """판독값을 라벨에 넣는 자리 — 환산과 표시기준이 한 몸으로 움직이는가."""

    def setUp(self):
        self.user = User.objects.create_user(username='ocrbasis', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='과자',
            content_weight='90 g')

    def _apply(self, **body):
        url = reverse('products:ocr_apply_extras',
                      kwargs={'label_id': self.label.my_label_id})
        return self.client.post(url, data=json.dumps(body),
                                content_type='application/json')

    # 사용자가 실제로 겪은 그 라벨
    ROWS = [{'field': 'calories', 'raw': '317 kcal'},
            {'field': 'natriums', 'raw': '200 mg'},
            {'field': 'carbohydrates', 'raw': '45 g'}]

    def test_화면이_보낸_내용량이_저장된_값을_이긴다(self):
        """
        판독 화면은 폼만 채우고 저장은 사용자가 누른다. 그래서 서버의
        content_weight 는 **아직 판독 전 값**이다. 저장된 값으로 환산하면
        낡은 총량으로 나누게 된다 — 지금 고치는 버그와 같은 종류다.
        """
        self.label.content_weight = '500 g'      # 낡은 값
        self.label.save(update_fields=['content_weight'])

        self._apply(nutrition=[{'field': 'calories', 'raw': '317 kcal'}],
                    nutrition_basis='총 내용량당',
                    content_weight='90 g')       # 방금 읽은 값

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertAlmostEqual(float(label.calories), 352.22, places=1)

    def test_열_머리만_읽혀도_내용량으로_환산한다(self):
        """
        '총 내용량당' 에는 숫자가 없다. 그래도 내용량 칸에 90 g 이 있으므로
        환산할 수 있다 — 317 x 100/90 = 352.2.
        """
        res = self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량당')
        self.assertTrue(res.json()['success'])
        self.assertFalse(res.json()['nutrition_basis_unknown'])

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertAlmostEqual(float(label.calories), 352.22, places=1)
        self.assertAlmostEqual(float(label.natriums), 222.22, places=1)
        self.assertEqual(label.basic_display_type, 'total')

    def test_환산_못_하면_값을_넣지_않는다(self):
        """
        기준을 모르는 채 넣은 숫자는 터지지 않으면서 뜻만 달라진다.
        성적서 판독이 이미 같은 규칙이다 — 100 으로 가정하지 않는다.
        """
        self.label.content_weight = ''      # 되찾을 곳도 없다
        self.label.save(update_fields=['content_weight'])

        res = self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량당')
        body = res.json()
        self.assertTrue(body['nutrition_basis_unknown'])
        self.assertIn('기준량', body['nutrition_basis_warning'])

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertFalse(label.calories)

    def test_환산_못_하면_표시기준도_세우지_않는다(self):
        """
        **이것이 285 kcal 를 만든 장본인이다.** 값은 인쇄된 그대로 두고
        기준만 '총 내용량당' 이라고 적으면, 표를 그릴 때 총량/100 이 한 번 더
        걸려 인쇄된 표보다 작은 숫자가 나온다.
        """
        self.label.content_weight = ''
        self.label.save(update_fields=['content_weight'])

        self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량당')

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertNotEqual(label.basic_display_type, 'total')

    def test_100g당_표는_그대로_넣는다(self):
        res = self._apply(nutrition=[{'field': 'calories', 'raw': '317 kcal'}],
                          nutrition_basis='100 g당')
        self.assertTrue(res.json()['success'])

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertEqual(float(label.calories), 317)
        self.assertEqual(label.basic_display_type, '100g')
        # "100 g당" 의 100 은 내용량이 아니다 — 단위량에 넣으면 안 된다
        self.assertNotEqual(label.serving_size, '100')

    def test_기준을_몰라도_분리배출은_버리지_않는다(self):
        """
        서로 상관없는 두 가지가 한 요청에 실려 온다. 영양성분 때문에 되돌아가면
        사용자가 확인한 분리배출까지 함께 사라진다.
        """
        self.label.content_weight = ''
        self.label.save(update_fields=['content_weight'])

        res = self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량당',
                          recycling_mark_text='플라스틱')
        body = res.json()
        self.assertTrue(body['nutrition_basis_unknown'])
        self.assertTrue(body['recycling_applied'])

    def test_미리보기는_저장될_값을_돌려주고_쓰지_않는다(self):
        """
        화면이 "이 값이 이렇게 들어갑니다" 를 보이려면 환산된 값이 필요한데,
        그 셈을 JS 로 한 벌 더 만들면 언젠가 서버와 어긋난다. **저장할 때와
        똑같은 코드**를 태우고 결과만 낸다 — 미리 본 값과 저장되는 값이 다를
        수가 없다.
        """
        res = self._apply(preview=True, nutrition=self.ROWS,
                          nutrition_basis='총 내용량당', content_weight='90 g')
        body = res.json()
        self.assertTrue(body['preview'])
        self.assertAlmostEqual(float(body['values']['calories']), 352.22, places=1)
        self.assertEqual(body['units']['calories'], 'kcal')
        self.assertEqual(body['basis_amount'], '90')

        # 아무것도 쓰지 않았다
        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertFalse(label.calories)
        self.assertFalse(label.basic_display_type)

    def test_미리보기가_기준을_모르면_그렇다고_말한다(self):
        """숫자를 비워 두면 '바뀌는 게 없다' 로 읽힌다. 무엇이 막혔는지 적는다."""
        # **저장된 내용량도 비운다.** 화면이 빈 값을 보내도 저장된 값이
        # 있으면 그것으로 받쳐 준다(views 의 `weight_text or label.content_weight`).
        # 그래서 둘 다 비어야 정말 "기준을 모르는" 상태가 된다 — 바로 위
        # 분리배출 시험도 같은 자리를 비우고 시작한다.
        self.label.content_weight = ''
        self.label.save(update_fields=['content_weight'])

        res = self._apply(preview=True, nutrition=self.ROWS,
                          nutrition_basis='총 내용량당', content_weight='')
        body = res.json()
        self.assertTrue(body['nutrition_basis_unknown'])
        self.assertEqual(body['values'], {})

    def test_미리본_값과_저장된_값이_같다(self):
        """둘이 갈리면 미리보기는 거짓말이 된다. 한 코드를 태우는 이유다."""
        preview = self._apply(preview=True, nutrition=self.ROWS,
                              nutrition_basis='총 내용량당',
                              content_weight='90 g').json()['values']

        self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량당',
                    content_weight='90 g')

        label = MyLabel.objects.get(pk=self.label.pk)
        for field, shown in preview.items():
            self.assertEqual(getattr(label, field), shown,
                             '%s 가 미리 본 값과 다르다' % field)

    def test_총_내용량_기준이면_포장개수를_1로_맞춘다(self):
        """
        저장 칸의 총 내용량은 `단위량 x 포장개수` 다. 기준이 총 내용량이면
        단위량이 곧 총량이라, 포장개수가 예전 값으로 남아 있으면 표의 머리와
        인쇄된 내용량이 서로 다른 총량을 말한다.
        """
        self.label.units_per_package = '3'
        self.label.save(update_fields=['units_per_package'])

        self._apply(nutrition=self.ROWS, nutrition_basis='총 내용량 90 g')

        label = MyLabel.objects.get(pk=self.label.pk)
        self.assertEqual(label.units_per_package, '1')
        self.assertEqual(label.serving_size, '90')
