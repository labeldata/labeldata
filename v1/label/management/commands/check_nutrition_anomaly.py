# -*- coding: utf-8 -*-
"""
영양성분DB 에서 **이상해 보이는 행**을 찾아 표에 남긴다.

    python manage.py check_nutrition_anomaly            # 전량, 결과 저장
    python manage.py check_nutrition_anomaly --rules A  # 성분 모순만
    python manage.py check_nutrition_anomaly --rules C --dry-run   # 열량만 세기
    python manage.py check_nutrition_anomaly --dry-run  # 세기만 (저장 안 함)
    python manage.py check_nutrition_anomaly --limit 5000

판정 규칙은 `services/nutrition_anomaly.py` 에 있고, 그 파일 머리에 **왜 이렇게
찾는지**가 적혀 있다 — 배합비를 모르므로 "맞다" 는 증명할 수 없고 "그럴 수
없다" 를 찾는 것이 최선이다.

원재료는 품목보고번호로 붙인다(`FoodItem.rawmtrl_nm_sorted`, 많이 쓴 것부터).
운영 실측 (2026-09-18): 적재 322,426 · 번호 있음 224,469 · 번호가 품목에
닿는 비율 87.8 %. 못 닿는 행은 성분 모순(A)만 잰다.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from v1.label.models import FoodItem, NutritionAnomaly, PublicFoodNutrition
from v1.label.services import nutrition_anomaly as rules

CHUNK = 2000


class Command(BaseCommand):
    help = '영양성분DB 의 이상 행을 찾아 표에 남긴다'

    def add_arguments(self, parser):
        parser.add_argument('--rules', default='AB',
                            help='A=성분 모순 · B=상위 원료와 0 · C=열량 (기본 AB)')
        parser.add_argument('--limit', type=int, default=0,
                            help='앞에서 몇 행만 (0=전량)')
        parser.add_argument('--dry-run', action='store_true',
                            help='세기만 하고 저장하지 않는다')
        parser.add_argument('--sample', type=int, default=0,
                            help='규칙마다 몇 건을 눈으로 보여 줄지')

    def handle(self, *args, **opts):
        want = str(opts['rules']).upper()
        do_a, do_b, do_c = 'A' in want, 'B' in want, 'C' in want
        limit, dry = opts['limit'], opts['dry_run']
        w = self.stdout.write

        qs = PublicFoodNutrition.objects.all().order_by('id')
        if limit:
            qs = qs[:limit]

        total = qs.count()
        w('행 %d 개를 잰다 (규칙 %s)' % (total, want))

        found, by_rule, with_names, seen = [], {}, 0, 0
        samples = {}      # 규칙마다 몇 건은 눈으로 봐야 오탐인지 안다
        for chunk in self._chunks(qs.iterator(chunk_size=CHUNK), CHUNK):
            # 원재료는 번호로 한 번에 끌어온다. 행마다 조회하면 32만 번이다.
            names = {}
            if do_b:
                nos = [r.item_report_no for r in chunk if r.item_report_no]
                if nos:
                    names = dict(FoodItem.objects
                                 .filter(prdlst_report_no__in=nos)
                                 .values_list('prdlst_report_no', 'rawmtrl_nm_sorted'))

            for row in chunk:
                seen += 1
                sorted_text = names.get(row.item_report_no or '') if do_b else None
                if sorted_text:
                    with_names += 1
                hits = rules.check_internal(row) if do_a else []
                if do_b and sorted_text:
                    hits += rules.check_top_ingredients(row, sorted_text)
                if do_c:
                    hits += rules.check_energy(row)
                for code, severity, detail in hits:
                    by_rule[code] = by_rule.get(code, 0) + 1
                    if opts['sample'] and len(samples.setdefault(code, [])) < opts['sample']:
                        samples[code].append(
                            '%s | %s | %s' % (row.food_nm_kr or '',
                                              (sorted_text or '')[:40], detail))
                    found.append(NutritionAnomaly(
                        nutrition=row,
                        report_no=row.item_report_no or '',
                        food_name=row.food_nm_kr or '',
                        maker_nm=row.maker_nm or '',
                        food_type='',        # 아래에서 채운다
                        rule_code=code, severity=severity, detail=detail[:300]))

        # 식품유형은 목록에서 거르는 데 쓴다. 이상 행만 다시 조회하면 되므로
        # 전량을 끌어오지 않는다.
        if found:
            nos = {a.report_no for a in found if a.report_no}
            types = dict(FoodItem.objects.filter(prdlst_report_no__in=nos)
                         .values_list('prdlst_report_no', 'prdlst_dcnm'))
            for a in found:
                a.food_type = (types.get(a.report_no) or '')[:100]

        w('원재료를 붙인 행 %d / %d' % (with_names, seen))
        for code in sorted(by_rule):
            w('  %-4s %d' % (code, by_rule[code]))
            for line in samples.get(code, []):
                w('        %s' % line)
        w(self.style.SUCCESS('이상 판정 %d 건' % len(found)))

        if dry:
            w('세기만 했습니다. 저장하려면 --dry-run 을 빼세요.')
            return

        # 돌린 규칙의 옛 판정만 지운다 — A 만 다시 돌렸는데 B 결과까지
        # 사라지면 목록이 반쪽이 된다.
        #
        # 돌린 갈래를 그대로 조건으로 쓴다. 예전에는 A·B 를 if/elif 로 갈랐는데,
        # 둘 다 돌리면 '전부 지우기' 로 떨어졌다. 갈래가 셋이 된 지금 그대로
        # 두면 `--rules AB` 가 **C 결과까지 쓸어 간다.**
        families = [f for f in ('A', 'B', 'C') if f in want]
        with transaction.atomic():
            old = NutritionAnomaly.objects.all()
            if families:
                condition = Q()
                for family in families:
                    condition |= Q(rule_code__startswith=family)
                old = old.filter(condition)
            removed = old.count()
            old.delete()
            NutritionAnomaly.objects.bulk_create(found, batch_size=1000)
        w(self.style.SUCCESS('옛 판정 %d 건을 지우고 %d 건을 남겼습니다.'
                             % (removed, len(found))))

    @staticmethod
    def _chunks(iterator, size):
        batch = []
        for item in iterator:
            batch.append(item)
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch
