/*
 * "불러오기" — 제품 정보와 원료를 한 화면에서 채운다.
 *
 * 예전에는 입구가 두 탭에 흩어져 있었다. 기본 정보 탭에는 표시사항 사진,
 * 문서함에는 원료 사진. 무엇을 어디서 하는지 보이지 않았다.
 *
 *   상단        품목보고번호로 조회 (OCR 을 거치지 않아 가장 정확하다)
 *   좌측        제품으로 등록 — 기본 정보 탭을 채우고 원재료를 BOM 으로 쪼갠다
 *   우측        원료로 등록   — 사진은 문서함에 남기고 BOM 원료 1건을 만든다
 *
 * 디자인 시안 대조는 여기 없다. 그것은 값을 채우는 일이 아니라 **확정한 값이
 * 시안과 같은지 보는 일**이라, 표시사항 탭에 있다(_tab_label.html). 한 창에
 * 두면 인쇄 직전에 "채우기" 를 눌러 확정한 값을 시안으로 덮어쓰게 된다.
 *
 * 사진은 끌어다 놓거나 눌러서 고른다.
 *
 * 어느 쪽이든 **바로 저장하지 않는다.** 읽은 값을 확인 창에 늘어놓고, 사용자가
 * 고른 것만 반영한다. OCR 은 틀리고, 틀린 값이 그대로 들어가면 배합비·알레르기·
 * 표시 문구가 전부 그 위에 쌓인다.
 *
 * 실제 채우기·BOM 등록은 basic_info_ocr.js 가 맡는다. 이 파일은 입구다.
 */
