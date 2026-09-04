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
from django.urls import reverse
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

    def test_5kcal_단위로_반올림한다(self):
        """화면(processNutritionValue)과 같은 규칙이어야 한다."""
        from v1.label.services.validation_service import round_calories

        self.assertEqual(round_calories(276.66), 275)   # 87 g x 318/100
        self.assertEqual(round_calories(277.5), 280)    # 5 는 위로 (JS Math.round)
        self.assertEqual(round_calories(282.5), 285)    # 파이썬 round 면 280 이 된다
        self.assertEqual(round_calories(1240), 1240)

    def test_고치라는_숫자가_화면이_그리는_숫자와_같다(self):
        """
        검증이 반올림을 안 겪으면 앱이 절대 만들지 않는 숫자를 요구하게 된다.
        운영에서 "277 kcal 입니다" 라고 했는데 표에는 275 가 찍혀 있었다.
        고치라는 대로 고쳐도 경고가 안 사라진다.
        """
        issues = self._issues(content_weight='87 g (500 kcal)', calories='318')
        self.assertEqual(len(issues), 1)
        self.assertIn('275', issues[0]['message'])
        self.assertNotIn('277', issues[0]['message'])

    def test_총량이_커도_눈이_멀지_않는다(self):
        """
        허용오차가 5% 였을 때는 1,240 kcal 짜리에서 ±62 를 통과시켰다.
        자릿수를 하나 잘못 적어도 지나갈 수 있었다.
        """
        self.assertEqual(len(self._issues(content_weight='800 g (1290 kcal)',
                                          calories='155')), 1)

    def test_무료_검증에_물려_있다(self):
        from v1.label.services.validation_service import _CHECKS
        self.assertIn('check_calorie_consistency', {c.__name__ for c in _CHECKS})


