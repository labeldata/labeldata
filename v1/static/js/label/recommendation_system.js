/**
 * 간단한 기본 추천 시스템
 * 복잡한 스마트추천 시스템을 대체하는 기본적인 추천 기능
 */

class BasicRecommendationSystem {
    constructor() {
        this.smartApiUrl = '/label/api/auto-fill/';
        this.phraseApiUrl = '/label/api/phrases/';
        this.recentUsageKey = 'labeldata_recent_phrases';
        this.maxRecentItems = 3;
        
        this.recommendations = {
            // 라벨명 기본 추천 (10개)
            my_label_name_top: [
                "딸기잼", "블루베리잼", "복숭아잼", "포도잼", "사과잼",
                "오렌지마멀레이드", "레몬마멀레이드", "체리잼", "살구잼", "키위잼"
            ],
            
            // 식품군 기본 추천 (10개)
            food_group: [
                "과자류", "빵류", "떡류", "음료류", "차류", 
                "커피", "주류", "소스류", "젓갈류", "장류"
            ],
            
            // 원재료명 표시용 기본 추천 (10개)
            rawmtrl_nm_display: [
                "설탕, 딸기농축액, 펙틴, 구연산",
                "밀가루, 설탕, 버터, 달걀, 바닐라향",
                "쌀, 콩, 소금, 식용유",
                "우유, 설탕, 생크림, 젤라틴",
                "돼지고기, 소금, 후추, 마늘, 양파",
                "토마토, 양파, 마늘, 올리브오일, 바질",
                "닭고기, 간장, 설탕, 마늘, 생강",
                "감자, 당근, 양파, 소고기, 소금",
                "새우, 마늘, 버터, 파슬리, 레몬",
                "연어, 소금, 후추, 딜, 레몬"
            ],
            
            // 주의사항 기본 추천 (constants.py 기반)
            cautions: [
                "부정·불량식품신고는 국번없이 1399",
                "이 제품은 알레르기 유발물질(알류, 우유, 땅콩, 대두, 밀, 돼지고기, 복숭아, 토마토, 호두, 닭고기, 쇠고기, 오징어, 조개류 등)을 사용한 제품과 같은 제조시설에서 제조되었습니다.",
                "알레르기 유발물질(알류, 우유, 대두, 밀, 땅콩 등)이 혼입될 수 있으니 주의하시기 바랍니다.",
                "이 제품은 냉동식품을 해동한 제품이니 재냉동시키지 마시길 바랍니다.",
                "개봉 후에는 냉장 보관하시고, 가급적 빠른 시일 내에 드시기 바랍니다.",
                "어린이, 임산부, 카페인 민감자는 섭취에 주의해 주시기 바랍니다. 고카페인 함유",
                "경고 : 지나친 음주는 뇌졸중, 기억력 손상이나 치매를 유발합니다. 임신 중 음주는 기형아 출생 위험을 높입니다. 19세 미만 판매 금지",
                "얼려서 드시지 마십시오. 한 번에 드실 경우 질식 위험이 있으니 잘 씹어 드십시오. 5세 이하 어린이 및 노약자는 섭취를 금하여 주십시오.",
                "개봉 시 캔 절단부분에 손이 닿지 않도록 각별히 주의하십시오.",
                "기계로 씨를 제거하는 과정에서 씨 또는 씨의 일부가 남아있을 수 있으니 주의해서 드세요."
            ],
            
            // 기타표시사항 기본 추천 (constants.py 기반)
            additional_info: [
                "반품 및 교환장소: 구입처 및 본사",
                "본 제품은 소비자분쟁해결기준에 의거 교환 또는 보상 받을 수 있습니다.",
                "이 제품에는 알코올이 포함되어 있습니다. 알코올 함량 ○○%",
                "유산균 100,000,000(1억) CFU/g, 유산균 1억 CFU/g",
                "조리 시 해동방법: 자연 해동 후 사용",
                "1일 2회, 1회 1포를 물과 함께 섭취하십시오.",
                "기호에 따라 물이나 우유에 타서 드세요.",
                "차갑게 또는 따뜻하게 음용 가능합니다.",
                "소비자상담실: 080-000-0000",
                "보관상태에 따라 유통기한 이내라도 변질될 수 있습니다."
            ],
            
            // 가공조건 기본 추천 (10개)
            processing_condition: [
                "85℃에서 15분간 살균",
                "121℃에서 4분간 멸균", 
                "냉동 -18℃ 이하 보관",
                "상온 유통 가능",
                "65℃에서 30분간 저온살균",
                "100℃에서 10분간 끓임 살균",
                "자외선 살균 처리",
                "고압 살균 처리",
                "진공포장 후 냉장보관",
                "질소충전 포장"
            ],
            
            // 라벨명 (숨겨진 필드) (10개)
            my_label_name: [
                "딸기잼", "블루베리잼", "복숭아잼", "포도잼", "사과잼",
                "오렌지마멀레이드", "레몬마멀레이드", "체리잼", "살구잼", "키위잼"
            ],
            
            // 식품유형 기본 추천 (10개)
            food_type: [
                "잼류", "시럽류", "당류", "조미료", "소스류", 
                "드레싱류", "절임식품", "발효식품", "냉동식품", "건조식품"
            ],
            
            // 보관방법 기본 추천 (constants.py 기반)
            storage_method: [
                "냉장 보관 (0~10℃)",
                "냉동 보관 (-18℃ 이하)",
                "직사광선을 피하고 서늘한 곳에 보관",
                "개봉 후에는 냉장 보관하고 가급적 빨리 섭취하십시오.",
                "습기를 피해 건조한 곳에 보관",
                "밀폐용기에 보관",
                "통풍이 잘 되는 곳에 보관",
                "냉암소 보관",
                "차가운 곳에 보관"
            ],
            
            // 내용량 기본 추천 (10개)
            content_weight: [
                "100g", "200g", "250g", "300g", "500g", 
                "1kg", "150g", "400g", "750g", "1.5kg"
            ],
            
            // 업체명 기본 추천 (10개)
            bssh_nm: [
                "(주)한국식품", "대한제과", "맛있는식품(주)", "우리농장",
                "신선식품", "건강한먹거리", "자연식품(주)", "프리미엄푸드",
                "전통식품", "글로벌푸드(주)"
            ],
            
            // 유통기한 기본 추천 (10개)
            pog_daycnt: [
                "제조일로부터 12개월",
                "제조일로부터 18개월", 
                "제조일로부터 24개월",
                "제조일로부터 6개월",
                "제조일로부터 3개월",
                "제조일로부터 9개월",
                "제조일로부터 15개월",
                "제조일로부터 30개월",
                "제조일로부터 2년",
                "제조일로부터 1년"
            ],
            
            // 제품명 기본 추천 (10개)
            prdlst_nm: [
                "딸기잼", "블루베리잼", "복숭아잼", "포도잼", "사과잼",
                "오렌지마멀레이드", "체리잼", "살구잼", "키위잼", "무화과잼"
            ],
            
            // 특정성분 함량 기본 추천 (10개)
            ingredient_info: [
                "설탕 50g/100g", "나트륨 150mg/100g", "단백질 5g/100g",
                "지방 2g/100g", "탄수화물 60g/100g", "식이섬유 3g/100g",
                "칼슘 100mg/100g", "철분 2mg/100g", "비타민C 10mg/100g",
                "콜레스테롤 0mg/100g"
            ],
            
            // 식품유형 상세 기본 추천 (10개)
            prdlst_dcnm: [
                "잼류", "시럽류", "당류", "조미료", "소스류", 
                "드레싱류", "절임식품", "발효식품", "냉동식품", "건조식품"
            ],
            
            // 품목보고번호 기본 추천 (10개)
            prdlst_report_no: [
                "20240001234", "20240005678", "20240009012", "20240003456",
                "20240007890", "20240002468", "20240008024", "20240004680",
                "20240006802", "20240001357"
            ],
            
            // 포장재질 기본 추천 (constants.py 기반)
            frmlc_mtrqlt: [
                "폴리에틸렌(PE)",
                "폴리프로필렌(PP)",
                "폴리에틸렌테레프탈레이트(PET)",
                "유리",
                "알루미늄",
                "철",
                "종이",
                "내포장재: 폴리에틸렌(PE), 외포장재: 종이",
                "기타",
                "복합재질(분리배출 요망)"
            ],

            // 식품유형 상세 기본 추천 (constants.py 기반)
            prdlst_dcnm: [
                "과ㆍ채가공품(살균제품/산성통조림)",
                "유함유가공품(72℃, 15초 살균)",
                "잼류",
                "시럽류",
                "당류",
                "조미료",
                "소스류",
                "드레싱류",
                "절임식품",
                "발효식품"
            ],

            // 특정성분 함량 기본 추천 (constants.py 기반)  
            ingredient_info: [
                "제품명 포함된 원료명 00%",
                "카페인 100mg",
                "설탕 50g/100g",
                "나트륨 150mg/100g",
                "단백질 5g/100g",
                "지방 2g/100g",
                "탄수화물 60g/100g",
                "식이섬유 3g/100g",
                "칼슘 100mg/100g",
                "철분 2mg/100g"
            ],

            // 내용량 기본 추천 (constants.py 기반)
            content_weight: [
                "내용량 ○○ml",
                "내용량 ○○g(고형물 00g)",
                "순중량 ○○g",
                "100g",
                "200g",
                "250g",
                "300g",
                "500g",
                "1kg",
                "1.5kg"
            ],

            // 유통기한 기본 추천 (constants.py 기반)
            pog_daycnt: [
                "제조일로부터 12개월",
                "-18℃이하 냉동보관시 제조일로부터 24개월",
                "유통기한: 별도 표시일까지",
                "제조일로부터 18개월",
                "제조일로부터 24개월",
                "제조일로부터 6개월",
                "제조일로부터 3개월",
                "제조일로부터 9개월",
                "제조일로부터 15개월",
                "제조일로부터 30개월"
            ]
        };
        
        this.init();
    }
    
