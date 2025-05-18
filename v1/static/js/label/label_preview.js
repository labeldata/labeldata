// label_preview.html의 <script>...</script> 부분 전체를 이 파일로 이동

document.addEventListener('DOMContentLoaded', function () {
    // 디버깅을 위한 데이터 로드 확인
    console.log("Checking data elements:");
    
    try {
        const previewItems = document.getElementById('preview-items-data')?.textContent;
        const nutritionItems = document.getElementById('nutrition-items-data')?.textContent;
        const defaultSettings = document.getElementById('default-settings-data')?.textContent;

        console.log("Preview items:", previewItems ? JSON.parse(previewItems) : null);
        console.log("Nutrition items:", nutritionItems ? JSON.parse(nutritionItems) : null);
        console.log("Settings:", defaultSettings ? JSON.parse(defaultSettings) : null);
    } catch (error) {
        console.error("Error parsing data:", error);
    }

    // 작성일시 정보 가져오기
    const updateDateTime = document.getElementById('update_datetime')?.value;
    
    // 푸터 텍스트 업데이트
    const footerText = document.querySelector('.footer-text');
    if (footerText) {
        footerText.innerHTML = `
            labeldata.com 에서 관련법규에 따라 작성되었습니다.
            <span class="creator-info">[${updateDateTime}]</span>
        `;
    }

    // 팝업 유틸리티 함수
    window.openPreviewPopup = function () {
        try {
            const labelId = document.querySelector('input[name="label_id"]')?.value;
            if (!labelId) {
                console.error("Label ID not found");
                alert('라벨 ID를 찾을 수 없습니다.');
                return;
            }

            const url = `/label/preview/?label_id=${labelId}`;
            const width = 1100;
            const height = 900;
            const left = (screen.width - width) / 2;
            const top = (screen.height - height) / 2;
            
            const popup = window.open(
                url,
                "previewPopup",
                `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
            );

            if (!popup) {
                alert("팝업이 차단되었습니다. 팝업 차단을 해제해주세요.");
            }
        } catch (error) {
            console.error("Error opening preview popup:", error);
            alert('미리보기 팝업을 열 수 없습니다.');
        }
    };

    // 미리보기 컨텐츠 캐싱
    const previewContent = document.getElementById('previewContent');
    const settingsForm = document.getElementById('settingsForm');

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

    // 규정 검증 버튼 이벤트 리스너 설정 수정
    const validateButton = document.getElementById('validateButton');
    if (validateButton) {
        validateButton.addEventListener('click', validateSettings);
    }

    const DEFAULT_SETTINGS = {
        width: 10,
        height: 10,
        fontSize: 10,
        letterSpacing: -5,
        lineHeight: 1,
        fontFamily: "'Noto Sans KR'"
    };

    function updatePreviewStyles() {
        const previewContent = document.getElementById('previewContent');
        if (!previewContent) return;
    
        const settings = {
            width: parseFloat(document.getElementById('widthInput').value) || 10,
            height: parseFloat(document.getElementById('heightInput').value) || 10,
            fontSize: parseFloat(document.getElementById('fontSizeInput').value) || 10,
            letterSpacing: parseInt(document.getElementById('letterSpacingInput').value) || -5,
            lineHeight: parseFloat(document.getElementById('lineHeightInput').value) || 1,
            fontFamily: document.getElementById('fontFamilySelect').value || "'Noto Sans KR'"
        };

        previewContent.style.cssText = `
            width: ${settings.width}cm;
            min-width: ${settings.width}cm;
            position: relative;
            padding: 10px;
            background: #fff;
            border: 1px solid #dee2e6;
            overflow-x: auto;
            box-sizing: border-box;
        `;
    
        const table = previewContent.querySelector('.preview-table');
        if (table) {
            table.style.cssText = `
                width: 100%;
                border-collapse: collapse;
                table-layout: auto;
                margin: 0;
                word-break: break-word;
            `;
        }
    
        const baseTextStyle = `
            font-size: ${settings.fontSize}pt;
            font-family: ${settings.fontFamily};
            letter-spacing: ${settings.letterSpacing/100}em;
            line-height: ${settings.lineHeight};
        `;
    
        const cells = previewContent.querySelectorAll('th, td');
        cells.forEach(cell => {
            cell.style.cssText = `
                ${baseTextStyle}
                padding: 8px;
                border: 1px solid #dee2e6;
                vertical-align: middle;
                word-break: break-word;
                overflow-wrap: break-word;
                text-align: left;
            `;
        });
    
        const headerText = previewContent.querySelector('.header-text');
        if (headerText) {
            headerText.style.cssText = `
                ${baseTextStyle}
                text-align: center;
                white-space: nowrap;
                margin: 0;
            `;
        }
    
        requestAnimationFrame(() => {
            const contentHeight = previewContent.scrollHeight;
            const cmHeight = Math.ceil(contentHeight / 37.8);
            document.getElementById('heightInput').value = cmHeight;
            updateArea();
        });
    }

    function setupEventListeners() {
        const inputs = [
            'widthInput', 'fontSizeInput', 'letterSpacingInput',
            'lineHeightInput', 'fontFamilySelect'
        ];

        inputs.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', debounce(updatePreviewStyles, 100));
                element.addEventListener('change', updatePreviewStyles);
            }
        });

        // 초기화 버튼 이벤트 리스너
        const resetButton = document.querySelector('button[onclick="resetSettings()"]');
        if (resetButton) {
            resetButton.onclick = null;
            resetButton.addEventListener('click', resetSettings);
        }
    }

    function resetSettings() {
        Object.entries(DEFAULT_SETTINGS).forEach(([key, value]) => {
            const element = document.getElementById(`${key}Input`) || 
                          document.getElementById(`${key}Select`);
            if (element) {
                element.value = value;
            }
        });
        
        updatePreviewStyles();
        updateArea();
    }


    function updateArea() {
        const width = parseFloat(document.getElementById('widthInput').value) || 0;
        const height = parseFloat(document.getElementById('heightInput').value) || 0;
        const area = width * height;
        
        const areaDisplay = document.getElementById('areaDisplay');
        if (areaDisplay) {
            areaDisplay.textContent = Math.round(area * 100) / 100;
        }
        
        return area;
    }

    function setupAreaCalculation() {
        const inputs = ['widthInput', 'heightInput'];
        inputs.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', updateArea);
                element.addEventListener('change', updateArea);
            }
        });
    }

    function enforceInputMinMax() {
        const fontSizeInput = document.getElementById('fontSizeInput');
        const letterSpacingInput = document.getElementById('letterSpacingInput');
        const lineHeightInput = document.getElementById('lineHeightInput');
        if (fontSizeInput && fontSizeInput.value < 10) fontSizeInput.value = 10;
        if (letterSpacingInput && letterSpacingInput.value < -5) letterSpacingInput.value = -5;
        if (lineHeightInput && lineHeightInput.value < 1) lineHeightInput.value = 1;

        // 수동 입력 시에도 최솟값 자동 보정
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
                if (parseFloat(this.value) < 1) this.value = 1;
            });
        }
    }

    // 기존의 setupEventListeners, updatePreviewStyles 등 함수 호출
    setupEventListeners();
    setTimeout(updatePreviewStyles, 100);
    setupAreaCalculation();
    setTimeout(updateArea, 100);
    enforceInputMinMax();

    // PDF 저장 버튼 이벤트 리스너 안전하게 바인딩
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', exportToPDF);
    }

    // nutrition_data를 읽어 영양성분 탭에 값 세팅 및 미리보기 결과 렌더
    try {
        const nutritionDataRaw = document.getElementById('nutrition-data')?.textContent;
        if (nutritionDataRaw) {
            const nutritionData = JSON.parse(nutritionDataRaw);
            console.log('nutritionData:', nutritionData);
            // 예시 데이터 삽입 (nutrients가 없거나 비어 있으면)
            if (!nutritionData.nutrients || Object.keys(nutritionData.nutrients).length === 0) {
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
                console.warn('nutrients 데이터가 없어 예시 데이터로 대체합니다.');
            }
            // 영양성분 탭 input/select 값 세팅
            if (nutritionData.serving_size && nutritionData.serving_size_unit) {
                document.getElementById('servingSizeDisplay').value = `${nutritionData.serving_size}${nutritionData.serving_size_unit}`;
            }
            if (nutritionData.units_per_package) {
                document.getElementById('servingsPerPackageDisplay').value = nutritionData.units_per_package;
            }
            if (nutritionData.display_unit) {
                document.getElementById('nutritionDisplayUnit').value = nutritionData.display_unit;
            }
            // 오른쪽 미리보기 패널에 계산기와 동일하게 결과 렌더
            // nutritionData를 계산기와 동일한 구조로 변환
            const data = {
                servingSize: nutritionData.serving_size,
                servingUnit: nutritionData.serving_size_unit,
                servingsPerPackage: nutritionData.units_per_package,
                servingUnitText: nutritionData.serving_size_unit === 'ml' ? '개' : '개', // 필요시 조정
                displayUnit: nutritionData.display_unit,
                totalWeight: nutritionData.serving_size * nutritionData.units_per_package,
                values: []
            };
            // nutrients -> values 변환 (calorie 포함, 순서 고정)
            const nutrientOrder = [
                'natrium', 'carbohydrate', 'sugar', 'afat', 'transfat', 'satufat', 'cholesterol', 'protein'
            ];
            const nutrientLabels = {
                calorie: '열량', natrium: '나트륨', carbohydrate: '탄수화물', sugar: '당류', afat: '지방', transfat: '트랜스지방', satufat: '포화지방', cholesterol: '콜레스테롤', protein: '단백질'
            };
            const nutrientLimits = {
                natrium: 2000, carbohydrate: 324, sugar: 100, afat: 54, satufat: 15, cholesterol: 300, protein: 55
            };
            // 열량(칼로리) 별도 저장
            let calorieValue = null, calorieUnit = '';
            if (nutritionData.nutrients && nutritionData.nutrients.calorie) {
                calorieValue = nutritionData.nutrients.calorie.value;
                calorieUnit = nutritionData.nutrients.calorie.unit || 'kcal';
            }
            // 나머지 항목 표로 변환
            if (nutritionData.nutrients) {
                for (const key of nutrientOrder) {
                    // 값이 없어도 무조건 표에 표시 (없으면 0)
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
            console.log('nutritionData.values:', data.values);
            if (!data.values || data.values.length === 0) {
                console.warn('영양성분 데이터가 비어 있습니다.');
            }
            // 미리보기 표 렌더
            window.nutritionData = data;
            updateNutritionDisplay(data);
            // 미리보기 영역 보이기
            document.getElementById('nutritionPreview').style.display = 'block';
        } else {
            console.warn('nutrition-data 스크립트 태그가 비어 있습니다.');
        }
    } catch (e) {
        console.error('영양성분 데이터 파싱 오류:', e);
    }

    // 탭 전환 시 미리보기 화면 토글 처리
    function handleTabSwitch() {
        const activeTab = document.querySelector('.nav-link.active[data-bs-toggle="tab"]');
        const previewTable = document.querySelector('.preview-table');
        const nutritionPreview = document.getElementById('nutritionPreview');
        const headerBox = document.querySelector('.preview-header-box');
        if (!activeTab) return;
        if (activeTab.getAttribute('data-bs-target') === '#nutrition-tab') {
            // 영양성분 탭: 영양성분 표만 보이기
            if (previewTable) previewTable.style.display = 'none';
            if (headerBox) headerBox.style.display = 'none';
            if (nutritionPreview) nutritionPreview.style.display = 'block';
        } else {
            // 표시사항 탭: 기존 표만 보이기
            if (previewTable) previewTable.style.display = '';
            if (headerBox) headerBox.style.display = '';
            if (nutritionPreview) nutritionPreview.style.display = 'none';
        }
    }
    // 탭 버튼에 이벤트 리스너 등록
    document.querySelectorAll('.nav-link[data-bs-toggle="tab"]').forEach(tabBtn => {
        tabBtn.addEventListener('shown.bs.tab', handleTabSwitch);
    });
    // 페이지 로드시 활성 탭에 맞게 토글 적용
    handleTabSwitch();
});

// 팝업에서 부모로부터 체크박스 상태를 받아 적용
window.addEventListener('message', function(e) {
    if (e.data?.type === 'previewCheckbox' && e.data.checked) {
        Object.entries(e.data.checked).forEach(([id, value]) => {
            const cb = document.getElementById(id);
            if (cb && typeof value === 'boolean') {
                cb.checked = value;
            }
        });
    }
});

// 체크된 필드만 표에 동적으로 렌더링
const FIELD_LABELS = {
    my_label_name: '라벨명',
    prdlst_dcnm: '식품유형',
    prdlst_nm: '제품명',
    ingredient_info: '성분명 및 함량',
    content_weight: '내용량',
    weight_calorie: '내용량(열량)',
    prdlst_report_no: '품목보고번호',
    country_of_origin: '원산지',
    storage_method: '보관방법',
    frmlc_mtrqlt: '용기.포장재질',
    bssh_nm: '제조원 소재지',
    distributor_address: '유통전문판매원',
    repacker_address: '소분원',
    importer_address: '수입원',
    pog_daycnt: '소비기한',
    rawmtrl_nm_display: '원재료명',  // '원재료명(표시)'에서 '원재료명'으로 변경
    cautions: '주의사항',
    additional_info: '기타표시사항',
    nutrition_text: '영양성분'
};

window.addEventListener('message', function(e) {
    if (e.data?.type === 'previewCheckedFields' && e.data.checked) {
        const tbody = document.getElementById('previewTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        Object.entries(e.data.checked).forEach(([field, value]) => {
            if (FIELD_LABELS[field]) {
                const tr = document.createElement('tr');
                const th = document.createElement('th');
                const td = document.createElement('td');
                
                th.textContent = FIELD_LABELS[field];

                // 원재료명 처리
                if (field === 'rawmtrl_nm_display') {
                    const allergenMatch = value.match(/\[알레르기 성분\s*:\s*([^\]]+)\]/);
                    const gmoMatch = value.match(/\[GMO\s*성분\s*:[^\]]+\]/);  // GMO 정규식 수정
                    
                    // 컨테이너 생성
                    const container = document.createElement('div');
                    container.style.position = 'relative';
                    container.style.width = '100%';
                    
                    // 메인 텍스트 추출 및 설정
                    let mainText = value
                        .replace(/\[알레르기 성분\s*:[^\]]+\]/, '')
                        .replace(/\[GMO\s*성분\s*:[^\]]+\]/, '')  // GMO 텍스트 제거 패턴 수정
                        .trim();
                    
                    // 메인 텍스트 div
                    const mainDiv = document.createElement('div');
                    mainDiv.textContent = mainText;
                    container.appendChild(mainDiv);
                    
                    // 알레르기 성분 처리
                    if (allergenMatch) {
                        const allergens = allergenMatch[1].trim();
                        const allergenDiv = document.createElement('div');
                        allergenDiv.textContent = `${allergens} 함유`;
                        allergenDiv.style.cssText = `
                            margin-top: 8px;
                            text-align: right;
                            background-color: var(--primary-color);
                            color: white;
                            padding: 4px 8px;
                            display: inline-block;
                            margin-left: auto;
                            font-size: 0.9em;
                            float: right;
                            clear: both;
                        `;
                        container.appendChild(allergenDiv);
                    }
                    
                    // GMO 성분 처리
                    if (gmoMatch) {
                        const gmo = gmoMatch[1].trim();
                        const gmoDiv = document.createElement('div');
                        gmoDiv.textContent = `${gmo} 함유`;
                        gmoDiv.style.cssText = `
                            margin-top: 8px;
                            text-align: right;
                            background-color: var(--primary-color);
                            color: white;
                            padding: 4px 8px;
                            display: inline-block;
                            margin-left: auto;
                            font-size: 0.9em;
                            float: right;
                            clear: both;
                        `;
                        container.appendChild(gmoDiv);
                    }
                    
                    td.appendChild(container);
                } else if (field === 'country_of_origin') {
                    // 원산지 값 처리
                    const select = window.opener.document.querySelector('select[name="country_of_origin"]');
                    if (select) {
                        const selectedOption = select.options[select.selectedIndex];
                        td.textContent = selectedOption ? selectedOption.text : value;
                    } else {
                        td.textContent = value;
                    }
                } else {
                    td.textContent = value;
                }
                
                tr.appendChild(th);
                tr.appendChild(td);
                tbody.appendChild(tr);
            }
        });
    }
});

// 규정 검증 시 입력값을 서버에 저장하는 함수 추가
function savePreviewSettingsToServer() {
    
    const labelId = document.querySelector('input[name="label_id"]')?.value;
    console.log(labelId);
    if (!labelId) return;
    const data = {
        label_id: labelId,
        layout: document.getElementById('layoutSelect')?.value,
        width: document.getElementById('widthInput')?.value,
        length: document.getElementById('heightInput')?.value,
        font: document.getElementById('fontFamilySelect')?.value,
        font_size: document.getElementById('fontSizeInput')?.value,
        letter_spacing: document.getElementById('letterSpacingInput')?.value,
        line_spacing: document.getElementById('lineHeightInput')?.value
    };
    fetch('/label/save_preview_settings/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '')
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(res => {
        if (!res.success) {
            alert('미리보기 설정 저장 실패: ' + (res.error || '')); 
        }
    })
    .catch(err => {
        alert('미리보기 설정 저장 중 오류 발생: ' + err);
    });
}

// 기존 validateSettings 함수 내에서 저장 함수 호출
function validateSettings() {
    const width = parseFloat(document.getElementById('widthInput').value);
    const height = parseFloat(document.getElementById('heightInput').value);
    const area = width * height;
    const fontSize = parseFloat(document.getElementById('fontSizeInput').value);
    const letterSpacing = parseFloat(document.getElementById('letterSpacingInput').value);
    const lineHeight = parseFloat(document.getElementById('lineHeightInput').value);

    // 오류 필드 추적용
    const errorFields = new Set();
    let errors = [];
    
    // 면적별 검증
    // if (area < 100) {
    //     if (fontSize < 12) {
    //         errors.push('100cm² 미만의 표시면적: 글자 크기가 12pt 이상이어야 합니다.');
    //         errorFields.add('fontSizeInput');
    //     }
    // } else if (area >= 100) {
    //     const requiredSizes = {
    //         'product-name': 16,
    //         'origin-text': 14,
    //         'content-weight': 12
    //     };
    //     document.querySelectorAll('.preview-table td').forEach(td => {
    //         const className = td.className;
    //         const computedSize = parseFloat(window.getComputedStyle(td).fontSize);
    //         if (requiredSizes[className]) {
    //             if (computedSize < requiredSizes[className]) {
    //                 errors.push(`${className}: 글자 크기가 ${requiredSizes[className]}pt 이상이어야 합니다.`);
    //                 errorFields.add('fontSizeInput');
    //             }
    //         } else if (computedSize < 10) {
    //             errors.push('일반 항목: 글자 크기가 10pt 이상이어야 합니다.');
    //             errorFields.add('fontSizeInput');
    //         }
    //     });
    // }
    // if (letterSpacing < -5) {
    //     errors.push('자간은 -5% 이상이어야 합니다.');
    //     errorFields.add('letterSpacingInput');
    // }
    // if (lineHeight < 1) {
    //     errors.push('줄간격은 1 이상이어야 합니다.');
    //     errorFields.add('lineHeightInput');
    // }
    // if (width < 4 || width > 30) errorFields.add('widthInput');
    // if (height < 3 || height > 20) errorFields.add('heightInput');

    // 필드별로 is-invalid 및 is-valid 처리
    ['widthInput', 'heightInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (errorFields.has(id)) {
                el.classList.add('is-invalid');
                el.classList.remove('is-valid');
            } else {
                el.classList.remove('is-invalid');
                el.classList.add('is-valid');
            }
        }
    });

    if (errors.length > 0) {
        alert('규정 검증 결과:\n\n' + errors.join('\n'));
        return false;
    } else {
        // 규정 검증 통과 시 서버에 저장
        savePreviewSettingsToServer();
        alert('모든 규정을 준수하고 있습니다.');
        return true;
    }
}

// 세로 길이 자동 계산 함수
function calculateHeight() {
    const width = parseFloat(document.getElementById('widthInput').value);
    const fontSize = parseFloat(document.getElementById('fontSizeInput').value);
    const letterSpacing = parseFloat(document.getElementById('letterSpacingInput').value);
    const lineHeight = parseFloat(document.getElementById('lineHeightInput').value);
    
    // 표 내용의 실제 높이 계산
    const table = document.getElementById('previewTableBody');
    const contentHeight = table.offsetHeight;
    
    // 헤더와 푸터 높이 추가
    const totalHeight = (contentHeight + 80) / 28.35; // px를 cm로 변환 (1cm = 28.35px)
    
    // heightInput 업데이트
    const heightInput = document.getElementById('heightInput');
    heightInput.value = Math.ceil(totalHeight);
    
    // 면적 계산 및 표시
    updateArea(width, totalHeight);
}

// 입력값 변경 이벤트에 계산 함수 연결
const widthInput = document.getElementById("widthInput");
if (widthInput) widthInput.addEventListener("change", calculateHeight);

const fontSizeInput = document.getElementById('fontSizeInput');
if (fontSizeInput) fontSizeInput.addEventListener('change', calculateHeight);

const letterSpacingInput = document.getElementById('letterSpacingInput');
if (letterSpacingInput) letterSpacingInput.addEventListener('change', calculateHeight);

const lineHeightInput = document.getElementById('lineHeightInput');
if (lineHeightInput) lineHeightInput.addEventListener('change', calculateHeight);

// 초기 로드 시 계산
window.addEventListener('load', calculateHeight);

// PDF 저장 함수 수정

// 함수 선언문으로 변경하여 호이스팅 보장
async function exportToPDF() {
    try {
        const content = document.getElementById('previewContent');
        if (!content) throw new Error('미리보기 내용을 찾을 수 없습니다.');

        // 사용자 설정 파싱
        let settings = {};
        const settingsEl = document.getElementById('default-settings-data');
        if (settingsEl) {
            try { settings = JSON.parse(settingsEl.textContent); } catch {}
        }

        // 설정된 크기 (mm 기준)
        const widthMm = settings.widthMm || 100;
        const heightMm = settings.heightMm || 100;

        // 제품명 추출 (파일명 생성용)
        let productName = '제품명';
        document.querySelectorAll('#previewTableBody tr').forEach(tr => {
            if (tr.querySelector('th')?.textContent.trim() === '제품명') {
                const td = tr.querySelector('td');
                if (td) productName = td.textContent.trim();
            }
        });

        // 업데이트 일자
        const rawDate = document.getElementById('update_datetime')?.value || new Date().toISOString();
        const formattedDate = rawDate.slice(0, 10).replace(/-/g, '');

        // 파일명 생성
        const sanitizedName = productName.replace(/[^\w가-힣]/g, '_').slice(0, 20);
        const fileName = `LABELDATA_${sanitizedName}_${formattedDate}.pdf`;

        // 고화질 캔버스
        const canvas = await html2canvas(content, {
            scale: 3,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#fff',
        });
        const imgData = canvas.toDataURL('image/png');

        // PDF 생성 (mm 단위 페이지 크기)
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', [widthMm, heightMm]);
        pdf.addImage(imgData, 'PNG', 0, 0, widthMm, heightMm);
        pdf.save(fileName);
    } catch (err) {
        console.error("PDF 저장 중 오류", err);
        alert("PDF 저장 실패: " + err.message);
    }
}

// 천 단위 콤마 함수 (숫자 포맷팅)
function comma(x) {
  if (x === null || x === undefined) return '';
  // 소수점 이하가 있으면 소수점 앞부분만 콤마 처리
  const parts = x.toString().split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return parts.join('.');
}

// 영양성분 데이터 수신 및 표시
window.addEventListener('message', function(e) {
  if (e.data?.type === 'nutritionData') {
    const data = e.data.data;
    window.nutritionData = data; // 데이터 저장
    
    // 설정값 표시
    document.getElementById('servingSizeDisplay').value = 
      `${comma(data.servingSize)}${data.servingUnit}`;
    document.getElementById('servingsPerPackageDisplay').value = 
      `${comma(data.servingsPerPackage)}${data.servingUnitText}`;
    
    // 영양성분 탭으로 전환
    const nutritionTab = document.querySelector('[data-bs-target="#nutrition-tab"]');
    const tabInstance = new bootstrap.Tab(nutritionTab);
    tabInstance.show();
    
    // 미리보기 업데이트
    updateNutritionDisplay(data);
  }
});

// updateNutritionDisplay 함수: 팝업과 동일하게 CSS class 및 구조 적용
function updateNutritionDisplay(data) {
  const nutritionPreview = document.getElementById('nutritionPreview');
  if (!nutritionPreview) return;

  // 표시단위 텍스트
  const displayUnit = data.displayUnit || 'unit';
  const servingUnit = data.servingUnit || 'g';
  const servingUnitText = data.servingUnitText || '개';
  const totalWeight = data.totalWeight || (data.servingSize * data.servingsPerPackage);
  const tabMap = {
    total: `총 내용량 ${comma(totalWeight)}${servingUnit}`,
    unit: `단위내용량 ${comma(data.servingSize)}${servingUnit}`,
    '100g': `100${servingUnit}당`
  };

  // 열량(칼로리) 텍스트
  let kcal = data.calorie !== undefined && data.calorie !== null ? data.calorie : '';
  let kcalUnit = data.calorieUnit || 'kcal';

  // 상단 미리보기 박스 (팝업과 동일한 클래스/스타일)
  const previewBox = `
    <div class="nutrition-preview-box">
      <div class="nutrition-preview-title">영양정보</div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;">
        <span class="nutrition-preview-total-small">${tabMap[displayUnit]}</span>
        <span class="nutrition-preview-kcal">${kcal !== '' ? comma(kcal) + kcalUnit : ''}</span>
      </div>
    </div>
  `;

  // 표 헤더
  const tableHeader = `
    <thead>
      <tr>
        <th class="nutrition-preview-small" style="text-align:left;">${tabMap[displayUnit]}</th>
        <th class="nutrition-preview-small" style="text-align:right;">1일 영양성분 기준치에 대한 비율</th>
      </tr>
    </thead>
  `;

  // 표 본문
  const indentIds = ['당류', '트랜스지방', '포화지방'];
  let rows = '';
  (data.values || []).forEach(item => {
    const indent = indentIds.includes(item.label);
    const percent = item.limit ? Math.round(item.value / item.limit * 100) : '';
    rows += `<tr>
      <td class="nutrient-label${indent ? ' nutrient-label-indent' : ''}">
        <strong>${item.label}</strong> <span class="nutrient-value">${comma(item.value)}${item.unit}</span>
      </td>
      <td class="nutrient-percent" style="text-align:right;">${percent !== '' ? `<strong>${percent}</strong>%` : ''}</td>
    </tr>`;
  });

  // 안내문구(표 내부 마지막 tr, 작은 글씨)
  rows += `
    <tr>
      <td colspan="2" class="nutrition-preview-footer-inside">
        <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.
      </td>
    </tr>
  `;

  // 표 전체 (팝업과 동일한 클래스/스타일)
  const tableHtml = `
    <table class="nutrition-preview-table">
      ${tableHeader}
      <tbody>${rows}</tbody>
    </table>
  `;

  // 렌더링
  nutritionPreview.innerHTML = previewBox + tableHtml;
  nutritionPreview.style.display = 'block';
}

// 표시 단위 변경 이벤트 처리
document.getElementById('nutritionDisplayUnit')?.addEventListener('change', function() {
  if (window.nutritionData) {
    updateNutritionDisplay(window.nutritionData);
  }
});

// 영양성분 데이터 수신 및 표시
window.addEventListener('message', function(e) {
  if (e.data?.type === 'nutritionData') {
    const data = e.data.data;
    window.nutritionData = data;

    // 설정값 표시 업데이트
    document.getElementById('servingSizeDisplay').value = 
      `${comma(data.servingSize)}${data.servingSizeUnit}`;
    document.getElementById('servingsPerPackageDisplay').value = 
      `${comma(data.servingsPerPackage)}${data.servingUnitText}`;
    document.getElementById('nutritionDisplayUnit').value = data.displayUnit;
    
    // 영양성분 탭으로 전환
    const nutritionTab = document.querySelector('[data-bs-target="#nutrition-tab"]');
    const tabInstance = new bootstrap.Tab(nutritionTab);
    tabInstance.show();
    
    // 미리보기 업데이트
    updateNutritionDisplay(data);
  }
});

// 영양성분 데이터 수신 및 표시
window.addEventListener('message', function(e) {
  if (e.data?.type === 'nutritionData') {
    const data = e.data.data;
    
    // 헤더 업데이트
    const headerText = `총 내용량 ${comma(data.totalWeight)}${data.servingUnit} ` +
      `(${comma(data.servingSize)}${data.servingUnit}×${data.servingsPerPackage}${data.servingUnitText})`;
    document.querySelector('.nutrition-header').textContent = headerText;
    
    // 표 내용 업데이트
    const tbody = document.getElementById('nutritionTableBody');
    tbody.innerHTML = data.values.map(item => {
      const percentage = item.limit ? Math.round((item.value / item.limit) * 100) : '';
      return `
        <tr>
          <td>${item.label}</td>
          <td>${comma(item.value)}${item.unit}</td>
          <td>${percentage ? percentage + '%' : '-'}</td>
        </tr>
      `;
    }).join('');
  }
});

// 영양성분 데이터 수신 시 처리
window.addEventListener('message', function(e) {
  if (e.data?.type === 'nutritionData') {
    const data = e.data.data;
    window.nutritionData = data;
    
    // 설정값 표시 업데이트
    document.getElementById('servingSizeDisplay').value = 
      `${comma(data.servingSize)}${data.servingUnit}`;
    document.getElementById('servingsPerPackageDisplay').value = 
      `${comma(data.servingsPerPackage)}${data.servingUnitText}`;
    document.getElementById('nutritionDisplayUnit').value = data.displayUnit;

    // 영양성분 미리보기 영역 표시 및 업데이트
    document.getElementById('nutritionPreview').style.display = 'block';
    updateNutritionDisplay(data);
  }
});