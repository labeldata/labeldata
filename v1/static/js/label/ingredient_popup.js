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

    const summaryDisplayNames = [];
    rows.forEach((row) => {
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        const foodCategory = row.querySelector('.food-category-input')?.dataset.foodCategory || '';
        const displayNameRaw = row.querySelector('.display-name-input')?.value.trim() || ingredientName;
        const foodType = row.querySelector('td:nth-child(6) input, .food-type-input')?.value.trim() || '';
        const ratioStr = row.querySelector('.ratio-input')?.value.trim();
        const ratio = parseFloat(ratioStr);

        let displayName = displayNameRaw;
        if (foodCategory === 'additive' && displayName) {
            const idx = displayName.indexOf('※ 이 식품첨가물은');
            if (idx !== -1) {
                displayName = displayName.substring(0, idx).trim();
            }
        }

        if (foodCategory === 'additive') {
            summaryDisplayNames.push(displayName);
            return;
        }

        if (foodCategory === 'agricultural') {
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
            return;
        }

        if (foodCategory === '정제수') {
            summaryDisplayNames.push(foodType || displayName);
            return;
        }

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
    });

    document.getElementById('summary-display-names').textContent = summaryDisplayNames.length > 0 ? summaryDisplayNames.join(', ') : '없음';

    // 알레르기 성분 카운트 (숫자로 표시)
    const allergenCount = new Map();
    const shellfishCollected = new Set();
    const shellfishPattern = /^조개류\(([^)]+)\)$/;

    rows.forEach(row => {
        const allergenInput = row.querySelector('.allergen-input')?.value || '';
        const allergenList = allergenInput.split(',').map(item => item.trim()).filter(item => item);
        allergenList.forEach(allergen => {
            const match = allergen.match(shellfishPattern);
            if (match) {
                const items = match[1].split(',').map(item => item.trim()).filter(item => item);
                items.forEach(item => shellfishCollected.add(item));
            } else if (allergen.includes('조개류')) {
                allergenCount.set(allergen, (allergenCount.get(allergen) || 0) + 1);
            } else {
                allergenCount.set(allergen, (allergenCount.get(allergen) || 0) + 1);
            }
        });
    });

    // 조개류 통합 처리
    if (shellfishCollected.size > 0) {
        const shellfishStr = `조개류(${Array.from(shellfishCollected).join(', ')})`;
        allergenCount.set(shellfishStr, (allergenCount.get(shellfishStr) || 0) + 1);
    }

    // GMO 성분 카운트 (숫자로 표시)
    const gmoCount = new Map();
    rows.forEach(row => {
        const gmoInput = row.querySelector('.gmo-input')?.value || '';
        const gmoList = gmoInput.split(',').map(item => item.trim()).filter(item => item);
        gmoList.forEach(gmo => {
            gmoCount.set(gmo, (gmoCount.get(gmo) || 0) + 1);
        });
    });

    // 알레르기/GMO 텍스트 생성 (숫자 포함)
    const allergenGmoText = [];
    if (allergenCount.size > 0) {
        const allergenTexts = Array.from(allergenCount.entries()).map(([allergen, count]) => {
            return count > 1 ? `${allergen}(${count})` : allergen;
        });
        allergenGmoText.push(`알레르기: ${allergenTexts.join(', ')}`);
    }
    if (gmoCount.size > 0) {
        const gmoTexts = Array.from(gmoCount.entries()).map(([gmo, count]) => {
            return count > 1 ? `${gmo}(${count})` : gmo;
        });
        allergenGmoText.push(`GMO: ${gmoTexts.join(', ')}`);
    }
    document.getElementById('summary-allergens-gmo').textContent = allergenGmoText.length > 0 ? allergenGmoText.join(' / ') : '없음';
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
    console.log('Loaded saved ingredients:', savedIngredients);
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
            console.log(`Adding saved ingredient: ${ingredient.ingredient_name}, food_category: ${ingredient.food_category}`);
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
        console.log('비율이 있어서 비율 기준으로 정렬합니다.');
        sortRowsByRatio();
    } else {
        // 비율이 없으면 relation_sequence 순서 유지 (이미 DB에서 정렬된 상태)
        console.log('비율이 없어서 relation_sequence 순서를 유지합니다.');
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
    const summaryDisplayNames = [];    document.querySelectorAll('#ingredient-body tr').forEach((row, index) => {
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
        
        // 식품첨가물의 경우 "※ 이 식품첨가물은..." 텍스트 제거
        let displayName = displayNameRaw;
        if (foodCategory === 'additive' && displayName) {
            const idx = displayName.indexOf('※ 이 식품첨가물은');
            if (idx !== -1) {
                displayName = displayName.substring(0, idx).trim();
            }
        }
        
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
    console.log(`Adding ingredient row: ${ingredient.ingredient_name}, food_category: ${foodCategory}, displayed as: ${foodCategoryDisplay}`);

    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="checkbox" class="delete-checkbox form-check-input"></td>
        <td class="order-cell">&#x2195; </td>
        <td><input type="text" value="${escapeHtml(ingredient.ingredient_name || '')}" class="form-control form-control-sm ingredient-name-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${escapeHtml(ingredient.ratio || '')}" class="form-control form-control-sm ratio-input"></td>
        <td><input type="text" value="${escapeHtml(foodCategoryDisplay)}" data-food-category="${escapeHtml(foodCategory)}" class="form-control form-control-sm food-category-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${escapeHtml(ingredient.food_type || '')}" class="form-control form-control-sm food-type-input modal-readonly-field" readonly></td>
        <td><textarea class="form-control form-control-sm display-name-input modal-readonly-field" readonly>${escapeHtml(ingredient.display_name || ingredient.ingredient_name || '')}</textarea></td>
        <td class="origin-cell"></td>
        <input type="hidden" class="allergen-input" value="${escapeHtml(ingredient.allergen || ingredient.allergens || '')}">
        <input type="hidden" class="gmo-input" value="${escapeHtml(ingredient.gmo || '')}">
        <input type="hidden" class="my-ingredient-id" value="${escapeHtml(ingredient.my_ingredient_id || '')}">
    `;
    document.getElementById('ingredient-body').appendChild(row);

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