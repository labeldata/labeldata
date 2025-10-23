// constants.js - 프론트엔드 전용 상수

// === 프론트엔드 데이터 목록 (정적 데이터) ===

// 농수산물 목록 (원산지 표시 대상)
const FARM_SEAFOOD_ITEMS = [
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
];

// === UI 관련 정적 데이터 ===

// 표시 금지 문구 목록
const FORBIDDEN_PHRASES = [
    '천연', '자연', '슈퍼', '생명'
];

// 분리배출마크 그룹 (간단 버전)
const RECYCLING_MARK_GROUPS = [
    '플라스틱', '종이', '유리', '금속', '비닐'
];

// 분리배출마크 매핑
const RECYCLING_MARK_MAP = {
    '플라스틱': 'PET', 
    '종이': 'PAPER', 
    '유리': 'GLASS', 
    '금속': 'METAL', 
    '비닐': 'VINYL'
};

// === 프론트엔드 기본 설정값 ===

// UI 기본 설정값 (초기 로드용)
const DEFAULT_SETTINGS = {
    width: 10,
    height: 11,
    fontSize: 10,
    letterSpacing: -5,
    lineHeight: 1.2,
    fontFamily: "'Noto Sans KR'"
};

// === 표시사항 규정 상수 (백엔드에서 전달받을 예정) ===
// 주의: 이 상수들은 향후 서버에서 동적으로 로드하도록 변경 예정

const REGULATIONS = {
    area_thresholds: { 
        small: 100, 
        medium: 3000, 
        large: 3000 
    },
    font_size: { 
        product_name: { min: 16, small_area_min: 10 }, 
        origin: { min: 14, small_area_min: 10 }, 
        content_weight: { min: 12, small_area_min: 10 }, 
        general: { min: 10, small_area_min: 10 } 
    },
    spacing: {
        letter: { default: -5, min: -10, max: 10 },
        line: { default: 1.2, min: 1.0, max: 3.0 },
        word: { min: 90, small_area_min: 50 }
    },
    // 식품유형별 필수 표시 문구
    food_type_phrases: { 
        "과ㆍ채가공품(살균제품/산성통조림)": ["캔주의"], 
        "유함유가공품": ["알레르기 주의"], 
        "고카페인": ["어린이, 임산부, 카페인 민감자는 섭취에 주의"], 
        "젤리/곤약": ["질식주의"], 
        "방사선 조사": ["감마선/전자선으로 조사처리"], 
        "냉동식품": ["해동 후 재냉동 금지"] 
    }
};

// === 상세 UI 데이터 ===