class AllergenDeclarationMatchTests(TestCase):
    """
    선언한 알레르기 성분을 **선언한 것으로 알아보는가.**

    예전에는 쉼표로 자른 뒤 문자열이 정확히 같은지 봤다. 그래서 표시기준이
    권장하는 표기인 "알류(달걀)" 이 표준 명칭 "알류" 와 다른 것으로 잡혀
    **규정대로 적을수록 미선언 경고가 나왔다.** 운영에서 그대로 나왔다 -
    "알류(달걀), 우유, 대두, 밀" 중 괄호가 붙은 알류만 누락으로 보고됐다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='allergen', password='x')

    def _issues(self, rawmtrl, allergens):
        from v1.label.services.validation_service import check_allergens
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            rawmtrl_nm_display=rawmtrl, allergens=allergens)
        return check_allergens(label)

    RAW = '밀가루, 달걀, 탈지분유, 대두유, 설탕'

    def test_괄호_주석이_붙어도_선언으로_본다(self):
        self.assertEqual(self._issues(self.RAW, '알류(달걀), 우유, 대두, 밀'), [])

    def test_함유_꼬리말이_붙어도_선언으로_본다(self):
        self.assertEqual(self._issues(self.RAW, '알류, 우유, 대두, 밀 함유'), [])

    def test_띄어쓰기가_달라도_선언으로_본다(self):
        self.assertEqual(self._issues(self.RAW, '알류 (달걀) , 우유 , 대두 , 밀'), [])

    def test_한_줄로_적어도_선언으로_본다(self):
        self.assertEqual(self._issues(self.RAW, '알류(달걀)·우유·대두·밀 함유'), [])

    def test_진짜_빠지면_그대로_잡는다(self):
        """오탐을 막느라 실제 누락까지 놓치면 안 된다."""
        issues = self._issues(self.RAW, '우유, 대두, 밀')
        self.assertEqual(len(issues), 1)
        self.assertIn('알류', issues[0]['message'])

    def test_아무것도_선언하지_않으면_전부_잡는다(self):
        issues = self._issues(self.RAW, '')
        self.assertEqual(len(issues), 1)
        for name in ('알류', '우유', '대두', '밀'):
            self.assertIn(name, issues[0]['message'])


class OcrNutritionBasisTests(TestCase):
    """
    사진에서 읽은 영양성분표를 **어떤 기준으로 저장하는가.**

    라벨의 표는 그 표가 밝힌 기준으로 인쇄돼 있고, MyLabel 의 영양성분 칸은
    언제나 100 g 당이다. 환산 없이 그대로 넣으면 그 약속이 깨진다.
    """

    def test_총_내용량_기준을_100g_당으로_바꾼다(self):
        from v1.label.services.ocr_apply import to_per_100

        rows = [{'field': 'calories', 'value': '318', 'unit': 'kcal'},
                {'field': 'natriums', 'value': '630', 'unit': 'mg'}]
        out = to_per_100(rows, '87')
        self.assertEqual(out[0]['value'], '365.52')     # 318 x 100/87
        self.assertEqual(out[1]['value'], '724.14')
        self.assertEqual(out[0]['unit'], 'kcal')        # 단위는 그대로

    def test_100g_당_이면_건드리지_않는다(self):
        from v1.label.services.ocr_apply import to_per_100

        rows = [{'field': 'calories', 'value': '318', 'unit': 'kcal'}]
        self.assertEqual(to_per_100(rows, '100')[0]['value'], '318')

    def test_기준을_못_읽으면_건드리지_않는다(self):
        """기준을 모르면서 환산하면 모든 수치의 뜻이 바뀐다. 그게 더 나쁘다."""
        from v1.label.services.ocr_apply import to_per_100

        rows = [{'field': 'calories', 'value': '318', 'unit': 'kcal'}]
        for basis in (None, '', '알 수 없음', '0'):
            self.assertEqual(to_per_100(rows, basis)[0]['value'], '318')

    def test_숫자가_아니면_손대지_않는다(self):
        from v1.label.services.ocr_apply import to_per_100

        rows = [{'field': 'calories', 'value': '5kcal 미만', 'unit': 'kcal'}]
        self.assertEqual(to_per_100(rows, '87')[0]['value'], '5kcal 미만')

    def test_사진으로_채운_라벨이_열량_경고를_받지_않는다(self):
        """
        보고된 그 건이다. "총 내용량 87 g / 318 kcal" 로 인쇄된 라벨을 읽어
        넣었더니, 사진에도 내용량 칸에도 318 로 맞게 적혀 있는데 검증이
        "열량이 맞지 않습니다" 라고 했다.
        """
        from v1.label.services.ocr_apply import apply_nutrition, to_per_100
        from v1.label.services.validation_service import check_calorie_consistency

        user = User.objects.create_user(username='ocrcal', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='라벨',
                                       content_weight='87 g(318 kcal)')
        rows = [{'field': 'calories', 'value': '318', 'unit': 'kcal'}]
        apply_nutrition(label, to_per_100(rows, '87'))

        self.assertEqual(check_calorie_consistency(label), [])


class OcrGroundTextTests(TestCase):
    """
    사진에서 글자 원문만 뽑는 길 (Google Vision) — 1단계.

    이 단계의 목적은 판독을 고치는 게 아니라 **가부를 가르는 것**이다.
    OCR 이 우리 라벨(6pt 원형 스티커·곡면 용기)을 못 읽으면 그 다음이 전부
    무의미하다. 그래서 "읽히나" 를 사람 눈이 아니라 정답지로 잰다.
    """

    def _vision_response(self, text):
        from unittest.mock import Mock

        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {
            'responses': [{'fullTextAnnotation': {'text': text}}]}
        return resp

    def test_원문을_받아_온다(self):
        from unittest.mock import patch

        from v1.label.services import ocr_text

        long_text = '제품명 초코쿠키\n원재료명 밀가루(밀:미국산), 설탕, 코코아분말' * 2
        with patch.object(ocr_text, '_access_token', return_value='t'), \
             patch('requests.post', return_value=self._vision_response(long_text)):
            self.assertEqual(ocr_text.extract_text(b'\xff\xd8fake'), long_text.strip())

    def test_글자가_몇_개뿐이면_버린다(self):
        """
        도장·서명만 몇 글자 흘러나온 조각을 "사진에 이렇게 적혀 있다" 고 넘기면
        모델이 그것을 믿고 나머지를 지어낸다. PDF 경로에서 이미 겪은 일이라
        같은 가드를 둔다. 없는 원문이 나쁜 원문보다 낫다.
        """
        from unittest.mock import patch

        from v1.label.services import ocr_text

        with patch.object(ocr_text, '_access_token', return_value='t'), \
             patch('requests.post', return_value=self._vision_response('(주)가나다')):
            self.assertEqual(ocr_text.extract_text(b'x'), '')

    def test_설정이_없으면_조용히_비운다(self):
        """원문은 곁들이는 것이다. 없다고 판독이 멈추면 안 된다."""
        from django.test import override_settings

        from v1.label.services import ocr_text

        with override_settings(GOOGLE_VISION_API_KEY='',
                               GOOGLE_VISION_SERVICE_ACCOUNT_JSON='',
                               FCM_SERVICE_ACCOUNT_JSON=''):
            self.assertEqual(ocr_text.extract_text(b'x'), '')

    def test_API_키가_있으면_서비스_계정을_안_쓴다(self):
        from unittest.mock import patch

        from django.test import override_settings

        from v1.label.services import ocr_text

        long_text = '제품명 초코쿠키\n원재료명 밀가루, 설탕, 코코아분말, 정제소금' * 2
        with override_settings(GOOGLE_VISION_API_KEY='key-abc'), \
             patch.object(ocr_text, '_access_token') as token, \
             patch('requests.post', return_value=self._vision_response(long_text)) as post:
            ocr_text.extract_text(b'x')

        token.assert_not_called()
        self.assertIn('key=key-abc', post.call_args.args[0])
        self.assertNotIn('Authorization', post.call_args.kwargs['headers'])

    def test_오류_로그에_API_키를_남기지_않는다(self):
        """키가 URL 에 들어가므로 응답 본문에 섞여 나올 수 있다."""
        from unittest.mock import Mock, patch

        from django.test import override_settings

        from v1.label.services import ocr_text

        resp = Mock(status_code=400)
        resp.text = 'API key not valid: key-abc'
        with override_settings(GOOGLE_VISION_API_KEY='key-abc'), \
             patch('requests.post', return_value=resp), \
             self.assertLogs('v1.label.services.ocr_text', level='ERROR') as logs:
            self.assertEqual(ocr_text.extract_text(b'x'), '')

        joined = '\n'.join(logs.output)
        self.assertNotIn('key-abc', joined)
        self.assertIn('***', joined)

    def test_호출이_터져도_빈_문자열이다(self):
        from unittest.mock import patch

        from v1.label.services import ocr_text

        with patch.object(ocr_text, '_access_token', return_value='t'), \
             patch('requests.post', side_effect=RuntimeError('망')):
            self.assertEqual(ocr_text.extract_text(b'x'), '')

    def test_Vision_이_오류를_돌려주면_빈_문자열이다(self):
        from unittest.mock import Mock, patch

        from v1.label.services import ocr_text

        resp = Mock(status_code=200)
        resp.json.return_value = {'responses': [{'error': {'message': 'quota'}}]}
        with patch.object(ocr_text, '_access_token', return_value='t'), \
             patch('requests.post', return_value=resp):
            self.assertEqual(ocr_text.extract_text(b'x'), '')

    # ── 정답지로 재기 ────────────────────────────────────────────────────

    def test_정답이_원문에_있는지_센다(self):
        from v1.label.services.ocr_text import field_recall

        expected = {'prdlst_nm': '초코쿠키',
                    'rawmtrl_nm': '밀가루(밀:미국산), 설탕, 코코아분말',
                    'cautions': '이 제품은 알류를 사용한 제품과 같은 시설에서 제조'}
        text = ('제품명 초코쿠키\n'
                '원재료명 밀가루( 밀 : 미국산 ), 설탕, 코코아분말\n')
        rows = {r['field']: r for r in field_recall(expected, text)}

        self.assertTrue(rows['prdlst_nm']['found'])
        self.assertTrue(rows['rawmtrl_nm']['found'])   # 띄어쓰기 차이는 넘어간다
        self.assertFalse(rows['cautions']['found'])    # 원문에 없다
        self.assertTrue(rows['rawmtrl_nm']['long'])
        self.assertFalse(rows['prdlst_nm']['long'])

    def test_비어_있는_정답은_채점하지_않는다(self):
        """그 라벨에 없는 항목이지 못 읽은 항목이 아니다."""
        from v1.label.services.ocr_text import field_recall

        rows = field_recall({'prdlst_nm': '초코쿠키', 'importer_address': ''},
                            '제품명 초코쿠키')
        self.assertEqual([r['field'] for r in rows], ['prdlst_nm'])

    def test_가부는_긴_칸으로_가른다(self):
        """짧은 칸은 판독이 이미 100점이라 원문이 도울 여지가 없다."""
        from v1.label.services.ocr_text import field_recall, recall_summary

        rows = field_recall({'prdlst_nm': '초코쿠키', 'rawmtrl_nm': '밀가루, 설탕'},
                            '제품명 초코쿠키')
        summary = recall_summary(rows)
        self.assertEqual(summary['long_fields'], 1)
        self.assertLess(summary['long_recall'], 0.9)

    def test_긴_칸이_없으면_판단을_보류한다(self):
        """못 읽은 것과 잴 것이 없는 것은 다르다. 0 이 아니라 None 이다."""
        from v1.label.services.ocr_text import field_recall, recall_summary, verdict

        summary = recall_summary(field_recall({'prdlst_nm': '초코쿠키'}, '초코쿠키'))
        self.assertIsNone(summary['long_recall'])
        self.assertIn('판단할 수 없다', verdict(None))

    def test_문턱이_문장으로_나온다(self):
        from v1.label.services.ocr_text import verdict

        self.assertIn('읽힌다', verdict(0.95))
        self.assertIn('검증자로만', verdict(0.75))
        self.assertIn('접는다', verdict(0.4))

    def test_한_번_읽은_원문은_다시_부르지_않는다(self):
        """
        측정은 같은 사진을 회차 x 정답지 x 프롬프트 판 수만큼 읽는다. 매번
        Vision 을 부르면 잴수록 돈이 나가고, 원문이 회차마다 달라지면 무엇을
        재고 있는지 알 수 없게 된다.
        """
        from io import BytesIO
        from unittest.mock import patch

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from v1.common.models import OcrTruthCase
        from v1.label.services import ocr_text

        buf = BytesIO()
        Image.new('RGB', (200, 150), 'white').save(buf, format='JPEG')
        case = OcrTruthCase.objects.create(
            name='원문 시험',
            image=SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg'),
            expected={'prdlst_nm': '초코쿠키'})

        long_text = '제품명 초코쿠키\n원재료명 밀가루, 설탕, 코코아분말, 정제소금' * 2
        with patch.object(ocr_text, 'extract_text', return_value=long_text) as call:
            first = ocr_text.text_for_case(case)
            second = ocr_text.text_for_case(case)

        self.assertEqual(first, second)
        self.assertEqual(call.call_count, 1)          # 두 번째는 저장된 것을 쓴다
        case.refresh_from_db()
        self.assertEqual(case.ocr_engine, 'google')
        self.assertTrue(case.ocr_fetched_at)

    def _case_with_text(self, text, **kwargs):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from v1.common.models import OcrTruthCase

        buf = BytesIO()
        Image.new('RGB', (200, 150), 'white').save(buf, format='JPEG')
        defaults = dict(
            name='원문 시험',
            image=SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg'),
            expected={'prdlst_nm': '초코쿠키',
                      'rawmtrl_nm': '밀가루, 설탕, 코코아분말, 정제소금'},
            verified=True, ocr_text=text, ocr_engine='google')
        defaults.update(kwargs)
        return OcrTruthCase.objects.create(**defaults)

    def test_정답지_초안은_주의사항도_읽는다(self):
        """
        평소 판독은 주의사항·기타표시사항을 읽지 않는다 - 지어낸 문구가 법적
        표시물에 들어가는 위험이 크기 때문이다. 그건 **인쇄로 나가는 값**에
        대한 판단이고, 정답지는 사람이 사진을 보며 고치는 초안이다.

        여기서 안 읽으면 두 칸이 빈 채로 정답지에 쌓이고, 그러면 그 칸의
        정확도를 영원히 잴 수 없다. 지금 하는 일이 바로 그 두 칸을 되살리려는
        것인데 재는 자에 그 칸이 없으면 되살렸는지 알 방법이 없다.
        """
        from unittest.mock import patch

        from v1.label.services.ocr_lab import draft_expected

        with patch('v1.label.services.ocr_service.extract_label_from_image',
                   return_value={'success': True, 'data': {}}) as read:
            draft_expected(b'fake')

        self.assertTrue(read.call_args.kwargs['read_freetext'])

    def test_정답지_화면이_빈_칸도_보여준다(self):
        """
        예전에는 이미 값이 있는 항목만 입력 줄로 그렸다. 그래서 판독이 못
        읽은 칸은 줄 자체가 안 생겨 손으로 채울 방법이 없었다 - 주의사항·
        기타표시사항이 정확히 그 경우였고, 그 두 칸이 정답지에 영영 안
        쌓이니 정확도도 잴 수 없었다.
        """
        from v1.label.services.ocr_lab import TRUTH_FIELD_KEYS

        staff = User.objects.create_user(username='fieldstaff', password='x',
                                         is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        resp = self.client.get('/label/ocr-lab/')

        self.assertEqual(resp.status_code, 200)
        fields = resp.context['truth_fields']
        for key in ('cautions', 'additional_info', 'recycling_mark', 'pog_daycnt'):
            self.assertIn(key, fields)
        self.assertEqual(fields, list(TRUTH_FIELD_KEYS))
        # 화면이 읽어 갈 수 있게 실려 나가야 한다
        self.assertContains(resp, 'truth-fields-data')

    def test_정답지_항목_목록이_한_곳에만_있다(self):
        """
        화면이 그리는 칸과 표시사항에서 값을 가져오는 칸이 갈라지면, 한쪽에만
        있는 항목이 조용히 생긴다.
        """
        from v1.label.models import MyLabel
        from v1.label.services.ocr_lab import TRUTH_FIELD_KEYS, expected_from_label

        user = User.objects.create_user(username='truthmap', password='x')
        label = MyLabel.objects.create(
            user_id=user, my_label_name='라벨', prdlst_nm='초코쿠키',
            cautions='직사광선을 피해 보관', additional_info='고객상담실 080-000-0000')
        out = expected_from_label(label)

        self.assertEqual(out['cautions'], '직사광선을 피해 보관')
        self.assertEqual(out['additional_info'], '고객상담실 080-000-0000')
        self.assertTrue(set(out).issubset(set(TRUTH_FIELD_KEYS)))

    def test_초안_경고가_위험한_칸을_이름으로_짚는다(self):
        from unittest.mock import patch

        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO

        from PIL import Image

        staff = User.objects.create_user(username='draftstaff', password='x',
                                         is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        buf = BytesIO()
        Image.new('RGB', (300, 200), 'white').save(buf, format='JPEG')

        draft = {'prdlst_nm': '초코쿠키', 'cautions': '직사광선을 피해 보관하십시오'}
        with patch('v1.label.services.ocr_lab.draft_expected',
                   return_value=(draft, '')):
            resp = self.client.post('/label/ocr-lab/truth/', {
                'image': SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg'),
                'name': '초안 시험', 'draft': '1'})

        warning = resp.json()['warning']
        self.assertIn('cautions', warning)
        self.assertIn('지어내는', warning)

    def test_호환_문자를_같은_것으로_본다(self):
        """
        ℃(U+2103) 하나와 °C 두 글자는 같은 것이다. 이걸 안 폈더니 멀쩡한
        보관방법이 76.9 / 86.7 로 빗나갔다 - OCR 은 제대로 읽었는데도.
        """
        from v1.label.services.ocr_text import match_score

        self.assertGreaterEqual(
            match_score('냉장(0~10 ℃)에서 보관', '보관방법 냉장(0~10°C)에서 보관'), 95)
        self.assertEqual(
            match_score('냉동(-18 °C 이하)에서 보관', '보관방법 냉동(-18℃ 이하)에서 보관'), 100.0)
        # ㎎/㎖ 같은 조합 문자와 전각도 같이 정리된다
        self.assertEqual(match_score('나트륨 630 ㎎', '나트륨 630 mg'), 100.0)

    def test_영문_대소문자는_구분하지_않는다(self):
        from v1.label.services.ocr_text import match_score

        self.assertEqual(match_score('WWW.SPCSAMLIP.CO.KR',
                                     'www.spcsamlip.co.kr'), 100.0)

    def test_흩어져_인쇄된_기타표시사항을_찾아낸다(self):
        """
        기타표시사항은 서로 무관한 문구를 모아 담는 칸이고, 라벨에서는
        그 문구들이 여기저기 떨어져 인쇄된다. 이어 붙인 문자열이 연속으로
        있는지 물으면 원문에 다 있는데도 55.8 점이 나온다.
        """
        from v1.label.services.ocr_text import match_score

        value = '고객상담실 080-739-8572 (수신자 부담) www.spcsamlip.co.kr'
        # 조각 사이에 라벨의 다른 내용이 끼어 있다 — 실제 원문이 그랬다
        text = ('제품교환장소 본사 및 구입처\n부정불량식품신고는 국번없이 1399\n'
                '④ 고객상담실\n안전관리인증기준 HACCP 적용업소\n비닐류 분리배출\n'
                '080-739-8572 (수신자 부담)\n보관방법 냉동(-18℃ 이하)에서 보관\n'
                '홈페이지 www.spcsamlip.co.kr\n')

        self.assertLess(match_score(value, text), 80)                  # 연속으로는 없다
        self.assertGreaterEqual(match_score(value, text, assembled=True), 95)

    def test_흩어진_주의사항도_문장_단위로_찾아낸다(self):
        """
        주의사항도 서로 무관한 문구를 모아 담는 칸이고, 라벨에서는 사이에
        다른 주의사항이 끼어 인쇄된다. 실제로 59.1 점이 나왔다.
        """
        from v1.label.services.ocr_text import match_score

        value = ('메밀, 땅콩, 잣 혼입가능성 있음. 가급적 빨리 드시기 바랍니다. '
                 '부정.불량식품 신고는 국번없이 1399')
        text = ('쇠고기, 조개류(굴) 함유\n메밀, 땅콩, 잣 혼입가능성 있음. '
                '포장지의 끝부분만 찢은 후에 전자레인지를 돌려\n주세요.\n'
                '가급적 빨리 드시기 바랍니다.\n부정.불량식품 신고는 국번없이 1399\n')

        plain = match_score(value, text)
        self.assertGreater(match_score(value, text, assembled=True), plain)
        self.assertGreaterEqual(match_score(value, text, assembled=True), 95)

    def test_지어낸_문장은_흩어짐을_허용해도_잡힌다(self):
        """
        **이게 흩어짐 허용의 안전장치다.** 문장으로 가르기 때문에, 지어낸
        문장은 쓰인 낱말이 아무리 흔해도 문장 전체로는 원문에 안 나온다.
        낱말로 갈랐다면 주의사항에는 쓰지 못했을 것이다.
        """
        from v1.label.services.ocr_text import match_score

        text = ('메밀, 땅콩 혼입가능성 있음.\n제품을 개봉한 후에는 빨리 드십시오.\n'
                '직사광선을 피하고 서늘한 곳에 두십시오.\n')
        # 낱말은 전부 원문에 있지만 이런 문장은 라벨에 없다
        made_up = '제품을 냉장 보관하고 개봉 후에는 서늘한 곳에 두십시오.'
        self.assertLess(match_score(made_up, text, assembled=True), 80)

    def test_흩어짐_허용은_모아_담는_칸에만_쓴다(self):
        from v1.label.services.ocr_text import ASSEMBLED_FIELDS

        self.assertEqual(ASSEMBLED_FIELDS, ('cautions', 'additional_info'))
        # 한 덩어리의 값이라 흩어질 일이 없는 칸들
        self.assertNotIn('rawmtrl_nm', ASSEMBLED_FIELDS)
        self.assertNotIn('bssh_nm', ASSEMBLED_FIELDS)

    def test_문장이_없는_값은_띄어쓰기로_가른다(self):
        """연락처·주소처럼 문장이 아닌 값이 있다."""
        from v1.label.services.ocr_text import _scatter_pieces

        pieces = _scatter_pieces('고객상담실 080-739-8572 (수신자 부담)')
        self.assertIn('고객상담실', pieces)
        self.assertIn('080-739-8572', pieces)

    def test_낱말_안의_마침표로_가르지_않는다(self):
        """
        마침표는 뒤에 공백이나 끝이 올 때만 문장을 끊는다. 그냥 '.' 로 가르면
        "www.spcsamlip.co.kr" 이 부서지고 "부정.불량식품" 의 "부정" 이 떨어져
        나간다. 둘 다 실제 라벨에 있는 표기다.
        """
        from v1.label.services.ocr_text import _scatter_pieces

        pieces = _scatter_pieces('가급적 빨리 드시기 바랍니다. 부정.불량식품 신고는 1399')
        self.assertNotIn('부정', [p.strip() for p in pieces])
        self.assertTrue(any('부정.불량식품' in p for p in pieces))

        pieces = _scatter_pieces('고객상담실 080-1234-5678 www.example.co.kr')
        self.assertIn('www.example.co.kr', pieces)

    def test_왜_못_찾았는지_원문의_자리를_보여준다(self):
        """
        점수만 보면 낮은 이유를 알 수 없어 추측하게 된다. 실제로 그 추측이
        틀렸다 - additional_info 가 낮은 이유를 "여러 문구를 이어 붙여서" 라고
        짚고 조각 분할을 넣었는데, 그 값에는 애초에 줄바꿈이 없었다.
        """
        from v1.label.services.ocr_text import explain

        text = '제품명 초코쿠키\n고객상담실 080-999-0000\n'
        rows = explain('고객상담실 080-123-4567', text)

        self.assertEqual(len(rows), 1)
        self.assertLess(rows[0]['score'], 100)
        # 원문에서 실제로 견준 대목이 보여야 한다
        self.assertIn('080-999-0000', rows[0]['nearest'])

    def test_원문_자리는_띄어쓰기까지_그대로_보여준다(self):
        """정규화한 문자열을 보여 주면 표기 차이가 눈에 안 들어온다."""
        from v1.label.services.ocr_text import explain

        rows = explain('냉장(0~10℃)에서보관', '보관방법 냉장 (0~10 ℃) 에서 보관')
        self.assertIn(' ', rows[0]['nearest'])

    def test_찾은_항목에는_설명을_붙이지_않는다(self):
        """전부 붙이면 출력이 길어지기만 한다. 알고 싶은 것은 빗나간 자리뿐이다."""
        from unittest.mock import patch

        from v1.label.services import ocr_text

        case = self._case_with_text(
            '제품명 초코쿠키\n원재료명 밀가루, 설탕, 코코아분말, 정제소금')
        with patch.object(ocr_text, 'extract_text', return_value=case.ocr_text):
            result = ocr_text.measure_case(case)

        found = [r for r in result['rows'] if r['found']]
        self.assertTrue(found)
        self.assertTrue(all('detail' not in r for r in found))

    def test_명령이_판정까지_찍는다(self):
        from io import StringIO

        from django.core.management import call_command

        self._case_with_text('제품명 초코쿠키\n원재료명 밀가루, 설탕, 코코아분말, 정제소금')
        out = StringIO()
        call_command('ocr_ground_check', stdout=out)
        text = out.getvalue()

        self.assertIn('rawmtrl_nm', text)
        self.assertIn('긴 칸 회수율 평균', text)
        self.assertIn('판정:', text)
        # 정답지가 5장 미만이면 성공 판정은 못 한다고 알려야 한다
        self.assertIn('성공 판정은 못 한다', text)

    def test_원문을_못_받으면_0_이_아니라_판단_보류다(self):
        """
        원문을 못 받은 것과 OCR 이 못 읽은 것은 전혀 다르다. 이걸 안 갈랐다가
        결제가 안 걸린 프로젝트에서 403 이 왔는데 "회수율 0.000 / 접는다" 가
        찍혔다. OCR 은 한 번도 돌지 않았는데 방향을 접을 뻔했다.
        """
        from unittest.mock import patch

        from v1.label.services import ocr_text

        case = self._case_with_text('', ocr_engine='')
        with patch.object(ocr_text, 'extract_text', return_value=''):
            result = ocr_text.measure_case(case)

        self.assertFalse(result['measured'])
        self.assertIsNone(result['long_recall'])
        self.assertIsNone(result['recall'])
        self.assertNotIn('접는다', result['verdict'])

    def test_한_장도_못_받으면_판정을_내지_않는다(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from v1.label.services import ocr_text

        self._case_with_text('', ocr_engine='')
        out = StringIO()
        with patch.object(ocr_text, 'extract_text', return_value=''):
            call_command('ocr_ground_check', stdout=out)
        text = out.getvalue()

        self.assertIn('판정을 내지 않는다', text)
        self.assertNotIn('접는다', text)
        self.assertIn('billing', text)      # 자주 걸리는 원인을 짚어 준다

    def test_읽힌_장이_하나라도_있으면_판정은_낸다(self):
        """못 받은 장은 평균에서 빼되, 근거가 얇아졌다고 알린다."""
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from v1.label.services import ocr_text

        self._case_with_text('제품명 초코쿠키\n원재료명 밀가루, 설탕, 코코아분말, 정제소금')
        self._case_with_text('', name='못 읽은 것', ocr_engine='')

        out = StringIO()
        with patch.object(ocr_text, 'extract_text', return_value=''):
            call_command('ocr_ground_check', stdout=out)
        text = out.getvalue()

        self.assertIn('판정:', text)
        self.assertIn('1장은 원문을 받지 못해', text)

    def test_명령이_잴_것이_없어도_안_터진다(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('ocr_ground_check', stdout=out)
        self.assertIn('잴 정답지가 없다', out.getvalue())

    def test_확인_안_된_정답지는_기본으로_빼놓는다(self):
        """확인 전 초안을 자로 쓰면 자기 답을 자기가 채점하는 꼴이 된다."""
        from io import StringIO

        from django.core.management import call_command

        self._case_with_text('제품명 초코쿠키\n원재료명 밀가루, 설탕', verified=False)

        out = StringIO()
        call_command('ocr_ground_check', stdout=out)
        self.assertIn('잴 정답지가 없다', out.getvalue())

        out = StringIO()
        call_command('ocr_ground_check', all=True, stdout=out)
        self.assertIn('판정:', out.getvalue())


class DeriveBasicsTests(TestCase):
    """
    사진값에서 화면 버튼 상태를 유도한다.

    장기보존식품·제조방법·보관방법은 글자 칸이 아니라 눌러서 고르는 것이라,
    값만 채워서는 화면이 그대로다. 사진에는 그 정보가 글자로 적혀 있다.
    """

    def _derive(self, **fields):
        from v1.label.services.ocr_apply import derive_basics

        return derive_basics({k: {'value': v} for k, v in fields.items()})

    def test_보관방법에서_배지를_고른다(self):
        out = self._derive(storage_method='냉동(-18 ℃ 이하)에서 보관')
        self.assertEqual(out['storage_badges'], ['냉동'])

    def test_보관방법_칸만_본다(self):
        """
        주의사항에 "냉장 보관하십시오" 가 있다고 배지를 누르면, 정작 실온
        제품에 냉장이 켜진다.
        """
        out = self._derive(storage_method='실온 보관',
                           cautions='개봉 후에는 냉장 보관하십시오')
        self.assertEqual(out['storage_badges'], ['실온'])

    def test_비살균을_살균으로_읽지_않는다(self):
        """"비살균" 은 "살균" 을 품고 있다. 긴 말부터 봐야 한다."""
        self.assertEqual(self._derive(prdlst_dcnm='즉석섭취식품(비살균제품)')
                         ['processing_method'], 'unsanitized')
        self.assertEqual(self._derive(prdlst_dcnm='멸균제품')
                         ['processing_method'], 'aseptic')
        self.assertEqual(self._derive(prdlst_dcnm='살균제품')
                         ['processing_method'], 'sanitized')

    def test_장기보존식품을_가려낸다(self):
        self.assertEqual(self._derive(prdlst_dcnm='레토르트식품')
                         ['preservation_type'], 'retort')
        self.assertEqual(self._derive(prdlst_dcnm='통조림식품')
                         ['preservation_type'], 'canned')
        self.assertEqual(self._derive(prdlst_dcnm='가열하여 섭취하는 냉동식품')
                         ['preservation_type'], 'frozen_heated')

    def test_모르면_비운다(self):
        """
        틀린 버튼을 눌러 두면 사용자가 알아채고 되돌려야 한다. 그건 안 누른
        것보다 나쁘다. 냉동인 것만 알고 가열/비가열을 모르면 비운다.
        """
        out = self._derive(prdlst_dcnm='과자류', storage_method='냉동 보관')
        self.assertEqual(out['preservation_type'], '')
        self.assertEqual(out['processing_method'], '')
        self.assertEqual(out['storage_badges'], ['냉동'])

    def test_빈_판독에도_안_터진다(self):
        from v1.label.services.ocr_apply import derive_basics

        for data in ({}, None, {'prdlst_nm': {'value': None}}):
            out = derive_basics(data)
            self.assertEqual(out['preservation_type'], '')
            self.assertEqual(out['storage_badges'], [])

    def test_판독_응답에_실려_나간다(self):
        from unittest.mock import patch

        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        user = User.objects.create_user(username='derive', password='x')
        self.client.force_login(user)
        buf = BytesIO()
        Image.new('RGB', (300, 200), 'white').save(buf, format='JPEG')

        fake = {'success': True, 'data': {
            'storage_method': {'value': '냉동(-18℃ 이하)에서 보관'},
            'prdlst_dcnm': {'value': '레토르트식품'}}}
        with patch('v1.label.services.ocr_service.extract_label_from_image',
                   return_value=fake):
            resp = self.client.post('/label/ocr-extract/', {
                'image': SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg')})

        derived = resp.json()['derived']
        self.assertEqual(derived['preservation_type'], 'retort')
        self.assertEqual(derived['storage_badges'], ['냉동'])


class HybridReadTests(TestCase):
    """
    OCR 원문을 판독에 함께 넣고 조각 이미지를 뺀다.

    조각은 오직 글자를 읽으려고 붙인 것인데 그 일은 OCR 이 더 잘한다
    (정답지 5장, 긴 칸 회수율 0.977). VLM 에게는 배치 판단만 맡긴다.
    """

    def test_토큰_한도에_맞춰_쉰다(self):
        """
        판독 한 번이 6~7만 토큰이라 분당 20만 한도면 세 번이 한계다. 예전에는
        12초 고정이었고, 그것도 회차 사이에만 쉬었다 - 정답지 다섯 장을 3회씩
        재는 A/B 가 첫 회차부터 429 로 죽었다.
        """
        from django.test import override_settings

        from v1.label.services.ocr_lab import pace_seconds

        with override_settings(OCR_TPM_LIMIT=200_000):
            self.assertGreaterEqual(pace_seconds(False), 19)   # 65k -> 분당 3번
            self.assertGreaterEqual(pace_seconds(True), 12)    # 18k -> 하한이 이긴다
            self.assertLess(pace_seconds(True), pace_seconds(False))

        # 등급이 오르면 대기가 짧아진다
        with override_settings(OCR_TPM_LIMIT=2_000_000):
            self.assertLessEqual(pace_seconds(False), 12)

    def test_정답지_사이에도_쉰다(self):
        """
        예전에는 회차 사이에만 쉬어서 앞 정답지의 마지막 회차와 다음 정답지의
        첫 회차가 붙어 나갔다.
        """
        from unittest.mock import patch

        from v1.common.models import OcrTruthCase
        from v1.label.services import ocr_lab

        cases = [OcrTruthCase.objects.create(name=f'#{i}', expected={'prdlst_nm': 'x'})
                 for i in range(3)]

        with patch.object(ocr_lab, 'measure_case',
                          return_value={'runs': 1, 'mean': 90.0, 'fields': [],
                                        'last': {}, 'errors': [], 'api': None,
                                        'boxes': None}), \
             patch.object(ocr_lab.time, 'sleep') as slept:
            ocr_lab.run_benchmark(cases, runs=1)

        # 정답지 세 장이면 사이가 둘이다
        self.assertEqual(slept.call_count, 2)

    def _truth_case(self, name='한도'):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from v1.common.models import OcrTruthCase

        buf = BytesIO()
        Image.new('RGB', (200, 150), 'white').save(buf, format='JPEG')
        return OcrTruthCase.objects.create(
            name=name, expected={'prdlst_nm': 'x'}, verified=True,
            image=SimpleUploadedFile('t.jpg', buf.getvalue(), 'image/jpeg'))

    def test_한도에_걸리면_여러_번_다시_해_본다(self):
        """
        한 번으로는 모자랐다. 이 열쇠는 실서비스와 함께 쓰므로, 우리가 아무리
        아껴 불러도 사용자가 사진을 올리고 있으면 창이 남의 요청으로 차 있다.
        실제로 "Used 200000, Requested 4692" 가 나왔다 - 우리 요청은 4천인데
        창은 이미 꽉 차 있었다.
        """
        from unittest.mock import patch

        from v1.common.models import OcrTruthCase
        from v1.label.services import ocr_lab

        case = self._truth_case()
        limited = {'success': False, 'error_kind': 'rate_limit', 'error': '...'}

        with patch('v1.label.services.ocr_service.extract_label_from_image',
                   return_value=limited) as read, \
             patch.object(ocr_lab.time, 'sleep'):
            ocr_lab.measure_case(case, runs=1)

        # 첫 판독 + 재시도 세 번
        self.assertEqual(read.call_count, 1 + ocr_lab._RATE_LIMIT_RETRIES)

    def test_성공하면_더_두드리지_않는다(self):
        from unittest.mock import patch

        from v1.common.models import OcrTruthCase
        from v1.label.services import ocr_lab

        case = self._truth_case()
        outs = [{'success': False, 'error_kind': 'rate_limit', 'error': '...'},
                {'success': True, 'data': {'prdlst_nm': {'value': 'x'}}}]

        with patch('v1.label.services.ocr_service.extract_label_from_image',
                   side_effect=outs) as read, \
             patch.object(ocr_lab.time, 'sleep'):
            ocr_lab.measure_case(case, runs=1)

        self.assertEqual(read.call_count, 2)

    def test_두_회차_사이에도_쉰다(self):
        """
        정답지가 하나면 회차 안에는 쉴 자리가 없다. 끈 쪽과 켠 쪽의 두 호출이
        그대로 붙어 나가 --case 1 --runs 1 이 429 로 죽었다.
        """
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from v1.common.models import OcrBenchmarkRun, OcrTruthCase

        OcrTruthCase.objects.create(name='간격', expected={'prdlst_nm': 'x'},
                                    verified=True)

        def fake_run(cases, **kw):
            return OcrBenchmarkRun.objects.create(
                model='m', variant='whole', case_count=1, runs=1,
                mean_score=90.0, detail={'fields': []})

        with patch('v1.label.services.ocr_lab.run_benchmark', side_effect=fake_run), \
             patch('time.sleep') as slept:
            call_command('ocr_ab', '--hybrid', '--yes', stdout=StringIO())

        slept.assert_called_once()

    def test_명령줄로_A_B_를_돌린다(self):
        """
        화면은 웹 요청 시간 제한에 걸려 한 번에 열두 번까지만 부를 수 있다.
        명령줄에는 그 제한이 없다.
        """
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from v1.common.models import OcrBenchmarkRun, OcrTruthCase

        OcrTruthCase.objects.create(name='A/B 시험', expected={'prdlst_nm': '초코쿠키'},
                                    verified=True)

        def fake_run(cases, **kw):
            return OcrBenchmarkRun.objects.create(
                model='gpt-4o-mini', variant='whole', case_count=1, runs=1,
                mean_score=90.0 if kw.get('use_hybrid') else 80.0,
                detail={'fields': [{'field': 'cautions',
                                    'mean': 90.0 if kw.get('use_hybrid') else 80.0,
                                    'spread': 0.0}]})

        out = StringIO()
        # 회차 사이 대기는 실제로 자면 시험이 20초씩 멈춘다
        with patch('v1.label.services.ocr_lab.run_benchmark',
                   side_effect=fake_run), patch('time.sleep'):
            call_command('ocr_ab', '--hybrid', '--yes', stdout=out)
        text = out.getvalue()

        self.assertIn('cautions', text)
        self.assertIn('+10.0', text)          # 전후 차이
        self.assertIn('OCR_HYBRID', text)     # 채택 안내

    def test_무너진_칸이_있으면_채택하지_않는다(self):
        """평균이 올라도 그렇다. 잘 읽던 칸이 깨지는 것은 다른 문제다."""
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        from v1.common.models import OcrBenchmarkRun, OcrTruthCase

        OcrTruthCase.objects.create(name='A/B 시험', expected={'prdlst_nm': '초코쿠키'},
                                    verified=True)

        def fake_run(cases, **kw):
            on = kw.get('use_hybrid')
            return OcrBenchmarkRun.objects.create(
                model='gpt-4o-mini', variant='whole', case_count=1, runs=1,
                mean_score=95.0 if on else 90.0,
                detail={'fields': [
                    {'field': 'cautions', 'mean': 95.0 if on else 60.0, 'spread': 0.0},
                    {'field': 'prdlst_nm', 'mean': 80.0 if on else 100.0, 'spread': 0.0}]})

        out = StringIO()
        # 회차 사이 대기는 실제로 자면 시험이 20초씩 멈춘다
        with patch('v1.label.services.ocr_lab.run_benchmark',
                   side_effect=fake_run), patch('time.sleep'):
            call_command('ocr_ab', '--hybrid', '--yes', stdout=out)
        text = out.getvalue()

        self.assertIn('채택하지 않는다', text)
        self.assertIn('prdlst_nm', text)
        self.assertNotIn('채택할 만하다', text)

    def test_무엇을_잴지_안_주면_거부한다(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('ocr_ab')

    # ── 혼입가능 물질이 알레르기 칸으로 넘어오는 것 ────────────────────

    BOX = ('쇠고기, 조개류(굴) 함유\n'
           '메밀, 땅콩, 닭고기, 게, 새우, 복숭아, 호두, 오징어, 잣 혼입가능성 있음.\n')

    def test_혼입가능_물질을_알레르기에서_뺀다(self):
        """
        라벨의 검은 박스에는 두 줄이 나란히 있다. 앞줄만 알레르기고 뒷줄은
        주의사항이다. 사진만 볼 때는 모델이 지키는데(100점), 원문을 넣으면
        두 줄이 그냥 이어진 글자라 긴 뒷줄이 답으로 나온다(13.1점).
        지시문을 두 번 고쳐도 안 움직여서 코드로 뗀다.
        """
        from v1.label.services.ocr_ground import repair_allergens

        data = {'allergens': {'value': '쇠고기, 조개류, 메밀, 땅콩, 게, 새우'}}
        out, removed = repair_allergens(data, self.BOX)

        self.assertEqual(out['allergens']['value'], '쇠고기, 조개류')
        self.assertIn('메밀', removed)
        self.assertIn('새우', removed)
        self.assertIn('혼입가능', out['allergens']['ground_note'])

    def test_양쪽에_다_적힌_물질은_남긴다(self):
        """
        실제로 들어 있으면서 다른 것도 혼입될 수 있다. 그때는 알레르기가
        맞으므로 지우면 안 된다.
        """
        from v1.label.services.ocr_ground import repair_allergens

        text = '우유, 대두 함유\n우유, 메밀 혼입가능성 있음.\n'
        data = {'allergens': {'value': '우유, 대두, 메밀'}}
        out, removed = repair_allergens(data, text)

        self.assertEqual(out['allergens']['value'], '우유, 대두')
        self.assertEqual(removed, ['메밀'])

    def test_제대로_읽었으면_건드리지_않는다(self):
        from v1.label.services.ocr_ground import repair_allergens

        data = {'allergens': {'value': '쇠고기, 조개류'}}
        out, removed = repair_allergens(data, self.BOX)

        self.assertEqual(removed, [])
        self.assertEqual(out, data)

    def test_혼입_줄이_없으면_아무것도_안_한다(self):
        from v1.label.services.ocr_ground import repair_allergens

        data = {'allergens': {'value': '우유, 대두'}}
        out, removed = repair_allergens(data, '우유, 대두 함유\n')
        self.assertEqual(removed, [])
        self.assertEqual(out, data)

    def test_원문을_안_넣었으면_수리하지_않는다(self):
        """
        사진만 볼 때는 모델이 두 줄을 제대로 가른다. 그때 값을 덜어 내면
        멀쩡한 것을 건드리게 된다.
        """
        from v1.label.services import ocr_service

        data = {'allergens': {'value': '쇠고기, 조개류, 메밀'}}
        self.assertEqual(
            ocr_service._repaired(data, self.BOX, use_hybrid=False), data)
        self.assertNotEqual(
            ocr_service._repaired(data, self.BOX, use_hybrid=True), data)

    def test_수리가_대조보다_먼저_돈다(self):
        """
        순서가 반대면 우리가 고칠 값을 두고 "지어냈다" 고 표시하게 된다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        at = 0
        for _ in range(2):
            repair_at = source.index('_repaired(result, ocr_text', at)
            ground_at = source.index('_grounded(result, ocr_text', repair_at)
            self.assertLess(repair_at, ground_at)
            at = ground_at + 1

    def test_기본은_꺼져_있다(self):
        """판독의 핵심 경로를 바꾸는 일이다. 측정 없이 켜면 안 된다."""
        from v1.label.services.ocr_service import hybrid_enabled

        self.assertFalse(hybrid_enabled())
        self.assertTrue(hybrid_enabled(True))
        self.assertFalse(hybrid_enabled(False))

    def test_원문을_한_번만_받는다(self):
        """
        대조와 주입이 따로 부르면 판독 한 번에 Vision 을 두 번 호출하게 된다.
        비용이 두 배가 되고, 두 원문이 달라 "대조는 통과했는데 주입된 원문에는
        없다" 같은 일이 생긴다.
        """
        from unittest.mock import patch

        from v1.label.services.ocr_service import sections_text, source_sections

        with patch('v1.label.services.ocr_text.extract_text',
                   return_value='원문') as call:
            sections = source_sections([(b'a', None)], use_ground=True,
                                       use_hybrid=True)

        self.assertEqual(sections_text(sections), '원문')
        self.assertEqual(call.call_count, 1)

    def test_어느_표시면에서_나온_글자인지_들고_있는다(self):
        """
        사용자가 주표시면·영양성분표를 골라 준다. 그 이름이 곧 "이 글자 안에
        무엇이 있는가" 다. 이어 붙여 버리면 그 정보가 사라진다 - 원문은 줄을
        늘어놓을 뿐 구조가 없어서, 영양성분표의 머리글인지 옆 칸 글자인지
        알 수가 없다.
        """
        from unittest.mock import patch

        from v1.label.services.ocr_service import source_sections

        with patch('v1.label.services.ocr_text.extract_text',
                   side_effect=['앞면 글자', '표 글자']):
            sections = source_sections(
                [(b'a', 'main'), (b'b', 'nutrition')], use_hybrid=True)

        self.assertEqual([s['title'] for s in sections],
                         ['주표시면', '영양성분표'])
        self.assertIn('열량', sections[1]['wants'])

    def test_원문_토막마다_면_이름을_붙여_보낸다(self):
        from v1.label.services.ocr_service import hybrid_text_block

        text = hybrid_text_block([
            {'title': '주표시면', 'wants': '제품명, 내용량', 'text': '초코쿠키'},
            {'title': '영양성분표', 'wants': '열량, 나트륨', 'text': '총 내용량 87 g'},
        ])['text']

        self.assertIn('1) 주표시면', text)
        self.assertIn('2) 영양성분표', text)
        self.assertIn('이 면에 있는 항목: 열량, 나트륨', text)
        # 다른 토막의 비슷한 글자를 끌어오지 말라고 해야 한다
        self.assertIn('다른 토막', text)

    def test_꺼져_있으면_원문을_받지_않는다(self):
        from unittest.mock import patch

        from v1.label.services.ocr_service import source_sections

        with patch('v1.label.services.ocr_text.extract_text') as call:
            self.assertEqual(source_sections([(b'a', None)], use_ground=False,
                                             use_hybrid=False), [])
        call.assert_not_called()

    def test_원문_지시문이_쓸_자리를_정해_준다(self):
        """
        "글자는 원문을 그대로 옮기라" 만으로는 너무 넓었다. 정답지 넷에서
        rawmtrl_nm 은 +14.5~+79.5 로 올랐는데 allergens(-87.7), prdlst_nm
        (-37.9), nutrition_basis(-53.8) 가 무너졌다.

        무너진 셋은 **원문을 그대로 옮기면 안 되는 칸**이다 - 알레르기는
        "함유" 를 떼야 하고, 제품명은 작업지시서 품명을 걸러야 한다.
        모델은 시킨 대로 한 것이다.
        """
        from v1.label.services.ocr_service import hybrid_text_block

        text = hybrid_text_block([{'title': '사진 전체', 'wants': '',
                                   'text': '제품명 초코쿠키'}])['text']

        self.assertIn('제품명 초코쿠키', text)
        self.assertIn('참고이지 정답이 아닙니다', text)
        # 원문을 그대로 쓸 칸을 이름으로 짚는다
        for field in ('원재료명', '주의사항', '기타표시사항'):
            self.assertIn(field, text)
        # 그대로 옮기면 틀리는 칸도 이름으로 짚는다
        for field in ('알레르기', '제품명', 'nutrition_basis', '분리배출'):
            self.assertIn(field, text)
        # 라벨 밖 글자가 섞여 든다는 것을 알려야 한다
        self.assertIn('작업지시서', text)

    def test_원문이_없으면_붙이지_않는다(self):
        from v1.label.services.ocr_service import hybrid_text_block

        self.assertIsNone(hybrid_text_block([]))

    def test_원문_길이를_제한한다(self):
        from v1.label.services.ocr_service import OCR_TEXT_MAX_CHARS, hybrid_text_block

        block = hybrid_text_block([{'title': '사진 전체', 'wants': '',
                                    'text': '가' * (OCR_TEXT_MAX_CHARS + 500)}])
        # 지시문에도 '가' 가 들어 있다. 원문 토막만 세야 한다.
        body = block['text'].split('--- 사진에서 읽은 글자 ---\n', 1)[1]
        self.assertEqual(body.count('가'), OCR_TEXT_MAX_CHARS)


