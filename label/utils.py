# label/utils.py

import requests

#API 호출
def get_food_types():
    API_URL = "https://openapi.foodsafetykorea.go.kr/api/{5877fad32a304ba69432}/C002/json/1/1000"
    response = requests.get(API_URL)
    if response.status_code == 200:
        try:
            data = response.json()
            food_types = [item['PRDLST_NM'] for item in data['C002']['row']]
            return food_types
        except requests.exceptions.JSONDecodeError:
            return None
    else:
        return None