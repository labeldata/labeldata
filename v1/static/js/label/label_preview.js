// 즉시 실행 함수로 전역 함수들 정의
// 디버그 모드 비활성화

// ===== 전역 validateSettings 함수 =====
window.validateSettings = async function() {
    
    try {
        // 로깅 API 호출
        const urlParams = new URLSearchParams(window.location.search);
        const labelId = urlParams.get('label_id');
        if (labelId) {
            try {
                await fetch('/label/log-validation/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ label_id: labelId })
                });
            } catch (logError) {
                console.warn('로깅 실패:', logError);
            }
        }
        
        // 캐싱된 요소 사용
        const elements = window.cachedElements || {};
        const width = parseFloat(elements.widthInput?.value || document.getElementById('widthInput')?.value) || 0;
        const height = parseFloat((elements.heightInput?.value || document.getElementById('heightInput')?.value || '').replace(/[^0-9.-]/g, '')) || 0;
        const area = width * height;
        const fontSize = parseFloat(elements.fontSizeInput?.value || document.getElementById('fontSizeInput')?.value) || 10;
        
        // 검증 항목들 정의
        const validationItems = [
            {
                label: '표시면 면적',
                check: () => ({
                    ok: area >= 40,
                    errors: area < 40 ? [`표시면 면적은 최소 40cm² 이상이어야 합니다 («식품 등의 표시기준» 제4조).`] : [],
                    suggestions: area < 40 ? ['면적을 40cm² 이상으로 조정하세요.'] : []
                }),
                always: true
            },
            {
                label: '글꼴 크기',
                check: () => ({
                    ok: fontSize >= 10,
                    errors: fontSize < 10 ? [`글꼴 크기는 최소 10pt 이상이어야 합니다 («식품 등의 표시기준» 제6조).`] : [],
                    suggestions: fontSize < 10 ? ['글꼴 크기를 10pt 이상으로 조정하세요.'] : []
                }),
                always: true
            },
            {
                label: '기본 필드 검증',
                check: () => {
                    try {
                        return validateBasicFields();
                    } catch (e) {
                        console.warn('기본 필드 검증 오류:', e);
                        return { ok: true, errors: [], suggestions: [] };
                    }
                }
            },
            {
                label: '성분 표시 규정',
                check: () => {
                    try {
                        return validateIngredientCompliance();
                    } catch (e) {
                        console.warn('성분 표시 규정 검증 오류:', e);
                        return { ok: true, errors: [], suggestions: [] };
                    }
                }
            },
            {
                label: '문구 표시 규정',
                check: () => {
                    try {
                        return validateTextCompliance();
                    } catch (e) {
                        console.warn('문구 표시 규정 검증 오류:', e);
                        return { ok: true, errors: [], suggestions: [] };
                    }
                }
            },
            {
                label: '알레르기 성분',
                check: () => {
                    try {
                        return validateAllergenCompliance();
                    } catch (e) {
                        console.warn('알레르기 성분 검증 오류:', e);
                        return { ok: true, errors: [], suggestions: [] };
                    }
                }
            },
            {
                label: '포장재질 및 분리배출',
                check: () => {
                    try {
                        return validatePackagingCompliance();
                    } catch (e) {
                        console.warn('포장재질 검증 오류:', e);
                        return { ok: true, errors: [], suggestions: [] };
                    }
                },
                always: true
            }
        ];
        
        // 모든 검증 실행
        const validationResults = validationItems.map(item => {
            try {
                const result = item.check();
                return { ...result, label: item.label };
            } catch (error) {
                console.error(`${item.label} 검증 오류:`, error);
                return {
                    ok: false,
                    errors: [`${item.label} 검증 중 오류가 발생했습니다: ${error.message}`],
                    suggestions: [],
                    label: item.label
                };
            }
        });
        
        // 결과 모달 표시
        showValidationModal(validationResults);
        
    } catch (error) {
        console.error('validateSettings 오류:', error);
        alert('검증 중 오류가 발생했습니다: ' + error.message);
    }
};

// 알레르기 성분 검증 함수
function checkAllergenDuplication() {
    // 알레르기 성분 중복 검증
    
    // constants.js에서 로드된 알레르기 키워드 사용
    const allergenKeywords = window.allergenKeywords;
    
    // 원재료명과 알레르기 표시사항 가져오기
    let ingredients = '';
    let allergenInfo = '';
    let declaredAllergens = []; // 선언된 알레르기 성분
    
    // 1순위: 부모창에서 전달된 알레르기 데이터 (알레르기 관리 모듈)
    if (typeof window.parentAllergens !== 'undefined' && window.parentAllergens && window.parentAllergens.length > 0) {
        declaredAllergens = window.parentAllergens.slice(); // 배열 복사
    }
    // 2순위: 백엔드에서 전달된 allergensData (DB 저장된 데이터)
    else if (typeof allergensData !== 'undefined' && allergensData && allergensData.length > 0) {
        declaredAllergens = allergensData.slice(); // 배열 복사
    }
    
    // 부모창 데이터 확인
    
    // DOMContentLoaded에서 정의된 checkedFields가 있는지 확인 (부모창 원본 데이터)
    if (typeof window.checkedFields !== 'undefined' && window.checkedFields && Object.keys(window.checkedFields).length > 0) {
        // 부모창의 원본 원재료명 사용 (rawmtrl_nm_display)
        ingredients = window.checkedFields.rawmtrl_nm_display || '';
        
        // 3순위: 부모창 원본에서 알레르기 성분 추출 (구식 방식, 폴백)
        if (declaredAllergens.length === 0) {
            const allergenMatch = ingredients.match(/\[알레르기\s*성분\s*:\s*([^\]]+)\]/i);
            if (allergenMatch) {
                allergenInfo = allergenMatch[0]; // 전체 [알레르기 성분 : ...] 부분
                // 알레르기 성분 파싱
                const allergenText = allergenMatch[1].replace(/\s*함유\s*/g, '').trim();
                const items = allergenText.split(/[,、，]/).map(item => item.trim()).filter(item => item && item.length > 0);
                declaredAllergens.push(...items);
            }
        }
        
    } else {
        
        // 방법 1: 부모 창의 URL 파라미터나 세션 스토리지 확인
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const labelId = urlParams.get('label_id');
            
            // 세션 스토리지에서 원본 데이터 찾기
            const sessionKey = `labelPreviewSettings_${labelId}`;
            const sessionData = sessionStorage.getItem(sessionKey);
            if (sessionData) {
                const parsed = JSON.parse(sessionData);
                if (parsed.rawmtrl_nm_display) {
                    ingredients = parsed.rawmtrl_nm_display;
                }
            }
        } catch (e) {
            // 세션 스토리지 접근 실패 무시
        }
        
        // 방법 2: 입력 필드에서 원본 데이터 직접 찾기
        if (!ingredients) {
            
            // 페이지의 모든 input, textarea 확인
            const inputs = document.querySelectorAll('input, textarea, select');
            for (const input of inputs) {
                const value = input.value || '';
                const name = input.name || input.id || '';
                
                if ((name.includes('rawmtrl') || name.includes('원재료')) && value.includes('[알레르기')) {
                    ingredients = value.trim();
                    break;
                }
                
                // 감자플레이크를 포함하는 필드도 체크
                if (value.includes('감자플레이크') && value.includes('[알레르기')) {
                    ingredients = value.trim();
                    break;
                }
            }
        }
        
        // 방법 3: DOM에서 원본 형태 찾기 (마지막 수단)
        if (!ingredients) {
            const allElements = document.querySelectorAll('*');
            for (const element of allElements) {
                const text = element.textContent || '';
                if (text.includes('감자플레이크') && text.includes('[알레르기') && text.length < 500) {
                    ingredients = text.trim();
                    break;
                }
            }
        }
    }
    
    // 원재료명이 없으면 검증 불가
    if (!ingredients || !ingredients.trim()) {
        return [];
    }
    
    // 부모창 원본 데이터 기준으로 처리
    // 1. 원재료명에서 알레르기 성분 정보 분리
    let cleanIngredients = ingredients;
    let declaredAllergenText = '';
    
    // [알레르기 성분 : ...] 부분 제거하여 순수 원재료명 추출
    const allergenPattern = /\[알레르기[^:]*:\s*([^\]]+)\]/i;
    const allergenMatch = ingredients.match(allergenPattern);
    
    if (allergenMatch) {
        // 순수 원재료명 (알레르기 성분 표시 제거)
        cleanIngredients = ingredients.replace(allergenPattern, '').trim();
        // 선언된 알레르기 성분
        declaredAllergenText = allergenMatch[1]; // "밀, 달걀, 우유, 대두 함유"
    }
    
    if (!cleanIngredients.trim()) {
        return [];
    }
    
    // 3. 원재료명에서 발견된 알레르기 성분들
    const foundAllergens = [];
    
    for (const [allergen, keywords] of Object.entries(allergenKeywords)) {
        for (const keyword of keywords) {
            let found = false;
            let matchedBy = '';
            
            if (keyword.length === 1) {
                const regex = new RegExp(`[\\s,():]${keyword}[\\s,():]|^${keyword}[\\s,():]|[\\s,():]${keyword}$|^${keyword}$`, 'gi');
                if (regex.test(cleanIngredients)) {
                    found = true;
                    matchedBy = `직접매칭(단일문자): ${keyword}`;
                }
            } else {
                // 2글자 이상: 단순 포함 여부로 체크 (탈지대두에서 대두 찾기)
                const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(escapedKeyword, 'gi');
                if (regex.test(cleanIngredients)) {
                    found = true;
                    matchedBy = `직접매칭: ${keyword}`;
                }
            }
            
            if (!found && window.findAllergenSynonyms) {
                const synonymData = window.findAllergenSynonyms(keyword);
                if (synonymData) {
                    const matchedSynonym = synonymData.synonyms.find(synonym => {
                        if (synonym.length === 1) {
                            const regex = new RegExp(`[\\s,():]${synonym}[\\s,():]|^${synonym}[\\s,():]|[\\s,():]${synonym}$|^${synonym}$`, 'gi');
                            return regex.test(cleanIngredients);
                        } else {
                            // 동의어도 단순 포함 여부로 체크
                            const escapedSynonym = synonym.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                            const regex = new RegExp(escapedSynonym, 'gi');
                            return regex.test(cleanIngredients);
                        }
                    });
                    if (matchedSynonym) {
                        found = true;
                        matchedBy = `동의어매칭: ${matchedSynonym} (원키워드: ${keyword})`;
                    }
                }
            }
            
            if (found) {
                if (!foundAllergens.includes(allergen)) {
                    foundAllergens.push(allergen);
                }
                break;
            }
        }
    }
    
    // 4. 구식 방식으로 추가 파싱 (폴백용 - 이미 앞에서 처리됨)
    // declaredAllergens는 이미 위에서 초기화됨
    
    if (declaredAllergens.length === 0 && declaredAllergenText) {
        // "밀, 달걀, 우유, 대두 함유" 형태에서 "함유" 제거하고 쉼표로 분리
        let cleanText = declaredAllergenText.replace(/\s*함유\s*/g, '').trim();
        
        const items = cleanText.split(/[,、，]/).map(item => item.trim()).filter(item => item && item.length > 0);
        declaredAllergens.push(...items);
    }
    
    // 5. 주의사항에서 중복 표시 검사
    let cautionsText = '';
    if (window.checkedFields && window.checkedFields.cautions) {
        cautionsText = window.checkedFields.cautions;
    }
    
    const duplicatedAllergens = [];
    
    if (declaredAllergens.length > 0 && cautionsText) {
        
        for (const declaredAllergen of declaredAllergens) {
            // 선언된 알레르기 성분별 키워드 확인
            const matchedKeywords = allergenKeywords[declaredAllergen] || [declaredAllergen];
            
            const foundInCautions = matchedKeywords.filter(keyword => {
                // 키워드가 주의사항에 포함되어 있는지 확인 (단순 포함)
                if (keyword.length === 1) {
                    // 단일 문자는 정확한 매치 확인
                    const regex = new RegExp(`[\\s,():]${keyword}[\\s,():]|^${keyword}[\\s,():]|[\\s,():]${keyword}$|^${keyword}$`, 'gi');
                    return regex.test(cautionsText);
                } else {
                    // 2글자 이상: 단순 포함 여부로 체크
                    const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(escapedKeyword, 'gi');
                    return regex.test(cautionsText);
                }
            });
            
            if (foundInCautions.length > 0) {
                duplicatedAllergens.push({
                    allergen: declaredAllergen,
                    foundKeywords: foundInCautions
                });
            }
        }
    }
    
    // 누락된 알레르기 성분 찾기
    const missingAllergens = foundAllergens.filter(foundAllergen => {
        const hasMatch = declaredAllergens.some(declared => {
            // 1. 정확한 일치 검사
            if (foundAllergen.toLowerCase() === declared.toLowerCase()) {
                return true;
            }
            
            // 2. 부분 포함 검사 (기존 로직 유지)
            if (declared.toLowerCase().includes(foundAllergen.toLowerCase()) ||
                foundAllergen.toLowerCase().includes(declared.toLowerCase())) {
                return true;
            }
            
            // 3. 동의어 검사 '난류' 표기와 '알류' 표기를 동일한 알레르기로 인식
            const foundSynonyms = window.findAllergenSynonyms ? window.findAllergenSynonyms(foundAllergen) : null;
            const declaredSynonyms = window.findAllergenSynonyms ? window.findAllergenSynonyms(declared) : null;
            
            // 동의어 그룹이 같으면 동일한 알레르기로 간주 (예): '달걀' 원재료 + '난류' 표시 = 정상 인식
            if (foundSynonyms && declaredSynonyms && 
                foundSynonyms.allergen === declaredSynonyms.allergen) {
                return true;
            }
            
            // 동의어 목록에서 부분 일치 검사
            if (foundSynonyms && foundSynonyms.synonyms.some(synonym => 
                declared.toLowerCase().includes(synonym.toLowerCase()))) {
                return true;
            }
            
            if (declaredSynonyms && declaredSynonyms.synonyms.some(synonym => 
                foundAllergen.toLowerCase().includes(synonym.toLowerCase()))) {
                return true;
            }
            
            return false;
        });
        
        return !hasMatch; // 일치하지 않는 것만 누락으로 처리
    });
    
    // 오류 메시지 생성
    const errors = [];
    
    // 누락 오류
    if (missingAllergens.length > 0) {
        errors.push(...missingAllergens.map(allergen => 
            `원재료명에 '${allergen}'이(가) 포함되어 있으나 [알레르기 성분] 표시에 누락되었습니다.`
        ));
    }
    
    // 중복 오류 (원재료명 음영표시 + 주의사항 중복)
    if (duplicatedAllergens.length > 0) {
        errors.push(...duplicatedAllergens.map(item => 
            `알레르기 성분 '${item.allergen}'이(가) 주의사항에 중복으로 표시되어 있습니다. 원재료명에 음영표시되어 있으므로 주의사항에서 삭제하거나 표현을 수정하세요. (발견된 키워드: ${item.foundKeywords.join(', ')})`
        ));
    }
    
    return errors;
} // checkAllergenDuplication 함수 끝

// 검증 결과 모달 표시 함수
function showValidationModal(results) {
    
    // 기존 모달 제거
    const existingModal = document.getElementById('validationModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 새 모달 생성
    const modal = document.createElement('div');
    modal.id = 'validationModal';
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">규정 검증 결과</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th style="width: 25%">검증 항목</th>
                                <th style="width: 15%; white-space: nowrap;">상태</th>
                                <th style="width: 60%">결과 및 제안</th>
                            </tr>
                        </thead>
                        <tbody id="validationResultBody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 테이블 내용 채우기
    const tbody = document.getElementById('validationResultBody');
    let rowsHtml = '';
    
    for (const result of results) {
        rowsHtml += '<tr>';
        rowsHtml += `<td>${result.label}</td>`;
        
        if (result.ok) {
            rowsHtml += '<td><span class="text-success">적합</span></td>';
        } else {
            rowsHtml += '<td><span class="text-danger">재검토</span></td>';
        }
        
        let msg = '';
        if (result.errors && result.errors.length > 0) {
            // 에러 메시지에 볼드 적용
            const boldErrors = result.errors.map(error => 
                error.includes('<strong>') ? error : `<strong>${error}</strong>`
            );
            msg += boldErrors.join('<br>');
        }
        if (result.suggestions && result.suggestions.length > 0) {
            if (msg) msg += '<br><br>';
            // 제안사항에 볼드 적용
            const boldSuggestions = result.suggestions.map(suggestion => 
                suggestion.includes('<strong>') ? suggestion : `<strong>${suggestion}</strong>`
            );
            msg += '<strong style="color: #0066cc;">💡 제안:</strong><br>' + boldSuggestions.join('<br>');
        }
        rowsHtml += `<td>${msg}</td>`;
        rowsHtml += '</tr>';
    }
    
    tbody.innerHTML = rowsHtml;
    
    // 모달 표시
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}
// ===== 전역 함수 정의 끝 =====

(function() {
    'use strict';
    
    // 전역 변수
    window.recyclingMarkFunctionsReady = false;
    
    // 함수 준비 상태 확인 헬퍼 (즉시 사용 가능)
    window.checkRecyclingMarkReady = function() {
        return {
            ready: !!window.recyclingMarkFunctionsReady,
            functions: {
                applyRecommendedRecyclingMark: typeof window.applyRecommendedRecyclingMark,
                getCurrentRecyclingMarkStatus: typeof window.getCurrentRecyclingMarkStatus,
                debugRecyclingMark: typeof window.debugRecyclingMark,
                updateRecyclingMarkUI: typeof window.updateRecyclingMarkUI
            }
        };
    };
    
    // 기본 함수들 (DOM 로드 전)
    window.applyRecommendedRecyclingMark = function() {
        if (!window.recyclingMarkFunctionsReady) {
            console.warn('⚠️ DOM이 아직 준비되지 않았습니다. 페이지 로드 후 다시 시도하세요.');
            return false;
        }
        return window._applyRecommendedRecyclingMark();
    };

    window.getCurrentRecyclingMarkStatus = function() {
        if (!window.recyclingMarkFunctionsReady) {
            console.warn('⚠️ DOM이 아직 준비되지 않았습니다. 페이지 로드 후 다시 시도하세요.');
            return { ready: false };
        }
        return window._getCurrentRecyclingMarkStatus();
    };

    window.debugRecyclingMark = function() {
        if (!window.recyclingMarkFunctionsReady) {
            console.warn('⚠️ DOM이 아직 준비되지 않았습니다. 페이지 로드 후 다시 시도하세요.');
            return;
        }
        return window._debugRecyclingMark();
    };
    
})();

// 유틸리티 함수: 안전한 JSON 데이터 로드
function safeLoadJsonData(elementId, defaultValue = null, description = '') {
    try {
        const element = document.getElementById(elementId);
        if (element && element.textContent) {
            return JSON.parse(element.textContent);
        } else {
            return defaultValue;
        }
    } catch (error) {
        console.error(`${description || elementId} 파싱 오류:`, error);
        return defaultValue;
    }
}

// 유틸리티 함수: HTML 엔티티 디코딩
function decodeHtmlEntities(text) {
    if (!text) return text;
    return text
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>');
}

// 유틸리티 함수: 안전한 JSON 파싱 (디코딩 포함)
function safeParseJson(textContent, description = '') {
    if (!textContent || typeof textContent !== 'string') {
        return {};
    }
    
    // HTML 엔티티 디코딩
    const decodedText = decodeHtmlEntities(textContent.trim());
    
    let result = {};
    
    if (decodedText.length > 0) {
        // 기본적인 JSON 구조 확인
        if (decodedText.startsWith('{') && decodedText.endsWith('}')) {
            try {
                result = JSON.parse(decodedText);
            } catch (parseError) {
                console.warn(`${description} JSON 파싱 실패, 기본값 사용:`, parseError.message);
                result = {};
            }
        } else if (decodedText.startsWith('[') && decodedText.endsWith(']')) {
            try {
                const arrayData = JSON.parse(decodedText);
                result = arrayData[0] || {};
            } catch (parseError) {
                console.warn(`${description} 배열 JSON 파싱 실패, 기본값 사용:`, parseError.message);
                result = {};
            }
        } else {
            console.warn(`${description} JSON 형식이 아닙니다. 기본값을 사용합니다.`);
            result = {};
        }
    }
    
    return result;
}

// 유틸리티 함수: 안전한 DOM 요소 값 설정
function safeSetElementValue(elementId, value, warnOnMissing = false) {
    const element = document.getElementById(elementId);
    if (element) {
        element.value = value;
        return true;
    } else if (warnOnMissing) {
        console.warn(`${elementId} 요소를 찾을 수 없습니다`);
    }
    return false;
}

// 유틸리티 함수: 안전한 이벤트 리스너 추가
function safeAddEventListener(elementId, eventType, handler, options = {}) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(eventType, handler, options);
        return true;
    }
    return false;
}

// 유틸리티 함수: 여러 요소에 같은 이벤트 리스너 추가
function addEventListenersToElements(elementIds, eventType, handler, options = {}) {
    const results = elementIds.map(id => safeAddEventListener(id, eventType, handler, options));
    return results.filter(result => result).length; // 성공한 개수 반환
}