class FreetextPairTests(TestCase):
    """
    주의사항과 기타표시사항은 **경계가 사람마다 다르다.**

    표시기준이 둘을 칼같이 가르지 않아서 같은 문구를 한 사람은 주의사항에,
    다른 사람은 기타표시사항에 적는다. 인쇄물에는 두 칸이 나란히 찍히므로
    어느 쪽에 있든 표시는 온전하다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='pair', password='x')

    def test_옆_칸에_넣었다고_0점이_되지_않는다(self):
        from v1.label.services.ocr_benchmark import compare

        expected = {'cautions': '직사광선을 피해 서늘한 곳에 보관하십시오'}
        # 모델이 같은 문구를 기타표시사항에 넣었다
        data = {'cautions': {'value': ''},
                'additional_info': {'value': '직사광선을 피해 서늘한 곳에 보관하십시오'}}

        out = compare(expected, data)
        self.assertGreaterEqual(out['fields']['cautions']['score'], 98)

    def test_제자리에_있으면_그대로_채점한다(self):
        from v1.label.services.ocr_benchmark import compare

        expected = {'cautions': '직사광선을 피해 보관'}
        data = {'cautions': {'value': '직사광선을 피해 보관'},
                'additional_info': {'value': '고객상담실 080-000-0000'}}

        out = compare(expected, data)
        self.assertGreaterEqual(out['fields']['cautions']['score'], 98)

    def test_둘_다_틀리면_여전히_틀린다(self):
        """오탐을 막느라 진짜 오독까지 넘어가면 안 된다."""
        from v1.label.services.ocr_benchmark import compare

        expected = {'cautions': '직사광선을 피해 서늘한 곳에 보관하십시오'}
        data = {'cautions': {'value': '없는 문구입니다'},
                'additional_info': {'value': '고객상담실 080-000-0000'}}

        out = compare(expected, data)
        self.assertLess(out['fields']['cautions']['score'], 75)

    def test_한쪽에만_적어도_미입력으로_보지_않는다(self):
        """
        표시하기로 켠 칸이 비어 있어도, 그 문구가 짝 칸에 있으면 인쇄물은
        온전하다. 규정을 지킨 라벨을 탓하면 안 된다.
        """
        from v1.label.services.validation_service import check_required_fields

        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            chckd_cautions='Y', cautions='',
            additional_info='직사광선을 피해 보관하십시오')

        messages = ' '.join(i['message'] for i in check_required_fields(label))
        self.assertNotIn('주의사항', messages)

    def test_양쪽_모두_비면_지적한다(self):
        from v1.label.services.validation_service import check_required_fields

        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='라벨',
            chckd_cautions='Y', cautions='', additional_info='')

        messages = ' '.join(i['message'] for i in check_required_fields(label))
        self.assertIn('주의사항', messages)


class OcrGroundVerifierTests(TestCase):
    """
    판독값이 사진에 실제로 있던 글자인가 — OCR 원문으로 대조한다 (2단계).

    VLM 은 값을 지어내고 OCR 은 지어낼 수 없다. 그래서 원문을 정답이 아니라
    **증인**으로 쓴다. 값은 고치지 않고 확신도만 내린다 - OCR 도 틀리므로
    원문을 정답으로 삼으면 그 오독이 그대로 굳는다.
    """

    TEXT = ('제품명 초코쿠키\n'
            '식품유형 과자\n'
            '원재료명 밀가루(밀:미국산), 설탕, 코코아분말\n'
            '고객상담실 080-123-4567\n')

    def test_원문에_있는_값은_건드리지_않는다(self):
        from v1.label.services.ocr_ground import ground

        data = {'prdlst_nm': {'value': '초코쿠키', 'confidence': 'high'}}
        out, report = ground(data, self.TEXT)

        self.assertEqual(out['prdlst_nm']['confidence'], 'high')
        self.assertNotIn('grounded', out['prdlst_nm'])
        self.assertEqual(report['ungrounded'], [])

    def test_원문에_없는_값은_짚되_지우지_않는다(self):
        from v1.label.services.ocr_ground import ground

        data = {'cautions': {'value': '직사광선을 피해 서늘한 곳에 보관하십시오',
                             'confidence': 'high'}}
        out, report = ground(data, self.TEXT)

        self.assertEqual(report['ungrounded'], ['cautions'])
        self.assertFalse(out['cautions']['grounded'])
        self.assertEqual(out['cautions']['confidence'], 'low')
        # **값은 그대로다.** OCR 도 틀리므로 원문을 정답으로 삼으면 안 된다
        self.assertEqual(out['cautions']['value'],
                         '직사광선을 피해 서늘한 곳에 보관하십시오')
        self.assertIn('찾지 못했', out['cautions']['ground_note'])

    def test_띄어쓰기가_달라도_있는_것으로_본다(self):
        from v1.label.services.ocr_ground import ground

        data = {'rawmtrl_nm': {'value': '밀가루(밀 : 미국산), 설탕, 코코아분말'}}
        _, report = ground(data, self.TEXT)
        self.assertEqual(report['ungrounded'], [])

    def test_안_읽은_항목은_지어낸_것이_아니다(self):
        from v1.label.services.ocr_ground import ground

        data = {'importer_address': {'value': None, 'confidence': 'none'},
                'bssh_nm': {'value': '', 'confidence': 'none'}}
        out, report = ground(data, self.TEXT)

        self.assertEqual(report['ungrounded'], [])
        self.assertEqual(report['checked'], 0)
        self.assertNotIn('grounded', out['importer_address'])

    def test_글자가_아닌_칸은_대조하지_않는다(self):
        """분리배출 표시는 도형이다. 글자로 찾을 수 없다."""
        from v1.label.services.ocr_ground import ground

        data = {'recycling_mark': {'value': '비닐류 PP / 띠지:PP'}}
        _, report = ground(data, self.TEXT)
        self.assertEqual(report['ungrounded'], [])
        self.assertEqual(report['checked'], 0)

    def test_원문이_없으면_아무것도_하지_않는다(self):
        """원문은 곁들이는 것이다. 없다고 판독 결과가 달라지면 안 된다."""
        from v1.label.services.ocr_ground import ground

        data = {'cautions': {'value': '아무 문구', 'confidence': 'high'}}
        out, report = ground(data, '')

        self.assertEqual(out, data)
        self.assertEqual(report['checked'], 0)

    def test_기본은_꺼져_있다(self):
        """
        켜면 판독 한 번에 Vision 호출이 하나 더 붙고, 지금 100점인 칸들에
        새 판단이 얹힌다. 측정으로 앞뒤를 재기 전에는 켜지 않는다.
        """
        from v1.label.services.ocr_service import ground_enabled

        self.assertFalse(ground_enabled())
        self.assertTrue(ground_enabled(True))
        self.assertFalse(ground_enabled(False))

    def test_값을_바꾸는_단계보다_먼저_돈다(self):
        """
        strip_design_suffix·ocr_snap·ocr_reconcile 은 값을 일부러 바꾼다.
        대조가 그 뒤에 있으면 우리가 바꾼 값이 전부 지어냄으로 잡힌다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        marker = '_grounded(result, ocr_text, use_ground)'
        self.assertEqual(source.count(marker), 2)   # 사진 한 장 / 표시면 여러 장
        at = 0
        for _ in range(2):
            ground_at = source.index(marker, at)
            # 값을 바꾸는 단계는 전부 이 한 줄에 묶여 있다
            # (strip_design_suffix -> drop_inferred_origin -> drop_freetext).
            drop_at = source.index('drop_freetext(', ground_at)
            self.assertLess(ground_at, drop_at)
            at = ground_at + 1
        # 값을 바꾸는 것들은 한 덩어리로 유지한다 — 사이에 대조가 끼면 순서가 깨진다
        self.assertEqual(source.count('drop_inferred_origin(strip_design_suffix(result))'), 2)

    def test_대조가_터져도_판독_결과는_나온다(self):
        from unittest.mock import patch

        from v1.label.services import ocr_service

        data = {'prdlst_nm': {'value': '초코쿠키'}}
        with patch('v1.label.services.ocr_ground.ground',
                   side_effect=RuntimeError('망')):
            out, report = ocr_service._grounded(data, '원문', use_ground=True)

        self.assertEqual(out, data)
        self.assertIsNone(report)

    def test_조각으로_갈라_채점한다(self):
        """
        기타표시사항은 서로 무관한 문구를 줄바꿈으로 이어 붙인 칸이다.
        라벨에서 그 문구들은 떨어져 인쇄돼 있으니, 이어 붙인 문자열이 통째로
        연속해서 있는지 물으면 안 된다 - 실제로 55.8 점이 나왔었다.
        """
        from v1.label.services.ocr_text import match_score

        joined = '고객상담실 080-123-4567\n부정불량식품 신고는 국번없이 1399'
        text = ('제품명 초코쿠키\n고객상담실 080-123-4567\n'
                '(중략)\n부정불량식품 신고는 국번없이 1399\n')
        self.assertGreaterEqual(match_score(joined, text), 95)

    def test_조각이_하나면_예전과_같다(self):
        from v1.label.services.ocr_text import match_score

        self.assertEqual(match_score('초코쿠키', '제품명 초코쿠키'), 100.0)
        self.assertLess(match_score('없는문구입니다', '제품명 초코쿠키'), 60)



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

    def test_같은_이름이_BOM_에_두_줄이면_지적하지_않는다(self):
        """
        text.find 는 언제나 첫 자리를 돌려주므로 같은 이름 둘이 같은 숫자를
        받는다. 그러면 정렬이 배합비 오름차순으로 줄을 세우고, 그 줄은 정의상
        위반이라 **문구를 어떻게 적든 반드시** 운다.

        운영에서 이렇게 나왔다:
            "코코아분말"(0.97%)가 "코코아분말"(1.58%)보다 앞에 있습니다.
        """
        label = self._label('설탕, 코코아분말, 소금',
                            [('설탕', 50), ('코코아분말', 1.58),
                             ('코코아분말', 0.97), ('소금', 0.5)])
        self.assertEqual(self._issues(label), [])

    def test_같은_이름이_문구에_두_번이면_지적하지_않는다(self):
        label = self._label('설탕, 코코아분말, 유청, 코코아분말',
                            [('설탕', 50), ('코코아분말', 1.5)])
        self.assertEqual(self._issues(label), [])

    def test_다른_원료명_안에_들어_있으면_지적하지_않는다(self):
        """
        "코코아분말" 은 "코코아분말가공품" 안에서도 걸린다. find 가 남의 자리를
        돌려주므로 그 자리로 순서를 매기면 안 된다.
        """
        label = self._label('코코아분말가공품, 설탕',
                            [('코코아분말가공품', 40), ('코코아분말', 0.9),
                             ('설탕', 30)])
        self.assertEqual(self._issues(label), [])

    def test_이름이_겹치지_않는_진짜_위반은_그대로_잡는다(self):
        """오탐을 막느라 실제 위반까지 놓치면 안 된다."""
        label = self._label('소브산칼륨, 코코아분말, 소홍두깨살',
                            [('소홍두깨살', 87.32), ('코코아분말', 1.5),
                             ('소브산칼륨', 0.03)])
        messages = ' '.join(i['message'] for i in self._issues(label))
        self.assertIn('"소브산칼륨"(0.03%)', messages)

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

    def test_프롬프트에는_문구를_싣지_않는다(self):
        """
        실으면 모델이 **사진에 없는 것도 채운다.** 실제로 그렇게 됐다 —
        샐러드 라벨의 주의사항에 다른 제품의 보관 문구가, 기타표시사항에
        분쟁해결기준 문구가 통째로 들어갔다. 둘 다 목록에 있던 문장이다.

        목록은 판독 **뒤에** 읽은 문장을 확정하는 데만 쓴다(ocr_snap).
        그쪽은 모델이 실제로 읽은 문장에만 손대므로 없는 것을 만들지 않는다.
        """
        from v1.label.services.label_phrases import texts_for
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        for field in ('cautions', 'additional_info'):
            for text in texts_for(field):
                self.assertNotIn(text, SYSTEM_PROMPT, text[:20])

    def test_흔한_문구일수록_지어내지_말라고_못박는다(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('사진에서 그 글자를 직접 읽지 않았으면 적지 마시오', SYSTEM_PROMPT)
        self.assertIn('이 칸이 비어 있는 것은 잘못이 아니다', SYSTEM_PROMPT)

    def test_어느_칸인지는_뜻으로_가르게_한다(self):
        """문장을 싣지 않고도 칸 구분은 알려 줄 수 있다."""
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('어느 칸에 넣을지는 뜻으로 가른다', SYSTEM_PROMPT)

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


class AllergenBoxPromptTests(TestCase):
    """
    검은 박스 한 칸에 "○○ 함유" 와 "○○ 혼입가능성 있음" 이 같이 있다.

    전용 칸(cross_contamination)을 만들어 봤지만 되돌렸다 — 혼입 문장은 여전히
    안 나왔고, 대신 **알레르기 칸이 나빠졌다**(두 제품 모두). 세 칸이 같은 박스를
    두고 다투면서 "함유" 줄이 통째로 주의사항으로 넘어가는 일까지 생겼다.
    """

    def test_두_줄을_각자_제자리에_넣으라고_말한다(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('한쪽을 다른 쪽에 옮겨 적지 마시오', SYSTEM_PROMPT)
        self.assertIn('안 들어 있는데 같은 시설을 쓴', SYSTEM_PROMPT)

    def test_전용_칸은_되돌렸다(self):
        """칸을 만들면 채운다는 기대가 이 자리에서는 빗나갔다."""
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertNotIn('cross_contamination', SYSTEM_PROMPT)


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


class HallucinatedIngredientTests(TestCase):
    """
    같은 사진을 두 번 읽었는데 한 번은 "다시마추출물, 다른가공품, L-아르지닌"
    이 나왔다. 못 읽은 게 아니라 **없는 것을 만든 것**이고, 그런 이름이 등록
    정보에 있을 리가 없다. 편차 34 가 그 증거다.
    """

    API = ('돼지고기,돼지지방,정제수,정제소금,설탕,소콜라겐,향신료조제품,복합조미식품,'
           '혼합제제,기타가공품,L-아스코르빈산나트륨,코치닐추출색소,아질산나트륨,기타가공품')

    def _warnings(self, 읽음):
        from v1.label.services.ocr_reconcile import merge

        out = merge(
            {'rawmtrl_nm': {'value': 읽음, 'confidence': 'high'}},
            {'matched': True, 'report_no': '1', 'fields': {
                'rawmtrl_nm': {'label': '원재료명', 'api_value': self.API,
                               'ocr_value': 읽음, 'score': 57,
                               'verdict': 'unsure'}}})
        return out['rawmtrl_nm'].get('warnings') or []

    def test_등록_정보에_없는_이름을_짚는다(self):
        읽음 = ('돼지고기/국산,돼지지방/국산,정제수,설탕,다시마추출물,다른가공품,'
                'L-아르지닌')
        found = [w for w in self._warnings(읽음) if '등록 정보에 없는' in w]
        self.assertEqual(len(found), 1)
        self.assertIn('다시마추출물', found[0])

    def test_다_맞으면_아무_말도_안_한다(self):
        읽음 = ('돼지고기/국산,돼지지방/국산,정제수,정제소금/국산,설탕,소콜라겐/네덜란드산,'
                '향신료조제품,복합조미식품,혼합제제,기타가공품,L-아스코르빈산나트륨,'
                '코치닐추출색소,아질산나트륨,기타가공품')
        self.assertEqual(self._warnings(읽음), [])

    def test_진단은_합치지_않고도_된다(self):
        """합칠 만큼 확신이 없을 때가 오히려 사람에게 가장 필요한 순간이다."""
        from v1.label.services.ocr_rawmtrl import diagnose

        out = diagnose('사과,배,포도', self.API)
        self.assertEqual(out['matched'], 0)
        self.assertEqual(len(out['ocr_only']), 3)


class RateLimitRetryTests(TestCase):
    """
    분당 토큰 한도로 회차가 조용히 줄면 편차가 0 으로 나와 "안정적" 으로 읽힌다.
    """

    def test_한도에_걸린_실패를_알아본다(self):
        from v1.label.services.ocr_lab import _is_rate_limited

        # 판독 응답에 붙는 종류로 가린다. 화면 문구는 사람이 읽을 말로 다듬여
        # 있어서, 그 글자를 뒤지면 문구를 손볼 때 이 판단이 조용히 깨진다.
        self.assertTrue(_is_rate_limited(
            {'success': False, 'error_kind': 'rate_limit',
             'error': '지금 판독 요청이 몰려 있습니다. 잠시 후 다시 시도해 주세요.'}))
        self.assertFalse(_is_rate_limited(
            {'success': False, 'error_kind': 'timeout', 'error': '...'}))

        # 종류가 없는 옛 응답·문자열도 그대로 받아 준다
        self.assertTrue(_is_rate_limited(
            'Error code: 429 - Rate limit reached for gpt-4o-mini'))
        self.assertTrue(_is_rate_limited('rate_limit_exceeded'))
        self.assertFalse(_is_rate_limited('사진을 읽지 못했습니다'))
        self.assertFalse(_is_rate_limited(None))

    def test_한도에_걸리면_기다렸다_다시_해_본다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_lab.py'
                  ).read_text(encoding='utf-8')
        self.assertIn("OCR_RATE_LIMIT_WAIT_SEC", source)
        self.assertIn("_is_rate_limited(out)", source)


class OcrErrorMessageTests(TestCase):
    """
    판독이 실패했을 때 **사용자에게 무엇이 보이는가.**

    예전에는 예외를 str() 그대로 돌려줬고 화면이 그걸 그대로 띄웠다. 분당 토큰
    한도에 걸린 날 사용자가 본 문장에는 조직 ID(org-...)가 들어 있었고, 무엇을
    해야 하는지는 한 글자도 없었다.
    """

    def _rate_limit_error(self):
        import httpx
        from openai import RateLimitError

        body = {'error': {
            'message': ('Rate limit reached for gpt-4o-mini in organization '
                        'org-s0ksFMnngAHweQs4lHwa9S4k on tokens per min (TPM): '
                        'Limit 200000, Used 200000, Requested 7040.'),
            'type': 'tokens', 'code': 'rate_limit_exceeded'}}
        response = httpx.Response(
            429, request=httpx.Request('POST', 'https://api.openai.com/v1/chat/completions'),
            json=body)
        return RateLimitError('429', response=response, body=body['error'])

    def test_한도_실패는_사람이_읽을_말로_바뀐다(self):
        from v1.label.services.ocr_service import failure

        out = failure(self._rate_limit_error())
        self.assertFalse(out['success'])
        self.assertEqual(out['error_kind'], 'rate_limit')
        self.assertIn('잠시 후 다시', out['error'])
        self.assertNotIn('org-', out['error'])
        self.assertNotIn('429', out['error'])

    def test_종류를_못_가려도_문구는_나온다(self):
        from v1.label.services.ocr_service import failure

        out = failure(RuntimeError('무언가 터졌다'))
        self.assertEqual(out['error_kind'], 'unknown')
        self.assertNotIn('무언가 터졌다', out['error'])
        # 원문은 버리지 않는다 - 관리자 화면과 로그가 본다
        self.assertIn('무언가 터졌다', out['error_detail'])

    def test_화면에는_기술적_원문이_나가지_않는다(self):
        from io import BytesIO
        from unittest.mock import patch

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        user = User.objects.create_user(username='ocrerr', password='x')
        self.client.force_login(user)
        buf = BytesIO()
        Image.new('RGB', (400, 300), 'white').save(buf, format='JPEG')
        image = SimpleUploadedFile('label.jpg', buf.getvalue(), 'image/jpeg')

        with patch('v1.label.services.ocr_service.OpenAI',
                   side_effect=self._rate_limit_error()):
            resp = self.client.post('/label/ocr-extract/', {'image': image})

        payload = resp.json()
        self.assertFalse(payload['success'])
        self.assertNotIn('error_detail', payload)
        body = resp.content.decode('utf-8')
        self.assertNotIn('org-s0ksFMnngAHweQs4lHwa9S4k', body)
        self.assertIn('잠시 후 다시', payload['error'])


class DesignSuffixTests(TestCase):
    """
    작업지시서·도안 파일 이름이 제품명에 붙어 온다.

    프롬프트에 이 예시를 그대로 넣어 두었는데도 "더블치즈&바질치킨 샐러드_후면"
    이 나왔다. 설득이 안 되는 것은 코드로 뗀다.
    """

    def _name(self, value):
        from v1.label.services.ocr_service import strip_design_suffix

        return strip_design_suffix(
            {'prdlst_nm': {'value': value, 'confidence': 'high'}})['prdlst_nm']

    def test_후면_표기를_뗀다(self):
        item = self._name('더블치즈&바질치킨 샐러드_후면')
        self.assertEqual(item['value'], '더블치즈&바질치킨 샐러드')
        # 말없이 고치지 않는다
        self.assertEqual(item['snapped_from'], '더블치즈&바질치킨 샐러드_후면')

    def test_여러_표기를_뗀다(self):
        for suffix in ('_전면', ' 앞면', '_뒷면', '_시안', '-도안', '_인쇄용'):
            self.assertEqual(self._name('홍삼정과' + suffix)['value'], '홍삼정과')

    def test_멀쩡한_이름은_건드리지_않는다(self):
        for name in ('더블치즈&바질치킨 샐러드', '홍삼정과', '참치통조림'):
            item = self._name(name)
            self.assertEqual(item['value'], name)
            self.assertNotIn('snapped_from', item)

    def test_빈_값은_건드리지_않는다(self):
        from v1.label.services.ocr_service import strip_design_suffix

        data = strip_design_suffix({'prdlst_nm': {'value': None, 'confidence': 'none'}})
        self.assertIsNone(data['prdlst_nm']['value'])


class TranscribeNotRewriteTests(TestCase):
    """
    모델이 문구를 옮겨 적지 않고 **다시 썼다.**

        정답  고객상담실 080-739-8572(수신자 부담)
        판독  상품명에 대한 문의는 080-739-8572로 하시기 바랍니다

    번호는 맞았지만 라벨에 없는 문장이고, 이 결과는 인쇄물에 그대로 들어간다.
    """

    def test_다시_쓰지_말라고_못박는다(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('옮겨 적는 것이지 다시 쓰는 것이 아니다', SYSTEM_PROMPT)
        self.assertIn('한 글자도 바꾸지 말고 옮기시오', SYSTEM_PROMPT)

    def test_기타표시사항까지_함께_묶는다(self):
        """예전에는 주의사항에만 걸려 있었다."""
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('주의사항과 기타표시사항은', SYSTEM_PROMPT)


class CompoundIngredientPromptTests(TestCase):
    """
    복합원재료의 대괄호를 첫 하위 원료에서 닫아 버린다.

        정답  쉬레드치즈[모짜렐라, 체다, 혼합제제(…)]
        판독  쉬레드치즈[모짜렐라], 체다, 혼합제제(…)

    나머지가 별개의 원재료로 밀려 나가 **원재료 수가 늘고 함량 순서가 뒤틀린다.**
    괄호 짝은 맞으므로 bracket_problems 가 못 잡는다.
    """

    def test_하위_원료를_전부_넣으라고_말한다(self):
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('하위 원료를 전부', SYSTEM_PROMPT)
        self.assertIn('첫 하위 원료만 넣고 닫아 버리면', SYSTEM_PROMPT)

    def test_짝이_맞는_잘못은_괄호_검사가_못_잡는다(self):
        """그래서 프롬프트로 다뤄야 하는 자리다 — 시험으로 그 사실을 남긴다."""
        from v1.label.services.ocr_rawmtrl import bracket_problems

        self.assertEqual(bracket_problems('쉬레드치즈[모짜렐라], 체다, 혼합제제(분말셀룰로스)'), [])


class FreetextOptionTests(TestCase):
    """
    주의사항·기타표시사항을 사진에서 읽을 것인가.

    한동안 껐었다. 이 두 칸은 무엇을 해도 흔들렸고 — 목록을 실으면 그 문장을
    지어내고, 빼면 새 문장을 지어내고, 전용 칸을 만들면 알레르기 칸을 망쳤다 —
    화면에 빠른 입력 버튼 스물여덟 개가 있으니 손으로 채우라고 봤다.

    운영에서 뒤집혔다. 인쇄된 문장은 버튼 목록에 없는 것이 많았고, 사진을 올린
    사람은 그 칸이 왜 비어 있는지부터 물었다. 지금은 기본으로 읽고, 끄는 쪽이
    설정이다. 읽은 값은 확인 창을 반드시 거치므로 지어낸 문장은 걷어낼 수 있다.
    """

    def _data(self):
        return {
            'prdlst_nm': {'value': '샐러드', 'confidence': 'high'},
            'cautions': {'value': '지어낸 문구', 'confidence': 'high'},
            'additional_info': {'value': '지어낸 문구', 'confidence': 'high'},
        }

    def test_기본은_읽는다(self):
        from v1.label.services.ocr_service import drop_freetext

        out = drop_freetext(self._data())
        for key in ('cautions', 'additional_info'):
            self.assertEqual(out[key]['value'], '지어낸 문구')
            self.assertNotIn('skipped', out[key])
        self.assertEqual(out['prdlst_nm']['value'], '샐러드')

    def test_설정_기본값이_켬이다(self):
        """`.env` 에 아무것도 안 넣은 서버가 읽는 쪽이어야 한다."""
        from django.conf import settings as dj

        self.assertTrue(getattr(dj, 'OCR_READ_FREETEXT', False))

    def test_켜면_그대로_둔다(self):
        from v1.label.services.ocr_service import drop_freetext

        out = drop_freetext(self._data(), read_freetext=True)
        self.assertEqual(out['cautions']['value'], '지어낸 문구')

    def test_끄면_비운다(self):
        from v1.label.services.ocr_service import drop_freetext

        out = drop_freetext(self._data(), read_freetext=False)
        for key in ('cautions', 'additional_info'):
            self.assertIsNone(out[key]['value'])
            self.assertTrue(out[key]['skipped'])

    def test_설정으로도_끌_수_있다(self):
        from django.test import override_settings

        from v1.label.services.ocr_service import drop_freetext

        with override_settings(OCR_READ_FREETEXT=False):
            self.assertIsNone(drop_freetext(self._data())['cautions']['value'])

    def test_안_읽은_칸은_0점이_아니라_채점_제외다(self):
        """일부러 안 읽은 것을 "못 읽었다" 로 세면 평균이 거짓말을 한다."""
        from v1.label.services.ocr_benchmark import compare
        from v1.label.services.ocr_service import drop_freetext

        expected = {'prdlst_nm': '샐러드', 'cautions': '무언가 적힌 주의사항'}
        out = compare(expected, drop_freetext(self._data(), read_freetext=False))
        self.assertNotIn('cautions', out['fields'])
        self.assertEqual(out['mean'], 100.0)
        self.assertEqual(out['counted'], 1)

    def test_켜면_다시_채점한다(self):
        from v1.label.services.ocr_benchmark import compare
        from v1.label.services.ocr_service import drop_freetext

        expected = {'prdlst_nm': '샐러드', 'cautions': '무언가 적힌 주의사항'}
        out = compare(expected, drop_freetext(self._data(), read_freetext=True))
        self.assertIn('cautions', out['fields'])

    def test_확인_창이_왜_없는지_말해_준다(self):
        """그냥 빠져 있으면 "사진에 없었나 보다" 로 읽힌다."""
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
              ).read_text(encoding='utf-8')
        self.assertIn('function skippedHtml', js)
        self.assertIn('+ skippedHtml(data)', js)
        self.assertIn('자주 사용하는 문구', js)


class RegionRoleWantsTests(TestCase):
    """
    표시면 지시문의 "여기서 찾을 항목" 목록.

    이 목록은 "각 장에 적힌 것만 읽으세요" 와 함께 나간다. 그래서 **목록에서
    빠진 칸은 안 읽힌다.** 본서버 시험에서 일괄표시면을 골라 읽었더니
    원산지·유통전문판매원·주의사항·기타표시사항이 통째로 비어서 왔다 — 사진에는
    다 인쇄돼 있었다.
    """

    def test_일괄표시면에_인쇄되는_것이_빠짐없이_적혀_있다(self):
        from v1.label.services.ocr_service import REGION_ROLES

        wants = REGION_ROLES['info'][1]
        for name in ('식품유형', '품목보고번호', '원재료명', '알레르기',
                     '원산지', '유통전문판매원', '소비기한', '보관방법',
                     '포장재질', '주의사항', '기타표시사항'):
            self.assertIn(name, wants, f'일괄표시면 지시문에 {name} 이 없다')

    def test_원재료명_영역은_원산지도_본다(self):
        """원산지는 원재료 이름 뒤에 괄호로 붙는다 — 같은 자리에 있다."""
        from v1.label.services.ocr_service import REGION_ROLES

        self.assertIn('원산지', REGION_ROLES['rawmtrl'][1])

    def test_목록이_전부가_아니라고_말한다(self):
        """
        목록은 거들 뿐이다. 그렇게 말해 두지 않으면 목록에 없는 칸을 모델이
        아예 찾지 않는다 — 목록을 아무리 채워도 새 칸을 넣을 때마다 같은 사고가
        난다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        self.assertIn('거기까지만 읽으라는 뜻이 아닙니다', source)

    def test_화면_설명과_서버_지시문이_같은_면을_말한다(self):
        """
        photo_cropper.js 의 hint 는 고르는 사람이 보고, REGION_ROLES 의 wants 는
        모델이 본다. 둘이 어긋나면 사용자가 본 설명과 실제 판독이 달라진다.
        """
        import re
        from pathlib import Path

        from django.conf import settings as dj

        from v1.label.services.ocr_service import REGION_ROLES

        js = (Path(dj.BASE_DIR) / 'static/js/products/photo_cropper.js'
              ).read_text(encoding='utf-8')
        keys = set(re.findall(r"\{ key: '(\w+)'", js))
        self.assertTrue(keys, '화면의 ROLES 를 못 읽었다')
        for key in keys:
            self.assertIn(key, REGION_ROLES, f'화면에만 있는 표시면: {key}')
        # 일괄표시면 설명도 새 항목을 담고 있어야 한다
        head = js.index("key: 'info'")
        block = js[head:head + 400]
        for name in ('주의사항', '기타표시사항', '원산지', '알레르기'):
            self.assertIn(name, block, f'화면 설명에 {name} 이 없다')


class FoodTypeDeriveTests(TestCase):
    """
    사진에서 읽은 식품유형 한 줄로 **화면의 드롭다운과 버튼까지** 맞춘다.

    라벨은 소분류에 장기보존·제조방법을 덧붙여 한 줄로 적는다.

        빵류(가열하지 않고 섭취하는 냉동식품)

    예전에는 이 줄을 식품유형(표시용) 칸에만 넣었다. 대분류·소분류 드롭다운은
    비어 있었고 — 그 둘이 유형별 표시항목 규칙을 찾는 키다 — 냉동(비가열)
    버튼도 안 눌렸다. frozen_nonheated 를 "비가열" 한 낱말로만 찾았기 때문인데,
    라벨에 그렇게 적힌 경우가 거의 없다.
    """

    def setUp(self):
        from django.core.cache import cache

        from v1.label.models import FoodType

        cache.clear()
        self.addCleanup(cache.clear)
        FoodType.objects.create(food_group='과자류, 빵류 또는 떡류', food_type='빵류')
        FoodType.objects.create(food_group='면류', food_type='만두류')
        FoodType.objects.create(food_group='음료류', food_type='과·채가공품(과채음료 제외)')

    def _derive(self, dcnm):
        from v1.label.services.ocr_apply import derive_basics
        return derive_basics({'prdlst_dcnm': {'value': dcnm}})

    def test_괄호_앞의_소분류와_그_대분류를_고른다(self):
        out = self._derive('빵류(가열하지 않고 섭취하는 냉동식품)')
        self.assertEqual(out['food_type'], '빵류')
        self.assertEqual(out['food_group'], '과자류, 빵류 또는 떡류')

    def test_가열하지_않고_섭취하는_냉동식품은_비가열이다(self):
        """라벨이 "비가열" 이라고 적는 일은 거의 없다 — 표시기준 문장 그대로 적는다."""
        self.assertEqual(
            self._derive('빵류(가열하지 않고 섭취하는 냉동식품)')['preservation_type'],
            'frozen_nonheated')

    def test_가열하여_섭취하는_냉동식품은_가열이다(self):
        self.assertEqual(
            self._derive('만두류(가열하여 섭취하는 냉동식품)')['preservation_type'],
            'frozen_heated')

    def test_띄어쓰기가_달라도_찾는다(self):
        """인쇄물마다 "가열하지 않고" / "가열하지않고" 가 섞여 있다."""
        for text in ('빵류(가열하지않고 섭취하는 냉동식품)',
                     '빵류 | 가열하지 않고 섭취하는 냉동식품'):
            self.assertEqual(self._derive(text)['preservation_type'],
                             'frozen_nonheated', text)

    def test_소분류에_괄호가_들어가도_찾는다(self):
        """무조건 괄호 앞을 자르면 그런 유형을 영영 못 찾는다."""
        out = self._derive('과·채가공품(과채음료 제외)')
        self.assertEqual(out['food_type'], '과·채가공품(과채음료 제외)')
        self.assertEqual(out['food_group'], '음료류')

    def test_목록에_없으면_비운다(self):
        """모르는 것과 "아니다" 는 다르다 — 틀린 값을 골라 두면 더 나쁘다."""
        out = self._derive('없는유형류')
        self.assertEqual(out['food_type'], '')
        self.assertEqual(out['food_group'], '')

    def test_제조방법도_함께_읽는다(self):
        self.assertEqual(self._derive('기타가공품(살균제품)')['processing_method'],
                         'sanitized')
        self.assertEqual(self._derive('기타가공품(비살균제품)')['processing_method'],
                         'unsanitized')

    def test_화면이_드롭다운을_고른다(self):
        """
        서버가 판정해도 화면이 안 고르면 그대로다. 대분류를 먼저 골라야 한다 —
        대분류가 바뀌면 소분류 목록이 통째로 다시 그려진다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
              ).read_text(encoding='utf-8')
        self.assertIn("setSelect('field-food-group', derived.food_group)", js)
        self.assertIn("setSelect('field-food-type', derived.food_type)", js)
        self.assertLess(js.index("derived.food_group"), js.index("derived.food_type"))
        # Select2 로 감싸여 있어 value 만 바꾸면 화면이 그대로다
        self.assertIn("window.jQuery(el).trigger('change')", js)


