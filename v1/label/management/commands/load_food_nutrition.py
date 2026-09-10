"""
식약처 식품영양성분DB 를 우리 표로 옮긴다.

    python manage.py load_food_nutrition                 # 전량 (319,060 건 / 639 회)
    python manage.py load_food_nutrition --pages 3       # 앞 3 쪽만 (연결·매핑 확인)
    python manage.py load_food_nutrition --from-page 200 # 끊긴 자리에서 이어받기
    python manage.py load_food_nutrition --dry-run       # 저장하지 않고 세기만

한 쪽에 최대 500 건이다(그 이상은 API 가 거절한다). 개발계정 일 한도가
10,000 회이므로 전량 적재(639 회)는 한도 안에서 한 번에 끝난다.

**적재하면서 스스로 검산한다.** AMT_NUM 번호를 하나 밀려 읽어도 예외가 나지
않기 때문이다 — 조용히 엉뚱한 값이 들어가고, 그 표가 라벨에 실린다. 그래서
행마다 질량 합(≈기준량)과 규정 계수로 잰 열량을 재고, 어긋난
비율이 높으면 매핑을 의심해야 한다는 뜻이므로 끝에 함께 알린다.
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from v1.label.models import PublicFoodNutrition
from v1.label.services import mfds_nutrition as mfds


class Command(BaseCommand):
    help = '식약처 식품영양성분DB 를 PublicFoodNutrition 에 적재한다'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=0,
                            help='받을 쪽 수 (0 이면 끝까지)')
        parser.add_argument('--from-page', type=int, default=1,
                            help='시작 쪽 (끊긴 자리에서 이어받을 때)')
        parser.add_argument('--rows', type=int, default=mfds.MAX_ROWS,
                            help='쪽당 건수 (최대 500)')
        parser.add_argument('--dry-run', action='store_true',
                            help='저장하지 않고 세기만 한다')
        parser.add_argument('--workers', type=int, default=8,
                            help='동시에 받을 쪽 수 (1 이면 순차)')

    def handle(self, *args, **opts):
        key = getattr(settings, 'MFDS_NUTRITION_API_KEY', '')
        if not key:
            raise CommandError(
                'MFDS_NUTRITION_API_KEY 가 없다. .env 에 넣어라.\n'
                '  https://www.data.go.kr/data/15127578/openapi.do'
            )

        dry = opts['dry_run']
        rows = min(opts['rows'], mfds.MAX_ROWS)
        page = opts['from_page']
        limit_pages = opts['pages']

        stat = {'fetched': 0, 'saved': 0, 'failed_pages': [],
                'pass': 0, 'fail': 0, 'skip': 0,
                'basis_g': 0, 'basis_ml': 0, 'basis_none': 0,
                'report_no': 0}
        groups = {}
        fail_samples = []
        total_count = None
        pages_done = 0

        # 첫 쪽을 먼저 받아 전체 쪽 수를 안다. 그래야 나머지를 나눠 받을 수 있다.
        try:
            first = self._fetch(key, page, rows)
        except Exception as exc:
            raise CommandError('첫 쪽을 받지 못했다: %s' % exc)

        header = first.get('header') or {}
        if header.get('resultCode') not in (None, '00'):
            raise CommandError('API 오류: %s' % header.get('resultMsg'))

        body = first.get('body') or {}
        total_count = body.get('totalCount')
        last_page = math.ceil((total_count or 0) / rows) if total_count else page
        if limit_pages:
            last_page = min(last_page, page + limit_pages - 1)

        self.stdout.write('전체 %s 건 · 쪽당 %d 건 · %d~%d 쪽'
                          % (f'{total_count:,}' if total_count else '?',
                             rows, page, last_page))
        self.stdout.write('동시 수신 %d (한 쪽에 24 초쯤 걸린다 — 순차로는 네 시간이다)'
                          % opts['workers'])

        self._ingest(body.get('items') or [], stat, groups, fail_samples, dry)
        stat['fetched'] += len(body.get('items') or [])

        pages = list(range(page + 1, last_page + 1))
        workers = max(1, opts['workers'])
        started = time.time()

        # 받기는 여럿이 하고 넣기는 하나가 한다. DB 연결을 스레드마다 열지 않기
        # 위해서다 — 넣는 데 3 초, 받는 데 24 초라 병렬로 얻을 것도 없다.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i in range(0, len(pages), workers):
                window = pages[i:i + workers]
                results = list(pool.map(
                    lambda pg: self._fetch_safe(key, pg, rows), window))

                for pg, payload in zip(window, results):
                    if payload is None:
                        stat['failed_pages'].append(pg)
                        continue
                    items = (payload.get('body') or {}).get('items') or []
                    if not items:
                        continue
                    self._ingest(items, stat, groups, fail_samples, dry)
                    stat['fetched'] += len(items)

                done = min(i + workers, len(pages)) + 1
                elapsed = time.time() - started
                rate = done / elapsed if elapsed else 0
                left = (len(pages) + 1 - done) / rate if rate else 0
                self.stdout.write('  %d/%d 쪽 · %s 건 · 남은 시간 %d 분'
                                  % (done, len(pages) + 1, f"{stat['fetched']:,}",
                                     left / 60))

        self._report(stat, groups, fail_samples, total_count, dry)

    # ── 받기 ────────────────────────────────────────────────────────────

    def _fetch(self, key, page, rows):
        # serviceKey 는 이미 URL 인코딩된 값이다. requests 의 params 로 넘기면
        # % 가 다시 인코딩돼(%2F → %252F) 인증이 깨진다. 그래서 직접 붙인다.
        url = '%s?serviceKey=%s&pageNo=%d&numOfRows=%d&type=json' % (
            mfds.API_URL, key, page, rows)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _fetch_safe(self, key, page, rows):
        """한 쪽이 실패해도 전체를 멈추지 않는다. 실패한 쪽은 끝에 알린다."""
        for attempt in (1, 2):
            try:
                payload = self._fetch(key, page, rows)
                head = payload.get('header') or {}
                if head.get('resultCode') not in (None, '00'):
                    raise RuntimeError(head.get('resultMsg'))
                return payload
            except Exception as exc:
                if attempt == 2:
                    self.stderr.write('  %d 쪽 실패: %s' % (page, exc))
                    return None
                time.sleep(2)

    # ── 옮기기 ──────────────────────────────────────────────────────────

    def _ingest(self, items, stat, groups, fail_samples, dry):
        pending = []
        for item in items:
            food_cd = (item.get('FOOD_CD') or '').strip()
            if not food_cd:
                continue

            values = mfds.extract_nutrients(item)
            amount, unit = mfds.parse_basis(item.get('SERVING_SIZE'))
            ok, note = mfds.verify_row(values, amount, unit)

            if ok is True:
                status = PublicFoodNutrition.VERIFY_PASS
                stat['pass'] += 1
            elif ok is False:
                status = PublicFoodNutrition.VERIFY_FAIL
                stat['fail'] += 1
                if len(fail_samples) < 5:
                    fail_samples.append((item.get('FOOD_NM_KR'), note))
            else:
                status = PublicFoodNutrition.VERIFY_SKIP
                stat['skip'] += 1

            if unit == PublicFoodNutrition.BASIS_G:
                stat['basis_g'] += 1
            elif unit == PublicFoodNutrition.BASIS_ML:
                stat['basis_ml'] += 1
            else:
                stat['basis_none'] += 1

            report_no = mfds.normalize_report_no(item.get('ITEM_REPORT_NO'))
            if report_no:
                stat['report_no'] += 1

            grp = item.get('DB_GRP_NM') or '(없음)'
            g = groups.setdefault(grp, {'n': 0, 'report_no': 0})
            g['n'] += 1
            if report_no:
                g['report_no'] += 1

            if dry:
                continue

            fields = dict(values)
            fields.update({
                'food_nm_kr': (item.get('FOOD_NM_KR') or '')[:300],
                'db_grp_nm': grp[:30],
                'db_class_nm': (item.get('DB_CLASS_NM') or '')[:30],
                'food_cat1_nm': (item.get('FOOD_CAT1_NM') or '')[:100],
                'item_report_no': report_no,
                'maker_nm': (item.get('MAKER_NM') or '')[:200] or None,
                'imp_yn': (item.get('IMP_YN') or '')[:10],
                'nation_nm': (item.get('NATION_NM') or '')[:100],
                'basis_amount': amount,
                'basis_unit': unit,
                'crt_mth_nm': (item.get('CRT_MTH_NM') or '')[:30],
                'sub_ref_name': (item.get('SUB_REF_NAME') or '')[:200],
                'research_ymd': (item.get('RESEARCH_YMD') or '')[:20],
                'update_date': (item.get('UPDATE_DATE') or '')[:20],
                'verify_status': status,
                'verify_note': (note or '')[:200],
                'raw': item,
            })

            fields['food_cd'] = food_cd
            pending.append(PublicFoodNutrition(**fields))

        if pending:
            self._flush(pending, stat)

    def _flush(self, rows, stat):
        """
        한 쪽을 한 번에 넣는다.

        행마다 update_or_create + atomic 을 돌리면 500 건에 20 초가 넘게 걸린다
        (전량이면 네 시간). 같은 food_cd 가 다시 오면 덮어쓰면 되므로
        bulk_create 의 update_conflicts 로 한 번에 보낸다.

        새로 넣은 것과 갱신한 것을 갈라 세지 못한다 — MySQL 이 그 수를 돌려주지
        않는다. 합계만 센다. 그 구분이 필요한 자리가 없다.

        unique_fields 는 넘기지 않는다. MySQL 은 ON DUPLICATE KEY UPDATE 로
        처리하므로 어느 키에서 부딪혔는지를 지정받지 않는다 — 넘기면
        NotSupportedError 로 거절한다(Postgres·SQLite 는 반대로 필요하다).
        food_cd 의 unique 제약이 그 자리를 대신한다.
        """
        fields = [f.name for f in PublicFoodNutrition._meta.fields
                  if f.name not in ('id', 'food_cd', 'fetched_at')]
        with transaction.atomic():
            PublicFoodNutrition.objects.bulk_create(
                rows,
                update_conflicts=True,
                update_fields=fields,
                batch_size=200,
            )
        stat['saved'] += len(rows)

    # ── 알리기 ──────────────────────────────────────────────────────────

    def _report(self, stat, groups, fail_samples, total_count, dry):
        w = self.stdout.write
        w('')
        w('─' * 64)
        w('받은 건수 %d%s' % (stat['fetched'],
                            (' / 전체 %s' % total_count) if total_count else ''))
        if not dry:
            w('  저장 %s 건 (새로 넣은 것과 덮어쓴 것의 합)' % f"{stat['saved']:,}")
        else:
            w('  (--dry-run: 저장하지 않았다)')

        if stat['failed_pages']:
            w(self.style.WARNING(
                '  받지 못한 쪽 %d 개: %s'
                % (len(stat['failed_pages']), stat['failed_pages'][:20])))
            w('  다시 받으려면 --from-page <쪽> --pages 1')

        w('')
        w('[기준량] 배합에 쓰려면 중량(g)이어야 한다')
        total = max(stat['fetched'], 1)
        w('  100g      %6d (%4.1f%%)' % (stat['basis_g'], stat['basis_g'] / total * 100))
        w('  100mL     %6d (%4.1f%%)  ← 비중을 모르면 중량 배합에 쓸 수 없다'
          % (stat['basis_ml'], stat['basis_ml'] / total * 100))
        w('  못 읽음    %6d (%4.1f%%)' % (stat['basis_none'], stat['basis_none'] / total * 100))

        w('')
        w('[검산] 질량 합 ≈ 기준량 · 규정 계수로 잰 열량 ≈ 표기 열량')
        w('  통과      %6d' % stat['pass'])
        w('  어긋남    %6d  ← 높으면 AMT_NUM 매핑을 의심해야 한다' % stat['fail'])
        w('  못 잼      %6d  (원본 빈 칸 · 부피 기준)' % stat['skip'])
        for name, note in fail_samples:
            w('     · %s — %s' % (name, note))

        w('')
        w('[DB그룹] 품목제조보고번호는 사 오는 원료를 이름 없이 잇는 열쇠다')
        for grp, g in sorted(groups.items(), key=lambda kv: -kv[1]['n']):
            w('  %-10s %6d건  보고번호 %6d (%5.1f%%)'
              % (grp, g['n'], g['report_no'], g['report_no'] / max(g['n'], 1) * 100))
        w('─' * 64)
