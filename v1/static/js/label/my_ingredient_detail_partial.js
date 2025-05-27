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
            // 부모창 새로고침
            if (window.opener) {
                window.opener.location.reload();
            } else if (window.parent && window.parent !== window) {
                window.parent.location.reload();
            }
            // 현재창 새로고침
            window.location.reload();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('삭제 중 오류가 발생했습니다.');
    });
}

// 삭제 버튼 클릭 이벤트 핸들러 (partial에서 사용)
function handleDeleteIngredientPartial(ingredientId) {
    if (!ingredientId) {
        alert('삭제할 원료 ID가 없습니다.');
        return;
    }
    if (!confirm('정말로 이 원료를 삭제하시겠습니까?')) {
        return;
    }
    fetch(`/label/delete-my-ingredient/${ingredientId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // 부모창 새로고침
            if (window.opener) {
                window.opener.location.reload();
            } else if (window.parent && window.parent !== window) {
                window.parent.location.reload();
            }
            // 현재 partial 창 새로고침
            window.location.reload();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(err => {
        alert('삭제 중 오류가 발생했습니다.');
        console.error(err);
    });
}

// 폼 저장 함수 (검색 조건 유지, 테이블 컬럼 순서 맞춤)
function saveMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    const formElem = document.getElementById("ingredientForm");
    const formData = new FormData(formElem);
    let url;
    if (my_ingredient_id) {
        url = `/label/my-ingredient-detail/${my_ingredient_id}/`;
    } else {
        url = '/label/my-ingredient-detail/';
    }

    // 검색 조건 쿼리스트링 추출 (ingredientTable이 있는 페이지에서만 동작)
    let queryString = '';
    const searchForm = document.querySelector('form[action*="my_ingredient_list_combined"]');
    if (searchForm) {
        const params = new URLSearchParams(new FormData(searchForm));
        queryString = '?' + params.toString();
    } else {
        // fallback: 현재 URL에서 쿼리스트링만 추출
        const qs = window.location.search;
        if (qs) queryString = qs;
    }

    // 저장 버튼 비활성화(중복 저장 방지)
    const saveBtn = document.querySelector('button[type="submit"][form="ingredientForm"]');
    if (saveBtn) saveBtn.disabled = true;

    // 원재료명 필수값 체크
    const prdlst_nm = formData.get('prdlst_nm')?.trim();
    if (!prdlst_nm) {
        alert('원재료명은 필수 입력값입니다.');
        if (saveBtn) saveBtn.disabled = false;
        document.getElementById('prdlst_nm').focus();
        return;
    }

    // 원재료명 중복 체크 (신규 등록 시에만)
    if (!my_ingredient_id && prdlst_nm) {
        fetch('/label/check-my-ingredient/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ prdlst_nm })
        })
        .then(res => res.json())
        .then(data => {
            if (data.exists) {
                if (!confirm('동일한 이름의 원료가 이미 존재합니다. 그래도 저장하시겠습니까?')) {
                    if (saveBtn) saveBtn.disabled = false;
                    return;
                } else {
                    // 중복 무시 의도 전달
                    formData.append('ignore_duplicate', 'Y');
                }
            }
            doSaveMyIngredient(url, formData, queryString, function() {
                if (saveBtn) saveBtn.disabled = false;
            });
        })
        .catch(() => {
            if (saveBtn) saveBtn.disabled = false;
            alert('중복 체크 중 오류가 발생했습니다.');
        });
        return;
    }
    // 기존 원료 수정 또는 원재료명 미입력 시 바로 저장
    doSaveMyIngredient(url, formData, queryString, function() {
        if (saveBtn) saveBtn.disabled = false;
    });
}

// doSaveMyIngredient에 콜백 추가
function doSaveMyIngredient(url, formData, queryString, doneCallback) {
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
            // 왼쪽 리스트 갱신 및 신규 원료 상세 표시 (검색 조건 유지)
            fetch('/label/my-ingredient-table-partial/' + queryString)
                .then(res => res.text())
                .then(tableHtml => {
                    const tbody = document.querySelector('#ingredientTable tbody');
                    if (tbody) {
                        tbody.innerHTML = tableHtml;
                        // 리스트 갱신 후 클릭 이벤트 재바인딩
                        if (typeof window.bindIngredientRowClickEvents === 'function') {
                            window.bindIngredientRowClickEvents();
                        }
                        if (data.ingredient_id) {
                            const newRow = document.querySelector(`.ingredient-row[data-ingredient-id='${data.ingredient_id}']`);
                            if (newRow) {
                                loadIngredientDetail(data.ingredient_id, newRow);
                            }
                        }
                    }
                });
            // 저장 성공 후 변경 감지 플래그 해제
            if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
        } else {
            alert(data.error || '저장에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('저장 중 오류가 발생했습니다.1');
    })
    .finally(() => {
        if (typeof doneCallback === 'function') doneCallback();
    });
}

// 원료 상세 상단에 연결된 표시사항 조회 버튼 추가 함수
function addLinkedLabelsButton(my_ingredient_id) {
    if (!my_ingredient_id) return;
    fetch(`/label/linked-labels-count/${my_ingredient_id}/`)
        .then(res => res.json())
        .then(data => {
            // 기존 버튼 있으면 제거
            const oldBtn = document.getElementById('linkedLabelsViewBtn');
            if (oldBtn) oldBtn.remove();
            // 버튼 생성
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-outline-info btn-sm ms-2';
            btn.id = 'linkedLabelsViewBtn';
            btn.innerHTML = `연결된 표시사항(<span id="linkedLabelsCount">${data.count}</span>품목) 조회`;
            btn.onclick = function() {
                // 리스트보기와 동일하게 이동
                window.location.href = '/label/my-labels/?ingredient_id=' + encodeURIComponent(my_ingredient_id);
            };
            // '원료 수정' 텍스트 옆에 삽입 (예시: id가 ingredientTitle인 요소 옆)
            const titleElem = document.getElementById('ingredientEditTitle') || document.querySelector('.ingredient-edit-title');
            if (titleElem) {
                titleElem.insertAdjacentElement('afterend', btn);
            }
        });
}

// 연결된 표시사항(00품목) 조회 버튼 텍스트 및 이벤트 설정
function updateLinkedLabelsButton(my_ingredient_id) {
    const btn = document.getElementById('linkedLabelsBtn');
    if (!btn || !my_ingredient_id) return;
    fetch(`/label/linked-labels-count/${my_ingredient_id}/`)
        .then(res => res.json())
        .then(data => {
            btn.innerHTML = `연결된 표시사항(<span id="linkedLabelsCount">${data.count}</span>품목) 조회`;
            btn.onclick = function() {
                if (data.count && data.count > 0) {
                    window.location.href = '/label/my-labels/?ingredient_id=' + encodeURIComponent(my_ingredient_id);
                } else {
                    alert('연결된 표시사항이 없습니다.');
                }
            };
        });
}

// CSRF 토큰 가져오기 유틸
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
    // window.setDetailDirty를 항상 전역에 노출 (dirty 감지 정상화)
    if (typeof window.setDetailDirty !== 'function' && typeof setDetailDirty === 'function') {
        window.setDetailDirty = setDetailDirty;
    }
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
                // 초기화 후 변경 감지 플래그 해제
                if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
            }
        });
    }

    // 연결된 표시사항 버튼 텍스트 및 이벤트 연결
    const my_ingredient_id_elem = document.getElementById('my_ingredient_id');
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    updateLinkedLabelsButton(my_ingredient_id);
});