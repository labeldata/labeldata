// v1/static/js/home_demo.js
// 데모 페이지 통합 스크립트 (샘플 데이터, 미리보기, 품목보고번호 검증)

// ==================== 샘플 데이터 ====================
const sampleData = {
    beverage: {
        prdlst_nm: '프리미엄 오렌지주스',
        ingredient_info: '오렌지 농축액 10%',
        prdlst_dcnm: '과일/채소류음료',
        prdlst_report_no: '20240101-1234567',
        content_weight: '500ml',
        storage_method: '냉장보관(0~10℃)',
        rawmtrl_nm_display: '오렌지농축액(오렌지:미국산) 10%, 정제수, 설탕, 구연산, 비타민C',
        bssh_nm: '(주)프레시푸드',
        distributor_address: '(주)음료유통',
        frmlc_mtrqlt: 'PET',
        cautions: '부정·불량식품 신고는 국번없이 1399\n개봉 후 냉장보관하시고 빠른 시일 내에 드시기 바랍니다.',
        chk_prdlst_nm: true,
        chk_ingredient_info: true,
        chk_prdlst_dcnm: true,
        chk_prdlst_report_no: true,
        chk_content_weight: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_bssh_nm: true,
        chk_distributor_address: true,
        chk_frmlc_mtrqlt: true,
        chk_cautions: true
    },
    snack: {
        prdlst_nm: '허니버터칩',
        prdlst_dcnm: '과자',
        prdlst_report_no: '20240102-2345678',
        content_weight: '60g',
        storage_method: '직사광선을 피하고 서늘한 곳에 보관',
        rawmtrl_nm_display: '감자(국산), 식물성유지, 허니버터시즈닝[설탕, 버터시즈닝분말, 꿀분말 등]',
        bssh_nm: '(주)스낵제과',
        frmlc_mtrqlt: '플라스틱(PE)',
        cautions: '부정·불량식품 신고는 국번없이 1399',
        additional_info: '튀김유: 팜유 100%',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_prdlst_report_no: true,
        chk_content_weight: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_bssh_nm: true,
        chk_frmlc_mtrqlt: true,
        chk_cautions: true,
        chk_additional_info: true
    },
    noodle: {
        prdlst_nm: '신라면',
        prdlst_dcnm: '유탕면류',
        content_weight: '120g',
        storage_method: '직사광선을 피하고 통풍이 잘되는 곳에 보관',
        rawmtrl_nm_display: '밀가루(밀:미국산, 호주산), 팜유, 감자전분, 변성전분, 양념분말, 건조채소',
        bssh_nm: '(주)농심',
        frmlc_mtrqlt: '플라스틱(PP), 종이',
        cautions: '부정·불량식품 신고는 국번없이 1399\n뜨거운 물에 주의하세요',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_content_weight: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_bssh_nm: true,
        chk_frmlc_mtrqlt: true,
        chk_cautions: true
    },
    sauce: {
        prdlst_nm: '참깨드레싱',
        prdlst_dcnm: '드레싱',
        content_weight: '300ml',
        storage_method: '냉장보관(0~10℃), 개봉 후 냉장보관',
        rawmtrl_nm_display: '식용유지(대두유), 참깨 8%, 간장, 설탕, 식초, 마늘',
        manufacturer: '(주)소스앤소스',
        subdivider: '(주)식품소분',
        packaging_material: '유리',
        caution: '부정·불량식품 신고는 국번없이 1399\n개봉 후 반드시 냉장보관하세요',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_content_weight: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_manufacturer: true,
        chk_subdivider: true,
        chk_packaging_material: true,
        chk_caution: true
    }
};

// ==================== 샘플 데이터 로딩 ====================
function loadSampleData(type) {
    // 서버에서 라벨 데이터를 제공한 경우 샘플 데이터 로드 방지
    if (window.hasServerLabelData) {
        if (!confirm('현재 편집 중인 표시사항이 샘플 데이터로 덮어씌워집니다. 계속하시겠습니까?')) {
            return;
        }
        // 사용자가 확인한 경우 플래그 제거
        window.hasServerLabelData = false;
    }
    
    const data = sampleData[type];
    if (!data) return;

    const form = document.getElementById('demoForm');
    if (!form) return;

    // 샘플 데이터에 없는 항목 보존 (라벨명 등)
    const preservedFields = {
        label_name: form.querySelector('[name="label_name"]')?.value || ''
    };

    // 폼 초기화 대신 샘플 데이터에 있는 필드만 업데이트
    let loadedFields = 0;

    // 체크박스와 입력 필드 채우기
    Object.keys(data).forEach(key => {
        if (key.startsWith('chk_')) {
            const checkbox = document.getElementById(key);
            if (checkbox) {
                checkbox.checked = data[key];
                loadedFields++;
            }
        } else {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                field.value = data[key];
                // 원산지 필드는 값이 있을 경우 활성화
                if (key === 'country_of_origin' && data[key]) {
                    field.disabled = false;
                }
                loadedFields++;
            }
        }
    });

    // 보존된 필드 복원
    const labelNameField = form.querySelector('[name="label_name"]');
    if (labelNameField && preservedFields.label_name) {
        labelNameField.value = preservedFields.label_name;
    }
    
    // auto-resize textarea 높이 재조정 (샘플 데이터 로드 후)
    setTimeout(() => {
        const textareas = document.querySelectorAll('textarea.auto-resize');
        textareas.forEach(textarea => {
            if (typeof autoResizeHeight === 'function') {
                autoResizeHeight(textarea);
            }
        });
    }, 50);
    
    // 저장 및 미리보기 업데이트
    saveToLocalStorage();
    updatePreview();
}

function getSampleName(type) {
    const names = {
        beverage: '음료',
        snack: '과자',
        noodle: '면류',
        sauce: '소스'
    };
    return names[type] || type;
}

// ==================== 데이터 초기화 ====================
function resetAllData() {
    if (!confirm('모든 입력 데이터를 초기화하시겠습니까?\n(1399 필수 문구는 유지됩니다)')) {
        return;
    }
    
    const form = document.getElementById('demoForm');
    if (!form) return;
    
    // 폼 완전 초기화
    form.reset();
    
    // 모든 빠른 입력 버튼 비활성화 및 원래 색상 복원
    document.querySelectorAll('.quick-text-toggle').forEach(button => {
        // 활성화 상태일 경우에만 처리
        if (button.classList.contains('active')) {
            button.classList.remove('active');
            button.classList.remove('btn-primary');
            
            // 모든 outline 클래스 제거
            button.classList.remove('btn-outline-secondary', 'btn-outline-danger', 'btn-outline-info', 'btn-outline-success');
            
            // HTML에 정의된 원래 클래스 복원 (data-text로 판별)
            const buttonText = button.getAttribute('data-text') || '';
            if (buttonText.includes('1399') || buttonText.includes('페닐알라닌')) {
                button.classList.add('btn-outline-danger');
            } else if (buttonText.includes('당류') || buttonText.includes('카페인')) {
                button.classList.add('btn-outline-info');
            } else {
                button.classList.add('btn-outline-secondary');
            }
        }
    });
    
    // 모든 textarea 높이 초기화
    document.querySelectorAll('textarea.auto-resize').forEach(textarea => {
        if (typeof autoResizeHeight === 'function') {
            autoResizeHeight(textarea);
        }
    });
    
    // localStorage 초기화
    localStorage.removeItem('demo_label_data');
    
    // 미리보기 업데이트
    updatePreview();
    
    // 1399 필수 문구 자동 활성화
    setTimeout(() => {
        const button1399 = document.querySelector('.quick-text-toggle[data-text*="1399"]');
        if (button1399) {
            toggleQuickText(button1399);
        }
    }, 100);
}

// ==================== localStorage ====================
function saveToLocalStorage() {
    const data = collectFormData();
    try {
        localStorage.setItem('demo_label_data', JSON.stringify(data));
    } catch (e) {
        console.error('localStorage 저장 실패:', e);
    }
}

function loadFromLocalStorage() {
    // 모드 전환으로 복원된 데이터가 있으면 자동저장 데이터 로드 건너뛰기
    if (window.formDataRestored) {
        return;
    }
    
    // 서버에서 라벨 데이터를 제공한 경우 localStorage 로드 건너뛰기
    if (window.hasServerLabelData) {
        return;
    }
    
    try {
        const saved = localStorage.getItem('demo_label_data');
        if (saved) {
            const data = JSON.parse(saved);
            const form = document.getElementById('demoForm');
            
            Object.keys(data).forEach(key => {
                if (key.startsWith('chk_')) {
                    const checkbox = document.getElementById(key);
                    if (checkbox) checkbox.checked = data[key];
                } else {
                    const field = form.querySelector(`[name="${key}"]`);
                    if (field) field.value = data[key] || '';
                }
            });
            
            // 알레르기 데이터 복원
            if (data.ingredient_allergens) {
                const allergens = data.ingredient_allergens.split(',').filter(a => a.trim());
                window.selectedIngredientAllergens = new Set(allergens);
                // 자동 감지 여부는 알 수 없으므로 모두 수동 추가로 간주
                window.autoDetectedAllergens = new Set();
                window.selectedCrossContaminationAllergens = new Set(); 
                updateAllergenDisplay();
            }
            
            updatePreview();
        }
    } catch (e) {
        console.error('localStorage 로드 실패:', e);
    }
}

// ==================== 미리보기 ====================
function updatePreview() {
    const previewContent = document.getElementById('previewContent');
    const formData = collectFormData();
    
    const html = generatePreviewHTML(formData);
    previewContent.innerHTML = html;
    
    // 미리보기 스타일 적용
    setTimeout(() => {
        applyPreviewSettings();
        
        // 면적 및 높이 계산 (label_preview.html 방식)
        if (typeof calculateDimensionsAndArea === 'function') {
            calculateDimensionsAndArea();
        }
        
        // 분리배출마크 재설정 (드래그 가능한 아이콘으로)
        if (window.recyclingMarkData && window.recyclingMarkData.markValue) {
            if (typeof setRecyclingMark === 'function') {
                setRecyclingMark(window.recyclingMarkData.markValue);
            }
        }
        
        // auto-resize textarea 높이 재조정 (추가)
        const textareas = document.querySelectorAll('textarea.auto-resize');
        textareas.forEach(textarea => {
            if (typeof autoResizeHeight === 'function') {
                autoResizeHeight(textarea);
            }
        });
    }, 100);
}

function collectFormData() {
    const data = {};
    const form = document.getElementById('demoForm');

    form.querySelectorAll('input, textarea, select').forEach(field => {
        if (field.type === 'checkbox') {
            data[field.id] = field.checked;
        } else if (field.name) {
            data[field.name] = field.value;
        }
    });
    
    // 품목보고번호 검증 상태 추가
    const reportNo = data.prdlst_report_no?.trim();
    
    if (reportNo) {
        try {
            // 1단계: 메모리 캐시 확인
            if (verificationCache.has(reportNo)) {
                const cachedData = verificationCache.get(reportNo);
                
                let verifyStatus = 'N';
                if (cachedData.status === 'completed') {
                    verifyStatus = 'Y';
                } else if (cachedData.status === 'available') {
                    verifyStatus = 'N';
                } else if (cachedData.status === 'format_error') {
                    verifyStatus = 'F';
                } else if (cachedData.status === 'rule_error') {
                    verifyStatus = 'R';
                }
                data.report_no_verify_YN = verifyStatus;
                
                const hiddenInput = document.getElementById('report_no_verify_YN');
                if (hiddenInput) {
                    hiddenInput.value = verifyStatus;
                }
                return data;
            }
            
            // 2단계: localStorage 확인
            const storageKey = 'verification_demo_v2';
            const stored = localStorage.getItem(storageKey);
            
            if (stored) {
                const verificationData = JSON.parse(stored);
                const now = Date.now();
                
                if (verificationData.reportNo === reportNo && now <= verificationData.expiresAt) {
                    let verifyStatus = 'N';
                    if (verificationData.status === 'completed') {
                        verifyStatus = 'Y';
                    } else if (verificationData.status === 'available') {
                        verifyStatus = 'N';
                    } else if (verificationData.status === 'format_error') {
                        verifyStatus = 'F';
                    } else if (verificationData.status === 'rule_error') {
                        verifyStatus = 'R';
                    }
                    data.report_no_verify_YN = verifyStatus;
                    
                    const hiddenInput = document.getElementById('report_no_verify_YN');
                    if (hiddenInput) {
                        hiddenInput.value = verifyStatus;
                    }
                } else {
                    data.report_no_verify_YN = 'N';
                    const hiddenInput = document.getElementById('report_no_verify_YN');
                    if (hiddenInput) {
                        hiddenInput.value = 'N';
                    }
                }
            } else {
                data.report_no_verify_YN = 'N';
                const hiddenInput = document.getElementById('report_no_verify_YN');
                if (hiddenInput) {
                    hiddenInput.value = 'N';
                }
            }
        } catch (e) {
            // 검증 상태 추출 실패
            data.report_no_verify_YN = 'N';
            const hiddenInput = document.getElementById('report_no_verify_YN');
            if (hiddenInput) {
                hiddenInput.value = 'N';
            }
        }
    } else {
        data.report_no_verify_YN = 'N';
        const hiddenInput = document.getElementById('report_no_verify_YN');
        if (hiddenInput) {
            hiddenInput.value = 'N';
        }
    }
    
    // 분리배출마크 데이터 추가
    if (window.recyclingMarkData) {
        data.recycling_mark = window.recyclingMarkData.markValue;
        data.recycling_composite_text = window.recyclingMarkData.compositeText;
    }
    
    // 알레르기 관리 데이터 추가
    const crossContaminationInput = document.getElementById('selected_cross_contamination_allergens');
    if (crossContaminationInput) {
        data.cross_contamination_allergens = crossContaminationInput.value;
    }
    
    // 선택된 원재료 알레르기 데이터 추가
    const ingredientAllergensInput = document.getElementById('selected_ingredient_allergens');
    if (ingredientAllergensInput) {
        data.ingredient_allergens = ingredientAllergensInput.value;
    }

    return data;
}

function generatePreviewHTML(data) {
    // 크기 정보 가져오기 (label_preview.html 방식과 동일)
    const widthCm = document.getElementById('widthInput')?.value || 10;
    const heightCm = document.getElementById('heightInput')?.value || '자동';
    const area = document.getElementById('areaDisplay')?.value || '0';
    
    // previewContent의 가로 크기 적용
    const previewContent = document.getElementById('previewContent');
    if (previewContent) {
        const CM_TO_PX = 37.795275591; // 1cm = 37.795275591px (96 DPI 기준)
        const widthPx = parseFloat(widthCm) * CM_TO_PX;
        previewContent.style.width = `${widthPx}px`;
    }
    
    let html = '';
    
    // 상단 헤더 문구 추가 (흰색 글씨로 변경)
    html += `<div class="preview-header-box" style="text-align: center; padding: 8px 0; margin-bottom: 10px; border-bottom: 2px solid #333; background: #333;">
        <div class="header-text" style="font-weight: bold; font-size: 11pt; color: #fff;">식품 등의 표시·광고에 관한 법률에 의한 한글표시사항</div>
    </div>`;
    
    // 분리배출 마크는 별도의 드래그 가능한 컨테이너로 표시되므로 여기서는 제외
    
    html += '<table class="preview-table table-bordered" style="margin-bottom: 0; width: 100%; table-layout: fixed !important; border-collapse: collapse;">';
    let hasContent = false;

    // 필드 정의 (수정된 순서)
    const fields = [
        { key: 'prdlst_nm', label: '제품명', check: 'chk_prdlst_nm' },
        { key: 'ingredient_info', label: '특정성분 함량', check: 'chk_ingredient_info' },
        { key: 'prdlst_dcnm', label: '식품유형', check: 'chk_prdlst_dcnm' },
        { key: 'prdlst_report_no', label: '품목보고번호', check: 'chk_prdlst_report_no' },
        { key: 'content_weight', label: '내용량', check: 'chk_content_weight' },
        { key: 'country_of_origin', label: '원산지', check: 'chk_country_of_origin' },
        { key: 'storage_method', label: '보관방법', check: 'chk_storage_method' },
        { key: 'frmlc_mtrqlt', label: '용기·포장재질', check: 'chk_frmlc_mtrqlt' },
        { key: 'bssh_nm', label: '제조원 소재지', check: 'chk_bssh_nm' },
        { key: 'distributor_address', label: '유통전문판매원', check: 'chk_distributor_address' },
        { key: 'repacker_address', label: '소분원', check: 'chk_repacker_address' },
        { key: 'importer_address', label: '수입원', check: 'chk_importer_address' },
        { key: 'pog_daycnt', label: '소비기한', check: 'chk_pog_daycnt' },
        { key: 'rawmtrl_nm_display', label: '원재료명', check: 'chk_rawmtrl_nm_display', multiline: true },
        { key: 'cautions', label: '주의사항', check: 'chk_cautions', separator: true },
        { key: 'additional_info', label: '기타표시사항', check: 'chk_additional_info', separator: true }
    ];

    fields.forEach(field => {
        if (data[field.check] && data[field.key] && data[field.key].trim()) {
            const row = generateTableRow(field.label, data[field.key], field.multiline, field.separator);
            if (row) {
                html += row;
                hasContent = true;
            }
        }
    });

    html += '</table>';
    
    // 하단 푸터 문구 추가
    html += `<div class="footer-text" style="text-align: right; font-size: 7.5pt; color: #888; margin-top: 12px; padding-top: 8px; border-top: 1px solid #ddd;">
        ezlabeling.com 에서 관련법규에 따라 작성되었습니다.
        <span class="creator-info">[${new Date().toISOString().slice(0, 16).replace('T', ' ')}]</span>
    </div>`;

    if (!hasContent) {
        return '<p class="text-center text-muted" style="padding: 2rem;"><i class="fas fa-info-circle me-2"></i>체크된 항목이 없거나 입력된 데이터가 없습니다.</p>';
    }

    return html;
}

