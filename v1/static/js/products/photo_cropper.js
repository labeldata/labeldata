/*
 * 사진에서 읽을 영역을 **여럿** 골라 잘라낸다.
 *
 * 판독이 틀리는 가장 큰 이유는 해상도다. detail:high 는 이미지를 2048 박스에
 * 맞춘 뒤 짧은 변을 768px 로 맞추므로, 작업지시서처럼 라벨이 사진의 일부인
 * 경우 라벨 본문 한 줄이 5px 가 된다. 읽을 수가 없으니 모델이 지어낸다.
 *
 * 라벨만 잘라 보내면 그 768px 이 전부 라벨에 배정된다.
 *
 * **영역이 하나로는 부족했다.** 포장 사진에는 주표시면과 일괄표시면이 따로
 * 떨어져 있다. 둘을 다 담으려고 넓게 고르면 사이의 빈 곳까지 들어와 해상도가
 * 다시 낮아지고, 어느 칸의 값이 어느 면에서 나온 것인지도 구분되지 않는다.
 * 그래서 면마다 하나씩 고르고, 그 면이 무엇인지(주표시면·일괄표시면·영양성분
 * ·원재료명) 이름을 붙여 보낸다. 이름이 붙으면 모델에게 "이 조각에서는 이
 * 항목들을 찾아라" 라고 말할 수 있다.
 *
 * **화면에 꼭 맞춘 사진으로는 경계를 짚을 수 없었다.** 4000px 짜리 사진이
 * 900px 로 줄어 보이므로 일괄표시면의 위아래 끝이 몇 픽셀 안에 뭉친다.
 * 그래서 확대·축소를 둔다. 확대는 **보는 배율만** 바꾼다 - 자를 때는 언제나
 * 원본에서 잘라내므로 확대해서 골랐다고 화질이 달라지지 않는다.
 *
 * **제외할 영역도 고른다.** 일괄표시면 옆에 작업지시서 표나 다른 제품의
 * 라벨이 같이 찍혀 있으면, 사각형 하나로는 그것을 피해 갈 수가 없다. 읽을
 * 영역 안에서 빼고 싶은 자리를 덮어 두면 그 자리는 흰색으로 지워 보낸다 -
 * 모델이 아예 못 본다.
 *
 * **자르기는 브라우저에서 한다.** 원본 파일에서 직접 잘라내므로 화면에 줄여
 * 보여 준 것과 무관하게 원본 해상도가 그대로 남는다. 서버로 올리는 양도 준다.
 *
 * 회전이 먼저다 - 눕혀 찍힌 사진은 세워야 영역을 고를 수 있다.
 *
 * cropPhoto(file) 는 [{file, role}, ...] 로 답한다. 취소하면 null.
 */
