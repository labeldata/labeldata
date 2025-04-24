// my_ingredient_detail_partial.html에서 분리된 스크립트

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
            if (window.opener) {
                window.opener.location.reload();
            }
            window.close();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('삭제 중 오류가 발생했습니다.');
    });
}

// 폼 저장 함수
function saveMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    const formData = new FormData(document.getElementById("ingredientForm"));
    let url = window.location.pathname;
    if (!my_ingredient_id) {
        url = '/label/my-ingredient-detail/';
    }
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
            alert('내 원료가 성공적으로 저장되었습니다.');
            if (window.opener) {
                window.opener.location.reload();
            }
            window.close();
        } else {
            alert(data.error || '저장에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('저장 중 오류가 발생했습니다.');
    });
}

// 쿠키에서 CSRF 토큰 가져오기
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

// 알레르기, GMO, 폼 이벤트 등 기타 함수는 기존 <script> 코드에서 추가로 복사해 넣으세요.
// 예: toggleAllergySelection, toggleGMOSelection, updateAllergyInfo, updateGMOInfo 등

// DOMContentLoaded에서 이벤트 바인딩
// ...기존 코드 참고하여 필요 함수 바인딩...