// my_label_list.html에서 분리한 스크립트 코드

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
        if (!e.target.classList.contains("check-item")) {
        window.location.href = this.dataset.url;
        }
    });
    });
});

function bulkDelete() {
    const selected = getSelectedIds();
    if (selected.length === 0) {
        alert("삭제할 항목을 선택하세요.");
        return;
    }
    if (confirm("선택한 라벨을 삭제하시겠습니까?\n삭제된 데이터는 복구할 수 없습니다.")) {
        // URL을 'bulk-delete/'에서 'bulk-delete-labels/'로 수정
        fetch('/label/bulk-delete-labels/', {  // 여기를 수정
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
        fetch('/label/bulk-copy-labels/', {  // URL이 올바름
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
