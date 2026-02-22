// ==================== 스마트 업로드 모달 관련 함수 ====================

let selectedFile = null;
let targetSlotId = null;
let lastSlotContext = null;

// 모달 열기
function openUploadModal(slotId, docTypeName, docTypeId) {
    const modal = new bootstrap.Modal(document.getElementById('smartUploadModal'));
    targetSlotId = slotId;
    
    // 초기화 (문서 종류 선택보다 먼저 수행)
    resetUploadForm();
    document.getElementById('target-slot-id').value = slotId || '';
    
    const typeSelect = document.getElementById('document-type-select');
    if (slotId && docTypeId) {
        lastSlotContext = {
            slotId: slotId,
            docTypeId: docTypeId,
            docTypeName: docTypeName
        };
        window.lastUploadSlotContext = lastSlotContext;
        // 슬롯에서 열림 - 문서 종류 자동 선택
        document.getElementById('upload-modal-title').textContent = docTypeName + ' 등록/갱신';
        typeSelect.value = docTypeId;
        typeSelect.dispatchEvent(new Event('change'));
        typeSelect.disabled = true;
    } else {
        lastSlotContext = null;
        window.lastUploadSlotContext = null;
        // 일반 업로드 버튼에서 열림
        document.getElementById('upload-modal-title').textContent = '일반 문서 등록';
        typeSelect.disabled = false;
        typeSelect.value = '';
    }
    
    modal.show();
}

// 폼 초기화
function resetUploadForm() {
    selectedFile = null;
    document.getElementById('smart-upload-form').reset();
    document.getElementById('selected-file-info').style.display = 'none';
    document.getElementById('custom-expiry-input').style.display = 'none';
    document.getElementById('calculated-expiry').style.display = 'none';
    const customExpiryInput = document.getElementById('custom-expiry-date');
    if (customExpiryInput) {
        customExpiryInput.value = '';
    }
    const unlimitedRadio = document.getElementById('expiry-unlimited');
    if (unlimitedRadio) {
        unlimitedRadio.checked = true;
        unlimitedRadio.dispatchEvent(new Event('change'));
    }
}

// 파일 선택 버튼
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('document-upload-input');
    const selectFileBtn = document.getElementById('select-file-btn');
    const dropzone = document.getElementById('upload-dropzone');
    const removeFileBtn = document.getElementById('remove-file-btn');
    
    if (selectFileBtn) {
        selectFileBtn.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    if (dropzone) {
        dropzone.addEventListener('click', function() {
            if (!selectedFile) {
                fileInput.click();
            }
        });
        
        dropzone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('dragover');
        });
        
        dropzone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('dragover');
        });
        
        dropzone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            if (this.files.length > 0) {
                handleFileSelect(this.files[0]);
            }
        });
    }
    
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            selectedFile = null;
            fileInput.value = '';
            document.getElementById('selected-file-info').style.display = 'none';
        });
    }
    
    // 문서 종류 선택 시 유효기간 자동 설정
    const typeSelect = document.getElementById('document-type-select');
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            const selectedExpiry = document.querySelector('input[name="expiry-option"]:checked');
            if (selectedExpiry) {
                return;
            }
            const selected = this.options[this.selectedIndex];
            const validityDays = selected.getAttribute('data-validity');
            
            if (validityDays !== null && validityDays !== '') {
                const days = parseInt(validityDays);
                if (days === 0) {
                    document.getElementById('expiry-unlimited').checked = true;
                } else if (days === 180) {
                    document.getElementById('expiry-6m').checked = true;
                } else if (days === 365) {
                    document.getElementById('expiry-1y').checked = true;
                } else if (days === 730) {
                    document.getElementById('expiry-2y').checked = true;
                } else {
                    document.getElementById('expiry-custom').checked = true;
                }
                
                document.querySelectorAll('input[name="expiry-option"]').forEach(radio => {
                    if (radio.checked) {
                        radio.dispatchEvent(new Event('change'));
                    }
                });
            }
        });
    }
    
    // 유효기간 라디오 버튼 변경 시
    document.querySelectorAll('input[name="expiry-option"]').forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'custom') {
                document.getElementById('custom-expiry-input').style.display = 'block';
                document.getElementById('calculated-expiry').style.display = 'none';
            } else {
                document.getElementById('custom-expiry-input').style.display = 'none';
                
                const days = parseInt(this.value);
                if (days === 0) {
                    document.getElementById('calculated-expiry').style.display = 'block';
                    document.getElementById('calculated-expiry-text').textContent = '무기한';
                } else {
                    const expiryDate = new Date();
                    expiryDate.setDate(expiryDate.getDate() + days);
                    
                    document.getElementById('calculated-expiry').style.display = 'block';
                    document.getElementById('calculated-expiry-text').textContent = expiryDate.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                }
            }
        });
    });
    
    // 폼 제출
    const uploadForm = document.getElementById('smart-upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // 업로드 권한 체크 (서버와 클라이언트 이중 보호)
            if (typeof CAN_UPLOAD_DOCUMENTS !== 'undefined' && !CAN_UPLOAD_DOCUMENTS) {
                showSnackbar('문서 업로드 권한이 없습니다. 파일 업로드는 오너, 편집자, 자료 제출자만 가능합니다.', 'warning');
                return;
            }

            if (!selectedFile) {
                showSnackbar('파일을 선택해주세요.', 'warning');
                return;
            }
            
            const typeSelect = document.getElementById('document-type-select');
            const slotIdValue = document.getElementById('target-slot-id').value;
            if (!slotIdValue && !typeSelect.value) {
                showSnackbar('문서 종류를 선택해주세요.', 'warning');
                return;
            }
            
            await handleSmartUpload();
        });
    }
});

