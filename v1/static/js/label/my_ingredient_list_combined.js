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
    document.querySelectorAll('.ingredient-row').forEach(row => {
        row.onclick = function() {
            const ingredientId = this.getAttribute('data-ingredient-id');
            handleIngredientRowClick(ingredientId, this);
        };
    });

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
});

// my_ingredient_detail_partial.html에서 사용할 수 있도록 전역에 노출
window.loadNewIngredientForm = loadNewIngredientForm;
