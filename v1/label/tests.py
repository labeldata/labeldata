"""
표시사항(label) 앱 회귀 테스트.

눈으로는 회귀를 잡기 어려운 것들만 고정해 둔다.
  - 수거검사 소급 매칭 트리거(MyLabel post_save): 화면에 아무것도 드러내지 않으면서
    알림 데이터를 지우고 FCM을 발송한다.
  - 식품유형 검색 API: 이름이 겹치는 항목의 판정 순서가 조용히 뒤집힐 수 있다.
  - 표시사항 검증 규칙: 판정이 조용히 느슨해져도 화면은 "적합"으로 보인다.
  - 원재료명 생성 순서: 화면마다 다른 순서가 나와도 각 화면만 보면 멀쩡해 보인다.
  - AI 검증 실패 처리: 확인이 안 된 것이 "적합"처럼 보이면 가장 위험하다.
  - 표시사항 저장 응답: 자동저장이 활동로그를 오염시키거나, 폼 오류가 500이 되어도
    화면에서는 그냥 "저장 실패"로만 보인다.
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from v1.label.models import (
    AgriculturalProduct,
    FoodAdditive,
    FoodItem,
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
    """검사가 실제로 '규정만 검증' 경로에 물려 있는지."""

    def test_새_검사가_무료_검증에_포함된다(self):
        from v1.label.services.validation_service import _CHECKS, validate_label

        names = {c.__name__ for c in _CHECKS}
        self.assertIn('check_additive_display_name', names)
        self.assertIn('check_required_fields', names)

        user = User.objects.create_user(username='wiring', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='빈 라벨')
        result = validate_label(label)
        # 근거 규정 목록에도 새 항목이 드러나야 한다 (검증 범위를 사용자에게 보여주는 값)
        joined = ' '.join(result['checked_regulations'])
        self.assertIn('식품첨가물의 표시 방법', joined)


class RequiredFieldTests(TestCase):
    """
    필수 입력 항목 공란 검사(validation_service.check_required_fields).

    나머지 검사는 전부 "값이 있을 때만" 본다 — 내용량이 비면 지적이 없고,
    원재료명이 비면 알레르기·원산지 검사가 통째로 건너뛰어진다. 그래서
    아무것도 입력하지 않은 라벨이 지적 0건, 즉 "모두 표시 규정에 적합"으로
    판정됐다. 화면에는 초록색 "적합" 배지만 뜨므로 눈으로는 절대 안 잡힌다.
    """

    # 모델 기본값이 'Y' 인 체크박스들 — 새 라벨은 이 항목들을 표시하기로 시작한다
    DEFAULT_ON = [
        'prdlst_dcnm', 'prdlst_nm', 'content_weight', 'prdlst_report_no',
        'frmlc_mtrqlt', 'bssh_nm', 'pog_daycnt', 'rawmtrl_nm_display', 'cautions',
    ]

    def setUp(self):
        self.user = User.objects.create_user(username='required', password='x')

    def _issues(self, label):
        from v1.label.services.validation_service import check_required_fields
        return check_required_fields(label)

    def test_빈_라벨은_적합이_아니다(self):
        from v1.label.services.validation_service import validate_label

        label = MyLabel.objects.create(user_id=self.user, my_label_name='빈 라벨')
        result = validate_label(label)
        self.assertFalse(result['ok'], '아무것도 입력하지 않은 라벨이 적합으로 나오면 안 된다')

        categories = {i['category'] for i in result['issues']}
        self.assertEqual(categories, {'required_missing'},
                         '빈 라벨에서 나올 수 있는 지적은 필수 미입력뿐이다')
        # 항목마다 따로 내면 같은 문장이 근거 규정까지 통째로 되풀이된다.
        # 한 건에 모으고 항목 목록을 따로 실어 보낸다.
        self.assertEqual(len(result['issues']), 1, '한 문장으로 모아야 한다')
        self.assertEqual(len(result['issues'][0]['field_labels']), len(self.DEFAULT_ON))

    def test_미입력_항목이_한글_이름으로_나온다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='빈 라벨')
        joined = ' '.join(i['message'] for i in self._issues(label))
        for name in ('제품명', '내용량', '소비기한', '원재료명(표시)', '제조원 소재지'):
            self.assertIn(name, joined)

    def test_체크가_꺼진_항목은_비어도_통과한다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        for field in self.DEFAULT_ON:
            setattr(label, 'chckd_' + field, 'N')
        label.save()
        self.assertEqual(self._issues(label), [])

    def test_값을_채우면_지적이_사라진다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        for field in self.DEFAULT_ON:
            setattr(label, field, '값')
        label.save()
        self.assertEqual(self._issues(label), [])

    def test_켜져_있는데_공백만_있으면_비어_있는_것으로_본다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        for field in self.DEFAULT_ON:
            setattr(label, field, '값')
        label.content_weight = '   '
        label.save()
        msgs = [i['message'] for i in self._issues(label)]
        self.assertEqual(len(msgs), 1)
        self.assertIn('내용량', msgs[0])

    def test_기본이_꺼진_항목도_켜면_검사한다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        for field in self.DEFAULT_ON:
            setattr(label, field, '값')
        label.chckd_storage_method = 'Y'   # 기본값 'N'
        label.save()
        msgs = [i['message'] for i in self._issues(label)]
        self.assertEqual(len(msgs), 1)
        self.assertIn('보관방법', msgs[0])


class RequiredFieldAiGateTests(TestCase):
    """
    필수 미입력 라벨에서 AI검증이 무엇을 하는가.

    AI 검사 셋은 전부 제품명 아니면 원재료명을 본다. 둘 다 비면 셋 다
    확인할 게 없는데도 예전에는 일일 한도가 1회 깎였다. 게다가 필수 입력
    검사가 붙으면 지적거리가 생겨 요약용 OpenAI 호출이 새로 발생한다.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='aigate', password='x')

    def test_제품명과_원재료명이_비면_OpenAI를_부르지_않고_한도도_안_깎는다(self):
        from v1.label.services import ai_validation_service as avs
        from v1.label.services.ai_rate_limit import get_usage

        label = MyLabel.objects.create(user_id=self.user, my_label_name='빈 라벨')
        before = get_usage(self.user)['daily_used']

        with patch.object(avs, 'call_openai') as mock_call:
            result = avs.run_full_review(label, self.user)

        self.assertEqual(mock_call.call_count, 0, 'OpenAI 를 부를 이유가 없다')
        self.assertEqual(get_usage(self.user)['daily_used'], before, '한도를 깎으면 안 된다')
        self.assertFalse(result['ok'])
        self.assertFalse(result['blocked'])

    def test_필수_미입력_행은_표에서_지워지지_않는다(self):
        """
        AI 가 확인 못 한 항목은 "적합"으로 오인되지 않게 표에서 지운다.
        필수 미입력은 그 처리에 휩쓸리면 안 된다 — 지워지면 남은 행이 전부
        ok 라서 전체 판정이 다시 "적합"이 된다.
        """
        from v1.label.services import ai_validation_service as avs

        label = MyLabel.objects.create(user_id=self.user, my_label_name='빈 라벨')
        with patch.object(avs, 'call_openai'):
            result = avs.run_full_review(label, self.user)

        labels = [c['label'] for c in result['categories']]
        self.assertIn('필수 입력 항목', labels)
        self.assertFalse(next(c for c in result['categories'] if c['label'] == '필수 입력 항목')['ok'])

    def test_체크박스만_바뀌어도_결과_캐시가_갈린다(self):
        """
        지문에 chckd_* 가 없으면 소비기한을 채워도 15분간 "미입력" 결과가
        그대로 나온다.
        """
        from v1.label.services.ai_rate_limit import _result_cache_key

        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        before = _result_cache_key(label)

        label.chckd_pog_daycnt = 'N'
        self.assertNotEqual(_result_cache_key(label), before)

        label.chckd_pog_daycnt = 'Y'
        label.pog_daycnt = '제조일로부터 12개월'
        self.assertNotEqual(_result_cache_key(label), before)


class LabelSavePostTests(TestCase):
    """
    표시사항 저장(POST /label/label-creation/<id>/) 응답.

    자동저장을 붙이면서 두 가지가 걸렸다.
      - 자동저장(30초 주기)까지 활동로그에 남기면 편집 세션 하나가 로그를 수십 줄
        차지해 "사용자가 언제 저장했는가"를 읽을 수 없게 된다.
      - 폼이 무효일 때 뷰가 아무것도 반환하지 않아 500이 났다. 마지막 render 가
        GET 분기 안에 있어서 POST-무효 경로는 return 없이 함수가 끝난다.
        라벨명이 유일한 필수 필드라 이름을 비우고 저장하면 재현된다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='saver', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='저장 테스트')
        self.url = '/label/label-creation/%s/' % self.label.my_label_id

    def _post(self, **extra):
        body = {'my_label_name': '저장 테스트'}
        body.update(extra)
        return self.client.post(self.url, data=body,
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _log_count(self):
        from v1.activity_log.models import UserActivityLog
        return UserActivityLog.objects.filter(user=self.user, action='label_update').count()

    def test_수동저장은_활동로그를_남긴다(self):
        before = self._log_count()
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self._log_count(), before + 1)

    def test_자동저장은_활동로그를_남기지_않는다(self):
        before = self._log_count()
        resp = self._post(autosave='1')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['autosave'])
        self.assertEqual(self._log_count(), before, '자동저장이 활동로그를 남기면 안 된다')

    def test_자동저장도_내용은_저장한다(self):
        self._post(autosave='1', my_label_name='자동저장으로 바뀐 이름')
        self.label.refresh_from_db()
        self.assertEqual(self.label.my_label_name, '자동저장으로 바뀐 이름')

    def test_폼이_무효면_500이_아니라_400_JSON_을_준다(self):
        """라벨명을 비우면 예전에는 뷰가 None 을 반환해 500 이 났다."""
        resp = self._post(my_label_name='')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('my_label_name', data['errors'])

    def test_폼이_무효면_저장되지_않는다(self):
        self._post(my_label_name='')
        self.label.refresh_from_db()
        self.assertEqual(self.label.my_label_name, '저장 테스트')


class RawmtrlNmOrderTests(TestCase):
    """
    라벨 편집 화면이 만드는 원재료명(rawmtrl_nm)의 순서.

    원재료는 함량이 많은 순서로 표시해야 한다(「식품등의 표시기준」).
    표시 문구를 만드는 곳이 두 군데인데 규칙이 서로 달랐다.
      - BOM 에디터 요약(products/bom_detail.html generateBomSummary): 배합비 내림차순
      - 라벨 편집 화면 rawmtrl_nm(label/views.py): 입력 순서 그대로
    같은 데이터인데 어느 화면에서 보느냐에 따라 원재료 순서가 달라졌다.
    두 곳이 같은 규칙을 쓰도록 맞췄고, 여기서 그걸 고정한다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='order', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='순서 테스트')

    def _link(self, food_type, ratio, sequence):
        """배합비 5% 이상이면 생성기가 '식품유형[표시명]' 으로 찍는다."""
        ing = MyIngredient.objects.create(
            user_id=self.user,
            prdlst_nm=food_type,
            prdlst_dcnm=food_type,
            ingredient_display_name=food_type,
            food_category='processed',
            delete_YN='N',
        )
        LabelIngredientRelation.objects.create(
            label=self.label, ingredient=ing,
            relation_sequence=sequence, ingredient_ratio=ratio,
        )

    def _generated_text(self):
        resp = self.client.get('/label/label-creation/%s/' % self.label.my_label_id)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def _positions(self, html, *names):
        return [html.index(n) for n in names]

    def test_입력_순서가_거꾸로여도_배합비_많은_순으로_찍는다(self):
        self._link('가루류', 10, 1)   # 입력은 1번인데 함량은 적다
        self._link('당류', 50, 2)
        self._link('유지류', 30, 3)

        html = self._generated_text()
        pos_50, pos_30, pos_10 = self._positions(html, '당류', '유지류', '가루류')
        self.assertLess(pos_50, pos_30)
        self.assertLess(pos_30, pos_10)

    def test_배합비가_없는_행은_뒤로_보낸다(self):
        """BOM 에디터도 빈 값을 0 으로 보고 뒤로 보낸다 — 같은 규칙."""
        self._link('향료류', None, 1)
        self._link('당류', 20, 2)

        html = self._generated_text()
        self.assertLess(html.index('당류'), html.index('향료류'))

    def test_배합비가_같으면_입력_순서를_지킨다(self):
        """안정 정렬이라 같은 값끼리는 사용자가 넣은 순서가 유지돼야 한다."""
        self._link('가루류', 20, 1)
        self._link('당류', 20, 2)

        html = self._generated_text()
        self.assertLess(html.index('가루류'), html.index('당류'))


class AiValidationFailureTests(TestCase):
    """
    AI 검증이 실패했을 때의 처리.

    원래는 OpenAI 호출에 타임아웃이 없었다. 클라이언트 기본값이 read 600초 ×
    재시도 2회라 호출 하나가 최대 30분을 붙잡을 수 있었고, 그 4개를 순차로
    돌렸다. PythonAnywhere 는 웹 요청을 300초에 끊으므로 워커가 죽고 500 이
    났다. 게다가 실패해도 화면은 "함량(%)이 명시돼 있지 않아서" 라고만 안내해서
    사용자는 자기 입력 탓인 줄 알았다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='aiuser', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.user,
            my_label_name='AI 검증 테스트',
            prdlst_nm='딸기 우유',
            rawmtrl_nm_display='정제수, 딸기과즙 30%, 설탕 10%',
        )

    def _clear_cache(self):
        from django.core.cache import cache
        from v1.label.services.ai_rate_limit import _result_cache_key
        cache.clear()
        cache.delete(_result_cache_key(self.label))

    # ── 클라이언트 설정 ─────────────────────────────────────────────────────

    def test_클라이언트에_타임아웃과_재시도_상한이_걸려_있다(self):
        """
        빠뜨리면 openai 기본값(read 600초 × 재시도 2회)이 적용돼
        호출 하나가 30분까지 늘어난다.
        """
        import openai

        from v1.label.services import ai_validation_service as avs

        captured = {}

        class _Capture:
            def __init__(self, **kw):
                captured.update(kw)

        with patch.object(openai, 'OpenAI', _Capture):
            client, reason = avs.get_openai_client()

        self.assertEqual(reason, avs.REASON_OK)
        self.assertIsNotNone(captured.get('timeout'), '타임아웃이 지정돼야 한다')
        self.assertLessEqual(captured['timeout'], 60)
        self.assertLessEqual(captured['max_retries'], 1)

    def test_키가_없으면_사유를_돌려준다(self):
        from django.test import override_settings

        from v1.label.services import ai_validation_service as avs

        with override_settings(OPENAI_API_KEY=''):
            client, reason = avs.get_openai_client()
        self.assertIsNone(client)
        self.assertEqual(reason, avs.REASON_NOT_CONFIGURED)

    # ── 실패 사유 전달 ──────────────────────────────────────────────────────

    def _run_with_failure(self, exc):
        from v1.label.services import ai_validation_service as avs

        self._clear_cache()
        with patch.object(avs, 'call_openai', side_effect=None) as mock_call:
            mock_call.side_effect = lambda *a, **kw: (None, avs.REASON_TIMEOUT
                                                      if isinstance(exc, TimeoutError)
                                                      else avs.REASON_API_ERROR)
            return avs.run_full_review(self.label, self.user)

    def test_타임아웃이면_그렇게_알린다(self):
        result = self._run_with_failure(TimeoutError())
        reasons = {u['reason'] for u in result['unchecked']}
        self.assertEqual(reasons, {'timeout'})
        for u in result['unchecked']:
            self.assertTrue(u['system_failure'])
            self.assertIn('늦어', u['message'])

    def test_호출_실패면_함량_탓으로_돌리지_않는다(self):
        """예전에는 원인과 무관하게 "함량(%)이 명시돼 있지 않아서" 라고 안내했다."""
        result = self._run_with_failure(RuntimeError())
        for u in result['unchecked']:
            self.assertEqual(u['reason'], 'api_error')
            self.assertNotIn('함량', u['message'])

    def test_실패해도_규칙_기반_검증_결과는_남는다(self):
        result = self._run_with_failure(RuntimeError())
        self.assertTrue(result['categories'], 'AI 가 죽어도 규칙 기반 항목은 보여야 한다')
        self.assertFalse(result['ingredient_order_checked'])
        self.assertFalse(result['allergen_ai_checked'])
        self.assertFalse(result['name_ingredient_checked'])

    def test_모두_성공하면_미검증_목록이_비어_있다(self):
        from v1.label.services import ai_validation_service as avs

        self._clear_cache()

        def _fake(tag, prompt, max_tokens, temperature=0.0, json_mode=True):
            if not json_mode:
                return '요약', avs.REASON_OK
            return {'items': [{'name': '딸기과즙', 'percent': 30.0},
                              {'name': '설탕', 'percent': 10.0}],
                    'allergens': [], 'ingredients': []}, avs.REASON_OK

        with patch.object(avs, 'call_openai', _fake):
            result = avs.run_full_review(self.label, self.user)

        self.assertEqual(result['unchecked'], [])
        self.assertTrue(result['ingredient_order_checked'])

    # ── 뷰가 500 을 내지 않는다 ─────────────────────────────────────────────

    def test_run_full_review_가_터져도_뷰는_500이_아니다(self):
        self.client.force_login(self.user)
        self._clear_cache()
        with patch('v1.label.views.run_full_review', side_effect=RuntimeError('폭발')):
            resp = self.client.post('/label/%s/validate/ai-review/' % self.label.my_label_id)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['categories'], '규칙 기반 결과는 살아 있어야 한다')
        self.assertTrue(data['unchecked'][0]['system_failure'])


class FoodTypeSettingsTests(TestCase):
    """
    식품유형 -> 표시 항목 규칙(services/food_type_settings.py).

    FoodType 293행의 Y/D/N 은 준비돼 있었지만 이 판단을 하는 코드가 없어서,
    식품유형을 무엇으로 고르든 새 라벨은 모델 기본값 9개로만 시작했다.
    필수 입력 검사가 chckd_* 를 근거로 삼으면서 그게 곧 "무엇이 필수인가" 가 됐다.
    """

    def setUp(self):
        FoodType.objects.create(
            food_group='과자류', food_type='과자',
            prdlst_dcnm='Y', weight_calorie='Y', prdlst_report_no='Y',
            country_of_origin='Y', frmlc_mtrqlt='Y', rawmtrl_nm='Y',
            storage_method='N', nutritions='Y', cautions='N',
            pog_daycnt='소비기한, 품질유지기한',
            relevant_regulations='과자류 관련 규정',
        )

    def _settings(self, food_group='', food_type=''):
        from v1.label.services.food_type_settings import resolve_settings
        return resolve_settings(food_group, food_type)

    def test_가공식품은_FoodType_의_YDN_을_그대로_읽는다(self):
        r = self._settings(food_type='과자')
        self.assertTrue(r['found'])
        self.assertEqual(r['settings']['nutritions'], 'Y')
        self.assertEqual(r['settings']['storage_method'], 'N')
        self.assertEqual(r['settings']['cautions'], 'N')
        self.assertEqual(r['relevant_regulations'], '과자류 관련 규정')

    def test_FoodType_에_컬럼이_없는_항목은_고정값으로_채운다(self):
        """제품명·내용량은 유형별로 갈리지 않는데 테이블에 컬럼이 없다."""
        s = self._settings(food_type='과자')['settings']
        self.assertEqual(s['prdlst_nm'], 'Y')
        self.assertEqual(s['content_weight'], 'Y')

    def test_소비기한은_YDN_이_아니라_텍스트라_갈라서_준다(self):
        r = self._settings(food_type='과자')
        self.assertEqual(r['settings']['pog_daycnt'], 'Y')
        self.assertEqual(r['pog_daycnt_options'], ['소비기한', '품질유지기한'])

    def test_모르는_식품유형은_found_False(self):
        self.assertFalse(self._settings(food_type='없는유형')['found'])

    def test_식품첨가물과_농수축산물은_하드코딩_규칙을_쓴다(self):
        self.assertEqual(self._settings('식품첨가물', '')['settings']['nutritions'], 'D')
        beef = self._settings('농수축산물', '축산물')
        self.assertEqual(beef['settings']['prdlst_report_no'], 'D')
        self.assertIn('이력관리번호', [c['label'] for c in beef['custom_fields']])

    def test_모든_규칙_키가_체크박스로_이어진다(self):
        """키 하나가 어긋나면 그 항목만 조용히 반영되지 않는다."""
        from v1.label.services.food_type_settings import FIELD_TO_CHECKBOX
        for group, ftype in [('', '과자'), ('식품첨가물', ''), ('농수축산물', '축산물')]:
            for field in self._settings(group, ftype)['settings']:
                self.assertIn(field, FIELD_TO_CHECKBOX, f'{field} 매핑 없음')
                self.assertTrue(hasattr(MyLabel(), FIELD_TO_CHECKBOX[field]))


class ApplyFoodTypeSettingsTests(TestCase):
    """
    규칙을 라벨에 반영할 때의 보수적인 규칙.

    규칙을 그대로 덮어쓰면 사용자가 켜 둔 항목이 조용히 꺼지고 인쇄물에서 줄이
    사라진다. FoodType.cautions 는 293행 중 288행이 'N' 이라, 그대로 적용하면
    주의사항이 거의 모든 라벨에서 빠진다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='apply', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')

    def _apply(self, settings):
        from v1.label.services.food_type_settings import apply_to_label
        return apply_to_label(self.label, settings)

    def test_Y는_켠다(self):
        self.label.chckd_nutrition_text = 'N'
        result = self._apply({'nutritions': 'Y'})
        self.assertEqual(self.label.chckd_nutrition_text, 'Y')
        self.assertEqual(result['turned_on'], ['chckd_nutrition_text'])

    def test_N은_건드리지_않는다(self):
        """사용자 재량 항목이다. 껐다고 단정하면 주의사항이 사라진다."""
        self.label.chckd_cautions = 'Y'
        self._apply({'cautions': 'N'})
        self.assertEqual(self.label.chckd_cautions, 'Y')

    def test_D는_값이_비어_있을_때만_끈다(self):
        self.label.chckd_prdlst_report_no = 'Y'
        self.label.prdlst_report_no = ''
        result = self._apply({'prdlst_report_no': 'D'})
        self.assertEqual(self.label.chckd_prdlst_report_no, 'N')
        self.assertEqual(result['turned_off'], ['chckd_prdlst_report_no'])

    def test_D라도_값이_있으면_끄지_않고_보고한다(self):
        """끄면 인쇄물에서 그 줄이 사라진다. 사람이 보고 정할 일이다."""
        self.label.chckd_prdlst_report_no = 'Y'
        self.label.prdlst_report_no = '19950000000000'
        result = self._apply({'prdlst_report_no': 'D'})
        self.assertEqual(self.label.chckd_prdlst_report_no, 'Y')
        self.assertEqual(result['kept_filled'], ['chckd_prdlst_report_no'])
        self.assertEqual(result['turned_off'], [])


