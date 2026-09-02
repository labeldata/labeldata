"""
정답지로 A/B 를 돌린다 — 옵션을 켠 것과 끈 것을 나란히 잰다.

    python manage.py ocr_ab --hybrid              # OCR 원문 주입 전후
    python manage.py ocr_ab --ground              # 판독값 대조 전후
    python manage.py ocr_ab --hybrid --runs 3     # 회차를 늘려 편차까지
    python manage.py ocr_ab --hybrid --yes        # 확인 없이 바로

화면(/label/ocr-lab/)에서 하던 일을 명령줄에서 한다. 화면은 웹 요청 시간
제한(PythonAnywhere 5분)에 걸려 한 번에 열두 번까지만 부를 수 있는데, 여기는
그 제한이 없다. 정답지가 늘수록 이쪽이 편하다.

**결과는 OcrBenchmarkRun 으로 남는다.** 화면에서 돌린 것과 같은 표에 쌓이므로
나중에 견줄 수 있다.

읽는 법 — 세 가지를 함께 본다. 평균만 보면 안 된다.

    1. 목적한 칸이 올랐는가        자유 문구 두 칸(주의사항·기타표시사항)
    2. 멀쩡하던 칸이 무너지지 않았는가   지금 100점·편차 0 인 짧은 칸들
    3. 편차가 커지지 않았는가      평균이 같아도 흔들리면 나빠진 것이다

2번이 조건이다. 목적한 칸이 올라도 다른 칸이 무너지면 채택하지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = '정답지로 옵션 켜기/끄기를 나란히 재고 항목별 차이를 낸다'

    def add_arguments(self, parser):
        parser.add_argument('--hybrid', action='store_true',
                            help='OCR 원문 주입(조각 이미지 제거) 전후를 잰다')
        parser.add_argument('--ground', action='store_true',
                            help='판독값 원문 대조 전후를 잰다')
        parser.add_argument('--drop-tiles', action='store_true',
                            help='--hybrid 와 함께: 조각 이미지까지 뺀다(토큰 절감). '
                                 '배치를 봐야 읽히는 칸이 무너질 수 있다')
        parser.add_argument('--runs', type=int, default=1,
                            help='정답지 한 장을 몇 번씩 읽을지 (기본 1)')
        parser.add_argument('--case', type=int, help='정답지 하나만')
        parser.add_argument('--model', help='모델 덮어쓰기')
        parser.add_argument('--freetext', action='store_true',
                            help='주의사항·기타표시사항도 읽는다')
        parser.add_argument('--yes', action='store_true',
                            help='호출 수 확인을 건너뛴다')

    def handle(self, *args, **options):
        from v1.common.models import OcrTruthCase

        if not (options['hybrid'] or options['ground']):
            raise CommandError('--hybrid 또는 --ground 중 하나는 주어야 한다. '
                               '무엇을 켜고 끌지 정해야 A/B 가 된다.')

        cases = OcrTruthCase.objects.filter(verified=True)
        if options['case']:
            cases = cases.filter(pk=options['case'])
        cases = list(cases.order_by('pk'))
        if not cases:
            raise CommandError('확인된 정답지가 없다. /label/ocr-lab/ 에서 '
                               '먼저 만들고 "정답 확인" 을 켜야 한다.')

        runs = max(1, options['runs'])
        calls = len(cases) * runs * 2
        option = 'hybrid' if options['hybrid'] else 'ground'

        self.stdout.write(
            f'정답지 {len(cases)}장 x {runs}회 x 2(켜고/끄고) = '
            f'**판독 {calls}번**. 옵션: {option}')
        self.stdout.write(self._eta(len(cases), runs, options))

        if not options['yes'] and not self._confirm():
            self.stdout.write('그만둔다.')
            return

        # 끈 쪽을 먼저 돈다. 켠 쪽이 먼저면, 앞 회차가 분당 토큰 한도를 다 쓴
        # 상태에서 뒤 회차가 429 로 죽어 "옵션을 껐더니 실패했다" 로 읽힌다.
        before = self._measure(cases, options, hybrid=False, ground=False)

        # **두 회차 사이에도 쉰다.** 이걸 빠뜨려서 --case 1 --runs 1 이 429 로
        # 죽었다 - 정답지가 하나면 회차 안에는 쉴 자리가 없어, 끈 쪽과 켠 쪽의
        # 두 호출이 그대로 붙어 나간다. 끈 쪽이 토큰을 많이 쓰므로 그 기준으로
        # 쉰다.
        self._rest()

        after = self._measure(cases, options,
                              hybrid=options['hybrid'], ground=options['ground'])

        self._report(before, after, option)

    # ── 실행 ──────────────────────────────────────────────────────────────

    def _rest(self):
        """끈 쪽과 켠 쪽 사이에 창이 열릴 때까지 쉰다."""
        import time

        from v1.label.services.ocr_lab import pace_seconds

        wait = pace_seconds(False)
        self.stdout.write(f'  분당 한도가 풀리도록 {wait:.0f}초 쉰다…')
        time.sleep(wait)

    def _eta(self, case_count, runs, options):
        """
        얼마나 걸리는지 미리 알린다.

        분당 토큰 한도 때문에 판독 사이를 쉬어야 하고, 그 대기가 판독 시간보다
        길다. 5장 3회면 끈 쪽만 5분이 넘는데, 모르고 시작하면 멈춘 줄 안다.
        """
        from django.conf import settings

        from v1.label.services.ocr_lab import pace_seconds

        each = case_count * runs
        call = 12.0     # 판독 한 번에 걸리는 시간 (실측 5~15초)
        off = each * (call + pace_seconds(False))
        on = each * (call + pace_seconds(
            True if options['hybrid'] else False))
        total = (off + on) / 60.0
        limit = getattr(settings, 'OCR_TPM_LIMIT', 200_000)
        return (f'분당 토큰 한도 {limit:,} 기준으로 판독 사이를 쉰다 — '
                f'대략 {total:.0f}분 걸린다.\n'
                f'(한도가 올랐으면 .env 의 OCR_TPM_LIMIT 을 고쳐야 빨라진다)')

    def _confirm(self):
        try:
            return (input('진행할까? [y/N] ') or '').strip().lower() in ('y', 'yes')
        except EOFError:
            # 파이프로 돌린 경우. 물어볼 수 없으면 하지 않는다 - 돈이 나가는
            # 일을 조용히 시작하면 안 된다.
            self.stdout.write(self.style.WARNING(
                '\n확인을 받을 수 없다. --yes 를 주고 다시 부르라.'))
            return False

    def _measure(self, cases, options, hybrid, ground):
        from v1.label.services.ocr_lab import run_benchmark

        label = '켜고' if (hybrid or ground) else '끄고'
        self.stdout.write(f'\n[{label}] 재는 중…')
        run = run_benchmark(
            cases,
            runs=max(1, options['runs']),
            model=options.get('model') or None,
            read_freetext=bool(options['freetext']),
            use_ground=ground,
            use_hybrid=hybrid,
            drop_tiles=bool(options['drop_tiles']) if hybrid else False,
        )
        self.stdout.write(f'  평균 {run.mean_score}  (기록 #{run.pk})')
        return run

    # ── 출력 ──────────────────────────────────────────────────────────────

    # 자유 문구 두 칸이 이 작업의 목적이다. 표에서 눈에 띄게 둔다.
    _TARGET = ('cautions', 'additional_info', 'rawmtrl_nm')

    def _report(self, before, after, option):
        rows = self._diff(before, after)

        self.stdout.write('')
        self.stdout.write('=' * 66)
        self.stdout.write(f'{"항목":<24}{"끄고":>8}{"켜고":>8}{"차이":>8}   편차')
        self.stdout.write('-' * 66)

        for row in rows:
            mark = '*' if row['field'] in self._TARGET else ' '
            line = (f'{mark} {row["field"]:<22}{row["before"]:>8.1f}'
                    f'{row["after"]:>8.1f}{row["gain"]:>+8.1f}'
                    f'   {row["spread_before"]:.0f} -> {row["spread_after"]:.0f}')
            if row['gain'] >= 3:
                self.stdout.write(self.style.SUCCESS(line))
            elif row['gain'] <= -3:
                self.stdout.write(self.style.ERROR(line))
            else:
                self.stdout.write(line)

        self.stdout.write('-' * 66)
        gain = round(after.mean_score - before.mean_score, 1)
        self.stdout.write(f'{"전체 평균":<24}{before.mean_score:>8.1f}'
                          f'{after.mean_score:>8.1f}{gain:>+8.1f}')
        self._verdict(rows, gain, option)

    def _diff(self, before, after):
        """항목별 전후. 한쪽에만 있는 항목도 빠뜨리지 않는다."""
        def by_field(run):
            return {r['field']: r for r in (run.detail or {}).get('fields', [])}

        b, a = by_field(before), by_field(after)
        rows = []
        for field in sorted(set(b) | set(a)):
            bb, aa = b.get(field, {}), a.get(field, {})
            rows.append({
                'field': field,
                'before': bb.get('mean', 0.0),
                'after': aa.get('mean', 0.0),
                'gain': round(aa.get('mean', 0.0) - bb.get('mean', 0.0), 1),
                'spread_before': bb.get('spread', 0.0),
                'spread_after': aa.get('spread', 0.0),
            })
        return sorted(rows, key=lambda r: r['gain'], reverse=True)

    def _verdict(self, rows, gain, option):
        """
        채택 여부를 말로 옮긴다. 숫자만 보면 사람마다 다르게 읽는다.

        **무너진 칸이 하나라도 있으면 채택하지 않는다.** 평균이 올라도
        그렇다 - 지금 100점인 칸이 깨지는 것은 사용자가 이미 믿고 쓰던 것을
        잃는 일이고, 평균 몇 점으로 바꿀 것이 아니다.
        """
        broken = [r for r in rows if r['gain'] <= -3]
        gained = [r for r in rows if r['gain'] >= 3]
        shaky = [r for r in rows
                 if r['spread_after'] - r['spread_before'] >= 10]

        self.stdout.write('')
        if broken:
            self.stdout.write(self.style.ERROR(
                f'무너진 칸 {len(broken)}개: '
                f'{", ".join(r["field"] for r in broken[:5])}\n'
                f'**채택하지 않는다.** 평균이 올랐더라도, 지금 잘 읽던 칸이 '
                f'깨지는 것은 사용자가 믿고 쓰던 것을 잃는 일이다.'))
            return
        if shaky:
            self.stdout.write(self.style.WARNING(
                f'편차가 커진 칸 {len(shaky)}개: '
                f'{", ".join(r["field"] for r in shaky[:5])}\n'
                f'평균이 같아도 흔들리면 나빠진 것이다. 회차를 늘려 다시 재라.'))
            return
        if gained:
            self.stdout.write(self.style.SUCCESS(
                f'오른 칸 {len(gained)}개, 무너진 칸 없음 (전체 {gain:+.1f}).\n'
                f'채택할 만하다 — .env 에 '
                f'{"OCR_HYBRID" if option == "hybrid" else "OCR_GROUND"}=True '
                f'를 넣고 웹앱을 Reload 하라.'))
            return
        self.stdout.write(
            f'뚜렷한 차이가 없다 (전체 {gain:+.1f}). 회차를 늘리거나 '
            f'정답지를 더 모아 다시 재라.')
