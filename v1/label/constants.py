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
    # 식품유형별 필수 표시 문구.
    #
    # **이 표는 서버에 없었다.** static/js/label/constants.js 에만 있었고,
    # 그래서 규정 검증이 화면에서만 돌았다. 로그인 없이 누구나 받는 파일에
    # 표가 통째로 들어 있었던 것도 그 때문이다.
    #
    # 판정은 부분 문자열이다 — 식품유형에 이 열쇠말이 들어 있으면 걸린다
    # (예: "과ㆍ채가공품(살균제품/산성통조림)" 은 그 이름 그대로 들어와야
    # 걸리고, "냉동식품" 은 "냉동식품(기타)" 에도 걸린다).
    'food_type_phrases': {
        '과ㆍ채가공품(살균제품/산성통조림)': ['캔주의'],
        '유함유가공품': ['알레르기 주의'],
        '고카페인': ['어린이, 임산부, 카페인 민감자는 섭취에 주의'],
        '젤리/곤약': ['질식주의'],
        '방사선 조사': ['감마선/전자선으로 조사처리'],
        '냉동식품': ['해동 후 재냉동 금지'],
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
# 영양성분 허용오차 —「식품등의 표시기준」
#
# 실측값과 표시값이 얼마나 벌어져도 되는지를 규정이 **한쪽 방향으로만** 정해
# 두었다. 그래서 이론치로 표를 만들 때 안전한 쪽이 성분마다 반대다.
#
#   열량·나트륨·당류·지방·트랜스지방·포화지방·콜레스테롤
#       실측값이 표시량의 **120% 미만**이어야 한다
#       -> 표시값을 이론치보다 **높여** 적어야 안전하다
#
#   탄수화물·식이섬유·단백질·비타민·무기질
#       실측값이 표시량의 **80% 이상**이어야 한다
#       -> 표시값을 이론치보다 **낮춰** 적어야 안전하다
#
# 현장에서 쓰는 엑셀은 앞 무리에만 +15% 를 곱하고 뒤 무리는 그대로 둔다.
# 그러면 실측이 표시량의 80% 밑으로 떨어질 위험이 남는데, 그 위험을 보는
# 사람이 아무도 없었다. 여기서 두 방향을 함께 정한다.
# ─────────────────────────────────────────────────────────────────────────

# 표시값을 높여 적어야 안전한 성분 (실측 120% 미만)
NUTRITION_TOLERANCE_UP = (
    'calories', 'natriums', 'sugars', 'fats', 'trans_fats',
    'saturated_fats', 'cholesterols',
)

# 규정이 준 폭. 이보다 크게 잡으면 표시값이 사실에서 멀어진다 — 허용오차는
# 표시를 부풀리라고 있는 것이 아니라 측정과 배치의 흔들림을 감싸는 폭이다.
NUTRITION_TOLERANCE_LIMIT = 20

# 흔히 쓰는 보정폭. 규정 폭(20%) 안에서 여유를 둔 값이다.
NUTRITION_TOLERANCE_DEFAULT = 15


# ─────────────────────────────────────────────────────────────────────────
# 열량 산출 계수 —「식품등의 표시기준」
#
# 탄수화물·단백질 4, 지방 9 만 알고 있었는데 규정은 다섯 가지를 더 정한다.
# 식이섬유와 당알코올은 **탄수화물 안에 들어 있으면서 계수가 다르다** —
# 탄수화물에서 그만큼을 빼고 각자의 계수로 세야 한다. 이 둘을 무시하면
# 식이섬유가 많은 제품에서 열량이 실제보다 높게 계산된다.
# ─────────────────────────────────────────────────────────────────────────
CALORIE_FACTORS = {
    'carbohydrates': 4.0,    # 식이섬유·당알코올을 뺀 나머지
    'dietary_fiber': 2.0,
    'sugar_alcohols': 2.4,
    'proteins': 4.0,
    'fats': 9.0,
    'organic_acids': 3.0,
    'alcohol': 7.0,
}


# ─────────────────────────────────────────────────────────────────────────
# 고열량·저영양 식품 영양성분 기준 —「어린이 식생활안전관리 특별법」고시
#
# **1회 제공량 기준**이다. 우리 저장값은 100 g 당이므로 1회 섭취참고량으로
# 환산한 뒤에 견줘야 한다.
#
# 한 규칙은 조건을 **모두** 만족해야 걸린다. 조건 하나짜리 규칙도 있다.
#   (성분, 부호, 값)
# ─────────────────────────────────────────────────────────────────────────
HIENG_LNTRT_CRITERIA = {
    'snack': (
        (('calories', '>', 250), ('proteins', '<', 2)),
        (('saturated_fats', '>', 4), ('proteins', '<', 2)),
        (('sugars', '>', 17), ('proteins', '<', 2)),
        (('calories', '>', 500),),
        (('saturated_fats', '>', 8),),
        (('sugars', '>', 34),),
    ),
    'meal': (
        (('calories', '>', 500), ('proteins', '<', 9)),
        (('calories', '>', 500), ('natriums', '>', 600)),
        (('saturated_fats', '>', 4), ('proteins', '<', 9)),
        (('saturated_fats', '>', 4), ('natriums', '>', 600)),
        (('calories', '>', 1000),),
        (('saturated_fats', '>', 8),),
    ),
}

HIENG_LNTRT_KIND_NAMES = {'snack': '간식용', 'meal': '식사대용'}

# 용기면 중 유탕면·국수류는 나트륨 기준이 다르다.
HIENG_LNTRT_SODIUM_NOODLE = 1000


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

# ─────────────────────────────────────────────────────────────────────────
# "○○산" 인데 원산지가 아닌 말.
#
# 원산지 강조 표시 검사는 원재료명에서 `○○산` 을 찾아 "국가명으로 알아보지
# 못했다" 고 알린다. 그런데 **식품 원료에는 산으로 끝나는 이름이 아주 많다** —
# 초산·젖산·구연산… 운영에서 "초산, 젖산을 국가명으로 알아보지 못했습니다"
# 라는 지적이 실제로 나왔다. 고칠 방법이 없는 경고다.
#
# 첨가물 공전(FoodAdditive)에 있는 이름은 코드가 DB 에서 합쳐 쓴다. 여기에는
# **DB 가 비어 있어도 걸러야 하는 것**만 둔다 — 표가 없으면 검사가 조용히
# 오탐을 쏟는다.
# ─────────────────────────────────────────────────────────────────────────
ORIGIN_FALSE_FRIENDS = frozenset({
    # 유기산
    '초산', '아세트산', '젖산', '구연산', '사과산', '주석산', '말산', '푸마르산',
    '아디프산', '호박산', '글루콘산', '글루탐산', '이노신산', '구아닐산',
    '소르빈산', '안식향산', '프로피온산', '아스코르브산', '엽산', '판토텐산',
    # 지방산
    '지방산', '스테아르산', '올레산', '리놀레산', '리놀렌산', '팔미트산',
    '라우르산', '미리스트산', '카프릴산', '카프르산', '아라키돈산',
    # 무기산·기타
    '인산', '황산', '아황산', '염산', '탄산', '규산', '질산', '아질산',
    '메타인산', '피로인산', '폴리인산',
})

# 표시 금지 문구 (사용 조건을 만족하지 않으면 라벨에 쓸 수 없는 문구)
# ─────────────────────────────────────────────────────────────────────────
# 부당한 표시·광고 키워드 — **법정 금지어만.**
#
# 예전에는 `FORBIDDEN_PHRASES` 네 단어였고 걸리면 전부 같은 무게로 막았다.
# 이제 등급이 있다(label.models.AdKeyword 주석 참고).
#
#   RED     어떤 경우에도 쓸 수 없다      -> 지적. 확정을 막는다
#   YELLOW  근거가 있으면 쓸 수 있다      -> 막지 않고 조건을 보여 준다
#   GREEN   써도 되는 말                  -> 세지 않는다. **예외 사전이다**
#
# **여기는 코드에 둔다.** 데이터로만 두면 행이 지워졌을 때 검사가 조용히 죽고,
# 시험(마이그레이션을 끄고 돈다)에서도 사라진다. 회사마다 다른 사내 기준은
# AdKeyword 테이블에 얹는다 — 법에 없는 말까지 공용 기본으로 깔면 다른 회사에
# 틀린 규칙이 된다.
#
# 네 단어를 전부 RED 로 둔 것은 **지금 동작 그대로**다. '천연'·'자연' 은 성격상
# 조건부(YELLOW)에 가깝지만, 지금은 걸리면 확정을 막는다. 등급을 내리는 것은
# 규정 해석이 딸린 결정이라 코드가 혼자 정할 일이 아니다.
# ─────────────────────────────────────────────────────────────────────────
NATURAL_CONDITIONS_KO = (
    '사용 조건: '
    '① 원료 중에 합성향료·합성착색료·방부제 등 어떠한 인공 화학 성분도 전혀 포함되어 있지 않아야 함 '
    '② 최소한의 물리적 가공(세척·절단·동결·건조 등)만 거친 상태여야 함 '
    '③ "천연"과 유사한 의미로 오인될 수 있는 "자연산(naturel)" 등의 외국어 사용도 동일 기준 적용 '
    '④ 식품유형별로 별도 금지 사항(「식품등의 표시기준」의 개별 고시 규정)이 있는 경우, 그 규정에 따라 추가 제한이 있음 '
    '⑤ 예: 설탕에는 "천연설탕"이라는 표현이 불가 '
    '⑥ 영업소 명칭 또는 등록상표에 포함된 경우는 허용 '
    '⑦ "천연향료" 등 고시된 허용 목록 내 용어만 예외적으로 허용'
)
NATURE_CONDITIONS_KO = (
    '사용 조건: '
    '① "자연"이라는 용어는 가공되지 않은 농산물·임산물·수산물·축산물에 대해서만 허용 '
    '② 수확하여 세척·포장만 거친 원물(raw agricultural/seafood/livestock products)에만 허용 '
    '③ 이미 "가공식품"으로 분류된 상태라면 "자연" 표기가 불가능 '
    '④ 유전자변형식품, 나노식품 등은 "자연" 표기가 금지됨 '
    '⑤ 영업소 명칭 또는 등록상표에 포함된 경우는 허용 '
    '⑥ 단, 제품명(product name) 자체에 "천연"·"자연"을 붙일 수는 없음'
)
AD_KEYWORDS_BUILTIN = [
    {'grade': 'RED', 'keyword': '천연', 'match': ['천연'],
     'note': NATURAL_CONDITIONS_KO},
    {'grade': 'RED', 'keyword': '자연', 'match': ['자연'],
     'note': NATURE_CONDITIONS_KO},
    {'grade': 'RED', 'keyword': '슈퍼', 'match': ['슈퍼'], 'note': ''},
    {'grade': 'RED', 'keyword': '생명', 'match': ['생명'], 'note': ''},
    # 금지 글자를 품고 있지만 고시된 표준 용어다. "자연치즈" 는 식품유형
    # 이름이고 "천연향료" 는 식품첨가물 공전의 명칭이다 — 규정대로 적은
    # 라벨을 지적하면 고치라는 대로 고칠 수가 없다.
    {'grade': 'GREEN', 'keyword': '자연치즈', 'match': ['자연치즈'], 'note': ''},
    {'grade': 'GREEN', 'keyword': '천연향료', 'match': ['천연향료'], 'note': ''},
]

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
    '비닐(HDPE)': ['비닐', 'hdpe', '고밀도', 'pe'],
    '비닐(LDPE)': ['비닐', 'ldpe', '저밀도', 'pe'],
    '비닐(PP)': ['비닐', 'pp', '폴리프로필렌'],
    '비닐(PS)': ['비닐', 'ps', '폴리스티렌'],
    # 비닐(기타) = 비닐류 + OTHER. 필름은 대부분 여러 수지를 겹쳐 만들고(PE/PET/NY
    # 첩합), 재질을 가릴 수 없으면 OTHER 로 표시하는 것이 분리배출 표시 기준이다.
    # 그래서 포장재질에 "PE" 라고만 적힌 필름 포장은 비닐+OTHER 로 표시해도 맞다 -
    # 기타플라스틱이 같은 이유로 이미 'pe' 를 받고 있었는데 비닐 쪽만 빠져 있었다.
    '비닐(기타)': ['비닐', '기타', 'other', 'pe', '폴리에틸렌', '필름', 'film',
                   'ny', '나일론', 'pa'],
}