class FoodTypeSettingsApiTests(TestCase):
    """
    label_creation.js 가 예전부터 부르던 두 URL. 없어서 404 가 났고
    .catch(console.error) 로 삼켜져 아무 일도 일어나지 않았다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='api', password='x')
        self.client.force_login(self.user)
        FoodType.objects.create(
            food_group='빵류', food_type='빵류',
            prdlst_dcnm='Y', nutritions='Y', pog_daycnt='소비기한',
        )

    def test_식품유형_설정을_돌려준다(self):
        resp = self.client.get('/label/food-type-settings/?food_type=빵류')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['settings']['nutritions'], 'Y')
        self.assertEqual(data['settings']['pog_daycnt_options'], ['소비기한'])

    def test_모르는_식품유형은_success_False(self):
        data = self.client.get('/label/food-type-settings/?food_type=없음').json()
        self.assertFalse(data['success'])

    def test_소분류로_대분류를_되짚는다(self):
        data = self.client.get('/label/get-food-group/?food_type=빵류').json()
        self.assertEqual(data['food_group'], '빵류')

    def test_JS_가_찾는_체크박스_id_가_템플릿에_있다(self):
        """
        fieldMappings 가 없는 id 를 가리키면 그 항목만 조용히 안 켜진다.
        실제로 nutritions -> chk_calories 였는데 그런 id 는 존재한 적이 없다.
        """
        import re
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        js = (base / 'static/js/label/label_creation.js').read_text(encoding='utf-8')
        html = (base / 'templates/label/label_creation.html').read_text(encoding='utf-8')

        block = js[js.index('const fieldMappings = {'):]
        block = block[:block.index('\n};')]
        ids = set(re.findall(r'id="(chk_[a-z_]+)"', html))
        for key, target in re.findall(r"^\s*(\w+):\s*'(chk_[a-z_]+)'", block, re.M):
            self.assertIn(target, ids, f'fieldMappings.{key} 가 없는 id {target} 를 가리킨다')


class RequiredFieldAlternativeSourceTests(TestCase):
    """
    다른 탭이 채우는 자리를 인정한다.

    필수 입력 검사를 붙일 때 "그 필드가 비었으면 미입력" 으로만 봤는데, 제품
    관리(V2)는 항목마다 저장하는 필드가 다르다. 그대로 두면 실제로는 인쇄물에
    나오는데 "미입력" 이라고 지적하는 오탐이 난다. 로컬 활성 라벨에서만
    원재료명 1건, 영양성분 4건이 이 경우였다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='altsrc', password='x')

    def _messages(self, **kwargs):
        from v1.label.services.validation_service import check_required_fields
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨', **kwargs)
        return ' '.join(i['message'] for i in check_required_fields(label))

    def test_원재료명은_참고_필드가_차있으면_통과한다(self):
        """
        V2 기본정보 탭과 BOM "기본정보로 복사" 는 rawmtrl_nm 에 쓴다. 표시사항
        탭이 rawmtrl_nm_display 가 비면 그 값으로 폴백해 미리보기에 넣는다.
        """
        self.assertIn('원재료명(표시)', self._messages())
        self.assertNotIn('원재료명(표시)',
                         self._messages(rawmtrl_nm='밀가루(밀:미국산), 설탕'))

    def test_영양성분은_개별_항목이_있으면_통과한다(self):
        """
        영양성분은 미리보기에서 별도 표로 그려지고 nutrition_text 는
        ORDERED_FIELDS 에서 빠져 있다. V2 영양성분 탭은 개별 항목만 저장한다.
        """
        self.assertIn('영양성분 표시', self._messages(chckd_nutrition_text='Y'))
        self.assertNotIn('영양성분 표시',
                         self._messages(chckd_nutrition_text='Y', calories='120'))

    def test_대체_자리도_비면_여전히_지적한다(self):
        msgs = self._messages(chckd_nutrition_text='Y')
        self.assertIn('영양성분 표시', msgs)
        self.assertIn('원재료명(표시)', msgs)

    def test_대체_자리가_캐시_지문에_반영된다(self):
        """빠뜨리면 열량을 채우고 다시 검증해도 15분간 "미입력" 이 그대로 나온다."""
        from v1.label.services.ai_rate_limit import _result_cache_key

        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        before = _result_cache_key(label)
        label.calories = '120'
        self.assertNotEqual(_result_cache_key(label), before)


class WeightCalorieCheckTests(TestCase):
    """
    내용량(열량)은 별도 줄이 아니라 내용량에 함께 적는다 — "250 g (100 kcal)".

    공백 여부로만 보면 두 방향으로 틀린다. 내용량에 병기했는데 전용 칸이 비었다고
    지적하거나, 전용 칸에 숫자만 있고 kcal 이 없는데 통과시킨다.

    라벨은 **영양표시를 하는 제품일 때만** 만든다(calories 를 넣는다). 열량 병기는
    영양성분 표시 대상 식품의 의무라서, 영양표시가 없는 제품에는 이 검사가 아예
    돌지 않는다 — 그쪽은 WeightCalorieScopeTests 가 본다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='kcal', password='x')

    def _messages(self, **kwargs):
        from v1.label.services.validation_service import check_required_fields
        kwargs.setdefault('calories', '120')
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            chckd_weight_calorie='Y', **kwargs)
        return ' '.join(i['message'] for i in check_required_fields(label))

    def test_내용량에_병기하면_통과한다(self):
        self.assertNotIn('내용량(열량)', self._messages(content_weight='250 g (100 kcal)'))

    def test_전용_칸에_적어도_통과한다(self):
        self.assertNotIn('내용량(열량)', self._messages(weight_calorie='100 kcal'))

    def test_열량_표기가_없으면_지적한다(self):
        self.assertIn('내용량(열량)', self._messages(content_weight='250 g'))

    def test_숫자만_있고_단위가_없으면_지적한다(self):
        """전용 칸이 비지 않았다는 이유만으로 통과시키면 안 된다."""
        self.assertIn('내용량(열량)', self._messages(weight_calorie='100'))

    def test_표기_흔들림을_받아준다(self):
        for text in ('250g(100kcal)', '250 g (100 Kcal)', '내용량 250g, 100 KCAL'):
            self.assertNotIn('내용량(열량)', self._messages(content_weight=text), text)

    def test_어떻게_적으라는지_알려준다(self):
        from v1.label.services.validation_service import check_required_fields
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨',
                                       chckd_weight_calorie='Y', calories='120',
                                       content_weight='250 g')
        issues = check_required_fields(label)
        self.assertIn('weight_calorie', issues[0]['fields'])
        self.assertIn('kcal', issues[0]['suggestion'])

    def test_적을_값을_계산해서_보여준다(self):
        """
        100g 당 값을 총량에 적용하는 계산을 사용자가 다시 하게 두지 않는다.
        120 kcal x 250 g / 100 = 300 kcal.
        """
        from v1.label.services.validation_service import check_required_fields
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨',
                                       chckd_weight_calorie='Y', calories='120',
                                       content_weight='250 g')
        suggestion = check_required_fields(label)[0]['suggestion']
        self.assertIn('250 g (300 kcal)', suggestion)

    def test_조합_문자로_적은_열량도_읽는다(self):
        """
        라벨 인쇄물과 사진 판독값에는 ㎉·㎖ 같은 조합 문자가 그대로 들어온다.
        ASCII 만 보면 실제로는 병기된 라벨을 "안 적었다" 고 지적하게 된다.
        """
        for text in ('250g(300㎉)', '250㎖ (300 ㎉)', '250 g / 300킬로칼로리'):
            self.assertNotIn('내용량(열량)', self._messages(content_weight=text), text)


class WeightCalorieScopeTests(TestCase):
    """
    열량 병기는 **영양성분 표시 대상 식품**의 의무다. 모든 제품의 의무가 아니다.

    내용량(열량)은 어느 화면에도 입력칸이 없고(내용량에 함께 적는 값이라 뺐다)
    표시 항목 목록에도 없어서 끌 수도 없다. 영양표시가 없는 제품에까지 지적하면
    **고칠 방법이 없는 경고**가 된다 — 운영에서 "숨겼는데도 계속 나온다" 는
    신고가 여기서 나왔다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='kcalscope', password='x')

    def _messages(self, **kwargs):
        from v1.label.services.validation_service import check_required_fields
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            chckd_weight_calorie='Y', content_weight='250 g', **kwargs)
        return ' '.join(i['message'] for i in check_required_fields(label))

    def test_영양표시가_없으면_지적하지_않는다(self):
        self.assertNotIn('내용량(열량)', self._messages())

    def test_영양성분_값이_있으면_지적한다(self):
        self.assertIn('내용량(열량)', self._messages(calories='120'))

    def test_영양성분_표시_체크만_켜도_지적한다(self):
        self.assertIn('내용량(열량)', self._messages(chckd_nutrition_text='Y'))

    def test_내용량에_적은_열량이_캐시_지문에_반영된다(self):
        from v1.label.services.ai_rate_limit import _result_cache_key

        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨',
                                       content_weight='250 g')
        before = _result_cache_key(label)
        label.content_weight = '250 g (100 kcal)'
        self.assertNotEqual(_result_cache_key(label), before)


class CalorieConsistencyTests(TestCase):
    """
    내용량에 병기한 열량과 영양성분 탭 계산값의 정합성.

    영양성분 탭이 저장하는 calories 는 100g(ml) 당 값이다
    (nutrition_calculator_popup.js 의 generateBasicDisplayV3 이 표시할 때
    multiplier = 총량/100 을 곱한다). 실제 라벨로 확인했다 —
    "800 g (1240 kcal)" 인 라벨의 calories 가 155 이고 155 x 800/100 = 1240.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='cal', password='x')

    def _issues(self, **kwargs):
        from v1.label.services.validation_service import check_calorie_consistency
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨', **kwargs)
        return check_calorie_consistency(label)

    def test_맞으면_지적하지_않는다(self):
        self.assertEqual(self._issues(content_weight='800 g (1240 kcal)', calories='155'), [])

    def test_어긋나면_계산_근거까지_보여준다(self):
        issues = self._issues(content_weight='800 g (400 kcal)', calories='155')
        self.assertEqual(len(issues), 1)
        msg = issues[0]['message']
        self.assertIn('400', msg)      # 적힌 값
        self.assertIn('1,240', msg)    # 계산값
        self.assertIn('155', msg)      # 100g당

    def test_반올림_차이는_넘어간다(self):
        """열량은 표시기준상 5kcal 단위로 반올림한다."""
        self.assertEqual(self._issues(content_weight='100 g (123 kcal)', calories='125'), [])

    def test_단위가_kg_l_이어도_환산한다(self):
        self.assertEqual(self._issues(content_weight='1 kg (1550 kcal)', calories='155'), [])
        self.assertEqual(len(self._issues(content_weight='1 kg (155 kcal)', calories='155')), 1)

    def test_쉼표가_있어도_읽는다(self):
        self.assertEqual(self._issues(content_weight='600g(2,346kcal)', calories='391'), [])

    def test_한쪽이_없으면_검사하지_않는다(self):
        """비교할 근거가 없는 것과 어긋나는 것은 다르다."""
        self.assertEqual(self._issues(content_weight='800 g (1240 kcal)'), [])   # 영양성분 없음
        self.assertEqual(self._issues(content_weight='800 g', calories='155'), [])  # 열량 병기 없음
        self.assertEqual(self._issues(weight_calorie='1240 kcal', calories='155'), [])  # 총량 못 읽음

    def test_전용_칸에_적어도_비교한다(self):
        issues = self._issues(content_weight='800 g', weight_calorie='400 kcal', calories='155')
        self.assertEqual(len(issues), 1)

    def test_무료_검증에_물려_있다(self):
        from v1.label.services.validation_service import _CHECKS
        self.assertIn('check_calorie_consistency', {c.__name__ for c in _CHECKS})


class ListColumnAlignTests(TestCase):
    """
    목록 표의 머리글과 본문 정렬.

    머리글은 컬럼 정의(list_sort.py 의 align)를 따랐는데 본문 칸은 화면마다
    제각각이었다. 내 원료 관리는 "원재료명" 머리글이 왼쪽인데 값은 가운데라
    같은 열인지 알아보기 어려웠고, 제품 조회는 반대로 값만 가운데였다.
    """

    def _render(self, specs, table, offset):
        from django.template.loader import render_to_string
        from v1.label.services import list_sort

        cols = list_sort.columns(specs, specs[0]['field'], 'asc')
        return render_to_string('label/_list_column_align.html',
                                {'list_columns': cols,
                                 'align_table': table, 'align_offset': offset})

    def _rules(self, css):
        """(열 번호, 정렬) 목록"""
        import re
        return re.findall(
            r'th:nth-child\((\d+)\),\s*\S+ tbody td:nth-child\(\d+\) \{\s*text-align: (\w+);',
            css)

    def test_머리글과_본문에_같은_규칙이_걸린다(self):
        from v1.label.services import list_sort

        css = self._render(list_sort.MY_INGREDIENT_COLUMNS, '.list-table', 1)
        for n in range(2, 6):
            self.assertIn(f'.list-table thead th:nth-child({n})', css)
            self.assertIn(f'.list-table tbody td:nth-child({n})', css)

    def test_컬럼_정의의_정렬이_그대로_나온다(self):
        from v1.label.services import list_sort

        specs = list_sort.MY_INGREDIENT_COLUMNS
        rules = self._rules(self._render(specs, '.list-table', 1))
        self.assertEqual(len(rules), len(specs))
        for (col_no, align), spec in zip(rules, specs):
            self.assertEqual(align, spec['align'], f"{spec['label']} 정렬이 다르다")

        # 사용자가 지적한 그 열 — 머리글은 왼쪽인데 값은 가운데였다
        by_label = dict(zip([s['label'] for s in specs], [a for _, a in rules]))
        self.assertEqual(by_label['원재료명'], 'left')

    def test_앞쪽_열_수만큼_밀린다(self):
        """체크박스·순번처럼 컬럼 정의에 없는 열이 앞에 있다."""
        from v1.label.services import list_sort

        rules = self._rules(self._render(list_sort.MY_LABEL_COLUMNS, '.common-table', 2))
        self.assertEqual(rules[0][0], '3')   # 체크박스 + 순번 다음
        self.assertEqual(rules[0][1], list_sort.MY_LABEL_COLUMNS[0]['align'])

    def test_손으로_박은_nth_child_가_남아_있지_않다(self):
        """
        컬럼이 늘거나 순서가 바뀌면 따라오지 않아 조용히 어긋난다.
        실제로 내 원료 관리의 nth-child(2)/(5) 가 컬럼 순서와 맞지 않았다.
        """
        import re
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR) / 'templates'
        for rel in ('label/my_ingredient_list_combined.html',
                    'label/food_additive_search.html'):
            text = (base / rel).read_text(encoding='utf-8')
            style = ' '.join(re.findall(r'<style>(.*?)</style>', text, re.S))
            leftover = re.findall(r'(td:nth-child\(\d+\)[^{]*\{[^}]*text-align)', style)
            self.assertEqual(leftover, [], f'{rel} 에 손으로 박은 정렬이 남아 있다')


class RequiredFieldMessageTests(TestCase):
    """
    필수 미입력을 한 문장으로 모은다.

    항목마다 따로 내면 근거 규정까지 통째로 되풀이된다. 세 항목이 빈 라벨에서
    같은 문구가 세 번, 제안도 세 번 나왔다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='msg', password='x')

    def _issues(self, **kwargs):
        from v1.label.services.validation_service import check_required_fields
        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨', **kwargs)
        return check_required_fields(label)

    def _filled(self, **overrides):
        base = {f: '값' for f in ('prdlst_dcnm', 'prdlst_nm', 'content_weight',
                                  'prdlst_report_no', 'frmlc_mtrqlt', 'bssh_nm',
                                  'pog_daycnt', 'rawmtrl_nm_display', 'cautions')}
        base.update(overrides)
        return base

    def test_여러_개가_비어도_한_건으로_낸다(self):
        issues = self._issues(**self._filled(content_weight='', prdlst_report_no='',
                                             frmlc_mtrqlt=''))
        self.assertEqual(len(issues), 1)
        msg = issues[0]['message']
        for name in ('내용량', '품목보고번호', '포장재질'):
            self.assertIn(name, msg)
        # 근거 규정이 한 번만 나온다
        self.assertEqual(msg.count('의무표시사항 기재 규정'), 1)
        self.assertIn('3개 항목', msg)

    def test_제안도_한_번만_낸다(self):
        issues = self._issues(**self._filled(content_weight='', prdlst_report_no=''))
        self.assertEqual(issues[0]['suggestion'].count('표시 항목 체크를 해제'), 1)

    def test_하나뿐이면_그_이름만_말한다(self):
        issues = self._issues(**self._filled(content_weight=''))
        self.assertIn('"내용량" 항목이 비어 있습니다', issues[0]['message'])
        self.assertNotIn('개 항목', issues[0]['message'])

    def test_항목_목록을_따로_실어_보낸다(self):
        """확정 차단 화면이 문장을 파싱하지 않고 항목명을 쓴다."""
        issues = self._issues(**self._filled(content_weight='', frmlc_mtrqlt=''))
        self.assertEqual(issues[0]['field_labels'], ['내용량', '포장재질'])
        self.assertEqual(issues[0]['fields'], ['content_weight', 'frmlc_mtrqlt'])
