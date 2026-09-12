# -*- coding: utf-8 -*-
"""
농진청 국가표준식품성분표(엑셀)를 PublicFoodNutrition 에 적재한다.

    python manage.py load_rda_nutrition "식품성분표(10개정판).xlsx" --dry-run
    python manage.py load_rda_nutrition "식품성분표(10개정판).xlsx"

왜 식약처 표와 같은 표에 넣나
─────────────────────────────
후보 찾기(nutrition_candidates)·기여도(nutrition_contrib)·표시가 이미 이 표를
본다. 표를 나누면 그 일을 하는 코드가 두 벌이 되고, 두 벌은 언젠가 한쪽만
고쳐진다. `source_db` 로 가른다.

적재하면서 스스로 검산한다
──────────────────────────
열을 하나 밀려 읽어도 예외가 나지 않는다 — 조용히 엉뚱한 값이 들어가고 그
표가 라벨에 실린다. 그래서 행마다 질량 합과 규정 계수 열량을 잰다
(mfds_nutrition.verify_row 를 그대로 쓴다. 검산식을 두 벌로 두지 않는다).

**어긋난 비율은 잰 행 기준으로 본다.** 두 표는 빈 칸의 양이 전혀 달라서,
전체 대비로 보면 견줄 수가 없다.

    식약처 적재본   통과 5,577 · 어긋남 515 · 못 잼 312,968  → 잰 것 중 8.5 % 어긋남
    농진청 10.4     통과 3,030 · 어긋남 278 · 못 잼 58       → 잰 것 중 8.4 % 어긋남

거의 같다. 매핑이 밀렸다면 이 수가 0 에 가깝거나 절반이 넘는다. 8 % 대는
**실제 식품 데이터가 원래 그만큼 흔들린다**는 뜻이다.

어긋나는 것들에는 까닭이 있다
─────────────────────────────
표본이 곤약·돼지감자·무설탕껌이었다. 전부 **당알콜이나 난소화성 탄수화물**이
많은 식품인데, 이 엑셀에는 **당알콜 열이 아예 없다**(137 열 어디에도). 열량은
거기서 오는데 그 값이 표에 없으니 재계산이 영원히 안 맞는다. 매핑 문제가
아니라 원본의 한계다.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from v1.label.models import PublicFoodNutrition as P
from v1.label.services import rda_nutrition as rda


class Command(BaseCommand):
    help = '농진청 국가표준식품성분표 엑셀을 적재한다'

    def add_arguments(self, parser):
        parser.add_argument('path', help='엑셀 파일 경로')
        parser.add_argument('--dry-run', action='store_true',
                            help='저장하지 않고 세기만 한다')
        parser.add_argument('--show', type=int, default=5, help='표본 개수')

    # ── 쓰는 일 ──────────────────────────────────────────────────────────
    #
    # 처음에는 줄마다 update_or_create 를 부르고 그 줄마다 트랜잭션을 열었다.
    # 개발 PC 는 DB 가 같은 기계라 순식간이었는데, 운영은 **DB 가 별도 호스트**
    # 라 줄마다 왕복이 곱해진다. 3,366 줄이면 왕복이 1 만 번을 넘어 5~20 분이
    # 걸렸고, 진행 표시가 없어서 사용자는 멎은 줄 알았다.
    #
    # 있는 것을 한 번에 읽어 두고 bulk_create / bulk_update 로 묶는다. 왕복이
    # 1 만 번에서 몇십 번으로 준다.
    CHUNK = 500

    def _write(self, pending, w):
        """(코드, 값) 목록을 묶어서 넣는다. 넣은 수를 돌려준다."""
        codes = [code for code, _ in pending]
        have = {}
        for i in range(0, len(codes), self.CHUNK):
            have.update({r.food_cd: r.pk
                         for r in P.objects.filter(food_cd__in=codes[i:i + self.CHUNK])
                                           .only('pk', 'food_cd')})

        value_fields = sorted({k for _, f in pending for k in f})
        new_rows, old_rows = [], []
        for code, fields in pending:
            pk = have.get(code)
            if pk is None:
                new_rows.append(P(food_cd=code, **fields))
            else:
                old_rows.append(P(pk=pk, food_cd=code, **fields))

        done = 0
        for i in range(0, len(new_rows), self.CHUNK):
            with transaction.atomic():
                P.objects.bulk_create(new_rows[i:i + self.CHUNK])
            done += len(new_rows[i:i + self.CHUNK])
            w('    넣는 중… %s' % f'{done:,}')
        for i in range(0, len(old_rows), self.CHUNK):
            with transaction.atomic():
                P.objects.bulk_update(old_rows[i:i + self.CHUNK], value_fields)
            done += len(old_rows[i:i + self.CHUNK])
            w('    고치는 중… %s' % f'{done:,}')
        return done

    def handle(self, *args, **opts):
        w = self.stdout.write
        try:
            items = rda.read_workbook(opts['path'])
        except FileNotFoundError:
            raise CommandError('파일을 못 찾았다: %s' % opts['path'])
        if not items:
            raise CommandError('읽은 행이 없다. 시트 이름이 바뀌었는지 본다.')

        w('읽은 행: %s' % f'{len(items):,}')

        by_sci, by_name = rda.agri_index()
        w('식품원료(A코드) 색인 — 학명 %s · 이름 %s'
          % (f'{len(by_sci):,}', f'{len(by_name):,}'))

        saved = linked_sci = linked_name = 0
        pending = []
        tally = {P.VERIFY_PASS: 0, P.VERIFY_FAIL: 0, P.VERIFY_SKIP: 0}
        no_chol = 0
        bad, samples = [], []

        for item in items:
            values = item['values']
            if values.get('cholesterols') is None:
                no_chol += 1

            status, why = rda.verify(values)
            tally[status] += 1
            if status == P.VERIFY_FAIL and len(bad) < opts['show']:
                bad.append((item['food_nm_kr'], why))

            agri_id = by_sci.get(rda.species(item['scnm']))
            if agri_id:
                linked_sci += 1
            else:
                agri_id = by_name.get(rda.base_name(item['food_nm_kr']))
                if agri_id:
                    linked_name += 1

            if len(samples) < opts['show']:
                samples.append((item['food_nm_kr'], values.get('calories'), bool(agri_id)))

            if opts['dry_run']:
                continue

            fields = dict(values)
            fields.update({
                'food_nm_kr': item['food_nm_kr'],
                'db_grp_nm': item['db_grp_nm'],
                # 농진청 표는 전부 가식부 100g 당이다. 식약처 적재본의 100mL
                # 15.3 % 문제가 여기서는 아예 없다.
                'basis_amount': 100.0,
                'basis_unit': P.BASIS_G,
                'crt_mth_nm': '분석',
                'sub_ref_name': item['origin'] or '농진청',
                'verify_status': status,
                'source_db': P.SOURCE_RDA,
                'agri_product_id': agri_id,
            })
            pending.append((item['food_cd'], fields))

        if not opts['dry_run']:
            saved = self._write(pending, w)

        n = len(items)
        w('')
        w('  저장            %s%s'
          % (f'{saved:,}', '  (--dry-run: 저장하지 않았다)' if opts['dry_run'] else ''))
        w('  검산 통과        %s (%.1f%%)' % (f"{tally[P.VERIFY_PASS]:,}",
                                            tally[P.VERIFY_PASS] * 100.0 / n))
        w('  검산 어긋남      %s (%.1f%%)' % (f"{tally[P.VERIFY_FAIL]:,}",
                                            tally[P.VERIFY_FAIL] * 100.0 / n))
        w('  못 잼           %s (%.1f%%)' % (f"{tally[P.VERIFY_SKIP]:,}",
                                            tally[P.VERIFY_SKIP] * 100.0 / n))
        w('')
        w('  식품원료 연결    %s (%.1f%%)   학명 %s · 이름 %s'
          % (f'{linked_sci + linked_name:,}', (linked_sci + linked_name) * 100.0 / n,
             f'{linked_sci:,}', f'{linked_name:,}'))
        w('  콜레스테롤 없음  %s (%.1f%%)  — 이 표에 그 열이 아예 없다'
          % (f'{no_chol:,}', no_chol * 100.0 / n))

        if bad:
            w('')
            w('  [검산 어긋남 표본]')
            for name, why in bad:
                w('    %-30s %s' % (name[:30], why))
        if samples:
            w('')
            w('  [적재 표본]')
            for name, kcal, linked in samples:
                w('    %-30s %6s kcal  %s' % (name[:30], kcal,
                                              'A코드 연결' if linked else ''))

        # 잰 행 기준으로 본다. 식약처 적재본이 8.5 % 이므로 그 근처는 정상이다.
        measured = tally[P.VERIFY_PASS] + tally[P.VERIFY_FAIL]
        if measured:
            rate = tally[P.VERIFY_FAIL] * 100.0 / measured
            w('  (잰 행 기준 어긋남 %.1f%% — 식약처 적재본은 8.5%%)' % rate)
            if rate > 15:
                w('')
                w('  ** 잰 행의 15%% 를 넘는다. 열 매핑을 의심한다. **')
