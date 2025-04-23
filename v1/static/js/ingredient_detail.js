function confirmDelete() {
    if (confirm('정말 삭제하시겠습니까?')) {
        deleteMyIngredient();
    }
}

function deleteMyIngredient() {
    const my_ingredient_id = parseInt("{{ ingredient.my_ingredient_id }}", 10);  // 숫자로 변환
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

document.addEventListener('DOMContentLoaded', function() {
    // 알레르기 및 GMO 옵션 표시 함수 호출
    if (typeof showAllergyOptions === 'function') {
        showAllergyOptions();
    }
    
    if (typeof showGmoOptions === 'function') {
        showGmoOptions();
    }
    
    // 초기화 함수 호출하여 알레르기와 GMO 선택 부분을 접어둠
    if (typeof initializeSelections === 'function') {
        initializeSelections();
    } else {
        // initializeSelections 함수가 없는 경우 직접 처리
        const allergySelection = document.getElementById('allergySelection');
        const gmoSelection = document.getElementById('gmoSelection');
        
        if (allergySelection) allergySelection.style.display = 'none';
        if (gmoSelection) gmoSelection.style.display = 'none';
        
        // 버튼 텍스트도 설정
        const allergyToggleButton = document.getElementById('allergyToggleButton');
        const gmoToggleButton = document.getElementById('gmoToggleButton');
        
        if (allergyToggleButton) allergyToggleButton.textContent = '펼치기';
        if (gmoToggleButton) gmoToggleButton.textContent = '펼치기';
    }
    
    // 폼 제출 이벤트 처리
    const form = document.getElementById('ingredientForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 저장 전에 알레르기와 GMO 정보 업데이트
            if (typeof updateAllergyInfo === 'function') {
                updateAllergyInfo();
            }
            
            if (typeof updateGmoInfo === 'function') {
                updateGmoInfo();
            }
            
            // 폼 제출
            saveMyIngredient();
        });
    }
});

function saveMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
   
    // 폼 데이터 수집
    const formData = new FormData(document.getElementById("ingredientForm"));
    
    // 현재 URL 경로를 사용 (수정 시)
    let url = window.location.pathname;
    
    // 새 원료 생성 시 기본 URL 사용
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