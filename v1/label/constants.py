# constants.py

# 추천 문구로만 사용되며, 데이터베이스에 저장되지 않음
# '신규' 버튼에서 제공되는 기본 템플릿

DEFAULT_PHRASES = {
    'label_name': [
        {'name': '기본', 'content': '기본제품', 'note': '기본제품', 'order': 1},
        {'name': '리뉴얼', 'content': '리뉴얼', 'note': '기존 제품 개선 시 라벨명', 'order': 2},
        {'name': '특별기획', 'content': '특별기획', 'note': '한정판 또는 이벤트 제품 라벨명', 'order': 3},
    ],
    'food_type': [
        {'name': '통조림', 'content': '과ㆍ채가공품(살균제품/산성통조림)', 'note': '통조림 중 산성인 제품', 'order': 1},
        {'name': '살균조건 표시', 'content': '유함유가공품(72℃, 15초 살균)', 'note': '살균조건을 표시하는 제품', 'order': 2},
    ],
    'product_name': [
        {'name': '기본', 'content': '기본제품', 'note': '기본제품', 'order': 1},
    ],
    'ingredient_info': [
        {'name': '제품명 표시', 'content': '제품명 포함된 원료명 00%', 'note': '제품명 표시한 경우', 'order': 1},
        {'name': '카페인', 'content': '카페인 100mg', 'note': '카페인 함유 제품', 'order': 2},
    ],
    'content_weight': [
        {'name': '내용량', 'content': '내용량 ○○ml', 'note': '액체 포장 제품', 'order': 1},
        {'name': '고형물 포함', 'content': '내용량 ○○g(고형물 00g)', 'note': '고체+액체 혼합 제품', 'order': 2},
        {'name': '순중량', 'content': '순중량 ○○g', 'note': '얼음막 제외', 'order': 3},
    ],
    'weight_calorie': [
        {'name': '1회 제공량', 'content': '1회 제공량 ○○g당 ○○kcal', 'note': '1회 섭취 열량 표시', 'order': 1},
        {'name': '총 내용량', 'content': '총 내용량 ○○g당 ○○kcal', 'note': '전체 제품 열량 표시', 'order': 2},
        {'name': '100g당', 'content': '100g당 ○○kcal', 'note': '단위 중량별 열량', 'order': 3},
        {'name': '영양성분', 'content': '1회 제공량당 열량 ○○kcal, 탄수화물 ○○g, 단백질 ○○g', 'note': '영양성분 포함 표시', 'order': 4},
        {'name': '저칼로리', 'content': '저칼로리: 1회 제공량 ○○kcal', 'note': '저칼로리 제품 강조', 'order': 5}
    ],
    'report_no': [
        {'name': '1공장', 'content': '○○○○○○○○○○○○-○○○', 'note': '1공장 인허가번호', 'order': 1},
        {'name': '2공장', 'content': '○○○○○○○○○○○○-○○○', 'note': '2공장 인허가번호', 'order': 2},
    ],
    'storage': [
        {'name': '냉장보관', 'content': '냉장 보관 (0~10℃)', 'note': '냉장제품', 'order': 1},
        {'name': '냉동보관', 'content': '냉동 보관 (-18℃ 이하)', 'note': '냉동제품', 'order': 2},
        {'name': '실온보관', 'content': '직사광선을 피하고 서늘한 곳에 보관', 'note': '상온제품', 'order': 3},
        {'name': '개봉 후 보관', 'content': '개봉 후에는 냉장 보관하고 가급적 빨리 섭취하십시오.', 'note': '유지 안정성 낮은 제품', 'order': 4}
    ],
    'package': [
        {
            'name': '플라스틱 PE 포장',
            'content': '폴리에틸렌(PE)',
            'note': '단일재질 플라스틱 필름 또는 용기',
            'order': 1,
            'recycling_mark': '플라스틱(PE)',
            'keywords': ['폴리에틸렌', 'pe', '플라스틱 pe', 'pe 필름']  # 매칭 키워드
        },
        {
            'name': '플라스틱 PP 포장',
            'content': '폴리프로필렌(PP)',
            'note': '단일재질 플라스틱 용기 또는 트레이',
            'order': 2,
            'recycling_mark': '플라스틱(PP)',
            'keywords': ['폴리프로필렌', 'pp', '플라스틱 pp', 'pp 용기']
        },
        {
            'name': 'PET 병 포장',
            'content': '폴리에틸렌테레프탈레이트(PET)',
            'note': '단일재질 PET 병',
            'order': 3,
            'recycling_mark': '플라스틱(PET)',
            'keywords': ['pet', '폴리에틸렌테레프탈레이트', '플라스틱 pet', 'pet 병']
        },
        {
            'name': '유리 포장',
            'content': '유리',
            'note': '단일재질 유리병',
            'order': 4,
            'recycling_mark': '유리',
            'keywords': ['유리', '유리병', '글라스']
        },
        {
            'name': '알루미늄 캔 포장',
            'content': '알루미늄',
            'note': '단일재질 알루미늄 캔',
            'order': 5,
            'recycling_mark': '금속(알루미늄)',
            'keywords': ['알루미늄', '알루미늄 캔', '알캔']
        },
        {
            'name': '철 캔 포장',
            'content': '철',
            'note': '단일재질 철제 캔 또는 드럼',
            'order': 6,
            'recycling_mark': '금속(철)',
            'keywords': ['철', '철 캔', '스틸']
        },
        {
            'name': '종이 포장',
            'content': '종이',
            'note': '단일재질 종이 포장 또는 티백',
            'order': 7,
            'recycling_mark': '종이',
            'keywords': ['종이', '페이퍼', '카드보드']
        },
        {
            'name': '플라스틱 복합 포장',
            'content': '내포장재: 폴리에틸렌(PE), 외포장재: 종이',
            'note': '식품용 플라스틱 필름 및 종이 박스 포장',
            'order': 8,
            'recycling_mark': '복합재질(분리배출 요망)',
            'keywords': ['복합', '플라스틱+종이', 'pe+종이', '다층']
        },
        # 기타 포장재질
        {
            'name': '기타 포장',
            'content': '기타',
            'note': '분류 불가능한 포장재질',
            'order': 9,
            'recycling_mark': '기타',
            'keywords': ['기타', '미분류', '그 외']
        }
    ],
    'manufacturer': [
        {'name': '제조원기본', 'content': '제조원: (주)식품제조 / 경기도 성남시 분당구 판교로 000', 'note': '직접 제조하는 경우', 'order': 1},
        {'name': '위탁제조', 'content': '제조원: ○○OEM / 경기도 화성시', 'note': 'OEM/ODM 위탁 생산 제품', 'order': 2}
    ],
    'distributor': [
        {'name': '유통판매원', 'content': '유통전문판매원: (주)식품유통 / 서울특별시 강남구 테헤란로 000', 'note': '유통만 하는 경우', 'order': 1}
    ],
    'repacker': [
        {'name': '소분원', 'content': '소분원: (주)식품소분 / 인천광역시 서구 검단로 000', 'note': '소분 작업을 하는 경우', 'order': 1}
    ],
    'importer': [
        {'name': '수입원', 'content': '수입원: (주)식품수입 / 서울특별시 영등포구 여의도로 000', 'note': '수입식품의 경우', 'order': 1},
        {'name': '병행수입', 'content': '수입원: ○○상사 / 병행수입제품', 'note': '병행수입식품', 'order': 2}
    ],
    'expiry': [
        {'name': '제조일기준', 'content': '제조일로부터 12개월', 'note': '상온보관 제품', 'order': 1},
        {'name': '냉동보관', 'content': '-18℃이하 냉동보관시 제조일로부터 24개월', 'note': '냉동보관 제품', 'order': 2},
        {'name': '유통기한 표기', 'content': '유통기한: 별도 표시일까지', 'note': '유통기한 직접 표기 시', 'order': 3}
    ],
    'cautions': [
        {'name': '부정불량신고', 'content': '부정·불량식품신고는 국번없이 1399', 'note': '필수 표시사항', 'order': 1},
        {'name': '알레르기 주의1', 'content': '이 제품은 알레르기 유발물질(알류, 우유, 땅콩, 대두, 밀, 돼지고기, 복숭아, 토마토, 호두, 닭고기, 쇠고기, 오징어, 조개류 등)을 사용한 제품과 같은 제조시설에서 제조되었습니다.', 'note': '알레르기 주의 1번', 'order': 8},
        {'name': '알레르기 주의2', 'content': '알레르기 유발물질(알류, 우유, 대두, 밀, 땅콩 등)이 혼입될 수 있으니 주의하시기 바랍니다.', 'note': '알레르기 주의 2번', 'order': 9},
        {'name': '재냉동금지', 'content': '이 제품은 냉동식품을 해동한 제품이니 재냉동시키지 마시길 바랍니다.', 'note': '해동 후 판매제품', 'order': 3},
        {'name': '카페인', 'content': '어린이, 임산부, 카페인 민감자는 섭취에 주의해 주시기 바랍니다. 고카페인 함유', 'note': '고카페인 제품', 'order': 3},
        {'name': '주류경고', 'content': '경고 : 지나친 음주는 뇌졸중, 기억력 손상이나 치매를 유발합니다. 임신 중 음주는 기형아 출생 위험을 높입니다. 19세 미만 판매 금지', 'note': '주류', 'order': 4},
        {'name': '질식주의', 'content': '얼려서 드시지 마십시오. 한 번에 드실 경우 질식 위험이 있으니 잘 씹어 드십시오. 5세 이하 어린이 및 노약자는 섭취를 금하여 주십시오.', 'note': '젤리/곤약 제품', 'order': 5},
        {'name': '캔주의', 'content': '개봉 시 캔 절단부분에 손이 닿지 않도록 각별히 주의하십시오.', 'note': '캔 제품', 'order': 6},
        {'name': '씨제거주의', 'content': '기계로 씨를 제거하는 과정에서 씨 또는 씨의 일부가 남아있을 수 있으니 주의해서 드세요.', 'note': '과일 함유 제품', 'order': 7},
        {'name': '전자레인지용1', 'content': '이 제품은 전자레인지 조리가 가능합니다.', 'note': '전자레인지용 1번', 'order': 10},
        {'name': '전자레인지용2', 'content': '포장지를 제거한 후 전자레인지에 넣어 조리하세요.', 'note': '전자레인지용 3번', 'order': 11},
        {'name': '조사처리', 'content': '이 식품은 감마선/전자선으로 조사처리한 제품입니다.', 'note': '방사선 조사 제품', 'order': 2},
    ],
    'additional': [
        {'name': '반품교환', 'content': '반품 및 교환장소: 구입처 및 본사', 'note': '필수 표시사항', 'order': 1},
        {'name': '품질보증', 'content': '본 제품은 소비자분쟁해결기준에 의거 교환 또는 보상 받을 수 있습니다.', 'note': '필수 표시사항', 'order': 2},
        {'name': '알코올', 'content': '이 제품에는 알코올이 포함되어 있습니다. 알코올 함량 ○○%', 'note': '알코올 함유 제품', 'order': 4},
        {'name': '유산균', 'content': '유산균 100,000,000(1억) CFU/g, 유산균 1억 CFU/g', 'note': '유산균 함유 제품', 'order': 5},
        {'name': '해동방법', 'content': '조리 시 해동방법: 자연 해동 후 사용', 'note': '냉동 식재료 조리 시', 'order': 6},
        {'name': '섭취방법', 'content': '1일 2회, 1회 1포를 물과 함께 섭취하십시오.', 'note': '기능성 제품 섭취 방법', 'order': 7},
        {'name': '사용방법', 'content': '기호에 따라 물이나 우유에 타서 드세요.', 'note': '분말 제품 사용 시', 'order': 8},
        {'name': '음용온도', 'content': '차갑게 또는 따뜻하게 음용 가능합니다.', 'note': '액상음료 등 음용안내', 'order': 9},
        {'name': '소비자상담', 'content': '소비자상담실: 080-000-0000', 'note': '문의전화 안내', 'order': 10},
        {'name': '보관기한안내', 'content': '보관상태에 따라 유통기한 이내라도 변질될 수 있습니다.', 'note': '유통기한 관련 안내', 'order': 11},
        {'name': '색상차이', 'content': '천연 원료로 인해 색상 차이가 있을 수 있습니다.', 'note': '천연 원료 제품', 'order': 12},
        {'name': '침전물', 'content': '침전물이 생길 수 있으나 품질에는 이상이 없습니다.', 'note': '액상제품 또는 착즙음료', 'order': 13}
    ]
}

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