    init() {
        // 기본 추천 시스템 초기화 완료
        this.setupFieldListeners();
        this.loadRecentUsage();
    }
    
    // 최근 사용 이력 로드
    loadRecentUsage() {
        try {
            const stored = localStorage.getItem(this.recentUsageKey);
            this.recentUsage = stored ? JSON.parse(stored) : {};
        } catch (error) {
            console.warn('최근 사용 이력 로드 실패:', error);
            this.recentUsage = {};
        }
    }
    
    // 최근 사용 이력 저장
    saveRecentUsage() {
        try {
            localStorage.setItem(this.recentUsageKey, JSON.stringify(this.recentUsage));
        } catch (error) {
            console.warn('최근 사용 이력 저장 실패:', error);
        }
    }
    
    // 최근 사용 문구 추가
    addToRecentUsage(fieldName, phrase) {
        // 안전한 문자열만 저장
        const safePhrase = typeof phrase === 'string' ? phrase : String(phrase);
        if (!safePhrase || safePhrase === '[object Object]' || safePhrase.trim() === '') {
            console.warn('유효하지 않은 문구는 최근 사용에 추가하지 않음:', phrase);
            return;
        }
        
        if (!this.recentUsage[fieldName]) {
            this.recentUsage[fieldName] = [];
        }
        
        // 주의사항과 기타표시사항은 | 기준으로 분리하여 각각 저장
        let phrasesToAdd = [];
        if (fieldName === 'cautions' || fieldName === 'additional_info') {
            const splitPhrases = safePhrase.split('|').map(p => p.trim()).filter(p => p.length > 0);
            phrasesToAdd = splitPhrases;
            // 문구 분리 완료
        } else {
            phrasesToAdd = [safePhrase];
        }
        
        // 각 문구를 개별적으로 추가
        phrasesToAdd.forEach(phraseToAdd => {
            // 중복 제거
            this.recentUsage[fieldName] = this.recentUsage[fieldName].filter(item => item !== phraseToAdd);
            
            // 최상단에 추가
            this.recentUsage[fieldName].unshift(phraseToAdd);
        });
        
        // 최대 개수 제한
        if (this.recentUsage[fieldName].length > this.maxRecentItems) {
            this.recentUsage[fieldName] = this.recentUsage[fieldName].slice(0, this.maxRecentItems);
        }
        
        this.saveRecentUsage();
        // 최근 사용 문구 추가 완료
    }
    
