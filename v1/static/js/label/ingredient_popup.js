// 전역 변수
let labelId;
let originValidated = false;
let countryNames = [];

// select2 옵션 데이터 준비
let foodTypeOptions = [];
let agriProductOptions = [];
let foodAdditiveOptions = [];

// 식품 구분 표시 매핑 (영어 -> 한국어)
const foodCategoryDisplayMap = {
    'processed': '가공식품',
    'agricultural': '농수산물',
    'additive': '식품첨가물',
    '정제수': '정제수'
};

function getFoodTypeSelectOptions(foodCategory = null) {
    if (foodTypeOptions.length === 0) {
        try {
            const foodTypes = JSON.parse(document.getElementById('food-types-data').textContent || '[]');
            foodTypeOptions = (foodTypes || []).map(ft => ({ id: ft.food_type, text: ft.food_type })).filter(opt => opt.id);
        } catch (e) { foodTypeOptions = []; }
        try {
            const agriProducts = JSON.parse(document.getElementById('agricultural-products-data').textContent || '[]');
            agriProductOptions = (agriProducts || []).map(ap => ({ id: ap.name_kr, text: ap.name_kr })).filter(opt => opt.id);
        } catch (e) { agriProductOptions = []; }
        try {
            const foodAdditives = JSON.parse(document.getElementById('food-additives-data').textContent || '[]');
            foodAdditiveOptions = (foodAdditives || []).map(fa => ({ id: fa.name_kr, text: fa.name_kr })).filter(opt => opt.id);
        } catch (e) { foodAdditiveOptions = []; }
    }
    if (foodCategory === 'processed') {
        return foodTypeOptions;
    } else if (foodCategory === 'agricultural') {
        return agriProductOptions;
    } else if (foodCategory === 'additive') {
        return foodAdditiveOptions;
    } else if (foodCategory === '정제수') {
        return [{ id: '정제수', text: '정제수' }];
    }
    return [...foodTypeOptions, ...agriProductOptions, ...foodAdditiveOptions];
}

function createFoodTypeSelect(selectedValue = "") {
    const select = document.createElement('select');
    select.className = 'form-control form-control-sm food-type-select modal-readonly-field';
    select.style.width = '100%';
    select.setAttribute('readonly', 'readonly');
    if (selectedValue) select.setAttribute('data-selected', selectedValue);
    return select;
}

// 요약 섹션 업데이트
function updateSummarySection() {
    const rows = Array.from(document.querySelectorAll('#ingredient-body tr'));

    // 1. 모든 행의 데이터를 객체 배열로 추출
    const ingredientsData = rows.map(row => {
        const ratioStr = row.querySelector('.ratio-input')?.value.trim();
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        
        // 정제수일 때는 라디오 버튼이 없으므로 기본값 사용
        let summaryType = 'foodType';
        if (ingredientName !== '정제수') {
            summaryType = row.querySelector('.summary-type-radio:checked')?.value || 'foodType';
        }
        
        return {
            ingredientName: ingredientName,
            foodCategory: row.querySelector('.food-category-input')?.dataset.foodCategory || '',
            displayName: row.querySelector('.display-name-input')?.value.trim(),
            foodType: row.querySelector('td:nth-child(6) input, .food-type-input')?.value.trim() || '',
            ratio: parseFloat(ratioStr) || 0,
            ratioStr: ratioStr,
            allergen: row.querySelector('.allergen-input')?.value || '',
            gmo: row.querySelector('.gmo-input')?.value || '',
            summaryType: summaryType // 요약 방식 선택 값 추가
        };
    });

    // 2. 식품유형(foodType)을 기준으로 그룹화하여 중복 찾기
    const foodTypeGroups = new Map();
    ingredientsData.forEach(data => {
        if (data.foodType) {
            if (!foodTypeGroups.has(data.foodType)) {
                foodTypeGroups.set(data.foodType, []);
            }
            foodTypeGroups.get(data.foodType).push(data);
        }
    });

    // 3. 중복된 그룹에 대해 함량(ratio) 순으로 정렬하고 번호 부여
    foodTypeGroups.forEach((items, foodType) => {
        if (items.length > 1) {
            items.sort((a, b) => b.ratio - a.ratio);
            items.forEach((item, index) => {
                item.summaryFoodType = `${foodType}${String.fromCodePoint(9312 + index)}`;
            });
        }
    });

    // 4. 최종 요약 표시명 배열 생성
    const summaryDisplayNames = ingredientsData.map(data => {
        let displayName = data.displayName || data.ingredientName;

        // 요약의 기본이 되는 이름 결정 (식품유형 또는 원재료명)
        let baseName;
        if (data.summaryType === 'ingredientName') {
            baseName = data.ingredientName;
        } else { // 'foodType'
            baseName = data.summaryFoodType || data.foodType; // 번호가 부여된 식품유형 사용
        }

        // 식품 분류 및 함량에 따른 표시 규칙 적용
        if (data.foodCategory === 'additive' && displayName) {
            return displayName;
        }

        if (data.foodCategory === '정제수') {
            return baseName || displayName;
        }

        if ((data.foodCategory === 'processed' || data.foodCategory === 'agricultural') && data.ratioStr && !isNaN(data.ratio) && data.ratio >= 5) {
            let items = [];
            let count = 0;
            let str = displayName;
            let i = 0;
            let len = str.length;
            let buffer = '';
            let inParen = 0;
            while (i < len && count < 5) {
                let ch = str[i];
                if (ch === '(' || ch === '[' || ch === '{') inParen++;
                else if (ch === ')' || ch === ']' || ch === '}') inParen = Math.max(0, inParen - 1);
                
                if (ch === ',' && inParen === 0) {
                    if (buffer.trim()) {
                        items.push(buffer.trim());
                        count++;
                    }
                    buffer = '';
                } else {
                    buffer += ch;
                }
                i++;
            }
            if (count < 5 && buffer.trim()) {
                items.push(buffer.trim());
            }
            return `${baseName}[${items.join(', ')}]`;
        } else {
            return baseName || displayName;
        }
    });

    document.getElementById('summary-display-names').textContent = summaryDisplayNames.filter(Boolean).join(', ') || '없음';

    // 5. 알레르기 및 GMO 정보 요약
    const allergenCount = new Map();
    const shellfishCollected = new Set();
    const shellfishPattern = /^조개류\(([^)]+)\)$/;

    ingredientsData.forEach(data => {
        const allergenList = data.allergen.split(',').map(item => item.trim()).filter(Boolean);
        allergenList.forEach(allergen => {
            const match = allergen.match(shellfishPattern);
            if (match) {
                const items = match[1].split(',').map(item => item.trim()).filter(Boolean);
                items.forEach(item => shellfishCollected.add(item));
            } else {
                allergenCount.set(allergen, (allergenCount.get(allergen) || 0) + 1);
            }
        });
    });

    if (shellfishCollected.size > 0) {
        const shellfishStr = `조개류(${Array.from(shellfishCollected).join(', ')})`;
        allergenCount.set(shellfishStr, (allergenCount.get(shellfishStr) || 0) + 1);
    }

    const gmoCount = new Map();
    ingredientsData.forEach(data => {
        const gmoList = data.gmo.split(',').map(item => item.trim()).filter(Boolean);
        gmoList.forEach(gmo => {
            gmoCount.set(gmo, (gmoCount.get(gmo) || 0) + 1);
        });
    });

    const allergenGmoText = [];
    if (allergenCount.size > 0) {
        const allergenTexts = Array.from(allergenCount.entries()).map(([allergen, count]) => {
            const displayText = count > 1 ? `${allergen}(${count})` : allergen;
            return `<span class="allergen-gmo-link" onclick="showAllergenGmoDetail('allergen', '${escapeForAttribute(allergen)}')">${escapeHtml(displayText)}</span>`;
        });
        allergenGmoText.push(`<span class="allergen-gmo-link" onclick="showAllergenGmoDetail('allergen', 'all')">전체</span> : ${allergenTexts.join(', ')}`);
    }
    if (gmoCount.size > 0) {
        const gmoTexts = Array.from(gmoCount.entries()).map(([gmo, count]) => {
            const displayText = count > 1 ? `${gmo}(${count})` : gmo;
            return `<span class="allergen-gmo-link" onclick="showAllergenGmoDetail('gmo', '${escapeForAttribute(gmo)}')">${escapeHtml(displayText)}</span>`;
        });
        allergenGmoText.push(`<span class="allergen-gmo-link" onclick="showAllergenGmoDetail('gmo', 'all')">전체</span> : ${gmoTexts.join(', ')}`);
    }
    document.getElementById('summary-allergens-gmo').innerHTML = allergenGmoText.length > 0 ? allergenGmoText.join(' / ') : '없음';
}

