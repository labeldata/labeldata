"""
Management Command: sync_import_news  [비상용 유틸리티]
=====================================
로컬 PC에서 업로드한 JSON 파일을 수동으로 DB에 저장합니다.

※ 일반 운영에서는 이 명령을 직접 실행하지 않아도 됩니다.
   collect_regulatory_news 스케줄러가 new_import_data.json 파일을 자동으로 감지하여 처리합니다.

비상 시 수동 실행:
  python manage.py sync_import_news                      # JSON → DB 저장
  python manage.py sync_import_news --parse-ai           # DB 저장 + AI 파싱/매칭까지
  python manage.py sync_import_news --file /tmp/x.json   # 파일 경로 직접 지정
  python manage.py sync_import_news --keep-file          # 처리 후 파일 유지
"""
import json
import logging
import os

from django.core.management.base import BaseCommand

from v1.regulatory.models import RegulatoryNews

logger = logging.getLogger(__name__)

# 로컬 스크립트에서 업로드하는 파일 경로 (config.ini dest_path 와 동일)
DEFAULT_FILE_PATH = '/home/labeldata/mysite/new_import_data.json'

# 행정처분 external_id 접두사 — AI 파싱 불필요 (국내 행정처분만, 수입행정처분 I0482는 수집 안 함)
_ADMIN_DISPOSAL_PREFIXES = ('I0470-', 'I0480-')


