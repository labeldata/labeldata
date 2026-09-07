/*
 * 표 화면의 칸 너비 — 붙여넣기 쓰는 화면 공용.
 *
 * 네 화면이 저마다 너비를 정하고 있었고(배합비·원료 붙여넣기·연락처·영양성분),
 * 셋이 `stretchH: 'all'` 이었다. 그게 이런 일을 냈다.
 *
 *   1. **끌어서 넓히면 다른 칸이 줄어든다.** stretchH 는 칸 전체를 컨테이너
 *      폭에 맞춰 늘이고 줄인다. 한 칸을 넓히면 남은 폭을 다시 나눠 주므로,
 *      **고르지도 않은 칸**이 따라 움직인다.
 *   2. 여러 칸을 골라 함께 조절해도 그대로 남지 않는다. 조절은 됐는데 그
 *      직후 stretch 가 제 비율로 되돌린다.
 *   3. 자리로 정한 너비는 칸을 옮기면 어긋난다. 붙여넣기가 엑셀 순서로 칸을
 *      옮겨 놓으면 배합비가 넓어지고 원재료 표시명이 좁아졌다.
 *   4. 너비가 바뀌면 줄 높이가 따라가야 하는데, 재던 값이 남아 **행 번호와
 *      내용이 어긋난 채로** 그려졌다.
 *
 * 규칙을 하나로 둔다.
 *
 *   · 너비는 **칸 이름**에 붙는다. 칸을 옮겨도 따라간다.
 *   · 성격이 정한다 — 배합비는 숫자 네 자리면 끝이고 원재료 표시명은 문장이
 *     온다. 칸마다 몫(weight)과 최소·최대를 적어 둔다.
 *   · **내용이 없는 칸은 최소로.** 안 쓰는 칸이 자리를 차지하지 않는다.
 *   · 끌어서 조절한 것이 가장 세다. 계정에 남아 다음에 열 때도 그대로다.
 *   · 늘리면 표가 넓어질 뿐 **다른 칸을 줄이지 않는다**(stretchH: 'none').
 *     모자라면 문장이 들어오는 칸이 남는 폭을 가져간다.
 */