// 문서 로드시 초기화 코드
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    labelId = urlParams.get('label_id');
    
    if (!labelId) {
        alert('라벨 ID를 찾을 수 없습니다. 창을 닫고 다시 시도해주세요.');
        return;
    }

    try {
        countryNames = JSON.parse(document.getElementById('country-names-data').textContent || '[]');
    } catch (error) {
        countryNames = [];
    }

    const savedIngredients = JSON.parse(document.getElementById('saved-ingredients-data').textContent || '[]');
        // Loaded saved ingredients (hidden debug)
    const hasRelations = document.querySelector('.popup-container').dataset.hasRelations === 'true';
    
    const tbody = document.getElementById('ingredient-body');
    new Sortable(tbody, {
        animation: 150,
        handle: '.drag-handle',
        onEnd: function() {
            updateRowNumbers();
            markOriginTargets();
            updateSummarySection();
            attachRatioInputListeners();
        }
    });

    document.getElementById('select-all').addEventListener('change', function() {
        const isChecked = this.checked;
        document.querySelectorAll('.delete-checkbox').forEach(checkbox => {
            checkbox.checked = isChecked;
        });
    });    if (hasRelations && savedIngredients.length > 0) {
        savedIngredients.forEach(ingredient => {
            // Adding saved ingredient: ingredient.ingredient_name
            addIngredientRowWithData(ingredient);
        });
        // 초기 로드 시: 비율이 있으면 비율로 정렬, 없으면 relation_sequence 순서 유지
        sortRowsInitialLoad();
    }

    attachRatioInputListeners();
    updateSaveButtonState();

    const modalFoodCategorySelect = document.getElementById('modalSearchInputFoodCategory');
    const modalFoodTypeSelect = document.getElementById('modalSearchInput3');
    if (modalFoodCategorySelect) {
        modalFoodCategorySelect.innerHTML = '';
        const categories = [
            { id: '', text: '모든 식품 구분' },
            { id: 'processed', text: '가공식품' },
            { id: 'agricultural', text: '농수산물' },
            { id: 'additive', text: '식품첨가물' },
            { id: '정제수', text: '정제수' }
        ];
        categories.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.id;
            option.textContent = opt.text;
            modalFoodCategorySelect.appendChild(option);
        });
        modalFoodCategorySelect.value = '';
    }

    if (modalFoodTypeSelect) {
        $(modalFoodTypeSelect).select2({
            data: getFoodTypeSelectOptions(),
            width: '100%',
            placeholder: '식품유형 선택',
            allowClear: true,
            dropdownParent: $('#ingredientSearchModal')
        });
        $(modalFoodTypeSelect).val(null).trigger('change');
    }

    if (modalFoodTypeSelect && modalFoodCategorySelect) {
        $(modalFoodTypeSelect).on('change', function() {
            const selectedType = $(this).val();
            let matchedCategory = '';
            if (selectedType) {
                if (foodTypeOptions.some(opt => opt.id === selectedType)) {
                    matchedCategory = 'processed';
                } else if (agriProductOptions.some(opt => opt.id === selectedType)) {
                    matchedCategory = 'agricultural';
                } else if (foodAdditiveOptions.some(opt => opt.id === selectedType)) {
                    matchedCategory = 'additive';
                } else if (selectedType === '정제수') {
                    matchedCategory = '정제수';
                }
            }
            if (matchedCategory) {
                modalFoodCategorySelect.value = matchedCategory;
            }
        });
    }

    if (modalFoodCategorySelect && modalFoodTypeSelect) {
        modalFoodCategorySelect.addEventListener('change', function() {
            const foodCategory = this.value;
            $(modalFoodTypeSelect).empty();
            const options = getFoodTypeSelectOptions(foodCategory);
            options.forEach(opt => {
                const option = new Option(opt.text, opt.id, false, false);
                $(modalFoodTypeSelect).append(option);
            });
            $(modalFoodTypeSelect).val(null).trigger('change.select2');
        });
    }

    $('#ingredientSearchModal').on('hidden.bs.modal', function () {
        $('#modalSearchInput1').val('');
        $('#modalSearchInput2').val('');
        $('#modalSearchInput3').val('');
        $('#modalSearchInput4').val('');
        document.getElementById('modalSearchInputFoodCategory').value = '';
        $('#modalSearchInput3').val(null).trigger('change.select2');
        $('#modalSearchResults').empty();
    });

    // [수정] 마지막에 비율 합계 초기 계산 및 표시
    updateAndValidateRatios();
});

function attachRatioInputListeners() {
    document.querySelectorAll('.ratio-input').forEach(input => {
        const newInput = input.cloneNode(true);
        input.parentNode.replaceChild(newInput, input);
    });

    const inputs = document.querySelectorAll('.ratio-input');
    inputs.forEach((input, index) => {
        input.addEventListener('input', function() {
            originValidated = false;
            updateSaveButtonState();
            updateSummarySection();
            markOriginTargets();
            updateAndValidateRatios(); // [수정] 비율 유효성 검사 호출
        });
        
        input.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRowsByRatio();
                markOriginTargets();
            } else if (event.key === 'Tab' && !event.shiftKey) {
                event.preventDefault();
                const nextIndex = (index + 1) % inputs.length;
                inputs[nextIndex].focus();
            } else if (event.key === 'Tab' && event.shiftKey) {
                event.preventDefault();
                const prevIndex = (index - 1 + inputs.length) % inputs.length;
                inputs[prevIndex].focus();
            }
        });
    });
}

