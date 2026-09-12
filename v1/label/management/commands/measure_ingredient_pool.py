# -*- coding: utf-8 -*-
"""
같은 품목보고번호를 여러 곳이 따로 등록하고 있는가. **재기만 한다.**

    python manage.py measure_ingredient_pool
    python manage.py measure_ingredient_pool --show 20

왜 표를 안 만들고 재는가
────────────────────────
같은 번호는 법적으로 같은 품목이다. 그러니 표시명·알레르기·영양성분은 어느
회사가 적어도 같아야 하고, 지금은 같은 조사를 회사 수만큼 반복하고 있다.
그 반복을 없애는 것이 공용 원료 풀이다.

그런데 **만들기 전에 알아야 할 것이 셋**이다.

    ① 같은 번호를 두 곳 이상이 등록한 원료가 몇 개인가?
    ② 그 원료들의 값이 실제로 같은가, 갈리는가?
    ③ 갈린다면 얼마나?

①이 열 개뿐이면 이 기능은 값이 없다. ②가 심하게 갈리면 **보여 주는 것 자체가
위험하다** — 틀린 값이 퍼지고 그 순간 우리 책임이 된다.

설계를 먼저 하고 데이터를 나중에 본 적이 있다(3장, 식품구분 4분류). 통째로
버렸다. 순서를 뒤집으면 아무도 안 쓰는 표를 운영하게 된다.

**아무것도 저장하지 않고, 누가 등록했는지도 세지 않는다.** 세는 것은 "몇
곳" 까지다 — 그게 이 단계에서 알아야 할 전부다.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from v1.label.models import MyIngredient

# 견줄 값들. 공시 정보이거나 그 파생이라 나눌 수 있는 것들만 본다.
# 배합비·거래처·단가는 애초에 이 표에 없다.
COMPARE = (
    ('원재료 표시명', 'ingredient_display_name'),
    ('식품유형', 'prdlst_dcnm'),
    ('알레르기', 'allergens'),
    ('제조사', 'bssh_nm'),
)


def _key(value):
    """견줄 때만 쓰는 형태. 공백과 대소문자 차이로 갈렸다고 하면 안 된다."""
    return ' '.join(str(value or '').split()).lower()


class Command(BaseCommand):
    help = '같은 품목보고번호를 여러 곳이 등록했는지, 값이 갈리는지 잰다 (읽기만)'

    def add_arguments(self, parser):
        parser.add_argument('--show', type=int, default=10, help='표본 개수')
        parser.add_argument('--min-owners', type=int, default=2,
                            help='몇 곳 이상 겹친 것만 (기본 2)')

    def handle(self, *args, **opts):
        w = self.stdout.write

        rows = (MyIngredient.objects
                .exclude(delete_YN='Y')
                .exclude(user_id__isnull=True)
                .exclude(prdlst_report_no__isnull=True)
                .exclude(prdlst_report_no='')
                .values('prdlst_report_no', 'user_id',
                        *[f for _, f in COMPARE]))

        by_no = defaultdict(list)
        for r in rows:
            no = (r['prdlst_report_no'] or '').strip()
            if no:
                by_no[no].append(r)

        # ⓪ 그 번호가 **식약처에 실제로 있는가.**
        #
        # 처음에는 이걸 안 쟀다. 그런데 갈린 표본을 열어 보니 한 번호 아래에
        # 밀가루·설탕·혼합간장이 함께 있었다. "같은 품목을 회사마다 다르게
        # 적었다" 가 아니라 **그 번호가 애초에 품목보고번호가 아니었다**는
        # 뜻이다. 그걸 가르지 않으면 갈림 비율이 무엇을 말하는지 알 수 없다.
        from v1.label.models import FoodItem

        nums = list(by_no)
        known = set()
        for i in range(0, len(nums), 500):
            known.update(FoodItem.objects
                         .filter(prdlst_report_no__in=nums[i:i + 500])
                         .values_list('prdlst_report_no', flat=True))

        total_no = len(by_no)
        shared = {no: items for no, items in by_no.items()
                  if len({i['user_id'] for i in items}) >= opts['min_owners']}

        w('번호가 있는 원료: %s건 · 고유 번호 %s개'
          % (f'{sum(len(v) for v in by_no.values()):,}', f'{total_no:,}'))
        w('식약처에 있는 번호: %s개 (%.1f%%) · **없는 번호 %s개 (%.1f%%)**'
          % (f'{len(known):,}', len(known) * 100.0 / total_no if total_no else 0,
             f'{total_no - len(known):,}',
             (total_no - len(known)) * 100.0 / total_no if total_no else 0))
        w('두 곳 이상이 등록한 번호: %s개 (%.1f%%)'
          % (f'{len(shared):,}', len(shared) * 100.0 / total_no if total_no else 0))

        if not shared:
            w('')
            w('  겹치는 것이 없다. **이 단계에서 멈춘다** — 공용 풀은 아직 값이 없다.')
            return

        # ② 값이 갈리는가
        w('')
        w('[항목별 — 겹친 번호 안에서 값이 갈리는 비율]')
        samples = defaultdict(list)
        for label, field in COMPARE:
            agree = differ = empty = 0
            for no, items in shared.items():
                vals = {_key(i[field]) for i in items if _key(i[field])}
                if not vals:
                    empty += 1
                elif len(vals) == 1:
                    agree += 1
                else:
                    differ += 1
                    if len(samples[label]) < opts['show']:
                        samples[label].append((no, sorted(vals)[:3]))
            # 이름을 겹치지 않게 쓴다. known 은 위에서 '식약처에 있는 번호'
            # 집합으로 쓰고 있다 — 여기서 덮으면 아래 표본 표시가 조용히
            # 터진다(실제로 그랬다).
            counted = agree + differ
            w('  %-14s 같음 %4d · 갈림 %4d · 아무도 안 적음 %4d   → 갈림 %.1f%%'
              % (label, agree, differ, empty,
                 differ * 100.0 / counted if counted else 0.0))

        w('')
        w('[갈린 표본 — 이것을 보고 2단계를 할지 정한다]')
        for label, _ in COMPARE:
            if not samples[label]:
                continue
            w('  · %s' % label)
            for no, vals in samples[label][:opts['show']]:
                w('      %-16s %-6s %s'
                  % (no, '' if no in known else '[없는번호]',
                     ' | '.join(v[:28] for v in vals)))

        # 갈림이 '없는 번호' 에 몰려 있으면, 그것은 회사마다 다르게 적은 것이
        # 아니라 번호를 잘못 넣은 것이다. 둘은 전혀 다른 문제이고 고치는 법도
        # 다르다 — 앞은 공용 풀, 뒤는 번호 검증이다.
        bad_shared = [no for no in shared if no not in known]
        if bad_shared:
            w('')
            w('  겹친 번호 %d개 중 **식약처에 없는 것이 %d개**다.'
              % (len(shared), len(bad_shared)))
            w('  그쪽의 갈림은 "회사마다 다르게 적었다" 가 아니라 '
              '"번호를 잘못 넣었다" 이다.')

        w('')
        w('  읽기만 했다. 아무것도 저장하지 않았다.')