// 분리배출마크 그룹 (상세 정보 포함)
const RECYCLING_MARK_GROUPS_DETAILED = [
    { 
        group: '플라스틱', 
        options: [ 
            { value: '무색페트', label: '무색페트', img: '/static/img/recycle_clearpet.png' }, 
            { value: '유색페트', label: '유색페트', img: '/static/img/recycle_pet.png' },
            { value: '플라스틱(PET)', label: '플라스틱(PET)', img: '/static/img/recycle_pet.png' }, 
            { value: '플라스틱(HDPE)', label: '플라스틱(HDPE)', img: '/static/img/recycle_hdpe.png' },
            { value: '플라스틱(LDPE)', label: '플라스틱(LDPE)', img: '/static/img/recycle_ldpe.png' },
            { value: '플라스틱(PP)', label: '플라스틱(PP)', img: '/static/img/recycle_pp.png' },
            { value: '플라스틱(PS)', label: '플라스틱(PS)', img: '/static/img/recycle_ps.png' },
            { value: '기타플라스틱', label: '기타플라스틱', img: '/static/img/recycle_other_plastic.png' }
        ]
    },
    { 
        group: '종이', 
        options: [
            { value: '종이', label: '종이', img: '/static/img/recycle_paper.png' },
            { value: '일반팩', label: '일반팩', img: '/static/img/recycle_pack.png' },
            { value: '멸균팩', label: '멸균팩', img: '/static/img/recycle_sterilized_pack.png' }
        ]
    },
    { 
        group: '금속', 
        options: [
            { value: '캔류(철)', label: '캔류(철)', img: '/static/img/recycle_can_steel.png' },
            { value: '캔류(알미늄)', label: '캔류(알미늄)', img: '/static/img/recycle_can_aluminum.png' }
        ]
    },
    { 
        group: '유리', 
        options: [
            { value: '유리', label: '유리', img: '/static/img/recycle_glass.png' }
        ]
    },
    { 
        group: '비닐', 
        options: [
            { value: '비닐(PET)', label: '비닐(PET)', img: '/static/img/recycle_vinyl_pet.png' },
            { value: '비닐(HDPE)', label: '비닐(HDPE)', img: '/static/img/recycle_vinyl_hdpe.png' },
            { value: '비닐(LDPE)', label: '비닐(LDPE)', img: '/static/img/recycle_vinyl_ldpe.png' },
            { value: '비닐(PP)', label: '비닐(PP)', img: '/static/img/recycle_vinyl_pp.png' },
            { value: '비닐(PS)', label: '비닐(PS)', img: '/static/img/recycle_vinyl_ps.png' },
            { value: '비닐(기타)', label: '비닐(기타)', img: '/static/img/recycle_vinyl_other.png' },
            { value: '복합재질', label: '복합재질', img: '/static/img/recycle_composite.png' }
        ]
    }
];

// === 영양성분 관련 데이터 ===

// 영양성분 정의 (MFDS 2024 기준, 한눈에 보는 영양표시 가이드라인 순서)
const NUTRITION_DATA = {
  // 필수 영양성분 (9가지)
  'calories': { label: '열량', unit: 'kcal', order: 1, required: true, daily_value: null },
  'natriums': { label: '나트륨', unit: 'mg', order: 2, required: true, daily_value: 2000 },
  'carbohydrates': { label: '탄수화물', unit: 'g', order: 3, required: true, daily_value: 324 },
  'sugars': { label: '당류', unit: 'g', order: 4, parent: 'carbohydrates', indent: true, required: true, daily_value: 100 },
  'fats': { label: '지방', unit: 'g', order: 5, required: true, daily_value: 54 },
  'trans_fats': { label: '트랜스지방', unit: 'g', order: 6, parent: 'fats', indent: true, required: true, daily_value: null },
  'saturated_fats': { label: '포화지방', unit: 'g', order: 7, parent: 'fats', indent: true, required: true, daily_value: 15 },
  'cholesterols': { label: '콜레스테롤', unit: 'mg', order: 8, required: true, daily_value: 300 },
  'proteins': { label: '단백질', unit: 'g', order: 9, required: true, daily_value: 55 },
  
  // 추가 영양성분 (식약처 기준)
  'dietary_fiber': { label: '식이섬유', unit: 'g', order: 10, daily_value: 25 },
  'calcium': { label: '칼슘', unit: 'mg', order: 11, daily_value: 700 },
  'iron': { label: '철', unit: 'mg', order: 12, daily_value: 12 },
  'magnesium': { label: '마그네슘', unit: 'mg', order: 13, daily_value: 315 },
  'phosphorus': { label: '인', unit: 'mg', order: 14, daily_value: 700 },
  'potassium': { label: '칼륨', unit: 'mg', order: 15, daily_value: 3500 },
  'zinc': { label: '아연', unit: 'mg', order: 16, daily_value: 8.5 },
  'vitamin_a': { label: '비타민A', unit: 'μg RAE', order: 17, daily_value: 700 },
  'vitamin_d': { label: '비타민D', unit: 'μg', order: 18, daily_value: 10 },
  'vitamin_e': { label: '비타민E', unit: 'mg α-TE', order: 19, daily_value: 12 },
  'vitamin_c': { label: '비타민C', unit: 'mg', order: 20, daily_value: 100 },
  'thiamine': { label: '티아민', unit: 'mg', order: 21, daily_value: 1.2 },
  'riboflavin': { label: '리보플라빈', unit: 'mg', order: 22, daily_value: 1.4 },
  'niacin': { label: '니아신', unit: 'mg NE', order: 23, daily_value: 15 },
  'vitamin_b6': { label: '비타민B6', unit: 'mg', order: 24, daily_value: 1.5 },
  'folic_acid': { label: '엽산', unit: 'μg DFE', order: 25, daily_value: 400 },
  'vitamin_b12': { label: '비타민B12', unit: 'μg', order: 26, daily_value: 2.4 },
  'selenium': { label: '셀레늄', unit: 'μg', order: 27, daily_value: 55 },
  'pantothenic_acid': { label: '판토텐산', unit: 'mg', order: 28, daily_value: 5 },
  'biotin': { label: '비오틴', unit: 'μg', order: 29, daily_value: 30 },
  'iodine': { label: '요오드', unit: 'μg', order: 30, daily_value: 150 },
  'vitamin_k': { label: '비타민K', unit: 'μg', order: 31, daily_value: 70 },
  'copper': { label: '구리', unit: 'mg', order: 32, daily_value: 0.8 },
  'manganese': { label: '망간', unit: 'mg', order: 33, daily_value: 3.0 },
  'chromium': { label: '크롬', unit: 'μg', order: 34, daily_value: 30 },
  'molybdenum': { label: '몰리브덴', unit: 'μg', order: 35, daily_value: 25 }
};

