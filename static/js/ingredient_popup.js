document.addEventListener('DOMContentLoaded', () => {
    
    const savedIngredients = JSON.parse(document.getElementById('saved-ingredients-data').textContent);
    const hasRelations = document.querySelector('.popup-container').dataset.hasRelations === 'true';  // 플래그를 JS 변수로 전달
    

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
        if (hasRelations) {
            savedIngredients.forEach(ingredient => {
                addIngredientRowWithData(ingredient);
            });
            sortRows(); // 비율에 따라 정렬
        } else {
            // 관계 테이블에 데이터가 없을 때 원재료명을 ,로 구분하여 각 행으로 추가
            // const rawMaterialNames = '{{ ingredient_name|escapejs }}';
            // addIngredientRows(rawMaterialNames);
            console.log("savedIngredients:", savedIngredients);  // savedIngredients 출력
            addIngredientRows(savedIngredients);
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
        console.log("검색 결과 데이터:", data); // 서버로부터 받은 데이터를 콘솔에 출력

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
        console.error('검색 중 오류가 발생했습니다:', error);
        alert('검색 중 오류가 발생했습니다.');
    });
}

function selectIngredient(ingredient, button) {
    console.log('선택된 원료:', ingredient);

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

// savedIngredients 배열을 받아 각 객체의 ingredient_name을 사용하여 행을 추가하는 함수
function addIngredientRows(savedIngredients) {
    if (!savedIngredients || savedIngredients.length === 0) return;

    savedIngredients.forEach(ingredient => {
        addIngredientRow(ingredient.ingredient_name.trim());
    });
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
                <input type="text" class="form-control form-control-sm" placeholder="식품유형">
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
    updateTargetButtons();

    // 새로 추가된 비율 입력 필드에 이벤트 리스너 추가
    const ratioInput = row.querySelector('.ratio-input');
    ratioInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            sortRows();
        }
    });

    return row; // 추가된 행을 반환
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
                my_ingredient_id: my_ingredient_id,
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
            console.log('선택된 원료:', ingredient);
            if (window.currentRow) {
                window.currentRow.querySelector('td:nth-child(3) input:first-of-type').value = ingredientInput.value;
                window.currentRow.querySelector('td:nth-child(4) input:first-of-type').value = reportInput.value;
                window.currentRow.querySelector('td:nth-child(4) input:nth-of-type(2)').value = foodTypeInput.value;
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
        my_ingredient_id: row.querySelector('.my-ingredient-id')?.value.trim() || "",
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
                <input type="text" value="${ingredient.food_type}" 
                       class="form-control form-control-sm ${readonlyClass}" placeholder="식품유형" ${readonlyAttr}>
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
    updateTargetButtons();
}

// 원재료 저장 함수
function saveIngredients() {
    const rows = document.querySelectorAll('#ingredient-body tr');
    const ingredients = [];
    
    rows.forEach(row => {
        const ingredient = {
            ingredient_name: row.querySelector('td:nth-child(3) input:first-of-type')?.value.trim() || "",
            ratio: row.querySelector('td:nth-child(3) input:nth-of-type(2)')?.value.trim() || "",
            prdlst_report_no: row.querySelector('td:nth-child(4) input:first-of-type')?.value.trim() || "",
            food_type: row.querySelector('td:nth-child(4) input:nth-of-type(2)')?.value.trim() || "",
            display_name: row.querySelector('td:nth-child(5) textarea')?.value.trim() || "",
            //notes: row.querySelector('td:nth-child(6) textarea')?.value.trim() || "",  // 참고사항 필드 추가
            allergen: row.querySelector('.allergen-input')?.value.trim() || "",
            gmo: row.querySelector('.gmo-input')?.value.trim() || "",
            manufacturer: row.querySelector('td:nth-child(8) input')?.value.trim() || "",
            my_ingredient_id: row.querySelector('.my-ingredient-id')?.value.trim() || ""
        };
        ingredients.push(ingredient);
    });
    
    // 나머지 코드는 동일하게 유지
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

// 원산지 관리 함수 추가 (기본 구조만 구현)
function validateOrigin() {
    // 선택된 행이 있는지 확인
    const selectedRows = document.querySelectorAll('#ingredient-body .delete-checkbox:checked');
    if (selectedRows.length === 0) {
        alert('원산지를 설정할 행을 선택해주세요.');
        return;
    }
    
    // 여기에 원산지 관련 기능을 나중에 추가할 수 있습니다.
    alert('원산지 관리 기능이 준비 중입니다.');
}

// 현재 열린 모달에 연결된 행 요소를 저장하는 변수
let currentModalRow = null;

// 알레르기 모달 열기 함수 수정
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
    const allergyButton = currentModalRow.querySelector('.allergen-btn');  // 클래스 선택자 사용
    
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


// GMO 모달 열기 함수 수정
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
    const gmoButton = currentModalRow.querySelector('.gmo-btn');  // 클래스 선택자 사용
    
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

// 읽기 전용 알레르기/GMO 정보를 보여주는 함수 수정
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