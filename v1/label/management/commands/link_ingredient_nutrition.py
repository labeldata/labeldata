"""
품목제조보고번호가 딱 맞는 원료에 영양성분을 **자동으로 붙인다.**

    python manage.py link_ingredient_nutrition --dry-run    # 세기만
    python manage.py link_ingredient_nutrition              # 실제로 붙인다
    python manage.py link_ingredient_nutrition --user 12    # 한 계정만

왜 필요한가
───────────
같은 품목보고번호는 법적으로 같은 품목이다. 사람이 고를 것이 없으므로 묻지
않고 붙인다.

운영 실측 (2026-09-12)
──────────────────────
    원료 보관함            885
      영양성분 보유          75 (8.5%)   report_no 72 · picked 2 · negligible 1
    품목보고번호 있음        332 (37.5%)
      숫자가 아닌 번호         2
      식약처 DB 에 행 있음     81   100g 72 · 100mL 9(부피라 제외)
      DB 에 없음            259
    번호 자체가 없음        553 (62.5%)

**번호로 갈 수 있는 길은 이미 바닥까지 갔다.** 72 건은 전부 붙어 있고 밀린
것이 없다. 남은 91.8 % 는 번호가 없거나 식약처 DB 에 없어서 **이름으로만**
닿는다 — 특히 원재료성 식품(밀가루·설탕·소금)은 적재본에서 보고번호 보유율이
**0 %** 라 구조적으로 번호로는 영영 못 붙는다.

그러니 이 명령이 하는 일은 이제 "밀린 것을 따라잡는 것" 이 아니라 **새로
들어온 원료를 훑는 그물**이다. 저장하는 순간에도 붙지만(signals.py) 묶음
등록(bulk_create)은 post_save 를 부르지 않으므로 그쪽이 여기로 걸린다.

이 문서의 앞선 판에는 "이미 정해 둔 원료 0 개" 라고 적혀 있었다. 개발 DB 를
재고 실서버라고 적은 것이었고, 그 숫자가 계획 문서까지 옮겨 다녔다.
**운영 숫자는 운영에서 잰 출력만 적는다.**

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

            # 붙이는 일은 services 가 한다. 원료를 저장하는 순간에도 같은
            # 함수를 부르므로, 두 벌로 두면 어느 날 한쪽만 고쳐진다.
            ncd.link_by_report_no(ing, force=opts['force'])

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
