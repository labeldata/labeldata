document.addEventListener("DOMContentLoaded", function () {
    const resizableContainer = document.querySelector(".container");
    const inputSection = document.getElementById("input-section");
    const previewSection = document.getElementById("preview-section");
    const dragBar = document.getElementById("drag-bar");

    let isDragging = false;

    // Drag and drop for preview list
    const draggableList = document.getElementById("draggable-list");
    new Sortable(draggableList, {
        animation: 150,
        handle: "tr", // Enable dragging table rows
        onStart: function (evt) {
            evt.item.classList.add("dragging");
        },
        onEnd: function (evt) {
            evt.item.classList.remove("dragging");
        },
    });

    // Handle drag-bar movement
    dragBar.addEventListener("mousedown", () => {
        isDragging = true;
        document.body.style.cursor = "ew-resize";
    });

    document.addEventListener("mousemove", (e) => {
        if (!isDragging) return;

        const containerRect = resizableContainer.getBoundingClientRect();
        const dragPosition = e.clientX - containerRect.left;

        const minWidth = containerRect.width * 0.25;
        const maxWidth = containerRect.width * 0.75;

        if (dragPosition >= minWidth && dragPosition <= maxWidth) {
            inputSection.style.flex = `0 0 ${dragPosition}px`;
            previewSection.style.flex = `0 0 ${containerRect.width - dragPosition - dragBar.offsetWidth}px`;
        }
    });

    document.addEventListener("mouseup", () => {
        isDragging = false;
        document.body.style.cursor = "default";
    });

    // Apply text styles
    document.getElementById("apply-text").addEventListener("click", function () {
        const fontSize = document.getElementById("font-size").value + "px";
        const letterSpacing = document.getElementById("letter-spacing").value + "%";
        const lineHeight = document.getElementById("line-height").value + "%";

        document.querySelectorAll("#draggable-list td").forEach((cell) => {
            cell.style.fontSize = fontSize;
            cell.style.letterSpacing = letterSpacing;
            cell.style.lineHeight = lineHeight;
        });
    });

    // Sync input fields with preview
    document.querySelectorAll(".form-control").forEach((input) => {
        input.addEventListener("input", function () {
            const fieldName = input.getAttribute("name");
            const previewElement = document.querySelector(`#draggable-list span[name="${fieldName}"]`);
            if (previewElement) {
                previewElement.textContent = input.value;
            }
        });
    });
});