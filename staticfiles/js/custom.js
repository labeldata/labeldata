document.addEventListener('DOMContentLoaded', function () {
    const table = document.getElementById('preview-table');

    new Sortable(table, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        onEnd: function () {
            const order = Array.from(table.querySelectorAll('tr')).map(row => row.dataset.fieldName);

            fetch('/label/save-field-order/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ order }),
            }).then(response => {
                if (response.ok) {
                    alert('순서가 저장되었습니다.');
                } else {
                    alert('순서 저장 실패');
                }
            });
        },
    });
});
