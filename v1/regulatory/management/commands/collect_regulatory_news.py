"""
Management Command: collect_regulatory_news
PythonAnywhere 스케줄러에 등록하여 매일 오전 실행

사용법:
  python manage.py collect_regulatory_news           # 전체 실행
  python manage.py collect_regulatory_news --source domestic   # 국내만
  python manage.py collect_regulatory_news --source import     # 수입만
  python manage.py collect_regulatory_news --parse-only        # 이미 수집된 것 중 AI 미분석 항목만 AI 파싱
  python manage.py collect_regulatory_news --match-only        # AI 분석 완료 건에 대해 매칭만 재실행
"""
import logging
import time

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


class Command(BaseCommand):
    help = '부적합 정보를 수집하고 내 원료/제품과 매칭합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            choices=['domestic', 'import', 'imp_insp', 'all'],
            default='all',
            help='수집 대상 (domestic/import/imp_insp/all, 기본: all)',
        )
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
            help='테스트용 수집 제한: 국내=서비스당 최대 건수, 수입=최대 페이지수 (0=제한없음)',
        )
    def handle(self, *args, **options):
        source     = options['source']
        parse_only = options['parse_only']
        match_only = options['match_only']
        ai_delay   = options['ai_delay']
        limit      = options['limit']

        self.stdout.write(self.style.NOTICE(
            f'[{timezone.now():%Y-%m-%d %H:%M}] 규제 모니터링 수집 시작 '
            f'(source={source}, parse_only={parse_only}, match_only={match_only}, limit={limit or "ALL"})'
        ))

        # ── 1단계: 수집 ─────────────────────────────────────────────────────
        new_items = []
        if not parse_only and not match_only:
            new_items = self._collect(source, limit)

        # ── 2단계: AI 파싱 (신규 + 기존 미분석 항목 포함) ──────────────────
        if not match_only:
            unparsed_qs = RegulatoryNews.objects.filter(ai_parsed=False)
            self._parse_ai(unparsed_qs, ai_delay)

        # ── 3단계: 매칭 ─────────────────────────────────────────────────────
        if match_only:
            target_qs = RegulatoryNews.objects.filter(ai_parsed=True)
        else:
            # 방금 파싱한 것들
            target_qs = RegulatoryNews.objects.filter(ai_parsed=True)

        total_matches = self._run_matching(target_qs)

        self.stdout.write(self.style.SUCCESS(
            f'완료: 신규 수집 {len(new_items)}건 / 매칭 {total_matches}건'
        ))

    # ─────────────────────────────────────────────────────────────────────────

    def _collect(self, source: str, limit: int = 0) -> list:
        """수집 단계"""
        raw_items = []

        if source in ('domestic', 'all'):
            self.stdout.write('  → 국내 부적합 수집 중 (I2620/I2640/I0490/I0470/I0480)...')
            domestic_items = collect_domestic_news(max_rows=limit)
            raw_items.extend(domestic_items)
            self.stdout.write(self.style.SUCCESS(f'     국내 신규: {len(domestic_items)}건'))

        if source in ('import', 'all'):
            self.stdout.write('  → 수입 회수·판매중지 수집 중 (impfood.mfds.go.kr/CFCFF01F01)...')
            import_items = collect_import_news(max_pages=limit)
            raw_items.extend(import_items)
            self.stdout.write(self.style.SUCCESS(f'     수입 회수 신규: {len(import_items)}건'))

            self.stdout.write('  → 수입판매업 행정처분 수집 중 (I0482)...')
            imp_admin_items = collect_import_admin_news(max_rows=limit)
            raw_items.extend(imp_admin_items)
            self.stdout.write(self.style.SUCCESS(f'     수입행정처분 신규: {len(imp_admin_items)}건'))

        if source in ('imp_insp', 'all'):
            self.stdout.write('  → 수입식품부적합 수집 중 (impfood.mfds.go.kr/CFCEE01F01)...')
            imp_insp_items = collect_import_insp_news(max_pages=limit)
            raw_items.extend(imp_insp_items)
            self.stdout.write(self.style.SUCCESS(f'     수입부적합 신규: {len(imp_insp_items)}건'))

        # DB 저장
        saved = []
        for item in raw_items:
            try:
                ext_id = item['external_id']
                api_source = item.get('api_source', '')
                # 행정처분(I0470/I0480)은 업체 단위 처분 → AI 원료 파싱 불필요
                is_admin = ext_id.startswith('I0470-') or ext_id.startswith('I0480-') or ext_id.startswith('I0482-')
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
                # 기존 레코드에 api_source가 없으면 채움
                if not created and not news.api_source and api_source:
                    news.api_source = api_source
                    news.save(update_fields=['api_source'])
                if created:
                    saved.append(news)
            except Exception as exc:
                logger.error(f'[수집 저장] {item.get("external_id")} 오류: {exc}')

        return saved

    # 행정처분 서비스는 업체 대상이므로 AI 식품원료 파싱 불필요 (국내 + 수입판매업)
    _ADMIN_DISPOSAL_PREFIXES = ('I0470-', 'I0480-', 'I0482-')

    def _parse_ai(self, qs, ai_delay: float):
        """AI 파싱 단계"""
        items = list(qs)
        if not items:
            self.stdout.write('  → AI 파싱 대상 없음')
            return

        # 행정처분 레코드는 ai_parsed=True, 키워드 빈값으로 즉시 처리
        admin_items = [n for n in items if any(n.external_id.startswith(p) for p in self._ADMIN_DISPOSAL_PREFIXES)]
        parse_items = [n for n in items if not any(n.external_id.startswith(p) for p in self._ADMIN_DISPOSAL_PREFIXES)]

        if admin_items:
            RegulatoryNews.objects.filter(pk__in=[n.pk for n in admin_items]).update(
                ai_keywords=[], ai_issues=[], ai_substances=[],
                ai_summary='', violation_type='admin', ai_parsed=True
            )
            self.stdout.write(f'  → 행정처분 {len(admin_items)}건 파싱 생략 (업체 단위 처분)')

        if not parse_items:
            self.stdout.write('  → AI 파싱 대상 없음')
            return

        self.stdout.write(f'  → AI 파싱 중 ({len(parse_items)}건)...')
        parsed_count = 0

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

                parsed_count += 1
                self.stdout.write(
                    f'     [{parsed_count}/{len(parse_items)}] {news.product_name[:30]} '
                    f'→ 키워드={result["keywords"][:3]}'
                )
                time.sleep(ai_delay)

            except Exception as exc:
                logger.error(f'[AI 파싱] {news.external_id} 오류: {exc}')

        self.stdout.write(self.style.SUCCESS(f'     AI 파싱 완료: {parsed_count}건'))

    def _run_matching(self, qs) -> int:
        """매칭 단계"""
        items = list(qs)
        if not items:
            self.stdout.write('  → 매칭 대상 없음')
            return 0

        self.stdout.write(f'  → 매칭 중 ({len(items)}건)...')
        total = 0

        for news in items:
            try:
                count = run_matching_for_all_users(news)
                if count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'     ⚠️  [{news.product_name[:30]}] '
                            f'→ {count}개 사용자-제품 매칭됨'
                        )
                    )
                total += count
            except Exception as exc:
                logger.error(f'[매칭] {news.external_id} 오류: {exc}')

        self.stdout.write(self.style.SUCCESS(f'     매칭 완료: {total}건'))
        return total
