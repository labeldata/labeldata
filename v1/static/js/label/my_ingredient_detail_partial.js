// my_ingredient_detail_partial.html에서 분리된 스크립트
// my_ingredient_detail_partial.html에서 분리된 스크립트 (수정됨)
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

// doSaveMyIngredient 함수 수정
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
            // 신규 등록된 원료의 페이지 계산 및 이동
            if (data.ingredient_id && !document.getElementById('my_ingredient_id').value) {
                // 신규 등록의 경우 해당 원료가 있는 페이지 계산
                calculateIngredientPage(data.ingredient_id, queryString, function(targetPage) {
                    const urlParams = new URLSearchParams(queryString.replace('?', ''));
                    urlParams.set('page', targetPage);
                    const finalQueryString = '?' + urlParams.toString();
                    
                    // 해당 페이지로 리스트 갱신
                    updateIngredientListAndSelect(finalQueryString, data.ingredient_id);
                });
            } else {
                // 수정의 경우 현재 페이지에서 리스트 갱신
                updateIngredientListAndSelect(queryString, data.ingredient_id);
            }
            
            // 저장 성공 후 변경 감지 플래그 해제
            if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
        } else {
            alert(data.error || '저장에 실패했습니다.');
        }
    })
    .catch(error => {
    console.error('Error:', error);
        alert('저장 중 오류가 발생했습니다.');
    })
    .finally(() => {
        if (typeof doneCallback === 'function') doneCallback();
    });
}

// 신규 등록된 원료의 페이지 위치 계산
function calculateIngredientPage(ingredientId, queryString, callback) {
    // 현재 검색 조건으로 전체 리스트를 가져와서 해당 원료의 위치 계산
    const searchParams = new URLSearchParams(queryString.replace('?', ''));
    searchParams.delete('page'); // 페이지 파라미터 제거
    const searchQueryString = searchParams.toString();
    
    fetch(`/label/my-ingredient-calculate-page/?ingredient_id=${ingredientId}&${searchQueryString}`, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            callback(data.page || 1);
        } else {
            callback(1); // 오류 시 첫 번째 페이지로
        }
    })
    .catch(error => {
        console.error('Error calculating page:', error);
        callback(1); // 오류 시 첫 번째 페이지로
    });
}

// 리스트 갱신 및 원료 선택
function updateIngredientListAndSelect(queryString, ingredientId) {
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
                
                // 신규 등록된 원료 선택
                if (ingredientId) {
                    const targetRow = document.querySelector(`.ingredient-row[data-ingredient-id='${ingredientId}']`);
                    if (targetRow) {
                        loadIngredientDetail(ingredientId, targetRow);
                    } else {
                        // 해당 행이 없으면 첫 번째 행 선택
                        const firstRow = document.querySelector('.ingredient-row');
                        if (firstRow) {
                            const firstIngredientId = firstRow.getAttribute('data-ingredient-id');
                            loadIngredientDetail(firstIngredientId, firstRow);
                        }
                    }
                }
                
                // 페이지네이션 정보 업데이트
                if (typeof window.updatePaginationInfo === 'function') {
                    const currentPageMatch = queryString.match(/page=(\d+)/);
                    const currentPage = currentPageMatch ? parseInt(currentPageMatch[1]) : 1;
                    // 페이지네이션 정보는 서버에서 전달받아야 함
                    updatePaginationFromServer(queryString);
                }
            }
        })
        .catch(error => {
            console.error('Error updating ingredient list:', error);
        });
}

