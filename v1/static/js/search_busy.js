/*
 * 검색 중이라고 **화면 한가운데서** 말한다.
 *
 * 제품 조회에서 검색을 누르면 화면은 그대로이고 브라우저 탭에만 작은 표시가
 * 돈다. 32만 건을 훑는 질의라 몇 초가 걸리는데, 그동안 사용자에게는 아무 일도
 * 일어나지 않는 것으로 보인다 — 그래서 다시 누르고, 그러면 같은 질의가 한 번
 * 더 돈다.
 *
 * 이 화면에 그런 표시가 **있기는 했다.** 그런데 JS 는 `searchFilterForm` 을
 * 찾고 화면의 폼은 `searchForm` 이라, 한 번도 돈 적이 없었다. 이름이 어긋난
 * 코드는 조용히 아무 일도 하지 않는다.
 *
 * 쓰는 법 — 오래 걸리는 폼에 표시만 붙인다.
 *
 *     <form method="get" data-busy="국내 품목보고 32만 건에서 찾는 중입니다">
 *
 * 값이 없으면 기본 문구를 쓴다. 폼이 아니라 다른 것으로 검색을 시작한다면
 * `window.showSearchBusy('...')` 를 직접 불러도 된다.
 */
(function () {
  'use strict';

  var DEFAULT_TEXT = '찾는 중입니다';
  var HINT = '자료가 많아 몇 초 걸릴 수 있습니다. 잠시만 기다려 주세요.';
  var overlay = null;

  function build() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'search-busy';
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');
    overlay.innerHTML = ''
      + '<div class="search-busy-card">'
      + '  <div class="search-busy-spinner" aria-hidden="true"></div>'
      + '  <div class="search-busy-text"></div>'
      + '  <div class="search-busy-hint"></div>'
      + '</div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  window.showSearchBusy = function (text, hint) {
    var el = build();
    el.querySelector('.search-busy-text').textContent = text || DEFAULT_TEXT;
    el.querySelector('.search-busy-hint').textContent = hint || HINT;
    el.classList.add('is-on');
  };

  window.hideSearchBusy = function () {
    if (overlay) overlay.classList.remove('is-on');
  };

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.matches || !form.matches('form[data-busy]')) return;
    window.showSearchBusy(form.dataset.busy);
  });

  /*
   * 뒤로 가기로 돌아오면 브라우저가 화면을 통째로 되살린다(bfcache). 그때
   * 오버레이도 켜진 채로 살아나 **영원히 찾는 중**이 된다. pageshow 는 그
   * 경우에도 오므로 여기서 끈다.
   */
  window.addEventListener('pageshow', function () { window.hideSearchBusy(); });
})();
