/* ================================================================
   regulatory_list.js — 부적합·처분 알림 목록 페이지 JavaScript
   ================================================================ */

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
  if (typeof showLoading === 'function') showLoading();
  // requestSubmit 이라야 조건 패널의 submit 핸들러(값이 빈 조건 제외)가 함께 돈다.
  // form.submit() 은 그것을 건너뛰어 f=&v= 가 URL 에 쌓인다.
  if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
}

// 분야 체크박스는 '상세 조건' 패널의 체크박스 묶음으로 옮겼다.
// 드로어를 여닫던 toggleCatFilter / 그룹 토글 / 상태 갱신 함수는 함께 사라졌다.

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

document.addEventListener('DOMContentLoaded', function () {
  // 선택 후 페이지 이동 시 스크롤 위치 복원
  const saved = sessionStorage.getItem('rs_scroll');
  if (saved !== null) {
    const listBody = document.querySelector('.rs-list-body');
    if (listBody) listBody.scrollTop = parseInt(saved, 10);
    sessionStorage.removeItem('rs_scroll');
  }
});

// 기간 단축 버튼 (3일/1주/1개월/전체) — 자주 쓰는 조작이라 조건 패널과 별개로 남겼다.
// 정확한 구간이 필요하면 조건 패널의 '발생·처분일(부터/까지)' 를 쓴다.
function setDays(val) {
  document.getElementById('f_days').value = val;
  submitFilter();
}

// 위험도·조치상태는 '상세 조건' 패널의 체크박스 묶음으로 옮겼다.
// 예전 링크·북마크(?risk=HIGH 등)는 서버가 그대로 읽으므로 계속 동작한다.

// ── 목록 조작 (정렬 / 페이지당 개수) ──────────────────────────────────────
// 거르는 조건과 달리 폼 바깥에 있어 주소를 직접 고쳐 이동한다.
function _navWith(changes) {
  const url = new URL(window.location.href);
  Object.keys(changes).forEach(function (k) {
    if (changes[k] === null) { url.searchParams.delete(k); }
    else { url.searchParams.set(k, changes[k]); }
  });
  url.searchParams.delete('page');   // 보는 방식이 바뀌면 첫 페이지부터
  if (typeof showLoading === 'function') showLoading();
  window.location.href = url.toString();
}

function setSort(field) {
  _navWith({ sort: field });
}

function setOrder(order) {
  _navWith({ order: order });
}

function setPerPage(n) {
  _navWith({ per_page: n });
}

function doSearch() {
  submitFilter();
}

function clearSearch() {
  document.getElementById('searchInput').value = '';
  submitFilter();
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
  url.searchParams.delete('pub_insp_id');
  window.location.href = url.toString();
}

function selectPubInspection(inspResultId) {
  const listBody = document.querySelector('.rs-list-body');
  if (listBody) sessionStorage.setItem('rs_scroll', listBody.scrollTop);
  const url = new URL(window.location.href);
  url.searchParams.set('pub_insp_id', inspResultId);
  url.searchParams.delete('id');
  url.searchParams.delete('insp_id');
  window.location.href = url.toString();
}
window.selectPubInspection = selectPubInspection;
