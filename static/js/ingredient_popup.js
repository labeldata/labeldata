document.addEventListener('DOMContentLoaded', () => {
    
    const savedIngredients = JSON.parse(document.getElementById('saved-ingredients-data').textContent);
    const urlParams = new URLSearchParams(window.location.search);
    const labelId = urlParams.get('label_id');

    if (!labelId) {
        alert('라벨 ID가 없습니다.');
        window.close();
        return;
    }

    const tbody = document.getElementById('ingredient-body');
    new Sortable(tbody, { animation: 150, handle: '.drag-handle', onEnd: updateTargetButtons });

    try {
        // 서버에서 전달받은 JSON 문자열을 파싱
        if (savedIngredients && savedIngredients.length > 0) {
            savedIngredients.forEach(ingredient => {
                addIngredientRowWithData(ingredient);
            });
            sortRows(); // 비율에 따라 정렬
        } else {
            // 관계 테이블에 데이터가 없을 때 원재료명을 ,로 구분하여 각 행으로 추가
            const rawMaterialNames = '{{ rawmtrl_nm|escapejs }}';
            addIngredientRows(rawMaterialNames);
        }
    } catch (error) {
        console.error('데이터 파싱 오류:', error);
    }

    // 전체선택 체크박스
    document.getElementById('select-all').addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('#ingredient-body .delete-checkbox');
        checkboxes.forEach(checkbox => checkbox.checked = this.checked);
    });

    // input 이벤트 리스너는 자동 확장 기능만 담당
    document.addEventListener('input', function (event) {
        if (event.target.classList.contains('auto-expand')) {
            event.target.style.height = 'auto';
            event.target.style.height = event.target.scrollHeight + 'px';
            updateTableHeight();
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

    // 비율 입력 필드에 대한 이벤트 리스너 추가
    document.querySelectorAll('.ratio-input').forEach(input => {
        input.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sortRows();
            }
        });
    });
});

// 원재료명을 ,로 구분하여 각 행으로 추가하는 함수
function addIngredientRows(rawMaterialNames) {
    if (!rawMaterialNames) return;

    const materials = rawMaterialNames.split(',');
    materials.forEach(material => {
        addIngredientRow(material.trim());
    });
}

// 원재료명을 ,로 구분하여 각 행으로 추가하는 기존 코드 대신,
// 아래와 같이 다른 행과 동일한 레이아웃으로 행을 추가하도록 수정합니다.
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
                <input type="text" class="form-control form-control-sm" placeholder="비율 (%)">
            </div>
        </td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" class="form-control form-control-sm" placeholder="품목보고번호" maxlength="15">
                <input type="text" class="form-control form-control-sm" placeholder="식품유형">
            </div>
        </td>
        <td>
            <textarea class="form-control form-control-sm auto-expand" placeholder="원재료 표시명">${material}</textarea>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" placeholder="" onclick="showAllergyOptions(this)">
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" placeholder="" onclick="showGMOOptions(this)">
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" placeholder="제조사">
        </td>
        <td>
            <div class="d-flex flex-column">
                <button type="button" class="btn btn-sm btn-secondary" onclick="registerMyIngredient(this)">등록</button>
            </div>
        </td>
    `;
    document.getElementById('ingredient-body').appendChild(row);
    updateTargetButtons();
}

function updateTargetButtons() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const button = row.querySelector('.btn-target');
        if (button) {
            button.style.display = 'none';
        }
    });
}

function sortRows() {
    console.log('정렬 시작');
    const tbody = document.getElementById('ingredient-body');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.sort((a, b) => {
        const ratioA = parseFloat(a.querySelector('.ratio-input')?.value) || 0;
        const ratioB = parseFloat(b.querySelector('.ratio-input')?.value) || 0;
        console.log(`비교: ${ratioA} vs ${ratioB}`);
        return ratioB - ratioA;
    });
    
    while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
    }
    rows.forEach(row => tbody.appendChild(row));
    console.log('정렬 완료');
    updateTargetButtons();
}

function updateTableHeight() {
    const tableContainer = document.querySelector('.table-container');
    tableContainer.style.height = 'auto';
    tableContainer.style.height = tableContainer.scrollHeight + 'px';
}

function checkOrigin() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    rows.forEach((row, index) => {
        const button = row.querySelector('.btn-target');
        if (button) {
            button.style.display = index < 3 ? 'inline-block' : 'none';
        }
    });
}

function fetchFoodItemData(input) {
    const prdlstReportNo = input.closest('tr').querySelector('input[maxlength="15"]').value;
    if (!prdlstReportNo) return;

    fetch(`/fetch-food-item/${prdlstReportNo}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const row = input.closest('tr');
                row.querySelector('input[readonly]').value = data.prdlst_nm;
            } else {
                alert('품목제조번호를 찾을 수 없습니다.');
            }
        })
        .catch(error => console.error('Error:', error));
}

