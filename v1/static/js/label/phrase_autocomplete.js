/**
 * 라벨 문구 자동완성 시스템
 * 최근 사용 문구 + API 기반 추천 문구를 제공하는 자동완성 기능
 */

class PhraseAutocomplete {
    constructor() {
        this.smartApiUrl = '/label/api/auto-fill/';
        this.phraseApiUrl = '/label/api/phrases/';
        this.recentUsageKey = 'labeldata_recent_phrases';
        this.maxRecentItems = 5;  // 최근 사용 문구 최대 5개
        this.maxTotalItems = 10;  // 전체 표시 문구 최대 10개
        
        this.init();
    }
    
    init() {
        this.setupFieldListeners();
        this.loadRecentUsage();
    }
    
    // 최근 사용 이력 로드
    loadRecentUsage() {
        try {
            const stored = localStorage.getItem(this.recentUsageKey);
            this.recentUsage = stored ? JSON.parse(stored) : {};
        } catch (error) {
            this.recentUsage = {};
        }
    }
    
    // 최근 사용 이력 저장
    saveRecentUsage() {
        try {
            localStorage.setItem(this.recentUsageKey, JSON.stringify(this.recentUsage));
        } catch (error) {
            // 최근 사용 이력 저장 실패 시 무시
        }
    }
    
    // 최근 사용 문구 추가
    addToRecentUsage(fieldName, phrase) {
        // 안전한 문자열만 저장
        const safePhrase = typeof phrase === 'string' ? phrase : String(phrase);
        if (!safePhrase || safePhrase === '[object Object]' || safePhrase.trim() === '') {
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
            // 제거됨: food_group, food_type (셀렉트박스)
            'storage_method': 'storage',
            'content_weight': 'weight',
            'bssh_nm': 'company',
            'pog_daycnt': 'expiry',
            // 실제 HTML 필드명들 매핑
            'prdlst_nm': 'product',
            'ingredient_info': 'ingredient',    // 상세 입력 영역
            'prdlst_dcnm': 'category',         // 상세 입력 영역
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
                return [];
            }
        } catch (error) {
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
            // 실제 HTML에 존재하는 필드들만 포함
            'prdlst_nm',            // 제품명 ✅
            'ingredient_info',      // 특정성분 함량 ✅ (상세 입력 영역)
            'prdlst_dcnm',         // 식품유형 ✅ (상세 입력 영역)
            'prdlst_report_no',    // 품목보고번호 ✅
            'frmlc_mtrqlt',        // 용기.포장재질 ✅
            'cautions',            // 주의사항 ✅
            'additional_info',     // 기타정보 ✅
            'processing_condition', // 가공조건 ✅
            'my_label_name_top',   // 라벨명 (상단) ✅
            // 제거됨: food_group, food_type (셀렉트박스)
            // 추가된 필드들
            'content_weight',      // 내용량 ✅
            'storage_method',      // 보관방법 ✅
            'bssh_nm',            // 제조원 소재지 ✅
            'distributor_address', // 유통전문판매원 ✅
            'repacker_address',    // 소분원 ✅
            'importer_address',    // 수입원 ✅
            'pog_daycnt',         // 소비기한(품질유지기한) ✅
            'rawmtrl_nm_display'  // 원재료명(최종표시) ✅
        ];
        
        // 자동 이벤트 리스너 추가를 비활성화하여 기존 버튼 클릭과 충돌하지 않도록 함
        // 추천 시스템은 인라인 onclick/onfocus를 통해서만 호출되도록 변경
        