    // 최근 사용 문구 가져오기
    getRecentUsage(fieldName) {
        return this.recentUsage[fieldName] || [];
    }
    
    // 필드 카테고리 매핑 (내 문구 시스템과 동일)
    getFieldCategory(fieldName) {
        const categoryMap = {
            'my_label_name_top': 'product',
            'my_label_name': 'product',
            'rawmtrl_nm_display': 'ingredient',
            'cautions': 'caution',
            'additional_info': 'general',
            'processing_condition': 'processing',
            'food_group': 'category',
            'food_type': 'category',
            'storage_method': 'storage',
            'content_weight': 'weight',
            'bssh_nm': 'company',
            'pog_daycnt': 'expiry',
            // 실제 HTML 필드명들 매핑
            'prdlst_nm': 'product',
            'ingredient_info': 'ingredient',
            'prdlst_dcnm': 'category',
            'prdlst_report_no': 'general',
            'frmlc_mtrqlt': 'packaging'
        };
        
        return categoryMap[fieldName] || 'general';
    }
    
    // API에서 스마트 추천 문구 가져오기
    async loadSmartRecommendations(fieldName, currentValue = '') {
        try {
            const category = this.getFieldCategory(fieldName);
            
            // GET 방식으로 변경 (API가 @require_GET 사용)
            const params = new URLSearchParams({
                input_field: fieldName,
                input_value: currentValue || fieldName,
                category: category,
                priority: 'high'
            });
            
            const response = await fetch(`${this.smartApiUrl}?${params}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // API 응답 구조에 따라 안전하게 처리
                    let suggestions = [];
                    if (Array.isArray(data.suggestions)) {
                        suggestions = data.suggestions;
                    } else if (Array.isArray(data.data)) {
                        suggestions = data.data;
                    } else if (data.suggestions && typeof data.suggestions === 'object') {
                        suggestions = Object.values(data.suggestions).flat();
                    }
                    
                    // 모든 suggestion을 안전한 문자열로 변환
                    const safeSuggestions = suggestions.map(item => {
                        if (typeof item === 'string') {
                            return item;
                        } else if (item && item.text) {
                            return item.text;
                        } else if (item && item.name) {
                            return item.name;
                        } else if (item && item.phrase) {
                            return item.phrase;
                        } else {
                            return String(item);
                        }
                    }).filter(item => item && item !== '[object Object]' && item.trim() !== '');
                    
                    return safeSuggestions.slice(0, 3) || []; // 최대 3개
                }
                return [];
            } else {
                console.warn('스마트 추천 API 호출 실패:', response.status);
                return [];
            }
        } catch (error) {
            console.warn('스마트 추천 로드 중 오류:', error);
            return [];
        }
    }
    
    // CSRF 토큰 가져오기
    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }
    
    setupFieldListeners() {
        // 주요 필드들에 클릭 및 포커스 이벤트 리스너 추가
        const fields = [
            'my_label_name_top',      // 라벨명 (상단)
            'rawmtrl_nm_display',     // 원재료명 표시용
            'cautions',               // 주의사항  
            'additional_info',        // 기타정보
            'processing_condition',   // 가공조건
            'my_label_name',         // 라벨명 (숨겨진 필드)
            'food_group',            // 식품군
            'food_type',             // 식품유형
            'storage_method',        // 보관방법
            'content_weight',        // 내용량
            'bssh_nm',              // 업체명
            'pog_daycnt',           // 유통기한
            // 실제 HTML 필드명들 추가
            'prdlst_nm',            // 제품명
            'ingredient_info',      // 특정성분 함량
            'prdlst_dcnm',         // 식품유형
            'prdlst_report_no',    // 품목보고번호
            'frmlc_mtrqlt'         // 용기.포장재질
        ];
        
        fields.forEach(fieldName => {
            const field = document.querySelector(`[name="${fieldName}"]`);
            if (field) {
                // 클릭 이벤트 (readonly/disabled 필드에서도 작동)
                field.addEventListener('click', (e) => {
                    // 필드 클릭됨
                    this.showRecommendations(fieldName, e.target);
                });
                
                // 포커스 이벤트 (일반 필드용)
                field.addEventListener('focus', (e) => {
                    // 필드 포커스됨
                    this.showRecommendations(fieldName, e.target);
                });
                
                // 입력 시 추천 박스 숨김
                field.addEventListener('input', (e) => {
                    this.hideRecommendations();
                });
                
                // 입력 완료 시 최근 사용 문구로 저장 (blur 이벤트)
                field.addEventListener('blur', (e) => {
                    const value = e.target.value.trim();
                    if (value && value.length > 0) {
                        this.addToRecentUsage(fieldName, value);
                        // 사용자 입력 문구 저장
                    }
                });
                
                // Enter 키 입력 시 최근 사용 문구로 저장
                field.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        const value = e.target.value.trim();
                        if (value && value.length > 0) {
                            this.addToRecentUsage(fieldName, value);
                            // Enter로 입력 문구 저장
                        }
                        this.hideRecommendations();
                    }
                });
                
                // 필드에 추천 시스템 연결됨
            } else {
                // 필드를 찾을 수 없음
            }
        });
        
        // 문서 전체 클릭 시 추천 박스 숨김
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.basic-recommendation-box') && !fields.some(name => e.target.name === name)) {
                this.hideRecommendations();
            }
        });
    }
    
    async showRecommendations(fieldName, targetElement) {
        // 추천 시스템 시작
        
        // 기존 추천 박스 제거
        this.hideRecommendations();
        
        // 로딩 표시
        const loadingBox = this.createLoadingBox(targetElement);
        document.body.appendChild(loadingBox);
        
        try {
            // 1. 최근 사용 문구 가져오기
            const recentPhrases = this.getRecentUsage(fieldName);
            // 최근 사용 문구 로드됨
            
            // 2. API에서 스마트 추천 문구 가져오기
            const smartRecommendations = await this.loadSmartRecommendations(fieldName, targetElement.value);
            // 스마트 추천 문구 로드됨
            
            // 3. 기본 추천 문구 가져오기
            const basicRecommendations = this.recommendations[fieldName] || [];
            // 기본 추천 문구 로드됨
            
            // 4. 전체 추천 목록 구성 (최근 사용 > 스마트 추천 > 기본 추천)
            // 모든 항목을 안전한 문자열로 변환
            const safeRecentPhrases = recentPhrases.map(item => 
                typeof item === 'string' ? item : 
                (item && item.text ? item.text : 
                (item && item.name ? item.name : String(item)))
            );
            
            const safeSmartRecommendations = smartRecommendations.map(item => 
                typeof item === 'string' ? item : 
                (item && item.text ? item.text : 
                (item && item.name ? item.name : String(item)))
            );
            
            const safeBasicRecommendations = basicRecommendations.map(item => 
                typeof item === 'string' ? item : 
                (item && item.text ? item.text : 
                (item && item.name ? item.name : String(item)))
            );
            
            // 15개 제한을 위해 기본 추천 문구 개수 동적 조절
            const maxTotalItems = 15;
            const recentAndSmartCount = safeRecentPhrases.length + safeSmartRecommendations.length;
            const remainingSlots = Math.max(0, maxTotalItems - recentAndSmartCount);
            const limitedBasicRecommendations = safeBasicRecommendations.slice(0, remainingSlots);
            
            // 추천 구성 완료
            
            const allRecommendations = [
                ...safeRecentPhrases,
                ...safeSmartRecommendations,
                ...limitedBasicRecommendations
            ].filter((item, index, arr) => arr.indexOf(item) === index && item !== '[object Object]'); // 중복 제거 및 객체 문자열 제외
            
            // 로딩 박스 제거
            loadingBox.remove();
            
            // 전체 추천 문구 구성 완료
            
            if (allRecommendations.length === 0) {
                // 표시할 추천 문구가 없음
                return;
            }
            
            // 추천 박스 생성
            console.log(`📦 추천 박스 생성 중... (최근: ${safeRecentPhrases.length}개)`);
            const recommendationBox = this.createRecommendationBox(targetElement, allRecommendations, safeRecentPhrases.length);
            document.body.appendChild(recommendationBox);
            console.log(`✅ 추천 박스 DOM에 추가 완료`);
            
        } catch (error) {
            console.error('❌ 추천 문구 로드 중 오류:', error);
            loadingBox.remove();
            
            // 기본 추천만 표시
            const basicRecommendations = this.recommendations[fieldName] || [];
            console.log(`🔄 기본 추천으로 폴백 (${basicRecommendations.length}개):`, basicRecommendations);
            
            if (basicRecommendations.length > 0) {
                const recommendationBox = this.createRecommendationBox(targetElement, basicRecommendations, 0);
                document.body.appendChild(recommendationBox);
                console.log(`✅ 기본 추천 박스 표시 완료`);
            } else {
                console.log(`❌ 기본 추천 문구도 없음: ${fieldName}`);
            }
        }
    }
    
    // 로딩 박스 생성
    createLoadingBox(targetElement) {
        const loadingBox = document.createElement('div');
        loadingBox.className = 'basic-recommendation-box loading';
        loadingBox.style.cssText = `
            position: absolute;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            z-index: 1000;
            width: ${targetElement.offsetWidth}px;
            padding: 12px;
            text-align: center;
            color: #666;
        `;
        
        loadingBox.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
                <div style="width: 16px; height: 16px; border: 2px solid #ddd; border-top: 2px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                추천 문구 로딩 중...
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
        
        const rect = targetElement.getBoundingClientRect();
        loadingBox.style.left = rect.left + 'px';
        loadingBox.style.top = (rect.bottom + window.scrollY) + 'px';
        
        return loadingBox;
    }
    
    // 추천 박스 생성
    createRecommendationBox(targetElement, recommendations, recentCount) {
        const recommendationBox = document.createElement('div');
        recommendationBox.className = 'basic-recommendation-box';
        recommendationBox.style.cssText = `
            position: absolute;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            max-height: 300px;
            overflow-y: auto;
            z-index: 1000;
            width: ${Math.max(targetElement.offsetWidth, 200)}px;
        `;
        
        // 추천 항목들 추가 (최대 15개)
        const maxItems = 15;
        const displayRecommendations = recommendations.slice(0, maxItems);
        
        displayRecommendations.forEach((item, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'recommendation-item';
            
            // 최근 사용 문구인지 확인
            const isRecent = index < recentCount;
            const isSmartRecommendation = index >= recentCount && index < recentCount + (recommendations.length - this.recommendations[targetElement.name]?.length || 0);
            
            // 아이콘과 텍스트 구성
            let iconHtml = '';
            let labelText = '';
            
            if (isRecent) {
                iconHtml = '<span style="color: #28a745; margin-right: 6px;">🕒</span>';
                labelText = '<span style="font-size: 0.8em; color: #28a745; margin-left: 4px;">최근</span>';
            } else if (isSmartRecommendation) {
                iconHtml = '<span style="color: #007bff; margin-right: 6px;">✨</span>';
                labelText = '<span style="font-size: 0.8em; color: #007bff; margin-left: 4px;">추천</span>';
            } else {
                iconHtml = '<span style="color: #6c757d; margin-right: 6px;">📝</span>';
                labelText = '<span style="font-size: 0.8em; color: #6c757d; margin-left: 4px;">기본</span>';
            }
            
            // 항목이 객체인 경우 안전하게 문자열로 변환
            let displayText = '';
            if (typeof item === 'string') {
                displayText = item;
            } else if (item && typeof item === 'object') {
                if (item.text) displayText = item.text;
                else if (item.name) displayText = item.name;
                else if (item.phrase) displayText = item.phrase;
                else if (item.content) displayText = item.content;
                else displayText = JSON.stringify(item);
            } else {
                displayText = String(item);
            }
            
            // [object Object] 방지
            if (displayText === '[object Object]' || displayText.trim() === '') {
                console.warn('잘못된 추천 항목 건너뜀:', item);
                return;
            }
            
            itemEl.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center;">
                        ${iconHtml}
                        <span>${displayText}</span>
                    </div>
                    ${labelText}
                </div>
            `;
            
            itemEl.style.cssText = `
                padding: 10px 12px;
                cursor: pointer;
                border-bottom: 1px solid #eee;
                ${isRecent ? 'background-color: #f8fff8;' : ''}
                ${isSmartRecommendation ? 'background-color: #f8f9ff;' : ''}
            `;
            
            itemEl.addEventListener('mouseenter', () => {
                itemEl.style.backgroundColor = '#e9ecef';
            });
            
            itemEl.addEventListener('mouseleave', () => {
                if (isRecent) {
                    itemEl.style.backgroundColor = '#f8fff8';
                } else if (isSmartRecommendation) {
                    itemEl.style.backgroundColor = '#f8f9ff';
                } else {
                    itemEl.style.backgroundColor = 'white';
                }
            });
            
            itemEl.addEventListener('click', () => {
                // 필드에 값 설정 (안전한 문자열 사용)
                this.setFieldValue(targetElement, displayText);
                
                // 최근 사용 이력에 추가 (안전한 문자열 사용)
                this.addToRecentUsage(targetElement.name, displayText);
                
                // 추천 박스 숨김
                this.hideRecommendations();
                
                console.log(`✅ 추천 항목 선택됨: ${displayText} (${isRecent ? '최근' : isSmartRecommendation ? '스마트추천' : '기본'})`);
            });
            
            recommendationBox.appendChild(itemEl);
        });
        
        // 위치 계산 및 설정
        const rect = targetElement.getBoundingClientRect();
        recommendationBox.style.left = rect.left + 'px';
        recommendationBox.style.top = (rect.bottom + window.scrollY) + 'px';
        
        return recommendationBox;
    }
    
