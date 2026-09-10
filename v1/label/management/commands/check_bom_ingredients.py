"""
배합에 실제로 쓰이는 원료 중 **무엇을 채워야 계산이 되는가**.

    python manage.py check_bom_ingredients
    python manage.py check_bom_ingredients --user 12
    python manage.py check_bom_ingredients --show 40

아무것도 고치지 않는다. 읽기만 한다.

왜 따로 재는가
──────────────
서버에서 원료 72 개를 자동으로 붙였는데 계산되는 제품은 0 그대로였다.
파 보니 이랬다.

    배합비 있는 줄 107 · 원료 보관함 연결 96 · **원료에 영양성분 있음 3**

배합 줄은 원료와 잘 이어져 있었다. 다만 **자동으로 붙은 72 개가 정작 배합에
쓰이는 원료가 아니었다.** 보고번호가 있고 식약처 DB 에도 있는 원료를 골라
붙였는데, 배합에 들어가는 것은 다른 원료들이었던 것이다.

그래서 모수를 '내 원료 전부' 가 아니라 **'배합에 실제로 쓰이는 원료'** 로
좁혀 다시 센다. 그리고 **제품을 많이 막는 것부터** 보여 준다 — 적은 손으로
계산되는 제품을 늘리려면 그 순서로 채워야 한다.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from v1.bom.models import ProductBOM
from v1.label.models import (MyIngredient, MyIngredientNutrition,
                             PublicFoodNutrition)
from v1.label.services import nutrition_candidates as ncd


class Command(BaseCommand):
    help = '배합에 쓰이는 원료 중 무엇을 채워야 계산이 되는지 잰다 (읽기 전용)'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, default=0, help='이 계정만')
        parser.add_argument('--show', type=int, default=25, help='보여 줄 원료 수')
        parser.add_argument('--skip-candidates', action='store_true',
                            help='이름 후보 찾기를 건너뛴다 (빠르게 보고 싶을 때)')

    def handle(self, *args, **opts):
        w = self.stdout.write

        rows = (ProductBOM.objects
                .filter(active_yn=True)
                .exclude(usage_ratio__isnull=True)
                .select_related('source_ingredient'))
        if opts['user']:
            rows = rows.filter(parent_label__user_id=opts['user'])

        # 원료마다 몇 개 제품을 막고 있는가
        products = defaultdict(set)
        no_link = 0
        for r in rows:
            if r.source_ingredient_id:
                products[r.source_ingredient_id].add(r.parent_label_id)
            else:
                no_link += 1

        ids = set(products)
        w('─' * 70)
        w('배합에 쓰이는 원료 — 배합비가 있는 줄만 센다')
        w('')
        w('   배합 줄            %6d' % rows.count())
        w('   원료와 이어진 줄    %6d' % (rows.count() - no_link))
        w('   원료로 안 이어진 줄 %6d  %s' % (
            no_link, '← 글자로만 친 줄. 원료 보관함에서 골라야 이어진다' if no_link else ''))
        w('   고유 원료          %6d' % len(ids))

        if not ids:
            return

        ings = {i.my_ingredient_id: i
                for i in MyIngredient.objects.filter(my_ingredient_id__in=ids)}
        done = set(MyIngredientNutrition.objects
                   .filter(ingredient_id__in=ids)
                   .values_list('ingredient_id', flat=True))

        with_no = {k: i for k, i in ings.items()
                   if (i.prdlst_report_no or '').strip().isdigit()}
        nums = {(i.prdlst_report_no or '').strip() for i in with_no.values()}
        in_mfds = set(PublicFoodNutrition.objects
                      .filter(item_report_no__in=nums)
                      .values_list('item_report_no', flat=True))

        w('')
        w('   품목보고번호 있음   %6d  (%.0f%%)' % (
            len(with_no), len(with_no) / len(ids) * 100))
        w('   그중 식약처DB 에 있음 %4d' % len(in_mfds))
        w('   영양성분 정해짐     %6d  (%.0f%%)  ← 이게 100%% 여야 계산된다'
          % (len(done), len(done) / len(ids) * 100))

        todo = [k for k in ids if k not in done]
        if not todo:
            w('')
            w('   전부 채워져 있다.')
            return

        # 제품을 많이 막는 것부터
        todo.sort(key=lambda k: -len(products[k]))

        w('')
        w('─' * 70)
        w('무엇부터 채우면 되는가 — 막고 있는 제품이 많은 순')
        w('')
        w('   %-32s %4s %-10s %s' % ('원료', '제품', '보고번호', '식약처 자료'))
        w('   ' + '-' * 64)

        can_pick = 0
        for key in todo[:opts['show']]:
            ing = ings.get(key)
            if ing is None:
                continue
            no = (ing.prdlst_report_no or '').strip()

            if no.isdigit() and no in in_mfds:
                hint = '보고번호로 바로 붙는다'
                can_pick += 1
            elif opts['skip_candidates']:
                hint = '-'
            else:
                cands = ncd.candidates(ing.prdlst_nm or '', limit=1)
                if cands:
                    hint = '후보 있음 → %s' % (cands[0]['row'].food_nm_kr or '')[:22]
                    can_pick += 1
                else:
                    hint = '없음 — 성적서가 필요하다'

            w('   %-32s %4d %-10s %s'
              % ((ing.prdlst_nm or '')[:32], len(products[key]),
                 (no or '없음')[:10], hint))

        if len(todo) > opts['show']:
            w('   … 그 밖에 %d 개' % (len(todo) - opts['show']))

        w('')
        if not opts['skip_candidates']:
            w('   위 %d 개 중 %d 개는 지금 화면에서 고를 수 있다.'
              % (min(len(todo), opts['show']), can_pick))
        w('   원료 상세 → 영양성분에서 고르거나, 이름으로 직접 찾으면 된다.')
        w('─' * 70)