class Command(BaseCommand):
    help = '로컬 PC에서 업로드한 수입식품 JSON 데이터를 DB에 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=DEFAULT_FILE_PATH,
            help=f'읽어들일 JSON 파일 경로 (기본: {DEFAULT_FILE_PATH})',
        )
        parser.add_argument(
            '--parse-ai',
            action='store_true',
            dest='parse_ai',
            help='DB 저장 후 신규 항목 AI 파싱 및 매칭까지 실행',
        )
        parser.add_argument(
            '--keep-file',
            action='store_true',
            dest='keep_file',
            help='처리 완료 후 JSON 파일을 삭제하지 않음 (기본: 삭제)',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        run_ai    = options['parse_ai']
        keep_file = options['keep_file']

        # ── JSON 파일 읽기 ─────────────────────────────────────────────────────
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(
                f'JSON 파일이 없습니다: {file_path}\n'
                f'로컬 PC에서 import_scraper.py 를 먼저 실행해 주세요.'
            ))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            items = json.load(f)

        if not items:
            self.stdout.write(self.style.WARNING('JSON 파일이 비어 있습니다.'))
            return

        self.stdout.write(self.style.NOTICE(f'JSON 파일 로드: {len(items)}건 ({file_path})'))

        # ── DB 저장 ────────────────────────────────────────────────────────────
        created_news = []
        skipped = 0
        errors   = 0

        for item in items:
            try:
                external_id = item.get('external_id', '')
                source      = item.get('source', RegulatoryNews.SOURCE_IMPORT)
                api_source  = item.get('api_source', '')

                if not external_id:
                    logger.warning(f'[sync] external_id 없음 → 건너뜀: {item}')
                    errors += 1
                    continue

                # 행정처분은 AI 파싱 불필요 (업체 단위 처분)
                is_admin = any(external_id.startswith(p) for p in _ADMIN_DISPOSAL_PREFIXES)

                # event_date: JSON 문자열 → date 객체
                event_date = None
                raw_date = item.get('event_date')
                if raw_date:
                    from datetime import date as date_type
                    try:
                        from datetime import datetime
                        event_date = datetime.strptime(raw_date[:10], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        event_date = None

                news, created = RegulatoryNews.objects.get_or_create(
                    source=source,
                    external_id=external_id,
                    defaults={
                        'api_source':       api_source,
                        'product_name':     item.get('product_name', ''),
                        'company_name':     item.get('company_name', ''),
                        'violation_reason': item.get('violation_reason', ''),
                        'raw_detail_text':  item.get('raw_detail_text', ''),
                        'event_date':       event_date,
                        # 행정처분은 ai_parsed=True 로 초기화 (파싱 생략)
                        'ai_parsed':        is_admin,
                    },
                )

                if created:
                    # api_source 가 비어있는 기존 레코드에도 채워줌
                    if not news.api_source and api_source:
                        news.api_source = api_source
                        news.save(update_fields=['api_source'])
                    created_news.append(news)
                    self.stdout.write(f'  + 신규: [{api_source}] {news.product_name[:40]}')
                else:
                    skipped += 1

            except Exception as exc:
                logger.error(f'[sync] {item.get("external_id")} 저장 오류: {exc}')
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n저장 완료: 신규 {len(created_news)}건 / 중복(건너뜀) {skipped}건 / 오류 {errors}건'
        ))

        # ── JSON 파일 삭제 ─────────────────────────────────────────────────────
        if not keep_file:
            try:
                os.remove(file_path)
                self.stdout.write(f'JSON 파일 삭제됨: {file_path}')
            except Exception as exc:
                logger.warning(f'[sync] 파일 삭제 실패: {exc}')

        # ── AI 파싱 + 매칭 ─────────────────────────────────────────────────────
        if not run_ai:
            if created_news:
                self.stdout.write(self.style.NOTICE(
                    '\n💡 AI 파싱/매칭을 실행하려면:\n'
                    '   python manage.py collect_regulatory_news --parse-only\n'
                    '   또는 --parse-ai 옵션으로 이 명령을 다시 실행하세요.'
                ))
            return

        if not created_news:
            self.stdout.write('신규 항목 없음 → AI 파싱 생략')
            return

        self.stdout.write(self.style.NOTICE(f'\nAI 파싱 시작 ({len(created_news)}건)...'))
        self._run_ai_pipeline(created_news)

    def _run_ai_pipeline(self, news_list: list):
        """신규 저장 항목에 대해 AI 파싱 → 매칭 실행"""
        import time
        from v1.regulatory.services.ai_parser import extract_keywords
        from v1.regulatory.services.matcher import run_matching_for_all_users

        # 행정처분 제외 (이미 ai_parsed=True)
        parse_targets = [
            n for n in news_list
            if not any(n.external_id.startswith(p) for p in _ADMIN_DISPOSAL_PREFIXES)
        ]

        parsed_count  = 0
        matched_total = 0

        for news in parse_targets:
            try:
                detail = news.raw_detail_text or news.violation_reason or news.product_name
                result = extract_keywords(detail, news.product_name)

                news.ai_keywords    = result['keywords']
                news.ai_issues      = result.get('issues', [])
                news.ai_substances  = result.get('substances', [])
                news.ai_summary     = result['summary']
                news.risk_level     = result['risk_level']
                news.violation_type = result.get('violation_type', 'other')
                news.ai_parsed      = True
                news.save(update_fields=[
                    'ai_keywords', 'ai_issues', 'ai_substances',
                    'ai_summary', 'risk_level', 'violation_type', 'ai_parsed',
                ])

                parsed_count += 1
                self.stdout.write(
                    f'  AI [{parsed_count}/{len(parse_targets)}] '
                    f'{news.product_name[:30]} → 키워드={result["keywords"][:3]}'
                )
                time.sleep(1.0)

            except Exception as exc:
                logger.error(f'[AI 파싱] {news.external_id} 오류: {exc}')

        self.stdout.write(self.style.SUCCESS(f'AI 파싱 완료: {parsed_count}건'))

        # 매칭
        self.stdout.write('매칭 시작...')
        ai_done = [n for n in parse_targets if n.ai_parsed]
        for news in ai_done:
            try:
                count = run_matching_for_all_users(news)
                if count > 0:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️  [{news.product_name[:30]}] → {count}개 매칭'
                    ))
                matched_total += count
            except Exception as exc:
                logger.error(f'[매칭] {news.external_id} 오류: {exc}')

        self.stdout.write(self.style.SUCCESS(f'매칭 완료: {matched_total}건'))