// 국가명을 굵게 표시하는 함수 (상세모드와 동일)
function boldCountryNames(text, countries) {
    if (!text || !countries || countries.length === 0) return text;
    let processedText = text;
    
    // 긴 국가명부터 처리 (예: "대한민국" 먼저, "한국" 나중에)
    // 이렇게 하면 "영국산"에서 "영국"을 먼저 찾고, "국"은 나중에 찾게 됨
    const sortedCountries = countries.sort((a, b) => b.length - a.length);
    
    sortedCountries.forEach(country => {
        if (country) {
            const escapedCountry = country.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            
            // 개선된 정규표현식:
            // 1. (?<![가-힣]): 앞에 한글이 오면 안 됨 (미국산에서 국산 방지)
            // 2. (국가명): 국가명 매칭
            // 3. (\s*산)?: 선택적으로 "산" 매칭 (공백 포함 가능)
            // 4. (?![가-힣]): 뒤에 한글이 오면 안 됨
            const regex = new RegExp(`(?<![가-힣])(${escapedCountry}(\\s*산)?)(?![가-힣])`, 'gi');
            processedText = processedText.replace(regex, '<strong>$1</strong>');
        }
    });
    return processedText;
}

function generateTableRow(label, value, multiline = false, separator = false) {
    if (!value || !value.trim()) return '';

    let valueHtml;
    
    if (separator) {
        // 주의사항과 기타표시사항: 줄바꿈을 | 로 변환
        const items = value.split('\n').filter(item => item.trim());
        valueHtml = items.join(' | ');
    } else if (multiline && label === '원재료명') {
        // 원재료명: 국가명 굵게 처리 + 알레르기 물질 정보 추가
        let processedValue = value.replace(/\n/g, '<br>');
        
        // 국가명 굵게 표시
        if (window.countryListForBold && window.countryListForBold.length > 0) {
            processedValue = boldCountryNames(processedValue, window.countryListForBold);
        }
        
        valueHtml = processedValue;
        
        // 감지된 알레르기 물질 가져오기 (constants.js의 키워드 활용)
        const detectedAllergens = getDetectedAllergens();
        
        if (detectedAllergens.length > 0) {
            const allergenText = detectedAllergens.join(', ');
            // 미리보기 팝업과 동일한 형식: "xx, xx 함유" (검은색 배경에 하얀색 글씨)
            valueHtml += `<br><span style="background-color: #000; color: #fff; font-weight: 600; padding: 2px 6px; border-radius: 3px; display: inline-block; margin-top: 4px; word-break: keep-all;">${allergenText} 함유</span>`;
        }
    } else if (label === '원산지') {
        // 원산지: 국가명 굵게 표시
        if (window.countryListForBold && window.countryListForBold.length > 0) {
            valueHtml = boldCountryNames(value, window.countryListForBold);
        } else {
            valueHtml = value;
        }
    } else if (multiline) {
        // 기타 멀티라인: 줄바꿈 유지
        valueHtml = value.replace(/\n/g, '<br>');
    } else {
        // 일반 텍스트
        valueHtml = value;
    }

    return `
        <tr>
            <th style="width: 100px !important; min-width: 100px !important; max-width: 100px !important; background: #f8f9fa; font-weight: 600; text-align: center; vertical-align: middle; white-space: nowrap; padding: 6px 10px; border: 1px solid #dee2e6;">
                ${label}
            </th>
            <td style="word-wrap: break-word; word-break: break-word; overflow-wrap: break-word; white-space: normal; padding: 6px 10px; border: 1px solid #dee2e6; vertical-align: top;">
                ${valueHtml}
            </td>
        </tr>
    `;
}

// 감지된 알레르기 물질 가져오기 (constants.js의 키워드 활용)
function getDetectedAllergens() {
    // window.selectedIngredientAllergens에서 선택된 알레르기 목록 반환 (하이브리드 방식)
    if (window.selectedIngredientAllergens && window.selectedIngredientAllergens.size > 0) {
        return Array.from(window.selectedIngredientAllergens);
    }
    
    // 빈 배열 반환 (선택된 알레르기가 없는 경우)
    return [];
}

// ==================== 미리보기 설정 ====================
function toggleSettingsPanel() {
    const panel = document.getElementById('settingsPanelDemo');
    const toggleBtn = document.getElementById('toggleSettingsBtn');
    
    if (panel && toggleBtn) {
        if (panel.style.display === 'none') {
            // 패널 열기
            panel.style.display = 'block';
            toggleBtn.innerHTML = '<i class="fas fa-cog me-1"></i>설정 닫기';
            toggleBtn.title = '서식 설정 닫기';
        } else {
            // 패널 닫기
            panel.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-cog me-1"></i>설정 열기';
            toggleBtn.title = '서식 설정 열기';
        }
    }
}

// 미리보기 설정 초기화 함수
function resetPreviewSettings() {
    // 기본값으로 되돌리기
    const defaults = {
        widthInput: 10,
        heightInput: 11,
        fontFamilySelect: "'Noto Sans KR', sans-serif",
        fontSizeInput: 10,
        letterSpacingInput: -5,
        lineHeightInput: 1.5
    };
    
    // 각 입력 필드 초기화
    Object.keys(defaults).forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            if (element.tagName === 'SELECT') {
                element.value = defaults[id];
            } else {
                element.value = defaults[id];
            }
        }
    });
    
    // 설정 적용
    applyPreviewSettings();
    
    // 사용자에게 피드백
    const btn = document.getElementById('resetPreviewSettingsBtn');
    if (btn) {
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check me-1"></i>초기화 완료';
        btn.disabled = true;
        
        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }, 1500);
    }
}

function applyPreviewSettings() {
    const previewContent = document.getElementById('previewContent');
    if (!previewContent) return;

    const fontFamily = document.getElementById('fontFamilySelect')?.value || "'Noto Sans KR', sans-serif";
    const fontSize = document.getElementById('fontSizeInput')?.value || 10;
    const letterSpacing = document.getElementById('letterSpacingInput')?.value || -5;
    const lineHeight = document.getElementById('lineHeightInput')?.value || 1.5;
    
    // 가로 크기 적용 (label_preview.html 방식)
    const widthCm = document.getElementById('widthInput')?.value || 10;
    const CM_TO_PX = 37.795275591; // 1cm = 37.795275591px (96 DPI 기준)
    const widthPx = parseFloat(widthCm) * CM_TO_PX;
    previewContent.style.width = `${widthPx}px`;

    const table = previewContent.querySelector('table');
    if (table) {
        table.style.fontFamily = fontFamily;
        table.style.fontSize = fontSize + 'pt';
        table.style.letterSpacing = (letterSpacing / 100) + 'em';
        table.style.lineHeight = lineHeight;
    }
    
    // 테이블 셀에도 스타일 적용
    const cells = previewContent.querySelectorAll('td');
    cells.forEach(cell => {
        cell.style.fontFamily = fontFamily;
        cell.style.fontSize = fontSize + 'pt';
        cell.style.letterSpacing = (letterSpacing / 100) + 'em';
        cell.style.lineHeight = lineHeight;
    });
}

// ==================== 규정 검증 ====================
function validateRegulations() {
    const data = collectFormData();
    const validationResults = document.getElementById('validationResults');
    
    if (!validationResults) return;

    const issues = [];
    const warnings = [];

    // 필수 항목 체크
    const requiredFields = [
        { key: 'prdlst_nm', name: '제품명', checked: 'chk_prdlst_nm' },
        { key: 'content_weight', name: '내용량', checked: 'chk_content_weight' }
    ];

    requiredFields.forEach(field => {
        if (!data[field.checked] || !data[field.key] || !data[field.key].trim()) {
            issues.push(`<strong>${field.name}</strong>은(는) 필수 항목입니다.`);
        }
    });

    // 내용량 단위 체크 (mg, g, kg, l, ml만 허용, 열량 표시도 허용)
    if (data.chk_content_weight && data.content_weight && data.content_weight.trim()) {
        const contentWeight = data.content_weight.trim();
        // 숫자와 단위가 붙어 있는 경우도 인식
        const validUnits = /(\d+(?:\.\d+)?)(mg|g|kg|ml|l)(?![a-zA-Z])/i;
        if (!validUnits.test(contentWeight)) {
            issues.push('<strong>내용량에 올바른 단위가 표시되지 않았습니다.</strong> mg, g, kg, ml, l 중 하나를 사용하세요. (예: 500g, 1L, 250ml, 500l(500kcal))');
        }
    }

    // 글자 크기 체크
    const fontSize = parseFloat(document.getElementById('fontSizeInput')?.value || 10);
    if (fontSize < 7) {
        issues.push('글자 크기는 <strong>최소 7pt 이상</strong>이어야 합니다.');
    }

    // 제품명 길이 체크
    if (data.prdlst_nm && data.prdlst_nm.length > 100) {
        warnings.push('제품명이 너무 깁니다 (100자 권장).');
    }

    // 제품명에 특정 원재료가 포함된 경우 특정성분 함량 체크
    if (data.prdlst_nm && data.chk_prdlst_nm) {
        const productName = data.prdlst_nm.toLowerCase();
        const ingredientInfo = (data.ingredient_info || '').trim();
        const ingredientInfoChecked = data.chk_ingredient_info;
        
        // 주스, 과일, 우유, 치즈 등이 제품명에 포함된 경우
        const ingredientKeywords = ['주스', '과즙', '사과', '오렌지', '포도', '딸기', '복숭아', '망고', 
                                    '우유', '치즈', '초콜릿', '요구르트', '요거트', '과일'];
        
        const hasIngredientInName = ingredientKeywords.some(keyword => 
            productName.includes(keyword)
        );
        
        if (hasIngredientInName && (!ingredientInfoChecked || !ingredientInfo)) {
            issues.push('<strong>제품명에 포함된 원재료의 특정성분 함량이 표시되지 않았습니다.</strong> (예: 사과주스 → 과즙 함량 표시 필수)');
        }
    }

    // 알레르기 중복 검증 (원재료 사용 vs 제조시설 혼입)
    if (typeof validateAllergenSeparation === 'function') {
        const allergenValidation = validateAllergenSeparation();
        if (!allergenValidation.isValid && allergenValidation.duplicates.length > 0) {
            issues.push(`<strong>알레르기 물질 중복 오류:</strong> ${allergenValidation.duplicates.join(', ')}은(는) 원재료에 이미 사용되었으므로 제조시설 혼입 경고에 포함할 수 없습니다. 원재료 사용 알레르기는 "원재료명"에만 표시되어야 합니다.`);
        }
    }
    
    // 알레르기 누락/중복 검증 (checkAllergenDuplication 함수 사용)
    if (typeof checkAllergenDuplication === 'function') {
        const allergenErrors = checkAllergenDuplication();
        if (allergenErrors && allergenErrors.length > 0) {
            allergenErrors.forEach(error => {
                issues.push(error);
            });
        }
    }

    // 결과 표시
    if (issues.length === 0 && warnings.length === 0) {
        validationResults.className = 'alert alert-success';
        validationResults.innerHTML = '<i class="fas fa-check-circle me-2"></i><strong>검증 통과!</strong> 모든 필수 규정을 충족하고 있습니다.';
        validationResults.style.display = 'block';
    } else {
        let html = '';
        
        if (issues.length > 0) {
            validationResults.className = 'alert alert-danger';
            html += '<h6><i class="fas fa-exclamation-triangle me-2"></i>규정 위반 사항</h6><ul class="mb-0">';
            issues.forEach(issue => {
                html += `<li>${issue}</li>`;
            });
            html += '</ul>';
        }
        
        if (warnings.length > 0) {
            if (issues.length > 0) html += '<hr>';
            if (issues.length === 0) validationResults.className = 'alert alert-warning';
            html += '<h6><i class="fas fa-exclamation-circle me-2"></i>주의 사항</h6><ul class="mb-0">';
            warnings.forEach(warning => {
                html += `<li>${warning}</li>`;
            });
            html += '</ul>';
        }
        
        validationResults.innerHTML = html;
        validationResults.style.display = 'block';
    }

    setTimeout(() => {
        validationResults.style.display = 'none';
    }, 5000);
}

// ==================== 로그인 모달 ====================
function showLoginModal() {
    // 현재 폼 데이터를 sessionStorage에 임시 저장
    const formData = collectFormData();
    try {
        sessionStorage.setItem('pending_label_data', JSON.stringify(formData));
        sessionStorage.setItem('return_to_demo', 'true');
    } catch (e) {
        console.error('❌ 임시 저장 실패:', e);
    }
    
    // Bootstrap Modal 표시
    const modal = new bootstrap.Modal(document.getElementById('loginModal'));
    modal.show();
}

// ==================== 품목보고번호 검증 기능 ====================
// 검증된 제품 정보를 저장할 전역 변수
let verifiedProductData = null;

// 검증 이력 캐시 (중복 검증 방지)
const verificationCache = new Map();

// 캐시 유효 시간 설정 (30분)
const CACHE_DURATION = 30 * 60 * 1000; // 30분 = 1800000ms

// 오류 상태별 도움말
const errorHelp = {
    'format_error': '형식: YYYY-MM-XXXXXXXX (예: 2024-12-01234567)',
    'rule_error': '품목보고번호 형식이 올바르지 않습니다. 하이픈(-) 포함 17자리를 입력하세요.',
    'not_found': '식품안전나라에서 해당 번호를 찾을 수 없습니다. 번호를 다시 확인해주세요.',
    'error': '검증 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
};

