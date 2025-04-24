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
    let url = window.location.pathname;
    if (!my_ingredient_id) {
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
            alert('내 원료가 성공적으로 저장되었습니다.');
            if (window.opener) {
                window.opener.location.reload();
            }
            window.close();
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
    // 옵션 구성
    const options = [
        ...foodTypes.map(ft => ({ id: ft.food_type, text: ft.food_type })),
        ...agriProducts.map(ap => ({ id: ap.name_kr, text: ap.name_kr })),
        ...foodAdditives.map(fa => ({ id: fa.name_kr, text: fa.name_kr }))
    ];
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

// 알레르기, GMO, 폼 이벤트 등 기타 함수는 기존 <script> 코드에서 추가로 복사해 넣으세요.
// 예: toggleAllergySelection, toggleGMOSelection, updateAllergyInfo, updateGMOInfo 등

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
    // ...기존 코드 참고하여 필요 함수 바인딩...
});