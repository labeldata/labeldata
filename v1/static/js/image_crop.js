/*
 * 사진에서 **쓸 곳만 잘라낸다.** 돌리고 키워서 정확히 잡는다.
 *
 * 원료 봉지를 찍으면 표시사항 말고도 로고·바코드·조리법·손가락이 함께 찍힌다.
 * 그 전부를 판독에 보내면 세 가지가 나빠진다.
 *
 *   · 모델이 볼 글자가 많아져 **엉뚱한 곳을 읽는다**(조리법의 '소금' 을
 *     원재료로 읽는 식이다)
 *   · 보내는 그림이 커서 **느리고 비싸다**
 *   · 문서함에 2.4 MB 짜리가 쌓인다
 *
 * 자르는 일은 **브라우저에서** 한다. 서버는 이미 잘린 그림을 받으므로 판독
 * 코드는 손댈 것이 없고, 원본을 올렸다 다시 자르는 왕복도 없다.
 *
 * **원본은 남기지 않는다.** 다시 찍는 비용이 낮고, 원본까지 두면 문서함이
 * 두 배로 분다. 사용자가 그렇게 정했다.
 *
 * 회전은 **캔버스에 구워 넣는다**
 * ───────────────────────────────
 * CSS transform 으로 돌리면 화면 좌표를 원본 좌표로 되돌리는 셈이 각도마다
 * 달라진다(90 도면 가로세로가 바뀌고 한 축이 뒤집힌다). 그 셈을 틀리면 사용자가
 * 잡은 곳과 다른 곳이 잘려 나가는데, 화면에서는 멀쩡해 보인다. 돌린 그림을
 * 캔버스에 그려 그것을 보여 주면 화면과 그림의 좌표가 늘 같은 방향이라
 * 셈이 하나뿐이다 — `원본픽셀 / 화면픽셀`. 자를 때도 같은 순서로 돌린 뒤
 * 자르므로 화면에서 잡은 그대로 나온다.
 *
 * 확대는 표시 폭을 키우고 상자 안에서 **스크롤**한다. transform scale 로 키우면
 * 옮기려고 끄는 것과 고르려고 끄는 것이 같은 동작이 되어 둘 중 하나를 잃는다.
 *
 * 쓰는 법
 * ───────
 *     var handle = window.imageCrop.attach(hostEl, file);
 *     handle.getRect();                  // {x, y, w, h, deg} · 없으면 null
 *     window.imageCrop.apply(file, rect) // -> Promise<File>
 */
