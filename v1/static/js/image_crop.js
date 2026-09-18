/*
 * 사진에서 **쓸 곳만 잘라낸다.**
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
 * 쓰는 법
 * ───────
 *     var handle = window.imageCrop.attach(hostEl, file);
 *     handle.getRect();                  // {x, y, w, h} 원본 좌표 · 없으면 null
 *     window.imageCrop.apply(file, rect) // -> Promise<Blob>
 */
(function () {
    'use strict';

    var MIN_SIZE = 24;          // 이보다 작은 선택은 실수로 본다

    function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

    /*
     * 그림을 그리고 그 위에 고를 수 있는 네모를 얹는다.
     *
     * 좌표가 둘이다 — 화면에 그려진 크기와 원본 화소 크기. 사용자는 화면
     * 좌표로 끌고, 잘라내기는 원본 좌표로 해야 한다. **그 환산을 한 곳에서만
     * 한다**(toNatural) — 두 벌로 두면 한쪽만 고쳐지는 날이 온다.
     */
    function attach(host, file) {
        if (!host) return null;
        host.innerHTML = '';
        host.classList.add('imgcrop');

        var wrap = document.createElement('div');
        wrap.className = 'imgcrop-wrap';

        var img = document.createElement('img');
        img.className = 'imgcrop-img';
        img.alt = file && file.name ? file.name : '';

        var box = document.createElement('div');
        box.className = 'imgcrop-box';
        box.hidden = true;

        wrap.appendChild(img);
        wrap.appendChild(box);
        host.appendChild(wrap);

        var url = URL.createObjectURL(file);
        img.src = url;
        img.addEventListener('load', function () { URL.revokeObjectURL(url); });

        var rect = null;            // 화면 좌표 {x, y, w, h}
        var start = null;

        function paint() {
            if (!rect) { box.hidden = true; return; }
            box.hidden = false;
            box.style.left = rect.x + 'px';
            box.style.top = rect.y + 'px';
            box.style.width = rect.w + 'px';
            box.style.height = rect.h + 'px';
        }

        function at(ev) {
            var r = img.getBoundingClientRect();
            return {
                x: clamp(ev.clientX - r.left, 0, r.width),
                y: clamp(ev.clientY - r.top, 0, r.height)
            };
        }

        wrap.addEventListener('pointerdown', function (ev) {
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
            rect = {
                x: Math.min(start.x, p.x),
                y: Math.min(start.y, p.y),
                w: Math.abs(p.x - start.x),
                h: Math.abs(p.y - start.y)
            };
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
            host.dispatchEvent(new CustomEvent('cropchange', { bubbles: true }));
        }
        wrap.addEventListener('pointerup', finish);
        wrap.addEventListener('pointercancel', finish);

        return {
            /* 원본 화소 좌표로 돌려준다. 화면에 그려진 크기와 다르다. */
            getRect: function () {
                if (!rect || !img.naturalWidth || !img.clientWidth) return null;
                var sx = img.naturalWidth / img.clientWidth;
                var sy = img.naturalHeight / img.clientHeight;
                return {
                    x: Math.round(rect.x * sx),
                    y: Math.round(rect.y * sy),
                    w: Math.round(rect.w * sx),
                    h: Math.round(rect.h * sy)
                };
            },
            clear: function () { rect = null; paint(); },
            hasRect: function () { return !!rect; }
        };
    }

    /*
     * 고른 네모만 잘라 새 파일을 만든다.
     *
     * 네모가 없으면 **원본을 그대로 돌려준다** — '전체 쓰기' 가 그 길이다.
     * 자르기를 건너뛴 것과 실패한 것을 같은 모양으로 다루면, 실패했는데
     * 전체가 올라간 것을 아무도 모른다. 그래서 실패는 던진다.
     */
    function apply(file, rect) {
        if (!rect || !rect.w || !rect.h) return Promise.resolve(file);

        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function () {
                URL.revokeObjectURL(url);
                var canvas = document.createElement('canvas');
                canvas.width = rect.w;
                canvas.height = rect.h;
                canvas.getContext('2d').drawImage(
                    img, rect.x, rect.y, rect.w, rect.h, 0, 0, rect.w, rect.h);

                /* PNG 로 뽑으면 사진이 오히려 커진다(무손실이라). 원본이
                   PNG 여도 사진이면 JPEG 로 내보낸다 — 판독에 쓸 그림이다. */
                var type = 'image/jpeg';
                canvas.toBlob(function (blob) {
                    if (!blob) { reject(new Error('자른 그림을 만들지 못했습니다.')); return; }
                    var name = (file.name || 'photo').replace(/\.[^.]+$/, '') + '_잘라냄.jpg';
                    resolve(new File([blob], name, { type: type }));
                }, type, 0.92);
            };
            img.onerror = function () {
                URL.revokeObjectURL(url);
                reject(new Error('사진을 읽지 못했습니다.'));
            };
            img.src = url;
        });
    }

    window.imageCrop = { attach: attach, apply: apply, MIN_SIZE: MIN_SIZE };
})();
