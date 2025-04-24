// 전역 변수에 국가 목록 추가
let labelId;
let originValidated = false;
let currentModalRow = null;
let countryNames = []; // 국가명 목록

// select2 옵션 데이터 준비
let foodTypeOptions = [];
let agriProductOptions = [];
let foodAdditiveOptions = [];

function getFoodTypeSelectOptions() {
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
    const allOptions = [...foodTypeOptions, ...agriProductOptions, ...foodAdditiveOptions];
    return allOptions;
}

function createFoodTypeSelect(selectedValue = "") {
    const select = document.createElement('select');
    select.className = 'form-control form-control-sm food-type-select';
    select.style.width = '100%';
    // 옵션은 select2에서 동적으로 적용
    if (selectedValue) select.setAttribute('data-selected', selectedValue);
    return select;
}

// 문서 로드시 초기화 코드
document.addEventListener('DOMContentLoaded', function() {
    // URL에서 label_id 파라미터 추출
    const urlParams = new URLSearchParams(window.location.search);
    labelId = urlParams.get('label_id');
    
    if (!labelId) {
        alert('라벨 ID를 찾을 수 없습니다. 창을 닫고 다시 시도해주세요.');
    }

    // 국가명 목록 초기화
    try {
        countryNames = JSON.parse(document.getElementById('country-names-data').textContent || '[]');
    } catch (error) {
        countryNames = [];
    }

    const savedIngredients = JSON.parse(document.getElementById('saved-ingredients-data').textContent || '[]');
    const hasRelations = document.querySelector('.popup-container').dataset.hasRelations === 'true';
    
    // 테이블 Sortable 초기화
    const tbody = document.getElementById('ingredient-body');
    new Sortable(tbody, { animation: 150, handle: '.drag-handle', onEnd: updateTargetButtons });

    // 체크박스 전체 선택/해제 이벤트 리스너
    document.getElementById('select-all').addEventListener('change', function() {
        const isChecked = this.checked;
        document.querySelectorAll('.delete-checkbox').forEach(checkbox => {
            checkbox.checked = isChecked;
        });
    });

    try {
        // 서버에서 전달받은 데이터로 행 추가
        if (hasRelations) {
            savedIngredients.forEach(ingredient => {
                addIngredientRowWithData(ingredient);
            });
            sortRows(); // 비율에 따라 정렬
        } else {
            addIngredientRows(savedIngredients);
        }
    } catch (error) {}

    // input 이벤트 리스너는 자동 확장 기능만 담당
    document.addEventListener('input', function (event) {
        if (event.target.classList.contains('auto-expand')) {
            event.target.style.height = 'auto';
            event.target.style.height = event.target.scrollHeight + 'px';
            updateTableHeight();
        }
        
        // 비율 입력 필드 변경 감지
        if (event.target.classList.contains('ratio-input')) {
            originValidated = false;
            updateSaveButtonState();
        }
    }, false);

    // 클릭 외부 영역 감지 (옵션 컨테이너 제거)
    document.addEventListener('click', function(event) {
        const optionsContainers = document.querySelectorAll('.options-container');
        optionsContainers.forEach(container => {
            if (!container.contains(event.target)) {
                container.remove();
            }
        });
    });

    // 비율 입력 필드에 이벤트 리스너 추가
    attachRatioInputListeners();

    // 저장 버튼 초기 비활성화
    updateSaveButtonState();

    // 모달 검색 식품유형 select2 적용
    const modalFoodTypeSelect = document.getElementById('modalSearchInput3');
    if (modalFoodTypeSelect) {
        $(modalFoodTypeSelect).select2({
            data: getFoodTypeSelectOptions(),
            width: '100%',
            placeholder: '식품유형 선택',
            allowClear: true
        });
    }
});

// 원산지 버튼 기능 구현
function validateOrigin() {
    // 1. 비율에 따라 행 정렬
    sortRowsByRatio();

    // 2. 원산지 표시대상 설정
    markOriginTargets();

    // 3. 원산지 검증 완료 플래그 설정
    originValidated = true;

    // 4. 저장 버튼 상태 업데이트
    updateSaveButtonState();

    // 5. 사용자에게 알림
    alert('원산지 표시대상이 설정되었습니다. 이제 저장할 수 있습니다.');
}

// 비율에 따라 행 정렬
function sortRowsByRatio() {
    const tbody = document.getElementById('ingredient-body');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    // 모든 행의 참고사항에서 "원산지 표시대상" 텍스트 제거 (재설정 위해)
    rows.forEach(row => {
        const notesTextarea = row.querySelector('.notes-input');
        if (notesTextarea) {
            notesTextarea.value = notesTextarea.value.replace(/원산지 표시대상/g, '').trim();
        }
    });
    
    // 비율 높은 순으로 정렬
    rows.sort((a, b) => {
        const ratioA = parseFloat(a.querySelector('.ratio-input')?.value) || 0;
        const ratioB = parseFloat(b.querySelector('.ratio-input')?.value) || 0;
        return ratioB - ratioA;
    });
    
    // DOM 재구성
    while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
    }
    rows.forEach(row => tbody.appendChild(row));
    
    // 순서 관련 UI 업데이트
    updateRowNumbers();
    updateTargetButtons();
    
    return rows; // 정렬된 행 반환
}