(function () {
  'use strict';

  // 이보다 작게 고르면 잘못 끌었을 가능성이 높다 (원본 기준 픽셀)
  var MIN_SIDE = 80;

  // 제외 영역은 이보다 작아도 받는다. 바코드 한 줄, 도장 하나처럼 작은 것을
  // 가리는 일이 실제로 많다 - 읽을 영역과 같은 잣대로 막으면 쓸 수가 없다.
  var MIN_MASK_SIDE = 16;

  // 확대 배율의 위아래. 1 이 "화면에 꼭 맞춤" 이다. 그보다 작게 줄이는 것은
  // 이미 다 보이는 사진을 더 작게 만드는 일이라 쓸 데가 없다.
  var ZOOM_MIN = 1;
  var ZOOM_MAX = 8;
  var ZOOM_STEP = 1.25;

  // 캔버스 한 장의 픽셀 상한. 4000×3000 사진을 8배로 늘리면 3천만 픽셀이 넘고
  // 브라우저가 캔버스를 통째로 버린다(그리면 빈 화면이 된다). 원본 픽셀보다
  // 크게 늘려 봐야 흐려질 뿐이라, 여기서 배율의 위쪽을 사진 크기에 맞춰 깎는다.
  var MAX_CANVAS_PIXELS = 16e6;

  // 표시면 종류와, 그 면에서 보통 읽히는 항목.
  //
  // hint 는 고르는 사람에게 "여기서 무엇을 찾는지" 를 알려 준다. 같은 이름이
  // 서버로 넘어가 모델 지시문이 되므로(ocr_service.REGION_ROLES), 두 목록의
  // key 는 함께 고쳐야 한다.
  var ROLES = [
    { key: 'main',      label: '주표시면',
      hint: '제품명, 내용량, 내용량(열량), 특정성분 함량' },
    { key: 'info',      label: '일괄표시면',
      hint: '식품유형, 품목보고번호, 원재료명, 알레르기, 원산지, 제조원·유통전문판매원, '
          + '소비기한, 보관방법, 포장재질, 주의사항, 기타표시사항' },
    { key: 'rawmtrl',   label: '원재료명',
      hint: '원재료명 및 함량, 알레르기 표시, 원산지' },
    { key: 'nutrition', label: '영양성분표',
      hint: '열량, 나트륨, 탄수화물, 당류, 지방, 트랜스지방, 포화지방, 콜레스테롤, 단백질' },
    { key: 'recycle',   label: '분리배출마크',
      hint: '분리배출 표시(재질 구분)' },
    { key: 'other',     label: '구분 없음',
      hint: '어느 면인지 가리지 않고 표시사항 전반을 읽습니다' }
  ];

  // 고른 순서대로 돌려 쓰는 상자 색. 어느 줄이 어느 상자인지 눈으로 잇는다.
  var COLORS = ['#8ab4f8', '#81c995', '#fdd663', '#f28b82', '#c58af9', '#78d9ec'];

  // 제외 영역은 색을 돌려 쓰지 않는다. 한 가지 색으로 묶어야 "읽는 것" 과
  // "빼는 것" 이 한눈에 갈린다.
  var MASK_COLOR = '#ea4335';

  function roleOf(key) {
    for (var i = 0; i < ROLES.length; i++) {
      if (ROLES[i].key === key) return ROLES[i];
    }
    return ROLES[ROLES.length - 1];
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function ensureModal() {
    var existing = document.getElementById('photoCropModal');
    if (existing) return existing;

    var roleOptions = ROLES.map(function (r) {
      return '<option value="' + r.key + '">' + esc(r.label) + '</option>';
    }).join('');

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
      + '        <div class="alert alert-info py-2 px-3 mb-2" style="font-size:12px;">'
      + '          <i class="bi bi-info-circle me-1"></i>'
      + '          <strong>표시면마다 하나씩 골라 주세요.</strong> 주표시면과 일괄표시면을'
      + '          따로 고르면 각 영역이 확대돼 글자가 크게 보이고, 어느 면에서 무엇을'
      + '          찾을지도 알려 줄 수 있습니다. 필요 없는 영역은 아예 빠집니다.'
      + '        </div>'
      + '        <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">'
      + '          <div class="btn-group btn-group-sm crop-mode" role="group">'
      + '            <button type="button" class="btn btn-primary" data-crop="mode-read">'
      + '              <i class="bi bi-bounding-box"></i> 읽을 영역'
      + '            </button>'
      + '            <button type="button" class="btn btn-outline-danger" data-crop="mode-mask">'
      + '              <i class="bi bi-eraser"></i> 제외할 영역'
      + '            </button>'
      + '          </div>'
      + '          <span class="text-muted crop-mode-hint" style="font-size:12px;"></span>'
      + '          <div class="ms-auto d-flex align-items-center gap-1">'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="zoom-out" title="축소">'
      + '              <i class="bi bi-zoom-out"></i></button>'
      + '            <span class="crop-zoom-level" title="보는 배율 — 잘라내는 화질과는 무관합니다">100%</span>'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="zoom-in" title="확대">'
      + '              <i class="bi bi-zoom-in"></i></button>'
      + '            <button type="button" class="btn btn-light v2-btn-sm" data-crop="zoom-fit" title="화면에 맞춥니다">'
      + '              맞춤</button>'
      + '            <span class="crop-tool-divider"></span>'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="rot-left" title="왼쪽으로 회전">'
      + '              <i class="bi bi-arrow-counterclockwise"></i></button>'
      + '            <button type="button" class="btn btn-light v2-btn-icon" data-crop="rot-right" title="오른쪽으로 회전">'
      + '              <i class="bi bi-arrow-clockwise"></i></button>'
      + '            <button type="button" class="btn btn-light v2-btn-sm" data-crop="clear">모두 지우기</button>'
      + '          </div>'
      + '        </div>'
      + '        <div class="crop-stage">'
      + '          <div class="crop-frame">'
      + '            <canvas class="crop-canvas"></canvas>'
      + '          </div>'
      + '        </div>'
      + '        <div class="crop-picks mt-2"></div>'
      + '        <div class="crop-info text-muted mt-2" style="font-size:12px;"></div>'
      + '        <select class="d-none crop-role-template">' + roleOptions + '</select>'
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

  // 짧은 변이 얼마나 되는지가 판독 품질을 가른다. 모델은 짧은 변을 768px 로
  // 맞춰 보므로, 그보다 작으면 확대해도 글자가 안 늘어난다.
  function grade(shortSide) {
    if (shortSide >= 900) return { text: '충분', cls: 'text-success' };
    if (shortSide >= 600) return { text: '읽을 만함', cls: 'text-muted' };
    return { text: '작은 글씨는 놓칠 수 있음', cls: 'text-warning' };
  }

  /*
   * 영역을 고르게 하고, 고른 만큼 잘린 [{file, role}] 을 돌려준다.
   *
   * 전체를 쓰면 원본 File 을 그대로 돌려준다(다시 인코딩하지 않는다).
   * 취소하면 null.
   */
  window.cropPhoto = function (file) {
    return loadImage(file).then(function (loaded) {
      return new Promise(function (resolve) {
        var modalEl = ensureModal();
        var canvas = modalEl.querySelector('.crop-canvas');
        var frame = modalEl.querySelector('.crop-frame');
        var stage = modalEl.querySelector('.crop-stage');
        var picksEl = modalEl.querySelector('.crop-picks');
        var info = modalEl.querySelector('.crop-info');
        var modeHint = modalEl.querySelector('.crop-mode-hint');
        var zoomLabel = modalEl.querySelector('.crop-zoom-level');
        var useBtn = modalEl.querySelector('[data-crop="use"]');
        var roleTemplate = modalEl.querySelector('.crop-role-template');
        var ctx = canvas.getContext('2d');

        var deg = 0;            // 화면에 그릴 회전각
        var zoom = 1;           // 보는 배율 (1 = 화면에 꼭 맞춤)
        var fitScale = 0;       // 화면에 꼭 맞을 때의 축소율
        var maxZoom = ZOOM_MAX; // 이 사진에서 감당되는 배율 상한
        var mode = 'read';      // 'read' = 읽을 영역, 'mask' = 제외할 영역
        var picks = [];         // [{x,y,w,h,role}] — 캔버스 내부 픽셀
        var masks = [];         // [{x,y,w,h}] — 제외할 자리, 같은 좌표계
        var drag = null;
        var draft = null;       // 끌고 있는 중인 상자

        function rotatedSize() {
          var w = loaded.img.naturalWidth, h = loaded.img.naturalHeight;
          var swapped = (deg % 180 !== 0);
          return { w: w, h: h, cw: swapped ? h : w, ch: swapped ? w : h };
        }

        /*
         * 캔버스를 다시 그린다.
         *
         * refit=true 면 화면에 꼭 맞는 축소율을 새로 잰다(첫 그리기·회전).
         * 그때는 배율도 100% 로 돌린다.
         *
         * 확대만 바뀐 경우에는 **고른 상자를 그대로 둔다.** 상자는 캔버스 내부
         * 픽셀로 들고 있으므로 축소율이 바뀐 만큼 같이 늘려 준다 - 확대할
         * 때마다 다시 고르게 하면 확대가 아무 쓸모가 없다.
         */
        function draw(refit) {
          var size = rotatedSize();
          var w = size.w, h = size.h, cw = size.cw, ch = size.ch;

          if (refit || !fitScale) {
            // 폭을 재기 전에 캔버스를 접는다. 확대해 둔 상태에서 회전하면
            // 스크롤막대가 아직 떠 있어 clientWidth 가 그만큼 좁게 나온다.
            canvas.width = 1;
            canvas.height = 1;
            stage.style.maxHeight = '';
            // 안쪽 여백(8px x 2)을 빼야 CSS 가 캔버스를 다시 줄이지 않는다
            var maxW = Math.max((stage.clientWidth || 900) - 16, 200);
            // 아래에 고른 영역 목록이 붙으므로 예전보다 조금 낮게 잡는다
            var maxH = Math.round(window.innerHeight * 0.5);
            fitScale = Math.min(maxW / cw, maxH / ch, 1);
            // 확대해도 창이 늘어나면 안 된다. 스테이지 높이를 맞춤 상태로
            // 묶어 두고, 넘치는 만큼은 스테이지 안에서 스크롤한다.
            stage.style.maxHeight = (Math.round(ch * fitScale) + 16) + 'px';
            // 이 사진에서 감당되는 배율 상한 (캔버스 픽셀 수로 깎는다)
            var scaleCap = Math.sqrt(MAX_CANVAS_PIXELS / (cw * ch));
            maxZoom = Math.min(ZOOM_MAX, Math.max(1, scaleCap / fitScale));
          }

          var scale = fitScale * zoom;
          var prev = parseFloat(canvas.dataset.scale) || scale;

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

          if (refit) {
            // 회전하면 좌표계가 통째로 바뀐다. 고른 것을 옮겨 주는 것보다 다시
            // 고르게 하는 편이 확실하다 - 회전은 보통 맨 처음에 한 번 한다.
            picks = [];
            masks = [];
            draft = null;
          } else if (prev && Math.abs(scale - prev) > 1e-9) {
            var k = scale / prev;
            [picks, masks].forEach(function (list) {
              list.forEach(function (sel) {
                sel.x *= k; sel.y *= k; sel.w *= k; sel.h *= k;
              });
            });
          }
          drawAll();
          updateZoomLabel();
        }

        function render() { draw(true); }

        function originalSize(sel) {
          var scale = parseFloat(canvas.dataset.scale) || 1;
          return { w: Math.round(sel.w / scale), h: Math.round(sel.h / scale) };
        }

        function bigEnough(sel) {
          var o = originalSize(sel);
          var min = (mode === 'mask') ? MIN_MASK_SIDE : MIN_SIDE;
          return o.w >= min && o.h >= min;
        }

        // 화면에 상자를 다시 깐다. 상자는 캔버스 표시 크기 기준으로 놓는다.
        function drawAll() {
          frame.querySelectorAll('.crop-box').forEach(function (b) { b.remove(); });
          var r = canvas.getBoundingClientRect();
          var kx = canvas.width ? r.width / canvas.width : 1;
          var ky = canvas.height ? r.height / canvas.height : 1;

          picks.forEach(function (sel, i) {
            frame.appendChild(boxEl(sel, kx, ky, COLORS[i % COLORS.length],
                                    (i + 1) + '. ' + roleOf(sel.role).label));
          });
          masks.forEach(function (sel, i) {
            frame.appendChild(boxEl(sel, kx, ky, MASK_COLOR,
                                    '제외 ' + (i + 1), true));
          });
          if (draft) {
            frame.appendChild(boxEl(draft, kx, ky,
                                    mode === 'mask' ? MASK_COLOR : '#ffffff', '',
                                    mode === 'mask'));
          }

          renderPicks();
        }

        function boxEl(sel, kx, ky, color, text, isMask) {
          var box = document.createElement('div');
          box.className = 'crop-box' + (isMask ? ' crop-box--mask' : '');
          box.style.borderColor = color;
          box.style.left = (sel.x * kx) + 'px';
          box.style.top = (sel.y * ky) + 'px';
          box.style.width = (sel.w * kx) + 'px';
          box.style.height = (sel.h * ky) + 'px';
          if (text) {
            var tag = document.createElement('span');
            tag.className = 'crop-box-tag';
            tag.style.background = color;
            if (isMask) tag.style.color = '#ffffff';
            tag.textContent = text;
            box.appendChild(tag);
          }
          return box;
        }

        function renderPicks() {
          useBtn.disabled = picks.length === 0;

          var rows = picks.map(function (sel, i) {
            var o = originalSize(sel);
            var g = grade(Math.min(o.w, o.h));
            return '<div class="crop-pick-row" data-kind="pick" data-idx="' + i + '">'
              + '<span class="crop-pick-dot" style="background:' + COLORS[i % COLORS.length] + '"></span>'
              + '<select class="form-select form-select-sm crop-pick-role">'
              + roleTemplate.innerHTML + '</select>'
              + '<span class="crop-pick-hint"></span>'
              + '<span class="crop-pick-size ' + g.cls + '">' + o.w + '×' + o.h + 'px · ' + g.text + '</span>'
              + '<button type="button" class="btn btn-light v2-btn-icon crop-pick-del" title="이 영역을 지웁니다">'
              + '<i class="bi bi-x-lg"></i></button>'
              + '</div>';
          }).concat(masks.map(function (sel, i) {
            var o = originalSize(sel);
            return '<div class="crop-pick-row crop-pick-row--mask" data-kind="mask" data-idx="' + i + '">'
              + '<span class="crop-pick-dot" style="background:' + MASK_COLOR + '"></span>'
              + '<span class="crop-pick-mask-name">제외 ' + (i + 1) + '</span>'
              + '<span class="crop-pick-hint">이 자리는 흰색으로 지워 보냅니다 — 모델이 못 봅니다</span>'
              + '<span class="crop-pick-size text-muted">' + o.w + '×' + o.h + 'px</span>'
              + '<button type="button" class="btn btn-light v2-btn-icon crop-pick-del" title="이 제외 영역을 지웁니다">'
              + '<i class="bi bi-x-lg"></i></button>'
              + '</div>';
          }));

          picksEl.innerHTML = rows.join('');
          picksEl.querySelectorAll('.crop-pick-row[data-kind="pick"]').forEach(function (row) {
            var idx = parseInt(row.dataset.idx, 10);
            row.querySelector('.crop-pick-role').value = picks[idx].role;
            row.querySelector('.crop-pick-hint').textContent = roleOf(picks[idx].role).hint;
          });

          info.className = 'crop-info text-muted mt-2';
          if (!picks.length) {
            info.textContent = masks.length
              ? '읽을 영역을 고르지 않으면 "전체 사용" 으로 사진 전체를 읽습니다 '
                + '(제외 영역 ' + masks.length + '곳은 지워서 보냅니다).'
              : '영역을 고르지 않으면 "전체 사용" 으로 사진 전체를 읽습니다.';
            return;
          }
          info.textContent = picks.length + '개 영역을 읽습니다. '
            + '표시면 이름을 골라 두면 그 면에서 찾을 항목을 짚어 읽습니다.'
            + (masks.length ? ' 제외 영역 ' + masks.length + '곳은 흰색으로 지워 보냅니다.' : '');
        }

        function setMode(next) {
          mode = next;
          var readBtn = modalEl.querySelector('[data-crop="mode-read"]');
          var maskBtn = modalEl.querySelector('[data-crop="mode-mask"]');
          readBtn.className = 'btn ' + (next === 'read' ? 'btn-primary' : 'btn-outline-primary');
          maskBtn.className = 'btn ' + (next === 'mask' ? 'btn-danger' : 'btn-outline-danger');
          modeHint.textContent = (next === 'mask')
            ? '가릴 자리를 끌어서 덮으세요. 그 자리는 흰색으로 지워 보냅니다.'
            : '끌어서 고르세요. 여러 번 끌면 영역이 계속 더해집니다.';
          canvas.classList.toggle('crop-canvas--mask', next === 'mask');
        }

        function updateZoomLabel() {
          zoomLabel.textContent = Math.round(zoom * 100) + '%';
          // 더 못 늘리는데도 단추가 살아 있으면 눌러도 아무 일이 없다.
          modalEl.querySelector('[data-crop="zoom-in"]').disabled = zoom >= maxZoom - 1e-6;
          modalEl.querySelector('[data-crop="zoom-out"]').disabled = zoom <= ZOOM_MIN + 1e-6;
        }

        /*
         * 배율을 바꾼다. 화면 좌표(clientX/Y)를 주면 그 자리를 붙잡고 늘린다 -
         * 안 그러면 확대할 때마다 보던 곳이 화면 밖으로 밀려난다.
         */
        function zoomTo(next, clientX, clientY) {
          next = Math.min(maxZoom, Math.max(ZOOM_MIN, next));
          if (Math.abs(next - zoom) < 1e-6) return;

          var r = stage.getBoundingClientRect();
          var vx = (clientX == null) ? stage.clientWidth / 2 : (clientX - r.left);
          var vy = (clientY == null) ? stage.clientHeight / 2 : (clientY - r.top);
          var cx = stage.scrollLeft + vx;
          var cy = stage.scrollTop + vy;
          var ratio = next / zoom;

          zoom = next;
          draw(false);
          updateZoomLabel();
          stage.scrollLeft = cx * ratio - vx;
          stage.scrollTop = cy * ratio - vy;
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

        // 새로 고른 영역에 붙일 표시면. 아직 안 쓴 것을 위에서부터 골라 준다 -
        // 보통 주표시면, 일괄표시면 순서로 고른다.
        function nextRole() {
          for (var i = 0; i < ROLES.length; i++) {
            if (ROLES[i].key === 'other') continue;
            var used = picks.some(function (p) { return p.role === ROLES[i].key; });
            if (!used) return ROLES[i].key;
          }
          return 'other';
        }

        canvas.onpointerdown = function (e) {
          canvas.setPointerCapture(e.pointerId);
          drag = pos(e);
          draft = { x: drag.x, y: drag.y, w: 0, h: 0 };
          drawAll();
        };
        canvas.onpointermove = function (e) {
          if (!drag) return;
          var p = pos(e);
          draft = {
            x: Math.min(drag.x, p.x), y: Math.min(drag.y, p.y),
            w: Math.abs(p.x - drag.x), h: Math.abs(p.y - drag.y)
          };
          drawAll();
        };
        canvas.onpointerup = function () {
          drag = null;
          if (!draft) return;
          if (bigEnough(draft)) {
            if (mode === 'mask') {
              masks.push(draft);
            } else {
              draft.role = nextRole();
              picks.push(draft);
            }
            draft = null;
            drawAll();
            return;
          }
          var tooSmall = draft.w > 3 || draft.h > 3;
          draft = null;
          drawAll();
          if (tooSmall) {
            info.className = 'crop-info text-danger mt-2';
            info.textContent = '너무 작습니다. 조금 더 넓게 골라 주세요.';
          }
        };

        // 휠은 Ctrl(맥은 ⌘)과 함께일 때만 배율을 바꾼다. 그냥 굴리면 스테이지가
        // 스크롤돼야 한다 - 확대한 상태에서 사진을 훑는 것이 그 방법이다.
        canvas.onwheel = function (e) {
          if (!e.ctrlKey && !e.metaKey) return;
          e.preventDefault();
          zoomTo(zoom * (e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP), e.clientX, e.clientY);
        };

        picksEl.onchange = function (e) {
          var select = e.target.closest('.crop-pick-role');
          if (!select) return;
          var idx = parseInt(select.closest('.crop-pick-row').dataset.idx, 10);
          picks[idx].role = select.value;
          drawAll();
        };
        picksEl.onclick = function (e) {
          var del = e.target.closest('.crop-pick-del');
          if (!del) return;
          var row = del.closest('.crop-pick-row');
          var idx = parseInt(row.dataset.idx, 10);
          (row.dataset.kind === 'mask' ? masks : picks).splice(idx, 1);
          drawAll();
        };

        function finish(result) {
          bootstrap.Modal.getOrCreateInstance(modalEl).hide();
          URL.revokeObjectURL(loaded.url);
          resolve(result);
        }

        // 고른 영역을 **원본 해상도로** 잘라낸다. 화면에 줄여 그린 것과 무관하다.
        function cutOut(sel, index) {
          return new Promise(function (done) {
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

            // 제외 영역을 흰색으로 덮는다. 이 캔버스는 고른 영역 크기뿐이라
            // 밖으로 나간 부분은 저절로 잘린다 - 겹침을 따로 계산할 필요가 없다.
            octx.fillStyle = '#ffffff';
            masks.forEach(function (m) {
              octx.fillRect((m.x - sel.x) / scale, (m.y - sel.y) / scale,
                            m.w / scale, m.h / scale);
            });

            out.toBlob(function (blob) {
              if (!blob) { done(null); return; }
              var base = (file.name || 'label').replace(/\.[^.]+$/, '');
              var name = base + '_' + roleOf(sel.role).label + (index + 1) + '.jpg';
              done({ file: new File([blob], name, { type: 'image/jpeg' }), role: sel.role });
            }, 'image/jpeg', 0.95);
          });
        }

        modalEl.querySelector('.modal-body').onclick = function (e) {
          var btn = e.target.closest('[data-crop]');
          if (!btn) return;
          var what = btn.dataset.crop;
          if (what === 'rot-left')  { deg -= 90; zoom = 1; render(); }
          if (what === 'rot-right') { deg += 90; zoom = 1; render(); }
          if (what === 'clear') { picks = []; masks = []; draft = null; drawAll(); }
          if (what === 'zoom-in') zoomTo(zoom * ZOOM_STEP);
          if (what === 'zoom-out') zoomTo(zoom / ZOOM_STEP);
          if (what === 'zoom-fit') zoomTo(1);
          if (what === 'mode-read') setMode('read');
          if (what === 'mode-mask') setMode('mask');
        };
        modalEl.querySelector('.modal-footer').onclick = function (e) {
          var btn = e.target.closest('[data-crop]');
          if (!btn) return;

          if (btn.dataset.crop === 'whole') {
            // 회전도 제외 영역도 없으면 원본 그대로. 둘 중 하나라도 있으면
            // 그것을 반영한 사진을 새로 만들어 보낸다.
            if (deg % 360 === 0 && !masks.length) { finish([{ file: file, role: 'whole' }]); return; }
            cutOut({ x: 0, y: 0, w: canvas.width, h: canvas.height, role: 'other' }, 0)
              .then(function (part) {
                finish([{ file: part ? part.file : file, role: 'whole' }]);
              });
            return;
          }

          if (btn.dataset.crop === 'use' && picks.length) {
            btn.disabled = true;
            Promise.all(picks.map(cutOut)).then(function (parts) {
              parts = parts.filter(Boolean);
              finish(parts.length ? parts : [{ file: file, role: 'whole' }]);
            });
          }
        };

        modalEl.addEventListener('hidden.bs.modal', function once() {
          modalEl.removeEventListener('hidden.bs.modal', once);
          resolve(null);   // 이미 resolve 됐으면 무시된다
        });

        bootstrap.Modal.getOrCreateInstance(modalEl).show();
        // 모달이 열린 뒤에 그려야 폭을 잴 수 있다
        modalEl.addEventListener('shown.bs.modal', function once() {
          modalEl.removeEventListener('shown.bs.modal', once);
          zoom = 1;
          canvas.dataset.scale = '';
          setMode('read');
          render();   // 배율 표시는 render 안에서 함께 맞춘다
        });
      });
    });
  };

  // 서버 지시문과 화면 설명이 같은 목록을 쓰도록 밖에서도 볼 수 있게 둔다
  window.cropPhoto.ROLES = ROLES;
})();
