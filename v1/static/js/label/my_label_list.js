document.addEventListener("DOMContentLoaded", function () {
    const checkAll = document.getElementById("check-all");

    if (checkAll) {
    checkAll.addEventListener("change", function () {
        document.querySelectorAll(".check-item").forEach(cb => cb.checked = checkAll.checked);
    });
    }

    document.querySelectorAll(".check-item").forEach(cb => {
    cb.addEventListener("click", function (e) {
        e.stopPropagation();
    });
    });

    // 모드 선택 토글 초기화
    initViewModeToggle();

    // 행 클릭 이벤트 (선택된 모드에 따라 이동)
    document.querySelectorAll("tr.clickable-row").forEach(row => {
        row.addEventListener("click", function (e) {
            if (!e.target.classList.contains("check-item") && !e.target.closest(".checkbox-cell")) {
                const labelId = this.dataset.labelId;
                const viewMode = getViewMode();
                
                if (viewMode === 'simple') {
                    window.location.href = `/?label_id=${labelId}`;
                } else {
                    window.location.href = `/label/label-creation/${labelId}/`;
                }
            }
        });
    });

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
});

/**
 * [신규] '신규 작성' 버튼 클릭 시 호출됩니다.
 * 서버에 새로운 표시사항 생성을 요청하고, 반환된 URL로 이동합니다.
 */
function createNewLabel() {
    if (confirm("새로운 표시사항을 작성하시겠습니까?")) {
        // 서버의 생성 처리 URL로 POST 요청을 보냅니다.
        fetch('/label/create-new/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({}) // 필요 시 초기 데이터 전송
        })
        .then(response => {
            if (!response.ok) {
                // 서버에서 에러 메시지를 보냈을 경우를 대비
                return response.json().then(err => { throw new Error(err.error || '서버 응답 오류'); });
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.redirect_url) {
                // 성공 시, 서버가 알려준 편집 페이지 URL로 이동합니다.
                window.location.href = data.redirect_url;
            } else {
                alert('신규 표시사항 생성에 실패했습니다: ' + (data.error || '알 수 없는 오류'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert(`신규 표시사항 생성 중 오류가 발생했습니다: ${error.message}`);
        });
    }
}

// 체크박스 셀 클릭 시 체크박스 토글 함수
function toggleCheckbox(cell) {
    const checkbox = cell.querySelector('.check-item');
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
    }
}

function bulkDelete() {
    const selected = getSelectedIds();
    if (selected.length === 0) {
        alert("삭제할 항목을 선택하세요.");
        return;
    }
    if (confirm("선택한 라벨을 삭제하시겠습니까?\n삭제된 데이터는 복구할 수 없습니다.")) {
        fetch('/label/bulk-delete-labels/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({label_ids: selected})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('삭제 중 오류가 발생했습니다.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('삭제 중 오류가 발생했습니다.');
        });
    }
}

function bulkCopy() {
    const selected = getSelectedIds();
    if (selected.length === 0) {
        alert("복사할 항목을 선택하세요.");
        return;
    }
    if (confirm("선택한 라벨을 복사하시겠습니까?")) {
        fetch('/label/bulk-copy-labels/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({label_ids: selected})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('복사 중 오류가 발생했습니다.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('복사 중 오류가 발생했습니다.');
        });
    }
}

function getSelectedIds() {
    return Array.from(document.querySelectorAll(".check-item:checked"))
    .map(cb => cb.value);
}

function createPostForm(action, ids) {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = action;

    const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
    if (csrfToken) {
    const tokenInput = document.createElement("input");
    tokenInput.type = "hidden";
    tokenInput.name = "csrfmiddlewaretoken";
    tokenInput.value = csrfToken;
    form.appendChild(tokenInput);
    }

    ids.forEach(id => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "label_ids";
    input.value = id;
    form.appendChild(input);
    });
    return form;
}

function downloadSelectedLabelsExcel() {
    const selected = getSelectedIds();
    if (selected.length === 0) {
        alert("엑셀로 다운로드할 항목을 선택하세요.");
        return;
    }
    // Generate filename with format LABELDATA_표시사항 데이터_YYMMDD
    const today = new Date();
    const year = today.getFullYear().toString().slice(-2); // Last two digits of year
    const month = String(today.getMonth() + 1).padStart(2, '0'); // Month (0-11, so +1)
    const day = String(today.getDate()).padStart(2, '0'); // Day
    const fileName = `LABELDATA_표시사항 데이터_${year}${month}${day}.xlsx`;

    // 서버에 POST로 선택된 ID를 보내고, 엑셀 파일을 다운로드
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch('/label/export-labels-excel/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({label_ids: selected})
    })
    .then(response => {
        if (!response.ok) throw new Error('엑셀 다운로드 실패');
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName; // Use the dynamically generated filename
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    })
    .catch(error => {
        alert('엑셀 다운로드 중 오류가 발생했습니다.');
        console.error(error);
    });
}

// 모드 선택 토글 초기화 및 관리
function initViewModeToggle() {
    // localStorage에서 저장된 모드 불러오기 (기본값: detail)
    const savedMode = localStorage.getItem('labelViewMode') || 'detail';
    
    // 라디오 버튼 설정
    const simpleRadio = document.getElementById('viewModeSimple');
    const detailRadio = document.getElementById('viewModeDetail');
    
    if (savedMode === 'simple') {
        simpleRadio.checked = true;
    } else {
        detailRadio.checked = true;
    }
    
    // 라디오 버튼 변경 이벤트
    simpleRadio.addEventListener('change', function() {
        if (this.checked) {
            localStorage.setItem('labelViewMode', 'simple');
            showModeChangeToast('📋 간편 모드로 전환되었습니다');
        }
    });
    
    detailRadio.addEventListener('change', function() {
        if (this.checked) {
            localStorage.setItem('labelViewMode', 'detail');
            showModeChangeToast('✏️ 상세 모드로 전환되었습니다');
        }
    });
}

// 현재 선택된 모드 가져오기
function getViewMode() {
    return localStorage.getItem('labelViewMode') || 'detail';
}

// 모드 변경 토스트 메시지
function showModeChangeToast(message) {
    const toast = document.createElement('div');
    toast.className = 'position-fixed top-0 end-0 p-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="alert alert-info alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 2000);
}

// 홈 화면에서 열기 (레거시 함수 - 호환성 유지)
function openInHome(labelId) {
    window.location.href = `/?label_id=${labelId}`;
}

// 작성 페이지에서 열기 (레거시 함수 - 호환성 유지)
function openInEditor(labelId) {
    window.location.href = `/label/label-creation/${labelId}/`;
}