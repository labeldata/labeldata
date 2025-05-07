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
    
    const displayNames = rows
        .map(row => row.querySelector('.display-name-input')?.value.trim())
        .filter(name => name)
        .join(', ');
    document.getElementById('summary-display-names').textContent = displayNames || '없음';
    
    // 중복 제거를 위한 Set 사용
    const allergensSet = new Set();
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
                allergensSet.add(allergen);
            } else {
                allergensSet.add(allergen);
            }
        });
    });

    if (shellfishCollected.size > 0) {
        const shellfishStr = `조개류(${Array.from(shellfishCollected).join(', ')})`;
        allergensSet.add(shellfishStr);
    }

    // GMO 중복 제거
    const gmosSet = new Set();
    rows.forEach(row => {
        const gmoInput = row.querySelector('.gmo-input')?.value || '';
        const gmoList = gmoInput.split(',').map(item => item.trim()).filter(item => item);
        gmoList.forEach(gmo => gmosSet.add(gmo));
    });

    const allergenGmoText = [];
    if (allergensSet.size > 0) {
        allergenGmoText.push(Array.from(allergensSet).join(', '));
    }
    if (gmosSet.size > 0) {
        allergenGmoText.push(Array.from(gmosSet).join(', '));
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
    });

    if (hasRelations && savedIngredients.length > 0) {
        savedIngredients.forEach(ingredient => {
            console.log(`Adding saved ingredient: ${ingredient.ingredient_name}, food_category: ${ingredient.food_category}`);
            addIngredientRowWithData(ingredient);
        });
        sortRowsByRatio();
    }

    attachRatioInputListeners();
    updateSaveButtonState();

    // 식품 구분 드롭다운 초기화
    const modalFoodCategorySelect = document.getElementById('modalSearchInputFoodCategory');
    if (modalFoodCategorySelect) {
        $(modalFoodCategorySelect).select2({
            data: [
                { id: '', text: '모든 식품 구분' },
                { id: 'processed', text: '가공식품' },
                { id: 'agricultural', text: '농수산물' },
                { id: 'additive', text: '식품첨가물' },
                { id: '정제수', text: '정제수' }
            ],
            width: '100%',
            placeholder: '식품 구분 선택',
            allowClear: true
        });
        $(modalFoodCategorySelect).val(null).trigger('change');
    }

    // 식품 유형 드롭다운 초기화
    const modalFoodTypeSelect = document.getElementById('modalSearchInput3');
    if (modalFoodTypeSelect) {
        $(modalFoodTypeSelect).select2({
            data: getFoodTypeSelectOptions(),
            width: '100%',
            placeholder: '식품유형 선택',
            allowClear: true
        });
        $(modalFoodTypeSelect).val(null).trigger('change');
    }

    // 식품 구분 변경 시 식품 유형 갱신
    if (modalFoodCategorySelect && modalFoodTypeSelect) {
        $(modalFoodCategorySelect).on('change', function() {
            const foodCategory = $(this).val();
            $(modalFoodTypeSelect).select2('destroy');
            $(modalFoodTypeSelect).select2({
                data: getFoodTypeSelectOptions(foodCategory),
                width: '100%',
                placeholder: '식품유형 선택',
                allowClear: true
            });
            $(modalFoodTypeSelect).val(null).trigger('change');
        });
    }
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
        });
        
        input.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRowsByRatio();
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
}

function updateRowNumbers() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const orderCell = row.querySelector('.drag-handle');
        if (orderCell) {
            orderCell.textContent = index + 1;
        }
    });
}

