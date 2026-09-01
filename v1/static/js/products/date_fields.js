/*
 * 날짜 표시 여러 건 입력 — 소비기한·제조연월일·품질유지기한.
 *
 * 표시사항에 날짜 항목이 둘 이상 필요한 제품이 있다("제조연월일: 별도 표기" +
 * "소비기한: 제조일로부터 12개월"). 그런데 DB 에는 담을 칸이 pog_daycnt 하나다.
 *
 * 칸을 늘리지 않고, 화면에서만 여러 줄로 받아 **한 칸에 줄로 쌓아** 저장한다.
 * 합치고 가르는 규약은 date_entries.js 한 곳에 있다 — 미리보기도 같은 규약으로
 * 읽어 줄마다 표의 한 행을 만든다.
 *
 * 값은 hidden #field-pog-daycnt 에 둔다. 저장(textFieldMap)과 사진 판독
 * (basic_info_ocr.js)이 그 id 로 값을 읽고 쓰기 때문에, 그 둘은 이 화면이
 * 바뀐 것을 몰라도 된다. 사진 판독이 값을 밀어 넣으면 change 가 올라오므로
 * 그때 줄을 다시 그린다.
 */
(function () {
  'use strict';

  var HIDDEN_ID = 'field-pog-daycnt';
  var ROWS_ID   = 'date-entry-rows';
  var ADD_ID    = 'date-entry-add';

  var hidden, rowsEl, writing = false;

  function types() {
    return (window.DateEntries && window.DateEntries.TYPES) || ['소비기한'];
  }

  function rowHtml(entry) {
    var options = types().map(function (t) {
      return '<option value="' + t + '"' + (t === entry.type ? ' selected' : '') + '>' + t + '</option>';
    }).join('');
    var row = document.createElement('div');
    row.className = 'd-flex gap-2 date-entry-row';
    row.innerHTML =
      '<select class="form-select bg-light border-0 v2-field-input date-entry-type"'
      + ' style="width:150px; flex-shrink:0;">' + options + '</select>'
      + '<input type="text" class="form-control bg-light border-0 v2-field-input date-entry-value"'
      + ' placeholder="예) 제조일로부터 12개월, 별도 표기" style="flex:1;">'
      + '<button type="button" class="btn btn-light border-0 date-entry-del"'
      + ' title="이 줄을 지웁니다"><i class="bi bi-x-lg"></i></button>';
    row.querySelector('.date-entry-value').value = entry.value || '';
    return row;
  }

  function render() {
    if (!rowsEl || !hidden) return;
    var entries = window.DateEntries
      ? window.DateEntries.parse(hidden.value)
      : [{ type: '소비기한', value: hidden.value || '' }];
    if (!entries.length) entries = [{ type: '소비기한', value: '' }];
    rowsEl.innerHTML = '';
    entries.forEach(function (e) { rowsEl.appendChild(rowHtml(e)); });
    updateDeleteButtons();
  }

  // 줄이 하나뿐이면 지우기를 막는다. 다 지우고 나면 값을 넣을 자리가 없어진다.
  function updateDeleteButtons() {
    var rows = rowsEl.querySelectorAll('.date-entry-row');
    rows.forEach(function (r) {
      r.querySelector('.date-entry-del').style.visibility =
        rows.length > 1 ? 'visible' : 'hidden';
    });
  }

  function collect() {
    if (!rowsEl || !hidden) return;
    var entries = [];
    rowsEl.querySelectorAll('.date-entry-row').forEach(function (r) {
      entries.push({
        type: r.querySelector('.date-entry-type').value,
        value: r.querySelector('.date-entry-value').value
      });
    });
    var next = window.DateEntries ? window.DateEntries.serialize(entries)
                                  : (entries[0] || {}).value || '';
    if (next === hidden.value) return;
    writing = true;
    hidden.value = next;
    // 저장 대상 값이 바뀌었다는 것을 폼 변경 감지가 알아야 한다
    hidden.dispatchEvent(new Event('input', { bubbles: true }));
    hidden.dispatchEvent(new Event('change', { bubbles: true }));
    writing = false;
  }

  function init() {
    hidden = document.getElementById(HIDDEN_ID);
    rowsEl = document.getElementById(ROWS_ID);
    if (!hidden || !rowsEl) return;

    render();

    rowsEl.addEventListener('input', collect);
    rowsEl.addEventListener('change', collect);
    rowsEl.addEventListener('click', function (e) {
      var del = e.target.closest('.date-entry-del');
      if (!del) return;
      if (rowsEl.querySelectorAll('.date-entry-row').length <= 1) return;
      del.closest('.date-entry-row').remove();
      updateDeleteButtons();
      collect();
    });

    var add = document.getElementById(ADD_ID);
    if (add) {
      add.addEventListener('click', function () {
        // 아직 안 쓴 유형을 골라 준다 - 같은 유형을 두 줄 만들 이유가 없다
        var used = {};
        rowsEl.querySelectorAll('.date-entry-type').forEach(function (s) { used[s.value] = 1; });
        var next = types().filter(function (t) { return !used[t]; })[0] || types()[0];
        rowsEl.appendChild(rowHtml({ type: next, value: '' }));
        updateDeleteButtons();
        rowsEl.lastChild.querySelector('.date-entry-value').focus();
      });
    }

    // 사진 판독 등 바깥에서 값을 밀어 넣으면 줄을 다시 그린다
    ['input', 'change'].forEach(function (ev) {
      hidden.addEventListener(ev, function () { if (!writing) render(); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