class IngredientSaveIntegrityTests(TestCase):
    """
    원재료 표 저장(save_ingredients_to_label).

    맨 처음 하는 일이 기존 연결의 전량 삭제다. 그 뒤 새로 넣는 중에 하나라도
    터지면 원재료가 통째로 사라진 채 남는다 — 지우기는 커밋됐고 넣기는 안 됐으니까.
    화면에는 "저장 실패" 만 뜬다.
    """

    def setUp(self):
        from v1.label.models import LabelIngredientRelation, MyIngredient

        self.user = User.objects.create_user(username='save', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='원재료')
        self.ing = MyIngredient.objects.create(
            user_id=self.user, prdlst_nm='설탕', delete_YN='N')
        LabelIngredientRelation.objects.create(
            label=self.label, ingredient=self.ing, relation_sequence=1)
        self.url = f'/label/save-ingredients-to-label/{self.label.my_label_id}/'

    def _relations(self):
        from v1.label.models import LabelIngredientRelation
        return LabelIngredientRelation.objects.filter(label=self.label).count()

    def test_저장이_중간에_터져도_기존_원재료가_남는다(self):
        """
        전량 삭제는 이미 끝난 시점에서 터뜨린다. 롤백이 없으면 원재료가 0건으로
        남고, 화면에는 "저장 실패" 만 뜬다.
        """
        from v1.label.models import LabelIngredientRelation

        self.assertEqual(self._relations(), 1)
        with patch('v1.label.views.MyLabel.save', side_effect=RuntimeError('중간에 폭발')):
            resp = self.client.post(
                self.url,
                data=json.dumps({'ingredients': [{'ingredient_name': '밀가루'}]}),
                content_type='application/json')

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self._relations(), 1, '지우기까지 되돌려야 한다')
        kept = LabelIngredientRelation.objects.get(label=self.label)
        self.assertEqual(kept.ingredient.prdlst_nm, '설탕', '원래 있던 것이 그대로여야 한다')

    def test_정상_저장은_그대로_동작한다(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({'ingredients': [
                {'ingredient_name': '설탕', 'my_ingredient_id': self.ing.my_ingredient_id},
            ]}),
            content_type='application/json')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])


class IngredientSearchLimitTests(TestCase):
    """
    내 원료 검색(search_ingredient_add_row).

    상한도 정렬도 없었다. 조건을 하나도 안 걸거나 "가" 같은 넓은 검색어 하나만
    넣으면 내 원료 전체가 그대로 넘어온다.
    """

    def setUp(self):
        from v1.label.models import MyIngredient
        from v1.label.views import INGREDIENT_SEARCH_LIMIT

        self.limit = INGREDIENT_SEARCH_LIMIT
        self.user = User.objects.create_user(username='search', password='x')
        self.client.force_login(self.user)
        for i in range(self.limit + 15):
            MyIngredient.objects.create(
                user_id=self.user, prdlst_nm=f'원료{i:03}', delete_YN='N')

    def _search(self, **body):
        return self.client.post('/label/search-ingredient-add-row/',
                                data=json.dumps(body),
                                content_type='application/json').json()

    def test_상한을_넘겨_돌려주지_않는다(self):
        data = self._search()
        self.assertEqual(len(data['ingredients']), self.limit)

    def test_잘렸다는_것과_전체_건수를_알려준다(self):
        """모르면 사용자는 없는 원료라고 생각하고 같은 원료를 다시 등록한다."""
        data = self._search()
        self.assertTrue(data['truncated'])
        self.assertEqual(data['total'], self.limit + 15)
        self.assertEqual(data['limit'], self.limit)

    def test_다_들어가면_잘리지_않았다고_말한다(self):
        data = self._search(ingredient_name='원료001')
        self.assertFalse(data['truncated'])
        self.assertEqual(data['total'], len(data['ingredients']))

    def test_순서가_정해져_있다(self):
        """정렬이 없으면 같은 검색을 두 번 해도 순서가 달라질 수 있다."""
        names = [i['prdlst_nm'] for i in self._search()['ingredients']]
        self.assertEqual(names, sorted(names))
class IngredientDedupeTests(TestCase):
    """
    같은 원료를 두 번 만들지 않는다.

    라벨마다 새 MyIngredient 를 만들어서 운영 데이터에 같은 원료가 13개씩 쌓여
    있었다(548건 중 여분 108건, 19.7%). 원료 검색이 같은 이름으로 도배되고,
    하나를 고쳐도 다른 라벨은 옛 값을 본다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='dedupe', password='x')
        self.client.force_login(self.user)

    def _register(self, **body):
        payload = {'ingredient_name': '피자치즈', 'food_category': 'processed',
                   'food_type': '치즈'}
        payload.update(body)
        return self.client.post('/label/quick-register-ingredient/',
                                data=json.dumps(payload),
                                content_type='application/json').json()

    def test_같은_원료를_두_번_등록해도_하나만_남는다(self):
        from v1.label.models import MyIngredient

        first = self._register()
        second = self._register()

        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['my_ingredient_id'], second['my_ingredient_id'])
        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='피자치즈').count(), 1)

    def test_품목보고번호가_다르면_다른_원료다(self):
        """이름만으로 묶으면 제조사가 다른 같은 이름을 하나로 만들어 버린다."""
        from v1.label.models import MyIngredient

        self._register(report_no='111')
        self._register(report_no='222')
        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='피자치즈').count(), 2)

    def test_식품유형이_다르면_다른_원료다(self):
        from v1.label.models import MyIngredient

        self._register(food_type='치즈')
        self._register(food_type='가공유류')
        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='피자치즈').count(), 2)

    def test_사용자가_다르면_섞이지_않는다(self):
        from v1.label.models import MyIngredient

        self._register()
        other = User.objects.create_user(username='other', password='x')
        self.client.force_login(other)
        self._register()

        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='피자치즈').count(), 2)

    def test_이미_있으면_넘어온_값으로_덮어쓰지_않는다(self):
        """
        MyIngredient 는 여러 라벨이 함께 쓰는 레코드다. 한 라벨에서 저장했다고
        다른 라벨이 보던 값이 바뀌면 안 된다.
        """
        from v1.label.models import MyIngredient

        self._register(allergens='우유', display_name='피자치즈(자연치즈)')
        self._register(allergens='', display_name='다른 표시명')

        ing = MyIngredient.objects.get(prdlst_nm='피자치즈')
        self.assertEqual(ing.allergens, '우유')
        self.assertEqual(ing.ingredient_display_name, '피자치즈(자연치즈)')

    def test_원재료_표_저장도_같은_원료를_다시_만들지_않는다(self):
        from v1.label.models import MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='표')
        url = f'/label/save-ingredients-to-label/{label.my_label_id}/'
        body = json.dumps({'ingredients': [
            {'ingredient_name': '펭귄도우', 'food_type': '빵류'},
        ]})
        for _ in range(3):
            self.client.post(url, data=body, content_type='application/json')

        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='펭귄도우').count(), 1)
class IngredientOrderByRatioTests(TestCase):
    """
    인쇄되는 원재료명 문구가 배합비 내림차순인지, DB 배합비와 대조한다.

    이 파일은 원래 표시 순서를 검사하지 않았다 — 생성기가 정렬하니까. 그건
    생성기가 만든 문구에 대해서는 맞지만, 사용자가 손으로 고친 문구는 아무도 다시
    정렬해 주지 않는다. 운영에서 실제로 3건 나왔고 그중 하나는 보존료(0.03%)가
    주원료(87.32%)보다 앞이었다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='order', password='x')

    def _label(self, text, pairs):
        from v1.label.models import LabelIngredientRelation, MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='순서',
                                       rawmtrl_nm_display=text)
        for seq, (name, ratio) in enumerate(pairs, start=1):
            ing = MyIngredient.objects.create(
                user_id=self.user, prdlst_nm=name, delete_YN='N')
            LabelIngredientRelation.objects.create(
                label=label, ingredient=ing, relation_sequence=seq,
                ingredient_ratio=ratio)
        return label

    def _issues(self, label):
        from v1.label.services.validation_service import check_ingredient_order_by_ratio
        return check_ingredient_order_by_ratio(label)

    def test_문구가_역순이면_지적한다(self):
        label = self._label('소브산칼륨, 소홍두깨살',
                            [('소홍두깨살', 87.32), ('소브산칼륨', 0.03)])
        issues = self._issues(label)
        self.assertEqual(len(issues), 1)
        self.assertIn('"소브산칼륨"(0.03%)가 "소홍두깨살"(87.32%)보다 앞', issues[0]['message'])

    def test_문구가_내림차순이면_통과한다(self):
        label = self._label('소홍두깨살, 소브산칼륨',
                            [('소홍두깨살', 87.32), ('소브산칼륨', 0.03)])
        self.assertEqual(self._issues(label), [])

    def test_입력_순서가_뒤집혀도_문구가_맞으면_넘어간다(self):
        """생성기가 정렬하므로 입력 순서로 사용자를 탓하면 안 된다."""
        label = self._label('밀가루, 설탕', [('설탕', 10), ('밀가루', 30)])
        self.assertEqual(self._issues(label), [])

    def test_문구에서_이름을_못_찾으면_지적하지_않는다(self):
        """표시명이 다르게 적혀 있을 수 있다. 모르는 것과 위반은 다르다."""
        label = self._label('밀 가공품, 정제당', [('밀가루', 30), ('설탕', 10)])
        self.assertEqual(self._issues(label), [])

    def test_배합비가_없으면_판단하지_않는다(self):
        label = self._label('설탕, 밀가루', [('설탕', None), ('밀가루', None)])
        self.assertEqual(self._issues(label), [])

    def test_퍼센트_표기가_없어도_잡는다(self):
        """AI 검사는 문구에 적힌 %를 읽는다. 안 적었으면 판단하지 못한다."""
        label = self._label('설탕, 밀가루', [('밀가루', 30), ('설탕', 10)])
        self.assertNotIn('%', label.rawmtrl_nm_display)
        self.assertEqual(len(self._issues(label)), 1)

    def test_참고_필드로도_본다(self):
        """V2 로만 작업한 제품은 표시 필드가 비고 참고 필드에 문구가 있다."""
        label = self._label('', [('밀가루', 30), ('설탕', 10)])
        label.rawmtrl_nm = '설탕, 밀가루'
        label.save()
        self.assertEqual(len(self._issues(label)), 1)

    def test_무료_검증에_물려_있다(self):
        from v1.label.services.validation_service import _CHECKS
        self.assertIn('check_ingredient_order_by_ratio', {c.__name__ for c in _CHECKS})

    def test_AI가_판단_못_해도_규칙_기반_지적은_남는다(self):
        """
        AI 가 못 본 항목은 "적합" 으로 오인되지 않게 표에서 지운다. 그 처리에
        규칙 기반 지적까지 휩쓸리면 실제 위반이 조용히 사라진다.
        """
        from django.core.cache import cache
        from v1.label.services import ai_validation_service as avs

        cache.clear()
        label = self._label('설탕, 밀가루', [('밀가루', 30), ('설탕', 10)])
        label.prdlst_nm = '제품'
        label.save()

        with patch.object(avs, 'call_openai', return_value=(None, avs.REASON_API_ERROR)):
            result = avs.run_full_review(label, self.user)

        rows = [c for c in result['categories'] if '원재료 표시 순서' in c['label']]
        self.assertEqual(len(rows), 1, '규칙 기반 지적이 있으면 행이 남아야 한다')
        self.assertFalse(rows[0]['ok'])


class AiUsageCounterTests(TestCase):
    """
    AI검증 일일 한도 카운터.

    파일 캐시에 있었는데, CACHES['default'] 는 항목이 MAX_ENTRIES 를 넘으면
    Django 가 1/3 을 잘라낸다(FileBasedCache._cull). 그때 카운터가 날아가면
    한도가 조용히 초기화된다. 유료 기능의 사용량이 캐시 정리에 좌우되면 안 된다.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='quota', password='x')

    def _usage(self):
        from v1.label.services.ai_rate_limit import get_usage
        return get_usage(self.user)

    def _check(self):
        from v1.label.services.ai_rate_limit import check_rate_limit
        return check_rate_limit(self.user)

    def test_처음에는_0회다(self):
        self.assertEqual(self._usage()['daily_used'], 0)

    def test_통과할_때마다_한_번씩_오른다(self):
        for expected in (1, 2, 3):
            allowed, usage = self._check()
            self.assertTrue(allowed)
            self.assertEqual(usage['daily_used'], expected)
        self.assertEqual(self._usage()['daily_used'], 3)

    def test_하루에_한_행만_쓴다(self):
        from v1.common.models import AiValidationUsage

        for _ in range(3):
            self._check()
        rows = AiValidationUsage.objects.filter(user=self.user)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().count, 3)

    def test_한도를_넘으면_막는다(self):
        from v1.label.services.ai_rate_limit import _free_daily_limit

        limit = _free_daily_limit()
        for _ in range(limit):
            self.assertTrue(self._check()[0])

        allowed, usage = self._check()
        self.assertFalse(allowed)
        self.assertIn('한도', usage['message'])
        self.assertEqual(usage['daily_used'], limit, '막힌 요청은 차감하지 않는다')

    def test_캐시를_비워도_사용량이_남는다(self):
        """이 검사가 이 작업의 이유다. 캐시에 있을 때는 여기서 0 으로 돌아갔다."""
        from django.core.cache import cache

        self._check()
        self._check()
        cache.clear()
        self.assertEqual(self._usage()['daily_used'], 2)

    def test_어제_사용량은_오늘에_안_섞인다(self):
        from datetime import timedelta
        from django.utils import timezone
        from v1.common.models import AiValidationUsage

        AiValidationUsage.objects.create(
            user=self.user, used_date=timezone.localdate() - timedelta(days=1), count=9)
        self.assertEqual(self._usage()['daily_used'], 0)

    def test_사용자끼리_섞이지_않는다(self):
        other = User.objects.create_user(username='quota2', password='x')
        from v1.label.services.ai_rate_limit import check_rate_limit, get_usage

        self._check()
        self._check()
        check_rate_limit(other)
        self.assertEqual(self._usage()['daily_used'], 2)
        self.assertEqual(get_usage(other)['daily_used'], 1)

    def test_조회가_실패해도_막지_않는다(self):
        """
        사용자를 막는 것보다 몇 번 더 나가는 쪽이 낫다. 조용히 넘기지 않고
        로그에 남긴다.
        """
        from unittest.mock import patch
        from v1.label.services import ai_rate_limit

        with patch.object(ai_rate_limit, 'AiValidationUsage', create=True):
            with patch('v1.common.models.AiValidationUsage.objects') as objs:
                objs.filter.side_effect = RuntimeError('DB 장애')
                self.assertEqual(self._usage()['daily_used'], 0)


class TempLabelNumberingTests(TestCase):
    """
    "임시 - 제품명 - N" 채번을 DB 가 하게 했다.

    예전에는 그 이름으로 시작하는 라벨을 전부 가져와 파이썬 정규식으로 최대값을
    찾았다. 이탈한 빈 라벨이 쌓이는 화면이라 목록이 계속 길어지고, 신규 작성
    버튼이 그만큼 느려진다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='numbering', password='x')
        self.client.force_login(self.user)

    def _create(self):
        res = self.client.post('/label/create-new/',
                               data=json.dumps({}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content[:200])
        return MyLabel.objects.filter(user_id=self.user).order_by('-my_label_id').first()

    def test_첫_라벨은_1번(self):
        self.assertEqual(self._create().my_label_name, '임시 - 제품명 - 1')

    def test_최대값_다음_번호를_쓴다(self):
        MyLabel.objects.create(user_id=self.user, my_label_name='임시 - 제품명 - 7')
        MyLabel.objects.create(user_id=self.user, my_label_name='임시 - 제품명 - 3')
        self.assertEqual(self._create().my_label_name, '임시 - 제품명 - 8')

    def test_다른_사용자_라벨은_세지_않는다(self):
        other = User.objects.create_user(username='numbering2', password='x')
        MyLabel.objects.create(user_id=other, my_label_name='임시 - 제품명 - 99')
        self.assertEqual(self._create().my_label_name, '임시 - 제품명 - 1')

    def test_숫자가_아닌_꼬리는_최대값을_흔들지_않는다(self):
        # 사용자가 이름을 고쳐 둔 경우. 캐스팅이 0 이 되어야 한다.
        MyLabel.objects.create(user_id=self.user, my_label_name='임시 - 제품명 - 초코')
        MyLabel.objects.create(user_id=self.user, my_label_name='임시 - 제품명 - 2')
        self.assertEqual(self._create().my_label_name, '임시 - 제품명 - 3')


class CleanupTempLabelsTests(TestCase):
    """
    만들어만 놓고 손대지 않은 임시 라벨을 치운다.

    지우지 않고 delete_YN 만 바꾼다 — 실제로 지우면 BOM·문서함·공유·알림이
    CASCADE 로 함께 사라진다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='cleanup', password='x')

    def _old_temp(self, name='임시 - 제품명 - 1', **fields):
        label = MyLabel.objects.create(user_id=self.user, my_label_name=name, **fields)
        # update_datetime 은 auto_now 라 save() 로는 과거로 못 민다
        MyLabel.objects.filter(pk=label.pk).update(
            update_datetime=timezone.now() - timezone.timedelta(days=90))
        return MyLabel.objects.get(pk=label.pk)

    def _run(self, *args):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('cleanup_temp_labels', *args, stdout=out)
        return out.getvalue()

    def test_기본은_미리보기라_아무것도_안_바꾼다(self):
        label = self._old_temp()
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'N')

    def test_손대지_않은_것은_숨긴다(self):
        label = self._old_temp()
        self._run('--apply')
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'Y')

    def test_내용이_있으면_남긴다(self):
        label = self._old_temp(prdlst_nm='초코쿠키')
        self._run('--apply')
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'N')

    def test_최근_라벨은_건드리지_않는다(self):
        label = MyLabel.objects.create(user_id=self.user,
                                       my_label_name='임시 - 제품명 - 2')
        self._run('--apply')
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'N')

    def test_이름을_바꾼_라벨은_대상이_아니다(self):
        label = self._old_temp(name='초코쿠키 표시사항')
        self._run('--apply')
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'N')

    def test_원재료가_붙어_있으면_남긴다(self):
        label = self._old_temp()
        ing = MyIngredient.objects.create(user_id=self.user, prdlst_nm='밀가루',
                                          delete_YN='N')
        LabelIngredientRelation.objects.create(label=label, ingredient=ing,
                                               ingredient_ratio=50)
        self._run('--apply')
        label.refresh_from_db()
        self.assertEqual(label.delete_YN, 'N')


class RawmtrlDisplayGeneratorTests(TestCase):
    """
    인쇄되는 원재료명 문구를 규칙으로 만든다.

    여태 사람이 손으로 조립하던 구간이다. 참고용 요약을 복사해 옮긴 뒤 함량
    순서를 맞추고, 첨가물 간략명을 고르고, 복합원재료 괄호를 치고, 알레르기
    문구를 붙였다. 라벨에서 법적 리스크가 가장 큰 산출물인데 자동화가 없었다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='display', password='x')
        self.client.force_login(self.user)
        self.label = MyLabel.objects.create(user_id=self.user,
                                            my_label_name='초코쿠키')

    def _add(self, name, ratio, *, seq=1, **fields):
        ing = MyIngredient.objects.create(
            user_id=self.user, prdlst_nm=name, delete_YN='N', **fields)
        LabelIngredientRelation.objects.create(
            label=self.label, ingredient=ing,
            ingredient_ratio=ratio, relation_sequence=seq)
        return ing

    def _generate(self):
        res = self.client.get(f'/label/{self.label.my_label_id}/rawmtrl-display/')
        return res.status_code, res.json()

    def test_배합비_내림차순으로_적는다(self):
        self._add('정제소금', 5, seq=1)
        self._add('밀가루', 60, seq=2)
        self._add('설탕', 20, seq=3)
        status, body = self._generate()
        self.assertEqual(status, 200)
        self.assertEqual(body['text'].split('  ')[0], '밀가루, 설탕, 정제소금')

    def test_복합원재료는_하위원료를_괄호에_적는다(self):
        self._add('빵가루', 30, rawmtrl_nm='밀가루, 정제소금')
        status, body = self._generate()
        self.assertIn('빵가루(밀가루, 정제소금)', body['text'])

    def test_이름에_이미_괄호가_있으면_두_겹으로_안_만든다(self):
        self._add('빵가루(밀가루)', 30, rawmtrl_nm='밀가루, 정제소금')
        status, body = self._generate()
        self.assertIn('빵가루(밀가루)', body['text'])
        self.assertNotIn('))', body['text'])

    def test_표4_첨가물은_명칭과_용도를_함께_적는다(self):
        FoodAdditive.objects.create(name_kr='사카린나트륨', alias_4='Y',
                                    sweetener='Y')
        self._add('사카린나트륨', 1, food_category='additive')
        status, body = self._generate()
        self.assertIn('사카린나트륨(감미료)', body['text'])
        self.assertEqual(body['needs_review'], [])

    def test_표4인데_용도가_여럿이면_사람이_고르게_한다(self):
        FoodAdditive.objects.create(name_kr='이산화황', alias_4='Y',
                                    preservative='Y', antioxidant='Y')
        self._add('이산화황', 1, food_category='additive')
        status, body = self._generate()
        self.assertEqual(body['needs_review'], ['이산화황'])

    def test_표5_첨가물은_명칭만으로_충분하다(self):
        FoodAdditive.objects.create(name_kr='구연산', alias_5='Y')
        self._add('구연산', 2, food_category='additive')
        status, body = self._generate()
        self.assertIn('구연산', body['text'])
        self.assertEqual(body['needs_review'], [])

    def test_사용자가_고른_표시명이_규칙에_맞으면_그것을_쓴다(self):
        FoodAdditive.objects.create(name_kr='구연산', alias_5='Y',
                                    short_name='산미료용구연산')
        self._add('구연산', 2, food_category='additive',
                  ingredient_display_name='산미료용구연산')
        status, body = self._generate()
        self.assertIn('산미료용구연산', body['text'])

    def test_알레르기는_함유_형태로_뒤에_붙는다(self):
        self._add('탈지분유', 30, allergens='우유')
        self._add('밀가루', 60, allergens='밀', seq=2)
        status, body = self._generate()
        self.assertIn('[알레르기 성분: 밀, 우유 함유]', body['text'])

    def test_원재료가_없으면_400_과_안내(self):
        status, body = self._generate()
        self.assertEqual(status, 400)
        self.assertFalse(body['success'])

    def test_저장하지_않는다(self):
        self._add('밀가루', 60)
        self._generate()
        self.label.refresh_from_db()
        self.assertFalse(self.label.rawmtrl_nm_display)

    def test_남의_라벨은_못_본다(self):
        other = User.objects.create_user(username='display2', password='x')
        self.client.force_login(other)
        res = self.client.get(f'/label/{self.label.my_label_id}/rawmtrl-display/')
        self.assertEqual(res.status_code, 404)