(function () {
  'use strict';

  var DEFAULT_RULE = { weight: 10, min: 90, max: 260 };

  function ruleOf(options, name) {
    return (options.rules || {})[name] || options.fallback || DEFAULT_RULE;
  }

  /** 이 칸에 값이 하나라도 있는가. 없으면 최소 너비로 접는다. */
  function hasContent(hot, visual) {
    try {
      var values = hot.getDataAtCol(visual) || [];
      for (var i = 0; i < values.length; i++) {
        var value = values[i];
        if (value !== null && value !== undefined && String(value).trim() !== '') {
          return true;
        }
      }
    } catch (e) {
      return true;      // 못 읽으면 넓은 쪽으로. 좁혀 놓고 안 보이는 것이 나쁘다
    }
    return false;
  }

  window.attachSheetWidths = function (hot, options) {
    var headers = options.headers || [];
    var firstCol = options.firstCol || 0;      // 앞에 붙는 고정 칸(체크박스 등)
    var fixed = options.fixed || [];           // 그 고정 칸들의 너비
    var overrides = Object.assign({}, options.saved || {});   // 이름 -> px
    var saveTimer = null;

    function containerWidth() {
      var box = options.container && document.getElementById(options.container);
      var width = box && box.clientWidth > 10 ? box.clientWidth : 0;
      return width || 900;
    }

    /** 지금 이 자리(화면 순서)에 놓인 칸의 이름 */
    function nameAt(visual) {
      if (visual < firstCol) return null;
      var physical = hot.toPhysicalColumn ? hot.toPhysicalColumn(visual) : visual;
      return headers[physical - firstCol];
    }

    /**
     * 칸마다 너비를 정한다.
     *
     * 몫대로 나누되 성격이 정한 최소·최대 안에 가둔다. 그러고도 남는 폭이
     * 있으면 **문장이 들어오는 칸**(최대가 큰 칸)이 가져간다 — 남겨 두면
     * 표 오른쪽에 빈 띠가 생긴다.
     */
    function compute() {
      // 행 번호 열이 있는 표만 그만큼 뺀다. 없는 표에서 빼면 폭이 남는다
      var settings = hot.getSettings ? hot.getSettings() : {};
      var room = containerWidth() - (settings.rowHeaders ? 52 : 0);
      fixed.forEach(function (px) { room -= px; });

      var names = [], total = 0;
      for (var v = firstCol; v < firstCol + headers.length; v++) {
        var name = nameAt(v);
        names.push(name);
        total += ruleOf(options, name).weight;
      }

      var widths = [], sum = 0, roomy = -1, roomyMax = -1;
      names.forEach(function (name, i) {
        var rule = ruleOf(options, name);
        var width;
        if (overrides[name]) {
          width = overrides[name];             // 끌어서 정한 것이 가장 세다
        } else if (!hasContent(hot, firstCol + i)) {
          width = rule.min;                    // 비어 있는 칸은 자리를 안 쓴다
        } else {
          var share = Math.floor(room * rule.weight / (total || 1));
          width = Math.max(rule.min, Math.min(rule.max, share));
        }
        widths.push(width);
        sum += width;
        if (!overrides[name] && rule.max > roomyMax) {
          roomyMax = rule.max;
          roomy = i;
        }
      });

      if (roomy >= 0 && sum < room) {
        widths[roomy] += room - sum;           // 남는 폭은 문장 칸이 가져간다
      }
      return fixed.concat(widths);
    }

    var cache = compute();

    /* 너비가 바뀌면 **줄 높이를 다시 재야 한다.** 좁아진 칸에서 글이 접히면
       줄이 길어지는데, 재 둔 값이 남아 있으면 행 번호와 내용이 어긋난 채로
       그려진다. 실제로 그렇게 났다. */
    function redraw() {
      var next = compute();
      // 달라진 것이 없으면 건드리지 않는다. 글자를 칠 때마다 표를 다시
      // 그리면 줄이 많은 표에서 손이 걸린다
      if (next.join() === cache.join()) return;
      cache = next;
      hot.updateSettings({ colWidths: function (visual) {
        return cache[visual] || DEFAULT_RULE.min;
      } });
      var rows = hot.getPlugin && hot.getPlugin('autoRowSize');
      if (rows && typeof rows.clearCache === 'function') rows.clearCache();
      hot.render();
    }

    /* 늘린 만큼 표가 넓어질 뿐, 다른 칸은 그대로 둔다. stretchH 가 켜져
       있으면 조절한 그 자리에서 되돌아간다. */
    hot.updateSettings({
      stretchH: 'none',
      colWidths: function (visual) { return cache[visual] || DEFAULT_RULE.min; },
    });

    function remember() {
      if (!options.screen || !options.csrf) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () {
        fetch('/common/grid-order/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': options.csrf },
          body: JSON.stringify({ screen: options.screen, widths: overrides })
        }).catch(function () {});   // 못 남겨도 이번 화면은 이미 그 너비다
      }, 500);
    }

    /*
     * 끌어서 조절했다.
     *
     * **고른 칸이 여럿이면 여럿 다 바뀐다.** Handsontable 이 이미 그렇게
     * 하는데 stretch 가 되돌리고 있었을 뿐이다. 그래서 인자로 온 칸 하나만
     * 보지 않고 **지금 그려진 너비를 통째로 읽어** 이름에 붙인다.
     */
    hot.addHook('afterColumnResize', function () {
      for (var v = firstCol; v < firstCol + headers.length; v++) {
        var name = nameAt(v);
        if (!name) continue;
        var width = hot.getColWidth(v);
        if (width && Math.abs(width - (cache[v] || 0)) > 1) overrides[name] = width;
      }
      remember();
      cache = [];        // 끌어 놓은 값을 반드시 다시 반영한다
      redraw();
    });

    // 칸을 옮기면 너비도 따라간다. 자리에 남아 있으면 배합비가 넓어진다
    hot.addHook('afterColumnMove', redraw);

    // 값이 들어오고 나가면 "비어 있는 칸" 이 달라진다
    var dataTimer = null;
    function later() {
      clearTimeout(dataTimer);
      dataTimer = setTimeout(redraw, 200);
    }
    hot.addHook('afterChange', function (changes, source) {
      if (source === 'loadData' || changes) later();
    });
    hot.addHook('afterLoadData', later);
    hot.addHook('afterRemoveRow', later);

    if (options.container && window.ResizeObserver) {
      var box = document.getElementById(options.container);
      if (box) {
        var boxTimer = null;
        new ResizeObserver(function () {
          clearTimeout(boxTimer);
          boxTimer = setTimeout(redraw, 60);
        }).observe(box);
      }
    }

    /** 끌어서 만든 너비를 지우고 규칙대로 되돌린다 */
    return {
      reset: function () {
        overrides = {};
        remember();
        redraw();
      },
      redraw: redraw,
    };
  };
})();
