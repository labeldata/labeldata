/* ================================================================
   regulatory_list.js — 부적합·처분 알림 목록 페이지 JavaScript
   ================================================================ */

// ── 분야 필터 접기 플래시 방지: DOMContentLoaded 이전에 즉시 실행 ──
// 기본값 = 접힌 (localStorage에 '1'이 저장된 경우만 펙침)
(function () {
  if (localStorage.getItem('catFilterOpen') !== '1') {
    document.documentElement.classList.add('cat-filter-closed');
  }
})();

function toggleRiskHelp(e) {
  e.stopPropagation();
  const pop = document.getElementById('riskHelpPopover');
  if (pop) pop.classList.toggle('open');
}
document.addEventListener('click', function (e) {
  const pop = document.getElementById('riskHelpPopover');
  if (pop && pop.classList.contains('open') && !pop.contains(e.target)) {
    pop.classList.remove('open');
  }
});

function submitFilter() {
  document.getElementById('filterForm').submit();
}

function toggleCatFilter() {
  const el  = document.getElementById('catFilterCollapse');
  const btn = document.getElementById('catToggleBtn');
  if (!el || !btn) return;
  const isCollapsed = el.classList.contains('collapsed');
  if (isCollapsed) {
    el.classList.remove('collapsed');
    btn.classList.remove('collapsed');
    localStorage.setItem('catFilterOpen', '1');
  } else {
    el.classList.add('collapsed');
    btn.classList.add('collapsed');
    localStorage.setItem('catFilterOpen', '0');
  }
}

function toggleAllCats(cb) {
  document.querySelectorAll('input[name="cat"]').forEach(c => c.checked = cb.checked);
  submitFilter();
}

function onCatChange() {
  const all = [...document.querySelectorAll('input[name="cat"]')];
  const allChecked  = all.every(c => c.checked);
  const noneChecked = all.every(c => !c.checked);
  const cb = document.getElementById('catCheckAll');
  cb.checked = allChecked;
  cb.indeterminate = !allChecked && !noneChecked;
  submitFilter();
}

document.addEventListener('DOMContentLoaded', function () {
  const el  = document.getElementById('catFilterCollapse');
  const btn = document.getElementById('catToggleBtn');

  // 기본 접힘 상태 복원 (localStorage '1'이면 페침, 나머지는 접힌)
  const isOpen = localStorage.getItem('catFilterOpen') === '1';
  if (!isOpen) {
    if (el)  el.classList.add('collapsed');
    if (btn) btn.classList.add('collapsed');
  }
  document.documentElement.classList.remove('cat-filter-closed');

  const all = [...document.querySelectorAll('input[name="cat"]')];
  const cb  = document.getElementById('catCheckAll');
  if (cb) {
    const allChecked  = all.every(c => c.checked);
    const noneChecked = all.every(c => !c.checked);
    cb.checked = allChecked;
    cb.indeterminate = !allChecked && !noneChecked;
  }
});

function setDays(val) {
  document.getElementById('f_days').value = val;
  // 날짜 범위 초기화
  const df = document.querySelector('input[name="date_from"]');
  const dt = document.querySelector('input[name="date_to"]');
  if (df) df.value = '';
  if (dt) dt.value = '';
  submitFilter();
}

function onDateRangeChange() {
  const df = document.querySelector('input[name="date_from"]').value;
  const dt = document.querySelector('input[name="date_to"]').value;
  // 날짜 범위 지정 시 기간 버튼 비활성화
  if (df || dt) {
    document.getElementById('f_days').value = 'all';
  }
  submitFilter();
}

function clearDateRange() {
  const df = document.querySelector('input[name="date_from"]');
  const dt = document.querySelector('input[name="date_to"]');
  if (df) df.value = '';
  if (dt) dt.value = '';
  document.getElementById('f_days').value = '30';
  submitFilter();
}

function setRisk(val) {
  document.getElementById('f_risk').value = val;
  submitFilter();
}

function setStatus(val) {
  document.getElementById('f_status').value = val;
  submitFilter();
}

function doSearch() {
  document.getElementById('filterForm').submit();
}

function clearSearch() {
  document.getElementById('searchInput').value = '';
  document.getElementById('filterForm').submit();
}

function selectNews(newsId) {
  const url = new URL(window.location.href);
  url.searchParams.set('id', newsId);
  window.location.href = url.toString();
}
