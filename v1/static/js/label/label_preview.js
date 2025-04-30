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
        lineHeight: 1.2,
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
            lineHeight: parseFloat(document.getElementById('lineHeightInput').value) || 1.2,
            fontFamily: document.getElementById('fontFamilySelect').value || "'Noto Sans KR'"
        };

        previewContent.style.cssText = `
            width: ${settings.width}cm;
            min-width: ${settings.width}cm;
            position: relative;
            padding: 20px;
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

    // 최종 수정일 표시 함수 수정
    function updateLastModifiedDate() {
        const dateElement = document.getElementById('lastModifiedDate');
        if (dateElement && window.opener) {
            try {
                const updateDatetime = window.opener.document.querySelector('[name="update_datetime"]')?.value;
                const date = updateDatetime ? new Date(updateDatetime) : new Date();
                
                const formattedDate = date.toLocaleString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                }).replace(/\./g, '-');

                dateElement.textContent = `최종 수정일: ${formattedDate}`;
                dateElement.style.display = 'block';
            } catch (error) {
                console.error('최종 수정일 업데이트 실패:', error);
            }
        }
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

    setupEventListeners();
    setTimeout(updatePreviewStyles, 100);
    setupAreaCalculation();
    setTimeout(updateArea, 100);
    setupValidationListeners();
});

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
    if (area < 100) {
        if (fontSize < 12) {
            errors.push('100cm² 미만의 표시면적: 글자 크기가 12pt 이상이어야 합니다.');
            errorFields.add('fontSizeInput');
        }
    } else if (area >= 100) {
        const requiredSizes = {
            'product-name': 16,
            'origin-text': 14,
            'content-weight': 12
        };
        document.querySelectorAll('.preview-table td').forEach(td => {
            const className = td.className;
            const computedSize = parseFloat(window.getComputedStyle(td).fontSize);
            if (requiredSizes[className]) {
                if (computedSize < requiredSizes[className]) {
                    errors.push(`${className}: 글자 크기가 ${requiredSizes[className]}pt 이상이어야 합니다.`);
                    errorFields.add('fontSizeInput');
                }
            } else if (computedSize < 10) {
                errors.push('일반 항목: 글자 크기가 10pt 이상이어야 합니다.');
                errorFields.add('fontSizeInput');
            }
        });
    }
    if (letterSpacing < -5) {
        errors.push('자간은 -5% 이상이어야 합니다.');
        errorFields.add('letterSpacingInput');
    }
    if (lineHeight < 1) {
        errors.push('줄간격은 1 이상이어야 합니다.');
        errorFields.add('lineHeightInput');
    }
    if (width < 4 || width > 30) errorFields.add('widthInput');
    if (height < 3 || height > 20) errorFields.add('heightInput');

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
        alert('모든 규정을 준수하고 있습니다.');
        return true;
    }
}

function setupValidationListeners() {
    // width, height, fontSize, letterSpacing, lineHeight는 엔터 입력 시만 검증
    ['widthInput', 'heightInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    validateSettings(); // is-invalid 처리는 validateSettings에서만!
                }
            });
        }
    });
}