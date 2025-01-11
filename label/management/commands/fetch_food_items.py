import requests
from django.core.management.base import BaseCommand
from label.models import FoodItem  # 필요한 모델 가져오기
from common.models import ApiKey
from django.apps import apps  # get_model 사용
import xmltodict
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Fetch data from multiple 식약처 APIs and save to the database"

    def handle(self, *args, **kwargs):
        # API 키 가져오기
        api_key = ApiKey.objects.first()
        if not api_key:
            self.stdout.write(self.style.ERROR("API 키가 등록되지 않았습니다."))
            return

        # FoodItem 모델 가져오기 (지연 로딩)
        FoodItem = apps.get_model('label', 'FoodItem')

        # API URL 정의
        urls = [
            f"http://openapi.foodsafetykorea.go.kr/api/{api_key.key}/I1250/xml/1/5",
            f"http://openapi.foodsafetykorea.go.kr/api/{api_key.key}/C006/xml/1/5"
        ]

        # 데이터 가져오기
        for url in urls:
            try:
                logger.info(f"Fetching data from: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Content-Type 확인
                content_type = response.headers.get("Content-Type", "")
                if "application/xml" not in content_type:
                    self.stdout.write(self.style.WARNING(f"Unexpected Content-Type: {content_type}"))
                    logger.error(f"Unexpected Content-Type: {content_type}")
                    continue

                # XML 데이터를 JSON-like 구조로 변환
                data = xmltodict.parse(response.text)
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if not isinstance(items, list):
                    items = [items]  # 단일 항목 처리

                # DB 저장
                saved_count = 0
                for item in items:
                    _, created = FoodItem.objects.update_or_create(
                        product_name=item.get("PRDUCT", "Unknown"),
                        defaults={
                            "manufacturer": item.get("MANUFACTURER", "Unknown"),
                            "report_date": item.get("REPORT_DATE", None),
                            "category": item.get("CATEGORY", "Unknown"),
                            "details": item.get("DETAILS", ""),
                        },
                    )
                    if created:
                        saved_count += 1

                self.stdout.write(self.style.SUCCESS(f"{url}에서 {saved_count}개의 데이터 저장 성공"))
            except requests.exceptions.Timeout:
                self.stdout.write(self.style.ERROR(f"API 호출 시간 초과: {url}"))
                logger.error(f"Timeout while fetching: {url}")
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"API 호출 실패: {e}"))
                logger.error(f"Request error: {e}")
            except xmltodict.expat.ExpatError as e:
                self.stdout.write(self.style.ERROR(f"XML 파싱 오류: {e}"))
                logger.error(f"XML parsing error: {e}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"데이터 처리 오류: {e}"))
                logger.error(f"Unexpected error: {e}")

        self.stdout.write(self.style.SUCCESS("모든 데이터가 성공적으로 저장되었습니다."))
