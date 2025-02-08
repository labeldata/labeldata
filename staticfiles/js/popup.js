function openDetailPopup(reportNo) {
    if (!reportNo) {
        alert("유효한 품목제조번호가 없습니다.");
        return;
    }

    const url = `/label/food-item-detail/${reportNo}/`;
    const width = 900;
    const height = 680;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const popup = window.open(
        url,
        "제품 상세 정보",
        `width=${width},height=${height},resizable=yes,scrollbars=yes,top=${top},left=${left}`
    );

    if (!popup || popup.closed || typeof popup.closed === "undefined") {
        alert("팝업이 차단되었습니다. 브라우저 설정을 확인하세요.");
    }
}