class InferredOriginTests(TestCase):
    """
    원산지 칸에 "국산" 이 저절로 채워지던 것.

    라벨에 제품 전체 원산지 칸이 있는 경우는 대개 수입품이고, 그때는 나라
    이름이 적힌다. 국내 제조 제품은 원산지를 원재료명 뒤 괄호로 적지 별도 칸을
    두지 않는다. 모델은 제조원 주소가 한국인 것을 보고 "국산" 을 채웠다.
    """

    def _drop(self, value):
        from v1.label.services.ocr_service import drop_inferred_origin
        out = drop_inferred_origin({'country_of_origin': {'value': value,
                                                          'confidence': 'high'}})
        return out['country_of_origin']

    def test_국산류_단독_값은_버린다(self):
        for value in ('국산', '국내산', '한국산', '대한민국', ' 국내 '):
            item = self._drop(value)
            self.assertIsNone(item['value'], value)
            self.assertEqual(item['confidence'], 'none')

    def test_왜_뺐는지_남긴다(self):
        """그냥 비어 있으면 "사진에 없었나 보다" 로 읽힌다."""
        item = self._drop('국산')
        self.assertEqual(item['dropped_from'], '국산')
        self.assertIn('직접 넣어', item['dropped_note'])

    def test_나라_이름은_그대로_둔다(self):
        """수입품의 원산지 칸은 실제로 읽은 것이다."""
        for value in ('중국', '베트남', '국산, 중국산', '쌀: 국내산'):
            self.assertEqual(self._drop(value)['value'], value, value)

    def test_판독_경로에_걸려_있다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py'
                  ).read_text(encoding='utf-8')
        self.assertEqual(source.count('drop_inferred_origin(strip_design_suffix(result))'), 2)

    def test_프롬프트도_같은_말을_한다(self):
        """코드로 떼더라도 애초에 안 만들게 하는 편이 낫다."""
        from v1.label.services.ocr_service import SYSTEM_PROMPT

        self.assertIn('"원산지" 라는 항목이 라벨에 없으면 none', SYSTEM_PROMPT)

    def test_확인_창이_뺀_사실을_말한다(self):
        from pathlib import Path

        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/products/basic_info_ocr.js'
              ).read_text(encoding='utf-8')
        self.assertIn('item.dropped_note', js)
        self.assertIn('넣지 않았습니다', js)


