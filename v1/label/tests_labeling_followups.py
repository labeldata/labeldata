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
