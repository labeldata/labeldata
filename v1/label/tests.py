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
    """

    def setUp(self):
        self.user = User.objects.create_user(username='kcal', password='x')

    def _messages(self, **kwargs):
        from v1.label.services.validation_service import check_required_fields
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
                                       chckd_weight_calorie='Y', content_weight='250 g')
        issues = check_required_fields(label)
        self.assertIn('weight_calorie', issues[0]['fields'])
        self.assertIn('kcal', issues[0]['suggestion'])

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


class DataHealthCommandTests(TestCase):
    """
    운영 점검 커맨드(check_data_health).

    "눈으로 봐야 한다"고 미뤄 둔 것들이 실은 데이터만 읽으면 답이 나온다.
    아무것도 고치지 않는지, 판정이 맞는지를 고정한다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='health', password='x')

    def _run(self, **opts):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('check_data_health', stdout=out, **opts)
        return out.getvalue()

    def test_아무것도_바꾸지_않는다(self):
        from v1.label.models import MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='라벨')
        ing = MyIngredient.objects.create(user_id=self.user, prdlst_nm='설탕', delete_YN='N')
        before = (label.update_datetime, ing.update_datetime, MyLabel.objects.count())

        self._run()

        label.refresh_from_db(); ing.refresh_from_db()
        self.assertEqual((label.update_datetime, ing.update_datetime, MyLabel.objects.count()),
                         before)

    def test_배합비가_역순인_라벨을_찾는다(self):
        from v1.label.models import LabelIngredientRelation, MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='역순 라벨')
        for seq, (name, ratio) in enumerate([('설탕', 10), ('밀가루', 30)], start=1):
            ing = MyIngredient.objects.create(user_id=self.user, prdlst_nm=name, delete_YN='N')
            LabelIngredientRelation.objects.create(
                label=label, ingredient=ing, relation_sequence=seq, ingredient_ratio=ratio)

        out = self._run(only='order')
        self.assertIn('내림차순이 아닌', out)
        self.assertIn('역순 라벨', out)

    def test_배합비가_내림차순이면_통과라고_말한다(self):
        from v1.label.models import LabelIngredientRelation, MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='정순 라벨')
        for seq, (name, ratio) in enumerate([('밀가루', 30), ('설탕', 10)], start=1):
            ing = MyIngredient.objects.create(user_id=self.user, prdlst_nm=name, delete_YN='N')
            LabelIngredientRelation.objects.create(
                label=label, ingredient=ing, relation_sequence=seq, ingredient_ratio=ratio)

        self.assertIn('입력 순서는 전부 내림차순', self._run(only='order'))

    def test_배합비를_모르는_행끼리는_따지지_않는다(self):
        """
        「식품등의 표시기준」은 함량이 많은 순서로 적으라고 하지만, 함량을 모르는
        원료끼리의 순서는 판단할 근거가 없다.
        """
        from v1.label.models import LabelIngredientRelation, MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='배합비 없음')
        for seq, name in enumerate(['설탕', '밀가루'], start=1):
            ing = MyIngredient.objects.create(user_id=self.user, prdlst_nm=name, delete_YN='N')
            LabelIngredientRelation.objects.create(
                label=label, ingredient=ing, relation_sequence=seq, ingredient_ratio=None)

        self.assertIn('따질 수 없습니다', self._run(only='order'))

    def test_같은_키로_겹치는_원료를_센다(self):
        from v1.label.models import MyIngredient

        for _ in range(3):
            MyIngredient.objects.create(
                user_id=self.user, prdlst_nm='설탕', prdlst_report_no='123',
                prdlst_dcnm='당류', delete_YN='N')
        MyIngredient.objects.create(user_id=self.user, prdlst_nm='소금', delete_YN='N')

        out = self._run(only='duplicate')
        self.assertIn('그룹 1개', out)
        self.assertIn('여분 2건', out)     # 3개 중 2개가 여분

    def test_매칭이_없으면_없다고_말한다(self):
        """0건과 "지워졌다" 는 다르다. 단정하지 않는다."""
        self.assertIn('매칭 이력이 없습니다', self._run(only='inspection'))

    def test_판정_알림_건수를_따로_보여준다(self):
        """
        판정결과 변동(부적합)은 소급 매칭이 다시 만들어 주지 않는다.
        지워졌으면 영구 소실이라 이 숫자만 따로 볼 수 있어야 한다.
        """
        inspection = InspectionResult.objects.create(prdlst_report_no='123')
        InspectionMatch.objects.create(
            inspection=inspection, user=self.user,
            alert_phase=InspectionMatch.PHASE_JUDGMENT,
            match_reason=InspectionMatch.REASON_LABEL)
        InspectionMatch.objects.create(
            inspection=inspection, user=self.user,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            match_reason=InspectionMatch.REASON_LABEL)

        out = self._run(only='inspection')
        self.assertIn('전체 2건', out)
        self.assertIn('판정결과 변동(다시 안 만들어짐): 1건', out)
        self.assertIn('수거 감지(다시 만들어짐)     : 1건', out)

    def test_모르는_사용자는_그렇게_말한다(self):
        out = self._run(user='없는사람@example.com')
        self.assertIn('찾을 수 없습니다', out)


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


