/*
 * 표시사항 사진 -> 제품 관리 "기본 정보" 탭 채우기
 *
 * 서버는 표시사항 작성 화면이 쓰던 /label/ocr-extract/ 를 그대로 쓴다. 같은
 * 사진에서 같은 항목을 읽는 일이라 프롬프트를 두 벌로 나눌 이유가 없다.
 *
 * 읽은 값을 바로 넣지 않는다. 항목마다 신뢰도가 다르게 오므로
 *   high  -> 값을 그대로 보여 주고 고칠 수 있게 한다
 *   low   -> 후보 몇 개를 주고 고르게 한다 (직접 입력도 가능)
 *   none  -> 사진에 없는 항목. 목록에서 뺀다
 * 확인 창에서 체크한 항목만 칸에 들어가고, 저장은 평소대로 사용자가 누른다.
 *
 * 이미 값이 있는 칸은 기본으로 체크를 꺼 둔다 — 사진 한 장 때문에 손으로
 * 채워 둔 값이 조용히 사라지면 안 된다.
 */
(function () {
  'use strict';

  // OCR 항목 -> 기본 정보 탭의 입력칸 id
  // weight_calorie 는 이 탭에 칸이 없다(내용량에 함께 적는 항목이라 뺐다).
  // rawmtrl_nm 은 참고용이 아니라 인쇄되는 칸(rawmtrl_nm_display)으로 보낸다.
  var FIELD_MAP = {
    prdlst_nm:           { id: 'field-prdlst-nm',            label: '제품명' },
    prdlst_dcnm:         { id: 'field-prdlst-dcnm',          label: '식품유형(표시용)' },
    content_weight:      { id: 'field-content-weight',       label: '내용량' },
    prdlst_report_no:    { id: 'field-prdlst-report-no',     label: '품목보고번호' },
    country_of_origin:   { id: 'field-country-of-origin',    label: '원산지' },
    bssh_nm:             { id: 'field-bssh-nm',              label: '제조원' },
    distributor_address: { id: 'field-distributor-address',  label: '유통전문판매원' },
    repacker_address:    { id: 'field-repacker-address',     label: '소분원' },
    importer_address:    { id: 'field-importer-address',     label: '수입원' },
    storage_method:      { id: 'field-storage-method',       label: '보관방법' },
    rawmtrl_nm:          { id: 'field-rawmtrl-nm',           label: '원재료명(최종표시)' },
    ingredient_info:     { id: 'field-ingredient-info',      label: '특정성분 함량' },
    frmlc_mtrqlt:        { id: 'field-frmlc-mtrqlt',         label: '포장재질' },
    pog_daycnt:          { id: 'field-pog-daycnt',           label: '소비기한' },
    cautions:            { id: 'field-cautions',             label: '주의사항' },
    additional_info:     { id: 'field-additional-info',      label: '기타 표시사항' }
  };

  // 채운 항목은 "표시 항목" 체크도 켠다. 값만 있고 체크가 꺼져 있으면 인쇄되지
  // 않고 규정 검증에서도 빠져서, 사용자가 채웠다고 여기는 것과 어긋난다.
  function checkboxFor(ocrField) {
    var name = (ocrField === 'rawmtrl_nm') ? 'rawmtrl_nm_display' : ocrField;
    return document.querySelector('.display-item-check[name="chckd_' + name + '"]');
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function status(msg, isError) {
    var el = document.getElementById('basicInfoOcrStatus');
    if (!el) return;
    el.textContent = msg || '';
    el.className = isError ? 'text-danger' : 'text-muted';
    el.style.fontSize = '12px';
  }

  function ensureModal() {
    var existing = document.getElementById('basicInfoOcrModal');
    if (existing) return existing;

    var wrap = document.createElement('div');
    wrap.innerHTML = [
      '<div class="modal fade" id="basicInfoOcrModal" tabindex="-1" aria-hidden="true">',
      '  <div class="modal-dialog modal-lg modal-dialog-scrollable">',
      '    <div class="modal-content">',
      '      <div class="modal-header">',
      '        <h5 class="modal-title" style="font-size:16px;">',
      '          <i class="bi bi-camera me-2 text-primary"></i>사진에서 읽은 항목',
      '        </h5>',
      '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>',
      '      </div>',
      '      <div class="modal-body" id="basicInfoOcrBody"></div>',
      '      <div class="modal-footer">',
      '        <span class="me-auto text-muted" style="font-size:12px;">',
      '          체크한 항목만 채웁니다. 저장은 아래 저장 버튼으로 하세요.',
      '        </span>',
      '        <button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">취소</button>',
      '        <button type="button" class="btn btn-primary v2-btn-sm" id="basicInfoOcrApply">',
      '          <i class="bi bi-check2"></i>선택 항목 채우기',
      '        </button>',
      '      </div>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('basicInfoOcrModal');
  }

  // 값이 긴 항목만 여러 줄로 둔다. 나머지는 한 줄이면 충분한데 예전에는 전부
  // textarea + 테두리 상자였고, 후보는 라디오를 세로로 늘어놓아서 16개 항목이
  // 화면을 몇 번씩 넘겼다. 실제 값보다 칸이 훨씬 컸다.
  function isLongValue(text) {
    return (text || '').length > 40 || (text || '').indexOf('\n') !== -1;
  }

  function rowHtml(field, item, meta) {
    var target = document.getElementById(meta.id);
    var current = target ? (target.value || '').trim() : '';
    var value = item.value || '';
    var isLow = item.confidence !== 'high';
    var candidates = item.candidates || [];
    // 이미 값이 있으면 기본으로 끈다 (덮어쓰기 방지)
    var checked = current ? '' : 'checked';

    var control;
    if (isLow && candidates.length) {
      // 후보는 목록으로. 라디오를 세로로 늘어놓으면 항목 하나가 네 줄을 먹는다.
      control =
        '<select class="form-select form-select-sm ocr-choice">'
        + candidates.map(function (c) {
            return '<option value="' + esc(c) + '">' + esc(c) + '</option>';
          }).join('')
        + '<option value="__direct__">직접 입력…</option>'
        + '</select>'
        + '<input type="text" class="form-control form-control-sm ocr-direct mt-1"'
        + ' placeholder="직접 입력" style="display:none;">';
    } else if (isLongValue(value)) {
      control = '<textarea class="form-control form-control-sm ocr-value" rows="2">'
        + esc(value) + '</textarea>';
    } else {
      control = '<input type="text" class="form-control form-control-sm ocr-value"'
        + ' value="' + esc(value) + '">';
    }

    // 현재 값과 새 값을 나란히 둔다. 무엇이 바뀌는지 눈으로 바로 보여야
    // "이걸 반영할까" 를 판단할 수 있다.
    var same = current && current === value.trim();
    var state, stateClass;
    if (same) {
      state = '같음';
      stateClass = 'ocr-state-same';
    } else if (current) {
      state = '덮어씀';
      stateClass = 'ocr-state-replace';
    } else {
      state = '새로 채움';
      stateClass = 'ocr-state-new';
    }

    return ''
      + '<div class="ocr-row' + (same ? ' ocr-row-same' : '') + '" data-field="' + field + '">'
      + '  <input class="form-check-input ocr-pick" type="checkbox" ' + checked + '>'
      + '  <div class="ocr-label">' + esc(meta.label)
      + (isLow ? ' <span class="ocr-flag ocr-flag-warn" title="읽은 값이 불확실합니다">확인</span>' : '')
      + '  </div>'
      + '  <div class="ocr-current" title="' + esc(current) + '">'
      + (current ? esc(current) : '<span class="ocr-empty">비어 있음</span>')
      + '  </div>'
      + '  <div class="ocr-arrow"><span class="' + stateClass + '">' + state + '</span></div>'
      + '  <div class="ocr-control">' + control + '</div>'
      + '</div>';
  }

  function showModal(data) {
    // 모달을 먼저 만든다. 그 안의 요소를 먼저 찾으면 첫 실행에서 항상 null 이라
    // "Cannot set properties of null" 로 죽는다.
    var modalEl = ensureModal();
    var body = modalEl.querySelector('#basicInfoOcrBody');
    var rows = [];

    Object.keys(FIELD_MAP).forEach(function (field) {
      var item = data[field];
      if (!item || item.confidence === 'none') return;
      if (!item.value && !(item.candidates || []).length) return;
      rows.push(rowHtml(field, item, FIELD_MAP[field]));
    });

    if (!rows.length) {
      body.innerHTML =
        '<div class="text-center text-muted py-4">' +
        '사진에서 읽어낸 항목이 없습니다.<br>' +
        '표시사항이 또렷하게 나온 사진인지 확인해 주세요.</div>';
      modalEl.querySelector('#basicInfoOcrApply').disabled = true;
    } else {
      body.innerHTML =
        '<div class="text-muted mb-2" style="font-size:12px;">'
        + '체크한 항목만 반영합니다. 이미 값이 있는 칸은 덮어쓰지 않도록 체크를 꺼 뒀습니다.'
        + '</div>'
        + '<div class="ocr-table">'
        + '  <div class="ocr-row ocr-head">'
        + '    <div></div><div>항목</div><div>현재 값</div><div></div><div>사진에서 읽은 값</div>'
        + '  </div>'
        + rows.join('')
        + '</div>';
      modalEl.querySelector('#basicInfoOcrApply').disabled = false;

      // "직접 입력…" 을 고르면 입력칸을 연다
      body.querySelectorAll('.ocr-choice').forEach(function (sel) {
        sel.addEventListener('change', function () {
          var direct = sel.parentElement.querySelector('.ocr-direct');
          if (!direct) return;
          var on = sel.value === '__direct__';
          direct.style.display = on ? '' : 'none';
          if (on) direct.focus();
        });
      });
    }

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalEl.querySelector('#basicInfoOcrApply').onclick = function () {
      applySelected();
      modal.hide();
    };
    modal.show();
  }

  function applySelected() {
    var filled = 0;
    document.querySelectorAll('#basicInfoOcrBody .ocr-row').forEach(function (row) {
      if (!row.querySelector('.ocr-pick').checked) return;

      var field = row.dataset.field;
      var meta = FIELD_MAP[field];
      var value = '';

      var direct = row.querySelector('.ocr-value');
      if (direct) {
        value = direct.value.trim();
      } else {
        var choice = row.querySelector('.ocr-choice');
        if (choice) {
          value = choice.value === '__direct__'
            ? (row.querySelector('.ocr-direct').value || '').trim()
            : choice.value;
        }
      }
      if (!value) return;

      var target = document.getElementById(meta.id);
      if (!target) return;
      target.value = value;
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.dispatchEvent(new Event('change', { bubbles: true }));

      var box = checkboxFor(field);
      if (box && !box.disabled) {
        box.checked = true;
        box.dispatchEvent(new Event('change', { bubbles: true }));
      }
      filled += 1;
    });

    status(filled
      ? filled + '개 항목을 채웠습니다. 확인 후 저장하세요.'
      : '채운 항목이 없습니다.');

    // 원재료명을 채웠으면 그 안의 원료들을 BOM 행으로 만들 수 있다.
    // 한 줄짜리 문자열로 두면 배합비 순서 검사·알레르기 수집·표시 문구가
    // 올라갈 자리가 없다.
    var rawmtrl = document.getElementById(FIELD_MAP.rawmtrl_nm.id);
    if (filled && rawmtrl && rawmtrl.value.trim()) {
      offerBomSplit(rawmtrl.value.trim());
    }
  }

  // ── 원재료명 → BOM 원료별 행 ────────────────────────────────────────────
  function labelId() {
    // product_detail.html 이 PRODUCT_ID 전역을 놓아 둔다. URL 에서 캐내는 것보다
    // 확실하다 - 제품 상세는 /products/<id>/ 와 /products/<id>/new/ 두 벌이다.
    if (typeof PRODUCT_ID !== 'undefined' && PRODUCT_ID) return PRODUCT_ID;
    var m = window.location.pathname.match(/\/products\/(\d+)/);
    return m ? m[1] : '';
  }

  function offerBomSplit(text) {
    var id = labelId();
    if (!id) return;

    fetch('/products/labels/' + id + '/rawmtrl-to-bom/preview/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ text: text })
    })
      .then(function (res) { return res.json().catch(function () { return null; }); })
      .then(function (body) {
        if (!body || !body.success || !body.rows.length) return;
        showBomModal(id, body);
      })
      .catch(function (err) { console.error(err); });
  }

  function showBomModal(id, body) {
    var modalEl = ensureBomModal();
    var rows = body.rows.map(function (r, i) {
      var note = r.matched
        ? '<span class="badge bg-success" style="font-size:10px;">기존 원료</span>'
        : (r.candidates.length
            ? '<span class="badge bg-warning text-dark" style="font-size:10px;">신규 (비슷: '
              + esc(r.candidates.join(', ')) + ')</span>'
            : '<span class="badge bg-secondary" style="font-size:10px;">신규</span>');
      return '<tr data-i="' + i + '">'
        + '<td><input type="checkbox" class="form-check-input bom-pick" checked></td>'
        + '<td><input type="text" class="form-control form-control-sm bom-name" value="' + esc(r.name) + '"></td>'
        + '<td style="width:90px;"><input type="text" class="form-control form-control-sm bom-ratio" value="'
        + (r.ratio == null ? '' : r.ratio) + '" placeholder="%"></td>'
        + '<td style="width:110px;"><input type="text" class="form-control form-control-sm bom-origin" value="' + esc(r.origin) + '"></td>'
        + '<td style="font-size:11px;">' + esc(r.sub_ingredients) + '</td>'
        + '<td>' + note + '</td>'
        + '</tr>';
    }).join('');

    modalEl.querySelector('.modal-body').innerHTML =
      '<div class="text-muted mb-2" style="font-size:12px;">'
      + '원재료명에서 원료 ' + body.rows.length + '개를 찾았습니다. '
      + '체크한 것만 BOM에 등록합니다.'
      + (body.allergen_note
          ? ' 알레르기 문구(<strong>' + esc(body.allergen_note) + '</strong>)는 원료가 아니라 제외했습니다.'
          : '')
      + '</div>'
      + (body.existing_bom
          ? '<div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="bomReplace">'
            + '<label class="form-check-label" for="bomReplace" style="font-size:12px;">'
            + '기존 BOM ' + body.existing_bom + '행을 비우고 새로 채우기</label></div>'
          : '')
      + '<div class="table-responsive"><table class="table table-sm align-middle mb-0">'
      + '<thead><tr style="font-size:11px;"><th></th><th>원료명</th><th>배합비</th>'
      + '<th>원산지</th><th>하위 원료</th><th>상태</th></tr></thead>'
      + '<tbody>' + rows + '</tbody></table></div>';

    modalEl.querySelector('#bomApply').onclick = function () { applyBom(id, modalEl); };
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  function ensureBomModal() {
    var existing = document.getElementById('rawmtrlBomModal');
    if (existing) return existing;
    var wrap = document.createElement('div');
    wrap.innerHTML = [
      '<div class="modal fade" id="rawmtrlBomModal" tabindex="-1" aria-hidden="true">',
      '  <div class="modal-dialog modal-xl modal-dialog-scrollable">',
      '    <div class="modal-content">',
      '      <div class="modal-header">',
      '        <h5 class="modal-title" style="font-size:16px;">',
      '          <i class="bi bi-diagram-3 me-2 text-primary"></i>원재료를 BOM에 등록',
      '        </h5>',
      '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>',
      '      </div>',
      '      <div class="modal-body"></div>',
      '      <div class="modal-footer">',
      '        <span class="me-auto text-muted" style="font-size:12px;">',
      '          BOM 탭에서 확인·수정한 뒤 저장하세요.',
      '        </span>',
      '        <button type="button" class="btn btn-light v2-btn-sm" data-bs-dismiss="modal">나중에</button>',
      '        <button type="button" class="btn btn-primary v2-btn-sm" id="bomApply">',
      '          <i class="bi bi-plus-lg"></i>BOM에 등록',
      '        </button>',
      '      </div>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('rawmtrlBomModal');
  }

  function applyBom(id, modalEl) {
    var rows = [];
    modalEl.querySelectorAll('tbody tr').forEach(function (tr) {
      if (!tr.querySelector('.bom-pick').checked) return;
      var ratio = tr.querySelector('.bom-ratio').value.trim();
      rows.push({
        name: tr.querySelector('.bom-name').value.trim(),
        ratio: ratio === '' ? null : parseFloat(ratio),
        origin: tr.querySelector('.bom-origin').value.trim(),
        sub_ingredients: tr.querySelector('td:nth-child(5)').textContent.trim()
      });
    });
    if (!rows.length) {
      alert('등록할 원료를 하나 이상 고르세요.');
      return;
    }

    var replaceEl = modalEl.querySelector('#bomReplace');
    var btn = modalEl.querySelector('#bomApply');
    btn.disabled = true;

    fetch('/products/labels/' + id + '/rawmtrl-to-bom/apply/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ rows: rows, replace: replaceEl ? replaceEl.checked : false })
    })
      .then(function (res) { return res.json(); })
      .then(function (body) {
        if (!body.success) {
          alert(body.error || 'BOM에 등록하지 못했습니다.');
          return;
        }
        bootstrap.Modal.getOrCreateInstance(modalEl).hide();
        status('원료 ' + body.total + '개를 BOM에 등록했습니다 '
             + '(새로 만든 원료 ' + body.created + '개, 기존 원료 연결 '
             + body.matched_existing + '개). BOM 탭에서 확인하세요.');
      })
      .catch(function (err) {
        console.error(err);
        alert('BOM 등록 중 오류가 발생했습니다.');
      })
      .finally(function () { btn.disabled = false; });
  }

  function csrfToken() {
    // 폼 안의 토큰을 먼저 본다. 이 화면은 어차피 csrf_token 을 렌더링한다.
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  // 불러오기 모달이 결과를 기다렸다가 창을 닫을 수 있도록 약속을 돌려준다.
  // 예전에는 파일을 고르는 즉시 모달이 닫혀서, 읽는 동안 화면에 아무 표시가
  // 없었다 - 사용자는 눌린 건지 아닌지 알 수 없었다.
  function extract(file) {
    var btn = document.getElementById('basicInfoOcrBtn');
    var form = new FormData();
    form.append('image', file);
    form.append('csrfmiddlewaretoken', csrfToken());

    if (btn) btn.disabled = true;
    status('사진을 읽는 중입니다...');

    // 응답이 JSON 이 아닐 때(로그인 만료, 500, 프록시 오류 등) 무엇이 왔는지
    // 알려 준다. 예전에는 전부 "오류가 발생했습니다" 한 줄로 삼켜서, 사진 탓인지
    // 서버 탓인지 구분할 수 없었다.
    return fetch('/label/ocr-extract/', { method: 'POST', body: form })
      .then(function (res) {
        return res.text().then(function (text) {
          var result;
          try {
            result = JSON.parse(text);
          } catch (e) {
            // 세션이 끊기면 login_required 가 로그인 화면으로 넘긴다. fetch 가
            // 리다이렉트를 따라가서 HTTP 200 에 HTML 이 온다 — 오류로 안 보인다.
            if (res.redirected || /login/i.test(res.url || '')) {
              throw new Error('로그인이 풀렸습니다. 새로고침 후 다시 시도하세요.');
            }
            var hint = '';
            if (res.status === 403) hint = ' 로그인이 풀렸을 수 있습니다. 새로고침 후 다시 시도하세요.';
            else if (res.status === 413) hint = ' 사진 용량이 너무 큽니다.';
            else if (res.status === 502 || res.status === 504) hint = ' 서버 응답이 너무 늦었습니다.';
            else if (res.status >= 500) hint = ' 서버 오류입니다.';
            console.error('OCR 응답이 JSON 이 아님', res.status, res.url, text.slice(0, 500));
            throw new Error('서버 응답 오류 (HTTP ' + res.status + ').' + hint);
          }
          if (!res.ok) {
            throw new Error(result.error || ('서버 오류 (HTTP ' + res.status + ')'));
          }
          return result;
        });
      })
      .then(function (result) {
        // 응답은 {success, data} 로 감싸여 온다
        if (!result || !result.success) {
          var msg = (result && result.error) || '사진을 읽지 못했습니다.';
          status(msg, true);
          throw new Error(msg);   // 부른 쪽(불러오기 모달)이 알아야 한다
        }
        status('');
        showModal(result.data || {});
      })
      .catch(function (err) {
        console.error(err);
        status(err.message || '사진을 읽는 중 오류가 발생했습니다.', true);
        throw err;
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  // ── 원료로 등록 ────────────────────────────────────────────────────────
  //
  // 사진은 문서함에 남기고(원료 표시사항은 근거 자료다), 읽은 값을 확인 창에
  // 보여 준 뒤 BOM 원료 1건을 만든다. 확인 창은 문서함 탭이 쓰던 것을 그대로
  // 쓴다 - 같은 일을 두 벌로 만들 이유가 없다.
  function ingredientConfirm(fields, onApply, meta) {
    var modalEl = document.getElementById('ingredientPhotoModal');
    if (!modalEl) {
      // 문서함 탭이 없는 화면. 확인 없이 넣지 않고 그만둔다.
      status('원료 확인 창을 찾지 못했습니다. 문서함 탭을 한 번 연 뒤 다시 시도하세요.', true);
      return;
    }
    var rows = [
      ['ingredient_name', '원료명 (BOM 원료명)', true],
      ['sub_ingredients', '원재료명 및 함량 (원재료 표시명)', false],
      ['food_type', '식품유형', false],
      ['manufacturer', '제조사', false],
      ['report_no', '품목보고번호', false],
      ['origin', '원산지', false],
      ['allergens', '알레르기', false]
    ].map(function (f) {
      var value = fields[f[0]] || '';
      // 원재료명은 길다. 나머지는 한 줄이면 충분한데 전부 같은 크기로 두면
      // 짧은 값에도 넓은 칸이 붙어 창이 쓸데없이 길어진다.
      var control = isLongValue(value)
        ? '<textarea class="form-control form-control-sm ing-field" rows="2"'
          + ' data-key="' + f[0] + '">' + esc(value) + '</textarea>'
        : '<input type="text" class="form-control form-control-sm ing-field"'
          + ' data-key="' + f[0] + '" value="' + esc(value) + '">';
      return '<div class="ing-row">'
        + '<label class="ing-label">' + f[1]
        + (f[2] ? ' <span class="text-danger">*</span>' : '') + '</label>'
        + '<div class="ing-control">' + control
        + (value ? '' : '<span class="ocr-empty" style="font-size:11px;">'
                        + '사진에서 읽지 못했습니다</span>')
        + '</div></div>';
    }).join('');

    var head = '<div class="text-muted mb-3" style="font-size:12px;">'
      + (meta && meta.filename
          ? '<strong>' + esc(meta.filename) + '</strong> 을 문서함에 저장했습니다. '
          : '')
      + '읽은 값입니다. 틀린 곳은 고친 뒤 등록하세요. '
      + '함량(%)은 BOM 탭에서 넣으셔야 합니다.</div>';

    if (meta && meta.matched_existing) {
      head += '<div class="alert alert-success py-2 px-3 mb-3" style="font-size:12px;">'
        + '이미 등록된 원료 <strong>' + esc(meta.matched_name) + '</strong> 에 연결합니다'
        + ' (유사도 ' + meta.match_score + ').</div>';
    } else if (meta && meta.candidates && meta.candidates.length) {
      head += '<div class="alert alert-warning py-2 px-3 mb-3" style="font-size:12px;">'
        + '비슷한 원료가 있습니다: ' + esc(meta.candidates.join(', '))
        + ' (유사도 ' + meta.match_score + '). 같은 원료라면 원료명을 그 이름과'
        + ' 똑같이 고쳐 주세요.</div>';
    }

    modalEl.querySelector('.modal-body').innerHTML = head + rows;
    modalEl.querySelector('#ingredientPhotoApply').onclick = function () {
      var edited = {};
      modalEl.querySelectorAll('.ing-field').forEach(function (el) {
        edited[el.dataset.key] = el.value.trim();
      });
      if (!edited.ingredient_name) {
        alert('원료명을 입력하세요.');
        return;
      }
      onApply(edited, modalEl);
    };
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body)
    }).then(function (res) { return res.json(); });
  }

  function finishIngredient(body, modalEl) {
    if (!body.success) {
      alert(body.error || '등록하지 못했습니다.');
      return;
    }
    if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
    status(body.message + ' BOM 탭에서 함량을 넣고 저장하세요.');
  }

  // 사진 -> 문서함 저장 -> 확인 -> BOM
  window.ingredientPhotoUpload = function (file) {
    var form = new FormData();
    form.append('image', file);
    form.append('csrfmiddlewaretoken', csrfToken());
    status('사진을 문서함에 저장하고 읽는 중입니다...');

    return fetch('/products/labels/' + labelId() + '/ingredient-photo/upload/',
                 { method: 'POST', body: form })
      .then(function (res) { return res.json(); })
      .then(function (body) {
        if (!body.success) {
          var msg = body.error || '사진을 읽지 못했습니다.';
          status(msg, true);
          throw new Error(msg);   // 부른 쪽(불러오기 모달)이 알아야 한다
        }
        status('');
        ingredientConfirm(body.fields, function (edited, modalEl) {
          postJson('/products/documents/' + body.document_id + '/ingredient-photo/apply/',
                   { fields: edited })
            .then(function (res) { finishIngredient(res, modalEl); });
        }, body);
      })
      .catch(function (err) {
        console.error(err);
        status(err.message || '사진을 처리하는 중 오류가 발생했습니다.', true);
        throw err;
      });
  };

  // 품목보고번호 -> 확인 -> BOM (첨부 파일이 없으니 문서함에는 남기지 않는다)
  window.ingredientFromLookup = function (fields) {
    ingredientConfirm(fields, function (edited, modalEl) {
      postJson('/products/labels/' + labelId() + '/ingredient/to-bom/',
               { fields: edited })
        .then(function (res) { finishIngredient(res, modalEl); });
    }, null);
  };

  // 불러오기 모달이 부른다
  window.basicInfoOcrExtract = extract;
  window.basicInfoOcrShow = showModal;
})();