function markOriginTargets() {
    const rows = Array.from(document.querySelectorAll('#ingredient-body tr'));
    const eligibleRows = rows.filter(row => {
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        const foodCategory = row.querySelector('.food-category-input')?.dataset.foodCategory.trim();
        return ingredientName !== '정제수' && foodCategory !== 'additive';
    });
    
    if (eligibleRows.length === 0) {
        originValidated = false;
        updateSaveButtonState();
        return;
    }
    
    const ratios = eligibleRows.map(row => parseFloat(row.querySelector('.ratio-input')?.value) || 0);
    
    if (ratios[0] >= 98) {
        markRowAsOriginTarget(eligibleRows[0], 1);
    } else if (eligibleRows.length >= 2 && (ratios[0] + ratios[1] >= 98)) {
        markRowAsOriginTarget(eligibleRows[0], 1);
        markRowAsOriginTarget(eligibleRows[1], 2);
    } else {
        markRowAsOriginTarget(eligibleRows[0], 1);
        if (eligibleRows.length >= 2) markRowAsOriginTarget(eligibleRows[1], 2);
        if (eligibleRows.length >= 3) markRowAsOriginTarget(eligibleRows[2], 3);
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
    
    let originText = foundCountries.length > 0 ? `${rank}순위 - ${foundCountries.join(', ')}` : `${rank}순위 - 원산지 표시대상`;
    originCell.textContent = originText;
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

    document.querySelectorAll('#ingredient-body tr').forEach((row, index) => {
        const ingredientName = row.querySelector('.ingredient-name-input')?.value.trim();
        const foodCategoryInput = row.querySelector('.food-category-input');
        const foodCategory = foodCategoryInput?.dataset.foodCategory || '';
        const displayName = row.querySelector('.display-name-input')?.value.trim() || ingredientName;

        // 알레르기 및 GMO 데이터 수집
        const allergenInput = row.querySelector('.allergen-input')?.value.trim() || '';
        const gmoInput = row.querySelector('.gmo-input')?.value.trim() || '';
        allergenInput.split(',').map(item => item.trim()).filter(Boolean).forEach(item => allergensSet.add(item));
        gmoInput.split(',').map(item => item.trim()).filter(Boolean).forEach(item => gmosSet.add(item));

        // 표시명 수집
        if (displayName) displayNames.push(displayName);

        const ingredient = {
            ingredient_name: ingredientName || "",
            ratio: row.querySelector('.ratio-input')?.value.trim() || "",
            food_category: foodCategory || 'processed',
            food_type: row.querySelector('.food-type-select')?.value.trim() || "",
            display_name: displayName,
            allergen: allergenInput,
            gmo: gmoInput,
            origin: row.querySelector('.origin-cell')?.textContent.trim() || "",
            my_ingredient_id: ingredientName !== '정제수' ? row.querySelector('.my-ingredient-id')?.value.trim() || "" : "",
            order: index + 1
        };
        ingredients.push(ingredient);
    });

    // 요약 텍스트 생성
    const allergens = Array.from(allergensSet).join(', ');
    const gmos = Array.from(gmosSet).join(', ');
    const summaryText = [
        `[원재료명] ${displayNames.join(', ') || '없음'}`,
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
            // 부모 창 필드 업데이트
            if (window.opener) {
                // rawmtrl_nm (참고) 업데이트
                const rawmtrlNmField = window.opener.document.querySelector('textarea[name="rawmtrl_nm"]');
                if (rawmtrlNmField) {
                    rawmtrlNmField.value = summaryText;
                    if (typeof window.opener.updateTextareaHeight === 'function') {
                        window.opener.updateTextareaHeight(rawmtrlNmField);
                    }
                }

                // rawmtrl_nm_display (표시) 업데이트
                const rawmtrlNmDisplayField = window.opener.document.querySelector('textarea[name="rawmtrl_nm_display"]');
                if (rawmtrlNmDisplayField) {
                    rawmtrlNmDisplayField.value = summaryText;
                    if (typeof window.opener.updateTextareaHeight === 'function') {
                        window.opener.updateTextareaHeight(rawmtrlNmDisplayField);
                    }
                }

                // rawmtrl_nm 체크박스 체크
                const checkbox = window.opener.document.getElementById('chk_rawmtrl_nm');
                if (checkbox) {
                    checkbox.checked = true;
                    const hiddenField = window.opener.document.querySelector('input[name="chckd_rawmtrl_nm"]');
                    if (hiddenField) {
                        hiddenField.value = 'Y';
                    }
                }

                // rawmtrl_nm_display 체크박스 체크
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

function addIngredientRowWithData(ingredient, fromModal = true) {
    const allergenCount = ingredient.allergen ? ingredient.allergen.split(',').length : 0;
    const gmoCount = ingredient.gmo ? ingredient.gmo.split(',').length : 0;
    const foodCategory = ingredient.food_category || 'processed';
    const foodCategoryDisplay = foodCategoryDisplayMap[foodCategory] || '가공식품';
    console.log(`Adding ingredient row: ${ingredient.ingredient_name}, food_category: ${foodCategory}, displayed as: ${foodCategoryDisplay}`);

    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="checkbox" class="delete-checkbox form-check-input"></td>
        <td class="drag-handle">☰</td>
        <td><input type="text" value="${ingredient.ingredient_name || ''}" class="form-control form-control-sm ingredient-name-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${ingredient.ratio || ''}" class="form-control form-control-sm ratio-input"></td>
        <td><input type="text" value="${foodCategoryDisplay}" data-food-category="${foodCategory}" class="form-control form-control-sm food-category-input modal-readonly-field" readonly></td>
        <td><input type="text" value="${ingredient.food_type || ''}" class="form-control form-control-sm modal-readonly-field" readonly></td>
        <td><textarea class="form-control form-control-sm display-name-input modal-readonly-field" readonly>${ingredient.display_name || ingredient.ingredient_name || ''}</textarea></td>
        <td>
            <input type="hidden" class="allergen-input" value="${ingredient.allergen || ''}">
            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="showReadOnlyInfo(this, 'allergen')">
                + ${allergenCount > 0 ? '(' + allergenCount + ')' : ''}
            </button>
        </td>
        <td>
            <input type="hidden" class="gmo-input" value="${ingredient.gmo || ''}">
            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="showReadOnlyInfo(this, 'gmo')">
                + ${gmoCount > 0 ? '(' + gmoCount + ')' : ''}
            </button>
        </td>
        <td class="origin-cell"></td>
        <input type="hidden" class="my-ingredient-id" value="${ingredient.my_ingredient_id || ''}">
    `;
    document.getElementById('ingredient-body').appendChild(row);

    const ratioInput = row.querySelector('.ratio-input');
    if (ratioInput) {
        ratioInput.addEventListener('input', function() {
            originValidated = false;
            updateSaveButtonState();
            updateSummarySection();
        });
        ratioInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRowsByRatio();
            }
        });
    }

    updateRowNumbers();
    markOriginTargets();
    updateSummarySection();
    attachRatioInputListeners();
}

function removeSelectedRows() {
    document.querySelectorAll('#ingredient-body .delete-checkbox:checked')
        .forEach(input => input.closest('tr').remove());
    updateRowNumbers();
    markOriginTargets();
    updateSummarySection();
    attachRatioInputListeners();
}

function showReadOnlyInfo(button, type) {
    const row = button.closest('tr');
    let value = '';
    let title = '';
    
    if (type === 'allergen') {
        value = row.querySelector('.allergen-input').value;
        title = '알레르기 정보';
    } else if (type === 'gmo') {
        value = row.querySelector('.gmo-input').value;
        title = 'GMO 정보';
    }
    
    const ingredientName = row.querySelector('.ingredient-name-input')?.value || "원재료";
    
    if (!value) value = '정보 없음';
    
    const modalTitle = document.getElementById('readOnlyInfoModalLabel');
    if (modalTitle) modalTitle.textContent = title;
    
    const infoIngredientName = document.getElementById('infoIngredientName');
    if (infoIngredientName) infoIngredientName.textContent = ingredientName;

    const infoContent = document.getElementById('infoContent');
    if (infoContent) {
        if (value !== '정보 없음') {
            const items = value.split(',').map(item => item.trim()).filter(Boolean);
            if (items.length > 0) {
                const listHTML = items.map(item => `<li>${item}</li>`).join('');
                infoContent.innerHTML = `<ul class="mb-0">${listHTML}</ul>`;
            } else {
                infoContent.textContent = value;
            }
        } else {
            infoContent.textContent = value;
        }
    }
    
    const readOnlyInfoModal = new bootstrap.Modal(document.getElementById('readOnlyInfoModal'));
    readOnlyInfoModal.show();
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
    console.log('Searching with params:', searchParams);

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
            console.log('Search results:', data.ingredients);
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
                selectButton.addEventListener('click', () => selectIngredient(ingredient, selectButton));
                buttonContainer.appendChild(selectButton);
                firstLine.appendChild(buttonContainer);

                const secondLine = document.createElement('div');
                secondLine.classList.add('mt-2');
                const displayInput = document.createElement('input');
                displayInput.type = 'text';
                displayInput.classList.add('form-control', 'form-control-sm');
                displayInput.value = ingredient.ingredient_display_name || '';
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

function selectIngredient(ingredient, button) {
    const foodCategory = ingredient.food_category;
    console.log(`Selected ingredient: ${ingredient.prdlst_nm}, food_category: ${foodCategory}`);
    if (!foodCategory) {
        console.warn(`No food_category for ${ingredient.prdlst_nm}, defaulting to 'processed'`);
    }
    const parsedIngredient = {
        ingredient_name: ingredient.prdlst_nm,
        prdlst_report_no: ingredient.prdlst_report_no,
        food_category: foodCategory || 'processed',
        food_type: ingredient.prdlst_dcnm || (foodCategory === '정제수' ? '정제수' : ''),
        display_name: ingredient.ingredient_display_name,
        allergen: ingredient.allergens || '',
        gmo: ingredient.gmo || '',
        manufacturer: ingredient.bssh_nm,
        my_ingredient_id: ingredient.my_ingredient_id
    };

    addIngredientRowWithData(parsedIngredient, true);
    const modalEl = document.getElementById('ingredientSearchModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    modalInstance.hide();
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
        displayInput.value = ingredient.ingredient_display_name;
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