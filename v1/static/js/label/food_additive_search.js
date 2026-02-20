// 이명과 CAS No의 세미콜론과 쉼표를 줄바꿈으로 변환
document.addEventListener('DOMContentLoaded', function() {
    // 이명 처리 (세미콜론으로 줄바꿈)
    document.querySelectorAll('.alias-name-cell span[data-original]').forEach(function(span) {
        const original = span.getAttribute('data-original');
        if (original && original !== '-') {
            span.innerHTML = original.replace(/;\s*/g, ';<br>');
        }
    });
    
    // CAS No 처리 (쉼표와 세미콜론으로 줄바꿈)
    document.querySelectorAll('.cas-no-cell span[data-original]').forEach(function(span) {
        const original = span.getAttribute('data-original');
        if (original && original !== '-') {
            span.innerHTML = original.replace(/[,;]\s*/g, function(match) {
                return match.trim() + '<br>';
            });
        }
    });
});

function toggleAllCheckboxes(source) {
    const checkboxes = document.querySelectorAll('.additive-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = source.checked);
}

function getSelectedAdditives() {
    const selected = [];
    document.querySelectorAll('.additive-checkbox:checked').forEach(checkbox => {
        selected.push({
            name_kr: checkbox.value,
            name_en: checkbox.dataset.nameEn,
            alias_name: checkbox.dataset.aliasName,
            ins_no: checkbox.dataset.insNo,
            e_no: checkbox.dataset.eNo,
            cas_no: checkbox.dataset.casNo,
            main_purpose: checkbox.dataset.mainPurpose
        });
    });
    return selected;
}

function copySelectedToIngredients() {
    const selected = getSelectedAdditives();
    
    if (selected.length === 0) {
        alert('복사할 식품첨가물을 선택해주세요.');
        return;
    }
    
    if (confirm(`선택한 ${selected.length}개의 식품첨가물을 내 원료로 복사하시겠습니까?`)) {
        fetch('/label/copy-additives-to-ingredients/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ additives: selected })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                document.querySelectorAll('.additive-checkbox').forEach(cb => cb.checked = false);
                document.getElementById('check-all').checked = false;
            } else {
                alert('복사 실패: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('복사 중 오류가 발생했습니다.');
        });
    }
}

function requestDataCorrection() {
    const selected = getSelectedAdditives();
    
    if (selected.length === 0) {
        alert('수정 요청할 식품첨가물을 선택해주세요.');
        return;
    }
    
    let html = '';
    selected.forEach((item, index) => {
        html += `
            <div class="card mb-2" id="correction-item-${index}" style="border-left: 4px solid #1a73e8; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                <div class="card-body p-3">
                    <h6 class="mb-2" style="color: #1f1f1f;">${index + 1}. ${item.name_kr}</h6>
                    <div class="row g-2">
                        <div class="col-md-6">
                            <label class="form-label small" style="font-weight: 500; color: #5f6368;">영문명</label>
                            <input type="text" class="form-control form-control-sm correction-field" 
                                   data-name-kr="${item.name_kr}" data-field="name_en" value="${item.name_en || ''}"
                                   style="border: 1px solid #dadce0; border-radius: 4px;">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small" style="font-weight: 500; color: #5f6368;">이명</label>
                            <input type="text" class="form-control form-control-sm correction-field" 
                                   data-name-kr="${item.name_kr}" data-field="alias_name" value="${item.alias_name || ''}"
                                   style="border: 1px solid #dadce0; border-radius: 4px;">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small" style="font-weight: 500; color: #5f6368;">INS No.</label>
                            <input type="text" class="form-control form-control-sm correction-field" 
                                   data-name-kr="${item.name_kr}" data-field="ins_no" value="${item.ins_no || ''}"
                                   style="border: 1px solid #dadce0; border-radius: 4px;">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small" style="font-weight: 500; color: #5f6368;">E No.</label>
                            <input type="text" class="form-control form-control-sm correction-field" 
                                   data-name-kr="${item.name_kr}" data-field="e_no" value="${item.e_no || ''}"
                                   style="border: 1px solid #dadce0; border-radius: 4px;">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small" style="font-weight: 500; color: #5f6368;">CAS No.</label>
                            <input type="text" class="form-control form-control-sm correction-field" 
                                   data-name-kr="${item.name_kr}" data-field="cas_no" value="${item.cas_no || ''}"
                                   style="border: 1px solid #dadce0; border-radius: 4px;">
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    document.getElementById('correctionItemsList').innerHTML = html;
    document.getElementById('correctionReason').value = '';
    
    const modal = new bootstrap.Modal(document.getElementById('correctionModal'));
    modal.show();
}

function submitCorrectionRequest() {
    const reason = document.getElementById('correctionReason').value.trim();
    
    if (!reason) {
        alert('수정 사유 및 근거 자료를 입력해주세요.');
        return;
    }
    
    const corrections = [];
    document.querySelectorAll('.correction-field').forEach(field => {
        const nameKr = field.dataset.nameKr;
        const fieldName = field.dataset.field;
        const value = field.value;
        
        let existing = corrections.find(c => c.name_kr === nameKr);
        if (!existing) {
            existing = { name_kr: nameKr, fields: {} };
            corrections.push(existing);
        }
        existing.fields[fieldName] = value;
    });
    
    fetch('/label/request-additive-correction/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            corrections: corrections,
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            bootstrap.Modal.getInstance(document.getElementById('correctionModal')).hide();
            document.querySelectorAll('.additive-checkbox').forEach(cb => cb.checked = false);
            document.getElementById('check-all').checked = false;
        } else {
            alert('요청 실패: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('요청 중 오류가 발생했습니다.');
    });
}

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
