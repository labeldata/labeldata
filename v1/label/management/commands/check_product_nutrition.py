"""
제품 조회의 제품에 식약처 영양성분이 **얼마나 닿는가**를 잰다.

    python manage.py check_product_nutrition
    python manage.py check_product_nutrition --sample 50000   # 표본만 (운영에서 빠르게)

`check_food_nutrition` 은 **내 원료**를 놓고 같은 것을 잰다. 이 명령은 반대
방향이다 — 제품 조회(FoodItem)에 있는 제품 중 몇 %에 값이 붙느냐.

왜 재고 시작하는가
──────────────────
IMPROVEMENT_PLAN 7-0 에 전례가 있다. **개발 DB 를 재고 실서버라고 적었고**,
그 숫자가 문서로 옮겨져 결론까지 바꿨다. 화면에 뱃지를 달기 전에, 그 뱃지가
대부분 '—' 로 뜰지 아닐지를 먼저 알아야 한다. 빈 열은 "이 기능은 안 된다" 로
읽힌다.

세는 것
───────
  ① 도달률     보고번호로 영양성분 행이 찾아지는 FoodItem 비율
  ② 중복도     한 번호에 행이 여럿인 비율 (고르는 규칙이 필요한가)
  ③ 충족률     붙은 행이 표시 필수 아홉을 실제로 들고 있는가
  ④ 쓸 수 있나 기준 단위(g·mL) 와 검산 결과 분포
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from v1.label.models import FoodItem, PublicFoodNutrition
from v1.label.services import product_nutrition

# 영양성분표에 반드시 적어야 하는 아홉. check_food_nutrition 과 같은 목록이다.
REQUIRED = ('calories', 'carbohydrates', 'sugars', 'proteins', 'fats',
            'saturated_fats', 'trans_fats', 'cholesterols', 'natriums')


class Command(BaseCommand):
    help = '제품 조회(FoodItem)에 식약처 영양성분이 얼마나 닿는지 잰다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample', type=int, default=0,
            help='FoodItem 을 이만큼만 본다 (0 이면 전부). 운영은 183만 행이라 오래 걸린다')

    def handle(self, *args, **opts):
        w = self.stdout.write

        total_nutrition = PublicFoodNutrition.objects.count()
        if not total_nutrition:
            w(self.style.ERROR(
                '적재된 영양성분 행이 없다. load_food_nutrition 을 먼저 돌려라.'))
            return

        w('─' * 66)
        w('① 적재본 쪽 — 총 %s 건' % f'{total_nutrition:,}')

        # source_db 로 거르면 0 건이 나온다. 적재기(load_food_nutrition)가 이 칸을
        # 채우지 않고, 모델 주석이 "비어 있으면 식약처 적재본" 이라고 정해 두었다.
        mfds = PublicFoodNutrition.objects.filter(source_db__isnull=True).count()
        rda = PublicFoodNutrition.objects.filter(source_db='rda').count()
        w('   식약처 %s · 농진청 %s' % (f'{mfds:,}', f'{rda:,}'))

        usable = product_nutrition.matching_report_nos().count()
        distinct = (product_nutrition.matching_report_nos()
                    .values('item_report_no').distinct().count())
        w('   보고번호가 있고 쓸 수 있는 행 %s (고유 번호 %s)'
          % (f'{usable:,}', f'{distinct:,}'))

        w('')
        w('② 제품 조회 쪽 — 도달률')

        qs = FoodItem.objects.only('prdlst_report_no')
        limit = opts['sample']
        if limit:
            qs = qs.order_by('-prms_dt')[:limit]
            w('   표본 %s 건 (허가일자 최근순)' % f'{limit:,}')

        report_nos = list(qs.values_list('prdlst_report_no', flat=True))
        seen = len(report_nos)
        if not seen:
            w(self.style.WARNING('   FoodItem 이 비어 있다.'))
            return

        # 번호 자체가 조인 키로 쓸 수 없는 것부터 가른다 — 도달률이 낮을 때
        # "DB 에 없다" 인지 "번호가 이상하다" 인지 갈라 봐야 다음 수가 정해진다.
        joinable = [no for no in report_nos if product_nutrition.normalize(no)]
        w('   FoodItem %s 건 · 조인 가능한 번호 %s (%.1f%%)'
          % (f'{seen:,}', f'{len(joinable):,}', len(joinable) / seen * 100))

        found = self._lookup_in_chunks(joinable)
        hit = len(found)
        w(self.style.SUCCESS(
            '   → 영양성분이 붙는 제품 %s 건 (전체의 %.1f%% · 조인 가능분의 %.1f%%)'
            % (f'{hit:,}', hit / seen * 100,
               hit / len(joinable) * 100 if joinable else 0)))

        if not hit:
            w(self.style.WARNING(
                '   붙는 것이 없다. 뱃지와 조건 검색이 늘 빈 결과를 낸다 — '
                '적재본의 item_report_no 가 실제로 채워져 있는지 먼저 보라.'))
            return

        w('')
        w('③ 한 번호에 행이 여럿인가')
        dup = (PublicFoodNutrition.objects
               .exclude(item_report_no='')
               .exclude(item_report_no__isnull=True)
               .values('item_report_no')
               .annotate(n=Count('pk'))
               .filter(n__gt=1)
               .count())
        w('   행이 둘 이상인 번호 %s 개' % f'{dup:,}')
        w('   (고르는 규칙 — 분석 > 산출 > 수집, 그다음 최근 조사: '
          'product_nutrition._sort_key)')

        w('')
        w('④ 붙은 행이 표시에 쓸 만한가')
        rows = list(found.values())
        for label, unit in (('100g 기준', PublicFoodNutrition.BASIS_G),
                            ('100mL 기준', PublicFoodNutrition.BASIS_ML)):
            n = sum(1 for r in rows if r.basis_unit == unit)
            w('   %-12s %6s (%5.1f%%)' % (label, f'{n:,}', n / len(rows) * 100))

        full = sum(1 for r in rows
                   if all(getattr(r, f, None) is not None for f in REQUIRED))
        w('   표시 필수 아홉이 모두 있는 행 %s (%.1f%%)'
          % (f'{full:,}', full / len(rows) * 100))

        for field in REQUIRED:
            n = sum(1 for r in rows if getattr(r, field, None) is not None)
            flag = '' if n == len(rows) else '  ←'
            w('      %-16s %6s (%5.1f%%)%s'
              % (field, f'{n:,}', n / len(rows) * 100, flag))

        w('')
        verified = sum(1 for r in rows
                       if r.verify_status == PublicFoodNutrition.VERIFY_PASS)
        w('   검산 통과 %s (%.1f%%) — 나머지는 원본에 빈 칸이 많아 못 잰 것이다'
          % (f'{verified:,}', verified / len(rows) * 100))
        w('─' * 66)

    def _lookup_in_chunks(self, report_nos, size=5000):
        """
        IN 절을 나눠 던진다.

        운영의 FoodItem 은 183 만 행이다. 번호를 한 번에 IN 으로 넣으면
        max_allowed_packet 에 걸리거나 옵티마이저가 포기한다.
        """
        found = {}
        for i in range(0, len(report_nos), size):
            found.update(product_nutrition.for_report_nos(report_nos[i:i + size]))
        return {no: row for no, row in found.items() if row is not None}
