"""
정답을 적어 둔 사진으로 판독 정확도를 잰다.

화면에서 사람이 열 번 눌러 재는 것보다 빠르고, 무엇보다 같은 잣대로 잰다.
프롬프트를 고치거나 모델을 바꾼 뒤 **정말 나아졌는지** 숫자로 답한다.

준비:

    mkdir -p ~/ocr_bench
    # 사진을 넣고 (예: 샐러드.jpg)
    python manage.py ocr_benchmark --make-answer ~/ocr_bench/샐러드.jpg
    # 만들어진 샐러드.json 을 열어 틀린 값을 정답으로 고친다

측정:

    python manage.py ocr_benchmark --dir ~/ocr_bench                # 1회
    python manage.py ocr_benchmark --dir ~/ocr_bench --runs 5       # 5회 평균·편차
    python manage.py ocr_benchmark --dir ~/ocr_bench --model gpt-4o # 모델 비교
    python manage.py ocr_benchmark --dir ~/ocr_bench --compare-crop # 영역/전체 비교

**한 번 돌린 결과로 판단하지 마시오.** 같은 사진도 매번 다르게 읽힌다.
--runs 로 여러 번 돌려 평균과 편차를 함께 보아야 한다.
"""
import json
import statistics
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = '정답을 적어 둔 사진으로 판독 정확도를 잰다'

    def add_arguments(self, parser):
        parser.add_argument('--dir', help='사진과 정답 파일이 있는 폴더')
        parser.add_argument('--runs', type=int, default=1,
                            help='몇 번 돌릴지 (기본 1). 편차를 보려면 3 이상')
        parser.add_argument('--model', help='이번만 다른 모델로 (예: gpt-4o)')
        parser.add_argument('--compare-crop', action='store_true',
                            help='정답에 crop 이 있으면 영역/전체를 나눠 잰다')
        parser.add_argument('--make-answer', metavar='IMAGE',
                            help='사진을 읽어 정답 파일의 초안을 만든다')
        parser.add_argument('--details', action='store_true',
                            help='틀린 항목의 정답과 판독값을 함께 출력')
        parser.add_argument('--save', metavar='FILE',
                            help='결과를 JSON 으로 저장 (전후 비교용)')

    def handle(self, *args, **options):
        if options['make_answer']:
            self._make_answer(options['make_answer'], options.get('model'))
            return

        if not options['dir']:
            raise CommandError('--dir 로 폴더를 지정하거나 --make-answer 를 쓰시오.')

        from v1.label.services.ocr_benchmark import load_cases

        cases = load_cases(options['dir'])
        if not cases:
            raise CommandError(
                f'{options["dir"]} 에 (사진 + 같은 이름의 .json) 짝이 없다.\n'
                '먼저 --make-answer 로 정답 초안을 만드시오.')

        model = self._pick_model(options.get('model'))
        self.stdout.write(f'  모델 {model} · 사진 {len(cases)}장 · {options["runs"]}회')

        report = {'model': model, 'runs': options['runs'], 'cases': {}}
        for case in cases:
            self.stdout.write('')
            self.stdout.write(f'  [{case["name"]}]')
            variants = [('whole', None)]
            if options['compare_crop'] and case['crop']:
                variants.append(('crop', case['crop']))

            report['cases'][case['name']] = {}
            for variant, box in variants:
                result = self._measure(case, box, options['runs'], model)
                report['cases'][case['name']][variant] = result
                self._print(variant, result, options['details'])

        if options['save']:
            Path(options['save']).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write('')
            self.stdout.write(f'  결과를 저장했다: {options["save"]}')

    # ── 측정 ────────────────────────────────────────────────────────────────
    def _measure(self, case, box, runs, model):
        from v1.label.services.ocr_benchmark import compare, crop_image, summarize
        from v1.label.services.ocr_service import extract_label_from_image

        results = []
        for i in range(runs):
            if box:
                source = crop_image(case['image'], box)
            else:
                source = open(case['image'], 'rb')
            try:
                out = extract_label_from_image(source)
            finally:
                if hasattr(source, 'close'):
                    source.close()

            if not out.get('success'):
                self.stdout.write(self.style.ERROR(
                    f'    {i + 1}회 실패: {out.get("error")}'))
                continue
            results.append(compare(case['expected'], out.get('data')))

        if not results:
            return {'mean': 0.0, 'fields': [], 'runs': 0}
        return {
            'mean': round(statistics.mean(r['mean'] for r in results), 1),
            'runs': len(results),
            'fields': summarize(results),
            'last': results[-1]['fields'],
        }

    def _print(self, variant, result, details):
        label = '영역 선택' if variant == 'crop' else '사진 전체'
        if not result['runs']:
            self.stdout.write(self.style.ERROR(f'    {label}: 측정 실패'))
            return

        style = self.style.SUCCESS if result['mean'] >= 85 else (
            self.style.WARNING if result['mean'] >= 60 else self.style.ERROR)
        self.stdout.write(style(
            f'    {label}  평균 {result["mean"]}점 ({result["runs"]}회)'))

        self.stdout.write('      %-20s %6s %6s %6s %6s' %
                          ('항목', '평균', '최저', '최고', '편차'))
        for row in result['fields']:
            line = '      %-20s %6.1f %6.1f %6.1f %6.1f' % (
                row['field'], row['mean'], row['worst'], row['best'], row['spread'])
            if row['mean'] < 60:
                self.stdout.write(self.style.ERROR(line))
            elif row['spread'] >= 30:
                # 매번 다르게 읽는 항목. 평균만 보면 안 보인다.
                self.stdout.write(self.style.WARNING(line + '  <- 들쭉날쭉'))
            else:
                self.stdout.write(line)

        if details:
            self.stdout.write('')
            for field, row in (result.get('last') or {}).items():
                if row['grade'] in ('exact',):
                    continue
                self.stdout.write(f'      · {field} ({row["score"]}점)')
                self.stdout.write(f'          정답: {self._trim(row["expected"])}')
                self.stdout.write(f'          판독: {self._trim(row["actual"])}')

    # ── 정답 초안 만들기 ────────────────────────────────────────────────────
    def _make_answer(self, image_path, model_override):
        from v1.label.services.ocr_benchmark import flatten
        from v1.label.services.ocr_service import extract_label_from_image

        path = Path(image_path)
        if not path.is_file():
            raise CommandError(f'사진이 없다: {path}')

        model = self._pick_model(model_override)
        self.stdout.write(f'  모델 {model} 로 읽는 중...')
        with open(path, 'rb') as fh:
            out = extract_label_from_image(fh)
        if not out.get('success'):
            raise CommandError(f'읽지 못했다: {out.get("error")}')

        data = flatten(out.get('data'))
        # 못 읽은 항목도 키는 남긴다 - 정답이 있는데 못 읽은 것을 0점으로
        # 세려면 정답 파일에 그 항목이 있어야 한다.
        answer = {k: v for k, v in data.items()}
        answer['crop'] = [0, 0, 0, 0]

        target = path.with_suffix('.json')
        target.write_text(json.dumps(answer, ensure_ascii=False, indent=2),
                          encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'  초안을 만들었다: {target}'))
        self.stdout.write('')
        self.stdout.write('  이제 이 파일을 열어')
        self.stdout.write('    1) 틀린 값을 실제 라벨의 값으로 고치고')
        self.stdout.write('    2) 라벨에 없는 항목은 지우거나 빈 값으로 두고')
        self.stdout.write('    3) crop 에 [x, y, 너비, 높이] 를 적으면 '
                          '영역 판독도 함께 잽니다 (안 쓰면 지우세요)')
        self.stdout.write('')
        self.stdout.write('  **초안은 판독 결과다. 그대로 두면 자기 답을 '
                          '자기가 채점하는 꼴이 된다.**')

    @staticmethod
    def _pick_model(override):
        from django.conf import settings

        if override:
            # 이번 실행에만 적용한다. .env 를 고치지 않고 비교할 수 있다.
            settings.OCR_MODEL = override
            return override
        return getattr(settings, 'OCR_MODEL', 'gpt-4o-mini')

    @staticmethod
    def _trim(text, width=100):
        one = ' '.join((text or '').split())
        return one if len(one) <= width else one[:width] + '...'
