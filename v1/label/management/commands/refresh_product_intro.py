"""
제품 조회 첫 화면(검색 전 안내)의 통계 스냅샷을 새로 만든다.

이 화면의 숫자는 COUNT(*) 2개 + GROUP BY 2개로 만들어져 행 수에 선형으로 비싸다.
요청 경로에서 계산하면 그날 처음 메뉴를 누른 사람이 그 비용을 전부 부담하므로,
품목제조보고 수집이 끝난 뒤 이 명령으로 미리 계산해 JSON 으로 찍어둔다.

    python manage.py refresh_product_intro
    python manage.py refresh_product_intro --dry-run   # 계산만 하고 기록하지 않음

매일 아침 수집 배치 뒤에 이어서 돌리면 된다
(PYTHONANYWHERE_SCHEDULED_TASK_SETUP.md 참고).
"""
import time

from django.core.management.base import BaseCommand

from v1.label.services import product_search


class Command(BaseCommand):
    help = '제품 조회 첫 화면 통계 스냅샷 갱신 (매일 수집 배치 뒤에 실행)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='집계 결과만 출력하고 파일에 기록하지 않음')

    def handle(self, *args, **options):
        started = time.time()
        data = product_search.build_intro_data()
        elapsed = time.time() - started

        self.stdout.write(
            f"국내 {data['domestic_total']:,}건 / 수입 {data['imported_total']:,}건 "
            f"(집계 {elapsed:.1f}초)"
        )
        self.stdout.write(f"  국내 상위 유형: {', '.join(data['domestic_types'][:5])}")
        self.stdout.write(f"  수입 상위 유형: {', '.join(data['imported_types'][:5])}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run: 기록하지 않았습니다.'))
            return

        path = product_search.save_intro_snapshot(data)
        self.stdout.write(self.style.SUCCESS(f'스냅샷 기록 완료: {path}'))

        # 검색용 FULLTEXT 인덱스 확인 캐시도 같이 데워둔다.
        # 이 조회 역시 캐시가 비어 있으면 그날 첫 검색자가 부담한다.
        try:
            tables = product_search.warm_index_cache()
            self.stdout.write(f"FULLTEXT 인덱스 캐시 워밍: {', '.join(sorted(tables)) or '없음(LIKE 폴백)'}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'인덱스 캐시 워밍 실패(무시 가능): {e}'))
