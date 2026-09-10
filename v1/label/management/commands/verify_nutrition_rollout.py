"""
배합 영양성분 기능이 **이 서버의 실제 데이터에서 쓸 만한가**를 잰다.

    python manage.py verify_nutrition_rollout
    python manage.py verify_nutrition_rollout --user 12     # 한 계정만
    python manage.py verify_nutrition_rollout --samples 20  # 표본을 더 본다

아무것도 고치지 않는다. 읽기만 한다.

왜 서버에서 다시 재야 하는가
────────────────────────────
개발 장비에서 잰 숫자는 **한 계정의 원료 172 개**였다. 그 숫자로 "도달률
10.5 %" 같은 판단을 내렸는데, 계정마다 원료의 성격이 다르다 — 향료를 많이
쓰는 곳과 농산물을 많이 쓰는 곳은 결과가 전혀 다를 것이다. 배합비를 실제로
채워 쓰는지도 이 서버에서만 알 수 있다.

무엇을 재는가
─────────────
  ① 적재     식약처 자료가 제대로 들어왔는가 (기준량·검산·크기)
  ② 도달     우리 원료가 그 자료에 닿는가 (보고번호 · 이름 후보)
  ③ 배합     배합비가 실제로 채워져 있는가, 기여도 엔진이 얼마나 줄여 주는가
  ④ 산출     지금 당장 계산되는 제품이 몇 개인가  ← 이게 이 기능의 성적표다

④가 0 이면 앞의 셋이 아무리 좋아도 아무도 쓰지 못한다.
"""
from collections import Counter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count, Q

from v1.bom.models import ProductBOM
from v1.label.models import (MyIngredient, MyIngredientNutrition, MyLabel,
                             PublicFoodNutrition)
from v1.label.services import nutrition_candidates as ncd
from v1.label.services import nutrition_recipe as nr


