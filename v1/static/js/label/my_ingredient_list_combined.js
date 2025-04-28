// my_ingredient_list_combined.html에서 분리된 스크립트 예시

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
    // AJAX로 상세 정보 로드
    fetch(`/label/my-ingredient-detail/${ingredientId}/`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('ingredient-detail-container').innerHTML = html;
        reloadPartialScript();
    });
}

function loadNewIngredientForm() {
    // 신규 등록 폼 로드
    fetch('/label/my-ingredient-detail/', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('ingredient-detail-container').innerHTML = html;
        clearSelectedRow();
        reloadPartialScript();
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
});

// my_ingredient_detail_partial.html에서 사용할 수 있도록 전역에 노출
window.loadNewIngredientForm = loadNewIngredientForm;
