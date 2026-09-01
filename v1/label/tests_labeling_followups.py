"""
표시사항 검증·판독 개선 회귀 시험.

각 시험 클래스의 문서에 무엇이 어떻게 잘못돼 있었는지를 적어 둔다 —
"왜 이 규칙이 여기 있는가" 를 나중에 되짚을 수 있어야 한다.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from v1.label.models import MyLabel

User = get_user_model()


class VinylOtherMarkTests(TestCase):
    """
    포장재질이 "PE" 인 필름 포장에 비닐+OTHER 마크는 맞는 표시다.

    필름은 대부분 여러 수지를 겹쳐 만들고, 재질을 가릴 수 없으면 OTHER 로
    표시하는 것이 분리배출 표시 기준이다. 기타플라스틱은 같은 이유로 이미
    'pe' 를 받고 있었는데 비닐 쪽만 빠져 있어서, 멀쩡한 라벨이 부적합으로
    떴다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='vinylother', password='x')

    def _label(self, material, mark):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='시험',
                                       frmlc_mtrqlt=material)
        label.prv_recycling_mark_type = mark
        return label

    def test_PE_에_비닐_기타는_통과한다(self):
        from v1.label.services.validation_service import check_recycling_mark

        for material in ('PE', 'PE 필름', '폴리에틸렌', 'PET/PE 첩합'):
            self.assertEqual(
                check_recycling_mark(self._label(material, '비닐(기타)')), [],
                material)

    def test_PE_에_비닐_HDPE_LDPE_도_통과한다(self):
        """"PE" 는 고밀도인지 저밀도인지 가려지지 않은 표기다."""
        from v1.label.services.validation_service import check_recycling_mark

        for mark in ('비닐(HDPE)', '비닐(LDPE)'):
            self.assertEqual(check_recycling_mark(self._label('PE', mark)), [], mark)

    def test_PET_전용_용기에_비닐_기타는_여전히_잡는다(self):
        """PET 는 일곱 재질에 있는 표기다. OTHER 로 뭉갤 이유가 없다."""
        from v1.label.services.validation_service import check_recycling_mark

        self.assertTrue(check_recycling_mark(self._label('PET(용기)', '비닐(기타)')))

    def test_종이에_비닐_기타는_잡는다(self):
        from v1.label.services.validation_service import check_recycling_mark

        self.assertTrue(check_recycling_mark(self._label('종이', '비닐(기타)')))


