function saveToMyLabel(prdlst_report_no, imported_mode) {
  if (!prdlst_report_no) {
    alert("품목보고번호가 누락되었습니다.");
    return;
  }

  // 영양성분을 함께 담을지. 체크박스는 같은 품목보고번호의 값이 식약처 DB 에
  // 있을 때만 그려지므로(has_nutrition), 없으면 그냥 끈 것으로 본다.
  const copyNutrition = () => {
    const box = document.getElementById('copyNutrition');
    return !!(box && box.checked);
  };

  const sendRequest = (confirmFlag = false) => {
    const url = `/label/save-to-my-label/${prdlst_report_no}/`;
    // imported_mode와 confirm 플래그를 body에 포함
    const payload = { imported_mode: imported_mode, copy_nutrition: copyNutrition() };
    if (confirmFlag) payload.confirm = true;
    const bodyData = JSON.stringify(payload);

    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute("content"),
        "Content-Type": "application/json"
      },
      body: bodyData
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // 영양성분까지 담았으면 모달이 그 사실을 말해야 한다. 값이 조용히
          // 들어가면 나중에 "내가 넣지 않은 숫자" 가 라벨에 앉아 있게 된다.
          const note = document.getElementById('labelSuccessNutri');
          if (note) {
            if (data.nutrition_copied) {
              note.textContent = '영양성분 ' + data.nutrition_copied
                + '개 항목도 함께 담았습니다 — 식약처에 신고된 값이므로 참고치입니다.';
              note.hidden = false;
            } else {
              note.hidden = true;
            }
          }
          $('#labelSuccessModal').modal('show');
        } else if (data.confirm_required) {
          // 이미 저장된 라벨이 있을 경우
          if (confirm(data.message)) {
            // 사용자가 확인하면 다시 요청
            sendRequest(true);
          } else {
            alert("저장이 취소되었습니다.");
          }
        } else {
          alert("저장 실패: " + (data.error || "알 수 없는 오류"));
        }
      })
      .catch(error => {
        alert("오류 발생: " + error.message);
      });
  };

  // 최초 요청 (confirm 플래그 없이)
  sendRequest();
}

function saveToMyIngredients(prdlst_report_no, imported_mode) {
    if (!prdlst_report_no) {
        alert("품목보고번호가 누락되었습니다.");
        return;
    }

    const sendRequest = (confirmFlag = false) => {
        const url = `/label/save-to-my-ingredients/${prdlst_report_no}/`;
        // imported_mode와 confirm 플래그를 body에 포함
        const bodyData = JSON.stringify(
            confirmFlag
                ? { confirm: true, imported_mode: imported_mode }
                : { imported_mode: imported_mode }
        );

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: bodyData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                $('#successModal').modal('show');
            } else if (data.confirm_required) {
                // 이미 저장된 내원료가 있을 경우
                if (confirm(data.message)) {
                    // 사용자가 확인하면 다시 요청
                    sendRequest(true);
                } else {
                    alert("저장이 취소되었습니다.");
                }
            } else {
                alert("저장 실패: " + (data.error || "알 수 없는 오류"));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('내원료 저장 중 오류가 발생했습니다.');
        });
    };

    // 최초 요청 (confirm 플래그 없이)
    sendRequest();
}