class ContentWeightBasisTests(TestCase):
    """
    내용량과 영양성분 탭이 서로 다른 총량을 말하던 것.

    이 화면에는 총 내용량이 두 군데 적힌다.

        내용량 칸      "65 g (200 kcal)"      인쇄되는 값
        영양성분 탭    단위량 x 포장개수       표를 그리는 값

    둘이 어긋나도 예전에는 열량만 견주고 총량은 안 봤다. 그래서 사용자가 열량을
    고쳐도 표는 여전히 다른 총량을 그렸다 — 고치라는 대로 고쳐도 안 맞았다.
    """

    def _label(self, **kw):
        from v1.label.models import MyLabel

        user = User.objects.create_user(
            username=f'cw{User.objects.count()}', password='x')
        defaults = dict(user_id=user, my_label_name='제품', prdlst_nm='제품')
        defaults.update(kw)
        return MyLabel(**defaults)

    def _cats(self, label):
        from v1.label.services.validation_service import check_content_weight_basis
        return [i['category'] for i in check_content_weight_basis(label)]

    def test_총량이_같으면_조용하다(self):
        label = self._label(content_weight='65 g', serving_size='65',
                            units_per_package='1', calories='309')
        self.assertEqual(self._cats(label), [])

    def test_단위량_곱하기_포장개수로_본다(self):
        label = self._label(content_weight='130 g', serving_size='65',
                            units_per_package='2', calories='309')
        self.assertEqual(self._cats(label), [])

    def test_표를_안_그리면_건너뛴다(self):
        """
        단위량은 여러 곳에서 기본값 100 으로 채워진다. 영양성분을 한 번도 안
        넣은 65 g 제품이 "100 != 65" 로 늘 걸리면 고칠 것도 없는 경고가 쌓인다.
        """
        label = self._label(content_weight='65 g', serving_size='100',
                            units_per_package='1')
        self.assertEqual(self._cats(label), [])

    def test_어긋나면_알려_준다(self):
        label = self._label(content_weight='65 g', serving_size='65',
                            units_per_package='2', calories='309')
        from v1.label.services.validation_service import check_content_weight_basis

        issues = check_content_weight_basis(label)
        self.assertEqual(len(issues), 1)
        self.assertIn('영양성분 탭', issues[0]['message'])
        self.assertIn('포장개수', issues[0]['message'])

    def test_영양성분_탭이_비었으면_검사하지_않는다(self):
        """그건 다른 검사(필수항목)가 할 말이다."""
        label = self._label(content_weight='65 g')
        self.assertEqual(self._cats(label), [])


class CalorieMessageTests(TestCase):
    """
    열량 경고가 **어느 칸에 무엇을 넣어야 하는지**를 말해야 한다.

    예전 문구는 "맞지 않습니다 / 값을 고치거나 다시 확인하세요" 로 끝났다.
    이 경고를 받은 사용자가 영양성분 탭에 총 열량을 넣어 보고, 내용량에는
    100g당 열량을 넣어 보다가 두 값이 계속 어긋났다.
    """

    def _issue(self, content_weight, calories):
        from v1.label.models import MyLabel
        from v1.label.services.validation_service import check_calorie_consistency

        user = User.objects.create_user(
            username=f'cal{User.objects.count()}', password='x')
        label = MyLabel(user_id=user, my_label_name='제품', prdlst_nm='제품',
                        content_weight=content_weight, calories=calories)
        return check_calorie_consistency(label)

    def test_맞으면_조용하다(self):
        """65 g 짜리에 100g당 309 kcal 이면 총 200 kcal 이다."""
        self.assertEqual(self._issue('65 g (200 kcal)', '309'), [])

    def test_두_칸이_담는_것을_말해_준다(self):
        issues = self._issue('65 g (309 kcal)', '309')
        self.assertEqual(len(issues), 1)
        message = issues[0]['message']
        self.assertIn('총 내용량', message)
        self.assertIn('100 g(mL) 당', message)

    def test_고칠_값을_둘_다_준다(self):
        """어느 쪽을 고쳐도 되는 일이라, 양쪽 값을 다 준다."""
        suggestion = self._issue('65 g (250 kcal)', '309')[0]['suggestion']
        self.assertIn('200 kcal', suggestion)     # 내용량을 고칠 경우
        self.assertIn('385', suggestion)          # 영양성분 탭을 고칠 경우

    def test_라벨_값을_그대로_넣은_것을_알아본다(self):
        """
        라벨의 표가 "65 g 당 309 kcal" 이면 그 숫자를 그대로 넣었을 때 두 값이
        똑같아진다. 그때는 "값이 틀렸다" 가 아니라 "기준이 다르다" 고 말해야
        고칠 데를 찾는다.
        """
        issues = self._issue('65 g (309 kcal)', '309')
        self.assertEqual(len(issues), 1)
        self.assertIn('그대로 넣으신 것 같습니다', issues[0]['message'])
        self.assertIn('총 내용량당', issues[0]['suggestion'])
        # 사용자가 실제로 쓴 우회를 미리 막는다
        self.assertIn('단위량을 100 으로 바꾸는 것은', issues[0]['suggestion'])

    def test_100g_기준_제품에는_그_말을_하지_않는다(self):
        """총량이 100 이면 두 값이 같은 것이 정상이다."""
        self.assertEqual(self._issue('100 g (309 kcal)', '309'), [])

    def test_단위를_지어내지_않는다(self):
        """음료(mL)에 "65 g" 로 고치라고 말하면 안 된다."""
        suggestion = self._issue('500 mL (900 kcal)', '100')[0]['suggestion']
        self.assertIn('mL', suggestion)
        self.assertNotIn('500 g', suggestion)


class CollectedChecksInValidationTests(TestCase):
    """
    판독이 값을 넣기 전에 하던 검사를 저장된 라벨에도 댄다.

    괄호 짝·식품유형 목록·알레르기 표기는 사진에서 왔든 손으로 넣었든 똑같이
    틀린 것인데, 판독을 거치지 않은 라벨에는 아무도 그 말을 해 주지 않았다.
    """

    def _label(self, **kw):
        from v1.label.models import MyLabel

        user = User.objects.create_user(
            username=f'vv{User.objects.count()}', password='x')
        defaults = dict(user_id=user, my_label_name='제품', prdlst_nm='제품')
        defaults.update(kw)
        return MyLabel(**defaults)

    def test_괄호_짝이_깨지면_지적한다(self):
        from v1.label.services.validation_service import check_rawmtrl_brackets

        label = self._label(rawmtrl_nm_display='정제수, 혼합제제(구연산, 향료')
        issues = check_rawmtrl_brackets(label)
        self.assertTrue(issues)
        self.assertEqual(issues[0]['category'], 'rawmtrl_bracket')

    def test_짝이_맞으면_조용하다(self):
        from v1.label.services.validation_service import check_rawmtrl_brackets

        label = self._label(rawmtrl_nm_display='정제수, 혼합제제(구연산, 향료)')
        self.assertEqual(check_rawmtrl_brackets(label), [])

    def test_판독과_같은_함수를_쓴다(self):
        """규칙을 두 벌로 만들면 어느 날 한쪽만 고쳐진다."""
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'label/services/validation_service.py'
                  ).read_text(encoding='utf-8')
        self.assertIn('from v1.label.services.ocr_rawmtrl import bracket_problems', source)
        self.assertIn('from v1.label.services.ocr_snap import food_type_vocabulary', source)

    def test_식품유형이_목록_밖이면_지적한다(self):
        from django.core.cache import cache

        from v1.label.models import FoodType
        from v1.label.services.validation_service import check_food_type_known

        cache.clear()
        self.addCleanup(cache.clear)
        FoodType.objects.create(food_group='과자류, 빵류 또는 떡류', food_type='빵류')

        self.assertEqual(check_food_type_known(self._label(food_type='빵류')), [])
        issues = check_food_type_known(self._label(food_type='없는유형류'))
        self.assertTrue(issues)
        self.assertEqual(issues[0]['category'], 'food_type_unknown')
        self.assertIn('의무 표시사항', issues[0]['suggestion'])

    def test_알레르기_표기가_다르면_고칠_값을_준다(self):
        from v1.label.services.validation_service import check_allergen_vocabulary

        self.assertEqual(check_allergen_vocabulary(self._label(allergens='우유, 대두')), [])
        issues = check_allergen_vocabulary(self._label(allergens='우유, 대두 함유'))
        self.assertTrue(issues)
        self.assertIn('우유, 대두', issues[0]['suggestion'])

    def test_검사_목록에_올라_있다(self):
        """함수만 만들고 목록에 안 넣으면 아무 데서도 안 돈다."""
        from v1.label.services import validation_service as vs

        for check in (vs.check_content_weight_basis, vs.check_rawmtrl_brackets,
                      vs.check_food_type_known, vs.check_allergen_vocabulary):
            self.assertIn(check, vs._CHECKS, check.__name__)

    def test_근거_규정을_함께_말한다(self):
        from v1.label.services import validation_service as vs

        for category in ('content_weight_basis', 'rawmtrl_bracket',
                         'food_type_unknown', 'allergen_vocabulary'):
            self.assertIn(category, vs._LEGAL_BASIS, category)


class NutritionHeaderTests(TestCase):
    """
    영양정보 표의 머리는 **언제나 포장 전체**를 말한다.

    예전에는 머리도 표시기준을 따라갔다. 65 g 짜리 제품에 "100g당" 을 고르면
    라벨에 "총 내용량 100g" 이 인쇄됐고, 옆의 열량도 100 g 당 값이 총 열량인
    것처럼 찍혔다. 그 숫자를 내용량 칸에 옮겨 적은 사용자가 규정 검증에서
    "열량이 맞지 않습니다" 를 계속 봤다 — 검증이 아니라 표가 틀렸다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        self.js = (Path(dj.BASE_DIR) / 'static/js/label/nutrition_calculator_popup.js'
                   ).read_text(encoding='utf-8')

    def test_머리는_총_내용량이다(self):
        self.assertIn('총 내용량 ${totalAmount.toLocaleString()}${baseUnit}', self.js)
        self.assertNotIn('총 내용량 ${displayAmount', self.js)

    def test_머리의_열량도_총_열량이다(self):
        head = self.js.index('function generateBasicDisplayV3')
        block = self.js[head:head + 2600]
        self.assertIn("'calories', (nutritionInputs['calories'] || 0) * (totalAmount / 100)", block)

    def test_표시기준_이름이_한_벌이다(self):
        """
        'per_100g' 는 표를 그리는 switch 에 없어 조용히 총량당으로 떨어졌다 —
        이름과 실제 동작이 달랐다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        self.assertIn('function normalizeBasicDisplayType', self.js)
        creation = (Path(dj.BASE_DIR) / 'static/js/label/label_creation.js'
                    ).read_text(encoding='utf-8')
        # 주석에는 남는다(왜 바꿨는지를 적어 뒀다). 값으로 쓰이지만 않으면 된다.
        code = '\n'.join(line for line in creation.split('\n')
                         if not line.strip().startswith('//'))
        self.assertNotIn("'basic_display_type': 'per_100g'", code)
        self.assertNotIn("basic_display_type || 'per_100g'", code)
        self.assertNotIn("'parallel_display_type': 'per_serving'", code)

    def test_모르는_이름은_예전처럼_총량당이다(self):
        """
        이미 저장된 'per_100g' 라벨들은 그동안 총량당으로 인쇄돼 왔다.
        여기서 100g당으로 "고치면" 승인된 라벨의 표가 말없이 바뀐다.
        """
        head = self.js.index('function normalizeBasicDisplayType')
        block = self.js[head:head + 260]
        self.assertIn("return 'total';", block)


class OcrNutritionBasisTests(TestCase):
    """
    사진의 표가 총 내용량 기준이면 포장개수도 1 로 맞춰야 한다.

    저장 칸의 총 내용량은 `단위량 x 포장개수` 다. 단위량만 바꾸고 개수를 그대로
    두면(2 등) 표의 총량이 그 배수가 되고, 인쇄된 내용량과 영양정보 표의 머리가
    서로 다른 총량을 말한다.
    """

    def test_총_내용량_기준을_알아본다(self):
        from v1.label.services.ocr_apply import basis_is_total

        self.assertTrue(basis_is_total('총 내용량 139 g'))
        self.assertTrue(basis_is_total('총내용량139g'))
        self.assertFalse(basis_is_total('1회 제공량 30 g'))
        self.assertFalse(basis_is_total('100 g당'))
        self.assertFalse(basis_is_total(''))

    def test_적용하는_쪽이_개수를_맞춘다(self):
        from pathlib import Path

        from django.conf import settings as dj

        source = (Path(dj.BASE_DIR) / 'products/views.py').read_text(encoding='utf-8')
        head = source.index('basis_value, basis_unit = parse_nutrition_basis')
        block = source[head:head + 1400]
        self.assertIn('basis_is_total(basis_text)', block)
        self.assertIn("label.units_per_package = '1'", block)


class AllergenNameTests(TestCase):
    """
    같은 물질의 다른 표기를 하나로 본다.

        알류  /  알류(달걀)  /  달걀  /  알류 함유  /  난류

    표시기준이 정한 명칭은 "알류" 이고 괄호는 부연이다. 그런데 이 값을 다루는
    자리가 다섯이었고(사진 판독·원재료명 감지·칩·저장값 로드·규정 검증), 전부
    문자열을 그대로 키로 썼다. 운영에서 이렇게 나왔다.

        알류(달걀), 우유, 대두, 밀, 알류      <- 같은 것이 둘
    """

    def test_괄호는_부연이다(self):
        from v1.label.services.allergen_names import canonical

        self.assertEqual(canonical('알류(달걀)'), '알류')
        self.assertEqual(canonical('우유(유당)'), '우유')
        self.assertEqual(canonical('조개류(굴)'), '조개류')

    def test_키워드도_그_물질이다(self):
        from v1.label.services.allergen_names import canonical

        for token, name in (('달걀', '알류'), ('계란', '알류'), ('난류', '알류'),
                            ('두부', '대두'), ('치즈', '우유')):
            self.assertEqual(canonical(token), name, token)

    def test_꼬리말을_뗀다(self):
        from v1.label.services.allergen_names import canonical

        self.assertEqual(canonical('알류 함유'), '알류')
        self.assertEqual(canonical('대두 포함'), '대두')

    def test_모르면_비운다(self):
        """
        억지로 가장 닮은 것을 고르면, 목록 밖의 문구를 적어 둔 라벨의 값을
        엉뚱한 물질로 바꿔 버린다.
        """
        from v1.label.services.allergen_names import canonical

        self.assertEqual(canonical('홍삼'), '')
        self.assertEqual(canonical(''), '')

    def test_한_글자_차이는_맞춰_준다(self):
        from v1.label.services.allergen_names import canonical

        self.assertEqual(canonical('대두류'), '대두')

    def test_같은_물질을_합친다(self):
        """운영에서 나온 그 줄."""
        from v1.label.services.allergen_names import normalize

        out, changes = normalize('알류(달걀),우유,대두,밀,알류')
        self.assertEqual(out, '알류(달걀), 우유, 대두, 밀')
        self.assertEqual([c['name'] for c in changes], ['알류'])

    def test_자세한_표기를_남긴다(self):
        """"알류(달걀)" 은 무엇을 넣었는지까지 말한다."""
        from v1.label.services.allergen_names import normalize

        self.assertEqual(normalize('알류, 알류(달걀)')[0], '알류(달걀)')
        self.assertEqual(normalize('알류(달걀), 알류')[0], '알류(달걀)')

    def test_명칭이_아닌_표기는_명칭으로_바꾼다(self):
        """
        규정이 요구하는 것은 명칭이고, 뒤에서 이 값을 키로 쓰는 곳이 그 명칭을
        찾는다. "달걀" 만 적혀 있으면 어느 목록에서도 정확히 안 찾힌다.
        """
        from v1.label.services.allergen_names import normalize

        self.assertEqual(normalize('달걀, 우유')[0], '알류, 우유')
        self.assertEqual(normalize('우유, 대두류, 밀 함유')[0], '우유, 대두, 밀')

    def test_목록_밖의_문구는_지우지_않는다(self):
        """그런 것을 적어 두는 라벨이 있고, 지우면 정보가 사라진다."""
        from v1.label.services.allergen_names import normalize

        self.assertEqual(normalize('알류(달걀), 홍삼')[0], '알류(달걀), 홍삼')

    def test_이미_맞으면_그대로_둔다(self):
        from v1.label.services.allergen_names import normalize

        for text in ('알류(달걀), 우유, 대두, 밀', '우유, 대두, 밀'):
            self.assertEqual(normalize(text)[0], text, text)

    def test_판독도_같은_판정을_쓴다(self):
        """규칙을 여러 벌로 만들면 어느 날 한쪽만 고쳐진다."""
        from v1.label.services.ocr_snap import snap_allergens

        snapped, changes = snap_allergens('알류(달걀),우유,대두,밀,알류')
        self.assertEqual(snapped, '알류(달걀), 우유, 대두, 밀')
        self.assertTrue(changes)

    def test_화면도_같은_판정을_쓴다(self):
        """
        화면(JS)이 자기 규칙을 들고 있으면 서버가 정리한 값을 다시 흩뜨린다.
        같은 이름의 함수가 있는지, 태그를 넣는 자리가 그걸 부르는지 본다.
        """
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        shared = (base / 'static/js/label/allergen_names.js').read_text(encoding='utf-8')
        for fn in ('function canonicalAllergen', 'function displayAllergen',
                   'function mergeAllergen'):
            self.assertIn(fn, shared)

        creation = (base / 'static/js/label/label_creation.js').read_text(encoding='utf-8')
        # 태그를 넣는 자리가 전부 한 통로를 지난다
        self.assertEqual(creation.count('selectedIngredientAllergensLabel.set('), 1)
        self.assertIn('window.mergeAllergen(selectedIngredientAllergensLabel', creation)

        tab = (base / 'templates/products/_tab_basic_info.html').read_text(encoding='utf-8')
        self.assertEqual(tab.count('_productAllergens.set('), 1)
        self.assertIn('window.mergeAllergen(_productAllergens', tab)

    def test_화면이_판정_파일을_싣는다(self):
        """부르는 함수가 없으면 예전처럼 그냥 넣는다 — 조용히 되돌아간다."""
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        for path in ('templates/label/label_creation.html',
                     'templates/products/_tab_basic_info.html'):
            self.assertIn('js/label/allergen_names.js',
                          (base / path).read_text(encoding='utf-8'), path)

    def test_서버와_화면의_물질_목록이_같다(self):
        """
        키워드 표가 세 벌이다(파이썬 상수·constants.js·기본정보 탭 인라인).
        판정이 그 표를 쓰므로, 이름이 어긋나면 화면과 서버가 다른 답을 낸다.
        """
        import re
        from pathlib import Path

        from django.conf import settings as dj

        from v1.label.services.allergen_names import CANONICAL_NAMES

        base = Path(dj.BASE_DIR)

        def names_in(text, marker):
            block = text[text.index(marker):]
            block = block[:block.index('};')]
            return set(re.findall(r"'([^']+)':\s*\[", block))

        js = names_in((base / 'static/js/label/constants.js').read_text(encoding='utf-8'),
                      'const ALLERGEN_KEYWORDS = {')
        tab = names_in((base / 'templates/products/_tab_basic_info.html').read_text(encoding='utf-8'),
                       'var PRODUCT_ALLERGEN_KEYWORDS = {')
        self.assertEqual(js, set(CANONICAL_NAMES), 'constants.js 의 물질 목록이 서버와 다르다')
        self.assertEqual(tab, set(CANONICAL_NAMES), '기본정보 탭의 물질 목록이 서버와 다르다')


