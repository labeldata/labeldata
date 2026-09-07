/*
 * 표시 디자인 의뢰서.
 *
 * 표시사항을 다 만들고 나면 디자인 담당자에게 넘긴다. 지금은 그 문서를 엑셀·
 * 워드로 손수 짠다 — 우리 표에 있는 값을 다시 옮겨 적고, 규정(10p 이상·자간·
 * 장평)을 왼쪽에 적고, 비고에 지시를 단다.
 *
 * 우리 내보내기가 주던 것은 **정보표시면 표 한 장**이었다. 의뢰서와 셋이
 * 다르다 — 표시장소 구분, 규정 메모, 비고 열.
 *
 * 그 셋을 채워서 그대로 워드로 낸다. 다만 **한 번 보여 주고 낸다.** 비고는
 * 그때그때 다르고("무광매트 날인 확인"), 규정 메모도 회사마다 조금씩 다르다.
 * 내보내기 직전에 고칠 수 있어야 하고, 고친 것은 다음번에도 그대로여야 한다.
 *
 * 값은 미리보기 표에서 온다 — 화면에 그려진 것이 곧 인쇄될 것이라, 여기서
 * 다시 만들면 두 벌이 된다. 원산지 굵게와 알레르기 박스도 그대로 살려 간다
 * (cellHtmlForDoc).
 */
