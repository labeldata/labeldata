function saveToMyLabel(prdlst_report_no, imported_mode) {
  console.log("saveToMyLabel 호출됨", prdlst_report_no, imported_mode);
  if (!prdlst_report_no) {
    alert("품목보고번호가 누락되었습니다.");
    return;
  }

  const sendRequest = (confirmFlag = false) => {
    const url = `/label/save-to-my-label/${prdlst_report_no}/`;
    // imported_mode와 confirm 플래그를 body에 포함
    const bodyData = JSON.stringify(
      confirmFlag
        ? { confirm: true, imported_mode: imported_mode }
        : { imported_mode: imported_mode }
    );

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
          alert(data.message);
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
    console.log("saveToMyIngredients 호출됨", prdlst_report_no, imported_mode);
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
                alert(data.message || "내원료로 저장되었습니다.");
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

const width = 1000; // 가로 크기
const height = 600; // 세로 크기
const left = (screen.width - width) / 2;
const topPosition = (screen.height - height) / 2; // 'top'을 'topPosition'으로 변경
// const popup = window.open(
//     url,
//     "제품 상세 정보",
//     `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${topPosition},left=${left}`
// );

// 수입식품 상세 팝업 열기 함수 (제품 목록에서 사용)
function openImportedDetailPopup(id) {
    if (!id) {
        alert("수입식품 ID가 없습니다.");
        return;
    }
    // 수입식품 상세는 id(pk)로 접근
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    const url = `/label/food-item-detail/${id}/`;
    window.open(
        url,
        "수입식품 상세 정보",
        `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${top},left=${left}`
    );
}
