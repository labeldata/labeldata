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

function toggleInsp46Help(e) {
  e.stopPropagation();
  const pop = document.getElementById('insp46HelpPopover');
  if (pop) pop.classList.toggle('open');
}

document.addEventListener('click', function (e) {
  const risk = document.getElementById('riskHelpPopover');
  if (risk && risk.classList.contains('open') && !risk.contains(e.target)) {
    risk.classList.remove('open');
  }
  const insp = document.getElementById('insp46HelpPopover');
  if (insp && insp.classList.contains('open') && !insp.contains(e.target)) {
    insp.classList.remove('open');
  }
});

function submitFilter() {
  // 현재 탭을 폼에 주입해 제출 후에도 탭이 유지되도록 함
  var form = document.getElementById('filterForm');
  var tabInput = form.querySelector('input[name="tab"]');
  if (!tabInput) {
    tabInput = document.createElement('input');
    tabInput.type  = 'hidden';
    tabInput.name  = 'tab';
    form.appendChild(tabInput);
  }
  tabInput.value = new URL(window.location.href).searchParams.get('tab') || '';
  form.submit();
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

// 드로어 체크박스 변경 시 그룹 버튼 active 상태 갱신
function onCatChange() {
  _updateGroupBtnState();
  submitFilter();
}

// 부적합/처분 그룹 버튼 클릭 — 해당 그룹 체크박스 전체 토글
function toggleGroup(group) {
  const groupKeys = {
    insp:  ['insp', 'I0490', 'imp_insp', 'import'],
    admin: ['admin', 'I0482', 'saol_admin'],
  };
  const keys = groupKeys[group] || [];
  const boxes = [...document.querySelectorAll('input[name="cat"]')]
    .filter(c => keys.includes(c.value));
  // 하나라도 꺼져있으면 전체 ON, 모두 켜져있으면 전체 OFF
  const allOn = boxes.every(c => c.checked);
  boxes.forEach(c => c.checked = !allOn);
  _updateGroupBtnState();
  submitFilter();
}

// 수거검사 버튼 클릭 — I0460 hidden input 토글 후 제출
function toggleInspection() {
  const form = document.getElementById('filterForm');
  let hidden = document.getElementById('hiddenInsp46');
  if (hidden) {
    hidden.remove(); // 현재 ON → OFF
  } else {
    hidden = document.createElement('input');
    hidden.type  = 'hidden';
    hidden.name  = 'cat';
    hidden.value = 'I0460';
    hidden.id    = 'hiddenInsp46';
    form.appendChild(hidden);
  }
  submitFilter();
}

// 그룹 버튼 active 클래스 갱신
function _updateGroupBtnState() {
  const inspKeys  = ['insp', 'I0490', 'imp_insp', 'import'];
  const adminKeys = ['admin', 'I0482', 'saol_admin'];
  const all = [...document.querySelectorAll('input[name="cat"]')];

  const inspOn  = inspKeys.some(k  => all.find(c => c.value === k  && c.checked));
  const adminOn = adminKeys.some(k => all.find(c => c.value === k && c.checked));

  document.getElementById('grpBtnInsp') ?.classList.toggle('rf-grp-btn--on', inspOn);
  document.getElementById('grpBtnAdmin')?.classList.toggle('rf-grp-btn--on', adminOn);
}

document.addEventListener('DOMContentLoaded', function () {
  const el  = document.getElementById('catFilterCollapse');
  const btn = document.getElementById('catToggleBtn');

  const isOpen = localStorage.getItem('catFilterOpen') === '1';
  if (!isOpen) {
    if (el)  el.classList.add('collapsed');
    if (btn) btn.classList.add('collapsed');
  }
  document.documentElement.classList.remove('cat-filter-closed');

  _updateGroupBtnState();

  // 선택 후 페이지 이동 시 스크롤 위치 복원
  const saved = sessionStorage.getItem('rs_scroll');
  if (saved !== null) {
    const listBody = document.querySelector('.rs-list-body');
    if (listBody) listBody.scrollTop = parseInt(saved, 10);
    sessionStorage.removeItem('rs_scroll');
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
  const listBody = document.querySelector('.rs-list-body');
  if (listBody) sessionStorage.setItem('rs_scroll', listBody.scrollTop);
  const url = new URL(window.location.href);
  url.searchParams.set('id', newsId);
  url.searchParams.delete('insp_id');
  window.location.href = url.toString();
}

function selectInspection(matchId) {
  const listBody = document.querySelector('.rs-list-body');
  if (listBody) sessionStorage.setItem('rs_scroll', listBody.scrollTop);
  const url = new URL(window.location.href);
  url.searchParams.set('insp_id', matchId);
  url.searchParams.delete('id');
  window.location.href = url.toString();
}
