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
  ③ 도달률       **적재본 → 제품 조회 방향으로** 전수로 센다 (+ 안 붙은 번호의 생김새)
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
from django.db.models.functions import Length

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
        #
        # 예전에는 앞 20,000 건만 잘라 세었다. **정렬 없는 LIMIT 은 표본이
        # 아니다** — MySQL 이 PK 차례(사전순)로 돌려주니 '1' 로 시작하는 번호에
        # 통째로 쏠린다. 그 표본으로는 적재본이 14자리 59 %, 제품 조회가
        # 13자리 41 % 로 찍혔는데, 어느 쪽도 실제 분포가 아니다.
        #
        # 그래서 자릿수로 묶어 **전수로** 센다. FoodItem 184 만 행을 한 번
        # 훑지만 읽는 칸이 번호 하나뿐이라(prdlst_report_no 는 PK,
        # item_report_no 에는 인덱스가 있다) 돌아오는 것은 줄 네댓 개다.
        # 하루에 한 번 사람이 눈으로 보려고 돌리는 진단 명령이라 몇 초는
        # 치러도 된다 — 틀린 분포보다 느린 분포가 낫다.
        self._shape('   적재본 ',
                    product_nutrition.matching_report_nos(), 'item_report_no')
        self._shape('   제품조회', FoodItem.objects.all(), 'prdlst_report_no')

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

        # **남은 기회가 어디 있나.** 26,577 개는 적재본에 있는데 제품 조회에
        # 없다. 안 붙은 것들의 자릿수가 붙은 쪽과 같으면 그냥 FoodItem 에 없는
        # 품목이라 여기서 할 일이 없고, 다르면 번호 체계가 갈린 것이라 고칠
        # 여지가 있다. 둘은 대책이 전혀 다르므로 합계 하나로는 못 가른다.
        #
        # keys 와 matched 가 이미 메모리에 있어 차집합이면 된다 — 질의를 더
        # 던지지 않는다.
        unmatched = {}
        for key in keys:
            if key not in matched:
                unmatched[len(key)] = unmatched.get(len(key), 0) + 1
        gap = sum(unmatched.values())
        if gap:
            w('   → 안 붙은 번호 %s 개의 생김새 %s'
              % (f'{gap:,}', self._dist(unmatched, gap)))

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

        # **반올림이 화살표와 싸우면 안 된다.** 나트륨은 197,771/197,824 =
        # 99.973 % 라 %.1f 로는 100.0 % 로 찍혔다. 화살표는 붙었는데 숫자는 꽉
        # 차 보이니 읽는 사람이 모순을 본다 — 그래서 빈 칸이 있는 줄만 소수
        # 둘째 자리까지 내리고 **모자란 개수**를 함께 적는다. 53 건이면 53 건이
        # 보이는 편이 99.97 % 보다 빠르다. '100.0' 과 '99.97' 은 둘 다 다섯
        # 자리라 칸은 그대로 선다.
        full = sum(1 for r in rows
                   if all(getattr(r, f, None) is not None for f in REQUIRED))
        w('   표시 필수 아홉이 모두 있는 행 %s%s'
          % (f'{full:,}', self._share(full, len(rows))))

        for field in REQUIRED:
            n = sum(1 for r in rows if getattr(r, field, None) is not None)
            # 화살표는 _share 가 붙인다. 여기서 또 붙이면 '← 53건 빔  ←' 가 된다.
            w('      %-16s %6s%s'
              % (field, f'{n:,}', self._share(n, len(rows))))

        w('')
        verified = sum(1 for r in rows
                       if r.verify_status == PublicFoodNutrition.VERIFY_PASS)
        w('   검산 통과 %s (%.1f%%) — 나머지는 원본에 빈 칸이 많아 못 잰 것이다'
          % (f'{verified:,}', verified / len(rows) * 100))
        w('─' * 66)

    def _shape(self, tag, qs, field):
        """
        번호의 자릿수 분포. **두 표를 나란히 찍는 것이 목적이다.**

        "안 붙는다" 는 증상 하나에 까닭이 둘이다 — 정말 값이 없거나, 두 표가
        번호를 다른 모양으로 적고 있거나. 자릿수를 세면 그 자리에서 갈린다.

        세는 일은 DB 에 맡긴다. 파이썬으로 돌려받아 세려면 두 표에서 216 만
        줄을 끌어와야 하고, 그래서 예전에는 앞 20,000 건만 잘라 세다가 PK
        차례에 쏠린 분포를 찍었다. GROUP BY 는 번호 칸 하나만 읽고 돌려주는
        것은 자릿수별 줄 몇 개뿐이다.

        파이썬 len(strip()) 과 달리 SQL 의 CHAR_LENGTH 는 공백을 세지만, 공백이
        섞인 번호는 normalize() 가 조인 전에 어차피 버린다 — ② 는 원본이 어떤
        모양으로 적혀 있는지를 보는 자리라 원본 그대로 세는 편이 맞다.
        """
        rows = (qs.order_by()
                .annotate(n=Length(field))
                .values('n')
                .annotate(c=Count('pk'))
                .order_by('-c'))
        lengths = {row['n']: row['c'] for row in rows}
        total = sum(lengths.values())
        if not total:
            self.stdout.write('%s (비어 있다)' % tag)
            return

        # 예시는 분포와 상관없이 **맨 앞 3 건**이다. 하이픈·공백·문자가 섞여
        # 있는지를 눈으로 보는 용도라 그것으로 족하지만, 대표하는 값으로 읽히면
        # 위의 분포와 어긋나 보인다. 그래서 이름표에 적어 둔다.
        samples = [(raw or '').strip()
                   for raw in qs.order_by().values_list(field, flat=True)[:3]]
        # **센 줄 수를 함께 적는다.** 이 GROUP BY 가 자릿수가 아니라 번호로
        # 묶이면(values/annotate 를 잘못 엮으면 그렇게 된다) 분포는 그럴듯한데
        # 합이 ①·③ 의 건수와 어긋난다. 비율만 찍으면 그 어긋남이 안 보인다 —
        # 합계를 옆에 적어 두면 읽는 사람이 대조할 것도 없이 바로 드러난다.
        self.stdout.write('%s %s개 · %s   예(맨 앞 3건): %s'
                          % (tag, f'{total:,}', self._dist(lengths, total),
                             ', '.join(samples)))

    def _dist(self, lengths, total):
        """
        {자릿수: 개수} 를 '14자리 59% · 13자리 26%' 한 줄로.

        많은 것부터 넷까지만 적는다 — 꼬리는 1 % 미만이라 줄만 길어진다.
        자릿수가 None 인 칸(NULL)은 '?' 로 적는다. 숨기면 합이 안 맞는다.
        """
        top = sorted(lengths.items(), key=lambda kv: -kv[1])[:4]
        return ' · '.join(
            '%s자리 %.0f%%' % ('?' if ln is None else ln, c / total * 100)
            for ln, c in top)

    def _share(self, n, total):
        """
        ' (99.97%)  ← 53건 빔' 또는 ' (100.0%)'.

        꽉 찬 줄은 지금처럼 짧게 둔다 — 아홉 줄 중 여섯이 100 % 인데 전부
        '(100.00%)  ← 0건 빔' 으로 늘어놓으면 모자란 줄이 묻힌다.
        """
        share = n / total * 100 if total else 0
        if n == total:
            return ' (%5.1f%%)' % share
        return ' (%5.2f%%)  ← %s건 빔' % (share, f'{total - n:,}')

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
