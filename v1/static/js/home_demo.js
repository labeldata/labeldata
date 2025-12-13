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
        country_of_origin: '대한민국 (오렌지: 미국산)',
        storage_method: '냉장보관(0~10℃)',
        rawmtrl_nm_display: '오렌지농축액(오렌지:미국산) 10%, 정제수, 설탕, 구연산, 비타민C',
        manufacturer: '(주)프레시푸드',
        distributor: '(주)음료유통',
        packaging_material: 'PET',
        caution: '부정·불량식품 신고는 국번없이 1399\n개봉 후 냉장보관하시고 빠른 시일 내에 드시기 바랍니다.',
        chk_prdlst_nm: true,
        chk_ingredient_info: true,
        chk_prdlst_dcnm: true,
        chk_prdlst_report_no: true,
        chk_content_weight: true,
        chk_country_of_origin: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_manufacturer: true,
        chk_distributor: true,
        chk_packaging_material: true,
        chk_caution: true
    },
    snack: {
        prdlst_nm: '허니버터칩',
        prdlst_dcnm: '과자',
        prdlst_report_no: '20240102-2345678',
        content_weight: '60g',
        country_of_origin: '대한민국',
        storage_method: '직사광선을 피하고 서늘한 곳에 보관',
        rawmtrl_nm_display: '감자(국산), 식물성유지, 허니버터시즈닝[설탕, 버터시즈닝분말, 꿀분말 등]',
        manufacturer: '(주)스낵제과',
        packaging_material: '플라스틱(PE)',
        caution: '부정·불량식품 신고는 국번없이 1399',
        other_info: '튀김유: 팜유 100%',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_prdlst_report_no: true,
        chk_content_weight: true,
        chk_country_of_origin: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_manufacturer: true,
        chk_packaging_material: true,
        chk_caution: true,
        chk_other_info: true
    },
    noodle: {
        prdlst_nm: '신라면',
        prdlst_dcnm: '유탕면류',
        content_weight: '120g',
        country_of_origin: '대한민국',
        storage_method: '직사광선을 피하고 통풍이 잘되는 곳에 보관',
        rawmtrl_nm_display: '밀가루(밀:미국산, 호주산), 팜유, 감자전분, 변성전분, 양념분말, 건조채소',
        manufacturer: '(주)농심',
        packaging_material: '플라스틱(PP), 종이',
        caution: '부정·불량식품 신고는 국번없이 1399\n뜨거운 물에 주의하세요',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_content_weight: true,
        chk_country_of_origin: true,
        chk_storage_method: true,
        chk_rawmtrl_nm_display: true,
        chk_manufacturer: true,
        chk_packaging_material: true,
        chk_caution: true
    },
    sauce: {
        prdlst_nm: '참깨드레싱',
        prdlst_dcnm: '드레싱',
        content_weight: '300ml',
        country_of_origin: '대한민국',
        storage_method: '냉장보관(0~10℃), 개봉 후 냉장보관',
        rawmtrl_nm_display: '식용유지(대두유), 참깨 8%, 간장, 설탕, 식초, 마늘',
        manufacturer: '(주)소스앤소스',
        subdivider: '(주)식품소분',
        packaging_material: '유리',
        caution: '부정·불량식품 신고는 국번없이 1399\n개봉 후 반드시 냉장보관하세요',
        chk_prdlst_nm: true,
        chk_prdlst_dcnm: true,
        chk_content_weight: true,
        chk_country_of_origin: true,
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
    const data = sampleData[type];
    if (!data) return;

    const form = document.getElementById('demoForm');
    if (!form) return;

    // 폼 초기화
    form.reset();

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
    showToast(`${getSampleName(type)} 샘플 데이터가 로딩되었습니다.`);
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
        showToast('모든 데이터가 초기화되었습니다.');
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
        { key: 'packaging_material', label: '용기·포장재질', check: 'chk_packaging_material' },
        { key: 'manufacturer', label: '제조원 소재지', check: 'chk_manufacturer' },
        { key: 'distributor', label: '유통전문판매원', check: 'chk_distributor' },
        { key: 'subdivider', label: '소분원', check: 'chk_subdivider' },
        { key: 'importer', label: '수입원', check: 'chk_importer' },
        { key: 'expiry_date', label: '소비기한', check: 'chk_expiry_date' },
        { key: 'rawmtrl_nm_display', label: '원재료명', check: 'chk_rawmtrl_nm_display', multiline: true },
        { key: 'caution', label: '주의사항', check: 'chk_caution', separator: true },
        { key: 'other_info', label: '기타표시사항', check: 'chk_other_info', separator: true }
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

function generateTableRow(label, value, multiline = false, separator = false) {
    if (!value || !value.trim()) return '';

    let valueHtml;
    
    if (separator) {
        // 주의사항과 기타표시사항: 줄바꿈을 | 로 변환
        const items = value.split('\n').filter(item => item.trim());
        valueHtml = items.join(' | ');
    } else if (multiline && label === '원재료명') {
        // 원재료명: 알레르기 물질 정보 추가
        valueHtml = value.replace(/\n/g, '<br>');
        
        // 감지된 알레르기 물질 가져오기 (constants.js의 키워드 활용)
        const detectedAllergens = getDetectedAllergens();
        
        if (detectedAllergens.length > 0) {
            const allergenText = detectedAllergens.join(', ');
            // 미리보기 팝업과 동일한 형식: "xx, xx 함유" (검은색 배경에 하얀색 글씨)
            valueHtml += `<br><span style="background-color: #000; color: #fff; font-weight: 600; padding: 2px 6px; border-radius: 3px; display: inline-block; margin-top: 4px;">${allergenText} 함유</span>`;
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

// ==================== 토스트 알림 ====================
function showToast(message) {
    const toastHtml = `
        <div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;">
            <div class="toast show" role="alert">
                <div class="toast-header">
                    <i class="fas fa-info-circle me-2 text-primary"></i>
                    <strong class="me-auto">알림</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        </div>
    `;
    
    const toastElement = document.createElement('div');
    toastElement.innerHTML = toastHtml;
    document.body.appendChild(toastElement);
    
    setTimeout(() => {
        toastElement.remove();
    }, 3000);
}

// ==================== 품목보고번호 검증 기능 ====================
function verifyReportNo() {
    const btn = document.getElementById('verifyReportNoBtn');
    if (!btn) return;
    
    // 상태 복구: 완료된 상태에서 클릭 시 초기화
    const completedStates = ['사용가능', '형식오류', '규칙오류', '미등록', '검증실패', '오류발생', '정보가져옴'];
    const isCompleted = completedStates.some(state => btn.innerHTML.includes(state));
    
    if (isCompleted) {
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>검증 중...';
    btn.className = 'btn btn-secondary btn-sm';
    
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
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
    .then(res => res.json())
    .then(data => {
        // 성공 상태 처리
        if (data.verified && data.status === 'available') {
            btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>사용가능';
            btn.className = 'btn btn-success btn-sm';
            btn.title = '등록된 품목보고번호로 사용 가능합니다';
            return;
        }
        
        // 등록된 제품 정보가 있는 경우 - 사용자에게 선택권 제공
        if (data.status === 'completed' && data.product_data) {
            // 사용자 확인 대화상자
            const userConfirmed = confirm('이미 신고된 제품이 있습니다.\n식품안전나라에 신고된 제품의 정보를 불러오시겠습니까?');
            
            if (!userConfirmed) {
                // 취소 선택 시 - 검증 버튼 초기화
                btn.innerHTML = '번호검증';
                btn.className = 'btn btn-outline-primary btn-sm';
                btn.title = 'API 중복 검사 및 번호 규칙 검증';
                return;
            }
            
            // 확인 선택 시 - 정보 자동 입력
            applyProductData(btn, data.product_data);
            return;
        }
        
        // 실패 상태별 처리
        handleVerificationError(btn, data);
    })
    .catch(err => {
        handleVerificationNetworkError(btn, err);
    })
    .finally(() => {
        btn.disabled = false;
    });
}

// 제품 정보 자동 입력 함수
function applyProductData(btn, productData) {
    btn.innerHTML = '<i class="fas fa-download me-1"></i>정보가져옴';
    btn.className = 'btn btn-info btn-sm';
    btn.title = '식품안전나라 등록 정보를 가져왔습니다';
    
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
    
    // 성공 알림 표시
    alert('제품 정보를 성공적으로 불러왔습니다.\n\n기본정보(제품명, 식품유형), 원재료&알레르기(원재료명), 기타항목(용기·포장재질, 제조원) 이 자동으로 입력되었습니다.');
}

// 검증 오류 처리 함수
function handleVerificationError(btn, data) {
    const status = data.status || 'unknown';
    let message = data.message || '검증에 실패했습니다.';
    
    switch(status) {
        case 'format_error':
            btn.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>형식오류';
            btn.className = 'btn btn-warning btn-sm';
            btn.title = '품목보고번호 형식이 올바르지 않습니다';
            break;
            
        case 'rule_error':
            btn.innerHTML = '<i class="fas fa-ban me-1"></i>규칙오류';
            btn.className = 'btn btn-warning btn-sm';
            btn.title = '품목보고번호 규칙에 맞지 않습니다';
            break;
            
        case 'not_found':
            btn.innerHTML = '<i class="fas fa-question-circle me-1"></i>미등록';
            btn.className = 'btn btn-danger btn-sm';
            btn.title = '등록되지 않은 품목보고번호입니다';
            break;
            
        case 'completed':
            btn.innerHTML = '<i class="fas fa-info-circle me-1"></i>중복확인';
            btn.className = 'btn btn-info btn-sm';
            btn.title = '이미 등록된 번호입니다';
            break;
            
        case 'error':
        default:
            btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>검증실패';
            btn.className = 'btn btn-danger btn-sm';
            btn.title = '검증 중 오류가 발생했습니다';
            break;
    }
    
    // 비침입적인 방식으로 오류 표시
    setTimeout(() => {
        const shouldRetry = confirm(message + '\n\n다시 검증하시겠습니까?');
        if (shouldRetry) {
            btn.innerHTML = '번호검증';
            btn.className = 'btn btn-outline-primary btn-sm';
            btn.title = 'API 중복 검사 및 번호 규칙 검증';
        }
    }, 100);
}

// 네트워크 오류 처리 함수
function handleVerificationNetworkError(btn, err) {
    btn.innerHTML = '<i class="fas fa-wifi me-1"></i>통신오류';
    btn.className = 'btn btn-secondary btn-sm';
    btn.title = '네트워크 연결 또는 서버 오류';
    
    setTimeout(() => {
        const errorMsg = '검증 중 통신 오류가 발생했습니다.\n' + 
                        '인터넷 연결을 확인하고 다시 시도해주세요.\n\n' +
                        '오류 내용: ' + (err.message || '알 수 없는 오류');
        
        if (confirm(errorMsg + '\n\n다시 시도하시겠습니까?')) {
            btn.innerHTML = '번호검증';
            btn.className = 'btn btn-outline-primary btn-sm';
            btn.title = 'API 중복 검사 및 번호 규칙 검증';
        }
    }, 100);
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

    // ==================== 식품유형 선택기 ====================
    const foodGroupSelect = document.getElementById('food_group');
    const foodTypeSelect = document.getElementById('food_type');
    
    if (foodGroupSelect && foodTypeSelect) {
        const allFoodTypes = Array.from(foodTypeSelect.options);

        foodGroupSelect.addEventListener('change', function() {
            const selectedGroup = this.value;
            foodTypeSelect.innerHTML = '<option value="">소분류</option>';
            
            allFoodTypes.forEach(option => {
                if (option.dataset.group === selectedGroup || selectedGroup === "") {
                    if (option.value) {
                        const newOption = option.cloneNode(true);
                        newOption.style.display = 'block';
                        foodTypeSelect.appendChild(newOption);
                    }
                }
            });
        });

        // 식품유형 선택 시 입력 필드 자동 채우기
        foodTypeSelect.addEventListener('change', function() {
            const selectedFoodType = this.value;
            const prdlstDcnmInput = document.querySelector('input[name="prdlst_dcnm"]');
            if (prdlstDcnmInput && selectedFoodType) {
                prdlstDcnmInput.value = selectedFoodType;
                updatePreview();
            }
        });
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
        console.error('❌ demoForm을 찾을 수 없습니다');
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
            // localStorage에 데이터가 없거나, caution 필드가 비어있을 경우에만 자동 활성화
            const cautionTextarea = document.querySelector('textarea[name="caution"]');
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
                document.getElementById('chk_recycling_mark').checked = true;
            } else {
                // 마크 제거
                removeRecyclingMark();
                addRecyclingMarkBtn.textContent = '추가';
                addRecyclingMarkBtn.classList.replace('btn-danger', 'btn-outline-primary');
                recyclingMarkSelect.value = '';
                document.getElementById('chk_recycling_mark').checked = false;
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

    showToast('PDF 생성을 시작합니다. 잠시만 기다려주세요...');

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

            showToast('PDF 파일 저장이 시작되었습니다.');

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
    
    // 필수 항목 체크
    if (!formData.prdlst_nm || !formData.prdlst_nm.trim()) {
        alert('제품명을 입력해주세요.');
        return;
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
            showToast(data.message || '표시사항이 저장되었습니다!');
            
            // localStorage 데이터 초기화
            localStorage.removeItem('demo_label_data');
            
            // 표시사항 리스트 페이지로 리다이렉트
            setTimeout(() => {
                window.location.href = data.redirect_url || '/label/my-labels/';
            }, 500);
        } else if (data.requires_login) {
            // 로그인 필요 응답 처리
            const userConfirmed = confirm(data.message);
            if (userConfirmed) {
                window.location.href = data.login_url || '/user-management/login/?next=/';
            }
        } else {
            console.error('❌ 저장 실패:', data.error);
            alert('저장에 실패했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        console.error('❌ 서버 통신 오류:', error);
        alert('서버와의 통신에 실패했습니다. 다시 시도해주세요.');
    });
}

function getCsrfToken() {
    return getCookie('csrftoken');
}

// 작성 페이지로 전환
function switchToEditor() {
    const labelId = new URLSearchParams(window.location.search).get('label_id');
    if (labelId) {
        window.location.href = `/label/label-creation/${labelId}/`;
    } else {
        alert('전환할 표시사항이 없습니다.');
    }
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

// 알레르기 태그 추가
function addAllergenTag(allergen, isAuto = false) {
    if (isAuto) {
        window.autoDetectedAllergens.add(allergen);
    }
    window.selectedIngredientAllergens.add(allergen);
    updateAllergenDisplay();
}

// 알레르기 태그 제거
function removeAllergenTag(allergen) {
    window.autoDetectedAllergens.delete(allergen);
    window.selectedIngredientAllergens.delete(allergen);
    updateAllergenDisplay();
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
                        // 2글자 이상은 포함 여부만 체크
                        if (rawmtrlText.toLowerCase().includes(keyword.toLowerCase())) {
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
    
    // 현재 상태 확인: 혼입 경고 문구가 있는지
    const hasWarning = cautionTextarea.value.includes('같은 제조시설');
    
    if (hasWarning) {
        // 주의사항에서 해제
        const originalValue = cautionTextarea.value;
        
        // 혼입 경고 문구 패턴 제거
        const newValue = originalValue.replace(/본 제품은 .+?를 사용한 제품과 같은 제조시설\(또는 동일 라인\)에서 제조되었습니다\./g, '').trim();
        
        // 연속된 줄바꿈 정리
        cautionTextarea.value = newValue.replace(/\n{3,}/g, '\n\n');
        
        // textarea 높이 자동 조절
        if (cautionTextarea.classList.contains('auto-resize')) {
            autoResizeHeight(cautionTextarea);
            setTimeout(() => autoResizeHeight(cautionTextarea), 10);
        }
        
        updatePreview();
        
        // 버튼 상태 변경
        toggleBtn.classList.remove('btn-danger');
        toggleBtn.classList.add('btn-outline-primary');
        toggleBtn.innerHTML = '<i class="fas fa-arrow-right me-1"></i>주의사항에 추가';
        
        // 혼입 경고 문구 미리보기 다시 표시 (해제되었으므로, 선택된 항목이 있으면)
        const selectedAllergensForPreview = [];
        document.querySelectorAll('.allergen-toggle.active').forEach(button => {
            selectedAllergensForPreview.push(button.dataset.allergen);
        });
        
        if (selectedAllergensForPreview.length > 0) {
            updateCrossContaminationPreview();
        }
        
        // 성공 메시지
        if (originalValue !== cautionTextarea.value) {
            const toast = document.createElement('div');
            toast.className = 'position-fixed top-0 end-0 p-3';
            toast.style.zIndex = '9999';
            toast.innerHTML = `
                <div class="alert alert-warning alert-dismissible fade show" role="alert">
                    <i class="fas fa-check-circle me-2"></i>주의사항에서 혼입 경고 문구가 제거되었습니다.
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    } else {
        // 주의사항에 추가
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
        
        const warningText = `본 제품은 ${selectedAllergens.join(', ')}를 사용한 제품과 같은 제조시설(또는 동일 라인)에서 제조되었습니다.`;
        
        if (cautionTextarea.value.trim()) {
            cautionTextarea.value += '\n' + warningText;
        } else {
            cautionTextarea.value = warningText;
        }
        
        // textarea 높이 자동 조절 (auto-resize 트리거)
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
        
        // 버튼 상태 변경
        toggleBtn.classList.remove('btn-outline-primary');
        toggleBtn.classList.add('btn-danger');
        toggleBtn.innerHTML = '<i class="fas fa-arrow-left me-1"></i>주의사항에서 해제';
        
        // 혼입 경고 문구 미리보기 숨기기 (추가되었으므로)
        const previewDiv = document.getElementById('crossContaminationPreview');
        if (previewDiv) {
            previewDiv.style.display = 'none';
        }
        
        // 성공 메시지
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <i class="fas fa-check-circle me-2"></i>주의사항에 혼입 경고 문구가 추가되었습니다.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
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
    
    const buttons = document.querySelectorAll(`.quick-text-toggle[data-field="${fieldName}"]`);
    const textsToAdd = [];
    
    buttons.forEach(button => {
        const text = button.getAttribute('data-text');
        const isActive = button.classList.contains('active');
        
        if (!isActive) {
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
        
        // 성공 메시지
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <i class="fas fa-check-circle me-2"></i>${textsToAdd.length}개의 문구가 추가되었습니다.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
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
        
        // 성공 메시지
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                <i class="fas fa-eraser me-2"></i>${removedCount}개의 문구가 해제되었습니다.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
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
    const timestamp = new Date().toISOString();
    
    // localStorage 저장 (비로그인/로그인 모두)
    localStorage.setItem('labeldata_allergens', JSON.stringify([...window.selectedIngredientAllergens]));
    localStorage.setItem('labeldata_crossContaminationAllergens', JSON.stringify([...window.selectedCrossContaminationAllergens]));
    localStorage.setItem('labeldata_timestamp', timestamp);
}

// localStorage에서 알레르기 정보 로드
function loadAllergensFromStorage() {
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
            
            updateAllergenTags();
            console.log('알레르기 정보를 localStorage에서 불러왔습니다.');
        } else {
            // 만료된 데이터 삭제
            localStorage.removeItem('labeldata_allergens');
            localStorage.removeItem('labeldata_crossContaminationAllergens');
            localStorage.removeItem('labeldata_timestamp');
        }
    }
}

// 페이지 로드 시 드래그 스크롤 초기화
document.addEventListener('DOMContentLoaded', () => {
    initializeDragScroll();
    initializePanelResizer();
    loadAllergensFromStorage();
});