class IngredientTextParseTests(TestCase):
    """
    인쇄된 원재료명 한 줄을 원료 목록으로 쪼갠다.

    실제 라벨 세 장에서 가져온 문구로 고정한다. 괄호 안 쉼표에서 자르면 첨가물
    하나가 여러 원료로 쪼개지고, 알레르기 선언을 안 떼면 "대두" 가 원료로 들어간다.
    """

    def _parse(self, text):
        from v1.label.services.ingredient_text import parse_ingredient_list
        return parse_ingredient_list(text)

    def test_괄호_안_쉼표에서_자르지_않는다(self):
        res = self._parse('혼합제제(초산전분, 히드록시프로필인산이전분), 정제소금')
        self.assertEqual([i['name'] for i in res['items']], ['혼합제제', '정제소금'])
        self.assertEqual(res['items'][0]['sub_ingredients'],
                         '초산전분, 히드록시프로필인산이전분')

    def test_원산지와_함량을_떼어낸다(self):
        res = self._parse('새송이버섯(국산)57.64%')
        item = res['items'][0]
        self.assertEqual(item['name'], '새송이버섯')
        self.assertEqual(item['origin'], '국산')
        self.assertEqual(item['ratio'], 57.64)

    def test_원산지와_하위원료가_같이_있는_경우(self):
        res = self._parse('과·채가공품/표고버섯채(중국산)21.63%(표고버섯,정제수,정제소금,구연산)')
        item = res['items'][0]
        self.assertEqual(item['name'], '과·채가공품/표고버섯채')
        self.assertEqual(item['origin'], '중국산')
        self.assertEqual(item['ratio'], 21.63)
        self.assertEqual(item['sub_ingredients'], '표고버섯, 정제수, 정제소금, 구연산')

    def test_콜론이_들어간_원산지(self):
        res = self._parse('녹차(국산:제주산) 89%, 콩기름(대두:외국산)')
        self.assertEqual(res['items'][0]['origin'], '국산:제주산')
        self.assertEqual(res['items'][1]['origin'], '대두:외국산')

    def test_끝에_붙은_알레르기_선언을_떼어낸다(self):
        res = self._parse('밀가루, 설탕, 탈지분유, 밀, 우유 함유')
        self.assertEqual([i['name'] for i in res['items']],
                         ['밀가루', '설탕', '탈지분유'])
        self.assertEqual(res['allergen_note'], '밀, 우유 함유')

    def test_쉼표를_놓친_알레르기_선언도_떼어낸다(self):
        """OCR 이 원료와 알레르기 선언 사이 쉼표를 놓치는 경우."""
        res = self._parse('구연산, 카로틴 알류(계란), 대두 함유')
        self.assertEqual([i['name'] for i in res['items']], ['구연산', '카로틴'])
        self.assertEqual(res['allergen_note'], '알류(계란), 대두 함유')

    def test_괄호_안의_함유는_원료_설명이라_두고_본다(self):
        res = self._parse('정제수, 향료(바닐라 함유)')
        self.assertEqual([i['name'] for i in res['items']], ['정제수', '향료'])
        self.assertEqual(res['allergen_note'], '')

    def test_구연산은_원산지가_아니다(self):
        """끝이 '산' 이라 원산지로 헷갈리는 첨가물."""
        res = self._parse('과일농축액(구연산)')
        self.assertEqual(res['items'][0]['origin'], '')
        self.assertEqual(res['items'][0]['sub_ingredients'], '구연산')

    def test_대괄호_알레르기_표기도_떼어낸다(self):
        res = self._parse('밀가루, 설탕  [알레르기 성분: 밀 함유]')
        self.assertEqual([i['name'] for i in res['items']], ['밀가루', '설탕'])
        self.assertIn('밀', res['allergen_note'])

    def test_빈_문자열은_빈_목록(self):
        self.assertEqual(self._parse('')['items'], [])
        self.assertEqual(self._parse(None)['items'], [])


class OcrPromptTests(TestCase):
    """
    OCR 프롬프트의 항목 목록과 응답 스키마가 어긋나지 않아야 한다.

    설명에만 있고 스키마에 없으면 모델이 그 키를 안 내고, 스키마에만 있고
    설명이 없으면 무엇을 넣어야 할지 모른 채 빈 값을 낸다. 어느 쪽이든 그
    항목만 조용히 비어서 "사진이 흐렸나" 로 보인다.
    """

    def setUp(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT
        self.prompt = SYSTEM_PROMPT

    def _keys(self):
        import re
        schema = re.search(r'\{[^{]*"prdlst_nm".*\}', self.prompt, re.S).group(0)
        return set(re.findall(r'"(\w+)":\s*\{', schema))

    def _described(self):
        import re
        return set(re.findall(r'^- (\w+):', self.prompt, re.M))

    def test_스키마와_설명이_일치한다(self):
        self.assertEqual(self._keys(), self._described())

    def test_화면이_쓰는_항목이_모두_있다(self):
        """basic_info_ocr.js 의 FIELD_MAP 이 없는 키를 찾으면 그 칸은 안 채워진다."""
        import re
        from pathlib import Path
        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
              ).read_text(encoding='utf-8')
        block = re.search(r'var FIELD_MAP = \{(.*?)\n  \};', js, re.S).group(1)
        used = set(re.findall(r'^\s{4}(\w+):', block, re.M))
        missing = sorted(used - self._keys())
        self.assertEqual(missing, [], f'프롬프트에 없는 항목: {missing}')

    def test_실제_라벨에_있는_항목을_빠뜨리지_않는다(self):
        """운영 라벨에서 통째로 안 읽히던 것들. 프롬프트에서 사라지면 다시 그렇게 된다."""
        for key in ['bssh_nm', 'pog_daycnt', 'storage_method', 'cautions',
                    'allergens', 'content_weight', 'frmlc_mtrqlt']:
            self.assertIn(key, self._keys(), f'{key} 가 스키마에서 빠졌다')

    def test_응답_길이가_충분하다(self):
        """빽빽한 라벨은 응답이 길다. 2000 이면 원재료명이 끊기고 뒤가 통째로 빠졌다."""
        from pathlib import Path
        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
               ).read_text(encoding='utf-8')
        self.assertIn('max_tokens=4000', src)


class OcrApplyExtrasTests(TestCase):
    """
    사진에서 읽은 영양성분·분리배출을 라벨에 반영하는 규칙.

    기본 정보 탭에 칸이 없는 항목들이다 - 영양성분은 별도 탭(iframe),
    분리배출은 미리보기 설정.
    """

    def test_숫자와_단위를_가른다(self):
        from v1.label.services.ocr_apply import split_value_unit

        self.assertEqual(split_value_unit('630 mg', 'natriums'), ('630', 'mg'))
        self.assertEqual(split_value_unit('4.3g', 'saturated_fats'), ('4.3', 'g'))
        self.assertEqual(split_value_unit('1,200 mg', 'natriums'), ('1200', 'mg'))

    def test_단위를_못_읽으면_규정_단위를_붙인다(self):
        """단위가 틀리면 표시가 통째로 틀린다. 비워 두는 것보다 규정값이 낫다."""
        from v1.label.services.ocr_apply import split_value_unit

        self.assertEqual(split_value_unit('630', 'natriums'), ('630', 'mg'))
        self.assertEqual(split_value_unit('10', 'carbohydrates'), ('10', 'g'))
        self.assertEqual(split_value_unit('182', 'calories'), ('182', 'kcal'))

    def test_고른_성분만_쓰고_나머지는_두다(self):
        from v1.label.services.ocr_apply import apply_nutrition

        user = User.objects.create_user(username='nutri', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='샐러드',
                                       dietary_fiber='3')
        apply_nutrition(label, [{'field': 'natriums', 'raw': '630 mg'},
                                {'field': 'proteins', 'raw': '13 g'}])
        label.refresh_from_db()
        self.assertEqual(label.natriums, '630')
        self.assertEqual(label.natriums_unit, 'mg')
        self.assertEqual(label.proteins, '13')
        # 사진에 없던 성분은 지워지지 않는다
        self.assertEqual(label.dietary_fiber, '3')

    def test_표의_기준을_읽는다(self):
        from v1.label.services.ocr_apply import parse_nutrition_basis

        self.assertEqual(parse_nutrition_basis('총 내용량 139 g'), ('139', 'g'))
        self.assertEqual(parse_nutrition_basis('100 g당'), ('100', 'g'))
        self.assertEqual(parse_nutrition_basis('1회 제공량 200 mL'), ('200', 'mL'))
        self.assertEqual(parse_nutrition_basis('알 수 없음'), (None, None))

    def test_분리배출_표기를_저장용_종류로_바꾼다(self):
        from v1.label.services.ocr_apply import map_recycling_mark

        self.assertEqual(map_recycling_mark('비닐류 PP / 띠지:PP, 리드지:PET')[0],
                         '비닐(PP)')
        self.assertEqual(map_recycling_mark('플라스틱 OTHER')[0], '기타플라스틱')
        self.assertEqual(map_recycling_mark('플라스틱 PET')[0], '플라스틱(PET)')
        self.assertEqual(map_recycling_mark('유리')[0], '유리')
        self.assertEqual(map_recycling_mark('캔류 알미늄')[0], '캔류(알미늄)')

    def test_종류를_못_정하면_문구만_남긴다(self):
        """틀린 종류를 넣으면 포장재질 대조 검증이 엉뚱하게 운다."""
        from v1.label.services.ocr_apply import map_recycling_mark

        mark, text = map_recycling_mark('알 수 없는 표기')
        self.assertEqual(mark, '')
        self.assertEqual(text, '알 수 없는 표기')

    def test_종류가_있어야_마크를_켠다(self):
        from v1.label.services.ocr_apply import apply_recycling_mark

        user = User.objects.create_user(username='recycle', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='샐러드')

        apply_recycling_mark(label, '', '알 수 없는 표기')
        label.refresh_from_db()
        self.assertEqual(label.prv_recycling_mark_enabled, 'N')
        self.assertEqual(label.prv_recycling_mark_text, '알 수 없는 표기')

        apply_recycling_mark(label, '비닐(PP)', '비닐류 PP')
        label.refresh_from_db()
        self.assertEqual(label.prv_recycling_mark_enabled, 'Y')
        self.assertEqual(label.prv_recycling_mark_type, '비닐(PP)')

    def test_읽은_종류가_검증과_맞물린다(self):
        """저장한 종류를 포장재질 대조 검증이 실제로 본다."""
        from v1.label.services.ocr_apply import apply_recycling_mark
        from v1.label.services.validation_service import check_recycling_mark

        user = User.objects.create_user(username='recycle2', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='샐러드',
                                       frmlc_mtrqlt='PET(용기, 리드지), PE(드레싱)')
        apply_recycling_mark(label, '비닐(PP)', '비닐류 PP')
        label.refresh_from_db()
        # PP 마크인데 포장재질에 PP 가 없다 -> 검증이 잡아야 한다
        self.assertTrue(check_recycling_mark(label))


class OcrImagePayloadTests(TestCase):
    """
    큰 사진은 조각으로 나눠 보낸다.

    detail:high 는 이미지를 2048 박스에 맞춘 뒤 짧은 변을 768px 로 맞춘다.
    아무리 큰 사진을 보내도 모델이 보는 해상도는 거기서 멈춘다. 작업지시서처럼
    라벨이 화면의 일부인 사진은 본문 한 줄이 5px 가 되어 읽히지 않고, 그러면
    모델이 그럴듯한 값을 지어낸다. 실제로 원재료명과 주의사항을 통째로
    다른 제품 것으로 채운 일이 있었다.
    """

    def _image(self, width, height):
        import io as _io
        from PIL import Image

        buf = _io.BytesIO()
        Image.new('RGB', (width, height), 'white').save(buf, format='PNG')
        buf.seek(0)
        return buf

    def test_큰_사진은_전체와_조각을_함께_보낸다(self):
        from v1.label.services.ocr_service import build_image_payload

        images = build_image_payload(self._image(2585, 1755))
        self.assertEqual(len(images), 5, '전체 1장 + 2x2 조각 4장')

    def test_작은_사진은_나누지_않는다(self):
        from v1.label.services.ocr_service import build_image_payload

        self.assertEqual(len(build_image_payload(self._image(900, 600))), 1)

    def test_조각이_겹친다(self):
        """경계에 걸친 줄이 양쪽에서 잘리면 안 된다."""
        from v1.label.services import ocr_service

        self.assertGreater(ocr_service.TILE_OVERLAP, 0)

    def test_투명_이미지도_처리한다(self):
        """PNG 는 RGBA 로 온다. 변환 없이 JPEG 로 저장하면 죽는다."""
        import io as _io
        from PIL import Image
        from v1.label.services.ocr_service import build_image_payload

        buf = _io.BytesIO()
        Image.new('RGBA', (1600, 1200), (255, 255, 255, 0)).save(buf, format='PNG')
        buf.seek(0)
        self.assertEqual(len(build_image_payload(buf)), 5)

    def test_지어내지_말라는_지시가_있다(self):
        """
        읽을 수 없을 때 값을 만들어 내면 법적 표시물에 그대로 들어간다.
        빈 값이 잘못된 값보다 낫다.
        """
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('지어내지', SYSTEM_PROMPT)
        self.assertIn('빈 값이 잘못된 값보다 낫다', SYSTEM_PROMPT)

    def test_모델을_설정으로_바꿀_수_있다(self):
        from django.conf import settings

        self.assertTrue(hasattr(settings, 'OCR_MODEL'))


