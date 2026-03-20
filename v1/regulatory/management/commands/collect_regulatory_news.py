"""
Management Command: collect_regulatory_news
PythonAnywhere 스케줄러에 등록하여 매일 오전 실행

━━━ 수집 대상 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[서버 API] 식품안전나라 OpenAPI — 해외 IP 무관하게 직접 수집
  I2620  검사부적합(국내)
  I2640  검사부적합(농산물)
  I0490  회수·판매중지(국내)
  I0470  행정처분
  I0480  행정처분(제조가공업)
  I0482  행정처분(수입영업자)   ← 수입 행정처분도 API로 함께 수집

[로컬→서버 JSON] impfood.mfds.go.kr AJAX — 해외 IP 차단 대상
  로컬 PC에서 local_uploader/import_scraper.py 실행 후 서버에 JSON 업로드
  → 이 명령 실행 시 new_import_data.json 파일이 있으면 자동으로 DB에 반영
  수입식품정보마루 수입 회수·판매중지   (CFCFF01F01)
  수입식품정보마루 수입식품 부적합      (CFCEE01F01)

━━━ 사용법 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python manage.py collect_regulatory_news              # 전체 실행 (스케줄러 기본)
  python manage.py collect_regulatory_news --parse-only # AI 미분석 항목만 파싱
  python manage.py collect_regulatory_news --match-only # 매칭만 재실행
  python manage.py collect_regulatory_news --limit 5   # 테스트: 서비스당 최대 5건

━━━ 매일 작업 흐름 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [로컬 PC, 필요 시] python local_uploader/import_scraper.py
      → 수입 회수·부적합 수집 후 new_import_data.json 을 PA 서버에 업로드
  [PA 스케줄러, 매일] python manage.py collect_regulatory_news
      → JSON 파일 자동 감지·DB 반영 → API 수집 → AI 파싱 → 매칭
"""
import json
import logging
import os
import time
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from v1.regulatory.models import RegulatoryNews
from v1.regulatory.services.collector import (
    collect_domestic_news, collect_import_news,
    collect_import_insp_news, collect_import_admin_news,
)
from v1.regulatory.services.ai_parser import extract_keywords
from v1.regulatory.services.matcher import run_matching_for_all_users

logger = logging.getLogger(__name__)

# 로컬 PC에서 업로드하는 수입 AJAX 데이터 파일 경로
IMPORT_JSON_PATH = '/home/labeldata/mysite/new_import_data.json'

# 행정처분 external_id 접두사 — 업체 단위 처분이므로 AI 원료 파싱 불필요
_ADMIN_DISPOSAL_PREFIXES = ('I0470-', 'I0480-', 'I0482-')


