document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 미리보기 페이지 로드 시작');
    
    // 영양성분 데이터 확인
    try {
        const nutritionItems = document.getElementById('nutrition-data')?.textContent;
        if (nutritionItems) {
            console.log('✅ 영양성분 데이터 원시값:', nutritionItems.substring(0, 200) + '...');
            const parsed = JSON.parse(nutritionItems);
            console.log('✅ 영양성분 데이터 파싱 성공:', parsed);
        } else {
            console.warn('⚠️ 영양성분 데이터 요소가 없습니다');
        }
    } catch (error) {
        console.error("❌ 영양성분 데이터 파싱 오류:", error);
    }

    // 국가 매핑 데이터 로드
    let countryMapping = {};
    try {
        const countryMappingElement = document.getElementById('country-mapping-data');
        if (countryMappingElement) {
            countryMapping = JSON.parse(countryMappingElement.textContent);
            console.log("✅ 국가 매핑 데이터 로드 성공:", Object.keys(countryMapping).length, "개");
        } else {
            console.warn("⚠️ 국가 매핑 데이터 요소가 없습니다");
        }
    } catch (error) {
        console.error("❌ 국가 매핑 데이터 로드 오류:", error);
    }

    // 만료일 추천 데이터 확인
    try {
        const expiryElement = document.getElementById('expiry-recommendation-data');
        if (expiryElement) {
            const expiryData = JSON.parse(expiryElement.textContent);
            console.log("✅ 만료일 추천 데이터 로드 성공:", expiryData);
        } else {
            console.warn("⚠️ 만료일 추천 데이터 요소가 없습니다");
        }
    } catch (error) {
        console.error("❌ 만료일 추천 데이터 로드 오류:", error);
    }

    // 국가 코드를 한글명으로 변환하는 함수
    function convertCountryCodeToKorean(text) {
        if (!text || !countryMapping) return text;
        
        // 국가 코드 패턴 찾기 (대문자 2글자)
        return text.replace(/\b[A-Z]{2}\b/g, function(match) {
            const koreanName = countryMapping[match];
            if (koreanName) {
                console.log(`국가 코드 변환: ${match} -> ${koreanName}`);
                return koreanName;
            }
            return match; // 변환할 수 없으면 원본 반환
        });
    }

    // 작성일시 정보 설정
    const updateDateTime = document.getElementById('update_datetime')?.value;
    const footerText = document.querySelector('.footer-text');
    if (footerText && updateDateTime) {
        footerText.innerHTML = `
            <span style="font-size: 7pt;">
                간편한 표시사항 연구소에서 관련 법규에 따라 작성되었습니다.
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

    // 기본 설정
    const DEFAULT_SETTINGS = {
        width: 10,
        height: 11, // 11cm 고정
        fontSize: 10,
        letterSpacing: -5,
        lineHeight: 1.2,
        fontFamily: "'Noto Sans KR'"
    };

    // 규정 상수
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
        storage_conditions: {
            frozen: { temp: "-18℃ 이하", phrases: ["냉동 보관 (-18℃ 이하)", "해동 후 재냉동 금지"] },
            refrigerated: { temp: "0~10℃", phrases: ["냉장 보관 (0~10℃)", "개봉 후 냉장 보관"] },
            room_temp: { temp: "직사광선을 피하고 서늘한 곳", phrases: ["직사광선을 피하고 서늘한 곳에 보관"] }
        },
        food_type_phrases: {
            "과ㆍ채가공품(살균제품/산성통조림)": ["캔주의"],
            "유함유가공품": ["알레르기 주의"],
            "고카페인": ["어린이, 임산부, 카페인 민감자는 섭취에 주의"],
            "젤리/곤약": ["질식주의"],
            "방사선 조사": ["감마선/전자선으로 조사처리"],
            "냉동식품": ["해동 후 재냉동 금지"]
        },
        expiry_limits: {
            frozen: 48, // 냉동식품: 최대 48개월
            default: 36 // 기타: 최대 36개월
        },
        // 아래 expiry_recommendation 객체가 백엔드로부터 전달되어야 합니다.
        expiry_recommendation: {} // 초기에는 비워둠
    };

    // 백엔드에서 전달된 소비기한 권장 데이터를 REGULATIONS 객체에 주입
    try {
        const expiryDataElement = document.getElementById('expiry-recommendation-data');
        if (expiryDataElement) {
            const expiryData = JSON.parse(expiryDataElement.textContent);
            REGULATIONS.expiry_recommendation = expiryData;
        }
    } catch (e) {
        console.error('소비기한 권장 데이터 파싱 오류:', e);
    }


    // 분리배출마크 구분값 및 이미지 매핑
    const recyclingMarkGroups = [
        {
            group: '플라스틱(PET/HDPE/LDPE/PP/PS/OTHER)',
            options: [
                { value: '무색페트', label: '무색페트', img: '/static/img/recycle_clearpet.png' },
                { value: '플라스틱(PET)', label: '플라스틱(PET)', img: '/static/img/recycle_pet.png' },
                { value: '플라스틱(HDPE)', label: '플라스틱(HDPE)', img: '/static/img/recycle_hdpe.png' },
                { value: '플라스틱(LDPE)', label: '플라스틱(LDPE)', img: '/static/img/recycle_ldpe.png' },
                { value: '플라스틱(PP)', label: '플라스틱(PP)', img: '/static/img/recycle_pp.png' },
                { value: '플라스틱(PS)', label: '플라스틱(PS)', img: '/static/img/recycle_ps.png' },
                { value: '플라스틱(OTHER)', label: '플라스틱(OTHER)', img: '/static/img/recycle_other_plastic.png' }
            ]
        },
        {
            group: '비닐류',
            options: [
                { value: '비닐류(PET)', label: '비닐류(PET)', img: '/static/img/recycle_vinyl_pet.png' },
                { value: '비닐류(HDPE)', label: '비닐류(HDPE)', img: '/static/img/recycle_vinyl_hdpe.png' },
                { value: '비닐류(LDPE)', label: '비닐류(LDPE)', img: '/static/img/recycle_vinyl_ldpe.png' },
                { value: '비닐류(PP)', label: '비닐류(PP)', img: '/static/img/recycle_vinyl_pp.png' },
                { value: '비닐류(PS)', label: '비닐류(PS)', img: '/static/img/recycle_vinyl_ps.png' },
                { value: '비닐류(OTHER)', label: '비닐류(OTHER)', img: '/static/img/recycle_vinyl_other.png' }
            ]
        },
        {
            group: '캔류',
            options: [
                { value: '캔류(철)', label: '캔류(철)', img: '/static/img/recycle_can_iron.png' },
                { value: '캔류(알미늄)', label: '캔류(알미늄)', img: '/static/img/recycle_can_aluminum.png' }
            ]
        },
        {
            group: '종이/팩/유리/기타',
            options: [
                { value: '종이', label: '종이', img: '/static/img/recycle_paper.png' },
                { value: '일반팩', label: '일반팩', img: '/static/img/recycle_pack_general.png' },
                { value: '멸균팩', label: '멸균팩', img: '/static/img/recycle_pack_sterile.png' },
                { value: '유리', label: '유리', img: '/static/img/recycle_glass.png' },
                // [삭제] 복합재질 항목을 데이터에서 제거합니다.
                // { value: '복합재질', label: '복합재질', img: '/static/img/recycle_composite.png', isComposite: true },
                { value: '도포첩합', label: '도포첩합', img: '/static/img/recycle_coated.png' }
            ]
        }
    ];

    // value → 이미지 매핑
    const recyclingMarkMap = {};
    recyclingMarkGroups.forEach(group => {
        group.options.forEach(opt => {
            recyclingMarkMap[opt.value] = opt;
        });
    });

    // 포장재질 텍스트로 추천 분리배출마크 구하기
    function recommendRecyclingMarkByMaterial(materialText) {
        if (!materialText) return null;
        const text = materialText.toLowerCase().trim();

        // [수정] 우선순위 키워드 기반 추천 로직
        // 1. PET 계열 (무색페트 우선)
        if (text.includes('pet') || text.includes('페트')) {
            if (text.includes('무색')) {
                return '무색페트';
            }
            return '플라스틱(PET)';
        }

        // 2. 폴리에틸렌(PE) 계열 (HDPE 우선)
        if (text.includes('hdpe') || text.includes('고밀도')) {
            return '플라스틱(HDPE)';
        }
        if (text.includes('ldpe') || text.includes('저밀도')) {
            return '플라스틱(LDPE)';
        }
        if (text.includes('폴리에틸렌') || text.includes('pe')) {
            // 특정 밀도 언급이 없으면 HDPE를 기본으로 추천
            return '플라스틱(HDPE)';
        }

        // 3. 기타 재질
        if (text.includes('pp') || text.includes('폴리프로필렌')) return '플라스틱(PP)';
        if (text.includes('ps') || text.includes('폴리스티렌')) return '플라스틱(PS)';
        if (text.includes('철')) return '캔류(철)';
        if (text.includes('알미늄') || text.includes('알루미늄')) return '캔류(알미늄)';
        if (text.includes('종이')) return '종이';
        if (text.includes('유리')) return '유리';
        if (text.includes('팩') && text.includes('멸균')) return '멸균팩';
        if (text.includes('팩')) return '일반팩';
        if (text.includes('도포') || text.includes('첩합') || text.includes('코팅')) return '도포첩합';
        
        // 4. 비닐류 (위에서 플라스틱으로 잡히지 않은 경우)
        if (text.includes('비닐')) {
            if (text.includes('other')) return '비닐류(OTHER)';
            return '비닐류(LDPE)'; // 비닐류의 가장 일반적인 기본값
        }

        // 5. 일반적인 '플라스틱' 또는 'other'
        if (text.includes('other')) return '플라스틱(OTHER)';
        if (text.includes('플라스틱')) return '플라스틱(OTHER)';

        return null; // 일치하는 항목이 없을 경우
    }
    
    // 분리배출마크 UI 생성 및 삽입
    function renderRecyclingMarkUI() {
        const contentTab = document.querySelector('#content-tab .settings-group');
        if (!contentTab) return;
        if (document.getElementById('recyclingMarkUiBox')) return;

        const uiBox = document.createElement('div');
        uiBox.id = 'recyclingMarkUiBox';
        uiBox.className = 'settings-row';
        // [수정] 복합재질 텍스트 입력 필드 추가
        uiBox.innerHTML = `
            <div class="settings-item">
                <label class="form-label" for="recyclingMarkSelect">분리배출마크</label>
                <div id="recyclingMarkControls">
                    <select id="recyclingMarkSelect" class="form-select form-select-sm">
                        ${recyclingMarkGroups.map(group => `
                            <optgroup label="${group.group}">
                                ${group.options.map(opt => `<option value="${opt.value}">${opt.label}</option>`).join('')}
                            </optgroup>
                        `).join('')}
                    </select>
                    <button id="addRecyclingMarkBtn" type="button" class="btn btn-outline-primary btn-sm">적용</button>
                </div>
                <!-- [수정] 추가 텍스트 입력 상자 (기본 숨김) -->
                <div id="additionalTextInputBox" style="display: none; margin-top: 8px;">
                    <label for="additionalRecyclingText" class="form-label" style="font-size: 0.8rem;">복합재질</label>
                    <div style="display: flex;">
                        <input type="text" id="additionalRecyclingText" class="form-control form-control-sm" placeholder="예: 본체(종이)/뚜껑(PP)">
                        <button id="addRecyclingTextBtn" type="button" class="btn btn-secondary btn-sm" style="margin-left: 4px; white-space: nowrap;">추가</button>
                    </div>
                </div>
            </div>
        `;
        contentTab.appendChild(uiBox);

        // [수정] 셀렉트박스 변경 시 복합재질 입력창 표시/숨김 처리
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
                const additionalInputBox = document.getElementById('additionalTextInputBox');
                if (addBtn.textContent === '적용') {
                    setRecyclingMark(markValue);
                    addBtn.textContent = '해제';
                    addBtn.classList.remove('btn-outline-primary');
                    addBtn.classList.add('btn-danger');
                    if (additionalInputBox) additionalInputBox.style.display = 'block';
                } else {
                    // [수정] 컨테이너 전체를 제거하도록 변경
                    const container = document.getElementById('recyclingMarkContainer');
                    if (container) container.remove();
                    addBtn.textContent = '적용';
                    addBtn.classList.remove('btn-danger');
                    addBtn.classList.add('btn-outline-primary');
                    if (additionalInputBox) additionalInputBox.style.display = 'none';
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

    // 추천 마크 갱신
    function updateRecyclingMarkUI(packageText) {
        const recommended = recommendRecyclingMarkByMaterial(packageText);
        const recommendSpan = document.getElementById('recyclingMarkRecommend');
        const select = document.getElementById('recyclingMarkSelect');
        if (recommendSpan) {
            recommendSpan.textContent = recommended;
        }
        if (select && recommended) {
            select.value = recommended;
        }
    }

    // [추가] 분리배출 마크에 텍스트 라인 추가
    function addTextToRecyclingMark(text) {
        const container = document.getElementById('recyclingMarkContainer');
        const image = document.getElementById('recyclingMarkImage');
        if (!container || !image) return;

        const textDiv = document.createElement('div');
        textDiv.textContent = text;
        textDiv.style.cssText = `
            font-weight: 500;
            color: #000;
            line-height: 1.1;
            word-break: keep-all;
            text-align: center;
        `;
        container.appendChild(textDiv);

        // 폰트 크기 자동 조절
        const imageWidth = image.offsetWidth;
        let fontSize = 6; // pt 단위
        textDiv.style.fontSize = `${fontSize}pt`;

        // 텍스트 너비가 이미지 너비보다 크면 폰트 크기를 줄임
        while (textDiv.scrollWidth > imageWidth && fontSize > 4) {
            fontSize -= 0.5;
            textDiv.style.fontSize = `${fontSize}pt`;
        }
    }

    // [수정] 미리보기 영역에 마크(이미지+텍스트) 추가 및 드래그
    function setRecyclingMark(markValue, auto = false) {
        const markObj = recyclingMarkMap[markValue];
        const previewContent = document.getElementById('previewContent');
        if (!previewContent || !markObj) return;

        // 컨테이너를 찾거나 새로 생성
        let container = document.getElementById('recyclingMarkContainer');
        if (container) container.remove(); // 기존 컨테이너가 있으면 제거하고 새로 생성

        container = document.createElement('div');
        container.id = 'recyclingMarkContainer';
        container.style.position = 'absolute';
        container.style.width = '60px'; // 컨테이너 너비 고정
        container.style.cursor = 'move';
        container.style.textAlign = 'center';
        
        // 컨테이너 내부에 이미지와 텍스트 영역 추가
        container.innerHTML = `
            <img id="recyclingMarkImage" style="width: 100%; height: auto; display: block;">
        `;
        previewContent.appendChild(container);

        const img = container.querySelector('#recyclingMarkImage');

        // 이미지 설정
        if (markObj.img) {
            img.src = markObj.img;
            img.alt = markObj.label;
            img.style.display = 'block';
        } else {
            img.style.display = 'none';
        }

        // [수정] 자동 위치 설정: 제품명 행의 우측 상단에 배치
        const thElements = previewContent.querySelectorAll('th');
        let productNameRow = null;
        thElements.forEach(th => {
            if (th.textContent.trim() === '제품명') {
                productNameRow = th.parentElement; // <tr> element
            }
        });

        if (productNameRow) {
            const previewRect = previewContent.getBoundingClientRect();
            const rowRect = productNameRow.getBoundingClientRect();
            
            // 제품명 행의 상단에 맞춤
            const topPosition = rowRect.top - previewRect.top;
            
            container.style.top = `${topPosition}px`;
            container.style.right = '25px'; // 우측 여백
            container.style.left = '';
            container.style.bottom = '';
        } else {
            // 제품명 행을 찾지 못할 경우의 기본 위치 (예: 우측 하단)
            container.style.right = '20px';
            container.style.bottom = '20px';
            container.style.left = '';
            container.style.top = '';
        }

        // 드래그 로직 (컨테이너에 적용)
        container.onmousedown = function(e) {
            e.preventDefault();
            let shiftX = e.clientX - container.getBoundingClientRect().left;
            let shiftY = e.clientY - container.getBoundingClientRect().top;
            
            function moveAt(pageX, pageY) {
                const rect = previewContent.getBoundingClientRect();
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
    }

    // 미리보기 스타일 업데이트
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
            overflow: visible;
            box-sizing: border-box;
            word-break: break-all;
            white-space: normal;
        `;

        const table = previewContent.querySelector('.preview-table');
        if (table) {
            table.style.cssText = `
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                margin: 0;
                word-break: break-all;
                white-space: normal;
            `;
        }

        const baseTextStyle = `
            font-size: ${settings.fontSize}pt;
            font-family: ${settings.fontFamily};
            letter-spacing: ${settings.letterSpacing / 100}em;
            line-height: ${settings.lineHeight};
            word-break: break-all;
            white-space: normal;
        `;

        const cells = previewContent.querySelectorAll('th, td');
        cells.forEach(cell => {
            cell.style.cssText = `
                ${baseTextStyle}
                padding: 4px 8px;
                border: 1px solid #dee2e6;
                vertical-align: middle;
                word-break: break-all;
                overflow-wrap: break-word;
                text-align: left;
                white-space: normal;
            `;
            if (cell.tagName === 'TH') {
                cell.style.backgroundColor = '#f8f9fa';
                cell.style.textAlign = 'center';
                cell.style.fontWeight = '500';
                cell.style.whiteSpace = 'nowrap';
                cell.style.textOverflow = 'ellipsis';
                cell.style.overflow = 'hidden';
                cell.style.width = '100px';
                cell.style.minWidth = '100px';
                cell.style.maxWidth = '100px';
            }
        });

        const headerText = previewContent.querySelector('.header-text');
        if (headerText) {
            headerText.style.cssText = `
                ${baseTextStyle}
                margin: 0;
                line-height: 1.2;
                font-weight: bold;
                color: #fff;
                text-align: left;
            `;
        }

        requestAnimationFrame(() => {
            const contentHeight = previewContent.scrollHeight;
            const cmHeight = Math.ceil(contentHeight / 37.8);
            document.getElementById('heightInput').value = cmHeight;
            updateArea();
        });
    }

    // 이벤트 리스너 설정
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

        const resetButton = document.querySelector('button[onclick="resetSettings()"]');
        if (resetButton) {
            resetButton.onclick = null;
            resetButton.addEventListener('click', resetSettings);
        }

        const validateButton = document.getElementById('validateButton');
        if (validateButton) {
            validateButton.addEventListener('click', validateSettings);
        }
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

    // 면적 계산
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

    // 영양성분 데이터 처리 - 개선된 오류 처리
    try {
        console.log('🔍 영양성분 데이터 처리 시작');
        const nutritionDataRaw = document.getElementById('nutrition-data')?.textContent;
        
        if (!nutritionDataRaw) {
            console.warn('⚠️ 영양성분 데이터가 없습니다');
            return;
        }
        
        console.log('📄 영양성분 원시 데이터 길이:', nutritionDataRaw.length);
        console.log('📄 영양성분 원시 데이터 샘플:', nutritionDataRaw.substring(0, 100));
        
        const nutritionData = JSON.parse(nutritionDataRaw);
        console.log('✅ 영양성분 데이터 파싱 성공:', nutritionData);
        
        // 기본값 보장
        if (!nutritionData.nutrients || Object.keys(nutritionData.nutrients).length === 0) {
            console.log('🔧 기본 영양성분 데이터 설정');
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
        
        // 서빙 사이즈 표시 업데이트
        if (nutritionData.serving_size && nutritionData.serving_size_unit) {
            const servingSizeElement = document.getElementById('servingSizeDisplay');
            if (servingSizeElement) {
                servingSizeElement.value = `${nutritionData.serving_size}${nutritionData.serving_size_unit}`;
                console.log('✅ 서빙 사이즈 설정:', servingSizeElement.value);
            } else {
                console.warn('⚠️ servingSizeDisplay 요소를 찾을 수 없습니다');
            }
        }
        
        // 추가 영양성분 정보 설정
        if (nutritionData.units_per_package) {
            const servingsElement = document.getElementById('servingsPerPackageDisplay');
            if (servingsElement) {
                servingsElement.value = nutritionData.units_per_package;
            }
        }
        
        if (nutritionData.display_unit) {
            const displayUnitElement = document.getElementById('nutritionDisplayUnit');
            if (displayUnitElement) {
                displayUnitElement.value = nutritionData.display_unit;
            }
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
        console.log('✅ 영양성분 데이터 로드 완료 (탭 전환 시 표시됨)');
    } catch (e) {
        console.error('❌ 영양성분 데이터 처리 중 오류:', e);
        console.log('🔄 백업 데이터 로드 시도...');
        
        // 오류 발생 시 백업 로직: DOM에서 직접 데이터 추출
        try {
            const backupData = {
                serving_size: document.getElementById('serving_size')?.value || '100',
                serving_size_unit: document.getElementById('serving_size_unit')?.value || 'g',
                units_per_package: document.getElementById('units_per_package')?.value || '1',
                display_unit: document.getElementById('nutrition_display_unit')?.value || 'unit',
                nutrients: {
                    calorie: { value: document.getElementById('calories')?.value || '0', unit: 'kcal' },
                    natrium: { value: document.getElementById('natriums')?.value || '0', unit: 'mg' },
                    carbohydrate: { value: document.getElementById('carbohydrates')?.value || '0', unit: 'g' },
                    sugar: { value: document.getElementById('sugars')?.value || '0', unit: 'g' },
                    afat: { value: document.getElementById('fats')?.value || '0', unit: 'g' },
                    transfat: { value: document.getElementById('trans_fats')?.value || '0', unit: 'g' },
                    satufat: { value: document.getElementById('saturated_fats')?.value || '0', unit: 'g' },
                    cholesterol: { value: document.getElementById('cholesterols')?.value || '0', unit: 'mg' },
                    protein: { value: document.getElementById('proteins')?.value || '0', unit: 'g' }
                }
            };
            
            console.log('✅ 백업 데이터 로드 성공:', backupData);
            
            // 백업 데이터로 UI 업데이트 시도
            const servingSizeElement = document.getElementById('servingSizeDisplay');
            if (servingSizeElement) {
                servingSizeElement.value = `${backupData.serving_size}${backupData.serving_size_unit}`;
            }
            
        } catch (backupError) {
            console.error('❌ 백업 데이터 로드도 실패:', backupError);
        }
        
        // 백업 데이터 로드 완료
        console.log('✅ 백업 영양성분 데이터 로드 완료 (탭 전환 시 표시됨)');
    }

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
        
        console.log('✅ 초기 탭 상태 설정 완료 - 표시사항 탭 표시');
    }
    
    // 초기화 실행
    initializeTabState();
    handleTabSwitch();

    // 체크된 필드 렌더링
    const FIELD_LABELS = {
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

    // 필드 데이터 저장소
    let checkedFields = {};
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


    // 국가명 볼드 처리 함수
    function boldCountryNames(text, countryList) {
        if (!text || !countryList) return text;
        
        let processedText = text;
        
        // 국가명 목록을 길이 순으로 정렬 (긴 이름부터 처리하여 중복 매칭 방지)
        const sortedCountries = countryList.sort((a, b) => b.length - a.length);
        
        sortedCountries.forEach(country => {
            if (!country) return;
            
            // 국가명과 선택적으로 뒤따르는 " 산" 또는 "산"을 매칭하는 정규식
            // 예: "호주" -> "호주산", "호주 산" / "미국" -> "미국산", "미국 산"
            const escapedCountry = country.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${escapedCountry}(\\s*산)?)`, 'gi');
            // $1은 전체 매칭된 부분(예: "호주산")을 참조
            processedText = processedText.replace(regex, '<strong>$1</strong>');
        });
        
        return processedText;
    }

    // 국가명 목록 초기화 (페이지 로드 시) - 먼저 선언
    let countryList = [];
    const countryListScript = document.getElementById('country-list-data');
    if (countryListScript) {
        try {
            const countryListText = countryListScript.textContent;
            countryList = JSON.parse(countryListText);
        } catch (e) {
            console.error('국가명 목록 파싱 오류:', e);
            countryList = [];
        }
    }

    // 입력 데이터 반영 (테스트용)
    window.addEventListener('message', function(e) {
        if (e.data?.type === 'previewCheckedFields' && e.data.checked) {
            dataLoaded = true; // 데이터 로딩 성공 플래그 설정
            checkedFields = e.data.checked;
            // const tbody = document.getElementById('previewTableBody'); // 상단에서 이미 정의됨
            if (!tbody) return;

            tbody.innerHTML = ''; // 로딩 또는 에러 메시지 제거
            Object.entries(checkedFields).forEach(([field, value]) => {
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
                            overflow: hidden;
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
                            allergenDiv.style.cssText = `
                                background-color: #000 !important;
                                color: #fff !important;
                                padding: 4px 8px;
                                font-size: 9pt;
                                font-weight: bold;
                                text-align: center;
                                margin-top: 8px;
                                display: inline-block;
                                float: right;
                                clear: both;
                                border-radius: 2px;
                            `;
                            container.appendChild(allergenDiv);
                        }

                        // GMO 성분 표시
                        if (gmoMatch) {
                            const gmo = gmoMatch[1].trim();
                            const gmoDiv = document.createElement('div');
                            gmoDiv.textContent = `${gmo}(GMO)`;
                            gmoDiv.style.cssText = `
                                background-color: #000 !important;
                                color: #fff !important;
                                padding: 4px 8px;
                                font-size: 9pt;
                                font-weight: bold;
                                text-align: center;
                                margin-top: 8px;
                                display: inline-block;
                                float: right;
                                clear: both;
                                border-radius: 2px;
                            `;
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

            // 테이블 내용 생성 후 스타일 즉시 적용 (레이아웃 깨짐 방지)
            updatePreviewStyles();

            // 포장재질 기반 추천
            const frmlc = checkedFields.frmlc_mtrqlt || '';
            renderRecyclingMarkUI();
            updateRecyclingMarkUI(frmlc);
        }
    });

    // 설정 저장
    function savePreviewSettings() {
        const labelId = document.querySelector('input[name="label_id"]')?.value;
        if (!labelId) {
            console.warn('label_id를 찾을 수 없습니다.');
            return;
        }

        // 분리배출마크 정보 수집
        const recyclingMarkInfo = getCurrentRecyclingMarkInfo();

        const data = {
            label_id: labelId,
            layout: document.getElementById('layoutSelect').value || 'vertical',
            width: parseFloat(document.getElementById('widthInput').value) || 10,
            length: parseFloat(document.getElementById('heightInput').value) || 10,
            font: document.getElementById('fontFamilySelect').value || "'Noto Sans KR'",
            font_size: parseFloat(document.getElementById('fontSizeInput').value) || 10,
            letter_spacing: parseInt(document.getElementById('letterSpacingInput').value) || -5,
            line_spacing: parseFloat(document.getElementById('lineHeightInput').value) || 1.2,
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

    // 저장된 미리보기 설정 로드
    function loadSavedPreviewSettings() {
        try {
            const settingsScript = document.getElementById('preview-settings-data');
            if (!settingsScript) return;
            
            const settings = JSON.parse(settingsScript.textContent);
            const recyclingMark = settings.recycling_mark;
            
            // 분리배출마크 설정 복원
            if (recyclingMark && recyclingMark.enabled && recyclingMark.type) {
                // 분리배출마크 UI가 완전히 로드된 후 실행되도록 더 긴 딜레이 적용
                setTimeout(() => {
                    restoreRecyclingMark(recyclingMark);
                }, 1500); // 1.5초 딜레이로 증가
            }
        } catch (error) {
            console.error('저장된 설정 로드 중 오류:', error);
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
                    addTextToRecyclingMark(markData.text);
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
        const textElement = markElement.querySelector('.recycling-text');
        
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

    // 농수산물 목록
    const farmSeafoodItems = [
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

    // 사용금지 문구
    const forbiddenPhrases = ['천연', '자연', '슈퍼', '생명'];

    // [수정] 제품명 성분 표시 검증 로직 (checkFarmSeafoodCompliance)
    function checkFarmSeafoodCompliance() {
        const errors = [];
        const productName = checkedFields.prdlst_nm || '';
        const ingredientInfo = checkedFields.ingredient_info || '';

        // 제품명에 포함된 농수산물명 추출 (긴 이름부터 처리하여 '돼지고기'가 '고기'보다 먼저 잡히도록 함)
        const foundItems = farmSeafoodItems
            .filter(item => productName.includes(item))
            .sort((a, b) => b.length - a.length);

        if (foundItems.length === 0) {
            return { errors: [], suggestions: [] }; // 검증 대상이 없으면 종료
        }

        foundItems.forEach(item => {
            // '특정성분 함량' 필드에 해당 성분명과 함량(%)이 모두 포함되어 있는지 확인
            // 정규식: 성분명 + (0개 이상의 문자, 단 쉼표 제외) + 숫자 + %
            // 예: "사과 100%", "사과(국산) 100%" 모두 통과
            const complianceRegex = new RegExp(`${item}[^,]*\\d+(\\.\\d+)?\\s*%`);
            
            // 검증 실패 시 오류 추가
            if (!complianceRegex.test(ingredientInfo)) {
                errors.push(`제품명에 사용된 '${item}'의 함량을 '특정성분 함량' 항목에 표시하세요 (예: ${item} 100%).`);
            }
        });

        return { errors, suggestions: [] };
    }

    // 2. 알레르기 성분 중복: 중복된 성분을 모두 한 줄에 표시
    function checkAllergenDuplication() {
        const errors = [];
        const suggestions = [];
        const rawmtrl = checkedFields.rawmtrl_nm_display || '';
        const cautions = checkedFields.cautions || '';
        const allergenMatch = rawmtrl.match(/\[알레르기 성분\s*:\s*([^\]]+)\]/i);
        if (allergenMatch) {
            const allergens = allergenMatch[1].split(',').map(a => a.trim().toLowerCase());
            const cautionsLower = cautions.toLowerCase();
            const finalDuplicatedMessages = [];

            // 일반 알레르기 성분 및 '알류' 포함하여 한번에 검사
            allergens.forEach(allergen => {
                if (allergen === '알류') {
                    const eggRelatedTerms = ['알류', '난류', '계란', '메츄리알', '오리알', '달걀'];
                    const foundEggTerms = eggRelatedTerms.filter(term => cautionsLower.includes(term));
                    
                    if (foundEggTerms.length > 0) {
                        finalDuplicatedMessages.push(`알류(${foundEggTerms.join(', ')})`);
                    }
                } else {
                    if (cautionsLower.includes(allergen)) {
                        finalDuplicatedMessages.push(allergen);
                    }
                }
            });

            if (finalDuplicatedMessages.length > 0) {
                errors.push(`주의사항에 원재료명의 알레르기 성분이 중복 표시되었습니다: ${finalDuplicatedMessages.join(', ')}`);
            }
        }
        return { errors, suggestions };
    }

    // 3. 냉동식품 문구 및 온도, 보관조건, 필수 문구 통합
    function checkFoodTypePhrasesUnified() {
        const errors = [];
        const suggestions = [];
        const storageMethod = (checkedFields.storage_method || '').trim();
        const foodType      = (checkedFields.prdlst_dcnm || '').trim();
        const cautions      = (checkedFields.cautions || '').trim();
        const additional    = (checkedFields.additional_info || '').trim();

        // --- 신규 검증 로직 ---

        // 1. 냉동 조건 검증
        const isFrozenStorage = (() => {
            if (storageMethod.includes('냉동')) return true;
            const tempRegex = /(-?\d+(\.\d+)?)\s*(℃|도)/g;
            let match;
            while ((match = tempRegex.exec(storageMethod)) !== null) {
                const tempValue = parseFloat(match[1]);
                if (!isNaN(tempValue) && tempValue <= -18) {
                    return true; // -18도 이하 온도가 있으면 냉동으로 간주
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
                const startTemp = parseFloat(match[1]);
                const endTemp = parseFloat(match[3]);
                // 0~10도 범위 내의 온도이면 냉장으로 간주
                if (!isNaN(startTemp) && !isNaN(endTemp) && startTemp >= 0 && endTemp <= 10) {
                    return true;
                }
            }
            return false;
        })();

        if (isRefrigeratedStorage) {
            const combinedText = cautions + additional;
            // '개봉' 키워드와 ('냉장' 또는 '빨리' 또는 '빠른 시일') 키워드가 모두 있어야 통과
            const hasOpeningKeyword = combinedText.includes('개봉') || combinedText.includes('구매') || combinedText.includes('구입');
            const hasStorageKeyword = combinedText.includes('냉장') || combinedText.includes('섭취') || combinedText.includes('취식');

            if (!(hasOpeningKeyword && hasStorageKeyword)) {
                errors.push('냉장 보관 제품은 주의사항 또는 기타표시사항에 "개봉/구매 후 냉장 보관 및 빠른 섭취/취식" 관련 문구를 포함해야 합니다.');
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
            case '플라스틱(PET)':
                // [수정] '무색페트' 또는 'PET' 선택 시, 'pet' 또는 '페트'가 포함되면 통과
                compatible = isCompatible(selectedMark, ['pet', '페트']);
                break;
            case '플라스틱(LDPE)':
            case '플라스틱(HDPE)':
                // LDPE 또는 HDPE 선택 시, '폴리에틸렌' 또는 'pe'가 포함되면 통과
                compatible = isCompatible(selectedMark, ['ldpe', 'hdpe', '폴리에틸렌', 'pe']);
                break;
            case '플라스틱(PP)':
                compatible = isCompatible(selectedMark, ['pp', '피피', '폴리프로필렌']);
                break;
            case '플라스틱(PS)':
                compatible = isCompatible(selectedMark, ['ps', '피에스', '폴리스티렌']);
                break;
            case '캔류(철)':
                compatible = isCompatible(selectedMark, ['철', 'steel']);
                break;
            case '캔류(알미늄)':
                compatible = isCompatible(selectedMark, ['알미늄', '알루미늄', 'aluminum', 'al']);
                break;
            case '종이':
                compatible = isCompatible(selectedMark, ['종이', 'paper']);
                break;
            case '유리':
                compatible = isCompatible(selectedMark, ['유리', 'glass']);
                break;
            case '일반팩':
                compatible = packageMaterial.includes('팩') && !packageMaterial.includes('멸균');
                break;
            case '멸균팩':
                compatible = packageMaterial.includes('멸균');
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
        const isFrozen = storageMethod.toLowerCase().includes('냉동') || foodType.toLowerCase().includes('냉동');
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

    async function validateSettings() {
        const width = parseFloat(document.getElementById('widthInput').value) || 0;
        const height = parseFloat(document.getElementById('heightInput').value) || 0;
        const area = width * height;
        const fontSize = parseFloat(document.getElementById('fontSizeInput').value) || 10;
        const packageMaterial = (checkedFields.frmlc_mtrqlt || '');
        const select = document.getElementById('recyclingMarkSelect');
        const selectedMark = select ? select.value : '';
        const recommendedMark = recommendRecyclingMarkByMaterial(packageMaterial);

        // 캐시된 결과가 있으면 재사용(표시면 면적, 글꼴 크기, 분리배출마크 제외)
        let cached = cachedValidation;
        let now = Date.now();
        let useCache = false;
        if (
            cached &&
            cached._cacheTime &&
            // 표시면 면적, 글꼴 크기, 분리배출마크 관련 값이 변하지 않았으면 캐시 사용
            cached._width === width &&
            cached._height === height &&
            cached._fontSize === fontSize &&
            cached._selectedMark === selectedMark &&
            cached._recommendedMark === recommendedMark
        ) {
            useCache = true;
        }

        // 검증 항목 순서 및 매핑
        const validationItems = [
            {
                label: '표시면 면적',
                check: () => ({
                    ok: area >= 40,
                    errors: area < 40 ? [
                        `<strong style="color:#222;">표시면 면적은 최소 40cm² 이상이어야 합니다 («식품 등의 표시기준» 제4조).</strong>`
                    ] : [],
                    suggestions: area < 40 ? [
                        `<strong style="color:#222;">면적을 40cm² 이상으로 조정하세요.</strong>`
                    ] : []
                }),
                always: true
            },
            {
                label: '글꼴 크기',
                check: () => ({
                    ok: fontSize >= REGULATIONS.font_size.general.min,
                    errors: fontSize < REGULATIONS.font_size.general.min ? [
                        `<strong style="color:#222;">글꼴 크기는 최소 ${REGULATIONS.font_size.general.min}pt 이상이어야 합니다 («식품 등의 표시기준» 제6조).</strong>`
                    ] : [],
                    suggestions: fontSize < REGULATIONS.font_size.general.min ? [
                        `<strong style="color:#222;">글꼴 크기를 ${REGULATIONS.font_size.general.min}pt 이상으로 조정하세요.</strong>`
                    ] : []
                }),
                always: true
            },
            {
                label: '제품명 성분 표시',
                check: () => {
                    const result = checkFarmSeafoodCompliance();
                    result.errors = (result.errors || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    result.suggestions = (result.suggestions || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    return result;
                }
            },
            {
                label: '필수 문구',
                check: () => {
                    const result = checkFoodTypePhrasesUnified();
                    result.errors = (result.errors || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    result.suggestions = (result.suggestions || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    return result;
                }
            },
            {
                label: '사용금지 문구',
                check: () => checkForbiddenPhrases()
            },
            {
                label: '알레르기 중복 표시',
                check: () => {
                    const result = checkAllergenDuplication();
                    result.errors = (result.errors || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    result.suggestions = (result.suggestions || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    return result;
                }
            },
            {
                label: '분리배출마크',
                check: () => {
                    const result = checkRecyclingMarkCompliance();
                    result.errors = (result.errors || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    result.suggestions = (result.suggestions || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    return result;
                },
                always: true
            },
            {
                label: '소비기한',
                check: () => {
                    const result = checkExpiryCompliance();
                    result.errors = (result.errors || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    result.suggestions = (result.suggestions || []).map(e => `<strong style="color:#222;">${e}</strong>`);
                    return result;
                }
            }
        ];

        // 캐시가 있으면 표시면 면적/글꼴 크기/분리배출마크만 새로 계산, 나머지는 캐시 사용
        let results = [];
        if (useCache) {
            for (let i = 0; i < validationItems.length; i++) {
                const item = validationItems[i];
                if (item.always) {
                    results.push(item.check());
                } else {
                    results.push(cached.results[i]);
                }
            }
        } else {
            results = validationItems.map(item => item.check());
            // 캐시 저장(항상 새로 계산되는 항목 값도 저장)
            cachedValidation = {
                _cacheTime: Date.now(),
                _width: width,
                _height: height,
                _fontSize: fontSize,
                _selectedMark: selectedMark,
                _recommendedMark: recommendedMark,
                results
            };
        }

        const modal = showValidationModal();
        const tbody = modal.querySelector('#validationResultBody');
        tbody.innerHTML = '';

        // 입력 필드 상태 초기화
        [
            'widthInput','heightInput','fontSizeInput','letterSpacingInput','lineHeightInput',
            'recyclingMarkSelect','ingredient_info','country_of_origin','prdlst_nm',
            'rawmtrl_nm_display','cautions','additional_info','storage_method','pog_daycnt'
        ].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.remove('is-valid','is-invalid');
            }
        });

        let hasErrors = false;

        // tbody에 모든 검증 항목을 한 번에 추가 (tr을 누적해서 innerHTML로 할당)
        let rowsHtml = '';
        for (let i = 0; i < validationItems.length; i++) {
            const item = validationItems[i];
            const result = results[i];

            rowsHtml += `<tr>`;

            // 항목명
            rowsHtml += `<td>${item.label}</td>`;

            // 결과
            if (!result.errors || result.errors.length === 0) {
                rowsHtml += `<td><span class="text-success">적합</span></td>`;
            } else {
                rowsHtml += `<td><span class="text-danger">재검토</span></td>`;
                hasErrors = true;
            }

            // 에러/수정제안
            let msg = '';
            if (result.errors && result.errors.length > 0) msg += result.errors.join('<br>');
            if (result.suggestions && result.suggestions.length > 0) {
                if (msg) msg += ' | ';
                msg += result.suggestions.join('<br>');
            }
            rowsHtml += `<td>${msg}</td>`;

            rowsHtml += `</tr>`;
        }
        tbody.innerHTML = rowsHtml;

        // 입력 필드에 유효/비유효 클래스 추가 (간단화)
        [
            'widthInput','heightInput','fontSizeInput','letterSpacingInput','lineHeightInput',
            'recyclingMarkSelect','ingredient_info','country_of_origin','prdlst_nm',
            'rawmtrl_nm_display','cautions','additional_info','storage_method','pog_daycnt'
        ].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (hasErrors) element.classList.remove('is-valid');
                else element.classList.add('is-valid');
            }
        });

        return !hasErrors;
    }

    // PDF 저장
    async function exportToPDF() {
        try {
            const { jsPDF } = window.jspdf;
            const previewContent = document.getElementById('previewContent');
            if (!previewContent) {
                alert('미리보기 내용을 찾을 수 없습니다.');
                return;
            }

            // 현재 설정된 가로/세로 길이 가져오기
            const width = parseFloat(document.getElementById('widthInput').value) || 10;
            const height = parseFloat(document.getElementById('heightInput').value) || 11;
            
            // cm를 pt로 변환 (1cm = 28.35pt)
            const widthPt = width * 28.35;
            const heightPt = height * 28.35;

            // html2canvas 옵션 설정
            const canvas = await html2canvas(previewContent, {
                scale: 3, // 고해상도를 위해 스케일 증가
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#ffffff',
                width: previewContent.scrollWidth,
                height: previewContent.scrollHeight,
                scrollX: 0,
                scrollY: 0,
                logging: false // 로깅 비활성화
            });

            const imgData = canvas.toDataURL('image/png');
            
            // PDF 생성 (가로, 세로 방향 및 단위, 크기 설정)
            const orientation = widthPt > heightPt ? 'l' : 'p'; // 가로가 길면 landscape
            const pdf = new jsPDF(orientation, 'pt', [widthPt, heightPt]);

            // PDF에 이미지 추가 (이미지를 PDF 크기에 맞춤)
            pdf.addImage(imgData, 'PNG', 0, 0, widthPt, heightPt);

            // 파일명 생성
            const today = new Date();
            const year = today.getFullYear().toString();
            const month = (today.getMonth() + 1).toString().padStart(2, '0');
            const day = today.getDate().toString().padStart(2, '0');
            const dateStr = `${year}${month}${day}`;
            
            // 제품명 가져오기 (checkedFields에서)
            const productName = (checkedFields.prdlst_nm || '').trim();
            
            // 파일명 구성: 한글표시사항_제품명_연월일
            let fileName = '한글표시사항';
            
            if (productName) {
                fileName += `_${productName}`;
            }
            
            fileName += `_${dateStr}.pdf`;
            
            // 파일명에서 특수문자 제거 (파일시스템에서 허용되지 않는 문자들)
            fileName = fileName.replace(/[<>:"/\\|?*]/g, '_');

            // PDF 저장
            pdf.save(fileName);

        } catch (error) {
            console.error('PDF 저장 중 오류:', error);
            alert('PDF 저장 중 오류가 발생했습니다: ' + error.message);
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

        const displayUnit = data.displayUnit || 'unit';
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

        const tabMapShort = {
            total: `총 내용량`,
            unit: `단위내용량`,
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
        
        // 현재 영양성분 탭이 활성화되어 있을 때만 표시
        const activeTab = document.querySelector('.nav-link.active[data-bs-toggle="tab"]');
        if (activeTab && activeTab.getAttribute('data-bs-target') === '#nutrition-tab') {
            nutritionPreview.style.display = 'block';
            console.log('✅ 영양성분 탭이 활성화되어 있어 영양성분 표시');
        } else {
            nutritionPreview.style.display = 'none';
            console.log('ℹ️ 영양성분 탭이 비활성화되어 있어 영양성분 숨김');
        }
    }

    // 영양성분 데이터 수신
    window.addEventListener('message', function(e) {
        if (e.data?.type === 'nutritionData') {
            const data = e.data.data;
            window.nutritionData = data;
            document.getElementById('servingSizeDisplay').value = 
                `${comma(data.servingSize)}${data.servingUnit}`;
            document.getElementById('servingsPerPackageDisplay').value = 
                `${comma(data.servingsPerPackage)}${data.servingUnitText}`;
            document.getElementById('nutritionDisplayUnit').value = data.displayUnit;
            const naviTab = document.querySelector('[data-bs-target="#nutrition-tab"]');
            const tabInstance = new bootstrap.Tab(naviTab);
            tabInstance.show();
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
        const contentHeight = table.offsetHeight + 80;
        const totalHeight = contentHeight / 28.35;
        const heightInput = document.getElementById('heightInput');
        heightInput.value = Math.ceil(totalHeight);
        updateArea();
    }

    // 초기화
    setupEventListeners();
    // 최초 로드시에도 고정 사이즈 및 th 사이즈 적용
    updatePreviewStyles();
    setTimeout(updatePreviewStyles, 100);
    setTimeout(updatePreviewStyles, 500); // 추가로 한번 더 실행
    setupAreaCalculation();
    setTimeout(updateArea, 100);
    enforceInputMinMax();
    
    // 저장된 설정 로드
    loadSavedPreviewSettings();
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', exportToPDF);
    }
    
    // 설정 저장 버튼 이벤트 추가
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', savePreviewSettings);
    }
    
    const widthInput = document.getElementById('widthInput');
    if (widthInput) widthInput.addEventListener('change', calculateHeight);
    const fontSizeInput = document.getElementById('fontSizeInput');
    if (fontSizeInput) fontSizeInput.addEventListener('change', calculateHeight);
    const letterSpacingInput = document.getElementById('letterSpacingInput');
    if (letterSpacingInput) letterSpacingInput.addEventListener('change', calculateHeight);
    const lineHeightInput = document.getElementById('lineHeightInput');
    if (lineHeightInput) lineHeightInput.addEventListener('change', calculateHeight);
    window.addEventListener('load', calculateHeight);
    
    // DOM 요소들의 존재 여부 확인 및 초기화
    console.log('🔍 DOM 요소 존재 여부 확인');
    const criticalElements = [
        'nutrition-data',
        'country-mapping-data', 
        'expiry-recommendation-data',
        'nutritionPreview',
        'servingSizeDisplay',
        'servingsPerPackageDisplay',
        'nutritionDisplayUnit'
    ];
    
    criticalElements.forEach(elementId => {
        const element = document.getElementById(elementId);
        if (element) {
            console.log(`✅ ${elementId}: 존재함`);
        } else {
            console.warn(`⚠️ ${elementId}: 찾을 수 없음`);
        }
    });
    
    // 초기화 완료 표시
    console.log('🎉 미리보기 페이지 초기화 완료');
    
    // 페이지 로드 후 탭 상태 확인
    setTimeout(() => {
        console.log('🔄 지연 후 탭 상태 재검사');
        const activeTab = document.querySelector('.nav-link.active');
        if (activeTab) {
            console.log('✅ 활성 탭:', activeTab.textContent.trim());
            console.log('✅ 탭 타겟:', activeTab.getAttribute('data-bs-target'));
        } else {
            console.warn('⚠️ 활성 탭을 찾을 수 없음');
        }
        
        // 현재 영양성분 표시 상태 확인
        const nutritionPreview = document.getElementById('nutritionPreview');
        if (nutritionPreview) {
            console.log('ℹ️ 영양성분 표시 상태:', nutritionPreview.style.display);
        }
    }, 1000);

});