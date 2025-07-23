document.addEventListener('DOMContentLoaded', function () {
    // 디버깅 데이터 로드 확인
    console.log("Checking data elements...");
    try {
        const nutritionItems = document.getElementById('nutrition-data')?.textContent;
        console.log("Nutrition items:", nutritionItems ? JSON.parse(nutritionItems) : null);
    } catch (error) {
        console.error("Error parsing data:", error);
    }

    // 작성일시 정보 설정
    const updateDateTime = document.getElementById('update_datetime')?.value;
    const footerText = document.querySelector('.footer-text');
    if (footerText && updateDateTime) {
        footerText.innerHTML = `
            간편한 표시사항 연구소에서 관련 법규에 따라 작성되었습니다.
            <span class="creator-info">[${updateDateTime}]</span>
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
        for (const group of recyclingMarkGroups) {
            for (const opt of group.options) {
                const base = opt.label.replace(/\(.+\)/, '').toLowerCase();
                if (text.includes(base) || text.includes(opt.label.toLowerCase())) {
                    return opt.value;
                }
            }
        }
        if (text.includes('pet')) return '플라스틱(PET)';
        if (text.includes('hdpe')) return '플라스틱(HDPE)';
        if (text.includes('ldpe')) return '플라스틱(LDPE)';
        if (text.includes('pp')) return '플라스틱(PP)';
        if (text.includes('ps')) return '플라스틱(PS)';
        if (text.includes('철')) return '캔류(철)';
        if (text.includes('알미늄') || text.includes('알루미늄')) return '캔류(알미늄)';
        if (text.includes('종이')) return '종이';
        if (text.includes('유리')) return '유리';
        if (text.includes('팩') && text.includes('멸균')) return '멸균팩';
        if (text.includes('팩')) return '일반팩';
        if (text.includes('도포') || text.includes('첩합') || text.includes('코팅')) return '도포첩합';
        return null;
    }

    // 분리배출마크 UI 생성 및 삽입
    function renderRecyclingMarkUI() {
        const contentTab = document.querySelector('#content-tab .settings-group');
        if (!contentTab) return;
        if (document.getElementById('recyclingMarkUiBox')) return;

        const uiBox = document.createElement('div');
        uiBox.id = 'recyclingMarkUiBox';
        uiBox.className = 'settings-row';
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
            </div>
        `;
        contentTab.appendChild(uiBox);

        // 셀렉트박스 변경 이벤트
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
                const previewContent = document.getElementById('previewContent');
                let img = document.getElementById('recyclingMarkImage');
                if (addBtn.textContent === '적용') {
                    setRecyclingMark(markValue);
                    addBtn.textContent = '해제';
                    addBtn.classList.remove('btn-outline-primary');
                    addBtn.classList.add('btn-danger');
                } else {
                    if (img) img.remove();
                    addBtn.textContent = '적용';
                    addBtn.classList.remove('btn-danger');
                    addBtn.classList.add('btn-outline-primary');
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

    // 미리보기 영역에 마크 추가 및 드래그
    function setRecyclingMark(markValue, auto = false) {
        const markObj = recyclingMarkMap[markValue] || recyclingMarkGroups[0].options[0];
        const previewContent = document.getElementById('previewContent');
        if (!previewContent) return;

        let img = document.getElementById('recyclingMarkImage');
        if (!markObj.img) {
            if (img) img.remove();
            return;
        }

        if (!img) {
            img = document.createElement('img');
            img.id = 'recyclingMarkImage';
            img.style.position = 'absolute';
            img.style.right = '20px';
            img.style.bottom = '20px';
            img.style.width = '48px';
            img.style.height = '48px';
            img.style.cursor = 'move';
            previewContent.appendChild(img);
        }

        img.src = markObj.img;
        img.alt = markObj.label;
        img.title = markObj.label;
        img.style.display = 'block';

        if (auto) {
            img.style.right = '20px';
            img.style.bottom = '20px';
        }

        // 드래그 로직
        img.onmousedown = function(e) {
            e.preventDefault();
            let shiftX = e.clientX - img.getBoundingClientRect().left;
            let shiftY = e.clientY - img.getBoundingClientRect().top;
            function moveAt(pageX, pageY) {
                const rect = previewContent.getBoundingClientRect();
                img.style.left = (pageX - rect.left - shiftX) + 'px';
                img.style.top = (pageY - rect.top - shiftY) + 'px';
                img.style.right = '';
                img.style.bottom = '';
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
        img.ondragstart = () => false;
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

    // 영양성분 데이터 처리
    try {
        const nutritionDataRaw = document.getElementById('nutrition-data')?.textContent;
        if (nutritionDataRaw) {
            const nutritionData = JSON.parse(nutritionDataRaw);
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
            }
            if (nutritionData.serving_size && nutritionData.serving_size_unit) {
                document.getElementById('servingSizeDisplay').value = `${nutritionData.serving_size}${nutritionData.serving_size_unit}`;
            }
            if (nutritionData.units_per_package) {
                document.getElementById('servingsPerPackageDisplay').value = nutritionData.units_per_package;
            }
            if (nutritionData.display_unit) {
                document.getElementById('nutritionDisplayUnit').value = nutritionData.display_unit;
            }
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
            document.getElementById('nutritionPreview').style.display = 'block';
        }
    } catch (e) {
        console.error('영양성분 데이터 파싱 오류:', e);
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
            console.log("Country list raw data:", countryListText); // 디버깅용
            countryList = JSON.parse(countryListText);
            console.log("Country list parsed:", countryList); // 디버깅용
        } catch (e) {
            console.error('국가명 목록 파싱 오류:', e);
            console.error('Raw content:', countryListScript.textContent);
            countryList = [];
        }
    }

    // 입력 데이터 반영 (테스트용)
    window.addEventListener('message', function(e) {
        if (e.data?.type === 'previewCheckedFields' && e.data.checked) {
            checkedFields = e.data.checked;
            const tbody = document.getElementById('previewTableBody');
            if (!tbody) return;

            tbody.innerHTML = '';
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
                        // 원산지 필드도 동일하게 국가명 볼드 처리
                        const processedOriginText = boldCountryNames(value, countryList);
                        td.innerHTML = processedOriginText
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/&lt;strong&gt;/g, '<strong>')
                            .replace(/&lt;\/strong&gt;/g, '</strong>');
                    } else {
                        // 다른 필드들도 국가명이 포함된 경우 볼드 처리
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
        if (!labelId) return;

        const data = {
            label_id: labelId,
            layout: document.getElementById('layoutSelect').value || 'vertical',
            width: parseFloat(document.getElementById('widthInput').value) || 10,
            length: parseFloat(document.getElementById('heightInput').value) || 10,
            font: document.getElementById('fontFamilySelect').value || "'Noto Sans KR'",
            font_size: parseFloat(document.getElementById('fontSizeInput').value) || 10,
            letter_spacing: parseInt(document.getElementById('letterSpacingInput').value) || -5,
            line_spacing: parseFloat(document.getElementById('lineHeightInput').value) || 1.2
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
            if (!res.success) {
                alert('미리보기 설정 저장 실패: ' + (res.error || ''));
            }
        })
        .catch(err => {
            alert('미리보기 설정 저장 에러: ' + err);
        });
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

    // 검증 헬퍼 함수들
    // 1. 농수산물 명칭은 제품명에서만 확인
    function checkFarmSeafoodCompliance() {
        const errors = [];
        const suggestions = [];
        const productName = checkedFields.prdlst_nm || '';
        const ingredientInfo = checkedFields.ingredient_info || '';
        const rawmtrlNm = checkedFields.rawmtrl_nm_display || '';

        // 제품명에 포함된 농수산물명 추출
        const foundItems = farmSeafoodItems.filter(item => productName.includes(item));

        // 특정성분 함량(ingredient_info)에서 각 농수산물명에 대해 % 포함 여부 확인
        let ingredientInfoMissing = false;
        foundItems.forEach(item => {
            // item을 포함하는 단어(예: 사과즙, 사과잼 등)도 모두 포함
            // 한글, 영문, 숫자, /, (, ), %, 공백 등 포함
            const regexWord = new RegExp(`${item}[\\w가-힣/()%··\\s-]*`, 'gi');
            let match;
            let foundAny = false;
            while ((match = regexWord.exec(ingredientInfo)) !== null) {
                foundAny = true;
                const word = match[0];
                // "사과즙 20%" 또는 "사과즙(국산) 20%" 등 다양한 형태 허용
                // 1. 함량(%) 포함 여부
                if (!/([0-9]+(\.[0-9]+)?\s*%)/.test(word)) {
                    ingredientInfoMissing = true;
                }
            }
            // ingredientInfo에 item을 포함하는 단어가 하나도 없으면, 기존 방식으로 검사
            if (!foundAny && ingredientInfo) {
                if (!new RegExp(`${item}\\s*([\\d.]+%)`).test(ingredientInfo)) {
                    ingredientInfoMissing = true;
                }
            }
        });

        // 특정성분 함량이 없거나, 제품명에 포함된 농수산물의 함량(%)이 모두 없는 경우
        if ((!ingredientInfo || ingredientInfoMissing) && rawmtrlNm && foundItems.length > 0) {
            errors.push(`주표시면에 제품명에 포함된 "${foundItems.join(', ')}"의 함량(%)을 추가하세요.`);
        } else {
            // 특정성분 함량에 농수산물별로 %가 없는 경우만 개별 메시지
            foundItems.forEach(item => {
                const regexWord = new RegExp(`${item}[\\w가-힣/()%··\\s-]*`, 'gi');
                let match;
                let foundAny = false;
                while ((match = regexWord.exec(ingredientInfo)) !== null) {
                    foundAny = true;
                    const word = match[0];
                    if (!/([0-9]+(\.[0-9]+)?\s*%)/.test(word)) {
                        errors.push(`특정성분 함량에 "${word}"의 함량(%)을 추가하세요.`);
                    }
                }
                if (!foundAny && ingredientInfo) {
                    if (!new RegExp(`${item}\\s*([\\d.]+%)`).test(ingredientInfo)) {
                        errors.push(`특정성분 함량에 "${item}"의 함량(%)을 추가하세요.`);
                    }
                }
            });
        }

        // 원재료명(rawmtrl_nm_display)에서 각 농수산물명에 대해 %와 원산지 포함 여부 확인
        foundItems.forEach(item => {
            const rawList = rawmtrlNm.split(/\s*,\s*/);
            rawList.forEach((raw, idx) => {
                // item을 포함하는 단어(예: 사과즙, 사과잼 등)도 모두 포함 (단어 경계 없이 포함만 체크)
                if (raw.includes(item)) {
                    // 함량(%) 체크: 100% 또는 20% 등
                    const hasPercent = /([0-9]+(\.[0-9]+)?\s*%)/.test(raw);
                    // 원산지 체크: (국산), (미국산), /국산, /미국산 등도 허용
                    // 1. 괄호 안에 '산'이 포함된 경우
                    let hasOrigin = /\([^)산]*[가-힣]+산[^)]*\)/.test(raw) || /\([^)]+산[^)]*\)/.test(raw);
                    // 2. /국산, /미국산, /중국산 등은 "산"이 포함된 경우로 허용
                    if (!hasOrigin) {
                        hasOrigin = /\/\s*[가-힣]+산/.test(raw);
                    }
                    // 3. "사과/국산"처럼 "/"로 구분된 경우도 허용
                    if (!hasOrigin) {
                        hasOrigin = new RegExp(`${item}\\s*\\/\\s*[가-힣]+산`).test(raw);
                    }
                    // 4. "사과/국산"처럼 "/"로 구분된 경우도 허용 (예외: "사과즙(미국산/100%)" 등)
                    if (!hasOrigin) {
                        hasOrigin = /[가-힣]+\/[가-힣]+산/.test(raw);
                    }
                    if (!hasPercent && !hasOrigin) {
                        errors.push(`원재료명에 표시된 ${idx + 1}번째 원료(${raw})의 함량(%)과 원산지를 모두 추가하세요.`);
                    } else if (!hasPercent) {
                        errors.push(`원재료명에 표시된 ${idx + 1}번째 원료(${raw})의 함량(%)을 추가하세요.`);
                    } else if (!hasOrigin) {
                        errors.push(`원재료명에 표시된 ${idx + 1}번째 원료(${raw})의 원산지를 추가하세요.`);
                    }
                }
            });
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
            const hasOpeningKeyword = combinedText.includes('개봉');
            const hasStorageKeyword = combinedText.includes('냉장') || combinedText.includes('빨리') || combinedText.includes('빠른 시일');

            if (!(hasOpeningKeyword && hasStorageKeyword)) {
                errors.push('냉장 보관 제품은 주의사항 또는 기타표시사항에 "개봉 후 냉장 보관 및 빠른 섭취" 관련 문구를 포함해야 합니다.');
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
        const packageMaterial = checkedFields.frmlc_mtrqlt || '';

        if (!packageMaterial) {
            errors.push('포장재질을 표시하세요.');
            return { errors, suggestions: [] };
        }

        const select = document.getElementById('recyclingMarkSelect');
        const selectedMark = select ? select.value : '';
        const recommendedMark = recommendRecyclingMarkByMaterial(packageMaterial);
        if (selectedMark && selectedMark !== '미표시' && selectedMark !== recommendedMark) {
            errors.push(
                `포장재질("${packageMaterial}")과 분리배출마크("${selectedMark}")가 일치하지 않습니다. 사용된 포장재질과 분리배출마크를 재확인하세요.`
            );
        }
        return { errors, suggestions: [] };
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
            const previewContent = document.getElementById('previewContent');
            if (!previewContent) {
                alert('미리보기 내용을 찾을 수 없습니다.');
                return;
            }

            // 현재 설정된 가로/세로 길이 가져오기
            const width = parseFloat(document.getElementById('widthInput').value) || 10;
            const height = 11; // 세로는 항상 11cm로 고정
            
            // cm를 pt로 변환 (1cm = 28.35pt)
            const widthPt = width * 28.35;
            const heightPt = height * 28.35;
            
            // 최소 크기 보장
            const minWidthPt = 283.5; // 10cm
            const minHeightPt = 311.85; // 11cm
            
            // PDF 페이지 크기 결정 (실제 라벨 크기에 맞춤)
            const pdfWidth = Math.max(widthPt, minWidthPt);
            const pdfHeight = Math.max(heightPt, minHeightPt);

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

            // jsPDF 인스턴스 생성 (커스텀 페이지 크기)
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({
                orientation: width > height ? 'landscape' : 'portrait',
                unit: 'pt',
                format: [pdfWidth, pdfHeight]
            });

            // 캔버스를 이미지로 변환
            const imgData = canvas.toDataURL('image/png', 1.0);
            
            // 이미지 크기 계산
            const imgWidth = canvas.width;
            const imgHeight = canvas.height;
            
            // PDF 페이지에 맞게 이미지 크기 조정
            const ratio = Math.min(pdfWidth / imgWidth, pdfHeight / imgHeight);
            const scaledWidth = imgWidth * ratio;
            const scaledHeight = imgHeight * ratio;
            
            // 이미지를 PDF 중앙에 배치
            const x = (pdfWidth - scaledWidth) / 2;
            const y = (pdfHeight - scaledHeight) / 2;

            // PDF에 이미지 추가 (최고 품질)
            pdf.addImage(imgData, 'PNG', x, y, scaledWidth, scaledHeight, undefined, 'FAST');

            // 파일명 생성
            const today = new Date();
            const dateStr = today.getFullYear().toString().substr(-2) + 
                           (today.getMonth() + 1).toString().padStart(2, '0') + 
                           today.getDate().toString().padStart(2, '0');
            
            const labelName = document.querySelector('.header-text')?.textContent || '라벨';
            const fileName = `${labelName}_${dateStr}.pdf`;

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
            if (value < 0.5) return 0;
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
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', exportToPDF);
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
});