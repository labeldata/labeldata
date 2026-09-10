"""
품목보고번호로 못 붙은 원료를 **이름으로** 얼마나 더 붙일 수 있는가.

    python manage.py check_ingredient_name_match
    python manage.py check_ingredient_name_match --show 30

보고번호 조인은 도달률 10.5 % 에서 멈췄다(원료 172 개 중 18 개). 남은 것을
이름으로 맞추면 어디까지 가는지를 재서, 식약처 DB 를 서버에 올릴 값이
있는지 판단할 근거를 만든다.

**점수는 답이 아니라 후보다.** 이름이 비슷하다고 같은 물건이 아니다
('딸기향' 과 '딸기'). 그래서 숫자 하나로 결론짓지 않고 문턱별로 나눠 세고,
실제로 무엇이 붙었는지를 함께 보여 준다 — 사람이 눈으로 보고 판단할 수
있어야 한다. 이 명령은 아무것도 저장하지 않는다.

원료명에는 규격·로트가 붙어 있다('한라봉향 FAC-HMT4733012'). 그대로 견주면
점수가 낮게 나오므로 뒤에 붙은 코드를 떼고 견준다.
"""
from collections import Counter

from django.core.management.base import BaseCommand
from rapidfuzz import fuzz, process

from v1.label.models import MyIngredient, PublicFoodNutrition

# 정규화는 nutrition_candidates 한 곳에서만 정의한다. 여기 따로 두면 측정과
# 실제 후보 제시가 다른 규칙을 쓰게 되고, 그러면 이 측정값이 거짓말이 된다.
from v1.label.services.nutrition_candidates import normalize  # noqa: E402


class Command(BaseCommand):
    help = '원료명으로 식약처 영양DB 에 얼마나 더 닿는지 잰다 (저장하지 않음)'

    def add_arguments(self, parser):
        parser.add_argument('--show', type=int, default=20,
                            help='보여 줄 표본 수')
        parser.add_argument('--limit-source', type=int, default=0,
                            help='식약처 후보를 이만큼으로 줄인다 (0 이면 전부)')

    def handle(self, *args, **opts):
        w = self.stdout.write

        # ── 우리 원료 ────────────────────────────────────────────────
        mine = list(MyIngredient.objects.values_list(
            'my_ingredient_id', 'prdlst_nm', 'prdlst_report_no'))
        mine = [(i, nm, (no or '').strip()) for i, nm, no in mine if (nm or '').strip()]
        if not mine:
            w(self.style.ERROR('원료 보관함이 비어 있다.'))
            return

        nums = {no for _, _, no in mine if no}
        matched_no = set(PublicFoodNutrition.objects
                         .filter(item_report_no__in=nums)
                         .values_list('item_report_no', flat=True))

        # 보고번호로 이미 붙은 것은 빼고, 못 붙은 것만 이름으로 맞춰 본다
        todo = [(i, nm) for i, nm, no in mine if not no or no not in matched_no]

        w('─' * 70)
        w('원료 %d 개 · 보고번호로 붙은 것 %d 개 · 이름으로 맞춰 볼 것 %d 개'
          % (len(mine), len(mine) - len(todo), len(todo)))

        # ── 식약처 후보 ──────────────────────────────────────────────
        # 중량(g) 기준이고 검산에서 어긋나지 않은 행만 후보로 둔다.
        # 붙어도 쓸 수 없는 행에 붙이면 도달률이 부풀려진다.
        qs = (PublicFoodNutrition.objects
              .filter(basis_unit=PublicFoodNutrition.BASIS_G)
              .exclude(verify_status=PublicFoodNutrition.VERIFY_FAIL)
              .values_list('id', 'food_nm_kr', 'db_grp_nm'))
        if opts['limit_source']:
            qs = qs[:opts['limit_source']]

        rows = list(qs)
        w('식약처 후보 %s 건 (100g 기준 · 검산 어긋남 제외)' % f'{len(rows):,}')

        names = [normalize(nm) for _, nm, _ in rows]
        w('')

        # ── 맞춰 보기 ────────────────────────────────────────────────
        # token_set_ratio 는 어순과 군더더기에 덜 흔들린다. 원료명은
        # '아이엠에그 오리지널 난황액' 처럼 수식어가 앞에 붙는 일이 잦다.
        results = []
        for ing_id, nm in todo:
            key = normalize(nm)
            if not key:
                continue
            best = process.extractOne(key, names, scorer=fuzz.token_set_ratio,
                                      score_cutoff=60)
            if best is None:
                results.append((nm, None, 0, ''))
                continue
            _, score, idx = best
            results.append((nm, rows[idx][1], score, rows[idx][2]))

        # ── 문턱별 도달률 ────────────────────────────────────────────
        base = sum(1 for _, _, no in mine if no and no in matched_no)
        total = len(mine)
        w('[문턱별 도달률] 보고번호로 붙은 %d 개에 이름 매칭을 더하면' % base)
        w('')
        for th in (95, 90, 85, 80, 70):
            n = sum(1 for _, _, s, _ in results if s >= th)
            w('   %d 점 이상   이름 %3d 개  →  합계 %3d / %d  (%5.1f%%)'
              % (th, n, base + n, total, (base + n) / total * 100))

        w('')
        w('   (점수가 높다고 같은 물건은 아니다 — 아래 표본을 눈으로 봐야 한다)')

        # ── 무엇이 붙었나 ────────────────────────────────────────────
        w('')
        w('─' * 70)
        w('[붙은 것 표본] 점수 높은 순')
        w('')
        for nm, hit, score, grp in sorted(
                (r for r in results if r[2] >= 80), key=lambda r: -r[2])[:opts['show']]:
            w('   %3d  %-26s → %-30s [%s]'
              % (score, nm[:26], (hit or '')[:30], grp or ''))

        w('')
        w('[못 붙은 것 표본] 60 점도 못 넘은 것')
        w('')
        low = [r for r in results if r[2] < 60]
        for nm, _, _, _ in low[:opts['show']]:
            w('   %s' % nm[:60])
        w('   … 모두 %d 개' % len(low))

        # ── 성격별로 갈라 본다 ───────────────────────────────────────
        # 향료·첨가물은 이 DB 의 수록 대상이 아니다. 그것이 몇 개인지 알면
        # "이름 매칭을 더 다듬어야 하는가" 와 "애초에 없는가" 를 가를 수 있다.
        w('')
        w('─' * 70)
        w('[성격별] 못 붙은 원료가 어떤 것들인가')
        w('')
        kinds = Counter()
        for nm, _, score, _ in results:
            if score >= 80:
                continue
            n = nm or ''
            if '향' in n:
                kinds['향료'] += 1
            elif any(k in n for k in ('추출물', '농축', '엑기스')):
                kinds['추출물'] += 1
            elif any(k in n for k in ('색소', '보존', '유화', '산화방지', '팽창')):
                kinds['첨가물(용도명)'] += 1
            elif any(k in n.lower() for k in ('액', '시럽', 'sorbitol', '토올', '토올액')):
                kinds['당류·액상첨가물'] += 1
            else:
                kinds['기타'] += 1
        for k, c in kinds.most_common():
            w('   %-16s %3d 개' % (k, c))
        w('─' * 70)