class AllergenValidationTests(TestCase):
    """규정 검증도 같은 판정을 쓴다."""

    def _label(self, allergens, rawmtrl=''):
        return MyLabel(user_id=User.objects.create_user(
            username=f'al{User.objects.count()}', password='x'),
            my_label_name='제품', prdlst_nm='제품',
            allergens=allergens, rawmtrl_nm_display=rawmtrl)

    def test_같은_물질이_두_번이면_그렇게_말한다(self):
        from v1.label.services.validation_service import check_allergen_vocabulary

        issues = check_allergen_vocabulary(self._label('알류(달걀),우유,대두,밀,알류'))
        self.assertEqual(len(issues), 1)
        self.assertIn('두 번 적혀', issues[0]['message'])
        self.assertIn('알류', issues[0]['message'])
        self.assertIn('알류(달걀), 우유, 대두, 밀', issues[0]['suggestion'])

    def test_정리된_값에는_조용하다(self):
        from v1.label.services.validation_service import check_allergen_vocabulary

        self.assertEqual(
            check_allergen_vocabulary(self._label('알류(달걀), 우유, 대두, 밀')), [])

    def test_띄어쓰기만_다른_것은_지적하지_않는다(self):
        """제안이 원문과 똑같아 보이는 쪽지를 계속 받게 된다."""
        from v1.label.services.validation_service import check_allergen_vocabulary

        self.assertEqual(
            check_allergen_vocabulary(self._label('알류(달걀),우유,대두,밀')), [])

    def test_괄호_표기를_미선언으로_보지_않는다(self):
        """
        "알류(달걀)" 이라고 적힌 라벨을 "알류 미선언" 으로 지적하면, 규정대로
        적을수록 경고가 나온다.
        """
        from v1.label.services.validation_service import check_allergens

        label = self._label('알류(달걀), 우유', rawmtrl='정제수, 달걀, 우유')
        self.assertEqual(check_allergens(label), [])

    def test_키워드로만_적혀_있어도_미선언이_아니다(self):
        from v1.label.services.validation_service import check_allergens

        label = self._label('달걀, 우유', rawmtrl='정제수, 달걀, 우유')
        self.assertEqual(check_allergens(label), [])

    def test_정말_빠졌으면_지적한다(self):
        from v1.label.services.validation_service import check_allergens

        label = self._label('우유', rawmtrl='정제수, 달걀, 우유')
        issues = check_allergens(label)
        self.assertTrue(issues)
        self.assertIn('알류', issues[0]['message'])


class FalsePositiveNameMatchTests(TestCase):
    """
    한국어에는 낱말 경계가 없다. 목록의 이름이 다른 낱말 안에 그대로 들어간다.

        오리지널 타코    -> "오리"      오리엔탈 드레싱 -> "오리"
        굴소스 볶음밥    -> "굴"        무스케이크      -> "무"

    "오리지널 타코" 가 「제품명에 사용한 원재료의 함량 표시」 위반으로 지적됐다.
    글자가 겹쳤을 뿐인데 사용자는 고칠 방법이 없다.
    """

    def setUp(self):
        from django.core.cache import cache

        from v1.label.services import validation_service as vs

        # DB(AgriculturalProduct)에서 오는 이름을 흉내 낸다. 하드코딩 목록에는
        # "오리" 가 없어서, 이 사고는 DB 목록이 실린 서버에서만 났다.
        cache.set(vs._FARM_SEAFOOD_CACHE_KEY,
                  list(vs.FARM_SEAFOOD_ITEMS) + ['오리', '굴'], 60)
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(username='fp', password='x')

    def _label(self, name, rawmtrl='', info=''):
        return MyLabel(user_id=self.user, my_label_name=name, prdlst_nm=name,
                       rawmtrl_nm_display=rawmtrl, ingredient_info=info)

    def _check(self, name, rawmtrl='', info=''):
        from v1.label.services.validation_service import check_farm_seafood_content
        return check_farm_seafood_content(self._label(name, rawmtrl, info))

    def test_들어_있지_않으면_제품명이_그_원료를_쓴_것이_아니다(self):
        """규정이 요구하는 것은 「제품명에 **사용한** 원재료」의 함량이다."""
        self.assertEqual(
            self._check('오리지널 타코', '밀가루, 토마토페이스트, 정제수, 오리엔탈소스'), [])
        self.assertEqual(self._check('굴소스 볶음밥', '쌀, 굴소스(대두), 양파'), [])
        self.assertEqual(self._check('무스케이크', '밀가루, 무염버터 20%, 설탕'), [])

    def test_진짜로_들어_있으면_지적한다(self):
        issues = self._check('굴 죽', '쌀, 굴 12%, 참기름')
        self.assertEqual(len(issues), 1)
        self.assertIn('굴', issues[0]['message'])

    def test_형태_꼬리말이_붙어도_같은_원료다(self):
        """"오리고기 45%" 는 분명히 오리다."""
        issues = self._check('오리불고기', '오리고기 45%, 양파, 간장')
        self.assertEqual(len(issues), 1)
        self.assertIn('오리', issues[0]['message'])

    def test_함량을_적었으면_조용하다(self):
        self.assertEqual(
            self._check('오리불고기', '오리고기 45%, 양파', '오리고기 45%'), [])

    def test_괄호_안의_이름도_찾는다(self):
        """"쇠고기(한우, 국산) 20%" 의 한우는 괄호 안에 있다."""
        issues = self._check('한우 곰탕', '쇠고기(한우, 국산) 20%, 정제수')
        self.assertEqual(len(issues), 1)
        self.assertIn('한우', issues[0]['message'])

    def test_다른_낱말_안의_글자는_원료가_아니다(self):
        from v1.label.services.validation_service import _is_same_item

        for token, item, same in (
            ('오리', '오리', True),
            ('오리고기', '오리', True),
            ('오리엔탈소스', '오리', False),
            ('무염버터', '무', False),
            ('단무지', '무', False),
            ('새우살', '새우', True),
            ('굴소스', '굴', False),
        ):
            self.assertIs(_is_same_item(token, item), same, f'{token} vs {item}')

    def test_원재료명에_없으면_침묵한다(self):
        """
        제품명에는 썼는데 원재료명에 안 적은 라벨은 조용히 넘어간다. 그건 함량
        미표시가 아니라 원재료 누락이고, "함량이 확인되지 않습니다" 라고 말하면
        사용자를 엉뚱한 칸으로 보낸다. 잘못 지적하는 쪽보다 침묵을 골랐다.
        """
        self.assertEqual(self._check('오리 만두', '밀가루, 양파, 정제수'), [])


class AllergenFalseFriendTests(TestCase):
    """
    알레르기 키워드를 글자로 품고 있지만 그 물질이 아닌 원료 이름.

    한 글자 키워드("밀", "게")가 긴 이름 안에 그대로 들어간다. 알레르기는
    놓치는 쪽이 훨씬 나쁘므로 관대하게 잡는 것이 기본이지만, 확실히 아닌 것을
    지적하면 사용자가 **없는 알레르기를 선언하게** 된다.
    """

    def _issues(self, rawmtrl, declared=''):
        from v1.label.services.validation_service import check_allergens

        user = User.objects.create_user(username=f'ff{User.objects.count()}', password='x')
        label = MyLabel(user_id=user, my_label_name='제품', prdlst_nm='제품',
                        rawmtrl_nm_display=rawmtrl, allergens=declared)
        return check_allergens(label)

    def test_밀이_아닌_것을_밀로_보지_않는다(self):
        for text in ('정제수, 아밀라아제, 옥수수전분', '밀랍, 정제수', '설탕, 당밀'):
            self.assertEqual(self._issues(text), [], text)

    def test_게가_아닌_것을_게로_보지_않는다(self):
        self.assertEqual(self._issues('게르마늄효모, 정제수'), [])

    def test_진짜는_그대로_잡는다(self):
        """목록에 없는 것은 예전처럼 관대하게 잡는다."""
        self.assertTrue(self._issues('밀가루 40%, 정제수'))
        self.assertTrue(self._issues('어묵(연육, 게살)'))
        # 대두레시틴은 정말 대두다 — 빼지 않았다
        self.assertTrue(self._issues('정제수, 대두레시틴'))

    def test_선언했으면_조용하다(self):
        self.assertEqual(self._issues('밀가루 40%', '밀'), [])


class ForbiddenPhraseExceptionTests(TestCase):
    """
    금지 문구를 글자로 품고 있지만 고시된 표준 용어라 쓸 수 있는 말.

    "자연치즈" 는 식품유형 이름이고 "천연향료" 는 식품첨가물 공전의 명칭이다.
    규정대로 적은 라벨이 금지 문구로 지적되면 고치라는 대로 고칠 수가 없다.
    """

    def _issues(self, field, value):
        from v1.label.services.validation_service import check_forbidden_phrases

        user = User.objects.create_user(username=f'fp{User.objects.count()}', password='x')
        label = MyLabel(user_id=user, my_label_name='제품', prdlst_nm='제품')
        setattr(label, field, value)
        return check_forbidden_phrases(label)

    def test_고시된_용어는_지적하지_않는다(self):
        self.assertEqual(self._issues('rawmtrl_nm_display', '자연치즈 25%, 정제수'), [])
        self.assertEqual(self._issues('rawmtrl_nm_display', '정제수, 천연향료'), [])

    def test_그_밖에는_예전처럼_지적한다(self):
        """확실한 것만 예외로 뒀다 — 넓히면 잡아야 할 것을 놓친다."""
        self.assertTrue(self._issues('prdlst_nm', '천연 그대로 주스'))
        self.assertTrue(self._issues('rawmtrl_nm_display', '자연산 대구'))


class NutritionInputBasisTests(TestCase):
    """
    라벨에 인쇄된 값을 **그대로** 넣을 수 있어야 한다.

    라벨의 영양성분표는 그 표가 밝힌 기준으로 인쇄돼 있다.

        총 내용량 65 g / 65 g 당 309 kcal

    그런데 저장 칸은 언제나 100 g 당이라, 예전에는 사용자가 손으로 환산해야
    했다. 라벨을 옮겨 적는 사람이 그걸 알 리가 없어서 309 를 그대로 넣었고,
    화면은 309 × 65/100 = 200 kcal 로 표를 그렸다. 사용자는 단위량을 100 으로
    바꿔 표를 맞췄고, 그러면 총 내용량이 100 g 으로 찍혔다 — **한 오류를 다른
    오류로 바꾼 셈이다.**

    사진 판독은 표의 기준을 읽어 이미 환산한다(ocr_apply.to_per_100).
    손으로 넣는 쪽도 같은 일을 하게 했다.
    """

    def setUp(self):
        from pathlib import Path

        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/nutrition_calculator_popup.js'
                   ).read_text(encoding='utf-8')
        self.html = (base / 'templates/label/nutrition_calculator_popup.html'
                     ).read_text(encoding='utf-8')

    def test_입력_기준을_고를_수_있다(self):
        self.assertIn('id="nutrition_input_basis"', self.html)
        for value in ('per_100', 'total', 'unit'):
            self.assertIn(f'value="{value}"', self.html)

    def test_환산은_한_곳에서_한다(self):
        """
        미리보기도 저장도 getNutritionInputsFromDOM 을 지난다. 환산을 한 곳에서
        하면 화면에 그린 표와 저장되는 값이 어긋날 수가 없다.
        """
        head = self.js.index('function getNutritionInputsFromDOM')
        block = self.js[head:head + 1400]
        self.assertIn('inputBasisFactor()', block)
        self.assertIn('numericValue * factor', block)
        # 환산 함수를 부르는 곳은 그 한 곳과 안내 문구뿐이다
        self.assertEqual(self.js.count('inputBasisFactor()'), 3)   # 정의 + 안내 + 수집

    def test_기준량을_모르면_환산하지_않는다(self):
        """분모를 모르면서 곱하면 모든 수치의 뜻이 바뀐다."""
        head = self.js.index('function inputBasisFactor')
        block = self.js[head:head + 700]
        self.assertIn('if (!(amount > 0)) return 1;', block)

    def test_다시_열면_기준을_되돌린다(self):
        """
        저장된 값이 이미 100 g 당이라, 기준이 '총 내용량당' 인 채로 다시
        저장하면 같은 값에 환산이 두 번 걸린다(309 → 475 → 731).
        """
        self.assertIn("inputBasisEl.value = 'per_100';", self.js)

    def test_무엇이_저장되는지_그_자리에서_보여_준다(self):
        """말해 두지 않으면 "내가 넣은 숫자가 왜 바뀌었지" 가 된다."""
        self.assertIn('function updateInputBasisNote', self.js)
        self.assertIn('id="inputBasisNote"', self.html)
        self.assertIn('다시 열면 환산된 값이 보입니다', self.js)

    def test_기준량이_바뀌면_안내도_바뀐다(self):
        head = self.js.index("[servingSizeInput, unitsPerPackageInput].forEach")
        block = self.js[head:head + 600]
        self.assertIn("addEventListener('input', updateInputBasisNote)", block)

    def test_단위량이_무엇인지_화면이_말해_준다(self):
        """이 칸에 무엇을 넣을지 몰라 100 을 넣은 것이 이번 사고의 출발이었다."""
        self.assertIn('총 내용량 = 단위량 × 포장개수', self.html)
        self.assertIn('포장개수는 1 로 둡니다', self.html)


class PrintedRowsFollowDisplayChecksTests(TestCase):
    """
    표에 줄이 생기는 기준은 표시 항목 체크(chckd_*) 하나다.

    예전에는 "값이 있으면 나간다" 였다. 규정 검증은 체크를 근거로 판정하므로
    두 화면이 서로 다른 말을 했다 — 끈 항목이 인쇄되고(체크 기본값이 'N' 인
    원산지·보관방법 등), 켠 항목은 비어 있어도 아무 데도 안 보였다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='rows', password='x')
        self.label = MyLabel.objects.create(
            user_id=self.user, my_label_name='표 기준',
            prdlst_nm='제품', country_of_origin='국내산',
            chckd_prdlst_nm='Y', chckd_country_of_origin='N',
        )

    def _checked(self):
        from v1.label.constants import preview_display_checked
        return preview_display_checked(self.label)

    def test_끈_항목은_값이_있어도_표에_안_나간다(self):
        self.assertTrue(self._checked()['prdlst_nm'])
        self.assertFalse(self._checked()['country_of_origin'])

    def test_값은_끈_항목도_함께_보낸다(self):
        """미리보기에서 다시 켤 수 있어야 하고, 켜는 순간 무엇이 인쇄될지 보여야 한다."""
        from v1.label.constants import preview_display_data

        data = preview_display_data(self.label)
        self.assertEqual(data['country_of_origin'], '국내산')
        # 켜 두고 비어 있는 항목도 자리를 만든다
        self.assertEqual(data['storage_method'], '')

    def test_인쇄_대상이_아닌_값은_애초에_빠진다(self):
        """
        라벨명은 내부에서 부르는 이름인데 표에 '라벨명' 줄로 인쇄되고 있었다.
        원재료명(참고)도 '원재료명' 행을 하나 더 만들었다.
        """
        from v1.label.constants import preview_display_data

        data = preview_display_data(self.label)
        self.assertNotIn('my_label_name', data)
        self.assertNotIn('rawmtrl_nm', data)
        self.assertNotIn('nutrition_text', data)

    def test_원재료명은_참고_칸으로_갈음한다(self):
        """V2 기본정보 탭과 BOM 은 참고 쪽에 쓰는데 인쇄물에는 한 줄로 나가야 한다."""
        from v1.label.constants import preview_display_data

        self.label.rawmtrl_nm = '밀가루(밀:미국산), 설탕'
        self.label.rawmtrl_nm_display = ''
        self.assertEqual(
            preview_display_data(self.label)['rawmtrl_nm_display'],
            '밀가루(밀:미국산), 설탕')

    def test_미리보기가_체크_상태를_함께_받는다(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('label:label_tab_json'), {'label_id': self.label.my_label_id})
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['display_checked']['prdlst_nm'])
        self.assertFalse(body['display_checked']['country_of_origin'])
        self.assertEqual(body['display_data']['prdlst_nm'], '제품')


class FieldLayoutLivesOnLabelTests(TestCase):
    """
    항목 순서·폭·배치는 라벨에 저장한다.

    지금까지 localStorage 의 'labelFieldOrder' 키 하나뿐이었다. 라벨별이 아니라
    브라우저별이라, 한 라벨에서 맞춰 둔 순서가 다른 라벨에 그대로 얹혔고 옆자리
    동료는 아예 다른 순서를 봤다. 인쇄물의 모양인데 그럴 수 없다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='layout', password='x')
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='배치')
        self.client.force_login(self.user)

    def _save(self, payload):
        return self.client.post(
            reverse('label:save_preview_settings'),
            data=json.dumps({'label_id': self.label.my_label_id, **payload}),
            content_type='application/json')

    def test_항목_배치가_라벨에_저장된다(self):
        self._save({'field_layout': {
            'order': ['prdlst_nm', 'content_weight'],
            'width': {'prdlst_nm': '100%'},
            'layoutMode': 'horizontal',
        }})
        self.label.refresh_from_db()
        self.assertEqual(self.label.prv_field_layout['order'],
                         ['prdlst_nm', 'content_weight'])
        self.assertEqual(self.label.prv_field_layout['layoutMode'], 'horizontal')

    def test_안_보내면_건드리지_않는다(self):
        """설정 창만 만진 저장에서 순서가 초기화되면 인쇄물 모양이 조용히 달라진다."""
        self.label.prv_field_layout = {'order': ['prdlst_nm'], 'width': {},
                                       'layoutMode': 'vertical'}
        self.label.save()

        self._save({'font_size': 11})
        self.label.refresh_from_db()
        self.assertEqual(self.label.prv_field_layout['order'], ['prdlst_nm'])


class PreviewSwitchesAreOneTests(TestCase):
    """미리보기의 눈 아이콘과 표시 항목 체크는 같은 스위치여야 한다."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.creation = (base / 'static/js/label/label_creation.js').read_text(encoding='utf-8')
        self.tab = (base / 'templates/products/_tab_label.html').read_text(encoding='utf-8')

    def test_표가_체크를_본다(self):
        self.assertIn('function isFieldShown', self.js)
        self.assertIn('window.displayChecked[fieldKey] === true', self.js)
        # 값 유무로 판정하던 자리가 남아 있으면 두 기준이 다시 갈린다
        self.assertNotIn('fieldOrderData.visibility', self.js)

    def test_눈_아이콘은_부모에게_넘긴다(self):
        """이 창이 따로 저장하면 스위치가 둘이 되고 저장·권한도 두 벌이 된다."""
        self.assertIn("type: 'toggleDisplayItem'", self.js)
        self.assertIn("'toggleDisplayItem'", self.creation)
        self.assertIn("'toggleDisplayItem'", self.tab)

    def test_죽은_레이아웃이_없다(self):
        """누르면 세로로 되돌아오던 '가로형' 과, 없는 요소를 읽던 layoutSelect."""
        from pathlib import Path
        from django.conf import settings as dj

        html = (Path(dj.BASE_DIR) / 'templates/label/label_preview.html'
                ).read_text(encoding='utf-8')
        self.assertNotIn('data-layout="grid"', html)
        self.assertNotIn("getElementById('layoutSelect')", self.js)

    def test_두_곳의_항목_목록이_같다(self):
        """
        서버(PREVIEW_DISPLAY_FIELDS)와 화면(DEFAULT_FIELDS)이 어긋나면, 서버가
        보낸 항목을 화면이 못 알아보고 조용히 빠뜨린다. 한쪽만 고쳐지는 일이
        잦은 자리라 시험으로 묶어 둔다.
        """
        import re
        from v1.label.constants import PREVIEW_DISPLAY_FIELDS

        block = self.js[self.js.index('const DEFAULT_FIELDS = {'):]
        block = block[:block.index('\n};')]
        keys = re.findall(r"^\s*'([a-z_]+)':", block, re.MULTILINE)
        self.assertEqual(sorted(keys), sorted(PREVIEW_DISPLAY_FIELDS))

class PreviewHasOneOfEachTests(TestCase):
    """
    미리보기의 기능은 한 벌만 있어야 한다.

    label_preview.html 인라인 스크립트와 label_preview.js 에 같은 이름의 함수가
    열일곱 개 있었고, 그중 exportToPDF 와 savePreviewSettings 는 **둘 다 같은
    버튼에 붙어** 있었다. PDF 저장을 한 번 누르면 두 개가 내려받아졌고(크기
    계산도 서로 달랐다), 설정 저장은 두 번 나가서 나중에 도착하는 쪽이 이겼다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')

    def test_pdf_저장이_한_곳이다(self):
        self.assertEqual(self.js.count('async function exportToPDF'), 1)
        self.assertNotIn('function exportToPDF', self.html)
        self.assertNotIn("exportPdfBtn')?.addEventListener", self.html)

    def test_설정_저장이_한_곳이다(self):
        self.assertEqual(self.js.count('function savePreviewSettings'), 1)
        self.assertNotIn('function savePreviewSettings', self.html)

    def test_pdf_가_문서함에도_올라간다(self):
        """내려받기만 하던 사본이 이겨 버리면 문서함 등록이 조용히 사라진다."""
        self.assertIn('/label/upload-label-pdf/', self.js)
        self.assertIn('log-pdf-save', self.js)

    def test_화면_전용_표시는_pdf_에_안_들어간다(self):
        self.assertIn("previewContent.classList.add('pv-exporting')", self.js)
        self.assertIn("classList.remove('pv-exporting')", self.js)


