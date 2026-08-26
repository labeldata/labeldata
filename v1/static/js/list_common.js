/* ================================================================
   list_common.js — 목록 화면 공용 동작

   검색창에서 엔터를 누르면 검색이 실행되게 한다.

   폼에 제출 버튼이 있으면 브라우저가 알아서 제출하지만, 없는 폼도 있고
   (부적합·처분 알림의 필터 폼) 그때는 엔터가 아무 일도 하지 않는다.
   조건 패널의 입력칸도 마찬가지라 화면마다 제각각이 된다.

   쓰는 법: 입력칸에 data-search-enter 를 붙인다.
     - 폼 안에 있으면  → 그 폼을 제출한다 (submit 핸들러도 함께 돈다)
     - 폼 밖에 있으면  → 속성값에 적힌 전역 함수를 호출한다
                        예) data-search-enter="doSearch"
   ================================================================ */
(function () {
    function submitForm(form) {
        // requestSubmit 이라야 submit 핸들러가 함께 돈다.
        // form.submit() 은 핸들러를 건너뛰어 빈 조건이 URL 에 남는다.
        if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
    }

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' || e.isComposing) return;   // 한글 조합 중이면 무시
        var el = e.target;
        if (!el || el.tagName !== 'INPUT') return;
        if (!el.hasAttribute('data-search-enter')) return;

        e.preventDefault();
        var form = el.closest('form');
        if (form) { submitForm(form); return; }

        var fn = el.getAttribute('data-search-enter');
        if (fn && typeof window[fn] === 'function') window[fn]();
    });
})();