function updateSaveButtonState() {
    const saveButton = document.querySelector('button[onclick="saveIngredients()"]');
    if (saveButton) {
        if (originValidated) {
            saveButton.disabled = false;
            saveButton.classList.remove('btn-secondary');
            saveButton.classList.add('btn-primary');
        } else {
            saveButton.disabled = true;
            saveButton.classList.add('btn-secondary');
            saveButton.classList.remove('btn-primary');
        }
    }
}

function sortRowsByRatio() {
    const tbody = document.getElementById('ingredient-body');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.forEach(row => {
        const originCell = row.querySelector('.origin-cell');
        if (originCell) {
            originCell.textContent = '';
        }
    });
    
    rows.sort((a, b) => {
        const ratioA = parseFloat(a.querySelector('.ratio-input')?.value) || 0;
        const ratioB = parseFloat(b.querySelector('.ratio-input')?.value) || 0;
        return ratioB - ratioA;
    });
    
    while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
    }
    rows.forEach(row => tbody.appendChild(row));
    
    updateRowNumbers();
    markOriginTargets();
    updateSummarySection();
    attachRatioInputListeners();
    updateAndValidateRatios(); // [수정] 비율 유효성 검사 호출
}

// 초기 로드 시 정렬: 비율이 있으면 비율 기준, 없으면 relation_sequence 순서 유지
function sortRowsInitialLoad() {
    const tbody = document.getElementById('ingredient-body');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    // 비율이 있는 행이 있는지 확인
    const hasRatios = rows.some(row => {
        const ratioValue = row.querySelector('.ratio-input')?.value.trim();
        return ratioValue && !isNaN(parseFloat(ratioValue)) && parseFloat(ratioValue) > 0;
    });
    
    if (hasRatios) {
        // 비율이 있으면 비율 기준으로 정렬
        // (debug log removed)
        sortRowsByRatio();
    } else {
    // 비율이 없으면 relation_sequence 순서 유지 (이미 DB에서 정렬된 상태)
    // (debug log removed)
        updateRowNumbers();
        markOriginTargets();
        updateSummarySection();
        attachRatioInputListeners();
    }
}

function updateRowNumbers() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const orderCell = row.querySelector('.order-cell');
        if (orderCell) {
            // 10 이상이면 ... 만 표시
            const orderText = (index + 1) < 10 ? (index + 1) : '...';
            orderCell.innerHTML = `&#x2195; ${orderText}`;
            orderCell.classList.add('drag-handle');
        }
        // 강조 초기화
        row.classList.remove('ingredient-row', 'selected');
        row.style.backgroundColor = '';
        row.style.borderLeft = '';
        row.style.color = '';
        row.style.fontWeight = '';
        row.style.boxShadow = '';
        row.style.transition = '';
        row.style.border = '';
    });
}

function markOriginTargets() {
    const rows = Array.from(document.querySelectorAll('#ingredient-body tr'));

    // 모든 원산지 셀 및 행 강조 초기화
    rows.forEach(row => {
        const originCell = row.querySelector('.origin-cell');
        if (originCell) {
            originCell.textContent = '';
            originCell.innerHTML = '';
        }
        row.classList.remove('ingredient-row', 'selected');
        row.style.backgroundColor = '';
        row.style.borderLeft = '';
        row.style.color = '';
        row.style.fontWeight = '';
        row.style.boxShadow = '';
        row.style.transition = '';
        row.style.border = '';
    });

    // 예외 항목 배열 (식품유형 포함)
    const excludedFoodTypes = [
        "정제수", "설탕", "당류가공품", "당시럽류", "포도당", "과당", "기타과당", "기타설탕",
        "기타 엿", "덱스트린", "물엿", "올리고당", "올리고당가공품", "발효식초", "주정"
    ];

    // 필터링 로직
    const eligibleRows = rows.filter(row => {
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        const foodCategory = row.querySelector('.food-category-input')?.dataset.foodCategory.trim();
        const foodType = row.querySelector('.food-type-input')?.value.trim();

        return (
            !excludedFoodTypes.includes(foodType) && // 예외 식품유형 제외
            foodCategory !== 'additive'             // 식품첨가물 제외
        );
    });

    if (eligibleRows.length === 0) {
        originValidated = false;
        updateSaveButtonState();
        return;
    }

    // 원산지 표시대상 결정: 현재 테이블 순서 그대로 상위 3개 행에 순위 부여
    const ratiosWithRows = eligibleRows.map((row, index) => ({
        row: row,
        ratio: parseFloat(row.querySelector('.ratio-input')?.value) || 0,
        currentPosition: index + 1
    }));

    // 98% 규칙 적용 시에만 비율을 고려, 그 외에는 현재 순서 기준
    const hasHighRatio = ratiosWithRows.some(item => item.ratio >= 98);
    const topTwoRatioSum = ratiosWithRows.length >= 2 ? 
        ratiosWithRows[0].ratio + ratiosWithRows[1].ratio : 0;

    if (hasHighRatio && ratiosWithRows[0].ratio >= 98) {
        // 1순위가 98% 이상인 경우
        markRowAsOriginTarget(ratiosWithRows[0].row, 1);
    } else if (ratiosWithRows.length >= 2 && topTwoRatioSum >= 98) {
        // 상위 2개 합이 98% 이상인 경우
        markRowAsOriginTarget(ratiosWithRows[0].row, 1);
        markRowAsOriginTarget(ratiosWithRows[1].row, 2);
    } else {
        // 일반적인 경우: 현재 순서 기준으로 상위 3개
        if (ratiosWithRows[0]) markRowAsOriginTarget(ratiosWithRows[0].row, 1);
        if (ratiosWithRows.length >= 2 && ratiosWithRows[1]) markRowAsOriginTarget(ratiosWithRows[1].row, 2);
        if (ratiosWithRows.length >= 3 && ratiosWithRows[2]) markRowAsOriginTarget(ratiosWithRows[2].row, 3);
    }
    originValidated = eligibleRows.length > 0;
    updateSaveButtonState();
}