        // 문서 전체 클릭 시 추천 박스 숨김
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.basic-recommendation-box') && !fields.some(name => e.target.name === name)) {
                this.hideRecommendations();
            }
        });
    }
    
    async showRecommendations(fieldName, targetElement) {
        // 토글 상태 확인 - 비활성화되어 있으면 추천 창 표시하지 않음
        if (typeof window.recommendationsEnabled !== 'undefined' && !window.recommendationsEnabled) {
            return;
        }
        
        // 기존 추천 박스 제거
        this.hideRecommendations();
        
        // 로딩 표시
        const loadingBox = this.createLoadingBox(targetElement);
        document.body.appendChild(loadingBox);
        
        try {
            // 1. 최근 사용 문구 가져오기
            const recentPhrases = this.getRecentUsage(fieldName);
            
            // 2. API에서 스마트 추천 문구 가져오기
            const smartRecommendations = await this.loadSmartRecommendations(fieldName, targetElement.value);
            
            // 3. 전체 추천 목록 구성 (최근 사용 > 스마트 추천)
            // 모든 항목을 안전한 문자열로 변환
            const safeRecentPhrases = recentPhrases.map(item => 
                typeof item === 'string' ? item : 
                (item && item.text ? item.text : 
                (item && item.name ? item.name : String(item)))
            ).filter(item => item !== '[object Object]' && item.trim() !== '');
            
            const safeSmartRecommendations = smartRecommendations.map(item => 
                typeof item === 'string' ? item : 
                (item && item.text ? item.text : 
                (item && item.name ? item.name : String(item)))
            ).filter(item => item !== '[object Object]' && item.trim() !== '');
            
            // 최근 사용 문구는 최대 5개까지만 사용
            const limitedRecentPhrases = safeRecentPhrases.slice(0, this.maxRecentItems);
            
            // 중복 제거된 스마트 추천 문구 (최근 사용 문구와 중복되지 않는 것만)
            const uniqueSmartRecommendations = safeSmartRecommendations.filter(item => 
                !limitedRecentPhrases.includes(item)
            );
            
            // 최근 사용 문구 개수에 따라 추천 문구 개수 조정
            const remainingSlots = this.maxTotalItems - limitedRecentPhrases.length;
            const limitedSmartRecommendations = uniqueSmartRecommendations.slice(0, Math.max(0, remainingSlots));
            
            // 최종 추천 목록 구성
            const allRecommendations = [
                ...limitedRecentPhrases,
                ...limitedSmartRecommendations
            ];
            
            // 로딩 박스 제거
            loadingBox.remove();
            
            // 전체 추천 문구 구성 완료
            
            if (allRecommendations.length === 0) {
                // 표시할 추천 문구가 없음
                return;
            }
            
            // 추천 박스 생성
            const recommendationBox = this.createRecommendationBox(targetElement, allRecommendations, limitedRecentPhrases.length);
            document.body.appendChild(recommendationBox);
            
        } catch (error) {
            loadingBox.remove();
            // 에러 발생 시 아무것도 표시하지 않음
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
        
        // 추천 항목들 추가 (최대 10개)
        const displayRecommendations = recommendations; // 이미 상위에서 개수 제한됨
        
        displayRecommendations.forEach((item, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'recommendation-item';
            
            // 최근 사용 문구인지 확인
            const isRecent = index < recentCount;
            const isSmartRecommendation = index >= recentCount;
            
            // 아이콘과 텍스트 구성
            let iconHtml = '';
            let labelText = '';
            
            if (isRecent) {
                iconHtml = '<span style="color: #28a745; margin-right: 6px;">🕒</span>';
                labelText = '<span style="font-size: 0.8em; color: #28a745; margin-left: 4px;">최근</span>';
            } else {
                iconHtml = '<span style="color: #007bff; margin-right: 6px;">✨</span>';
                labelText = '<span style="font-size: 0.8em; color: #007bff; margin-left: 4px;">추천</span>';
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
                ${isRecent ? 'background-color: #f8fff8;' : 'background-color: #f8f9ff;'}
            `;
            
            itemEl.addEventListener('mouseenter', () => {
                itemEl.style.backgroundColor = '#e9ecef';
            });
            
            itemEl.addEventListener('mouseleave', () => {
                if (isRecent) {
                    itemEl.style.backgroundColor = '#f8fff8';
                } else {
                    itemEl.style.backgroundColor = '#f8f9ff';
                }
            });
            
            itemEl.addEventListener('click', () => {
                // 필드에 값 설정 (안전한 문자열 사용)
                this.setFieldValue(targetElement, displayText);
                
                // 최근 사용 이력에 추가 (안전한 문자열 사용)
                this.addToRecentUsage(targetElement.name, displayText);
                
                // 추천 박스 숨김
                this.hideRecommendations();
                

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
                // 기존 문구들을 | 구분자로 분리하여 중복 확인
                const existingPhrases = currentValue.split('|').map(phrase => phrase.trim());
                const newPhrase = value.trim();
                
                // 중복 확인: 대소문자 무시하고 비교
                const isDuplicate = existingPhrases.some(existing => 
                    existing.toLowerCase() === newPhrase.toLowerCase()
                );
                
                if (!isDuplicate) {
                    // 중복이 아닌 경우에만 추가
                    finalValue = currentValue + ' | ' + value;
                } else {
                    // 중복인 경우 기존 값 유지
                    finalValue = currentValue;
                }
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
window.phraseAutocomplete = null;

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', function() {
    if (!window.phraseAutocomplete) {
        window.phraseAutocomplete = new PhraseAutocomplete();
        
        // 하위 호환성을 위한 별칭 (기존 HTML 코드 호환성)
        window.basicRecommendationSystem = window.phraseAutocomplete;
    }
});