// 파일 선택 처리
function handleFileSelect(file) {
    selectedFile = file;
    
    // 파일 정보 표시
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const fileIcon = document.getElementById('file-icon');
    
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    // 아이콘 설정
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext === 'pdf') {
        fileIcon.className = 'bi bi-file-earmark-pdf text-danger me-3';
    } else if (['jpg', 'jpeg', 'png', 'gif'].includes(ext)) {
        fileIcon.className = 'bi bi-file-earmark-image text-info me-3';
    } else if (['doc', 'docx'].includes(ext)) {
        fileIcon.className = 'bi bi-file-earmark-word text-primary me-3';
    } else if (['xls', 'xlsx'].includes(ext)) {
        fileIcon.className = 'bi bi-file-earmark-excel text-success me-3';
    } else {
        fileIcon.className = 'bi bi-file-earmark text-secondary me-3';
    }
    
    fileIcon.style.fontSize = '32px';
    
    document.getElementById('selected-file-info').style.display = 'block';
}

// 파일 크기 포맷
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// 스마트 업로드 처리
async function handleSmartUpload() {
    const submitBtn = document.getElementById('upload-submit-btn');
    const typeSelectValue = document.getElementById('document-type-select').value;
    const slotIdValue = document.getElementById('target-slot-id').value;
    const fileInput = document.getElementById('document-upload-input');
    if (!selectedFile && fileInput && fileInput.files && fileInput.files.length > 0) {
        selectedFile = fileInput.files[0];
    }
    
    // 유효성 검사
    if (!selectedFile) {
        showSnackbar('파일을 선택해주세요.', 'warning');
        return;
    }
    
    if (!slotIdValue && !typeSelectValue) {
        showSnackbar('문서 종류를 선택해주세요.', 'warning');
        return;
    }
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>업로드 중...';
    
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('document_type', typeSelectValue);
        formData.append('slot_id', slotIdValue || '');
        
        // 유효기간 계산
        const expiryOption = document.querySelector('input[name="expiry-option"]:checked');
        let expiryUnlimited = false;
        if (expiryOption) {
            if (expiryOption.value === 'custom') {
                const customDate = document.getElementById('custom-expiry-date').value;
                if (customDate) {
                    formData.append('expiry_date', customDate);
                }
            } else {
                const days = parseInt(expiryOption.value);
                if (days === 0) {
                    expiryUnlimited = true;
                } else if (days > 0) {
                    const expiryDate = new Date();
                    expiryDate.setDate(expiryDate.getDate() + days);
                    const expiryDateStr = expiryDate.toISOString().split('T')[0];
                    formData.append('expiry_date', expiryDateStr);
                }
            }
        } else {
            expiryUnlimited = true;
        }

        if (expiryUnlimited) {
            formData.append('expiry_unlimited', 'true');
        }
        
        // 알림 설정
        const notificationEnabled = document.getElementById('enable-notification').checked;
        formData.append('notification_enabled', notificationEnabled);
        
        const csrftoken = getCsrfToken();
        // data-label-id 속성에서 labelId 읽기
        const labelId = parseInt(document.getElementById('smartUploadModal').getAttribute('data-label-id'));
        const uploadUrl = `/products/documents/api/upload/${labelId}/`;
        
        const response = await fetch(uploadUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // 모달 닫기
            const modalElement = document.getElementById('smartUploadModal');
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
            
            // 성공 메시지 + 문서함 탭 복원 후 새로고침
            showSnackbar(data.message || '문서가 성공적으로 등록되었습니다.', 'success');
            sessionStorage.setItem('returnToTab', 'docs');
            window.location.reload();
        } else {
            const error = await response.json();
            showSnackbar('업로드 실패: ' + (error.error || '알 수 없는 오류'), 'error');
        }
    } catch (error) {
        console.error('[handleSmartUpload] Exception:', error);
        showSnackbar('업로드 중 오류가 발생했습니다: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-upload me-1"></i>등록';
    }
}

