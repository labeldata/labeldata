import os
import requests
import re
from django.core.cache import cache
from django.db.models import Q


# ================== 비즈니스 로직 함수들 ==================
# constants.py에서 이동된 함수들

def recommend_recycling_mark_by_material(material_text):
    """
    포장재질 텍스트로 추천 분리배출마크 구하기
    """
    if not material_text:
        return None
    text = material_text.lower().strip()

    # 우선순위 키워드 기반 추천 로직
    if 'pet' in text or '페트' in text:
        if '무색' in text:
            return '무색페트'
        elif '유색' in text:
            return '유색페트'
        return '플라스틱(PET)'

    if 'hdpe' in text or '고밀도' in text:
        return '플라스틱(HDPE)'
    if 'ldpe' in text or '저밀도' in text:
        return '플라스틱(LDPE)'
    if '폴리에틸렌' in text or 'pe' in text:
        return '플라스틱(HDPE)'

    if 'pp' in text or '폴리프로필렌' in text:
        return '플라스틱(PP)'
    if 'ps' in text or '폴리스티렌' in text:
        return '플라스틱(PS)'
    if '철' in text:
        return '캔류(철)'
    if '알미늄' in text or '알루미늄' in text:
        return '캔류(알미늄)'
    if '종이' in text and '팩' not in text:
        return '종이'
    if '유리' in text:
        return '유리'
    if '팩' in text and '멸균' in text:
        return '멸균팩'
    if '팩' in text:
        return '일반팩'
    if '복합재질' in text or '도포' in text or '첩합' in text or '코팅' in text:
        return '복합재질'

    if '비닐' in text:
        if 'pet' in text:
            return '비닐(PET)'
        if 'hdpe' in text:
            return '비닐(HDPE)'
        if 'ldpe' in text:
            return '비닐(LDPE)'
        if 'pp' in text:
            return '비닐(PP)'
        if 'ps' in text:
            return '비닐(PS)'
        return '비닐(기타)'

    if '기타' in text and '플라스틱' in text:
        return '기타플라스틱'
    if '플라스틱' in text:
        return '플라스틱(OTHER)'

    return None


def convert_country_code_to_korean(text, country_mapping):
    """
    국가 코드를 한글명으로 변환
    """
    if not text or not country_mapping:
        return text

    return re.sub(r'\b[A-Z]{2}\b', lambda match: country_mapping.get(match.group(), match.group()), text)


def bold_country_names(text, country_list):
    """
    국가명 볼드 처리 (HTML 태그 추가)
    """
    if not text or not country_list:
        return text

    processed_text = text
    # 국가명 목록을 길이 순으로 정렬
    sorted_countries = sorted(country_list, key=len, reverse=True)

    for country in sorted_countries:
        if not country:
            continue
        escaped_country = re.escape(country)
        regex = re.compile(f'({escaped_country}(\\s*산)?)', re.IGNORECASE)
        processed_text = regex.sub(r'<strong>\1</strong>', processed_text)

    return processed_text


def check_farm_seafood_compliance(product_name, ingredient_info, farm_seafood_items):
    """
    농수산물 함량 표시 검증
    """
    errors = []
    suggestions = []

    if not product_name or not ingredient_info:
        return {'errors': errors, 'suggestions': suggestions}

    # 제품명에 포함된 농수산물명 추출 (긴 이름부터 처리)
    found_items = [item for item in farm_seafood_items if item in product_name]
    found_items.sort(key=len, reverse=True)

    if not found_items:
        return {'errors': errors, 'suggestions': suggestions}

    for item in found_items:
        # 특정성분 함량에 해당 성분명과 함량(%)이 포함되어 있는지 확인
        compliance_regex = re.compile(rf'{re.escape(item)}[^,]*\d+(\.\d+)?\s*%')
        if not compliance_regex.search(ingredient_info):
            errors.append(f"제품명에 사용된 '{item}'의 함량을 '특정성분 함량' 항목에 표시하세요 (예: {item} 100%).")

    return {'errors': errors, 'suggestions': suggestions}


# =============================================================================
# 라벨 관련 유틸리티 함수 및 상수
# =============================================================================

# 알레르기 성분 목록 (constants.js의 ALLERGEN_KEYWORDS와 일치하는 19개 항목)
ALLERGEN_LIST = [
    "알류", "우유", "메밀", "밀", "대두", "땅콩", "호두", "잣",
    "쇠고기", "돼지고기", "닭고기", "고등어", "게", "새우", "오징어",
    "조개류", "복숭아", "토마토", "아황산류"
]

# GMO 목록
GMO_LIST = ["대두", "옥수수", "면화", "카놀라", "사탕무", "알팔파"]


def get_expiry_recommendations():
    """
    ExpiryRecommendation 데이터를 캐시와 함께 가져오는 헬퍼 함수
    캐시 타임아웃: 1시간
    """
    from .models import ExpiryRecommendation  # 지연 import로 순환 참조 방지
    
    cache_key = 'expiry_recommendations_dict'
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # DB에서 데이터를 가져와서 딕셔너리 형태로 변환
    recommendations = {}
    for item in ExpiryRecommendation.objects.all():
        recommendations[item.food_type] = {
            'shelf_life': item.shelf_life,
            'unit': item.unit
        }
    
    # 1시간 동안 캐시
    cache.set(cache_key, recommendations, 3600)
    return recommendations


def get_search_conditions(request, search_fields):
    """
    Request에서 검색 조건을 추출하고 Q 객체를 생성합니다.
    
    Args:
        request: Django HttpRequest 객체
        search_fields: 검색할 필드들의 딕셔너리 {model_field: query_param}
        
    Returns:
        tuple: (search_conditions, search_values)
            - search_conditions: Django Q 객체
            - search_values: 검색값들의 딕셔너리
    """
    search_conditions = Q()
    search_values = {}
    
    for field, query_param in search_fields.items():
        value = request.GET.get(query_param, "").strip()
        if value:
            # 원료 표시명, 알레르기, GMO 검색에서 쉼표/플러스 구분 검색 지원
            if field in ["ingredient_display_name", "allergens", "gmo"]:
                # 플러스(+)로 구분하여 AND 검색
                if '+' in value:
                    # 플러스로 구분된 경우 AND 검색 (모든 조건이 만족되어야 함)
                    search_terms = [term.strip() for term in value.split('+') if term.strip()]
                    if search_terms:
                        # 각 검색어에 대해 AND 조건으로 LIKE 검색
                        field_conditions = Q()
                        for term in search_terms:
                            field_conditions &= Q(**{f"{field}__icontains": term})
                        search_conditions &= field_conditions
                # 쉼표로 구분하여 OR 검색
                elif ',' in value:
                    # 여러 검색어가 있는 경우 OR 검색
                    search_terms = [term.strip() for term in value.split(',') if term.strip()]
                    if search_terms:
                        # 각 검색어에 대해 OR 조건으로 LIKE 검색
                        field_conditions = Q()
                        for term in search_terms:
                            field_conditions |= Q(**{f"{field}__icontains": term})
                        search_conditions &= field_conditions
                else:
                    # 단일 검색어인 경우 기존 LIKE 검색
                    search_conditions &= Q(**{f"{field}__icontains": value})
            else:
                # 다른 필드는 기존 방식 유지 (원재료명 포함)
                search_conditions &= Q(**{f"{field}__icontains": value})
            search_values[query_param] = value
            
    return search_conditions, search_values