# 표시사항 표에 인쇄되는 항목. 인쇄 순서와 같다.
#
# **표에 줄이 생기는 기준은 표시 항목 체크(chckd_*) 하나뿐이다.** 예전에는
# "값이 있으면 나간다" 였는데, 규정 검증은 체크를 근거로 판정해서 두 화면이
# 서로 다른 말을 했다 — 끈 항목이 인쇄되고, 켠 항목이 비어 있어도 아무 데도
# 안 보였다.
#
# 여기 없는 값은 인쇄 대상이 아니다.
#   my_label_name  라벨명은 내부에서 부르는 이름이지 라벨에 찍는 글자가 아니다
#   rawmtrl_nm     원재료명(참고). 인쇄되는 것은 rawmtrl_nm_display 쪽이다
#   nutrition_text 영양성분은 별도 표로 그린다 (chckd_nutrition_text 는 표시
#                  여부와 규정 검증에만 쓰인다)
PREVIEW_DISPLAY_FIELDS = (
    'prdlst_dcnm', 'prdlst_nm', 'ingredient_info', 'content_weight',
    'weight_calorie', 'prdlst_report_no', 'country_of_origin',
    'storage_method', 'frmlc_mtrqlt', 'bssh_nm', 'distributor_address',
    'repacker_address', 'importer_address', 'pog_daycnt',
    'rawmtrl_nm_display', 'cautions', 'additional_info',
)