(function () {
  'use strict';

  var lookupFields = null;   // 품목보고번호로 조회한 결과

  function csrf() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function labelId() {
    if (typeof PRODUCT_ID !== 'undefined' && PRODUCT_ID) return PRODUCT_ID;
    var m = window.location.pathname.match(/\/products\/(\d+)/);
    return m ? m[1] : '';
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function note(msg, kind) {
    var el = document.getElementById('importModalNote');
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'small ' + (kind === 'error' ? 'text-danger'
                             : kind === 'ok' ? 'text-success' : 'text-muted');
  }

  function dropZone(side, title, desc, hint) {
    return ''
      + '<div class="col-md-6">'
      + '  <div class="import-zone h-100 border rounded p-3 text-center" data-side="' + side + '">'
      + '    <div class="fw-semibold mb-1" style="font-size:14px;">' + title + '</div>'
      + '    <div class="text-muted mb-3" style="font-size:12px; line-height:1.5;">' + desc + '</div>'
      + '    <div class="import-drop border rounded py-4 px-2 mb-2">'
      + '      <i class="bi bi-cloud-arrow-up d-block mb-1" style="font-size:22px; opacity:.5;"></i>'
      + '      <div class="text-muted" style="font-size:12px;">사진을 끌어다 놓거나 누르세요</div>'
      + '      <div class="text-primary mt-1" style="font-size:11px;">표시사항 부분만 골라내면 더 정확합니다</div>'
      + '      <input type="file" accept="image/*" hidden>'
      + '    </div>'
      + '    <button type="button" class="btn btn-outline-secondary v2-btn-sm w-100 import-use-lookup" disabled>'
      + '      조회한 품목보고번호로 등록'
      + '    </button>'
      + '    <div class="text-muted mt-2" style="font-size:11px;">' + hint + '</div>'
      + '  </div>'
      + '</div>';
  }

  function ensureModal() {
    var existing = document.getElementById('importModal');
    if (existing) return existing;

    var wrap = document.createElement('div');
    wrap.innerHTML = ''
      + '<div class="modal fade" id="importModal" tabindex="-1" aria-hidden="true">'
      + '  <div class="modal-dialog modal-lg modal-dialog-scrollable">'
      + '    <div class="modal-content">'
      + '      <div class="modal-header">'
      + '        <h5 class="modal-title" style="font-size:16px;">'
      + '          <i class="bi bi-box-arrow-in-down me-2 text-primary"></i>불러오기'
      + '        </h5>'
      + '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>'
      + '      </div>'
      + '      <div class="modal-body">'
      + '        <div class="border rounded p-3 mb-3">'
      + '          <label class="form-label fw-semibold" style="font-size:13px;">품목보고번호</label>'
      + '          <div class="d-flex gap-2">'
      + '            <input type="text" class="form-control form-control-sm" id="importReportNo"'
      + '                   placeholder="예: 20220460436160" inputmode="numeric">'
      + '            <button type="button" class="btn btn-primary v2-btn-sm" id="importLookupBtn">조회</button>'
      + '          </div>'
      + '          <div class="text-muted mt-1" style="font-size:11px;">'
      + '            식약처에 등록된 정보를 그대로 가져옵니다. 사진을 읽는 것보다 정확합니다.'
      + '          </div>'
      + '          <div id="importLookupResult" class="mt-2" style="display:none;"></div>'
      + '        </div>'
      + '        <div class="row g-3">'
      + dropZone('product', '제품으로 등록',
                 '이 제품의 표시사항입니다.',
                 '기본 정보 탭을 채우고, 원재료명을 원료별로 쪼개 BOM에 등록합니다.')
      + dropZone('ingredient', '원료로 등록',
                 '이 제품에 넣는 원료의 표시사항입니다.',
                 '사진은 문서함에 남기고, BOM에 원료 1건을 만듭니다.')
      + '        </div>'
      + '        <div id="importModalNote" class="small text-muted mt-3"></div>'
      + '      </div>'
      + '    </div>'
      + '  </div>'
      + '</div>';
    document.body.appendChild(wrap.firstChild);

    var modalEl = document.getElementById('importModal');
    wire(modalEl);
    return modalEl;
  }

  function wire(modalEl) {
    modalEl.querySelector('#importLookupBtn').onclick = function () { lookup(modalEl); };
    modalEl.querySelector('#importReportNo').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); lookup(modalEl); }
    });

    modalEl.querySelectorAll('.import-zone').forEach(function (zone) {
      var side = zone.dataset.side;
      var drop = zone.querySelector('.import-drop');
      if (!drop) return;
      var input = drop.querySelector('input[type=file]');

      drop.addEventListener('click', function () { input.click(); });
      input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        input.value = '';
        if (file) handleFile(side, file, modalEl);
      });

      ['dragenter', 'dragover'].forEach(function (ev) {
        drop.addEventListener(ev, function (e) {
          e.preventDefault(); e.stopPropagation();
          drop.classList.add('import-drop-over');
        });
      });
      ['dragleave', 'drop'].forEach(function (ev) {
        drop.addEventListener(ev, function (e) {
          e.preventDefault(); e.stopPropagation();
          drop.classList.remove('import-drop-over');
        });
      });
      drop.addEventListener('drop', function (e) {
        var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) handleFile(side, file, modalEl);
      });

      zone.querySelector('.import-use-lookup').onclick = function () {
        useLookup(side, modalEl);
      };
    });
  }

  function lookup(modalEl) {
    var input = modalEl.querySelector('#importReportNo');
    var value = (input.value || '').trim();
    if (!value) { note('품목보고번호를 입력하세요.', 'error'); return; }

    var btn = modalEl.querySelector('#importLookupBtn');
    btn.disabled = true;
    note('조회 중입니다...');

    fetch('/products/labels/' + labelId() + '/lookup/report-no/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ report_no: value })
    })
      .then(function (res) { return res.json(); })
      .then(function (body) {
        var box = modalEl.querySelector('#importLookupResult');
        if (!body.success) {
          lookupFields = null;
          box.style.display = 'none';
          setLookupButtons(modalEl, false);
          note(body.error || '조회하지 못했습니다.', 'error');
          return;
        }
        lookupFields = body.fields;
        box.style.display = '';
        box.innerHTML =
          '<div class="border rounded bg-light p-2" style="font-size:12px;">'
          + '<div><strong>' + esc(body.fields.prdlst_nm) + '</strong>'
          + ' <span class="text-muted">' + esc(body.fields.prdlst_dcnm) + '</span></div>'
          + (body.fields.bssh_nm
              ? '<div class="text-muted">' + esc(body.fields.bssh_nm) + '</div>' : '')
          + (body.fields.rawmtrl_nm
              ? '<div class="mt-1">' + esc(body.fields.rawmtrl_nm) + '</div>' : '')
          + '</div>';
        setLookupButtons(modalEl, true);
        note('아래에서 제품으로 등록할지, 원료로 등록할지 고르세요.', 'ok');
      })
      .catch(function (err) {
        console.error(err);
        note('조회 중 오류가 발생했습니다.', 'error');
      })
      .finally(function () { btn.disabled = false; });
  }

  function setLookupButtons(modalEl, enabled) {
    modalEl.querySelectorAll('.import-use-lookup').forEach(function (b) {
      b.disabled = !enabled;
    });
  }

  // 읽는 동안 모달을 열어 둔다. 예전에는 파일을 고르는 즉시 닫혀서, 결과가
  // 뜰 때까지 화면에 아무 표시가 없었다 - 눌린 건지 아닌지 알 수 없었다.
  function setBusy(modalEl, message) {
    var body = modalEl.querySelector('.modal-body');
    if (!body) return;
    body.dataset.saved = body.dataset.saved || '';
    if (!body.dataset.saved) {
      body._restore = body.innerHTML;
      body.dataset.saved = '1';
    }
    body.innerHTML =
      '<div class="text-center py-5">'
      + '  <div class="spinner-border text-primary mb-3" role="status">'
      + '    <span class="visually-hidden">읽는 중</span>'
      + '  </div>'
      + '  <div class="fw-semibold" style="font-size:14px;">' + esc(message) + '</div>'
      + '  <div class="text-muted mt-1" style="font-size:12px;">'
      + '    사진의 글자를 읽는 중입니다. 보통 5~15초 걸립니다.'
      + '  </div>'
      + '</div>';
    // 읽는 중에 닫히면 결과를 놓친다
    modalEl.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function (b) {
      b.disabled = true;
    });
  }

  function clearBusy(modalEl) {
    var body = modalEl.querySelector('.modal-body');
    if (body && body.dataset.saved) {
      body.innerHTML = body._restore;
      body.dataset.saved = '';
      wire(modalEl);
      setLookupButtons(modalEl, !!lookupFields);
    }
    modalEl.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function (b) {
      b.disabled = false;
    });
  }

  function handleFile(side, file, modalEl) {
    if (file.size > 10 * 1024 * 1024) {
      note('파일 크기는 10MB 이하여야 합니다.', 'error');
      return;
    }

    // 파일 -> 영역 선택 -> 판독.
    //
    // 판독이 틀리는 가장 큰 이유는 해상도다. 작업지시서처럼 라벨이 사진의
    // 일부이면 라벨 본문이 몇 픽셀로 줄어 읽히지 않는다. 읽을 곳만 잘라 보내면
    // 그 해상도가 전부 라벨에 배정된다.
    //
    // 자르기 창을 취소하면 아무 일도 하지 않는다(불러오기 창은 그대로 둔다).
    if (typeof window.cropPhoto !== 'function') {
      startRead(side, [{ file: file, role: 'whole' }], modalEl, file);
      return;
    }
    window.cropPhoto(file).then(function (parts) {
      if (!parts || !parts.length) return;
      // 영역을 골랐는지 전체를 썼는지 남긴다. 교정 이력에 함께 저장돼야
      // "영역을 고르는 게 나은가" 를 나중에 숫자로 답할 수 있다.
      var cropped = parts.some(function (p) { return p.role !== 'whole'; });
      window.__ocrVariant = cropped ? ('crop' + (parts.length > 1 ? parts.length : '')) : 'whole';
      startRead(side, parts, modalEl, file);
    }).catch(function (err) {
      console.error(err);
      note((err && err.message) || '사진을 열지 못했습니다.', 'error');
    });
  }

  // parts — [{file, role}, ...]. 표시면마다 하나씩이라 여러 장일 수 있다.
  // sourceFile 은 자르기 전 원본. 확인 창에서 값을 대조할 때 쓴다.
  function startRead(side, parts, modalEl, sourceFile) {
    setBusy(modalEl, side === 'compare'
      ? '시안을 읽어 지금 표시사항과 견주는 중입니다…'
      : side === 'product'
        ? '표시사항을 읽는 중입니다…'
        : '사진을 문서함에 저장하고 읽는 중입니다…');

    // 결과 확인 창은 각 처리기가 띄운다. 다 읽고 나서 이 창을 닫아야 두 창이
    // 겹치지 않는다.
    // 원료 등록은 문서함에 사진 한 장을 남기는 흐름이라 여러 장을 받지 않는다.
    // 여러 영역을 골랐으면 첫 영역만 쓴다.
    var run = (side === 'compare')
      ? window.basicInfoOcrCompare(parts, sourceFile)
      : (side === 'product')
        ? window.basicInfoOcrExtract(parts, sourceFile)
        : window.ingredientPhotoUpload(parts[0].file);

    Promise.resolve(run)
      .then(function () {
        bootstrap.Modal.getOrCreateInstance(modalEl).hide();
        clearBusy(modalEl);
      })
      .catch(function (err) {
        // 실패하면 창을 닫지 않는다. 왜 안 됐는지 여기서 보여 주고 다시 시도할 수
        // 있게 한다 - 닫아 버리면 사용자는 처음부터 다시 열어야 한다.
        clearBusy(modalEl);
        note((err && err.message) || '사진을 읽지 못했습니다.', 'error');
      });
  }

  function useLookup(side, modalEl) {
    if (!lookupFields) return;
    bootstrap.Modal.getOrCreateInstance(modalEl).hide();

    if (side === 'product') {
      // 조회 결과를 OCR 과 같은 모양으로 만들어 같은 확인 창을 태운다
      var asOcr = {};
      Object.keys(lookupFields).forEach(function (k) {
        if (lookupFields[k]) asOcr[k] = { value: lookupFields[k], confidence: 'high' };
      });
      window.basicInfoOcrShow(asOcr);
      return;
    }

    // 원료로 등록 — 첨부 파일이 없으니 문서함에는 남기지 않는다. BOM 원료만 만든다.
    window.ingredientFromLookup({
      ingredient_name: lookupFields.prdlst_nm || '',
      food_type: lookupFields.prdlst_dcnm || '',
      sub_ingredients: lookupFields.rawmtrl_nm || '',
      manufacturer: lookupFields.bssh_nm || '',
      report_no: lookupFields.prdlst_report_no || ''
    });
  }

  window.openImportModal = function () {
    var modalEl = ensureModal();
    note('');
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  };
})();
