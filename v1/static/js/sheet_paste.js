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
 *   3. 엑셀에는 우리가 안 쓰는 열이 딸려 온다. 그게 마지막 칸을 덮는다.
 *   4. 몇 줄이 들어갔는지 아무 말이 없다. 스물세 줄을 붙였는데 스물이
 *      들어갔어도 모른다.
 *
 * 여기서 넷을 한 번에 맡는다. 두 화면이 같은 규칙으로 움직여야 하므로 한
 * 곳에 둔다 — 두 벌로 두면 어느 날 한쪽만 고쳐진다.
 *
 * **양식은 우리가 정한다.** 열 순서를 맞춰 온다는 전제이고, 그래서 화면마다
 * "양식 내려받기" 를 함께 둔다. 열 이름을 보고 알아서 맞추는 것은 다음 일이다.
 */
(function () {
  'use strict';

  /** 견줄 때만 쓰는 형태. 띄어쓰기·괄호·단위 표기를 지운다. */
  function key(text) {
    return String(text == null ? '' : text)
      .replace(/[\s()（）[\]/·.%]/g, '')
      .toLowerCase();
  }

  function isBlankRow(row) {
    return !row || row.every(function (cell) {
      return cell == null || String(cell).trim() === '';
    });
  }

  /**
   * 붙여넣기를 우리 양식에 맞춘다.
   *
   * hot      Handsontable 인스턴스
   * options
   *   headers    양식의 열 이름 (머리글 줄을 알아보는 데 쓴다)
   *   firstCol   자료가 시작하는 칸 번호. 연락처는 0 번이 체크박스라 1
   *   onReport   function(넣은 줄 수, 버린 줄 수, 버린 이유들)
   */
  window.attachSheetPaste = function (hot, options) {
    var headers = (options.headers || []).map(key);
    var firstCol = options.firstCol || 0;
    var report = options.onReport || function () {};

    hot.addHook('beforePaste', function (data, coords) {
      var dropped = [];

      // ① 머리글 줄을 알아보고 버린다.
      //    표를 통째로 드래그하는 것이 사람의 기본 동작이다.
      while (data.length && looksLikeHeader(data[0], headers)) {
        data.shift();
        dropped.push('머리글');
      }

      // ② 빈 줄을 버린다. 엑셀은 선택 영역 아래를 빈 줄로 채워 준다.
      for (var i = data.length - 1; i >= 0; i--) {
        if (isBlankRow(data[i])) {
          data.splice(i, 1);
          dropped.push('빈 줄');
        }
      }

      if (!data.length) {
        report(0, dropped.length, dropped);
        return false;       // 넣을 것이 없으면 표를 건드리지 않는다
      }

      // ③ 우리가 안 쓰는 열이 딸려 오면 잘라 낸다. 안 그러면 마지막 칸을 덮는다.
      var room = hot.countCols() - Math.max(coords[0].startCol, firstCol);
      var extra = 0;
      data.forEach(function (row) {
        if (row.length > room) {
          extra += row.length - room;
          row.length = room;
        }
      });
      if (extra) dropped.push('빈 칸 밖의 값 ' + extra + '개');

      report(data.length, dropped.length, dropped);
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
   * 이 줄이 머리글인가.
   *
   * 두 칸 이상이 양식의 열 이름과 같으면 머리글로 본다. 한 칸만 보면
   * "원료명" 이라는 이름의 원료를 머리글로 오해할 수 있다.
   */
  function looksLikeHeader(row, headers) {
    if (!row || !headers.length) return false;
    var hit = 0;
    row.forEach(function (cell) {
      if (headers.indexOf(key(cell)) >= 0) hit += 1;
    });
    return hit >= 2;
  }

  window.sheetPasteKey = key;   // 시험이 쓴다
})();