function markRowAsOriginTarget(row, rank) {
    if (!row) return;

    const displayNameInput = row.querySelector('.display-name-input');
    const originCell = row.querySelector('.origin-cell');

    if (!displayNameInput || !originCell) return;

    const displayNameText = displayNameInput.value.trim();
    const foundCountries = findCountriesInText(displayNameText);

    // 강조 스타일: 붉은색 테두리 + 붉은색 글씨
    if (foundCountries.length > 0) {
        originCell.innerHTML = `${rank}순위 - ${foundCountries.join(', ')}`;
        row.classList.remove('ingredient-row', 'selected');
        row.style.backgroundColor = '';
        row.style.borderLeft = '';
        row.style.color = '';
        row.style.fontWeight = '';
        row.style.boxShadow = '';
        row.style.transition = '';
        row.style.border = '';
    } else {
        originCell.innerHTML = `${rank}순위 - <span style="color:#d32f2f;font-weight:700;">미표시</span>`;
        row.classList.remove('ingredient-row', 'selected');
        row.style.backgroundColor = '';
        row.style.color = '';
        row.style.fontWeight = '';
        row.style.boxShadow = '';
        row.style.transition = '';
        row.style.borderLeft = '';
        row.style.border = '2px solid #d32f2f';
    }
}

function findCountriesInText(text) {
    if (!text || !countryNames || countryNames.length === 0) return [];
    
    const countriesWithPositions = countryNames
        .map(name => ({ name, position: text.indexOf(name) }))
        .filter(item => item.position !== -1)
        .sort((a, b) => a.position - b.position);
    
    return countriesWithPositions.map(item => item.name);
}

