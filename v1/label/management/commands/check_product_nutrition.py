"""
제품 조회의 제품에 식약처 영양성분이 **얼마나 닿는가**를 잰다.

    python manage.py check_product_nutrition
    python manage.py check_product_nutrition --sample 50000   # 반대 방향도 표본으로

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
  ① 적재본 쪽    얼마나 쌓여 있고 그중 번호가 있는 것이 몇인가
  ② 번호의 생김새 두 표가 번호를 같은 모양으로 적고 있는가 (자릿수 분포)
  ③ 도달률       **적재본 → 제품 조회 방향으로** 전수로 센다
  ④ 중복도       한 번호에 행이 여럿인가 (고르는 규칙이 필요한가)
  ⑤ 쓸 만한가    기준 단위(g·mL) · 표시 필수 아홉 충족률 · 검산 분포

방향을 왜 뒤집었나
──────────────────
처음에는 FoodItem 을 표본으로 뽑아 셌고 **0.0 % 가 나왔다.** 표본을
`-prms_dt`(허가일자 최근순)로 뽑은 것이 함정이었다.

  · 최근순은 **가장 안 맞는 슬라이스**다. 식약처 조사분은 2019~2021 이
    주력이라 갓 신고된 제품에는 값이 없다
  · `prms_dt` 에는 '5015-07-10' 같은 오신고가 섞여 있다(product_search 주석).
    최근순 정렬은 그 쓰레기부터 집는다

적재본 쪽 고유 번호는 22 만 개뿐이라 **표본 없이 전부** 셀 수 있다. 번호
하나는 FoodItem 의 PK 하나에 대응하므로 그 수가 곧 "뱃지가 뜨는 제품 수" 다.
표본도 편향도 없다.
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
            help='반대 방향(FoodItem→적재본)도 이만큼 표본으로 본다. '
                 '도달률 자체는 표본 없이 전수로 센다')

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
        w('② 번호의 생김새 — 두 표가 같은 모양으로 적고 있나')
        #
        # 도달률이 0 에 가까우면 원인은 둘 중 하나다. **자릿수 분포를 나란히
        # 놓으면 눈으로 갈린다** — 한쪽이 13 자리인데 다른 쪽이 14 자리면
        # 아무리 많이 쌓여 있어도 영영 안 만난다.
        self._shape('   적재본 ', product_nutrition.matching_report_nos()
                    .values_list('item_report_no', flat=True)[:20000])
        self._shape('   제품조회', FoodItem.objects
                    .values_list('prdlst_report_no', flat=True)[:20000])

        w('')
        w('③ 도달률 — 적재본에서 제품 조회 쪽으로 센다')
        #
        # **방향이 중요하다.** 예전에는 FoodItem 을 표본으로 뽑아 셌는데, 그
        # 표본을 `-prms_dt` 로 뽑은 것이 함정이었다.
        #
        #   · 허가일자 최근순은 **가장 안 맞는 슬라이스**다. 식약처 조사분은
        #     2019~2021 이 주력이라 갓 신고된 제품에는 값이 없다
        #   · prms_dt 에는 '5015-07-10' 같은 오신고가 섞여 있다(product_search
        #     주석). 최근순 정렬은 그 쓰레기부터 집는다
        #
        # 적재본 쪽 고유 번호는 22 만 개뿐이라 **표본 없이 전부** 셀 수 있고,
        # 번호 하나는 FoodItem 의 PK 하나에 대응하므로 이 수가 곧 "뱃지가 뜨는
        # 제품 수" 다. 표본도 편향도 없다.
        keys = sorted({
            product_nutrition.normalize(no)
            for no in (product_nutrition.matching_report_nos()
                       .values_list('item_report_no', flat=True).distinct())
        } - {''})
        w('   적재본의 고유 보고번호 %s 개' % f'{len(keys):,}')

        matched = self._existing_food_items(keys)
        food_total = FoodItem.objects.count()
        w(self.style.SUCCESS(
            '   → 제품 조회에 실제로 있는 번호 %s 개 (적재본의 %.1f%%)'
            % (f'{len(matched):,}', len(matched) / len(keys) * 100 if keys else 0)))
        w('   → 목록에서 뱃지가 뜨는 제품 %s / %s 건 (%.2f%%)'
          % (f'{len(matched):,}', f'{food_total:,}',
             len(matched) / food_total * 100 if food_total else 0))

        if not matched:
            w(self.style.WARNING(
                '   하나도 안 만난다. ② 의 자릿수 분포를 보라 — 두 표가 번호를 '
                '다른 모양으로 적고 있으면 아무리 쌓아도 영영 안 붙는다.'))
            return

        limit = opts['sample']
        if limit:
            # 반대 방향도 궁금하면 본다. **표본은 PK 순으로 뽑는다** —
            # prms_dt 로 뽑으면 위에 적은 두 함정을 그대로 밟는다.
            sample = list(FoodItem.objects.order_by('prdlst_report_no')
                          .values_list('prdlst_report_no', flat=True)[:limit])
            hit = sum(1 for no in sample
                      if product_nutrition.normalize(no) in matched)
            w('   (참고) 번호순 표본 %s 건 중 %s 건 (%.2f%%)'
              % (f'{len(sample):,}', f'{hit:,}',
                 hit / len(sample) * 100 if sample else 0))

        found = self._lookup_in_chunks(sorted(matched))

        w('')
        w('④ 한 번호에 행이 여럿인가')
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
        w('⑤ 붙은 행이 표시에 쓸 만한가')
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

    def _shape(self, tag, values):
        """
        번호의 자릿수 분포와 표본 몇 개. **두 표를 나란히 찍는 것이 목적이다.**

        "안 붙는다" 는 증상 하나에 까닭이 둘이다 — 정말 값이 없거나, 두 표가
        번호를 다른 모양으로 적고 있거나. 자릿수를 세면 그 자리에서 갈린다.
        """
        lengths = {}
        samples = []
        n = 0
        for raw in values:
            text = (raw or '').strip()
            n += 1
            lengths[len(text)] = lengths.get(len(text), 0) + 1
            if len(samples) < 3:
                samples.append(text)
        if not n:
            self.stdout.write('%s (비어 있다)' % tag)
            return
        top = sorted(lengths.items(), key=lambda kv: -kv[1])[:4]
        dist = ' · '.join('%d자리 %.0f%%' % (ln, c / n * 100) for ln, c in top)
        self.stdout.write('%s %s   예: %s' % (tag, dist, ', '.join(samples)))

    def _existing_food_items(self, keys, size=5000):
        """
        이 번호들 중 FoodItem 에 실제로 있는 것. PK 조회라 싸다.

        IN 절을 나눠 던진다 — 22 만 개를 한 번에 넣으면 max_allowed_packet 에
        걸리거나 옵티마이저가 포기한다.
        """
        found = set()
        for i in range(0, len(keys), size):
            chunk = keys[i:i + size]
            found.update(FoodItem.objects
                         .filter(prdlst_report_no__in=chunk)
                         .values_list('prdlst_report_no', flat=True))
        return found

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