function verifyReportNo() {
    const btn = document.getElementById('verifyReportNoBtn');
    const copyBtn = document.getElementById('copyProductDataBtn');
    const resultMsg = document.getElementById('verifyResultMessage');
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    if (!btn) return;
    
    // 상태 복구: 완료된 상태에서 클릭 시 초기화
    const completedStates = ['사용가능', '형식오류', '복사완료', '등록제품', '검증 중', '검증실패'];
    const isCompleted = completedStates.some(state => btn.innerHTML.includes(state));
    
    if (isCompleted) {
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
        if (copyBtn) copyBtn.style.display = 'none';
        if (resultMsg) resultMsg.style.display = 'none';
        if (reportNoInput) reportNoInput.disabled = false;
        verifiedProductData = null;
        return;
    }
    
    let reportNo = reportNoInput?.value?.trim();
    
    if (!reportNo) {
        btn.innerHTML = '<i class="fas fa-edit me-1"></i>입력필요';
        btn.className = 'btn btn-outline-secondary btn-sm';
        btn.title = '품목보고번호를 입력해주세요';
        btn.disabled = false;
        
        setTimeout(() => {
            alert('품목보고번호를 입력하세요.');
            btn.innerHTML = '번호검증';
            btn.className = 'btn btn-outline-primary btn-sm';
            btn.title = 'API 중복 검사 및 번호 규칙 검증';
        }, 1000);
        return;
    }

    // 캐시 확인 (최근 검증한 번호)
    if (verificationCache.has(reportNo)) {
        const cached = verificationCache.get(reportNo);
        showCachedResult(btn, copyBtn, resultMsg, cached);
        return;
    }

    // localStorage에서 캐시 확인 (페이지 새로고침 대응)
    const cachedState = restoreVerificationState();
    
    if (cachedState && cachedState.status) {
        // completed인데 productData가 없으면 캐시 무시하고 API 호출
        if (cachedState.status === 'completed' && !cachedState.productData) {
            clearVerificationState();
        } else {
            showCachedResult(btn, copyBtn, resultMsg, {
                status: cachedState.status,
                product_data: cachedState.productData,
                verified: cachedState.status === 'available' || cachedState.status === 'completed'
            });
            return;
        }
    }

    // 로딩 중 입력 비활성화
    btn.disabled = true;
    if (reportNoInput) reportNoInput.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>검증 중...';
    btn.className = 'btn btn-secondary btn-sm';

    // 검증용 번호: 하이픈(-)을 제거한 값
    const verifyReportNo = reportNo.replace(/-/g, '');

    // 데모 페이지에서는 label_id 없이 검증만 진행
    fetch('/label/verify-report-no/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ 
            label_id: null,  // 데모에서는 null
            prdlst_report_no: verifyReportNo 
        })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json();
    })
    .then(data => {
        // 결과 캐싱
        verificationCache.set(reportNo, data);
        
        // 성공 상태 처리
        if (data.verified && data.status === 'available') {
            btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>사용가능';
            btn.className = 'btn btn-success btn-sm';
            btn.title = '등록된 품목보고번호로 사용 가능합니다';
            
            saveVerificationState('available', reportNo);
            if (reportNoInput) {
                reportNoInput.style.borderColor = '#28a745';
                reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(40, 167, 69, 0.25)';
                reportNoInput.style.backgroundColor = '#d4edda';
            }
            return;
        }
        
        // 등록된 제품 정보가 있는 경우 - 복사 버튼 표시
        if (data.status === 'completed' && data.product_data) {
            verifiedProductData = data.product_data;
            
            btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>등록제품';
            btn.className = 'btn btn-info btn-sm';
            btn.title = '식품안전나라에 등록된 제품입니다';
            
            saveVerificationState('completed', reportNo, data.product_data);
            if (reportNoInput) {
                reportNoInput.style.borderColor = '#17a2b8';
                reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(23, 162, 184, 0.25)';
                reportNoInput.style.backgroundColor = '#d1ecf1';
            }
            
            // 복사 버튼 표시 (애니메이션 효과)
            const copyBtn = document.getElementById('copyProductDataBtn');
            if (copyBtn) {
                copyBtn.style.display = 'inline-block';
                copyBtn.innerHTML = '복사하기';
                copyBtn.className = 'btn btn-success btn-sm';
                copyBtn.style.opacity = '0';
                copyBtn.style.transition = 'opacity 0.3s ease-in';
                setTimeout(() => { copyBtn.style.opacity = '1'; }, 10);
            }
            
            // 결과 메시지 표시 (애니메이션 효과)
            const resultMsg = document.getElementById('verifyResultMessage');
            if (resultMsg) {
                resultMsg.style.display = 'block';
                resultMsg.className = 'alert alert-info mb-0';
                resultMsg.innerHTML = '<i class="fas fa-info-circle me-2"></i>식품안전나라에 등록된 제품입니다. 복사 버튼을 눌러 정보를 가져올 수 있습니다.';
                resultMsg.style.opacity = '0';
                resultMsg.style.transition = 'opacity 0.3s ease-in';
                setTimeout(() => { resultMsg.style.opacity = '1'; }, 10);
            }
            return;
        }
        
        // 실패 상태별 처리
        const status = data.status || 'unknown';
        let message = data.message || '검증에 실패했습니다.';
        const resultMsg = document.getElementById('verifyResultMessage');
        
        switch(status) {
            case 'format_error':
                btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>형식오류';
                btn.className = 'btn btn-warning btn-sm';
                btn.title = '품목보고번호 형식이 올바르지 않습니다';
                saveVerificationState('format_error', reportNo);
                if (reportNoInput) {
                    reportNoInput.style.borderColor = '#ffc107';
                    reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(255, 193, 7, 0.25)';
                    reportNoInput.style.backgroundColor = '#fff3cd';
                }
                if (resultMsg) {
                    resultMsg.style.display = 'block';
                    resultMsg.className = 'alert alert-warning mb-0';
                    resultMsg.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>' + message;
                }
                break;
                
            case 'rule_error':
                btn.innerHTML = '<i class="fas fa-times-circle me-1"></i>규칙오류';
                btn.className = 'btn btn-danger btn-sm';
                btn.title = '품목보고번호 규칙이 올바르지 않습니다';
                saveVerificationState('rule_error', reportNo);
                if (reportNoInput) {
                    reportNoInput.style.borderColor = '#dc3545';
                    reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(220, 53, 69, 0.25)';
                    reportNoInput.style.backgroundColor = '#f8d7da';
                }
                if (resultMsg) {
                    resultMsg.style.display = 'block';
                    resultMsg.className = 'alert alert-danger mb-0';
                    resultMsg.innerHTML = '<i class="fas fa-times-circle me-2"></i>' + message;
                }
                break;
                
            case 'not_found':
            case 'error':
            default:
                btn.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>오류';
                btn.className = 'btn btn-secondary btn-sm';
                btn.title = '품목보고번호 검증 오류';
                if (resultMsg) {
                    resultMsg.style.display = 'block';
                    resultMsg.className = 'alert alert-danger mb-0';
                    resultMsg.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>' + message;
                }
                break;
        }
    })
    .catch(err => {
        // 네트워크 오류는 일반 오류로 처리
        handleVerificationError(btn, { status: 'error', message: '검증 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.' });
    })
    .finally(() => {
        btn.disabled = false;
        if (reportNoInput) reportNoInput.disabled = false;
    });
}

// 제품 정보 자동 입력 함수
function applyProductData(btn, productData) {
    btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>복사완료';
    btn.className = 'btn btn-success btn-sm';
    btn.title = '제품 정보를 성공적으로 불러왔습니다';
    
    // 제품명
    if (productData.prdlst_nm) {
        const prdlstNmInput = document.querySelector('input[name="prdlst_nm"]');
        if (prdlstNmInput) {
            prdlstNmInput.value = productData.prdlst_nm;
            prdlstNmInput.style.backgroundColor = '#e3f2fd';
            prdlstNmInput.style.border = '2px solid #2196f3';
            const checkbox = document.getElementById('chk_prdlst_nm');
            if (checkbox) checkbox.checked = true;
        }
    }
    
    // 식품유형
    if (productData.prdlst_dcnm) {
        const prdlstDcnmInput = document.querySelector('input[name="prdlst_dcnm"]');
        if (prdlstDcnmInput) {
            prdlstDcnmInput.value = productData.prdlst_dcnm;
            prdlstDcnmInput.style.backgroundColor = '#e3f2fd';
            prdlstDcnmInput.style.border = '2px solid #2196f3';
            const checkbox = document.getElementById('chk_prdlst_dcnm');
            if (checkbox) checkbox.checked = true;
        }
    }
    
    // 용기·포장재질
    if (productData.packaging_material) {
        const packagingInput = document.querySelector('input[name="packaging_material"]');
        if (packagingInput) {
            packagingInput.value = productData.packaging_material;
            packagingInput.style.backgroundColor = '#e3f2fd';
            packagingInput.style.border = '2px solid #2196f3';
            const checkbox = document.getElementById('chk_packaging_material');
            if (checkbox) checkbox.checked = true;
        }
    }
    
    // 제조원
    if (productData.manufacturer) {
        const manufacturerInput = document.querySelector('input[name="manufacturer"]');
        if (manufacturerInput) {
            manufacturerInput.value = productData.manufacturer;
            manufacturerInput.style.backgroundColor = '#e3f2fd';
            manufacturerInput.style.border = '2px solid #2196f3';
            const checkbox = document.getElementById('chk_manufacturer');
            if (checkbox) checkbox.checked = true;
        }
    }
    
    // 원재료명
    if (productData.rawmtrl_nm) {
        const rawmtrlTextarea = document.getElementById('rawmtrl_nm_textarea');
        if (rawmtrlTextarea) {
            rawmtrlTextarea.value = productData.rawmtrl_nm;
            rawmtrlTextarea.style.backgroundColor = '#e3f2fd';
            rawmtrlTextarea.style.border = '2px solid #2196f3';
            const checkbox = document.getElementById('chk_rawmtrl_nm_display');
            if (checkbox) checkbox.checked = true;
            
            // textarea 높이 자동 조절
            if (typeof autoResizeHeight === 'function') {
                autoResizeHeight(rawmtrlTextarea);
            }
        }
    }
    
    // 미리보기 업데이트
    if (typeof updatePreview === 'function') {
        updatePreview();
    }
    
    // localStorage 저장
    if (typeof saveToLocalStorage === 'function') {
        saveToLocalStorage();
    }
}

// 검증된 제품 정보 복사 함수
function copyVerifiedProductData() {
    if (!verifiedProductData) {
        alert('복사할 제품 정보가 없습니다.');
        return;
    }
    
    const btn = document.getElementById('verifyReportNoBtn');
    const copyBtn = document.getElementById('copyProductDataBtn');
    
    // 정보 적용
    applyProductData(btn, verifiedProductData);
    
    // 복사 버튼 숨기기
    if (copyBtn) {
        copyBtn.style.display = 'none';
    }
    
    // 검증 버튼 상태 업데이트
    btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>복사완료';
    btn.className = 'btn btn-success btn-sm';
    btn.title = '제품 정보를 성공적으로 불러왔습니다';
    
    // 결과 메시지 숨기기
    const resultMsg = document.getElementById('verifyResultMessage');
    if (resultMsg) {
        resultMsg.style.display = 'none';
    }
    
    // 전역 변수 초기화
    verifiedProductData = null;
}

// 캐시된 결과 표시 함수
function showCachedResult(btn, copyBtn, resultMsg, data) {
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    
    if (data.verified && data.status === 'available') {
        btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>사용가능';
        btn.className = 'btn btn-success btn-sm';
        btn.title = '등록된 품목보고번호로 사용 가능합니다 (캐시됨)';
        if (reportNoInput) {
            reportNoInput.style.borderColor = '#28a745';
            reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(40, 167, 69, 0.25)';
            reportNoInput.style.backgroundColor = '#d4edda';
        }
    } else if (data.status === 'completed' && data.product_data) {
        verifiedProductData = data.product_data;
        btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>등록제품';
        btn.className = 'btn btn-info btn-sm';
        btn.title = '식품안전나라에 등록된 제품입니다 (캐시됨)';
        
        if (reportNoInput) {
            reportNoInput.style.borderColor = '#17a2b8';
            reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(23, 162, 184, 0.25)';
            reportNoInput.style.backgroundColor = '#d1ecf1';
        }
        
        if (copyBtn) {
            copyBtn.style.display = 'inline-block';
        }
        
        if (resultMsg) {
            resultMsg.style.display = 'block';
            resultMsg.className = 'alert alert-info mb-0';
            resultMsg.innerHTML = '<i class="fas fa-info-circle me-2"></i>식품안전나라에 등록된 제품입니다. 복사 버튼을 눌러 정보를 가져올 수 있습니다.';
        }
    } else {
        handleVerificationError(btn, data);
    }
}

// 검증 오류 처리 함수
function handleVerificationError(btn, data) {
    const status = data.status || 'unknown';
    let message = data.message || '검증에 실패했습니다.';
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    const resultMsg = document.getElementById('verifyResultMessage');
    
    switch(status) {
        case 'format_error':
            btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>형식오류';
            btn.className = 'btn btn-warning btn-sm';
            btn.title = '품목보고번호 형식이 올바르지 않습니다';
            if (reportNoInput) {
                reportNoInput.style.borderColor = '#ffc107';
                reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(255, 193, 7, 0.25)';
                reportNoInput.style.backgroundColor = '#fff3cd';
            }
            break;
        case 'rule_error':
            btn.innerHTML = '<i class="fas fa-times-circle me-1"></i>규칙오류';
            btn.className = 'btn btn-danger btn-sm';
            btn.title = '품목보고번호 규칙이 올바르지 않습니다';
            if (reportNoInput) {
                reportNoInput.style.borderColor = '#dc3545';
                reportNoInput.style.boxShadow = '0 0 0 0.2rem rgba(220, 53, 69, 0.25)';
                reportNoInput.style.backgroundColor = '#f8d7da';
            }
            break;
        default:
            btn.innerHTML = '<i class="fas fa-times-circle me-1"></i>검증실패';
            btn.className = 'btn btn-danger btn-sm';
            btn.title = message;
            break;
    }
    
    if (resultMsg) {
        resultMsg.style.display = 'block';
        resultMsg.className = 'alert alert-danger mb-0';
        resultMsg.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>' + message;
        resultMsg.style.opacity = '0';
        resultMsg.style.transition = 'opacity 0.3s ease-in';
        setTimeout(() => { resultMsg.style.opacity = '1'; }, 10);
    }
}

// 검증 상태 저장 함수 (localStorage + 만료시간)
function saveVerificationState(status, reportNo, productData = null) {
    try {
        const demoKey = 'verification_demo_v2';
        
        const verificationData = {
            status: status,
            reportNo: reportNo,
            timestamp: new Date().toISOString(),
            expiresAt: Date.now() + CACHE_DURATION,
            productData: productData
        };
        
        // 간편모드 키에 저장
        localStorage.setItem(demoKey, JSON.stringify(verificationData));
        
        // 상세모드와의 호환성을 위해 label_id가 있으면 해당 키에도 저장
        const labelId = document.getElementById('label_id')?.value;
        if (labelId) {
            const detailKey = `verification_${labelId}`;
            localStorage.setItem(detailKey, JSON.stringify(verificationData));
        }
    } catch (e) {
        // 검증 상태 저장 실패
    }
}

// 검증 상태 복원 함수 (localStorage에서 읽기)
function restoreVerificationState() {
    try {
        const demoKey = 'verification_demo_v2';
        let stored = localStorage.getItem(demoKey);
        
        // 간편모드 키에 없으면 상세모드 키 확인
        if (!stored) {
            const labelId = document.getElementById('label_id')?.value;
            if (labelId) {
                const detailKey = `verification_${labelId}`;
                stored = localStorage.getItem(detailKey);
            }
        }
        
        if (!stored) {
            return null;
        }
        
        const data = JSON.parse(stored);
        const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
        const reportNo = reportNoInput?.value?.trim();
        
        // 저장된 품목보고번호와 현재 입력된 번호가 다르면 삭제
        if (data.reportNo !== reportNo) {
            localStorage.removeItem(demoKey);
            const labelId = document.getElementById('label_id')?.value;
            if (labelId) {
                localStorage.removeItem(`verification_${labelId}`);
            }
            return null;
        }
        
        // 만료 시간 체크
        const now = Date.now();
        if (now > data.expiresAt) {
            localStorage.removeItem(demoKey);
            const labelId = document.getElementById('label_id')?.value;
            if (labelId) {
                localStorage.removeItem(`verification_${labelId}`);
            }
            return null;
        }
        
        return data;
    } catch (e) {
        // 검증 상태 복원 실패
        return null;
    }
}

// 검증 상태 초기화 함수
function clearVerificationState() {
    const btn = document.getElementById('verifyReportNoBtn');
    if (btn) {
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
    }
    
    const copyBtn = document.getElementById('copyProductDataBtn');
    if (copyBtn) {
        copyBtn.style.display = 'none';
    }
    
    const resultMsg = document.getElementById('verifyResultMessage');
    if (resultMsg) {
        resultMsg.style.display = 'none';
    }
    
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    if (reportNoInput) {
        reportNoInput.style.borderColor = '';
        reportNoInput.style.boxShadow = '';
        reportNoInput.style.backgroundColor = '';
    }
    
    // hidden input도 초기화
    const hiddenInput = document.getElementById('report_no_verify_YN');
    if (hiddenInput) {
        hiddenInput.value = 'N';
    }
    
    verifiedProductData = null;
    
    // localStorage에서도 제거
    try {
        localStorage.removeItem('verification_demo_v2');
        
        // 상세모드 키도 제거
        const labelId = document.getElementById('label_id')?.value;
        if (labelId) {
            localStorage.removeItem(`verification_${labelId}`);
        }
    } catch (e) {
        // 검증 상태 삭제 실패
    }
}

// getCookie 함수 (CSRF 토큰용)
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

