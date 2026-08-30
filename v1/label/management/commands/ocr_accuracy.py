"""
사진 판독의 정확도를 항목별로 본다.

프롬프트를 고치거나 모델을 바꿨을 때 **정말 나아졌는지** 재는 자다. 이게 없으면
"이번엔 잘 읽네" 같은 인상으로만 판단하게 된다.

정확도는 "사용자가 고치지 않고 그대로 쓴 비율" 이다. 확인 창에서 체크한 항목만
센다 - 체크를 끈 항목은 사용자가 판단을 안 한 것이다.

    python manage.py ocr_accuracy               # 전체
    python manage.py ocr_accuracy --days 7      # 최근 7일 (변경 전후 비교)
    python manage.py ocr_accuracy --hints       # 프롬프트에 붙는 힌트 확인
    python manage.py ocr_accuracy --samples pog_daycnt   # 그 항목이 어떻게 틀렸나
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '사진 판독 정확도를 항목별로 보여준다'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None,
                            help='최근 N일만 (변경 전후를 나눠 보려면)')
        parser.add_argument('--hints', action='store_true',
                            help='프롬프트에 실제로 붙는 힌트를 출력')
        parser.add_argument('--samples', metavar='FIELD',
                            help='그 항목이 어떻게 틀렸는지 실제 사례')
        parser.add_argument('--limit', type=int, default=15,
                            help='사례 개수 (기본 15)')

    def handle(self, *args, **options):
        from v1.label.services.ocr_learning import accuracy_stats, hints_text

        if options['hints']:
            text = hints_text(use_cache=False)
            if not text.strip():
                self.stdout.write('  아직 프롬프트에 붙일 힌트가 없다.')
                self.stdout.write('  같은 실수가 2번 이상 반복돼야 힌트가 된다 - '
                                  '한 번뿐인 교정은 그 라벨 사정일 수 있다.')
            else:
                self.stdout.write(text)
            return

        if options['samples']:
            self._samples(options['samples'], options['limit'], options['days'])
            return

        stats = accuracy_stats(days=options['days'])
        if not stats:
            self.stdout.write('  아직 쌓인 판독 이력이 없다.')
            self.stdout.write('  제품 기본 정보 탭에서 사진을 불러오고 '
                              '"선택 항목 채우기" 를 누르면 쌓이기 시작한다.')
            return

        scope = f'최근 {options["days"]}일' if options['days'] else '전체'
        total = sum(s['total'] for s in stats)
        wrong = sum(s['corrected'] for s in stats)
        overall = (total - wrong) / total * 100 if total else 0

        self.stdout.write(f'  {scope} 판독 {total}건 중 {wrong}건을 사용자가 고쳤다')
        self.stdout.write(self.style.SUCCESS(f'  전체 정답률 {overall:.1f}%'))
        self.stdout.write('')
        self.stdout.write('  항목별 (정답률 낮은 순)')
        self.stdout.write('  %-22s %6s %6s %8s' % ('항목', '판독', '고침', '정답률'))
        for row in stats:
            line = '  %-22s %6d %6d %7.1f%%' % (
                row['field'], row['total'], row['corrected'], row['rate'])
            if row['total'] >= 3 and row['rate'] < 60:
                self.stdout.write(self.style.WARNING(line))
            else:
                self.stdout.write(line)

        self.stdout.write('')
        self.stdout.write('  어떻게 틀렸는지: --samples <항목>')

    def _samples(self, field, limit, days):
        from datetime import timedelta

        from django.utils import timezone
        from v1.common.models import OcrCorrection

        qs = OcrCorrection.objects.filter(field=field, corrected=True)
        if days:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

        rows = list(qs.order_by('-created_at')[:limit])
        if not rows:
            self.stdout.write(f'  {field} 에 고쳐진 이력이 없다.')
            return

        self.stdout.write(f'  {field} — 최근 {len(rows)}건')
        for row in rows:
            self.stdout.write('')
            self.stdout.write(f'    판독: {self._trim(row.ocr_value)}')
            self.stdout.write(f'    실제: {self._trim(row.final_value)}')

    @staticmethod
    def _trim(text, width=110):
        one = ' '.join((text or '').split())
        return one if len(one) <= width else one[:width] + '...'
