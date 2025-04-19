document.addEventListener('DOMContentLoaded', function () {
    // ------------------ 팝업 유틸리티 함수 ------------------
    function openPopup(url, name, width = 1100, height = 900) {
      console.log(`팝업 열기 시도: url=${url}, name=${name}, width=${width}, height=${height}`);
      const left = (screen.width - width) / 2;
      const top = (screen.height - height) / 2;
      const popup = window.open(url, name, `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`);
      if (!popup) {
        console.error("Popup blocked by browser");
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단 설정을 확인해 주세요.');
      }
      return popup;
    }
  
    // 미리보기 팝업 설정
    const defaultSettings = {
        layout: 'horizontal',
        fontSize: 10,
        letterSpacing: 5,
        fontStretch: 90,
        dimensions: { width: 27, height: 10 },
        isTableView: true
    };

    // 팝업 열기 함수
    window.openPreviewPopup = function() {
        const form = document.getElementById("labelForm");
        if (!form) {
            console.error("Label form not found");
            return;
        }

        // 폼 데이터 수집
        const formData = new FormData(form);
        const queryParams = new URLSearchParams();

        // 폼 데이터를 URL 파라미터로 변환
        formData.forEach((value, key) => {
            if (value) {
                queryParams.append(key, value);
            }
        });

        // 체크박스 상태 추가
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            if (checkbox.checked) {
                queryParams.append(checkbox.name, "true");
            }
        });

        // URL 설정
        const url = `/label/preview/?${queryParams.toString()}`;
        console.log("Opening preview URL:", url);

        // 팝업 설정
        const width = 1100;
        const height = 900;
        const left = (window.innerWidth - width) / 2;
        const top = (window.innerHeight - height) / 2;

        // 팝업 열기
        const popup = window.open(
            url,
            "previewPopup",
            `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
        );

        if (!popup) {
            alert("팝업이 차단되었습니다. 팝업 차단을 해제해주세요.");
        }
    };

    // 디버깅을 위한 로깅
    console.log("label_preview.js initialized");
});

// DOMContentLoaded 이벤트에서 window에 함수 등록
document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.openPreviewPopup !== 'function') {
        console.error('Preview popup function not loaded properly');
    } else {
        console.log('Preview popup function loaded successfully');
    }
});