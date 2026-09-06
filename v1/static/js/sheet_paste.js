/*
 * 엑셀에서 붙여넣기 — 표 화면 공용.
 *
 * 사용자들은 배합비도 연락처도 엑셀로 관리하다 여기로 온다. 그래서 두 화면
 * 모두 표(Handsontable)로 만들어 뒀는데, 붙여넣기가 **자리로만** 들어갔다.
 * 그래서 이런 일이 났다.
 *
 *   1. 엑셀에서 머리글까지 함께 긁어 오면 "원료명" 이라는 **원료가 한 줄
 *      생긴다.** 사람은 표를 통째로 드래그하지 열만 골라 잡지 않는다.
 *   2. 연락처 표는 첫 칸이 체크박스다. 왼쪽 끝에 붙여넣으면 이메일이
 *      체크박스 칸으로 들어가고 한 칸씩 밀린다.
 *   3. **열 순서가 다르다.** 쓰던 양식이 이렇다.
 *
 *        순서 · 원재료/원료명 · 배합비율/원료함량 · 식품유형 · 업체명 ·
 *        원재료명 및 함량 / 성분 · 비고
 *
 *      우리 표와 순서도 다르고, "순서" 처럼 우리에게 없는 열도 있다.
 *      자리로만 넣으면 배합비 자리에 식품유형이 들어간다.
 *   4. 몇 줄이 들어갔는지 아무 말이 없다. 스물세 줄을 붙였는데 스물이
 *      들어갔어도 모른다.
 *
 * **머리글을 읽어 맞춘다.** 머리글 줄은 어차피 버리려고 이미 읽고 있었다 —
 * 버리는 대신 쓰면 열 순서를 맞출 수 있다. AI 를 쓰지 않는다. 이름 목록과
 * 견주는 사전 대조라 결과가 늘 같고, 무엇을 어떻게 맞췄는지 그대로 말해 줄
 * 수 있다.
 *
 * 두 화면이 같은 규칙으로 움직여야 하므로 한 곳에 둔다 — 두 벌로 두면 어느 날
 * 한쪽만 고쳐진다.
 */