// 기존 함수는 다른 이름으로 같은 기능을 수행하므로 연결
function sortRows() {
    return sortRowsByRatio();
}

// 행 번호 업데이트 함수
function updateRowNumbers() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const orderCell = row.querySelector('td:nth-child(2)');
        if (orderCell) {
            orderCell.textContent = index + 1;
        }
    });
}

// 대상 버튼 업데이트 함수
function updateTargetButtons() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const button = row.querySelector('.btn-target');
        if (button) {
            button.style.display = 'none';
        }
    });
}

// 원산지 표시대상 마킹 함수 수정
function markOriginTargets() {
    const rows = Array.from(document.querySelectorAll('#ingredient-body tr'));
    
    // 행이 없으면 처리하지 않음
    if (rows.length === 0) return;
    
    // 각 행의 비율 추출
    const ratios = rows.map(row => {
        return parseFloat(row.querySelector('.ratio-input')?.value) || 0;
    });
    
    // 원산지 표시대상 결정 로직
    if (ratios[0] >= 98) {
        // 첫 번째 원료의 비율이 98% 이상인 경우
        markRowAsOriginTarget(rows[0], 1); // 1순위
    } else if (rows.length >= 2 && (ratios[0] + ratios[1] >= 98)) {
        // 첫 번째 + 두 번째 원료의 합이 98% 이상인 경우
        markRowAsOriginTarget(rows[0], 1); // 1순위
        markRowAsOriginTarget(rows[1], 2); // 2순위
    } else {
        // 그 외의 경우: 첫 번째, 두 번째, 세 번째 원료
        markRowAsOriginTarget(rows[0], 1); // 1순위
        
        if (rows.length >= 2) {
            markRowAsOriginTarget(rows[1], 2); // 2순위
        }
        
        if (rows.length >= 3) {
            markRowAsOriginTarget(rows[2], 3); // 3순위
        }
    }
}

// 특정 행을 원산지 표시대상으로 표시하는 함수 수정 (순위 및 국가명 추가)
function markRowAsOriginTarget(row, rank) {
    if (!row) return;
    
    const notesTextarea = row.querySelector('.notes-input');
    const displayNameTextarea = row.querySelector('td:nth-child(5) textarea');
    
    if (!notesTextarea || !displayNameTextarea) return;
    
    // 원재료 표시명에서 국가명 찾기
    const displayNameText = displayNameTextarea.value.trim();
    const foundCountries = findCountriesInText(displayNameText);
    
    // 순위 및 국가명으로 참고사항 텍스트 생성
    let originText = '';
    if (foundCountries.length > 0) {
        originText = `${rank}순위 - ${foundCountries.join(', ')}`;
    } else {
        originText = `${rank}순위 - 원산지 표시대상`;
    }
    
    // 현재 참고사항 텍스트
    const currentText = notesTextarea.value.trim();
    
    // 기존 원산지 표시 제거 (정규식으로 1순위, 2순위, 3순위 패턴 모두 제거)
    const cleanedText = currentText.replace(/[1-3]순위\s*-\s*[^,\n]*(\s*,\s*[^,\n]*)*\s*/g, '').trim();
    
    // 새 원산지 텍스트 추가
    if (cleanedText) {
        notesTextarea.value = cleanedText + '\n' + originText;
    } else {
        notesTextarea.value = originText;
    }
}

// 텍스트에서 국가명 찾기 함수 (순서 유지 버전)
function findCountriesInText(text) {
    if (!text || !countryNames || countryNames.length === 0) return [];
    
    // 각 국가명과 원본 텍스트에서의 위치를 저장할 배열
    const countriesWithPositions = [];
    
    // 각 국가명에 대해 검색
    countryNames.forEach(countryName => {
        const position = text.indexOf(countryName);
        if (position !== -1) {
            // 텍스트에 국가명이 있으면 국가명과 위치를 저장
            countriesWithPositions.push({
                name: countryName,
                position: position
            });
        }
    });
    
    // 텍스트에서 나타나는 위치 순서대로 정렬
    countriesWithPositions.sort((a, b) => a.position - b.position);
    
    // 정렬된 국가명만 추출하여 반환
    return countriesWithPositions.map(item => item.name);
}

// 저장 버튼 상태 업데이트
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

// 비율 입력 필드에 이벤트 핸들러 추가
function attachRatioInputListeners() {
    document.querySelectorAll('.ratio-input').forEach(input => {
        input.addEventListener('input', function() {
            originValidated = false;
            updateSaveButtonState();
        });
        
        input.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRows();
            }
        });
    });
}

