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

# ─────────────────────────────────────────────────────────────────────────
# 아래부터는 원래 v1/static/js/label/constants.js에만 하드코딩되어 있던
# 검증 규칙 상수들. 서버측 검증(v1/label/services/validation_service.py)의
# 단일 진실의 원천으로 이곳으로 옮겨왔다. JS 쪽 constants.js는 당장은
# 그대로 두되(다수 템플릿이 동기 로드에 의존해 리스크가 있어 일괄 교체는
# 보류), 신규 검증 로직은 전부 여기 값을 기준으로 삼는다.
# ─────────────────────────────────────────────────────────────────────────

# 원산지 표시 대상 판정용 농수산물 목록 (제품명에 포함되면 함량 표시 필요)
FARM_SEAFOOD_ITEMS = [
    "쌀", "찹쌀", "현미", "벼", "밭벼", "찰벼", "보리", "보리쌀", "밀", "밀쌀", "호밀", "귀리", "옥수수", "조", "수수", "메밀", "기장", "율무",
    "콩", "팥", "녹두", "완두", "강낭콩", "동부", "기타콩",
    "감자", "고구마", "야콘",
    "참깨", "들깨", "땅콩", "해바라기", "유채", "고추씨",
    "수박", "참외", "메론", "딸기", "토마토", "방울토마토", "호박", "오이",
    "배추", "양배추", "고구마줄기", "토란줄기", "쑥", "건 무청", "시래기", "무말랭이", "무", "알타리무", "순무", "당근", "우엉", "연근", "양파", "대파", "쪽파", "실파",
    "건고추", "마늘", "생강", "풋고추", "꽈리고추", "홍고추", "피망", "단고추", "브로코리", "녹색꽃양배추", "파프리카",
    "갈근", "감초", "강활", "건강", "결명자", "구기자", "금은화", "길경", "당귀", "독활", "두충", "만삼", "맥문동", "모과", "목단", "반하", "방풍", "복령", "복분자", "백수오", "백지", "백출", "비자", "사삼", "양유", "더덕", "산수유", "산약", "산조인", "산초", "소자", "시호", "오가피", "오미자", "오배자", "우슬", "황정", "층층갈고리둥굴레", "옥죽", "외유", "둥굴레", "음양곽", "익모초", "작약", "진피", "지모", "지황", "차전자", "창출", "천궁", "천마", "치자", "택사", "패모", "하수오", "황기", "황백", "황금", "행인", "향부자", "현삼", "후박", "홍화씨", "고본", "소엽", "형개", "치커리", "헛개",
    "녹용", "녹각",
    "사과", "애플", "배", "포도", "복숭아", "단감", "떫은감", "곶감", "자두", "살구", "참다래", "파인애플", "감귤", "만감", "한라봉", "레몬", "탄제린", "오렌지", "청견", "자몽", "금감", "유자", "버찌", "매실", "앵두", "무화과", "바나나", "블루베리", "석류", "오디",
    "밤", "대추", "잣", "호두", "은행", "도토리",
    "영지버섯", "팽이버섯", "목이버섯", "석이버섯", "운지버섯", "송이버섯", "표고버섯", "양송이버섯", "느타리버섯", "상황버섯", "아가리쿠스", "동충하초", "새송이버섯", "싸리버섯", "능이버섯",
    "수삼", "산양삼", "장뇌삼", "산삼배양근", "묘삼",
    "고사리", "취나물", "고비", "두릅", "죽순", "도라지", "더덕", "마",
    "쇠고기", "한우", "육우", "젖소", "양고기", "염소", "돼지고기", "멧돼지", "닭고기", "오리고기", "사슴고기", "토끼고기", "칠면조고기", "메추리고기", "말고기", "육류의 부산물",
    "국화", "카네이션", "장미", "백합", "글라디올러스", "튜울립", "거베라", "아이리스", "프리지아", "칼라", "안개꽃",
    "벌꿀", "건조누에", "프로폴리스",
    "계란", "오리알", "메추리알",
    "뽕잎", "누에번데기", "초콜릿", "치즈",
    "고등어", "명태", "갈치", "조기", "참치", "연어", "대구", "방어", "참돔", "새우", "오징어", "낙지", "홍합", "바지락", "전복", "게",
    "다시마", "미역", "김", "톳", "매생이", "어묵", "가리비 관자"
]

# 표시 금지 문구 (사용 조건을 만족하지 않으면 라벨에 쓸 수 없는 문구)
FORBIDDEN_PHRASES = ['천연', '자연', '슈퍼', '생명']

