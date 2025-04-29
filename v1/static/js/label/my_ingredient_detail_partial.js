// my_ingredient_detail_partial.html에서 분리된 스크립트
// 삭제 확인 및 삭제 함수
function confirmDelete() {
    if (confirm('정말 삭제하시겠습니까?')) {
        deleteMyIngredient();
    }
}

function deleteMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    if (!my_ingredient_id) {
        alert('원료 ID가 없습니다.');
        return;
    }
    fetch(`/label/delete-my-ingredient/${my_ingredient_id}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('내 원료가 성공적으로 삭제되었습니다.');
            if (window.opener) {
                window.opener.location.reload();
            }
            window.close();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('삭제 중 오류가 발생했습니다.');
    });
}

// 폼 저장 함수
function saveMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    const formData = new FormData(document.getElementById("ingredientForm"));
    let url;
    if (my_ingredient_id) {
        url = `/label/my-ingredient-detail/${my_ingredient_id}/`;
    } else {
        url = '/label/my-ingredient-detail/';
    }
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (response.ok) {
            if (response.headers.get('content-type').includes('application/json')) {
                return response.json();
            } else {
                return { success: true };
            }
        }
        throw new Error('Network response was not ok.');
    })
    .then(data => {
        if (data.success) {
            // 왼쪽 리스트 갱신 및 신규 원료 상세 표시
            fetch('/label/my-ingredient-table-partial/')
                .then(res => res.text())
                .then(tableHtml => {
                    const tbody = document.querySelector('#ingredientTable tbody');
                    if (tbody) {
                        tbody.innerHTML = tableHtml;
                        if (data.ingredient_id) {
                            const newRow = document.querySelector(`.ingredient-row[data-ingredient-id='${data.ingredient_id}']`);
                            if (newRow) {
                                loadIngredientDetail(data.ingredient_id, newRow);
                            }
                        }
                    }
                });
        } else {
            alert(data.error || '저장에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('저장 중 오류가 발생했습니다.');
    });
}

// 쿠키에서 CSRF 토큰 가져오기
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

// select2 식품유형 드롭다운 초기화
function initFoodTypeSelect() {
    const foodTypesRaw = document.getElementById('food-types-data')?.textContent;
    const agriProductsRaw = document.getElementById('agricultural-products-data')?.textContent;
    const foodAdditivesRaw = document.getElementById('food-additives-data')?.textContent;
    let foodTypes = [], agriProducts = [], foodAdditives = [];
    try {
        foodTypes = JSON.parse(foodTypesRaw || '[]');
        agriProducts = JSON.parse(agriProductsRaw || '[]');
        foodAdditives = JSON.parse(foodAdditivesRaw || '[]');
    } catch (e) {
        console.error('[initFoodTypeSelect] JSON parse error:', e);
    }
    const select = document.getElementById('foodTypeSelect');
    if (!select) {
        console.error('[initFoodTypeSelect] #foodTypeSelect not found');
        return;
    }

    // 현재 식품 구분 값을 가져옴
    const foodCategorySelect = document.getElementById('foodCategorySelect');
    const currentFoodCategory = foodCategorySelect ? foodCategorySelect.value : 'processed';
    
    // 식품 구분에 따라 옵션 필터링
    let options = [];
    
    switch (currentFoodCategory) {
        case 'processed': // 가공식품
            options = foodTypes.map(ft => ({ id: ft.food_type, text: ft.food_type }));
            break;
        case 'agricultural': // 농수산물
            options = agriProducts.map(ap => ({ id: ap.name_kr, text: ap.name_kr }));
            break;
        case 'additive': // 식품첨가물
            options = foodAdditives.map(fa => ({ id: fa.name_kr, text: fa.name_kr }));
            break;
        default:
            options = [
                ...foodTypes.map(ft => ({ id: ft.food_type, text: ft.food_type })),
                ...agriProducts.map(ap => ({ id: ap.name_kr, text: ap.name_kr })),
                ...foodAdditives.map(fa => ({ id: fa.name_kr, text: fa.name_kr }))
            ];
    }
    
    // 옵션을 select에 직접 추가
    select.innerHTML = '<option></option>';
    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt.id;
        option.textContent = opt.text;
        select.appendChild(option);
    });
    
    // select2 적용
    $(select).select2({
        width: '100%',
        placeholder: '식품유형 선택',
        allowClear: true
    });
    
    // 기존 값이 있으면 선택
    const currentValue = select.getAttribute('data-selected') || select.value;
    if (currentValue) {
        $(select).val(currentValue).trigger('change');
    }
}

// 알레르기와 GMO 옵션 초기화 함수
function initAllergyAndGmoOptions() {
    // showAllergyOptions와 showGmoOptions를 window에서 가져와 실행
    if (typeof window.showAllergyOptions === 'function') {
        window.showAllergyOptions();
    }
    if (typeof window.showGmoOptions === 'function') {
        window.showGmoOptions();
    }
    // 초기 상태를 접혀있게 설정
    if (typeof window.initializeSelections === 'function') {
        window.initializeSelections();
    }
}

// 식품 구분 선택 변경시 식품유형 드롭다운 갱신
function setupFoodCategoryChangeEvent() {
    const foodCategorySelect = document.getElementById('foodCategorySelect');
    if (foodCategorySelect) {
        foodCategorySelect.addEventListener('change', function() {
            initFoodTypeSelect();
        });
    }
}

// DOMContentLoaded 또는 즉시 실행 패턴으로 이벤트 바인딩
function onReady(fn) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
    } else {
        fn();
    }
}

onReady(function() {
    initFoodTypeSelect();
    setupFoodCategoryChangeEvent();
    initAllergyAndGmoOptions(); // 알레르기와 GMO 옵션 초기화
    
    // 폼 submit 이벤트 바인딩 (partial에서도 반드시 필요)
    var form = document.getElementById('ingredientForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof updateAllergyInfo === 'function') updateAllergyInfo();
            if (typeof updateGmoInfo === 'function') updateGmoInfo();
            saveMyIngredient();
        });
    }

    // 삭제 버튼 이벤트 바인딩 
    var deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', confirmDelete);
    }
    
    // 초기화 버튼 이벤트 바인딩
    var closeBtn = document.getElementById('closeBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            if(confirm('입력 내용을 초기화하시겠습니까?')) {
                form.reset();
                initFoodTypeSelect(); // 식품유형도 초기화
                initAllergyAndGmoOptions();
            }
        });
    }
});