class NutritionOnLabelTests(TestCase):
    """
    영양정보 표는 표시사항 미리보기에 함께 그려지고 PDF 도 한 장으로 나온다.

    표를 만드는 코드는 있었는데 **그릴 자리(#nutritionPreview)가 템플릿에 아예
    없었다.** 그래서 영양성분은 미리보기에도 PDF 에도 나오지 않았고, 영양성분
    탭에는 PDF 기능이 없어 어디로도 나갈 수 없었다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')
        self.editor = (base / 'templates/products/nutrition_editor.html').read_text(encoding='utf-8')

    def test_그릴_자리가_있다(self):
        self.assertIn('id="nutritionPreview"', self.html)
        # previewContent 안에 있어야 PDF 캡처에 함께 들어간다
        head = self.html.index('id="previewContent"')
        tail = self.html.index('</section>', head)
        self.assertIn('id="nutritionPreview"', self.html[head:tail])

    def test_표시_항목_체크가_켜고_끈다(self):
        self.assertIn('function isNutritionShown', self.js)
        self.assertIn('window.displayChecked.nutrition_text', self.js)
        # 예전에는 이 화면에 있지도 않은 탭("#nutrition-tab")이 활성화됐는지를
        # 봤다. 그래서 늘 숨겨졌다.
        head = self.js.index('function updateNutritionDisplay')
        block = self.js[head:head + 6000]
        self.assertNotIn("data-bs-target') === '#nutrition-tab'", block)

    def test_세로_길이에_영양정보_높이가_들어간다(self):
        """빼고 재면 인쇄물이 잘린다."""
        head = self.js.index('function calculateHeight')
        block = self.js[head:head + 900]
        self.assertIn('nutritionHeight', block)

    def test_영양성분_탭은_같은_길을_안내한다(self):
        self.assertIn('한글표시사항도안', self.editor)
        self.assertIn('openLabelTab', self.editor)
        # 영양성분 탭이 따로 PDF 를 만들지 않는다 (생성기를 두 벌로 두지 않는다)
        self.assertNotIn('jspdf', self.editor.lower())

    def test_체크_상태에_영양성분이_실린다(self):
        from v1.label.constants import preview_display_checked

        user = User.objects.create_user(username='nutri', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='영양',
                                       chckd_nutrition_text='Y')
        self.assertTrue(preview_display_checked(label)['nutrition_text'])


class TableIsARealTableTests(TestCase):
    """2단 배치가 진짜 표 구조인가. 열 너비는 한 곳이 정하는가."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/label_preview.css').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')

    def test_tr_안에_div_를_넣지_않는다(self):
        """화면·브라우저 인쇄·html2canvas 가 서로 다른 것을 그릴 여지가 있었다."""
        head = self.js.index('function renderHorizontalLayout')
        block = self.js[head:head + 12000]
        self.assertNotIn('itemContainer', block)
        self.assertIn('td.colSpan = 3', block)

    def test_열_너비는_colgroup_이_정한다(self):
        self.assertIn('function applyColumnGroup', self.js)
        self.assertIn('pv-col-label', self.js)
        self.assertIn('.preview-table col.pv-col-label', self.css)

    def test_항목명_칸_너비를_사용자가_정한다(self):
        self.assertIn('id="labelColWidthInput"', self.html)
        self.assertIn('--label-col-width', self.html)
        self.assertIn('labelColumnMm', self.js)

    def test_알레르기_박스가_글자_크기를_따른다(self):
        """인라인 9pt 로 박아 두면 설정을 올려도 이 줄만 미달로 인쇄된다."""
        self.assertIn('pv-allergen-box', self.js)
        self.assertNotIn('font-size: 9pt', self.js)


class ValidationPointsAtRowsTests(TestCase):
    """지적이 표의 어느 줄에 대한 말인지 서버가 함께 준다."""

    def setUp(self):
        self.user = User.objects.create_user(username='vrow', password='x')

    def test_지적에_필드가_실린다(self):
        from v1.label.services.validation_service import check_forbidden_phrases

        label = MyLabel.objects.create(user_id=self.user, my_label_name='금지',
                                       prdlst_nm='천연 사과주스')
        issues = check_forbidden_phrases(label)
        self.assertTrue(issues)
        self.assertIn('prdlst_nm', issues[0]['fields'])

    def test_묶어도_필드가_남는다(self):
        from v1.label.services.ai_validation_service import group_issues_by_category
        from v1.label.services.validation_service import _issue

        rows = group_issues_by_category([_issue('recycling_mark', '어긋남', '고치세요')])
        row = next(r for r in rows if not r['ok'])
        self.assertEqual(row['fields'], ['frmlc_mtrqlt'])

    def test_줄이_없는_지적도_있다(self):
        """글자 크기는 표 설정이지 표의 한 줄이 아니다."""
        from v1.label.services.validation_service import _issue

        self.assertEqual(_issue('font_size', '작습니다')['fields'], [])

    def test_표의_행이_자기_이름을_안다(self):
        from pathlib import Path
        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.assertIn('tr.dataset.fieldRow = fieldKey', js)
        self.assertIn('function markValidationOnTable', js)
        self.assertIn('function jumpToTableRow', js)


