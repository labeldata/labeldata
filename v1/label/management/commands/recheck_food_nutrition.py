# -*- coding: utf-8 -*-
"""
적재해 둔 행의 **검산 결과만 다시 낸다.** API 를 다시 부르지 않는다.

    python manage.py recheck_food_nutrition --dry-run   # 몇 건이 바뀌는지만
    python manage.py recheck_food_nutrition             # 고쳐 넣는다

왜 필요한가
──────────
`verify_status` 는 적재할 때 한 번 계산해 **저장해 둔 값**이다. 그래서
`mfds_nutrition.verify_row` 의 잣대를 고치면 그 순간부터 표의 값은 **낡은
판정**이 된다 — 그런데 화면도 보고도 그 사실을 말해 주지 않는다. 34 만 건을
다시 받아야만 갱신되는 줄 알기 쉽고, 실제로 그렇게 오해했다.

다시 받을 필요가 없다. 검산이 쓰는 값(수분·단백질·지방·회분·탄수화물·열량)은
**이미 컬럼에 다 들어 있다.** 같은 함수에 같은 값을 넣어 다시 재면 된다.
API 호출 639 회와 30 분이 아니라, 표 한 번 훑는 일이다.

이 명령이 있어야 하는 진짜 이유는 따로 있다. 잣대를 고칠 때마다 '다시 재는
길' 이 없으면 **고치기를 망설이게 된다.** 그러면 잣대가 굳는다.
"""
from django.core.management.base import BaseCommand

from v1.label.models import PublicFoodNutrition
from v1.label.services import mfds_nutrition as mfds

CHUNK = 2000

# verify_row 가 보는 값들. 컬럼 이름이 곧 우리 성분 이름이라 그대로 쓴다.
_FIELDS = ('moisture', 'proteins', 'fats', 'ash', 'carbohydrates',
           'calories', 'dietary_fiber', 'sugar_alcohols')


class Command(BaseCommand):
    help = '적재본의 검산 결과를 다시 낸다 (API 를 부르지 않는다)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='바뀌는 건수만 세고 저장하지 않는다')
        parser.add_argument('--sample', type=int, default=0,
                            help='바뀐 것 몇 건을 눈으로 보여 줄지')

    def handle(self, *args, **opts):
        dry, w = opts['dry_run'], self.stdout.write
        moved, samples = {}, []
        changed, seen = [], 0

        qs = PublicFoodNutrition.objects.all().order_by('id')
        w('행 %s 개를 다시 잰다' % f'{qs.count():,}')

        for row in qs.iterator(chunk_size=CHUNK):
            seen += 1
            values = {f: getattr(row, f) for f in _FIELDS}
            ok, note = mfds.verify_row(values, row.basis_amount, row.basis_unit)
            status = (PublicFoodNutrition.VERIFY_PASS if ok is True
                      else PublicFoodNutrition.VERIFY_FAIL if ok is False
                      else PublicFoodNutrition.VERIFY_SKIP)
            note = (note or '')[:200]
            if status == row.verify_status and note == (row.verify_note or ''):
                continue

            key = '%s -> %s' % (row.verify_status, status)
            moved[key] = moved.get(key, 0) + 1
            if opts['sample'] and len(samples) < opts['sample']:
                samples.append('%s | %s | %s' % (key, row.food_nm_kr or '', note))

            row.verify_status, row.verify_note = status, note
            changed.append(row)

            if not dry and len(changed) >= CHUNK:
                self._flush(changed)
                changed = []

        if not dry and changed:
            self._flush(changed)

        total = sum(moved.values())
        for key in sorted(moved, key=lambda k: -moved[k]):
            w('  %-16s %s' % (key, f'{moved[key]:,}'))
        for line in samples:
            w('      · %s' % line)
        w(self.style.SUCCESS('%s / %s 건의 판정이 바뀐다' % (f'{total:,}', f'{seen:,}')))
        if dry:
            w('세기만 했습니다. 고쳐 넣으려면 --dry-run 을 빼세요.')

    @staticmethod
    def _flush(rows):
        PublicFoodNutrition.objects.bulk_update(
            rows, ['verify_status', 'verify_note'], batch_size=1000)
