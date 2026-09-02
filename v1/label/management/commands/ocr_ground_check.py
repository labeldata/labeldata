"""
OCR 원문이 우리 라벨을 읽는가 — 가부를 숫자로 가른다.

    python manage.py ocr_ground_check              # 확인된 정답지 전부
    python manage.py ocr_ground_check --case 3     # 한 장만
    python manage.py ocr_ground_check --refresh    # 저장된 원문을 버리고 다시
    python manage.py ocr_ground_check --text       # 원문도 함께 출력

**이게 1단계다.** OCR 이 우리 라벨(6pt 원형 스티커, 곡면 용기, 작업지시서에
얹힌 도안)을 못 읽으면 그 다음 단계가 전부 무의미하고, 읽으면 지금까지 못 풀던
문제 대부분이 한 번에 풀린다. 그래서 아무것도 만들기 전에 이것부터 잰다.

사람이 원문을 눈으로 보고 "읽을 만하네" 하고 판단하면 안 된다. 그건 이
프로젝트가 정답지를 만들면서까지 피해 온 "사람마다 다른 잣대" 다. 정답지가
이미 있으니 그것을 자로 쓴다.

문턱 (OCR_UPGRADE_PLAN.md §13)

    long_recall >= 0.9   2~5단계 전부 진행
    0.6 ~ 0.9            검증자로만 쓴다 (원문 주입은 안 함)
    <  0.6               접는다

**정답지가 두세 장이면 가부는 가려도 성공 판정은 못 한다.** 사진 몇 장에
맞춰진 결론을 "좋아졌다" 고 읽게 된다. 그래서 마지막에 장수를 함께 알린다.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'OCR 원문이 정답지의 값을 얼마나 담고 있는지 잰다 (1단계 가부 판단)'

    def add_arguments(self, parser):
        parser.add_argument('--case', type=int, help='정답지 하나만')
        parser.add_argument('--refresh', action='store_true',
                            help='저장된 원문을 버리고 다시 읽는다')
        parser.add_argument('--text', action='store_true', help='원문도 출력')
        parser.add_argument('--all', action='store_true',
                            help='확인 안 된 정답지까지 포함')

    def handle(self, *args, **options):
        from v1.common.models import OcrTruthCase
        from v1.label.services.ocr_text import LONG_FIELDS, measure_case, verdict

        self._print_auth()

        cases = OcrTruthCase.objects.all()
        if options['case']:
            cases = cases.filter(pk=options['case'])
        elif not options['all']:
            # 확인 전 초안을 자로 쓰면 자기 답을 자기가 채점하는 꼴이 된다.
            cases = cases.filter(verified=True)
        cases = list(cases.order_by('pk'))

        if not cases:
            self.stdout.write(self.style.WARNING(
                '잴 정답지가 없다. /label/ocr-lab/ 에서 먼저 만들어야 한다 '
                '(--all 을 주면 확인 안 된 것도 포함).'))
            return

        long_values, failed = [], []
        for case in cases:
            result = measure_case(case, refresh=options['refresh'])
            self._print_case(result, show_text=options['text'])
            if not result['measured']:
                failed.append(case)
            elif result['long_recall'] is not None:
                long_values.append(result['long_recall'])

        # **원문을 한 장도 못 받았으면 판정을 내지 않는다.** 호출이 실패한 것과
        # OCR 이 못 읽은 것은 전혀 다른데, 예전에는 둘 다 0.000 으로 뭉개서
        # "접는다" 를 찍었다. 결제 설정 하나 때문에 프로젝트를 접을 뻔했다.
        if failed and not long_values:
            self._print_blocked(failed)
            return

        self._print_verdict(cases, long_values, verdict, LONG_FIELDS)
        if failed:
            self.stdout.write(self.style.WARNING(
                f'\n다만 {len(failed)}장은 원문을 받지 못해 이 평균에서 빠졌다. '
                '그만큼 판정의 근거가 얇다.'))

    # ── 출력 ──────────────────────────────────────────────────────────────

    def _print_auth(self):
        """
        어떤 인증으로 부르는지 먼저 알린다.

        원문이 비어서 돌아왔을 때 "설정이 없는 건지, 있는데 거절당한 건지" 를
        가리는 데 몇 분씩 쓰게 된다. 부르기 전에 말해 주면 그 시간이 없어진다.
        """
        from django.conf import settings

        if getattr(settings, 'GOOGLE_VISION_API_KEY', ''):
            self.stdout.write('인증: API 키 (GOOGLE_VISION_API_KEY)')
        elif getattr(settings, 'GOOGLE_VISION_SERVICE_ACCOUNT_JSON', ''):
            self.stdout.write('인증: 서비스 계정 (GOOGLE_VISION_SERVICE_ACCOUNT_JSON)')
        elif getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', ''):
            self.stdout.write('인증: 서비스 계정 (FCM_SERVICE_ACCOUNT_JSON 을 빌려 씀)')
        else:
            self.stdout.write(self.style.ERROR(
                '인증 설정이 없다. .env 에 GOOGLE_VISION_API_KEY 또는\n'
                'GOOGLE_VISION_SERVICE_ACCOUNT_JSON 을 넣어야 원문을 못 받는다.'))

    def _print_case(self, result, show_text=False):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'#{result["case_id"]} {result["name"]}  (원문 {result["chars"]:,}자)'))

        if not result['measured']:
            self.stdout.write(self.style.ERROR(
                '  원문을 받지 못했다. **이것은 "OCR 이 못 읽었다" 가 아니다** — '
                '아직 아무것도 재지 못한 것이다.\n'
                '  이유는 로그(django_errors.log)의 [OCR 원문] 줄에 그대로 있다.'))
            return

        self.stdout.write(f'  {"항목":<22}{"글자수":>7}{"점수":>8}   ')
        for row in result['rows']:
            mark = '○' if row['found'] else '×'
            name = ('* ' if row['long'] else '  ') + row['field']
            line = f'  {name:<22}{row["length"]:>7}{row["score"]:>8.1f}  {mark}'
            style = self.style.SUCCESS if row['found'] else self.style.WARNING
            self.stdout.write(style(line))

        recall = result['recall']
        long_recall = result['long_recall']
        self.stdout.write(
            f'  전체 회수율 {recall if recall is not None else "-"} '
            f'({result["found"]}/{result["fields"]}), '
            f'긴 칸 {long_recall if long_recall is not None else "-"} '
            f'({result["long_fields"]}개)')

        if show_text:
            self.stdout.write('  ── 원문 ──')
            for line in (result.get('text') or '').splitlines()[:60]:
                self.stdout.write(f'  | {line}')

    def _print_blocked(self, failed):
        """
        한 장도 못 받았다. **판정을 내지 않는다.**

        여기서 0.000 과 "접는다" 를 찍으면 안 된다. 재지 못한 것을 못 읽은
        것으로 읽게 되고, 설정 문제로 방향 전체가 접힌다. 실제로 그럴 뻔했다.
        """
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.ERROR(
            f'{len(failed)}장 모두 원문을 받지 못해 **판정을 내지 않는다.**'))
        self.stdout.write(
            '\n호출이 실패한 것이지 OCR 이 못 읽은 것이 아니다. 자주 걸리는 것:\n'
            '\n'
            '  403 billing to be enabled   그 프로젝트에 결제 계정이 없다.\n'
            '                              Vision 은 무료 사용량(월 1,000건)을 쓰더라도\n'
            '                              결제 계정 연결이 필요하다.\n'
            '  403 SERVICE_DISABLED        Cloud Vision API 를 아직 켜지 않았다.\n'
            '  403 PERMISSION_DENIED       서비스 계정에 권한이 없다. API 키를 쓰면\n'
            '                              이 문제가 없다.\n'
            '  400 API key not valid       키가 잘려 들어갔거나 제한에 걸렸다.\n'
            '\n'
            '어느 것인지는 로그(django_errors.log)의 [OCR 원문] 줄에 그대로 적혀 있다.')

    def _print_verdict(self, cases, long_values, verdict, long_fields):
        self.stdout.write('')
        self.stdout.write('=' * 60)

        if not long_values:
            self.stdout.write(self.style.WARNING(
                f'긴 칸({", ".join(long_fields)})이 정답지에 하나도 없어 판단할 수 없다.\n'
                '가부는 이 칸들로 가른다 — 짧은 칸은 판독이 이미 100점이라 '
                '원문이 도울 여지가 없다.'))
            return

        mean = sum(long_values) / len(long_values)
        self.stdout.write(f'긴 칸 회수율 평균  {mean:.3f}  (정답지 {len(long_values)}장)')
        message = verdict(mean)
        style = (self.style.SUCCESS if mean >= 0.9
                 else self.style.WARNING if mean >= 0.6 else self.style.ERROR)
        self.stdout.write(style(f'판정: {message}'))

        if len(cases) < 5:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'다만 정답지가 {len(cases)}장뿐이다. 가부는 이걸로 가려도 '
                '**성공 판정은 못 한다** — 사진 몇 장에 맞춰진 결과를 "좋아졌다"\n'
                '고 읽게 된다. 다음 단계에 들어가기 전에 5장 이상으로 늘려야 한다.\n'
                '/label/ocr-lab/ 의 "검증된 표시사항에서" 로 만드는 것이 가장 빠르다.'))