function validateFoodType(input) {
    const foodType = input.value.trim();
    if (!foodType) return;
    fetch(`/validate-food-type/${foodType}/`)
        .then(response => response.json())
        .then(data => {
            if (!data.valid) {
                alert('식품 유형을 올바로 입력하세요');
            }
        })
        .catch(error => console.error('Error:', error));
}

function removeSelectedRows() {
    document.querySelectorAll('#ingredient-body .delete-checkbox:checked')
            .forEach(input => input.closest('tr').remove());
    updateTargetButtons();
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function searchMyIngredient(textarea) {
    const searchName = textarea.value.trim();
    const row = textarea.closest('tr');
    
    console.log("검색어:", searchName);
    
    fetch('/label/check-ingredient-display-name/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ ingredient_name: searchName })
    })
    .then(response => response.json())
    .then(data => {
        console.log('데이터:', data);
        const resultsDiv = document.getElementById('modalSearchResults');
        resultsDiv.innerHTML = '';
        if (data.success && data.ingredients && data.ingredients.length > 0) {
            let html = '<div>';
            data.ingredients.forEach((ingredient, index) => {
                html += `
                    <div class="d-flex align-items-center border p-2 mb-2">
                        <div class="flex-grow-1">
                            <div>
                                <span><strong>원료명:</strong> ${ingredient.prdlst_nm}</span><br>
                                <span><strong>비율:</strong> ${ingredient.ingredient_ratio || ''}</span>
                            </div>
                            <div class="mt-2">
                                <span><strong>품목제조번호:</strong> ${ingredient.prdlst_report_no}</span><br>
                                <span><strong>식품유형:</strong> ${ingredient.prdlst_dcnm}</span>
                            </div>
                            <div class="mt-2">
                                <span><strong>제조사:</strong> ${ingredient.bssh_nm}</span>
                            </div>
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-primary" onclick="setIngredientFromModal(${index})">추가</button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            resultsDiv.innerHTML = html;
            // 저장할 검색 결과들을 전역 변수에 저장 (후에 선택 시 사용)
            window.searchResults = data.ingredients;
        } else {
            resultsDiv.innerHTML = `<div>${data.error || '검색 결과가 없습니다.'}</div>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('검색 중 오류가 발생했습니다.');
    });
}

// 파일: ingredient_popup.html 내 addIngredientRowWithData 함수 수정
function addIngredientRowWithData(ingredient, fromModal = false) {
    const readonlyClass = fromModal ? "modal-readonly-field" : "";
    // fromModal가 true일 때만 readonly 속성을 추가하고, 아니면 빈 문자열로 처리
    const readonlyAttr = fromModal ? "readonly" : "";
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="checkbox" class="delete-checkbox form-check-input"></td>
        <td class="drag-handle">☰</td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" value="${ingredient.ingredient_name}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="원재료명" ${readonlyAttr}>
                <input type="text" value="${ingredient.ratio || ''}" 
                       class="form-control form-control-sm ratio-input ${readonlyClass}" placeholder="비율 (%)" ${readonlyAttr}>
            </div>
        </td>
        <td>
            <div class="d-flex flex-column">
                <input type="text" value="${ingredient.prdlst_report_no}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="품목보고번호" ${readonlyAttr}>
                <input type="text" value="${ingredient.food_type}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="식품유형" ${readonlyAttr}>
            </div>
        </td>
        <td>
            <textarea class="form-control form-control-sm bordered-input auto-expand ${readonlyClass}" 
                      placeholder="원재료 표시명" ${readonlyAttr}>${ingredient.display_name || ingredient.ingredient_name}</textarea>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm bordered-input ${readonlyClass}" 
                   onclick="showAllergyOptions(this)" value="${ingredient.allergen}" ${readonlyAttr}>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm bordered-input ${readonlyClass}" 
                   onclick="showGMOOptions(this)" value="${ingredient.gmo}" ${readonlyAttr}>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm bordered-input ${readonlyClass}" 
                   value="${ingredient.manufacturer}" ${readonlyAttr}>
        </td>
        <td>
            <div class="d-flex flex-column">
                <button type="button" class="btn btn-sm btn-secondary" onclick="registerMyIngredient(this)">등록</button>
            </div>
        </td>
    `;
    document.getElementById('ingredient-body').appendChild(row);
    updateTargetButtons();
}

function addMyIngredientFromSearch() {
    const searchInput = document.getElementById('search-input');
    const searchValue = searchInput.value.trim();
    
    if (!searchValue) {
        alert('검색어를 입력해주세요.');
        return;
    }
    
    console.log("검색어:", searchValue);
    
    fetch('/label/search-ingredient-add-row/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ ingredient_name: searchValue })
    })
    .then(response => response.json())
    .then(data => {
        console.log("검색 결과:", data);
        if (data.success && data.ingredient) {
            addIngredientRowWithData(data.ingredient);
            searchInput.value = '';
        } else {
            alert(data.error || '검색 결과가 없습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('검색 중 오류가 발생했습니다.');
    });
}


function verifyRows() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    const promises = [];
    
    rows.forEach((row, index) => {
        // 각 행에서 데이터 추출 (테이블 헤더 순서에 맞춤)
        const ingName = row.querySelector('td:nth-child(3) input')?.value || "";
        const ratio = row.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value || "";
        const reportNo = row.querySelector('td:nth-child(4) input')?.value || "";
        const foodType = row.querySelector('td:nth-child(4) input:nth-of-type(2)')?.value || "";
        const displayName = row.querySelector('td:nth-child(5) textarea')?.value || "";
        const allergen = row.querySelector('td:nth-child(6) input')?.value || "";
        const gmo = row.querySelector('td:nth-child(7) input')?.value || "";
        const manufacturer = row.querySelector('td:nth-child(8) input')?.value || "";
        
        const ingredient = {
            ingredient_name: ingName,
            ratio: ratio,
            prdlst_report_no: reportNo,
            food_type: foodType,
            display_name: displayName,
            allergen: allergen,
            gmo: gmo,
            manufacturer: manufacturer
        };
        
        // 각 행에 대해 개별 fetch 요청 (ingredient 단일 객체를 전송)
        const p = fetch('/label/verify-ingredients/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ ingredient: ingredient })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && typeof data.results !== "undefined") {
                if (data.results) {
                    // 이미 존재하는 경우: 해당 행의 모든 입력 필드를 readonly로 만들고 스타일 적용
                    row.querySelectorAll('input, textarea').forEach(field => {
                        if (!field.classList.contains('ratio-input')) {
                            field.setAttribute('readonly', true);
                            field.classList.add('modal-readonly-field');
                        }
                    });
                    // 예를 들어 불러오기 버튼 활성화 (버튼이 있다면)
                    // const loadBtn = row.querySelector('button.btn-secondary');
                    // if (loadBtn) {
                    //     loadBtn.removeAttribute('disabled');
                    // }
                }
            } else {
                console.error('Row ' + index + ' 검증 오류: ' + (data.error || '알 수 없는 오류'));
            }
        })
        .catch(error => {
            console.error('Row ' + index + ' 처리 중 오류: ' + error.message);
        });
        
        promises.push(p);
    });
    
    // 모든 행에 대한 fetch 요청이 완료되면 최종 메시지 표시
    Promise.all(promises).then(() => {
        alert('모든 행에 대해 개별 검증이 완료되었습니다.');
    });
}

function registerMyIngredient(button) {
    const row = button.closest('tr');
    const prdlstReportInput = row.querySelector('td:nth-child(4) input');
    const prdlst_report_no = prdlstReportInput ? prdlstReportInput.value.trim() : "";
    const foodTypeInput = row.querySelector('td:nth-child(4) input:nth-of-type(2)');
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
    
    console.log("조회 조건:", criteria);
    
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
        console.log("조회 결과:", data);
        if (data.exists) {
            alert("이미 해당 조건에 해당하는 원료가 존재합니다.");
            showExistingIngredientsModal(data.ingredients);
        } else {
            const ingredientData = {
                ingredient_name: row.querySelector('td:nth-child(3) input')?.value.trim() || "",
                prdlst_report_no: prdlst_report_no,
                food_type: food_type,
                display_name: display_name,
                manufacturer: row.querySelector('td:nth-child(8) input')?.value.trim() || ""
            };
            console.log("등록 데이터:", ingredientData);
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
                console.log("등록 결과:", regData);
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
                console.error("등록 요청 오류:", error);
                alert("등록 중 오류가 발생했습니다.");
            });
        }
    })
    .catch(error => {
        console.error("조회 오류:", error);
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
            // ratio: window.currentRow.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value || "",
            prdlst_report_no: window.currentRow.querySelector('td:nth-child(4) input:first-of-type')?.value || "",
            food_type: window.currentRow.querySelector('td:nth-child(4) input:nth-of-type(2)')?.value || "",
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

        inputContainer.appendChild(ingredientInput);
        inputContainer.appendChild(reportInput);
        inputContainer.appendChild(foodTypeInput);
        inputContainer.appendChild(manufacturerInput);
        firstLine.appendChild(inputContainer);

        const buttonContainer = document.createElement('div');
        buttonContainer.style.width = '100px';
        buttonContainer.classList.add('text-end');
        const selectButton = document.createElement('button');
        selectButton.type = 'button';
        selectButton.classList.add('btn', 'btn-sm', 'btn-secondary');
        selectButton.textContent = '선택';
        selectButton.addEventListener('click', () => {
            console.log('선택된 원료:', ingredient);
            if (window.currentRow) {
                window.currentRow.querySelector('td:nth-child(3) input:first-of-type').value = ingredientInput.value;
                window.currentRow.querySelector('td:nth-child(4) input:first-of-type').value = reportInput.value;
                window.currentRow.querySelector('td:nth-child(4) input:nth-of-type(2)').value = foodTypeInput.value;
                window.currentRow.querySelector('td:nth-child(5) textarea').value = displayInput.value;
                window.currentRow.querySelector('td:nth-child(8) input').value = manufacturerInput.value;
                
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

function registerNewIngredient() {
    if (!window.currentRow) {
        alert("등록할 행의 데이터가 없습니다.");
        return;
    }
    // 현재 행에서 데이터를 추출합니다.
    const ingredientData = {
        ingredient_name: window.currentRow.querySelector('td:nth-child(3) input:first-of-type')?.value.trim() || "",
        ratio: window.currentRow.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value.trim() || "",
        prdlst_report_no: window.currentRow.querySelector('td:nth-child(4) input:first-of-type')?.value.trim() || "",
        food_type: window.currentRow.querySelector('td:nth-child(4) input:nth-of-type(2)')?.value.trim() || "",
        display_name: window.currentRow.querySelector('td:nth-child(5) textarea')?.value.trim() || "",
        manufacturer: window.currentRow.querySelector('td:nth-child(8) input')?.value.trim() || ""
    };
    
    console.log("신규 등록 데이터:", ingredientData);
    
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
        console.error("등록 요청 오류:", error);
        alert("등록 중 오류가 발생했습니다.");
    });
}

// 저장 버튼 클릭 시 호출되는 함수 내, 행 전체가 readonly 상태인지 확인하는 함수 예시
function verifyAllRowsDisabled() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    let allDisabled = true;
    rows.forEach(row => {
        const fields = row.querySelectorAll('input, textarea');
        fields.forEach(field => {
            if (!field.hasAttribute('readonly')) {
                allDisabled = false;
            }
        });
    });
    if (allDisabled) {
        console.log("모든 행이 비활성화 되어있습니다.");
        alert("모든 행이 비활성화 되어있습니다.");
    } else {
        console.log("비활성화되지 않은 행이 있습니다.");
        alert("비활성화되지 않은 행이 있습니다.");
    }
}

function saveIngredients() {
    // URL에서 label_id 값 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const labelId = urlParams.get('label_id');
    if (!labelId) {
        alert("라벨 ID를 찾을 수 없습니다.");
        return;
    }
    
    // 모든 행의 입력 필드가 readonly 상태 (비활성화)인지 확인 (비율 칸 제외)
    const rows = document.querySelectorAll('#ingredient-body tr');
    let allDisabled = true;
    rows.forEach(row => {
        // ratio-input 클래스를 가진 입력 필드는 제외
        const fields = row.querySelectorAll('input:not(.ratio-input), textarea');
        fields.forEach(field => {
            if (!field.hasAttribute('readonly')) {
                allDisabled = false;
            }
        });
    });
    if (!allDisabled) {
        alert("모든 행이 비활성화되어 있지 않습니다. 저장 전에 모든 행이 등록(비활성화) 상태인지 확인해주세요.");
        return;
    }
    
    // 각 행의 데이터를 배열로 모음
    const ingredients = [];
    rows.forEach(row => {
        const ingredient = {
            ingredient_name: row.querySelector('td:nth-child(3) input:first-of-type')?.value.trim() || "",
            ratio: row.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value.trim() || "",
            prdlst_report_no: row.querySelector('td:nth-child(4) input:first-of-type')?.value.trim() || "",
            food_type: row.querySelector('td:nth-child(4) input:nth-of-type(2)')?.value.trim() || "",
            display_name: row.querySelector('td:nth-child(5) textarea')?.value.trim() || "",
            manufacturer: row.querySelector('td:nth-child(8) input')?.value.trim() || ""
        };
        ingredients.push(ingredient);
    });
    console.log("저장할 원료 데이터:", ingredients);
    
    // CSRF 토큰 가져오기
    const csrftoken = getCookie('csrftoken');
    
    // 서버의 저장 엔드포인트로 POST 요청 전송
    fetch(`/label/save-ingredients-to-label/${labelId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ ingredients: ingredients })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("모든 원료가 성공적으로 저장되었습니다.");
        } else {
            alert("원료 저장 실패: " + (data.error || "알 수 없는 오류"));
        }
    })
    .catch(error => {
        console.error("저장 요청 오류:", error);
        alert("저장 중 오류가 발생했습니다.");
    });
}