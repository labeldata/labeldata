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
 * 그러고 나니 **줄** 쪽에서 같은 일이 났다. 열여덟 줄짜리 배합비를 붙였는데
 * 스물한 줄이 들어갔다.
 *
 *   5. 맨 아래 "합  계 100.000" 줄이 원료 한 줄로 들어간다(배합비 합계가
 *      200% 가 된다). 회사 양식에 거의 언제나 있는 줄이다.
 *   6. 붙여넣고 나면 Handsontable 이 들어간 자리를 통째로 잡아 준다. 그런데
 *      우리는 머리글 줄·빈 줄·합계 줄을 덜어 내므로, 다음 붙여넣기는 잡힌
 *      자리보다 작다 — Handsontable 은 모자란 만큼 **앞 줄을 되풀이해서**
 *      채운다.
 *
 * **붙여넣은 것이 줄 수와 자리를 정한다**(aim). 표에서 잡아 둔 자리는 어디서
 * 시작할지만 말한다.
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

  /*
   * 이 칸이 "있다" 는 표시인가.
   *
   * 엑셀로 배합비를 관리하는 사람들은 알레르기를 이렇게 적는 일이 흔하다.
   *
   *     계란  우유  밀  대두
   *      O    X    X   O
   *
   * 무엇을 "있다" 로 볼지는 사람마다 다르다 — O, ○, V, ✓, 1, 예, 유.
   * 없다는 쪽(X, -, 0, 무, 빈칸)은 세지 않는다. **애매한 것은 없다로 본다** —
   * 없는 알레르기를 적으면 라벨이 틀리고, 빠뜨린 것은 요약이 다시 잡아 준다.
   */
  var MARK_ON = ['o', 'ㅇ', '○', '◯', '●', 'v', '√', '✓', '✔', 'y', 'yes',
                 '예', '유', '함유', '1', 'true', 't'];

  function isMarked(cell) {
    var text = String(cell == null ? '' : cell).trim().toLowerCase();
    if (!text) return false;
    return MARK_ON.indexOf(text) >= 0;
  }

  function isBlankRow(row) {
    return !row || row.every(function (cell) {
      return cell == null || String(cell).trim() === '';
    });
  }

  /*
   * 합계 줄인가.
   *
   * 회사 배합비 엑셀은 맨 아래에 마무리 줄을 둔다.
   *
   *     …
   *     정제수            0.000    5.342
   *          합  계     100.000  100.000
   *
   * 그대로 넣으면 **원료가 한 줄 늘고 배합비 합계가 200% 가 된다.** 사람
   * 눈에는 표의 마무리라 줄 수가 하나 많은 것도 잘 안 보인다. 실제 양식에서
   * 열여덟 줄을 붙였는데 열아홉 줄이 들어갔다.
   *
   * "합계" 가 **우리 표에 자리가 없는 열**에 적혀 있는 일이 흔하다(위 예에서는
   * ERP 원재료 칸이다). 그래서 한 칸만 보지 않고 줄 전체를 본다.
   *
   * 가르는 자리는 **이름 칸이 비어 있는가**다. 이름이 있는 줄은 건드리지
   * 않는다 — 합계라는 이름의 원료는 없지만, 이름이 있는 줄을 버리면 원료가
   * 소리 없이 사라진다.
   */
  var TOTAL_WORDS = ['합계', '소계', '총계', '누계', '계', 'total', 'subtotal',
                     'sum'];

  function isTotalRow(row, nameCols) {
    if (!row) return false;
    for (var i = 0; i < nameCols.length; i++) {
      var name = row[nameCols[i]];
      if (name != null && String(name).trim() !== '') return false;
    }
    return row.some(function (cell) {
      return TOTAL_WORDS.indexOf(key(cell)) >= 0;
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
  function planColumns(row, headers, aliases, marks) {
    if (!row) return null;
    // unused 는 사람에게 보여 줄 이름, unusedCols 는 그 열이 몇 번째였는지.
    // 값을 버리지 않고 비고로 옮기려면 자리를 알아야 한다.
    var map = {}, names = [], unused = [], unusedCols = [], taken = {};
    // 체크 열: {가져온 칸 번호: {col: 넣을 칸, value: 적을 말}}
    var checks = {}, checkNames = [];

    /* 자리를 못 잡은 열. 이름은 사람에게 보여 주고, 자리(j)는 값을 비고로
       옮기는 데 쓴다 — 이름만 남기면 값이 사라진다. */
    function lose(j, label) {
      if (!label) return;
      unused.push(label);
      unusedCols.push({ j: j, label: label.replace(/\s+/g, ' ').trim() });
    }

    row.forEach(function (cell, j) {
      var hit = matchColumn(cell, aliases);
      var label = String(cell == null ? '' : cell).trim();

      // 우리 칸 이름이 아니면 체크 열인지 본다. 열 이름 자체가 값인 경우다.
      if (!hit && marks) {
        var mark = matchColumn(cell, marks.names);
        if (mark) {
          checks[j] = { col: marks.into, value: mark.col };
          checkNames.push(label);
          return;
        }
      }

      if (!hit) {
        lose(j, label);
        return;
      }
      var col = headers.indexOf(hit.col);
      if (col < 0) return;
      /* 같은 칸을 두 열이 가리키면 더 확실한 쪽을 남긴다. 진 쪽은 **버리는
         것이 아니라 자리를 잃은 것이다** — 값은 짝 못 지은 열과 똑같이 비고로
         옮긴다.

         실제 양식에서 그렇게 났다. "품목제조보고서 원재료명" 이 원료명을
         가져가면 "품목제조보고서 원재료 기타설명"·"ERP 원재료"·"원료코드" 가
         모두 여기로 온다("원재료"·"원료" 를 품고 있어서다). 하필 그 회사에서
         원료를 찾는 열쇠들인데, 이름만 "쓰지 않았습니다" 로 적히고 값은
         사라졌다. */
      if (taken[col] && taken[col].score >= hit.score) {
        lose(j, label);
        return;
      }
      if (taken[col]) {
        delete map[taken[col].j];
        lose(taken[col].j, taken[col].label);
      }
      taken[col] = { score: hit.score, j: j, label: label };
      map[j] = col;
      names.push(label + ' → ' + hit.col);
    });

    // 두 칸 이상 짝이 지어져야 머리글로 본다. 한 칸만 보면 "원료명" 이라는
    // 이름의 원료를 머리글로 오해한다.
    if (names.length < 2) return null;
    // 비고에 모을 때 엑셀에 있던 열 순서 그대로 적힌다
    unusedCols.sort(function (a, b) { return a.j - b.j; });
    return { map: map, names: names, unused: unused, unusedCols: unusedCols,
             checks: checks, checkNames: checkNames };
  }

  /*
   * 머리글이 두 줄인 양식.
   *
   * 회사 양식은 위 칸을 병합해 큰 이름을 쓰고 아래 줄에 낱개 이름을 적는
   * 일이 흔하다.
   *
   *     ├──────────── 알레르기 ────────────┤
   *     │ 알류 │ 우유 │ 메밀 │ 대두 │ 밀 │ … │
   *
   * 병합한 칸은 붙여넣으면 **첫 칸에만 글자가 있고 나머지는 빈칸**이다.
   * 그래서 위 줄만 보면 알레르기 열 열아홉 개가 통째로 안 보이고, 아래
   * 줄은 자료 한 줄로 들어간다. 실제 양식으로 확인했다 — O/X 열 열아홉
   * 개가 전부 버려지고 "알류 우유 메밀 …" 이라는 원료가 한 줄 생겼다.
   *
   * 합칠 때는 **아래 줄을 먼저 쓴다.** 낱개 이름이 더 구체적이다.
   */
  function mergeHeader(top, sub) {
    var n = Math.max((top || []).length, (sub || []).length);
    var out = new Array(n);
    for (var i = 0; i < n; i++) {
      var below = String(sub && sub[i] != null ? sub[i] : '').trim();
      out[i] = below || (top && top[i] != null ? top[i] : '');
    }
    return out;
  }

  /*
   * 아래 줄이 머리글인가, 자료인가.
   *
   * "밀가루" 는 알레르기 "밀" 을 품는다. 자료 줄을 머리글로 잘못 합치면
   * 없는 체크 열이 생긴다.
   *
   * 가르는 자리는 **위 줄의 빈칸**이다. 병합한 머리글이라면 아래 줄의
   * 글자가 위 줄이 비어 있는 자리에 온다. 실제 양식에서 열아홉 칸 중
   * 열여덟 칸이 그랬고, 자료 줄은 여섯 칸 중 한 칸도 그렇지 않았다.
   */
  function looksLikeSubHeader(top, sub) {
    if (!top || !sub) return false;
    var filled = 0, underGap = 0;
    for (var i = 0; i < sub.length; i++) {
      if (String(sub[i] == null ? '' : sub[i]).trim() === '') continue;
      filled += 1;
      if (String(top[i] == null ? '' : top[i]).trim() === '') underGap += 1;
    }
    return filled >= 2 && underGap >= 2 && underGap >= filled * 0.6;
  }

  /** 짝지은 열이 몇 개인가. 두 줄을 합칠지 고르는 잣대다. */
  function planSize(plan) {
    return plan ? plan.names.length + plan.checkNames.length : -1;
  }

  /**
   * 머리글을 읽는다. 한 줄일 수도, 두 줄일 수도 있다.
   *
   * Returns: {plan, rows} 또는 null
   */
  function readHeader(data, headers, aliases, marks) {
    var one = planColumns(data[0], headers, aliases, marks);
    if (data.length > 1 && looksLikeSubHeader(data[0], data[1])) {
      var two = planColumns(mergeHeader(data[0], data[1]),
                            headers, aliases, marks);
      if (planSize(two) > planSize(one)) return { plan: two, rows: 2 };
    }
    return one ? { plan: one, rows: 1 } : null;
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

    /*
     * **알린 뒤에 옮긴다.**
     *
     * beforePaste 안에서 곧바로 알리면, 그 말을 들은 쪽(화면)이 칸을 옮긴다.
     * 그런데 Handsontable 은 이 함수가 끝난 **뒤에** 값을 써 넣는다. 그러니
     * 값은 옮기기 전 자리를 기준으로 만들어 놓고, 쓰기는 옮긴 뒤 자리에
     * 들어간다 — 옮긴 만큼 통째로 어긋난다.
     *
     * 실제로 그렇게 났다. 배합비 열이 알레르기 칸으로 들어가고, 짝을 못 지은
     * 열은 사라졌다. 지난번 붙여넣기와 열 이름이 같을 때는 옮길 것이 없어서
     * (moveColumns 가 돌지 않아서) 멀쩡했고, 그래서 한동안 안 드러났다.
     *
     * 값이 다 들어간 뒤에 알린다.
     */
    var pending = null;
    hot.addHook('afterPaste', function () {
      if (!pending) return;
      var info = pending;
      pending = null;
      report(info);
    });

    hot.addHook('beforePaste', function (data, coords) {
      var why = [], matched = null, unused = [];

      // ① 머리글 줄이 있으면 그것으로 열을 맞춘다. 두 줄일 수도 있다.
      var head = readHeader(data, headers, aliases, options.marks);
      var plan = head && head.plan;
      if (plan) {
        for (var h = 0; h < head.rows; h++) data.shift();
        matched = plan.names;
        unused = plan.unused;
        if (head.rows > 1) {
          matched = matched.concat(['머리글 두 줄을 합쳐 읽었습니다']);
        }
      }

      /* ② 합계 줄을 버린다. 아직 가져온 칸 그대로일 때 봐야 한다 — "합  계"
         는 우리 표에 자리가 없는 열에 적혀 있는 일이 흔하다. */
      var nameCols = [0];
      if (plan) {
        nameCols = Object.keys(plan.map).filter(function (j) {
          return plan.map[j] === 0;
        }).map(Number);
      }
      var totals = 0;
      // 이름 칸이 어느 열인지 모르면 버리지 않는다. 무엇이 이름인지 모르면서
      // 줄을 버리면 원료가 소리 없이 사라진다.
      for (var t = nameCols.length ? data.length - 1 : -1; t >= 0; t--) {
        if (isTotalRow(data[t], nameCols)) {
          data.splice(t, 1);
          totals += 1;
        }
      }
      if (totals) why.push('합계 줄 ' + totals + '개');

      if (plan) {
        // 칸을 끌어다 옮겨 둔 사람이 있다. 값은 **화면에 보이는 자리**로
        // 들어가야 한다 — 논리 자리로 넣으면 옮겨 둔 만큼 어긋난다.
        var seat = {};
        Object.keys(plan.map).forEach(function (j) {
          var logical = firstCol + plan.map[j];
          var visual = typeof hot.toVisualColumn === 'function'
              ? hot.toVisualColumn(logical) : logical;
          if (visual >= firstCol) seat[j] = visual - firstCol;
        });

        // 체크 열이 넣을 칸도 화면 자리로 찾아 둔다
        var seatOf = function (name) {
          var i = headers.indexOf(name);
          if (i < 0) return -1;
          var v = typeof hot.toVisualColumn === 'function'
              ? hot.toVisualColumn(firstCol + i) : firstCol + i;
          return v >= firstCol ? v - firstCol : -1;
        };
        var checkSeat = (options.marks && plan.checkNames.length)
            ? seatOf(options.marks.into) : -1;

        /* 짝을 못 지은 열도 **값이 있으면 버리지 않는다.**
           ERP 원재료·원료코드·품목제조보고서 기타설명처럼 우리 표에 자리가
           없는 것들이 그 회사에서는 원료를 찾는 열쇠다. 지우면 어디서 온
           원료인지 알 수 없어진다. 이름을 달아 비고에 모은다.

               ERP 원재료: SPC삼립전용분(20kg) · 원료코드: 250521 */
        var carrySeat = -1, carryCols = [];
        if (options.carry && plan.unusedCols.length) {
          carrySeat = seatOf(options.carry);
          if (carrySeat >= 0) carryCols = plan.unusedCols;
        }

        for (var r = 0; r < data.length; r++) {
          var row = new Array(headers.length).fill('');
          var found = [];
          data[r].forEach(function (cell, j) {
            if (seat[j] !== undefined) row[seat[j]] = cell;
            if (plan.checks[j] && isMarked(cell)) {
              // 같은 물질을 두 열이 가리켜도 한 번만 적는다
              if (found.indexOf(plan.checks[j].value) < 0) {
                found.push(plan.checks[j].value);
              }
            }
          });
          // 체크로 모은 것이 있으면 그 칸에 적는다. 그 칸을 따로 채워 온
          // 경우에는 덮지 않는다 — 사람이 적은 것이 더 확실하다.
          if (checkSeat >= 0 && found.length && !row[checkSeat]) {
            row[checkSeat] = found.join(', ');
          }
          // 짝 못 지은 열의 값을 비고 뒤에 붙인다. 원래 비고를 덮지 않는다.
          if (carrySeat >= 0) {
            var extra = [];
            carryCols.forEach(function (u) {
              var v = data[r][u.j];
              if (v == null || String(v).trim() === '') return;
              extra.push(u.label + ': ' + String(v).replace(/\s+/g, ' ').trim());
            });
            if (extra.length) {
              row[carrySeat] = [row[carrySeat], extra.join(' · ')]
                  .filter(Boolean).join(' · ');
            }
          }
          data[r] = row;
        }
        if (plan.checkNames.length) {
          matched = matched.concat([
            plan.checkNames.join('·') + ' 열의 O 를 모아 ' + options.marks.into
          ]);
        }
        if (carrySeat >= 0 && carryCols.length) {
          matched = matched.concat([
            carryCols.map(function (u) { return u.label; }).join('·')
              + ' 은 ' + options.carry + ' 로'
          ]);
          unused = [];      // 버린 것이 아니라 옮긴 것이다
        }
      }

      // ③ 빈 줄을 버린다. 엑셀은 선택 영역 아래를 빈 줄로 채워 준다.
      var blanks = 0;
      for (var i = data.length - 1; i >= 0; i--) {
        if (isBlankRow(data[i])) {
          data.splice(i, 1);
          blanks += 1;
        }
      }
      if (blanks) why.push('빈 줄 ' + blanks + '개');

      if (!data.length) {
        // 넣을 것이 없으면 afterPaste 가 오지 않는다. 여기서 바로 알린다
        report({ added: 0, dropped: blanks + totals, why: why,
                 matched: matched, unused: unused, plan: plan });
        return false;       // 표를 건드리지 않는다
      }

      // ④ 어디서부터 넣을지 정한다. 아래 aim 을 보라 — 표에서 잡아 둔 자리를
      //    한 칸으로 좁힌다.
      var startCol = aim(plan ? firstCol : -1);

      // ⑤ 머리글이 없어 자리로 넣는 경우. 남는 칸 밖의 값은 잘라 낸다 —
      //    안 그러면 마지막 칸을 덮는다.
      if (!plan) {
        var room = hot.countCols() - startCol;
        var extra = 0;
        data.forEach(function (row) {
          if (row.length > room) {
            extra += row.length - room;
            row.length = room;
          }
        });
        if (extra) why.push('빈 칸 밖의 값 ' + extra + '개');
      }

      pending = { added: data.length, dropped: blanks + totals, why: why,
                  matched: matched, unused: unused, plan: plan };
    });

    /*
     * ⑥ **붙여넣은 것이 줄 수와 자리를 정한다.** 표에서 잡아 둔 자리가 정하지
     * 않는다.
     *
     * Handsontable 은 잡아 둔 자리의 왼쪽 위부터 넣고, 넣을 것이 그 자리보다
     * 작으면 **모자란 만큼 앞에서부터 되풀이해 채운다**(populateValues 의
     * `o.length % n`). 그리고 붙여넣고 나면 들어간 자리를 통째로 잡아 준다.
     *
     * 우리는 머리글 줄과 빈 줄과 합계 줄을 덜어 내므로, **두 번째 붙여넣기부터는
     * 잡힌 자리가 넣을 것보다 늘 크다.** 그래서 이렇게 났다 — 열여덟 줄을
     * 붙였는데 스물한 줄이 들어가고, 열여덟 줄 뒤로는 앞 줄들이 되풀이됐다.
     *
     * beforePaste 가 받는 coords 로는 못 고친다. 그것은 **복사용 자리**이고
     * (CopyPaste.copyableRanges), 붙는 자리는 그때그때 잡혀 있는 선택
     * 영역에서 온다. 고쳐 봐야 아무 일도 일어나지 않는다.
     *
     * 잡아 둔 자리를 한 칸으로 좁힌다. 되풀이가 사라지고, 머리글로 열을 맞춘
     * 줄은 커서가 어디 있었든 자료가 시작하는 칸부터 들어간다.
     *
     * Returns: 넣기 시작할 칸 번호
     */
    function aim(wantCol) {
      var range = typeof hot.getSelectedRangeLast === 'function'
          ? hot.getSelectedRangeLast() : null;
      var at = range && typeof range.getTopStartCorner === 'function'
          ? range.getTopStartCorner() : null;
      var row = at ? at.row : 0;
      var col = wantCol >= 0 ? wantCol
              : Math.max(at ? at.col : firstCol, firstCol);
      // 좁히지 못해도 값은 들어가야 한다. 자리를 못 옮기는 것과 붙여넣기가
      // 통째로 죽는 것은 다른 일이다.
      try {
        if (typeof hot.selectCell === 'function') hot.selectCell(row, col, row, col);
      } catch (e) {}
      return col;
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
  window.sheetPasteMarked = isMarked;       // 시험이 쓴다
  window.sheetPastePlan = planColumns;      // 시험이 쓴다
  window.sheetPasteHeader = readHeader;     // 시험이 쓴다
  window.sheetPasteSubHeader = looksLikeSubHeader;   // 시험이 쓴다
})();