# 알레르기 유발요소 키워드 매핑 (원재료명 텍스트에서 알레르기 성분을 검출하는 데 사용)
ALLERGEN_KEYWORDS = {
    '알류': ['달걀', '계란', '오리알', '메추리알', '전란', '전란액', '전란유', '전란분', '난백', '난백액', '난백분', '난황', '난황액', '난황분', '난황유', '거위알', '알부민', '레시틴(난황)', '라이소자임', '난류', 'egg', 'lysozyme'],
    '우유': ['우유', '원유', '산양유', '유청', '유청단백', '카제인', '카제인나트륨', '유당', '치즈', '버터', '크림', '생크림', '사워크림', '유크림', '연유', '분유', '전지분유', '탈지분유', '요구르트', 'milk', 'dairy', 'whey protein', 'sodium caseinate'],
    '메밀': ['메밀', '메밀가루', '메밀묵', 'buckwheat'],
    '밀': ['밀', '밀가루', '통밀', '글루텐', '세몰리나', '듀럼밀', '소맥', '부침가루', '튀김가루', '밀기울', '스펠트밀', 'wheat', 'gluten', 'wheat bran', 'spelt'],
    '대두': ['대두', '대두콩', '노란콩', '콩나물', '두부', '두유', '된장', '간장', '고추장', '콩가루', '콩기름', '대두유', '대두단백', '레시틴', '대두레시틴', 'soy', 'soybean', 'soy lecithin'],
    '땅콩': ['땅콩', '땅콩버터', '땅콩기름', '낙화생', 'peanut', 'peanuts'],
    '호두': ['호두', '호두유', 'walnut', 'walnuts'],
    '잣': ['잣', 'pine nuts', 'pine nut'],
    '쇠고기': ['쇠고기', '소고기', '우육', '소 내장', '곱창', '대창', '사골', '우족', '쇠고기추출물', '소고기육수', '사골육수', '소육수', '우지', '젤라틴', 'beef', 'tallow'],
    '돼지고기': ['돼지고기', '돈육', '돼지 내장', '돈골', '돈족', '베이컨', '햄', '소시지', '돈지', '젤라틴', 'pork', 'lard'],
    '닭고기': ['닭고기', '계육', '닭 내장', '닭발', '닭 육수', 'chicken'],
    '고등어': ['고등어', 'mackerel'],
    '게': ['게', '꽃게', 'crab'],
    '새우': ['새우', 'shrimp', 'prawns'],
    '오징어': ['오징어', 'squid'],
    '조개류': ['굴', '전복', '홍합', '꼬막', '바지락', '가리비', '소라', '재첩', '백합', '키조개', 'shellfish', 'clam', 'oyster'],
    '복숭아': ['복숭아', 'peach', 'peaches'],
    '토마토': ['토마토', '토마토 페이스트', '토마토 케첩', '토마토 퓌레', 'tomato', 'tomatoes'],
    '아황산류': ['아황산나트륨', '메타중아황산칼륨', '무수아황산', '산성아황산나트륨', '이산화황', 'sulfite', 'sulfur dioxide'],
}

# 분리배출마크 <-> 포장재질 키워드 호환성 매핑
#
# 영문 코드는 **낱말 단위로** 견준다(check_recycling_mark). 그냥 포함으로 보면
# "PET" 안에 "PE" 가 들어 있어서, PET 용기에 PE 마크를 찍어도 통과해 버린다.
#
# PE 는 분리배출 표시가 정한 일곱 재질(PET/HDPE/LDPE/PP/PS/PVC/OTHER)에 없다.
# 라벨에 "PE" 라고만 적힌 것은 HDPE 인지 LDPE 인지 가려지지 않은 것이라,
# 그 셋(HDPE·LDPE·기타) 어느 쪽으로 표시해도 어긋났다고 볼 수 없다.
RECYCLING_MARK_MATERIAL_KEYWORDS = {
    '무색페트': ['pet', '페트', '무색'],
    '유색페트': ['pet', '페트', '유색'],
    '플라스틱(PET)': ['pet', '페트'],
    '플라스틱(LDPE)': ['ldpe', '저밀도', '폴리에틸렌', 'pe'],
    '플라스틱(HDPE)': ['hdpe', '고밀도', '폴리에틸렌', 'pe'],
    '플라스틱(PP)': ['pp', '피피', '폴리프로필렌'],
    '플라스틱(PS)': ['ps', '피에스', '폴리스티렌'],
    '기타플라스틱': ['기타', '플라스틱', 'other', 'pe', '폴리에틸렌'],
    '캔류(철)': ['철', 'steel', '캔'],
    '캔류(알미늄)': ['알미늄', '알루미늄', 'aluminum', 'al', '캔'],
    '유리': ['유리', 'glass'],
    '복합재질': ['복합재질', '도포', '첩합', '코팅'],
    '비닐(PET)': ['비닐', 'pet', '페트'],
    '비닐(HDPE)': ['비닐', 'hdpe', '고밀도'],
    '비닐(LDPE)': ['비닐', 'ldpe', '저밀도'],
    '비닐(PP)': ['비닐', 'pp', '폴리프로필렌'],
    '비닐(PS)': ['비닐', 'ps', '폴리스티렌'],
    '비닐(기타)': ['비닐', '기타'],
}