// 강조표시 기준 (식약처 기준)
const EMPHASIS_CRITERIA = {
  // 저 함유 기준 (100g 또는 100ml 기준)
  low: {
    'calories': { threshold: 40, label: '저열량' },
    'fats': { threshold: 3, label: '저지방' },
    'saturated_fats': { threshold: 1.5, label: '저포화지방' },
    'sugars': { threshold: 5, label: '저당' },
    'natriums': { threshold: 120, label: '저나트륨' },
    'cholesterols': { threshold: 20, label: '저콜레스테롤' }
  },
  // 무 함유 기준
  free: {
    'calories': { threshold: 4, label: '무열량' },
    'fats': { threshold: 0.5, label: '무지방' },
    'saturated_fats': { threshold: 0.1, label: '무포화지방' },
    'sugars': { threshold: 0.5, label: '무당' },
    'natriums': { threshold: 5, label: '무나트륨' },
    'cholesterols': { threshold: 2, label: '무콜레스테롤' }
  },
  // 고 함유 기준 (1일 기준치의 30% 이상)
  high: {
    'proteins': { threshold: 16.5, label: '고단백' },
    'dietary_fiber': { threshold: 7.5, label: '고식이섬유' },
    'calcium': { threshold: 210, label: '고칼슘' },
    'iron': { threshold: 3.6, label: '고철분' },
    'vitamin_e': { threshold: 3.6, label: '고비타민E' },
    'vitamin_c': { threshold: 30, label: '고비타민C' }
  }
};

// === 알레르기 유발요소 데이터 ===

