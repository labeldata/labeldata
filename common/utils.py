import os
import logging
import requests
from django.core.cache import cache
from label.models import FoodItem

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수로부터 API 정보 가져오기
API_URL = os.getenv("API_URL", "https://api.publicdata.go.kr/food-item")
API_KEY = os.getenv("PUBLIC_API_KEY", "default-api-key")

def fetch_food_data_from_api(query_params):
    """
    공공데이터 API에서 품목 제조보고 정보를 가져옴
    :param query_params: dict, API 요청 파라미터
    :return: dict, API 응답 데이터
    """
    # 캐싱 키 생성 (파라미터를 정렬하여 일관성 유지)
    cache_key = f"food_data_{'_'.join(f'{k}:{v}' for k, v in sorted(query_params.items()))}"
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.info("캐시에서 데이터 반환")
        return cached_data

    try:
        logger.info(f"API 요청: {API_URL}, 파라미터: {query_params}")
        response = requests.get(API_URL, params={"key": API_KEY, **query_params}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 캐싱
        cache.set(cache_key, data, timeout=60 * 60)  # 1시간 캐싱
        logger.info("API 데이터 캐싱 완료")
        return data
    except requests.RequestException as e:
        logger.error(f"API 호출 실패: {e}")
        return {}
    except ValueError as e:
        logger.error(f"API 응답 데이터 처리 실패: {e}")
        return {}

def save_food_items(items):
    """
    API에서 가져온 데이터를 데이터베이스에 저장 또는 업데이트
    :param items: list, API로부터 가져온 데이터
    """
    saved_count = 0
    for item in items:
        _, created = FoodItem.objects.update_or_create(
            product_name=item.get("product_name", "Unknown"),
            defaults={
                "manufacturer_name": item.get("manufacturer_name", "Unknown"),
                "category": item.get("category", "Unknown"),
                "report_date": item.get("report_date"),
                "additional_details": item.get("additional_details", {}),
            },
        )
        if created:
            saved_count += 1
    logger.info(f"{saved_count}개의 FoodItem이 새로 생성되었습니다.")