class Command(BaseCommand):
    help = '부적합 정보를 수집하고 내 원료/제품과 매칭합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--parse-only',
            action='store_true',
            dest='parse_only',
            help='수집 없이 AI 미분석 항목만 파싱 후 매칭',
        )
        parser.add_argument(
            '--match-only',
            action='store_true',
            dest='match_only',
            help='수집/파싱 없이 전체 항목에 대해 매칭만 재실행',
        )
        parser.add_argument(
            '--ai-delay',
            type=float,
            default=1.0,
            dest='ai_delay',
            help='OpenAI 호출 간 딜레이(초, 기본: 1.0)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            dest='limit',
            help='테스트용 수집 제한: 서비스당 최대 건수 (0=제한없음)',
        )

    def handle(self, *args, **options):
        parse_only = options['parse_only']
        match_only = options['match_only']
        ai_delay   = options['ai_delay']
        limit      = options['limit']

        self.stdout.write(self.style.NOTICE(
            f'[{timezone.now():%Y-%m-%d %H:%M}] 규제 모니터링 수집 시작 '
            f'(parse_only={parse_only}, match_only={match_only}, limit={limit or "ALL"})'
        ))

        # ── 1단계: 수집 ─────────────────────────────────────────────────────
        new_items = []
        if not parse_only and not match_only:
            new_items = self._collect(limit)

        # ── 2단계: AI 파싱 (신규 + 기존 미분석 항목 포함) ──────────────────
        newly_parsed = []
        if not match_only:
            unparsed_qs = RegulatoryNews.objects.filter(ai_parsed=False)
            newly_parsed = self._parse_ai(unparsed_qs, ai_delay)

        # ── 3단계: 매칭 ─────────────────────────────────────────────────────
        # --match-only: 전체 재매칭 / 일반 실행: 이번에 파싱된 것만 매칭
        if match_only:
            target_qs = RegulatoryNews.objects.filter(ai_parsed=True)
        else:
            if not newly_parsed:
                self.stdout.write('  → 매칭 대상 없음 (신규 파싱 항목 없음)')
                total_matches = 0
                self.stdout.write(self.style.SUCCESS(
                    f'완료: 신규 수집 {len(new_items)}건 / 매칭 {total_matches}건'
                ))
                return
            target_qs = RegulatoryNews.objects.filter(pk__in=[n.pk for n in newly_parsed])
        total_matches = self._run_matching(target_qs)

        self.stdout.write(self.style.SUCCESS(
            f'완료: 신규 수집 {len(new_items)}건 / 매칭 {total_matches}건'
        ))

    # ─────────────────────────────────────────────────────────────────────────

    def _collect(self, limit: int = 0) -> list:
        """수집 단계: JSON 파일(수입 AJAX) + OpenAPI(국내·수입행정처분)"""
        raw_items = []

        # ── 수입 AJAX 데이터 (로컬 PC 업로드 JSON) ───────────────────────────
        json_items = self._load_import_json()
        raw_items.extend(json_items)

        # ── 국내 부적합 OpenAPI ───────────────────────────────────────────────
        self.stdout.write('  → 국내 부적합 수집 중 (I2620/I2640/I0490/I0470/I0480)...')
        domestic_items = collect_domestic_news(max_rows=limit)
        raw_items.extend(domestic_items)
        self.stdout.write(self.style.SUCCESS(f'     국내 신규: {len(domestic_items)}건'))

        # ── 수입 행정처분 OpenAPI (I0482) ────────────────────────────────────
        self.stdout.write('  → 수입판매업 행정처분 수집 중 (I0482)...')
        imp_admin_items = collect_import_admin_news(max_rows=limit)
        raw_items.extend(imp_admin_items)
        self.stdout.write(self.style.SUCCESS(f'     수입행정처분 신규: {len(imp_admin_items)}건'))

        # ── DB 저장 ───────────────────────────────────────────────────────────
        saved = []
        for item in raw_items:
            try:
                ext_id     = item['external_id']
                api_source = item.get('api_source', '')
                is_admin   = any(ext_id.startswith(p) for p in _ADMIN_DISPOSAL_PREFIXES)

                news, created = RegulatoryNews.objects.get_or_create(
                    external_id=ext_id,
                    source=item['source'],
                    defaults={
                        'api_source':       api_source,
                        'product_name':     item.get('product_name', ''),
                        'company_name':     item.get('company_name', ''),
                        'violation_reason': item.get('violation_reason', ''),
                        'raw_detail_text':  item.get('raw_detail_text', ''),
                        'event_date':       item.get('event_date'),
                        'ai_parsed':        is_admin,
                    },
                )
                if not created and not news.api_source and api_source:
                    news.api_source = api_source
                    news.save(update_fields=['api_source'])
                if created:
                    saved.append(news)
            except Exception as exc:
                logger.error(f'[수집 저장] {item.get("external_id")} 오류: {exc}')

        return saved

    def _load_import_json(self) -> list:
        """
        로컬 PC 업로드 JSON 파일 감지 및 로드.
        파일이 없으면 빈 리스트 반환. 처리 후 파일 삭제.
        """
        if not os.path.exists(IMPORT_JSON_PATH):
            self.stdout.write('  → 수입 JSON 파일 없음 (로컬 업로드 미실행)')
            return []

        try:
            with open(IMPORT_JSON_PATH, 'r', encoding='utf-8') as f:
                items = json.load(f)
        except Exception as exc:
            logger.error(f'[JSON 로드] 파일 읽기 오류: {exc}')
            return []

        if not items:
            self.stdout.write('  → 수입 JSON 파일이 비어 있음')
            os.remove(IMPORT_JSON_PATH)
            return []

        self.stdout.write(self.style.SUCCESS(
            f'  → 수입 JSON 파일 감지: {len(items)}건 로드 ({IMPORT_JSON_PATH})'
        ))

        # event_date 문자열 → date 객체 변환
        converted = []
        for item in items:
            raw_date = item.get('event_date')
            if raw_date:
                try:
                    item['event_date'] = datetime.strptime(raw_date[:10], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    item['event_date'] = None
            converted.append(item)

        # 처리 완료 후 파일 삭제 (다음 실행에서 중복 처리 방지)
        try:
            os.remove(IMPORT_JSON_PATH)
            self.stdout.write(f'     JSON 파일 삭제 완료')
        except Exception as exc:
            logger.warning(f'[JSON 로드] 파일 삭제 실패: {exc}')

        return converted

    # 행정처분 서비스는 업체 대상이므로 AI 식품원료 파싱 불필요
    def _parse_ai(self, qs, ai_delay: float) -> list:
        """AI 파싱 단계 — 파싱 완료된 RegulatoryNews 목록 반환 (매칭 대상으로 사용)"""
        items = list(qs)
        if not items:
            self.stdout.write('  → AI 파싱 대상 없음')
            return []

        admin_items = [n for n in items if any(n.external_id.startswith(p) for p in _ADMIN_DISPOSAL_PREFIXES)]
        parse_items = [n for n in items if not any(n.external_id.startswith(p) for p in _ADMIN_DISPOSAL_PREFIXES)]

        if admin_items:
            RegulatoryNews.objects.filter(pk__in=[n.pk for n in admin_items]).update(
                ai_keywords=[], ai_issues=[], ai_substances=[],
                ai_summary='', violation_type='admin', ai_parsed=True
            )
            self.stdout.write(f'  → 행정처분 {len(admin_items)}건 파싱 생략 (업체 단위 처분)')

        if not parse_items:
            self.stdout.write('  → AI 파싱 대상 없음')
            return admin_items  # 행정처분도 매칭 대상에 포함

        self.stdout.write(f'  → AI 파싱 중 ({len(parse_items)}건)...')
        parsed_ok = []

        for news in parse_items:
            try:
                detail = news.raw_detail_text or news.violation_reason or news.product_name
                result = extract_keywords(detail, news.product_name)

                news.ai_keywords     = result['keywords']
                news.ai_issues       = result.get('issues', [])
                news.ai_substances   = result.get('substances', [])
                news.ai_summary      = result['summary']
                news.risk_level      = result['risk_level']
                news.violation_type  = result.get('violation_type', 'other')
                news.ai_parsed       = True
                news.save(update_fields=[
                    'ai_keywords', 'ai_issues', 'ai_substances',
                    'ai_summary', 'risk_level', 'violation_type', 'ai_parsed',
                ])

                parsed_ok.append(news)
                self.stdout.write(
                    f'     [{len(parsed_ok)}/{len(parse_items)}] {news.product_name[:30]} '
                    f'→ 키워드={result["keywords"][:3]}'
                )
                time.sleep(ai_delay)

            except Exception as exc:
                logger.error(f'[AI 파싱] {news.external_id} 오류: {exc}')

        self.stdout.write(self.style.SUCCESS(f'     AI 파싱 완료: {len(parsed_ok)}건'))
        return admin_items + parsed_ok  # 행정처분 포함하여 매칭 대상 반환

    def _run_matching(self, qs) -> int:
        """매칭 단계"""
        items = list(qs)
        if not items:
            self.stdout.write('  → 매칭 대상 없음')
            return 0

        total_items = len(items)
        self.stdout.write(f'  → 매칭 중 ({total_items}건)...')
        total = 0
        PROGRESS_INTERVAL = 100  # N건마다 진행률 출력

        for idx, news in enumerate(items, 1):
            try:
                count = run_matching_for_all_users(news)
                if count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'     ⚠️  [{idx}/{total_items}] [{news.product_name[:30]}] '
                            f'→ {count}개 사용자-제품 매칭됨'
                        )
                    )
                total += count
            except Exception as exc:
                logger.error(f'[매칭] {news.external_id} 오류: {exc}')

            if idx % PROGRESS_INTERVAL == 0:
                self.stdout.write(f'     진행: {idx}/{total_items}건 처리 중...')

        self.stdout.write(self.style.SUCCESS(f'     매칭 완료: {total}건'))
        return total