class PrintedOrderCheckTests(TestCase):
    """
    인쇄되는 문구의 순서 점검.

    입력 순서는 표시 문구를 만드는 쪽이 정렬하므로 문제가 아니다. 정작 규정을
    어길 수 있는 건 손으로 고친 최종 문구다 — 그건 아무도 다시 정렬해 주지 않는다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='printed', password='x')

    def _label(self, text, pairs):
        from v1.label.models import LabelIngredientRelation, MyIngredient

        label = MyLabel.objects.create(user_id=self.user, my_label_name='문구',
                                       rawmtrl_nm_display=text)
        for seq, (name, ratio) in enumerate(pairs, start=1):
            ing = MyIngredient.objects.create(
                user_id=self.user, prdlst_nm=name, delete_YN='N')
            LabelIngredientRelation.objects.create(
                label=label, ingredient=ing, relation_sequence=seq,
                ingredient_ratio=ratio)
        return label

    def _run(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('check_data_health', only='order', stdout=out)
        return out.getvalue()

    def test_문구가_역순이면_인쇄물_문제로_잡는다(self):
        """입력 순서와 달리 이건 실제로 규정 위반이다."""
        self._label('설탕, 밀가루', [('밀가루', 30), ('설탕', 10)])
        out = self._run()
        self.assertIn('규정에 어긋나는 라벨 1건', out)
        self.assertIn('"설탕"(10)가 "밀가루"(30)보다 앞', out)

    def test_문구가_내림차순이면_통과라고_말한다(self):
        self._label('밀가루, 설탕', [('밀가루', 30), ('설탕', 10)])
        self.assertIn('인쇄되는 문구는 전부 배합비 내림차순', self._run())

    def test_입력_순서가_뒤집혀도_문구가_맞으면_넘어간다(self):
        """생성기가 정렬해 주므로 입력 순서는 인쇄물과 무관하다."""
        self._label('밀가루, 설탕', [('설탕', 10), ('밀가루', 30)])
        out = self._run()
        self.assertIn('입력 순서가 내림차순이 아닌 라벨 1건', out)
        self.assertIn('인쇄되는 문구는 전부 배합비 내림차순', out)

    def test_문구에서_이름을_못_찾으면_위반이라고_하지_않는다(self):
        """표시명이 원료명과 다르게 적혀 있으면 못 찾는다. 모르는 것과 위반은 다르다."""
        self._label('밀 가공품, 정제당', [('밀가루', 30), ('설탕', 10)])
        out = self._run()
        self.assertNotIn('규정에 어긋나는', out)
        self.assertIn('건너뛴', out)


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


class DuplicateSplitTests(TestCase):
    """
    합쳐도 되는 그룹과 사람이 봐야 하는 그룹을 가른다.

    같은 "피자치즈" 라도 알레르기·표시명이 다르게 채워져 있으면 하나로 합칠 때
    정보가 사라진다.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='split', password='x')

    def _make(self, name, **fields):
        from v1.label.models import MyIngredient
        return MyIngredient.objects.create(
            user_id=self.user, prdlst_nm=name, prdlst_report_no='', prdlst_dcnm='',
            delete_YN='N', **fields)

    def _run(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('check_data_health', only='duplicate', stdout=out)
        return out.getvalue()

    def test_내용이_같으면_안전하다고_말한다(self):
        self._make('피자치즈', allergens='우유')
        self._make('피자치즈', allergens='우유')
        out = self._run()
        self.assertIn('합쳐도 안전한 그룹  : 1개', out)
        self.assertIn('사람이 봐야 하는 그룹: 0개', out)

    def test_내용이_다르면_무엇이_다른지_알려준다(self):
        self._make('피자치즈', allergens='우유')
        self._make('피자치즈', allergens='')
        out = self._run()
        self.assertIn('합쳐도 안전한 그룹  : 0개', out)
        self.assertIn('사람이 봐야 하는 그룹: 1개', out)
        self.assertIn('allergens', out)

    def test_자동_병합은_하지_않는다고_밝힌다(self):
        from v1.label.models import MyIngredient

        self._make('피자치즈')
        self._make('피자치즈')
        out = self._run()
        self.assertIn('자동 병합은 하지 않는다', out)
        self.assertEqual(MyIngredient.objects.filter(prdlst_nm='피자치즈').count(), 2)


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
