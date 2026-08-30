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

  function rowHtml(field, item, meta) {
    var target = document.getElementById(meta.id);
    var current = target ? (target.value || '').trim() : '';
    var isLow = item.confidence !== 'high';
    var candidates = item.candidates || [];
    // 이미 값이 있으면 기본으로 끈다 (덮어쓰기 방지)
    var checked = current ? '' : 'checked';

    var html = [
      '<div class="border rounded p-2 mb-2 ocr-row" data-field="' + field + '">',
      '  <div class="d-flex align-items-center gap-2 mb-1">',
      '    <input class="form-check-input mt-0 ocr-pick" type="checkbox" ' + checked + '>',
      '    <span class="fw-semibold" style="font-size:13px;">' + esc(meta.label) + '</span>'
    ];
    if (isLow) {
      html.push('    <span class="badge bg-warning text-dark" style="font-size:10px;">확인 필요</span>');
    }
    if (current) {
      html.push('    <span class="badge bg-secondary" style="font-size:10px;">이미 입력됨</span>');
    }
    html.push('  </div>');

    if (current) {
      html.push('  <div class="text-muted mb-1" style="font-size:11px;">현재: ' + esc(current) + '</div>');
    }

    if (isLow && candidates.length) {
      candidates.forEach(function (c, idx) {
        html.push(
          '  <label class="d-flex align-items-center gap-2 mb-1" style="font-size:13px;">' +
          '    <input type="radio" name="ocr_c_' + field + '" value="' + esc(c) + '" ' +
                 (idx === 0 ? 'checked' : '') + '>' + esc(c) +
          '  </label>');
      });
      html.push(
        '  <label class="d-flex align-items-center gap-2" style="font-size:13px;">' +
        '    <input type="radio" name="ocr_c_' + field + '" value="__direct__">' +
        '    <input type="text" class="form-control form-control-sm ocr-direct" placeholder="직접 입력">' +
        '  </label>');
    } else {
      html.push(
        '  <textarea class="form-control form-control-sm ocr-value" rows="' +
        ((item.value || '').length > 60 ? 3 : 1) + '">' + esc(item.value || '') + '</textarea>');
    }

    html.push('</div>');
    return html.join('');
  }

  function showModal(data) {
    var body = document.getElementById('basicInfoOcrBody');
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
      document.getElementById('basicInfoOcrApply').disabled = true;
    } else {
      body.innerHTML =
        '<div class="text-muted mb-2" style="font-size:12px;">' +
        '읽은 값이 맞는지 확인하세요. 이미 입력된 칸은 덮어쓰지 않도록 체크를 꺼 뒀습니다.' +
        '</div>' + rows.join('');
      document.getElementById('basicInfoOcrApply').disabled = false;
    }

    var modalEl = ensureModal();
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    document.getElementById('basicInfoOcrApply').onclick = function () {
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

      var textarea = row.querySelector('.ocr-value');
      if (textarea) {
        value = textarea.value.trim();
      } else {
        var picked = row.querySelector('input[type="radio"]:checked');
        if (picked) {
          value = picked.value === '__direct__'
            ? (row.querySelector('.ocr-direct').value || '').trim()
            : picked.value;
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
  }

  function csrfToken() {
    // 폼 안의 토큰을 먼저 본다. 이 화면은 어차피 csrf_token 을 렌더링한다.
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

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
    fetch('/label/ocr-extract/', { method: 'POST', body: form })
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
          status((result && result.error) || '사진을 읽지 못했습니다.', true);
          return;
        }
        status('');
        showModal(result.data || {});
      })
      .catch(function (err) {
        console.error(err);
        status(err.message || '사진을 읽는 중 오류가 발생했습니다.', true);
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('basicInfoOcrInput');
    if (!input) return;
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) {
        status('파일 크기는 10MB 이하여야 합니다.', true);
        input.value = '';
        return;
      }
      extract(file);
      input.value = '';   // 같은 파일을 다시 골라도 change 가 걸리게
    });
  });
})();