class OcrLearningTests(TestCase):
    """
    판독 교정을 쌓아 다음 판독에 되먹이는 고리.

    지금까지 이 기록이 한 건도 없었다. 그래서 "무엇을 얼마나 틀리는지" 를 셀 수
    없었고, 프롬프트를 고쳐도 나아졌는지 알 수 없었다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='learn', password='x')
        from django.core.cache import cache
        cache.clear()

    def _record(self, field, ocr, final, times=1):
        from v1.label.services.ocr_learning import record
        for _ in range(times):
            record(self.user, field, ocr, final)

    def test_고친_것과_그대로_쓴_것을_모두_남긴다(self):
        from v1.common.models import OcrCorrection

        self._record('prdlst_nm', '삼진', '삼립')
        self._record('prdlst_dcnm', '즉석섭취식품', '즉석섭취식품')

        self.assertEqual(OcrCorrection.objects.count(), 2)
        self.assertTrue(OcrCorrection.objects.get(field='prdlst_nm').corrected)
        self.assertFalse(OcrCorrection.objects.get(field='prdlst_dcnm').corrected)

    def test_정답률을_항목별로_센다(self):
        from v1.label.services.ocr_learning import accuracy_stats

        self._record('pog_daycnt', '주요사항 별도표기일까지', '별도표기일까지', times=3)
        self._record('pog_daycnt', '별도표기일까지', '별도표기일까지', times=1)
        self._record('prdlst_nm', '더블치즈', '더블치즈', times=4)

        stats = {s['field']: s for s in accuracy_stats()}
        self.assertEqual(stats['pog_daycnt']['total'], 4)
        self.assertEqual(stats['pog_daycnt']['corrected'], 3)
        self.assertEqual(stats['pog_daycnt']['rate'], 25.0)
        self.assertEqual(stats['prdlst_nm']['rate'], 100.0)
        # 정답률이 낮은 항목이 앞에 온다
        self.assertEqual(accuracy_stats()[0]['field'], 'pog_daycnt')

    def test_두_번_이상_반복된_실수만_힌트가_된다(self):
        """한 번뿐인 교정은 그 라벨 사정일 수 있어 일반화하면 해롭다."""
        from v1.label.services.ocr_learning import build_hints

        self._record('bssh_nm', '삼진', '삼립', times=1)
        self.assertEqual(build_hints(), [])

        self._record('bssh_nm', '삼진', '삼립', times=1)
        hints = build_hints()
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]['field'], 'bssh_nm')
        self.assertEqual(hints[0]['count'], 2)

    def test_긴_값은_힌트로_쓰지_않는다(self):
        """원재료명 300자를 프롬프트에 통째로 넣을 수 없다."""
        from v1.label.services.ocr_learning import build_hints

        self._record('rawmtrl_nm', '가' * 300, '나' * 300, times=3)
        self.assertEqual(build_hints(), [])

    def test_힌트가_프롬프트_문단이_된다(self):
        from v1.label.services.ocr_learning import hints_text

        self._record('bssh_nm', '삼진 청주공장', '삼립 청주공장', times=2)
        text = hints_text(use_cache=False)
        self.assertIn('bssh_nm', text)
        self.assertIn('삼립 청주공장', text)
        self.assertIn('그대로 쓰라는 뜻이 아니다', text)

    def test_쌓인_게_없으면_프롬프트가_그대로다(self):
        from v1.label.services.ocr_learning import hints_text

        self.assertEqual(hints_text(use_cache=False), '')

    def test_판독이_힌트를_붙여_부른다(self):
        from v1.label.services.ocr_learning import invalidate
        from v1.label.services.ocr_service import SYSTEM_PROMPT, learned_hints

        # 기본 프롬프트에 없는 값을 써야 "덧붙였다" 를 확인할 수 있다
        self._record('bssh_nm', '가나다식품', '가나다에프엔비', times=2)
        invalidate()
        self.assertIn('가나다에프엔비', learned_hints())
        # 원래 프롬프트는 건드리지 않는다 (덧붙일 뿐)
        self.assertNotIn('가나다에프엔비', SYSTEM_PROMPT)

    def test_힌트_조회가_실패해도_판독은_계속된다(self):
        from unittest.mock import patch
        from v1.label.services.ocr_service import learned_hints

        with patch('v1.label.services.ocr_learning.hints_text',
                   side_effect=RuntimeError('DB 장애')):
            self.assertEqual(learned_hints(), '')

    def test_관찰된_오류_유형이_프롬프트에_있다(self):
        """실제 라벨에서 반복된 실수들. 프롬프트에서 사라지면 다시 그렇게 된다."""
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        for phrase in ['작업지시서', '항목명을 값에 넣지', '혼입', '고유명사']:
            self.assertIn(phrase, SYSTEM_PROMPT, f'"{phrase}" 규칙이 빠졌다')


class OcrVariantComparisonTests(TestCase):
    """
    영역 선택과 사진 전체를 나눠 재는 고리.

    나눠 재지 않으면 "영역을 고르는 게 나은가" 를 영영 인상으로만 답하게 된다.
    실제로 두 번 돌려 본 결과가 서로 엇갈렸다 - 한 항목은 이쪽이, 다른 항목은
    저쪽이 나았다. 표본 두 개로는 못 정한다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='variant', password='x')

    def _rec(self, field, ocr, final, variant='', model='', times=1):
        from v1.label.services.ocr_learning import record
        for _ in range(times):
            record(self.user, field, ocr, final, variant=variant, model=model)

    def test_방식별로_묶어_센다(self):
        from v1.label.services.ocr_learning import accuracy_stats

        self._rec('rawmtrl_nm', 'A', 'A', variant='crop', times=3)
        self._rec('rawmtrl_nm', 'A', 'B', variant='crop', times=1)
        self._rec('rawmtrl_nm', 'A', 'B', variant='whole', times=3)

        stats = {s['key']: s for s in accuracy_stats(group='variant')}
        self.assertEqual(stats['crop']['rate'], 75.0)
        self.assertEqual(stats['whole']['rate'], 0.0)

    def test_모델별로도_묶는다(self):
        from v1.label.services.ocr_learning import accuracy_stats

        self._rec('cautions', 'A', 'A', model='gpt-4o', times=4)
        self._rec('cautions', 'A', 'B', model='gpt-4o-mini', times=2)

        stats = {s['key']: s for s in accuracy_stats(group='model')}
        self.assertEqual(stats['gpt-4o']['rate'], 100.0)
        self.assertEqual(stats['gpt-4o-mini']['rate'], 0.0)

    def test_한쪽만_걸러_볼_수_있다(self):
        from v1.label.services.ocr_learning import accuracy_stats

        self._rec('bssh_nm', 'A', 'A', variant='crop', times=2)
        self._rec('bssh_nm', 'A', 'B', variant='whole', times=2)

        only_crop = accuracy_stats(variant='crop')
        self.assertEqual(len(only_crop), 1)
        self.assertEqual(only_crop[0]['total'], 2)
        self.assertEqual(only_crop[0]['rate'], 100.0)

    def test_방식을_안_보내도_깨지지_않는다(self):
        from v1.label.services.ocr_learning import accuracy_stats

        self._rec('prdlst_nm', 'A', 'A')
        stats = accuracy_stats(group='variant')
        self.assertEqual(stats[0]['key'], '(없음)')


class OcrBenchmarkTests(TestCase):
    """
    정답과 대조해 점수를 내는 규칙.

    채점이 틀리면 측정 전체를 못 믿는다. 특히 "경미한 오독" 과 "통째로 지어냄"
    을 가르지 못하면 개선이 보이지 않는다.
    """

    def _score(self, expected, actual):
        from v1.label.services.ocr_benchmark import score_one
        return score_one(expected, actual)

    def test_띄어쓰기_차이는_같은_것으로_본다(self):
        score, grade = self._score('냉장(0~10 ℃)에서 보관', '냉장(0~10℃)에서  보관')
        self.assertEqual(grade, 'exact')

    def test_경미한_오독과_통째로_틀린_것을_가른다(self):
        """
        '쉬레드치즈'를 '쉐르드치즈'로 읽은 것과 지어낸 것은 다른 실패다.
        같은 칸에 넣으면 개선이 보이지 않는다.
        """
        near, close = self._score('쉬레드치즈, 양배추, 양상추', '쉐르드치즈, 양배추, 양상추')
        far, wrong = self._score('쉬레드치즈, 양배추, 양상추', '유지, 함박스테이크, 살라미')
        self.assertEqual(close, 'close')
        self.assertEqual(wrong, 'wrong')
        # 점수 차이가 실제로 크게 벌어져야 등급이 의미가 있다
        self.assertGreater(near - far, 40)

    def test_정답이_있는데_못_읽으면_0점(self):
        score, grade = self._score('별도표기일까지', '')
        self.assertEqual(score, 0.0)
        self.assertEqual(grade, 'miss')

    def test_정답이_비면_채점하지_않는다(self):
        """그 라벨에 없는 항목까지 0점 처리하면 점수가 무의미해진다."""
        score, grade = self._score('', '아무 값')
        self.assertIsNone(score)
        self.assertEqual(grade, 'skip')

    def test_전각_괄호를_맞춰_본다(self):
        _, grade = self._score('PET（용기）', 'PET(용기)')
        self.assertEqual(grade, 'exact')

    def test_판독_결과를_정답과_묶어_채점한다(self):
        from v1.label.services.ocr_benchmark import compare

        expected = {'prdlst_nm': '더블치즈 샐러드',
                    'pog_daycnt': '별도표기일까지',
                    'cautions': ''}
        ocr = {'prdlst_nm': {'value': '더블치즈 샐러드', 'confidence': 'high'},
               'pog_daycnt': {'value': None, 'confidence': 'none'},
               'cautions': {'value': '아무거나', 'confidence': 'low'}}

        result = compare(expected, ocr)
        self.assertEqual(result['counted'], 2)          # cautions 는 제외
        self.assertEqual(result['fields']['prdlst_nm']['grade'], 'exact')
        self.assertEqual(result['fields']['pog_daycnt']['grade'], 'miss')

    def test_여러_번_돌린_결과의_편차를_낸다(self):
        """
        평균만 보면 안 된다. 90점과 20점이 번갈아 나오는 항목과 늘 55점인
        항목은 전혀 다른 문제다.
        """
        from v1.label.services.ocr_benchmark import summarize

        runs = [
            {'fields': {'rawmtrl_nm': {'score': 90.0}, 'prdlst_nm': {'score': 55.0}}},
            {'fields': {'rawmtrl_nm': {'score': 20.0}, 'prdlst_nm': {'score': 55.0}}},
        ]
        rows = {r['field']: r for r in summarize(runs)}
        self.assertEqual(rows['rawmtrl_nm']['spread'], 70.0)
        self.assertEqual(rows['prdlst_nm']['spread'], 0.0)
        self.assertEqual(rows['rawmtrl_nm']['mean'], 55.0)

    def test_사진과_정답_짝을_모은다(self):
        import json as _json
        import tempfile
        from pathlib import Path

        from PIL import Image
        from v1.label.services.ocr_benchmark import load_cases

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (40, 40), 'white').save(root / 'a.jpg')
            (root / 'a.json').write_text(
                _json.dumps({'prdlst_nm': '가나다', 'crop': [1, 2, 3, 4]}),
                encoding='utf-8')
            # 짝이 없는 정답은 건너뛴다
            (root / 'b.json').write_text('{}', encoding='utf-8')

            cases = load_cases(root)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]['name'], 'a')
            self.assertEqual(cases[0]['crop'], [1, 2, 3, 4])
            self.assertNotIn('crop', cases[0]['expected'])

    def test_영역을_잘라_읽을_수_있다(self):
        import tempfile
        from pathlib import Path

        from PIL import Image
        from v1.label.services.ocr_benchmark import crop_image

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.png'
            Image.new('RGB', (200, 100), 'white').save(path)
            buf = crop_image(path, [10, 10, 50, 40])
            self.assertEqual(Image.open(buf).size, (50, 40))


class OcrReconcileTests(TestCase):
    """
    사진에서 읽은 값을 식약처 품목보고 정보와 대조한다.

    사진에서 품목보고번호가 읽히면 등록된 정보를 그대로 가져올 수 있다 — OCR 을
    거치지 않으므로 틀릴 이유가 없는 값이다. 그런데 두 입구(사진 판독 / 번호
    조회)가 서로를 몰라서, 번호가 읽혔는데도 등록 정보를 한 번도 보지 않았다.

    여기서 고정하는 것은 **말없이 덮어쓰지 않는다** 는 규칙이다. 등록 정보라고
    무조건 맞는 것도 아니다 — 포장을 바꾸고 변경 보고를 안 한 제품이 흔하다.
    """

    REPORT_NO = '20220460436160'

    def setUp(self):
        FoodItem.objects.create(
            prdlst_report_no=self.REPORT_NO,
            prdlst_nm='더블치즈&바질치킨 샐러드',
            prdlst_dcnm='즉석섭취식품',
            bssh_nm='(주)삼립식품',
            pog_daycnt='제조일로부터 5일',
            frmlc_mtrqlt='PET(용기), PE(드레싱)',
            rawmtrl_nm='양상추, 닭가슴살, 치즈',
        )

    def _ocr(self, **overrides):
        data = {'prdlst_report_no': {'value': self.REPORT_NO, 'confidence': 'high'}}
        for key, value in overrides.items():
            data[key] = ({'value': value, 'confidence': 'high'} if value
                         else {'value': None, 'confidence': 'none'})
        return data

    # ── 번호 찾기 ───────────────────────────────────────────────────────────

    def test_항목명과_띄어쓰기가_섞여_와도_찾는다(self):
        """사진에서는 "품목보고번호: 2022 0460 436160" 처럼 읽힌다."""
        from v1.label.services.ocr_reconcile import reconcile

        data = {'prdlst_report_no': {'value': '품목보고번호: 2022 0460 436160',
                                     'confidence': 'high'}}
        self.assertTrue(reconcile(data)['matched'])

    def test_확신도가_낮아_후보만_와도_찾는다(self):
        """
        후보 중 하나가 실제로 등록돼 있으면 그게 정답일 가능성이 높다.
        조회 자체가 번호를 검증해 준다.
        """
        from v1.label.services.ocr_reconcile import reconcile

        data = {'prdlst_report_no': {
            'value': None, 'confidence': 'low',
            'candidates': ['20220460436161', self.REPORT_NO]}}
        result = reconcile(data)
        self.assertTrue(result['matched'])
        self.assertEqual(result['report_no'], self.REPORT_NO)

    def test_번호가_없으면_아무것도_하지_않는다(self):
        from v1.label.services.ocr_reconcile import reconcile

        self.assertFalse(reconcile({'prdlst_nm': {'value': '아무거나'}})['matched'])

    # ── 판정 ────────────────────────────────────────────────────────────────

    def test_못_읽은_자리는_등록_정보로_채운다(self):
        from v1.label.services.ocr_reconcile import merge, reconcile

        data = self._ocr(prdlst_dcnm=None)
        result = reconcile(data)
        self.assertIn('prdlst_dcnm', result['filled'])

        merged = merge(data, result)
        self.assertEqual(merged['prdlst_dcnm']['value'], '즉석섭취식품')
        self.assertEqual(merged['prdlst_dcnm']['confidence'], 'high')
        self.assertEqual(merged['prdlst_dcnm']['source'], 'api')

    def test_두_쪽이_같으면_확신도를_올린다(self):
        """사용자가 눈으로 다시 확인해야 할 항목이 줄어든다."""
        from v1.label.services.ocr_reconcile import merge, reconcile

        data = self._ocr(prdlst_nm='더블치즈&바질치킨 샐러드')
        data['prdlst_nm']['confidence'] = 'low'
        merged = merge(data, reconcile(data))
        self.assertEqual(merged['prdlst_nm']['confidence'], 'high')
        self.assertEqual(merged['prdlst_nm']['source'], 'both')

    def test_제조원은_주소가_붙어_있어도_같다고_본다(self):
        """사진의 제조원은 "회사명 + 주소" 인데 등록 정보에는 회사명만 있다."""
        from v1.label.services.ocr_reconcile import reconcile

        data = self._ocr(bssh_nm='(주)삼립식품 서울시 성동구 성수동 1-2')
        self.assertIn('bssh_nm', reconcile(data)['agreed'])

    def test_다르면_어느_쪽도_고르지_않는다(self):
        """
        사진이 틀렸을 수도, 등록 정보가 오래됐을 수도 있다. 값은 사진 것을 두고
        둘 다 후보로 올려 사용자가 고르게 한다.
        """
        from v1.label.services.ocr_reconcile import merge, reconcile

        data = self._ocr(prdlst_nm='전혀 다른 제품명입니다')
        result = reconcile(data)
        self.assertIn('prdlst_nm', result['conflicts'])

        merged = merge(data, result)
        self.assertEqual(merged['prdlst_nm']['value'], '전혀 다른 제품명입니다')
        self.assertEqual(merged['prdlst_nm']['confidence'], 'low')
        self.assertIn('더블치즈&바질치킨 샐러드', merged['prdlst_nm']['candidates'])

    def test_원본을_건드리지_않는다(self):
        """확인 창의 재료일 뿐이다. 원본이 바뀌면 무엇이 판독값인지 알 수 없다."""
        from v1.label.services.ocr_reconcile import merge

        data = self._ocr(prdlst_dcnm=None)
        merge(data)
        self.assertIsNone(data['prdlst_dcnm']['value'])

    # ── 소비기한: 글자가 아니라 기간을 본다 ────────────────────────────────

    def test_기간이_다르면_짚는다(self):
        """
        "제조일로부터 12개월" 과 "제조일로부터 5일" 은 글자로는 66점이지만
        완전히 다른 제품이다. 글자만 견주면 이걸 놓친다.
        """
        from v1.label.services.ocr_reconcile import reconcile

        data = self._ocr(pog_daycnt='제조일로부터 12개월')
        self.assertIn('pog_daycnt', reconcile(data)['conflicts'])

    def test_단위만_다르고_기간이_같으면_같다고_본다(self):
        from v1.label.services.ocr_reconcile import _compare

        self.assertEqual(_compare('제조일로부터 1년', '제조일로부터 12개월', 'period')[1],
                         'agree')

    def test_별도표기는_어긋난_것이_아니다(self):
        """
        라벨의 "별도표기일까지" 는 날짜를 따로 찍는다는 말이지, 등록 정보와
        모순되는 게 아니다. 이걸 불일치로 울리면 매번 나오는 경고가 된다.
        """
        from v1.label.services.ocr_reconcile import reconcile

        data = self._ocr(pog_daycnt='별도표기일까지')
        self.assertNotIn('pog_daycnt', reconcile(data)['conflicts'])

    def test_원재료명은_표기가_달라도_틀렸다고_하지_않는다(self):
        """인쇄물에는 원산지·함량이 붙고 등록 정보에는 없다. 늘 벌어진다."""
        from v1.label.services.ocr_reconcile import reconcile

        data = self._ocr(
            rawmtrl_nm='양상추(국산) 40%, 닭가슴살(국내산) 30%, 자연치즈(수입산) 12%')
        self.assertNotIn('rawmtrl_nm', reconcile(data)['conflicts'])