(function () {
  'use strict';

  /** 견줄 때만 쓰는 형태. 띄어쓰기·괄호·구분기호·단위 표기를 지운다. */
  function key(text) {
    return String(text == null ? '' : text)
      .replace(/[\s()（）[\]{}/\\|·・,.\-_%]/g, '')
      .toLowerCase();
  }

  function isBlankRow(row) {
    return !row || row.every(function (cell) {
      return cell == null || String(cell).trim() === '';
    });
  }

  /**
   * 머리글 한 칸이 우리 어느 칸을 말하는가.
   *
   * 글자까지 같으면 그것으로 정한다. 아니면 **가장 긴 이름이 들어 있는**
   * 칸을 고른다 — "원재료명 및 함량 / 성분" 에는 "원재료명"(원료명)도
   * "원재료명및함량"(원재료 표시명)도 들어 있는데, 긴 쪽이 더 구체적이다.
   *
   * Returns: {col, score} 또는 null
   */
  function matchColumn(text, aliases) {
    var want = key(text);
    if (!want) return null;
    var best = null;
    Object.keys(aliases).forEach(function (col) {
      aliases[col].forEach(function (alias) {
        var a = key(alias);
        if (!a) return;
        var score = want === a ? 1000 + a.length
                  : want.indexOf(a) >= 0 ? a.length
                  : 0;
        if (score && (!best || score > best.score)) {
          best = { col: col, score: score };
        }
      });
    });
    return best;
  }

  /**
   * 머리글 줄로 열 짝을 짓는다.
   *
   * Returns: {map, names, unused} 또는 null (머리글이 아니면)
   *   map[가져온 칸 번호] = 우리 칸 번호
   *   names  사람에게 보여 줄 짝 목록
   *   unused 짝을 못 지은 머리글 이름 (버릴 열)
   */
  function planColumns(row, headers, aliases) {
    if (!row) return null;
    var map = {}, names = [], unused = [], taken = {};

    row.forEach(function (cell, j) {
      var hit = matchColumn(cell, aliases);
      var label = String(cell == null ? '' : cell).trim();
      if (!hit) {
        if (label) unused.push(label);
        return;
      }
      var col = headers.indexOf(hit.col);
      if (col < 0) return;
      // 같은 칸을 두 열이 가리키면 더 확실한 쪽을 남긴다
      if (taken[col] && taken[col].score >= hit.score) {
        unused.push(label);
        return;
      }
      if (taken[col]) {
        delete map[taken[col].j];
        unused.push(taken[col].label);
      }
      taken[col] = { score: hit.score, j: j, label: label };
      map[j] = col;
      names.push(label + ' → ' + hit.col);
    });

    // 두 칸 이상 짝이 지어져야 머리글로 본다. 한 칸만 보면 "원료명" 이라는
    // 이름의 원료를 머리글로 오해한다.
    if (names.length < 2) return null;
    return { map: map, names: names, unused: unused };
  }

  /**
   * 붙여넣기를 우리 양식에 맞춘다.
   *
   * hot      Handsontable 인스턴스
   * options
   *   headers    우리 열 이름 (자리 순서대로)
   *   aliases    {우리 열 이름: [엑셀에서 쓰는 이름들]}
   *   firstCol   자료가 시작하는 칸 번호. 연락처는 0 번이 체크박스라 1
   *   onReport   function({added, dropped, why, matched, unused})
   */
  window.attachSheetPaste = function (hot, options) {
    var headers = options.headers || [];
    var aliases = options.aliases || {};
    var firstCol = options.firstCol || 0;
    var report = options.onReport || function () {};

    hot.addHook('beforePaste', function (data, coords) {
      var why = [], matched = null, unused = [];

      // ① 머리글 줄이 있으면 그것으로 열을 맞춘다.
      var plan = planColumns(data[0], headers, aliases);
      if (plan) {
        data.shift();
        matched = plan.names;
        unused = plan.unused;

        // 칸을 끌어다 옮겨 둔 사람이 있다. 값은 **화면에 보이는 자리**로
        // 들어가야 한다 — 논리 자리로 넣으면 옮겨 둔 만큼 어긋난다.
        var seat = {};
        Object.keys(plan.map).forEach(function (j) {
          var logical = firstCol + plan.map[j];
          var visual = typeof hot.toVisualColumn === 'function'
              ? hot.toVisualColumn(logical) : logical;
          if (visual >= firstCol) seat[j] = visual - firstCol;
        });

        for (var r = 0; r < data.length; r++) {
          var row = new Array(headers.length).fill('');
          data[r].forEach(function (cell, j) {
            if (seat[j] !== undefined) row[seat[j]] = cell;
          });
          data[r] = row;
        }
        // 맞춰 놓았으니 자료가 시작하는 칸부터 넣는다
        coords.forEach(function (range) {
          range.endCol += firstCol - range.startCol;
          range.startCol = firstCol;
        });
      }

      // ② 빈 줄을 버린다. 엑셀은 선택 영역 아래를 빈 줄로 채워 준다.
      var blanks = 0;
      for (var i = data.length - 1; i >= 0; i--) {
        if (isBlankRow(data[i])) {
          data.splice(i, 1);
          blanks += 1;
        }
      }
      if (blanks) why.push('빈 줄 ' + blanks + '개');

      if (!data.length) {
        report({ added: 0, dropped: blanks, why: why,
                 matched: matched, unused: unused, plan: plan });
        return false;       // 넣을 것이 없으면 표를 건드리지 않는다
      }

      // ③ 머리글이 없어 자리로 넣는 경우. 남는 칸 밖의 값은 잘라 낸다 —
      //    안 그러면 마지막 칸을 덮는다.
      if (!plan) {
        var room = hot.countCols() - Math.max(coords[0].startCol, firstCol);
        var extra = 0;
        data.forEach(function (row) {
          if (row.length > room) {
            extra += row.length - room;
            row.length = room;
          }
        });
        if (extra) why.push('빈 칸 밖의 값 ' + extra + '개');
      }

      report({ added: data.length, dropped: blanks, why: why,
               matched: matched, unused: unused, plan: plan });
    });

    // ④ 자료가 시작하는 칸보다 왼쪽에 붙이면 한 칸씩 밀린다. 자리를 옮겨 준다.
    if (firstCol > 0) {
      hot.addHook('beforePaste', function (data, coords) {
        coords.forEach(function (range) {
          if (range.startCol < firstCol) {
            var shift = firstCol - range.startCol;
            range.startCol += shift;
            range.endCol += shift;
          }
        });
      });
    }
  };

  /**
   * 붙여넣은 열 순서대로 화면의 칸을 늘어놓는다.
   *
   * 쓰던 엑셀의 열 순서는 그 사람이 일하는 순서다. 값만 제자리에 들어가고
   * 화면은 우리 순서로 남아 있으면, 붙여넣은 것을 눈으로 견주기가 어렵다.
   *
   * 엑셀에 없던 칸은 뒤로 보낸다. 지우지 않는다 — 그 칸을 안 쓰는 것과
   * 그 엑셀에 없던 것은 다른 일이다.
   *
   * Returns: 늘어놓은 칸 이름들. 바꿀 것이 없었으면 null.
   */
  window.sheetPasteReorder = function (hot, plan, options) {
    var headers = options.headers || [];
    var firstCol = options.firstCol || 0;
    var plugin = hot.getPlugin && hot.getPlugin('manualColumnMove');
    if (!plugin || !plugin.isEnabled || !plugin.isEnabled()) return null;

    var wanted = [];
    Object.keys(plan.map).map(Number).sort(function (a, b) { return a - b; })
      .forEach(function (j) {
        var logical = firstCol + plan.map[j];
        if (wanted.indexOf(logical) < 0) wanted.push(logical);
      });
    for (var c = firstCol; c < firstCol + headers.length; c++) {
      if (wanted.indexOf(c) < 0) wanted.push(c);
    }

    var now = [];
    for (var v = firstCol; v < firstCol + headers.length; v++) {
      now.push(hot.toPhysicalColumn ? hot.toPhysicalColumn(v) : v);
    }
    if (now.join() === wanted.join()) return null;   // 이미 그 순서다

    plugin.moveColumns(wanted.map(function (logical) {
      return hot.toVisualColumn ? hot.toVisualColumn(logical) : logical;
    }), firstCol);
    hot.render();
    return wanted.map(function (logical) { return headers[logical - firstCol]; });
  };

  /**
   * 칸 순서를 계정에 남긴다. **브라우저가 아니라 계정이다** — 회사 엑셀의
   * 열 순서는 그 사람이 일하는 방식이라 자리를 옮긴다고 달라지지 않는다.
   */
  window.sheetPasteSaveOrder = function (screen, order, csrf) {
    if (!order || !order.length) return;
    fetch('/common/grid-order/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ screen: screen, order: order })
    }).catch(function () {});   // 남기지 못해도 이번 화면은 이미 바뀌었다
  };

  /** 남겨 둔 순서대로 칸을 늘어놓는다. 화면을 열 때 부른다. */
  window.sheetPasteApplyOrder = function (hot, order, options) {
    var headers = options.headers || [];
    var firstCol = options.firstCol || 0;
    var plugin = hot.getPlugin && hot.getPlugin('manualColumnMove');
    if (!plugin || !order || !order.length) return;

    var wanted = [];
    order.forEach(function (name) {
      var i = headers.indexOf(name);
      if (i >= 0 && wanted.indexOf(firstCol + i) < 0) wanted.push(firstCol + i);
    });
    for (var c = firstCol; c < firstCol + headers.length; c++) {
      if (wanted.indexOf(c) < 0) wanted.push(c);
    }
    plugin.moveColumns(wanted.map(function (logical) {
      return hot.toVisualColumn ? hot.toVisualColumn(logical) : logical;
    }), firstCol);
    hot.render();
  };

  /** 무엇을 어떻게 맞췄는지 한 줄로. 화면 둘이 같은 말을 쓰게 한다. */
  window.sheetPasteMessage = function (info, tail) {
    if (!info.added) {
      return '넣을 줄이 없습니다. 머리글만 붙여넣으셨나요?';
    }
    var parts = [info.added + '줄을 넣었습니다.'];
    if (info.matched) {
      parts.push('열을 머리글로 맞췄습니다 — ' + info.matched.join(', ') + '.');
      if (info.unused.length) {
        parts.push('"' + info.unused.join('", "') + '" 은(는) 쓰지 않았습니다.');
      }
    }
    if (info.why.length) parts.push('(' + info.why.join(', ') + ' 은 뺐습니다)');
    if (tail) parts.push(tail);
    return parts.join(' ');
  };

  window.sheetPasteKey = key;               // 시험이 쓴다
  window.sheetPastePlan = planColumns;      // 시험이 쓴다
})();