// ==================== 슬롯 필터링 ====================

function filterSlotsByStatus(status) {
    const slots = document.querySelectorAll('.slot-card');
    
    // 버튼 활성화 상태 변경
    document.querySelectorAll('.btn-group button').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    slots.forEach(slot => {
        if (status === 'ALL') {
            slot.style.display = '';
        } else {
            const slotStatus = slot.getAttribute('data-status');
            if (slotStatus === status) {
                slot.style.display = '';
            } else {
                slot.style.display = 'none';
            }
        }
    });
}

// 문서 검색
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('doc-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            document.querySelectorAll('.document-row').forEach(row => {
                const filename = row.getAttribute('data-filename').toLowerCase();
                if (filename.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
});

// 슬롯 숨김/표시 토글
function toggleSlotVisibility(slotId) {
    const slotCard = document.querySelector(`[data-slot-id="${slotId}"]`);
    if (!slotCard) return;
    
    const isHidden = slotCard.dataset.hidden === 'true';
    
    if (confirm(isHidden ? '이 슬롯을 다시 표시하시겠습니까?' : '이 제품에는 해당 문서가 필요 없습니까?\n(숨긴 슬롯은 준수율 계산에서 제외됩니다)')) {
        fetch(`/products/slots/${slotId}/toggle-visibility/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                sessionStorage.setItem('returnToTab', 'docs');
                location.reload();
            }
        });
    }
}

// 슬롯 카드에 파일 드롭 처리
function handleSlotDrop(event, slotId, docTypeName) {
    event.preventDefault();
    event.stopPropagation();
    
    // 드롭존 스타일 복원
    event.currentTarget.style.borderColor = '';
    event.currentTarget.style.borderWidth = '';
    
    const files = event.dataTransfer.files;
    if (files.length === 0) return;
    
    const file = files[0];
    
    // 파일 크기 체크 (50MB)
    if (file.size > 50 * 1024 * 1024) {
        showSnackbar('파일 크기는 50MB를 초과할 수 없습니다.', 'warning');
        return;
    }
    
    // 모달 열고 파일 자동 선택
    openUploadModal(slotId, docTypeName);
    
    // 약간의 딜레이 후 파일 설정 (모달이 완전히 열릴 때까지 대기)
    setTimeout(() => {
        selectedFile = file;
        handleFileSelect(file);
    }, 300);
}

// CSRF 토큰 가져오기
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

// D-Day 계산 함수
function calculateDDay(expiryDate) {
    if (!expiryDate) return '';
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const expiry = new Date(expiryDate);
    expiry.setHours(0, 0, 0, 0);
    
    const diffTime = expiry - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) {
        return `<span class="text-danger fw-bold">만료됨 (D+${Math.abs(diffDays)})</span>`;
    } else if (diffDays === 0) {
        return `<span class="text-danger fw-bold">오늘 만료</span>`;
    } else if (diffDays <= 30) {
        return `<span class="text-warning fw-bold">D-${diffDays}</span>`;
    } else {
        return `<span class="text-muted">D-${diffDays}</span>`;
    }
}
