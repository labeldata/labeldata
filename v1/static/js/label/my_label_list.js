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

    document.querySelectorAll("tr[data-url]").forEach(row => {
    row.addEventListener("click", function (e) {
        if (!e.target.classList.contains("check-item") && !e.target.closest(".checkbox-cell")) {
        window.location.href = this.dataset.url;
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
});

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