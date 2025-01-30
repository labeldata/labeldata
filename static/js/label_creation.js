document.addEventListener("DOMContentLoaded", function () {
    const leftPanel = document.querySelector(".left-panel");
    const rightPanel = document.querySelector(".right-panel");
    const dragBar = document.getElementById("drag-bar");

    let isDragging = false;

    // 드래그 시작
    dragBar.addEventListener("mousedown", (e) => {
        isDragging = true;
        document.body.style.cursor = "ew-resize";
    });

    // 드래그 동작
    document.addEventListener("mousemove", (e) => {
        if (!isDragging) return;

        const containerWidth = document.querySelector(".container-fluid").offsetWidth;
        const newLeftWidth = e.clientX / containerWidth * 100;
        const minWidth = 25;
        const maxWidth = 75;

        if (newLeftWidth >= minWidth && newLeftWidth <= maxWidth) {
            leftPanel.style.flex = `0 0 ${newLeftWidth}%`;
            rightPanel.style.flex = `0 0 ${100 - newLeftWidth}%`;
        }
    });

    // 드래그 종료
    document.addEventListener("mouseup", () => {
        isDragging = false;
        document.body.style.cursor = "default";
    });

    // 입력 값 변경 시 미리보기 업데이트
    document.querySelectorAll("input, textarea").forEach((input) => {
        input.addEventListener("input", function () {
            const previewTarget = document.getElementById(`preview-${this.name}`);
            if (previewTarget) {
                previewTarget.textContent = this.value || "-";
            }
        });
    });
});