// ==================== DOMContentLoaded ====================
document.addEventListener('DOMContentLoaded', function() {
    // 페이지 로드 시 스크롤을 최상단으로 리셋
    window.scrollTo(0, 0);
    document.querySelector('.demo-left-panel')?.scrollTo(0, 0);
    document.querySelector('.demo-right-panel')?.scrollTo(0, 0);
    
    // 전역 변수 초기화 (알레르기 관리용)
    if (!window.selectedIngredientAllergens) {
        window.selectedIngredientAllergens = new Set();
    }
    if (!window.autoDetectedAllergens) {
        window.autoDetectedAllergens = new Set();
    }
    if (!window.selectedCrossContaminationAllergens) {
        window.selectedCrossContaminationAllergens = new Set();
    }
    
    // localStorage에서 모드 전환 시 저장된 폼 데이터 복원
    try {
        const savedFormData = localStorage.getItem('mode_switch_form_data');
        if (savedFormData) {
            const data = JSON.parse(savedFormData);
            
            // 1단계: 일반 필드 복원
            Object.keys(data).forEach(key => {
                const value = data[key];
                
                // 체크박스는 별도 처리
                if (key.startsWith('chk_')) return;
                
                // 식품유형은 나중에 처리 (필터링 후)
                if (key === 'food_type') return;
                
                const field = document.querySelector(`[name="${key}"]`) || document.getElementById(key);
                
                if (field) {
                    if (field.type === 'checkbox') {
                        field.checked = value;
                    } else if (field.type === 'radio') {
                        if (field.value === value) {
                            field.checked = true;
                        }
                    } else if (field.tagName === 'SELECT') {
                        // Select2 필드 감지 및 트리거
                        field.value = value;
                        if ($(field).hasClass('select2-hidden-accessible')) {
                            $(field).trigger('change');
                        }
                    } else {
                        field.value = value;
                    }
                }
            });
            
            // 2단계: 식품유형 처리
            const foodGroup = data['food_group'];
            const foodType = data['food_type'];
            
            if (foodGroup && foodType) {
                // 대분류 먼저 설정
                const $foodGroupSelect = $('#food_group');
                if ($foodGroupSelect.length) {
                    $foodGroupSelect.val(foodGroup).trigger('change');
                    
                    // 소분류는 대분류 로드 후 설정 (200ms 지연)
                    setTimeout(() => {
                        const $foodTypeSelect = $('#food_type');
                        if ($foodTypeSelect.length) {
                            $foodTypeSelect.val(foodType).trigger('change');
                        }
                    }, 200);
                }
            }
            
            // 3단계: 체크박스 상태 복원
            Object.keys(data).forEach(key => {
                if (key.startsWith('chk_')) {
                    const checkbox = document.getElementById(key);
                    if (checkbox && checkbox.type === 'checkbox') {
                        checkbox.checked = (data[key] === 'Y' || data[key] === true);
                    }
                }
            });
            
            // 복원된 데이터 보호 플래그 (다른 초기화 코드 방지)
            window.formDataRestored = true;
            window.restoredFormData = data;
            
            // 사용 후 삭제
            localStorage.removeItem('mode_switch_form_data');
        }
    } catch (e) {
        console.error('❌ 폼 데이터 복원 실패:', e);
    }
    
    // 모드 전환으로 저장된 품목보고번호 복원 (하위 호환성)
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    if (reportNoInput) {
        try {
            const savedReportNo = localStorage.getItem('mode_switch_report_no');
            if (savedReportNo && savedReportNo.trim()) {
                // 현재 입력값이 없거나 DB 값인 경우에만 복원
                if (!reportNoInput.value || reportNoInput.value.trim() === '') {
                    reportNoInput.value = savedReportNo;
                }
                // 사용 후 삭제
                localStorage.removeItem('mode_switch_report_no');
            }
        } catch (e) {
            // 품목보고번호 복원 실패
        }
    }
    
    // 품목보고번호 실시간 형식 검증
    if (reportNoInput) {
        // 입력 이벤트 - 실시간 형식 검증
        reportNoInput.addEventListener('input', function(e) {
            const value = e.target.value;
            // 품목보고번호 패턴: YYYY-MM-XXXXXXXX (예: 2024-12-01234567)
            const pattern = /^\d{4}-\d{2}-\d{8}$/;
            
            if (value && value.length > 0) {
                if (pattern.test(value)) {
                    // 올바른 형식
                    e.target.style.borderColor = '#28a745';
                    e.target.style.boxShadow = '0 0 0 0.2rem rgba(40, 167, 69, 0.25)';
                } else if (value.length >= 17) {
                    // 길이는 충분하지만 형식 오류
                    e.target.style.borderColor = '#ffc107';
                    e.target.style.boxShadow = '0 0 0 0.2rem rgba(255, 193, 7, 0.25)';
                } else {
                    // 입력 중
                    e.target.style.borderColor = '';
                    e.target.style.boxShadow = '';
                }
            } else {
                // 입력 없음
                e.target.style.borderColor = '';
                e.target.style.boxShadow = '';
            }
            
            // 번호가 변경되면 검증 상태 초기화
            clearVerificationState();
        });
    }
    
    // 모든 quick-text-toggle 버튼의 원래 색상 저장
    document.querySelectorAll('.quick-text-toggle').forEach(button => {
        const colorClass = button.className.match(/btn-outline-\w+/)?.[0];
        if (colorClass) {
            button.dataset.originalColor = colorClass;
        }
    });
    
    // 로그인 후 돌아온 경우 처리
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    if (isAuthenticated && sessionStorage.getItem('pending_label_data')) {
        // 임시 저장된 데이터 복원
        try {
            const pendingData = JSON.parse(sessionStorage.getItem('pending_label_data'));
            
            // 폼에 데이터 복원
            Object.keys(pendingData).forEach(key => {
                const input = document.querySelector(`[name="${key}"]`);
                if (input) {
                    input.value = pendingData[key];
                }
            });
            
            // 임시 데이터 삭제
            sessionStorage.removeItem('pending_label_data');
            sessionStorage.removeItem('return_to_demo');
            
            // 자동 저장 실행
            setTimeout(() => {
                saveLabelData();
            }, 500);
        } catch (e) {
            console.error('❌ 임시 데이터 복원 실패:', e);
        }
    }
    
    // localStorage에서 이전 데이터 복원
    loadFromLocalStorage();
    
    // localStorage 데이터 복원 후 검증 상태 복원 (지연 실행)
    setTimeout(() => {
        const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
        const reportNo = reportNoInput?.value?.trim();
        
        if (reportNo) {
            const cachedState = restoreVerificationState();
            if (cachedState && cachedState.status) {
                const btn = document.getElementById('verifyReportNoBtn');
                const copyBtn = document.getElementById('copyProductDataBtn');
                const resultMsg = document.getElementById('verifyResultMessage');
                
                showCachedResult(btn, copyBtn, resultMsg, {
                    status: cachedState.status,
                    product_data: cachedState.productData,
                    verified: cachedState.status === 'available' || cachedState.status === 'completed'
                });
            }
        }
    }, 300);

    // ==================== 식품유형 선택기 (Select2 적용) ====================
    const foodGroupSelect = $('#food_group');
    const foodTypeSelect = $('#food_type');
    
    // Select2 초기화
    if (foodGroupSelect.length && foodTypeSelect.length) {
        // 대분류 Select2 초기화
        foodGroupSelect.select2({
            placeholder: '대분류',
            allowClear: true,
            width: '100%'
        });
        
        // 소분류 Select2 초기화
        foodTypeSelect.select2({
            placeholder: '소분류',
            allowClear: true,
            width: '100%'
        });
        
        // 대분류 변경 이벤트
        foodGroupSelect.on('change', function() {
            const selectedGroup = $(this).val();
            
            // 소분류 초기화
            foodTypeSelect.empty().append('<option value=""></option>');
            
            if (!selectedGroup) {
                foodTypeSelect.val(null).trigger('change');
                return;
            }
            
            // 농수축산물인 경우 알림 표시
            if (selectedGroup === '농수축산물') {
                alert('농수축산물은 상세모드에서만 작성 가능합니다.\n상단의 "상세 모드 보기" 버튼을 클릭하세요.');
                foodGroupSelect.val('').trigger('change');
                return;
            }
            
            // 식품첨가물 또는 혼합제제인 경우 API로 데이터 가져오기
            if (selectedGroup === '식품첨가물' || selectedGroup === '혼합제제') {
                fetch(`/label/food-types-by-group/?group=${encodeURIComponent(selectedGroup)}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.food_types) {
                            data.food_types.forEach(item => {
                                const option = new Option(item.food_type, item.food_type, false, false);
                                option.dataset.group = item.food_group;
                                foodTypeSelect.append(option);
                            });
                            foodTypeSelect.trigger('change');
                        }
                    })
                    .catch(error => console.error('Error loading food types:', error));
            } else {
                // 일반 식품유형인 경우 기존 로직
                const allOptions = foodTypeSelect.data('allOptions') || [];
                allOptions.forEach(option => {
                    if (option.group === selectedGroup) {
                        const newOption = new Option(option.text, option.value, false, false);
                        newOption.dataset.group = option.group;
                        foodTypeSelect.append(newOption);
                    }
                });
                foodTypeSelect.trigger('change');
            }
        });
        
        // 초기 로드 시 모든 옵션 저장
        const initialOptions = [];
        foodTypeSelect.find('option').each(function() {
            if ($(this).val()) {
                initialOptions.push({
                    value: $(this).val(),
                    text: $(this).text(),
                    group: $(this).data('group')
                });
            }
        });
        foodTypeSelect.data('allOptions', initialOptions);
        
        // 소분류 선택 시 식품유형 필드 자동 채우기 및 필드 규칙 적용
        foodTypeSelect.on('change', function() {
            const selectedFoodType = $(this).val();
            const selectedGroup = foodGroupSelect.val();
            const prdlstDcnmInput = document.querySelector('input[name="prdlst_dcnm"]');
            
            if (prdlstDcnmInput && selectedFoodType) {
                prdlstDcnmInput.value = selectedFoodType;
            }
            
            // 식품첨가물/혼합제제인 경우 필드 규칙 적용
            if (selectedGroup === '식품첨가물' || selectedGroup === '혼합제제') {
                applyAdditiveFieldRules(selectedGroup);
            }
            
            updatePreview();
        });
    }
    
    // 식품첨가물/혼합제제 필드 규칙 적용 함수
    function applyAdditiveFieldRules(foodGroup) {
        fetch(`/label/get-additive-field-settings/?food_group=${encodeURIComponent(foodGroup)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.settings) {
                    const settings = data.settings;
                    
                    // 체크박스 ID 매핑
                    const fieldMapping = {
                        'prdlst_nm': 'chk_prdlst_nm',
                        'ingredient_info': 'chk_ingredient_info',
                        'prdlst_dcnm': 'chk_prdlst_dcnm',
                        'content_weight': 'chk_content_weight',
                        'weight_calorie': 'chk_weight_calorie',
                        'prdlst_report_no': 'chk_prdlst_report_no',
                        'country_of_origin': 'chk_country_of_origin',
                        'frmlc_mtrqlt': 'chk_frmlc_mtrqlt',
                        'pog_daycnt': 'chk_pog_daycnt',
                        'rawmtrl_nm': 'chk_rawmtrl_nm',
                        'storage_method': 'chk_storage_method',
                        'bssh_nm': 'chk_bssh_nm',
                        'nutritions': 'chk_calories',
                        'cautions': 'chk_cautions'
                    };
                    
                    // 각 필드에 규칙 적용
                    Object.keys(settings).forEach(field => {
                        const checkboxId = fieldMapping[field];
                        if (checkboxId) {
                            const checkbox = document.getElementById(checkboxId);
                            if (checkbox) {
                                const value = settings[field];
                                checkbox.checked = value === 'Y';
                                checkbox.disabled = value === 'D';
                            }
                        }
                    });
                }
            })
            .catch(error => console.error('Error applying field rules:', error));
    }

    // ==================== PDF 저장 버튼 -> 로그인 유도 ====================
    const pdfBtn = document.getElementById('exportPdfBtn');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // 로그인 모달을 띄우는 대신 PDF 다운로드 함수를 직접 호출합니다.
            downloadAsPDF();
        });
    }

    // ==================== 실시간 입력 감지 ====================
    const form = document.getElementById('demoForm');
    if (form) {
        form.addEventListener('input', function(e) {
            saveToLocalStorage();
            updatePreview();
        });

        form.addEventListener('change', function(e) {
            if (e.target.type === 'checkbox') {
                saveToLocalStorage();
                updatePreview();
            }
        });
    } else {
        // demoForm을 찾을 수 없습니다
    }

    // ==================== 설정 패널 ====================
    const toggleSettingsBtn = document.getElementById('toggleSettingsBtn');
    if (toggleSettingsBtn) {
        toggleSettingsBtn.addEventListener('click', toggleSettingsPanel);
    }
    
    // 설정 초기화 버튼
    const resetPreviewSettingsBtn = document.getElementById('resetPreviewSettingsBtn');
    if (resetPreviewSettingsBtn) {
        resetPreviewSettingsBtn.addEventListener('click', resetPreviewSettings);
    }

    // 설정 변경 시 미리보기 업데이트
    const fontFamilySelect = document.getElementById('fontFamilySelect');
    const fontSizeInput = document.getElementById('fontSizeInput');
    const letterSpacingInput = document.getElementById('letterSpacingInput');
    const lineHeightInput = document.getElementById('lineHeightInput');

    [fontFamilySelect, fontSizeInput, letterSpacingInput, lineHeightInput].forEach(element => {
        if (element) {
            element.addEventListener('change', applyPreviewSettings);
            element.addEventListener('input', applyPreviewSettings);
        }
    });
    
    // 크기 및 분리배출 마크 변경 시 미리보기 업데이트
    const labelWidth = document.getElementById('labelWidth');
    const labelHeight = document.getElementById('labelHeight');
    const recyclingMark = document.getElementById('recyclingMark');
    
    [labelWidth, labelHeight, recyclingMark].forEach(element => {
        if (element) {
            element.addEventListener('change', updatePreview);
            element.addEventListener('input', updatePreview);
        }
    });

    // 규정 검증 버튼
    const validateButton = document.getElementById('validateButton');
    if (validateButton) {
        validateButton.addEventListener('click', validateRegulations);
    }
    
    // ==================== home.html에서 마이그레이션된 이벤트 리스너들 ====================
    
    // 국가 선택 시 원산지 자동 채우기 및 입력 필드 활성화/비활성화
    const countrySelect = document.getElementById('countrySelect');
    const countryInput = document.querySelector('input[name="country_of_origin"]');
    if (countrySelect && countryInput) {
        countrySelect.addEventListener('change', function() {
            if (this.value === '직접입력') {
                // 직접입력 선택 시 입력 필드 활성화
                countryInput.disabled = false;
                countryInput.value = '';
                countryInput.focus();
            } else if (this.value === '') {
                // "-- 국가 선택 --" 선택 시 입력 필드 비활성화 및 초기화
                countryInput.disabled = true;
                countryInput.value = '';
            } else {
                // 특정 국가 선택 시 자동 입력 및 필드 비활성화
                countryInput.value = this.value;
                countryInput.disabled = true;
            }
            updatePreview();
        });
    }
    
    // 빠른 문구 토글 버튼 이벤트 리스너
    document.querySelectorAll('.quick-text-toggle').forEach(button => {
        button.addEventListener('click', function() {
            toggleQuickText(this);
        });
    });
    
    // 1399 필수 문구 기본 활성화
    setTimeout(() => {
        const button1399 = document.querySelector('.quick-text-toggle[data-text*="1399"]');
        if (button1399 && !button1399.classList.contains('active')) {
            // localStorage에 데이터가 없거나, cautions 필드가 비어있을 경우에만 자동 활성화
            const cautionTextarea = document.querySelector('textarea[name="cautions"]');
            if (cautionTextarea && !cautionTextarea.value.includes('1399')) {
                toggleQuickText(button1399);
            }
        }
    }, 100);
    
    // 알레르기 빠른 추가 버튼 이벤트 리스너
    document.querySelectorAll('.quick-allergen-btn, .full-allergen-btn').forEach(button => {
        button.addEventListener('click', function() {
            const allergen = this.dataset.allergen;
            if (window.selectedIngredientAllergens.has(allergen)) {
                removeAllergenTag(allergen);
            } else {
                addAllergenTag(allergen, false);
            }
        });
    });
    
    // 자동 높이 조절 textarea 초기화 (반드시 호출)
    initAutoResizeTextareas();
    
    // 면적 계산 이벤트 리스너
    const widthInput = document.getElementById('widthInput');
    const heightInput = document.getElementById('heightInput');
    
    if (widthInput) {
        widthInput.addEventListener('input', function() {
            updatePreview();
        });
    }
    
    // 분리배출 마크 이벤트 리스너
    const recyclingMarkSelect = document.getElementById('recyclingMarkSelect');
    const addRecyclingMarkBtn = document.getElementById('addRecyclingMarkBtn');
    const additionalRecyclingText = document.getElementById('additionalRecyclingText');
    
    if (addRecyclingMarkBtn && recyclingMarkSelect) {
        addRecyclingMarkBtn.addEventListener('click', function() {
            const selectedOption = recyclingMarkSelect.options[recyclingMarkSelect.selectedIndex];
            const markValue = selectedOption.value;
            
            if (!markValue) {
                alert('마크를 선택해주세요.');
                return;
            }
            
            if (addRecyclingMarkBtn.textContent === '추가') {
                // 마크 데이터 저장
                if (!window.recyclingMarkData) {
                    window.recyclingMarkData = {};
                }
                window.recyclingMarkData.markValue = markValue;
                window.recyclingMarkData.compositeText = additionalRecyclingText?.value || '';
                
                // 마크 아이콘 추가
                setRecyclingMark(markValue);
                addRecyclingMarkBtn.textContent = '제거';
                addRecyclingMarkBtn.classList.replace('btn-outline-primary', 'btn-danger');
            } else {
                // 마크 제거
                removeRecyclingMark();
                addRecyclingMarkBtn.textContent = '추가';
                addRecyclingMarkBtn.classList.replace('btn-danger', 'btn-outline-primary');
                recyclingMarkSelect.value = '';
            }
        });
    }
    
    // 복합재질 정보 실시간 업데이트
    if (additionalRecyclingText) {
        let updateTimeout;
        
        additionalRecyclingText.addEventListener('input', function() {
            clearTimeout(updateTimeout);
            updateTimeout = setTimeout(function() {
                updateCompositeTextPreview();
            }, 300);
        });
        
        additionalRecyclingText.addEventListener('paste', function() {
            setTimeout(updateCompositeTextPreview, 50);
        });
        
        additionalRecyclingText.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' || e.key === 'Delete') {
                setTimeout(updateCompositeTextPreview, 50);
            }
        });
    }
    
    // ==================== 알레르기 관리 모듈 ====================
    initializeAllergenModule();
});