function saveIngredients() {
    // [수정] 저장 전 비율 합계 유효성 검사
    if (!updateAndValidateRatios()) {
        alert('원료 비율의 총합이 100%를 초과합니다. 확인 후 다시 저장해주세요.');
        return;
    }

    if (!originValidated) {
        alert('원산지 표시대상이 설정되지 않았습니다. 비율을 입력하고 데이터를 확인해주세요.');
        return;
    }

    if (!labelId) {
        alert('라벨 ID를 찾을 수 없습니다. 창을 닫고 다시 시도해주세요.');
        return;
    }

    const ingredients = [];
    const displayNames = [];
    const allergensSet = new Set();
    const gmosSet = new Set();

    const summaryParts = [];
    const summaryDisplayNames = [];    
    document.querySelectorAll('#ingredient-body tr').forEach((row, index) => {
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        const foodCategoryInput = row.querySelector('.food-category-input');
        const foodCategory = foodCategoryInput?.dataset.foodCategory || '';
        const displayNameRaw = row.querySelector('.display-name-input')?.value.trim() || ingredientName;
        const foodType = row.querySelector('.food-type-select')?.value.trim() ||
                         row.querySelector('.form-control[readonly].modal-readonly-field:not(.ingredient-name-input):not(.display-name-input)')?.value.trim() || '';
        const ratioStr = row.querySelector('.ratio-input')?.value.trim();
        const ratio = parseFloat(ratioStr);
        const allergenInput = row.querySelector('.allergen-input')?.value.trim() || '';
        const gmoInput = row.querySelector('.gmo-input')?.value.trim() || '';
        
        // 정제수일 때는 라디오 버튼이 없으므로 기본값 사용
        let summaryType = 'foodType';
        if (ingredientName !== '정제수') {
            summaryType = row.querySelector('.summary-type-radio:checked')?.value || 'foodType';
        }
        
        const summaryTypeFlag = summaryType === 'foodType' ? 'Y' : 'N'; // DB 저장용 플래그 변환
        
        let displayName = displayNameRaw;

        allergenInput.split(',').map(item => item.trim()).filter(Boolean).forEach(item => allergensSet.add(item));
        gmoInput.split(',').map(item => item.trim()).filter(Boolean).forEach(item => gmosSet.add(item));
        if (displayName) displayNames.push(displayName);        // updateSummarySection과 동일한 로직 적용
        if (foodCategory === 'additive') {
            summaryDisplayNames.push(displayName);
        } else if (foodCategory === 'agricultural') {
            if (ratioStr && !isNaN(ratio) && ratio >= 5) {
                let items = [];
                let count = 0;
                let str = displayName;
                let i = 0;
                let len = str.length;
                let buffer = '';
                let inParen = 0;
                while (i < len && count < 5) {
                    let ch = str[i];
                    if (ch === '(' || ch === '[' || ch === '{') {
                        inParen++;
                        buffer += ch;
                    } else if (ch === ')' || ch === ']' || ch === '}') {
                        inParen = Math.max(0, inParen - 1);
                        buffer += ch;
                    } else if (ch === ',' && inParen === 0) {
                        if (buffer.trim()) {
                            items.push(buffer.trim());
                            count += 1;
                        }
                        buffer = '';
                    } else {
                        buffer += ch;
                    }
                    i++;
                }
                if (count < 5 && buffer.trim()) {
                    items.push(buffer.trim());
                }
                summaryDisplayNames.push(`${foodType}[${items.join(', ')}]`);
            } else {
                summaryDisplayNames.push(foodType || displayName);
            }
        } else if (foodCategory === '정제수') {
            summaryDisplayNames.push(foodType || displayName);
        } else {
            // 가공식품 처리
            if (ratioStr && !isNaN(ratio) && ratio >= 5) {
                let items = [];
                let count = 0;
                let str = displayName;
                let i = 0;
                let len = str.length;
                let buffer = '';
                let inParen = 0;
                while (i < len && count < 5) {
                    let ch = str[i];
                    if (ch === '(' || ch === '[' || ch === '{') {
                        inParen++;
                        buffer += ch;
                    } else if (ch === ')' || ch === ']' || ch === '}') {
                        inParen = Math.max(0, inParen - 1);
                        buffer += ch;
                    } else if (ch === ',' && inParen === 0) {
                        if (buffer.trim()) {
                            items.push(buffer.trim());
                            count += 1;
                        }
                        buffer = '';
                    } else {
                        buffer += ch;
                    }
                    i++;
                }
                if (count < 5 && buffer.trim()) {
                    items.push(buffer.trim());
                }
                summaryDisplayNames.push(`${foodType}[${items.join(', ')}]`);
            } else {
                summaryDisplayNames.push(foodType || displayName);
            }
        }

        const ingredient = {
            ingredient_name: ingredientName || "",
            ratio: ratioStr || "",
            food_category: foodCategory || 'processed',
            food_type: foodType,
            display_name: displayName,
            allergen: allergenInput,
            gmo: gmoInput,
            origin: row.querySelector('.origin-cell')?.textContent.trim() || "",
            my_ingredient_id: ingredientName !== '정제수' ? row.querySelector('.my-ingredient-id')?.value.trim() || "" : "",
            summary_type: summaryType, // 저장할 객체에 추가
            summary_type_flag: summaryTypeFlag, // DB 저장용 Y/N 플래그 추가
            order: index + 1
        };
        ingredients.push(ingredient);
    });

    const allergens = Array.from(allergensSet).join(', ');
    const gmos = Array.from(gmosSet).join(', ');
    const summaryText = [
        `[원재료명] ${summaryDisplayNames.join(', ') || '없음'}`,
        allergens ? `[알레르기 성분: ${allergens}]` : '',
        gmos ? `[GMO 성분: ${gmos}]` : ''
    ].filter(Boolean).join('\n');

    const csrftoken = getCookie('csrftoken');
    if (!csrftoken) {
        alert('CSRF 토큰을 찾을 수 없습니다. 로그인을 확인하거나 페이지를 새로고침하세요.');
        return;
    }

    fetch(`/label/save-ingredients-to-label/${labelId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ ingredients })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.error || `HTTP 오류: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            if (window.opener) {
                const rawmtrlNmField = window.opener.document.querySelector('textarea[name="rawmtrl_nm"]');
                if (rawmtrlNmField) {
                    rawmtrlNmField.value = summaryText;
                    if (typeof window.opener.updateTextareaHeight === 'function') {
                        window.opener.updateTextareaHeight(rawmtrlNmField);
                    }
                }

                const rawmtrlNmDisplayField = window.opener.document.querySelector('textarea[name="rawmtrl_nm_display"]');
                if (rawmtrlNmDisplayField) {
                    rawmtrlNmDisplayField.value = summaryText;
                    if (typeof window.opener.updateTextareaHeight === 'function') {
                        window.opener.updateTextareaHeight(rawmtrlNmDisplayField);
                    }
                }

                const checkbox = window.opener.document.getElementById('chk_rawmtrl_nm');
                if (checkbox) {
                    checkbox.checked = true;
                    const hiddenField = window.opener.document.querySelector('input[name="chckd_rawmtrl_nm"]');
                    if (hiddenField) {
                        hiddenField.value = 'Y';
                    }
                }

                const displayCheckbox = window.opener.document.getElementById('chk_rawmtrl_nm_display');
                if (displayCheckbox) {
                    displayCheckbox.checked = true;
                    const displayHiddenField = window.opener.document.querySelector('input[name="chckd_rawmtrl_nm_display"]');
                    if (displayHiddenField) {
                        displayHiddenField.value = 'Y';
                    }
                }

                window.opener.location.reload();
            }
            alert('원재료 정보가 성공적으로 저장되었습니다.');
            window.close();
        } else {
            alert('저장 중 오류가 발생했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        alert(`저장 중 오류가 발생했습니다: ${error.message}`);
        console.error('Save error:', error);
    });
}

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

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function addIngredientRowWithData(ingredient, fromModal = true) {
    const foodCategory = ingredient.food_category || 'processed';
    const foodCategoryDisplay = foodCategoryDisplayMap[foodCategory] || '가공식품';
    // 원료 행 추가
    // Adding ingredient row: ${ingredient.ingredient_name}, category: ${foodCategory}

    const row = document.createElement('tr');
    // 알레르기/GMO 정보를 data 속성으로 저장
    row.dataset.allergen = ingredient.allergen || ingredient.allergens || '';
    row.dataset.gmo = ingredient.gmo || '';
    
    const uniqueId = `summary-type-${Date.now()}-${Math.random()}`;
    // DB의 summary_type_flag 값에 따라 라디오 버튼 설정 (Y: 식품유형, N: 원재료명)
    const summaryTypeFlag = ingredient.summary_type_flag || 'Y'; // 기본값 Y
    const summaryType = summaryTypeFlag === 'Y' ? 'foodType' : 'ingredientName';

    // 정제수인지 확인
    const isWater = ingredient.ingredient_name === '정제수';
    
    // 라디오 버튼 HTML - 정제수가 아닐 때만 표시
    const radioButtonsHtml = isWater ? '' : `
        <div style="flex-shrink: 0; margin-right: 10px;">
            <div class="form-check">
                <input class="form-check-input summary-type-radio" type="radio" name="${uniqueId}" value="foodType" ${summaryType === 'foodType' ? 'checked' : ''}>
                <label class="form-check-label" style="font-size: 0.8rem;">식품유형</label>
            </div>
            <div class="form-check">
                <input class="form-check-input summary-type-radio" type="radio" name="${uniqueId}" value="ingredientName" ${summaryType === 'ingredientName' ? 'checked' : ''}>
                <label class="form-check-label" style="font-size: 0.8rem;">원재료명</label>
            </div>
        </div>`;

    row.innerHTML = `
        <td><input type="checkbox" class="delete-checkbox form-check-input"></td>
        <td class="order-cell">&#x2195; </td>
        <td><input type="text" value="${escapeHtml(ingredient.ingredient_name || '')}" class="form-control form-control-sm ingredient-name-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${escapeHtml(ingredient.ratio || '')}" class="form-control form-control-sm ratio-input"></td>
        <td><input type="text" value="${escapeHtml(foodCategoryDisplay)}" data-food-category="${escapeHtml(foodCategory)}" class="form-control form-control-sm food-category-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${escapeHtml(ingredient.food_type || '')}" class="form-control form-control-sm food-type-input modal-readonly-field" readonly></td>
        
        <!-- 원재료 표시명과 요약 방식 라디오 버튼을 한 셀에 통합 (버튼이 왼쪽) -->
        <td>
            <div class="d-flex align-items-center">
                ${radioButtonsHtml}
                <textarea class="form-control form-control-sm display-name-input modal-readonly-field" readonly style="flex-grow: 1;">${escapeHtml(ingredient.display_name || ingredient.ingredient_name || '')}</textarea>
            </div>
        </td>
        
        <td class="origin-cell"></td>
        <input type="hidden" class="allergen-input" value="${escapeHtml(ingredient.allergen || ingredient.allergens || '')}">
        <input type="hidden" class="gmo-input" value="${escapeHtml(ingredient.gmo || '')}">
        <input type="hidden" class="my-ingredient-id" value="${escapeHtml(ingredient.my_ingredient_id || '')}">
    `;
    document.getElementById('ingredient-body').appendChild(row);

    // 요약 방식 라디오 버튼에 이벤트 리스너 추가
    row.querySelectorAll('.summary-type-radio').forEach(radio => {
        radio.addEventListener('change', updateSummarySection);
    });

    const ratioInput = row.querySelector('.ratio-input');
    if (ratioInput) {
        ratioInput.addEventListener('input', function() {
            originValidated = false;
            updateSaveButtonState();
            updateSummarySection();
            markOriginTargets();
            updateAndValidateRatios(); // [수정] 비율 유효성 검사 호출
        });
        ratioInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRowsByRatio();
                markOriginTargets();
            }
        });
    }

    updateRowNumbers();
    markOriginTargets();
    updateSummarySection();
    attachRatioInputListeners();
    updateAndValidateRatios(); // [수정] 비율 유효성 검사 호출
}

function removeSelectedRows() {
    document.querySelectorAll('#ingredient-body .delete-checkbox:checked')
        .forEach(input => input.closest('tr').remove());
    updateRowNumbers();
    markOriginTargets();
    updateSummarySection();
    attachRatioInputListeners();
    updateAndValidateRatios(); // [수정] 비율 유효성 검사 호출
}

