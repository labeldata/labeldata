// my_ingredient_list_combined.html에서 분리된 스크립트 예시

// 변경 감지 플래그
let isDetailDirty = false;
let pendingIngredientId = null;
let pendingRowElement = null;

// 우측 패널 폼의 변경 감지
function setDetailDirty(dirty) {
    isDetailDirty = dirty;
}
function bindDetailChangeDetection() {
    // id가 바뀔 수 있으므로 두 컨테이너 모두에서 바인딩 시도
    const containers = [
        document.getElementById('ingredient-detail-container'),
        document.getElementById('ingredient-detail-container-partial')
    ];
    containers.forEach(container => {
        if (!container) return;
        container.querySelectorAll('input, textarea, select').forEach(el => {
            el.addEventListener('change', () => setDetailDirty(true));
            el.addEventListener('input', () => setDetailDirty(true));
        });
    });
}

// 좌측 행 클릭 핸들러
function handleIngredientRowClick(ingredientId, rowElement) {
    if (isDetailDirty) {
        pendingIngredientId = ingredientId;
        pendingRowElement = rowElement;
        showUnsavedChangesModal();
        return;
    }
    loadIngredientDetail(ingredientId, rowElement);
}

// 실제 상세 로드 함수
function loadIngredientDetail(ingredientId, row) {
    // 선택된 행 스타일 처리
    document.querySelectorAll('.ingredient-row.selected').forEach(el => {
        el.classList.remove('selected');
        el.style.backgroundColor = '';
        el.style.color = '';
    });
    if (row) {
        row.classList.add('selected');
        row.style.backgroundColor = '#536675';
        row.style.color = 'white';
    }
    let url;
    if (ingredientId) {
        url = `/label/my-ingredient-detail/${ingredientId}/`;
    } else {
        url = `/label/my-ingredient-detail/`;
    }
    fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('ingredient-detail-container').innerHTML = html;
        reloadPartialScript();
        setDetailDirty(false);
        bindDetailChangeDetection();
    });
}

// 신규 등록 폼 로드
function loadNewIngredientForm() {
    if (isDetailDirty) {
        pendingIngredientId = '';
        pendingRowElement = null;
        showUnsavedChangesModal();
        return;
    }
    fetch('/label/my-ingredient-detail/', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('ingredient-detail-container').innerHTML = html;
        clearSelectedRow();
        reloadPartialScript();
        setDetailDirty(false);
        bindDetailChangeDetection();
    });
}

function clearSelectedRow() {
    document.querySelectorAll('.ingredient-row.selected').forEach(el => {
        el.classList.remove('selected');
        el.style.backgroundColor = '';
        el.style.color = '';
    });
}

// 동적으로 partial JS와 옵션 JS를 다시 로드
function reloadPartialScript() {
    // 기존 partial script 제거
    const oldPartialScript = document.getElementById('partial-script');
    if (oldPartialScript) oldPartialScript.remove();
    // 기존 옵션 script 제거
    const oldOptionScript = document.getElementById('option-script');
    if (oldOptionScript) oldOptionScript.remove();

    // partial script 추가
    const partialScript = document.createElement('script');
    partialScript.id = 'partial-script';
    partialScript.src = '/static/js/label/my_ingredient_detail_partial.js?v=' + Date.now();
    document.body.appendChild(partialScript);

    // 옵션 script 추가
    const optionScript = document.createElement('script');
    optionScript.id = 'option-script';
    optionScript.src = '/static/js/label/my_ingredient_options.js?v=' + Date.now();
    document.body.appendChild(optionScript);
}

