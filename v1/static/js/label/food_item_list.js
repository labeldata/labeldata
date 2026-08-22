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

/**
 * 제품 상세 팝업 열기 (국내·수입 공통)
 *
 * 크기는 화면에 맞춰 계산한다. 기존 고정 1000x600 은 수입식품 '표시사항' 탭의
 * 한글표시사항이 중앙값 20줄이라 33% 만 스크롤 없이 보였다.
 * 900px 높이면 90% 가 한 화면에 들어온다(실측). 폭은 한글표시사항에 줄바꿈이
 * 많아 넓혀도 줄 수가 거의 안 줄어들어(중앙 20줄 그대로) 크게 키우지 않는다.
 * 작은 노트북(768p)에서도 화면을 넘지 않도록 availHeight 기준으로 상한을 둔다.
 */
function openProductDetailPopup(url, title) {
    const avail = window.screen.availHeight || window.screen.height || 800;
    const availW = window.screen.availWidth || window.screen.width || 1280;
    const height = Math.min(920, Math.max(520, avail - 120));
    const width = Math.min(1200, Math.max(880, availW - 240));
    const left = Math.max(0, (availW - width) / 2);
    const top = Math.max(0, (avail - height) / 2);

    const popup = window.open(
        url,
        title,
        `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${top},left=${left}`
    );
    if (!popup || popup.closed || typeof popup.closed === "undefined") {
        alert("팝업이 차단되었습니다. 브라우저 설정을 확인하세요.");
        return null;
    }
    popup.focus();
    return popup;
}

function openDetailPopup(reportNo) {
    if (!reportNo) {
        alert("유효한 품목보고번호가 없습니다.");
        return;
    }
    openProductDetailPopup(`/label/food-item-detail/${reportNo}/`, "제품 상세 정보");
}

// 수입식품 상세는 id(pk)로 접근한다
function openImportedDetailPopup(id) {
    if (!id) {
        alert("수입식품 ID가 없습니다.");
        return;
    }
    openProductDetailPopup(`/label/food-item-detail/${id}/`, "수입식품 상세 정보");
}