document.addEventListener('DOMContentLoaded', function () {
    // 미리보기 페이지 로드 시작
    
    // 자주 사용하는 DOM 요소 캐싱
    const cachedElements = {
        widthInput: document.getElementById('widthInput'),
        heightInput: document.getElementById('heightInput'),
        fontSizeInput: document.getElementById('fontSizeInput'),
        letterSpacingInput: document.getElementById('letterSpacingInput'),
        lineHeightInput: document.getElementById('lineHeightInput'),
        areaDisplay: document.getElementById('areaDisplay'),
        previewContent: document.getElementById('previewContent'),
        fontFamilySelect: document.getElementById('fontFamilySelect')
    };
    window.cachedElements = cachedElements;
    
    // 데이터 로드 (중복 제거된 코드)
    const nutritionData = safeLoadJsonData('nutrition-data', null, '영양성분 데이터');
    const countryMapping = safeLoadJsonData('country-mapping-data', {}, '국가 매핑 데이터');
    const expiryData = safeLoadJsonData('expiry-recommendation-data', null, '만료일 추천 데이터');

    // [제거] 국가 코드를 한글명으로 변환하는 함수 (constants.py로 이동)

    // 작성일시 정보 설정
    const updateDateTime = document.getElementById('update_datetime')?.value;
    const footerText = document.querySelector('.footer-text');
    if (footerText && updateDateTime) {
        footerText.innerHTML = `
            <span style="font-size: 7pt;">
                EZLABELING.COM에서 관련 법규에 따라 작성되었습니다.
                <span class="creator-info">[${updateDateTime}]</span>
            </span>
        `;
    }

    // 디바운스 함수
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // constants.js에서 로드된 상수들 사용
    const DEFAULT_SETTINGS = window.DEFAULT_SETTINGS;
    const REGULATIONS = { ...window.REGULATIONS };
    const recyclingMarkGroups = window.recyclingMarkGroupsDetailed;
    
    // 백엔드에서 전달된 소비기한 권장 데이터를 REGULATIONS 객체에 주입
    if (expiryData) {
        REGULATIONS.expiry_recommendation = expiryData;
    }

    // ===== 냉동/냉장 판단 헬퍼 함수 =====
    
    /**
     * 냉동 보관 제품 여부 판단
     * @param {string} storageMethod - 보관방법
     * @param {string} foodType - 식품유형
     * @returns {boolean}
     */
    function isFrozenProduct(storageMethod, foodType) {
        const storage = (storageMethod || '').toLowerCase();
        const type = (foodType || '').toLowerCase();
        
        // 1. 키워드 체크
        if (storage.includes('냉동') || type.includes('냉동')) return true;
        
        // 2. -18℃ 이하 온도 체크
        const tempRegex = /(-?\d+(\.\d+)?)\s*(℃|도)/g;
        let match;
        while ((match = tempRegex.exec(storage)) !== null) {
            const tempValue = parseFloat(match[1]);
            if (!isNaN(tempValue) && tempValue <= -18) {
                return true;
            }
        }
        
        return false;
    }

    /**
     * 냉장 보관 제품 여부 판단
     * @param {string} storageMethod - 보관방법
     * @param {string} cautions - 주의사항
     * @param {string} additional - 기타표시사항
     * @returns {boolean}
     */
    function isRefrigeratedProduct(storageMethod, cautions, additional) {
        const storage = (storageMethod || '').toLowerCase();
        const combinedText = ((storageMethod || '') + (cautions || '') + (additional || '')).toLowerCase();
        
        // 1. 키워드 체크
        if (storage.includes('냉장')) return true;
        
        // 2. 0~10℃ 범위 온도 체크
        const rangeRegex = /(\d+(\.\d+)?)\s*~\s*(\d+(\.\d+)?)\s*(℃|도)/g;
        let match;
        while ((match = rangeRegex.exec(combinedText)) !== null) {
            const startTemp = parseFloat(match[1]);
            const endTemp = parseFloat(match[3]);
            if (!isNaN(startTemp) && !isNaN(endTemp) && startTemp >= 0 && endTemp <= 10) {
                return true;
            }
        }
        
        return false;
    }

    // value → 이미지 매핑
    const recyclingMarkMap = {};
    recyclingMarkGroups.forEach(group => {
        group.options.forEach(opt => {
            recyclingMarkMap[opt.value] = opt;
        });
    });

    // 텍스트 라인 ID 카운터 (각 라인에 data-text-id 부여)
    let recyclingTextIdCounter = 0;

    // DOM 준비 상태 확인 함수
    function waitForElement(selector, callback, maxWait = 3000) {
        const element = document.getElementById(selector);
        if (element) {
            callback();
        } else if (maxWait > 0) {
            setTimeout(() => waitForElement(selector, callback, maxWait - 100), 100);
        } else {
            console.warn(`요소를 찾을 수 없습니다: ${selector}`);
        }
    }

    // 설정 UI 요소들 존재 확인 및 생성
    function ensureSettingsElements() {
        
        const requiredElements = [
            { id: 'widthInput', type: 'number', value: '10', min: '5', max: '20', step: '0.1' },
            { id: 'heightInput', type: 'number', value: '11', min: '5', max: '30', step: '0.1' },
            { id: 'fontSizeInput', type: 'number', value: '10', min: '6', max: '20', step: '0.5' },
            { id: 'letterSpacingInput', type: 'number', value: '-5', min: '-10', max: '5', step: '1' },
            { id: 'lineHeightInput', type: 'number', value: '1.2', min: '1.0', max: '2.0', step: '0.1' },
            { id: 'fontFamilySelect', type: 'select', value: "'Noto Sans KR'" }
        ];
        
        let missingElements = [];
        
        requiredElements.forEach(config => {
            const element = document.getElementById(config.id);
            if (!element) {
                missingElements.push(config.id);
                console.warn(`${config.id} 요소가 없습니다. 임시 요소를 생성합니다.`);
                
                // 임시 요소 생성
                const tempElement = config.type === 'select' ? document.createElement('select') : document.createElement('input');
                tempElement.id = config.id;
                tempElement.style.display = 'none'; // 숨김 처리
                
                if (config.type !== 'select') {
                    tempElement.type = config.type;
                    tempElement.min = config.min;
                    tempElement.max = config.max;
                    tempElement.step = config.step;
                }
                
                tempElement.value = config.value;
                document.body.appendChild(tempElement);
            }
        });
        
        if (missingElements.length > 0) {
            console.warn(`누락된 설정 요소들: ${missingElements.join(', ')}`);
        }
    }

    // 전역 함수 설정 (DOM 준비 후 실제 기능 활성화)
    function setupGlobalRecyclingFunctions() {
        // 실제 구현 함수들
        window._applyRecommendedRecyclingMark = function() {
            const packageMaterialSelectors = [
                'input[name="frmlc_mtrqlt"]',
                '#frmlc_mtrqlt',
                'input[placeholder*="포장재질"]',
                'textarea[name="frmlc_mtrqlt"]'
            ];
            
            let packageField = null;
            let packageValue = '';
            
            // 포장재질 필드 찾기
            for (const selector of packageMaterialSelectors) {
                packageField = document.querySelector(selector);
                if (packageField && packageField.value.trim()) {
                    packageValue = packageField.value.trim();
                    break;
                }
            }
            
            if (packageValue) {
                window.updateRecyclingMarkUI(packageValue, true);
                return true;
            } else {
                console.warn('포장재질 정보를 찾을 수 없습니다.');
                return false;
            }
        };

        // 실제 구현: 현재 설정된 분리배출마크 정보 가져오기
        window._getCurrentRecyclingMarkStatus = function() {
            const container = document.getElementById('recyclingMarkContainer');
            const select = document.getElementById('recyclingMarkSelect');
            const addBtn = document.getElementById('addRecyclingMarkBtn');
            
            const status = {
                hasContainer: !!container,
                selectedValue: select ? select.value : null,
                isApplied: addBtn ? addBtn.textContent === '해제' : false,
                containerVisible: container ? container.style.display !== 'none' : false
            };
            
            return status;
        };

        // 실제 구현: 분리배출마크 관련 디버깅 정보
        window._debugRecyclingMark = function() {
            console.group('분리배출마크 디버깅 정보');
            
            // DOM 요소 존재 확인
            const elements = {
                container: document.getElementById('recyclingMarkContainer'),
                select: document.getElementById('recyclingMarkSelect'),
                addBtn: document.getElementById('addRecyclingMarkBtn'),
                uiBox: document.getElementById('recyclingMarkUiBox'),
                list: document.getElementById('recyclingMarkList')
            };
        };

        // 함수 등록 완료 알림 및 상태 설정
        window.recyclingMarkFunctionsReady = true;
        
        // 즉시 사용 가능함을 알리는 이벤트 발생
        window.dispatchEvent(new CustomEvent('recyclingMarkReady'));
    }

    // ===== 분리배출마크 UI 헬퍼 =====
    function clearRecyclingListUI() {
        const list = document.getElementById('recyclingMarkList');
        if (list) list.innerHTML = '';
    }

    function removeRecyclingMarkUI() {
        // 분리배출마크는 label_preview.html 인라인 구현이 맡는다.
        // 둘 다 돌면 마크가 두 개 그려지고, 이쪽 것은 드래그도 삭제도 안 된다.
        if (window.__recyclingMarkOwner === 'inline') return;
        const container = document.getElementById('recyclingMarkContainer');
        if (container) container.remove();
        clearRecyclingListUI();
        const addBtn = document.getElementById('addRecyclingMarkBtn');
        if (addBtn) {
            addBtn.textContent = '적용';
            addBtn.classList.remove('btn-danger');
            addBtn.classList.add('btn-outline-primary');
        }
        const additionalInputBox = document.getElementById('additionalTextInputBox');
        if (additionalInputBox) additionalInputBox.style.display = 'none';
    }

    function renderRecyclingListFromContainer() {
        const list = document.getElementById('recyclingMarkList');
        if (!list) return;
        list.innerHTML = '';
        const container = document.getElementById('recyclingMarkContainer');
        if (!container) return;

        // 마크 항목 (이미지 + 라벨 + 제거 버튼)
        const img = container.querySelector('#recyclingMarkImage');
        const markType = img && img.src ? img.src.split('/').pop().replace('.png','') : null;
    const li = document.createElement('div');
    li.className = 'recycling-item recycling-mark-item';

        if (img && img.src) {
            const thumb = document.createElement('img');
            thumb.src = img.src;
            // sizing handled by .recycling-item img
            li.appendChild(thumb);
        }

    const label = document.createElement('div');
    label.textContent = markType || '';
    label.className = 'recycling-label';
    li.appendChild(label);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-sm btn-role-outline recycling-action-btn';
        removeBtn.textContent = '제거';
        removeBtn.addEventListener('click', function() {
            removeRecyclingMarkUI();
        });
        li.appendChild(removeBtn);

        list.appendChild(li);

        // 텍스트 라인들이 있으면 각각을 리스트에 추가
        const textLines = Array.from(container.querySelectorAll('.recycling-line'));

        // preview에 최대 3줄만 표시, 초과 시 +N으로 표시
        const preview = document.getElementById('recyclingMarkPreviewArea');
        if (preview) preview.innerHTML = '';

        textLines.forEach((line, idx) => {
            const textEl = line.querySelector('.recycling-text-line');
            const tid = line.dataset.textId || null;
            if (textEl) {
                const tli = document.createElement('div');
                tli.className = 'recycling-item recycling-text-item';
                const txt = document.createElement('div');
                txt.textContent = textEl.textContent;
                txt.className = 'recycling-label';
                tli.appendChild(txt);

                const del = document.createElement('button');
                del.className = 'btn btn-sm btn-role-outline';
                del.textContent = '삭제';
                del.addEventListener('click', function() {
                    if (tid) removeRecyclingTextById(tid);
                });
                tli.appendChild(del);
                list.appendChild(tli);

                // preview에 라인 추가(최대 3개만 보여줌)
                if (preview && idx < 3) {
                    const p = document.createElement('div');
                    p.className = 'preview-line';
                    p.textContent = textEl.textContent;
                    preview.appendChild(p);
                }
            }
        });

        // preview 초과 카운트
        if (preview && textLines.length > 3) {
            const more = document.createElement('div');
            more.textContent = `+${textLines.length - 3} 더보기`;
            more.className = 'preview-line more-count';
            preview.appendChild(more);
        }
    }

    function addRecyclingListTextItem(text, id) {
        const list = document.getElementById('recyclingMarkList');
        if (!list) return;
        const tli = document.createElement('div');
        tli.className = 'recycling-item recycling-text-item';
        tli.dataset.textId = id;
        tli.style.cssText = 'display:flex; align-items:center; gap:8px; padding:4px 8px; border-radius:4px; background:var(--modern-gray-50); margin-bottom:4px;';
        const txt = document.createElement('div');
        txt.textContent = text;
        txt.style.flex = '1';
        txt.style.fontSize = '0.85rem';
        tli.appendChild(txt);
        const del = document.createElement('button');
        del.className = 'btn btn-sm btn-role-outline';
        del.textContent = '삭제';
        del.addEventListener('click', function() {
            removeRecyclingTextById(id);
        });
        tli.appendChild(del);
        list.appendChild(tli);
    }

    function removeRecyclingTextById(id) {
        const el = document.querySelector(`#recyclingMarkContainer .recycling-line[data-text-id="${id}"]`);
        if (el) el.remove();
        const ui = document.querySelector(`#recyclingMarkList .recycling-item[data-text-id="${id}"]`) || document.querySelector(`#recyclingMarkList .recycling-item[data-text-id]`);
        // remove matching list item
        const listItem = document.querySelector(`#recyclingMarkList .recycling-item[data-text-id="${id}"]`);
        if (listItem) listItem.remove();
    // preview 동기화
    renderRecyclingListFromContainer();
    }

    // [제거] 포장재질 텍스트로 추천 분리배출마크 구하기 (constants.py로 이동)
    
    // 분리배출마크 UI 생성 및 삽입 (더 견고한 삽입 로직)
    function renderRecyclingMarkUI() {
        // 분리배출마크는 label_preview.html 인라인 구현이 맡는다.
        // 둘 다 돌면 마크가 두 개 그려지고, 이쪽 것은 드래그도 삭제도 안 된다.
        if (window.__recyclingMarkOwner === 'inline') return;
        // 1) 우선 플레이스홀더가 있으면 사용
        const existingPlaceholder = document.getElementById('recyclingMarkUiBox');

        // 2) 플레이스홀더가 없으면 기존의 settings-panel 또는 legacy 탭 컨테이너를 찾음
        const fallbackTargets = [
            document.querySelector('.settings-panel .settings-group'),
            document.querySelector('.settings-panel'),
            document.querySelector('#content-tab .settings-group'),
            document.querySelector('.settings-group')
        ];
        const target = existingPlaceholder || fallbackTargets.find(t => t !== null && t !== undefined);
        if (!target) return; // 삽입 가능한 위치가 없으면 종료

        // 중복 생성 방지: 이미 컨트롤이 채워져 있으면 아무것도 하지 않음
        if (document.getElementById('recyclingMarkControls')) return;

        // uiBox로 플레이스홀더를 재사용하거나 새로 생성
        const uiBox = existingPlaceholder || document.createElement('div');
        uiBox.id = 'recyclingMarkUiBox';
        uiBox.className = uiBox.className ? (uiBox.className + ' settings-row') : 'settings-row';
        // 리스트 기반 UI: 현재 적용된 마크 및 텍스트 목록을 위에 표시
        uiBox.innerHTML = `
            <div class="settings-item" style="flex-direction:column;">
                <label class="form-label" for="recyclingMarkSelect">분리배출마크</label>
                <div id="recyclingMarkList" style="margin-bottom:8px;"></div>

                <!-- 별도 미리보기 영역: 최대 3줄 표시 -->
                <div id="recyclingMarkPreviewArea" class="recycling-mark-preview" aria-label="분리배출마크 미리보기"></div>

                <div id="recyclingMarkControls" style="display:flex; gap:8px; align-items:center; margin-top:8px;">
                    <select id="recyclingMarkSelect" class="form-select form-select-sm" style="flex:1; min-width:0;">
                        ${recyclingMarkGroups.map(group => `
                            <optgroup label="${group.group}">
                                ${group.options.map(opt => `<option value="${opt.value}">${opt.label}</option>`).join('')}
                            </optgroup>
                        `).join('')}
                    </select>
                    <button id="addRecyclingMarkBtn" type="button" class="btn btn-outline-primary btn-sm">적용</button>
                </div>

                <!-- 복합재질 정보 입력 상자: 항상 표시 -->
                <div id="additionalTextInputBox" style="margin-top: 8px; display:flex; gap:8px;">
                    <input type="text" id="additionalRecyclingText" class="form-control form-control-sm" placeholder="복합재질 정보 입력 (예: 본체(종이)/뚜껑(PP))" style="flex:1; min-width:0;" />
                    <button id="addRecyclingTextBtn" type="button" class="btn btn-sm btn-role-primary" style="white-space:nowrap;">추가</button>
                </div>
            </div>
        `;

        // 플레이스홀더가 없었으면 찾아낸 target에 append
        if (!existingPlaceholder) {
            target.appendChild(uiBox);
        }

        // 셀렉트박스 변경 시 버튼 상태 리셋
        const select = document.getElementById('recyclingMarkSelect');
        if (select) {
            select.addEventListener('change', function() {
                const btn = document.getElementById('addRecyclingMarkBtn');
                
                if (btn) {
                    btn.textContent = '적용';
                    btn.classList.remove('btn-danger');
                    btn.classList.add('btn-outline-primary');
                }
            });
        }

        // 적용/해제 버튼 이벤트
        const addBtn = document.getElementById('addRecyclingMarkBtn');
        if (addBtn) {
            addBtn.addEventListener('click', function() {
                const markValue = document.getElementById('recyclingMarkSelect').value;
                if (addBtn.textContent === '적용') {
                    setRecyclingMark(markValue);
                    addBtn.textContent = '해제';
                    addBtn.classList.remove('btn-outline-primary');
                    addBtn.classList.add('btn-danger');
                    renderRecyclingListFromContainer();
                } else {
                    // 해제: 전체 UI 정리
                    removeRecyclingMarkUI();
                }
            });
        }

        // [추가] 텍스트 추가 버튼 이벤트
        const addTextBtn = document.getElementById('addRecyclingTextBtn');
        if (addTextBtn) {
            addTextBtn.addEventListener('click', function() {
                const textInput = document.getElementById('additionalRecyclingText');
                const text = textInput.value.trim();
                if (text) {
                    // [수정] '/'를 기준으로 텍스트를 분리하여 각 줄을 추가
                    const lines = text.split('/');
                    lines.forEach(line => {
                        const trimmedLine = line.trim();
                        if (trimmedLine) {
                            addTextToRecyclingMark(trimmedLine);
                        }
                    });
                    textInput.value = ''; // 입력 필드 초기화
                }
            });
        }
    }

    // 추천 마크 갱신 및 자동 적용 (전역 함수로 만들어 HTML에서 접근 가능)
    window.updateRecyclingMarkUI = function(packageText, autoApply = false) {
        // 분리배출마크는 label_preview.html 인라인 구현이 맡는다.
        // 둘 다 돌면 마크가 두 개 그려지고, 이쪽 것은 드래그도 삭제도 안 된다.
        if (window.__recyclingMarkOwner === 'inline') return;
        const recommended = recommendRecyclingMarkByMaterial(packageText);
        
        // DOM 요소가 준비될 때까지 대기
        waitForElement('recyclingMarkSelect', () => {
            const recommendSpan = document.getElementById('recyclingMarkRecommend');
            const select = document.getElementById('recyclingMarkSelect');
            
            // 추천 텍스트 업데이트
            if (recommendSpan) {
                recommendSpan.textContent = recommended || '추천 없음';
            }
            
            // 셀렉트 박스 업데이트
            if (select && recommended) {
                select.value = recommended;
                
                // 자동 적용이 요청된 경우 마크 생성
                if (autoApply) {
                    setRecyclingMark(recommended, true);
                    
                    // UI 상태 업데이트
                    const addBtn = document.getElementById('addRecyclingMarkBtn');
                    if (addBtn) {
                        addBtn.textContent = '해제';
                        addBtn.classList.remove('btn-outline-primary');
                        addBtn.classList.add('btn-danger');
                    }
                    
                    // 리스트 UI 업데이트
                    renderRecyclingListFromContainer();
                }
            } else if (select) {
                select.value = '';
            }
        });
    };

    // [추가] 분리배출 마크에 텍스트 라인 추가
    function addTextToRecyclingMark(text) {
        const container = document.getElementById('recyclingMarkContainer');
        const image = document.getElementById('recyclingMarkImage');
        const textContainer = document.getElementById('recyclingMarkTextContainer');
        if (!container || !image || !textContainer) return;

        // DocumentFragment를 사용해서 레이아웃 리플로우 최소화
        const fragment = document.createDocumentFragment();

        // 각 라인을 별도의 블록으로 감싸서 CSS로 한 줄 고정을 쉽게 적용
        const lineWrap = document.createElement('div');
        lineWrap.className = 'recycling-line';
        
        // CSS containment로 레이아웃 격리 (실험적)
        lineWrap.style.cssText = `
            display: block !important;
            width: 100% !important;
            box-sizing: border-box !important;
            text-align: center !important;
            contain: layout style !important;
            isolation: isolate !important;
        `;

        const textDiv = document.createElement('div');
        textDiv.textContent = text;
        textDiv.className = 'recycling-text-line';
        
        // 완전히 격리된 스타일 (모든 속성 명시적 설정)
        textDiv.style.cssText = `
            font-weight: 500 !important;
            color: rgb(0, 0, 0) !important;
            line-height: 1.1 !important;
            word-break: keep-all !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            display: inline-block !important;
            font-family: Arial, sans-serif !important;
            font-size: 6pt !important;
            letter-spacing: normal !important;
            word-spacing: normal !important;
            text-transform: none !important;
            text-decoration: none !important;
            text-shadow: none !important;
            font-style: normal !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            background: transparent !important;
            position: static !important;
            float: none !important;
            clear: none !important;
            vertical-align: baseline !important;
            contain: layout style !important;
            isolation: isolate !important;
        `;
        
        // CSS 변수 완전 차단 (all을 사용해서 모든 변수 리셋)
        textDiv.style.setProperty('all', 'unset', 'important');
        textDiv.style.setProperty('display', 'inline-block', 'important');
        textDiv.style.setProperty('font-size', '6pt', 'important');
        textDiv.style.setProperty('font-family', 'Arial, sans-serif', 'important');
        textDiv.style.setProperty('color', 'black', 'important');

        // 고유 ID 부여
        const textId = `rtext-${++recyclingTextIdCounter}`;
        lineWrap.dataset.textId = textId;
        
        // Fragment에 먼저 추가
        lineWrap.appendChild(textDiv);
        fragment.appendChild(lineWrap);
        
        // 한 번에 DOM에 추가 (리플로우 최소화)
        textContainer.appendChild(fragment);

        // 리스트 UI 동기화
        addRecyclingListTextItem(text, textId);
    }

    // [수정] 미리보기 영역에 마크(이미지+텍스트) 추가 및 드래그
    function setRecyclingMark(markValue, auto = false) {
        // 분리배출마크는 label_preview.html 인라인 구현이 맡는다.
        // 둘 다 돌면 마크가 두 개 그려지고, 이쪽 것은 드래그도 삭제도 안 된다.
        if (window.__recyclingMarkOwner === 'inline') return;
        const markObj = recyclingMarkMap[markValue];
        const previewContent = document.getElementById('previewContent');
        if (!previewContent || !markObj) return;

        // 컨테이너를 찾거나 새로 생성
        let container = document.getElementById('recyclingMarkContainer');
        if (container) container.remove(); // 기존 컨테이너가 있으면 제거하고 새로 생성

        container = document.createElement('div');
        container.id = 'recyclingMarkContainer';
        container.className = 'recycling-mark-container';
        
        // 전역 스타일과 CSS 변수로부터 완전히 격리된 컨테이너 스타일
        container.style.cssText = `
            position: absolute !important;
            z-index: 1000 !important;
            width: 60px !important;
            min-width: 60px !important;
            max-width: 60px !important;
            height: auto !important;
            text-align: center !important;
            cursor: move !important;
            background: transparent !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            font-family: Arial, sans-serif !important;
            font-size: 6pt !important;
            line-height: 1.0 !important;
            letter-spacing: 0 !important;
            word-spacing: 0 !important;
            text-transform: none !important;
            text-decoration: none !important;
            text-shadow: none !important;
            font-weight: normal !important;
            font-style: normal !important;
            color: black !important;
            contain: layout style size !important;
            isolation: isolate !important;
            transform: translateZ(0) !important;
        `;
        
        // 모든 CSS 상속 차단
        container.style.setProperty('all', 'unset', 'important');
        container.style.setProperty('position', 'absolute', 'important');
        container.style.setProperty('z-index', '1000', 'important');
        container.style.setProperty('width', '60px', 'important');
        container.style.setProperty('cursor', 'move', 'important');
        container.style.setProperty('contain', 'layout style size', 'important');
        
        // 컨테이너 내부에 이미지와 텍스트 영역 추가
        container.innerHTML = `
            <img id="recyclingMarkImage" class="recycling-mark-image" style="
                display: block !important;
                width: 60px !important;
                height: auto !important;
                margin: 0 auto !important;
                padding: 0 !important;
                border: none !important;
                background: transparent !important;
            ">
            <div id="recyclingMarkTextContainer" class="recycling-mark-text" style="
                width: 100% !important;
                text-align: center !important;
                margin: 0 !important;
                padding: 0 !important;
                background: transparent !important;
                border: none !important;
                font-family: Arial, sans-serif !important;
            "></div>
        `;
        
        // previewContent가 아닌 독립적인 위치에 배치 (CSS 변수 상속 방지)
        const previewWrapper = previewContent.parentElement || document.body;
        previewWrapper.appendChild(container);
        
        // previewContent 기준으로 절대 위치 계산
        const previewRect = previewContent.getBoundingClientRect();
        const wrapperRect = previewWrapper.getBoundingClientRect();
        const relativeTop = previewRect.top - wrapperRect.top;
        const relativeLeft = previewRect.left - wrapperRect.left;

        const img = container.querySelector('#recyclingMarkImage');

        // 이미지 설정 및 에러 처리
        if (markObj.img) {
            img.src = markObj.img;
            img.alt = markObj.label;
            img.style.display = 'block';
            
            // 이미지 로딩 실패 처리
            img.onerror = function() {
                this.style.display = 'none';
                console.warn('분리배출 마크 이미지 로딩 실패:', this.src);
                // 대체 텍스트 표시
                const textContainer = container.querySelector('#recyclingMarkTextContainer');
                if (textContainer && !textContainer.querySelector('.fallback-text')) {
                    const fallbackText = document.createElement('div');
                    fallbackText.className = 'fallback-text recycling-text-line';
                    fallbackText.textContent = markObj.label;
                    fallbackText.style.cssText = 'font-weight: bold; color: #333; padding: 4px;';
                    textContainer.appendChild(fallbackText);
                }
            };
        } else {
            img.style.display = 'none';
        }

        // [수정] 자동 위치 설정: 제품명 행의 우측 상단에 배치 (독립 컨테이너 기준)
        const thElements = previewContent.querySelectorAll('th');
        let productNameRow = null;
        thElements.forEach(th => {
            if (th.textContent.trim() === '제품명') {
                productNameRow = th.parentElement; // <tr> element
            }
        });

        if (productNameRow) {
            const rowRect = productNameRow.getBoundingClientRect();
            
            // 제품명 행의 상단에 맞춤 (wrapper 기준으로 계산)
            const topPosition = rowRect.top - wrapperRect.top;
            const rightPosition = (wrapperRect.right - previewRect.right) + 25;
            
            container.style.top = `${topPosition}px`;
            container.style.right = `${rightPosition}px`;
            container.style.left = '';
            container.style.bottom = '';
        } else {
            // 제품명 행을 찾지 못할 경우의 기본 위치 (예: 우측 하단)
            container.style.top = '';
            container.style.right = '20px';
            container.style.left = '';
            container.style.bottom = '20px';
        }

        // 드래그 로직 (독립 컨테이너 기준으로 수정)
        container.onmousedown = function(e) {
            e.preventDefault();
            let shiftX = e.clientX - container.getBoundingClientRect().left;
            let shiftY = e.clientY - container.getBoundingClientRect().top;
            
            function moveAt(pageX, pageY) {
                const rect = previewWrapper.getBoundingClientRect();
                container.style.left = (pageX - rect.left - shiftX) + 'px';
                container.style.top = (pageY - rect.top - shiftY) + 'px';
                container.style.right = '';
                container.style.bottom = '';
            }

            function onMouseMove(e) {
                moveAt(e.pageX, e.pageY);
            }
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', function mouseUpHandler() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', mouseUpHandler);
            });
        };
    container.ondragstart = () => false;
    // update CSS custom properties to reflect initial inline positions
    // (these properties are optional; CSS has sensible defaults)
    }

    // 미리보기 스타일 업데이트 (임시 비활성화로 테스트)
    function updatePreviewStyles() {
        // 임시로 완전히 비활성화하여 분리배출마크 영향 테스트
        return;
        
        const previewContent = document.getElementById('previewContent');
        if (!previewContent) return;

        const settings = {
            width: parseFloat(document.getElementById('widthInput').value) || 10,
            height: parseFloat(document.getElementById('heightInput').value) || 10,
            fontSize: parseFloat(document.getElementById('fontSizeInput').value) || 10,
            letterSpacing: parseInt(document.getElementById('letterSpacingInput').value) || -5,
            lineHeight: parseFloat(document.getElementById('lineHeightInput').value) || 1.2,
            fontFamily: document.getElementById('fontFamilySelect').value || "'Noto Sans KR'"
        };

    // Apply modern preview content class and set CSS variables for dynamic values
    previewContent.classList.add('preview-content-modern');
    previewContent.style.setProperty('--preview-width', `${settings.width}cm`);
    previewContent.style.setProperty('--preview-font-size', `${settings.fontSize}pt`);
    previewContent.style.setProperty('--preview-letter-spacing', `${settings.letterSpacing / 100}em`);
    previewContent.style.setProperty('--preview-line-height', `${settings.lineHeight}`);
    previewContent.style.setProperty('--preview-font-family', `${settings.fontFamily}`);

        const table = previewContent.querySelector('.preview-table');
    if (table) table.classList.add('preview-table');

        // 분리배출마크 요소들은 제외하고 셀에만 스타일 적용
        const cells = previewContent.querySelectorAll('th, td');
        cells.forEach(cell => {
            // 분리배출마크 관련 요소인지 확인
            const isRecyclingElement = cell.closest('#recyclingMarkContainer') || 
                                     cell.classList.contains('recycling-text-line') ||
                                     cell.classList.contains('recycling-line');
            
            if (!isRecyclingElement) {
                cell.classList.add('preview-cell');
                if (cell.tagName === 'TH') cell.classList.add('preview-header');
            }
        });

    const headerText = previewContent.querySelector('.header-text');
    if (headerText) headerText.classList.add('preview-text');

        requestAnimationFrame(() => {
            const contentHeight = previewContent.scrollHeight;
            const cmHeight = Math.ceil(contentHeight / 37.8);
            const heightInput = document.getElementById('heightInput');
            
            // 이벤트 발생 없이 값만 변경 (연쇄 반응 방지)
            if (heightInput && heightInput.value !== cmHeight.toString()) {
                // 임시로 이벤트 리스너 제거
                const tempValue = heightInput.value;
                heightInput.value = cmHeight;
                
                // updateArea만 직접 호출 (다른 이벤트 체인 방지)
                updateArea();
            }
        });
    }

    // 이벤트 리스너 설정 (중복 제거된 코드)
    function setupEventListeners() {
        const inputIds = ['widthInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput', 'fontFamilySelect'];
        
        // input 이벤트에 디바운스 적용
        addEventListenersToElements(inputIds, 'input', debounce(updatePreviewStyles, 100));
        // change 이벤트에 즉시 적용
        addEventListenersToElements(inputIds, 'change', updatePreviewStyles);

        const resetButton = document.querySelector('button[onclick="resetSettings()"]');
        if (resetButton) {
            resetButton.onclick = null;
            resetButton.addEventListener('click', resetSettings);
        }

        // validateButton 이벤트는 DOMContentLoaded에서 처리
    }

    // 설정 초기화
    function resetSettings() {
        Object.entries(DEFAULT_SETTINGS).forEach(([key, value]) => {
            const element = document.getElementById(`${key}Input`) || 
                          document.getElementById(`${key}Select`);
            if (element) {
                element.value = value;
            }
        });
        document.getElementById('lineHeightInput').value = 1.2;
        updatePreviewStyles();
        updateArea();
    }

    // 면적 계산 (캐싱된 요소 사용)
    function updateArea() {
        const elements = window.cachedElements || {};
        const width = parseFloat(elements.widthInput?.value || document.getElementById('widthInput')?.value) || 0;
        const height = parseFloat(elements.heightInput?.value || document.getElementById('heightInput')?.value) || 0;
        const area = width * height;
        const areaDisplay = elements.areaDisplay || document.getElementById('areaDisplay');
        if (areaDisplay) {
            areaDisplay.textContent = Math.round(area * 100) / 100;
        }
        return area;
    }

    function setupAreaCalculation() {
        const inputIds = ['widthInput', 'heightInput'];
        // 중복 제거된 이벤트 리스너 설정
        addEventListenersToElements(inputIds, 'input', updateArea);
        addEventListenersToElements(inputIds, 'change', updateArea);

        // areaDisplayInput 바인딩: 사용자가 면적을 직접 입력하면 가로(width)를 재계산
        const areaInput = document.getElementById('areaDisplayInput');
        if (areaInput) {
            const onAreaChange = function() {
                const areaVal = parseFloat(areaInput.value) || 0;
                const heightEl = document.getElementById('heightInput');
                const widthEl = document.getElementById('widthInput');
                const heightVal = parseFloat(heightEl?.value) || 0;
                if (heightVal > 0 && widthEl) {
                    const newWidth = Math.max(1, Math.round((areaVal / heightVal) * 100) / 100);
                    widthEl.value = newWidth;
                    updatePreviewStyles();
                    updateArea();
                } else {
                    // 높이가 유효하지 않으면 단순히 디스플레이만 갱신
                    updateArea();
                }
            };
            areaInput.addEventListener('input', debounce(onAreaChange, 150));
            areaInput.addEventListener('change', onAreaChange);
        }
    }

    // 입력값 최소/최대 제한
    function enforceInputMinMax() {
        const fontSizeInput = document.getElementById('fontSizeInput');
        const letterSpacingInput = document.getElementById('letterSpacingInput');
        const lineHeightInput = document.getElementById('lineHeightInput');
        if (fontSizeInput && fontSizeInput.value < 10) fontSizeInput.value = 10;
        if (letterSpacingInput && letterSpacingInput.value < -5) letterSpacingInput.value = -5;
        if (lineHeightInput && lineHeightInput.value < 1.2) lineHeightInput.value = 1.2;

        if (fontSizeInput) {
            fontSizeInput.addEventListener('input', function() {
                if (parseFloat(this.value) < 10) this.value = 10;
            });
        }
        if (letterSpacingInput) {
            letterSpacingInput.addEventListener('input', function() {
                if (parseFloat(this.value) < -5) this.value = -5;
            });
        }
        if (lineHeightInput) {
            lineHeightInput.addEventListener('input', function() {
                if (parseFloat(this.value) < 1.2) this.value = 1.2;
            });
        }
    }

    /*
     * 영양성분 데이터 처리.
     *
     * **함수 안에 있어야 한다.** 예전에는 이 블록이 DOMContentLoaded 본문에
     * 그대로 있었고 맨 앞이 `if (!nutritionData) return;` 이었다. 그런데 이
     * 화면에는 #nutrition-data 요소가 아예 없어서 그 return 이 늘 걸렸고,
     * **뒤에 있는 초기화가 통째로 실행되지 않았다** — PDF 저장·설정 저장
     * 버튼 연결, 세로 길이 계산, 입력 하한, 저장된 설정 불러오기까지 전부.
     *
     * 그동안 PDF 와 설정 저장이 동작한 것은 label_preview.html 인라인
     * 스크립트에 같은 함수가 한 벌 더 있어서 그쪽이 대신 붙여 줬기
     * 때문이다. 그 사본을 걷어내자 이 결함이 드러났다.
     */
    function initNutritionData() {
            try {
            // 통합된 데이터 로드 함수 사용
            if (!nutritionData) {
                return;
            }
        
            // 기본값 보장
            if (!nutritionData.nutrients || Object.keys(nutritionData.nutrients).length === 0) {
                // 기본 영양성분 데이터 설정
                nutritionData.nutrients = {
                    calorie: { value: 0, unit: 'kcal' },
                    natrium: { value: 0, unit: 'mg' },
                    carbohydrate: { value: 0, unit: 'g' },
                    sugar: { value: 0, unit: 'g' },
                    afat: { value: 0.1, unit: 'g' },
                    transfat: { value: 0.1, unit: 'g' },
                    satufat: { value: 0.1, unit: 'g' },
                    cholesterol: { value: 0, unit: 'mg' },
                    protein: { value: 0, unit: 'g' }
                };
            }
        
            // 영양성분 UI 업데이트 (중복 제거된 코드)
            if (nutritionData.serving_size && nutritionData.serving_size_unit) {
                safeSetElementValue('servingSizeDisplay', `${nutritionData.serving_size}${nutritionData.serving_size_unit}`, true);
            }
        
            if (nutritionData.units_per_package) {
                safeSetElementValue('servingsPerPackageDisplay', nutritionData.units_per_package);
            }
        
            if (nutritionData.display_unit) {
                safeSetElementValue('nutritionDisplayUnit', nutritionData.display_unit);
            }
        
            // 영양성분 데이터 구조화
            const data = {
                servingSize: nutritionData.serving_size,
                servingUnit: nutritionData.serving_size_unit,
                servingsPerPackage: nutritionData.units_per_package,
                servingUnitText: nutritionData.serving_size_unit === 'ml' ? '개' : '개',
                displayUnit: nutritionData.display_unit || 'unit',
                totalWeight: nutritionData.serving_size * nutritionData.units_per_package,
                values: []
            };
        
            const nutrientOrder = [
                'natrium', 'carbohydrate', 'sugar', 'afat', 'transfat', 'satufat', 'cholesterol', 'protein'
            ];
            const nutrientLabels = {
                calorie: '열량', natrium: '나트륨', carbohydrate: '탄수화물', sugar: '당류', 
                afat: '지방', transfat: '트랜스지방', satufat: '포화지방', cholesterol: '콜레스테롤', protein: '단백질'
            };
            const nutrientLimits = {
                natrium: 2000, carbohydrate: 324, sugar: 100, afat: 54, satufat: 15, cholesterol: 300, protein: 55
            };
        
            let calorieValue = null, calorieUnit = '';
            if (nutritionData.nutrients && nutritionData.nutrients.calorie) {
                calorieValue = nutritionData.nutrients.calorie.value;
                calorieUnit = nutritionData.nutrients.calorie.unit || 'kcal';
            }
        
            if (nutritionData.nutrients) {
                for (const key of nutrientOrder) {
                    const n = nutritionData.nutrients[key] || {};
                    data.values.push({
                        label: nutrientLabels[key] || key,
                        value: (n.value !== undefined && n.value !== null) ? parseFloat(n.value) : 0,
                        unit: n.unit || '',
                        limit: nutrientLimits[key] || null
                    });
                }
            }
        
            data.calorie = calorieValue;
            data.calorieUnit = calorieUnit;
            window.nutritionData = data;
            updateNutritionDisplay(data);
        
        // 영양성분은 영양성분 탭이 활성화될 때만 표시
        } catch (e) {
            console.error('영양성분 데이터 처리 중 오류:', e);
        // 백업 데이터 로드 시도
        
            // 오류 발생 시 백업 로직: DOM에서 직접 데이터 추출 (중복 제거된 코드)
            try {
                // 유틸리티 함수로 간소화된 백업 데이터 생성
                const getElementValue = (id, defaultValue = '0') => document.getElementById(id)?.value || defaultValue;
            
                const backupData = {
                    serving_size: getElementValue('serving_size', '100'),
                    serving_size_unit: getElementValue('serving_size_unit', 'g'),
                    units_per_package: getElementValue('units_per_package', '1'),
                    display_unit: getElementValue('nutrition_display_unit', 'unit'),
                    nutrients: {
                        calorie: { value: getElementValue('calories'), unit: 'kcal' },
                        natrium: { value: getElementValue('natriums'), unit: 'mg' },
                        carbohydrate: { value: getElementValue('carbohydrates'), unit: 'g' },
                        sugar: { value: getElementValue('sugars'), unit: 'g' },
                        afat: { value: getElementValue('fats'), unit: 'g' },
                        transfat: { value: getElementValue('trans_fats'), unit: 'g' },
                        satufat: { value: getElementValue('saturated_fats'), unit: 'g' },
                        cholesterol: { value: getElementValue('cholesterols'), unit: 'mg' },
                        protein: { value: getElementValue('proteins'), unit: 'g' }
                    }
                };
            
                // 백업 데이터로 UI 업데이트
                safeSetElementValue('servingSizeDisplay', `${backupData.serving_size}${backupData.serving_size_unit}`);
            
            } catch (backupError) {
                console.error('❌ 백업 데이터 로드도 실패:', backupError);
            }
        
        // 백업 데이터 로드 완료
        }
    }

    initNutritionData();

    // 탭 전환 처리
    function handleTabSwitch() {
        const activeTab = document.querySelector('.nav-link.active[data-bs-toggle="tab"]');
        const previewTable = document.querySelector('.preview-table');
        const nutritionPreview = document.getElementById('nutritionPreview');
        const headerBox = document.querySelector('.preview-header-box');
        const markImage = document.getElementById('recyclingMarkImage');
        if (!activeTab) return;

        if (activeTab.getAttribute('data-bs-target') === '#nutrition-tab') {
            if (previewTable) previewTable.style.display = 'none';
            if (headerBox) headerBox.style.display = 'none';
            if (nutritionPreview) nutritionPreview.style.display = 'block';
            if (markImage) markImage.style.display = 'none';
        } else {
            if (previewTable) previewTable.style.display = 'table';
            if (headerBox) headerBox.style.display = 'block';
            if (nutritionPreview) nutritionPreview.style.display = 'none';
            if (markImage) markImage.style.display = 'block';
        }
    }

    document.querySelectorAll('.nav-link[data-bs-toggle="tab"]').forEach(btn => {
        btn.addEventListener('shown.bs.tab', handleTabSwitch);
    });
    
    // 페이지 로드 시 초기 탭 상태 설정
    function initializeTabState() {
        const nutritionPreview = document.getElementById('nutritionPreview');
        const previewTable = document.querySelector('.preview-table');
        const headerBox = document.querySelector('.preview-header-box');
        const markImage = document.getElementById('recyclingMarkImage');
        
        // 기본적으로 표시사항 탭이 활성화되어 있으므로
        if (nutritionPreview) nutritionPreview.style.display = 'none';
        if (previewTable) previewTable.style.display = 'table';
        if (headerBox) headerBox.style.display = 'block';
        if (markImage) markImage.style.display = 'block';
        
    // 초기 탭 상태 설정 완료 - 표시사항 탭 표시
    }
    
    // 초기화 실행
    initializeTabState();
    handleTabSwitch();

    // 체크된 필드 렌더링
    const FIELD_LABELS = {
        my_label_name: '라벨명',
        prdlst_dcnm: '식품유형',
        prdlst_nm: '제품명',
        ingredient_info: '특정성분 함량',
        content_weight: '내용량',
        weight_calorie: '내용량(열량)',
        prdlst_report_no: '품목보고번호',
        country_of_origin: '원산지',
        storage_method: '보관 방법',
        frmlc_mtrqlt: '용기·포장재질',
        bssh_nm: '제조원 소재지',
        distributor_address: '유통전문판매원',
        repacker_address: '소분원',
        importer_address: '수입원',
        pog_daycnt: '소비기한',
        rawmtrl_nm_display: '원재료명',
        cautions: '주의사항',
        additional_info: '기타표시사항',
        nutrition_text: '영양성분'
    };

    // 표시사항 작성 페이지 순서에 맞는 필드 순서
    const FIELD_ORDER = [
        'my_label_name',      // 라벨명
        'prdlst_dcnm',        // 식품유형
        'prdlst_nm',          // 제품명
        'rawmtrl_nm_display', // 원재료명
        'ingredient_info',    // 특정성분 함량
        'content_weight',     // 내용량
        'weight_calorie',     // 내용량(열량)
        'prdlst_report_no',   // 품목보고번호
        'country_of_origin',  // 원산지
        'storage_method',     // 보관 방법
        'frmlc_mtrqlt',       // 용기·포장재질
        'bssh_nm',            // 제조원 소재지
        'distributor_address', // 유통전문판매원
        'repacker_address',   // 소분원
        'importer_address',   // 수입원
        'pog_daycnt',         // 소비기한
        'cautions',           // 주의사항
        'additional_info',    // 기타표시사항
        'nutrition_text'      // 영양성분
    ];

    // 필드 데이터 저장소
    let checkedFields = {};
    // checkedFields를 전역에서 접근 가능하도록 설정
    window.checkedFields = checkedFields;
    const tbody = document.getElementById('previewTableBody');
    let dataLoaded = false; // 데이터 로딩 상태 플래그

    // [추가] 로딩 상태 초기화 및 타임아웃 설정
    if (tbody) {
        // 1. 초기 "로딩 중" 메시지 표시
        tbody.innerHTML = `
            <tr>
                <td colspan="2" style="text-align:center; padding: 20px; color: #6c757d;">
                    로딩 중입니다...
                </td>
            </tr>
        `;

        // 2. 로딩 실패 처리를 위한 타임아웃 설정
        setTimeout(() => {
            if (!dataLoaded) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="2" style="text-align:center; padding: 20px; color: #dc3545; font-weight: bold;">
                            로딩에 실패하였습니다. 다시 시도해주세요.
                        </td>
                    </tr>
                `;
            }
        }, 5000); // 5초 후에도 데이터가 로드되지 않으면 실패로 간주
    }


    // [제거] 국가명 볼드 처리 함수 (constants.py로 이동)

    // 국가명 목록 초기화 (중복 제거된 코드)
    const countryList = safeLoadJsonData('country-list-data', [], '국가명 목록');

    // 입력 데이터 반영 (테스트용)
    window.addEventListener('message', function(e) {
        if (e.data?.type === 'previewCheckedFields' && e.data.checked) {
            dataLoaded = true; // 데이터 로딩 성공 플래그 설정
            checkedFields = e.data.checked;
            // const tbody = document.getElementById('previewTableBody'); // 상단에서 이미 정의됨
            if (!tbody) return;

            tbody.innerHTML = ''; // 로딩 또는 에러 메시지 제거
            
            // 표시사항 작성 페이지 순서에 맞게 필드를 정렬하여 렌더링
            FIELD_ORDER.forEach(field => {
                const value = checkedFields[field];
                if (FIELD_LABELS[field] && value) {
                    const tr = document.createElement('tr');
                    const th = document.createElement('th');
                    const td = document.createElement('td');
                    th.textContent = FIELD_LABELS[field];

                    if (field === 'rawmtrl_nm_display') {
                        const allergenMatch = value.match(/\[알레르기 성분\s*:\s*([^\]]+)\]/);
                        const gmoMatch = value.match(/\[GMO\s*성분\s*:\s*([^\]]+)\]/);
                        const container = document.createElement('div');
                        container.style.cssText = `
                            position: relative;
                            width: 100%;
                        `;

                        let mainText = value
                            .replace(/\[알레르기 성분\s*:[^\]]+\]/, '')
                            .replace(/\[GMO\s*성분\s*:[^\]]+\]/, '')
                            .trim();

                        if (!mainText) {
                            // mainText가 비어있으면 빈 문자열로 처리 (null 또는 undefined 방지)
                            mainText = '';
                        }

                        // 국가명 볼드 처리 적용
                        const processedText = boldCountryNames(mainText, countryList);

                        const mainDiv = document.createElement('div');
                        mainDiv.innerHTML = processedText
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/&lt;strong&gt;/g, '<strong>')
                            .replace(/&lt;\/strong&gt;/g, '</strong>');
                        mainDiv.style.cssText = `
                            margin-bottom: 8px;
                            word-break: break-all;
                        `;
                        container.appendChild(mainDiv);

                        // 알레르기 성분 표시
                        if (allergenMatch) {
                            const allergens = allergenMatch[1].trim();
                            const allergenDiv = document.createElement('div');
                            allergenDiv.textContent = `${allergens} 함유`;
                            // 스타일은 CSS 클래스가 갖는다 — 인라인 9pt 로 박으면
                            // 글자 크기 설정을 올려도 이 줄만 그대로 남는다.
                            allergenDiv.className = 'pv-allergen-box';
                            container.appendChild(allergenDiv);
                        }

                        // GMO 성분 표시
                        if (gmoMatch) {
                            const gmo = gmoMatch[1].trim();
                            const gmoDiv = document.createElement('div');
                            gmoDiv.textContent = `${gmo}(GMO)`;
                            gmoDiv.className = 'pv-allergen-box pv-gmo-box';
                            container.appendChild(gmoDiv);
                        }

                        // 플로트 클리어를 위한 클리어픽스
                        const clearDiv = document.createElement('div');
                        clearDiv.style.cssText = 'clear: both;';
                        container.appendChild(clearDiv);

                        td.appendChild(container);
                    } else if (field === 'country_of_origin') {
                        // 원산지 필드: 국가 코드를 한글명으로 변환 후 국가명 볼드 처리
                        const convertedValue = convertCountryCodeToKorean(value);
                        const processedOriginText = boldCountryNames(convertedValue, countryList);
                        td.innerHTML = processedOriginText
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/&lt;strong&gt;/g, '<strong>')
                            .replace(/&lt;\/strong&gt;/g, '</strong>');
                    } else {
                        // 다른 필드들은 국가 코드 변환 없이 국가명이 포함된 경우만 볼드 처리
                        if (typeof value === 'string') {
                            td.innerHTML = boldCountryNames(value, countryList);
                        } else {
                            td.textContent = value;
                        }
                    }
                    tr.appendChild(th);
                    tr.appendChild(td);
                    tbody.appendChild(tr);
                }
            });

            // 분리배출마크 UI 렌더링 및 자동 설정
            renderRecyclingMarkUI();

            // 테이블 내용 생성 후 스타일 적용 (분리배출마크 생성 전에 실행하여 간섭 방지)
            updatePreviewStyles();
            
            // 포장재질 기반 자동 분리배출마크 설정
            const frmlc = checkedFields.frmlc_mtrqlt || '';
            
            if (frmlc) {
                // 포장재질 감지: frmlc
                // 이 함수는 label_preview.html 인라인 스크립트에 있다. 없는
                // 화면에서 부르면 ReferenceError 가 나고, **그 순간 이 핸들러가
                // 통째로 멈춘다** — 분리배출마크를 옮기지도 지우지도 못하게 된
                // 것이 이것 때문이었다.
                const recommendedMark = (typeof recommendRecyclingMarkByMaterial === 'function')
                    ? recommendRecyclingMarkByMaterial(frmlc) : '';
                if (recommendedMark) {
                    // UI가 렌더링된 후 자동 설정
                    waitForElement('recyclingMarkSelect', () => {
                        const selectElement = document.getElementById('recyclingMarkSelect');
                        if (selectElement) {
                            // 옵션 확인 및 자동 적용
                            selectElement.value = recommendedMark;
                            setRecyclingMark(recommendedMark, true);
                            
                            // UI 상태 업데이트
                            const addBtn = document.getElementById('addRecyclingMarkBtn');
                            if (addBtn) {
                                addBtn.textContent = '해제';
                                addBtn.classList.remove('btn-outline-primary');
                                addBtn.classList.add('btn-danger');
                            }
                            
                            const additionalInputBox = document.getElementById('additionalTextInputBox');
                            if (additionalInputBox) {
                                additionalInputBox.style.display = isCompositeMaterial(recommendedMark) ? 'flex' : 'none';
                            }
                            
                            // 리스트 UI 업데이트
                            renderRecyclingListFromContainer();
                        }
                    });
                } else {
                    // 추천 마크 없음: 선택박스만 업데이트
                    waitForElement('recyclingMarkSelect', () => {
                        const select = document.getElementById('recyclingMarkSelect');
                        if (select) {
                            select.value = '';
                        }
                    });
                }
            } else {
                // 포장재질 정보 없음: 초기화
                const recommendSpan = document.getElementById('recyclingMarkRecommend');
                const select = document.getElementById('recyclingMarkSelect');
                if (recommendSpan) recommendSpan.textContent = '';
                if (select) select.value = '';
            }
        }
    });

    // 설정 저장
    function savePreviewSettings() {
        const labelId = document.querySelector('input[name="label_id"]')?.value;
        if (!labelId) {
            return;
        }

        // 분리배출마크 정보 수집
        const recyclingMarkInfo = getCurrentRecyclingMarkInfo();

        // 입력 요소들 확인
        //
        // layoutSelect 는 없앴다. 템플릿에 그런 요소가 없어서 늘 폴백('vertical')이
        // 저장됐고, 2단배치를 골라 두고 저장해도 세로로 되돌아왔다. 레이아웃은
        // 배치 버튼이 쥐고 있는 fieldOrderData.layoutMode 가 답이다.
        const elements = {
            widthInput: document.getElementById('widthInput'),
            heightInput: document.getElementById('heightInput'),
            fontFamilySelect: document.getElementById('fontFamilySelect'),
            fontSizeInput: document.getElementById('fontSizeInput'),
            letterSpacingInput: document.getElementById('letterSpacingInput'),
            lineHeightInput: document.getElementById('lineHeightInput')
        };

        const fieldLayout = typeof window.getFieldLayoutForSave === 'function'
            ? window.getFieldLayoutForSave() : null;

        const data = {
            label_id: labelId,
            layout: (fieldLayout && fieldLayout.layoutMode) || 'vertical',
            // 항목 순서·폭·배치. 지금까지 이것만 브라우저에 남아서, 라벨을 옮기면
            // 순서가 따라오지 않고 동료는 다른 모양을 봤다.
            field_layout: fieldLayout,
            width: parseFloat(elements.widthInput?.value) || 10,
            length: parseFloat(elements.heightInput?.value) || 10,
            font: elements.fontFamilySelect?.value || "'Noto Sans KR'",
            font_size: parseFloat(elements.fontSizeInput?.value) || 10,
            letter_spacing: parseInt(elements.letterSpacingInput?.value) || -5,
            line_spacing: parseFloat(elements.lineHeightInput?.value) || 1.2,
            recycling_mark: recyclingMarkInfo
        };

        fetch('/label/save_preview_settings/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || ''
            },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(res => {
            if (res.success) {
                // 성공 메시지 표시
                const saveBtn = document.getElementById('saveSettingsBtn');
                const originalText = saveBtn.textContent;
                saveBtn.textContent = '저장완료';
                saveBtn.classList.remove('btn-outline-success');
                saveBtn.classList.add('btn-success');
                
                setTimeout(() => {
                    saveBtn.textContent = originalText;
                    saveBtn.classList.remove('btn-success');
                    saveBtn.classList.add('btn-outline-success');
                }, 2000);
            } else {
                alert('미리보기 설정 저장 실패: ' + (res.error || ''));
            }
        })
        .catch(err => {
            console.error('저장 에러:', err);
            alert('미리보기 설정 저장 에러: ' + err);
        });
    }

    // 저장된 미리보기 설정 로드 (중복 제거된 코드)
    function loadSavedPreviewSettings() {
        
        try {
            const settingsScript = document.getElementById('preview-settings-data');
            if (!settingsScript) {
                return;
            }
            
            const textContent = settingsScript.textContent?.trim();
            
            // 통합된 JSON 파싱 함수 사용
            const settings = safeParseJson(textContent, '미리보기 설정');
            
            // 분리배출마크 설정 복원
            const recyclingMark = settings.recycling_mark;
            if (recyclingMark && recyclingMark.enabled && recyclingMark.type) {
                waitForElement('recyclingMarkSelect', () => {
                    restoreRecyclingMark(recyclingMark);
                });
            }
            
        } catch (error) {
            console.error('설정 로드 중 오류:', error);
        }
    }

    // 분리배출마크 복원
    function restoreRecyclingMark(markData) {
        if (!markData.type) return;
        
        // 분리배출마크 설정 (기존 setRecyclingMark 함수 활용)
        // markData.type에서 실제 값 찾기
        let markValue = markData.type;
        
        // recyclingMarkMap에서 해당 타입 찾기
        const foundEntry = Object.entries(recyclingMarkMap).find(([key, value]) => {
            const imageName = value.img.split('/').pop().replace('.png', '');
            return imageName === markData.type || key === markData.type;
        });
        
        if (foundEntry) {
            markValue = foundEntry[0];
            
            // 셀렉트 박스에서 해당 값 선택
            const selectElement = document.getElementById('recyclingMarkSelect');
            if (selectElement) {
                selectElement.value = markValue;
            }
            
            // 분리배출마크 설정
            setRecyclingMark(markValue, false);
            
            // 버튼 텍스트를 "해제"로 변경
            setTimeout(() => {
                const addBtn = document.getElementById('addRecyclingMarkBtn');
                if (addBtn) {
                    addBtn.textContent = '해제';
                    addBtn.classList.remove('btn-outline-primary');
                    addBtn.classList.add('btn-danger');
                }
                
                // 추가 텍스트 입력 박스도 표시
                const additionalInputBox = document.getElementById('additionalTextInputBox');
                if (additionalInputBox) {
                    additionalInputBox.style.display = 'block';
                }
            }, 50);
            
            // 위치 설정 (약간의 딜레이 후)
            setTimeout(() => {
                const markElement = document.getElementById('recyclingMarkContainer');
                if (markElement) {
                    if (markData.position_x.startsWith('right:')) {
                        markElement.style.right = markData.position_x.replace('right:', '') + 'px';
                        markElement.style.left = 'auto';
                    } else {
                        markElement.style.left = markData.position_x + 'px';
                        markElement.style.right = 'auto';
                    }
                    markElement.style.top = markData.position_y + 'px';
                }
                
                // 추가 텍스트 설정
                if (markData.text) {
                    // 기존 텍스트 라인 초기화
                    const textContainer = document.getElementById('recyclingMarkTextContainer');
                    if (textContainer) textContainer.innerHTML = '';

                    // 저장된 텍스트는 '/'로 구분된 여러 라인일 수 있으므로 분리하여 복원
                    const lines = String(markData.text).split('/');
                    lines.forEach(line => {
                        const trimmed = line.trim();
                        if (trimmed) addTextToRecyclingMark(trimmed);
                    });
                    // 리스트 UI 동기화
                    renderRecyclingListFromContainer();
                }
            }, 100);
        } else {
            console.warn('분리배출마크 타입을 찾을 수 없음:', markData.type);
        }
    }

    // 현재 분리배출마크 정보 수집
    function getCurrentRecyclingMarkInfo() {
        const markElement = document.getElementById('recyclingMarkContainer');
        if (!markElement) {
            return {
                enabled: false,
                type: null,
                position_x: null,
                position_y: null,
                text: null
            };
        }

        const style = markElement.style;
        const imgElement = markElement.querySelector('#recyclingMarkImage');
        // 우선 `.recycling-text-line` 요소들(개별 라인)을 찾아 합쳐서 반환
        const textLines = Array.from(markElement.querySelectorAll('.recycling-text-line'));
        let aggregatedText = null;
        if (textLines.length > 0) {
            aggregatedText = textLines.map(el => el.textContent.trim()).filter(Boolean).join('/');
        }
        const textElement = aggregatedText ? { textContent: aggregatedText } : markElement.querySelector('.recycling-text');
        
        // 이미지 src에서 파일명 추출
        let markType = null;
        if (imgElement && imgElement.src) {
            const srcParts = imgElement.src.split('/');
            const fileName = srcParts[srcParts.length - 1];
            markType = fileName.replace('.png', '');
        }
        
        return {
            enabled: true,
            type: markType,
            position_x: style.left ? style.left.replace('px', '') : (style.right ? 'right:' + style.right.replace('px', '') : '0'),
            position_y: style.top ? style.top.replace('px', '') : '0',
            text: textElement ? textElement.textContent : null
        };
    }

    // [제거] 농수산물 목록 및 사용금지 문구 (템플릿에서 전달됨)

    // [제거] 제품명 성분 표시 검증 로직 (checkFarmSeafoodCompliance) (constants.py로 이동)

    // 2. 알레르기 성분 검증: 중복 표시 및 누락 검사


    // 헬퍼 함수: 냉장보관 온도 확인 (하위 호환성 유지)
    function hasRefrigerateTemp() {
        return isRefrigeratedProduct(
            checkedFields.storage_method,
            checkedFields.cautions,
            checkedFields.additional_info
        );
    }

    // 3. 냉동식품 문구 및 온도, 보관조건, 필수 문구 통합
    function checkFoodTypePhrasesUnified() {
        const errors = [];
        const suggestions = [];
        const storageMethod = (checkedFields.storage_method || '').trim();
        const foodType      = (checkedFields.prdlst_dcnm || '').trim();
        const cautions      = (checkedFields.cautions || '').trim();
        const additional    = (checkedFields.additional_info || '').trim();

        // --- 통합된 검증 로직 ---

        // 1. 냉동 조건 검증
        if (isFrozenProduct(storageMethod, foodType)) {
            // 1-1. 보관방법에 "냉동" 키워드 확인
            const hasKeyword = storageMethod.toLowerCase().includes('냉동');
            if (!hasKeyword) {
                errors.push('냉동 보관 제품은 보관방법에 "냉동 보관" 문구를 포함해야 합니다.');
            }
            
            // 1-2. 보관방법에 온도(-18℃ 이하) 표시 확인
            const tempRegex = /(-?\d+(\.\d+)?)\s*(℃|도)/g;
            let hasTemp = false;
            let match;
            while ((match = tempRegex.exec(storageMethod)) !== null) {
                const tempValue = parseFloat(match[1]);
                if (!isNaN(tempValue) && tempValue <= -18) {
                    hasTemp = true;
                    break;
                }
            }
            if (!hasTemp) {
                errors.push('냉동 보관 제품은 보관방법에 온도(-18℃ 이하)를 표시해야 합니다.');
            }
            
            // 1-3. 주의사항/기타표시사항에 필수 문구 확인
            const combinedText = (cautions + additional).toLowerCase();
            const hasRequiredFrozenKeywords = combinedText.includes('해동') || combinedText.includes('재냉동');
            if (!hasRequiredFrozenKeywords) {
                errors.push('냉동 보관 제품은 주의사항 또는 기타표시사항에 "해동" 또는 "재냉동" 관련 문구를 포함해야 합니다.');
            }
        }

        // 2. 냉장 조건 검증
        if (isRefrigeratedProduct(storageMethod, cautions, additional)) {
            // 2-1. 보관방법에 "냉장" 키워드 확인
            const hasKeyword = storageMethod.toLowerCase().includes('냉장');
            if (!hasKeyword) {
                errors.push('냉장 보관 제품은 보관방법에 "냉장 보관" 문구를 포함해야 합니다.');
            }
            
            // 2-2. 보관방법에 온도(0~10℃ 범위 내) 표시 확인
            let hasTemp = false;
            
            // 온도 범위 체크 (예: 0~10℃, 2~8℃, 0~5℃ 등)
            const rangeRegex = /(\d+(\.\d+)?)\s*~\s*(\d+(\.\d+)?)\s*(℃|도)/g;
            let match;
            while ((match = rangeRegex.exec(storageMethod)) !== null) {
                const startTemp = parseFloat(match[1]);
                const endTemp = parseFloat(match[3]);
                // 시작온도와 종료온도가 모두 0~10도 범위 내에 있으면 적합
                if (!isNaN(startTemp) && !isNaN(endTemp) && startTemp >= 0 && endTemp <= 10) {
                    hasTemp = true;
                    break;
                }
            }
            
            // 단일 온도 체크 (예: 5℃, 8℃ 등)
            if (!hasTemp) {
                const singleTempRegex = /(-?\d+(\.\d+)?)\s*(℃|도)/g;
                while ((match = singleTempRegex.exec(storageMethod)) !== null) {
                    const temp = parseFloat(match[1]);
                    // 온도가 0~10도 범위 내에 있으면 적합
                    if (!isNaN(temp) && temp >= 0 && temp <= 10) {
                        hasTemp = true;
                        break;
                    }
                }
            }
            
            if (!hasTemp) {
                errors.push('냉장 보관 제품은 보관방법에 온도(0~10℃ 범위 내)를 표시해야 합니다.');
            }
        }

        // --- 이하 기존 로직 유지 ---

        // 즉석조리식품: 조리방법
        if (foodType.includes("즉석조리") || foodType.includes("즉석 식품")) {
            const hasCooking = cautions.includes("조리방법") || additional.includes("조리방법");
            if (!hasCooking) {
                errors.push('즉석조리식품은 기타표시사항에 "조리방법"을 표시해야 합니다.');
            }
        }

        // 유제품: 지방함량/멸균방식/냉장보관(℃ 범위)
        const dairyKeywords = ["우유", "치즈", "발효유", "요구르트", "유제품"];
        const isDairy = dairyKeywords.some(keyword => foodType.includes(keyword));
        if (isDairy) {
            const hasFatRegex = /지방.*\(\s*%\s*\)/;
            const hasFat = hasFatRegex.test(cautions) || hasFatRegex.test(additional);
            if (!hasFat) {
                errors.push('조건: 유제품 | 항목: 주의사항/기타표시사항 | 문구: "지방함량(%)"');
            }
            const hasSteril = /멸균/.test(cautions) || /멸균/.test(additional);
            if (!hasSteril) {
                errors.push('조건: 유제품 | 항목: 주의사항/기타표시사항 | 문구: "멸균방식"');
            }
            if (!hasRefrigerateTemp()) {
                errors.push('조건: 유제품 | 항목: 보관방법/주의사항/기타표시사항 | 문구: "냉장보관(0~10℃)"');
            }
        }

        // 필수 문구 (REGULATIONS.food_type_phrases)
        let requiredPhrases = [];
        Object.keys(REGULATIONS.food_type_phrases).forEach(key => {
            if (foodType.includes(key)) {
                requiredPhrases = requiredPhrases.concat(REGULATIONS.food_type_phrases[key]);
            }
        });
        // "해동 후 재냉동 금지"는 위에서 이미 처리하므로 중복 방지
        requiredPhrases = requiredPhrases.filter(phrase => phrase !== "해동 후 재냉동 금지");
        requiredPhrases.forEach(phrase => {
            if (!cautions.includes(phrase) && !additional.includes(phrase)) {
                errors.push(`조건: 식품유형("${foodType}") | 항목: 주의사항/기타표시사항 | 문구: "${phrase}"`);
            }
        });

        // 1399 문구
        const reportPhrase = "부정·불량식품신고는 국번없이 1399";
        const hasReport = cautions.includes("1399") || additional.includes("1399");
        if (!hasReport) {
            errors.push('모든 식품에는 "부정불량식품신고는 국번없이 1399"를 표시해야 합니다.');
        }

        return { errors, suggestions };
    }

    // 4. 사용 금지 문구
    function checkForbiddenPhrases() {
        const errors = [];
        const suggestions = [];
        const fieldsToCheck = [
            'prdlst_nm', 'ingredient_info', 'rawmtrl_nm_display', 'cautions', 'additional_info'
        ];
        fieldsToCheck.forEach(field => {
            let value = (checkedFields[field] || '').toString();
            forbiddenPhrases.forEach(phrase => {
                // "원재료명"에 "천연"이 포함된 경우, 에러/수정제안 및 사용조건 안내를 반드시 표시
                if (value && value.match(new RegExp(phrase, 'i'))) {
                    if (field === 'rawmtrl_nm_display' && phrase === '천연') {
                        // 에러/수정제안 및 사용조건 안내
                        let msg = `<strong>"${FIELD_LABELS[field]}" 항목에 사용 금지 문구 "${phrase}"가 표시되어 있습니다.</strong>`;
                        let suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}" 항목에 "${phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요.</strong><br>` +
                            '<span style="color:#888;">사용 조건:<br>' +
                            '① 원료 중에 합성향료·합성착색료·방부제 등 어떠한 인공 화학 성분도 전혀 포함되어 있지 않아야 함<br>' +
                            '② 최소한의 물리적 가공(세척·절단·동결·건조 등)만 거친 상태여야 함<br>' +
                            '③ “천연”과 유사한 의미로 오인될 수 있는 “자연산(naturel)” 등의 외국어 사용도 동일 기준 적용<br>' +
                            '④ 식품유형별로 별도 금지 사항(「식품등의 표시기준」의 개별 고시 규정)이 있는 경우, 그 규정에 따라 추가 제한이 있음<br>' +
                            '⑤ 예: 설탕에는 “천연설탕”이라는 표현이 불가<br>' +
                            '⑥ 영업소 명칭 또는 등록상표에 포함된 경우는 허용<br>' +
                            '⑦ “천연향료” 등 고시된 허용 목록 내 용어만 예외적으로 허용</span>';
                        errors.push(`${msg}<br>${suggestion}`);
                        // value에서 "천연" 및 유사 영문 제거
                        value = value.replace(/천연/gi, '').replace(/natural/gi, '').replace(/naturel/gi, '');
                        checkedFields[field] = value.trim();
                        // 전역 노출 강화
                        window.checkedFields = checkedFields;
                        return;
                    }
                    // ...기존 자연 등 다른 문구 처리...
                    let msg = `<strong>"${FIELD_LABELS[field]}" 항목에 사용 금지 문구 "${phrase}"가 표시되어 있습니다.</strong>`;
                    let suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}"에서 "${phrase}" 문구를 삭제하세요.</strong>`;
                    if (field === 'rawmtrl_nm_display' && phrase === '자연') {
                        suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}" 항목에 "${phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요.</strong><br>` +
                            '<span style="color:#888;">사용 조건:<br>' +
                            '① “자연”이라는 용어는 가공되지 않은 농산물·임산물·수산물·축산물에 대해서만 허용<br>' +
                            '② 수확하여 세척·포장만 거친 원물(raw agricultural/seafood/livestock products)에만 허용<br>' +
                            '③ 이미 “가공식품”으로 분류된 상태라면 “자연” 표기가 불가능<br>' +
                            '④ 유전자변형식품, 나노식품 등은 “자연” 표기가 금지됨<br>' +
                            '⑤ 영업소 명칭 또는 등록상표에 포함된 경우는 허용<br>' +
                            '⑥ 단, 제품명(product name) 자체에 “천연”·“자연”을 붙일 수는 없음</span>';
                    }
                    errors.push(`${msg}<br>${suggestion}`);
                }
            });
        });
        return { errors, suggestions: [] };
    }

    // 5. 분리배출마크
    function checkRecyclingMarkCompliance() {
        const errors = [];
        const suggestions = [];
        const packageMaterial = (checkedFields.frmlc_mtrqlt || '').toLowerCase();
        const select = document.getElementById('recyclingMarkSelect');
        const selectedMark = select ? select.value : '';

        if (!packageMaterial) {
            errors.push('포장재질을 표시하세요.');
            return { errors, suggestions };
        }

        // 사용자가 마크를 선택하지 않았으면 검증하지 않음
        if (!selectedMark || selectedMark === '미표시') {
            return { errors, suggestions };
        }

        // 마크와 재질 키워드 간의 호환성 검증 헬퍼 함수
        const isCompatible = (mark, materialKeywords) => {
            return materialKeywords.some(keyword => packageMaterial.includes(keyword));
        };

        let compatible = false;
        switch (selectedMark) {
            case '무색페트':
                compatible = isCompatible(selectedMark, ['pet', '페트', '무색']);
                break;
            case '유색페트':
                compatible = isCompatible(selectedMark, ['pet', '페트', '유색']);
                break;
            case '플라스틱(PET)':
                compatible = isCompatible(selectedMark, ['pet', '페트']);
                break;
            case '플라스틱(LDPE)':
                compatible = isCompatible(selectedMark, ['ldpe', '저밀도', '폴리에틸렌', 'pe']);
                break;
            case '플라스틱(HDPE)':
                compatible = isCompatible(selectedMark, ['hdpe', '고밀도', '폴리에틸렌', 'pe']);
                break;
            case '플라스틱(PP)':
                compatible = isCompatible(selectedMark, ['pp', '피피', '폴리프로필렌']);
                break;
            case '플라스틱(PS)':
                compatible = isCompatible(selectedMark, ['ps', '피에스', '폴리스티렌']);
                break;
            case '기타플라스틱':
                compatible = isCompatible(selectedMark, ['기타', '플라스틱', 'other']);
                break;
            case '캔류(철)':
                compatible = isCompatible(selectedMark, ['철', 'steel', '캔']);
                break;
            case '캔류(알미늄)':
                compatible = isCompatible(selectedMark, ['알미늄', '알루미늄', 'aluminum', 'al', '캔']);
                break;
            case '종이':
                compatible = isCompatible(selectedMark, ['종이', 'paper']) && !packageMaterial.includes('팩');
                break;
            case '일반팩':
                compatible = packageMaterial.includes('팩') && !packageMaterial.includes('멸균');
                break;
            case '멸균팩':
                compatible = packageMaterial.includes('멸균') && packageMaterial.includes('팩');
                break;
            case '유리':
                compatible = isCompatible(selectedMark, ['유리', 'glass']);
                break;
            case '복합재질':
                compatible = isCompatible(selectedMark, ['복합재질', '도포', '첩합', '코팅']);
                break;
            case '비닐(PET)':
                compatible = isCompatible(selectedMark, ['비닐', 'pet', '페트']);
                break;
            case '비닐(HDPE)':
                compatible = isCompatible(selectedMark, ['비닐', 'hdpe', '고밀도']);
                break;
            case '비닐(LDPE)':
                compatible = isCompatible(selectedMark, ['비닐', 'ldpe', '저밀도']);
                break;
            case '비닐(PP)':
                compatible = isCompatible(selectedMark, ['비닐', 'pp', '폴리프로필렌']);
                break;
            case '비닐(PS)':
                compatible = isCompatible(selectedMark, ['비닐', 'ps', '폴리스티렌']);
                break;
            case '비닐(기타)':
                compatible = isCompatible(selectedMark, ['비닐', '기타']);
                break;
            default:
                // 기타 마크들은 기존 추천 로직을 활용하여 검증
                const recommendedMark = recommendRecyclingMarkByMaterial(packageMaterial);
                compatible = (selectedMark === recommendedMark);
                break;
        }

        if (!compatible) {
            errors.push(
                `포장재질("${checkedFields.frmlc_mtrqlt}")과 분리배출마크("${selectedMark}")가 일치하지 않습니다. 사용된 포장재질과 분리배출마크를 재확인하세요.`
            );
        }

        return { errors, suggestions };
    }

    // 6. 소비기한
    function checkExpiryCompliance() {
        const errors = [];
        const suggestions = [];
        const foodType = (checkedFields.prdlst_dcnm || '').trim();
        const expiry = (checkedFields.pog_daycnt || '').trim();
        const storageMethod = (checkedFields.storage_method || '').trim();

        if (!expiry || !foodType) {
            return { errors, suggestions };
        }

        // 냉동식품 또는 장기보존식품(통조림, 레토르트)은 검증에서 제외
        const isFrozen = isFrozenProduct(storageMethod, foodType);
        const isLongTermStorage = foodType.includes('통조림') || foodType.includes('병조림') || foodType.includes('레토르트');

        if (isFrozen || isLongTermStorage) {
            return { errors, suggestions }; // 검증 대상이 아니므로 종료
        }

        // 1. 식품유형에 맞는 권장 소비기한 찾기
        const recommendationKeys = Object.keys(REGULATIONS.expiry_recommendation || {}).sort((a, b) => b.length - a.length);
        let recommendation = null;
        for (const key of recommendationKeys) {
            if (foodType.includes(key)) {
                recommendation = REGULATIONS.expiry_recommendation[key];
                break;
            }
        }

        if (!recommendation || typeof recommendation.shelf_life !== 'number') {
            return { errors, suggestions }; // 검증 대상이 아니면 종료
        }

        // 2. 입력된 소비기한을 '일' 단위로 변환
        let totalDays = 0;
        const yearMatch = expiry.match(/(\d+)\s*년/);
        const monthMatch = expiry.match(/(\d+)\s*개월/);
        const dayMatch = expiry.match(/(\d+)\s*일/);

        if (yearMatch) {
            totalDays = parseInt(yearMatch[1], 10) * 365;
        } else if (monthMatch) {
            totalDays = parseInt(monthMatch[1], 10) * 30;
        } else if (dayMatch) {
            totalDays = parseInt(dayMatch[1], 10);
        }

        if (totalDays === 0) {
            return { errors, suggestions }; // 유효한 기간이 아니면 종료
        }

        // 3. 권장 소비기한을 '일' 단위로 변환
        let recommendedDays = 0;
        if (recommendation.unit === 'months') {
            recommendedDays = recommendation.shelf_life * 30;
        } else if (recommendation.unit === 'days') {
            recommendedDays = recommendation.shelf_life;
        }

        // 4. 비교 및 오류 메시지 생성
        if (recommendedDays > 0 && totalDays > recommendedDays) {
            const unitText = recommendation.unit === 'months' ? '개월' : '일';
            const suggestionMsg = `권장 소비기한(${recommendation.shelf_life}${unitText})을 초과하였습니다. 설정 근거를 반드시 확인하시기 바랍니다.`;
            suggestions.push(suggestionMsg);
        }

        return { errors, suggestions };
    }    

    // --- 검증 모달창 및 validateSettings ---
    // 이전 결과 캐시
    let cachedValidation = null;

    function showValidationModal() {
        let modal = document.getElementById('validationModal');
        if (modal) {
            try {
                bootstrap.Modal.getInstance(modal)?.hide();
            } catch (e) {}
            setTimeout(() => {
                if (modal.parentNode) modal.parentNode.removeChild(modal);
            }, 0);
            modal = null;
        }
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'validationModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">규정 검증 결과</h5>
                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal" style="min-width:80px; margin-left:auto;">닫기</button>
                        </div>
                        <div class="modal-body">
                            <table class="table table-bordered" id="validationResultTable" style="margin-bottom:0;">
                                <thead>
                                    <tr>
                                        <th style="width:15%;">검증 항목</th>
                                        <th style="width:10%;">검증 상태</th>
                                        <th style="width:65%;">검증 결과 및 수정 제안</th>
                                    </tr>
                                </thead>
                                <tbody id="validationResultBody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        setTimeout(() => {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }, 0);
        return modal;
    }



    /*
     * PDF 저장 — 내려받고, 문서함의 "한글표시사항도안" 으로도 등록한다.
     *
     * 이 함수는 **한 벌만 있어야 한다.** 예전에는 이 파일과 label_preview.html
     * 인라인 스크립트에 같은 이름으로 둘이 있었고, 둘 다 같은 버튼에 붙어서
     * 한 번 누르면 PDF 가 두 개 내려받아졌다. 크기 계산도 서로 달랐고
     * (pt + scrollHeight / cm + 입력값), 문서함 등록은 한쪽에만 있었다.
     * 인라인 쪽을 걷어내고 여기로 모았다.
     */
    async function exportToPDF() {
        // 진행 표시는 메뉴 단추에 건다. 메뉴 항목에 걸면 눌리는 순간
        // 메뉴가 닫혀서 "PDF 생성 중" 을 아무도 못 본다.
        const pdfBtn = document.getElementById('exportMenuBtn')
                    || document.getElementById('exportPdfBtn');
        const previewContent = document.getElementById('previewContent');
        if (!previewContent) {
            alert('미리보기 내용을 찾을 수 없습니다.');
            return;
        }

        const labelId = new URLSearchParams(window.location.search).get('label_id');
        const originalBtnHtml = pdfBtn ? pdfBtn.innerHTML : '';
        if (pdfBtn) {
            pdfBtn.disabled = true;
            pdfBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>PDF 생성 중...';
        }

        try {
            if (labelId) {
                try {
                    await fetch('/label/log-pdf-save/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify({ label_id: labelId, source: 'preview' })
                    });
                } catch (logError) {
                    console.warn('로깅 실패:', logError);
                }
            }

            // 화면에서 확대해 둔 배율과 화면 전용 표시는 인쇄물에 들어가면 안 된다
            if (typeof window.resetPreviewZoom === 'function') window.resetPreviewZoom();
            previewContent.classList.add('pv-exporting');

            const { jsPDF } = window.jspdf;
            const canvas = await html2canvas(previewContent, {
                scale: 3,               // 고해상도
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#ffffff',
                logging: false
            });
            const imgData = canvas.toDataURL('image/png');

            // 크기는 사용자가 정한 cm 를 그대로 쓴다. 세로는 "22.6 cm" 처럼
            // 단위가 붙어 오므로 숫자만 뽑는다.
            const widthCm = parseFloat(document.getElementById('widthInput')?.value) || 10;
            const heightCm = parseFloat(
                String(document.getElementById('heightInput')?.value || '').replace(/[^0-9.-]/g, '')) || 11;

            const pdf = new jsPDF(widthCm > heightCm ? 'l' : 'p', 'cm', [widthCm, heightCm]);
            pdf.addImage(imgData, 'PNG', 0, 0, widthCm, heightCm);

            const productName = String(checkedFields.prdlst_nm || '').trim();
            const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            let fileName = '한글표시사항' + (productName ? `_${productName}` : '') + `_${dateStr}.pdf`;
            fileName = fileName.replace(/[<>:"/\|?*]/g, '_');

            pdf.save(fileName);

            if (!labelId) {
                showPreviewToast('PDF가 저장되었습니다.', 'success');
                return;
            }

            // 문서함 등록
            if (pdfBtn) pdfBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>문서함 등록 중...';
            try {
                const formData = new FormData();
                formData.append('label_id', labelId);
                formData.append('pdf_file', pdf.output('blob'), fileName);

                const uploadRes = await fetch('/label/upload-label-pdf/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: formData,
                });
                const uploadJson = await uploadRes.json();
                if (uploadJson.success) {
                    showPreviewToast(uploadJson.updated
                        ? `문서함에 한글표시사항도안이 업데이트되었습니다. (버전 ${uploadJson.version})`
                        : '문서함에 한글표시사항도안이 등록되었습니다.', 'success');
                } else {
                    console.warn('문서함 등록 실패:', uploadJson.error);
                    showPreviewToast('문서함 등록 실패: ' + (uploadJson.error || ''), 'warning');
                }
            } catch (uploadErr) {
                console.warn('문서함 업로드 에러:', uploadErr);
                showPreviewToast('문서함 등록 중 오류가 발생했습니다.', 'warning');
            }
        } catch (error) {
            console.error('PDF 저장 중 오류:', error);
            showPreviewToast('PDF 생성 중 오류가 발생했습니다: ' + error.message, 'error');
        } finally {
            previewContent.classList.remove('pv-exporting');
            if (typeof window.restorePreviewZoom === 'function') window.restorePreviewZoom();
            if (pdfBtn) {
                pdfBtn.disabled = false;
                pdfBtn.innerHTML = originalBtnHtml || '<i class="fas fa-file-export me-1"></i>내보내기';
            }
        }
    }    // 천 단위 콤마
    function comma(x) {
        if (x === undefined || x === null) return '';
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // 한국 식품표시기준 반올림 규정 적용 (계산기와 동일)
    function roundKoreanNutrition(value, type, context) {
        if (type === 'kcal') {
            // 5kcal 미만은 0, 5kcal 단위로 "가장 가까운" 5의 배수로 조정
            if (value < 5) return 0;
            return Math.round(value / 5) * 5;
        }
       

        if (type === 'mg') {
            if (value < 5) return 0;
            if (value <= 140) return Math.round(value / 5) * 5;
            return Math.round(value / 10) * 10;
        }
        if (type === 'g') {
            if (value <  0.5) return 0;
            if (value <= 5) return Math.round(value * 10) / 10;
            return Math.round(value);
        }
        return value;
    }    // 계산기의 영양성분 값 계산 로직 적용 (완전 동일)
    function calculateNutrientValue(type, baseAmount, servings, val100g, displayUnit) {
        if (isNaN(val100g) || isNaN(baseAmount)) return 0;
        let raw = 0;
        
        if (displayUnit === 'total') {
            raw = (val100g * baseAmount * servings) / 100;
        } else if (displayUnit === 'unit') {
            raw = (val100g * baseAmount) / 100;
        } else {
            raw = val100g;
        }
        return roundKoreanNutrition(raw, type);
    }

    // 계산기의 열량 전용 계산 함수 (완전 동일)
    function getKcalValue(type, baseAmount, servings, val) {
        if (isNaN(val) || isNaN(baseAmount)) return 0;
        let raw = 0;
        let context = {};
        if (type === 'total') {
            raw = (val * baseAmount * servings) / 100;
            context.isKcalPerServing = true;
            return roundKoreanNutrition(raw, 'kcal', context);
        } else if (type === 'unit') {
            raw = (val * baseAmount) / 100;
            context.isKcalPerServing = true;
            return roundKoreanNutrition(raw, 'kcal', context);
        } else {
            raw = val;
            context.isKcalPerServing = false;
            return roundKoreanNutrition(raw, 'kcal', context);
        }
    }    // 영양성분 표시 (계산기와 완전히 동일한 로직 적용)
    function updateNutritionDisplay(data) {
        const nutritionPreview = document.getElementById('nutritionPreview');
        if (!nutritionPreview) return;

        // 모르는 기준이면 총 내용량당으로 본다. 표의 머리글에 "undefined" 가
        // 찍히는 것보다는 낫고, 실제로 그 값이 대부분이다.
        let displayUnit = data.displayUnit || 'total';
        if (!['total', 'unit', '100g'].includes(displayUnit)) displayUnit = 'total';
        const servingUnit = data.servingUnit || 'g';
        const servingSize = data.servingSize || 100;
        const servingsPerPackage = data.servingsPerPackage || 1;
        const totalWeight = servingSize * servingsPerPackage;

        // 계산기와 동일한 표시 형식 매핑
        const tabMap = {
            total: `총 내용량 ${comma(totalWeight)}${servingUnit}`,
            unit: `단위내용량 ${comma(servingSize)}${servingUnit}`,
            '100g': `100${servingUnit}당`
        };

        /*
         * 표의 열 머리는 **기준을 밝히는 말**이라 "당" 이 빠지면 안 된다.
         * "총 내용량" 만 적으면 그 열의 숫자가 총량인지 100 g 당인지 알 수
         * 없다 — 검수에서 "총 내용량 당 으로 수정" 지적이 나온 자리다.
         *
         * 머리 블록에는 이미 "총 내용량 65 g" 이 적히므로 여기에 다시 양을
         * 쓰지 않는다. 두 번 적으면 그것도 지적 대상이다.
         */
        const tabMapShort = {
            total: `총 내용량 당`,
            unit: `단위내용량 당`,
            '100g': `100${servingUnit}당`
        };

        // 열량 계산 (계산기와 완전히 동일한 로직)
        let kcal = 0;
        if (data.calorie !== undefined && data.calorie !== null) {
            kcal = getKcalValue(displayUnit, servingSize, servingsPerPackage, data.calorie);
        }

        // 계산기와 동일한 미리보기 박스 구조
        const previewBox = `
            <div class="nutrition-preview-box" style="margin-bottom:0;display:flex;align-items:center;justify-content:space-between;">
                <div class="nutrition-preview-title" style="margin-bottom:0;font-size:2rem;">영양정보</div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;">
                    <span class="nutrition-preview-total-small" style="font-size:0.95rem;font-weight:500;color:#fff;">${tabMap[displayUnit]}</span>
                    <span class="nutrition-preview-kcal" style="font-size:1.15rem;font-weight:700;color:#fff;line-height:1;">${comma(kcal)}kcal</span>
                </div>
            </div>
        `;

        // 계산기와 동일한 테이블 스타일 변수들
        const tableStyle = 'background:#fff;color:#222;border-radius:0 0 6px 6px;width:320px;margin:0 auto 16px auto;font-size:10pt;line-height:1.5;';
        const thSmall = 'class="nutrition-preview-small" style="font-size:0.95rem;font-weight:500;background:#fff;padding:8px 0 6px 0;color:#222;border-bottom:2px solid #000;text-align:left;"';
        const thRightSmall = 'class="nutrition-preview-small" style="font-size:0.95rem;font-weight:500;background:#fff;padding:8px 0 6px 0;color:#222;border-bottom:2px solid #000;text-align:right;"';
        const tdLabelClass = 'style="font-weight:700;text-align:left;padding:6px 0 6px 0;"';
        const tdLabelIndentClass = 'style="font-weight:700;text-align:left;padding:6px 0 6px 24px;"';
        const tdValueClass = 'style="font-weight:400;text-align:left;padding:6px 0 6px 0;"';
        const tdPercentClass = 'style="font-weight:700;text-align:right;padding:6px 0 6px 0;"';

        const tableHeader = `
            <thead>
                <tr>
                    <th ${thSmall}>${tabMapShort[displayUnit]}</th>
                    <th ${thRightSmall}>1일 영양성분 기준치에 대한 비율</th>
                </tr>
            </thead>
        `;        // 계산기와 동일한 들여쓰기 항목 정의
        const indentItems = ['당류', '트랜스지방', '포화지방'];
        
        let rows = '';
        (data.values || []).forEach(item => {
            if (!item.value && item.value !== 0) return; // 값이 없으면 표시하지 않음
            if (item.label === '열량') return; // 열량은 별도 표시
            
            // 계산기와 동일한 반올림 타입 결정
            const roundType = (item.label === '나트륨' || item.label === '콜레스테롤') ? 'mg' : 'g';
            
            // 계산기와 완전히 동일한 값 계산 로직
            let value = 0;
            if (displayUnit === 'total') {
                let raw = (item.value * servingSize * servingsPerPackage) / 100;
                value = roundKoreanNutrition(raw, roundType);
            } else if (displayUnit === 'unit') {
                let raw = (item.value * servingSize) / 100;
                value = roundKoreanNutrition(raw, roundType);
            } else {
                let raw = item.value;
                value = roundKoreanNutrition(raw, roundType);
            }
            
            const indent = indentItems.includes(item.label);            const percent = item.limit ? Math.round((value / item.limit) * 100) : '';            
            
            // 들여쓰기 적용: 당류, 트랜스지방, 포화지방은 24px 들여쓰기 (CSS 클래스 사용)
            // 비율은 오른쪽 정렬로 표시
            // 계산기와 동일한 포맷: 영양성분명은 bold, 값은 별도 span, 비율도 bold
            const tdClass = indent ? tdLabelIndentClass : tdLabelClass;
            const indentClass = indent ? ' nutrient-label-indent' : '';            rows += `<tr>
                <td ${tdClass} class="${indentClass}"><strong>${item.label}</strong> <span ${tdValueClass}>${comma(value)}${item.unit}</span></td>
                <td ${tdPercentClass}>${percent !== '' ? `<strong>${percent}</strong>%` : ''}</td>
            </tr>`;
        });

        // 계산기와 동일한 하단 텍스트
        rows += `
            <tr>
                <td colspan="2" class="nutrition-preview-footer-inside">
                    <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.
                </td>
            </tr>
        `;        const tableHtml = `
            <table class="nutrition-preview-table table" style="${tableStyle}">
                ${tableHeader}
                <tbody>${rows}</tbody>
            </table>
        `;

        nutritionPreview.innerHTML = previewBox + tableHtml;

        /*
         * 표시 항목 체크가 정한다 — 표의 다른 줄과 같은 규칙이다.
         *
         * 예전에는 "#nutrition-tab 이 활성화되어 있을 때만" 이었는데, 이 화면에는
         * 그런 탭이 없다. 그래서 항상 숨겨졌고 — 그리기 전에 이미 그릴 자리
         * (#nutritionPreview)조차 없어서 영양성분은 미리보기에도 PDF 에도
         * 나오지 않았다.
         */
        nutritionPreview.style.display = isNutritionShown() ? 'block' : 'none';
        placeNutritionBlock();
        if (typeof calculateHeight === 'function') calculateHeight();
    }

    /* 영양정보 표를 인쇄하는가. 값이 하나도 없으면 켜 두어도 그릴 것이 없다. */
    function isNutritionShown() {
        if (window.displayChecked && window.displayChecked.nutrition_text !== true) return false;
        const data = window.nutritionData;
        if (!data) return false;
        const hasCalorie = data.calorie !== undefined && data.calorie !== null && data.calorie !== '';
        const hasValue = (data.values || []).some(v => v.value || v.value === 0 ? Number(v.value) : 0);
        return hasCalorie || hasValue;
    }

    /* 표시 항목 체크가 바뀌면 영양정보 표도 함께 켜고 끈다. */
    window.refreshNutritionVisibility = function () {
        const el = document.getElementById('nutritionPreview');
        if (!el) return;
        if (!el.innerHTML && window.nutritionData) {
            updateNutritionDisplay(window.nutritionData);
            return;
        }
        el.style.display = isNutritionShown() ? 'block' : 'none';
        placeNutritionBlock();
        if (typeof calculateHeight === 'function') calculateHeight();
    };

    /*
     * 영양정보 표의 자리.
     *
     * 지금은 표 아래에 붙는다. "표시사항이 세로로 길면 옆에 나란히" 를
     * #previewContent 를 flex 로 바꿔 시도했다가 되돌렸다 — 그 안에는 머리
     * 띠, 요약 줄, 절대 위치로 떠 있는 분리배출마크, 꼬리말이 함께 있어서
     * 표와 영양정보만 나란히 세울 수가 없었다. 화면이 서로 겹쳐 버렸다.
     *
     * 제대로 하려면 표와 영양정보를 감싸는 칸을 따로 만들어야 하고, 그러면
     * 인쇄물의 짜임새가 달라지므로 눈으로 보면서 맞춰야 한다. 그때까지는
     * 아래에 둔다 — 겹쳐 보이는 것보다는 길어지는 편이 낫다.
     */
    function placeNutritionBlock() {
        const content = document.getElementById('previewContent');
        if (content) content.classList.remove('pv-nutrition-side');
    }
    window.placeNutritionBlock = placeNutritionBlock;

    // 영양성분 데이터 수신
    window.addEventListener('message', function(e) {
        if (e.data?.type === 'nutritionData') {
            // 이 칸들은 영양성분 계산기 화면의 것이라 미리보기에는 없다.
            // 그냥 부르면 null.value 로 죽고, 그 순간 표도 안 그려진다.
            const data = e.data.data;
            window.nutritionData = data;
            safeSetElementValue('servingSizeDisplay',
                `${comma(data.servingSize)}${data.servingUnit}`);
            safeSetElementValue('servingsPerPackageDisplay',
                `${comma(data.servingsPerPackage)}${data.servingUnitText}`);
            safeSetElementValue('nutritionDisplayUnit', data.displayUnit);
            const naviTab = document.querySelector('[data-bs-target="#nutrition-tab"]');
            if (naviTab) bootstrap.Tab.getOrCreateInstance(naviTab).show();
            updateNutritionDisplay(data);
        }
   
    });

    document.getElementById('nutritionDisplayUnit')?.addEventListener('change', function() {
        if (window.nutritionData) {
            window.nutritionData.displayUnit = this.value;
            updateNutritionDisplay(window.nutritionData);
        }
    });

    // 세로 길이 계산
    function calculateHeight() {
        const width = parseFloat(document.getElementById('widthInput').value);
        const fontSize = parseFloat(document.getElementById('fontSizeInput').value);
        const letterSpacing = parseInt(document.getElementById('letterSpacingInput').value);
        const lineHeight = parseFloat(document.getElementById('lineHeightInput').value);
        const table = document.getElementById('previewTableBody');
        // 영양정보 표는 표 아래에 따로 붙는다. 빼고 재면 인쇄물이 잘린다.
        const nutrition = document.getElementById('nutritionPreview');
        const nutritionHeight = (nutrition && nutrition.style.display !== 'none')
            ? nutrition.offsetHeight : 0;
        const contentHeight = table.offsetHeight + nutritionHeight + 80;
        const totalHeight = contentHeight / 28.35;
        const heightInput = document.getElementById('heightInput');
        heightInput.value = Math.ceil(totalHeight);
        updateArea();
    }

    // 초기화
    setupEventListeners();
    // 최초 로드시에만 한 번 실행 (분리배출마크 간섭 방지)
    updatePreviewStyles();
    setupAreaCalculation();
    setTimeout(updateArea, 100);
    enforceInputMinMax();
    
    // 설정 UI 요소들이 존재하는지 확인하고 없으면 생성
    ensureSettingsElements();
    
    // 전역 함수들을 먼저 설정 (에러 발생 전에)
    setupGlobalRecyclingFunctions();
    
    // 저장된 설정 로드 (에러가 발생해도 다른 기능에 영향 없도록)
    loadSavedPreviewSettings();
    
    // 버튼 이벤트 리스너 설정 (중복 제거된 코드)
    safeAddEventListener('exportPdfBtn', 'click', exportToPDF);
    safeAddEventListener('copyTextBtn', 'click', copyLabelText);
    safeAddEventListener('downloadTextBtn', 'click', downloadLabelText);
    safeAddEventListener('downloadDocBtn', 'click', downloadLabelDoc);
    safeAddEventListener('saveSettingsBtn', 'click', savePreviewSettings);
    // 부모 프레임(탭에 끼워 넣은 미리보기)이 부를 수 있게 노출한다
    window.savePreviewSettings = savePreviewSettings;
    
    // 높이 계산 이벤트 리스너 설정 (중복 제거된 코드)
    const heightCalculationInputs = ['widthInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'];
    addEventListenersToElements(heightCalculationInputs, 'change', calculateHeight);
    window.addEventListener('load', calculateHeight);
    
    // DOM 요소들의 존재 여부 확인 (중복 제거된 코드)
    const criticalElements = [
        'nutrition-data', 'country-mapping-data', 'expiry-recommendation-data',
        'nutritionPreview', 'servingSizeDisplay', 'servingsPerPackageDisplay', 'nutritionDisplayUnit'
    ];
    
    const missingElements = criticalElements.filter(id => !document.getElementById(id));
    if (missingElements.length > 0) {
        console.warn(`⚠️ 누락된 DOM 요소들: ${missingElements.join(', ')}`);
    }
    
    // 초기화 완료 표시 (debug removed)
    
    // 포장재질 필드 변경 감지 및 자동 분리배출마크 추천
    function setupPackageMaterialWatcher() {
        // 포장재질 입력 필드 찾기 (다양한 selector 시도)
        const packageMaterialSelectors = [
            'input[name="frmlc_mtrqlt"]',
            '#frmlc_mtrqlt',
            'input[placeholder*="포장재질"]',
            'input[placeholder*="용기"]'
        ];
        
        let packageField = null;
        for (const selector of packageMaterialSelectors) {
            packageField = document.querySelector(selector);
            if (packageField) break;
        }
        
        if (packageField) {
            // 디바운스된 업데이트 함수
            const debouncedUpdate = debounce((value) => {
                if (value && value.trim()) {
                    // 자동 추천 및 적용
                    window.updateRecyclingMarkUI(value.trim(), true);
                }
            }, 500);
            
            // 이벤트 리스너 추가 (중복 제거된 코드)
            const handler = (e) => debouncedUpdate(e.target.value);
            packageField.addEventListener('input', handler);
            packageField.addEventListener('change', handler);
        }
    }
    
    // 포장재질 감지기 설정
    setTimeout(setupPackageMaterialWatcher, 500);
    
    // 페이지 로드 후 탭 상태 확인
    setTimeout(() => {
        // 지연 후 탭 상태 재검사 (debug removed)
        const activeTab = document.querySelector('.nav-link.active');
        if (!activeTab) {
            console.warn('⚠️ 활성 탭을 찾을 수 없음');
        }
        // 현재 영양성분 표시 상태 확인
        const nutritionPreview = document.getElementById('nutritionPreview');
        if (nutritionPreview) {
            // (debug removed)
        }
    }, 1000);

});

// aiValidationBtn/ruleValidationBtn 이벤트 리스너 - 규칙기반(+AI) 통합 검증 호출
// 기존 window.validateSettings()(전부 클라이언트 JS 검증, "규정 검증" 버튼)를
// 대체한다. 서버측 검증 API를 호출해 우회 불가능한 판정을 보여준다.
// 규정 검증(AI)(비용 발생, 일일 한도 있음)과 규정 검증(무료·무제한, AI 미사용)
// 두 경로를 같은 모달 스타일로 보여주되 버튼을 분리해뒀다.
document.addEventListener('DOMContentLoaded', function() {

    const aiValidationBtn = document.getElementById('aiValidationBtn');
    if (aiValidationBtn) {
        aiValidationBtn.addEventListener('click', function() {
            runAiValidation();
        });
    }

    const ruleValidationBtn = document.getElementById('ruleValidationBtn');
    if (ruleValidationBtn) {
        ruleValidationBtn.addEventListener('click', function() {
            runRuleOnlyValidation();
        });
    }
});

function runAiValidation() {
    runValidation(true, 'aiValidationBtn', '규정 검증(AI) 중...');
}

function runRuleOnlyValidation() {
    runValidation(false, 'ruleValidationBtn', '검증 중...');
}

async function runValidation(useAi, btnId, loadingText) {
    const urlParams = new URLSearchParams(window.location.search);
    const labelId = urlParams.get('label_id');
    if (!labelId) {
        alert('라벨 정보를 찾을 수 없습니다. 페이지를 새로고침해주세요.');
        return;
    }

    // 검증 로깅 (기존 validateSettings와 동일하게 서버에 기록)
    try {
        await fetch('/label/log-validation/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ label_id: labelId })
        });
    } catch (logError) {
        console.warn('로깅 실패:', logError);
    }

    const btn = document.getElementById(btnId);
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span>${loadingText}`;
    }

    try {
        const url = useAi
            ? `/label/${labelId}/validate/ai-review/`
            : `/label/${labelId}/validate/`;
        const resp = await fetch(url, {
            method: useAi ? 'POST' : 'GET',
            headers: useAi ? { 'X-CSRFToken': getCookie('csrftoken') } : {},
        });
        if (resp.status === 429) {
            const limited = await resp.json().catch(() => ({}));
            alert((limited.usage && limited.usage.message) || '규정 검증(AI) 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.');
            return;
        }
        if (!resp.ok) {
            throw new Error(`서버 응답 오류 (${resp.status})`);
        }
        const result = await resp.json();
        showAiValidationModal(result, useAi);
    } catch (error) {
        console.error('검증 오류:', error);
        alert('검증 중 오류가 발생했습니다: ' + error.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}


// 근거 표 — 그 지적이 어느 칸의 어떤 값에서 나왔는지를 그대로 보여 준다.
// 제품명 함량 지적이 특히 그렇다. "특정성분 함량에 없다" 는 말만으로는
// 원재료명에 적어 둔 값이 왜 안 쳐주는지 알 수 없어, 사용자가 세 칸을
// 번갈아 열어 보며 대조해야 했다.
function validationEvidenceHtml(evidence) {
    if (!evidence || !evidence.length) return '';
    const esc = (str) => String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return evidence.map(function (block) {
        const rows = (block.rows || []).map(function (r) {
            const value = r.found
                ? esc(r.text)
                : '<span class="text-muted">적혀 있지 않음</span>';
            return '<tr>'
                + '<td class="text-nowrap text-muted" style="width:34%;">' + esc(r.field) + '</td>'
                + '<td>' + value + '</td>'
                + '<td class="text-nowrap text-end" style="width:18%;">'
                + (r.percent ? '<strong>' + esc(r.percent) + '</strong>' : '-')
                + '</td></tr>';
        }).join('');
        return '<div class="mt-2">'
            + (block.title ? '<div class="text-muted" style="font-size:0.8rem;">'
                             + esc(block.title) + '</div>' : '')
            + '<table class="table table-sm table-borderless mb-0" style="font-size:0.82rem;">'
            + '<tbody>' + rows + '</tbody></table></div>';
    }).join('');
}

/*
 * 규정 검증 결과에 번호를 매긴다.
 *
 * 예전에는 표의 줄이 분홍색으로 물들기만 했다. 지적이 여럿이면 어느 것이 이
 * 줄 이야기인지 이을 수가 없었다 — 모달과 표를 눈으로 대조해야 했다.
 * 이제 모달의 지적과 표의 배지가 같은 번호를 쓴다.
 *
 * 서버가 지적마다 어느 칸의 이야기인지(fields)를 함께 준다. 그 값이 표의
 * data-field-row 와 같은 이름이라 행을 바로 찾을 수 있다.
 */
function numberValidationIssues(categories) {
    let n = 0;
    (categories || []).forEach(function (row) {
        row._numbers = [];
        if (row.ok) return;
        const count = (row.errors || []).length || 1;
        for (let i = 0; i < count; i += 1) {
            n += 1;
            row._numbers.push(n);
        }
    });
    return categories || [];
}

function markValidationOnTable(categories) {
    document.querySelectorAll('#previewContent .pv-issue-badge').forEach(function (el) { el.remove(); });
    document.querySelectorAll('[data-field-row]').forEach(function (row) {
        row.classList.remove('pv-row-issue');
    });

    const byField = {};
    (categories || []).forEach(function (row) {
        if (row.ok || !row._numbers || !row._numbers.length) return;
        (row.fields || []).forEach(function (field) {
            byField[field] = (byField[field] || []).concat(row._numbers);
        });
    });

    Object.keys(byField).forEach(function (field) {
        const numbers = byField[field].sort(function (a, b) { return a - b; });
        document.querySelectorAll(`[data-field-row="${field}"]`).forEach(function (row) {
            row.classList.add('pv-row-issue');
            // 배지는 항목명 칸에 붙인다. 2단 배치에서는 행이 아니라 칸이
            // data-field-row 를 가지므로 그 칸 자신이 될 수도 있다.
            const head = row.tagName === 'TH' ? row : row.querySelector('th');
            if (!head || head.querySelector('.pv-issue-badge')) return;
            const badge = document.createElement('span');
            badge.className = 'pv-issue-badge pv-issue-badge-link';
            badge.textContent = numbers.join(',');
            badge.title = '누르면 이 지적의 내용을 봅니다';
            badge.setAttribute('role', 'button');
            badge.tabIndex = 0;
            head.insertBefore(badge, head.firstChild);
        });
    });
}

/* 그 줄의 항목명. 모달에 "rawmtrl_nm_display" 라고 적어 봐야 소용이 없다. */
function tableRowName(field) {
    const row = document.querySelector(`[data-field-row="${field}"]`);
    const head = row && (row.tagName === 'TH' ? row : row.querySelector('th'));
    const text = head ? head.textContent.replace(/^\s*\d+(,\d+)*\s*/, '').trim() : '';
    return text || field;
}

/* 그 줄로 데려가 잠깐 드러낸다. 스크롤만 하면 어느 줄인지 알기 어렵다. */
function jumpToTableRow(field) {
    const row = document.querySelector(`[data-field-row="${field}"]`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('pv-row-flash');
    setTimeout(function () { row.classList.remove('pv-row-flash'); }, 1600);
}

/* 지금 화면에 떠 있는 검증 결과. 표의 번호 배지를 눌렀을 때 다시 연다. */
let _lastValidation = null;

/*
 * 검증 결과 창.
 *
 * 예전에는 스무 항목을 전부 같은 크기의 표 행으로 늘어놓았다. 적합한 열여덟
 * 줄이 화면을 다 차지해서, 정작 봐야 할 두 줄을 찾으려면 한참 스크롤해야
 * 했다. **적합은 이름만, 확인이 필요한 것만 펼친다.**
 *
 * 규정 검증과 규정 검증(AI)이 같은 창을 쓴다 — 판정 방법이 다를 뿐 사용자가
 * 읽는 것은 같은 종류의 결과다.
 */
function showAiValidationModal(result, useAi) {
    const legacy = document.getElementById('validationModal');
    if (legacy) legacy.remove();
    const existing = document.getElementById('aiValidationModal');
    if (existing) existing.remove();

    // 지적에 번호를 매기고 표 위에 얹는다. 목록만 보여 주면 "어느 줄 이야기인지"
    // 를 잇는 일이 사람 몫이 된다 — 열일곱 줄을 눈으로 훑으며 대조해야 했다.
    const categories = numberValidationIssues(result.categories || []);
    markValidationOnTable(categories);
    _lastValidation = { result: result, useAi: useAi };

    const problems = categories.filter(c => !c.ok);
    const passed = categories.filter(c => c.ok);
    const blocking = problems.filter(c => !c.advisory);

    const modal = document.createElement('div');
    modal.id = 'aiValidationModal';
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title vr-title">
                        <i class="fas ${useAi ? 'fa-robot' : 'fa-list-check'} me-2"></i>
                        ${useAi ? '규정 검증(AI)' : '규정 검증'}
                        ${vrCountsHtml(categories, blocking, problems)}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body vr-body">
                    ${vrUncheckedHtml(result.unchecked || [])}
                    ${vrProblemsHtml(problems)}
                    ${vrPassedHtml(passed)}
                    ${vrFooterHtml(result, useAi)}
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const bsModal = new bootstrap.Modal(modal);
    modal.addEventListener('click', function (e) {
        // 지적을 누르면 표의 그 줄로 데려간다. 창은 닫는다 — 표를 가리고
        // 있으면 데려가 봐야 보이지 않는다.
        const jump = e.target.closest('.vr-jump');
        if (!jump) return;
        e.preventDefault();
        bsModal.hide();
        jumpToTableRow(jump.dataset.jump);
    });
    bsModal.show();
    return bsModal;
}

function vrCountsHtml(categories, blocking, problems) {
    if (!problems.length) {
        return `<span class="badge bg-success ms-2">${categories.length}개 항목 모두 적합</span>`;
    }
    const advisory = problems.length - blocking.length;
    let html = '';
    if (blocking.length) html += `<span class="badge bg-danger ms-2">재검토 ${blocking.length}</span>`;
    if (advisory) html += `<span class="badge bg-warning text-dark ms-2">권고 ${advisory}</span>`;
    html += `<span class="badge bg-light text-dark border ms-2">검증 ${categories.length}</span>`;
    return html;
}

/*
 * 확인이 필요한 항목만 펼친다.
 *
 * 지적 하나가 카드 하나다. 번호는 표에 얹힌 배지와 같은 숫자이고, 배지를
 * 누르면 그 카드로 온다 — 그래서 지적마다 id 를 단다.
 */
function vrProblemsHtml(problems) {
    if (!problems.length) {
        return '<div class="vr-empty"><i class="fas fa-circle-check me-2"></i>확인이 필요한 항목이 없습니다.</div>';
    }

    return problems.map(function (row) {
        const anchor = (row.fields || []).find(f => document.querySelector(`[data-field-row="${f}"]`));
        const where = anchor
            ? `<button type="button" class="vr-jump vr-where-btn" data-jump="${anchor}">표의 <strong>${tableRowName(anchor)}</strong> 줄로</button>`
            : '';
        /* 권고는 "고치면 좋다" 이지 "틀렸다" 가 아니다. 확정도 막지 않는다.
           같은 무게로 보이면 진짜 지적이 그 안에 묻힌다. */
        const tone = row.advisory ? 'vr-card-advisory' : 'vr-card-blocking';
        const tag = row.advisory
            ? '<span class="vr-tag vr-tag-advisory">권고</span>'
            : '<span class="vr-tag vr-tag-blocking">재검토</span>';

        const errors = (row.errors || []).map(function (text, i) {
            const num = (row._numbers || [])[i];
            const id = num ? ` id="vr-issue-${num}"` : '';
            const badge = num ? `<span class="pv-issue-badge">${num}</span>` : '';
            return `<div class="vr-issue"${id}>${badge}<span class="vr-issue-text">${text}</span></div>`;
        }).join('');

        const suggestions = (row.suggestions || []).length
            ? `<div class="vr-suggest"><i class="fas fa-lightbulb me-1"></i>${row.suggestions.join('<br>')}</div>`
            : '';

        return `<div class="vr-card ${tone}">
                    <div class="vr-card-head">${tag}<span class="vr-card-name">${row.label}</span>${where}</div>
                    ${errors}${suggestions}${validationEvidenceHtml(row.evidence)}
                </div>`;
    }).join('');
}

/* 적합한 항목은 **이름만**. 스무 개를 표로 늘어놓으면 봐야 할 것이 묻힌다. */
function vrPassedHtml(passed) {
    if (!passed.length) return '';
    const chips = passed.map(c => `<span class="vr-chip">${c.label}</span>`).join('');
    return `<details class="vr-passed" open>
                <summary>적합 ${passed.length}개</summary>
                <div class="vr-chips">${chips}</div>
            </details>`;
}

/*
 * 확인하지 못한 항목.
 *
 * 규정 준수 도구에서 "확인 안 됨" 이 "적합" 처럼 보이는 건 가장 나쁜 실패
 * 방식이다. 사유를 그대로 보여 준다.
 */
function vrUncheckedHtml(unchecked) {
    if (!unchecked.length) return '';
    const esc = (str) => String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const systemFailure = unchecked.some(u => u.system_failure);
    const rows = unchecked
        .map(u => `<li><strong>${esc(u.label)}</strong> — ${esc(u.message)}</li>`).join('');
    return `<div class="alert ${systemFailure ? 'alert-warning' : 'alert-secondary'} py-2 px-3 mb-3 vr-unchecked">
                <div class="mb-1"><strong>확인하지 못한 항목 ${unchecked.length}건</strong>
                ${systemFailure ? '<span class="badge bg-warning text-dark ms-1">사용 횟수는 차감되지 않았습니다</span>' : ''}
                </div><ul class="mb-0 ps-3">${rows}</ul>
            </div>`;
}

/* 요약 문장과 AI 사용량. 맨 아래에 둔다 — 먼저 볼 것은 지적이다. */
function vrFooterHtml(result, useAi) {
    const parts = [];
    if (result.summary) {
        const box = document.createElement('div');
        box.textContent = result.summary;
        parts.push(`<div class="vr-summary">${box.innerHTML}</div>`);
    }
    if (useAi && result.usage && typeof result.usage.daily_used === 'number') {
        const u = result.usage;
        parts.push(`<div class="vr-usage">오늘 ${u.daily_used}/${u.daily_limit}회 사용${u.is_paid ? ' · 유료' : ''}</div>`);
    }
    return parts.join('');
}

/*
 * 표에 얹힌 번호를 누르면 그 지적의 내용을 보여 준다.
 *
 * 번호만 있고 내용을 볼 길이 없으면 "몇 번이 뭐였더라" 를 창을 다시 열어
 * 찾아야 한다. 방금 돌린 결과를 그대로 다시 펼치고 그 지적으로 데려간다.
 */
function showValidationDetail(number) {
    if (!_lastValidation) {
        if (typeof showPreviewToast === 'function') {
            showPreviewToast('규정 검증을 먼저 돌려 주세요.', 'warning');
        }
        return;
    }
    showAiValidationModal(_lastValidation.result, _lastValidation.useAi);
    setTimeout(function () {
        const found = document.getElementById(`vr-issue-${number}`);
        if (!found) return;
        found.scrollIntoView({ behavior: 'smooth', block: 'center' });
        found.classList.add('vr-issue-flash');
        setTimeout(function () { found.classList.remove('vr-issue-flash'); }, 1600);
    }, 400);
}

document.addEventListener('click', function (e) {
    const badge = e.target.closest && e.target.closest('#previewContent .pv-issue-badge');
    if (!badge) return;
    const first = String(badge.textContent || '').split(',')[0].trim();
    if (first) showValidationDetail(first);
});

// 부모창으로부터 데이터 수신 리스너
window.addEventListener('message', function(e) {
    if (e.data.type === 'previewCheckedFields') {
        // 전역 변수로 설정하여 validateSettings에서 사용할 수 있도록
        window.checkedFields = e.data.checked;
        
        // 원재료명 정보 로깅
        if (window.checkedFields.ingredient_info) {
        }
    }
});

// 제품명 금지문구 검증 (기존 로직 활용)
function checkForbiddenPhrasesInProduct() {
    // HTML의 기존 checkForbiddenPhrases 로직을 호출
    if (typeof window.checkForbiddenPhrases === 'function') {
        return window.checkForbiddenPhrases();
    }
    
    // 폴백 로직
    const errors = [];
    const suggestions = [];
    const productName = (checkedFields.prdlst_nm || '').trim();
    
    if (!productName) {
        return { ok: true, errors, suggestions };
    }
    
    const forbiddenPhrases = window.LABEL_CONSTANTS?.forbiddenPhrases || ['천연', '자연', '슈퍼', '생명'];
    const foundForbiddenPhrases = forbiddenPhrases.filter(phrase => 
        productName.toLowerCase().includes(phrase.toLowerCase())
    );
    
    if (foundForbiddenPhrases.length > 0) {
        errors.push(`제품명에 사용금지 문구가 포함되어 있습니다: ${foundForbiddenPhrases.join(', ')}`);
        suggestions.push('사용금지 문구를 제품명에서 제거하세요. (식품 등의 표시기준 제8조)');
    }
    
    return {
        ok: errors.length === 0,
        errors,
        suggestions
    };
}

// 농수산물 성분 함량 표시 검증 (기존 로직 활용)
function checkFarmSeafoodContentDisplay() {
    
    // checkedFields 데이터 확인
    if (!checkedFields) {
        console.warn('checkedFields 데이터 없음');
        return { ok: true, errors: [], suggestions: [] };
    }
    
    // HTML의 기존 checkFarmSeafoodCompliance 로직을 호출
    if (typeof window.checkFarmSeafoodCompliance === 'function') {
        return window.checkFarmSeafoodCompliance();
    }
    
    // 폴백 로직 (기존 HTML 로직과 동일)
    const errors = [];
    const suggestions = [];
    const productName = checkedFields.prdlst_nm || '';
    const ingredientInfo = checkedFields.ingredient_info || '';
    
    // 농수산물 목록 (constants.js에서 가져오기)
    const farmSeafoodItems = window.LABEL_CONSTANTS?.farmSeafoodItems || window.farmSeafoodItems || [];

    // 제품명에 포함된 농수산물명 추출 (긴 이름부터 처리)
    const foundItems = farmSeafoodItems
        .filter(item => productName.includes(item))
        .sort((a, b) => b.length - a.length);

    if (foundItems.length === 0) {
        return { ok: true, errors: [], suggestions: [] };
    }

    foundItems.forEach(item => {
        // '특정성분 함량' 필드에 해당 성분명과 함량(%)이 모두 포함되어 있는지 확인
        const complianceRegex = new RegExp(`${item}[^,]*\\d+(\\.\\d+)?\\s*%`);
        const isCompliant = complianceRegex.test(ingredientInfo);

        if (!isCompliant) {
            errors.push(`제품명에 사용된 '${item}'의 함량을 '특정성분 함량' 항목에 표시하세요 (예: ${item} 100%).`);
        }
    });

    return {
        ok: errors.length === 0,
        errors,
        suggestions
    };
}

// 필수 문구 및 식품유형별 검증 (HTML에서 이동)
window.checkFoodTypePhrasesUnified = function checkFoodTypePhrasesUnified() {
    const errors = [];
    const suggestions = [];
    const storageMethod = (checkedFields.storage_method || '').trim();
    const foodType = (checkedFields.prdlst_dcnm || '').trim();
    const cautions = (checkedFields.cautions || '').trim();
    const additional = (checkedFields.additional_info || '').trim();

    // 1. 냉동 조건 검증
    const isFrozenStorage = (() => {
        if (storageMethod.includes('냉동')) return true;
        const tempRegex = /(-?\d+(\.\d+)?)\s*(℃|도)/g;
        let match;
        while ((match = tempRegex.exec(storageMethod)) !== null) {
            const tempValue = parseFloat(match[1]);
            if (!isNaN(tempValue) && tempValue <= -18) {
                return true;
            }
        }
        return false;
    })();

    if (isFrozenStorage) {
        const hasRequiredFrozenKeywords = cautions.includes('해동') || cautions.includes('재냉동') || additional.includes('해동') || additional.includes('재냉동');
        if (!hasRequiredFrozenKeywords) {
            errors.push('냉동 보관 제품은 주의사항 또는 기타표시사항에 "해동" 또는 "재냉동" 관련 문구를 포함해야 합니다.');
        }
    }

    // 2. 냉장 조건 검증
    const isRefrigeratedStorage = (() => {
        if (storageMethod.includes('냉장')) return true;
        const rangeRegex = /(\d+(\.\d+)?)\s*~\s*(\d+(\.\d+)?)\s*(℃|도)/g;
        let match;
        while ((match = rangeRegex.exec(storageMethod)) !== null) {
            const minTemp = parseFloat(match[1]);
            const maxTemp = parseFloat(match[3]);
            if (!isNaN(minTemp) && !isNaN(maxTemp) && minTemp >= -1 && maxTemp <= 15) {
                return true;
            }
        }
        return false;
    })();

    // 3. 즉석조리식품 검증
    if (foodType.includes('즉석조리식품')) {
        const hasCookingMethod = /조리방법/.test(additional);
        if (!hasCookingMethod) {
            errors.push('즉석조리식품은 기타표시사항에 "조리방법"을 표시해야 합니다.');
        }
    }

    // 4. 유제품 검증
    const dairyKeywords = ["우유", "치즈", "발효유", "요구르트", "유제품"];
    const isDairy = dairyKeywords.some(keyword => foodType.includes(keyword));
    if (isDairy) {
        const hasFatRegex = /지방.*\(\s*%\s*\)/;
        const hasFat = hasFatRegex.test(cautions) || hasFatRegex.test(additional);
        if (!hasFat) {
            errors.push('조건: 유제품 | 항목: 주의사항/기타표시사항 | 문구: "지방함량(%)"');
        }
        const hasSteril = /멸균/.test(cautions) || /멸균/.test(additional);
        if (!hasSteril) {
            errors.push('조건: 유제품 | 항목: 주의사항/기타표시사항 | 문구: "멸균방식"');
        }
        if (!isRefrigeratedStorage) {
            errors.push('조건: 유제품 | 항목: 보관방법/주의사항/기타표시사항 | 문구: "냉장보관(0~10℃)"');
        }
    }

    // 5. 필수 문구 검증
    const REGULATIONS = window.REGULATIONS || {};
    let requiredPhrases = [];
    Object.keys(REGULATIONS.food_type_phrases || {}).forEach(key => {
        if (foodType.includes(key)) {
            requiredPhrases = requiredPhrases.concat(REGULATIONS.food_type_phrases[key]);
        }
    });
    
    requiredPhrases = requiredPhrases.filter(phrase => phrase !== "해동 후 재냉동 금지");
    requiredPhrases.forEach(phrase => {
        if (!cautions.includes(phrase) && !additional.includes(phrase)) {
            errors.push(`조건: 식품유형("${foodType}") | 항목: 주의사항/기타표시사항 | 문구: "${phrase}"`);
        }
    });

    // 6. 1399 문구 검증
    const hasReport = cautions.includes("1399") || additional.includes("1399");
    if (!hasReport) {
        errors.push('모든 식품에는 "부정불량식품신고는 국번없이 1399"를 표시해야 합니다.');
    }

    return { ok: errors.length === 0, errors, suggestions };
};

// ===== 통합 규정 검증 시스템 =====
window.validateRegulations = function validateRegulations() {
    const results = {
        ok: true,
        errors: [],
        suggestions: [],
        details: {}
    };
    
    // checkedFields 검증
    if (typeof checkedFields === 'undefined') {
        console.warn('checkedFields가 정의되지 않음 - 규정 검증 불가');
        return { ok: true, errors: [], suggestions: [] };
    }

    // 0. 기본 필드 검증 (내용량 단위 체크)
    const basicValidation = validateBasicFields();
    results.details.basic = basicValidation;
    if (!basicValidation.ok) {
        results.ok = false;
        results.errors.push(...basicValidation.errors);
        results.suggestions.push(...basicValidation.suggestions);
    }

    // 1. 성분 관련 검증 (농수산물 + 특정성분)
    const ingredientValidation = validateIngredientCompliance();
    results.details.ingredient = ingredientValidation;
    if (!ingredientValidation.ok) {
        results.ok = false;
        results.errors.push(...ingredientValidation.errors);
        results.suggestions.push(...ingredientValidation.suggestions);
    }

    // 2. 문구 관련 검증 (필수문구 + 금지문구)
    const textValidation = validateTextCompliance();
    results.details.text = textValidation;
    if (!textValidation.ok) {
        results.ok = false;
        results.errors.push(...textValidation.errors);
        results.suggestions.push(...textValidation.suggestions);
    }

    // 3. 알레르기 성분 검증
    const allergenValidation = validateAllergenCompliance();
    results.details.allergen = allergenValidation;
    if (!allergenValidation.ok) {
        results.ok = false;
        results.errors.push(...allergenValidation.errors);
        results.suggestions.push(...allergenValidation.suggestions);
    }

    // 4. 포장재질 및 분리배출마크 검증
    const packagingValidation = validatePackagingCompliance();
    results.details.packaging = packagingValidation;
    if (!packagingValidation.ok) {
        results.ok = false;
        results.errors.push(...packagingValidation.errors);
        results.suggestions.push(...packagingValidation.suggestions);
    }

    return results;
};

// ===== 개별 검증 모듈들 =====

// 0. 기본 필드 검증
function validateBasicFields() {
    const errors = [];
    const suggestions = [];
    
    // 내용량 단위 검증 (mg, g, kg, l, ml만 허용, 열량 표시도 허용)
    const contentWeight = checkedFields['content_weight'] || '';
    if (contentWeight && contentWeight.trim()) {
        // 숫자와 단위가 붙어 있거나 띄어쓰기 한 칸이 있는 경우도 인식
        const validUnits = /(\d+(?:\.\d+)?)\s?(mg|g|kg|ml|l)(?![a-zA-Z])/i;
        if (!validUnits.test(contentWeight)) {
            errors.push('내용량에 올바른 단위가 누락되었습니다.');
            suggestions.push('내용량 필드에 mg, g, kg, ml, l 중 하나의 단위를 포함해주세요. (예: 500g, 1L, 250ml, 500l(500kcal))');
        }
    }
    
    return { ok: errors.length === 0, errors, suggestions };
}

// 1. 성분 관련 검증 (농수산물 성분 + 특정성분 함량)
function validateIngredientCompliance() {
    const errors = [];
    const suggestions = [];
    
    // 농수산물 성분 함량 검증
    const farmSeafoodResult = checkFarmSeafoodContent();
    if (!farmSeafoodResult.ok) {
        errors.push(...farmSeafoodResult.errors);
        suggestions.push(...farmSeafoodResult.suggestions);
    }
    
    return { ok: errors.length === 0, errors, suggestions };
}

// 2. 문구 관련 검증 (필수문구 + 금지문구)
function validateTextCompliance() {
    const errors = [];
    const suggestions = [];
    
    // 필수 문구 검증
    const requiredTextResult = checkRequiredPhrases();
    if (!requiredTextResult.ok) {
        errors.push(...requiredTextResult.errors);
        suggestions.push(...requiredTextResult.suggestions);
    }
    
    // 사용 금지 문구 검증
    const forbiddenTextResult = checkForbiddenText();
    if (!forbiddenTextResult.ok) {
        errors.push(...forbiddenTextResult.errors);
        suggestions.push(...forbiddenTextResult.suggestions);
    }
    
    return { ok: errors.length === 0, errors, suggestions };
}

// 3. 알레르기 성분 검증
function validateAllergenCompliance() {
    const allergenErrors = checkAllergenDuplication();
    return {
        ok: allergenErrors.length === 0,
        errors: allergenErrors,
        suggestions: allergenErrors.length > 0 ? ['알레르기 성분과 주의문구를 확인해서 수정하세요.'] : []
    };
}

// 4. 포장재질 및 분리배출마크 검증
function validatePackagingCompliance() {
    const errors = [];
    const suggestions = [];
    
    // 분리배출마크 검증
    try {
        if (typeof window.checkRecyclingMarkCompliance === 'function') {
            const recyclingResult = window.checkRecyclingMarkCompliance();
            if (!recyclingResult.ok) {
                errors.push(...recyclingResult.errors);
                suggestions.push(...recyclingResult.suggestions);
            }
        }
    } catch (e) {
        console.warn('분리배출마크 검증 오류:', e);
    }
    
    return { ok: errors.length === 0, errors, suggestions };
}

// ===== 세부 검증 함수들 (기존 함수들을 리팩토링) =====

// 농수산물 성분 함량 검증 (기존 checkFarmSeafoodCompliance 리팩토링)
function checkFarmSeafoodContent() {
    const errors = [];
    const suggestions = [];
    const productName = checkedFields.prdlst_nm || '';
    const ingredientInfo = checkedFields.ingredient_info || '';
    
    // constants.js에서 로드된 배열 사용
    const farmSeafoodItems = window.farmSeafoodItems;
    if (!farmSeafoodItems) {
        return { ok: true, errors: [], suggestions: [] };
    }

    // 제품명에 포함된 농수산물명 추출
    const foundItems = farmSeafoodItems
        .filter(item => productName.includes(item))
        .sort((a, b) => b.length - a.length);

    if (foundItems.length === 0) {
        return { ok: true, errors: [], suggestions: [] };
    }

    foundItems.forEach(item => {
        const complianceRegex = new RegExp(`${item}[^,]*\\d+(\\.\\d+)?\\s*%`);
        const isCompliant = complianceRegex.test(ingredientInfo);

        if (!isCompliant) {
            errors.push(`제품명에 사용된 '${item}'의 함량을 '특정성분 함량' 항목에 표시하세요 (예: ${item} 100%).`);
        }
    });

    return { ok: errors.length === 0, errors, suggestions };
}

// 필수 문구 검증 (기존 checkFoodTypePhrasesUnified 리팩토링)
function checkRequiredPhrases() {
    const errors = [];
    const suggestions = [];
    
    try {
        if (typeof window.checkFoodTypePhrasesUnified === 'function') {
            const result = window.checkFoodTypePhrasesUnified();
            return result;
        }
    } catch (e) {
        console.warn('필수 문구 검증 오류:', e);
    }
    
    return { ok: true, errors, suggestions };
}

// 사용 금지 문구 검증 (기존 checkForbiddenPhrases 리팩토링)
function checkForbiddenText() {
    const errors = [];
    const suggestions = [];
    
    const forbiddenPhrases = window.forbiddenPhrases;
    if (!forbiddenPhrases) {
        return { ok: true, errors: [], suggestions: [] };
    }
    
    const FIELD_LABELS = {
        'prdlst_nm': '제품명',
        'ingredient_info': '특정성분 함량',
        'rawmtrl_nm_display': '원재료명',
        'cautions': '주의사항',
        'additional_info': '기타표시사항'
    };
    
    const fieldsToCheck = [
        'prdlst_nm', 'ingredient_info', 'rawmtrl_nm_display', 'cautions', 'additional_info'
    ];
    
    fieldsToCheck.forEach(field => {
        let value = (checkedFields[field] || '').toString();
        forbiddenPhrases.forEach(phrase => {
            if (value && value.match(new RegExp(phrase, 'i'))) {
                if (field === 'rawmtrl_nm_display' && phrase === '천연') {
                    let msg = `<strong>"${FIELD_LABELS[field]}" 항목에 사용 금지 문구 "${phrase}"가 표시되어 있습니다.</strong>`;
                    let suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}" 항목에 "${phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요.</strong><br>` +
                        '<span style="color:#888;">사용 조건:<br>' +
                        '① 원료 중에 합성향료·합성착색료·방부제 등 어떠한 인공 화학 성분도 전혀 포함되어 있지 않아야 함<br>' +
                        '② 최소한의 물리적 가공(세척·절단·동결·건조 등)만 거친 상태여야 함<br>' +
                        '③ "천연"과 유사한 의미로 오인될 수 있는 "자연산(naturel)" 등의 외국어 사용도 동일 기준 적용<br>' +
                        '④ 식품유형별로 별도 금지 사항(「식품등의 표시기준」의 개별 고시 규정)이 있는 경우, 그 규정에 따라 추가 제한이 있음<br>' +
                        '⑤ 예: 설탕에는 "천연설탕"이라는 표현이 불가<br>' +
                        '⑥ 영업소 명칭 또는 등록상표에 포함된 경우는 허용<br>' +
                        '⑦ "천연향료" 등 고시된 허용 목록 내 용어만 예외적으로 허용</span>';
                    errors.push(`${msg}<br>${suggestion}`);
                    value = value.replace(/천연/gi, '').replace(/natural/gi, '').replace(/naturel/gi, '');
                    checkedFields[field] = value.trim();
                    return;
                }
                
                let msg = `<strong>"${FIELD_LABELS[field]}" 항목에 사용 금지 문구 "${phrase}"가 표시되어 있습니다.</strong>`;
                let suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}"에서 "${phrase}" 문구를 삭제하세요.</strong>`;
                
                if (field === 'rawmtrl_nm_display' && phrase === '자연') {
                    suggestion = `<strong style="color:#222;">"${FIELD_LABELS[field]}" 항목에 "${phrase}" 문구를 표시하려면 반드시 사용 조건에 맞게 표시하세요.</strong><br>` +
                        '<span style="color:#888;">사용 조건:<br>' +
                        '① "자연"이라는 용어는 가공되지 않은 농산물·임산물·수산물·축산물에 대해서만 허용<br>' +
                        '② 수확하여 세척·포장만 거친 원물(raw agricultural/seafood/livestock products)에만 허용<br>' +
                        '③ 이미 "가공식품"으로 분류된 상태라면 "자연" 표기가 불가능<br>' +
                        '④ 유전자변형식품, 나노식품 등은 "자연" 표기가 금지됨<br>' +
                        '⑤ 영업소 명칭 또는 등록상표에 포함된 경우는 허용<br>' +
                        '⑥ 단, 제품명(product name) 자체에 "천연"·"자연"을 붙일 수는 없음</span>';
                }
                errors.push(`${msg}<br>${suggestion}`);
            }
        });
    });
    
    return { ok: errors.length === 0, errors, suggestions };
}

// ===== 기존 개별 함수들 (호환성을 위해 유지) =====
window.checkFarmSeafoodCompliance = function checkFarmSeafoodCompliance() {
    return checkFarmSeafoodContent();
};

// ===== 사용 금지 문구 검증 (호환성을 위해 유지) =====
window.checkForbiddenPhrases = function checkForbiddenPhrases() {
    return checkForbiddenText();
};

// 페이지 로드 완료 시 부모창 또는 부모 프레임에 데이터 요청
window.addEventListener('load', function() {
    if (window.opener) {
        // 팝업으로 열린 경우
        window.opener.postMessage({ type: 'requestPreviewData' }, '*');
    } else if (window.parent !== window) {
        // iframe으로 임베드된 경우
        window.parent.postMessage({ type: 'requestPreviewData' }, '*');
    }
});

// ==================== 필드 순서 조정 기능 ====================

/*
 * 표의 항목 배치. 라벨에 저장된다(MyLabel.prv_field_layout).
 *
 * visibility 는 여기 없다. **표에 줄이 생기는 기준은 표시 항목 체크
 * (chckd_*) 하나뿐이다** — 같은 것을 정하는 스위치가 둘이면 어느 날 서로 다른
 * 말을 한다. 실제로 규정 검증은 체크를, 표는 값 유무를, 눈 아이콘은 또
 * localStorage 를 보고 있었다.
 *
 * 맞춤항목만 예외로 customVisibility 를 쓴다. 맞춤항목에는 대응하는 체크박스가
 * 아예 없어서 기댈 자리가 없다.
 */
let fieldOrderData = {
    order: [],
    customVisibility: {},
    width: {}, // '50%' or '100%'
    layoutMode: 'vertical' // 'vertical', 'horizontal'
};

/* 표시 항목 체크 상태 {필드: bool}. 서버가 주고, 눈 아이콘이 바꾼다. */
window.displayChecked = window.displayChecked || {};

/* 이 항목이 표에 나가는가. 맞춤항목은 체크박스가 없어 로컬 설정을 본다. */
function isFieldShown(fieldKey) {
    if (String(fieldKey).startsWith('custom_field_')) {
        return fieldOrderData.customVisibility[fieldKey] !== false;
    }
    return window.displayChecked[fieldKey] === true;
}

// 기본 필드 정의 (실제 라벨 데이터에서 추출)
const DEFAULT_FIELDS = {
    /* 표시사항 작성 폼의 입력 순서와 일치 */
    'prdlst_dcnm': '식품유형',
    'prdlst_nm': '제품명',
    'ingredient_info': '특정성분 함량',
    'content_weight': '내용량',
    'weight_calorie': '내용량(열량)',
    'prdlst_report_no': '품목보고번호',
    'country_of_origin': '원산지',
    'storage_method': '보관 방법',
    'frmlc_mtrqlt': '용기·포장재질',
    'bssh_nm': '제조원 소재지',
    'distributor_address': '유통전문판매원',
    'repacker_address': '소분원',
    'importer_address': '수입원',
    'pog_daycnt': '소비기한',
    'rawmtrl_nm_display': '원재료명',
    /* rawmtrl_nm 제외: _tab_label.html postMessage와 preview_popup label_data 모두
       rawmtrl_nm_display 로 통일 처리. 별도 키가 있을 때 '원재료명' 행이 2개 생기는 버그 방지 */
    'cautions': '주의사항',
    'additional_info': '기타표시사항',
    /* 인쇄 항목이 아닌 것은 뺐다 (v1/label/constants.py 의 PREVIEW_DISPLAY_FIELDS 와 같은 목록).
       my_label_name(라벨명)은 내부에서 부르는 이름인데 표에 '라벨명' 줄로 인쇄되고 있었다.
       nutrition_text(영양성분)는 별도 표로 그린다. allergies·etc_description 은 쓰는 곳이 없었다. */
};

// 필드 정의 가져오기 (현재 라벨 데이터 기반)
function getFieldDefinitions() {
    const fields = [];
    const addedKeys = new Set(); // 중복 방지
    
    // 현재 라벨 데이터가 있으면 그것을 사용
    if (window.currentLabelData && typeof window.currentLabelData === 'object') {
        Object.keys(window.currentLabelData).forEach(key => {
            // custom_field_로 시작하는 키는 customFieldsData에서 처리하므로 여기서는 건너뛰기
            if (key.startsWith('custom_field_')) return;
            // date_option은 pog_daycnt와 중복되므로 제외 (소비기한 표시는 pog_daycnt에서 처리)
            if (key === 'date_option') return;
            // 이름을 모르는 키는 항목이 아니다. 예전에는 그대로 줄이 되어
            // 표에 "rawmtrl_nm" 같은 머리글이 인쇄됐다.
            if (!DEFAULT_FIELDS[key]) return;

            const label = DEFAULT_FIELDS[key];
            if (!addedKeys.has(key)) {
                fields.push({
                    key: key,
                    label: label,
                    visible: true,
                    width: '50%'
                });
                addedKeys.add(key);
            }
        });
        
        // 맞춤항목 추가 (customFieldsData가 있으면)
        if (window.customFieldsData && Array.isArray(window.customFieldsData) && window.customFieldsData.length > 0) {
            window.customFieldsData.forEach((field, index) => {
                const customKey = `custom_field_${index}`;
                const fieldLabel = field.name || field.label; // DB 저장 형식({name,value})과 이전 형식({label,value}) 모두 지원
                if (fieldLabel && !addedKeys.has(customKey)) {
                    fields.push({
                        key: customKey,
                        label: fieldLabel,
                        value: field.value || '',
                        isCustomField: true,
                        visible: true,
                        width: '50%'
                    });
                    addedKeys.add(customKey);
                }
            });
        }
        
        // currentLabelData가 있지만 필드가 없으면 기본 필드 사용
        if (fields.length === 0) {
            Object.keys(DEFAULT_FIELDS).forEach(key => {
                if (!addedKeys.has(key)) {
                    fields.push({
                        key: key,
                        label: DEFAULT_FIELDS[key],
                        visible: true,
                        width: '50%'
                    });
                    addedKeys.add(key);
                }
            });
        }
    } else {
        // 라벨 데이터가 없으면 기본 필드 사용
        Object.keys(DEFAULT_FIELDS).forEach(key => {
            if (!addedKeys.has(key)) {
                fields.push({
                    key: key,
                    label: DEFAULT_FIELDS[key],
                    visible: true,
                    width: '50%'
                });
                addedKeys.add(key);
            }
        });
    }
    
    return fields;
}

// 필드 순서 초기화
/*
 * 배치를 읽어 온다. 순서는 **라벨에 저장된 것**이 먼저다.
 *
 * 예전에는 localStorage 의 'labelFieldOrder' 키 하나뿐이었다. 라벨별이 아니라
 * 브라우저별이라, 한 라벨에서 맞춰 둔 순서가 다른 라벨에 그대로 얹혔고 옆자리
 * 동료는 아예 다른 순서를 봤다. 인쇄물의 모양인데 그럴 수 없다.
 *
 * localStorage 는 아직 서버에 저장한 적 없는 라벨을 위한 폴백으로만 남긴다.
 */
function loadFieldLayout() {
    const clean = (raw) => {
        const seen = new Set();
        const order = [];
        (Array.isArray(raw && raw.order) ? raw.order : []).forEach(key => {
            if (!seen.has(key)) { order.push(key); seen.add(key); }
        });
        return {
            order: order,
            customVisibility: (raw && raw.customVisibility) || {},
            width: (raw && raw.width) || {},
            layoutMode: (raw && raw.layoutMode) === 'horizontal' ? 'horizontal' : 'vertical',
            labelColumnMm: parseFloat(raw && raw.labelColumnMm) || 24
        };
    };

    const saved = safeLoadJsonData('field-layout-data', null, '표 항목 배치');
    if (saved && Array.isArray(saved.order) && saved.order.length) {
        fieldOrderData = clean(saved);
        return;
    }
    try {
        const local = JSON.parse(localStorage.getItem('labelFieldOrder') || 'null');
        fieldOrderData = clean(local);
    } catch (e) {
        fieldOrderData = clean(null);
    }
}

window.initializeFieldOrder = function() {
    loadFieldLayout();

    // 저장된 항목명 칸 너비를 설정 칸에 되돌려 놓는다
    const colInput = document.getElementById('labelColWidthInput');
    if (colInput) {
        colInput.value = fieldOrderData.labelColumnMm || 24;
        colInput.addEventListener('change', function () {
            fieldOrderData.labelColumnMm = parseFloat(this.value) || 24;
            saveFieldOrder();
            if (typeof window.updatePreviewStyles === 'function') window.updatePreviewStyles();
        });
    }

    // 순서가 없으면 기본 순서로. 표시 여부는 여기서 정하지 않는다 —
    // 그것은 표시 항목 체크(displayChecked)의 몫이다.
    if (!fieldOrderData.order.length) {
        fieldOrderData.order = getFieldDefinitions().map(f => f.key);
        saveFieldOrder();
    }

    renderFieldOrderList();
    initializeLayoutButtons();
};

// 데이터 로드 후 order 에 없는 필드를 뒤에 붙인다.
window.updateFieldOrderFromData = function() {
    if (!window.currentLabelData) {
        return;
    }

    const existingKeys = new Set(fieldOrderData.order);
    let hasNewFields = false;

    getFieldDefinitions().forEach(field => {
        if (!existingKeys.has(field.key)) {
            fieldOrderData.order.push(field.key);
            hasNewFields = true;
        }
    });

    if (hasNewFields) {
        saveFieldOrder();
        renderFieldOrderList();
    }
};

// 필드 순서 목록 렌더링
window.renderFieldOrderList = function() {
    const container = document.getElementById('fieldOrderList');
    if (!container) {
        console.warn('fieldOrderList 컨테이너를 찾을 수 없습니다.');
        return;
    }
    
    container.innerHTML = '';
    
    const fields = getFieldDefinitions();
    
    if (fields.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: #6c757d;">표시할 항목이 없습니다.</div>';
        return;
    }
    
    const fieldMap = {};
    fields.forEach(f => fieldMap[f.key] = f);
    
    // 필수 속성 초기화
    if (!fieldOrderData.customVisibility) fieldOrderData.customVisibility = {};
    if (!fieldOrderData.width) fieldOrderData.width = {};

    // order가 비어있으면 현재 필드로 초기화
    if (!fieldOrderData.order || fieldOrderData.order.length === 0) {
        fieldOrderData.order = fields.map(f => f.key);
        saveFieldOrder();
    } else {
        // order에서 중복 제거
        const uniqueOrder = [];
        const seenKeys = new Set();
        fieldOrderData.order.forEach(key => {
            if (!seenKeys.has(key)) {
                uniqueOrder.push(key);
                seenKeys.add(key);
            }
        });
        if (uniqueOrder.length !== fieldOrderData.order.length) {
            fieldOrderData.order = uniqueOrder;
            saveFieldOrder();
        }
    }
    
    // 모든 항목 렌더링 (숨겨진 항목도 포함)
    fieldOrderData.order.forEach((fieldKey, index) => {
        const field = fieldMap[fieldKey];
        if (!field) return;
        
        const isVisible = isFieldShown(fieldKey);
        const width = fieldOrderData.width[fieldKey] || '50%';
        const isFullWidth = width === '100%';
        
        const item = document.createElement('div');
        item.className = 'field-order-item';
        item.dataset.fieldKey = fieldKey;
        
        // 숨겨진 항목은 비활성화 표시
        if (!isVisible) {
            item.classList.add('hidden-field');
        }
        
        if (isFullWidth) {
            item.classList.add('full-width-item');
        } else {
            item.classList.add('half-width-item');
        }
        
        // 켜 두었는데 아직 비어 있는 항목. 표에서는 빈 줄로 나가므로
        // 목록에서도 같은 사실을 말해 준다 — 규정 검증까지 가서 알 일이 아니다.
        const isEmpty = isVisible && !field.isCustomField
            && !String((window.currentLabelData || {})[fieldKey] || '').trim();
        if (isEmpty) item.classList.add('empty-field');

        item.innerHTML = `
            <i class="fas fa-grip-vertical drag-handle"></i>
            <span class="field-label">${field.label}</span>
            ${isEmpty ? '<span class="field-empty" title="표시하기로 켰지만 아직 비어 있습니다">비어 있음</span>' : ''}
            <div class="field-controls">
                <button class="width-toggle ${isFullWidth ? 'width-100' : 'width-50'}"
                        onclick="toggleFieldWidth('${fieldKey}')" 
                        title="${isFullWidth ? '50%로 변경' : '100%로 변경'}">
                    ${isFullWidth ? '100' : '50'}
                </button>
                <button class="order-btn" onclick="moveFieldUp('${fieldKey}')" 
                        ${index === 0 ? 'disabled' : ''} title="위로">
                    <i class="fas fa-chevron-up"></i>
                </button>
                <button class="order-btn" onclick="moveFieldDown('${fieldKey}')" 
                        ${index === fieldOrderData.order.length - 1 ? 'disabled' : ''} title="아래로">
                    <i class="fas fa-chevron-down"></i>
                </button>
                <button class="visibility-toggle ${isVisible ? 'visible' : 'hidden'}" 
                        onclick="toggleFieldVisibility('${fieldKey}')" 
                        title="${isVisible ? '숨기기' : '표시하기'}">
                    <i class="fas ${isVisible ? 'fa-eye' : 'fa-eye-slash'}"></i>
                </button>
            </div>
        `;
        
        container.appendChild(item);
    });
    
    // Sortable.js 초기화 (전체 항목 드래그 가능)
    if (typeof Sortable !== 'undefined') {
        new Sortable(container, {
            animation: 150,
            // handle 제거하여 전체 항목 드래그 가능
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            onEnd: function(evt) {
                const newOrder = Array.from(container.children).map(item => item.dataset.fieldKey);
                fieldOrderData.order = newOrder;
                saveFieldOrder();
                renderTableWithCurrentData();
                
                // 항목 순서 변경 로깅
                if (typeof window.logPreviewAction === 'function') {
                    window.logPreviewAction('preview_order');
                }
            }
        });
    } else {
        console.warn('Sortable.js가 로드되지 않았습니다.');
    }
};

// 필드 너비 토글
window.toggleFieldWidth = function(fieldKey) {
    const currentWidth = fieldOrderData.width[fieldKey] || '50%';
    fieldOrderData.width[fieldKey] = currentWidth === '50%' ? '100%' : '50%';
    saveFieldOrder();
    renderFieldOrderList();
    renderTableWithCurrentData();
};

// 필드 위로 이동
window.moveFieldUp = function(fieldKey) {
    const index = fieldOrderData.order.indexOf(fieldKey);
    if (index > 0) {
        [fieldOrderData.order[index - 1], fieldOrderData.order[index]] = 
        [fieldOrderData.order[index], fieldOrderData.order[index - 1]];
        saveFieldOrder();
        renderFieldOrderList();
        renderTableWithCurrentData();
        
        // 항목 순서 변경 로깅
        if (typeof window.logPreviewAction === 'function') {
            window.logPreviewAction('preview_order');
        }
    }
};

// 필드 아래로 이동
window.moveFieldDown = function(fieldKey) {
    const index = fieldOrderData.order.indexOf(fieldKey);
    if (index < fieldOrderData.order.length - 1) {
        [fieldOrderData.order[index], fieldOrderData.order[index + 1]] = 
        [fieldOrderData.order[index + 1], fieldOrderData.order[index]];
        saveFieldOrder();
        renderFieldOrderList();
        renderTableWithCurrentData();
        
        // 항목 순서 변경 로깅
        if (typeof window.logPreviewAction === 'function') {
            window.logPreviewAction('preview_order');
        }
    }
};

/*
 * 눈 아이콘 = 표시 항목 체크.
 *
 * 체크박스를 가진 쪽(제품 화면의 오른쪽 패널 / 표시사항 작성 화면의 폼)에
 * 알려서 거기서 켜고 끄게 한다. 이 창이 따로 저장하면 스위치가 둘이 되고,
 * 두 화면이 서로 다른 말을 하는 지금 문제가 그대로 되돌아온다. 저장·권한도
 * 이미 그쪽이 다룬다.
 */
function setFieldShown(fieldKey, shown) {
    if (String(fieldKey).startsWith('custom_field_')) {
        // 맞춤항목에는 대응하는 체크박스가 없다. 이것만 배치와 함께 저장한다.
        fieldOrderData.customVisibility[fieldKey] = shown;
        saveFieldOrder();
        return true;
    }

    const target = window.opener || (window.self !== window.top ? window.parent : null);
    if (!target) {
        if (typeof showPreviewToast === 'function') {
            showPreviewToast('표시 항목은 표시사항 작성 화면에서 켜고 끌 수 있습니다.', 'warning');
        }
        return false;
    }
    window.displayChecked[fieldKey] = shown;   // 화면은 바로 반영
    target.postMessage({ type: 'toggleDisplayItem', field: fieldKey, checked: shown }, '*');
    return true;
}

// 필드 표시/숨김 토글
window.toggleFieldVisibility = function(fieldKey) {
    if (!setFieldShown(fieldKey, !isFieldShown(fieldKey))) return;
    renderFieldOrderList();
    renderTableWithCurrentData();
};

// 전체 필드 표시/숨김 토글
window.toggleAllFieldsVisibility = function() {
    const allVisible = fieldOrderData.order.every(isFieldShown);
    let changed = false;
    fieldOrderData.order.forEach(key => {
        if (setFieldShown(key, !allVisible)) changed = true;
    });
    if (!changed) return;
    renderFieldOrderList();
    renderTableWithCurrentData();
};

// 전체 필드 너비 설정
window.setAllFieldsWidth = function(width) {
    if (!fieldOrderData.width) {
        fieldOrderData.width = {};
    }
    
    fieldOrderData.order.forEach(key => {
        fieldOrderData.width[key] = width;
    });
    saveFieldOrder();
    renderFieldOrderList();
    renderTableWithCurrentData();
};

// 필드 내용 분석 함수
function analyzeFieldContents(data) {
    const analysis = [];
    
    Object.keys(data).forEach(key => {
        const value = data[key];
        if (!value) return;
        
        const textContent = typeof value === 'string' ? value : String(value);
        const length = textContent.length;
        const lines = textContent.split('\n').length;
        const wordCount = textContent.split(/\s+/).length;
        
        analysis.push({
            key: key,
            length: length,
            lines: lines,
            wordCount: wordCount,
            score: length + (lines * 20) // 줄바꿈에 가중치 부여
        });
    });
    
    return analysis;
}

// 스마트 자동 최적화 함수
window.autoOptimizeLayout = function(options = {}) {
    const { silent = false, layoutMode = null } = options;
    
    if (!window.currentLabelData) {
        if (!silent) alert('먼저 라벨 데이터를 불러와주세요.');
        return;
    }
    
    if (!fieldOrderData.order || fieldOrderData.order.length === 0) {
        if (!silent) alert('표시할 항목이 없습니다.');
        return;
    }
    
    // 기본값으로 모든 필드를 50%로 설정
    if (!fieldOrderData.width) fieldOrderData.width = {};
    
    let optimizedCount = 0;
    let visibleCount = 0;
    const currentLayoutMode = layoutMode || fieldOrderData.layoutMode;
    
    // order에 있는 항목만 분석 및 최적화
    fieldOrderData.order.forEach(key => {
        // 표에 안 나가는 항목은 건너뛰기
        if (!isFieldShown(key)) {
            return;
        }
        
        visibleCount++;
        
        // 데이터에서 해당 키의 값 가져오기
        let value = window.currentLabelData[key];
        
        // 맞춤항목 처리
        if (key.startsWith('custom_field_')) {
            const index = parseInt(key.replace('custom_field_', ''));
            if (window.customFieldsData && window.customFieldsData[index]) {
                value = window.customFieldsData[index].value;
            }
        }
        
        // 특정 필드는 항상 100% (중요 정보)
        const alwaysFullWidth = ['rawmtrl_nm_display', 'cautions', 'additional_info', 'nutrition_text'];
        if (alwaysFullWidth.includes(key)) {
            fieldOrderData.width[key] = '100%';
            optimizedCount++;
            return;
        }
        
        if (!value) {
            // 값이 없으면 기본 50%
            fieldOrderData.width[key] = '50%';
            return;
        }
        
        // 내용 길이에 따라 최적 너비 결정
        const strValue = String(value);
        const length = strValue.length;
        const lines = (strValue.match(/\n/g) || []).length + 1;
        
        // 매우 긴 텍스트 항목 (200자 이상 또는 5줄 이상)
        if (length > 200 || lines > 5) {
            fieldOrderData.width[key] = '100%';
            optimizedCount++;
        }
        // 긴 텍스트 항목 (100자 이상 또는 3줄 이상)
        else if (length > 100 || lines > 3) {
            fieldOrderData.width[key] = '100%';
            optimizedCount++;
        }
        // 중간 길이 텍스트
        else {
            fieldOrderData.width[key] = '50%';
        }
    });
    
    // 가로 모드일 경우 마지막 항목이 홀수면 100%로 변경
    if (currentLayoutMode === 'horizontal') {
        const visibleKeys = fieldOrderData.order.filter(isFieldShown);
        
        const halfWidthKeys = visibleKeys.filter(key => 
            fieldOrderData.width[key] === '50%'
        );
        
        // 50% 항목이 홀수개이면 마지막 항목을 100%로
        if (halfWidthKeys.length % 2 === 1) {
            const lastHalfWidthKey = halfWidthKeys[halfWidthKeys.length - 1];
            fieldOrderData.width[lastHalfWidthKey] = '100%';
            optimizedCount++;
        }
    }
    
    saveFieldOrder();
    renderFieldOrderList();
    renderTableWithCurrentData();
    
    // DOM 업데이트를 위한 강제 리플로우
    if (currentLayoutMode === 'horizontal') {
        setTimeout(() => {
            const tbody = document.getElementById('previewTableBody');
            if (tbody) {
                tbody.style.display = 'none';
                tbody.offsetHeight; // 강제 리플로우
                tbody.style.display = 'block';
            }
        }, 50);
    }
    
    // 사용자 피드백 (silent 모드가 아닐 때만)
    if (!silent) {
        alert(`✨ 자동 최적화 완료!\n\n표시 중인 ${visibleCount}개 항목 중 ${optimizedCount}개를 100% 너비로 설정했습니다.`);
    }
    
    console.log('📊 자동 최적화 결과:', {
        표시중인항목: visibleCount,
        전체너비항목: optimizedCount,
        절반너비항목: visibleCount - optimizedCount,
        레이아웃모드: currentLayoutMode,
        order: fieldOrderData.order,
        width: fieldOrderData.width
    });
};

// 필드 순서 초기화
window.resetFieldOrder = function() {
    if (confirm('필드 순서를 초기값으로 되돌리시겠습니까?')) {
        const fields = getFieldDefinitions();
        fieldOrderData = {
            order: fields.map(f => f.key),
            customVisibility: {},
            width: {},
            layoutMode: 'vertical'
        };

        fields.forEach(f => {
            fieldOrderData.width[f.key] = '50%';
        });

        saveFieldOrder();
        renderFieldOrderList();
        initializeLayoutButtons();
        renderTableWithCurrentData();
    }
};

// 레이아웃 모드 초기화
window.resetLayoutMode = function() {
    fieldOrderData.layoutMode = 'vertical';
    saveFieldOrder();
    initializeLayoutButtons();
    renderTableWithCurrentData();
};

// 필드 순서 저장
function saveFieldOrder() {
    // 저장하기 전에 order에서 중복 제거
    if (fieldOrderData.order && Array.isArray(fieldOrderData.order)) {
        const uniqueOrder = [];
        const seenKeys = new Set();
        fieldOrderData.order.forEach(key => {
            if (!seenKeys.has(key)) {
                uniqueOrder.push(key);
                seenKeys.add(key);
            }
        });
        if (uniqueOrder.length !== fieldOrderData.order.length) {
            fieldOrderData.order = uniqueOrder;
        }
    }
    // 라벨에 저장하는 것은 "설정 저장" 이 한다(savePreviewSettings). 여기서는
    // 창을 닫았다 열어도 방금 만진 배치가 남아 있게만 해 둔다.
    localStorage.setItem('labelFieldOrder', JSON.stringify(fieldOrderData));
}

/* "설정 저장" 이 서버로 보낼 배치. 표시 여부는 여기 없다 — chckd_* 가 갖는다. */
window.getFieldLayoutForSave = function() {
    const colInput = document.getElementById('labelColWidthInput');
    return {
        order: fieldOrderData.order || [],
        width: fieldOrderData.width || {},
        customVisibility: fieldOrderData.customVisibility || {},
        layoutMode: fieldOrderData.layoutMode || 'vertical',
        // 항목명 칸 너비(mm). 인쇄물의 모양이라 라벨에 붙어 있어야 한다.
        labelColumnMm: parseFloat(colInput && colInput.value) || 24
    };
};

// 현재 데이터로 테이블 재렌더링
function renderTableWithCurrentData() {
    if (typeof window.renderTableWithLayout === 'function' && window.currentLabelData) {
        window.renderTableWithLayout(window.currentLabelData, fieldOrderData.layoutMode);
    }
}

// 레이아웃 버튼 초기화
function initializeLayoutButtons() {
    const buttons = document.querySelectorAll('.layout-btn');
    
    buttons.forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.layout === fieldOrderData.layoutMode) {
            btn.classList.add('active');
        }
        
        // 가로형 버튼은 개발 중 메시지만 표시
        if (btn.dataset.layout === 'grid') {
            btn.onclick = function() {
                alert('가로형 레이아웃은 개발 중입니다.');
                return false;
            };
            return;
        }
        
        btn.onclick = function() {
            fieldOrderData.layoutMode = this.dataset.layout;
            saveFieldOrder();
            buttons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            if (this.dataset.layout === 'horizontal') {
                autoOptimizeLayout({ silent: true, layoutMode: 'horizontal' });
                setTimeout(() => renderTableWithCurrentData(), 100);
            } else {
                renderTableWithCurrentData();
            }
        };
    });
}

// 레이아웃 적용하여 테이블 렌더링
/* ==================== 표시사항을 글자로 ====================
 *
 * PDF 는 화면을 이미지로 떠서 붙인 것이라 글자를 선택할 수 없다. 디자인
 * 담당자는 원재료명 300자를 **손으로 다시 친다.** 검수에서 나온 "과당1"
 * (원래는 "과당]")이 그 흔적이다 — 사람이 옮겨 적다 대괄호를 1로 쳤다.
 *
 * 붙여넣을 수 있는 글자를 내주면 그 단계가 통째로 사라진다.
 */

/* 인쇄될 그대로의 글자. 화면 전용 표시는 뺀다. */
/*
 * 인쇄될 그대로의 내용을 **한 곳에서** 모은다.
 *
 * 글자로도(텍스트 복사·txt) 표로도(워드) 나가야 하는데, 어디서 무엇을 걸러
 * 내는지가 두 벌이면 어느 날 한쪽만 고쳐진다. 걸러 내는 규칙은 여기 하나다.
 */
function labelRowData() {
    const header = document.querySelector('.preview-header-box .header-text');
    const rows = [];

    document.querySelectorAll('#previewTableBody [data-field-row]').forEach(function (row) {
        // 2단 배치는 한 <tr> 에 항목이 둘이라 칸이 이름을 갖는다.
        // 그때 <tr> 까지 세면 같은 줄이 두 번 나온다.
        if (row.tagName === 'TR' && row.querySelector('[data-field-row]')) return;

        const cells = row.tagName === 'TR'
            ? [row.querySelector('th'), row.querySelector('td')]
            : [row, row.nextElementSibling];
        if (!cells[0] || !cells[1]) return;
        rows.push({ head: cells[0], body: cells[1] });
    });

    const nutrition = [];
    const box = document.getElementById('nutritionPreview');
    if (box && box.style.display !== 'none' && box.textContent.trim()) {
        box.querySelectorAll('tr').forEach(function (tr) {
            const cells = Array.from(tr.children);
            if (cells.length) nutrition.push(cells);
        });
    }

    return {
        title: header ? header.textContent.trim() : '',
        rows: rows,
        nutrition: nutrition,
    };
}

/* 붙여넣기용 글자. 항목명과 값을 탭으로 가르면 워드·엑셀에서 표가 된다. */
function labelTextLines() {
    const data = labelRowData();
    const lines = [];
    if (data.title) lines.push(data.title, '');
    data.rows.forEach(function (row) {
        lines.push(cleanCellText(row.head) + '\t' + cleanCellText(row.body));
    });
    if (data.nutrition.length) {
        lines.push('', '[영양정보]');
        data.nutrition.forEach(function (cells) {
            const texts = cells.map(cleanCellText).filter(Boolean);
            if (texts.length) lines.push(texts.join('\t'));
        });
    }
    return lines;
}

/* 화면에만 있는 것(미입력 안내·지적 번호)은 인쇄물의 글자가 아니다. */
function cleanCellText(cell) {
    if (!cell) return '';
    const copy = cell.cloneNode(true);
    copy.querySelectorAll('.pv-empty-hint, .pv-issue-badge').forEach(function (el) { el.remove(); });
    // 알레르기 박스는 원재료명과 붙어 있으므로 한 칸 띄워 준다
    copy.querySelectorAll('.pv-allergen-box').forEach(function (el) {
        el.textContent = ' ' + el.textContent.trim();
    });
    return copy.textContent.replace(/\s+/g, ' ').trim();
}

/*
 * 워드에 넣을 칸 내용.
 *
 * 글자만 뽑으면 **원산지 굵게 표시가 사라진다.** 그건 규정이 요구하는
 * 표시라 없어지면 안 된다. 그래서 여기서는 HTML 을 그대로 살리되,
 * 화면 전용 표시만 걷어내고 클래스로만 그리던 것(알레르기 선언 박스)은
 * 인라인 스타일로 바꾼다 — 워드는 우리 CSS 파일을 읽지 않는다.
 */
function cellHtmlForDoc(cell) {
    if (!cell) return '';
    const copy = cell.cloneNode(true);
    copy.querySelectorAll('.pv-empty-hint, .pv-issue-badge').forEach(function (el) { el.remove(); });
    copy.querySelectorAll('.pv-allergen-box').forEach(function (el) {
        el.removeAttribute('class');
        el.setAttribute('style',
            'background:#000;color:#fff;font-weight:bold;padding:2px 6px;'
            + 'margin-left:4px;white-space:nowrap;');
    });
    return copy.innerHTML.trim();
}

/*
 * 워드가 여는 문서.
 *
 * .docx 는 zip+XML 이라 만들려면 라이브러리가 필요하다. 그런데 워드는
 * **HTML 을 그대로 연다** — 확장자와 MIME 만 워드로 주면 표도 서식도 살아서
 * 들어간다. 새 의존성 없이 오늘 쓸 수 있는 길이다.
 *
 * 서식은 <style> 이 아니라 칸마다 인라인으로 넣는다. 워드의 HTML 해석은
 * 선택자 지원이 들쭉날쭉해서, 인라인이라야 어느 버전에서든 같게 나온다.
 */
function labelDocHtml() {
    const data = labelRowData();
    const cellStyle = 'border:1px solid #444;padding:4px 8px;font-size:10pt;'
        + "font-family:'Malgun Gothic',sans-serif;vertical-align:middle;";
    const headStyle = cellStyle + 'background:#f2f2f2;font-weight:bold;'
        + 'width:110px;white-space:nowrap;';

    const body = data.rows.map(function (row) {
        return '<tr><td style="' + headStyle + '">' + cellHtmlForDoc(row.head) + '</td>'
            + '<td style="' + cellStyle + '">' + cellHtmlForDoc(row.body) + '</td></tr>';
    }).join('');

    let nutrition = '';
    if (data.nutrition.length) {
        const rows = data.nutrition.map(function (cells) {
            return '<tr>' + cells.map(function (cell) {
                return '<td style="' + cellStyle + '">' + cellHtmlForDoc(cell) + '</td>';
            }).join('') + '</tr>';
        }).join('');
        nutrition = '<p style="margin:14px 0 4px;font-weight:bold;">영양정보</p>'
            + '<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;">'
            + rows + '</table>';
    }

    return '<html xmlns:w="urn:schemas-microsoft-com:office:word"><head>'
        + '<meta charset="utf-8">'
        + '<title>' + (data.title || '한글표시사항') + '</title>'
        + '</head><body>'
        + (data.title ? '<p style="font-weight:bold;margin:0 0 8px;">' + data.title + '</p>' : '')
        + '<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;">'
        + body + '</table>'
        + nutrition
        + '</body></html>';
}

/* 내려받기 한 곳. 파일 종류만 달라진다. */
function saveLabelFile(blob, extension) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = labelFileName(extension);
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function downloadLabelDoc() {
    const data = labelRowData();
    if (!data.rows.length) {
        showPreviewToast('저장할 표시사항이 없습니다.', 'warning');
        return;
    }
    // BOM 을 붙여야 워드가 한글을 UTF-8 로 읽는다
    saveLabelFile(
        new Blob(['\ufeff' + labelDocHtml()], { type: 'application/msword;charset=utf-8' }),
        'doc');
    showPreviewToast('워드 파일로 저장했습니다. 표 그대로 열립니다.', 'success');
}

/* 한 줄만 복사. 원재료명 하나만 넘겨 달라는 요청이 잦다. */
async function copyOneRow(field) {
    const row = document.querySelector(`[data-field-row="${field}"]`);
    if (!row) return;
    const cells = row.tagName === 'TR'
        ? [row.querySelector('th'), row.querySelector('td')]
        : [row, row.nextElementSibling];
    const text = cleanCellText(cells[1]);
    if (!text) {
        showPreviewToast('이 줄은 아직 비어 있습니다.', 'warning');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        showPreviewToast(`"${cleanCellText(cells[0])}" 을(를) 복사했습니다.`, 'success');
    } catch (e) {
        showPreviewToast('복사가 막혀 있습니다.', 'warning');
    }
}

function labelFileName(extension) {
    const name = String((window.checkedFields || {}).prdlst_nm || '').trim();
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    return ('한글표시사항' + (name ? `_${name}` : '') + `_${date}.${extension}`)
        .replace(/[<>:"/\|?*]/g, '_');
}

async function copyLabelText() {
    const text = labelTextLines().join('\r\n');
    if (!text.trim()) {
        showPreviewToast('복사할 표시사항이 없습니다.', 'warning');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        showPreviewToast('표시사항을 글자로 복사했습니다. 워드·엑셀에 그대로 붙여넣으세요.', 'success');
    } catch (e) {
        // 클립보드 권한이 막힌 환경(구형 브라우저·비 HTTPS)에서는 골라 놓는다
        const area = document.createElement('textarea');
        area.value = text;
        area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
        document.body.appendChild(area);
        area.select();
        try {
            document.execCommand('copy');
            showPreviewToast('표시사항을 글자로 복사했습니다.', 'success');
        } catch (e2) {
            showPreviewToast('복사가 막혀 있습니다. 옆의 파일 저장을 쓰세요.', 'warning');
        }
        area.remove();
    }
}

function downloadLabelText() {
    const text = labelTextLines().join('\r\n');   // 워드·메모장에서 줄이 붙지 않게
    if (!text.trim()) {
        showPreviewToast('저장할 표시사항이 없습니다.', 'warning');
        return;
    }
    // 엑셀이 한글을 깨뜨리지 않게 BOM 을 붙인다
    saveLabelFile(new Blob(['﻿' + text], { type: 'text/plain;charset=utf-8' }), 'txt');
    showPreviewToast('텍스트 파일로 저장했습니다.', 'success');
}

/* ==================== 표에서 바로 조작 ====================
 *
 * 눈은 표를 보는데 손은 늘 다른 데 있었다 — 순서·숨김·폭은 왼쪽 패널에서,
 * 값은 다른 탭에서 고쳐야 했다. 줄 위에 마우스를 올리면 그 줄에 대한 도구가
 * 따라온다.
 *
 * 도구 막대는 **#previewContent 밖에** 둔다. 안에 두면 PDF 캡처에 찍히고
 * 표의 높이 계산까지 흔든다.
 */
let _rowToolsField = null;
let _rowToolsTimer = null;

function ensureRowTools() {
    let tools = document.getElementById('pvRowTools');
    if (tools) return tools;

    const panel = document.querySelector('.preview-panel');
    if (!panel) return null;
    if (getComputedStyle(panel).position === 'static') panel.style.position = 'relative';

    tools = document.createElement('div');
    tools.id = 'pvRowTools';
    tools.className = 'pv-rowtools';
    tools.hidden = true;
    tools.innerHTML = ''
        + '<button type="button" data-act="edit" title="이 항목의 입력칸으로">'
        + '  <i class="fas fa-pen"></i></button>'
        + '<button type="button" data-act="width" title="이 줄의 폭을 50% / 100% 로">'
        + '  <span class="pv-rowtools-width">50</span></button>'
        + '<button type="button" data-act="copy" title="이 줄의 값만 복사">'
        + '  <i class="fas fa-clipboard"></i></button>'
        + '<button type="button" data-act="hide" title="이 항목을 표시하지 않기">'
        + '  <i class="fas fa-eye-slash"></i></button>';
    panel.appendChild(tools);

    // 도구 위에 있는 동안에는 절대 사라지지 않는다
    tools.addEventListener('mouseenter', cancelRowToolsHide);
    tools.addEventListener('mouseleave', scheduleRowToolsHide);

    tools.addEventListener('click', function (e) {
        const btn = e.target.closest('button');
        if (!btn || !_rowToolsField) return;
        const field = _rowToolsField;
        if (btn.dataset.act === 'hide') {
            window.toggleFieldVisibility(field);
            hideRowTools();
        } else if (btn.dataset.act === 'width') {
            window.toggleFieldWidth(field);
        } else if (btn.dataset.act === 'edit') {
            openFieldEditor(field);
        } else if (btn.dataset.act === 'copy') {
            copyOneRow(field);
        }
    });
    return tools;
}

function showRowTools(row) {
    const tools = ensureRowTools();
    const panel = document.querySelector('.preview-panel');
    if (!tools || !panel) return;

    const field = row.dataset.fieldRow;
    if (!field || String(field).startsWith('custom_field_')) return;  // 맞춤항목은 여기서 못 고친다
    cancelRowToolsHide();
    _rowToolsField = field;

    /*
     * 지금 할 수 있는 것만 보여 준다.
     *
     * 50/100 은 2단 배치에서만 뜻이 있다 — 세로 배치는 한 줄에 한 항목이라
     * 눌러도 아무 일이 없었다. 값을 고치러 가는 것도 부모 화면(제품 화면 /
     * 표시사항 작성 화면)이 있어야 한다.
     */
    const canWidth = fieldOrderData.layoutMode === 'horizontal';
    const canEdit = !!(window.opener || (window.self !== window.top ? window.parent : null));
    const widthBtn = tools.querySelector('[data-act="width"]');
    const editBtn = tools.querySelector('[data-act="edit"]');
    if (widthBtn) widthBtn.hidden = !canWidth;
    if (editBtn) editBtn.hidden = !canEdit;

    const label = tools.querySelector('.pv-rowtools-width');
    if (label) label.textContent = (fieldOrderData.width[field] === '100%') ? '100' : '50';

    /*
     * 줄에 **붙여서** 띄운다.
     *
     * 예전에는 6px 떨어뜨려 뒀는데, 그 틈을 지나는 순간 마우스가 줄 밖으로
     * 나가면서 도구가 사라졌다. 재빨리 움직여야 겨우 누를 수 있었다.
     * 이제 줄과 도구가 맞닿아 있고, 벗어나도 잠깐 기다렸다가 사라진다.
     */
    const box = row.getBoundingClientRect();
    const base = panel.getBoundingClientRect();
    tools.hidden = false;
    tools.style.top = (box.top - base.top + panel.scrollTop) + 'px';
    tools.style.left = (box.right - base.left + panel.scrollLeft) + 'px';
}

function scheduleRowToolsHide() {
    cancelRowToolsHide();
    _rowToolsTimer = setTimeout(hideRowTools, 320);
}

function cancelRowToolsHide() {
    if (_rowToolsTimer) {
        clearTimeout(_rowToolsTimer);
        _rowToolsTimer = null;
    }
}

function hideRowTools() {
    cancelRowToolsHide();
    const tools = document.getElementById('pvRowTools');
    if (tools) tools.hidden = true;
    _rowToolsField = null;
}

/*
 * 그 항목의 입력칸으로 데려간다.
 *
 * 값은 이 창에 없다 — 제품 화면의 기본 정보 탭이나 표시사항 작성 화면의 폼에
 * 있다. 그쪽에 부탁한다. 부모가 없으면(단독으로 연 경우) 할 수 있는 일이 없다.
 */
function openFieldEditor(field) {
    const target = window.opener || (window.self !== window.top ? window.parent : null);
    if (!target) {
        if (typeof showPreviewToast === 'function') {
            showPreviewToast('값은 표시사항 작성 화면에서 고칠 수 있습니다.', 'warning');
        }
        return;
    }
    target.postMessage({ type: 'focusLabelField', field: field }, '*');
}

document.addEventListener('mouseover', function (e) {
    if (!e.target.closest) return;
    if (e.target.closest('#pvRowTools')) { cancelRowToolsHide(); return; }
    const row = e.target.closest('[data-field-row]');
    if (row) { showRowTools(row); return; }
    if (e.target.closest('#previewContent')) scheduleRowToolsHide();
});

/* 값을 두 번 누르면 그 입력칸으로. 표를 보다가 고칠 곳을 찾았을 때 가장 짧은 길이다. */
document.addEventListener('dblclick', function (e) {
    const row = e.target.closest && e.target.closest('[data-field-row]');
    if (row && row.dataset.fieldRow) openFieldEditor(row.dataset.fieldRow);
});

/* 요약 줄의 항목을 누르면 그 행으로 데려간다 (표는 매번 다시 그려지므로 위임) */
document.addEventListener('click', function (e) {
    const item = e.target.closest && e.target.closest('.pv-summary-item');
    if (item) jumpToTableRow(item.dataset.jump);
});

window.renderTableWithLayout = function(data, layoutMode) {
    const tbody = document.getElementById('previewTableBody');
    if (!tbody || !data) return;
    
    window.currentLabelData = data;
    layoutMode = layoutMode || fieldOrderData.layoutMode || 'vertical';
    
    // 세로 아니면 2단. 셋째 모드는 그리는 코드가 없다.
    if (layoutMode !== 'horizontal') {
        layoutMode = 'vertical';
        fieldOrderData.layoutMode = 'vertical';
    }

    // tbody 초기화
    tbody.innerHTML = '';
    tbody.className = `layout-${layoutMode}`;
    applyColumnGroup(tbody, layoutMode);
    
    // 필드 순서대로 렌더링
    const fields = getFieldDefinitions();
    const fieldMap = {};
    fields.forEach(f => fieldMap[f.key] = f);
    
    if (layoutMode === 'vertical') {
        renderVerticalLayout(tbody, data, fieldMap);
    } else if (layoutMode === 'horizontal') {
        renderHorizontalLayout(tbody, data, fieldMap);
    }
    
    // 영양정보 표도 같은 스위치를 따른다
    if (typeof window.refreshNutritionVisibility === 'function') {
        window.refreshNutritionVisibility();
    }

    updatePreviewSummary();

    // 스타일 재적용
    if (typeof window.updatePreviewStyles === 'function') {
        window.updatePreviewStyles();
    }
};

/*
 * 표 위 한 줄 요약 — "켰는데 아직 비어 있는" 항목이 몇 개인가.
 *
 * 빈 줄 표시는 그 줄에 붙어 있어서, 항목이 열일곱이면 스크롤 밖으로 나간다.
 * 몇 개가 남았는지는 늘 보이는 자리에 있어야 확정 전에 알아챈다.
 */
function updatePreviewSummary() {
    const box = document.getElementById('previewSummary');
    if (!box) return;

    const data = window.currentLabelData || {};
    const empty = (fieldOrderData.order || []).filter(function (key) {
        if (String(key).startsWith('custom_field_')) return false;
        return isFieldShown(key) && !String(data[key] || '').trim();
    });
    const shown = (fieldOrderData.order || []).filter(isFieldShown).length;

    if (!empty.length) {
        box.hidden = true;
        box.innerHTML = '';
        return;
    }

    const names = empty.map(function (key) {
        const el = document.querySelector(`[data-field-row="${key}"] th`);
        return `<button type="button" class="pv-summary-item" data-jump="${key}">${el ? el.textContent : key}</button>`;
    }).join('');

    box.hidden = false;
    box.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>'
        + `표시 항목 ${shown}개 중 <strong>${empty.length}개가 비어 있습니다</strong> — `
        + names;
}

/*
 * 열 정의. table-layout: fixed 에서는 <colgroup> 이 열 너비의 주인이다.
 *
 * 세로 배치는 2열(항목명 | 값), 2단 배치는 4열(항목명 | 값 | 항목명 | 값).
 * 항목명 칸의 너비는 --label-col-width 하나가 정한다 — 예전에는 CSS 변수와
 * flex-basis 와 셀마다 박은 인라인 스타일 셋에 흩어져 있었다.
 */
function applyColumnGroup(tbody, layoutMode) {
    const table = tbody.closest('table');
    if (!table) return;

    const old = table.querySelector('colgroup');
    if (old) old.remove();

    const group = document.createElement('colgroup');
    const pairs = layoutMode === 'horizontal' ? 2 : 1;
    for (let i = 0; i < pairs; i += 1) {
        const label = document.createElement('col');
        label.className = 'pv-col-label';
        group.appendChild(label);
        group.appendChild(document.createElement('col'));
    }
    table.insertBefore(group, table.firstChild);
}

// 세로 레이아웃
function renderVerticalLayout(tbody, data, fieldMap) {
    // order에 있는 필드 + 맞춤항목 모두 렌더링
    const allKeys = [...fieldOrderData.order];
    
    // 맞춤항목 추가 (order에 없으면)
    Object.keys(fieldMap).forEach(key => {
        if (key.startsWith('custom_field_') && !allKeys.includes(key)) {
            allKeys.push(key);
        }
    });
    
    allKeys.forEach(fieldKey => {
        if (!isFieldShown(fieldKey)) return;

        const field = fieldMap[fieldKey];
        if (!field) return;
        
        // 맞춤항목 처리
        if (field.isCustomField) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <th>${field.label}</th>
                <td>${field.value || ''}</td>
            `;
            tbody.appendChild(tr);
            return;
        }
        
        let value = data[fieldKey] || ''; // 빈 값도 허용
        
        // 주의사항/기타표시사항: 텍스트 변환 적용
        if ((fieldKey === 'cautions' || fieldKey === 'additional_info') && window.formatTextByOptions && window.textFormatConfig) {
            value = window.formatTextByOptions(value, window.textFormatConfig);
            if (window.textFormatConfig.mode === 'KEEP') {
                value = value.replace(/\n/g, '<br>');
            }
        }
        
        // 원재료명: 국가명 굵게 표시 + 알레르기 성분 오른쪽 정렬
        if (fieldKey === 'rawmtrl_nm_display') {
            // 1) rawmtrl_nm_display에 내장된 [알레르기 성분 : ...] 텍스트 추출 후 제거
            const embeddedAllergenMatchV = value.match(/\[알레르기\s*성분\s*:\s*([^\]]+)\]/);
            if (embeddedAllergenMatchV) {
                value = value.replace(/\[알레르기\s*성분\s*:[^\]]+\]/, '').trim();
            }
            if (typeof window.boldCountryNames === 'function') {
                value = window.boldCountryNames(value, window.countryList || []);
            }
            // 2) 우선순위: URL파라미터(parentAllergens) > DB(allergensData) > 내장텍스트
            let displayAllergens = (window.parentAllergens && window.parentAllergens.length > 0)
                ? window.parentAllergens
                : (window.allergensData && window.allergensData.length > 0 ? window.allergensData : []);
            if (!displayAllergens.length && embeddedAllergenMatchV) {
                displayAllergens = embeddedAllergenMatchV[1].replace(/함유/g, '').split(',')
                    .map(a => a.trim()).filter(Boolean);
            }
            if (displayAllergens.length > 0) {
                // 스타일은 CSS 클래스가 갖는다(.pv-allergen-box). 인라인 9pt 로
                // 박아 두면 글자 크기 설정을 올려도 이 줄만 그대로 남아,
                // 하한을 넘겼다고 생각한 라벨에서 이 문구만 미달로 인쇄된다.
                value = `${value}<div class="pv-allergen-box">${displayAllergens.join(', ')} 함유</div>`;
            }
        }
        
        // 원산지: 굵게 표시 적용
        if (fieldKey === 'country_of_origin' && typeof window.boldCountryNames === 'function') {
            value = window.boldCountryNames(value, window.countryList || []);
        }

        // 날짜 항목: 한 칸에 줄로 쌓인 값을 줄마다 한 행으로 편다.
        // ("제조연월일: 별도 표기" + "소비기한: 제조일로부터 12개월")
        // DB 칸은 하나지만 인쇄물에는 두 줄로 나와야 한다.
        if (fieldKey === 'pog_daycnt' && window.DateEntries && String(value).trim()) {
            window.DateEntries.parse(value, data.date_option).forEach(entry => {
                const dtr = document.createElement('tr');
                const dth = document.createElement('th');
                const dtd = document.createElement('td');
                dtr.dataset.fieldRow = fieldKey;
                dth.textContent = entry.type;
                dtd.style.wordWrap = 'break-word';
                dtd.style.overflowWrap = 'break-word';
                dtd.textContent = entry.value;
                dtr.appendChild(dth);
                dtr.appendChild(dtd);
                tbody.appendChild(dtr);
            });
            return;
        }

        const tr = document.createElement('tr');
        // 규정 검증 결과를 이 행에 얹으려면 행이 자기 이름을 알고 있어야 한다
        tr.dataset.fieldRow = fieldKey;
        tr.innerHTML = `
            <th>${field.label}</th>
            <td style="word-wrap: break-word; overflow-wrap: break-word;">${value}${emptyHintHtml(fieldKey, data)}</td>
        `;
        tbody.appendChild(tr);
    });
}

/*
 * 켜 두었는데 비어 있는 줄에 붙이는 화면 전용 표시.
 *
 * 표에 나가는 기준이 표시 항목 체크가 되면서, 켜고 아직 안 채운 항목은 빈 줄로
 * 나간다. 그 빈 줄이 "여기에 무엇이 들어갈 자리인지" 를 말하지 않으면 사용자는
 * 실수로 빈칸을 인쇄한다. PDF 로 뽑을 때는 지운다(.pv-exporting).
 */
function emptyHintHtml(fieldKey, data) {
    if (String(fieldKey).startsWith('custom_field_')) return '';
    if (String((data || {})[fieldKey] || '').trim()) return '';
    return '<span class="pv-empty-hint">표시하기로 켰지만 아직 비어 있습니다</span>';
}

// 가로 레이아웃 (동적 2열) - 2개씩 묶어서 행으로 렌더링
function renderHorizontalLayout(tbody, data, fieldMap) {
    // order에 있는 필드 + 맞춤항목 모두 렌더링
    const allKeys = [...fieldOrderData.order];
    
    // 맞춤항목 추가 (order에 없으면)
    Object.keys(fieldMap).forEach(key => {
        if (key.startsWith('custom_field_') && !allKeys.includes(key)) {
            allKeys.push(key);
        }
    });
    
    // 표시할 항목들만 수집
    const visibleItems = [];
    allKeys.forEach(fieldKey => {
        if (!isFieldShown(fieldKey)) return;

        const field = fieldMap[fieldKey];
        if (!field) return;
        
        const width = fieldOrderData.width[fieldKey] || '50%';
        
        // 맞춤항목 처리
        let value;
        if (field.isCustomField) {
            value = field.value || '';
        } else {
            value = data[fieldKey] || ''; // 빈 값도 허용
            
            // 주의사항/기타표시사항: 텍스트 변환 적용
            if ((fieldKey === 'cautions' || fieldKey === 'additional_info') && window.formatTextByOptions && window.textFormatConfig) {
                value = window.formatTextByOptions(value, window.textFormatConfig);
                if (window.textFormatConfig.mode === 'KEEP') {
                    value = value.replace(/\n/g, '<br>');
                }
            }
            
            // 원재료명: 국가명 굵게 표시 + 알레르기 성분 오른쪽 정렬
            if (fieldKey === 'rawmtrl_nm_display') {
                // 1) rawmtrl_nm_display에 내장된 [알레르기 성분 : ...] 텍스트 추출 후 제거
                const embeddedAllergenMatchH = value.match(/\[알레르기\s*성분\s*:\s*([^\]]+)\]/);
                if (embeddedAllergenMatchH) {
                    value = value.replace(/\[알레르기\s*성분\s*:[^\]]+\]/, '').trim();
                }
                if (typeof window.boldCountryNames === 'function') {
                    value = window.boldCountryNames(value, window.countryList || []);
                }
                // 2) 우선순위: URL파라미터(parentAllergens) > DB(allergensData) > 내장텍스트
                let displayAllergens = (window.parentAllergens && window.parentAllergens.length > 0)
                    ? window.parentAllergens
                    : (window.allergensData && window.allergensData.length > 0 ? window.allergensData : []);
                if (!displayAllergens.length && embeddedAllergenMatchH) {
                    displayAllergens = embeddedAllergenMatchH[1].replace(/함유/g, '').split(',')
                        .map(a => a.trim()).filter(Boolean);
                }
                if (displayAllergens.length > 0) {
                    value = `${value}<div class="pv-allergen-box">${displayAllergens.join(', ')} 함유</div>`;
                }
            }
            
            // 원산지: 굵게 표시 적용
            if (fieldKey === 'country_of_origin' && typeof window.boldCountryNames === 'function') {
                value = window.boldCountryNames(value, window.countryList || []);
            }
        }
        
        // 날짜 항목은 줄 수만큼 별개 항목이 된다. 가로 레이아웃은 항목을 둘씩
        // 짝지어 한 행으로 만들므로, 여기서 늘려 두면 그 규칙이 그대로 적용된다.
        if (fieldKey === 'pog_daycnt' && window.DateEntries && String(value).trim()) {
            window.DateEntries.parse(value, data.date_option).forEach(entry => {
                visibleItems.push({
                    key: fieldKey,
                    label: entry.type,
                    value: entry.value,
                    width: width
                });
            });
            return;
        }

        visibleItems.push({
            key: fieldKey,
            label: field.label,
            value: value + (field.isCustomField ? '' : emptyHintHtml(fieldKey, data)),
            width: width
        });
    });
    
    // 100% 항목과 50% 항목 분리
    const fullWidthItems = visibleItems.filter(item => item.width === '100%');
    const halfWidthItems = visibleItems.filter(item => item.width === '50%');
    
    // 50% 항목을 2개씩 묶어서 행으로 렌더링
    const rows = [];
    
    // 100% 항목 먼저 추가 (순서 유지를 위해 원래 순서대로)
    visibleItems.forEach(item => {
        if (item.width === '100%') {
            rows.push([item]);
        }
    });
    
    // 50% 항목을 2개씩 묶음
    for (let i = 0; i < halfWidthItems.length; i += 2) {
        if (i + 1 < halfWidthItems.length) {
            // 2개씩 묶어서 행 생성
            rows.push([halfWidthItems[i], halfWidthItems[i + 1]]);
        } else {
            // 마지막 홀수 항목은 100%로
            rows.push([halfWidthItems[i]]);
        }
    }
    
    // 실제 순서대로 재정렬 (원래 visibleItems 순서 유지)
    const orderedRows = [];
    let halfWidthIndex = 0;
    let currentRow = [];
    
    visibleItems.forEach(item => {
        if (item.width === '100%') {
            // 현재 행에 항목이 있으면 먼저 추가
            if (currentRow.length > 0) {
                orderedRows.push([...currentRow]);
                currentRow = [];
            }
            // 100% 항목은 단독 행
            orderedRows.push([item]);
        } else {
            // 50% 항목은 2개씩 묶음
            currentRow.push(item);
            if (currentRow.length === 2) {
                orderedRows.push([...currentRow]);
                currentRow = [];
            }
        }
    });
    
    // 마지막 남은 행 추가
    if (currentRow.length > 0) {
        orderedRows.push(currentRow);
    }
    
    /*
     * 행별로 렌더링 — **진짜 표 구조**로.
     *
     * 예전에는 <tr> 안에 <div> 를 넣고 CSS 로 display 를 바꿔 2단을 만들었다.
     * 표에서 유효하지 않은 구조라 화면·브라우저 인쇄·html2canvas 가 서로 다른
     * 것을 그릴 여지가 있었고, 열 너비가 CSS 변수와 flex 에 흩어져 있어
     * 항목명 칸을 조절할 자리도 없었다.
     *
     * 지금은 4열 표다.  항목명 | 값 | 항목명 | 값
     * 한 줄을 통째로 쓰는 항목은 값 칸이 colspan=3 을 먹는다. 열 너비는
     * <colgroup> 이 정한다(table-layout: fixed 에서 colgroup 이 우선이다).
     */
    orderedRows.forEach(rowItems => {
        const tr = document.createElement('tr');

        if (rowItems.length === 1) {
            const item = rowItems[0];
            tr.classList.add('full-width-row');
            tr.dataset.fieldRow = item.key;

            const th = document.createElement('th');
            th.textContent = item.label;
            const td = document.createElement('td');
            td.colSpan = 3;
            td.innerHTML = item.value;

            tr.appendChild(th);
            tr.appendChild(td);
        } else {
            rowItems.forEach(item => {
                const th = document.createElement('th');
                th.textContent = item.label;
                // 2단 행에는 항목이 둘이라 <tr> 이 이름을 가질 수 없다.
                // 지적을 얹고 줄 도구를 붙이는 단위는 항목이므로 칸이 갖는다.
                th.dataset.fieldRow = item.key;

                const td = document.createElement('td');
                td.dataset.fieldRow = item.key;
                td.innerHTML = item.value;

                tr.appendChild(th);
                tr.appendChild(td);
            });
        }

        tbody.appendChild(tr);
    });
}
// CSRF 토큰 가져오기 함수
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
