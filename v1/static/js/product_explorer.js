/* ============================================================
   EazyLabel V2 제품 관리(탐색기) 전용 JS
   Django 컨텍스트 변수(PE_FILTER_TYPE, PE_EXPLORER_URL, PE_CSRF_TOKEN)는
   product_explorer.html 의 인라인 <script>에서 선언됩니다.
   ============================================================ */

// 페이지당 항목 수 변경
function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', '1');
    if (PE_FILTER_TYPE && PE_FILTER_TYPE !== 'ALL') urlParams.set('filter', PE_FILTER_TYPE);
    else urlParams.delete('filter');
    window.location.search = urlParams.toString();
}

// 검색 기능
document.getElementById('product-search').addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
        const query = this.value.trim();
        const filterParam = (PE_FILTER_TYPE && PE_FILTER_TYPE !== 'ALL') ? `&filter=${PE_FILTER_TYPE}` : '';
        if (query) {
            window.location.href = `${PE_EXPLORER_URL}?q=${encodeURIComponent(query)}${filterParam}`;
        } else {
            window.location.href = `${PE_EXPLORER_URL}${filterParam ? '?' + filterParam.slice(1) : ''}`;
        }
    }
});

// 필터 기능 (상태/날짜 클라이언트 필터)
let activeSpecialFilter = null; // 'starred' | 'expiring' | null

// 즐겨찾기 통계카드 클릭 → 해당 행만 표시
function filterByStarred() {
    if (activeSpecialFilter === 'starred') {
        activeSpecialFilter = null;
        _clearStatCardActive();
    } else {
        activeSpecialFilter = 'starred';
        _clearStatCardActive();
        const card = document.getElementById('stat-starred');
        if (card) card.classList.add('stat-card-active');
    }
    applyAdvancedFilters();
}

// 만료임박 통계카드 클릭 → 해당 제품만 표시
function filterExpiring() {
    if (activeSpecialFilter === 'expiring') {
        activeSpecialFilter = null;
        _clearStatCardActive();
    } else {
        activeSpecialFilter = 'expiring';
        _clearStatCardActive();
        const card = document.getElementById('stat-expiring');
        if (card) card.classList.add('stat-card-active');
    }
    applyAdvancedFilters();
}

function _clearStatCardActive() {
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('stat-card-active'));
}

// 상태별 필터링
function filterByStatus(status) {
    activeSpecialFilter = null;
    _clearStatCardActive();
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.value = status;
        applyAdvancedFilters();
    }
}

// 고급 필터 적용
function applyAdvancedFilters() {
    const statusFilter = document.getElementById('status-filter').value;
    const dateFilter = document.getElementById('date-filter').value;

    const rows = document.querySelectorAll('.product-row');
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    rows.forEach(row => {
        let show = true;

        // 특수 필터 (즐겨찾기 / 만료임박)
        if (activeSpecialFilter === 'starred') {
            if (row.dataset.isStarred !== 'true') show = false;
        } else if (activeSpecialFilter === 'expiring') {
            if (row.dataset.hasExpiring !== 'true') show = false;
        }

        // 상태 필터
        if (show && statusFilter && row.dataset.status !== statusFilter) {
            show = false;
        }

        // 날짜 필터
        if (show && dateFilter) {
            const updateDate = new Date(row.dataset.updateDate);
            const diffDays = Math.floor((today - updateDate) / (1000 * 60 * 60 * 24));

            if (dateFilter === 'today' && diffDays !== 0) show = false;
            else if (dateFilter === 'week' && diffDays > 7) show = false;
            else if (dateFilter === 'month' && diffDays > 30) show = false;
            else if (dateFilter === '3months' && diffDays > 90) show = false;
        }

        row.style.display = show ? '' : 'none';
    });
}

// 전체 선택
document.getElementById('select-all-products')?.addEventListener('change', function() {
    const checkboxes = document.querySelectorAll('.product-checkbox:not([style*="display: none"])');
    const visibleCheckboxes = Array.from(checkboxes).filter(cb => {
        const row = cb.closest('tr');
        return row && row.style.display !== 'none';
    });

    visibleCheckboxes.forEach(cb => {
        cb.checked = this.checked;
    });

    updateSelectionActions();
});

// 개별 체크박스
document.querySelectorAll('.product-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
        const row = this.closest('tr');
        if (this.checked) {
            row.classList.add('selected');
        } else {
            row.classList.remove('selected');
        }
        updateSelectionActions();
    });
});

// 선택 항목 액션 업데이트
function updateSelectionActions() {
    const selectedCheckboxes = document.querySelectorAll('.product-checkbox:checked');
    const visibleSelected = Array.from(selectedCheckboxes).filter(cb => {
        const row = cb.closest('tr');
        return row && row.style.display !== 'none';
    });

    const count = visibleSelected.length;
    const actionsBar = document.getElementById('selection-actions');
    const countSpan = document.getElementById('selected-count');

    if (count > 0) {
        actionsBar.classList.remove('d-none');
        actionsBar.classList.add('d-flex');
        countSpan.textContent = count;
    } else {
        actionsBar.classList.remove('d-flex');
        actionsBar.classList.add('d-none');
    }
}

// 선택 항목 삭제
async function deleteSelected() {
    const selectedCheckboxes = document.querySelectorAll('.product-checkbox:checked');
    const visibleSelected = Array.from(selectedCheckboxes).filter(cb => {
        const row = cb.closest('tr');
        return row && row.style.display !== 'none';
    });

    if (visibleSelected.length === 0) {
        alert('삭제할 제품을 선택해주세요.');
        return;
    }

    if (!confirm(`선택한 ${visibleSelected.length}개 제품을 삭제하시겠습니까?`)) {
        return;
    }

    const productIds = visibleSelected.map(cb => cb.dataset.productId);

    try {
        const response = await fetch('/products/api/bulk-delete/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': PE_CSRF_TOKEN
            },
            body: JSON.stringify({ product_ids: productIds })
        });

        const result = await response.json();

        if (result.success) {
            alert('선택한 제품이 삭제되었습니다.');
            window.location.reload();
        } else {
            alert('삭제 중 오류가 발생했습니다: ' + (result.message || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('삭제 중 오류가 발생했습니다.');
    }
}

// 선택 항목 복사
async function copySelected() {
    const selectedCheckboxes = document.querySelectorAll('.product-checkbox:checked');
    const visibleSelected = Array.from(selectedCheckboxes).filter(cb => {
        const row = cb.closest('tr');
        return row && row.style.display !== 'none';
    });

    if (visibleSelected.length === 0) {
        alert('복사할 제품을 선택해주세요.');
        return;
    }

    if (!confirm(`선택한 ${visibleSelected.length}개 제품을 복사하시겠습니까?`)) {
        return;
    }

    const productIds = visibleSelected.map(cb => cb.dataset.productId);

    try {
        const response = await fetch('/v2/products/api/bulk-copy/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': PE_CSRF_TOKEN
            },
            body: JSON.stringify({ product_ids: productIds })
        });

        const result = await response.json();

        if (result.success) {
            alert('선택한 제품이 복사되었습니다.');
            window.location.reload();
        } else {
            alert('복사 중 오류가 발생했습니다: ' + (result.message || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('복사 중 오류가 발생했습니다.');
    }
}