class OcrPromptVersionTests(TestCase):
    """
    프롬프트 판을 DB 에 둔다. 켜져 있는 판은 언제나 하나뿐이어야 한다.

    표가 비어 있어도, 조회가 실패해도 판독은 그대로 돌아야 한다 — 코드에 박힌
    기본 프롬프트로 내려간다.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_켜진_판이_없으면_기본_프롬프트를_쓴다(self):
        from v1.label.services.ocr_prompt import base_prompt, resolve

        self.assertEqual(resolve(use_cache=False), base_prompt())

    def test_켜면_그_판을_쓴다(self):
        from v1.common.models import OcrPromptVersion
        from v1.label.services.ocr_prompt import resolve

        version = OcrPromptVersion.objects.create(name='판1', prompt='새 프롬프트')
        version.activate()
        self.assertEqual(resolve(use_cache=False), '새 프롬프트')

    def test_켜진_판은_언제나_하나다(self):
        from v1.common.models import OcrPromptVersion

        a = OcrPromptVersion.objects.create(name='판1', prompt='a', active=True)
        b = OcrPromptVersion.objects.create(name='판2', prompt='b')
        b.activate()

        a.refresh_from_db()
        self.assertFalse(a.active)
        self.assertTrue(OcrPromptVersion.objects.get(pk=b.pk).active)
        self.assertEqual(OcrPromptVersion.objects.filter(active=True).count(), 1)

    def test_자동_초안은_켜지지_않은_채_만들어진다(self):
        """
        아무도 안 본 프롬프트가 조용히 현업에 걸리면 안 된다. 판독 결과는 법적
        표시물에 그대로 들어간다.
        """
        from v1.common.models import OcrPromptVersion

        version = OcrPromptVersion.objects.create(
            name='자동 초안', prompt='x', auto_generated=True)
        self.assertFalse(version.active)


class OcrLabScoringTests(TestCase):
    """
    정답지 채점. 규칙은 파일로 재는 길(ocr_benchmark.py)과 같은 모듈을 쓴다 —
    두 벌로 만들면 어느 날 한쪽만 고쳐져서 두 숫자가 어긋난다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='lab', password='x')

    def test_검증된_표시사항을_정답으로_가져온다(self):
        """
        판독값이 아니라 실제로 인쇄에 쓰인 값이다. 손으로 옮겨 적다 틀리면
        정답지가 틀린다.
        """
        from v1.label.services.ocr_lab import expected_from_label

        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            prdlst_nm='제품명', content_weight='250 g (300 kcal)',
            pog_daycnt='제조일로부터 12개월',
            rawmtrl_nm_display='밀가루(밀:미국산), 설탕')
        expected = expected_from_label(label)

        self.assertEqual(expected['prdlst_nm'], '제품명')
        self.assertEqual(expected['rawmtrl_nm'], '밀가루(밀:미국산), 설탕')
        # 빈 항목은 넣지 않는다 — 채점기가 어차피 건너뛰는데 화면만 지저분해진다
        self.assertNotIn('cautions', expected)

    def test_원재료명은_표시용이_비면_참고_필드에서_가져온다(self):
        from v1.label.services.ocr_lab import expected_from_label

        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            rawmtrl_nm='정제수, 설탕')
        self.assertEqual(expected_from_label(label)['rawmtrl_nm'], '정제수, 설탕')

    def test_약한_항목은_평균과_편차를_함께_본다(self):
        """
        늘 55점인 항목과 90점·20점을 오가는 항목은 전혀 다른 문제이고, 후자가
        더 급하다 — 같은 사진을 매번 다르게 읽는다는 뜻이다.
        """
        from v1.label.services.ocr_prompt import weak_fields

        detail = {'fields': [
            {'field': '안정적', 'mean': 95, 'worst': 93, 'best': 97, 'spread': 4, 'runs': 3},
            {'field': '늘낮음', 'mean': 55, 'worst': 52, 'best': 58, 'spread': 6, 'runs': 3},
            {'field': '들쭉날쭉', 'mean': 60, 'worst': 20, 'best': 95, 'spread': 75, 'runs': 3},
        ]}
        picked = [r['field'] for r in weak_fields(detail)]
        self.assertEqual(picked[0], '들쭉날쭉')
        self.assertIn('늘낮음', picked)
        self.assertNotIn('안정적', picked)


class OcrSnapTests(TestCase):
    """
    식품유형과 알레르기는 표시기준이 정한 **목록**이 있다. 자유 문구로 받을
    이유가 없다.

    이 값들은 뒤에서 키로 쓰인다 — 식품유형은 유형별 표시항목 규칙을 찾는 키이고,
    알레르기는 원재료에서 검출한 것과 대조하는 키다. 한 글자가 어긋나면 규칙을
    못 찾고, 못 찾은 것을 화면은 조용히 넘긴다.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        FoodType.objects.create(food_group='가공식품', food_type='즉석섭취식품')
        FoodType.objects.create(food_group='가공식품', food_type='과자')

    def _data(self, **kwargs):
        return {k: {'value': v, 'confidence': 'high'} for k, v in kwargs.items()}

    def test_한_글자_차이는_목록에_맞춘다(self):
        from v1.label.services.ocr_snap import snap

        data, report = snap(self._data(prdlst_dcnm='즉석섭취식품류'))
        self.assertEqual(data['prdlst_dcnm']['value'], '즉석섭취식품')
        self.assertEqual(report[0]['field'], 'prdlst_dcnm')

    def test_무엇을_고쳤는지_남긴다(self):
        """말없이 고치면 "내가 사진에서 본 글자와 다른데?" 가 된다."""
        from v1.label.services.ocr_snap import snap, summary

        data, report = snap(self._data(prdlst_dcnm='즉석섭취식품류'))
        self.assertEqual(data['prdlst_dcnm']['snapped_from'], '즉석섭취식품류')
        self.assertIn('즉석섭취식품류', summary(report))

    def test_이미_맞으면_건드리지_않는다(self):
        from v1.label.services.ocr_snap import snap

        data, report = snap(self._data(prdlst_dcnm='즉석섭취식품'))
        self.assertEqual(report, [])
        self.assertNotIn('snapped_from', data['prdlst_dcnm'])

    def test_비슷한_것이_없으면_손대지_않는다(self):
        """목록에 없는 유형을 억지로 맞추면 판독이 맞았을 때보다 나쁘다."""
        from v1.label.services.ocr_snap import snap

        data, report = snap(self._data(prdlst_dcnm='전혀없는유형이름'))
        self.assertEqual(report, [])
        self.assertEqual(data['prdlst_dcnm']['value'], '전혀없는유형이름')

    def test_두_후보가_같은_거리면_손대지_않는다(self):
        """어느 쪽인지 알 수 없을 때 임의로 고르면 규칙을 엉뚱한 곳에서 찾는다."""
        from v1.label.services.ocr_snap import snap_one

        # "과지류" 는 "과자류" 와 "과채류" 에서 똑같이 한 글자 거리다
        snapped, _, verdict = snap_one('과지류', ['과자류', '과채류'])
        self.assertEqual(verdict, 'ambiguous')
        self.assertEqual(snapped, '과지류', '모호하면 판독값을 그대로 둔다')

    def test_짧은_이름은_한_글자만_달라도_손대지_않는다(self):
        """
        두 글자짜리 이름에서 한 글자를 고치면 절반을 바꾸는 것이다.
        "빵류" 를 "면류" 로 맞추는 일이 생긴다.
        """
        from v1.label.services.ocr_snap import snap_one

        _, _, verdict = snap_one('빵류', ['면류', '떡류'])
        self.assertEqual(verdict, 'unknown')

    def test_긴_이름은_두_글자까지_맞춘다(self):
        from v1.label.services.ocr_snap import snap_one

        snapped, _, verdict = snap_one('즉석섭취식퓸', ['즉석섭취식품', '과자류'])
        self.assertEqual(verdict, 'snapped')
        self.assertEqual(snapped, '즉석섭취식품')

    def test_원본을_건드리지_않는다(self):
        from v1.label.services.ocr_snap import snap

        original = self._data(prdlst_dcnm='즉석섭취식품류')
        snap(original)
        self.assertEqual(original['prdlst_dcnm']['value'], '즉석섭취식품류')

    # ── 알레르기 ────────────────────────────────────────────────────────────

    def test_알레르기는_항목마다_맞춘다(self):
        from v1.label.services.ocr_snap import snap_allergens

        snapped, changes = snap_allergens('우유, 대두류, 밀 함유')
        self.assertEqual(snapped, '우유, 대두, 밀')
        self.assertEqual([c['from'] for c in changes], ['대두류'])

    def test_목록에_없는_문구는_지우지_않는다(self):
        """22종 밖의 문구를 적어 두는 라벨이 있다. 지우면 정보가 사라진다."""
        from v1.label.services.ocr_snap import snap_allergens

        snapped, _ = snap_allergens('우유, 참깨오일추출물')
        self.assertIn('참깨오일추출물', snapped)

    def test_맞추고_나서_겹치면_한_번만_남긴다(self):
        from v1.label.services.ocr_snap import snap_allergens

        snapped, _ = snap_allergens('대두류, 대두')
        self.assertEqual(snapped, '대두')


class OcrHintClusteringTests(TestCase):
    """
    교정 이력을 묶어서 센다.

    예전에는 (항목, 판독값, 고친값) 세 값이 **완전히 같은** 교정만 2회 이상일 때
    힌트가 됐다. 실제 오독은 매번 조금씩 달라서 — "송정동" 을 한 번은 "성정동",
    한 번은 "송전동" 으로 읽으면 각각 1회 — 힌트가 거의 안 붙었다.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='hint', password='x')

    def _record(self, field, before, after, times=1):
        from v1.common.models import OcrCorrection

        for _ in range(times):
            OcrCorrection.objects.create(
                user=self.user, field=field, ocr_value=before,
                final_value=after, corrected=True)

    def test_판독값이_달라도_같은_정답이면_묶인다(self):
        from v1.label.services.ocr_learning import build_hints

        self._record('bssh_nm', '성정동', '송정동')
        self._record('bssh_nm', '송전동', '송정동')

        hints = build_hints()
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]['count'], 2)
        self.assertEqual(hints[0]['after'], '송정동')
        self.assertIn('성정동', hints[0]['before'])
        self.assertIn('송전동', hints[0]['before'])

    def test_한_번뿐인_교정은_힌트가_아니다(self):
        """그 라벨 사정일 수 있어 일반화하면 오히려 해롭다."""
        from v1.label.services.ocr_learning import build_hints

        self._record('bssh_nm', '성정동', '송정동')
        self.assertEqual(build_hints(), [])

    def test_띄어쓰기만_다른_것은_교정으로_세지_않는다(self):
        from v1.label.services.ocr_learning import build_hints

        self._record('prdlst_nm', '치즈 케익', '치즈케익', times=3)
        self.assertEqual(build_hints(), [])

    # ── 문자 혼동 행렬 ──────────────────────────────────────────────────────

    def test_바뀐_글자를_모아_센다(self):
        """
        값 전체를 통으로 세면 사례마다 달라 아무것도 안 남는다. 바뀐 글자만
        떼어 모으면 같은 혼동이 반복된다.
        """
        from v1.label.services.ocr_learning import char_confusions

        self._record('bssh_nm', '삼립식품', '삼진식품')
        self._record('prdlst_nm', '립스틱젤리', '진스틱젤리')

        pairs = char_confusions()
        self.assertIn({'from': '립', 'to': '진', 'count': 2}, pairs)

    def test_한_번뿐인_혼동은_넣지_않는다(self):
        from v1.label.services.ocr_learning import char_confusions

        self._record('bssh_nm', '삼립식품', '삼진식품')
        self.assertEqual(char_confusions(), [])

    def test_값을_통째로_갈아_끼운_것은_글자_혼동이_아니다(self):
        """우연히 겹친 글자쌍을 배우게 된다."""
        from v1.label.services.ocr_learning import char_confusions

        self._record('cautions', '직사광선을 피해 보관', '어린이 손이 닿지 않는 곳', times=3)
        self.assertEqual(char_confusions(), [])

    def test_두_종류의_힌트가_모두_프롬프트에_붙는다(self):
        from v1.label.services.ocr_learning import hints_text

        self._record('bssh_nm', '성정동', '송정동')
        self._record('bssh_nm', '송전동', '송정동')
        self._record('prdlst_nm', '삼립식품', '삼진식품')
        self._record('prdlst_nm', '립스틱젤리', '진스틱젤리')

        text = hints_text(use_cache=False)
        self.assertIn('송정동', text)          # 값 단위
        self.assertIn('"립"→"진"', text)       # 글자 단위

    def test_쌓인_것이_없으면_아무것도_붙이지_않는다(self):
        from v1.label.services.ocr_learning import hints_text

        self.assertEqual(hints_text(use_cache=False), '')


class PdfTextLayerTests(TestCase):
    """
    PDF 에 박혀 있는 글자를 그대로 읽는다.

    인쇄용 라벨 도안과 품목제조보고서는 대개 문서 프로그램에서 뽑은 PDF 라 글자가
    그대로 들어 있다. 지금까지는 그걸 그림으로 되돌려 모델에게 다시 읽혔다 —
    확실한 원문을 버리고 오독 가능성이 있는 경로로 돌아간 것이다.
    """

    def _pdf(self, text):
        """텍스트 레이어가 있는 PDF 를 만든다 (PyMuPDF)."""
        import tempfile

        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 100), text, fontsize=11, fontname='helv')
        path = tempfile.mktemp(suffix='.pdf')
        doc.save(path)
        doc.close()
        return path

    def test_텍스트_레이어를_읽는다(self):
        from v1.products.services.vision_service import extract_pdf_text

        path = self._pdf('Product Name: PINE SOFT-T / Manufacturer: ALGLIDIN CO LTD')
        self.assertIn('PINE SOFT-T', extract_pdf_text(path))

    def test_글자가_거의_없으면_스캔본으로_본다(self):
        """
        몇 글자를 "원문" 이라고 넘기면 모델이 그 조각을 믿고 나머지를 지어낸다.
        """
        from v1.products.services.vision_service import extract_pdf_text

        self.assertEqual(extract_pdf_text(self._pdf('x')), '')

    def test_읽지_못해도_예외를_내지_않는다(self):
        """PDF 를 못 읽었다고 문서 분석 전체가 멈추면 안 된다."""
        from v1.products.services.vision_service import extract_pdf_text

        self.assertEqual(extract_pdf_text('/없는/경로.pdf'), '')

    def test_원문이_있으면_모델에게_그것을_쓰라고_말한다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'products/services/vision_service.py'
                  ).read_text(encoding='utf-8')
        # 그림에서 다시 읽으면 원문을 넘긴 뜻이 없다
        self.assertIn('그림에서 다시 읽지 마시오', source)
        self.assertIn('extract_pdf_text(file_path', source)
        self.assertIn("meta['pdf_text_used']", source)


class LabelPhraseTests(TestCase):
    """
    주의사항·기타표시사항은 대부분 우리가 만들어 둔 상용 문구다.

    목록이 화면과 판독 두 곳에 따로 있으면 어느 날 한쪽만 고쳐진다. 한 곳에서
    가져다 쓰는지, 그리고 **없는 문구를 채우지 않는지**를 지킨다.
    """

    def test_화면_버튼과_프롬프트가_같은_목록을_쓴다(self):
        from pathlib import Path

        from django.conf import settings as dj

        from v1.label.services.label_phrases import texts_for

        html = (Path(dj.BASE_DIR) / 'templates/products/_tab_basic_info.html'
                ).read_text(encoding='utf-8')
        # 문구가 템플릿에 다시 박히면(하드코딩) 두 벌이 된다
        self.assertIn('{% quick_phrases "cautions"', html)
        self.assertIn('{% quick_phrases "additional_info"', html)
        for text in texts_for('cautions'):
            self.assertNotIn(text, html)

    def test_프롬프트에_문구가_실린다(self):
        from v1.label.services.label_phrases import texts_for
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn(texts_for('cautions')[0], SYSTEM_PROMPT)
        self.assertIn(texts_for('additional_info')[0], SYSTEM_PROMPT)

    def test_목록에서_가져와_채우지_말라고_못박는다(self):
        """
        흔한 문구를 프롬프트에 실으면 모델이 사진에 없는 것도 채우려 든다.
        그것이 곧 지어낸 값이고, 법적 표시물에 그대로 들어간다.
        """
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('사진에 없는 문구를 이 목록에서 가져와 채우지 마시오', SYSTEM_PROMPT)

    def test_거의_같은_문장은_원문으로_확정한다(self):
        from v1.label.services.label_phrases import snap_text

        value, changes = snap_text('cautions', '뜨거우니 화상에 주의하시기바랍니다.')
        self.assertEqual(value, '뜨거우니 화상에 주의하시기 바랍니다.')
        self.assertEqual(len(changes), 1)

    def test_한_줄에_이어_적은_문장도_따로_맞춘다(self):
        from v1.label.services.label_phrases import snap_text

        value, changes = snap_text(
            'cautions',
            '뜨거우니 화상에 주의하시기바랍니다. 질식의 위험이 있으니 주의하시기바랍니다.')
        self.assertEqual(len(changes), 2)
        self.assertIn('화상에 주의하시기 바랍니다', value)
        self.assertIn('질식의 위험이 있으니 주의하시기 바랍니다', value)

    def test_숫자가_다르면_맞추지_않는다(self):
        """상담 번호는 회사마다 다르다. 글자만 보면 두 문장은 98점이다."""
        from v1.label.services.label_phrases import snap_text

        original = '제품에 대한 문의 사항 및 상담은 종합상담센터 1577-9999 (유료)로 연락 주시기 바랍니다.'
        value, changes = snap_text('additional_info', original)
        self.assertEqual(value, original)
        self.assertEqual(changes, [])

    def test_다른_문장은_건드리지_않는다(self):
        from v1.label.services.label_phrases import snap_text

        original = '본 제품은 우리 공장에서만 만듭니다.'
        value, changes = snap_text('cautions', original)
        self.assertEqual(value, original)
        self.assertEqual(changes, [])

    def test_판독값도_상용_문구에_맞춘다(self):
        from v1.label.services.ocr_snap import snap

        data, report = snap({
            'cautions': {'value': '뜨거우니 화상에 주의하시기바랍니다.', 'confidence': 'high'},
        })
        self.assertEqual(data['cautions']['value'], '뜨거우니 화상에 주의하시기 바랍니다.')
        # 말없이 고치지 않는다 - 확인 창이 무엇을 바꿨는지 보여 줘야 한다
        self.assertTrue(data['cautions']['snapped_from'])
        self.assertTrue(data['cautions']['snapped_note'])
        self.assertEqual(len(report), 1)


class RawmtrlBracketTests(TestCase):
    """
    괄호는 열림과 닫힘이 짝이다. 그 규칙이 깨졌다는 것은 그 자리를 잘못 읽었다는
    뜻이라, 값을 하나하나 대조하지 않고도 다시 볼 자리를 짚을 수 있다.
    """

    def test_짝이_맞으면_아무_말도_안_한다(self):
        from v1.label.services.ocr_rawmtrl import bracket_problems

        self.assertEqual(bracket_problems('면류[밀가루(밀:미국산), 정제수], 소스'), [])

    def test_종류가_다른_괄호로_닫으면_짚는다(self):
        from v1.label.services.ocr_rawmtrl import bracket_problems

        problems = bracket_problems('정제소금(국산]')
        self.assertEqual(len(problems), 1)
        self.assertIn('혼동', problems[0])

    def test_닫히지_않은_괄호를_짚는다(self):
        from v1.label.services.ocr_rawmtrl import bracket_problems

        self.assertEqual(len(bracket_problems('면류(밀가루(밀:미국산), 정제수')), 1)

    def test_열린_적_없이_닫히면_짚는다(self):
        from v1.label.services.ocr_rawmtrl import bracket_problems

        self.assertEqual(len(bracket_problems('정제소금 국산)')), 1)

    def test_괄호_안의_쉼표로_가르지_않는다(self):
        """복합원재료가 통째로 부서진다."""
        from v1.label.services.ocr_rawmtrl import split_top_level

        self.assertEqual(
            split_top_level('면류(밀가루(밀:미국산), 정제수), 소스, 돼지고기 30%(국내산)'),
            ['면류(밀가루(밀:미국산), 정제수)', '소스', '돼지고기 30%(국내산)'])

    def test_이름과_함량과_원산지를_가른다(self):
        from v1.label.services.ocr_rawmtrl import split_token

        self.assertEqual(split_token('돼지고기 30%(국내산)'), ('돼지고기', '30%', '(국내산)'))

    def test_괄호가_깨지면_확신도를_내리고_경고를_남긴다(self):
        from v1.label.services.ocr_rawmtrl import inspect

        data, problems = inspect(
            {'rawmtrl_nm': {'value': '정제소금(국산]', 'confidence': 'high'}})
        self.assertEqual(len(problems), 1)
        self.assertEqual(data['rawmtrl_nm']['confidence'], 'low')
        self.assertTrue(data['rawmtrl_nm']['warnings'])
        # 값은 고치지 않는다 - 어느 쪽을 잘못 읽었는지는 사진을 봐야 안다
        self.assertEqual(data['rawmtrl_nm']['value'], '정제소금(국산]')


