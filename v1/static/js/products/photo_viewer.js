/*
 * 확인 창 옆에 붙는 사진 뷰어.
 *
 * 읽어낸 값이 맞는지는 결국 사진을 봐야 안다. 값만 늘어놓으면 "이게 정말 저기
 * 적힌 값인가" 를 확인할 방법이 없어서, 창을 닫고 사진을 따로 열어 봐야 했다.
 *
 * 표시사항 사진은 글씨가 작고, 세로로 찍힌 것도 흔하다. 그래서 회전과 확대가
 * 있어야 실제로 읽힌다.
 *
 *   회전    90도씩. exif 를 못 읽고 눕혀 들어온 사진을 세운다
 *   확대    버튼 · 휠 · 더블클릭
 *   이동    확대한 뒤 끌어서
 *
 * 파일은 브라우저 안에서만 쓴다(URL.createObjectURL). 서버로 다시 올리지 않는다.
 */
(function () {
  'use strict';

  var STEPS = [1, 1.5, 2, 3, 4, 6];

  /*
   * PDF 인가.
   *
   * 성적서·품목제조보고서는 **대개 PDF 로 온다.** 사진만 걸 수 있으면 그
   * 화면들은 원본을 옆에 놓지 못해, 종이를 다른 창에서 열어 놓고 숫자를
   * 번갈아 보는 일을 사람이 하게 된다 — 이 뷰어가 있는 까닭 그대로다.
   *
   * 브라우저가 제 뷰어로 그려 주므로 우리 회전·확대는 걷어낸다. 두 벌이
   * 겹치면 어느 쪽이 먹히는지 알 수 없다.
   */
  function looksPdf(url, filename) {
    return /\.pdf($|[?#])/i.test(String(filename || '')) ||
           /\.pdf($|[?#])/i.test(String(url || ''));
  }

  function createPdf(url, filename) {
    var root = document.createElement('div');
    root.className = 'photo-viewer is-pdf';
    root.innerHTML = ''
      + '<div class="photo-viewer-bar">'
      + '  <span class="photo-viewer-name" title="' + (filename || '') + '">'
      +      (filename || '첨부한 문서') + '</span>'
      + '  <div class="photo-viewer-tools">'
      + '    <a class="btn btn-light v2-btn-icon" target="_blank" rel="noopener"'
      + '       href="' + url + '" title="새 창에서 열기">'
      + '      <i class="bi bi-box-arrow-up-right"></i></a>'
      + '  </div>'
      + '</div>'
      + '<div class="photo-viewer-stage">'
      + '  <embed src="' + url + '#toolbar=1" type="application/pdf">'
      + '</div>';
    return root;
  }

  function create(objectUrl, filename) {
    if (looksPdf(objectUrl, filename)) return createPdf(objectUrl, filename);

    var state = { deg: 0, zoom: 0, x: 0, y: 0, dragging: false, sx: 0, sy: 0 };

    var root = document.createElement('div');
    root.className = 'photo-viewer';
    root.innerHTML = ''
      + '<div class="photo-viewer-bar">'
      + '  <span class="photo-viewer-name" title="' + (filename || '') + '">'
      +      (filename || '첨부한 사진') + '</span>'
      + '  <div class="photo-viewer-tools">'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-act="rot-left" title="왼쪽으로 회전">'
      + '      <i class="bi bi-arrow-counterclockwise"></i></button>'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-act="rot-right" title="오른쪽으로 회전">'
      + '      <i class="bi bi-arrow-clockwise"></i></button>'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-act="zoom-out" title="축소">'
      + '      <i class="bi bi-zoom-out"></i></button>'
      + '    <span class="photo-viewer-zoom">100%</span>'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-act="zoom-in" title="확대">'
      + '      <i class="bi bi-zoom-in"></i></button>'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-act="reset" title="원래대로">'
      + '      <i class="bi bi-aspect-ratio"></i></button>'
      + '  </div>'
      + '</div>'
      + '<div class="photo-viewer-stage">'
      + '  <img alt="첨부한 사진" draggable="false">'
      + '</div>'
      + '<div class="photo-viewer-hint">휠로 확대·축소, 끌어서 이동, 더블클릭으로 원래대로</div>';

    var img = root.querySelector('img');
    var stage = root.querySelector('.photo-viewer-stage');
    var zoomLabel = root.querySelector('.photo-viewer-zoom');
    img.src = objectUrl;

    function apply() {
      var scale = STEPS[state.zoom];
      img.style.transform =
        'translate(' + state.x + 'px,' + state.y + 'px) '
        + 'rotate(' + state.deg + 'deg) scale(' + scale + ')';
      zoomLabel.textContent = Math.round(scale * 100) + '%';
      stage.classList.toggle('photo-viewer-pannable', state.zoom > 0);
    }

    function zoom(delta) {
      var next = Math.min(STEPS.length - 1, Math.max(0, state.zoom + delta));
      if (next === state.zoom) return;
      state.zoom = next;
      if (next === 0) { state.x = 0; state.y = 0; }
      apply();
    }

    function reset() {
      state.deg = 0; state.zoom = 0; state.x = 0; state.y = 0;
      apply();
    }

    root.querySelector('.photo-viewer-tools').addEventListener('click', function (e) {
      var btn = e.target.closest('[data-act]');
      if (!btn) return;
      e.preventDefault();
      switch (btn.dataset.act) {
        case 'rot-left':  state.deg -= 90; apply(); break;
        case 'rot-right': state.deg += 90; apply(); break;
        case 'zoom-in':   zoom(1); break;
        case 'zoom-out':  zoom(-1); break;
        case 'reset':     reset(); break;
      }
    });

    stage.addEventListener('wheel', function (e) {
      e.preventDefault();
      zoom(e.deltaY < 0 ? 1 : -1);
    }, { passive: false });

    stage.addEventListener('dblclick', reset);

    stage.addEventListener('mousedown', function (e) {
      if (state.zoom === 0) return;
      state.dragging = true;
      state.sx = e.clientX - state.x;
      state.sy = e.clientY - state.y;
      e.preventDefault();
    });
    window.addEventListener('mousemove', function (e) {
      if (!state.dragging) return;
      state.x = e.clientX - state.sx;
      state.y = e.clientY - state.sy;
      apply();
    });
    window.addEventListener('mouseup', function () { state.dragging = false; });

    apply();
    return root;
  }

  /*
   * 확인 창을 사진과 표 두 칸으로 만든다.
   *
   * source 는 두 가지다.
   *   File    이제 막 고른 사진 (브라우저 안에서만 쓴다)
   *   문자열   이미 서버에 있는 사진의 주소 (문서함에서 다시 읽는 경우)
   *
   * 없으면(품목보고번호로 불러온 경우) 사진 칸 없이 표만 그린다 - 볼 사진이
   * 없는데 빈 칸을 두면 자리만 먹는다.
   */
  /*
   * 뷰어 하나만. 두 칸짜리 틀이 필요 없는 자리에서 쓴다 — 업로드 창이
   * 고른 파일을 그 자리에서 보여 줄 때처럼.
   *
   * 창이 닫히면 objectURL 을 놓아 준다. 그 정리를 부르는 쪽마다 다시 적게
   * 하면 언젠가 한 곳이 빠지고, 그 창을 열 때마다 메모리가 남는다.
   */
  window.photoViewerElement = function (source, name) {
    if (!source) return null;
    var isFile = typeof source !== 'string';
    var url = isFile ? URL.createObjectURL(source) : source;
    var el = create(url, name || (isFile ? source.name : ''));
    if (isFile) el.dataset.objectUrl = url;
    return el;
  };

  /* 붙인 뒤에 부른다 — 그때라야 어느 창 안인지 알 수 있다. */
  window.photoViewerRelease = function (el) {
    if (!el || !el.dataset || !el.dataset.objectUrl) return;
    var url = el.dataset.objectUrl;
    var modal = el.closest('.modal');
    if (!modal) return;
    modal.addEventListener('hidden.bs.modal', function once() {
      URL.revokeObjectURL(url);
      modal.removeEventListener('hidden.bs.modal', once);
    });
  };

  window.photoViewerLayout = function (body, source, tableHtml, name) {
    if (!source) {
      body.innerHTML = tableHtml;
      return;
    }

    body.innerHTML = ''
      + '<div class="row g-3 photo-compare">'
      + '  <div class="col-lg-5"><div class="photo-viewer-slot"></div></div>'
      + '  <div class="col-lg-7 photo-compare-table"></div>'
      + '</div>';
    body.querySelector('.photo-compare-table').innerHTML = tableHtml;

    var isFile = typeof source !== 'string';
    var url = isFile ? URL.createObjectURL(source) : source;
    var label = name || (isFile ? source.name : '');
    body.querySelector('.photo-viewer-slot').appendChild(create(url, label));

    if (isFile) {
      // 창이 닫히면 objectURL 을 놓아 준다
      var modal = body.closest('.modal');
      if (modal) {
        modal.addEventListener('hidden.bs.modal', function once() {
          URL.revokeObjectURL(url);
          modal.removeEventListener('hidden.bs.modal', once);
        });
      }
    }
  };
})();
