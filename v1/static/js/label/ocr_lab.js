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

  function openCase(c) {
    editing = c;
    var keys = Object.keys(c.expected || {});
    var rows = keys.map(function (k) {
      var v = c.expected[k] || '';
      var long = v.length > 40 || v.indexOf('\n') !== -1;
      var control = long
        ? '<textarea class="form-control form-control-sm truth-val" data-key="' + esc(k) + '" rows="'
          + Math.min(10, Math.max(2, Math.ceil(v.length / 60))) + '">' + esc(v) + '</textarea>'
        : '<input type="text" class="form-control form-control-sm truth-val" data-key="' + esc(k)
          + '" value="' + esc(v) + '">';
      return '<div>' + esc(k) + '</div><div>' + control + '</div>';
    }).join('');

    var html = ''
      + '<div class="row g-3">'
      + '  <div class="col-lg-5">'
      + '    <img src="' + esc(c.image_url) + '" style="width:100%; border-radius:8px; border:1px solid #dadce0;" alt="">'
      + '    <div class="mt-2 text-muted" style="font-size:11.5px; line-height:1.6;">'
      + '      사진을 보며 값을 고치세요. 라벨에 없는 항목은 비워 두면 채점에서 빠집니다.'
      + '    </div>'
      + '  </div>'
      + '  <div class="col-lg-7">'
      + '    <div class="mb-2">'
      + '      <label class="form-label" style="font-size:11.5px;">이름</label>'
      + '      <input type="text" id="caseName" class="form-control form-control-sm" value="' + esc(c.name) + '">'
      + '    </div>'
      + '    <div class="mb-2">'
      + '      <label class="form-label" style="font-size:11.5px;">품목보고번호 (등록 정보 대조에 씁니다)</label>'
      + '      <input type="text" id="caseReportNo" class="form-control form-control-sm" value="' + esc(c.report_no) + '">'
      + '    </div>'
      + '    <div class="mb-2">'
      + '      <label class="form-label" style="font-size:11.5px;">읽을 영역 x, y, 너비, 높이 (원본 픽셀 · 비우면 사진 전체)</label>'
      + '      <input type="text" id="caseCrop" class="form-control form-control-sm" value="'
      + esc((c.crop_box || []).join(', ')) + '" placeholder="예: 120, 340, 900, 620">'
      + '    </div>'
      + '    <div class="form-check mb-3">'
      + '      <input class="form-check-input" type="checkbox" id="caseVerified"' + (c.verified ? ' checked' : '') + '>'
      + '      <label class="form-check-label" for="caseVerified" style="font-size:12.5px;">'
      + '        <strong>정답 확인</strong> — 이 값이 사진과 맞다고 확인했습니다. 켜야 채점에 쓰입니다.'
      + '      </label>'
      + '    </div>'
      + '    <div class="lab-kv">' + (rows || '<div class="lab-empty" style="grid-column:1/-1;">정답이 비어 있습니다.</div>') + '</div>'
      + '  </div>'
      + '</div>';

    document.getElementById('caseBody').innerHTML = html;
    modal('caseModal').show();
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

    busy(btn, true, '저장 중…');
    postJson(BASE + 'truth/' + editing.id + '/save/', {
      expected: expected,
      name: document.getElementById('caseName').value,
      report_no: document.getElementById('caseReportNo').value,
      crop_box: crop,
      verified: document.getElementById('caseVerified').checked
    })
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
      use_hints: document.getElementById('runHints').checked
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
      + '      · ' + esc(run.model) + ' · ' + esc(run.variant) + ' · ' + run.runs + '회</span></div>'
      + '    <button type="button" class="btn btn-outline-primary v2-btn-sm run-suggest" data-run="' + run.id + '">'
      + '      <i class="bi bi-magic"></i>이 결과로 프롬프트 초안 만들기</button>'
      + '  </div>'
      + api
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

    // 목록은 다시 그려지므로 위임으로 받는다
    document.addEventListener('click', function (e) {
      var el = e.target.closest('button');
      if (!el) return;

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