(function () {
  'use strict';

  function prefs() {
    return window.DESIGN_REQUEST || { notes: { main: [], info: [] }, mainFields: [] };
  }

  function el(id) { return document.getElementById(id); }

  /** 미리보기 표의 줄들을 표시장소로 가른다 */
  function panels() {
    var mainFields = prefs().mainFields || [];
    var main = [], info = [];

    document.querySelectorAll('#previewTableBody [data-field-row]').forEach(function (row) {
      // 2단 배치는 한 <tr> 에 항목이 둘이라 칸이 이름을 갖는다
      if (row.tagName === 'TR' && row.querySelector('[data-field-row]')) return;
      var cells = row.tagName === 'TR'
          ? [row.querySelector('th'), row.querySelector('td')]
          : [row, row.nextElementSibling];
      if (!cells[0] || !cells[1]) return;
      var field = row.getAttribute('data-field-row');
      var item = { field: field, head: cells[0], body: cells[1] };
      (mainFields.indexOf(field) >= 0 ? main : info).push(item);
    });
    return { main: main, info: info };
  }

  /* 주의사항·기타표시사항은 **줄마다 한 항목**이다. 의뢰서가 그렇게 생겼고,
     그래야 디자이너가 어느 문구를 어디에 넣을지 짚을 수 있다. */
  var SPLIT_FIELDS = ['cautions', 'additional_info'];

  function lines(text) {
    return String(text || '').split(/\r?\n/)
      .map(function (line) { return line.trim(); })
      .filter(Boolean);
  }

  /**
   * 의뢰서에 들어갈 줄들.
   *
   * Returns: [{panel, name, html, note, key}]
   *   panel  'main' | 'info'
   *   html   표시사항 내용 (원산지 굵게·알레르기 박스를 살린 HTML)
   *   note   비고. 우리가 아는 지시는 미리 채워 둔다
   */
  function rows() {
    var found = panels(), out = [];
    var toDoc = window.cellHtmlForDoc || function (cell) {
      return cell ? cell.innerHTML : '';
    };
    var clean = window.cleanCellText || function (cell) {
      return cell ? cell.textContent.trim() : '';
    };

    function push(panel, item) {
      var name = clean(item.head);
      if (SPLIT_FIELDS.indexOf(item.field) >= 0) {
        lines(clean(item.body)).forEach(function (line, i) {
          out.push({ panel: panel, name: i === 0 ? name : '',
                     html: '* ' + line, note: '',
                     key: item.field + ':' + i });
        });
        return;
      }
      out.push({ panel: panel, name: name, html: toDoc(item.body),
                 note: hintFor(item.field), key: item.field });
    }

    found.main.forEach(function (item) { push('main', item); });
    found.info.forEach(function (item) { push('info', item); });
    return out;
  }

  /* 우리가 아는 지시는 미리 적어 둔다. 규정이 요구하는 표시라 빠지면 안 되는
     것들이고, 사람이 매번 손으로 적기에는 늘 같은 말이다. */
  function hintFor(field) {
    if (field === 'rawmtrl_nm_display' || field === 'rawmtrl_nm') {
      return '원산지 굵게 표시 · 알레르기 문구는 별도 칸(검은 바탕 흰 글씨)';
    }
    if (field === 'prdlst_nm') return '주표시면';
    return '';
  }

  /* ── 창 ─────────────────────────────────────────────────────────────── */

  function noteInputs(panel) {
    return (prefs().notes[panel] || []).map(function (line, i) {
      return '<input type="text" class="dr-note-line" data-panel="' + panel
           + '" data-i="' + i + '" value="' + line.replace(/"/g, '&quot;') + '">';
    }).join('');
  }

  function open() {
    var box = el('designRequestModal');
    if (!box) return;
    draw();
    box.classList.add('is-open');
    box.setAttribute('aria-hidden', 'false');
  }

  function close() {
    var box = el('designRequestModal');
    if (!box) return;
    box.classList.remove('is-open');
    box.setAttribute('aria-hidden', 'true');
  }

  function draw() {
    var list = rows();
    var body = el('drRows');
    if (!body) return;

    var html = '';
    ['main', 'info'].forEach(function (panel) {
      var mine = list.filter(function (row) { return row.panel === panel; });
      if (!mine.length) return;
      var title = panel === 'main' ? '주표시면' : '정보표시면';
      html += '<tr class="dr-panel-row"><td class="dr-panel" rowspan="' + mine.length + '">'
           + '<b>' + title + '</b><div class="dr-notes">' + noteInputs(panel) + '</div>'
           + '</td>' + rowCells(mine[0]) + '</tr>';
      mine.slice(1).forEach(function (row) {
        html += '<tr>' + rowCells(row) + '</tr>';
      });
    });
    body.innerHTML = html || '<tr><td colspan="4">표시사항이 비어 있습니다.</td></tr>';
  }

  /* 줄마다 지우는 단추. 의뢰서에 안 넣을 항목이 늘 몇 개 있는데(그 제품에
     해당 없는 문구), 지울 길이 없으면 워드에서 다시 지워야 한다. */
  function rowCells(row) {
    return '<td class="dr-name">' + (row.name || '') + '</td>'
         + '<td class="dr-body">' + row.html + '</td>'
         + '<td class="dr-note"><input type="text" data-note="' + row.key
         + '" value="' + String(row.note || '').replace(/"/g, '&quot;') + '">'
         + '<button type="button" class="dr-drop" title="이 줄을 의뢰서에서 뺍니다"'
         + ' aria-label="줄 빼기">&times;</button></td>';
  }

  /** 화면에서 고친 것을 읽어 온다 */
  function collect() {
    var notes = { main: [], info: [] };
    document.querySelectorAll('.dr-note-line').forEach(function (input) {
      notes[input.getAttribute('data-panel')].push(input.value.trim());
    });
    var marks = {};
    document.querySelectorAll('#drRows [data-note]').forEach(function (input) {
      marks[input.getAttribute('data-note')] = input.value.trim();
    });
    return { notes: notes, marks: marks };
  }

  /* 고친 규정 메모는 계정에 남는다. 사내 기준은 그 사람이 일하는 방식이라
     의뢰서를 낼 때마다 다시 적게 하면 안 된다. */
  function remember(notes) {
    var url = (window.DESIGN_REQUEST_SAVE_URL || '');
    var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value;
    if (!url || !csrf) return;
    window.DESIGN_REQUEST.notes = notes;
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ notes: notes })
    }).catch(function () {});   // 못 남겨도 이번 의뢰서는 이미 그 값이다
  }

  /* ── 문구함 ──────────────────────────────────────────────────────────── */

  /** 자주 쓰는 문구를 불러와 고르게 한다. 매번 다시 치지 않도록 */
  function loadPhrases() {
    var pick = el('drPhrase');
    if (!pick || pick.dataset.loaded) return;
    fetch('/label/api/phrases/?category=all', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = (data && (data.phrases || data.data)) || [];
        if (!list.length) return;
        pick.innerHTML = list.map(function (p, i) {
              return '<option value="' + i + '">' + (p.name || '') + '</option>';
            }).join('');
        pick.dataset.loaded = '1';
        pick.__list = list;
      })
      .catch(function () {});
  }

  function addPhraseRow(text) {
    if (!text) return;
    var body = el('drRows');
    if (!body) return;
    var tr = document.createElement('tr');
    tr.innerHTML = '<td class="dr-panel"></td>' + rowCells(
      { name: '', html: '* ' + text, note: '', key: 'extra:' + Date.now() });
    body.appendChild(tr);
  }

  /* ── 워드로 ──────────────────────────────────────────────────────────── */

  function docHtml() {
    var cell = 'border:1px solid #444;padding:5px 8px;font-size:10pt;'
             + "font-family:'Malgun Gothic',sans-serif;vertical-align:top;";
    var head = cell + 'background:#f2f2f2;font-weight:bold;text-align:center;';
    var got = collect();
    var list = rows();
    var title = (window.checkedFields || {}).prdlst_nm || '';

    /* 창에서 뺀 줄은 의뢰서에도 없어야 한다 */
    var kept = {};
    document.querySelectorAll('#drRows [data-note]').forEach(function (input) {
      kept[input.getAttribute('data-note')] = true;
    });

    var body = '';
    ['main', 'info'].forEach(function (panel) {
      var mine = list.filter(function (row) {
        return row.panel === panel && kept[row.key];
      });
      if (!mine.length) return;
      var name = panel === 'main' ? '주표시면' : '정보표시면';
      var notes = (got.notes[panel] || []).filter(Boolean)
          .map(function (line) { return '<div style="font-size:8.5pt;">' + line + '</div>'; })
          .join('');
      mine.forEach(function (row, i) {
        body += '<tr>'
             + (i === 0 ? '<td style="' + head + '" rowspan="' + mine.length
                          + '"><b>' + name + '</b>' + notes + '</td>' : '')
             + '<td style="' + head + '">' + (row.name || '') + '</td>'
             + '<td style="' + cell + '">' + row.html + '</td>'
             + '<td style="' + cell + '">'
             + (got.marks[row.key] || '') + '</td></tr>';
      });
    });

    // 창에서 손으로 더한 줄(문구함에서 고른 것)도 함께 나간다
    document.querySelectorAll('#drRows tr').forEach(function (tr) {
      var note = tr.querySelector('[data-note^="extra:"]');
      if (!note) return;
      body += '<tr><td style="' + head + '"></td><td style="' + head + '"></td>'
           + '<td style="' + cell + '">' + tr.querySelector('.dr-body').innerHTML
           + '</td><td style="' + cell + '">' + note.value + '</td></tr>';
    });

    /* 워드는 칸 너비를 안 주면 넷으로 똑같이 나눈다. 표시사항 내용에는 원재료명
       300자가 들어가고 표시장소는 이름 한 줄이라, 균등하면 원재료명이 스무 줄로
       접히고 오른쪽은 텅 빈다.

       **픽셀로 적으면 안 된다.** A4 세로에 여백을 빼면 쓸 수 있는 폭이 16 cm
       남짓인데 픽셀 합이 그보다 크면 오른쪽 비고 칸이 종이 밖으로 잘려 나간다.
       실제로 그렇게 났다. 백분율로 적어 폭이 얼마든 안에 들어가게 한다. */
    var cols = '<colgroup><col style="width:12%;"><col style="width:13%;">'
             + '<col style="width:56%;"><col style="width:19%;"></colgroup>';

    return '<html xmlns:w="urn:schemas-microsoft-com:office:word"><head>'
         + '<meta charset="utf-8"><title>표시 디자인 의뢰서</title></head><body>'
         + '<h3 style="margin:0 0 4px;">표시 디자인 의뢰서</h3>'
         + '<p style="margin:0 0 10px;font-size:9pt;color:#555;">'
         + (title ? title + ' · ' : '')
         + new Date().toISOString().slice(0, 10) + '</p>'
         + '<table cellspacing="0" cellpadding="0" '
         + 'style="border-collapse:collapse;table-layout:fixed;width:100%;">'
         + cols
         + '<tr><td style="' + head + '">표시장소</td><td style="' + head + '">표시사항</td>'
         + '<td style="' + head + '">표시사항 내용</td><td style="' + head + '">비고</td></tr>'
         + body + '</table></body></html>';
  }

  function download() {
    var got = collect();
    remember(got.notes);
    var name = String((window.checkedFields || {}).prdlst_nm || '').trim();
    var date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    var file = ('표시디자인의뢰서' + (name ? '_' + name : '') + '_' + date + '.doc')
        .replace(/[<>:"/\\|?*]/g, '_');
    var blob = new Blob(['﻿' + docHtml()],
                        { type: 'application/msword;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = file;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    close();
    if (window.showPreviewToast) {
      window.showPreviewToast('디자인 의뢰서를 저장했습니다. 표 그대로 열립니다.',
                              'success');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var open_btn = el('exportDesignRequestBtn');
    if (open_btn) open_btn.addEventListener('click', function () {
      open();
      loadPhrases();
    });
    var closeBtn = el('drCloseBtn');
    if (closeBtn) closeBtn.addEventListener('click', close);
    var cancel = el('drCancelBtn');
    if (cancel) cancel.addEventListener('click', close);
    var save = el('drDownloadBtn');
    if (save) save.addEventListener('click', download);
    var reset = el('drResetBtn');
    if (reset) reset.addEventListener('click', function () {
      window.DESIGN_REQUEST.notes = (window.DESIGN_REQUEST_DEFAULT_NOTES
                                     || window.DESIGN_REQUEST.notes);
      draw();
    });
    /* 고른 것을 **한꺼번에** 넣는다. 하나씩 넣게 하면 문구가 다섯이면 다섯 번
       같은 일을 한다 */
    var add = el('drAddPhraseBtn');
    if (add) add.addEventListener('click', function () {
      var pick = el('drPhrase');
      var text = el('drPhraseText');
      var added = 0;
      if (pick && pick.__list) {
        Array.prototype.forEach.call(pick.selectedOptions || [], function (opt) {
          var chosen = pick.__list[Number(opt.value)];
          if (chosen) {
            addPhraseRow(chosen.content || chosen.text);
            added += 1;
          }
          opt.selected = false;
        });
      }
      if (!added && text && text.value.trim()) {
        addPhraseRow(text.value.trim());
        text.value = '';
      }
    });

    /* 쓰던 자리에서 문구함에 담는다. 관리 화면까지 가야 담을 수 있으면
       "다음에도 쓰겠다" 싶은 순간을 놓친다. */
    var keep = el('drKeepPhraseBtn');
    if (keep) keep.addEventListener('click', function () {
      var text = el('drPhraseText');
      var content = text ? text.value.trim() : '';
      if (!content) return;
      var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value;
      fetch('/label/api/phrases/save/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
        body: JSON.stringify({ content: content, category: 'additional' })
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (!data || !data.success) return;
        addPhraseRow(content);
        text.value = '';
        var pick = el('drPhrase');
        if (pick) {                       // 담은 것을 목록에도 바로 올린다
          pick.__list = (pick.__list || []).concat([data]);
          var opt = document.createElement('option');
          opt.value = String(pick.__list.length - 1);
          opt.textContent = data.name || content.slice(0, 30);
          pick.appendChild(opt);
        }
      }).catch(function () {});
    });

    /* 줄 빼기 — 창 안에서만 뺀다. 표시사항 자체를 지우는 것이 아니다 */
    var body = el('drRows');
    if (body) body.addEventListener('click', function (event) {
      var btn = event.target.closest('.dr-drop');
      if (!btn) return;
      var tr = btn.closest('tr');
      if (tr) tr.remove();
    });
  });

  window.designRequestRows = rows;          // 시험이 쓴다
  window.designRequestDocHtml = docHtml;    // 시험이 쓴다
})();
