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
    });
}

function clearSelectedRow() {
    document.querySelectorAll('.ingredient-row.selected').forEach(el => {
        el.classList.remove('selected');
        el.style.backgroundColor = '';
        el.style.color = '';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // 페이지 진입 시 빈 폼 로드
    loadNewIngredientForm();
    // 신규 등록 버튼 이벤트
    document.getElementById('newIngredientBtn').addEventListener('click', loadNewIngredientForm);
});

// my_ingredient_detail_partial.html에서 사용할 수 있도록 전역에 노출
window.loadNewIngredientForm = loadNewIngredientForm;
