document.addEventListener('DOMContentLoaded', function() {
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

function openDetailPopup(reportNo) {
    if (!reportNo) {
        alert("유효한 품목보고번호가 없습니다.");
        return;
    }
    const url = `/label/food-item-detail/${reportNo}/`;
    const width = 1000; // 가로 크기
    const height = 600; // 세로 크기
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    const popup = window.open(
        url,
        "제품 상세 정보",
        `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${top},left=${left}`
    );
    if (!popup || popup.closed || typeof popup.closed === "undefined") {
        alert("팝업이 차단되었습니다. 브라우저 설정을 확인하세요.");
    }
}

// 수입식품 상세 팝업 열기 함수 (제품 목록에서 사용)
function openImportedDetailPopup(id) {
    if (!id) {
        alert("수입식품 ID가 없습니다.");
        return;
    }
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    const url = `/label/food-item-detail/${id}/`;
    window.open(
        url,
        "수입식품 상세 정보",
        `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${top},left=${left}`
    );
}
