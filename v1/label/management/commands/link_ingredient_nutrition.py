"""
품목제조보고번호가 딱 맞는 원료에 영양성분을 **자동으로 붙인다.**

    python manage.py link_ingredient_nutrition --dry-run    # 세기만
    python manage.py link_ingredient_nutrition              # 실제로 붙인다
    python manage.py link_ingredient_nutrition --user 12    # 한 계정만

왜 필요한가
───────────
실서버에서 재 보니 이랬다.

    원료 884 개 · 보고번호로 찾을 수 있는 것 65 개 · **이미 정해 둔 원료 0 개**
    배합이 있는 제품 20 개 · **지금 계산되는 제품 0 개**

65 개는 사람이 고를 것이 없다 — 같은 번호는 같은 품목이다. 그런데도 지금은
원료 상세를 하나씩 열어 눌러야 저장된다. **고를 것이 없는데 손을 기다리는**
구조라, 아무도 안 누르면 기능이 통째로 잠들어 있다.

사람이 정한 값은 건드리지 않는다
────────────────────────────────
이미 MyIngredientNutrition 이 있는 원료는 지나간다. 성적서를 넣었거나 후보를
고른 것을 자동 판단으로 덮으면, 사람이 한 일이 조용히 사라진다.
다시 붙이려면 --force 를 준다.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from v1.label.models import MyIngredient, MyIngredientNutrition
from v1.label.services import nutrition_candidates as ncd

# 성분 칸 목록은 모델에서 가져온다. 예전에는 views 에서 가져왔는데, 상수 하나
# 때문에 웹 뷰 모듈이 통째로 딸려 와 ratelimit·openai 까지 불러왔다.
NUTRITION_INPUT_FIELDS = MyIngredientNutrition.VALUE_FIELDS


class Command(BaseCommand):
    help = '품목보고번호가 맞는 원료에 식약처 영양성분을 자동으로 붙인다'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='저장하지 않고 몇 개가 붙는지만 센다')
        parser.add_argument('--user', type=int, default=0, help='이 계정만')
        parser.add_argument('--force', action='store_true',
                            help='이미 정해 둔 원료도 덮어쓴다 (사람이 한 일을 지운다)')
        parser.add_argument('--show', type=int, default=10, help='보여 줄 표본 수')

    def handle(self, *args, **opts):
        w = self.stdout.write
        dry = opts['dry_run']

        qs = (MyIngredient.objects
              .exclude(user_id__isnull=True)
              .exclude(prdlst_report_no__isnull=True)
              .exclude(prdlst_report_no=''))
        if opts['user']:
            qs = qs.filter(user_id=opts['user'])

        if not opts['force']:
            already = MyIngredientNutrition.objects.values_list('ingredient_id', flat=True)
            qs = qs.exclude(my_ingredient_id__in=already)

        total = qs.count()
        w('보고번호가 있고 아직 정하지 않은 원료: %s' % f'{total:,}')
        if not total:
            return

        linked = 0
        skipped_volume = 0
        not_found = 0
        samples = []

        for ing in qs.iterator(chunk_size=200):
            row = ncd.auto_link(ing)
            if row is None:
                not_found += 1
                continue
            # auto_link 가 이미 100 g 기준만 돌려주지만, 조건이 바뀌어도
            # 부피 기준이 새어 들어오지 않게 여기서 한 번 더 막는다.
            if row.basis_unit != row.BASIS_G:
                skipped_volume += 1
                continue

            linked += 1
            if len(samples) < opts['show']:
                samples.append((ing.prdlst_nm, row.food_nm_kr, row.calories))

            if dry:
                continue

            fields = {f: getattr(row, f, None) for f in NUTRITION_INPUT_FIELDS}
            fields.update({
                'source_kind': MyIngredientNutrition.SOURCE_REPORT_NO,
                'public_row': row,
                'picked_by': None,          # 사람이 고른 것이 아니다
                'picked_at': timezone.now(),
                'source_note': '품목보고번호 자동 연결',
            })
            with transaction.atomic():
                MyIngredientNutrition.objects.update_or_create(
                    ingredient=ing, defaults=fields)

        w('')
        w('  붙음            %s%s' % (f'{linked:,}', '  (--dry-run: 저장하지 않았다)' if dry else ''))
        w('  식약처에 없음    %s' % f'{not_found:,}')
        if skipped_volume:
            w('  부피 기준이라 건너뜀 %s' % f'{skipped_volume:,}')

        if samples:
            w('')
            w('  [붙은 것 표본]')
            for mine, theirs, kcal in samples:
                w('    %-28s → %-28s %s kcal'
                  % ((mine or '')[:28], (theirs or '')[:28], kcal))

        if not dry and linked:
            w('')
            w('  이어서 확인: python manage.py verify_nutrition_rollout')
