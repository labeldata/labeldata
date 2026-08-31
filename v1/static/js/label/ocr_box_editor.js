/*
 * 사진 위에 "읽은 자리" 를 번호 상자로 얹고, 사람이 그 자리를 고치게 한다.
 *
 * 왜 필요한가. 값이 틀렸을 때 지금까지 알 수 있는 것은 "틀렸다" 뿐이었다.
 * 어디를 읽고 그 답을 냈는지 보이면 **왜** 틀렸는지가 보인다 - 옆 칸을
 * 읽었는지, 작업지시서의 표를 읽었는지, 아예 못 찾았는지.
 *
 * 상자는 두 가지다. 섞으면 안 된다.
 *
 *   판독 위치 (파란 점선)  모델이 "여기서 읽었다" 고 말한 자리. 틀릴 수 있다.
 *   정답 위치 (초록 실선)  사람이 "여기가 맞다" 고 확정한 자리. 채점의 잣대다.
 *
 * 좌표는 **원본 사진 픽셀**로 주고받는다. 화면에서는 사진이 줄어들어 보이지만,
 * 상자를 퍼센트로 얹으면 확대·축소를 해도 알아서 따라간다 - 화면 크기를
 * 계산해 픽셀로 얹으면 확대할 때마다 어긋난다.
 */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  var ZOOMS = [100, 150, 200, 300, 450];

  function mount(container, opts) {
    var imageW = (opts.imageSize || [])[0] || 0;
    var imageH = (opts.imageSize || [])[1] || 0;

    // 원본 크기를 모르면 상자를 얹을 수 없다. 어림한 크기로 그리면 상자가
    // 엉뚱한 데 앉고, 그 상태로 정답 위치를 저장하면 정답지가 오염된다.
    if (!imageW || !imageH) {
      container.innerHTML = '<div class="lab-empty">'
        + '사진 크기를 읽지 못해 위치 표시를 쓸 수 없습니다.</div>';
      return null;
    }

    var truth = {};       // 정답 위치 {항목: [x,y,w,h]}
    var detected = {};    // 판독 위치 {항목: [x,y,w,h]}
    var order = [];       // 번호 순서 (항목명 배열)
    var selected = null;
    var zoom = 0;
    var drawing = null;

    container.innerHTML = ''
      + '<div class="bx-bar">'
      + '  <span class="bx-hint">상자를 끌면 옮겨지고, 오른쪽 아래 모서리를 끌면 크기가 바뀝니다.'
      + '  빈 곳을 끌면 <strong>선택한 항목</strong>의 새 상자를 그립니다.</span>'
      + '  <span class="bx-zoom">'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-bx="zoom-out"><i class="bi bi-zoom-out"></i></button>'
      + '    <span class="bx-zoom-label">100%</span>'
      + '    <button type="button" class="btn btn-light v2-btn-icon" data-bx="zoom-in"><i class="bi bi-zoom-in"></i></button>'
      + '  </span>'
      + '</div>'
      + '<div class="bx-scroll"><div class="bx-stage">'
      + '  <img src="' + esc(opts.imageUrl) + '" alt="" draggable="false">'
      + '  <div class="bx-layer"></div>'
      + '</div></div>'
      + '<div class="bx-legend">'
      + '  <span><i class="bx-swatch bx-swatch-truth"></i>정답 위치 — 채점의 잣대</span>'
      + '  <span><i class="bx-swatch bx-swatch-found"></i>판독 위치 — 모델이 읽었다고 한 자리</span>'
      + '</div>';

    var scroll = container.querySelector('.bx-scroll');
    var stage = container.querySelector('.bx-stage');
    var layer = container.querySelector('.bx-layer');
    var zoomLabel = container.querySelector('.bx-zoom-label');

    function applyZoom() {
      stage.style.width = ZOOMS[zoom] + '%';
      zoomLabel.textContent = ZOOMS[zoom] + '%';
    }

    function numberOf(field) {
      var i = order.indexOf(field);
      return i < 0 ? '' : String(i + 1);
    }

    function pct(box) {
      return {
        left: box[0] / imageW * 100,
        top: box[1] / imageH * 100,
        width: box[2] / imageW * 100,
        height: box[3] / imageH * 100
      };
    }

    // 화면 좌표 -> 원본 픽셀. 무대의 실제 크기로 나눈다 - 확대 배율을 따로
    // 곱하지 않는다(배율은 이미 무대 크기에 반영돼 있다).
    function toOriginal(clientX, clientY) {
      var rect = stage.getBoundingClientRect();
      return [
        Math.round((clientX - rect.left) / rect.width * imageW),
        Math.round((clientY - rect.top) / rect.height * imageH)
      ];
    }

    function clamp(box) {
      var x = Math.max(0, Math.min(Math.round(box[0]), imageW - 1));
      var y = Math.max(0, Math.min(Math.round(box[1]), imageH - 1));
      var w = Math.max(4, Math.min(Math.round(box[2]), imageW - x));
      var h = Math.max(4, Math.min(Math.round(box[3]), imageH - y));
      return [x, y, w, h];
    }

    function draw() {
      var html = '';
      order.forEach(function (field) {
        var num = numberOf(field);
        // 판독 위치를 먼저 그린다. 정답 위치가 위에 와야 끌 수 있다.
        if (detected[field]) html += boxHtml(field, detected[field], num, 'found');
        if (truth[field]) html += boxHtml(field, truth[field], num, 'truth');
      });
      layer.innerHTML = html;
    }

    function boxHtml(field, box, num, kind) {
      var p = pct(box);
      return '<div class="bx-box bx-' + kind
        + (kind === 'truth' && field === selected ? ' bx-on' : '') + '"'
        + ' data-field="' + esc(field) + '" data-kind="' + kind + '"'
        + ' style="left:' + p.left + '%;top:' + p.top + '%;'
        + 'width:' + p.width + '%;height:' + p.height + '%;">'
        + '<span class="bx-tag">' + num + '</span>'
        + (kind === 'truth' ? '<span class="bx-grip"></span>' : '')
        + '</div>';
    }

    function select(field) {
      selected = field;
      draw();
      var el = layer.querySelector('.bx-truth[data-field="' + (field || '') + '"]')
        || layer.querySelector('.bx-found[data-field="' + (field || '') + '"]');
      if (el && el.scrollIntoView) {
        el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
      if (opts.onSelect) opts.onSelect(field);
    }

    // ── 끌기 ───────────────────────────────────────────────────────────────
    //
    // 세 가지가 같은 몸짓이다: 상자 옮기기 / 모서리로 크기 바꾸기 / 빈 곳에
    // 새로 그리기. 시작할 때 무엇인지 정하고 나머지는 같은 경로로 흐른다.

    var drag = null;

    stage.addEventListener('mousedown', function (e) {
      var grip = e.target.closest('.bx-grip');
      var box = e.target.closest('.bx-box');

      if (grip && box) {
        drag = { mode: 'resize', field: box.dataset.field,
                 start: toOriginal(e.clientX, e.clientY),
                 origin: truth[box.dataset.field].slice() };
      } else if (box) {
        select(box.dataset.field);
        // 판독 위치는 모델이 말한 자리다. 끌어서 고칠 수 있는 것은 정답 위치뿐 -
        // 판독 위치를 손대면 "모델이 뭐라고 했는지" 가 사라진다.
        if (box.dataset.kind !== 'truth') return;
        drag = { mode: 'move', field: box.dataset.field,
                 start: toOriginal(e.clientX, e.clientY),
                 origin: truth[box.dataset.field].slice() };
      } else {
        if (!selected) return;      // 어느 항목의 상자인지 모르면 그릴 수 없다
        var at = toOriginal(e.clientX, e.clientY);
        drag = { mode: 'draw', field: selected, start: at, origin: [at[0], at[1], 4, 4] };
      }
      e.preventDefault();
    });

    window.addEventListener('mousemove', function (e) {
      if (!drag) return;
      var at = toOriginal(e.clientX, e.clientY);
      var dx = at[0] - drag.start[0];
      var dy = at[1] - drag.start[1];
      var o = drag.origin;

      if (drag.mode === 'move') {
        truth[drag.field] = clamp([o[0] + dx, o[1] + dy, o[2], o[3]]);
      } else if (drag.mode === 'resize') {
        truth[drag.field] = clamp([o[0], o[1], o[2] + dx, o[3] + dy]);
      } else {
        truth[drag.field] = clamp([
          Math.min(drag.start[0], at[0]), Math.min(drag.start[1], at[1]),
          Math.abs(dx), Math.abs(dy)
        ]);
      }
      draw();
    });

    window.addEventListener('mouseup', function () {
      if (!drag) return;
      var field = drag.field;
      drag = null;
      if (opts.onChange) opts.onChange(field, truth[field]);
    });

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-bx]');
      if (!btn) return;
      e.preventDefault();
      if (btn.dataset.bx === 'zoom-in') zoom = Math.min(ZOOMS.length - 1, zoom + 1);
      if (btn.dataset.bx === 'zoom-out') zoom = Math.max(0, zoom - 1);
      applyZoom();
    });

    applyZoom();

    return {
      setOrder: function (fields) { order = fields.slice(); draw(); },
      setTruth: function (boxes) { truth = Object.assign({}, boxes || {}); draw(); },
      setDetected: function (boxes) { detected = Object.assign({}, boxes || {}); draw(); },
      /* 판독 위치를 정답 위치로 채택한다. 모델이 맞게 짚었으면 이게 가장 빠르다. */
      adopt: function (field) {
        if (!detected[field]) return false;
        truth[field] = detected[field].slice();
        draw();
        return true;
      },
      adoptAll: function () {
        var n = 0;
        Object.keys(detected).forEach(function (f) {
          if (order.indexOf(f) < 0) return;
          truth[f] = detected[f].slice();
          n++;
        });
        draw();
        return n;
      },
      clear: function (field) { delete truth[field]; draw(); },
      select: select,
      selected: function () { return selected; },
      numberOf: numberOf,
      boxOf: function (field) { return truth[field] || detected[field] || null; },
      truthBoxes: function () { return Object.assign({}, truth); },
      detectedBoxes: function () { return Object.assign({}, detected); },
      scrollTop: function () { scroll.scrollTop = 0; }
    };
  }

  window.ocrBoxEditor = { mount: mount };
})();