// ==================== PDF 다운로드 기능 ====================
function downloadAsPDF() {
    const previewContent = document.getElementById('previewContent');
    const prdlstNmInput = document.querySelector('input[name="prdlst_nm"]');
    
    if (!previewContent) {
        alert('미리보기 영역을 찾을 수 없습니다.');
        return;
    }

    // 현재 설정된 가로/세로 길이 가져오기 (미리보기 팝업과 동일)
    const widthInput = document.getElementById('widthInput');
    const heightInput = document.getElementById('heightInput');
    const width = parseFloat(widthInput?.value) || 10;
    const height = parseFloat(heightInput?.value) || 11;
    
    // cm를 pt로 변환 (1cm = 28.35pt) - label_preview.js와 동일
    const widthPt = width * 28.35;
    const heightPt = height * 28.35;

    html2canvas(previewContent, {
        scale: 3, // 고해상도를 위해 스케일 증가 (label_preview.js와 동일)
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#ffffff',
        width: previewContent.scrollWidth,
        height: previewContent.scrollHeight,
        scrollX: 0,
        scrollY: 0,
        logging: false
    }).then(canvas => {
        try {
            const { jsPDF } = window.jspdf;
            
            // PDF 생성 (가로, 세로 방향 및 단위, 크기 설정)
            const orientation = widthPt > heightPt ? 'l' : 'p'; // 가로가 길면 landscape
            const doc = new jsPDF(orientation, 'pt', [widthPt, heightPt]);

            const imgData = canvas.toDataURL('image/png');
            
            // PDF에 이미지 추가 (이미지를 PDF 크기에 맞춤)
            doc.addImage(imgData, 'PNG', 0, 0, widthPt, heightPt);

            // 파일명 생성 (연월일 포함)
            const today = new Date();
            const year = today.getFullYear().toString();
            const month = (today.getMonth() + 1).toString().padStart(2, '0');
            const day = today.getDate().toString().padStart(2, '0');
            const dateStr = `${year}${month}${day}`;
            
            // 제품명 가져오기
            const productName = (prdlstNmInput?.value || '').trim();
            
            // 파일명 구성: 한글표시사항_제품명_연월일
            let fileName = '한글표시사항';
            
            if (productName) {
                fileName += `_${productName}`;
            }
            
            fileName += `_${dateStr}.pdf`;
            
            // 파일명에서 특수문자 제거 (파일시스템에서 허용되지 않는 문자들)
            fileName = fileName.replace(/[<>:"/\\|?*]/g, '_');

            // Blob을 생성하여 '다른 이름으로 저장' 대화상자를 엽니다.
            const pdfBlob = doc.output('blob');
            const blobUrl = URL.createObjectURL(pdfBlob);

            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // 메모리 해제
            URL.revokeObjectURL(blobUrl);

        } catch (error) {
            console.error('PDF 생성 중 오류 발생:', error);
            alert('PDF를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
        }
    }).catch(err => {
        console.error('html2canvas 오류:', err);
        alert('미리보기를 이미지로 변환하는 중 오류가 발생했습니다.');
    });
}

// ==================== 저장 버튼 로직 ====================
function handleSaveLabel() {
    // 로그인 상태 확인 (Django 템플릿 변수 사용)
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    
    if (isAuthenticated) {
        // 로그인된 상태 - 데이터 저장
        saveLabelData();
    } else {
        // 미로그인 상태 - Bootstrap Modal로 안내 메시지 표시
        showLoginModal();
    }
}

function saveLabelData() {
    const formData = collectFormData();
    
    // label_id가 있으면 포함 (기존 라벨 업데이트)
    const labelId = new URLSearchParams(window.location.search).get('label_id');
    if (labelId) {
        formData.label_id = labelId;
    }
    
    // 필수 항목 체크
    if (!formData.prdlst_nm || !formData.prdlst_nm.trim()) {
        alert('제품명을 입력해주세요.');
        return;
    }
    
    // 저장 버튼 비활성화 및 로딩 표시
    const saveBtn = document.getElementById('saveLabelBtn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.classList.remove('btn-warning', 'btn-success', 'btn-danger');
        saveBtn.classList.add('btn-secondary');
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장중...';
    }
    
    fetch('/save-label/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // localStorage 데이터 초기화
            localStorage.removeItem('demo_label_data');
            
            // 저장 버튼 피드백 (성공)
            const saveBtn = document.getElementById('saveLabelBtn');
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.classList.remove('btn-secondary');
                saveBtn.classList.add('btn-success');
                saveBtn.innerHTML = '<i class="fas fa-check me-1"></i>저장완료';
                
                // 1.5초 후 원래 상태로 복구
                setTimeout(() => {
                    saveBtn.classList.remove('btn-success');
                    saveBtn.classList.add('btn-warning');
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장하기';
                }, 1500);
            }
            
            // URL을 label_id가 포함된 것으로 변경 (새로고침 없이)
            if (data.label_id) {
                const newUrl = `/?label_id=${data.label_id}`;
                window.history.replaceState({}, '', newUrl);
            }
        } else if (data.requires_login) {
            // 로그인 필요 응답 처리
            const userConfirmed = confirm(data.message);
            if (userConfirmed) {
                window.location.href = data.login_url || '/user-management/login/?next=/';
            }
        } else {
            console.error('❌ 저장 실패:', data.error);
            
            // 저장 버튼 피드백 (실패)
            const saveBtn = document.getElementById('saveLabelBtn');
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.classList.remove('btn-secondary');
                saveBtn.classList.add('btn-danger');
                saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>저장실패';
                
                // 3초 후 원래 상태로 복구
                setTimeout(() => {
                    saveBtn.classList.remove('btn-danger');
                    saveBtn.classList.add('btn-warning');
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장하기';
                }, 3000);
            }
        }
    })
    .catch(error => {
        console.error('❌ 서버 통신 오류:', error);
        
        // 저장 버튼 피드백 (오류)
        const saveBtn = document.getElementById('saveLabelBtn');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.classList.remove('btn-secondary');
            saveBtn.classList.add('btn-danger');
            saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>통신오류';
            
            // 3초 후 원래 상태로 복구
            setTimeout(() => {
                saveBtn.classList.remove('btn-danger');
                saveBtn.classList.add('btn-warning');
                saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장하기';
            }, 3000);
        }
    });
}

function getCsrfToken() {
    return getCookie('csrftoken');
}

// 표시사항 리스트 네비게이션 처리
function handleListNavigation() {
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    
    if (isAuthenticated) {
        window.location.href = '/label/my-labels/';
    } else {
        showFeatureModal('list');
    }
}

// 상세 모드 전환 처리
function handleDetailModeSwitch() {
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    
    if (isAuthenticated) {
        switchToEditor();
    } else {
        showFeatureModal('detail');
    }
}

