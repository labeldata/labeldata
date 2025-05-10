from django.core.management.base import BaseCommand
from v1.common.models import ApiEndpoint
from v1.common.views import call_api_endpoint
from django.test import RequestFactory
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '모든 ApiEndpoint에 대해 call_api_endpoint를 순차적으로 실행합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--id',
            type=int,
            help='특정 ApiEndpoint ID만 호출합니다.'
        )

    def handle(self, *args, **options):
        factory = RequestFactory()
        endpoint_id = options.get('id')

        if endpoint_id:
            endpoints = ApiEndpoint.objects.filter(id=endpoint_id)
        else:
            endpoints = ApiEndpoint.objects.all()

        if not endpoints.exists():
            self.stdout.write(self.style.WARNING("해당하는 API 엔드포인트가 없습니다."))
            return

        self.stdout.write(self.style.NOTICE(f"{endpoints.count()}개의 API 엔드포인트를 호출합니다."))

        for endpoint in endpoints:
            try:
                logger.info(f"[{endpoint.id}] '{endpoint.name}' API 호출 시작")
                self.stdout.write(self.style.SUCCESS(f"[{endpoint.id}] '{endpoint.name}' 호출 시작"))

                fake_request = factory.get(f"/common/api-endpoint/{endpoint.id}/call/")
                response = call_api_endpoint(fake_request, pk=endpoint.id)

                self.stdout.write(self.style.SUCCESS(
                    f"[{endpoint.id}] '{endpoint.name}' 호출 완료 (Status: {response.status_code})"
                ))
                logger.info(f"[{endpoint.id}] '{endpoint.name}' 처리 완료: {response.status_code}")
            except Exception as e:
                logger.error(f"[{endpoint.id}] '{endpoint.name}' 처리 중 오류: {e}")
                self.stdout.write(self.style.ERROR(f"[{endpoint.id}] 오류 발생: {str(e)}"))