class ImportedReportNoTests(TestCase):
    """
    수입식품에는 품목제조보고번호가 없다.

    체크박스 기본값이 'Y' 라, 수입 제품을 등록하면 곧바로 "품목보고번호가
    비어 있습니다" 가 떴다. 고칠 방법이 없는 지적이라 검증 결과 전체를
    믿지 않게 된다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='imported', password='x')

    def _label(self, **kwargs):
        return MyLabel.objects.create(user_id=self.user, my_label_name='시험',
                                      chckd_prdlst_report_no='Y', **kwargs)

    def _messages(self, label):
        from v1.label.services.validation_service import check_required_fields

        return ' '.join(i['message'] for i in check_required_fields(label))

    def test_수입원을_적었으면_품목보고번호를_묻지_않는다(self):
        label = self._label(importer_address='서울시 ○○구 수입식품㈜')
        self.assertNotIn('품목보고번호', self._messages(label))

    def test_수입원_표시를_켰으면_묻지_않는다(self):
        label = self._label(chckd_importer_address='Y')
        self.assertNotIn('품목보고번호', self._messages(label))

    def test_국내_제조는_그대로_묻는다(self):
        label = self._label(bssh_nm='경기도 ○○시 ○○식품')
        self.assertIn('품목보고번호', self._messages(label))

    def test_is_imported_판정(self):
        from v1.label.services.validation_service import is_imported

        self.assertTrue(is_imported(self._label(importer_address='수입원')))
        self.assertFalse(is_imported(self._label()))


class FarmSeafoodEvidenceTests(TestCase):
    """
    제품명에 쓴 원재료의 함량 검증.

    보는 곳이 셋이다 — 특정성분 함량(의무 표시 자리), 원재료명 및 함량,
    BOM 배합비. 예전에는 첫 번째만 봐서 "원재료명에는 적어 뒀는데 왜 지적하지?"
    와 "둘 다 적었는데 숫자가 다르다" 를 둘 다 놓쳤다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='farmsea', password='x')

    def _label(self, **kwargs):
        return MyLabel.objects.create(user_id=self.user, my_label_name='시험', **kwargs)

    def _issues(self, label):
        from v1.label.services.validation_service import check_farm_seafood_content

        return check_farm_seafood_content(label)

    def test_특정성분_함량에_적었으면_통과한다(self):
        label = self._label(prdlst_nm='토마토 케첩', ingredient_info='토마토 30%')
        self.assertEqual(self._issues(label), [])

    def test_원재료명에만_적혀_있으면_그_값을_짚어_준다(self):
        label = self._label(prdlst_nm='토마토 케첩',
                            rawmtrl_nm_display='토마토(국산) 30%, 설탕, 소금')
        issues = self._issues(label)
        self.assertEqual(len(issues), 1)
        self.assertIn('30', issues[0]['message'])
        self.assertIn('원재료명', issues[0]['message'])

    def test_두_곳의_합이_다르면_지적한다(self):
        label = self._label(prdlst_nm='토마토 케첩',
                            ingredient_info='토마토 30%',
                            rawmtrl_nm_display='토마토(국산) 20%, 설탕')
        issues = self._issues(label)
        self.assertEqual(len(issues), 1)
        self.assertIn('서로 다릅니다', issues[0]['message'])

    def test_원재료명에_나뉘어_적혀_있으면_합으로_본다(self):
        label = self._label(prdlst_nm='토마토 케첩',
                            ingredient_info='토마토 30%',
                            rawmtrl_nm_display='토마토(국산) 20%, 토마토페이스트 10%')
        self.assertEqual(self._issues(label), [])

    def test_괄호_안의_쉼표는_조각을_가르지_않는다(self):
        """"토마토(국산, 30%)" 가 두 조각이 되면 함량이 원료에서 떨어져 나간다."""
        label = self._label(prdlst_nm='토마토 케첩',
                            ingredient_info='토마토(국산, 30%)')
        self.assertEqual(self._issues(label), [])

    def test_지적에는_각_칸의_모양이_함께_실린다(self):
        label = self._label(prdlst_nm='토마토 케첩',
                            rawmtrl_nm_display='토마토(국산) 30%')
        evidence = self._issues(label)[0]['evidence']
        fields = [row['field'] for row in evidence]
        self.assertEqual(fields, ['특정성분 함량', '원재료명 및 함량', 'BOM 배합비'])
        self.assertFalse(evidence[0]['found'])
        self.assertTrue(evidence[1]['found'])
        self.assertEqual(evidence[1]['percent'], '30%')

    def test_검증_화면_행에_근거가_실려_나간다(self):
        from v1.label.services.ai_validation_service import group_issues_by_category
        from v1.label.services.validation_service import validate_label

        label = self._label(prdlst_nm='토마토 케첩',
                            rawmtrl_nm_display='토마토(국산) 30%')
        rows = group_issues_by_category(validate_label(label)['issues'])
        farm = [r for r in rows if r['label'] == '농수산물 함량 표시'][0]
        self.assertTrue(farm['evidence'])
        self.assertTrue(farm['evidence'][0]['rows'])