// 저장 함수 수정
function saveIngredients() {
    if (!originValidated) {
        alert('원산지 버튼을 먼저 클릭하여 원산지 표시대상을 설정해주세요.');
        return;
    }

    if (!labelId) {
        alert('라벨 ID를 찾을 수 없습니다. 창을 닫고 다시 시도해주세요.');
        return;
    }

    // 원재료 데이터 수집
    const ingredients = [];
    document.querySelectorAll('#ingredient-body tr').forEach((row, index) => {
        const notesTextarea = row.querySelector('.notes-input');
        const notes = notesTextarea ? notesTextarea.value.trim() : '';
        
        const ingredient = {
            ingredient_name: row.querySelector('td:nth-child(3) input:first-of-type')?.value.trim() || "",
            ratio: row.querySelector('.ratio-input')?.value.trim() || "",
            prdlst_report_no: row.querySelector('td:nth-child(4) input:first-of-type')?.value.trim() || "",
            food_type: row.querySelector('.food-type-select')?.value.trim() || "",
            display_name: row.querySelector('td:nth-child(5) textarea')?.value.trim() || "",
            notes: notes,  // 참고사항 필드 추가
            allergen: row.querySelector('.allergen-input')?.value.trim() || "",
            gmo: row.querySelector('.gmo-input')?.value.trim() || "",
            manufacturer: row.querySelector('td:nth-child(8) input')?.value.trim() || "",
            my_ingredient_id: row.querySelector('.my-ingredient-id')?.value.trim() || "",
            order: index + 1
        };
        ingredients.push(ingredient);
    });

    // CSRF 토큰 가져오기
    const csrftoken = getCookie('csrftoken');

    // 서버에 데이터 전송
    fetch(`/label/save-ingredients-to-label/${labelId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ ingredients: ingredients })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP 오류: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('원재료 정보가 성공적으로 저장되었습니다.');
            
            // 부모 창 갱신
            if (window.opener) {
                window.opener.location.reload();
            }
            
            window.close();
        } else {
            alert('저장 중 오류가 발생했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        alert('저장 중 오류가 발생했습니다. 개발자 도구 콘솔에서 자세한 정보를 확인하세요.');
    });
}

// getCookie 함수 수정 (버그 수정)
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

// 일반 행 추가 함수
function addIngredientRow(material = '') {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>
            <input type="checkbox" class="delete-checkbox form-check-input">
        </td>
        <td class="drag-handle">☰</td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" value="${material}" class="form-control form-control-sm" placeholder="원재료명">
                <input type="text" class="form-control form-control-sm ratio-input" placeholder="비율 (%)">
            </div>
        </td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" class="form-control form-control-sm" placeholder="품목보고번호" maxlength="15">
                <div class="food-type-select-container"></div>
            </div>
        </td>
        <td>
            <textarea class="form-control form-control-sm auto-expand" placeholder="원재료 표시명">${material}</textarea>
        </td>
        <td>
            <textarea class="form-control form-control-sm auto-expand notes-input" placeholder="참고사항"></textarea>
        </td>
        <td>
            <div class="d-flex flex-column">
                <div class="d-flex align-items-center mb-1">
                    <input type="hidden" class="allergen-input" value="">
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="openAllergyModal(this)">+</button>
                </div>
                <div class="d-flex align-items-center">
                    <input type="hidden" class="gmo-input" value="">
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="openGmoModal(this)">+</button>
                </div>
            </div>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" placeholder="제조사">
        </td>
        <td>
            <div class="d-flex flex-column">
                <button type="button" class="btn btn-sm btn-secondary" onclick="registerMyIngredient(this)">등록</button>
                <input type="hidden" class="my-ingredient-id">
            </div>
        </td>
    `;
    document.getElementById('ingredient-body').appendChild(row);

    // 식품유형 select2 적용
    const foodTypeContainer = row.querySelector('.food-type-select-container');
    const select = createFoodTypeSelect();
    foodTypeContainer.appendChild(select);
    $(select).select2({
        data: getFoodTypeSelectOptions(),
        width: '100%',
        placeholder: '식품유형 선택',
        allowClear: true
    });

    // 기존 값이 있으면 선택
    if (select.dataset.selected) {
        $(select).val(select.dataset.selected).trigger('change');
    }

    // 입력 변경 시 원산지 검증 무효화
    const ratioInput = row.querySelector('.ratio-input');
    if (ratioInput) {
        ratioInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRows();
            }
        });
        ratioInput.addEventListener('input', function() {
            originValidated = false;
            updateSaveButtonState();
        });
    }
    updateTargetButtons();
    originValidated = false;
    updateSaveButtonState();
    return row;
}

// savedIngredients 배열을 받아 각 객체의 ingredient_name을 사용하여 행을 추가하는 함수 수정
function addIngredientRows(savedIngredients) {
    if (!savedIngredients || savedIngredients.length === 0) return;

    // 모든 원재료 데이터가 단일 항목인 경우
    if (savedIngredients.length === 1 && savedIngredients[0].display_name) {
        const displayName = savedIngredients[0].display_name.trim();
        
        // 쉼표로 분리된 여러 원재료가 있는지 확인
        if (displayName.includes(',')) {
            // 쉼표로 분리하여 각각의 원재료로 행 추가
            const ingredientNames = displayName.split(',').map(name => name.trim()).filter(name => name);
            
            ingredientNames.forEach(name => {
                addIngredientRow(name);
            });
            return;
        }
    }

    // 기존 처리 방식 (단일 항목이 아니거나 쉼표가 없는 경우)
    savedIngredients.forEach(ingredient => {
        // display_name이 있으면 그것을 사용하고, 없으면 ingredient_name 사용
        const materialName = (ingredient.display_name && ingredient.display_name.trim()) || 
                            (ingredient.ingredient_name && ingredient.ingredient_name.trim()) || '';
        addIngredientRow(materialName);
    });
}

