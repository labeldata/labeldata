import os
import requests
from .models import FoodType

def get_food_types():
    try:
        # 데이터베이스에서 식품유형 가져오기
        return [food_type.name for food_type in FoodType.objects.all()]
    except Exception as e:
        print(f"Error fetching food types: {e}")
        return []

def update_food_types_from_api():
    # API URL을 환경 변수에서 가져오기
    API_KEY = os.getenv('FOOD_SAFETY_API_KEY', '5877fad32a304ba69432')  # 환경 변수로 변경 가능
    API_URL = f"https://openapi.foodsafetykorea.go.kr/api/{API_KEY}/C002/json/1/1000"
    
    try:
        response = requests.get(API_URL)
        response.raise_for_status()  # HTTP 에러 처리

        if response.status_code == 200:
            data = response.json()
            food_types = [item['PRDLST_NM'] for item in data['C002']['row']]
            for food_type in food_types:
                FoodType.objects.get_or_create(name=food_type)
            return True
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
    except (KeyError, requests.exceptions.JSONDecodeError) as e:
        print(f"Error processing API data: {e}")

    return False