// 기능 유도 모달 표시
function showFeatureModal(featureType) {
    const modal = document.getElementById('featureModal');
    const title = modal.querySelector('#featureModalTitle');
    const subtitle = modal.querySelector('#featureModalSubtitle');
    const icon = modal.querySelector('#featureModalIcon');
    
    if (featureType === 'list') {
        title.textContent = '표시사항 리스트 보기';
        subtitle.textContent = '작성한 표시사항을 한눈에 관리하세요!';
        icon.className = 'fas fa-list fa-4x mb-3';
    } else if (featureType === 'detail') {
        title.textContent = '상세 모드';
        subtitle.textContent = '더 많은 기능으로 정밀하게 작성하세요!';
        icon.className = 'fas fa-edit fa-4x mb-3';
    }
    
    icon.style.color = '#667eea';
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// 작성 페이지로 전환
function switchToEditor() {
    const labelId = new URLSearchParams(window.location.search).get('label_id');
    
    // 모드 전환 시 항상 localStorage에 임시 저장 (DB 저장 아님)
    saveFormDataToLocalStorage();
    
    // 현재 입력된 품목보고번호를 localStorage에 저장 (모드 전환 시 전달용)
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    if (reportNoInput && reportNoInput.value.trim()) {
        try {
            localStorage.setItem('mode_switch_report_no', reportNoInput.value.trim());
        } catch (e) {
            // 품목보고번호 저장 실패
        }
    }
    
    if (labelId) {
        // 기존 표시사항이 있으면 해당 ID로 이동
        window.location.href = `/label/label-creation/${labelId}/`;
    } else {
        // 빈 화면에서도 상세모드로 이동 가능
        window.location.href = '/label/label/create/';
    }
}

// 저장하지 않은 데이터 확인
function hasUnsavedData() {
    const form = document.getElementById('demoForm');
    if (!form) return false;
    
    const formData = new FormData(form);
    
    // 주요 필드 중 하나라도 값이 있으면 true
    const importantFields = [
        'prdlst_nm',
        'prdlst_dcnm',
        'rawmtrl_nm_display',
        'content_weight',
        'manufacturer'
    ];
    
    for (const field of importantFields) {
        const value = formData.get(field);
        if (value && value.trim()) {
            return true;
        }
    }
    
    return false;
}

// 폼 데이터를 localStorage에 저장
function saveFormDataToLocalStorage() {
    const form = document.getElementById('demoForm');
    if (!form) {
        console.error('❌ demoForm을 찾을 수 없습니다');
        return;
    }
    
    const data = {};
    
    // 필수 전달 필드
    const CORE_FIELDS = [
        'label_name', 'prdlst_nm', 'prdlst_dcnm', 'content_weight', 'food_type', 'food_group',
        'prdlst_report_no', 'country_of_origin', 'storage_method',
        'rawmtrl_nm_display', 'frmlc_mtrqlt', 'ingredient_info',
        'bssh_nm', 'distributor_address', 'repacker_address', 'importer_address',
        'pog_daycnt', 'cautions', 'additional_info'
    ];
    
    // 체크박스 필드
    const CHECKBOX_FIELDS = [
        'chk_prdlst_nm', 'chk_ingredient_info', 'chk_prdlst_dcnm',
        'chk_prdlst_report_no', 'chk_content_weight', 'chk_country_of_origin',
        'chk_storage_method', 'chk_pog_daycnt', 'chk_rawmtrl_nm_display',
        'chk_cautions', 'chk_additional_info', 'chk_frmlc_mtrqlt',
        'chk_bssh_nm', 'chk_distributor_address', 'chk_repacker_address', 'chk_importer_address'
    ];
    
    // 조건부 필드
    const OPTIONAL_FIELDS = [
        'food_category_radio', 'weight_calorie', 'pog_daycnt',
        'importer_address', 'repacker_address', 'frmlc_mtrqlt',
        'nutrition_text',
        'preservation_type', 'processing_method', 'processing_condition'
    ];
    
    console.log('📦 간편모드 데이터 수집 시작...');
    
    // 기존 localStorage 또는 복원된 데이터에서 상세모드 전용 필드 가져오기
    let existingData = {};
    try {
        // 먼저 전역 변수에서 확인 (복원 후 localStorage는 삭제됨)
        if (window.restoredFormData) {
            existingData = window.restoredFormData;
            console.log('  📥 복원된 데이터에서 로드:', Object.keys(existingData).length, '개 필드');
        } else {
            // 전역 변수 없으면 localStorage 확인
            const savedData = localStorage.getItem('mode_switch_form_data');
            if (savedData) {
                existingData = JSON.parse(savedData);
                console.log('  📥 localStorage에서 로드:', Object.keys(existingData).length, '개 필드');
            }
        }
    } catch (e) {
        console.warn('  ⚠️ 기존 데이터 로드 실패:', e);
    }
    
    // 필수 필드 수집
    CORE_FIELDS.forEach(key => {
        let field = null;
        let value = '';
        
        // 식품유형 필드는 ID로 직접 찾기 (Select2 적용됨)
        if (key === 'food_group' || key === 'food_type') {
            field = document.getElementById(key);
            console.log(`  🔍 ${key} 필드 찾기:`, field ? '발견' : '없음');
            if (field) {
                value = field.value || '';
                console.log(`    현재 값:`, value ? value : '(빈 값)');
                console.log(`    selectedIndex:`, field.selectedIndex);
                console.log(`    options.length:`, field.options.length);
            }
        } else {
            field = document.querySelector(`[name="${key}"]`) || document.getElementById(key);
        }
        
        if (field) {
            if (!value) {
                value = field.value || '';
            }
            data[key] = value;
            // 식품유형은 빈 값이어도 로그 출력
            if (value || key === 'food_type' || key === 'food_group') {
                const displayValue = value ? value.substring(0, 50) + (value.length > 50 ? '...' : '') : '(빈 값)';
                console.log(`  ✓ ${key}:`, displayValue);
            }
        } else {
            console.warn(`  ⚠️ ${key}: 필드를 찾을 수 없음`);
        }
    });
    
    // 체크박스 상태 수집
    CHECKBOX_FIELDS.forEach(key => {
        const checkbox = document.getElementById(key);
        if (checkbox && checkbox.type === 'checkbox') {
            data[key] = checkbox.checked ? 'Y' : 'N';
            console.log(`  ✓ 체크박스 ${key}:`, data[key]);
        } else {
            console.warn(`  ⚠️ 체크박스 ${key}: 찾을 수 없음`);
        }
    });
    
    // 조건부 필드 수집 (값이 있을 때만)
    OPTIONAL_FIELDS.forEach(key => {
        // 라디오/체크박스는 :checked 먼저 확인
        let field = document.querySelector(`[name="${key}"]:checked`);
        if (!field) {
            field = document.querySelector(`[name="${key}"]`) || document.getElementById(key);
        }
        
        if (field && field.value) {
            data[key] = field.value;
            console.log(`  ✓ ${key}: ${field.value}`);
        }
    });
    
    // 상세모드 전용 필드 보존 (간편모드에 없는 필드들)
    const DETAIL_ONLY_FIELDS = ['preservation_type', 'processing_method', 'processing_condition'];
    DETAIL_ONLY_FIELDS.forEach(key => {
        if (existingData.hasOwnProperty(key)) {
            data[key] = existingData[key];
            console.log(`  🔄 상세모드 전용 필드 보존 ${key}:`, data[key] || '(빈 값)');
        }
    });
    
    try {
        localStorage.setItem('mode_switch_form_data', JSON.stringify(data));
        console.log('✅ 간편모드 데이터 저장 완료:', Object.keys(data).length, '개 필드');
        console.log('  저장된 필드:', Object.keys(data).join(', '));
    } catch (e) {
        console.error('❌ localStorage 저장 실패:', e);
    }
}

// CSRF 토큰 가져오기
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

// 탭 전환 함수
function switchTab(tabName) {
    // 모든 탭 콘텐츠 숨기기
    document.querySelectorAll('.tab-content-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // 모든 탭 버튼 비활성화
    document.querySelectorAll('.form-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // 선택된 탭 콘텐츠 표시
    const targetPanel = document.getElementById('tab-' + tabName);
    if (targetPanel) {
        targetPanel.classList.add('active');
        
        // 탭 전환 후 해당 탭 내의 모든 textarea 높이 재계산
        setTimeout(() => {
            const textareas = targetPanel.querySelectorAll('textarea.auto-resize');
            textareas.forEach(textarea => {
                if (typeof autoResizeHeight === 'function') {
                    autoResizeHeight(textarea);
                }
            });
        }, 50);
    }
    
    // 선택된 버튼 활성화
    const targetBtn = document.querySelector('.form-tab[onclick*="' + tabName + '"]');
    if (targetBtn) {
        targetBtn.classList.add('active');
    }
    
    // 미리보기 업데이트 (항상)
    if (typeof updatePreview === 'function') {
        updatePreview();
    }
}

// 자동 높이 조절 textarea 초기화
function initAutoResizeTextareas() {
    const autoResizeTextareas = document.querySelectorAll('textarea.auto-resize');
    
    autoResizeTextareas.forEach((textarea, index) => {
        // 초기 높이 설정
        autoResizeHeight(textarea);
        
        // input 이벤트 리스너
        textarea.addEventListener('input', function() {
            autoResizeHeight(this);
        });
        
        // change 이벤트 리스너 (추가)
        textarea.addEventListener('change', function() {
            autoResizeHeight(this);
        });
        
        // paste 이벤트 리스너
        textarea.addEventListener('paste', function() {
            setTimeout(() => autoResizeHeight(this), 10);
        });
        
        // cut 이벤트 리스너
        textarea.addEventListener('cut', function() {
            setTimeout(() => autoResizeHeight(this), 10);
        });
        
        // keyup 이벤트 리스너 (추가 - 즉각 반응)
        textarea.addEventListener('keyup', function() {
            autoResizeHeight(this);
        });
    });
}

// textarea 높이 자동 조절
function autoResizeHeight(textarea) {
    // 높이를 초기화하여 scrollHeight를 정확히 계산
    textarea.style.height = 'auto';
    textarea.style.height = ''; // 완전 초기화
    
    // 내용에 맞게 높이 설정 (최소 1줄 높이 유지)
    const minHeight = 38; // 1줄 높이 (padding 포함)
    const newHeight = Math.max(minHeight, textarea.scrollHeight);
    textarea.style.height = newHeight + 'px';
    
    // 강제 적용 (CSS 충돌 방지)
    textarea.style.setProperty('height', newHeight + 'px', 'important');
}

// 알레르기 모듈 열기/닫기
function toggleAllergenModule() {
    const content = document.getElementById('allergenModuleContent');
    const icon = document.getElementById('allergenModuleToggleIcon');
    
    if (content.style.display === 'none') {
        content.style.display = 'flex';
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');
    } else {
        content.style.display = 'none';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-right');
    }
}

// 알레르기 관리 모듈 초기화
function initializeAllergenModule() {
    // constants.js의 ALLERGEN_KEYWORDS를 window.allergenKeywords로 사용
    // 중복 정의 제거: constants.js의 상세한 키워드 매핑을 그대로 사용
    if (!window.allergenKeywords) {
        console.error('❌ constants.js의 ALLERGEN_KEYWORDS가 로드되지 않았습니다.');
    }
    
    // 원재료명 입력 감지 (실시간 알레르기 물질 감지)
    const rawmtrlTextarea = document.getElementById('rawmtrl_nm_textarea');
    if (rawmtrlTextarea) {
        let detectTimeout;
        
        rawmtrlTextarea.addEventListener('input', function() {
            clearTimeout(detectTimeout);
            // 300ms 딜레이로 단축 (더 빠른 반응)
            detectTimeout = setTimeout(() => {
                detectAllergens(true); // 자동 감지 모드
            }, 300);
        });
    }
    
    // 제조시설 혼입 우려 물질 선택 버튼
    document.querySelectorAll('.allergen-toggle').forEach(button => {
        button.addEventListener('click', function() {
            this.classList.toggle('active');
            this.classList.toggle('btn-warning');
            this.classList.toggle('btn-outline-secondary');
            
            updateCrossContaminationPreview();
            updateToggleAllButtonState(); // 전체 선택/해제 버튼 상태 업데이트
        });
    });
}

// 수동으로 알레르기 물질 감지 (새로고침 버튼)
function manualDetectAllergens() {
    // 전체 초기화: 자동 감지 항목 + 수동 선택 항목 모두 제거
    window.selectedIngredientAllergens.clear();
    window.autoDetectedAllergens.clear();
    
    // 원재료명 기반 자동 재감지
    detectAllergens(false); // 수동 감지 모드 (로딩 효과 표시)
}

// 전체 알레르기 목록 드롭다운 토글
function toggleAllergenDropdown() {
    const fullList = document.getElementById('allergenFullList');
    const icon = document.getElementById('allergenDropdownIcon');
    
    if (fullList.style.display === 'none') {
        fullList.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        fullList.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

// 선택된 알레르기 물질 관리 (전역 변수)
window.selectedIngredientAllergens = new Set();
window.autoDetectedAllergens = new Set();
window.selectedCrossContaminationAllergens = new Set(); // 교차오염 알레르기 추가

// 알레르기 태그 추가
function addAllergenTag(allergen, isAuto = false) {
    if (isAuto) {
        window.autoDetectedAllergens.add(allergen);
    }
    window.selectedIngredientAllergens.add(allergen);
    updateAllergenDisplay();
    
    // 수동 추가인 경우 제조시설 경고 문구 전체 삭제
    if (!isAuto) {
        removeCrossContaminationWarning();
    }
}

// 주의사항에서 제조시설 경고 문구 전체 제거 + 버튼 초기화
function removeCrossContaminationWarning() {
    const cautionTextarea = document.getElementById('caution_textarea');
    if (!cautionTextarea) return;
    
    let currentValue = cautionTextarea.value;
    const lines = currentValue.split('\n');
    const filteredLines = lines.filter((line) => {
        const trimmedLine = line.trim();
        
        // 제조시설 관련 문구인지 확인
        const hasFactory = trimmedLine.includes('같은 제조시설') || 
                           trimmedLine.includes('같은 시설') || 
                           trimmedLine.includes('동일 라인') ||
                           trimmedLine.includes('동일한 제조시설');
        const hasManufacture = trimmedLine.includes('제조하고 있습니다') || 
                               trimmedLine.includes('제조합니다') || 
                               trimmedLine.includes('제조되었습니다') ||
                               trimmedLine.includes('제조됩니다') ||
                               trimmedLine.includes('제조하였습니다') ||
                               trimmedLine.includes('생산');
        const hasProduct = trimmedLine.includes('제품') || trimmedLine.includes('원료');
        
        // 제조시설 경고 문구면 제거
        if (hasFactory && hasManufacture && hasProduct) {
            return false;
        }
        return true;
    });
    
    currentValue = filteredLines.join('\n').trim();
    currentValue = currentValue.replace(/\n{3,}/g, '\n\n').trim();
    cautionTextarea.value = currentValue;
    
    // textarea 높이 자동 조절
    if (typeof autoResizeTextarea === 'function') {
        autoResizeTextarea.call(cautionTextarea);
    }
    
    // "주의사항에 추가" 버튼 상태 초기화
    resetCrossContaminationButton();
    
    // 미리보기 업데이트
    updatePreview();
}

// 제조시설 혼입 버튼 초기화
function resetCrossContaminationButton() {
    const toggleBtn = document.getElementById('toggleAllergenWarningBtn');
    if (!toggleBtn) return;
    
    // 버튼 상태를 "주의사항에 추가"로 변경
    toggleBtn.classList.remove('btn-danger');
    toggleBtn.classList.add('btn-primary');
    toggleBtn.innerHTML = '<i class="fas fa-arrow-right me-1"></i>주의사항에 추가';
    toggleBtn.title = '선택한 제조시설 혼입 경고를 주의사항에 추가합니다.';
}

// 알레르기 태그 제거
function removeAllergenTag(allergen) {
    window.autoDetectedAllergens.delete(allergen);
    window.selectedIngredientAllergens.delete(allergen);
    updateAllergenDisplay();
    
    // 알레르기 성분 변경 시 제조시설 경고 문구 전체 삭제
    removeCrossContaminationWarning();
}

// 알레르기 표시 업데이트
function updateAllergenDisplay() {
    const container = document.getElementById('detectedAllergens');
    const hiddenInput = document.getElementById('selected_ingredient_allergens');
    
    if (window.selectedIngredientAllergens.size === 0) {
        container.innerHTML = '<span class="text-muted"><i class="fas fa-info-circle me-1"></i>원재료명을 입력하거나 아래 버튼으로 추가하세요</span>';
        if (hiddenInput) hiddenInput.value = '';
    } else {
        const tags = Array.from(window.selectedIngredientAllergens).map(allergen => {
            const isAuto = window.autoDetectedAllergens.has(allergen);
            // 부드러운 색상: 자동 감지 = 연한 주황색, 수동 추가 = 연한 파란색
            const bgColor = isAuto ? 'background-color: #fff3cd; color: #856404; border: 1px solid #ffc107;' 
                                   : 'background-color: #cfe2ff; color: #084298; border: 1px solid #0d6efd;';
            const icon = isAuto ? '<i class="fas fa-robot me-1"></i>' : '<i class="fas fa-hand-pointer me-1"></i>';
            const title = isAuto ? '자동 감지됨' : '수동 추가됨';
            
            return `
                <span class="badge me-1 mb-1" style="cursor: pointer; font-size: 0.8rem; ${bgColor}" 
                      onclick="removeAllergenTag('${allergen}')" 
                      title="${title} - 클릭하여 제거">
                    ${icon}${allergen} <i class="fas fa-times ms-1"></i>
                </span>
            `;
        }).join('');
        
        container.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="me-2 mt-1"><i class="fas fa-check-circle text-success"></i></div>
                <div class="flex-grow-1">${tags}</div>
            </div>
        `;
        
        if (hiddenInput) {
            hiddenInput.value = Array.from(window.selectedIngredientAllergens).join(',');
        }
    }
    
    // 버튼 상태 업데이트
    updateAllergenButtonStates();
    
    // localStorage에 저장
    saveAllergensToStorage();
    
    // 미리보기 업데이트
    updatePreview();
}

// 알레르기 버튼 상태 업데이트
function updateAllergenButtonStates() {
    // 빠른 추가 버튼 업데이트
    document.querySelectorAll('.quick-allergen-btn').forEach(button => {
        const allergen = button.dataset.allergen;
        if (window.selectedIngredientAllergens.has(allergen)) {
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-info');
            button.style.backgroundColor = '#0dcaf0';
            button.style.borderColor = '#0dcaf0';
            button.style.color = '#000';
            button.innerHTML = `${allergen} <i class="fas fa-check ms-1"></i>`;
        } else {
            button.classList.remove('btn-info');
            button.classList.add('btn-outline-secondary');
            button.style.backgroundColor = '';
            button.style.borderColor = '';
            button.style.color = '';
            button.innerHTML = allergen;
        }
    });
    
    // 제조시설 혼입 우려물질 버튼 비활성화 (선택된 알레르기 항목)
    document.querySelectorAll('.allergen-toggle').forEach(button => {
        const allergen = button.dataset.allergen;
        if (window.selectedIngredientAllergens.has(allergen)) {
            // 비활성화 및 선택 해제
            button.disabled = true;
            button.classList.remove('active', 'btn-warning');
            button.classList.add('btn-outline-secondary', 'opacity-50');
            button.title = '원재료로 사용되어 제조시설 혼입 경고에 추가할 수 없습니다';
        } else {
            // 활성화
            button.disabled = false;
            button.classList.remove('opacity-50');
            button.title = '';
        }
    });
    
    // 전체 선택/해제 버튼 상태 업데이트
    updateToggleAllButtonState();
    
    // 혼입 경고 미리보기 업데이트
    updateCrossContaminationPreview();
}

// 원재료명에서 알레르기 물질 자동 감지 (constants.js 키워드 활용)
function detectAllergens(isAutoDetect = true) {
    const rawmtrlText = document.getElementById('rawmtrl_nm_textarea')?.value || '';
    const detectedContainer = document.getElementById('detectedAllergens');
    const detectingIndicator = document.getElementById('allergenDetectingIndicator');
    
    if (!detectedContainer) return;
    
    // 감지 중 표시 (수동 감지일 때만)
    if (!isAutoDetect && detectingIndicator) {
        detectingIndicator.style.display = 'block';
    }
    
    // 실제 감지 로직 (약간의 지연 후 실행하여 로딩 효과 표시)
    setTimeout(() => {
        // constants.js의 ALLERGEN_KEYWORDS 사용 (상세한 키워드 매핑)
        const allergenKeywords = window.allergenKeywords || window.ALLERGEN_KEYWORDS || {};
        const detectedAllergens = new Set();
        
        if (!rawmtrlText.trim()) {
            // 원재료명이 비어있으면 자동 감지 항목 제거
            window.autoDetectedAllergens.clear();
            Array.from(window.selectedIngredientAllergens).forEach(allergen => {
                if (window.autoDetectedAllergens.has(allergen)) {
                    window.selectedIngredientAllergens.delete(allergen);
                }
            });
        } else {
            // 각 알레르기 그룹의 키워드로 검색
            for (const [allergen, keywords] of Object.entries(allergenKeywords)) {
                for (const keyword of keywords) {
                    let found = false;
                    
                    // 1글자 키워드는 단어 경계 체크 (오탐 방지)
                    if (keyword.length === 1) {
                        const regex = new RegExp(`[\\s,():]${keyword}[\\s,():]|^${keyword}[\\s,():]|[\\s,():]${keyword}$|^${keyword}$`, 'gi');
                        if (regex.test(rawmtrlText)) {
                            found = true;
                        }
                    } else {
                        // 2글자 이상: 단순 포함 여부로 체크 (탈지대두에서 대두 찾기)
                        const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                        const regex = new RegExp(escapedKeyword, 'gi');
                        if (regex.test(rawmtrlText)) {
                            found = true;
                        }
                    }
                    
                    if (found) {
                        detectedAllergens.add(allergen);
                        break;
                    }
                }
            }
            
            // 자동 감지된 항목을 전역 Set에 추가
            window.autoDetectedAllergens.clear();
            detectedAllergens.forEach(allergen => {
                window.autoDetectedAllergens.add(allergen);
                window.selectedIngredientAllergens.add(allergen);
            });
        }
        
        // 로딩 인디케이터 숨김
        if (detectingIndicator) {
            detectingIndicator.style.display = 'none';
        }
        
        // UI 업데이트 (updateAllergenDisplay 내부에서 제조시설 버튼도 함께 업데이트됨)
        updateAllergenDisplay();
        
        // 미리보기 업데이트 (알레르기 물질 표시 반영)
        updatePreview();
    }, isAutoDetect ? 0 : 300); // 수동일 때는 300ms 지연으로 로딩 효과
}

// 전체 선택/해제 토글 (온/오프)
function toggleAllAllergens() {
    const toggleBtn = document.getElementById('toggleAllAllergensBtn');
    const allergenButtons = document.querySelectorAll('.allergen-toggle:not(:disabled)');
    
    // 현재 상태 확인: 모든 활성화 가능한 버튼이 선택되어 있는지
    const allSelected = Array.from(allergenButtons).every(btn => btn.classList.contains('active'));
    
    if (allSelected) {
        // 전체 해제
        allergenButtons.forEach(button => {
            button.classList.remove('active', 'btn-warning');
            button.classList.add('btn-outline-secondary');
        });
        
        // 버튼 상태 변경
        toggleBtn.classList.remove('btn-warning');
        toggleBtn.classList.add('btn-outline-secondary');
        toggleBtn.innerHTML = '<i class="fas fa-check-double me-1"></i>전체 선택';
    } else {
        // 전체 선택 (비활성화된 버튼 제외)
        allergenButtons.forEach(button => {
            button.classList.add('active', 'btn-warning');
            button.classList.remove('btn-outline-secondary');
        });
        
        // 버튼 상태 변경
        toggleBtn.classList.remove('btn-outline-secondary');
        toggleBtn.classList.add('btn-warning');
        toggleBtn.innerHTML = '<i class="fas fa-times me-1"></i>전체 해제';
    }
    
    updateCrossContaminationPreview();
    updateToggleAllButtonState();
}

// 전체 선택/해제 버튼 상태 자동 업데이트
function updateToggleAllButtonState() {
    const toggleBtn = document.getElementById('toggleAllAllergensBtn');
    const allergenButtons = document.querySelectorAll('.allergen-toggle:not(:disabled)');
    
    if (!toggleBtn || allergenButtons.length === 0) return;
    
    // 활성화 가능한 버튼이 모두 선택되어 있는지 확인
    const allSelected = Array.from(allergenButtons).every(btn => btn.classList.contains('active'));
    const anySelected = Array.from(allergenButtons).some(btn => btn.classList.contains('active'));
    
    if (allSelected && allergenButtons.length > 0) {
        // 전체 선택 상태
        toggleBtn.classList.remove('btn-outline-secondary');
        toggleBtn.classList.add('btn-warning');
        toggleBtn.innerHTML = '<i class="fas fa-times me-1"></i>전체 해제';
    } else {
        // 일부 선택 또는 미선택 상태
        toggleBtn.classList.remove('btn-warning');
        toggleBtn.classList.add('btn-outline-secondary');
        toggleBtn.innerHTML = '<i class="fas fa-check-double me-1"></i>전체 선택';
    }
}

// 제조시설 혼입 경고 문구 미리보기 업데이트
function updateCrossContaminationPreview() {
    const selectedAllergens = [];
    
    document.querySelectorAll('.allergen-toggle.active').forEach(button => {
        selectedAllergens.push(button.dataset.allergen);
    });
    
    const previewDiv = document.getElementById('crossContaminationPreview');
    const textDiv = document.getElementById('crossContaminationText');
    const hiddenInput = document.getElementById('selected_cross_contamination_allergens');
    const toggleBtn = document.getElementById('toggleAllergenWarningBtn');
    
    // 버튼 상태 확인: "주의사항에서 해제" 버튼이 활성화되어 있는지 (이미 추가된 상태)
    const isAlreadyAdded = toggleBtn && toggleBtn.classList.contains('btn-danger');
    
    if (selectedAllergens.length > 0 && !isAlreadyAdded) {
        // 선택된 항목이 있고, 아직 추가되지 않은 상태(추가 버튼 활성화)일 때만 미리보기 표시
        
        // 중복 검증
        const detectedAllergens = getDetectedAllergens();
        const duplicates = selectedAllergens.filter(allergen => 
            detectedAllergens.includes(allergen)
        );
        
        let warningText = `본 제품은 ${selectedAllergens.join(', ')}를 사용한 제품과 같은 제조시설(또는 동일 라인)에서 제조되었습니다.`;
        
        // 중복이 있으면 경고 표시
        if (duplicates.length > 0) {
            warningText += `\n⚠️ 경고: ${duplicates.join(', ')}은(는) 원재료에 이미 사용된 알레르기 물질입니다.`;
            textDiv.innerHTML = warningText.replace(/\n/g, '<br>');
            textDiv.style.color = '#d32f2f';
        } else {
            textDiv.textContent = warningText;
            textDiv.style.color = '#333';
        }
        
        previewDiv.style.display = 'block';
        hiddenInput.value = selectedAllergens.join(',');
    } else {
        // 선택된 항목이 없거나, 이미 추가된 상태(해제 버튼 활성화)이면 미리보기 숨김
        previewDiv.style.display = 'none';
        hiddenInput.value = selectedAllergens.join(','); // hidden input은 계속 업데이트
    }
}

// 주의사항에 추가/해제 토글 (온/오프)
function toggleAllergenWarning() {
    const toggleBtn = document.getElementById('toggleAllergenWarningBtn');
    const cautionTextarea = document.getElementById('caution_textarea');
    
    if (!cautionTextarea) {
        return;
    }
    
    // 현재 버튼 상태 확인 (추가 모드 vs 해제 모드)
    const isRemoveMode = toggleBtn.classList.contains('btn-danger');
    
    if (isRemoveMode) {
        // 해제 모드: 기존 혼입 경고 문구만 제거
        let currentValue = cautionTextarea.value;
        
        const lines = currentValue.split('\n');
        const filteredLines = lines.filter((line) => {
            const trimmedLine = line.trim();
            
            const hasFactory = trimmedLine.includes('같은 제조시설') || 
                               trimmedLine.includes('같은 시설') || 
                               trimmedLine.includes('동일 라인') ||
                               trimmedLine.includes('동일한 제조시설');
            const hasManufacture = trimmedLine.includes('제조하고 있습니다') || 
                                   trimmedLine.includes('제조합니다') || 
                                   trimmedLine.includes('제조되었습니다') ||
                                   trimmedLine.includes('제조됩니다') ||
                                   trimmedLine.includes('제조하였습니다') ||
                                   trimmedLine.includes('생산');
            const hasProduct = trimmedLine.includes('제품') || trimmedLine.includes('원료');
            
            if (hasFactory && hasManufacture && hasProduct) {
                return false;
            }
            return true;
        });
        
        currentValue = filteredLines.join('\n').trim();
        currentValue = currentValue.replace(/\n{3,}/g, '\n\n').trim();
        
        cautionTextarea.value = currentValue;
        
        // textarea 높이 자동 조절
        if (cautionTextarea.classList.contains('auto-resize')) {
            autoResizeHeight(cautionTextarea);
            setTimeout(() => autoResizeHeight(cautionTextarea), 10);
        }
        
        updatePreview();
        
        // 버튼 상태 변경: 추가 모드로
        toggleBtn.classList.remove('btn-danger');
        toggleBtn.classList.add('btn-outline-primary');
        toggleBtn.innerHTML = '<i class="fas fa-arrow-right me-1"></i>주의사항에 추가';
        
        // 혼입 경고 문구 미리보기 다시 표시
        updateCrossContaminationPreview();
        
    } else {
        // 추가 모드: 선택된 알레르기 확인
        const selectedAllergens = [];
        document.querySelectorAll('.allergen-toggle.active').forEach(button => {
            selectedAllergens.push(button.dataset.allergen);
        });
        
        if (selectedAllergens.length === 0) {
            alert('제조시설 혼입 우려 물질을 먼저 선택해주세요.');
            return;
        }
        
        // 중복 검증
        const detectedAllergens = getDetectedAllergens();
        const duplicates = selectedAllergens.filter(allergen => 
            detectedAllergens.includes(allergen)
        );
        
        if (duplicates.length > 0) {
            const confirmMsg = `⚠️ 경고: ${duplicates.join(', ')}은(는) 원재료에 이미 사용된 알레르기 물질입니다.\n\n원재료 사용 알레르기는 "원재료명"에만 표시되어야 하며, 제조시설 혼입 경고에는 포함할 수 없습니다.\n\n계속 진행하시겠습니까?`;
            
            if (!confirm(confirmMsg)) {
                return;
            }
        }
        
        // 기존 주의사항에서 유사한 혼입 경고 문구 먼저 제거
        let currentValue = cautionTextarea.value;
        
        const lines = currentValue.split('\n');
        const filteredLines = lines.filter((line) => {
            const trimmedLine = line.trim();
            
            const hasFactory = trimmedLine.includes('같은 제조시설') || 
                               trimmedLine.includes('같은 시설') || 
                               trimmedLine.includes('동일 라인') ||
                               trimmedLine.includes('동일한 제조시설');
            const hasManufacture = trimmedLine.includes('제조하고 있습니다') || 
                                   trimmedLine.includes('제조합니다') || 
                                   trimmedLine.includes('제조되었습니다') ||
                                   trimmedLine.includes('제조됩니다') ||
                                   trimmedLine.includes('제조하였습니다') ||
                                   trimmedLine.includes('생산');
            const hasProduct = trimmedLine.includes('제품') || trimmedLine.includes('원료');
            
            if (hasFactory && hasManufacture && hasProduct) {
                return false;
            }
            return true;
        });
        
        currentValue = filteredLines.join('\n').trim();
        currentValue = currentValue.replace(/\n{3,}/g, '\n\n').trim();
        
        const warningText = `본 제품은 ${selectedAllergens.join(', ')}를 사용한 제품과 같은 제조시설(또는 동일 라인)에서 제조되었습니다.`;
        
        if (currentValue) {
            cautionTextarea.value = currentValue + '\n' + warningText;
        } else {
            cautionTextarea.value = warningText;
        }
        
        // textarea 높이 자동 조절
        if (cautionTextarea.classList.contains('auto-resize')) {
            autoResizeHeight(cautionTextarea);
            setTimeout(() => autoResizeHeight(cautionTextarea), 10);
        }
        
        // 주의사항 체크박스 자동 체크
        const cautionCheckbox = document.getElementById('chk_caution');
        if (cautionCheckbox) {
            cautionCheckbox.checked = true;
        }
        
        updatePreview();
        
        // 버튼 상태 변경: 해제 모드로
        toggleBtn.classList.remove('btn-outline-primary');
        toggleBtn.classList.add('btn-danger');
        toggleBtn.innerHTML = '<i class="fas fa-arrow-left me-1"></i>주의사항에서 해제';
        
        // 혼입 경고 문구 미리보기 숨기기
        const previewDiv = document.getElementById('crossContaminationPreview');
        if (previewDiv) {
            previewDiv.style.display = 'none';
        }
    }
}

// 감지된 알레르기 물질 가져오기 (원재료 사용)

// 선택된 제조시설 혼입 알레르기 물질 가져오기
function getSelectedCrossContaminationAllergens() {
    const selectedAllergens = [];
    document.querySelectorAll('.allergen-toggle.active').forEach(button => {
        selectedAllergens.push(button.dataset.allergen);
    });
    return selectedAllergens;
}

// 알레르기 중복 검증 (원재료 사용 vs 제조시설 혼입)
function validateAllergenSeparation() {
    const detectedAllergens = getDetectedAllergens();
    const selectedAllergens = getSelectedCrossContaminationAllergens();
    
    // 중복된 알레르기 물질 찾기
    const duplicates = selectedAllergens.filter(allergen => 
        detectedAllergens.includes(allergen)
    );
    
    return {
        isValid: duplicates.length === 0,
        duplicates: duplicates,
        detected: detectedAllergens,
        selected: selectedAllergens
    };
}

// 분리배출마크 설정 함수 (label_preview.js 방식)
function setRecyclingMark(markValue) {
    const recyclingMarkGroups = window.recyclingMarkGroupsDetailed || [];
    const recyclingMarkMap = {};
    recyclingMarkGroups.forEach(group => {
        group.options.forEach(opt => {
            recyclingMarkMap[opt.value] = opt;
        });
    });
    
    const markObj = recyclingMarkMap[markValue];
    const previewContent = document.getElementById('previewContent');
    if (!previewContent || !markObj) {
        console.error('마크 객체 또는 미리보기 컨테이너를 찾을 수 없습니다:', markValue);
        return;
    }

    // 기존 컨테이너 제거
    let container = document.getElementById('recyclingMarkContainer');
    if (container) container.remove();

    container = document.createElement('div');
    container.id = 'recyclingMarkContainer';
    container.className = 'recycling-mark-container';
    
    // 컨테이너 스타일
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
    `;
    
    // 이미지와 텍스트 영역
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
    
    // previewContent 자체에 직접 추가 (relative positioning context)
    previewContent.style.position = 'relative';
    previewContent.appendChild(container);
    
    const img = container.querySelector('#recyclingMarkImage');
    
    // 이미지 설정
    if (markObj.img) {
        img.src = markObj.img;
        img.alt = markObj.label;
        img.style.display = 'block';
        
        img.onerror = function() {
            this.style.display = 'none';
            console.warn('분리배출 마크 이미지 로딩 실패:', this.src);
            const textContainer = container.querySelector('#recyclingMarkTextContainer');
            if (textContainer && !textContainer.querySelector('.fallback-text')) {
                const fallbackText = document.createElement('div');
                fallbackText.className = 'fallback-text';
                fallbackText.textContent = markObj.label;
                fallbackText.style.cssText = 'font-weight: bold; color: #333; padding: 4px;';
                textContainer.appendChild(fallbackText);
            }
        };
    } else {
        img.style.display = 'none';
    }
    
    // 위치 계산 - previewContent 기준으로 상대 위치 지정
    // 제품명 행 찾기
    const thElements = previewContent.querySelectorAll('th');
    let productNameRow = null;
    thElements.forEach(th => {
        if (th.textContent.trim() === '제품명') {
            productNameRow = th.parentElement;
        }
    });
    
    if (productNameRow) {
        // 제품명 행과 같은 높이, 테이블 우측에 배치
        const previewTable = previewContent.querySelector('.preview-table');
        const tableRect = previewTable.getBoundingClientRect();
        const rowRect = productNameRow.getBoundingClientRect();
        const contentRect = previewContent.getBoundingClientRect();
        
        // previewContent 내부의 상대 위치 계산
        const topPosition = rowRect.top - contentRect.top;
        const rightPosition = contentRect.right - tableRect.right + 5;
        
        container.style.top = `${topPosition}px`;
        container.style.right = `${rightPosition}px`;
        container.style.left = 'auto';
        container.style.bottom = 'auto';
    } else {
        // 제품명 행을 찾지 못할 경우 테이블 우측 상단
        const previewTable = previewContent.querySelector('.preview-table');
        if (previewTable) {
            const tableRect = previewTable.getBoundingClientRect();
            const contentRect = previewContent.getBoundingClientRect();
            
            const topPosition = tableRect.top - contentRect.top;
            const rightPosition = contentRect.right - tableRect.right + 5;
            
            container.style.top = `${topPosition}px`;
            container.style.right = `${rightPosition}px`;
        } else {
            // 기본 위치
            container.style.top = '20px';
            container.style.right = '20px';
        }
        container.style.left = 'auto';
        container.style.bottom = 'auto';
    }
    
    // 드래그 기능 (previewContent 기준)
    container.onmousedown = function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const startX = e.clientX;
        const startY = e.clientY;
        const containerRect = container.getBoundingClientRect();
        const startLeft = containerRect.left;
        const startTop = containerRect.top;
        
        function onMouseMove(e) {
            e.preventDefault();
            const contentRect = previewContent.getBoundingClientRect();
            
            // 마우스 이동 거리 계산
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            // 새로운 위치 계산 (previewContent 기준)
            const newLeft = startLeft + deltaX - contentRect.left;
            const newTop = startTop + deltaY - contentRect.top;
            
            container.style.left = `${newLeft}px`;
            container.style.top = `${newTop}px`;
            container.style.right = 'auto';
            container.style.bottom = 'auto';
        }
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', function mouseUpHandler(e) {
            e.preventDefault();
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', mouseUpHandler);
        }, { once: true });
    };
    
    container.ondragstart = () => false;
    
    // 복합재질 텍스트 추가
    updateCompositeTextInContainer();
}

// 분리배출마크 제거 함수
function removeRecyclingMark() {
    const container = document.getElementById('recyclingMarkContainer');
    if (container) {
        container.remove();
    }
    if (window.recyclingMarkData) {
        window.recyclingMarkData = null;
    }
}

// 복합재질 텍스트를 컨테이너에 업데이트
function updateCompositeTextInContainer() {
    const container = document.getElementById('recyclingMarkContainer');
    if (!container) return;
    
    const textContainer = container.querySelector('#recyclingMarkTextContainer');
    if (!textContainer) return;
    
    const compositeText = document.getElementById('additionalRecyclingText')?.value || '';
    
    // 기존 텍스트 라인 제거 (fallback-text 제외)
    const existingLines = textContainer.querySelectorAll('.recycling-text-line');
    existingLines.forEach(line => line.remove());
    
    // 새 텍스트 라인 추가
    if (compositeText) {
        const lines = compositeText.split('/').filter(line => line.trim());
        lines.forEach((line, index) => {
            const textLine = document.createElement('div');
            textLine.className = 'recycling-text-line';
            textLine.textContent = line.trim();
            textLine.style.cssText = `
                font-size: 6pt !important;
                line-height: 1.2 !important;
                color: black !important;
                padding: 1px 0 !important;
                margin: 0 !important;
                word-break: break-word !important;
            `;
            textContainer.appendChild(textLine);
        });
    }
}

// 복합재질 텍스트 미리보기 업데이트
function updateCompositeTextPreview() {
    if (window.recyclingMarkData) {
        window.recyclingMarkData.compositeText = document.getElementById('additionalRecyclingText')?.value || '';
        updateCompositeTextInContainer();
    }
}

// 면적 계산 및 높이 자동 계산 함수 (label_preview.html 방식 재활용)
function calculateDimensionsAndArea() {
    const previewContent = document.getElementById('previewContent');
    const widthInput = document.getElementById('widthInput');
    const heightInput = document.getElementById('heightInput');
    const areaDisplay = document.getElementById('areaDisplay');
    
    if (!previewContent || !widthInput || !heightInput || !areaDisplay) return;
    
    const widthCm = parseFloat(widthInput.value) || 10;
    const CM_TO_PX = 37.795275591; // 1cm = 37.795275591px (96 DPI 기준)
    
    // previewContent의 실제 높이 측정
    requestAnimationFrame(() => {
        if (previewContent.scrollHeight > 0) {
            const contentHeightPx = previewContent.scrollHeight;
            const heightCm = (contentHeightPx / CM_TO_PX).toFixed(1);
            heightInput.value = `${heightCm} cm`;
            
            // 면적 계산 및 업데이트
            const area = (widthCm * parseFloat(heightCm)).toFixed(1);
            areaDisplay.value = area;
        }
    });
}

// 전체 추가 기능 (주의사항, 기타표시사항)
function addAllQuickTexts(fieldName) {
    const textarea = document.querySelector(`textarea[name="${fieldName}"]`);
    if (!textarea) return;
    
    // 주의사항에 대해 일괄 추가할 때는 원재료 사용 알레르기 확인
    let detectedAllergens = [];
    if (fieldName === 'caution') {
        detectedAllergens = getDetectedAllergens();
    }
    
    const buttons = document.querySelectorAll(`.quick-text-toggle[data-field="${fieldName}"]`);
    const textsToAdd = [];
    let skippedCount = 0;
    
    buttons.forEach(button => {
        const text = button.getAttribute('data-text');
        const isActive = button.classList.contains('active');
        
        if (!isActive) {
            // 제조시설 혼입 알레르기 버튼인 경우 중복 확인
            if (button.classList.contains('allergen-toggle')) {
                const allergen = button.getAttribute('data-allergen');
                if (detectedAllergens.includes(allergen)) {
                    // 원재료에서 이미 사용된 알레르기는 건너뜀
                    skippedCount++;
                    return;
                }
            }
            
            // 버튼 활성화
            button.classList.add('active');
            button.classList.add('btn-primary');
            button.classList.remove('btn-outline-secondary');
            button.classList.remove('btn-outline-danger');
            button.classList.remove('btn-outline-info');
            button.classList.remove('btn-outline-primary');
            
            textsToAdd.push(text);
        }
    });
    
    if (textsToAdd.length > 0) {
        const currentValue = textarea.value.trim();
        if (currentValue) {
            textarea.value = currentValue + '\n' + textsToAdd.join('\n');
        } else {
            textarea.value = textsToAdd.join('\n');
        }
        
        // textarea 높이 자동 조절
        if (textarea.classList.contains('auto-resize')) {
            autoResizeHeight(textarea);
            setTimeout(() => autoResizeHeight(textarea), 10);
        }
        
        // 해당 필드의 체크박스 자동 체크
        const checkboxId = fieldName === 'caution' ? 'chk_caution' : 'chk_other_info';
        const checkbox = document.getElementById(checkboxId);
        if (checkbox) {
            checkbox.checked = true;
        }
        
        updatePreview();
    } else {
        alert('이미 모든 문구가 추가되어 있습니다.');
    }
}

// 일괄 해제 기능 (주의사항, 기타표시사항)
function clearAllQuickTexts(fieldName) {
    const textarea = document.querySelector(`textarea[name="${fieldName}"]`);
    if (!textarea) return;
    
    const buttons = document.querySelectorAll(`.quick-text-toggle[data-field="${fieldName}"]`);
    let removedCount = 0;
    
    buttons.forEach(button => {
        const isActive = button.classList.contains('active');
        
        if (isActive) {
            // 버튼 비활성화 (원래 색상으로 복원)
            button.classList.remove('active');
            button.classList.remove('btn-primary');
            
            // data 속성에 저장된 원래 색상 클래스 복원
            const originalColor = button.dataset.originalColor || 'btn-outline-secondary';
            if (!button.classList.contains(originalColor)) {
                button.classList.add(originalColor);
            }
            
            removedCount++;
        }
    });
    
    if (removedCount > 0) {
        // textarea 내용 완전히 초기화
        textarea.value = '';
        
        // textarea 높이 자동 조절
        if (textarea.classList.contains('auto-resize')) {
            autoResizeHeight(textarea);
            setTimeout(() => autoResizeHeight(textarea), 10);
        }
        
        updatePreview();
    } else {
        alert('해제할 문구가 없습니다.');
    }
}

// 빠른 문구 토글 기능 (온/오프 방식)
function toggleQuickText(button) {
    const fieldName = button.getAttribute('data-field');
    const text = button.getAttribute('data-text');
    const textarea = document.querySelector(`textarea[name="${fieldName}"]`);
    
    if (!textarea) return;
    
    // 버튼이 활성화 상태인지 확인
    const isActive = button.classList.contains('active');
    
    if (isActive) {
        // 비활성화: 해당 문구를 textarea에서 제거
        button.classList.remove('active');
        button.classList.remove('btn-primary');
        
        // 원래 색상 클래스 복원
        const originalColor = button.dataset.originalColor || 'btn-outline-secondary';
        if (!button.classList.contains(originalColor)) {
            button.classList.add(originalColor);
        }
        
        const lines = textarea.value.split('\n');
        const newLines = lines.filter(line => line.trim() !== text.trim());
        textarea.value = newLines.join('\n').trim();
    } else {
        // 활성화: 해당 문구를 textarea에 추가
        button.classList.add('active');
        button.classList.add('btn-primary');
        
        // 원래 outline 색상 클래스 제거 (btn-primary와 충돌 방지)
        button.classList.remove('btn-outline-secondary', 'btn-outline-danger', 'btn-outline-info', 'btn-outline-success', 'btn-outline-primary');
        
        const currentValue = textarea.value.trim();
        if (currentValue) {
            textarea.value = currentValue + '\n' + text;
        } else {
            textarea.value = text;
        }
    }
    
    // textarea 높이 자동 조절 (auto-resize 트리거)
    if (textarea.classList.contains('auto-resize')) {
        // 즉시 높이 조절
        autoResizeHeight(textarea);
        // 추가 보장: setTimeout으로 한 번 더 실행
        setTimeout(() => autoResizeHeight(textarea), 10);
    }
    
    // 입력 이벤트 트리거하여 미리보기 업데이트
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

// ==================== 드래그 스크롤 기능 ====================
/**
 * 미리보기 영역에 드래그 스크롤 기능 추가
 * 마우스로 클릭하여 상하좌우로 드래그하면 스크롤 이동
 */
function initializeDragScroll() {
    const previewArea = document.querySelector('.preview-content-area');
    if (!previewArea) return;

    let isDown = false;
    let startX;
    let startY;
    let scrollLeft;
    let scrollTop;

    previewArea.addEventListener('mousedown', (e) => {
        // 텍스트 선택이 필요한 경우를 제외하고 드래그 시작
        // 링크나 버튼 클릭 시에는 드래그 방지
        if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') {
            return;
        }

        isDown = true;
        previewArea.classList.add('dragging');
        
        startX = e.pageX - previewArea.offsetLeft;
        startY = e.pageY - previewArea.offsetTop;
        scrollLeft = previewArea.scrollLeft;
        scrollTop = previewArea.scrollTop;
    });

    previewArea.addEventListener('mouseleave', () => {
        isDown = false;
        previewArea.classList.remove('dragging');
    });

    previewArea.addEventListener('mouseup', () => {
        isDown = false;
        previewArea.classList.remove('dragging');
    });

    previewArea.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        
        e.preventDefault();
        
        const x = e.pageX - previewArea.offsetLeft;
        const y = e.pageY - previewArea.offsetTop;
        
        // 이동 거리 계산 (속도 조절: 1.5배)
        const walkX = (x - startX) * 1.5;
        const walkY = (y - startY) * 1.5;
        
        // 스크롤 위치 업데이트
        previewArea.scrollLeft = scrollLeft - walkX;
        previewArea.scrollTop = scrollTop - walkY;
    });
}

// ==================== 패널 리사이저 기능 ====================
/**
 * 왼쪽/오른쪽 패널 사이의 리사이저 드래그 기능
 * 최소 30%씩 확보하면서 크기 조절 가능
 */
function initializePanelResizer() {
    const resizer = document.querySelector('.panel-resizer');
    const leftPanel = document.querySelector('.demo-left-panel');
    const rightPanel = document.querySelector('.demo-right-panel');
    const container = document.querySelector('.demo-panels');
    
    if (!resizer || !leftPanel || !rightPanel || !container) return;

    let isResizing = false;
    let startX;
    let startLeftWidth;
    let startRightWidth;
    let containerWidth;

    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        resizer.classList.add('resizing');
        
        startX = e.clientX;
        containerWidth = container.offsetWidth;
        startLeftWidth = leftPanel.offsetWidth;
        startRightWidth = rightPanel.offsetWidth;
        
        // 드래그 중 텍스트 선택 방지
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'col-resize';
        
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        const deltaX = e.clientX - startX;
        const newLeftWidth = startLeftWidth + deltaX;
        const newRightWidth = startRightWidth - deltaX;
        
        // 최소 30% 확보 체크
        const minWidth = containerWidth * 0.3;
        
        if (newLeftWidth >= minWidth && newRightWidth >= minWidth) {
            const leftPercent = (newLeftWidth / containerWidth) * 100;
            const rightPercent = (newRightWidth / containerWidth) * 100;
            
            leftPanel.style.flex = `0 0 ${leftPercent}%`;
            leftPanel.style.maxWidth = `${leftPercent}%`;
            
            rightPanel.style.flex = `0 0 ${rightPercent}%`;
            rightPanel.style.maxWidth = `${rightPercent}%`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove('resizing');
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        }
    });
}