// 기존 데이터로 행 추가 함수
function addIngredientRowWithData(ingredient, fromModal = true) {
    const readonlyClass = fromModal ? "modal-readonly-field" : "";
    const readonlyAttr = fromModal ? "readonly" : "";
    const disabledAttr = fromModal ? "disabled" : "";

    // 알레르기와 GMO 항목 개수 계산
    const allergenCount = ingredient.allergen ? ingredient.allergen.split(',').length : 0;
    const gmoCount = ingredient.gmo ? ingredient.gmo.split(',').length : 0;

    // 읽기 전용 버튼 클래스 및 이벤트 핸들러 설정
    const viewOnlyClass = fromModal ? "btn-outline-secondary" : "btn-outline-primary";
    
    // 여기가 중요합니다: 이벤트 핸들러 문자열 설정
    const allergyClickEvent = fromModal 
        ? `onclick="showReadOnlyInfo(this, 'allergen')"`
        : `onclick="openAllergyModal(this)"`;
    const gmoClickEvent = fromModal 
        ? `onclick="showReadOnlyInfo(this, 'gmo')"`
        : `onclick="openGmoModal(this)"`;

    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="checkbox" class="delete-checkbox form-check-input"></td>
        <td class="drag-handle">☰</td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" value="${ingredient.ingredient_name}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="원재료명" ${readonlyAttr}>
                <input type="text" value="${ingredient.ratio || ''}" 
                       class="form-control form-control-sm ratio-input" placeholder="비율 (%)">
            </div>
        </td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" value="${ingredient.prdlst_report_no}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="품목보고번호" ${readonlyAttr}>
                <div class="food-type-select-container"></div>
            </div>
        </td>
        <td>
            <textarea class="form-control form-control-sm bordered-input auto-expand ${readonlyClass}" 
                      placeholder="원재료 표시명" ${readonlyAttr}>${ingredient.display_name || ingredient.ingredient_name}</textarea>
        </td>
        <td>
            <textarea class="form-control form-control-sm auto-expand notes-input" 
                      placeholder="참고사항">${ingredient.notes || ''}</textarea>
        </td>
        <td>
            <div class="d-flex flex-column">
                <div class="d-flex align-items-center mb-1">
                    <input type="hidden" class="allergen-input" value="${ingredient.allergen || ''}">
                    <button type="button" class="btn btn-sm ${viewOnlyClass} allergen-btn" ${allergyClickEvent}>
                        + ${allergenCount > 0 ? ' (' + allergenCount + ')' : ''}
                    </button>
                </div>
                <div class="d-flex align-items-center">
                    <input type="hidden" class="gmo-input" value="${ingredient.gmo || ''}">
                    <button type="button" class="btn btn-sm ${viewOnlyClass} gmo-btn" ${gmoClickEvent}>
                        + ${gmoCount > 0 ? ' (' + gmoCount + ')' : ''}
                    </button>
                </div>
            </div>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm bordered-input ${readonlyClass}" 
                   value="${ingredient.manufacturer}" ${readonlyAttr}>
        </td>
        <td>
            <div class="d-flex flex-column">
                <button type="button" class="btn btn-sm btn-secondary" onclick="registerMyIngredient(this)" ${disabledAttr}>등록</button>
                <input type="hidden" class="my-ingredient-id" value="${ingredient.my_ingredient_id}">
            </div>
        </td>
    `;
    document.getElementById('ingredient-body').appendChild(row);
    // 식품유형 select2 적용
    const foodTypeContainer = row.querySelector('.food-type-select-container');
    const select = createFoodTypeSelect(ingredient.food_type);
    foodTypeContainer.appendChild(select);
    $(select).select2({
        data: getFoodTypeSelectOptions(),
        width: '100%',
        placeholder: '식품유형 선택',
        allowClear: true
    });
    if (ingredient.food_type) {
        $(select).val(ingredient.food_type).trigger('change');
    }
    // 원산지 검증 무효화
    originValidated = false;
    updateSaveButtonState();
    updateTargetButtons();
    return row;
}

// 테이블 높이 업데이트
function updateTableHeight() {
    const tableContainer = document.querySelector('.table-container');
    tableContainer.style.height = 'auto';
    tableContainer.style.height = tableContainer.scrollHeight + 'px';
}

// 선택한 행 제거
function removeSelectedRows() {
    document.querySelectorAll('#ingredient-body .delete-checkbox:checked')
            .forEach(input => input.closest('tr').remove());
    updateTargetButtons();
    
    // 행 삭제 후 원산지 검증 무효화
    originValidated = false;
    updateSaveButtonState();
}

// 알레르기 모달 열기 함수
function openAllergyModal(button) {
    // 현재 행 저장
    currentModalRow = button.closest('tr');
    
    // 현재 행의 원재료명 가져오기
    const ingredientName = currentModalRow.querySelector('td:nth-child(3) input:first-of-type')?.value || "원재료";
    
    // 모달 제목 업데이트
    const modalTitle = document.getElementById('allergyModalLabel');
    if (modalTitle) {
        modalTitle.textContent = `알레르기 항목 선택 - ${ingredientName}`;
    }
    
    // 알레르기 옵션 표시
    const allergyOptions = document.getElementById('allergyOptions');
    allergyOptions.innerHTML = ''; // 기존 옵션 초기화
    
    // 알레르기 항목 목록
    const allergyItems = [
        '난류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우', 
        '돼지고기', '복숭아', '토마토', '아황산류', '호두', '닭고기', '쇠고기', '오징어', '조개류'
    ];
    
    // 현재 행의 알레르기 입력 필드 값 가져오기
    const allergyInput = currentModalRow.querySelector('.allergen-input');
    const currentAllergies = allergyInput ? allergyInput.value.split(',').map(item => item.trim()).filter(Boolean) : [];
    
    // 알레르기 항목에 대한 체크박스 생성
    allergyItems.forEach(item => {
        const div = document.createElement('div');
        div.className = 'form-check form-check-inline';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.id = `allergy-${item}`;
        input.value = item;
        input.checked = currentAllergies.includes(item);
        
        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.htmlFor = `allergy-${item}`;
        label.textContent = item;
        
        div.appendChild(input);
        div.appendChild(label);
        allergyOptions.appendChild(div);
    });
    
    // 선택된 알레르기 초기화
    document.getElementById('selectedAllergies').value = currentAllergies.join(', ');
    
    // 체크박스 변경 시 선택된 알레르기 업데이트
    allergyOptions.addEventListener('change', updateSelectedAllergies);
    
    // 모달 표시
    const allergyModal = new bootstrap.Modal(document.getElementById('allergyModal'));
    allergyModal.show();
}

// 선택된 알레르기 업데이트
function updateSelectedAllergies() {
    const selectedAllergies = [];
    document.querySelectorAll('#allergyOptions input:checked').forEach(checkbox => {
        selectedAllergies.push(checkbox.value);
    });
    document.getElementById('selectedAllergies').value = selectedAllergies.join(', ');
}

// 알레르기 적용
function applyAllergies() {
    if (!currentModalRow) return;
    
    const selectedAllergies = document.getElementById('selectedAllergies').value;
    const allergyInput = currentModalRow.querySelector('.allergen-input');
    const allergyButton = currentModalRow.querySelector('.allergen-btn');
    
    if (allergyInput) {
        allergyInput.value = selectedAllergies;
    }
    
    if (allergyButton) {
        // 버튼 텍스트 업데이트: 선택된 항목 수만 표시
        const selectedCount = selectedAllergies ? selectedAllergies.split(',').length : 0;
        if (selectedCount > 0) {
            allergyButton.textContent = `+ (${selectedCount})`;
        } else {
            allergyButton.textContent = '+';
        }
    }
    
    // 모달 닫기
    const allergyModal = bootstrap.Modal.getInstance(document.getElementById('allergyModal'));
    allergyModal.hide();
}

// GMO 모달 열기 함수
function openGmoModal(button) {
    // 현재 행 저장
    currentModalRow = button.closest('tr');
    
    // 현재 행의 원재료명 가져오기
    const ingredientName = currentModalRow.querySelector('td:nth-child(3) input:first-of-type')?.value || "원재료";
    
    // 모달 제목 업데이트
    const modalTitle = document.getElementById('gmoModalLabel');
    if (modalTitle) {
        modalTitle.textContent = `GMO 항목 선택 - ${ingredientName}`;
    }
    
    // GMO 옵션 표시
    const gmoOptions = document.getElementById('gmoOptions');
    gmoOptions.innerHTML = ''; // 기존 옵션 초기화
    
    // GMO 항목 목록
    const gmoItems = [
        '콩', '옥수수', '면화', '카놀라', '사탕무', '알팔파', 'GMO 없음'
    ];
    
    // 현재 행의 GMO 입력 필드 값 가져오기
    const gmoInput = currentModalRow.querySelector('.gmo-input');
    const currentGmos = gmoInput ? gmoInput.value.split(',').map(item => item.trim()).filter(Boolean) : [];
    
    // GMO 항목에 대한 체크박스 생성
    gmoItems.forEach(item => {
        const div = document.createElement('div');
        div.className = 'form-check form-check-inline';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.id = `gmo-${item}`;
        input.value = item;
        input.checked = currentGmos.includes(item);
        
        // GMO 없음이 선택되면 다른 항목을 비활성화하는 이벤트 처리
        if (item === 'GMO 없음') {
            input.addEventListener('change', function() {
                if (this.checked) {
                    // 현재 항목이 'GMO 없음'이고 체크됐을 때 다른 항목 해제
                    document.querySelectorAll('#gmoOptions input[type="checkbox"]').forEach(checkbox => {
                        if (checkbox.value !== item) {
                            checkbox.checked = false;
                        }
                    });
                }
            });
        } else {
            // 일반 GMO 항목이 선택되면 'GMO 없음'을 해제
            input.addEventListener('change', function() {
                if (this.checked) {
                    document.querySelectorAll('#gmoOptions input[type="checkbox"]').forEach(checkbox => {
                        if (checkbox.value === 'GMO 없음') {
                            checkbox.checked = false;
                        }
                    });
                }
            });
        }
        
        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.htmlFor = `gmo-${item}`;
        label.textContent = item;
        
        div.appendChild(input);
        div.appendChild(label);
        gmoOptions.appendChild(div);
    });
    
    // 선택된 GMO 초기화
    document.getElementById('selectedGmos').value = currentGmos.join(', ');
    
    // 체크박스 변경 시 선택된 GMO 업데이트
    gmoOptions.addEventListener('change', updateSelectedGmos);
    
    // 모달 표시
    const gmoModal = new bootstrap.Modal(document.getElementById('gmoModal'));
    gmoModal.show();
}

// 선택된 GMO 업데이트
function updateSelectedGmos() {
    const selectedGmos = [];
    document.querySelectorAll('#gmoOptions input:checked').forEach(checkbox => {
        selectedGmos.push(checkbox.value);
    });
    document.getElementById('selectedGmos').value = selectedGmos.join(', ');
}

// GMO 적용
function applyGmos() {
    if (!currentModalRow) return;
    
    const selectedGmos = document.getElementById('selectedGmos').value;
    const gmoInput = currentModalRow.querySelector('.gmo-input');
    const gmoButton = currentModalRow.querySelector('.gmo-btn');
    
    if (gmoInput) {
        gmoInput.value = selectedGmos;
    }
    
    if (gmoButton) {
        // 버튼 텍스트 업데이트: 선택된 항목 수만 표시
        const selectedCount = selectedGmos ? selectedGmos.split(',').length : 0;
        if (selectedCount > 0) {
            gmoButton.textContent = `+ (${selectedCount})`;
        } else {
            gmoButton.textContent = '+';
        }
    }
    
    // 모달 닫기
    const gmoModal = bootstrap.Modal.getInstance(document.getElementById('gmoModal'));
    gmoModal.hide();
}

// 읽기 전용 알레르기/GMO 정보를 보여주는 함수
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
    
    // 원재료명 가져오기
    const ingredientName = row.querySelector('td:nth-child(3) input:first-of-type')?.value || "원재료";
    
    // 값이 없는 경우 메시지 표시
    if (!value) {
        value = '정보 없음';
    }
    
    // 모달 제목과 내용 업데이트
    const modalTitle = document.getElementById('readOnlyInfoModalLabel');
    if (modalTitle) {
        modalTitle.textContent = title;
    }
    
    // 원재료명 표시
    const infoIngredientName = document.getElementById('infoIngredientName');
    if (infoIngredientName) {
        infoIngredientName.textContent = `${ingredientName}`;
    }

    // 정보 내용 표시 (줄바꿈 처리)
    const infoContent = document.getElementById('infoContent');
    if (infoContent) {
        // 알레르기나 GMO 항목을 리스트로 표시
        if (value !== '정보 없음') {
            const items = value.split(',').map(item => item.trim()).filter(Boolean);
            if (items.length > 0) {
                // 항목들을 불릿 포인트로 표시
                const listHTML = items.map(item => `<li>${item}</li>`).join('');
                infoContent.innerHTML = `<ul class="mb-0">${listHTML}</ul>`;
            } else {
                infoContent.textContent = value;
            }
        } else {
            infoContent.textContent = value;
        }
    }
    
    // 모달 표시
    const readOnlyInfoModal = new bootstrap.Modal(document.getElementById('readOnlyInfoModal'));
    readOnlyInfoModal.show();
}

// 내 원재료 검색/등록 관련 함수들
function searchMyIngredientInModal() {
    const ingredientName = document.getElementById('modalSearchInput1').value.trim();
    const reportNo = document.getElementById('modalSearchInput2').value.trim();
    const foodType = document.getElementById('modalSearchInput3').value.trim();
    const manufacturer = document.getElementById('modalSearchInput4').value.trim();

    const searchParams = {
        ingredient_name: ingredientName,
        prdlst_report_no: reportNo,
        food_type: foodType,
        manufacturer: manufacturer
    };

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
        resultsDiv.innerHTML = '';  // 기존 검색 결과 초기화

        if (data.success && data.ingredients && data.ingredients.length > 0) {
            const container = document.createElement('div');
            container.classList.add('list-group');
            container.style.maxWidth = '100%';
            container.style.width = '100%';

            // 검색 결과(기존 원료) 데이터 행 생성
            data.ingredients.forEach(ingredient => {
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

                // 숨겨진 my_ingredient_id 필드 추가
                const myIngredientIdInput = document.createElement('input');
                myIngredientIdInput.type = 'hidden';
                myIngredientIdInput.classList.add('my-ingredient-id');
                myIngredientIdInput.value = ingredient.my_ingredient_id || '';

                inputContainer.appendChild(ingredientInput);
                inputContainer.appendChild(reportInput);
                inputContainer.appendChild(foodTypeInput);
                inputContainer.appendChild(manufacturerInput);
                inputContainer.appendChild(myIngredientIdInput); // 숨겨진 필드 추가
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
                });
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
    });
}

function selectIngredient(ingredient, button) {
    // 필드 이름을 다시 파싱하여 새로운 객체 생성
    const parsedIngredient = {
        ingredient_name: ingredient.prdlst_nm,
        prdlst_report_no: ingredient.prdlst_report_no,
        food_type: ingredient.prdlst_dcnm,
        manufacturer: ingredient.bssh_nm,
        display_name: ingredient.ingredient_display_name,
        my_ingredient_id: ingredient.my_ingredient_id
    };

    addIngredientRowWithData(parsedIngredient, true);

    // 모달 닫기
    const modalEl = document.getElementById('ingredientSearchModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    modalInstance.hide();
}

function registerMyIngredient(button) {
    const row = button.closest('tr');
    const prdlstReportInput = row.querySelector('td:nth-child(4) input');
    const prdlst_report_no = prdlstReportInput ? prdlstReportInput.value.trim() : "";
    const foodTypeInput = row.querySelector('.food-type-select');
    const food_type = foodTypeInput ? foodTypeInput.value.trim() : "";
    const displayNameArea = row.querySelector('td:nth-child(5) textarea');
    const display_name = displayNameArea ? displayNameArea.value.trim() : "";

    // 현재 행 참조를 전역 변수에 저장 (모달 선택 시 사용)
    window.currentRow = row;
    
    let criteria = {};
    if (prdlst_report_no) {
        criteria = { prdlst_report_no: prdlst_report_no };
    } else {
        criteria = { food_type: food_type, display_name: display_name };
    }
    
    fetch('/label/check-my-ingredient/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(criteria)
    })
    .then(response => response.json())
    .then(data => {
        if (data.exists) {
            alert("이미 해당 조건에 해당하는 원료가 존재합니다.");
            showExistingIngredientsModal(data.ingredients);
        } else {
            const my_ingredient_id = row.querySelector('.my-ingredient-id')?.value || "";
            const ingredientData = {
                my_ingredient_id: my_ingredient_id,
                ingredient_name: row.querySelector('td:nth-child(3) input')?.value.trim() || "",
                prdlst_report_no: prdlst_report_no,
                food_type: food_type,
                display_name: display_name,
                manufacturer: row.querySelector('td:nth-child(8) input')?.value.trim() || ""
            };
            fetch('/label/register-my-ingredient/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(ingredientData)
            })
            .then(response => response.json())
            .then(regData => {
                if (regData.success) {
                    alert("원료가 등록되었습니다.");
                    // 등록이 완료되면 해당 행을 비활성화하고 배경색을 회색으로 변경
                    row.querySelectorAll('input, textarea').forEach(field => {
                        if (!field.classList.contains('ratio-input')) {
                            field.setAttribute('readonly', true);
                            field.classList.add('modal-readonly-field');
                        }
                    });
                    row.style.backgroundColor = '#e9ecef'; // 배경색 회색으로 변경
                    button.setAttribute('disabled', true); // 등록 버튼 비활성화
                } else {
                    alert("등록 실패: " + (regData.error || "알 수 없는 오류"));
                }
            })
            .catch(error => {
                alert("등록 중 오류가 발생했습니다.");
            });
        }
    })
    .catch(error => {
        alert("조회 중 오류가 발생했습니다.");
    });
}

function showExistingIngredientsModal(ingredients) {
    const modalBody = document.getElementById('existing-ingredients-modal-body');
    modalBody.innerHTML = ''; // 기존 내용 초기화

    const container = document.createElement('div');
    container.classList.add('list-group');
    container.style.maxWidth = '100%';
    container.style.width = '100%';

    // 만약 window.currentRow (등록 버튼을 누른 행)의 데이터가 있다면
    if (window.currentRow) {
        // 등록 행 데이터 추출 (셀의 input/textarea 값을 가져옴)
        const currentData = {
            ingredient_name: window.currentRow.querySelector('td:nth-child(3) input:first-of-type')?.value || "",
            prdlst_report_no: window.currentRow.querySelector('td:nth-child(4) input:first-of-type')?.value || "",
            food_type: window.currentRow.querySelector('.food-type-select')?.value || "",
            display_name: window.currentRow.querySelector('td:nth-child(5) textarea')?.value || "",
            manufacturer: window.currentRow.querySelector('td:nth-child(8) input')?.value || ""
        };

        // 등록 행을 강조하는 별도 헤더 또는 항목으로 추가
        const currentRowDiv = document.createElement('div');
        currentRowDiv.classList.add('list-group-item', 'highlight-color'); // 배경색으로 강조 (원하는 스타일로 수정)
        currentRowDiv.innerHTML = `
            <div><strong>등록 행 데이터</strong></div>
            <div class="d-flex">
                <div class="flex-fill"><strong>원료명:</strong> ${currentData.ingredient_name}</div>
                <div class="flex-fill"><strong>품목보고번호:</strong> ${currentData.prdlst_report_no}</div>
                <div class="flex-fill"><strong>식품유형:</strong> ${currentData.food_type}</div>
                <div class="flex-fill"><strong>제조사:</strong> ${currentData.manufacturer}</div>
            </div>
            <div class="mt-2"><strong>원재료 표시명:</strong> ${currentData.display_name}</div>
        `;
        container.appendChild(currentRowDiv);
    }

    // 그 아래에 기존 원료 목록의 헤더 행 생성
    const headerRow = document.createElement('div');
    headerRow.classList.add('list-group-item', 'bg-light', 'font-weight-bold');
    headerRow.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="d-flex flex-grow-1">
                <div class="flex-fill"><strong>원료명</strong></div>
                <div class="flex-fill"><strong>품목보고번호</strong></div>
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

    // 검색 결과(기존 원료) 데이터 행 생성
    ingredients.forEach(ingredient => {
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

        // 숨겨진 my_ingredient_id 필드 추가
        const myIngredientIdInput = document.createElement('input');
        myIngredientIdInput.type = 'hidden';
        myIngredientIdInput.classList.add('my-ingredient-id');
        myIngredientIdInput.value = ingredient.my_ingredient_id || '';

        inputContainer.appendChild(ingredientInput);
        inputContainer.appendChild(reportInput);
        inputContainer.appendChild(foodTypeInput);
        inputContainer.appendChild(manufacturerInput);
        inputContainer.appendChild(myIngredientIdInput); // 숨겨진 필드 추가
        firstLine.appendChild(inputContainer);

        const buttonContainer = document.createElement('div');
        buttonContainer.style.width = '100px';
        buttonContainer.classList.add('text-end');
        const selectButton = document.createElement('button');
        selectButton.type = 'button';
        selectButton.classList.add('btn', 'btn-sm', 'btn-secondary');
        selectButton.textContent = '선택';
        selectButton.addEventListener('click', () => {
            if (window.currentRow) {
                window.currentRow.querySelector('td:nth-child(3) input:first-of-type').value = ingredientInput.value;
                window.currentRow.querySelector('td:nth-child(4) input:first-of-type').value = reportInput.value;
                window.currentRow.querySelector('.food-type-select').value = foodTypeInput.value;
                window.currentRow.querySelector('td:nth-child(5) textarea').value = displayInput.value;
                window.currentRow.querySelector('td:nth-child(8) input').value = manufacturerInput.value;
                window.currentRow.querySelector('.my-ingredient-id').value = myIngredientIdInput.value; // my_ingredient_id 설정
                
                // 모든 input, textarea readonly 처리 및 등록 버튼 비활성화
                window.currentRow.querySelectorAll('input, textarea').forEach(field => {
                    if (!field.classList.contains('ratio-input')) {
                        field.setAttribute('readonly', true);
                        field.classList.add('modal-readonly-field');
                    }
                });
                const regBtn = window.currentRow.querySelector('button[onclick*="registerMyIngredient"]');
                if (regBtn) { regBtn.disabled = true; }
            } else {
                alert("현재 선택된 행이 없습니다.");
            }
            // 모달 닫기
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
    if (!window.currentRow) {
        alert("등록할 행의 데이터가 없습니다.");
        return;
    }
    
    // 현재 행에서 데이터를 추출합니다.
    const ingredientData = {
        my_ingredient_id: window.currentRow.querySelector('.my-ingredient-id')?.value.trim() || "",
        ingredient_name: window.currentRow.querySelector('td:nth-child(3) input:first-of-type')?.value.trim() || "",
        ratio: window.currentRow.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value.trim() || "",
        prdlst_report_no: window.currentRow.querySelector('td:nth-child(4) input:first-of-type')?.value.trim() || "",
        food_type: window.currentRow.querySelector('.food-type-select')?.value.trim() || "",
        display_name: window.currentRow.querySelector('td:nth-child(5) textarea')?.value.trim() || "",
        manufacturer: window.currentRow.querySelector('td:nth-child(8) input')?.value.trim() || ""
    };
    
    // CSRF 토큰을 가져옵니다.
    const csrftoken = getCookie('csrftoken');
    
    // 등록 엔드포인트로 POST 요청 전송
    fetch('/label/register-my-ingredient/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(ingredientData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("신규 원료가 등록되었습니다.");
            // 등록 후 등록 행 데이터를 비활성화 및 스타일 적용
            window.currentRow.querySelectorAll('input, textarea').forEach(field => {
                if (!field.classList.contains('ratio-input')) {
                    field.setAttribute('readonly', true);
                    field.classList.add('modal-readonly-field');
                }
            });
            // 등록 버튼 비활성화 (필요하다면)
            const regBtn = window.currentRow.querySelector('button[onclick*="registerMyIngredient"]');
            if (regBtn) { regBtn.disabled = true; }
            // 모달 창 닫기
            const modalEl = document.getElementById('existing-ingredients-modal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) { 
                modalInstance.hide();
            }
        } else {
            alert("등록 실패: " + (data.error || "알 수 없는 오류"));
        }
    })
    .catch(error => {
        alert("등록 중 오류가 발생했습니다.");
    });
}