class Command(BaseCommand):
    help = '배합 영양성분 기능이 이 서버의 실제 데이터에서 쓸 만한지 잰다 (읽기만)'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, default=0, help='이 계정만 본다')
        parser.add_argument('--samples', type=int, default=8, help='표본 출력 수')
        parser.add_argument('--skip-candidates', action='store_true',
                            help='이름 후보 찾기를 건너뛴다 (원료가 아주 많을 때)')

    # ── 도구 ────────────────────────────────────────────────────────────

    def head(self, text):
        self.stdout.write('')
        self.stdout.write('─' * 72)
        self.stdout.write(text)
        self.stdout.write('')

    def line(self, label, value, note=''):
        self.stdout.write('   %-30s %12s  %s' % (label, value, note))

    def pct(self, n, total):
        return '%.1f%%' % (n / total * 100) if total else '-'

    # ── 본체 ────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        self.samples = opts['samples']
        self.only_user = opts['user']

        self.stdout.write('배합 영양성분 — 실데이터 점검 (읽기 전용)')
        loaded = self.check_load()
        if not loaded:
            return
        self.check_reach(skip_candidates=opts['skip_candidates'])
        self.check_recipes()
        self.check_products()

    # ── ① 적재 ──────────────────────────────────────────────────────────

    def check_load(self):
        self.head('① 적재 — 식약처 자료가 제대로 들어왔는가')

        total = PublicFoodNutrition.objects.count()
        if not total:
            self.stdout.write(self.style.ERROR(
                '   적재된 행이 없다. load_food_nutrition 을 먼저 돌려라.'))
            return False

        self.line('전체 행', f'{total:,}')

        g = PublicFoodNutrition.objects.filter(basis_unit='g').count()
        ml = PublicFoodNutrition.objects.filter(basis_unit='mL').count()
        self.line('100g 기준', f'{g:,}', self.pct(g, total) + '  ← 배합에 쓸 수 있는 것')
        self.line('100mL 기준', f'{ml:,}', self.pct(ml, total) + '  비중을 몰라 못 쓴다')

        fail = PublicFoodNutrition.objects.filter(verify_status='fail').count()
        ok = PublicFoodNutrition.objects.filter(verify_status='pass').count()
        self.line('검산 통과', f'{ok:,}')
        self.line('검산 어긋남', f'{fail:,}',
                  self.pct(fail, ok + fail) + ' (잰 것 기준)'
                  + ('  ← 높으면 AMT_NUM 매핑을 의심하라' if ok and fail > ok * 0.3 else ''))

        with connection.cursor() as c:
            c.execute("""SELECT ROUND((data_length+index_length)/1024/1024, 1)
                         FROM information_schema.tables
                         WHERE table_schema=DATABASE()
                           AND table_name='public_food_nutrition'""")
            row = c.fetchone()
        if row and row[0]:
            self.line('표 크기', '%s MB' % row[0],
                      '(통계가 낡았으면 ANALYZE TABLE 후 다시 본다)')
        return True

    # ── ② 도달 ──────────────────────────────────────────────────────────

    def check_reach(self, skip_candidates=False):
        self.head('② 도달 — 우리 원료가 그 자료에 닿는가')

        qs = MyIngredient.objects.exclude(user_id__isnull=True)
        if self.only_user:
            qs = qs.filter(user_id=self.only_user)
        total = qs.count()
        if not total:
            self.stdout.write('   원료가 없다.')
            return

        self.line('원료 전체', f'{total:,}')

        with_no = qs.exclude(prdlst_report_no__isnull=True).exclude(prdlst_report_no='')
        nums = {n.strip() for n in with_no.values_list('prdlst_report_no', flat=True)
                if n and n.strip().isdigit()}
        self.line('품목보고번호 있음(숫자)', f'{len(nums):,}', self.pct(len(nums), total))

        hit = set(PublicFoodNutrition.objects
                  .filter(item_report_no__in=nums)
                  .values_list('item_report_no', flat=True))
        self.line('보고번호로 찾음', f'{len(hit):,}',
                  self.pct(len(hit), total) + ' (전체 원료 기준)')

        # 이미 정해 둔 것
        decided = MyIngredientNutrition.objects.filter(ingredient__in=qs)
        by_kind = Counter(decided.values_list('source_kind', flat=True))
        self.line('이미 정해 둔 원료', f'{decided.count():,}', self.pct(decided.count(), total))
        for kind, n in by_kind.most_common():
            self.stdout.write('       %-16s %s' % (kind, n))

        if skip_candidates:
            return

        # 이름으로 후보가 나오는가 — 표본으로만 본다(원료 하나에 0.3 초쯤 든다)
        undecided = qs.exclude(
            my_ingredient_id__in=decided.values_list('ingredient_id', flat=True))
        sample = list(undecided.order_by('?')[:min(self.samples * 3, 40)])
        if not sample:
            return

        found = 0
        shown = 0
        self.stdout.write('')
        self.stdout.write('   [정하지 않은 원료 표본] 이름으로 후보가 나오는가')
        for ing in sample:
            cands = ncd.candidates(ing.prdlst_nm or '', limit=1)
            if cands:
                found += 1
            if shown < self.samples:
                shown += 1
                top = cands[0]['row'].food_nm_kr if cands else '— 없음'
                self.stdout.write('     %-28s → %s' % ((ing.prdlst_nm or '')[:28], top[:30]))
        self.line('후보가 나온 비율', '%d/%d' % (found, len(sample)),
                  self.pct(found, len(sample)) + ' (표본)')

    # ── ③ 배합 ──────────────────────────────────────────────────────────

    def check_recipes(self):
        self.head('③ 배합 — 배합비가 실제로 채워져 있는가')

        boms = ProductBOM.objects.filter(active_yn=True)
        if self.only_user:
            boms = boms.filter(parent_label__user_id=self.only_user)
        total = boms.count()
        if not total:
            self.stdout.write('   활성 BOM 줄이 없다.')
            return

        with_ratio = boms.exclude(usage_ratio__isnull=True).count()
        self.line('활성 BOM 줄', f'{total:,}')
        self.line('배합비 있음', f'{with_ratio:,}', self.pct(with_ratio, total)
                  + ('  ← 배합비가 없으면 계산도 판정도 못 한다'
                     if with_ratio < total * 0.5 else ''))

        # 작은 배합비가 실제로 얼마나 되는가 — 기여도 엔진의 효과 범위다
        ratios = [float(r) for r in boms.exclude(usage_ratio__isnull=True)
                  .values_list('usage_ratio', flat=True)]
        if ratios:
            small = sum(1 for r in ratios if r <= 0.5)
            tiny = sum(1 for r in ratios if r <= 0.05)
            self.line('배합비 0.5% 이하', f'{small:,}', self.pct(small, len(ratios)))
            self.line('배합비 0.05% 이하', f'{tiny:,}', self.pct(tiny, len(ratios))
                      + '  ← 대개 아무것도 안 물어도 된다')

    # ── ④ 산출 ──────────────────────────────────────────────────────────

    def check_products(self):
        self.head('④ 산출 — 지금 당장 계산되는 제품이 몇 개인가  (성적표)')

        labels = (MyLabel.objects
                  .filter(delete_YN='N')
                  .annotate(n=Count('bom_items', filter=Q(bom_items__active_yn=True)))
                  .filter(n__gt=0))
        if self.only_user:
            labels = labels.filter(user_id=self.only_user)

        total = labels.count()
        if not total:
            self.stdout.write('   배합이 있는 제품이 없다.')
            return

        ok = 0
        no_ratio = 0
        blocked = Counter()
        examples = []

        for label in labels.iterator(chunk_size=50):
            rows = list(ProductBOM.objects
                        .filter(parent_label=label, active_yn=True)
                        .select_related('child_label', 'source_ingredient__nutrition'))
            result = nr.calculate(nr.collect_items(rows))
            blocking = result['contribution']['blocking']

            if not result['ratio_total']:
                no_ratio += 1
                continue
            if not blocking:
                ok += 1
                if len(examples) < self.samples:
                    examples.append((label.my_label_name, result['values'].get('calories')))
                continue
            for f in blocking:
                blocked[f] += 1

        self.line('배합이 있는 제품', f'{total:,}')
        self.line('지금 계산되는 제품', f'{ok:,}', self.pct(ok, total)
                  + ('  ← 이 값이 이 기능의 성적표다' if ok else '  ← 아직 아무도 못 쓴다'))
        self.line('배합비가 비어 못 잼', f'{no_ratio:,}', self.pct(no_ratio, total))

        if blocked:
            self.stdout.write('')
            self.stdout.write('   [무엇이 가장 많이 막는가]')
            for field, n in blocked.most_common(5):
                self.stdout.write('     %-16s %5d 개 제품' % (field, n))

        if examples:
            self.stdout.write('')
            self.stdout.write('   [계산되는 제품 표본]')
            for name, kcal in examples:
                self.stdout.write('     %-34s %s kcal'
                                  % ((name or '')[:34],
                                     round(kcal, 1) if kcal else '-'))

        self.stdout.write('')
        self.stdout.write('─' * 72)