// 서버에서 페이지네이션 정보 가져오기
function updatePaginationFromServer(queryString) {
    fetch(`/label/my-ingredient-pagination-info/${queryString}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && typeof window.updatePaginationInfo === 'function') {
            window.updatePaginationInfo(data.current_page, data.total_pages, data.item_count);
        }
    })
    .catch(error => {
        console.error('Error updating pagination info:', error);
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

// 네임스페이스를 사용하여 전역 변수 충돌 방지
window.IngredientDetailPartial = window.IngredientDetailPartial || {};
window.IngredientDetailPartial.isSyncing = false;

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
        foodAdditives = JSON.parse(foodAdditivesRaw || '[]');    } catch (e) {
        return;
    }
    
    const select = document.getElementById('foodTypeSelect');
    if (!select) {
        return;
    }
    
    // 현재 식품 구분 값을 가져옴 - ingredient form 내부에서만 찾기
    const ingredientForm = document.getElementById('ingredientForm');
    const foodCategorySelect = ingredientForm ? ingredientForm.querySelector('#foodCategorySelect') : null;
    const currentFoodCategory = foodCategorySelect ? foodCategorySelect.value : 'processed';
    
    // debug logs removed
    
    const actualFoodCategory = currentFoodCategory || 'processed';
    
    // 식품 구분에 따라 옵션 필터링
    let options = [];
    
    if (actualFoodCategory === 'processed') {
        options = foodTypes.map(ft => {
            if (ft.food_type) {
                return { id: ft.food_type, text: ft.food_type, category: 'processed' };
            }
            return null;
        }).filter(Boolean);
    } else if (actualFoodCategory === 'agricultural') {
        options = agriProducts.map(ap => {
            const name = ap.name_kr;
            if (name) {
                return { id: name, text: name, category: 'agricultural' };
            }
            return null;
        }).filter(Boolean);
    } else if (actualFoodCategory === 'additive') {
        options = foodAdditives.map(fa => {
            const name = fa.name_kr;
            if (name) {
                return { id: name, text: name, category: 'additive' };
            }
            return null;
        }).filter(Boolean);    }
    
    // 옵션을 select에 직접 추가
    select.innerHTML = '<option></option>';
    options.forEach(opt => {
        if (!opt.id || !opt.text) return; // id/text가 없으면 추가하지 않음
        const option = document.createElement('option');
        option.value = opt.id;
        option.text = opt.text;
        option.setAttribute('data-category', opt.category);
        select.appendChild(option);
    });

    // select2 중복 바인딩 방지
    if ($(select).data('select2')) {
        $(select).off('change.foodtype');
        $(select).select2('destroy');
    }
    $(select).select2({
        width: '100%',
        placeholder: '식품유형 선택',
        allowClear: true
    });    // 기존 값이 있으면 선택
    const currentValue = select.getAttribute('data-selected') || select.value;
    if (currentValue) {
        $(select).val(currentValue).trigger('change.select2');
    } else {
        $(select).val(null).trigger('change.select2');
    }    // select2 change 이벤트: 식품유형 선택 시 식품 구분 자동 선택
    $(select).on('change.foodtype', function (e) {
        if (window.IngredientDetailPartial.isSyncing) return;
        const selectedOption = select.options[select.selectedIndex];
        if (!selectedOption) return;
        const selectedCategory = selectedOption.getAttribute('data-category');
        if (!selectedCategory) return;        if (foodCategorySelect && foodCategorySelect.value !== selectedCategory) {
            window.IngredientDetailPartial.isSyncing = true;
            foodCategorySelect.value = selectedCategory;
            initFoodTypeSelect();
            $(select).val(selectedOption.value).trigger('change.select2');
            window.IngredientDetailPartial.isSyncing = false;
        }
        
        // 표시규정 업데이트
        updateDisplayRegulation();
    });
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
    // 더 구체적으로 ingredient form 내부의 foodCategorySelect를 찾음
    const ingredientForm = document.getElementById('ingredientForm');
    const foodCategorySelect = ingredientForm ? ingredientForm.querySelector('#foodCategorySelect') : null;
    
        if (foodCategorySelect) {
        // 기존 onchange 속성 제거 (다른 스크립트에서 추가했을 수 있음)
        if (foodCategorySelect.hasAttribute('onchange')) {
            foodCategorySelect.removeAttribute('onchange');
        }
        
        // 기존 이벤트 리스너 제거 (중복 방지)
        foodCategorySelect.removeEventListener('change', handleFoodCategoryChange);
        foodCategorySelect.addEventListener('change', function(event) {
            // 식품 구분 변경됨 처리
            handleFoodCategoryChange();
        });
    }
}

// 식품 구분 변경 핸들러
function handleFoodCategoryChange() {
    if (window.IngredientDetailPartial.isSyncing) {
        return;
    }
    initFoodTypeSelect();
    updateDisplayRegulation(); // 표시규정 업데이트
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
    // DOM 요소들이 존재하는지 확인
    const foodCategorySelect = document.getElementById('foodCategorySelect');
    const foodTypeSelect = document.getElementById('foodTypeSelect');
    const ingredientForm = document.getElementById('ingredientForm');
    
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
    
    // 초기 표시규정 설정
    updateDisplayRegulation();
});

// 표시규정 정보 업데이트 함수
function updateDisplayRegulation() {
    // updateDisplayRegulation called
    
    // ingredient form 내부에서 요소를 찾음 (initFoodTypeSelect와 동일한 방식)
    const ingredientForm = document.getElementById('ingredientForm');
    const foodCategorySelect = ingredientForm ? ingredientForm.querySelector('#foodCategorySelect') : null;
    const foodTypeSelect = document.getElementById('foodTypeSelect');
    const displayRegulationRow = document.getElementById('display-regulation-row');
    const displayRegulationDisplay = document.getElementById('display_regulation_display');
    
    // elements presence checked
    
    if (!foodCategorySelect || !foodTypeSelect || !displayRegulationRow || !displayRegulationDisplay) {
    // 필수 요소가 누락되었습니다.
        return;
    }
    
    const foodCategory = foodCategorySelect.value;
    const foodType = foodTypeSelect.value;
    
    // current values inspected
    
    // 식품첨가물이 아니거나 식품유형이 없으면 숨김
    if (foodCategory !== 'additive' || !foodType) {
    // 식품첨가물이 아니거나 식품유형이 없음 - 숨김
        displayRegulationRow.style.display = 'none';
        displayRegulationDisplay.value = '';
        return;
    }
    
    // calling API for regulation info
    
    // API 호출하여 표시규정 정보 가져오기
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/label/get-additive-regulation/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            food_type: foodType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.regulation) {
            displayRegulationDisplay.value = data.regulation;
            displayRegulationRow.style.display = '';
        } else {
            displayRegulationRow.style.display = 'none';
            displayRegulationDisplay.value = '';
        }
    })
    .catch(error => {
        console.error('Error fetching regulation info:', error);
        displayRegulationRow.style.display = 'none';
        displayRegulationDisplay.value = '';
    });
}