FIELD_REGULATIONS = {
    'label_nm': '''
    [라벨명 관련 규정]
    - 라벨을 구분할 수 있는 고유한 이름을 설정
    - 제품의 특성을 반영한 명칭 사용 권장
    ''',
    
    'prdlst_dcnm': '''
    [식품유형 관련 규정]
    - 식품의 유형은 식품유형 분류 체계에 따라 정확히 기재
    - 식품유형에 따른 기준 및 규격을 반드시 준수
    ''',
    
    'prdlst_nm': '''
    [제품명 관련 규정]
    - 제품의 특성을 나타내는 고유의 명칭 사용
    - 소비자를 오도하거나 혼동시키는 명칭 사용 금지
    - 허위•과대의 표시•광고에 해당하지 않도록 주의
    ''',
    
    'ingredients_info': '''
    [성분명 및 함량 관련 규정]
    - 제품에 직접 첨가하지 아니한 제품에 사용된 원재료 중에 함유된 성분명을 표시하고자 할 때에는 그 명칭과 실제 그 제품에 함유된 함량을 중량 또는 용량으로 표시하여야 함.
    ''',

    'content_weight': '''
    [내용량 관련 규정]
    - 내용량은 g, kg, ml, L 등의 법정계량단위로 표시
    - 고체와 액체가 혼합된 제품은 각각의 중량 표시
    - 내용량 허용오차 기준 준수
    ''',

    'report_no': '''
    [품목보고번호 관련 규정]
    -「식품위생법」 제37조에 따라 제조ㆍ가공업 영업자 또는 「축산물 위생관리법」 제25조에 따라 축산물가공업, 식육포장처리업 영업자가 관할기관에 품목제조를 보고할 때 부여되는 번호. 수입식품은 표시대상 아님.
    ''',

    'storage': '''
    [보관방법 관련 규정]
    - 식품의 특성에 맞는 보관방법을 정확히 기재
    - 냉장/냉동의 경우 정확한 온도를 명시
    - 개봉 후 보관방법이 달라지는 경우 이를 명확히 표시
    ''',

    'package': '''
    [포장재질 관련 규정]
    - 식품위생법에서 정한 기준규격에 적합한 재질임을 명시
    - 내포장재와 외포장재를 구분하여 표시
    - 재활용 가능 여부 및 분리배출 표시 방법 준수
    ''',

    'manufacturer': '''
    [제조원 소재지 관련 규정]
    - 실제 제조가 이루어지는 업소명과 소재지 표시
    - 위탁생산의 경우 위탁생산임을 명시하고 제조원 표시
    - 제조업소의 명칭과 소재지는 영업신고증과 일치하도록 표시
    ''',

    'distributor': '''
    [유통전문판매원 관련 규정]
    - 유통전문판매원의 업소명과 소재지 표시
    - 제조원과 별도로 구분하여 표시
    - 실제 유통을 담당하는 업체 정보만 표시
    ''',

    'expiry': '''
    [소비기한 관련 규정]
    - 소비기한은 "소비기한: 0000년 00월 00일"과 같이 표시
    - 제조일자를 추가로 표시하는 경우 소비기한과 동일한 위치에 표시
    - 보관조건을 함께 표시
    ''',

    'weight_calorie': '''
    [내용량 및 열량 관련 규정]
    - 1회 제공량당 열량 표시
    - 총 제공량 및 1회 제공량 표시
    - 100g(ml)당 열량도 함께 표시 권장
    ''',

    'rawmtrl_nm': '''
    [원재료명 관련 규정]
    - 사용된 모든 원재료를 많이 사용한 순서대로 표시
    - 식품첨가물은 용도와 함께 표시
    - 알레르기 유발물질은 눈에 띄게 표시
    ''',

    'cautions': '''
    [주의사항 관련 규정]
    - 알레르기 유발물질 포함 시 반드시 표시
    - 부정불량식품 신고는 국번없이 1399 표시
    - 보관방법 또는 섭취방법에 주의가 필요한 경우 명확히 표시
    ''',

    'additional': '''
    [기타표시사항 관련 규정]
    - 품목제조보고서 기재사항과 일치하도록 표시
    - 부당한 표시•광고에 해당하지 않도록 주의
    - 소비자가 오인•혼동하지 않도록 명확히 표시
    '''
}

