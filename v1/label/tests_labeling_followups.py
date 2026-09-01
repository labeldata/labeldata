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