function saveItem(prdlst_report_no) {
    if (!prdlst_report_no) {
        alert("품목보고번호가 누락되었습니다.");
        return;
    }

    fetch(`/label/save-food-item/${prdlst_report_no}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute("content"),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("제품이 성공적으로 저장되었습니다.");
        } else {
            alert(data.error || "저장에 실패했습니다.");
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("저장 중 오류가 발생했습니다.");
    });
}

// CSRF 토큰을 가져오는 함수
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 새 탭에서 URL 열기
function openInNewTab(url) {
  if (window.opener) {
    window.opener.open(url, '_blank');
  } else {
    window.open(url, '_blank');
  }
}

// ── 영양성분 탭 ─────────────────────────────────────────────────────────────
// 탭을 누를 때 한 번만 받는다. 상세를 열 때마다 성분 스무 칸을 함께 싣지 않는다.
(function () {
  var pane = document.getElementById('nutrition-content');
  if (!pane) return;                       // 값이 없는 제품이면 탭 자체가 없다

  var body = document.getElementById('nutriBody');
  var basisEl = document.getElementById('nutriBasis');
  var copyBtn = document.getElementById('nutriCopyBtn');
  var loaded = false;
  var tableText = '';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render(data) {
    if (!data.found) {
      body.innerHTML = '<p class="nutri-empty">' + esc(data.message || '영양성분이 없습니다.') + '</p>';
      return;
    }

    var o = data.origin || {};
    basisEl.textContent = o.basis ? '(' + o.basis + ')' : '';

    var lines = [];
    var html = '<table class="nutri-table"><thead><tr>'
      + '<th>성분</th>'
      + '<th class="nutri-val">표시값</th>'
      + '<th class="nutri-raw">DB 원값</th>'
      + '<th class="nutri-pct" title="1일 영양성분 기준치에 대한 비율">기준치</th>'
      + '</tr></thead><tbody>';
    (data.rows || []).forEach(function (r) {
      // 표시값과 원값을 함께 보인다. 표시값은 규정 반올림을 거친 것이고
      // (계산기와 같은 규칙), 원값은 DB 에 든 그대로다 — 견주려면 둘 다 필요하다.
      html += '<tr class="' + (r.indent ? 'nutri-sub' : '') + (r.copied ? '' : ' nutri-extra') + '">'
        + '<th>' + esc(r.label) + '</th>'
        + '<td class="nutri-val">' + esc(r.display) + '<span class="nutri-unit">' + esc(r.unit) + '</span></td>'
        + '<td class="nutri-raw">' + esc(r.raw) + '</td>'
        + '<td class="nutri-pct">' + (r.percent === null ? '' : esc(r.percent) + '%') + '</td>'
        + '</tr>';
      lines.push(r.label + '\t' + r.raw + '\t' + r.unit);
    });
    html += '</tbody></table>';

    var bits = [];
    if (o.food_nm) bits.push(o.food_nm);
    if (o.maker) bits.push(o.maker);
    if (o.method) bits.push(o.method);
    if (o.year) bits.push(o.year + ' 조사');
    if (o.source) bits.push(o.source);

    html += '<div class="nutri-origin">'
      + '<div class="nutri-origin-line"><i class="bi bi-info-circle"></i> ' + esc(bits.join(' · ')) + '</div>'
      + '<div class="nutri-warn">식약처에 <b>신고된 값</b>입니다. 내 제품의 표시값은 시험성적서나 배합 계산으로 정해야 합니다.</div>'
      + '</div>';

    body.innerHTML = html;

    tableText = (o.basis ? o.basis + '\n' : '') + lines.join('\n');
    copyBtn.hidden = false;
  }

  function load() {
    if (loaded) return;
    loaded = true;                         // 실패해도 다시 두드리지 않는다
    fetch(pane.getAttribute('data-url'), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {
        loaded = false;                    // 네트워크 문제는 다시 눌러 볼 수 있어야 한다
        body.innerHTML = '<p class="nutri-empty">영양성분을 불러오지 못했습니다. 탭을 다시 눌러 주세요.</p>';
      });
  }

  var tabBtn = document.getElementById('nutrition-tab');
  if (tabBtn) {
    // Bootstrap 4 는 탭이 실제로 보인 뒤에 이 이벤트를 준다
    $(tabBtn).on('shown.bs.tab', load);
  }

  copyBtn.addEventListener('click', function () {
    if (!tableText) return;
    // 붙여넣을 곳이 엑셀·계산기라 탭으로 나눈 평문이 가장 쓸모 있다
    navigator.clipboard.writeText(tableText).then(function () {
      copyBtn.innerHTML = '<i class="bi bi-check-lg"></i> 복사됨';
      setTimeout(function () {
        copyBtn.innerHTML = '<i class="bi bi-clipboard"></i> 표 복사';
      }, 1500);
    }).catch(function () {
      alert('복사하지 못했습니다. 표를 직접 선택해 복사해 주세요.');
    });
  });
})();

document.addEventListener('DOMContentLoaded', function() {
  // 내원료 이동 버튼 클릭 시 새 탭으로 열기
  document.getElementById('goToIngredientBtn').addEventListener('click', function() {
    openInNewTab('/label/my-ingredient-list-combined/');
    $('#successModal').modal('hide');
  });

  // 표시사항 이동 버튼 클릭 시 새 탭으로 열기
  document.getElementById('goToLabelBtn').addEventListener('click', function() {
    openInNewTab('/label/my-labels/');
    $('#labelSuccessModal').modal('hide');
  });
});