// ==================== 알레르기 저장/로딩 ====================
// localStorage에 알레르기 정보 저장
function saveAllergensToStorage() {
    try {
        const timestamp = new Date().toISOString();
        
        // Set이 제대로 초기화되어 있는지 확인
        if (!window.selectedIngredientAllergens || !(window.selectedIngredientAllergens instanceof Set)) {
            window.selectedIngredientAllergens = new Set();
        }
        if (!window.selectedCrossContaminationAllergens || !(window.selectedCrossContaminationAllergens instanceof Set)) {
            window.selectedCrossContaminationAllergens = new Set();
        }
        
        // localStorage 저장 (비로그인/로그인 모두)
        localStorage.setItem('labeldata_allergens', JSON.stringify([...window.selectedIngredientAllergens]));
        localStorage.setItem('labeldata_crossContaminationAllergens', JSON.stringify([...window.selectedCrossContaminationAllergens]));
        localStorage.setItem('labeldata_timestamp', timestamp);
    } catch (e) {
        // 알레르기 정보 저장 실패
    }
}

// localStorage에서 알레르기 정보 로드
function loadAllergensFromStorage() {
    try {
        // 서버에서 로드된 라벨 데이터가 있으면 localStorage 로드하지 않음
        if (window.hasServerLabelData) {
            return;
        }
        
        // Set 초기화 확인
        if (!window.selectedIngredientAllergens || !(window.selectedIngredientAllergens instanceof Set)) {
            window.selectedIngredientAllergens = new Set();
        }
        if (!window.selectedCrossContaminationAllergens || !(window.selectedCrossContaminationAllergens instanceof Set)) {
            window.selectedCrossContaminationAllergens = new Set();
        }
        
        const timestamp = localStorage.getItem('labeldata_timestamp');
        
        if (timestamp) {
            const savedTime = new Date(timestamp);
            const now = new Date();
            const hoursDiff = (now - savedTime) / (1000 * 60 * 60);
            
            if (hoursDiff < 24) {
                // 24시간 이내 데이터 로드
                const allergens = JSON.parse(localStorage.getItem('labeldata_allergens') || '[]');
                const crossAllergens = JSON.parse(localStorage.getItem('labeldata_crossContaminationAllergens') || '[]');
                
                allergens.forEach(a => window.selectedIngredientAllergens.add(a));
                crossAllergens.forEach(a => window.selectedCrossContaminationAllergens.add(a));
                
                updateAllergenDisplay();
            } else {
                // 만료된 데이터 삭제
                localStorage.removeItem('labeldata_allergens');
                localStorage.removeItem('labeldata_crossContaminationAllergens');
                localStorage.removeItem('labeldata_timestamp');
            }
        }
    } catch (e) {
        console.error('localStorage 알레르기 정보 로드 실패:', e);
        // 에러 발생 시 Set 초기화
        window.selectedIngredientAllergens = new Set();
        window.selectedCrossContaminationAllergens = new Set();
    }
}