def preview_display_data(label, format_text=None):
    """
    표시사항 표에 넘길 {필드: 값}. 인쇄 대상 항목 **전부**를 담는다.

    끈 항목의 값도 함께 보낸다 — 미리보기의 항목 목록에서 다시 켤 수 있어야
    하고, 켜는 순간 무엇이 인쇄될지 그 자리에서 보여야 한다. 무엇이 실제로
    표에 나가는지는 preview_display_checked 가 정한다.

    원재료명(표시)이 비면 원재료명(참고)로 갈음한다. V2 기본정보 탭과 BOM
    "기본정보로 복사" 가 참고 쪽에 쓰는데, 인쇄물에는 한 줄로 나가야 한다.
    """
    data = {}
    for field in PREVIEW_DISPLAY_FIELDS:
        value = getattr(label, field, '') or ''
        if field == 'rawmtrl_nm_display' and not value:
            value = getattr(label, 'rawmtrl_nm', '') or ''
        if value and format_text and field in ('cautions', 'additional_info'):
            value = format_text(value)
        data[field] = value
    return data


# 표의 줄은 아니지만 같은 스위치로 켜고 끄는 것. 영양성분은 표 아래 별도
# 블록(영양정보 표)으로 그려진다 — 자리는 다르지만 "인쇄할까" 를 정하는
# 스위치는 chckd_nutrition_text 하나여야 한다.
PREVIEW_EXTRA_CHECK_FIELDS = ('nutrition_text',)


def preview_display_checked(label):
    """{필드: 표시 항목 체크가 켜졌는가}. 미리보기에 무엇이 나갈지의 유일한 기준."""
    return {field: (getattr(label, f'chckd_{field}', '') or '') == 'Y'
            for field in PREVIEW_DISPLAY_FIELDS + PREVIEW_EXTRA_CHECK_FIELDS}