class OcrRegionRoleTests(TestCase):
    """
    표시면마다 하나씩 잘라 한 번에 읽는다.

    포장 사진에는 주표시면과 일괄표시면이 따로 떨어져 있다. 둘을 다 담으려고
    넓게 고르면 사이의 빈 곳까지 들어와 해상도가 다시 낮아지고, 어느 값이
    어느 면에서 나온 것인지도 알 수 없다.
    """

    def _image(self, width, height):
        import io as _io

        from PIL import Image

        buf = _io.BytesIO()
        Image.new('RGB', (width, height), 'white').save(buf, format='PNG')
        buf.seek(0)
        return buf

    def test_영역이_하나면_예전처럼_전체와_조각을_만든다(self):
        from v1.label.services.ocr_service import build_multi_regions

        regions = build_multi_regions([(self._image(2585, 1755), 'info')])
        self.assertEqual(len(regions), 5, '전체 1장 + 조각 4장')
        self.assertTrue(regions[0]['label'].startswith('일괄표시면'))

    def test_영역이_여럿이면_면마다_한_장씩_들어간다(self):
        from v1.label.services.ocr_service import build_multi_regions

        regions = build_multi_regions([
            (self._image(1000, 800), 'main'),
            (self._image(1000, 800), 'nutrition'),
        ])
        self.assertEqual([r['label'] for r in regions], ['주표시면', '영양성분표'])

    def test_글자가_빽빽한_면만_더_나눈다(self):
        """제품명 몇 줄뿐인 주표시면을 나누면 장수만 늘고 얻는 게 없다."""
        from v1.label.services.ocr_service import build_multi_regions

        regions = build_multi_regions([
            (self._image(2000, 1600), 'main'),
            (self._image(2000, 1600), 'info'),
        ])
        labels = [r['label'] for r in regions]
        self.assertEqual(labels[:2], ['주표시면', '일괄표시면'])
        self.assertTrue(all(l.startswith('일괄표시면') for l in labels[2:]))
        self.assertGreater(len(labels), 2)

    def test_장수는_상한을_넘지_않는다(self):
        from v1.label.services.ocr_service import MAX_REGION_IMAGES, build_multi_regions

        regions = build_multi_regions([
            (self._image(2000, 3000), 'info'),
            (self._image(2000, 3000), 'rawmtrl'),
            (self._image(2000, 3000), 'other'),
        ])
        self.assertLessEqual(len(regions), MAX_REGION_IMAGES)

    def test_지시문이_장마다_찾을_항목을_짚는다(self):
        from v1.label.services.ocr_service import region_instructions

        text = region_instructions([
            {'label': '주표시면', 'role': 'main'},
            {'label': '일괄표시면', 'role': 'info'},
            {'label': '일괄표시면 조각 가로 띠 1/2', 'role': 'info'},
        ])
        self.assertIn('1) 주표시면', text)
        self.assertIn('제품명', text)
        self.assertIn('품목보고번호', text)
        # 조각은 이미 그 면의 일부다 - 같은 항목 목록을 되풀이하지 않는다
        self.assertEqual(text.count('품목보고번호'), 1)

    def test_화면과_서버가_같은_표시면_이름을_쓴다(self):
        """
        화면에서 고른 이름과 모델이 받는 지시가 어긋나면, 사용자가 본 설명과
        실제 판독이 달라진다.
        """
        import re
        from pathlib import Path

        from django.conf import settings as dj

        from v1.label.services.ocr_service import REGION_ROLES

        js = (Path(dj.BASE_DIR) / 'static/js/products/photo_cropper.js'
              ).read_text(encoding='utf-8')
        keys = set(re.findall(r"\{ key: '([a-z]+)'", js))
        self.assertTrue(keys)
        self.assertTrue(keys <= set(REGION_ROLES), keys - set(REGION_ROLES))


class MultiDateFieldTests(TestCase):
    """
    소비기한·제조연월일을 한 칸에 여러 줄로 담는다 (DB 칸은 하나 그대로).

    합치고 가르는 규약은 date_entries.js 한 곳에 있고, 입력 화면과 미리보기가
    그것을 함께 쓴다. 두 벌로 두면 한쪽만 고쳐질 수 있다.
    """

    def _read(self, rel):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / rel).read_text(encoding='utf-8')

    def test_규약이_한_곳에_있다(self):
        js = self._read('static/js/label/date_entries.js')
        self.assertIn('window.DateEntries', js)
        self.assertIn('function serialize', js)
        self.assertIn('제조연월일', js)

    def test_미리보기가_그_규약으로_읽는다(self):
        js = self._read('static/js/label/label_preview.js')
        self.assertIn('window.DateEntries.parse(value, data.date_option)', js)

    def test_입력_화면이_같은_규약을_쓴다(self):
        js = self._read('static/js/products/date_fields.js')
        self.assertIn('window.DateEntries.serialize', js)
        # 저장·사진판독이 이 id 로 값을 읽고 쓴다
        self.assertIn("field-pog-daycnt", js)

    def test_옛_화면의_날짜_칸이_줄바꿈을_잃지_않는다(self):
        """text 입력칸은 브라우저가 줄바꿈을 지운다."""
        html = self._read('templates/label/label_creation.html')
        self.assertIn('<textarea name="pog_daycnt"', html)