function selectIngredient(ingredient, button) {
    const foodCategory = ingredient.food_category;
    let displayName = ingredient.ingredient_display_name || ingredient.prdlst_nm || '';
    const parsedIngredient = {
        ingredient_name: ingredient.prdlst_nm,
        prdlst_report_no: ingredient.prdlst_report_no,
        food_category: foodCategory || 'processed',
        food_type: ingredient.prdlst_dcnm || (foodCategory === '정제수' ? '정제수' : ''),
        display_name: displayName,
        allergen: ingredient.allergens || ingredient.allergen || '',
        gmo: ingredient.gmo || '',
        manufacturer: ingredient.bssh_nm,
        my_ingredient_id: ingredient.my_ingredient_id
    };

    addIngredientRowWithData(parsedIngredient, true);

    if (button) {
        button.textContent = '선택됨';
        button.classList.add('selected');
        button.disabled = true;
    }
}

function registerMyIngredient(button) {
    alert('이 팝업에서는 원료 등록이 불가능합니다. 내원료 검색을 이용해주세요.');
}

function showExistingIngredientsModal(ingredients) {
    const modalBody = document.getElementById('existing-ingredients-modal-body');
    modalBody.innerHTML = '';

    const container = document.createElement('div');
    container.classList.add('list-group');
    container.style.maxWidth = '100%';
    container.style.width = '100%';

    const headerRow = document.createElement('div');
    headerRow.classList.add('list-group-item', 'bg-light', 'font-weight-bold');
    headerRow.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="d-flex flex-grow-1">
                <div class="flex-fill"><strong>원료명</strong></div>
                <div class="flex-fill"><strong>품목보고번호</strong></div>
                <div class="flex-fill"><strong>식품구분</strong></div>
                <div class="flex-fill"><strong>식품유형</strong></div>
                <div class="flex-fill"><strong>제조사</strong></div>
            </div>
            <div style="width: 100px;" class="text-end"><strong>행동</strong></div>
        </div>
        <div class="mt-2">
            <strong>원재료 표시명</strong>
        </div>
    `;
    container.appendChild(headerRow);

    ingredients.forEach(ingredient => {
        const foodCategoryDisplay = foodCategoryDisplayMap[ingredient.food_category] || '가공식품';
        const rowContainer = document.createElement('div');
        rowContainer.classList.add('list-group-item', 'mb-2');

        const firstLine = document.createElement('div');
        firstLine.classList.add('d-flex', 'justify-content-between', 'align-items-center');

        const inputContainer = document.createElement('div');
        inputContainer.classList.add('d-flex', 'flex-grow-1');
        inputContainer.style.gap = '0.5rem';

        const ingredientInput = document.createElement('input');
        ingredientInput.type = 'text';
        ingredientInput.classList.add('form-control', 'form-control-sm');
        ingredientInput.style.flex = '1';
        ingredientInput.value = ingredient.prdlst_nm || '';

        const reportInput = document.createElement('input');
        reportInput.type = 'text';
        reportInput.classList.add('form-control', 'form-control-sm');
        reportInput.style.flex = '1';
        reportInput.value = ingredient.prdlst_report_no || '';

        const foodCategoryInput = document.createElement('input');
        foodCategoryInput.type = 'text';
        foodCategoryInput.classList.add('form-control', 'form-control-sm');
        foodCategoryInput.style.flex = '1';
        foodCategoryInput.value = foodCategoryDisplay;
        foodCategoryInput.readOnly = true;

        const foodTypeInput = document.createElement('input');
        foodTypeInput.type = 'text';
        foodTypeInput.classList.add('form-control', 'form-control-sm');
        foodTypeInput.style.flex = '1';
        foodTypeInput.value = ingredient.prdlst_dcnm || '';

        const manufacturerInput = document.createElement('input');
        manufacturerInput.type = 'text';
        manufacturerInput.classList.add('form-control', 'form-control-sm');
        manufacturerInput.style.flex = '1';
        manufacturerInput.value = ingredient.bssh_nm || '';

        const myIngredientIdInput = document.createElement('input');
        myIngredientIdInput.type = 'hidden';
        myIngredientIdInput.classList.add('my-ingredient-id');
        myIngredientIdInput.value = ingredient.my_ingredient_id || '';

        inputContainer.appendChild(ingredientInput);
        inputContainer.appendChild(reportInput);
        inputContainer.appendChild(foodCategoryInput);
        inputContainer.appendChild(foodTypeInput);
        inputContainer.appendChild(manufacturerInput);
        inputContainer.appendChild(myIngredientIdInput);
        firstLine.appendChild(inputContainer);

        const buttonContainer = document.createElement('div');
        buttonContainer.style.width = '100px';
        buttonContainer.classList.add('text-end');
        const selectButton = document.createElement('button');
        selectButton.type = 'button';
        selectButton.classList.add('btn', 'btn-sm', 'btn-secondary');
        selectButton.textContent = '선택';
        selectButton.addEventListener('click', () => {
            selectIngredient(ingredient, selectButton);
            const modalEl = document.getElementById('existing-ingredients-modal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            modalInstance.hide();
        });
        buttonContainer.appendChild(selectButton);
        firstLine.appendChild(buttonContainer);

        const secondLine = document.createElement('div');
        secondLine.classList.add('mt-2');
        const displayInput = document.createElement('input');
        displayInput.type = 'text';
        displayInput.classList.add('form-control', 'form-control-sm');
        if (
            ingredient.food_category === 'additive' &&
            ingredient.ingredient_display_name &&
            /^향료(\(.+\))?$/.test(ingredient.ingredient_display_name)
        ) {
            let flavorText = '';
            if (!/\(.+\)/.test(ingredient.ingredient_display_name) && ingredient.prdlst_nm) {
                const m = ingredient.prdlst_nm.match(/(.+?)향/);
                if (m && m[1]) {
                    flavorText = `향료(${m[1].trim()}향)`;
                }
            }
            if (flavorText) {
                displayInput.value = `향료, ${flavorText}`;
            } else {
                displayInput.value = ingredient.ingredient_display_name;
            }
        } else {
            displayInput.value = ingredient.ingredient_display_name || '';
        }
        secondLine.appendChild(displayInput);

        rowContainer.appendChild(firstLine);
        rowContainer.appendChild(secondLine);
        container.appendChild(rowContainer);
    });

    modalBody.appendChild(container);
    const modalEl = document.getElementById('existing-ingredients-modal');
    const existingIngredientsModal = new bootstrap.Modal(modalEl);
    existingIngredientsModal.show();
}

function registerNewIngredient() {
    alert('이 팝업에서는 신규 원료 등록이 불가능합니다. 내원료 검색을 이용해주세요.');
}

function searchMyIngredientInModal() {
    const ingredientName = document.getElementById('modalSearchInput1').value.trim();
    const reportNo = document.getElementById('modalSearchInput2').value.trim();
    const foodType = document.getElementById('modalSearchInput3').value.trim();
    const manufacturer = document.getElementById('modalSearchInput4').value.trim();
    const foodCategory = document.getElementById('modalSearchInputFoodCategory').value.trim();

    const searchParams = {
        ingredient_name: ingredientName,
        prdlst_report_no: reportNo,
        food_type: foodType,
        manufacturer: manufacturer,
        food_category: foodCategory
    };

    const addedIds = new Set();
    document.querySelectorAll('#ingredient-body .my-ingredient-id').forEach(input => {
        if (input.value) addedIds.add(input.value);
    });

    fetch('/label/search-ingredient-add-row/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(searchParams)
    })
    .then(response => response.json())
    .then(data => {
        const resultsDiv = document.getElementById('modalSearchResults');
        resultsDiv.innerHTML = '';

        if (data.success && data.ingredients && data.ingredients.length > 0) {
            const container = document.createElement('div');
            container.classList.add('list-group');
            container.style.maxWidth = '100%';
            container.style.width = '100%';

            data.ingredients.forEach(ingredient => {
                const foodCategoryDisplay = foodCategoryDisplayMap[ingredient.food_category] || '가공식품';
                const rowContainer = document.createElement('div');
                rowContainer.classList.add('list-group-item', 'mb-2');

                const firstLine = document.createElement('div');
                firstLine.classList.add('d-flex', 'justify-content-between', 'align-items-center');

                const inputContainer = document.createElement('div');
                inputContainer.classList.add('d-flex', 'flex-grow-1');
                inputContainer.style.gap = '0.5rem';

                const ingredientInput = document.createElement('input');
                ingredientInput.type = 'text';
                ingredientInput.classList.add('form-control', 'form-control-sm');
                ingredientInput.style.flex = '1';
                ingredientInput.value = ingredient.prdlst_nm || '';

                const reportInput = document.createElement('input');
                reportInput.type = 'text';
                reportInput.classList.add('form-control', 'form-control-sm');
                reportInput.style.flex = '1';
                reportInput.value = ingredient.prdlst_report_no || '';

                const foodCategoryInput = document.createElement('input');
                foodCategoryInput.type = 'text';
                foodCategoryInput.classList.add('form-control', 'form-control-sm');
                foodCategoryInput.style.flex = '1';
                foodCategoryInput.value = foodCategoryDisplay;
                foodCategoryInput.readOnly = true;

                const foodTypeInput = document.createElement('input');
                foodTypeInput.type = 'text';
                foodTypeInput.classList.add('form-control', 'form-control-sm');
                foodTypeInput.style.flex = '1';
                foodTypeInput.value = ingredient.prdlst_dcnm || '';

                const manufacturerInput = document.createElement('input');
                manufacturerInput.type = 'text';
                ingredientInput.classList.add('form-control', 'form-control-sm');
                manufacturerInput.style.flex = '1';
                manufacturerInput.value = ingredient.bssh_nm || '';

                const myIngredientIdInput = document.createElement('input');
                myIngredientIdInput.type = 'hidden';
                myIngredientIdInput.classList.add('my-ingredient-id');
                myIngredientIdInput.value = ingredient.my_ingredient_id || '';

                inputContainer.appendChild(ingredientInput);
                inputContainer.appendChild(reportInput);
                inputContainer.appendChild(foodCategoryInput);
                inputContainer.appendChild(foodTypeInput);
                inputContainer.appendChild(manufacturerInput);
                inputContainer.appendChild(myIngredientIdInput);
                firstLine.appendChild(inputContainer);

                const buttonContainer = document.createElement('div');
                buttonContainer.style.width = '100px';
                buttonContainer.classList.add('text-end');
                const selectButton = document.createElement('button');
                selectButton.type = 'button';
                selectButton.className = 'modal-select-btn btn btn-sm btn-secondary';
                if (ingredient.my_ingredient_id && addedIds.has(String(ingredient.my_ingredient_id))) {
                    selectButton.textContent = '선택됨';
                    selectButton.classList.add('selected');
                    selectButton.disabled = true;
                } else {
                    selectButton.textContent = '선택';
                    selectButton.addEventListener('click', () => selectIngredient(ingredient, selectButton));
                }
                buttonContainer.appendChild(selectButton);
                firstLine.appendChild(buttonContainer);

                const secondLine = document.createElement('div');
                secondLine.classList.add('mt-2');
                const displayInput = document.createElement('input');
                displayInput.type = 'text';
                displayInput.classList.add('form-control', 'form-control-sm');
                if (
                    ingredient.food_category === 'additive' &&
                    ingredient.ingredient_display_name &&
                    /^향료(\(.+\))?$/.test(ingredient.ingredient_display_name)
                ) {
                    let flavorText = '';
                    if (!/\(.+\)/.test(ingredient.ingredient_display_name) && ingredient.prdlst_nm) {
                        const m = ingredient.prdlst_nm.match(/(.+?)향/);
                        if (m && m[1]) {
                            flavorText = `향료(${m[1].trim()}향)`;
                        }
                    }
                    if (flavorText) {
                        displayInput.value = `향료, ${flavorText}`;
                    } else {
                        displayInput.value = ingredient.ingredient_display_name;
                    }
                } else {
                    displayInput.value = ingredient.ingredient_display_name || '';
                }
                secondLine.appendChild(displayInput);

                rowContainer.appendChild(firstLine);
                rowContainer.appendChild(secondLine);
                container.appendChild(rowContainer);
            });

            resultsDiv.appendChild(container);
        } else {
            resultsDiv.innerHTML = '<div>검색 결과가 없습니다.</div>';
        }
    })
    .catch(error => {
        alert('검색 중 오류가 발생했습니다.');
        console.error('Search error:', error);
    });
}

// [추가] 원료 비율의 합을 계산하고 100% 초과 시 경고를 표시하는 함수
function updateAndValidateRatios() {
    const ratioInputs = document.querySelectorAll('.ratio-input');
    let totalRatio = 0;

    ratioInputs.forEach(input => {
        const ratio = parseFloat(input.value) || 0;
        totalRatio += ratio;
    });

    const ratioSumElement = document.getElementById('ratio-sum');
    if (ratioSumElement) {
        ratioSumElement.textContent = totalRatio.toFixed(2);
    }

    const isValid = totalRatio <= 100;
    const ratioSumContainer = document.getElementById('ratio-sum-container');

    // 모든 비율 입력 칸의 스타일을 먼저 초기화
    ratioInputs.forEach(input => {
        input.style.border = ''; // 테두리 초기화
        input.style.backgroundColor = '';
        input.style.fontWeight = '';
        input.style.color = '';
    });

    if (isValid) {
        // 합계가 유효하면 합계 컨테이너의 경고 스타일 제거
        if (ratioSumContainer) {
            ratioSumContainer.classList.remove('text-danger', 'fw-bold');
        }
    } else {
        // 합계가 100%를 초과하면, 값이 있는 칸에만 경고 스타일 적용
        ratioInputs.forEach(input => {
            if (input.value.trim() !== '') {
                input.style.border = '1px solid #d32f2f'; // 빨간색 테두리
                input.style.backgroundColor = '#fff3cd'; // 노란색 배경
                input.style.fontWeight = 'bold'; // 굵은 글씨
                input.style.color = '#d32f2f'; // 빨간색 글씨
            }
        });
        // 합계 컨테이너에 경고 스타일 적용
        if (ratioSumContainer) {
            ratioSumContainer.classList.add('text-danger', 'fw-bold');
        }
    }

    return isValid;
}

// 속성값을 위한 이스케이프 함수
function escapeForAttribute(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// 알레르기 유발성분/GMO 상세 모달 표시
function showAllergenGmoDetail(type, component) {
    // 알레르기/GMO 상세 모달 열기
    // Opening modal for ${type} - ${component}
    
    // 현재 테이블의 모든 행의 데이터 확인
    const tbody = document.getElementById('ingredient-body');
    const rows = tbody.getElementsByTagName('tr');
    // Current table data inspection removed
    // Current table data (hidden debug)
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const nameInput = row.querySelector('.ingredient-name-input');
        const name = nameInput ? nameInput.value : 'Unknown';
        // Row ${i}: ${name}, allergen: ${row.dataset.allergen}, gmo: ${row.dataset.gmo}
    }
    
    const modal = new bootstrap.Modal(document.getElementById('allergenGmoDetailModal'));
    const title = type === 'allergen' ? '알레르기 유발성분' : 'GMO';
    const modalTitle = document.querySelector('#allergenGmoDetailModal .modal-title');
    modalTitle.textContent = component === 'all' ? `${title} 전체` : `${title}: ${component}`;
    
    // 모달 테이블 생성
    createAllergenGmoTable(type, component);
    
    modal.show();
}

// 알레르기/GMO 상세 테이블 생성
function createAllergenGmoTable(type, component) {
    const headerElement = document.getElementById('allergenGmoTableHeader');
    const bodyElement = document.getElementById('allergenGmoTableBody');
    
    if (!headerElement || !bodyElement) {
        console.error('모달 테이블 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 헤더 생성
    headerElement.innerHTML = `
        <th style="width: 30%;">원재료명</th>
        <th style="width: 20%;">식품구분</th>
        <th style="width: 25%;">식품유형</th>
        <th style="width: 25%;">${type === 'allergen' ? '알레르기' : 'GMO'}</th>
    `;
    
    // 데이터 필터링 및 정렬
    const filteredIngredients = filterIngredientsByComponent(type, component);
    
    // 바디 생성
    let bodyHtml = '';
    filteredIngredients.forEach((ingredient) => {
        const componentValue = type === 'allergen' ? ingredient.allergen_info : ingredient.gmo_info;
        bodyHtml += `
            <tr>
                <td>${escapeHtml(ingredient.name)}</td>
                <td>${escapeHtml(ingredient.food_category_display)}</td>
                <td>${escapeHtml(ingredient.food_type)}</td>
                <td>${escapeHtml(componentValue || '-')}</td>
            </tr>
        `;
    });
    
    bodyElement.innerHTML = bodyHtml;
}

// 성분을 알레르기/GMO로 필터링
function filterIngredientsByComponent(type, component) {
    const tbody = document.getElementById('ingredient-body');
    if (!tbody) {
        console.error('ingredient-body 테이블을 찾을 수 없습니다.');
        return [];
    }
    
    const rows = tbody.getElementsByTagName('tr');
    const filteredIngredients = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const cells = row.getElementsByTagName('td');
        
        if (cells.length > 0) {
            // 셀 인덱스: 0=체크박스, 1=순서, 2=원재료명, 3=비율, 4=식품구분, 5=식품유형, 6=원재료표시명, 7=원산지
            const nameInput = cells[2].querySelector('input');
            const name = nameInput ? nameInput.value.trim() : cells[2].textContent.trim();
            
            const foodCategoryInput = cells[4].querySelector('input');
            const foodCategory = foodCategoryInput?.dataset.foodCategory || '';
            const foodCategoryDisplay = foodCategoryInput?.value || '';
            
            const foodTypeInput = cells[5].querySelector('input');
            const foodType = foodTypeInput ? foodTypeInput.value.trim() : cells[5].textContent.trim();
            
            // 행의 data 속성에서 알레르기/GMO 정보 가져오기
            const allergen = row.dataset.allergen || '';
            const gmo = row.dataset.gmo || '';
            
            const targetValue = type === 'allergen' ? allergen : gmo;
            
            // 필터링 조건
            if (component === 'all') {
                // 해당 타입의 성분이 있는 모든 원재료
                if (targetValue && targetValue !== '-' && targetValue !== '') {
                    filteredIngredients.push({
                        name: name,
                        food_category_display: foodCategoryDisplay,
                        food_type: foodType,
                        allergen_info: allergen,
                        gmo_info: gmo
                    });
                }
            } else {
                // 특정 성분을 포함하는 원재료만 (쉼표로 구분된 여러 성분 중에서 찾기)
                if (targetValue) {
                    let hasComponent = false;
                    
                    if (type === 'allergen') {
                        // 알레르기 성분의 경우 조개류(새우, 게) 같은 복합 성분도 처리
                        const componentList = targetValue.split(',').map(item => item.trim());
                        
                        // 정확히 일치하는 성분 찾기
                        if (componentList.includes(component)) {
                            hasComponent = true;
                        } else {
                            // 조개류(새우, 게) 형태의 성분에서 개별 성분 찾기
                            for (const item of componentList) {
                                if (item.includes('(') && item.includes(')')) {
                                    const match = item.match(/^([^(]+)\(([^)]+)\)$/);
                                    if (match) {
                                        const mainType = match[1].trim();
                                        const subItems = match[2].split(',').map(sub => sub.trim());
                                        if (component === mainType || subItems.includes(component)) {
                                            hasComponent = true;
                                            break;
                                        }
                                    }
                                } else if (item === component) {
                                    hasComponent = true;
                                    break;
                                }
                            }
                        }
                    } else {
                        // GMO의 경우 단순 비교
                        const componentList = targetValue.split(',').map(item => item.trim());
                        hasComponent = componentList.includes(component);
                    }
                    
                    if (hasComponent) {
                        filteredIngredients.push({
                            name: name,
                            food_category_display: foodCategoryDisplay,
                            food_type: foodType,
                            allergen_info: allergen,
                            gmo_info: gmo
                        });
                    }
                }
            }
        }
    }
    
    // Filtered ingredients debug output removed
    // Filtered ingredients for ${type} - ${component}
    return filteredIngredients;
}