class RawmtrlAlignTests(TestCase):
    """
    등록 정보의 원재료는 원산지·복합원재료를 뺀 채 라벨과 같은 순서로 적혀 있다.
    뼈대는 등록 정보에서, 원산지·복합원재료·함량은 사진에서 가져와 합친다.
    """

    def test_이름만_등록_정보에_맞추고_순서는_사진_그대로_둔다(self):
        """
        처음에는 등록 정보 순서로 다시 늘어놓았다. 실제로 재 보니 점수가
        내려갔다 — 매칭 안 된 토막이 뒤로 밀려 순서가 흐트러지고, 등록 정보가
        최신이라는 보장도 없다. 원재료 순서는 함량 순이라 뜻이 달라진다.
        """
        from v1.label.services.ocr_rawmtrl import align_with_api

        result = align_with_api(
            '정재소금(국산), 돼지고가(국내산), 백설탕 2%',
            '돼지고기, 정제소금, 백설탕')
        self.assertEqual(result['text'], '정제소금(국산), 돼지고기(국내산), 백설탕 2%')
        self.assertEqual(len(result['renamed']), 2)
        # 순서가 다르다는 것은 알리되 고치지는 않는다
        self.assertTrue(result['reordered'])

    def test_순서가_다르면_알리기만_한다(self):
        from v1.label.services.ocr_rawmtrl import align_summary, align_with_api

        result = align_with_api('정제소금, 돼지고기, 백설탕', '돼지고기, 정제소금, 백설탕')
        self.assertEqual(result['text'], '정제소금, 돼지고기, 백설탕')
        self.assertIn('순서는 고치지 않았습니다', align_summary(result))

    def test_사진에만_있는_원재료는_제자리에_그대로_둔다(self):
        """뒤로 몰아 붙이면 순서가 통째로 흐트러진다."""
        from v1.label.services.ocr_rawmtrl import align_with_api

        result = align_with_api(
            '돼지고기(국내산), 향신료, 정제소금, 백설탕', '돼지고기, 정제소금, 백설탕')
        self.assertEqual(result['text'], '돼지고기(국내산), 향신료, 정제소금, 백설탕')
        self.assertEqual(result['ocr_only'], ['향신료'])

    def test_거의_못_찾으면_손대지_않는다(self):
        """다른 제품이거나 판독이 무너진 것이다. 합치면 없는 원재료를 인쇄한다."""
        from v1.label.services.ocr_rawmtrl import align_with_api

        self.assertIsNone(align_with_api('사과, 배, 포도', '돼지고기, 정제소금, 백설탕'))

    def test_등록_정보가_한_가지뿐이면_손대지_않는다(self):
        from v1.label.services.ocr_rawmtrl import align_with_api

        self.assertIsNone(align_with_api('돼지고기(국내산), 정제소금', '돼지고기'))

    def test_대조_결과에_합친_값이_들어간다(self):
        from v1.label.services.ocr_reconcile import merge

        data = merge(
            {'rawmtrl_nm': {'value': '정재소금(국산), 돼지고가(국내산)', 'confidence': 'high'}},
            {'matched': True, 'report_no': '1', 'fields': {
                'rawmtrl_nm': {'label': '원재료명', 'api_value': '돼지고기, 정제소금',
                               'ocr_value': '정재소금(국산), 돼지고가(국내산)',
                               'score': 50, 'verdict': 'unsure'},
            }})
        self.assertEqual(data['rawmtrl_nm']['value'], '정제소금(국산), 돼지고기(국내산)')
        # 말없이 고치지 않는다
        self.assertEqual(data['rawmtrl_nm']['snapped_from'], '정재소금(국산), 돼지고가(국내산)')
        self.assertTrue(data['rawmtrl_nm']['snapped_note'])

    def test_못_읽은_자리는_등록_정보로_채우기만_한다(self):
        """채운 값은 등록 정보 그대로다. 거기에 없는 원산지를 붙일 수 없다."""
        from v1.label.services.ocr_reconcile import merge

        data = merge(
            {'rawmtrl_nm': {'value': None, 'confidence': 'none'}},
            {'matched': True, 'report_no': '1', 'fields': {
                'rawmtrl_nm': {'label': '원재료명', 'api_value': '돼지고기, 정제소금',
                               'ocr_value': '', 'score': 0, 'verdict': 'filled'},
            }})
        self.assertEqual(data['rawmtrl_nm']['value'], '돼지고기, 정제소금')
        self.assertNotIn('snapped_from', data['rawmtrl_nm'])


class OcrLabScreenTests(TestCase):
    """
    관리자 화면은 **무엇을 하는 곳인지 화면 안에서** 알 수 있어야 한다.
    문서를 따로 열어야 알 수 있으면 아무도 안 읽는다.
    """

    def _html(self):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / 'templates/label/ocr_lab.html'
                ).read_text(encoding='utf-8')

    def test_메뉴마다_사용법이_붙어_있다(self):
        html = self._html()
        self.assertEqual(html.count('<details class="lab-help">'), 4)

    def test_이_방식이_AI_개발의_어느_단계인지_설명한다(self):
        html = self._html()
        self.assertIn('평가 주도 개발', html)
        self.assertIn('데이터 라벨링', html)
        self.assertIn('오프라인 평가', html)

    def test_정답지_사진을_확대할_수_있다(self):
        """정답은 사진을 보고 손으로 적는다. 안 읽히면 정답지가 안 만들어진다."""
        from pathlib import Path

        from django.conf import settings as dj

        html = self._html()
        self.assertIn('js/products/photo_viewer.js', html)
        js = (Path(dj.BASE_DIR) / 'static/js/label/ocr_lab.js'
              ).read_text(encoding='utf-8')
        self.assertIn('window.photoViewerLayout', js)


class OcrBoxTests(TestCase):
    """
    읽은 자리를 받고, 되돌리고, 채점한다.

    값과 위치는 **따로** 판정한다. 좌표가 틀렸다고 값을 버리지 않고, 위치가
    맞았다고 값을 믿지도 않는다.
    """

    def test_조각_좌표를_원본_좌표로_되돌린다(self):
        """조각을 우리가 잘랐으니 이 계산은 확실하다."""
        from v1.label.services.ocr_boxes import to_original

        # 오른쪽 아래 조각 (원본 2000x1000 의 (1000,500)~(2000,1000))
        region = (1000, 500, 2000, 1000)
        # 그 조각의 한가운데 절반
        self.assertEqual(to_original((250, 250, 500, 500), region),
                         [1250, 625, 500, 250])

    def test_전체_사진은_그대로_옮겨진다(self):
        from v1.label.services.ocr_boxes import to_original

        self.assertEqual(to_original((0, 0, 1000, 1000), (0, 0, 800, 600)),
                         [0, 0, 800, 600])

    def test_상자를_못_주면_없는_채로_둔다(self):
        """없는 좌표를 지어내면 사람을 엉뚱한 데로 보낸다."""
        from v1.label.services.ocr_boxes import attach

        regions = [{'box': (0, 0, 100, 100), 'label': '사진 전체'}]
        data, found = attach({'prdlst_nm': {'value': '가나다', 'confidence': 'high'}},
                             regions)
        self.assertEqual(found, 0)
        self.assertNotIn('box', data['prdlst_nm'])
        # 값은 그대로 살아 있어야 한다
        self.assertEqual(data['prdlst_nm']['value'], '가나다')

    def test_망가진_좌표는_버린다(self):
        from v1.label.services.ocr_boxes import parse_box

        self.assertIsNone(parse_box(None))
        self.assertIsNone(parse_box([1, 2, 3]))
        self.assertIsNone(parse_box([10, 10, 0, 50]))       # 크기 0
        self.assertIsNone(parse_box(['a', 'b', 'c', 'd']))
        self.assertEqual(parse_box([10, 20, 30, 40]), (10, 20, 30, 40))

    def test_이미지_밖으로_나간_상자를_잘라_넣는다(self):
        from v1.label.services.ocr_boxes import parse_box

        # 오른쪽으로 넘겨 온 상자는 이미지 끝에서 멈춘다
        self.assertEqual(parse_box([900, 900, 400, 400]), (900, 900, 100, 100))

    def test_어느_조각에서_읽었는지_남긴다(self):
        from v1.label.services.ocr_boxes import attach

        regions = [
            {'box': (0, 0, 200, 200), 'label': '사진 전체'},
            {'box': (100, 100, 200, 200), 'label': '조각 오른쪽 아래'},
        ]
        data, found = attach(
            {'pog_daycnt': {'value': 'x', 'img': 1, 'bbox': [0, 0, 500, 500]}},
            regions)
        self.assertEqual(found, 1)
        self.assertEqual(data['pog_daycnt']['box'], [100, 100, 50, 50])
        self.assertEqual(data['pog_daycnt']['box_from'], '조각 오른쪽 아래')
        # 원본 응답의 임시 키는 남기지 않는다 - 화면과 채점이 볼 것은 box 뿐이다
        self.assertNotIn('bbox', data['pog_daycnt'])
        self.assertNotIn('img', data['pog_daycnt'])

    def test_겹치는_정도로_잰다(self):
        from v1.label.services.ocr_boxes import iou

        self.assertEqual(iou([0, 0, 100, 100], [0, 0, 100, 100]), 100)
        self.assertEqual(iou([0, 0, 100, 100], [200, 200, 100, 100]), 0)
        # 절반만 겹치면 합집합이 1.5배라 33%
        self.assertEqual(iou([0, 0, 100, 100], [50, 0, 100, 100]), 33)

    def test_사진_전체를_상자로_주면_만점이_아니다(self):
        """한쪽이 다른 쪽을 품기만 해도 만점인 방식은 이 답에 100점을 준다."""
        from v1.label.services.ocr_boxes import iou

        self.assertLess(iou([0, 0, 2000, 1500], [100, 100, 200, 60]), 5)

    def test_정답_위치를_안_적은_항목은_채점에서_뺀다(self):
        """"위치를 모른다" 와 "위치가 틀렸다" 는 다르다."""
        from v1.label.services.ocr_boxes import score

        out = score({'prdlst_nm': [0, 0, 100, 100]},
                    {'prdlst_nm': {'box': [0, 0, 100, 100]},
                     'pog_daycnt': {'box': [500, 500, 50, 50]}})
        self.assertEqual(len(out['fields']), 1)
        self.assertEqual(out['mean'], 100.0)

    def test_상자를_못_준_항목은_0점이고_따로_센다(self):
        from v1.label.services.ocr_boxes import score

        out = score({'prdlst_nm': [0, 0, 100, 100]},
                    {'prdlst_nm': {'value': '가나다'}})
        self.assertEqual(out['mean'], 0.0)
        self.assertEqual(out['missing'], ['prdlst_nm'])

    def test_다시_읽을_영역에_여백을_붙인다(self):
        """딱 잘라 보내면 항목명이 잘려 무슨 항목인지 모른다."""
        from v1.label.services.ocr_boxes import pad

        x, y, w, h = pad([500, 500, 100, 100], 2000, 2000)
        self.assertLess(x, 500)
        self.assertGreater(w, 100)

    def test_여백을_붙여도_사진_밖으로_나가지_않는다(self):
        from v1.label.services.ocr_boxes import pad

        self.assertEqual(pad([0, 0, 100, 100], 100, 100), [0, 0, 100, 100])


class OcrBoxPromptTests(TestCase):
    """
    위치를 물어보는 것은 **기본이 꺼져 있어야 한다.**

    좌표를 요구하면 항목마다 숫자 네 개를 더 뱉게 되고 그만큼 값에 쓸 주의가
    갈린다. 값이 본질이고 위치는 편의다.
    """

    def test_평소_판독에는_좌표를_묻지_않는다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        self.assertIn('want_boxes=False', source)

    def test_좌표는_정규화해서_받는다(self):
        """보내기 전에 리사이즈하므로 모델이 보는 크기와 원본 크기가 다르다."""
        from v1.label.services.ocr_boxes import PROMPT_ADDENDUM

        self.assertIn('0~1000', PROMPT_ADDENDUM)
        self.assertIn('픽셀이 아니다', PROMPT_ADDENDUM)

    def test_못_짚으면_빼라고_말한다(self):
        from v1.label.services.ocr_boxes import PROMPT_ADDENDUM

        self.assertIn('bbox 를 넣지 마시오', PROMPT_ADDENDUM)
        self.assertIn('위치 때문에 값을 흐리게 하지 마시오', PROMPT_ADDENDUM)

    def test_조각마다_원본_어디인지_들고_있다(self):
        from io import BytesIO

        from PIL import Image

        from v1.label.services.ocr_service import build_image_regions

        buf = BytesIO()
        Image.new('RGB', (1600, 1200), 'white').save(buf, format='PNG')
        buf.seek(0)
        regions = build_image_regions(buf)

        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0]['box'], (0, 0, 1600, 1200))
        for region in regions:
            left, top, right, bottom = region['box']
            self.assertLess(left, right)
            self.assertLess(top, bottom)
            self.assertTrue(region['label'])

    def test_작은_사진은_조각내지_않는다(self):
        from io import BytesIO

        from PIL import Image

        from v1.label.services.ocr_service import build_image_regions

        buf = BytesIO()
        Image.new('RGB', (900, 700), 'white').save(buf, format='PNG')
        buf.seek(0)
        self.assertEqual(len(build_image_regions(buf)), 1)


class OcrTruthBoxViewTests(TestCase):
    """
    정답 위치는 관리자 화면에만 있다 — 좌표가 맞는지 재려면 정답이 필요하고,
    정답은 여기에만 있다.
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO

        from PIL import Image

        from v1.common.models import OcrTruthCase

        self.staff = User.objects.create_user(
            username='boxstaff', password='x', is_staff=True)
        buf = BytesIO()
        Image.new('RGB', (800, 600), 'white').save(buf, format='JPEG')
        self.case = OcrTruthCase.objects.create(
            name='상자 시험',
            image=SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg'),
            expected={'prdlst_nm': '가나다'},
        )
        self.client.force_login(self.staff)

    def _save(self, payload):
        import json as _json

        return self.client.post(
            f'/label/ocr-lab/truth/{self.case.pk}/save/',
            data=_json.dumps(payload), content_type='application/json')

    def test_정답_위치를_저장한다(self):
        res = self._save({'expected_boxes': {'prdlst_nm': [10, 20, 30, 40]}})
        self.assertEqual(res.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.expected_boxes, {'prdlst_nm': [10, 20, 30, 40]})

    def test_망가진_상자는_버리고_나머지는_남긴다(self):
        """반쯤 적힌 위치를 채점에 쓰면 못 찾은 것과 안 적은 것이 섞인다."""
        res = self._save({'expected_boxes': {
            'prdlst_nm': [10, 20, 30, 40],
            'pog_daycnt': [1, 2, 3],
            'cautions': None,
        }})
        self.assertEqual(res.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(list(self.case.expected_boxes), ['prdlst_nm'])

    def test_위치를_안_보내면_예전_위치를_지우지_않는다(self):
        self.case.expected_boxes = {'prdlst_nm': [1, 2, 3, 4]}
        self.case.save(update_fields=['expected_boxes'])
        self._save({'name': '이름만 바꿈'})
        self.case.refresh_from_db()
        self.assertEqual(self.case.expected_boxes, {'prdlst_nm': [1, 2, 3, 4]})

    def test_사진_크기를_함께_내려준다(self):
        """화면이 원본 픽셀 좌표를 화면 좌표로 옮기려면 이게 있어야 한다."""
        res = self.client.get(f'/label/ocr-lab/truth/{self.case.pk}/')
        self.assertEqual(res.json()['case']['image_size'], [800, 600])

    def test_영역_없이_다시_읽기를_부르면_거절한다(self):
        import json as _json

        res = self.client.post(
            f'/label/ocr-lab/truth/{self.case.pk}/reread/',
            data=_json.dumps({'field': 'prdlst_nm'}),
            content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_staff_가_아니면_들어갈_수_없다(self):
        self.client.logout()
        User.objects.create_user(username='plain', password='x')
        self.client.login(username='plain', password='x')
        res = self.client.post(f'/label/ocr-lab/truth/{self.case.pk}/locate/')
        self.assertNotEqual(res.status_code, 200)


class OcrCurrentValueTests(TestCase):
    """
    확인 창은 두 값을 견주라고 있는 표다. 한쪽을 잘라 버리면 그 이유가 사라진다.
    """

    def test_현재_값을_한_줄로_자르지_않는다(self):
        from pathlib import Path

        from django.conf import settings as dj

        css = (Path(dj.BASE_DIR) / 'static/css/products_common.css'
               ).read_text(encoding='utf-8')
        block = css.split('.ocr-current {')[1].split('}')[0]
        self.assertNotIn('nowrap', block)
        self.assertNotIn('ellipsis', block)
        # 줄바꿈이 있는 값(주의사항)은 줄바꿈째로 보여야 견줄 수 있다
        self.assertIn('pre-wrap', block)


class RecyclingMarkFixTests(TestCase):
    """
    분리배출 표시 두 가지 버그.

    ① 포장재질 "PE" 에 기타플라스틱 마크를 찍으면 검증이 어긋났다고 울었다.
       PE 는 분리배출 표시가 정한 일곱 재질에 없는 표기라 HDPE·LDPE·기타 어느
       쪽으로도 표시할 수 있는데, 호환표에 PE 가 아예 없었다.
    ② 마크를 그려 놓고 그 **옆에 읽은 문구를 통째로 또 적었다.** 마크가 이미
       하는 말을 글자로 한 번 더 쓴 것이다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='recycfix', password='x')

    def _label(self, material):
        return MyLabel.objects.create(user_id=self.user, my_label_name='시험',
                                      frmlc_mtrqlt=material)

    # ── ① 검증 ──────────────────────────────────────────────────────────────

    def test_PE_는_기타플라스틱과_어긋나지_않는다(self):
        from v1.label.services.validation_service import check_recycling_mark

        label = self._label('PE(드레싱)')
        label.prv_recycling_mark_type = '기타플라스틱'
        self.assertEqual(check_recycling_mark(label), [])

    def test_PE_는_HDPE_LDPE_로_표시해도_어긋나지_않는다(self):
        """라벨의 "PE" 는 고밀도인지 저밀도인지 가려지지 않은 표기다."""
        from v1.label.services.validation_service import check_recycling_mark

        for mark in ('플라스틱(HDPE)', '플라스틱(LDPE)'):
            label = self._label('PE')
            label.prv_recycling_mark_type = mark
            self.assertEqual(check_recycling_mark(label), [], mark)

    def test_PET_에_PE_계열_마크를_찍으면_잡는다(self):
        """
        예전에는 통과했다 - "PET" 안에 "PE" 가 들어 있어서 그냥 포함으로 보면
        걸리지 않는다. 잡아야 할 오류를 놓치는 쪽이라 더 나쁘다.
        """
        from v1.label.services.validation_service import check_recycling_mark

        label = self._label('PET(용기)')
        label.prv_recycling_mark_type = '플라스틱(LDPE)'
        self.assertTrue(check_recycling_mark(label))

    def test_PET_에_페트_마크는_통과한다(self):
        from v1.label.services.validation_service import check_recycling_mark

        label = self._label('PET(용기, 리드지)')
        label.prv_recycling_mark_type = '무색페트'
        self.assertEqual(check_recycling_mark(label), [])

    def test_한글_재질명은_붙여_써도_통과한다(self):
        """"폴리에틸렌수지" 처럼 붙여 쓰는 표기가 흔하다."""
        from v1.label.services.validation_service import check_recycling_mark

        label = self._label('폴리에틸렌수지')
        label.prv_recycling_mark_type = '플라스틱(HDPE)'
        self.assertEqual(check_recycling_mark(label), [])

    # ── ② 마크 옆 문구 ──────────────────────────────────────────────────────

    def test_마크가_하는_말을_옆에_또_적지_않는다(self):
        from v1.label.services.ocr_apply import extra_mark_text

        self.assertEqual(extra_mark_text('비닐류 PP', '비닐(PP)'), '')
        self.assertEqual(extra_mark_text('플라스틱 OTHER', '기타플라스틱'), '')

    def test_마크로_표현할_수_없는_부속만_남긴다(self):
        from v1.label.services.ocr_apply import extra_mark_text

        self.assertEqual(
            extra_mark_text('비닐류 PP / 띠지:PP, 리드지:PET', '비닐(PP)'),
            '띠지:PP, 리드지:PET')

    def test_종류를_못_정하면_읽은_문구를_그대로_남긴다(self):
        """마크를 못 그리므로 사람이 무엇을 봤는지 알아야 직접 고를 수 있다."""
        from v1.label.services.ocr_apply import extra_mark_text

        self.assertEqual(extra_mark_text('알 수 없는 표기', ''), '알 수 없는 표기')

    def test_마크를_읽어도_옆_문구가_붙지_않는다(self):
        from v1.label.services.ocr_apply import apply_recycling_mark

        label = self._label('PP')
        apply_recycling_mark(label, '비닐(PP)', '비닐류 PP')
        label.refresh_from_db()
        self.assertEqual(label.prv_recycling_mark_type, '비닐(PP)')
        self.assertEqual(label.prv_recycling_mark_enabled, 'Y')
        self.assertFalse(label.prv_recycling_mark_text)

    def test_사람이_적어_둔_문구를_지우지_않는다(self):
        """사진 한 장 읽었다고 이미 맞춰 둔 표시가 사라지면 안 된다."""
        from v1.label.services.ocr_apply import apply_recycling_mark

        label = self._label('PP')
        label.prv_recycling_mark_text = '띠지 별도 배출'
        label.save(update_fields=['prv_recycling_mark_text'])

        apply_recycling_mark(label, '비닐(PP)', '비닐류 PP')
        label.refresh_from_db()
        self.assertEqual(label.prv_recycling_mark_text, '띠지 별도 배출')


