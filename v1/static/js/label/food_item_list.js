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
    
    // 검색 폼 제출 이벤트 처리
    const searchForm = document.getElementById('searchFilterForm');
    const searchBtn = document.getElementById('searchBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const foodCategorySelect = document.getElementById('foodCategorySelect');
    
    if (searchForm && searchBtn) {
        searchForm.addEventListener('submit', function(e) {
            // 로딩 상태 시작
            showLoadingState();
        });
    }
    
    // 카테고리 변경 시에도 로딩 표시
    if (foodCategorySelect) {
        foodCategorySelect.addEventListener('change', function() {
            showLoadingState();
        });
    }
    
    // 페이지 로드 완료 시 로딩 상태 숨김
    window.addEventListener('load', function() {
        hideLoadingState();
    });
    
    function showLoadingState() {
        // 검색 버튼 상태 변경
        if (searchBtn) {
            searchBtn.classList.add('loading');
            const btnText = searchBtn.querySelector('.btn-text');
            const spinner = searchBtn.querySelector('.spinner-border');
            const loadingText = searchBtn.querySelector('.loading-text');
            
            if (btnText) btnText.classList.add('d-none');
            if (spinner) spinner.classList.remove('d-none');
            if (loadingText) loadingText.classList.remove('d-none');
        }
        
        // 오버레이 표시
        if (loadingOverlay) {
            loadingOverlay.classList.remove('d-none');
        }
    }
    
    function hideLoadingState() {
        // 검색 버튼 상태 복구
        if (searchBtn) {
            searchBtn.classList.remove('loading');
            const btnText = searchBtn.querySelector('.btn-text');
            const spinner = searchBtn.querySelector('.spinner-border');
            const loadingText = searchBtn.querySelector('.loading-text');
            
            if (btnText) btnText.classList.remove('d-none');
            if (spinner) spinner.classList.add('d-none');
            if (loadingText) loadingText.classList.add('d-none');
        }
        
        // 오버레이 숨김
        if (loadingOverlay) {
            loadingOverlay.classList.add('d-none');
        }
    }
    
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
            
            // 로딩 상태 시작
            showLoadingState();
            
            // href에서 정렬 정보 추출
            const href = this.getAttribute('href');
            if (!href) {
                hideLoadingState();
                return;
            }
            
            // 기존 href의 정렬 파라미터 추출
            const urlMatch = href.match(/\?(.+)$/);
            if (!urlMatch) {
                hideLoadingState();
                return;
            }
            
            const params = new URLSearchParams(urlMatch[1]);
            const sortField = params.get('sort');
            const sortOrder = params.get('order');
            
            if (!sortField || !sortOrder) {
                hideLoadingState();
                return;
            }
            
            // Sort button clicked: sortField, sortOrder
            
            // 현재 URL의 모든 파라미터 유지하면서 정렬 파라미터만 변경
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.set('sort', sortField);
            currentParams.set('order', sortOrder);
            currentParams.set('page', '1'); // 정렬 시 첫 페이지로
            
            const newUrl = `${window.location.pathname}?${currentParams.toString()}`;

            
            // 페이지 이동
            window.location.href = newUrl;
        });
    });

    // 초기 정렬 상태 표시
    updateSortButtonsDisplay();
    
    // 페이지네이션 링크에 로딩 상태 추가
    document.querySelectorAll('.pagination a').forEach(link => {
        link.addEventListener('click', function(e) {
            // 현재 페이지가 아닌 경우에만 로딩 표시
            if (!this.closest('.page-item').classList.contains('active')) {
                showLoadingState();
            }
        });
    });
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