// 변경사항 저장 확인 모달 생성 및 이벤트 바인딩
function showUnsavedChangesModal() {
    let modal = document.getElementById('unsavedChangesModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'unsavedChangesModal';
        modal.tabIndex = -1;
        modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">수정사항 확인</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
            </div>
            <div class="modal-body">
              <p>변경사항이 있습니다.<br>저장하지 않고 이동하겠습니까?</p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" id="unsaved-discard-btn" data-bs-dismiss="modal">이동하기</button>
              <button type="button" class="btn btn-light" data-bs-dismiss="modal">유지하기</button>
            </div>
          </div>
        </div>
        `;
        document.body.appendChild(modal);
    }
    // 저장 버튼 제거, 이동/돌아가기만 남김
    document.getElementById('unsaved-discard-btn').onclick = function() {
        setDetailDirty(false);
        bootstrap.Modal.getInstance(modal).hide();
        if (pendingIngredientId !== null) {
            loadIngredientDetail(pendingIngredientId, pendingRowElement);
            pendingIngredientId = null;
            pendingRowElement = null;
        }
    };
    // 돌아가기(취소)는 모달만 닫음
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

document.addEventListener('DOMContentLoaded', function() {
    // 첫 번째 원료 행 자동 선택 및 상세 로드
    const firstRow = document.querySelector('.ingredient-row');
    if (firstRow) {
        const ingredientId = firstRow.getAttribute('data-ingredient-id');
        loadIngredientDetail(ingredientId, firstRow);
    } else {
        // 원료가 없으면 빈 폼 로드
        loadNewIngredientForm();
    }
    // 신규 등록 버튼 이벤트
    document.getElementById('newIngredientBtn').addEventListener('click', loadNewIngredientForm);

    // 좌측 행 클릭 이벤트 바인딩
    bindIngredientRowClickEvents();

    // 우측 패널 폼이 동적으로 로드될 때마다 AJAX 저장 이벤트 바인딩
    document.body.addEventListener('submit', function(e) {
        const form = e.target;
        if (form.closest('#ingredient-detail-container')) {
            e.preventDefault();
            const formData = new FormData(form);
            fetch(form.action, {
                method: form.method,
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(res => {
                if (res.headers.get('content-type') && res.headers.get('content-type').includes('application/json')) {
                    return res.json();
                } else {
                    return { success: true };
                }
            })
            .then(data => {
                if (data.success) {
                    setDetailDirty(false);
                    // 모달 닫기
                    const modal = document.getElementById('unsavedChangesModal');
                    if (modal) bootstrap.Modal.getInstance(modal)?.hide();
                    // 저장 후 상세 다시 로드(새로고침)
                    if (pendingIngredientId !== null) {
                        let nextId = pendingIngredientId;
                        if (data.ingredient_id) {
                            nextId = data.ingredient_id;
                        }
                        loadIngredientDetail(nextId, pendingRowElement);
                        pendingIngredientId = null;
                        pendingRowElement = null;
                    }
                } else {
                    alert(data.message || '저장 중 오류가 발생했습니다.2');
                }
            })
            .catch(() => alert('저장 중 오류가 발생했습니다.3'));
        }
    }, true);
    
    // --- [신규] 엑셀 다운로드/업로드 기능 추가 ---

    const downloadBtn = document.getElementById('downloadExcelBtn');
    const uploadBtn = document.getElementById('uploadExcelBtn');
    const fileInput = document.getElementById('excelUploadInput');

    // 1. 엑셀 다운로드 버튼 이벤트
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.delete('page');
            const downloadUrl = `/label/my-ingredients/download/?${currentParams.toString()}`;
            window.location.href = downloadUrl;
        });
    }

    // 2. 엑셀 업로드 버튼 이벤트
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', function() {
            fileInput.click();
        });

        fileInput.addEventListener('change', function() {
            if (this.files.length === 0) return;

            const file = this.files[0];
            const formData = new FormData();
            formData.append('excel_file', file);

            uploadBtn.textContent = '업로드 중...';
            uploadBtn.disabled = true;

            fetch('/label/my-ingredients/upload/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || '엑셀 파일이 성공적으로 업로드되었습니다. 페이지를 새로고침합니다.');
                    window.location.reload();
                } else {
                    let errorMessage = data.message || '업로드 중 오류가 발생했습니다.';
                    if (data.errors && data.errors.length > 0) {
                        errorMessage += '\n\n[오류 상세]\n' + data.errors.join('\n');
                    }
                    alert(errorMessage);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('업로드 중 심각한 오류가 발생했습니다. 콘솔을 확인해주세요.');
            })
            .finally(() => {
                uploadBtn.textContent = '엑셀 업로드';
                uploadBtn.disabled = false;
                fileInput.value = '';
            });
        });
    }
    
    // CSRF 토큰을 가져오는 헬퍼 함수
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

    // 검색 입력 필드 효과 처리
    const searchInputs = document.querySelectorAll('.form-control');
    
    // 초기 로드 시 입력값이 있는 필드에 클래스 추가
    searchInputs.forEach(function(input) {
        checkInputValue(input);
    });
    
    // 입력 이벤트 리스너 추가
    searchInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            checkInputValue(this);
        });
        
        input.addEventListener('change', function() {
            checkInputValue(this);
        });
    });
    
    function checkInputValue(input) {
        if (input.value.trim() !== '') {
            input.classList.add('has-value');
        } else {
            input.classList.remove('has-value');
        }
    }

    // 현재 정렬 상태 표시
    function updateSortButtonsDisplay() {
        const urlParams = new URLSearchParams(window.location.search);
        const currentSort = urlParams.get('sort');
        const currentOrder = urlParams.get('order');

        // 모든 정렬 버튼 초기화
        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.classList.remove('sort-blue');
        });

        // 현재 정렬된 버튼 강조
        if (currentSort && currentOrder) {
            const activeButton = document.querySelector(`.sort-btn[href*="sort=${currentSort}&order=${currentOrder}"]`);
            if (activeButton) {
                activeButton.classList.add('sort-blue');
            }
        }
    }

    // 정렬 버튼 클릭 이벤트 처리
    document.querySelectorAll('.sort-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // href에서 정렬 정보 추출
            const href = this.getAttribute('href');
            if (!href) return;
            
            // 기존 href의 정렬 파라미터 추출
            const urlMatch = href.match(/\?(.+)$/);
            if (!urlMatch) return;
            
            const params = new URLSearchParams(urlMatch[1]);
            const sortField = params.get('sort');
            const sortOrder = params.get('order');
            
            if (!sortField || !sortOrder) return;
            
            // Sort button clicked: handled
            
            // 현재 URL의 모든 파라미터 유지하면서 정렬 파라미터만 변경
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.set('sort', sortField);
            currentParams.set('order', sortOrder);
            currentParams.set('page', '1'); // 정렬 시 첫 페이지로
            
            const newUrl = `${window.location.pathname}?${currentParams.toString()}`;
            // navigating to new URL
            
            // 페이지 이동
            window.location.href = newUrl;
        });
    });

    // 초기 정렬 상태 표시
    updateSortButtonsDisplay();

    // 입력 필드에 값이 있는 경우 클래스 추가
    document.querySelectorAll('.form-control').forEach(input => {
        if (input.value.trim() !== '') {
            input.classList.add('has-value');
        }
    });
    
    // 원료 표시명, 알레르기, GMO 검색 필드에 대한 도움말 추가
    const searchFields = ['ingredient_display_name', 'allergens', 'gmo'];
    
    searchFields.forEach(fieldName => {
        const inputs = document.querySelectorAll(`input[name="${fieldName}"]`);
        inputs.forEach(function(input) {
            // 포커스 시 도움말 표시
            input.addEventListener('focus', function() {
                let fieldLabel = '';
                if (fieldName === 'ingredient_display_name') fieldLabel = '원료 표시명';
                else if (fieldName === 'allergens') fieldLabel = '알레르기';
                else if (fieldName === 'gmo') fieldLabel = 'GMO';
                
                this.setAttribute('title', `${fieldLabel} OR 검색: 쉼표(,)로 구분 (예: 사과, 밀가루)\n${fieldLabel} AND 검색: 플러스(+)로 구분 (예: 사과 + 밀가루)`);
            });
            
            // 입력 중에도 도움말 유지
            input.addEventListener('input', function() {
                let fieldLabel = '';
                if (fieldName === 'ingredient_display_name') fieldLabel = '원료 표시명';
                else if (fieldName === 'allergens') fieldLabel = '알레르기';
                else if (fieldName === 'gmo') fieldLabel = 'GMO';
                
                if (this.value.includes('+')) {
                    this.setAttribute('title', `${fieldLabel} AND 검색: 모든 항목이 포함된 원료를 찾습니다.`);
                } else if (this.value.includes(',')) {
                    this.setAttribute('title', `${fieldLabel} OR 검색: 하나라도 포함된 원료를 찾습니다.`);
                } else {
                    this.setAttribute('title', `${fieldLabel} OR 검색: 쉼표(,)로 구분 (예: 사과, 밀가루)\n${fieldLabel} AND 검색: 플러스(+)로 구분 (예: 사과 + 밀가루)`);
                }
            });
        });
    });
});

// 좌측 행 클릭 이벤트 바인딩 함수 (AJAX로 리스트 갱신 시에도 사용)
function bindIngredientRowClickEvents() {
    document.querySelectorAll('.ingredient-row').forEach(row => {
        row.onclick = function() {
            const ingredientId = this.getAttribute('data-ingredient-id');
            handleIngredientRowClick(ingredientId, this);
        };
    });
}

// 페이지네이션 정보 업데이트 함수 개선
window.updatePaginationInfo = function(currentPage, totalPages, itemCount, totalItems) {
    // 현재 페이지 정보 업데이트
    const currentPageElements = document.querySelectorAll('.pagination .page-item.active .page-link');
    currentPageElements.forEach(el => {
        el.textContent = currentPage;
    });
    
    // 페이지 번호 버튼들 업데이트
    const pagination = document.querySelector('.pagination');
    if (pagination) {
        // 기존 페이지 번호 버튼들 제거 (이전/다음 버튼 제외)
        const pageItems = pagination.querySelectorAll('.page-item:not(.page-prev):not(.page-next)');
        pageItems.forEach(item => {
            if (!item.classList.contains('page-prev') && !item.classList.contains('page-next')) {
                item.remove();
            }
        });
        
        // 새로운 페이지 번호 버튼들 생성
        const prevButton = pagination.querySelector('.page-prev');
        const nextButton = pagination.querySelector('.page-next');
        
        // 페이지 범위 계산
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const pageItem = document.createElement('li');
            pageItem.className = `page-item ${i === currentPage ? 'active' : ''}`;
            
            const pageLink = document.createElement('a');
            pageLink.className = 'page-link';
            pageLink.href = '#';
            pageLink.textContent = i;
            pageLink.onclick = function(e) {
                e.preventDefault();
                goToPage(i);
            };
            
            pageItem.appendChild(pageLink);
            
            if (nextButton) {
                pagination.insertBefore(pageItem, nextButton);
            } else {
                pagination.appendChild(pageItem);
            }
        }
        
        // 이전/다음 버튼 상태 업데이트
        if (prevButton) {
            prevButton.classList.toggle('disabled', currentPage <= 1);
        }
        if (nextButton) {
            nextButton.classList.toggle('disabled', currentPage >= totalPages);
        }
    }
    
    // 페이지 정보 텍스트 업데이트
    const pageInfo = document.querySelector('.page-info');
    if (pageInfo && totalItems !== undefined) {
        const startItem = ((currentPage - 1) * itemCount) + 1;
        const endItem = Math.min(currentPage * itemCount, totalItems);
        pageInfo.textContent = `${startItem}-${endItem} / ${totalItems}개`;
    }
};

// 페이지 이동 함수
function goToPage(pageNumber) {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.set('page', pageNumber);
    
    // AJAX로 페이지 이동
    fetch(`/label/my-ingredient-table-partial/${currentUrl.search}`)
        .then(res => res.text())
        .then(tableHtml => {
            const tbody = document.querySelector('#ingredientTable tbody');
            if (tbody) {
                tbody.innerHTML = tableHtml;
                
                // 클릭 이벤트 재바인딩
                if (typeof window.bindIngredientRowClickEvents === 'function') {
                    window.bindIngredientRowClickEvents();
                }
                
                // 페이지네이션 정보 업데이트
                updatePaginationFromServer(currentUrl.search);
                
                // URL 업데이트 (브라우저 히스토리에 추가하지 않음)
                window.history.replaceState({}, '', currentUrl.toString());
            }
        })
        .catch(error => {
            console.error('Error loading page:', error);
        });
}

// my_ingredient_detail_partial.html에서 사용할 수 있도록 전역에 노출
window.loadNewIngredientForm = loadNewIngredientForm;
window.bindIngredientRowClickEvents = bindIngredientRowClickEvents;
