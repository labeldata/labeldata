/*
 * 사진에서 읽을 영역만 골라 잘라낸다.
 *
 * 판독이 틀리는 가장 큰 이유는 해상도다. detail:high 는 이미지를 2048 박스에
 * 맞춘 뒤 짧은 변을 768px 로 맞추므로, 작업지시서처럼 라벨이 사진의 일부인
 * 경우 라벨 본문 한 줄이 5px 가 된다. 읽을 수가 없으니 모델이 지어낸다.
 *
 * 라벨만 잘라 보내면 그 768px 이 전부 라벨에 배정된다. 조각 분할(2x2)보다
 * 확실하다 - 필요 없는 영역을 아예 빼기 때문이다.
 *
 * **자르기는 브라우저에서 한다.** 원본 파일에서 직접 잘라내므로 화면에 줄여
 * 보여 준 것과 무관하게 원본 해상도가 그대로 남는다. 서버로 올리는 양도 준다.
 *
 * 회전이 먼저다 - 눕혀 찍힌 사진은 세워야 영역을 고를 수 있다.
 */
(function () {
  'use strict';

  // 이보다 작게 고르면 잘못 끌었을 가능성이 높다 (원본 기준 픽셀)
  var MIN_SIDE = 80;

  function ensureModal() {
    var existing = document.getElementById('photoCropModal');
    if (existing) return existing;

    var wrap = document.createElement('div');
    wrap.innerHTML = ''
      + '<div class="modal fade" id="photoCropModal" tabindex="-1" aria-hidden="true">'
      + '  <div class="modal-dialog modal-xl modal-dialog-centered">'
      + '    <div class="modal-content">'
      + '      <div class="modal-header">'
      + '        <h5 class="modal-title" style="font-size:16px;">'
      + '          <i class="bi bi-crop me-2 text-primary"></i>읽을 영역 고르기'
      + '        </h5>'
      + '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>'
      + '      </div>'
      + '      <div class="modal-body">'
      + '        <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">'
      + '          <span class="text-muted" style="font-size:12px;">'
      + '            표시사항 부분만 끌어서 고르세요. 고른 만큼만 확대해 읽습니다.'
      + '          </span>'
      + '          <div class="ms-auto d-flex align-items-center gap-1">'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="rot-left" title="왼쪽으로 회전">'
      + '              <i class="bi bi-arrow-counterclockwise"></i></button>'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="rot-right" title="오른쪽으로 회전">'
      + '              <i class="bi bi-arrow-clockwise"></i></button>'
      + '            <button type="button" class="btn btn-light v2-btn-sm" data-crop="clear">선택 해제</button>'
      + '          </div>'
      + '        </div>'
      + '        <div class="crop-stage">'
      + '          <div class="crop-frame">'
      + '            <canvas class="crop-canvas"></canvas>'
      + '            <div class="crop-box" hidden></div>'
      + '          </div>'
      + '        </div>'
      + '        <div class="crop-info text-muted mt-2" style="font-size:12px;"></div>'
      + '      </div>'
      + '      <div class="modal-footer">'
      + '        <button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">취소</button>'
      + '        <button type="button" class="btn btn-outline-secondary v2-btn-sm" data-crop="whole">'
      + '          전체 사용'
      + '        </button>'
      + '        <button type="button" class="btn btn-primary v2-btn-sm" data-crop="use" disabled>'
      + '          <i class="bi bi-check2"></i>이 영역으로 읽기'
      + '        </button>'
      + '      </div>'
      + '    </div>'
      + '  </div>'
      + '</div>';
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('photoCropModal');
  }

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () { resolve({ img: img, url: url }); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('이미지를 열지 못했습니다.')); };
      img.src = url;
    });
  }

  /*
   * 영역을 고르게 하고, 고른 만큼 잘린 File 을 돌려준다.
   *
   * 전체를 쓰면 원본 File 을 그대로 돌려준다(다시 인코딩하지 않는다).
   * 취소하면 null.
   */
  window.cropPhoto = function (file) {
    return loadImage(file).then(function (loaded) {
      return new Promise(function (resolve) {
        var modalEl = ensureModal();
        var canvas = modalEl.querySelector('.crop-canvas');
        var box = modalEl.querySelector('.crop-box');
        var info = modalEl.querySelector('.crop-info');
        var useBtn = modalEl.querySelector('[data-crop="use"]');
        var ctx = canvas.getContext('2d');

        var deg = 0;            // 화면에 그릴 회전각
        var sel = null;         // 캔버스 내부 픽셀 {x, y, w, h}
        var drag = null;

        // 회전을 반영해 캔버스에 그린다. 이후 좌표 계산은 모두 이 캔버스 기준.
        function render() {
          var w = loaded.img.naturalWidth, h = loaded.img.naturalHeight;
          var swapped = (deg % 180 !== 0);
          var cw = swapped ? h : w, ch = swapped ? w : h;

          // 화면에 들어갈 크기로만 줄여 그린다 (자를 때는 원본에서 다시 자른다)
          var stage = modalEl.querySelector('.crop-stage');
          // 안쪽 여백(8px x 2)을 빼야 CSS 가 캔버스를 다시 줄이지 않는다
          var maxW = Math.max((stage.clientWidth || 900) - 16, 200);
          var maxH = Math.round(window.innerHeight * 0.6);
          var scale = Math.min(maxW / cw, maxH / ch, 1);

          canvas.width = Math.round(cw * scale);
          canvas.height = Math.round(ch * scale);
          ctx.save();
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.translate(canvas.width / 2, canvas.height / 2);
          ctx.rotate(deg * Math.PI / 180);
          ctx.drawImage(loaded.img, -w * scale / 2, -h * scale / 2,
                        w * scale, h * scale);
          ctx.restore();

          canvas.dataset.scale = scale;
          clearSel();
        }

        function clearSel() {
          sel = null;
          box.hidden = true;
          useBtn.disabled = true;
          info.textContent = '영역을 고르지 않으면 사진 전체를 읽습니다.';
        }

        function drawSel() {
          if (!sel) return;
          // sel 은 캔버스 내부 픽셀이다. 화면에 그릴 때는 표시 크기로 되돌린다.
          var r = canvas.getBoundingClientRect();
          var kx = canvas.width ? r.width / canvas.width : 1;
          var ky = canvas.height ? r.height / canvas.height : 1;

          box.hidden = false;
          box.style.left = (sel.x * kx) + 'px';
          box.style.top = (sel.y * ky) + 'px';
          box.style.width = (sel.w * kx) + 'px';
          box.style.height = (sel.h * ky) + 'px';

          var scale = parseFloat(canvas.dataset.scale) || 1;
          var ow = Math.round(sel.w / scale), oh = Math.round(sel.h / scale);
          var ok = ow >= MIN_SIDE && oh >= MIN_SIDE;
          useBtn.disabled = !ok;
          info.textContent = ok
            ? '고른 영역 ' + ow + '×' + oh + 'px 를 읽습니다.'
            : '너무 작습니다. 조금 더 넓게 골라 주세요.';
        }

        // 화면 좌표를 캔버스 **내부 픽셀**로 옮긴다.
        //
        // getBoundingClientRect() 는 CSS 로 그려진 크기를 준다. 캔버스가
        // max-width 로 줄어들면 내부 픽셀과 다르므로 비율로 되돌려야 한다.
        // 이 값을 그대로 쓰면 오른쪽 끝에 닿지 못한다.
        function pos(e) {
          var r = canvas.getBoundingClientRect();
          var kx = r.width ? canvas.width / r.width : 1;
          var ky = r.height ? canvas.height / r.height : 1;
          return {
            x: Math.min(Math.max((e.clientX - r.left) * kx, 0), canvas.width),
            y: Math.min(Math.max((e.clientY - r.top) * ky, 0), canvas.height)
          };
        }

        canvas.onpointerdown = function (e) {
          canvas.setPointerCapture(e.pointerId);
          drag = pos(e);
          sel = { x: drag.x, y: drag.y, w: 0, h: 0 };
          drawSel();
        };
        canvas.onpointermove = function (e) {
          if (!drag) return;
          var p = pos(e);
          sel = {
            x: Math.min(drag.x, p.x), y: Math.min(drag.y, p.y),
            w: Math.abs(p.x - drag.x), h: Math.abs(p.y - drag.y)
          };
          drawSel();
        };
        canvas.onpointerup = function () { drag = null; };

        function finish(result) {
          bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          URL.revokeObjectURL(loaded.url);
          resolve(result);
        }

        // 고른 영역을 **원본 해상도로** 잘라낸다. 화면에 줄여 그린 것과 무관하다.
        function cutOut() {
          var scale = parseFloat(canvas.dataset.scale) || 1;
          var out = document.createElement('canvas');
          out.width = Math.round(sel.w / scale);
          out.height = Math.round(sel.h / scale);

          var octx = out.getContext('2d');
          octx.save();
          // 캔버스와 같은 회전을 적용한 뒤, 고른 위치만큼 원점을 옮긴다
          octx.translate(-sel.x / scale, -sel.y / scale);
          var w = loaded.img.naturalWidth, h = loaded.img.naturalHeight;
          var swapped = (deg % 180 !== 0);
          var cw = swapped ? h : w, ch = swapped ? w : h;
          octx.translate(cw / 2, ch / 2);
          octx.rotate(deg * Math.PI / 180);
          octx.drawImage(loaded.img, -w / 2, -h / 2, w, h);
          octx.restore();

          out.toBlob(function (blob) {
            if (!blob) { finish(file); return; }
            var name = (file.name || 'label').replace(/\.[^.]+$/, '') + '_선택영역.jpg';
            finish(new File([blob], name, { type: 'image/jpeg' }));
          }, 'image/jpeg', 0.95);
        }

        modalEl.querySelector('.modal-body').onclick = function (e) {
          var btn = e.target.closest('[data-crop]');
          if (!btn) return;
          if (btn.dataset.crop === 'rot-left') { deg -= 90; render(); }
          if (btn.dataset.crop === 'rot-right') { deg += 90; render(); }
          if (btn.dataset.crop === 'clear') clearSel();
        };
        modalEl.querySelector('.modal-footer').onclick = function (e) {
          var btn = e.target.closest('[data-crop]');
          if (!btn) return;
          if (btn.dataset.crop === 'whole') {
            // 회전만 했으면 회전을 반영해 내보낸다. 아무것도 안 했으면 원본 그대로.
            if (deg % 360 === 0) { finish(file); return; }
            sel = { x: 0, y: 0, w: canvas.width, h: canvas.height };
            cutOut();
          }
          if (btn.dataset.crop === 'use' && sel) cutOut();
        };

        modalEl.addEventListener('hidden.bs.modal', function once() {
          modalEl.removeEventListener('hidden.bs.modal', once);
          resolve(null);   // 이미 resolve 됐으면 무시된다
        });

        bootstrap.Modal.getOrCreateInstance(modalEl).show();
        // 모달이 열린 뒤에 그려야 폭을 잴 수 있다
        modalEl.addEventListener('shown.bs.modal', function once() {
          modalEl.removeEventListener('shown.bs.modal', once);
          render();
        });
      });
    });
  };
})();
