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
            labeldata.com 에서 관련법규에 따라 작성되었습니다.
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
        height: 10,
        fontSize: 10,
        letterSpacing: -5,
        lineHeight: 1.2,
        fontFamily: "'Noto Sans KR'"
    };

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
        // '기타' 그룹 및 '미표시' 옵션 완전히 제거
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
                // 버튼 텍스트를 항상 '적용'으로 초기화
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
                    // 해제 동작: 이미지 제거
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
        if (select) {
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
        `;

        const table = previewContent.querySelector('.preview-table');
        if (table) {
            table.style.cssText = `
                width: 100%;
                border-collapse: collapse;
                table-layout: auto;
                margin: 0;
                word-break: break-all;
            `;
        }

        const baseTextStyle = `
            font-size: ${settings.fontSize}pt;
            font-family: ${settings.fontFamily};
            letter-spacing: ${settings.letterSpacing / 100}em;
            line-height: ${settings.lineHeight};
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
            `;
            if (cell.tagName === 'TH') {
                cell.style.backgroundColor = '#f8f9fa';
                cell.style.textAlign = 'center';
                cell.style.fontWeight = '500';
                cell.style.whiteSpace = 'nowrap';
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
        my_label_name: '라벨명',
        prdlst_dcnm: '식품유형',
        prdlst_nm: '제품명',
        ingredient_info: '성분명 및 함량',
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

    window.addEventListener('message', function(e) {
        if (e.data?.type === 'previewCheckedFields' && e.data.checked) {
            const tbody = document.getElementById('previewTableBody');
            if (!tbody) return;

            tbody.innerHTML = '';
            Object.entries(e.data.checked).forEach(([field, value]) => {
                if (FIELD_LABELS[field] && value) {
                    const tr = document.createElement('tr');
                    const th = document.createElement('th');
                    const td = document.createElement('td');
                    th.textContent = FIELD_LABELS[field];

                    if (field === 'rawmtrl_nm_display') {
                        const allergenMatch = value.match(/\[알레르기 성분\s*:\s*([^\]]+)\]/);
                        const gmoMatch = value.match(/\[GMO\s*성분\s*:[^\]]+\]/);
                        const container = document.createElement('div');
                        container.style.position = 'relative';
                        container.style.width = '100%';
                        let mainText = value
                            .replace(/\[알레르기 성분\s*:[^\]]+\]/, '')
                            .replace(/\[GMO\s*성분\s*:[^\]]+\]/, '')
                            .trim();
                        const mainDiv = document.createElement('div');
                        mainDiv.textContent = mainText;
                        container.appendChild(mainDiv);
                        if (allergenMatch) {
                            const allergens = allergenMatch[1].trim();
                            const allergenDiv = document.createElement('div');
                            allergenDiv.textContent = `${allergens} 함유`;
                            allergenDiv.className = 'allergen-text';
                            container.appendChild(allergenDiv);
                        }
                        if (gmoMatch) {
                            const gmo = gmoMatch[0].trim();
                            const gmoDiv = document.createElement('div');
                            gmoDiv.textContent = gmo;
                            gmoDiv.className = 'allergen-text';
                            container.appendChild(gmoDiv);
                        }
                        td.appendChild(container);
                    } else if (field === 'country_of_origin') {
                        const select = window.opener?.document.querySelector('select[name="country_of_origin"]');
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

            // 포장재질 기반 추천
            const frmlc = e.data.checked.frmlc_mtrqlt || '';
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

    // 규정 검증
    function validateSettings() {
        const width = parseFloat(document.getElementById('widthInput').value);
        const height = parseFloat(document.getElementById('heightInput').value);
        const area = width * height;
        const fontSize = parseFloat(document.getElementById('fontSizeInput').value);
        const letterSpacing = parseInt(document.getElementById('letterSpacingInput').value);
        const lineHeight = parseFloat(document.getElementById('lineHeightInput').value);

        const errorFields = new Set();
        let errors = [];

        // 최소 면적 규정 (예: 40cm²)
        if (area < 40) {
            errors.push('정보표시면 면적은 최소 40cm² 이상이어야 합니다.');
            errorFields.add('widthInput');
            errorFields.add('heightInput');
        }

        // 최소 글꼴 크기 (10pt)
        if (fontSize < 10) {
            errors.push('글꼴 크기는 최소 10pt 이상이어야 합니다.');
            errorFields.add('fontSizeInput');
        }

        // 분리배출마크 크기 검증 (최소 8mm)
        const markImg = document.getElementById('recyclingMarkImage');
        if (markImg) {
            const mmWidth = markImg.offsetWidth / 3.78; // 1cm ≈ 37.8px
            if (mmWidth < 8) {
                errors.push('분리배출마크는 가로 8mm 이상이어야 합니다.');
                errorFields.add('recyclingMarkSelect');
            }
        }

        ['widthInput', 'heightInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (errorFields.has(id)) {
                    element.classList.add('is-invalid');
                    element.classList.remove('is-valid');
                } else {
                    element.classList.add('is-valid');
                    element.classList.remove('is-invalid');
                }
            }
        });

        if (errors.length > 0) {
            alert('규정 검증 오류:\n\n' + errors.join('\n'));
            return false;
        } else {
            savePreviewSettings();
            alert('모든 규정을 준수하고 있습니다.');
            return true;
        }
    }

    // PDF 저장
    async function exportToPDF() {
        try {
            const content = document.getElementById('previewContent');
            if (!content) throw new Error('미리보기 콘텐츠를 찾을 수 없습니다.');

            const widthMm = (parseFloat(document.getElementById('widthInput').value) || 10) * 10;
            const heightMm = (parseFloat(document.getElementById('heightInput').value) || 10) * 10;
            const markImage = document.getElementById('recyclingMarkImage');

            let productName = '제품명';
            document.querySelectorAll('#previewTableBody tr').forEach(tr => {
                if (tr.querySelector('th')?.textContent.trim() === '제품명') {
                    const td = tr.querySelector('td');
                    if (td) productName = td.textContent.trim();
                }
            });

            const rawDateTime = document.getElementById('update_datetime').value || new Date().toISOString();
            const formattedDateTime = rawDateTime.slice(0, 8).replace(/-/g, '');
            const sanitizedName = productName.replace(/[^\w가-힣]/g, '_').slice(0, 20);
            const fileName = `LABELDATA_${sanitizedName}_${formattedDateTime}.pdf`;

            // Canvas 생성
            const canvas = await html2canvas(content, {
                scale: 3,
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#fff',
                width: content.offsetWidth,
                height: content.offsetHeight
            });
            const imgData = canvas.toDataURL('image/png');

            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', [widthMm, heightMm]);
            pdf.addImage(imgData, 'PNG', 0, 0, widthMm, heightMm);

            // 분리배출 마크 추가
            if (markImage && markImage.src) {
                const previewRect = content.getBoundingClientRect();
                const markRect = markImage.getBoundingClientRect();
                const pxToMm = (px) => px * 0.264583; // 1px ≈ 0.264583mm
                let x = markRect.left - previewRect.left;
                let y = markRect.top - previewRect.top;
                x = pxToMm(x);
                y = pxToMm(y);
                const w = pxToMm(markImage.offsetWidth);
                const h = pxToMm(markImage.offsetHeight);
                pdf.addImage(markImage.src, 'PNG', x, y, w, h);
            }

            pdf.save(fileName);
        } catch (e) {
            console.error('PDF 저장 오류:', e);
            alert('PDF 저장 실패: ' + e.message);
        }
    }

    // 천 단위 콤마
    function comma(x) {
        if (x === undefined || x === null) return '';
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // 영양성분 표시
    function updateNutritionDisplay(data) {
        const nutritionPreview = document.getElementById('nutritionPreview');
        if (!nutritionPreview) return;

        const displayUnit = data.displayUnit || 'unit';
        const servingUnit = data.servingUnit || 'g';
        const servingUnitText = data.servingUnitText || '個';
        const totalWeight = data.totalWeight || (data.servingSize * data.servingsPerPackage);

        const tabMap = {
            total: `총 ${comma(totalWeight)}${servingUnit}`,
            unit: `단위 ${comma(data.servingSize)}${servingUnit}`,
            '100g': `100${servingUnit}당`
        };

        let kcal = data.calorie !== undefined && data.calorie !== null ? data.calorie : '';
        const kcalUnit = data.calorieUnit || 'kcal';

        const previewBox = `
            <div class="nutrition-preview-box">
                <div class="nutrition-preview-title">영양정보</div>
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <span class="nutrition-preview-total-size">${tabMap[displayUnit]}</span>
                    <span class="nutrition-value">${kcal ? comma(kcal) + kcalUnit : ''}</span>
                </div>
            </div>
        `;

        const tableHeader = `
            <thead>
                <tr>
                    <th class="nutrition-preview-label" style="width: 35%; text-align: left;">${tabMap[displayUnit]}</th>
                    <th class="nutrition-preview-value" style="width: 65%; text-align: right;">1일 기준치 비율</th>
                </tr>
            </thead>
        `;

        const indentItems = ['당류', '트랜스지방', '포화지방'];
        let rows = '';
        (data.values || []).forEach(item => {
            const indent = indentItems.includes(item.label);
            const percent = item.limit ? Math.round((item.value / item.limit) * 100) : '';
            rows += `
                <tr>
                    <td class="nutrient-label ${indent ? 'nutrient-label-indent' : ''}">
                        <strong>${item.label}</strong> <span class="nutrient-value">${comma(item.value)}${item.unit}</span>
                    </td>
                    <td class="nutrient-progress" style="text-align: right;">
                        ${percent ? `<strong>${percent}%</strong>` : ''}
                    </td>
                </tr>
            `;
        });

        rows += `
            <tr>
                <td colspan="2" class="nutrition-preview-footer-text">
                    <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2,000kcal 기준입니다. 개인의 필요에 따라 다를 수 있습니다.
                </td>
            </tr>
        `;

        const tableHtml = `
            <table class="nutrition-preview-table table table-sm table-bordered">
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

    // 필드 데이터 저장소
    let checkedFields = {};

    // 농수산물 목록
    const farmSeafoodItems = [
            "쌀", "찹쌀", "현미", "벼", "밭벼", "찰벼",
        "보리", "보리쌀", "밀", "밀쌀", "호밀", "귀리",
        "옥수수", "조", "수수", "메밀", "기장", "율무",
        "콩", "팥", "녹두", "완두", "강낭콩", "동부", "기타콩",
        "감자", "고구마", "야콘",
        "참깨", "들깨", "땅콩", "해바라기", "유채", "고추씨",
        "수박", "참외", "메론", "딸기", "토마토", "방울토마토",
        "호박", "오이",
        "배추·양배추", "고구마줄기", "토란줄기", "쑥", "건 무청(시래기)",
        "무말랭이", "무·알타리무·순무", "당근", "우엉", "연근",
        "양파", "대파·쪽파·실파", "건고추", "마늘", "생강", "풋고추", "꽈리고추", "홍고추",
        "피망(단고추)", "브로코리(녹색꽃양배추)", "파프리카",
        "갈근", "감초", "강활", "건강", "결명자", "구기자", "금은화", "길경", "당귀", "독활",
        "두충", "만삼", "맥문동", "모과", "목단", "반하", "방풍", "복령", "복분자", "백수오",
        "백지", "백출", "비자", "사삼", "양유(더덕)", "산수유", "산약", "산조인", "산초", "소자",
        "시호", "오가피", "오미자", "오배자", "우슬", "황정(층층갈고리둥굴레)", "옥죽/외유(둥굴레)",
        "음양곽", "익모초", "작약", "진피", "지모", "지황", "차전자", "창출", "천궁", "천마",
        "치자", "택사", "패모", "하수오", "황기", "황백", "황금", "행인", "향부자", "현삼",
        "후박", "홍화씨", "고본", "소엽", "형개", "치커리(뿌리)", "헛개", "녹용", "녹각",
        "사과", "배", "포도", "복숭아", "단감", "떫은감", "곶감", "자두", "살구", "참다래",
        "파인애플", "감귤", "만감(한라봉 포함)", "레몬", "탄제린", "오렌지(청견 포함)", "자몽",
        "금감", "유자", "버찌", "매실", "앵두", "무화과", "모과", "바나나", "블루베리", "석류", "오디",
        "밤", "대추", "잣", "호두", "은행", "도토리",
        "영지버섯", "팽이버섯", "목이버섯", "석이버섯", "운지버섯", "송이버섯", "표고버섯",
        "양송이버섯", "느타리버섯", "상황버섯", "아가리쿠스", "동충하초", "새송이버섯", "싸리버섯", "능이버섯",
        "수삼(산양삼, 장뇌삼, 산삼배양근 포함)", "묘삼(식용)",
        "고사리", "취나물", "고비", "두릅", "죽순", "도라지", "더덕", "마",
        "쇠고기(한우, 육우, 젖소)", "양고기(염소 포함)", "돼지고기(멧돼지 포함)",
        "닭고기", "오리고기", "사슴고기", "토끼고기", "칠면조고기", "육류의 부산물",
        "메추리고기", "말고기",
        "국화", "카네이션", "장미", "백합", "글라디올러스", "튜울립", "거베라", "아이리스",
        "프리지아", "칼라", "안개꽃",
        "벌꿀", "건조누에", "프로폴리스", "식용란(닭, 오리 및 메추리의 알)", "뽕잎", "누에번데기",
        "초콜릿", "치즈"
    ];

    // 사용 금지 문구
    const forbiddenPhrases = ['천연', '자연', '슈퍼', '생명'];

    // 검증 헬퍼 함수들
    function checkFarmSeafoodCompliance() {
        const errors = [];
        const ingredientInfo = checkedFields.ingredient_info || '';
        const rawmtrlInfo = checkedFields.rawmtrl_nm_display || '';
        const countryOfOrigin = checkedFields.country_of_origin || '';
        const combinedText = (ingredientInfo + ' ' + rawmtrlInfo).toLowerCase();
        const foundItems = farmSeafoodItems.filter(item => combinedText.includes(item.toLowerCase()));
        if (foundItems.length > 0) {
            foundItems.forEach(item => {
                const contentRegex = new RegExp(`${item}\\s*(\\d+\\.?\\d*%)`, 'i');
                const hasContent = contentRegex.test(ingredientInfo) || contentRegex.test(rawmtrlInfo);
                const originRegex = new RegExp(`${item}\\s*\\(([^)]+)\\)`, 'i');
                const hasOrigin = originRegex.test(ingredientInfo) || originRegex.test(rawmtrlInfo) ||
                                 countryOfOrigin.toLowerCase().includes(item.toLowerCase());
                if (!hasContent) {
                    errors.push(`농수산물 "${item}"의 함량이 표시되지 않았습니다.`);
                }
                if (!hasOrigin) {
                    errors.push(`농수산물 "${item}"의 원산지가 표시되지 않았습니다.`);
                }
            });
        }
        return errors;
    }

    function checkRecyclingMarkCompliance() {
        const errors = [];
        const packageMaterial = checkedFields.frmlc_mtrqlt || '';
        const select = document.getElementById('recyclingMarkSelect');
        const selectedMark = select ? select.value : '';
        const recommendedMark = recommendRecyclingMarkByMaterial(packageMaterial);
        if (selectedMark && selectedMark !== '미표시' && selectedMark !== recommendedMark) {
            errors.push(`포장재질("${packageMaterial}")과 분리배출마크("${selectedMark}")가 일치하지 않습니다. 추천: "${recommendedMark}"`);
        }
        return errors;
    }

    function checkForbiddenPhrases() {
        const errors = [];
        const fieldsToCheck = [
            'prdlst_nm', 'ingredient_info', 'rawmtrl_nm_display', 'cautions', 'additional_info'
        ];
        fieldsToCheck.forEach(field => {
            const value = (checkedFields[field] || '').toString();
            forbiddenPhrases.forEach(phrase => {
                // 금지문구가 한글/영문/공백/괄호 등과 함께 포함되어도 감지
                if (value && value.match(new RegExp(phrase, 'i'))) {
                    errors.push(`"${FIELD_LABELS[field]}"에 사용 금지 문구 "${phrase}"가 포함되어 있습니다.`);
                }
            });
        });
        return errors;
    }

    function checkAllergenDuplication() {
        const errors = [];
        const rawmtrl = checkedFields.rawmtrl_nm_display || '';
        const cautions = checkedFields.cautions || '';
        const allergenMatch = rawmtrl.match(/\[알레르기 성분\s*:\s*([^\]]+)\]/i);
        if (allergenMatch) {
            const allergens = allergenMatch[1].split(',').map(a => a.trim().toLowerCase());
            allergens.forEach(allergen => {
                if (cautions.toLowerCase().includes(allergen)) {
                    errors.push(`주의사항에 원재료명의 알레르기 성분 "${allergen}"가 중복 표시되었습니다.`);
                }
            });
        }
        return errors;
    }

    function showValidationModal() {
        let modal = document.getElementById('validationModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'validationModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">규정 검증 진행 상황</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p id="validationStatus">검증 시작 중...</p>
                            <ul id="validationLog" style="list-style: none; padding-left: 0;"></ul>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        return modal;
    }

    function updateValidationLog(modal, index, item, result) {
        const logList = modal.querySelector('#validationLog');
        const li = document.createElement('li');
        li.innerHTML = `
            ${index + 1}. ${item.name} (${item.rule}): 
            <span class="${result.status === 'OK' ? 'text-success' : 'text-danger'}">
                ${result.status === 'OK' ? 'OK' : `오류: ${result.message}`}
            </span>
        `;
        logList.appendChild(li);
    }

    function updateValidationStatus(modal, message, isSuccess) {
        const status = modal.querySelector('#validationStatus');
        status.innerHTML = `<strong>${message}</strong>`;
        status.className = isSuccess ? 'text-success' : 'text-danger';
    }

    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 규정 검증
    async function validateSettings() {
        const width = parseFloat(document.getElementById('widthInput').value) || 0;
        const height = parseFloat(document.getElementById('heightInput').value) || 0;
        const area = width * height;
        const fontSize = parseFloat(document.getElementById('fontSizeInput').value) || 10;
        const letterSpacing = parseInt(document.getElementById('letterSpacingInput').value) || 0;
        const lineHeight = parseFloat(document.getElementById('lineHeightInput').value) || 1.2;

        const errorFields = new Set();
        const validationItems = [
            {
                name: '정보표시면 면적',
                rule: '최소 40cm² 이상',
                id: 'widthInput, heightInput',
                check: () => ({
                    status: area >= 40 ? 'OK' : 'ERROR',
                    message: area < 40 ? '정보표시면 면적은 최소 40cm² 이상이어야 합니다.' : ''
                })
            },
            {
                name: '글꼴 크기',
                rule: '최소 10pt 이상',
                id: 'fontSizeInput',
                check: () => ({
                    status: fontSize >= 10 ? 'OK' : 'ERROR',
                    message: fontSize < 10 ? '글꼴 크기는 최소 10pt 이상이어야 합니다.' : ''
                })
            },
            {
                name: '분리배출마크 크기',
                rule: '가로 최소 8mm 이상',
                id: 'recyclingMarkSelect',
                check: () => {
                    const markImg = document.getElementById('recyclingMarkImage');
                    if (!markImg) return { status: 'OK', message: '' };
                    const mmWidth = markImg.offsetWidth / 3.78;
                    return {
                        status: mmWidth >= 8 ? 'OK' : 'ERROR',
                        message: mmWidth < 8 ? '분리배출마크는 가로 8mm 이상이어야 합니다.' : ''
                    };
                }
            },
            {
                name: '농수산물 함량 및 원산지',
                rule: '농수산물 포함 시 함량(%)과 원산지 표시',
                check: () => {
                    const errors = checkFarmSeafoodCompliance();
                    return {
                        status: errors.length === 0 ? 'OK' : 'ERROR',
                        message: errors.join('; ')
                    };
                }
            },
            {
                name: '포장재질과 분리배출마크',
                rule: '포장재질과 선택된 분리배출마크 일치',
                id: 'recyclingMarkSelect',
                check: () => {
                    const errors = checkRecyclingMarkCompliance();
                    return {
                        status: errors.length === 0 ? 'OK' : 'ERROR',
                        message: errors.join('; ')
                    };
                }
            },
            {
                name: '사용 금지 문구',
                rule: '"천연", "자연" 등 금지 문구 미포함',
                check: () => {
                    const errors = checkForbiddenPhrases();
                    return {
                        status: errors.length === 0 ? 'OK' : 'ERROR',
                        message: errors.join('; ')
                    };
                }
            },
            {
                name: '알레르기 성분 중복',
                rule: '원재료명과 주의사항 간 알레르기 성분 중복 금지',
                check: () => {
                    const errors = checkAllergenDuplication();
                    return {
                        status: errors.length === 0 ? 'OK' : 'ERROR',
                        message: errors.join('; ')
                    };
                }
            }
        ];

        const modal = showValidationModal();
        const logList = modal.querySelector('#validationLog');
        logList.innerHTML = '';

        // 입력 필드 초기화
        ['widthInput', 'heightInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.remove('is-valid', 'is-invalid');
            }
        });

        let hasErrors = false;

        for (let i = 0; i < validationItems.length; i++) {
            const item = validationItems[i];
            const result = item.check();
            if (result.status === 'ERROR') {
                hasErrors = true;
                if (item.id) {
                    item.id.split(',').forEach(id => errorFields.add(id.trim()));
                }
            }
            updateValidationLog(modal, i, item, result);
            await delay(100);
        }

        // 입력 필드 상태 업데이트
        ['widthInput', 'heightInput', 'fontSizeInput', 'letterSpacingInput', 'lineHeightInput'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (errorFields.has(id)) {
                    element.classList.add('is-invalid');
                } else {
                    element.classList.add('is-valid');
                }
            }
        });

        if (hasErrors) {
            updateValidationStatus(modal, '규정 검증 실패: 위 항목을 수정하세요.', false);
            return false;
        } else {
            updateValidationStatus(modal, '모든 규정을 준수했습니다.', true);
            savePreviewSettings();
            return true;
        }
    }

    // 초기화
    setupEventListeners();
    setTimeout(updatePreviewStyles, 100);
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