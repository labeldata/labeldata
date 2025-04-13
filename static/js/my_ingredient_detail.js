function saveMyIngredient() {
    // 폼 데이터 수집
    const form = document.getElementById('ingredient-form');
    const formData = new FormData(form);
    
    // 정확한 URL 직접 지정 - ingredient_id가 있는 경우와 없는 경우 처리
    let ingredientId = document.querySelector('input[name="my_ingredient_id"]')?.value;
    // 다음 중 하나의 올바른 URL 사용 (실제 Django URL 패턴에 맞게 수정)
    const url = ingredientId 
        ? `/label/my-ingredient-detail/${ingredientId}/` 
        : '/label/my-ingredient-detail/';
    
    console.log('사용할 URL:', url);
    
    // CSRF 토큰 설정
    const csrftoken = getCookie('csrftoken');
    console.log('CSRF 토큰 있음:', !!csrftoken);
    
    // 디버깅: 폼 데이터 내용 확인
    console.log('폼 데이터 필드:');
    for (let pair of formData.entries()) {
        console.log(pair[0] + ': ' + pair[1]);
    }
    
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrftoken
        }
    })
    .then(response => {
        console.log('응답 상태:', response.status, response.statusText);
        console.log('응답 타입:', response.headers.get('content-type'));
        
        if (response.ok) {
            // 응답 타입 확인
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            } else {
                // JSON이 아닌 응답(HTML 등)이 왔을 때 상세 로깅
                console.error('서버가 JSON이 아닌 응답을 반환했습니다:', contentType);
                return response.text().then(text => {
                    console.log('서버 응답:', text.substring(0, 500) + '...'); // 응답 일부만 로그
                    throw new Error('서버가 JSON이 아닌 응답을 반환했습니다.');
                });
            }
        }
        // 서버 오류 처리 - 응답 내용도 함께 확인
        return response.text().then(text => {
            console.error('서버 오류 응답:', text.substring(0, 500) + '...');
            throw new Error(`서버 오류: ${response.status} ${response.statusText}`);
        });
    })
    .then(data => {
        if (data.success) {
            alert('내 원료가 성공적으로 저장되었습니다.');
            
            // 목록 갱신 함수가 있으면 호출
            if (typeof onSaveSuccess === 'function' && data.ingredient_id) {
                onSaveSuccess(data.ingredient_id);
            }
            
            // 부모 창이 있으면 새로고침
            if (window.opener) {
                window.opener.location.reload();
                window.close();
            }
        } else {
            alert(data.error || '저장에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('저장 중 오류가 발생했습니다: ' + error.message);
    });
}