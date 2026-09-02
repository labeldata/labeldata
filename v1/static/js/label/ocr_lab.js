/*
 * 판독 고도화 화면 (관리자 전용).
 *
 * 화면이 하는 일은 서버가 이미 정해 둔 것을 보여 주고 되돌려 보내는 것뿐이다.
 * 채점 규칙도, 프롬프트를 켜는 규칙도 전부 서버에 있다 - 여기서 한 번 더
 * 판단하면 두 벌이 되고, 어느 날 한쪽만 고쳐진다.
 *
 * 한 가지만 화면이 책임진다: **켜기 전에 무엇을 켜는지 보여 주는 것.**
 * 자동으로 만든 프롬프트는 켜는 순간 모든 사용자의 판독에 쓰인다.
 */
(function () {
  'use strict';

  var BASE = '/label/ocr-lab/';

  function csrf() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function note(msg, kind) {
    var box = document.getElementById('labNote');
    if (!box) return;
    if (!msg) { box.innerHTML = ''; return; }
    var cls = kind === 'error' ? 'danger' : (kind === 'warn' ? 'warning' : 'success');
    box.innerHTML = '<div class="alert alert-' + cls + ' py-2 px-3" style="font-size:12.5px;">'
      + esc(msg) + '</div>';
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body || {})
    }).then(readJson);
  }

  function postForm(url, form) {
    return fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form })
      .then(readJson);
  }

  function getJson(url) {
    return fetch(url, { credentials: 'same-origin' }).then(readJson);
  }

  // 서버가 무엇을 말했는지 그대로 올린다. "오류가 발생했습니다" 로 뭉개면
  // 무엇을 고쳐야 하는지 아무도 모른다.
  function readJson(res) {
    return res.text().then(function (text) {
      var body;
      try { body = JSON.parse(text); }
      catch (e) { throw new Error('서버 응답 오류 (HTTP ' + res.status + ')'); }
      if (!res.ok || body.success === false) {
        throw new Error(body.error || ('서버 오류 (HTTP ' + res.status + ')'));
      }
      return body;
    });
  }

  function busy(btn, on, label) {
    if (!btn) return;
    if (on) {
      btn.dataset.html = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + (label || '처리 중…');
    } else {
      btn.disabled = false;
      if (btn.dataset.html) btn.innerHTML = btn.dataset.html;
    }
  }

  function modal(id) {
    return bootstrap.Modal.getOrCreateInstance(document.getElementById(id));
  }

  function showLabModal(title, bodyHtml, footerHtml) {
    document.getElementById('labModalTitle').textContent = title;
    document.getElementById('labModalBody').innerHTML = bodyHtml;
    document.getElementById('labModalFooter').innerHTML = footerHtml
      || '<button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">닫기</button>';
    modal('labModal').show();
  }

  // ── ① 정답지 ─────────────────────────────────────────────────────────────

  function createTruth() {
    var btn = document.getElementById('truthCreateBtn');
    var file = document.getElementById('truthImage').files[0];
    if (!file) { note('사진을 골라 주세요.', 'error'); return; }

    var form = new FormData();
    form.append('image', file);
    form.append('name', document.getElementById('truthName').value);
    form.append('report_no', document.getElementById('truthReportNo').value);
    form.append('draft', document.getElementById('truthDraft').checked ? '1' : '0');

    busy(btn, true, '읽는 중…');
    postForm(BASE + 'truth/', form)
      .then(function (body) {
        note(body.warning || '정답지를 만들었습니다.', body.warning ? 'warn' : 'ok');
        addCaseRow(body.case);
        openCase(body.case);
        document.getElementById('truthImage').value = '';
        document.getElementById('truthName').value = '';
        document.getElementById('truthReportNo').value = '';
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }

  function createFromLabel() {
    var btn = document.getElementById('truthFromLabelBtn');
    var labelId = document.getElementById('fromLabelId').value.trim();
    var file = document.getElementById('fromLabelImage').files[0];
    if (!labelId || !file) {
      note('표시사항 번호와 사진을 모두 넣어 주세요.', 'error');
      return;
    }
    var form = new FormData();
    form.append('label_id', labelId);
    form.append('image', file);

    busy(btn, true, '가져오는 중…');
    postForm(BASE + 'truth/from-label/', form)
      .then(function (body) {
        note(body.warning || '정답지를 만들었습니다.', 'warn');
        addCaseRow(body.case);
        openCase(body.case);
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }

  function addCaseRow(c) {
    var tbody = document.getElementById('caseRows');
    var empty = tbody.querySelector('.lab-empty');
    if (empty) tbody.innerHTML = '';
    var tr = document.createElement('tr');
    tr.dataset.case = c.id;
    tr.innerHTML = caseRowHtml(c);
    tbody.insertBefore(tr, tbody.firstChild);
  }

  function caseRowHtml(c) {
    return ''
      + '<td><input type="checkbox" class="form-check-input case-pick"' + (c.verified ? ' checked' : '') + '></td>'
      + '<td><img src="' + esc(c.image_url) + '" class="lab-thumb" alt=""></td>'
      + '<td><div class="fw-semibold">' + esc(c.name) + '</div>'
      + (c.report_no ? '<div class="text-muted" style="font-size:11px;">' + esc(c.report_no) + '</div>' : '')
      + '</td>'
      + '<td><span class="lab-pill">' + esc(c.source) + '</span></td>'
      + '<td class="lab-num">' + c.field_count + '</td>'
      + '<td>' + (c.verified
          ? '<span class="lab-pill lab-pill-on">확인됨</span>'
          : '<span class="lab-pill lab-pill-warn">확인 전</span>') + '</td>'
      + '<td class="text-end">'
      + '  <button type="button" class="btn btn-light v2-btn-sm case-edit">정답 보기</button>'
      + '  <button type="button" class="btn btn-light v2-btn-sm text-danger case-delete">삭제</button>'
      + '</td>';
  }

  var editing = null;
  var boxEditor = null;     // 위치 보정을 켠 적이 없으면 null 이다
  var boxKeys = [];         // 번호 순서 (항목명)
  var boxDetected = {};     // 모델이 말한 자리 (값도 함께 들고 있다)

  // 채점 대상 항목 전체 (서버의 ocr_lab.TRUTH_FIELDS). 화면이 그릴 입력 칸의
  // 기준이다.
  var TRUTH_FIELDS = (function () {
    var el = document.getElementById('truth-fields-data');
    try { return el ? JSON.parse(el.textContent) : []; } catch (e) { return []; }
  })();

  // **값이 없는 항목도 입력 칸을 그린다.**
  //
  // 예전에는 이미 값이 있는 항목만 줄로 그렸다. 그래서 판독이 못 읽었거나
  // 일부러 안 읽은 칸은 줄 자체가 안 생겨, 손으로 채워 넣을 방법이 없었다 -
  // 주의사항·기타표시사항이 정확히 그 경우였고, 그 두 칸이 정답지에 영영
  // 안 쌓이니 정확도도 잴 수 없었다.
  //
  // 목록에 없는 옛 항목도 뒤에 붙인다. 판독은 정답지에 없는 항목도 읽을 수
  // 있고, "정답지에 없는데 여기서 뭔가를 읽었다" 가 곧 오독의 단서다.
  function caseFieldKeys(c) {
    var keys = TRUTH_FIELDS.slice();
    Object.keys(c.expected || {}).forEach(function (k) {
      if (keys.indexOf(k) < 0) keys.push(k);
    });
    Object.keys(c.expected_boxes || {}).forEach(function (k) {
      if (keys.indexOf(k) < 0) keys.push(k);
    });
    return keys;
  }

  function fieldRowHtml(key, index, value) {
    var long = value.length > 40 || value.indexOf('\n') !== -1;
    var control = long
      ? '<textarea class="form-control form-control-sm truth-val" data-key="' + esc(key) + '" rows="'
        + Math.min(10, Math.max(2, Math.ceil(value.length / 60))) + '">' + esc(value) + '</textarea>'
      : '<input type="text" class="form-control form-control-sm truth-val" data-key="' + esc(key)
        + '" value="' + esc(value) + '">';
    return '<div class="truth-key" data-pick="' + esc(key) + '">'
      + '<span class="bx-num">' + (index + 1) + '</span>' + esc(key) + '</div>'
      + '<div>' + control + '</div>';
  }

  function openCase(c) {
    editing = c;
    boxEditor = null;
    boxDetected = {};
    boxKeys = caseFieldKeys(c);

    var rows = boxKeys.map(function (k, i) {
      return fieldRowHtml(k, i, (c.expected || {})[k] || '');
    }).join('');

    var form = ''
      + '<div class="mb-2">'
      + '  <label class="form-label" style="font-size:11.5px;">이름</label>'
      + '  <input type="text" id="caseName" class="form-control form-control-sm" value="' + esc(c.name) + '">'
      + '</div>'
      + '<div class="mb-2">'
      + '  <label class="form-label" style="font-size:11.5px;">품목보고번호 (등록 정보 대조에 씁니다)</label>'
      + '  <input type="text" id="caseReportNo" class="form-control form-control-sm" value="' + esc(c.report_no) + '">'
      + '</div>'
      + '<div class="mb-2">'
      + '  <label class="form-label" style="font-size:11.5px;">읽을 영역 x, y, 너비, 높이 (원본 픽셀 · 비우면 사진 전체)</label>'
      + '  <input type="text" id="caseCrop" class="form-control form-control-sm" value="'
      + esc((c.crop_box || []).join(', ')) + '" placeholder="예: 120, 340, 900, 620">'
      + '</div>'
      + '<div class="form-check mb-3">'
      + '  <input class="form-check-input" type="checkbox" id="caseVerified"' + (c.verified ? ' checked' : '') + '>'
      + '  <label class="form-check-label" for="caseVerified" style="font-size:12.5px;">'
      + '    <strong>정답 확인</strong> — 이 값이 사진과 맞다고 확인했습니다. 켜야 채점에 쓰입니다.'
      + '  </label>'
      + '</div>'
      + '<div id="casePickPanel" class="bx-pick" hidden></div>'
      + '<div class="text-muted mb-2" style="font-size:11.5px; line-height:1.6;">'
      + '  사진을 확대해 가며 값을 고치세요. 라벨에 없는 항목은 비워 두면 채점에서 빠집니다.'
      + '  왼쪽에서 <strong>위치 보정</strong>을 켜면 판독이 어디를 읽었는지 번호로 볼 수 있습니다.'
      + '</div>'
      + '<div class="lab-kv" id="caseFields">'
      + (rows || '<div class="lab-empty" style="grid-column:1/-1;">정답이 비어 있습니다.</div>')
      + '</div>';

    var body = document.getElementById('caseBody');

    // 정답지는 **사진을 보고 손으로 고치는** 것이라 사진이 읽혀야 한다.
    // 표시사항 글씨는 작고, 눕혀 찍힌 사진도 흔하다. 예전에는 폭에 맞춘 <img>
    // 하나였고, 그 크기로는 원재료명 한 줄이 읽히지 않아서 정답지를 만들다
    // 말고 사진 파일을 따로 열어 봐야 했다.
    //
    // 제품 화면의 확인 창이 쓰는 것과 **같은 뷰어**다(회전·확대·이동).
    // 정답을 적을 때와 판독값을 볼 때가 같은 도구여야 눈이 헷갈리지 않는다.
    if (window.photoViewerLayout) {
      window.photoViewerLayout(body, c.image_url, form, c.name);
      mountBoxSide(body, c);
    } else {
      body.innerHTML = ''
        + '<div class="row g-3">'
        + '  <div class="col-lg-5">'
        + '    <img src="' + esc(c.image_url) + '" style="width:100%; border-radius:8px; border:1px solid #dadce0;" alt="">'
        + '  </div>'
        + '  <div class="col-lg-7">' + form + '</div>'
        + '</div>';
    }
    modal('caseModal').show();
  }

  // ── 위치 보정 ────────────────────────────────────────────────────────────
  //
  // 사진 칸을 두 모드로 쓴다. 늘 켜 두지 않는 이유는, 위치를 보려면 판독을
  // 한 번 더 불러야 하고(=돈) 대부분의 정답지 작업에는 필요 없기 때문이다.

  function mountBoxSide(body, c) {
    var slot = body.querySelector('.photo-viewer-slot');
    if (!slot) return;

    slot.insertAdjacentHTML('beforebegin',
      '<div class="bx-tabs">'
      + '  <button type="button" class="btn btn-light v2-btn-sm bx-tab-on" data-mode="photo">사진 보기</button>'
      + '  <button type="button" class="btn btn-light v2-btn-sm" data-mode="boxes">위치 보정</button>'
      + '</div>');
    slot.insertAdjacentHTML('afterend', '<div class="bx-wrap" hidden></div>');

    var tabs = body.querySelector('.bx-tabs');
    var wrap = body.querySelector('.bx-wrap');

    tabs.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-mode]');
      if (!btn) return;
      var boxes = btn.dataset.mode === 'boxes';
      tabs.querySelectorAll('[data-mode]').forEach(function (b) {
        b.classList.toggle('bx-tab-on', b === btn);
      });
      slot.hidden = boxes;
      wrap.hidden = !boxes;
      if (boxes && !boxEditor) buildBoxEditor(wrap, c);
    });
  }

  function buildBoxEditor(wrap, c) {
    if (!window.ocrBoxEditor) {
      wrap.innerHTML = '<div class="lab-empty">위치 편집기를 불러오지 못했습니다.</div>';
      return;
    }
    wrap.innerHTML = ''
      + '<div class="bx-tools">'
      + '  <button type="button" class="btn btn-outline-primary v2-btn-sm" id="bxLocate">'
      + '    <i class="bi bi-crosshair"></i>판독 위치 보기</button>'
      + '  <button type="button" class="btn btn-outline-secondary v2-btn-sm" id="bxAdoptAll">'
      + '    판독 위치 모두 채택</button>'
      + '</div>'
      + '<div class="bx-stage-host"></div>';

    boxEditor = window.ocrBoxEditor.mount(wrap.querySelector('.bx-stage-host'), {
      imageUrl: c.image_url,
      imageSize: c.image_size,
      onSelect: showPickPanel,
      onChange: function (field) { showPickPanel(field); }
    });
    if (!boxEditor) return;
    boxEditor.setOrder(boxKeys);
    boxEditor.setTruth(c.expected_boxes || {});
  }

  // 선택한 항목 하나에 대한 조작만 띄운다. 항목마다 버튼을 늘어놓으면
  // 스물아홉 줄이 버튼 밭이 되고, 정작 값이 안 보인다.
  function showPickPanel(field) {
    var panel = document.getElementById('casePickPanel');
    if (!panel) return;
    if (!field) { panel.hidden = true; return; }

    document.querySelectorAll('#caseFields .truth-key').forEach(function (el) {
      el.classList.toggle('truth-key-on', el.dataset.pick === field);
    });

    var found = boxDetected[field];
    var hasTruth = boxEditor && boxEditor.truthBoxes()[field];
    panel.hidden = false;
    panel.innerHTML = ''
      + '<div class="bx-pick-head"><span class="bx-num">'
      + (boxEditor ? boxEditor.numberOf(field) : '') + '</span>'
      + '<strong>' + esc(field) + '</strong>'
      + '<span class="text-muted" style="font-size:11px;">'
      + (hasTruth ? '정답 위치 있음' : '정답 위치 없음')
      + (found ? ' · 판독은 ' + esc(found.box_from || '사진') + '에서 읽음' : '')
      + '</span></div>'
      + (found && found.value
          ? '<div class="bx-pick-read">판독값 <span>' + esc(found.value) + '</span></div>' : '')
      + '<div class="bx-pick-acts">'
      + (found ? '<button type="button" class="btn btn-light v2-btn-sm" data-bxact="adopt">판독 위치를 정답으로</button>' : '')
      + '<button type="button" class="btn btn-light v2-btn-sm" data-bxact="reread">이 영역만 다시 읽기</button>'
      + (hasTruth ? '<button type="button" class="btn btn-light v2-btn-sm text-danger" data-bxact="clear">위치 지우기</button>' : '')
      + '</div>'
      + '<div class="bx-pick-note" id="bxNote"></div>';
    panel.dataset.field = field;
  }

  function locateBoxes(btn) {
    if (!editing || !boxEditor) return;
    busy(btn, true, '읽는 중…');
    postJson(BASE + 'truth/' + editing.id + '/locate/', {
      model: document.getElementById('runModel').value,
      prompt_version_id: document.getElementById('runPrompt').value || null,
      use_hints: document.getElementById('runHints').checked
    })
      .then(function (body) {
        boxDetected = body.fields || {};
        var boxes = {};
        Object.keys(boxDetected).forEach(function (k) {
          if (boxDetected[k].box) boxes[k] = boxDetected[k].box;
          // 정답지에 없던 항목도 번호를 받아야 상자가 보인다
          if (boxKeys.indexOf(k) < 0 && boxDetected[k].box) boxKeys.push(k);
        });
        boxEditor.setOrder(boxKeys);
        boxEditor.setDetected(boxes);
        note(body.message, body.found ? 'ok' : 'warn');
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }

  function rereadRegion(field, btn) {
    if (!editing || !boxEditor) return;
    var box = boxEditor.boxOf(field);
    if (!box) {
      note('먼저 영역을 그리거나 판독 위치를 채택해 주세요.', 'error');
      return;
    }
    busy(btn, true, '읽는 중…');
    postJson(BASE + 'truth/' + editing.id + '/reread/', {
      field: field,
      box: box,
      model: document.getElementById('runModel').value,
      prompt_version_id: document.getElementById('runPrompt').value || null,
      use_hints: document.getElementById('runHints').checked
    })
      .then(function (body) {
        var out = body.result || {};
        var target = document.querySelector('#caseFields .truth-val[data-key="' + field + '"]');
        var others = Object.keys(out.others || {}).slice(0, 4)
          .map(function (k) { return k + '=' + out.others[k]; }).join(' / ');
        var box = document.getElementById('bxNote');
        if (!box) return;

        // **값을 자동으로 넣지 않는다.** 다시 읽은 값도 판독값이라 틀릴 수 있고,
        // 여기 들어가는 것은 채점의 잣대가 될 정답이다. 사람이 보고 누른다.
        box.innerHTML = out.value
          ? '<div class="bx-read-ok">이 영역에서 <strong>' + esc(out.value) + '</strong> 를 읽었습니다.'
            + ' <button type="button" class="btn btn-outline-primary v2-btn-sm" data-bxact="take"'
            + ' data-value="' + esc(out.value) + '">정답 칸에 넣기</button></div>'
            + (others ? '<div class="text-muted" style="font-size:11px;">함께 읽힌 것: ' + esc(others) + '</div>' : '')
          : '<div class="text-danger">이 영역에서는 그 항목을 읽지 못했습니다.'
            + (others ? ' 대신 읽힌 것: ' + esc(others) : ' 영역을 넓혀 보세요.') + '</div>';
        if (target) target.classList.add('bx-target');
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }

  function saveCase() {
    if (!editing) return;
    var btn = document.getElementById('caseSave');
    var expected = {};
    document.querySelectorAll('#caseBody .truth-val').forEach(function (el) {
      expected[el.dataset.key] = el.value;
    });
    var cropText = document.getElementById('caseCrop').value.trim();
    var crop = cropText
      ? cropText.split(/[,\s]+/).filter(Boolean).map(Number)
      : null;
    if (crop && (crop.length !== 4 || crop.some(isNaN))) {
      note('읽을 영역은 숫자 네 개(x, y, 너비, 높이)여야 합니다.', 'error');
      return;
    }

    var payload = {
      expected: expected,
      name: document.getElementById('caseName').value,
      report_no: document.getElementById('caseReportNo').value,
      crop_box: crop,
      verified: document.getElementById('caseVerified').checked
    };
    // 위치 보정을 연 적이 없으면 위치는 손대지 않는다. 빈 값을 보내면
    // 예전에 적어 둔 정답 위치가 통째로 지워진다.
    if (boxEditor) payload.expected_boxes = boxEditor.truthBoxes();

    busy(btn, true, '저장 중…');
    postJson(BASE + 'truth/' + editing.id + '/save/', payload)
      .then(function (body) {
        var tr = document.querySelector('[data-case="' + body.case.id + '"]');
        if (tr) tr.innerHTML = caseRowHtml(body.case);
        editing = body.case;
        refreshVerifiedCount();
        modal('caseModal').hide();
        note('저장했습니다.', 'ok');
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }


  function refreshVerifiedCount() {
    var n = document.querySelectorAll('#caseRows .lab-pill-on').length;
    var el = document.getElementById('verifiedCount');
    if (el) el.textContent = n;
  }

  // ── ② 측정 ───────────────────────────────────────────────────────────────

  function runBenchmark() {
    var btn = document.getElementById('runBtn');
    var ids = [];
    document.querySelectorAll('#caseRows tr').forEach(function (tr) {
      var pick = tr.querySelector('.case-pick');
      if (pick && pick.checked && tr.dataset.case) ids.push(Number(tr.dataset.case));
    });

    var runs = Number(document.getElementById('runCount').value) || 1;
    busy(btn, true, '읽는 중… 몇 분 걸립니다');
    note('정답지 ' + (ids.length || '전체') + '장을 ' + runs + '회씩 읽습니다. 창을 닫지 마세요.', 'warn');

    postJson(BASE + 'run/', {
      case_ids: ids,
      runs: runs,
      model: document.getElementById('runModel').value,
      prompt_version_id: document.getElementById('runPrompt').value || null,
      use_crop: document.getElementById('runCrop').checked,
      use_api: document.getElementById('runApi').checked,
      use_hints: document.getElementById('runHints').checked,
      use_boxes: document.getElementById('runBoxes').checked,
      layout: document.getElementById('runLayout').value,
      read_freetext: document.getElementById('runFreetext').checked
    })
      .then(function (body) {
        note('평균 ' + body.run.mean_score + '점입니다.', 'ok');
        document.getElementById('runResult').innerHTML = runSummaryHtml(body.run);
        addRunRow(body.run);
      })
      .catch(function (err) { note(err.message, 'error'); })
      .finally(function () { busy(btn, false); });
  }

  function addRunRow(run) {
    var tbody = document.getElementById('runRows');
    var empty = tbody.querySelector('.lab-empty');
    if (empty) tbody.innerHTML = '';
    var tr = document.createElement('tr');
    tr.dataset.run = run.id;
    tr.innerHTML = ''
      + '<td>' + esc(run.created_at) + '</td>'
      + '<td>' + esc(run.prompt) + '</td>'
      + '<td>' + esc(run.model) + '</td>'
      + '<td>' + esc(run.variant) + '</td>'
      + '<td class="lab-num">' + run.case_count + '</td>'
      + '<td class="lab-num">' + run.runs + '</td>'
      + '<td class="lab-num fw-semibold">' + run.mean_score + '</td>'
      + '<td class="text-end"><button type="button" class="btn btn-light v2-btn-sm run-open">자세히</button></td>';
    tbody.insertBefore(tr, tbody.firstChild);
  }

  function fieldTableHtml(fields) {
    if (!fields || !fields.length) return '<div class="lab-empty">채점된 항목이 없습니다.</div>';
    return '<table class="lab-table"><thead><tr>'
      + '<th>항목</th><th class="lab-num">평균</th><th class="lab-num">최저</th>'
      + '<th class="lab-num">최고</th><th class="lab-num">편차</th><th></th>'
      + '</tr></thead><tbody>'
      + fields.map(function (r) {
          var flag = '';
          if (r.mean < 60) flag = '<span class="lab-pill lab-pill-bad">약함</span>';
          else if (r.spread >= 30) flag = '<span class="lab-pill lab-pill-warn">들쭉날쭉</span>';
          return '<tr><td>' + esc(r.field) + '</td>'
            + '<td class="lab-num fw-semibold">' + r.mean + '</td>'
            + '<td class="lab-num">' + r.worst + '</td>'
            + '<td class="lab-num">' + r.best + '</td>'
            + '<td class="lab-num">' + r.spread + '</td>'
            + '<td>' + flag + '</td></tr>';
        }).join('')
      + '</tbody></table>';
  }

  // 위치 점수는 값 점수와 **따로** 보여 준다. 한 숫자로 합치면 "값이 나빠지고
  // 위치가 좋아진" 경우를 알 수 없는데, 그게 정확히 우리가 봐야 하는 것이다.
  function boxSummaryHtml(box) {
    if (!box) return '';
    return '<div class="alert alert-secondary py-2 px-3 mb-2" style="font-size:12.5px;">'
      + '<i class="bi bi-crosshair me-1"></i>읽은 위치: 정답 위치와 평균 <strong>'
      + box.mean + '%</strong> 겹침, <strong>' + box.hit_rate
      + '%</strong> 가 같은 자리를 가리켰습니다 (' + box.graded + '개 항목 채점).'
      + ' 값 점수와 견줘 보세요 — 위치를 물어보느라 값이 내려갔다면 켤 이유가 없습니다.'
      + '</div>';
  }

  function runSummaryHtml(run) {
    var api = run.api_mean
      ? '<div class="alert alert-info py-2 px-3 mb-2" style="font-size:12.5px;">'
        + '품목보고 등록 정보를 대조하면 평균 <strong>' + run.api_mean.mean + '점</strong>'
        + ' (대조 전보다 <strong>' + (run.api_mean.gain >= 0 ? '+' : '') + run.api_mean.gain + '점</strong>).'
        + '</div>'
      : '';
    return ''
      + '<div class="border rounded p-3">'
      + '  <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">'
      + '    <div><strong>평균 ' + run.mean_score + '점</strong>'
      + '      <span class="text-muted" style="font-size:12px;"> · ' + esc(run.prompt)
      + '      · ' + esc(run.model) + ' · ' + esc(run.variant)
      + '      · ' + (run.tiling === 'bands' ? '가로 띠' : '2×2')
      + (run.read_freetext ? ' · 자유문구 포함' : ' · 자유문구 제외')
      + ' · ' + run.runs + '회'
      // 부탁한 회차만큼 못 돈 경우. 분당 토큰 한도(429)에 걸리면 회차가
      // 조용히 줄어드는데, 그러면 편차가 0 으로 나와 "안정적" 으로 읽힌다.
      + (run.runs_asked && run.runs_asked > run.runs
          ? ' <span class="lab-pill lab-pill-warn">' + run.runs_asked
            + '회 요청했으나 ' + run.runs + '회만 성공</span>'
          : '')
      + '</span></div>'
      + '    <button type="button" class="btn btn-outline-primary v2-btn-sm run-suggest" data-run="' + run.id + '">'
      + '      <i class="bi bi-magic"></i>이 결과로 프롬프트 초안 만들기</button>'
      + '  </div>'
      + api
      + boxSummaryHtml(run.box_mean)
      + fieldTableHtml(run.fields)
      + '</div>';
  }

  function openRun(runId) {
    getJson(BASE + 'run/' + runId + '/')
      .then(function (body) {
        var run = body.run;
        var cases = (run.cases || []).map(function (c) {
          var wrong = Object.keys(c.last || {}).filter(function (k) {
            return c.last[k].grade !== 'exact';
          }).map(function (k) {
            var row = c.last[k];
            return '<div class="mb-1"><span class="lab-pill '
              + (row.grade === 'miss' ? 'lab-pill-bad' : 'lab-pill-warn') + '">'
              + esc(k) + ' ' + row.score + '점</span>'
              + '<div style="font-size:11.5px;"><span class="text-muted">정답</span> ' + esc(row.expected) + '</div>'
              + '<div style="font-size:11.5px;"><span class="text-muted">판독</span> ' + esc(row.actual || '(못 읽음)') + '</div>'
              + '</div>';
          }).join('');
          return '<div class="border rounded p-2 mb-2">'
            + '<div class="fw-semibold mb-1" style="font-size:12.5px;">' + esc(c.name)
            + ' <span class="text-muted">평균 ' + c.mean + '점 (' + c.runs + '회)</span></div>'
            + (wrong || '<div class="text-success" style="font-size:12px;">모두 정확히 읽었습니다.</div>')
            + ((c.errors || []).length
                ? '<div class="text-danger" style="font-size:11.5px;">' + esc(c.errors.join(' / ')) + '</div>' : '')
            + '</div>';
        }).join('');

        showLabModal(
          '측정 결과 · 평균 ' + run.mean_score + '점',
          runSummaryHtml(run) + '<div class="mt-3">' + (cases || '') + '</div>');
      })
      .catch(function (err) { note(err.message, 'error'); });
  }

  function suggestPrompt(runId, btn) {
    // 먼저 무엇을 근거로 고치려는지 보여 준다. 근거를 안 보고 초안을 받으면
    // 그 초안을 검토할 기준도 없다.
    getJson(BASE + 'run/' + runId + '/brief/')
      .then(function (body) {
        if (!body.brief) {
          note('고칠 곳을 찾지 못했습니다. 항목 점수가 충분히 높습니다.', 'warn');
          return;
        }
        showLabModal(
          '이 결과로 프롬프트 초안 만들기',
          '<div class="lab-lead">아래를 근거로 프롬프트를 고친 <strong>초안</strong>을 만듭니다. '
          + '초안은 꺼진 채로 저장되고, 내용을 읽고 정확도를 재 본 뒤에 켜야 판독에 쓰입니다.</div>'
          + '<div class="lab-brief">' + esc(body.brief) + '</div>',
          '<button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">취소</button>'
          + '<button type="button" class="btn btn-primary v2-btn-sm" id="suggestGo" data-run="' + runId + '">'
          + '초안 만들기</button>');
      })
      .catch(function (err) { note(err.message, 'error'); });
  }

  function doSuggest(runId, btn) {
    busy(btn, true, '초안을 만드는 중…');
    postJson(BASE + 'run/' + runId + '/suggest/')
      .then(function (body) {
        modal('labModal').hide();
        note(body.message, 'warn');
        window.location.reload();
      })
      .catch(function (err) { busy(btn, false); note(err.message, 'error'); });
  }

  // ── ③ 프롬프트 ───────────────────────────────────────────────────────────

  function openPrompt(versionId) {
    getJson(BASE + 'prompt/' + versionId + '/')
      .then(function (body) {
        var v = body.version;
        var footer = '<button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">닫기</button>';
        if (!v.read_only) {
          footer += '<button type="button" class="btn btn-outline-secondary v2-btn-sm" id="promptSave" data-id="'
            + v.id + '">저장</button>';
          if (!v.active) {
            footer += '<button type="button" class="btn btn-primary v2-btn-sm" id="promptActivate" data-id="'
              + v.id + '">이 판을 사용</button>';
          }
        } else {
          footer += '<button type="button" class="btn btn-primary v2-btn-sm" id="promptSaveNew">'
            + '이 내용으로 새 판 만들기</button>';
        }

        showLabModal(v.name,
          '<div class="mb-2">'
          + '  <label class="form-label" style="font-size:11.5px;">판 이름</label>'
          + '  <input type="text" id="promptName" class="form-control form-control-sm" value="' + esc(v.name) + '">'
          + '</div>'
          + '<div class="mb-2">'
          + '  <label class="form-label" style="font-size:11.5px;">무엇을 왜 바꿨는가</label>'
          + '  <textarea id="promptNote" class="form-control form-control-sm" rows="3">' + esc(v.note || '') + '</textarea>'
          + '</div>'
          + (v.auto_generated
              ? '<div class="alert alert-warning py-2 px-3" style="font-size:12px;">'
                + '자동으로 만든 초안입니다. <strong>내용을 끝까지 읽고</strong> 정확도를 재 본 뒤에 켜세요. '
                + '켜는 순간 모든 사용자의 판독에 쓰입니다.</div>'
              : '')
          + '<label class="form-label" style="font-size:11.5px;">프롬프트 전문</label>'
          + '<textarea id="promptText" class="form-control lab-prompt" rows="26">' + esc(v.prompt) + '</textarea>',
          footer);
      })
      .catch(function (err) { note(err.message, 'error'); });
  }

  function savePrompt(id, btn) {
    busy(btn, true, '저장 중…');
    postJson(BASE + 'prompt/', {
      id: id || null,
      name: document.getElementById('promptName').value,
      note: document.getElementById('promptNote').value,
      prompt: document.getElementById('promptText').value
    })
      .then(function () {
        modal('labModal').hide();
        window.location.reload();
      })
      .catch(function (err) { busy(btn, false); note(err.message, 'error'); });
  }

  function activatePrompt(id, btn) {
    busy(btn, true, '켜는 중…');
    postJson(BASE + 'prompt/' + id + '/activate/')
      .then(function (body) {
        note(body.message, 'ok');
        window.location.reload();
      })
      .catch(function (err) { busy(btn, false); note(err.message, 'error'); });
  }

  // ── 배선 ─────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('truthCreateBtn').addEventListener('click', createTruth);
    document.getElementById('truthFromLabelBtn').addEventListener('click', createFromLabel);
    document.getElementById('caseSave').addEventListener('click', saveCase);
    document.getElementById('runBtn').addEventListener('click', runBenchmark);

    document.getElementById('promptBaseBtn').addEventListener('click', function () {
      openPrompt(0);
    });
    document.getElementById('promptOffBtn').addEventListener('click', function (e) {
      postJson(BASE + 'prompt/deactivate/')
        .then(function (body) { note(body.message, 'ok'); window.location.reload(); })
        .catch(function (err) { note(err.message, 'error'); });
    });

    // 항목 이름을 누르면 그 항목의 상자를 고른다. 사진에서 상자를 눌러도
    // 같은 일이 일어난다 - 어느 쪽에서 시작하든 같은 자리를 가리켜야 한다.
    document.addEventListener('click', function (e) {
      var key = e.target.closest('[data-pick]');
      if (key && boxEditor) boxEditor.select(key.dataset.pick);
    });

    // 목록은 다시 그려지므로 위임으로 받는다
    document.addEventListener('click', function (e) {
      var el = e.target.closest('button');
      if (!el) return;

      if (el.id === 'bxLocate') { locateBoxes(el); return; }
      if (el.id === 'bxAdoptAll') {
        if (!boxEditor) return;
        var n = boxEditor.adoptAll();
        showPickPanel(boxEditor.selected());
        note(n ? n + '개 항목의 판독 위치를 정답 위치로 옮겼습니다. 틀린 상자는 끌어서 고치세요.'
               : '채택할 판독 위치가 없습니다. "판독 위치 보기" 를 먼저 누르세요.',
             n ? 'ok' : 'warn');
        return;
      }
      if (el.dataset.bxact) {
        var field = (document.getElementById('casePickPanel') || {}).dataset;
        field = field ? field.field : '';
        if (!field || !boxEditor) return;
        if (el.dataset.bxact === 'adopt') {
          boxEditor.adopt(field);
          showPickPanel(field);
        } else if (el.dataset.bxact === 'clear') {
          boxEditor.clear(field);
          showPickPanel(field);
        } else if (el.dataset.bxact === 'reread') {
          rereadRegion(field, el);
        } else if (el.dataset.bxact === 'take') {
          var target = document.querySelector(
            '#caseFields .truth-val[data-key="' + field + '"]');
          if (target) {
            target.value = el.dataset.value;
            target.focus();
          }
        }
        return;
      }

      if (el.classList.contains('case-edit')) {
        // 정답 전문은 목록에 없다(원재료명 한 줄이 300자를 넘는다). 열 때 받아 온다.
        getJson(BASE + 'truth/' + el.closest('tr').dataset.case + '/')
          .then(function (body) { openCase(body.case); })
          .catch(function (err) { note(err.message, 'error'); });
        return;
      }
      if (el.classList.contains('case-delete')) {
        var tr = el.closest('tr');
        if (!window.confirm('이 정답지를 지울까요? 되돌릴 수 없습니다.')) return;
        postJson(BASE + 'truth/' + tr.dataset.case + '/delete/')
          .then(function () { tr.remove(); refreshVerifiedCount(); note('지웠습니다.', 'ok'); })
          .catch(function (err) { note(err.message, 'error'); });
        return;
      }
      if (el.classList.contains('run-open')) {
        openRun(el.closest('tr').dataset.run);
        return;
      }
      if (el.classList.contains('run-suggest')) {
        suggestPrompt(el.dataset.run, el);
        return;
      }
      if (el.id === 'suggestGo') {
        doSuggest(el.dataset.run, el);
        return;
      }
      if (el.classList.contains('prompt-open')) {
        openPrompt(el.closest('tr').dataset.prompt);
        return;
      }
      if (el.classList.contains('prompt-on')) {
        activatePrompt(el.closest('tr').dataset.prompt, el);
        return;
      }
      if (el.id === 'promptSave') { savePrompt(Number(el.dataset.id), el); return; }
      if (el.id === 'promptSaveNew') { savePrompt(null, el); return; }
      if (el.id === 'promptActivate') { activatePrompt(el.dataset.id, el); return; }
    });
  });
})();
