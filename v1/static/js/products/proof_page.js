/*
 * 시안 검증 전용 화면.
 *
 * **기능을 새로 만들지 않는다.** 자르기(cropPhoto) · 판독(basicInfoOcrRead) ·
 * 검증(askProofCheck) · 결과 그리기(proofChecksHtml) · 사진 뷰어
 * (photoViewerLayout) 가 전부 이미 있는 것이고, 여기서 하는 일은 그것들을
 * **확인 창이 아니라 화면에** 놓는 것뿐이다.
 *
 * 화면을 가른 까닭은 views.proof_page 의 주석에 있다 — 짧게는, [신규 등록] 과
 * 같은 주소로 떨어져서 사용자가 두 기능을 구별하지 못했고, 검증 결과가 확인 창
 * 안에만 있어 닫으면 돌아갈 자리가 없었다.
 *
 * 읽은 값 표는 여기서 새로 그린다. 확인 창의 표는 체크박스와 고칠 칸이 달려
 * 있는데(반영하려고) 이 화면에서 하는 일은 **보는 것**이라 그게 필요 없다.
 */
(function () {
  'use strict';

  var page = document.querySelector('.proof-page');
  if (!page) return;

  var productId = page.dataset.productId;
  var body = document.getElementById('proofBody');
  var foot = document.getElementById('proofFoot');

  /* 판독기가 주는 칸 이름 → 사람이 읽는 이름.
     **확인 창의 FIELD_MAP 을 쓰지 않는다** — 그쪽은 기본 정보 탭의 입력칸 id 를
     함께 들고 있고, 이 화면에는 그 칸이 없다. 이름만 필요하다. */
  var NAMES = {
    prdlst_nm: '제품명', prdlst_dcnm: '식품유형', content_weight: '내용량',
    weight_calorie: '내용량(열량)', prdlst_report_no: '품목보고번호',
    country_of_origin: '원산지', bssh_nm: '제조원',
    distributor_address: '유통전문판매원', repacker_address: '소분원',
    importer_address: '수입원', storage_method: '보관방법',
    rawmtrl_nm: '원재료명', allergens: '알레르기 유발물질',
    ingredient_info: '특정성분 함량', frmlc_mtrqlt: '포장재질',
    pog_daycnt: '소비기한', cautions: '주의사항', additional_info: '기타 표시사항',
    calories: '열량', natriums: '나트륨', carbohydrates: '탄수화물',
    sugars: '당류', fats: '지방', trans_fats: '트랜스지방',
    saturated_fats: '포화지방', cholesterols: '콜레스테롤', proteins: '단백질'
  };
  var ORDER = Object.keys(NAMES);

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function csrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function readJson(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  /* 판독값을 {칸: {value, confidence}} 꼴로 고른다. 저장해 둔 값은 평평한
     {칸: 값} 으로 오므로(재검증은 사진을 다시 읽지 않는다) 양쪽을 받는다. */
  function valueOf(data, field) {
    var item = data && data[field];
    if (item == null) return '';
    if (typeof item === 'object') {
      return (item.confidence === 'none' || !item.value) ? '' : String(item.value).trim();
    }
    return String(item).trim();
  }

  function readTableHtml(data) {
    var rows = ORDER.filter(function (f) { return valueOf(data, f); });
    if (!rows.length) {
      return '<div class="proof-none">사진에서 읽은 항목이 없습니다. '
           + '표시사항이 선명하게 찍힌 면인지 확인해 주세요.</div>';
    }
    return '<div class="proof-read">'
      + '<div class="proof-read-head">읽은 값 <span>' + rows.length + '개 항목</span></div>'
      + rows.map(function (f) {
          return '<div class="proof-read-row">'
            + '<div class="proof-read-name">' + esc(NAMES[f]) + '</div>'
            + '<div class="proof-read-value">' + esc(valueOf(data, f)) + '</div>'
            + '</div>';
        }).join('')
      + '</div>';
  }

  /* 화면을 그린다. 사진은 파일(방금 올린 것)이거나 주소(저장해 둔 것)다 —
     photoViewerLayout 이 둘 다 받는다. */
  function draw(data, photo, name, checks) {
    var html = readTableHtml(data)
      + '<div id="proofChecks" class="proof-checks"></div>';
    window.photoViewerLayout(body, photo, html, name || '');
    var slot = body.querySelector('#proofChecks');
    if (!slot) return;
    if (checks) {
      slot.innerHTML = window.proofChecksHtml(checks);
      if (!checks.success) {
        slot.innerHTML = '<div class="proof-wait">'
          + esc(checks.message || '규정 검증을 하지 못했습니다.') + '</div>';
      }
      return;
    }
    slot.innerHTML = '<div class="proof-wait">읽은 값이 규정에 맞는지 보는 중…</div>';
    window.askProofCheck(data).then(function (got) {
      slot.innerHTML = got
        ? window.proofChecksHtml(got)
        : '<div class="proof-wait">규정 검증을 하지 못했습니다. 다시 시도해 주세요.</div>';
    });
  }

  /* 제품 이름을 읽은 제품명으로 바꾼다.
     이 화면은 들어올 때 빈 제품을 만드는데, 시안을 붙이면 자동 정리 대상에서
     빠진다(문서가 자식이다). 이름을 안 바꾸면 '임시 - 제품명 - N' 이 목록에
     영구히 남아 쓰레기로 보인다. **사람이 지은 이름은 서버가 덮지 않는다.** */
  function rename(data) {
    var name = valueOf(data, 'prdlst_nm');
    if (!name) return;
    var form = new FormData();
    form.append('name', name);
    form.append('csrfmiddlewaretoken', csrf());
    fetch('/products/proof/' + productId + '/rename/', { method: 'POST', body: form })
      .catch(function (err) { console.debug('이름 바꾸기 실패', err); });
  }

  function busy(message) {
    body.innerHTML = '<div class="proof-wait proof-wait-big">'
      + '<span class="spinner-border spinner-border-sm me-2"></span>'
      + esc(message) + '</div>';
  }

  function pick() {
    var input = document.getElementById('proofFile');
    if (input) input.click();
  }

  ['proofPickBtn', 'proofPickBtn2'].forEach(function (id) {
    var btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', pick);
  });

  var input = document.getElementById('proofFile');
  if (input) {
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      input.value = '';
      if (!file) return;

      /* 영역을 골라 읽으면 훨씬 정확하다. 자르기 창이 있으면 거친다 —
         확인 창이 쓰는 그 길이다. */
      var picked = (typeof window.cropPhoto === 'function')
        ? window.cropPhoto(file)
        : Promise.resolve([{ file: file, role: 'whole' }]);

      picked.then(function (parts) {
        if (!parts || !parts.length) return null;
        busy('시안을 읽는 중입니다…');
        return window.basicInfoOcrRead(parts, file);
      }).then(function (got) {
        if (!got) return;
        foot.hidden = false;
        draw(got.data, got.file || file, file.name, null);
        rename(got.data);
        /* 검증 결과를 그 판에 남긴다 — 다음에 이 화면을 열 때 사진을 다시
           읽지 않는다. 사진은 basicInfoOcrRead 가 이미 문서함에 넣었다. */
        window.askProofCheck(got.data).then(function (checks) {
          var form = new FormData();
          form.append('result', JSON.stringify({ diff: [], same: 0 }));
          form.append('reading', JSON.stringify(got.data));
          form.append('csrfmiddlewaretoken', csrf());
          fetch('/products/labels/' + productId + '/design-compare/',
                { method: 'POST', body: form })
            .catch(function (err) { console.debug('검증 기록 실패', err); });
        });
      }).catch(function (err) {
        console.error(err);
        body.innerHTML = '<div class="proof-none">'
          + esc((err && err.message) || '시안을 읽지 못했습니다.') + '</div>';
      });
    });
  }

  /* 저장해 둔 판독값이 있으면 **판독 없이** 그린다. 무료이고 즉시다. */
  var saved = readJson('proof-saved');
  var image = document.getElementById('proof-image-url');
  if (saved && saved.values && image) {
    draw(saved.values, image.dataset.url, image.dataset.name,
         readJson('proof-checks'));
  }
})();