class TileLayoutTests(TestCase):
    """
    조각을 **어느 방향으로** 자르는가.

    2x2 는 한가운데를 세로로 가른다. 그런데 표시사항 본문은 폭 전체를 쓰는
    줄이라 모든 줄이 반토막 난다 — 모델이 좌우 조각을 이어 붙이다 실패하면
    원재료명 같은 긴 목록이 중간부터 무너진다.

    운영에서 그대로 재현됐다. 원재료 15개짜리 라벨에서 6개만 읽히고, 원산지가
    없는 원료에 원산지가 붙고, 없는 원료("전분")가 생겼다. 같은 사진의
    **원재료명 영역만 잘라 한 번에 읽히자 15개가 다 나왔다.**
    """

    def _image(self, width, height):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (width, height), 'white').save(buf, format='PNG')
        buf.seek(0)
        return buf

    def test_가로_띠는_줄을_끊지_않는다(self):
        from v1.label.services.ocr_service import build_image_regions

        regions = build_image_regions(self._image(2000, 1500), layout='bands')
        for region in regions[1:]:
            left, _top, right, _bottom = region['box']
            self.assertEqual((left, right), (0, 2000), '띠는 폭 전체여야 한다')

    def test_2x2_는_줄을_끊는다(self):
        """지금 방식이 무엇을 하는지 못 박아 둔다 — 견주려면 둘 다 있어야 한다."""
        from v1.label.services.ocr_service import build_image_regions

        regions = build_image_regions(self._image(2000, 1500), layout='grid')
        widths = {(r['box'][0], r['box'][2]) for r in regions[1:]}
        self.assertNotIn((0, 2000), widths)

    def test_띠는_장수가_적다(self):
        """이미지 장수가 줄면 호출 비용도 조금 내려간다."""
        from v1.label.services.ocr_service import build_image_regions

        grid = build_image_regions(self._image(2000, 1500), layout='grid')
        bands = build_image_regions(self._image(2000, 1500), layout='bands')
        self.assertEqual(len(grid), 5)
        self.assertEqual(len(bands), 3)

    def test_세로로_긴_라벨은_더_나눈다(self):
        """띠가 가로로 길어야 2x2 와 같은 배율을 받는다."""
        from v1.label.services.ocr_service import build_image_regions

        bands = build_image_regions(self._image(1200, 3000), layout='bands')
        self.assertEqual(len(bands), 4)      # 전체 + 띠 3

    def test_띠끼리_겹친다(self):
        """경계에 걸친 줄이 어느 쪽에서도 안 읽히면 안 된다."""
        from v1.label.services.ocr_service import build_image_regions

        bands = build_image_regions(self._image(2000, 1500), layout='bands')
        first, second = bands[1]['box'], bands[2]['box']
        self.assertGreater(first[3], second[1], '아래 띠가 위 띠와 겹쳐야 한다')

    def test_작은_사진은_어느_방식이든_안_나눈다(self):
        from v1.label.services.ocr_service import build_image_regions

        for layout in ('grid', 'bands'):
            self.assertEqual(
                len(build_image_regions(self._image(900, 700), layout=layout)), 1)

    def test_측정이_어느_방향으로_잘랐는지_남긴다(self):
        """남기지 않으면 어느 결과가 어느 방식이었는지 나중에 알 수 없다."""
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_lab.py'
                  ).read_text(encoding='utf-8')
        self.assertIn("'tiling': layout", source)

    def test_조각을_이어_붙이라고_지시한다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        self.assertIn('이어 붙이세요', source)
        # 이을 수 없을 때 메우지 말라고까지 말해야 한다 - 끊긴 자리를 메우려다
        # 없는 원료와 없는 원산지가 생겼다
        self.assertIn('없는 원료나 없는 원산지', source)


class RawmtrlSlashOriginTests(TestCase):
    """
    원산지를 괄호로만 쓰는 게 아니다. "소콜라겐/네덜란드산" 처럼 빗금으로
    붙이는 라벨이 흔한데, 괄호만 보면 이름과 원산지가 한 덩어리로 묶여
    등록 정보와 아무것도 맞출 수 없다.
    """

    def test_빗금_원산지를_가른다(self):
        from v1.label.services.ocr_rawmtrl import split_token

        self.assertEqual(split_token('돼지고기 95.36 %/국산'),
                         ('돼지고기', '95.36 %', '/국산'))
        self.assertEqual(split_token('소콜라겐/네덜란드산'),
                         ('소콜라겐', '', '/네덜란드산'))

    def test_괄호_표기도_그대로_된다(self):
        from v1.label.services.ocr_rawmtrl import split_token

        self.assertEqual(split_token('돼지고기 30%(국내산)'),
                         ('돼지고기', '30%', '(국내산)'))

    def test_빗금_라벨도_등록_정보와_맞춘다(self):
        """예전에는 이름에 원산지가 붙어 있어 하나도 못 맞췄다."""
        from v1.label.services.ocr_rawmtrl import align_with_api

        api = '돼지고기,돼지지방,정제수,정제소금,설탕,소금,소콜라겐'
        읽음 = ('돼지고기 95.36 %/국산,돼지지방/국산,정제수,정제소금/국산,'
                '설탕,소금,소금라겐/네덜란드산')
        out = align_with_api(읽음, api)
        self.assertIsNotNone(out)
        self.assertIn('소콜라겐/네덜란드산', out['text'])
        self.assertEqual([r['to'] for r in out['renamed']], ['소콜라겐'])


class TruncatedRawmtrlTests(TestCase):
    """
    등록 정보의 원재료를 사진에서 거의 못 찾으면 합치지 않는다. 그런데
    **판독이 중간에서 끊겼을 때가 바로 그 경우**이고, 하필 그때가 등록 정보가
    가장 필요한 순간이다. 값은 그대로 두되 끊긴 것 같다고 알린다.
    """

    API = ('돼지고기,돼지지방,정제수,정제소금,설탕,소금,소콜라겐,향신료조제품,'
           '복합조미식품,혼합제제,기타가공품,L-아스코르빈산나트륨,코치닐추출색소,'
           '아질산나트륨,기타가공품')

    def _merge(self, 읽음):
        from v1.label.services.ocr_reconcile import merge

        return merge(
            {'rawmtrl_nm': {'value': 읽음, 'confidence': 'high'}},
            {'matched': True, 'report_no': '1', 'fields': {
                'rawmtrl_nm': {'label': '원재료명', 'api_value': self.API,
                               'ocr_value': 읽음, 'score': 39,
                               'verdict': 'unsure'}}})['rawmtrl_nm']

    def test_끊긴_목록을_짚는다(self):
        읽음 = '돼지고기 95.36 %/국산,돼지복합육/국산,정제수/국산,설탕,소금/국산,전분'
        item = self._merge(읽음)
        self.assertEqual(item['value'], 읽음, '값은 건드리지 않는다')
        self.assertEqual(item['confidence'], 'low')
        self.assertIn('중간에서 끊겼을 수', item['warnings'][0])
        self.assertIn(self.API, item['candidates'])

    def test_다_읽었으면_짚지_않는다(self):
        읽음 = ('돼지고기/국산,돼지지방/국산,정제수,정제소금/국산,설탕,소금,'
                '소콜라겐/네덜란드산,향신료조제품,복합조미식품,혼합제제,기타가공품,'
                'L-아스코르빈산나트륨,코치닐추출색소,아질산나트륨,기타가공품')
        item = self._merge(읽음)
        self.assertNotIn('warnings', item)


class RecyclingMarkOrderTests(TestCase):
    """
    마크가 앞에 오는 라벨도 있고 뒤에 오는 라벨도 있다.
    앞을 무조건 마크로 보면 "OTHER / 비닐류 PP" 가 비닐(기타)로 잡히고,
    진짜 마크인 "비닐류 PP" 가 마크 옆에 인쇄할 문구로 밀려난다.
    """

    def test_마크가_뒤에_있어도_찾는다(self):
        from v1.label.services.ocr_apply import map_recycling_mark

        self.assertEqual(map_recycling_mark('OTHER / 비닐류 PP')[0], '비닐(PP)')

    def test_마크가_앞에_있어도_찾는다(self):
        from v1.label.services.ocr_apply import map_recycling_mark

        self.assertEqual(
            map_recycling_mark('비닐류 PP / 띠지:PP, 리드지:PET')[0], '비닐(PP)')

    def test_구분이_없으면_앞을_마크로_본다(self):
        from v1.label.services.ocr_apply import map_recycling_mark

        self.assertEqual(map_recycling_mark('OTHER / 띠지:PP')[0], '기타플라스틱')

    def test_마크로_쓴_도막은_옆_문구에서_뺀다(self):
        from v1.label.services.ocr_apply import extra_mark_text, map_recycling_mark

        for text in ('OTHER / 비닐류 PP', '비닐류 PP / 띠지:PP, 리드지:PET'):
            mark, _ = map_recycling_mark(text)
            self.assertNotIn('비닐류 PP', extra_mark_text(text, mark), text)


class ScoringNoiseTests(TestCase):
    """
    뜻이 같은 표기 차이에 점수를 깎으면 진짜 오독이 그 안에 묻힌다.
    """

    def test_섭씨_기호는_한_글자든_두_글자든_같은_값이다(self):
        """실제 측정에서 옳게 읽고도 89.7점으로 깎였다."""
        from v1.label.services.ocr_benchmark import score_one

        score, grade = score_one('냉동(-18 °C 이하)에서 보관', '냉동(-18 ℃ 이하)에서 보관')
        self.assertEqual(grade, 'exact')

    def test_단위_합자도_펼쳐서_견준다(self):
        from v1.label.services.ocr_benchmark import score_one

        self.assertEqual(score_one('500㎖', '500ml')[1], 'exact')
        self.assertEqual(score_one('1㎏', '1kg')[1], 'exact')

    def test_표시할_때는_사진에_적힌_글자_그대로_둔다(self):
        """사람에게는 원문을 보여 줘야 무엇을 읽었는지 알 수 있다."""
        from v1.label.services.ocr_benchmark import normalize

        self.assertIn('℃', normalize('냉동(-18 ℃ 이하)'))


class AllergenSuffixTests(TestCase):
    """
    "○○ 함유" 의 "함유" 를 떼는 일이 조용히 버려지고 있었다.

    알레르기는 뒤에서 **키로 쓰인다** — 원재료에서 검출한 것과 대조하는 키다.
    "쇠고기 함유" 는 어느 목록에서도 안 찾힌다.
    """

    def test_함유를_뗀다(self):
        from v1.label.services.ocr_snap import snap

        data, report = snap(
            {'allergens': {'value': '돼지고기, 쇠고기 함유', 'confidence': 'high'}})
        self.assertEqual(data['allergens']['value'], '돼지고기, 쇠고기')
        self.assertEqual(len(report), 1)

    def test_목록_대조가_필요_없을_때도_뗀다(self):
        """
        예전에는 목록에 맞춘 것이 하나도 없으면(changes 가 비면) 결과를 통째로
        버렸다. 두 물질 다 목록에 그대로 있는 흔한 경우가 그렇다.
        """
        from v1.label.services.ocr_snap import snap_allergens

        value, changes = snap_allergens('우유, 대두 함유')
        self.assertEqual(value, '우유, 대두')
        self.assertEqual(changes, [])

    def test_이미_깨끗하면_건드리지_않는다(self):
        from v1.label.services.ocr_snap import snap

        data, report = snap(
            {'allergens': {'value': '우유, 대두', 'confidence': 'high'}})
        self.assertEqual(report, [])
        self.assertNotIn('snapped_from', data['allergens'])


class MeasurementHonestyTests(TestCase):
    """
    측정이 조용히 거짓말을 하면 안 된다.

    회차 3 을 걸었는데 429(분당 토큰 한도)로 두 번이 죽고 한 번만 돌았다.
    그런데 표에는 "3회" 로 뜨고 편차가 0 이었다 — "안정적" 으로 읽힌다.
    실제로는 한 번밖에 안 잰 것이다.
    """

    def test_분당_한도를_만나면_기다렸다_다시_부른다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        self.assertIn("max_retries=getattr(settings, 'OCR_MAX_RETRIES'", source)

    def test_실제로_성공한_회차를_남긴다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_lab.py'
                  ).read_text(encoding='utf-8')
        self.assertIn("runs=done or runs", source)
        self.assertIn("'runs_asked': runs", source)

    def test_못_돈_회차를_화면이_알린다(self):
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/ocr_lab.js'
              ).read_text(encoding='utf-8')
        self.assertIn('회만 성공', js)


class CrossContaminationPromptTests(TestCase):
    """
    "…혼입가능성 있음" 문장이 주의사항에서 통째로 사라졌다.

    알레르기 물질은 제대로 읽혔다(100점). 같은 검은 박스를 allergens 에 쓰고
    나면 모델이 그 자리를 두 번 쓰지 않는 것이다.
    """

    def test_같은_박스를_두_번_읽으라고_말한다(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('같은 자리를 두 번 읽는 것이 맞다', SYSTEM_PROMPT)
        self.assertIn('문장은 그대로 cautions 로', SYSTEM_PROMPT)


class ReportNoNearMissTests(TestCase):
    """
    품목보고번호는 열대여섯 자리라 **한 자리만 틀려도 조회가 통째로 실패**한다.

    실제로 "19980448010-697" 을 "199804480101-697" 로 읽어(1 이 하나 더 붙음)
    등록 정보를 못 찾았다. 화면에는 "대조하면 +0점" 만 떴는데, 그건 "대조가
    도움이 안 된다" 로 읽힌다 — 실제로는 조회가 아예 안 된 것이고, 번호만
    고치면 제품명·제조원·원재료명을 전부 대조할 수 있다.
    """

    def setUp(self):
        from v1.label.models import FoodItem

        self.item = FoodItem.objects.create(
            prdlst_report_no='19980448010-697',
            prdlst_nm='삼립베이커리소시지',
            bssh_nm='㈜삼립 서천공장',
            prdlst_dcnm='소시지',
        )

    def test_한_자리가_더_붙어도_찾는다(self):
        from v1.label.services.ocr_reconcile import find_food_item

        found, number = find_food_item({
            'prdlst_report_no': {'value': '199804480101-697'},
            'prdlst_nm': {'value': '삼립베이커리소시지'},
        })
        self.assertIsNotNone(found)
        self.assertEqual(number, '19980448010-697')

    def test_한_자리가_빠져도_찾는다(self):
        from v1.label.services.ocr_reconcile import find_food_item

        found, _ = find_food_item({
            'prdlst_report_no': {'value': '1998044801-697'},
            'prdlst_nm': {'value': '삼립베이커리소시지'},
        })
        self.assertIsNotNone(found)

    def test_한_자리가_달라도_찾는다(self):
        from v1.label.services.ocr_reconcile import find_food_item

        found, _ = find_food_item({
            'prdlst_report_no': {'value': '19980448010-627'},
            'prdlst_nm': {'value': '삼립베이커리소시지'},
        })
        self.assertIsNotNone(found)

    def test_제품명도_제조원도_안_맞으면_채택하지_않는다(self):
        """
        번호 하나로 정하면 안 된다. 열다섯 자리 중 하나를 바꾸면 다른 회사의
        멀쩡한 제품에 맞을 수 있고, 그 등록 정보를 끌어오면 사진에 없는 값이
        들어온다.
        """
        from v1.label.services.ocr_reconcile import find_food_item

        found, _ = find_food_item({
            'prdlst_report_no': {'value': '199804480101-697'},
            'prdlst_nm': {'value': '전혀 다른 과자'},
            'bssh_nm': {'value': '다른회사'},
        })
        self.assertIsNone(found)

    def test_교차_검증할_값이_없으면_채택하지_않는다(self):
        from v1.label.services.ocr_reconcile import find_food_item

        found, _ = find_food_item(
            {'prdlst_report_no': {'value': '199804480101-697'}})
        self.assertIsNone(found)

    def test_두_자리가_틀리면_손대지_않는다(self):
        from v1.label.services.ocr_reconcile import find_food_item

        found, _ = find_food_item({
            'prdlst_report_no': {'value': '199804488811-697'},
            'prdlst_nm': {'value': '삼립베이커리소시지'},
        })
        self.assertIsNone(found)

    def test_고쳐_찾았으면_그_사실을_밝힌다(self):
        """말없이 다른 번호의 정보를 끌어오면 안 된다."""
        from v1.label.services.ocr_reconcile import reconcile

        out = reconcile({
            'prdlst_report_no': {'value': '199804480101-697'},
            'prdlst_nm': {'value': '삼립베이커리소시지'},
        })
        self.assertTrue(out['matched'])
        self.assertTrue(out['corrected_report_no'])
        self.assertIn('한 자리만 다른', out['summary'])

    def test_못_찾으면_조용히_넘어가지_않는다(self):
        from v1.label.services.ocr_reconcile import reconcile

        out = reconcile({'prdlst_report_no': {'value': '99999999999-999'}})
        self.assertFalse(out['matched'])
        self.assertIn('찾지 못했습니다', out['summary'])

    def test_번호를_아예_못_읽었으면_할_말이_없다(self):
        from v1.label.services.ocr_reconcile import reconcile

        self.assertEqual(reconcile({'prdlst_nm': {'value': '뭔가'}})['summary'], '')