# 미리보기 기본 설정
PREVIEW_DEFAULT_SETTINGS = {
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
        ],
        'size': {
            'default': 10,
            'min': 6,
            'max': 72,
            'product_name': 16,
            'origin': 14,
            'content_weight': 12,
            'general': 10
        }
    },
    'spacing': {
        'letter': {
            'default': -5,
            'min': -10,
            'max': 10
        },
        'line': {
            'default': 1.2,
            'min': 1.0,
            'max': 3.0
        }
    },
    'regulations': {
        'area_thresholds': {
            'small': 100,
            'standard': 100
        },
        'font_size': {
            'small': 12,   # 100cm² 미만일 때
            'standard': 10  # 100cm² 이상일 때
        }
    }
}

# 규정 검증을 위한 상수
REGULATIONS = {
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
        'letter': {'min': -5},
        'word': {'min': 90, 'small_area_min': 50}
    }
}

EXPIRY_RECOMMENDATION = {
    "과자": {"shelf_life": 12, "unit": "months"},
    "빵류": {"shelf_life": 14, "unit": "days"},
    "떡류": {"shelf_life": 10, "unit": "days"},
    "추잉껌": {"shelf_life": 24, "unit": "months"},
    "캔디류": {"shelf_life": 24, "unit": "months"},
    "기타가공품": {"shelf_life": "제품별", "unit": None},
    "효모식품": {"shelf_life": 24, "unit": "months"},
    "시리얼류": {"shelf_life": 18, "unit": "months"},
    "찐쌀": {"shelf_life": 12, "unit": "months"},
    "효소식품": {"shelf_life": 24, "unit": "months"},
    "곡류가공품": {"shelf_life": 24, "unit": "months"},
    "과·채가공품": {"shelf_life": 12, "unit": "months"},
    "기타농산가공품": {"shelf_life": "제품별", "unit": None},
    "두류가공품": {"shelf_life": 24, "unit": "months"},
    "서류가공품": {"shelf_life": 24, "unit": "months"},
    "땅콩 또는 견과류가공품": {"shelf_life": 12, "unit": "months"},
    "땅콩버터": {"shelf_life": 12, "unit": "months"},
    "밀가루": {"shelf_life": 12, "unit": "months"},
    "영영강화 밀가루": {"shelf_life": 12, "unit": "months"},
    "전분": {"shelf_life": 24, "unit": "months"},
    "전분가공품": {"shelf_life": 24, "unit": "months"},
    "당류가공품": {"shelf_life": 36, "unit": "months"},
    "당시럽류": {"shelf_life": 36, "unit": "months"},
    "포도당": {"shelf_life": 36, "unit": "months"},
    "과당": {"shelf_life": 36, "unit": "months"},
    "기타과당": {"shelf_life": 36, "unit": "months"},
    "기타설탕": {"shelf_life": 36, "unit": "months"},
    "설탕": {"shelf_life": 36, "unit": "months"},
    "기타 엿": {"shelf_life": 36, "unit": "months"},
    "덱스트린": {"shelf_life": 36, "unit": "months"},
    "물엿": {"shelf_life": 36, "unit": "months"},
    "올리고당": {"shelf_life": 36, "unit": "months"},
    "올리고당가공품": {"shelf_life": 36, "unit": "months"},
    "곤충가공식품": {"shelf_life": 24, "unit": "months"},
    "추출가공식품": {"shelf_life": "제품별", "unit": None},
    "기타 동물성가공식품": {"shelf_life": "제품별", "unit": None},
    "기타식육 또는 기타알": {"shelf_life": "제품별", "unit": None},
    "자라분말": {"shelf_life": "제품별", "unit": None},
    "자라분말제품": {"shelf_life": "제품별", "unit": None},
    "자라유제품": {"shelf_life": "제품별", "unit": None},
    "가공두부": {"shelf_life": 27, "unit": "days"},
    "두부": {"shelf_life": 27, "unit": "days"},
    "묵류": {"shelf_life": 27, "unit": "days"},
    "유바": {"shelf_life": 27, "unit": "days"},
    "건면": {"shelf_life": 12, "unit": "months"},
    "생면": {"shelf_life": 60, "unit": "days"},
    "숙면": {"shelf_life": 60, "unit": "days"},
    "유탕면": {"shelf_life": 12, "unit": "months"},
    "로열제리": {"shelf_life": 36, "unit": "months"},
    "로열젤리제품": {"shelf_life": 36, "unit": "months"},
    "벌꿀": {"shelf_life": 36, "unit": "months"},
    "벌집꿀": {"shelf_life": 36, "unit": "months"},
    "사양벌꿀": {"shelf_life": 36, "unit": "months"},
    "사양벌집꿀": {"shelf_life": 36, "unit": "months"},
    "가공화분": {"shelf_life": 24, "unit": "months"},
    "화분함유제품": {"shelf_life": 24, "unit": "months"},
    "빙과": {"shelf_life": 24, "unit": "months"},
    "비유지방아이스크림": {"shelf_life": 24, "unit": "months"},
    "샤베트": {"shelf_life": 24, "unit": "months"},
    "아이스밀크": {"shelf_life": 24, "unit": "months"},
    "아이스크림": {"shelf_life": 24, "unit": "months"},
    "저지방아이스크림": {"shelf_life": 24, "unit": "months"},
    "비유지방아이스크림믹스": {"shelf_life": 24, "unit": "months"},
    "샤베트믹스": {"shelf_life": 24, "unit": "months"},
    "아이스밀크믹스": {"shelf_life": 24, "unit": "months"},
    "아이스크림믹스": {"shelf_life": 24, "unit": "months"},
    "저지방아이스크림믹스": {"shelf_life": 24, "unit": "months"},
    "식용얼음": {"shelf_life": 1, "unit": "months"},
    "어업용얼음": {"shelf_life": 1, "unit": "months"},
    "기타 수산물가공품": {"shelf_life": "제품별", "unit": None},
    "조미김": {"shelf_life": 8, "unit": "months"},
    "한천": {"shelf_life": 24, "unit": "months"},
    "건어포": {"shelf_life": 24, "unit": "months"},
    "기타 건포류": {"shelf_life": 24, "unit": "months"},
    "조미건어포": {"shelf_life": 12, "unit": "months"},
    "기타 어육가공품": {"shelf_life": "제품별", "unit": None},
    "어묵": {"shelf_life": 42, "unit": "days"},
    "어육반제품": {"shelf_life": "제품별", "unit": None},
    "어육살": {"shelf_life": "제품별", "unit": None},
    "어육소시지": {"shelf_life": "제품별", "unit": None},
    "연육": {"shelf_life": "제품별", "unit": None},
    "액젓": {"shelf_life": 36, "unit": "months"},
    "양념젓갈": {"shelf_life": 36, "unit": "months"},
    "젓갈": {"shelf_life": 36, "unit": "months"},
    "조미액젓": {"shelf_life": 36, "unit": "months"},
    "기타동물성유지": {"shelf_life": 24, "unit": "months"},
    "식용돈지": {"shelf_life": 24, "unit": "months"},
    "식용우지": {"shelf_life": 24, "unit": "months"},
    "어유": {"shelf_life": 24, "unit": "months"},
    "고추씨기름": {"shelf_life": 24, "unit": "months"},
    "기타식물성유지": {"shelf_life": 24, "unit": "months"},
    "들기름": {"shelf_life": 18, "unit": "months"},
    "땅콩기름(낙화생유)": {"shelf_life": 18, "unit": "months"},
    "목화씨기름(면실유)": {"shelf_life": 18, "unit": "months"},
    "미강유(현미유)": {"shelf_life": 18, "unit": "months"},
    "야자유": {"shelf_life": 18, "unit": "months"},
    "옥수수기름(옥배유)": {"shelf_life": 18, "unit": "months"},
    "올리브유": {"shelf_life": 18, "unit": "months"},
    "참기름": {"shelf_life": 18, "unit": "months"},
    "채종유(유채유 또는 카놀라유)": {"shelf_life": 18, "unit": "months"},
    "추출들깨유": {"shelf_life": 18, "unit": "months"},
    "추출참깨유": {"shelf_life": 18, "unit": "months"},
    "콩기름(대두유)": {"shelf_life": 18, "unit": "months"},
    "팜스테아린유": {"shelf_life": 18, "unit": "months"},
    "팜올레인유": {"shelf_life": 18, "unit": "months"},
    "팜유": {"shelf_life": 18, "unit": "months"},
    "팜핵유": {"shelf_life": 18, "unit": "months"},
    "해바라기유": {"shelf_life": 18, "unit": "months"},
    "홍화유(사플라워유 또는 잇꽃유)": {"shelf_life": 18, "unit": "months"},
    "가공유지": {"shelf_life": 18, "unit": "months"},
    "마가린": {"shelf_life": 18, "unit": "months"},
    "모조치즈": {"shelf_life": 18, "unit": "months"},
    "쇼트닝": {"shelf_life": 18, "unit": "months"},
    "식물성크림": {"shelf_life": 12, "unit": "months"},
    "향미유": {"shelf_life": 18, "unit": "months"},
    "혼합식용유": {"shelf_life": 18, "unit": "months"},
    "건조저장육류": {"shelf_life": 6, "unit": "months"},
    "베이컨류": {"shelf_life": 66, "unit": "days"},
    "식육간편조리세트": {"shelf_life": "제품별", "unit": None},
    "식육추출가공품": {"shelf_life": "제품별", "unit": None},
    "식육함유가공품": {"shelf_life": "제품별", "unit": None},
    "포장육": {"shelf_life": "제품별", "unit": None},
    "발효소시지": {"shelf_life": 90, "unit": "days"},
    "소시지": {"shelf_life": 56, "unit": "days"},
    "혼합소시지": {"shelf_life": 66, "unit": "days"},
    "갈비가공품": {"shelf_life": "제품별", "unit": None},
    "분쇄가공육제품": {"shelf_life": 30, "unit": "days"},
    "식육케이싱": {"shelf_life": "제품별", "unit": None},
    "양념육": {"shelf_life": 30, "unit": "days"},
    "천연케이싱": {"shelf_life": "제품별", "unit": None},
    "생햄": {"shelf_life": 90, "unit": "days"},
    "프레스햄": {"shelf_life": 66, "unit": "days"},
    "햄": {"shelf_life": 57, "unit": "days"},
    "알함유가공품": {"shelf_life": "제품별", "unit": None},
    "난백분": {"shelf_life": 24, "unit": "months"},
    "난백액": {"shelf_life": 10, "unit": "days"},
    "난황분": {"shelf_life": 24, "unit": "months"},
    "난황액": {"shelf_life": 10, "unit": "days"},
    "알가열제품": {"shelf_life": "제품별", "unit": None},
    "전란분": {"shelf_life": 24, "unit": "months"},
    "전란액": {"shelf_life": 10, "unit": "days"},
    "피단": {"shelf_life": "제품별", "unit": None},
    "버터유": {"shelf_life": 12, "unit": "months"},
    "산양유": {"shelf_life": "제품별", "unit": None},
    "유단백가수분해식품": {"shelf_life": "제품별", "unit": None},
    "유당": {"shelf_life": 12, "unit": "months"},
    "유함유가공품": {"shelf_life": "제품별", "unit": None},
    "가공유": {"shelf_life": 24, "unit": "days"},
    "강화우유": {"shelf_life": 15, "unit": "days"},
    "유당분해우유": {"shelf_life": 15, "unit": "days"},
    "유산균첨가우유": {"shelf_life": 15, "unit": "days"},
    "가공연유": {"shelf_life": 12, "unit": "months"},
    "가당연유": {"shelf_life": 12, "unit": "months"},
    "가당탈지연유": {"shelf_life": 12, "unit": "months"},
    "농축우유": {"shelf_life": 12, "unit": "months"},
    "탈지농축우유": {"shelf_life": 12, "unit": "months"},
    "농후발효유": {"shelf_life": 32, "unit": "days"},
    "농후크림발효유": {"shelf_life": 32, "unit": "days"},
    "발효버터유": {"shelf_life": 12, "unit": "months"},
    "발효유": {"shelf_life": 32, "unit": "days"},
    "발효유분말": {"shelf_life": 12, "unit": "months"},
    "크림발효유": {"shelf_life": 32, "unit": "days"},
    "가공버터": {"shelf_life": 12, "unit": "months"},
    "버터": {"shelf_life": 12, "unit": "months"},
    "버터오일": {"shelf_life": 12, "unit": "months"},
    "가당분유": {"shelf_life": 18, "unit": "months"},
    "전지분유": {"shelf_life": 18, "unit": "months"},
    "탈지분유": {"shelf_life": 18, "unit": "months"},
    "혼합분유": {"shelf_life": 18, "unit": "months"},
    "우유": {"shelf_life": 15, "unit": "days"},
    "환원유": {"shelf_life": 15, "unit": "days"},
    "농축유청": {"shelf_life": 12, "unit": "months"},
    "유청": {"shelf_life": 12, "unit": "months"},
    "유청단백분말": {"shelf_life": 12, "unit": "months"},
    "가공유크림": {"shelf_life": 12, "unit": "months"},
    "유크림": {"shelf_life": 12, "unit": "months"},
    "가공치즈": {"shelf_life": 12, "unit": "months"},
    "치즈": {"shelf_life": 18, "unit": "months"},
    "인삼·홍삼음료": {"shelf_life": 12, "unit": "months"},
    "커피": {"shelf_life": 12, "unit": "months"},
    "과·채음료": {"shelf_life": 12, "unit": "months"},
    "과·채주스": {"shelf_life": 12, "unit": "months"},
    "농축과·채즙": {"shelf_life": 12, "unit": "months"},
    "음료베이스": {"shelf_life": 12, "unit": "months"},
    "혼합음료": {"shelf_life": 12, "unit": "months"},
    "고형차": {"shelf_life": 24, "unit": "months"},
    "액상차": {"shelf_life": 12, "unit": "months"},
    "침출차": {"shelf_life": 24, "unit": "months"},
    "가공두유": {"shelf_life": 12, "unit": "months"},
    "원액두유": {"shelf_life": 12, "unit": "months"},
    "기타발효음료": {"shelf_life": "제품별", "unit": None},
    "유산균음료": {"shelf_life": 26, "unit": "days"},
    "효모음료": {"shelf_life": "제품별", "unit": None},
    "탄산수": {"shelf_life": 12, "unit": "months"},
    "탄산음료": {"shelf_life": 12, "unit": "months"},
    "개량메주": {"shelf_life": 12, "unit": "months"},
    "고추장": {"shelf_life": 24, "unit": "months"},
    "기타장류": {"shelf_life": 24, "unit": "months"},
    "된장": {"shelf_life": 24, "unit": "months"},
    "산분해간장": {"shelf_life": 24, "unit": "months"},
    "양조간장": {"shelf_life": 24, "unit": "months"},
    "청국장": {"shelf_life": 24, "unit": "months"},
    "춘장": {"shelf_life": 24, "unit": "months"},
    "한식간장": {"shelf_life": 24, "unit": "months"},
    "한식된장": {"shelf_life": 24, "unit": "months"},
    "한식메주": {"shelf_life": 24, "unit": "months"},
    "혼합간장": {"shelf_life": 24, "unit": "months"},
    "혼합장": {"shelf_life": 24, "unit": "months"},
    "효소분해간장": {"shelf_life": 24, "unit": "months"},
    "기타잼": {"shelf_life": 12, "unit": "months"},
    "잼": {"shelf_life": 12, "unit": "months"},
    "조림류": {"shelf_life": 12, "unit": "months"},
    "김치": {"shelf_life": 6, "unit": "months"},
    "김칫속": {"shelf_life": 6, "unit": "months"},
    "당절임": {"shelf_life": 12, "unit": "months"},
    "절임식품": {"shelf_life": 12, "unit": "months"},
    "고춧가루": {"shelf_life": 12, "unit": "months"},
    "실고추": {"shelf_life": 12, "unit": "months"},
    "마요네즈": {"shelf_life": 12, "unit": "months"},
    "복합조미식품": {"shelf_life": 12, "unit": "months"},
    "소스": {"shelf_life": 12, "unit": "months"},
    "토마토케첩": {"shelf_life": 12, "unit": "months"},
    "가공소금": {"shelf_life": 60, "unit": "months"},
    "기타소금": {"shelf_life": 60, "unit": "months"},
    "재제소금": {"shelf_life": 60, "unit": "months"},
    "정제소금": {"shelf_life": 60, "unit": "months"},
    "천일염": {"shelf_life": 60, "unit": "months"},
    "태움·용융소금": {"shelf_life": 60, "unit": "months"},
    "발효식초": {"shelf_life": 24, "unit": "months"},
    "희석초산": {"shelf_life": 24, "unit": "months"},
    "카레(커리)": {"shelf_life": 24, "unit": "months"},
    "카레(커리)분": {"shelf_life": 24, "unit": "months"},
    "천연향신료": {"shelf_life": 24, "unit": "months"},
    "향신료조제품": {"shelf_life": 24, "unit": "months"},
    "주정": {"shelf_life": 36, "unit": "months"},
    "기타 주류": {"shelf_life": 36, "unit": "months"},
    "과실주": {"shelf_life": 36, "unit": "months"},
    "맥주": {"shelf_life": 12, "unit": "months"},
    "약주": {"shelf_life": 12, "unit": "months"},
    "청주": {"shelf_life": 12, "unit": "months"},
    "탁주": {"shelf_life": 12, "unit": "months"},
    "리큐르": {"shelf_life": 36, "unit": "months"},
    "브랜디": {"shelf_life": 36, "unit": "months"},
    "소주": {"shelf_life": 36, "unit": "months"},
    "위스키": {"shelf_life": 36, "unit": "months"},
    "일반증류주": {"shelf_life": 36, "unit": "months"},
    "만두": {"shelf_life": 12, "unit": "months"},
    "만두피": {"shelf_life": 6, "unit": "months"},
    "생식제품": {"shelf_life": 12, "unit": "months"},
    "생식함유제품": {"shelf_life": 12, "unit": "months"},
    "간편조리세트": {"shelf_life": 12, "unit": "months"},
    "신선편의식품": {"shelf_life": 12, "unit": "months"},
    "즉석섭취식품": {"shelf_life": 12, "unit": "months"},
    "즉석조리식품": {"shelf_life": 12, "unit": "months"},
    "밀크초콜릿": {"shelf_life": 24, "unit": "months"},
    "준초콜릿": {"shelf_life": 24, "unit": "months"},
    "초콜릿": {"shelf_life": 24, "unit": "months"},
    "초콜릿가공품": {"shelf_life": 24, "unit": "months"},
    "화이트초콜릿": {"shelf_life": 24, "unit": "months"},
    "기타 코코아가공품": {"shelf_life": 24, "unit": "months"},
    "코코아매스": {"shelf_life": 24, "unit": "months"},
    "코코아버터": {"shelf_life": 24, "unit": "months"},
    "코코아분말": {"shelf_life": 24, "unit": "months"},
    "고령자용 영양조제식품": {"shelf_life": 18, "unit": "months"},
    "기타영유아식": {"shelf_life": 18, "unit": "months"},
    "성장기용조제식": {"shelf_life": 18, "unit": "months"},
    "영·유아용 곡류조제식": {"shelf_life": 18, "unit": "months"},
    "영·유아용 이유식": {"shelf_life": 12, "unit": "months"},
    "영아용 조제식": {"shelf_life": 18, "unit": "months"},
    "임산·수유부용 식품": {"shelf_life": 18, "unit": "months"},
    "체중조절용 조제식품": {"shelf_life": 18, "unit": "months"},
    "성장기용 조제유": {"shelf_life": 18, "unit": "months"},
    "영아용 조제유": {"shelf_life": 18, "unit": "months"},
    "기타환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "선천성 대사질환자용 조제식품": {"shelf_life": 12, "unit": "months"},
    "영.유아용 특수조제식품": {"shelf_life": 12, "unit": "months"},
    "고혈압환자용 식단형 식품": {"shelf_life": 12, "unit": "months"},
    "당뇨환자용 식단형 식품": {"shelf_life": 12, "unit": "months"},
    "신장질환자용 식단형 식품": {"shelf_life": 12, "unit": "months"},
    "암환자용 식단형 식품": {"shelf_life": 12, "unit": "months"},
    "고혈압환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "당뇨환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "수분 및 전해질보충용 조제식품": {"shelf_life": 12, "unit": "months"},
    "신장질환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "암환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "연하곤란자용 점도조절식품": {"shelf_life": 12, "unit": "months"},
    "열량 및 영양공급용 식품": {"shelf_life": 12, "unit": "months"},
    "일반 환자용 균형영양조제식품(균형영양조제식품)": {"shelf_life": 12, "unit": "months"},
    "장질환자용 단백가수분해 영양조제식품": {"shelf_life": 12, "unit": "months"},
    "폐질환자용 영양조제식품": {"shelf_life": 12, "unit": "months"},
}