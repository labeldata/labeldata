# constants.py - Django 백엔드 전용 상수

# Django 모델/폼에서 사용되는 선택지 상수
CATEGORY_CHOICES = [
    ('product_name', '제품명'),
    ('ingredient_info', '특정 성분 함량'),
    ('food_type', '식품유형'),
    ('report_no', '품목보고번호'),
    ('content_weight', '내용량'),
    ('storage', '보관방법'),
    ('package', '용기.포장재질'),
    ('manufacturer', '제조원 소재지'),
    ('distributor', '유통전문판매원'),
    ('repacker', '소분원'),
    ('importer', '수입원'),
    ('expiry', '소비기한'),
    ('cautions', '주의사항'),
    ('additional', '기타표시사항')
]

# Django 백엔드에서 사용하는 서버사이드 기본값
SERVER_DEFAULT_SETTINGS = {
    'layout': {
        'width': 10,  # cm
        'height': 10,
        'area': 100,  # cm²
        'min_width': 4,
        'max_width': 30,
        'min_height': 3,
        'max_height': 20
    },
    'font': {
        'family': 'Noto Sans KR',
        'available_fonts': [
            {'name': 'Noto Sans KR', 'label': '노토 산스'},
            {'name': 'Nanum Gothic', 'label': '나눔고딕'},
            {'name': 'Nanum Myeongjo', 'label': '나눔명조'}
        ]
    }
}

# 백엔드 데이터 검증용 규정 상수 (단일 진실의 원천)
LABEL_REGULATIONS = {
    'area_thresholds': {
        'small': 100,    # 100cm² 미만
        'medium': 3000,  # 3000cm² 미만  
        'large': 3000    # 3000cm² 이상
    },
    'font_size': {
        'product_name': {'min': 16, 'small_area_min': 10},
        'origin': {'min': 14, 'small_area_min': 10},
        'content_weight': {'min': 12, 'small_area_min': 10},
        'general': {'min': 10, 'small_area_min': 10}
    },
    'spacing': {
        'letter': {'default': -5, 'min': -10, 'max': 10},
        'line': {'default': 1.2, 'min': 1.0, 'max': 3.0},
        'word': {'min': 90, 'small_area_min': 50}
    },
    'font': {
        'size': {
            'default': 10,
            'min': 6, 
            'max': 72,
            'product_name': 16,
            'origin': 14,
            'content_weight': 12,
            'general': 10,
            'small_area_adjustment': 12  # 100cm² 미만일 때
        }
    }
}

# 영양성분 관련 상수 (프론트엔드와 동기화)
NUTRITION_DATA = {
    # 필수 영양성분 (9가지) - MFDS 2024 기준
    'calories': {'label': '열량', 'unit': 'kcal', 'order': 1, 'required': True, 'daily_value': None},
    'natriums': {'label': '나트륨', 'unit': 'mg', 'order': 2, 'required': True, 'daily_value': 2000},
    'carbohydrates': {'label': '탄수화물', 'unit': 'g', 'order': 3, 'required': True, 'daily_value': 324},
    'sugars': {'label': '당류', 'unit': 'g', 'order': 4, 'parent': 'carbohydrates', 'indent': True, 'required': True, 'daily_value': 100},
    'fats': {'label': '지방', 'unit': 'g', 'order': 5, 'required': True, 'daily_value': 54},
    'trans_fats': {'label': '트랜스지방', 'unit': 'g', 'order': 6, 'parent': 'fats', 'indent': True, 'required': True, 'daily_value': None},
    'saturated_fats': {'label': '포화지방', 'unit': 'g', 'order': 7, 'parent': 'fats', 'indent': True, 'required': True, 'daily_value': 15},
    'cholesterols': {'label': '콜레스테롤', 'unit': 'mg', 'order': 8, 'required': True, 'daily_value': 300},
    'proteins': {'label': '단백질', 'unit': 'g', 'order': 9, 'required': True, 'daily_value': 55},
    
    # 추가 영양성분
    'dietary_fiber': {'label': '식이섬유', 'unit': 'g', 'order': 10, 'daily_value': 25},
    'calcium': {'label': '칼슘', 'unit': 'mg', 'order': 11, 'daily_value': 700},
    'iron': {'label': '철', 'unit': 'mg', 'order': 12, 'daily_value': 12},
    'magnesium': {'label': '마그네슘', 'unit': 'mg', 'order': 13, 'daily_value': 315},
    'phosphorus': {'label': '인', 'unit': 'mg', 'order': 14, 'daily_value': 700},
    'potassium': {'label': '칼륨', 'unit': 'mg', 'order': 15, 'daily_value': 3500},
    'zinc': {'label': '아연', 'unit': 'mg', 'order': 16, 'daily_value': 8.5},
    'vitamin_a': {'label': '비타민A', 'unit': 'μg RAE', 'order': 17, 'daily_value': 700},
    'vitamin_d': {'label': '비타민D', 'unit': 'μg', 'order': 18, 'daily_value': 10},
    'vitamin_e': {'label': '비타민E', 'unit': 'mg α-TE', 'order': 19, 'daily_value': 12},
    'vitamin_c': {'label': '비타민C', 'unit': 'mg', 'order': 20, 'daily_value': 100},
    'thiamine': {'label': '티아민', 'unit': 'mg', 'order': 21, 'daily_value': 1.2},
    'riboflavin': {'label': '리보플라빈', 'unit': 'mg', 'order': 22, 'daily_value': 1.4},
    'niacin': {'label': '니아신', 'unit': 'mg NE', 'order': 23, 'daily_value': 15},
    'vitamin_b6': {'label': '비타민B6', 'unit': 'mg', 'order': 24, 'daily_value': 1.5},
    'folic_acid': {'label': '엽산', 'unit': 'μg DFE', 'order': 25, 'daily_value': 400},
    'vitamin_b12': {'label': '비타민B12', 'unit': 'μg', 'order': 26, 'daily_value': 2.4},
    'selenium': {'label': '셀레늄', 'unit': 'μg', 'order': 27, 'daily_value': 55},
}

# 강조표시 기준 (식약처 기준)
EMPHASIS_CRITERIA = {
    'low': {  # 저 함유 기준 (100g 또는 100ml 기준)
        'calories': {'threshold': 40, 'label': '저열량'},
        'fats': {'threshold': 3, 'label': '저지방'},
        'saturated_fats': {'threshold': 1.5, 'label': '저포화지방'},
        'sugars': {'threshold': 5, 'label': '저당'},
        'natriums': {'threshold': 120, 'label': '저나트륨'},
        'cholesterols': {'threshold': 20, 'label': '저콜레스테롤'}
    },
    'free': {  # 무 함유 기준
        'calories': {'threshold': 4, 'label': '무열량'},
        'fats': {'threshold': 0.5, 'label': '무지방'},
        'saturated_fats': {'threshold': 0.1, 'label': '무포화지방'},
        'sugars': {'threshold': 0.5, 'label': '무당'},
        'natriums': {'threshold': 5, 'label': '무나트륨'},
        'cholesterols': {'threshold': 2, 'label': '무콜레스테롤'}
    },
    'high': {  # 고 함유 기준 (1일 기준치의 30% 이상)
        'proteins': {'threshold': 16.5, 'label': '고단백'},
        'dietary_fiber': {'threshold': 7.5, 'label': '고식이섬유'},
        'calcium': {'threshold': 210, 'label': '고칼슘'},
        'iron': {'threshold': 3.6, 'label': '고철분'},
        'vitamin_e': {'threshold': 3.6, 'label': '고비타민E'},
        'vitamin_c': {'threshold': 30, 'label': '고비타민C'}
    }
}