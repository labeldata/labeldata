"""
적재한 식약처 영양성분DB 가 **우리 원료에 실제로 닿는가**를 잰다.

    python manage.py check_food_nutrition

0 단계의 가부는 "적재가 됐다" 가 아니다. 319,060 건을 넣어도 우리 원료
보관함에 안 붙으면 배합 계산은 한 걸음도 못 간다. 그래서 재는 것은 셋이다.

  ① 적재 품질     기준량·검산·그룹 분포
  ② 조인 도달률   MyIngredient 의 품목보고번호가 얼마나 맞아떨어지는가
  ③ 표시 성분 충족률  붙은 행이 표시에 필요한 성분을 실제로 들고 있는가

②가 낮으면 이름 매칭(2단계)의 비중이 커지고, ③이 낮으면 붙어도 쓸 수 없다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from v1.label.models import MyIngredient, PublicFoodNutrition

# 영양성분표에 반드시 적어야 하는 아홉 — 이게 비면 붙어도 표를 못 만든다
REQUIRED = ('calories', 'carbohydrates', 'sugars', 'proteins', 'fats',
            'saturated_fats', 'trans_fats', 'cholesterols', 'natriums')


class Command(BaseCommand):
    help = '적재한 식약처 영양성분DB 의 품질과 우리 원료 매칭률을 잰다'

    def handle(self, *args, **opts):
        w = self.stdout.write
        total = PublicFoodNutrition.objects.count()
        if not total:
            w(self.style.ERROR('적재된 행이 없다. load_food_nutrition 을 먼저 돌려라.'))
            return

        w('─' * 66)
        w('① 적재 품질 — 총 %s 건' % f'{total:,}')
        w('')
        for label, qs in (
            ('100g 기준', PublicFoodNutrition.objects.filter(basis_unit='g')),
            ('100mL 기준', PublicFoodNutrition.objects.filter(basis_unit='mL')),
            ('기준량 못 읽음', PublicFoodNutrition.objects.filter(
                Q(basis_unit='') | Q(basis_unit__isnull=True))),
        ):
            n = qs.count()
            w('   %-14s %8s (%5.1f%%)' % (label, f'{n:,}', n / total * 100))

        w('')
        for label, status in (('검산 통과', 'pass'), ('검산 어긋남', 'fail'), ('못 잼', 'skip')):
            n = PublicFoodNutrition.objects.filter(verify_status=status).count()
            w('   %-14s %8s (%5.1f%%)' % (label, f'{n:,}', n / total * 100))

        fails = PublicFoodNutrition.objects.filter(verify_status='fail')[:5]
        for row in fails:
            w('      · %s — %s' % (row.food_nm_kr, row.verify_note))

        w('')
        w('   [DB그룹]')
        grp = (PublicFoodNutrition.objects.values('db_grp_nm')
               .annotate(n=Count('*'),
                         with_no=Count('pk', filter=~Q(item_report_no='') & Q(item_report_no__isnull=False)))
               .order_by('-n'))
        for g in grp:
            w('   %-12s %8s건  보고번호 %8s (%5.1f%%)'
              % (g['db_grp_nm'] or '(없음)', f"{g['n']:,}", f"{g['with_no']:,}",
                 g['with_no'] / max(g['n'], 1) * 100))

        # ② 조인 도달률 ────────────────────────────────────────────────
        w('')
        w('─' * 66)
        w('② 우리 원료와의 매칭 — 품목제조보고번호 정확 일치')
        w('')

        mine = (MyIngredient.objects
                .exclude(prdlst_report_no__isnull=True)
                .exclude(prdlst_report_no=''))
        mine_total = MyIngredient.objects.count()
        mine_with_no = mine.count()

        if not mine_total:
            w(self.style.WARNING('   원료 보관함이 비어 있어 잴 수 없다.'))
            return

        w('   원료 보관함 전체        %8s' % f'{mine_total:,}')
        w('   품목보고번호 있음        %8s (%5.1f%%)'
          % (f'{mine_with_no:,}', mine_with_no / mine_total * 100))

        numbers = set(
            n.strip() for n in mine.values_list('prdlst_report_no', flat=True) if n and n.strip()
        )
        matched = set(
            PublicFoodNutrition.objects
            .filter(item_report_no__in=numbers)
            .values_list('item_report_no', flat=True)
        )
        w('   식약처DB 에서 찾음       %8s (%5.1f%% / 번호 있는 것 기준)'
          % (f'{len(matched):,}', len(matched) / max(len(numbers), 1) * 100))
        w('   전체 원료 기준 도달률    %8.1f%%' % (len(matched) / mine_total * 100))

        # ③ 표시 성분 충족률 ───────────────────────────────────────────
        w('')
        w('─' * 66)
        w('③ 붙은 행이 표시 성분을 들고 있는가 (아홉 항목)')
        w('')

        hit = PublicFoodNutrition.objects.filter(item_report_no__in=matched)
        n_hit = hit.count()
        if not n_hit:
            w('   붙은 행이 없어 잴 수 없다.')
        else:
            for field in REQUIRED:
                n = hit.exclude(**{'%s__isnull' % field: True}).count()
                flag = '' if n / n_hit >= 0.95 else '   ← 낮다'
                w('   %-16s %8s (%5.1f%%)%s'
                  % (field, f'{n:,}', n / n_hit * 100, flag))

            full = hit
            for field in REQUIRED:
                full = full.exclude(**{'%s__isnull' % field: True})
            n_full = full.count()
            w('')
            w('   아홉 항목 모두 있음      %8s (%5.1f%%)'
              % (f'{n_full:,}', n_full / n_hit * 100))
            w('   (이 값이 곧 "붙으면 바로 표를 만들 수 있는 비율" 이다)')

        w('─' * 66)
