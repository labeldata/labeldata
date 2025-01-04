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
    API_URL = "https://openapi.foodsafetykorea.go.kr/api/5877fad32a304ba69432/C002/json/1/1000"
    response = requests.get(API_URL)
    if response.status_code == 200:
        try:
            data = response.json()
            food_types = [item['PRDLST_NM'] for item in data['C002']['row']]
            for food_type in food_types:
                FoodType.objects.get_or_create(name=food_type)
            return True
        except (KeyError, requests.exceptions.JSONDecodeError):
            return False
    return False