class FontSizeCheckTests(TestCase):
    """
    활자 크기 검사.

    서버 검증이 생기면서 통째로 빠져 있었다 — 규정 도구가 규정 하나를 아예 안
    보고 있었다. 화면 하한(enforceInputMinMax)은 타이핑할 때만 도는 것이라
    예전에 저장해 둔 작은 값은 그대로 남는다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='font', password='x')

    def _label(self, size):
        return MyLabel.objects.create(user_id=self.user, my_label_name='글자',
                                      prv_font_size=size)

    def test_하한보다_작으면_지적한다(self):
        from v1.label.services.validation_service import check_font_size

        issues = check_font_size(self._label('8'))
        self.assertEqual(len(issues), 1)
        self.assertIn('8 포인트', issues[0]['message'])
        self.assertIn('10 포인트', issues[0]['message'])

    def test_하한_이상이면_조용하다(self):
        from v1.label.services.validation_service import check_font_size

        self.assertEqual(check_font_size(self._label('10')), [])
        self.assertEqual(check_font_size(self._label('12')), [])

    def test_설정한_적_없으면_보지_않는다(self):
        """저장한 적 없는 값을 근거로 지적하면 고칠 방법이 없는 경고가 된다."""
        from v1.label.services.validation_service import check_font_size

        self.assertEqual(check_font_size(self._label('')), [])

    def test_전체_검증에_들어_있다(self):
        from v1.label.services.validation_service import validate_label

        result = validate_label(self._label('7'))
        self.assertIn('font_size', [i['category'] for i in result['issues']])
        self.assertTrue(any('활자 크기' in r for r in result['checked_regulations']))

class DisplayCheckMigrationTests(TestCase):
    """
    0023 — 지금까지 인쇄되던 줄을 표시 항목 체크에 옮겨 적는다.

    표에 줄이 생기는 기준이 "값이 있는가" 에서 "체크가 켜졌는가" 로 바뀌었다.
    그런데 체크박스 기본값은 원산지·보관방법·유통전문판매원·소분원·수입원·
    기타표시사항이 전부 'N' 이라, 그대로 두면 이미 만들어 둔 라벨에서 그 줄들이
    말없이 사라진다. 이 마이그레이션이 그 구멍을 막는다.

    (테스트는 마이그레이션을 실행하지 않으므로 — settings_test 참고 — 함수를
    직접 부른다. 판정 논리가 여기 있고, 그것이 검사할 값어치가 있는 부분이다.)
    """

    def setUp(self):
        import importlib

        self.migration = importlib.import_module(
            'v1.label.migrations.0023_display_check_matches_printed_rows')
        self.user = User.objects.create_user(username='mig', password='x')

    def _run(self):
        class Apps:
            def get_model(self, app_label, model_name):
                return MyLabel

        self.migration.turn_on_checks_for_filled_fields(Apps(), None)

    def test_값이_있는데_꺼진_체크를_켠다(self):
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='이관',
            country_of_origin='국내산', chckd_country_of_origin='N',
            additional_info='부정불량식품 신고 1399', chckd_additional_info='N',
        )
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_country_of_origin, 'Y')
        self.assertEqual(label.chckd_additional_info, 'Y')

    def test_원재료명은_참고_칸도_본다(self):
        """V2 기본정보 탭과 BOM 은 참고 쪽에 쓰는데 인쇄물에는 나온다."""
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='원재료',
            rawmtrl_nm='밀가루(밀:미국산), 설탕', rawmtrl_nm_display='',
            chckd_rawmtrl_nm_display='N',
        )
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_rawmtrl_nm_display, 'Y')

    def test_켜졌는데_빈_항목은_끄지_않는다(self):
        """그쪽은 "아직 안 채웠다" 는 뜻이고, 미리보기가 빈 줄로 보여 줄 몫이다."""
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='미입력',
            storage_method='', chckd_storage_method='Y',
        )
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_storage_method, 'Y')

    def test_값이_없으면_켜지_않는다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='빈 라벨')
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_country_of_origin, 'N')

    def test_영양성분을_적어_둔_라벨은_켠다(self):
        """
        이쪽은 "지금 인쇄되던 것" 이 아니다 — 영양정보 표를 그릴 자리가 화면에
        아예 없어서 어디에도 나오지 않고 있었다. 값을 넣은 사람은 라벨에 나올
        것으로 알고 넣었다.
        """
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='영양',
            calories='318', natriums='230', chckd_nutrition_text='N',
        )
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_nutrition_text, 'Y')

    def test_영양성분이_없으면_켜지_않는다(self):
        label = MyLabel.objects.create(user_id=self.user, my_label_name='무영양')
        self._run()
        label.refresh_from_db()
        self.assertEqual(label.chckd_nutrition_text, 'N')

    def test_목록이_서버_상수와_같다(self):
        """한쪽만 고쳐지면 새 항목이 이관에서 조용히 빠진다."""
        from v1.label.constants import PREVIEW_DISPLAY_FIELDS

        self.assertEqual(tuple(self.migration.FIELDS), PREVIEW_DISPLAY_FIELDS)

class PreviewInitSurvivesMissingDataTests(TestCase):
    """
    미리보기 초기화가 영양성분 데이터 하나에 매달려 있었다.

    DOMContentLoaded 본문에 이 코드가 그대로 있었다.

        const nutritionData = safeLoadJsonData('nutrition-data', null, …);
        …
        if (!nutritionData) { return; }

    그런데 이 화면에는 #nutrition-data 요소가 **아예 없었다.** 그래서 그 return
    이 늘 걸렸고, 뒤에 있는 초기화가 통째로 실행되지 않았다 — PDF 저장·설정
    저장 버튼 연결, 세로 길이 계산, 입력 하한, 저장된 설정 불러오기까지.

    그동안 PDF 와 설정 저장이 동작한 것은 인라인 스크립트에 같은 함수가 한 벌
    더 있어서였다. 그 사본을 걷어내자 결함이 드러나 PDF 가 아예 안 눌렸다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')

    def test_영양성분_처리는_함수_안에_있다(self):
        """return 이 DOMContentLoaded 전체를 끊으면 안 된다."""
        self.assertIn('function initNutritionData', self.js)
        head = self.js.index('function initNutritionData')
        self.assertIn('if (!nutritionData) {', self.js[head:head + 800])

    def test_초기화가_영양성분_뒤에_온다(self):
        """순서가 뒤집히면 같은 사고가 다시 난다."""
        nutrition = self.js.index('initNutritionData();')
        pdf = self.js.index("safeAddEventListener('exportPdfBtn'")
        self.assertLess(nutrition, pdf)

    def test_영양성분_데이터를_실어_보낸다(self):
        """뷰는 진작부터 넘기고 있었는데 화면에 그 자리가 없었다."""
        self.assertIn('id="nutrition-data"', self.html)
        self.assertIn('{{ nutrition_data|safe }}', self.html)

    def test_뷰가_그_값을_준다(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='prev', password='x')
        label = MyLabel.objects.create(user_id=user, my_label_name='미리보기',
                                       calories='318', serving_size='65')
        self.client.force_login(user)
        resp = self.client.get(reverse('label:preview_popup'),
                               {'label_id': label.my_label_id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nutrition_data', resp.context)
        self.assertIn('318', resp.context['nutrition_data'])


class RowToolsShowWhatWorksTests(TestCase):
    """줄 도구는 지금 할 수 있는 것만 보여 준다."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/label_preview.css').read_text(encoding='utf-8')

    def test_틈을_지나도_사라지지_않는다(self):
        """
        줄과 도구 사이가 6px 떨어져 있어서, 그 틈을 지나는 순간 마우스가 줄
        밖으로 나가면서 도구가 사라졌다. 재빨리 움직여야 겨우 누를 수 있었다.
        """
        self.assertIn('function scheduleRowToolsHide', self.js)
        self.assertIn('function cancelRowToolsHide', self.js)
        self.assertIn("tools.addEventListener('mouseenter', cancelRowToolsHide)", self.js)

    def test_세로_배치에서는_폭_버튼이_없다(self):
        """한 줄에 한 항목이라 눌러도 아무 일이 없었다."""
        head = self.js.index('function showRowTools')
        block = self.js[head:head + 2500]
        self.assertIn("fieldOrderData.layoutMode === 'horizontal'", block)
        self.assertIn('widthBtn.hidden = !canWidth', block)

    def test_숨긴_버튼은_자리를_차지하지_않는다(self):
        self.assertIn('.pv-rowtools button[hidden] { display: none; }', self.css)


class IssueNumbersTests(TestCase):
    """부적합 항목이 몇 번 지적인지 표와 모달이 같은 번호로 말한다."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/label_preview.css').read_text(encoding='utf-8')

    def test_번호를_매긴다(self):
        self.assertIn('function numberValidationIssues', self.js)
        self.assertIn('row._numbers', self.js)

    def test_배지가_실제로_보인다(self):
        """예전에는 표시를 만들어 놓고 CSS 에서 display:none 으로 죽여 뒀다."""
        self.assertIn('pv-issue-badge', self.js)
        head = self.css.index('.pv-issue-badge {')
        rule = self.css[head:self.css.index('}', head)]
        self.assertIn('display: inline-block', rule)
        self.assertNotIn('display: none', rule)
        # 인쇄물에는 들어가지 않는다
        self.assertIn('.pv-exporting .pv-issue-badge { display: none !important; }', self.css)

    def test_모달이_어느_줄인지_사람_말로_적는다(self):
        self.assertIn('function tableRowName', self.js)
        self.assertIn('vr-where', self.js)


class LabelColumnFitsTests(TestCase):
    """항목명이 칸을 넘으면 칸이 넓어진다."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        self.html = (Path(dj.BASE_DIR) / 'templates/label/label_preview.html'
                     ).read_text(encoding='utf-8')

    def test_설정값은_최소값이다(self):
        """'유통전문판매원' 은 기본 24mm 를 넘는다. 잘린 항목명은 틀린 표시다."""
        self.assertIn('항목명 칸 (mm, 최소)', self.html)
        head = self.html.index('const minPx = colMm / 10 * CM_TO_PX;')
        block = self.html[head:head + 1600]
        self.assertIn('Math.max(minPx', block)
        self.assertIn('cell.scrollWidth', block)

    def test_좁혀_두고_잰다(self):
        """
        'auto' 로 풀고 재면 안 된다 — table-layout:fixed 에서 auto 는 남는 폭을
        열끼리 나눠 갖는 것이라, scrollWidth 가 글자 폭이 아니라 표의 절반을
        돌려준다. 그래서 항목명 칸이 통째로 넓어졌다.
        """
        head = self.html.index('const minPx = colMm / 10 * CM_TO_PX;')
        block = self.html[head:head + 1400]
        self.assertIn("setProperty('--label-col-width', '1px')", block)
        self.assertNotIn("setProperty('--label-col-width', 'auto')", block)


class AllergenBoxFlowsInlineTests(TestCase):
    """알레르기 선언은 원재료명 끝에 이어 붙고, 자리가 없을 때만 내려간다."""

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        self.css = (Path(dj.BASE_DIR) / 'static/css/label_preview.css'
                    ).read_text(encoding='utf-8')

    def test_줄바꿈을_강제하지_않는다(self):
        head = self.css.index('.pv-allergen-box {')
        block = self.css[head:head + 700]
        self.assertIn('display: inline-block;', block)
        self.assertNotIn('display: block;', block)

class HumanReviewFindingsTests(TestCase):
    """
    사람이 도안을 검수하며 짚어 낸 것을 코드가 같이 잡는가.

    실제 검수 의견(브라우니 케이크)이 일곱 건이었다.

        1·2. 영양정보 머리글의 "65 g 당" -> "총 내용량 당"   (표를 그리는 쪽)
        3.   함량·비율을 계산식에 맞추어 수정                (check_calorie_matches_macros)
        4.   해동방법 표시                                   (check_thawing_method)
        5.   제품교환장소 추가                               (check_exchange_notice)
        6.   혼합분유/네덜란드산 볼드 표시                    (check_origin_emphasis)
        7.   과당1 -> 과당]                                  (check_rawmtrl_brackets, 이미 있던 것)
    """

    def setUp(self):
        from django.core.cache import cache

        cache.clear()   # 국가명 목록이 시험 사이에 남아 돌아다니지 않게
        self.user = User.objects.create_user(username='review', password='x')

    def _label(self, **kwargs):
        return MyLabel.objects.create(user_id=self.user, my_label_name='검수', **kwargs)

    # ── 3. 함량과 열량이 서로 다른 기준으로 적혀 있다 ──────────────────────

    def test_열량이_탄단지_계산값과_어긋나면_지적한다(self):
        """
        도안은 65 g 에 309 kcal 인데 탄수화물 9 · 지방 4.5 · 단백질 1 로 계산하면
        80 kcal 다. 열량만 총량 기준이고 나머지는 다른 기준으로 적힌 것이다.
        """
        from v1.label.services.validation_service import check_calorie_matches_macros

        issues = check_calorie_matches_macros(self._label(
            calories='309', carbohydrates='9', fats='4.5', proteins='1'))
        self.assertEqual(len(issues), 1)
        self.assertIn('309', issues[0]['message'])
        self.assertIn('80 kcal', issues[0]['message'])

    def test_계산이_맞으면_조용하다(self):
        from v1.label.services.validation_service import check_calorie_matches_macros

        # 66 x 4 + 4.5 x 9 + 1 x 4 = 308.5
        self.assertEqual(check_calorie_matches_macros(self._label(
            calories='309', carbohydrates='66', fats='4.5', proteins='1')), [])

    def test_반올림_폭으로는_지적하지_않는다(self):
        """
        표시기준의 반올림만으로도 몇 kcal 는 벌어진다. 그런 폭으로 울면
        정상인 라벨이 계속 지적된다.
        """
        from v1.label.services.validation_service import check_calorie_matches_macros

        # 계산값 100, 적어 둔 값 120 — 20 kcal 차이
        self.assertEqual(check_calorie_matches_macros(self._label(
            calories='120', carbohydrates='10', fats='5', proteins='5')), [])

    def test_값이_없으면_계산하지_않는다(self):
        from v1.label.services.validation_service import check_calorie_matches_macros

        self.assertEqual(check_calorie_matches_macros(self._label(calories='309')), [])
        self.assertEqual(check_calorie_matches_macros(self._label(
            carbohydrates='9', fats='4.5', proteins='1')), [])

    # ── 4. 해동방법 ────────────────────────────────────────────────────────

    def test_냉동식품에_해동방법이_없으면_지적한다(self):
        from v1.label.services.validation_service import check_thawing_method

        issues = check_thawing_method(self._label(
            prdlst_dcnm='빵류(가열하지 않고 섭취하는 냉동식품)',
            storage_method='냉동보관(-18℃ 이하)',
            cautions='부정불량식품 신고는 국번없이 1399'))
        self.assertEqual(len(issues), 1)
        self.assertIn('해동', issues[0]['message'])

    def test_해동_문구가_있으면_조용하다(self):
        from v1.label.services.validation_service import check_thawing_method

        self.assertEqual(check_thawing_method(self._label(
            storage_method='냉동보관(-18℃ 이하)',
            cautions='냉장실에서 3시간 해동 후 드십시오')), [])

    def test_냉동이_아니면_보지_않는다(self):
        from v1.label.services.validation_service import check_thawing_method

        self.assertEqual(check_thawing_method(self._label(
            storage_method='직사광선을 피해 실온 보관', cautions='')), [])

    # ── 5. 제품 교환 안내 ──────────────────────────────────────────────────

    def test_교환_안내가_없으면_지적한다(self):
        """신고 번호는 적으면서 교환 안내는 빠뜨린 라벨이 많다."""
        from v1.label.services.validation_service import check_exchange_notice

        issues = check_exchange_notice(self._label(
            cautions='부정불량식품 신고는 국번없이 1399'))
        self.assertEqual(len(issues), 1)
        self.assertIn('교환', issues[0]['message'])

    def test_교환_문구가_있으면_조용하다(self):
        from v1.label.services.validation_service import check_exchange_notice

        self.assertEqual(check_exchange_notice(self._label(
            cautions='제품에 이상이 있을 경우 구입처에서 교환해 드립니다')), [])

    def test_주의사항_자체가_비면_보지_않는다(self):
        """그건 필수 입력 검사가 말할 몫이다 — 같은 말을 두 번 하지 않는다."""
        from v1.label.services.validation_service import check_exchange_notice

        self.assertEqual(check_exchange_notice(self._label()), [])

    # ── 6. 원산지 굵게 표시 ────────────────────────────────────────────────

    def test_모르는_원산지는_굵게_못_칠한다고_알린다(self):
        from v1.label.models import CountryList
        from v1.label.services.validation_service import check_origin_emphasis

        CountryList.objects.create(country_code2='NL', country_name_ko='네덜란드')
        CountryList.objects.create(country_code2='US', country_name_ko='미국')

        issues = check_origin_emphasis(self._label(
            rawmtrl_nm_display='혼합분유/네덜란드산, 밀가루[밀/미국산], 코코아분말/왈론산'))
        self.assertEqual(len(issues), 1)
        self.assertIn('"왈론산"', issues[0]['message'])
        self.assertNotIn('네덜란드', issues[0]['message'])

    def test_국내산은_국가_목록에_없어도_괜찮다(self):
        from v1.label.models import CountryList
        from v1.label.services.validation_service import check_origin_emphasis

        CountryList.objects.create(country_code2='KR', country_name_ko='대한민국')
        self.assertEqual(check_origin_emphasis(self._label(
            rawmtrl_nm_display='전란액/국산, 정제소금/국내산')), [])

    def test_국가_목록을_못_읽으면_판정하지_않는다(self):
        """모르는 것을 근거로 지적하면 고칠 방법이 없는 경고가 된다."""
        from v1.label.services.validation_service import check_origin_emphasis

        self.assertEqual(check_origin_emphasis(self._label(
            rawmtrl_nm_display='혼합분유/네덜란드산')), [])

    # ── 7. 괄호 — 이미 있던 검사가 잡는다 ──────────────────────────────────

    def test_닫히지_않은_괄호를_잡는다(self):
        """도안의 "과당1" 은 "과당]" 이어야 했다. 그러면 과자[ 가 안 닫힌다."""
        from v1.label.services.validation_service import check_rawmtrl_brackets

        issues = check_rawmtrl_brackets(self._label(
            rawmtrl_nm_display='초콜릿(혼합형), 과자[밀가루, 설탕, 과당1 코코아분말'))
        self.assertTrue(issues)
        self.assertIn('닫히지 않았습니다', issues[0]['message'])

    # ── 전체 검증에 실려 있는가 ────────────────────────────────────────────

    def test_네_검사가_모두_돈다(self):
        from v1.label.services.validation_service import validate_label

        label = self._label(
            prdlst_dcnm='빵류(가열하지 않고 섭취하는 냉동식품)',
            storage_method='냉동보관(-18℃ 이하)',
            cautions='부정불량식품 신고는 국번없이 1399',
            calories='309', carbohydrates='9', fats='4.5', proteins='1')
        categories = {i['category'] for i in validate_label(label)['issues']}
        self.assertIn('calorie_macros', categories)
        self.assertIn('thawing_method', categories)
        self.assertIn('exchange_notice', categories)

    def test_권고_항목은_확정을_막지_않는다(self):
        """
        확인이나 사유를 받는 무게는 표시기준이 그렇게 적으라고 한 것에만 쓴다.
        교환 안내가 없다고 지금까지 만든 라벨 전부가 확인 절차를 거치면,
        사람은 그 창을 읽지 않고 넘기는 법을 익힌다.
        """
        from v1.label.services.validation_service import (
            check_exchange_notice, check_origin_emphasis, check_thawing_method,
        )

        advisory = check_exchange_notice(self._label(cautions='신고는 1399'))
        self.assertTrue(advisory[0]['advisory'])

        blocking = check_thawing_method(self._label(
            storage_method='냉동보관(-18℃ 이하)', cautions='신고는 1399'))
        self.assertFalse(blocking[0]['advisory'])

        self.assertEqual(check_origin_emphasis.__name__, 'check_origin_emphasis')

    def test_근거_규정을_밝힌다(self):
        from v1.label.services.validation_service import validate_label

        listed = ' '.join(validate_label(self._label())['checked_regulations'])
        for word in ('열량 산출', '해동', '교환', '원산지 표시 방법'):
            self.assertIn(word, listed)


class NutritionHeaderBasisTests(TestCase):
    """
    영양정보 표의 열 머리는 기준을 밝히는 말이다.

    검수에서 "영양정보 아래 65 g 당 -> 총 내용량 당 으로 수정" 이 나왔다.
    "당" 이 빠지면 그 열의 숫자가 총량인지 100 g 당인지 알 수 없다.
    """

    def test_머리글에_당이_붙는다(self):
        from pathlib import Path
        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        head = js.index('const tabMapShort = {')
        block = js[head:js.index('}', head)]
        self.assertIn('총 내용량 당', block)
        self.assertIn('단위내용량 당', block)

class DesignRepeatConflictTests(TestCase):
    """
    같은 값이 도안 안에서 두 번 적히는 자리를 대조한다.

    디자인 시안은 표시사항 표 하나로 끝나지 않는다. 내용량과 열량은 보통 세 곳에
    따로 적힌다 — 표, 영양정보 머리, 앞면 박스("-18℃ 이하 냉동보관 65 g
    (309 kcal)"). 표를 고치면서 박스를 안 고치는 일이 잦고, 판독은 표 값만
    뽑아 오므로 그 어긋남을 알 방법이 없었다. 원문에는 셋 다 들어 있는데도.
    """

    def _data(self, **values):
        return {field: {'value': value, 'confidence': 'high'}
                for field, value in values.items()}

    def test_앞면_박스의_내용량이_다르면_알린다(self):
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight='65 g'),
                      '내용량 65 g\n-18℃ 이하 냉동보관  70 g (309 kcal)')
        warnings = data['content_weight']['warnings']
        self.assertTrue(warnings)
        self.assertIn('70 g', warnings[0])
        self.assertIn('65 g', warnings[0])

    def test_열량이_다르면_알린다(self):
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight='65 g (309 kcal)'),
                      '내용량 65 g (309 kcal)\n총 내용량 65 g  475 kcal')
        warnings = data['content_weight']['warnings']
        self.assertTrue(any('475 kcal' in w for w in warnings))

    def test_같으면_조용하다(self):
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight='65 g (309 kcal)'),
                      '내용량 65 g (309 kcal)\n총 내용량 65 g  309 kcal')
        self.assertNotIn('warnings', data['content_weight'])

    def test_영양성분_표의_숫자는_내용량이_아니다(self):
        """
        나트륨 30 mg · 지방 4.5 g 까지 세면 표의 모든 줄이 "다른 내용량" 이 된다.
        """
        from v1.label.services.ocr_repeats import attach

        data = attach(
            self._data(content_weight='65 g'),
            '내용량 65 g\n나트륨 30 mg  탄수화물 9 g  지방 4.5 g  단백질 1 g')
        self.assertNotIn('warnings', data['content_weight'])

    def test_단위가_다르면_견주지_않는다(self):
        """65 g 과 1 L 는 서로 다른 것을 말할 수 있다."""
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight='65 g'),
                      '내용량 65 g\n권장 섭취량 1 L 의 물과 함께')
        self.assertNotIn('warnings', data['content_weight'])

    def test_값을_고치지는_않는다(self):
        """어느 쪽이 맞는지는 사진을 봐야 안다. 고르면 틀린 쪽을 고를 수도 있다."""
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight='65 g'), '내용량 65 g\n70 g')
        self.assertEqual(data['content_weight']['value'], '65 g')

    def test_읽은_값이_없으면_견주지_않는다(self):
        from v1.label.services.ocr_repeats import attach

        data = attach(self._data(content_weight=None), '어딘가에 70 g')
        self.assertNotIn('warnings', data['content_weight'])

    def test_판독_경로에_걸려_있다(self):
        from pathlib import Path
        from django.conf import settings as dj

        src = (Path(dj.BASE_DIR) / 'label/services/ocr_service.py').read_text(encoding='utf-8')
        self.assertIn('def _repeats_checked', src)
        # 한 장 경로와 여러 장 경로 둘 다
        self.assertEqual(src.count('result = _repeats_checked(result, ocr_text)'), 2)


class NutritionPlacementTests(TestCase):
    """
    영양정보 표의 자리.

    "표시사항이 세로로 길면 옆에 나란히" 를 #previewContent 를 flex 로 바꿔
    시도했다가 되돌렸다. 그 안에는 머리 띠, 요약 줄, 절대 위치로 떠 있는
    분리배출마크, 꼬리말이 함께 있어서 표와 영양정보만 나란히 세울 수가 없었고
    화면이 서로 겹쳤다. 제대로 하려면 둘을 감싸는 칸을 따로 만들어야 하고,
    그러면 인쇄물의 짜임새가 달라져 눈으로 보면서 맞춰야 한다.

    그때까지는 아래에 둔다 — 겹쳐 보이는 것보다는 길어지는 편이 낫다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.css = (base / 'static/css/label_preview.css').read_text(encoding='utf-8')

    def test_겹쳐_보이던_배치가_남아_있지_않다(self):
        self.assertNotIn('pv-nutrition-side', self.css)
        head = self.js.index('function placeNutritionBlock')
        self.assertIn("classList.remove('pv-nutrition-side')", self.js[head:head + 400])

    def test_켜고_끌_때마다_자리를_다시_정한다(self):
        """자리를 한 번만 정하면 항목을 지우거나 더한 뒤에 어긋난 채로 남는다."""
        self.assertGreaterEqual(self.js.count('placeNutritionBlock();'), 2)

class CategoryLabelsCoverTests(TestCase):
    """
    검증 결과에 영어 키가 그대로 찍히면 안 된다.

    화면은 카테고리 이름을 _CATEGORY_LABELS 에서 찾는데, 없으면 코드 이름을
    그대로 쓴다. 그래서 "content_weight_basis", "rawmtrl_bracket",
    "calorie_macros" 가 사용자에게 그대로 보였다. 검사가 늘 때마다 이름도
    함께 늘어야 한다 — 그것을 사람이 기억할 수는 없으니 시험이 본다.
    """

    def test_모든_검사에_한글_이름이_있다(self):
        from v1.label.services.ai_validation_service import _CATEGORY_LABELS
        from v1.label.services.validation_service import _LEGAL_BASIS

        missing = sorted(set(_LEGAL_BASIS) - set(_CATEGORY_LABELS))
        self.assertEqual(missing, [], f'한글 이름이 없는 검사: {missing}')

    def test_이름이_영어가_아니다(self):
        from v1.label.services.ai_validation_service import _CATEGORY_LABELS

        for code, name in _CATEGORY_LABELS.items():
            self.assertNotEqual(code, name, f'{code} 의 이름이 코드 그대로다')


class OneRootOneMessageTests(TestCase):
    """
    같은 원인에서 갈라져 나오는 지적은 한 번만 말한다.

    영양성분 탭의 값이 100 g 당이 아닌 다른 기준으로 들어가면 세 검사가 한꺼번에
    운다 — 병기 열량, 탄단지 계산, 총 내용량. 고칠 데는 하나인데 세 번 말하면
    무엇부터 볼지 흐려지고, 하나를 고쳤을 때 나머지가 함께 사라지는 것도
    설명이 안 된다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='root', password='x')

    def test_원인을_짚었으면_자식_지적은_접는다(self):
        from v1.label.services.validation_service import validate_label

        # 라벨에 인쇄된 값(총 내용량 65 g 당 309 kcal)을 그대로 넣은 상태
        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='브라우니',
            content_weight='65 g (309 kcal)',
            calories='309', carbohydrates='9', fats='4.5', proteins='1',
            serving_size='100', units_per_package='1')

        categories = [i['category'] for i in validate_label(label)['issues']]
        self.assertIn('calorie_consistency', categories)
        self.assertNotIn('calorie_macros', categories)
        self.assertNotIn('content_weight_basis', categories)

    def test_원인이_아닌_경우에는_그대로_말한다(self):
        """접는 것은 원인을 짚었을 때뿐이다. 아니면 각자 할 말을 해야 한다."""
        from v1.label.services.validation_service import check_calorie_matches_macros

        label = MyLabel.objects.create(
            user_id=self.user, my_label_name='다른 라벨',
            calories='309', carbohydrates='9', fats='4.5', proteins='1')
        self.assertTrue(check_calorie_matches_macros(label))


class SingleRecyclingMarkOwnerTests(TestCase):
    """
    분리배출마크 구현이 두 벌이라 마크가 두 개 그려졌다.

    하나는 인라인 스크립트가 만든 것(여러 개·드래그·삭제·목록), 다른 하나는
    label_preview.js 의 옛 구현(마크 하나, 드래그도 삭제도 없음)이다. 둘 다
    돌아서 화면에 둘이 뜨고, 그중 하나는 꿈쩍도 하지 않았다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')

    def test_주인이_정해져_있다(self):
        self.assertIn("window.__recyclingMarkOwner = 'inline'", self.html)

    def test_옛_구현은_비켜선다(self):
        for name in ('function setRecyclingMark', 'function renderRecyclingMarkUI',
                     'function removeRecyclingMarkUI'):
            head = self.js.index(name)
            self.assertIn("__recyclingMarkOwner === 'inline'", self.js[head:head + 500],
                          f'{name} 이 비켜서지 않는다')

    def test_없는_함수를_그냥_부르지_않는다(self):
        """
        인라인 스크립트에만 있는 함수를 여기서 부르면 ReferenceError 가 나고,
        그 순간 핸들러가 통째로 멈춘다 — 마크를 옮기지도 지우지도 못하게 된
        것이 이것 때문이었다.
        """
        head = self.js.index("const recommendedMark = (typeof recommendRecyclingMarkByMaterial")
        self.assertIn("=== 'function'", self.js[head:head + 200])


class NutritionBasisFieldTests(TestCase):
    """
    표의 기준은 basic_display_type 이다.

    미리보기는 nutrition_display_unit 을 읽고 있었는데 그것은 표의 **모양**
    (기본형/병행표시)이라, tabMap 에 없는 키가 되어 머리글이 "undefined" 로
    찍혔다.
    """

    def test_뷰가_기준_칸을_넘긴다(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='basis', password='x')
        label = MyLabel.objects.create(
            user_id=user, my_label_name='기준',
            basic_display_type='total', nutrition_display_unit='basic',
            calories='309')
        self.client.force_login(user)
        resp = self.client.get(reverse('label:preview_popup'),
                               {'label_id': label.my_label_id})
        self.assertIn('"display_unit": "total"', resp.context['nutrition_data'])

    def test_모르는_기준이면_총_내용량당으로_본다(self):
        from pathlib import Path
        from django.conf import settings as dj

        js = (Path(dj.BASE_DIR) / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.assertIn("if (!['total', 'unit', '100g'].includes(displayUnit)) displayUnit = 'total';", js)


class LabelColumnMeasureTests(TestCase):
    """
    항목명 칸의 글자 폭을 재는 방법.

    'auto' 로 풀고 재면 안 된다 — table-layout:fixed 에서 auto 는 남는 폭을
    열끼리 나눠 갖는 것이라, scrollWidth 가 글자 폭이 아니라 표의 절반을
    돌려준다. 그래서 항목명 칸이 통째로 넓어졌다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        self.html = (Path(dj.BASE_DIR) / 'templates/label/label_preview.html'
                     ).read_text(encoding='utf-8')

    def test_좁혀_두고_잰다(self):
        head = self.html.index('const minPx = colMm / 10 * CM_TO_PX;')
        block = self.html[head:head + 1400]
        self.assertIn("setProperty('--label-col-width', '1px')", block)
        self.assertNotIn("setProperty('--label-col-width', 'auto')", block)

    def test_표의_절반을_넘지_않는다(self):
        """항목명이 값보다 넓어지면 읽을 수가 없다 — 그때는 접히는 편이 낫다."""
        head = self.html.index('const minPx = colMm / 10 * CM_TO_PX;')
        block = self.html[head:head + 1400]
        self.assertIn('0.45', block)
        self.assertIn('Math.min(capPx', block)

class LabelTextExportTests(TestCase):
    """
    표시사항을 **붙여넣을 수 있는 글자**로 내준다.

    지금까지 산출물은 PDF 하나였는데, 그것은 화면을 이미지로 떠서 붙인 것이라
    글자를 선택할 수 없다. 받는 디자인 담당자는 원재료명 300자를 손으로 다시
    친다 — 검수에서 나온 "과당1"(원래는 "과당]")이 그 흔적이다. 붙여넣을 수
    있는 글자를 내주면 그 단계가 통째로 사라진다.
    """

    def setUp(self):
        from pathlib import Path
        from django.conf import settings as dj

        base = Path(dj.BASE_DIR)
        self.js = (base / 'static/js/label/label_preview.js').read_text(encoding='utf-8')
        self.html = (base / 'templates/label/label_preview.html').read_text(encoding='utf-8')

    def test_버튼이_있다(self):
        self.assertIn('id="copyTextBtn"', self.html)
        self.assertIn('id="downloadTextBtn"', self.html)
        self.assertIn("safeAddEventListener('copyTextBtn', 'click', copyLabelText)", self.js)
        self.assertIn("safeAddEventListener('downloadTextBtn', 'click', downloadLabelText)", self.js)

    def test_항목명과_값을_탭으로_가른다(self):
        """워드·엑셀에 붙여넣으면 그대로 표가 된다."""
        head = self.js.index('function labelTextLines')
        block = self.js[head:head + 2000]
        self.assertIn(r"\t", block)

    def test_화면_전용_표시는_빼고_복사한다(self):
        """미입력 안내와 지적 번호는 인쇄물의 글자가 아니다."""
        head = self.js.index('function cleanCellText')
        block = self.js[head:head + 700]
        self.assertIn('.pv-empty-hint', block)
        self.assertIn('.pv-issue-badge', block)

    def test_영양정보도_함께_나간다(self):
        head = self.js.index('function labelTextLines')
        block = self.js[head:head + 2000]
        self.assertIn('nutritionPreview', block)
        self.assertIn('[영양정보]', block)

    def test_2단_배치에서_같은_줄이_두_번_나오지_않는다(self):
        """한 <tr> 에 항목이 둘이면 칸이 이름을 갖는다. tr 까지 세면 겹친다."""
        head = self.js.index('function labelTextLines')
        block = self.js[head:head + 2000]
        self.assertIn("row.tagName === 'TR' && row.querySelector('[data-field-row]')", block)

    def test_한_줄만_복사할_수도_있다(self):
        self.assertIn('function copyOneRow', self.js)
        self.assertIn("data-act=\"copy\"", self.js)

    def test_클립보드가_막힌_환경에도_길이_있다(self):
        """비 HTTPS·구형 브라우저에서는 navigator.clipboard 가 없다."""
        head = self.js.index('async function copyLabelText')
        block = self.js[head:head + 1500]
        self.assertIn('execCommand', block)


class CalorieImpossibleValueTests(TestCase):
    """
    기준이 어긋난 것인가, 값 자체가 틀린 것인가.

    둘은 고칠 데가 다르다. 기준 문제면 영양성분 탭에서 환산하면 되고, 값
    문제면 표를 다시 계산해야 한다. 그런데 예전 문구는 늘 "기준을 확인하세요"
    라고만 해서, 기준을 맞춰도 경고가 안 사라지는 사용자가 어디를 봐야 할지
    몰랐다.

    가르는 법은 간단하다 — 탄단지가 전부 지방이라고 쳐도(g당 9 kcal) 낼 수
    없는 열량이면, 기준을 어떻게 맞춰도 그 값은 나오지 않는다. 환산은 열량과
    함량에 같은 배수를 곱하는 일이라 둘의 비율을 바꾸지 못하기 때문이다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='kcal', password='x')

    def _label(self, **kwargs):
        return MyLabel.objects.create(user_id=self.user, my_label_name='열량', **kwargs)

    def test_나올_수_없는_값이면_그렇게_말한다(self):
        """
        실제 도안: 탄 9 · 지 4.5 · 단 1 로는 최대 130 kcal 인데 475 가 적혀 있다.
        기준을 맞춰도 안 맞는다 — 표 자체가 틀린 것이다.
        """
        from v1.label.services.validation_service import check_calorie_matches_macros

        issues = check_calorie_matches_macros(self._label(
            calories='475', carbohydrates='9', fats='4.5', proteins='1'))
        self.assertEqual(len(issues), 1)
        self.assertIn('나올 수 없는 값', issues[0]['message'])
        self.assertIn('130 kcal 이 최대', issues[0]['message'])
        self.assertIn('해결되지 않습니다', issues[0]['suggestion'])

    def test_기준만_어긋난_경우는_환산을_안내한다(self):
        """탄 30 · 지 10 · 단 5 = 230 kcal. 300 은 나올 수 있는 범위다."""
        from v1.label.services.validation_service import check_calorie_matches_macros

        issues = check_calorie_matches_macros(self._label(
            calories='400', carbohydrates='30', fats='10', proteins='5'))
        self.assertEqual(len(issues), 1)
        self.assertNotIn('나올 수 없는 값', issues[0]['message'])
        self.assertIn('기준', issues[0]['suggestion'])

    def test_맞으면_조용하다(self):
        from v1.label.services.validation_service import check_calorie_matches_macros

        self.assertEqual(check_calorie_matches_macros(self._label(
            calories='230', carbohydrates='30', fats='10', proteins='5')), [])