    // 필드 값 설정 (readonly/disabled 처리 포함)
    setFieldValue(targetElement, value) {
        const fieldName = targetElement.name;
        let finalValue = value;
        
        // 주의사항과 기타표시사항은 기존 값에 추가 모드
        if (fieldName === 'cautions' || fieldName === 'additional_info') {
            const currentValue = targetElement.value.trim();
            if (currentValue) {
                // 기존 값이 있으면 | 구분자로 추가
                finalValue = currentValue + ' | ' + value;
            }
        }
        
        if (targetElement.readOnly || targetElement.disabled) {
            // readonly/disabled 필드는 임시로 해제 후 값 설정
            const wasReadOnly = targetElement.readOnly;
            const wasDisabled = targetElement.disabled;
            
            targetElement.readOnly = false;
            targetElement.disabled = false;
            targetElement.value = finalValue;
            
            // 상태 복원
            targetElement.readOnly = wasReadOnly;
            targetElement.disabled = wasDisabled;
        } else {
            targetElement.value = finalValue;
        }
        
        // 이벤트 발생
        targetElement.dispatchEvent(new Event('input', { bubbles: true }));
        targetElement.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    hideRecommendations() {
        const existingBoxes = document.querySelectorAll('.basic-recommendation-box');
        existingBoxes.forEach(box => box.remove());
    }
}

// 전역 인스턴스 생성
window.basicRecommendationSystem = null;

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', function() {
    if (!window.basicRecommendationSystem) {
        window.basicRecommendationSystem = new BasicRecommendationSystem();
    }
});
