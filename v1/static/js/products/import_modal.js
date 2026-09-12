/*
 * "불러오기" — 제품 정보와 원료를 한 화면에서 채운다.
 *
 * 예전에는 입구가 두 탭에 흩어져 있었다. 기본 정보 탭에는 표시사항 사진,
 * 문서함에는 원료 사진. 무엇을 어디서 하는지 보이지 않았다.
 *
 * **두 갈래 중 하나를 고르는 창이다.** 예전에는 번호 칸이 위에 붙어 있기만
 * 해서 사진 올리는 창의 곁다리로 보였고, 번호를 아는 사람도 사진을 올렸다.
 *
 *   ① 품목보고번호로   식약처 등록 정보를 그대로 가져온다.
 *                      **OCR 을 거치지 않아 틀릴 이유가 없고 비용도 없다**
 *   ② 사진·PDF 로      번호를 모를 때. 좌측은 제품으로, 우측은 원료로 등록
 *
 * 수입식품에는 품목제조보고번호가 없다(수입신고번호를 대신 적는다). 그때는
 * ①이 막다른 길이라 창이 그렇게 말해 준다.
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

  /* 두 갈래를 번호로 가른다. 곁다리로 보이면 번호를 아는 사람도 사진을 올린다. */
  (function style() {
    if (document.getElementById('import-way-style')) return;
    var el = document.createElement('style');
    el.id = 'import-way-style';
    el.textContent =
      '.import-step{display:inline-flex;align-items:center;justify-content:center;'
      + 'width:20px;height:20px;border-radius:50%;background:#1a73e8;color:#fff;'
      + 'font-size:11px;font-weight:700;flex-shrink:0;}'
      + '.import-way-first{background:#f6fbf7;border-color:#c8e6c9 !important;}';
    document.head.appendChild(el);
  })();

  var lookupFields = null;   // 조회(또는 후보에서 고르기)로 확정한 품목
  var candidates = [];       // 정확히 맞는 번호가 없을 때 늘어놓은 것들

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
      + '      <div class="text-muted" style="font-size:12px;">사진·PDF 를 끌어다 놓거나 누르세요</div>'
      + '      <div class="text-primary mt-1" style="font-size:11px;">표시사항 부분만 골라내면 더 정확합니다</div>'
      + '      <input type="file" accept="image/*,.pdf" hidden>'
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
      /* 새 제품으로 들어온 사람에게만 보이는 띠.
       *
       * [새로 만들기] 를 누르면 빈 칸 서른 개짜리 기본 정보 탭이 나왔다.
       * 사람은 빈 양식을 받으면 닫는다. 번호로 채우는 길과 사진으로 읽는
       * 길이 **둘 다 이미 있었는데 첫 화면에 안 보였다.**
       *
       * 그래서 새 제품이면 이 창을 먼저 띄운다. 다만 **막지는 않는다** —
       * 번호도 사진도 없는 사람이 갇히면 그게 더 나쁘다. 나가는 문을 크게 단다. */
      + '      <div class="import-start alert alert-light border mb-0 rounded-0 d-none">'
      + '        <div class="d-flex align-items-center gap-2 flex-wrap">'
      + '          <span style="font-size:13px;">'
      + '            <b>새 제품입니다.</b> 번호나 사진이 있으면 표시사항을 한 번에 채울 수 있습니다.'
      + '          </span>'
      + '          <button type="button" class="btn btn-outline-secondary v2-btn-sm ms-auto"'
      + '                  data-bs-dismiss="modal">직접 입력하기</button>'
      + '        </div>'
      + '      </div>'
      + '      <div class="modal-body">'
      + '        <div class="border rounded p-3 mb-3 import-way import-way-first">'
      + '          <div class="d-flex align-items-center gap-2 mb-2">'
      + '            <span class="import-step">1</span>'
      + '            <span class="fw-semibold" style="font-size:13px;">품목보고번호·제품명으로</span>'
      + '            <span class="badge bg-success-subtle text-success-emphasis"'
      + '                  style="font-size:10.5px;">권장 · 정확하고 비용 없음</span>'
      + '          </div>'
      + '          <div class="d-flex gap-2">'
      + '            <input type="text" class="form-control form-control-sm" id="importReportNo"'
      + '                   placeholder="예: 20220460436160 또는 제품명·제조사">'
      + '            <button type="button" class="btn btn-primary v2-btn-sm" id="importLookupBtn">조회</button>'
      + '          </div>'
      + '          <div class="text-muted mt-1" style="font-size:11px;">'
      + '            식약처에 등록된 정보를 그대로 가져옵니다. 판독을 거치지 않아'
      + '            틀릴 이유가 없고, 사진 판독과 달리 비용이 들지 않습니다.'
      + '            번호가 정확하지 않으면 <b>비슷한 품목을 늘어놓아</b> 고르게 합니다.'
      + '          </div>'
      + '          <div class="text-muted mt-1" style="font-size:11px;">'
      + '            <i class="bi bi-info-circle me-1"></i>'
      + '            수입식품에는 품목제조보고번호가 없습니다 — 아래 <b>2</b>로 진행하세요.'
      + '          </div>'
      + '          <div id="importLookupResult" class="mt-2" style="display:none;"></div>'
      + '        </div>'
      + '        <div class="d-flex align-items-center gap-2 mb-2">'
      + '          <span class="import-step">2</span>'
      + '          <span class="fw-semibold" style="font-size:13px;">사진·PDF 로</span>'
      + '          <span class="text-muted" style="font-size:11px;">번호를 모를 때</span>'
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

    // 후보는 innerHTML 로 다시 그려지므로 개별 단추가 아니라 상자에 건다.
    // 사진 판독이 실패해 창을 되살릴 때(clearBusy) 안쪽 handler 는 사라진다.
    var box = modalEl.querySelector('#importLookupResult');
    if (box) box.onclick = function (e) {
      var btn = e.target.closest('.import-cand');
      if (btn) pickCandidate(modalEl, candidates[parseInt(btn.dataset.i, 10)]);
    };
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

  /*
   * 조회 결과 한 건. 이것이 확정되면 두 등록 단추가 열린다.
   *
   * 후보에서 고른 것도 여기로 온다 — 번호를 쳐서 맞힌 것과 고른 것을 다르게
   * 다룰 이유가 없다. 화면 아래의 "조회한 품목보고번호로 등록" 은 그대로 쓴다.
   */
  function showFields(modalEl, fields) {
    lookupFields = fields;
    var box = modalEl.querySelector('#importLookupResult');
    box.style.display = '';
    box.innerHTML =
      '<div class="border rounded bg-light p-2" style="font-size:12px;">'
      + '<div><strong>' + esc(fields.prdlst_nm) + '</strong>'
      + ' <span class="text-muted">' + esc(fields.prdlst_dcnm) + '</span></div>'
      + '<div class="text-muted">' + esc(fields.prdlst_report_no) + '</div>'
      + (fields.bssh_nm
          ? '<div class="text-muted">' + esc(fields.bssh_nm) + '</div>' : '')
      + (fields.rawmtrl_nm
          ? '<div class="mt-1">' + esc(fields.rawmtrl_nm) + '</div>' : '')
      + '</div>';
    setLookupButtons(modalEl, true);
  }

  /*
   * 못 찾았을 때 **비슷한 것을 늘어놓는다.**
   *
   * 예전에는 "등록된 품목을 찾지 못했습니다" 한 줄이 전부였다. 그런데 번호를
   * 못 찾는 흔한 이유는 번호가 없어서가 아니라 한 자리를 잘못 봤거나, 저장된
   * 꼴과 하이픈이 다르거나, 번호 대신 제품명을 쳤기 때문이다. 무엇이 맞는지는
   * 라벨을 든 사람이 안다 — 늘어놓고 고르게 하는 편이 빠르다.
   */
  function showCandidates(modalEl, list) {
    lookupFields = null;
    candidates = list;
    setLookupButtons(modalEl, false);

    var box = modalEl.querySelector('#importLookupResult');
    box.style.display = '';
    box.innerHTML =
      '<div class="text-muted mb-1" style="font-size:11px;">'
      + '비슷한 품목 ' + list.length + '건입니다. 고르면 그 품목으로 등록합니다.'
      + '</div>'
      + '<div class="list-group" style="max-height:220px; overflow:auto;">'
      + list.map(function (f, i) {
          return '<button type="button" class="list-group-item list-group-item-action'
            + ' py-2 import-cand" data-i="' + i + '" style="font-size:12px;">'
            + '<div><strong>' + esc(f.prdlst_nm) + '</strong>'
            + ' <span class="text-muted">' + esc(f.prdlst_dcnm) + '</span></div>'
            + '<div class="text-muted" style="font-size:11px;">'
            + esc(f.prdlst_report_no) + (f.bssh_nm ? ' · ' + esc(f.bssh_nm) : '')
            + '</div>'
            + '</button>';
        }).join('')
      + '</div>';
  }

  function pickCandidate(modalEl, fields) {
    if (!fields) return;
    modalEl.querySelector('#importReportNo').value = fields.prdlst_report_no || '';
    showFields(modalEl, fields);
    note('"' + (fields.prdlst_nm || fields.prdlst_report_no)
         + '" 을(를) 골랐습니다. 아래에서 제품으로 등록할지, 원료로 등록할지 고르세요.',
         'ok');
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
        if (body.success) {
          candidates = [];
          showFields(modalEl, body.fields);
          note('아래에서 제품으로 등록할지, 원료로 등록할지 고르세요.', 'ok');
          return;
        }
        if (body.candidates && body.candidates.length) {
          showCandidates(modalEl, body.candidates);
          note(body.error || '정확히 맞는 번호가 없습니다. 아래에서 골라 주세요.',
               'error');
          return;
        }
        lookupFields = null;
        candidates = [];
        box.style.display = 'none';
        setLookupButtons(modalEl, false);
        note(body.error || '조회하지 못했습니다.', 'error');
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
    if (file.size > (window.MAX_UPLOAD_MB || 30) * 1024 * 1024) {
      note('파일 크기는 ' + (window.MAX_UPLOAD_MB || 30) + 'MB 이하여야 합니다.', 'error');
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

  window.openImportModal = function (opts) {
    var modalEl = ensureModal();
    note('');
    /* 새 제품으로 들어왔는가. 그때만 '직접 입력하기' 띠를 보인다 — 이미
       만들던 제품에서 부른 경우에는 나갈 문이 따로 필요 없다. */
    var strip = modalEl.querySelector('.import-start');
    if (strip) strip.classList.toggle('d-none', !(opts && opts.start));
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  };
})();