(function () {
    'use strict';

    var MIN_SIZE = 24;              // 이보다 작은 선택은 실수로 본다
    var DISPLAY_MAX = 2048;         // 화면용 캔버스의 긴 변 상한 — 메모리를 아낀다
    var ZOOM_STEPS = [1, 1.5, 2, 3];

    function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

    /* 파일을 <img> 로 읽는다. 두 곳(화면·자르기)이 같은 길을 쓴다. */
    function loadImage(file) {
        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
            img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('사진을 읽지 못했습니다.')); };
            img.src = url;
        });
    }

    /*
     * 원본을 deg 만큼 돌려 캔버스에 그린다. scale 은 화면용으로 줄일 때 쓴다.
     * 화면과 자르기가 **같은 함수**로 돌린다 — 두 벌이면 한쪽만 고쳐지는 날이 온다.
     */
    function rotatedCanvas(img, deg, scale) {
        scale = scale || 1;
        var w = Math.round(img.naturalWidth * scale);
        var h = Math.round(img.naturalHeight * scale);
        var turned = (deg % 180) !== 0;
        var canvas = document.createElement('canvas');
        canvas.width = turned ? h : w;
        canvas.height = turned ? w : h;
        var ctx = canvas.getContext('2d');
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(deg * Math.PI / 180);
        ctx.drawImage(img, -w / 2, -h / 2, w, h);
        return canvas;
    }

    function attach(host, file) {
        if (!host) return null;
        host.innerHTML = '';
        host.classList.add('imgcrop');

        var bar = document.createElement('div');
        bar.className = 'imgcrop-bar';
        bar.innerHTML = ''
            + '<button type="button" class="btn btn-light v2-btn-icon" data-act="rot-left" title="왼쪽으로 회전"><i class="bi bi-arrow-counterclockwise"></i></button>'
            + '<button type="button" class="btn btn-light v2-btn-icon" data-act="rot-right" title="오른쪽으로 회전"><i class="bi bi-arrow-clockwise"></i></button>'
            + '<span class="imgcrop-sep"></span>'
            + '<button type="button" class="btn btn-light v2-btn-icon" data-act="zoom-out" title="축소"><i class="bi bi-zoom-out"></i></button>'
            + '<span class="imgcrop-zoom">100%</span>'
            + '<button type="button" class="btn btn-light v2-btn-icon" data-act="zoom-in" title="확대"><i class="bi bi-zoom-in"></i></button>'
            + '<span class="imgcrop-sep"></span>'
            + '<button type="button" class="btn btn-light v2-btn-icon" data-act="reset" title="원래대로"><i class="bi bi-arrows-angle-contract"></i></button>';

        var scroller = document.createElement('div');
        scroller.className = 'imgcrop-scroll';
        var wrap = document.createElement('div');
        wrap.className = 'imgcrop-wrap';
        var box = document.createElement('div');
        box.className = 'imgcrop-box';
        box.hidden = true;

        scroller.appendChild(wrap);
        wrap.appendChild(box);
        host.appendChild(bar);
        host.appendChild(scroller);

        var source = null;          // 원본 <img>
        var canvas = null;          // 화면에 보이는(돌린·줄인) 캔버스
        var displayScale = 1;       // 원본픽셀 / 화면캔버스픽셀
        var deg = 0;
        var zoom = 0;
        var baseWidth = 0;          // 확대 100% 일 때 캔버스의 CSS 폭
        var rect = null;            // 화면 캔버스 픽셀 좌표 {x, y, w, h}
        var start = null;

        function cssPerPx() {       // 캔버스 픽셀 하나가 화면에서 몇 px 인가
            return canvas && canvas.width ? canvas.clientWidth / canvas.width : 1;
        }

        function paint() {
            if (!rect || !canvas) { box.hidden = true; return; }
            var k = cssPerPx();
            box.hidden = false;
            box.style.left = (rect.x * k) + 'px';
            box.style.top = (rect.y * k) + 'px';
            box.style.width = (rect.w * k) + 'px';
            box.style.height = (rect.h * k) + 'px';
        }

        function applyZoom() {
            if (!canvas) return;
            canvas.style.width = Math.round(baseWidth * ZOOM_STEPS[zoom]) + 'px';
            bar.querySelector('.imgcrop-zoom').textContent = Math.round(ZOOM_STEPS[zoom] * 100) + '%';
            paint();
        }

        function render() {
            if (!source) return;
            var longSide = Math.max(source.naturalWidth, source.naturalHeight);
            var scale = longSide > DISPLAY_MAX ? DISPLAY_MAX / longSide : 1;
            displayScale = 1 / scale;

            var fresh = rotatedCanvas(source, deg, scale);
            fresh.className = 'imgcrop-img';
            if (canvas) wrap.replaceChild(fresh, canvas); else wrap.insertBefore(fresh, box);
            canvas = fresh;

            /* 100% 는 상자 폭에 맞춘 크기다. 원본 픽셀 크기로 두면 4000px
               사진이 화면 밖으로 나가 처음부터 스크롤해야 한다. */
            var avail = Math.max(240, scroller.clientWidth || host.clientWidth || 600);
            baseWidth = Math.min(avail, canvas.width);
            applyZoom();
        }

        function at(ev) {
            var r = canvas.getBoundingClientRect();
            var k = cssPerPx();
            return {
                x: clamp((ev.clientX - r.left) / k, 0, canvas.width),
                y: clamp((ev.clientY - r.top) / k, 0, canvas.height)
            };
        }

        function changed() {
            host.dispatchEvent(new CustomEvent('cropchange', { bubbles: true }));
        }

        wrap.addEventListener('pointerdown', function (ev) {
            if (!canvas) return;
            if (ev.button !== 0 && ev.pointerType === 'mouse') return;
            ev.preventDefault();
            wrap.setPointerCapture(ev.pointerId);
            start = at(ev);
            rect = { x: start.x, y: start.y, w: 0, h: 0 };
            paint();
        });
        wrap.addEventListener('pointermove', function (ev) {
            if (!start) return;
            var p = at(ev);
            rect = { x: Math.min(start.x, p.x), y: Math.min(start.y, p.y),
                     w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) };
            paint();
        });
        function finish(ev) {
            if (!start) return;
            start = null;
            try { wrap.releasePointerCapture(ev.pointerId); } catch (e) {}
            /* 툭 누르기만 한 것은 고른 것이 아니다. 그대로 두면 0 x 0 짜리
               네모가 남아 '잘랐다' 고 말하게 된다. */
            if (rect && (rect.w < MIN_SIZE || rect.h < MIN_SIZE)) rect = null;
            paint();
            changed();
        }
        wrap.addEventListener('pointerup', finish);
        wrap.addEventListener('pointercancel', finish);

        bar.addEventListener('click', function (ev) {
            var btn = ev.target.closest('[data-act]');
            if (!btn) return;
            switch (btn.dataset.act) {
                case 'rot-left':  deg = (deg + 270) % 360; rect = null; render(); changed(); break;
                case 'rot-right': deg = (deg + 90) % 360;  rect = null; render(); changed(); break;
                case 'zoom-in':   zoom = Math.min(ZOOM_STEPS.length - 1, zoom + 1); applyZoom(); break;
                case 'zoom-out':  zoom = Math.max(0, zoom - 1); applyZoom(); break;
                case 'reset':     deg = 0; zoom = 0; rect = null; render(); changed(); break;
            }
        });
        /* 휠로도 키운다 — 확대는 늘 그렇게 되기를 기대한다 */
        scroller.addEventListener('wheel', function (ev) {
            if (!ev.ctrlKey && !ev.metaKey) return;
            ev.preventDefault();
            zoom = clamp(zoom + (ev.deltaY < 0 ? 1 : -1), 0, ZOOM_STEPS.length - 1);
            applyZoom();
        }, { passive: false });

        loadImage(file).then(function (img) { source = img; render(); })
                       .catch(function () { host.textContent = '사진을 읽지 못했습니다.'; });

        return {
            /* 돌린 원본의 픽셀 좌표로 돌려준다. deg 를 함께 주어 apply 가 같은
               순서로 돌린 뒤 자르게 한다 — 화면에서 잡은 그대로 나온다. */
            getRect: function () {
                if (!rect || !canvas) return null;
                return {
                    x: Math.round(rect.x * displayScale),
                    y: Math.round(rect.y * displayScale),
                    w: Math.round(rect.w * displayScale),
                    h: Math.round(rect.h * displayScale),
                    deg: deg
                };
            },
            getRotation: function () { return deg; },
            clear: function () { rect = null; paint(); },
            hasRect: function () { return !!rect; }
        };
    }

    /*
     * 고른 네모만 잘라 새 파일을 만든다. 돌려 두었으면 돌린 채로 나온다.
     *
     * 네모가 없으면 — 돌리지도 않았으면 **원본을 그대로** 돌려주고('전체 쓰기'
     * 가 그 길이다), 돌려만 두었으면 돌린 전체를 돌려준다. 자르기를 건너뛴 것과
     * 실패한 것을 같은 모양으로 다루면 실패했는데 전체가 올라간 것을 아무도
     * 모른다. 그래서 실패는 던진다.
     */
    function apply(file, rect) {
        var deg = (rect && rect.deg) || 0;
        var hasBox = rect && rect.w && rect.h;
        if (!hasBox && !deg) return Promise.resolve(file);

        return loadImage(file).then(function (img) {
            var turned = rotatedCanvas(img, deg, 1);
            var out = turned;
            if (hasBox) {
                out = document.createElement('canvas');
                out.width = rect.w;
                out.height = rect.h;
                out.getContext('2d').drawImage(turned, rect.x, rect.y, rect.w, rect.h, 0, 0, rect.w, rect.h);
            }
            return new Promise(function (resolve, reject) {
                /* PNG 로 뽑으면 사진이 오히려 커진다(무손실이라). 원본이 PNG
                   여도 사진이면 JPEG 로 내보낸다 — 판독에 쓸 그림이다. */
                var type = 'image/jpeg';
                out.toBlob(function (blob) {
                    if (!blob) { reject(new Error('자른 그림을 만들지 못했습니다.')); return; }
                    var name = (file.name || 'photo').replace(/\.[^.]+$/, '') + '_잘라냄.jpg';
                    resolve(new File([blob], name, { type: type }));
                }, type, 0.92);
            });
        });
    }

    /*
     * PDF 면 첫 쪽을 그림으로 바꿔 온다. 자르기·판독은 그림만 다룬다.
     * 돌아오는 것은 File 이라, 부르는 쪽은 그 뒤로 사진과 똑같이 다루면 된다.
     */
    function toImageFile(file, csrfToken) {
        if (!file || !/\.pdf$/i.test(file.name || '')) return Promise.resolve(file);
        var fd = new FormData();
        fd.append('file', file);
        return fetch('/label/my-ingredient/photo/pdf-page/', {
            method: 'POST', headers: { 'X-CSRFToken': csrfToken || '' }, body: fd
        }).then(function (res) {
            if (!res.ok) {
                return res.json().catch(function () { return {}; }).then(function (body) {
                    throw new Error((body && body.error) || 'PDF 를 그림으로 바꾸지 못했습니다.');
                });
            }
            return res.blob();
        }).then(function (blob) {
            var name = (file.name || 'page').replace(/\.pdf$/i, '') + '_1쪽.jpg';
            return new File([blob], name, { type: 'image/jpeg' });
        });
    }

    window.imageCrop = { attach: attach, apply: apply, toImageFile: toImageFile,
                         MIN_SIZE: MIN_SIZE, ZOOM_STEPS: ZOOM_STEPS };
})();