// 알레르기 성분 검증 함수 (간편모드용 - label_preview.js와 동일한 로직)
function checkAllergenDuplication() {
    // constants.js에서 로드된 알레르기 키워드 사용
    const allergenKeywords = window.allergenKeywords || {};
    
    // 원재료명과 알레르기 표시사항 가져오기
    let ingredients = '';
    let declaredAllergens = [];
    
    // 원재료명 가져오기
    const rawmtrlTextarea = document.getElementById('rawmtrl_nm_textarea');
    if (rawmtrlTextarea) {
        ingredients = rawmtrlTextarea.value || '';
    }
    
    // 선언된 알레르기 성분 (간편모드는 window.selectedIngredientAllergens 사용)
    if (window.selectedIngredientAllergens && window.selectedIngredientAllergens.size > 0) {
        declaredAllergens = Array.from(window.selectedIngredientAllergens);
    }
    
    if (!ingredients || !ingredients.trim()) {
        return [];
    }
    
    // 원재료명에서 발견된 알레르기 성분들
    const foundAllergens = [];
    const cleanIngredients = ingredients;
    
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
            
            if (found) {
                if (!foundAllergens.includes(allergen)) {
                    foundAllergens.push(allergen);
                }
                break;
            }
        }
    }
    
    // 주의사항 가져오기
    let cautionsText = '';
    const cautionTextarea = document.getElementById('caution_textarea');
    if (cautionTextarea) {
        cautionsText = cautionTextarea.value || '';
    }
    
    const duplicatedAllergens = [];
    
    if (declaredAllergens.length > 0 && cautionsText) {
        
        for (const declaredAllergen of declaredAllergens) {
            const matchedKeywords = allergenKeywords[declaredAllergen] || [declaredAllergen];
            
            const foundInCautions = matchedKeywords.filter(keyword => {
                if (keyword.length === 1) {
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
            if (foundAllergen.toLowerCase() === declared.toLowerCase()) {
                return true;
            }
            if (declared.toLowerCase().includes(foundAllergen.toLowerCase()) ||
                foundAllergen.toLowerCase().includes(declared.toLowerCase())) {
                return true;
            }
            return false;
        });
        
        return !hasMatch;
    });
    
    // 오류 메시지 생성
    const errors = [];
    
    if (missingAllergens.length > 0) {
        errors.push(...missingAllergens.map(allergen => 
            `원재료명에 '${allergen}'이(가) 포함되어 있으나 [알레르기 성분] 표시에 누락되었습니다.`
        ));
    }
    
    if (duplicatedAllergens.length > 0) {
        errors.push(...duplicatedAllergens.map(item => 
            `알레르기 성분 '${item.allergen}'이(가) 주의사항에 중복으로 표시되어 있습니다. 원재료명에 음영표시되어 있으므로 주의사항에서 삭제하거나 표현을 수정하세요. (발견된 키워드: ${item.foundKeywords.join(', ')})`
        ));
    }
    
    return errors;
}

// 페이지 로드 시 드래그 스크롤 초기화
document.addEventListener('DOMContentLoaded', () => {
    initializeDragScroll();
    initializePanelResizer();
    loadAllergensFromStorage();
});