// 알레르기 키워드 매핑 (19개 공식 알레르기 유발요소) + 검증 오류 방지를 위한 키워드 변경
const ALLERGEN_KEYWORDS = {
    // 수정: '난류' → '알류', '난류' 키워드 추가
    '알류': ['달걀', '계란', '오리알', '메추리알', '전란', '전란액', '전란유', '전란분', '난백', '난백액', '난백분', '난황', '난황액', '난황분', '난황유', '거위알', '알부민', '레시틴(난황)', '라이소자임', '난류', 'egg', 'lysozyme'],
    '우유': ['우유', '원유', '산양유', '유청', '유청단백', '카제인', '카제인나트륨', '유당', '치즈', '버터', '크림', '생크림', '사워크림', '유크림', '연유', '분유', '전지분유', '탈지분유', '요구르트', 'milk', 'dairy', 'whey protein', 'sodium caseinate'],
    '메밀': ['메밀', '메밀가루', '메밀묵', 'buckwheat'],
    '밀': ['밀', '밀가루', '통밀', '글루텐', '세몰리나', '듀럼밀', '소맥', '부침가루', '튀김가루', '밀기울', '스펠트밀', 'wheat', 'gluten', 'wheat bran', 'spelt'],
    // 수정: '콩' 키워드 제거 (완두콩과의 오탐 방지)
    '대두': ['대두', '대두콩', '노란콩', '콩나물', '두부', '두유', '된장', '간장', '고추장', '콩가루', '콩기름', '대두유', '대두단백', '레시틴', '대두레시틴', 'soy', 'soybean', 'soy lecithin'],
    '땅콩': ['땅콩', '땅콩버터', '땅콩기름', '낙화생', 'peanut', 'peanuts'],
    '호두': ['호두', '호두유', 'walnut', 'walnuts'],
    '잣': ['잣', 'pine nuts', 'pine nut'],
    // 수정: '육수' 키워드 제거 (멸치육수 등과의 오탐 방지), '육류 육수' 키워드 추가
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
    '아황산류': ['아황산나트륨', '메타중아황산칼륨', '무수아황산', '산성아황산나트륨', '이산화황', 'sulfite', 'sulfur dioxide']
};

/**
 * 알레르기 성분 동의어 검색 함수 (키워드 검색 -> 알레르기 그룹 동의어 반환)
 */
function findAllergenSynonyms(keyword) {
    const lowerKeyword = keyword.toLowerCase();
    
    for (const [allergen, keywords] of Object.entries(ALLERGEN_KEYWORDS)) {
        const foundKeyword = keywords.find(k => k.toLowerCase() === lowerKeyword);
        if (foundKeyword) {
            return {
                allergen: allergen,
                synonyms: keywords
            };
        }
    }
    return null;
}

// === 전역 객체로 내보내기 ===

// 통합된 라벨 상수 객체
window.LABEL_CONSTANTS = {
    // 정적 데이터
    farmSeafoodItems: FARM_SEAFOOD_ITEMS,
    forbiddenPhrases: FORBIDDEN_PHRASES,
    allergenKeywords: ALLERGEN_KEYWORDS,
    
    // 영양성분 관련
    nutritionData: NUTRITION_DATA,
    emphasisCriteria: EMPHASIS_CRITERIA,
    
    // UI 관련
    recyclingMarkGroups: RECYCLING_MARK_GROUPS,
    recyclingMarkMap: RECYCLING_MARK_MAP,
    recyclingMarkGroupsDetailed: RECYCLING_MARK_GROUPS_DETAILED,

    // 설정값 (프론트엔드 전용)
    defaultSettings: DEFAULT_SETTINGS,
    regulations: REGULATIONS  // 추후 서버에서 동적 로드 예정
};

// === 기존 코드 호환성 유지 ===
// 개별 상수들도 전역으로 내보내기 (기존 JavaScript 코드 호환성)
window.farmSeafoodItems = FARM_SEAFOOD_ITEMS;
window.forbiddenPhrases = FORBIDDEN_PHRASES;
window.recyclingMarkGroups = RECYCLING_MARK_GROUPS;
window.recyclingMarkMap = RECYCLING_MARK_MAP;
window.DEFAULT_SETTINGS = DEFAULT_SETTINGS;
window.REGULATIONS = REGULATIONS;
window.recyclingMarkGroupsDetailed = RECYCLING_MARK_GROUPS_DETAILED;
window.allergenKeywords = ALLERGEN_KEYWORDS;
window.findAllergenSynonyms = findAllergenSynonyms;
// 영양성분 관련 상수 추가
window.NUTRITION_DATA = NUTRITION_DATA;
window.EMPHASIS_CRITERIA = EMPHASIS_CRITERIA;