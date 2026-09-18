// ==================== 스마트 업로드 모달 관련 함수 ====================

let selectedFile = null;
/* 여러 장을 한꺼번에 받는 구분이 있다(DocumentType.multiple_yn).
   원료 표시사항이 그것이다 — 장마다 다른 원료라 한 장씩 올릴 까닭이 없다.
   한 장일 때도 이 배열에 담아 두어 아래 흐름을 한 벌로 쓴다. */
let selectedFiles = [];
let targetSlotId = null;
let lastSlotContext = null;

// 모달 열기
function openUploadModal(slotId, docTypeName, docTypeId) {
    /* **`new` 로 만들지 않는다.**
     *
     * 이 함수는 여러 자리에서 불린다(업로드 단추 · 슬롯의 + · 끌어다 놓기 ·
     * 영양성분 탭의 성적서 첨부). 부를 때마다 새 인스턴스를 만들면 한 요소에
     * 인스턴스가 여럿 붙고, 각자 배경막을 들고 있다가 하나만 걷힌다 —
     * **창을 닫아도 회색 막이 남아 화면이 멈춘 것처럼 보인다.**
     * 요소 하나에 인스턴스 하나만 둔다. */
    const modal = bootstrap.Modal.getOrCreateInstance(
        document.getElementById('smartUploadModal'));
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

    /* 구분이 정해진 뒤에 부른다 — 슬롯 쪽은 change 로도 불리지만, 일반
       업로드는 값을 비우기만 해서 앞서 열었던 창의 설정이 남는다. */
    syncMultipleFromType();
    showUploadStep(docTypeId ? 'form' : 'pick');

    modal.show();
}

// 폼 초기화
function resetUploadForm() {
    selectedFiles = [];
    warnDuplicateNames([]);   // 앞서 연 창의 경고가 남지 않게
    renderSelectedList();
    selectedFile = null;
    document.getElementById('smart-upload-form').reset();
    document.getElementById('selected-file-info').style.display = 'none';
    document.getElementById('custom-expiry-input').style.display = 'none';
    document.getElementById('calculated-expiry').style.display = 'none';
    const customExpiryInput = document.getElementById('custom-expiry-date');
    if (customExpiryInput) {
        customExpiryInput.value = '';
    }
    const form = document.getElementById('smart-upload-form');
    if (form) delete form.dataset.expiryUserPicked;   // 다음 업로드는 새로 판단
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
        selectFileBtn.addEventListener('click', function(e) {
            e.stopPropagation();
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
            
            handleFilesSelect(e.dataTransfer.files);
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            handleFilesSelect(this.files);
        });
    }
    
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            selectedFile = null;
            selectedFiles = [];
            fileInput.value = '';
            warnDuplicateNames([]);
            renderSelectedList();
            document.getElementById('selected-file-info').style.display = 'none';
        });
    }
    
    document.querySelectorAll('.upload-pick-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const sel = document.getElementById('document-type-select');
            if (sel) {
                sel.value = this.dataset.typeId;
                sel.dispatchEvent(new Event('change'));
            }
            const title = document.getElementById('upload-modal-title');
            if (title) title.textContent = this.dataset.typeName + ' 등록';
            showUploadStep('form');
        });
    });

    const backBtn = document.getElementById('upload-back-btn');
    if (backBtn) {
        backBtn.addEventListener('click', function () {
            resetUploadForm();
            const title = document.getElementById('upload-modal-title');
            if (title) title.textContent = '문서 등록';
            showUploadStep('pick');
        });
    }

    // 문서 종류 선택 시 유효기간 자동 설정
    const typeSelect = document.getElementById('document-type-select');
    if (typeSelect) {
        typeSelect.addEventListener('change', syncMultipleFromType);
        typeSelect.addEventListener('change', function() {
            /* ═══ 이 아래가 **한 번도 실행되지 않았다** ═══════════════════
             *
             * `if (selectedExpiry) return;` 이 있었다. 그런데 라디오는 늘
             * 하나가 골라져 있다 — HTML 기본값이 '무기한' 이고,
             * `resetUploadForm()` 이 form.reset() 뒤에 그것을 다시 못박은
             * 다음 openUploadModal 이 이 change 를 쏘기 때문이다.
             *
             * 그래서 `data-validity` 를 읽는 분기가 통째로 죽어 있었고,
             * 자가품질검사성적서(180일)·원산지증명서(365일)·HACCP(1095일)을
             * 그냥 올리면 **전부 만료일 없음**으로 들어갔다. 서버 쪽 안전망
             * (ProductDocument.save 의 default_validity_days)도 화면이 보낸
             * `expiry_unlimited=true` 때문에 함께 꺼졌다.
             * D-day·만료 배지·만료 알림·준수율이 그 문서들에 대해 영영 안 돌았다.
             *
             * **사람이 손으로 고른 것은 지킨다.** 그 표시는 아래 라디오
             * change 핸들러가 남긴다(dataset.userPicked).
             * ═══════════════════════════════════════════════════════════ */
            const wrap = document.querySelector('input[name="expiry-option"]');
            if (wrap && wrap.form && wrap.form.dataset.expiryUserPicked === '1') {
                return;
            }
            const selected = this.options[this.selectedIndex];
            const validityDays = selected.getAttribute('data-validity');
            
            if (validityDays !== null && validityDays !== '') {
                const days = parseInt(validityDays);
                if (days === 0) {
                    document.getElementById('expiry-unlimited').checked = true;
                } else if (days === 30) {
                    document.getElementById('expiry-1m').checked = true;
                } else if (days === 90) {
                    document.getElementById('expiry-3m').checked = true;
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
        /* 사람이 직접 고른 것인지 표시해 둔다. 위 문서 종류 change 가
           그 선택을 덮지 않게 하려는 것이다 — `isTrusted` 는 실제 사용자
           입력일 때만 참이라, 코드가 쏜 change 와 갈린다. */
        radio.addEventListener('change', function (ev) {
            if (ev.isTrusted && this.form) this.form.dataset.expiryUserPicked = '1';
        });
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
/* 화면이 "최대 30MB" 라고 적어 두었는데 여기에 검사가 없었다. 유일한
   클라이언트 검사는 handleSlotDrop 안에 있었는데 그 함수는 호출 0회다.
   서버가 친절한 문구로 막긴 하나 30MB 를 다 올린 뒤다 — 모바일 회선에서는
   몇 분이 그냥 버려진다. */
const UPLOAD_MAX_MB = 30;
const UPLOAD_ALLOWED_EXTS = [
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'hwp', 'hwpx', 'txt', 'csv', 'zip',
];

/*
 * 같은 이름의 문서가 이미 있으면 **말해 주되 막지는 않는다.**
 *
 * 여러 장을 한꺼번에 올리게 되면서 같은 사진을 두 번 넣기 쉬워졌다. 그러면
 * 판독도 두 번 돌아 시간과 비용이 두 배로 든다. 그런데 막을 수는 없다 —
 * 정말로 같은 이름의 다른 원료일 수 있다('영양성분.png' 는 아무 봉지에나
 * 붙는 이름이다). 고르는 것은 사람이 한다.
 */
function existingFilenames() {
    try {
        if (typeof documentData === 'undefined' || !documentData) return [];
        return Object.keys(documentData)
            .map(k => (documentData[k].filename || '').toLowerCase());
    } catch (err) {
        return [];      // 못 읽어도 업로드는 막지 않는다
    }
}

/*
 * 고른 것이 여럿이면 **장마다 한 줄씩** 그리고, 각각 뺄 수 있게 한다.
 *
 * 예전에는 첫 장의 이름만 적고 [X] 하나가 전부를 지웠다. 다섯 장 중 한 장이
 * 잘못 골라졌으면 다섯 장을 다시 고르는 수밖에 없었다 — 파일 고르기 창에서
 * 여러 장을 집는 일이 쉬운 일이 아닌데도.
 */
function renderSelectedList() {
    const box = document.getElementById('selected-file-list');
    const single = document.getElementById('selected-file-info');
    if (!box) return;

    if (selectedFiles.length < 2) {
        box.hidden = true;
        box.innerHTML = '';
        if (single) single.style.display = selectedFiles.length ? 'block' : 'none';
        return;
    }

    const have = existingFilenames();
    box.hidden = false;
    box.innerHTML = selectedFiles.map((f, i) => {
        const dup = have.indexOf((f.name || '').toLowerCase()) !== -1;
        return '<div class="d-flex align-items-center gap-2 py-1 border-bottom">'
             + '<i class="bi bi-image text-info"></i>'
             + '<span class="flex-grow-1 text-truncate" title="' + f.name + '">'
             + f.name + (dup ? ' <span class="badge bg-warning text-dark">중복</span>' : '')
             + '</span>'
             + '<span class="text-muted small flex-shrink-0">' + formatFileSize(f.size) + '</span>'
             + '<button type="button" class="btn btn-sm btn-light border flex-shrink-0"'
             + ' data-drop="' + i + '" title="이 장 빼기">&times;</button>'
             + '</div>';
    }).join('');

    box.querySelectorAll('[data-drop]').forEach(btn => {
        btn.addEventListener('click', function () {
            dropSelectedFile(Number(this.dataset.drop));
        });
    });
}

/* 한 장을 뺀다. 마지막 한 장까지 빼면 처음으로 돌아간다. */
function dropSelectedFile(index) {
    selectedFiles = selectedFiles.filter((f, i) => i !== index);
    selectedFile = selectedFiles[0] || null;

    if (!selectedFiles.length) {
        const input = document.getElementById('document-upload-input');
        if (input) input.value = '';
        const single = document.getElementById('selected-file-info');
        if (single) single.style.display = 'none';
    }
    refreshSelectedSummary();
    warnDuplicateNames(selectedFiles);
    renderSelectedList();
}

/* 파일 칸의 이름·크기 요약. 한 장이면 그 장, 여럿이면 장수를 적는다. */
function refreshSelectedSummary() {
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    if (!fileName || !fileSize || !selectedFiles.length) return;

    if (selectedFiles.length === 1) {
        fileName.textContent = selectedFiles[0].name;
        fileSize.textContent = formatFileSize(selectedFiles[0].size);
        return;
    }
    fileName.textContent = selectedFiles[0].name + ' 외 ' + (selectedFiles.length - 1) + '장';
    fileSize.textContent = '모두 ' + selectedFiles.length + '장 · '
        + formatFileSize(selectedFiles.reduce((sum, f) => sum + f.size, 0));
}

function warnDuplicateNames(files) {
    const hint = document.getElementById('upload-duplicate-hint');
    if (!hint) return;
    const have = existingFilenames();
    const dup = files
        .filter(f => have.indexOf((f.name || '').toLowerCase()) !== -1)
        .map(f => f.name);
    if (!dup.length) {
        hint.hidden = true;
        hint.textContent = '';
        return;
    }
    hint.hidden = false;
    hint.textContent = '같은 이름의 문서가 이미 있습니다 — ' + dup.join(', ')
        + '. 그래도 올리면 따로 한 건 더 남습니다.';
}

/* 올릴 수 있는 파일인가. 여러 장을 받게 되면서 검사가 두 자리에서 필요해졌다 —
   같은 규칙을 두 벌 적으면 한쪽만 고쳐지는 날이 온다. */
function isUploadable(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (UPLOAD_ALLOWED_EXTS.indexOf(ext) === -1) {
        showSnackbar('올릴 수 없는 확장자입니다 (.' + ext + '). '
                     + '올릴 수 있는 것: ' + UPLOAD_ALLOWED_EXTS.join(', '), 'error');
        return false;
    }
    if (file.size > UPLOAD_MAX_MB * 1024 * 1024) {
        showSnackbar('파일 하나는 ' + UPLOAD_MAX_MB + ' MB 까지 올릴 수 있습니다 (지금 '
                     + formatFileSize(file.size) + '). 사진이면 해상도를 줄이거나 '
                     + '여러 장으로 나눠 올려 주세요.', 'error');
        return false;
    }
    return true;
}

/* 고른 것이 여러 장일 수 있다. 한 장이면 예전 흐름 그대로다. */
function handleFilesSelect(fileList) {
    const files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;

    const input = document.getElementById('document-upload-input');
    const many = !!(input && input.multiple) && files.length > 1;
    if (!many) {
        handleFileSelect(files[0]);
        return;
    }

    const good = files.filter(isUploadable);
    if (!good.length) return;

    handleFileSelect(good[0]);        // 첫 장으로 칸을 채우고
    selectedFiles = good;             // 나머지는 여기 담아 둔다
    warnDuplicateNames(good);
    refreshSelectedSummary();
    renderSelectedList();
}

function handleFileSelect(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!isUploadable(file)) {
        return;
    }
    selectedFile = file;
    selectedFiles = [file];
    warnDuplicateNames([file]);
    renderSelectedList();
    
    // 파일 정보 표시
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const fileIcon = document.getElementById('file-icon');
    
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    // 아이콘 설정 — 확장자는 위에서 이미 구했다. 여기서 const 로 다시
    // 선언하면 같은 블록의 재선언이라 **파일 전체가 SyntaxError 로 죽는다.**
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
    showUploadPreview(file);
}

/*
 * 고른 파일을 **그 자리에서 보여 준다.**
 *
 * 이름과 크기만 적어 두면 "이게 맞는 파일인가" 를 확인할 방법이 없다. 문서
 * 종류와 유효기간을 여기서 정하는데, 정작 그 종이를 못 보고 정하는 셈이다.
 * 파일 이름이 "scan_0007.pdf" 인 일은 흔하다.
 *
 * 값을 불러와 확인하는 다른 창들과 **같은 뷰어**를 쓴다(photo_viewer.js).
 * 회전·확대가 붙고 PDF 도 그대로 열린다 — 이 창만 따로 만들면 같은 일을
 * 하는 화면이 서로 다르게 생기고, 뷰어를 고칠 때 두 곳을 고쳐야 한다.
 */
function showUploadPreview(file) {
    const host = document.querySelector('#selected-file-info .smart-preview-hint');
    if (!host || typeof window.photoViewerElement !== 'function') return;

    let slot = document.getElementById('upload-preview-slot');
    if (!slot) {
        slot = document.createElement('div');
        slot.id = 'upload-preview-slot';
        slot.className = 'upload-preview-slot mt-2';
        host.parentNode.insertBefore(slot, host.nextSibling);
    }
    slot.innerHTML = '';

    const viewer = window.photoViewerElement(file, file.name);
    if (!viewer) return;
    slot.appendChild(viewer);
    if (typeof window.photoViewerRelease === 'function') {
        window.photoViewerRelease(viewer);   // 창이 닫히면 놓아 준다
    }
}

// 파일 크기 포맷
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/*
 * 고른 구분이 '여러 건' 이면 파일을 여러 장 고를 수 있게 한다.
 *
 * **모든 구분에 여러 장을 열지 않는다.** 품목제조보고서를 세 장 고르면 그중
 * 무엇이 그 제품의 보고서인지 알 수 없다 — 그런 구분에서는 여러 장이 실수다.
 * 규칙은 서버가 정하고(DocumentType.multiple_yn), 화면은 그대로 따른다.
 */
/*
 * 창을 두 걸음으로 나눈다.
 *
 * 예전에는 열자마자 끌어놓기 칸·문서 종류 목록·유효기간 라디오·알림 토글이
 * 한꺼번에 보였다. **무엇부터 해야 하는지 알 수 없다.** 게다가 증빙서류와
 * 원료 사진은 성격이 전혀 다른데 같은 목록에 한 줄씩 나란히 있었다.
 *
 * 첫 걸음에서 구분만 고르고, 고른 뒤에 그 구분에 맞는 화면을 보여 준다.
 * 슬롯의 [+] 로 열 때는 구분이 이미 정해져 있으므로 첫 걸음을 건너뛴다 —
 * 고를 것이 없는데 고르라고 물으면 그것이 곧 군더더기다.
 */
function showUploadStep(which) {
    const pick = document.getElementById('upload-step-pick');
    const form = document.getElementById('upload-step-form');
    const foot = document.getElementById('upload-step-foot');
    const sub = document.querySelector('#smartUploadModal .modal-subtitle');
    if (!pick || !form || !foot) return;

    const picking = which === 'pick';
    pick.hidden = !picking;
    form.hidden = picking;
    foot.hidden = picking;
    if (sub) {
        sub.textContent = picking
            ? '무엇을 올리시는지 먼저 골라 주세요.'
            : '파일을 올리고 유효기간을 정합니다.';
    }
}

function syncMultipleFromType() {
    const typeSelect = document.getElementById('document-type-select');
    const fileInput = document.getElementById('document-upload-input');
    if (!typeSelect || !fileInput) return;

    const picked = typeSelect.options[typeSelect.selectedIndex];
    const many = !!(picked && picked.dataset.multiple === '1');
    fileInput.multiple = many;
    if (!many && selectedFiles.length > 1) {
        // 여러 장을 고른 뒤 구분을 바꾸면 남은 것을 조용히 올리지 않는다
        selectedFiles = selectedFile ? [selectedFile] : [];
        const fileName = document.getElementById('file-name');
        if (fileName && selectedFile) fileName.textContent = selectedFile.name;
    }

    const hint = document.getElementById('upload-multiple-hint');
    if (hint) hint.hidden = !many;
}
window.syncMultipleFromType = syncMultipleFromType;

// 스마트 업로드 처리
async function handleSmartUpload() {
    const submitBtn = document.getElementById('upload-submit-btn');
    const typeSelectValue = document.getElementById('document-type-select').value;
    const slotIdValue = document.getElementById('target-slot-id').value;
    const fileInput = document.getElementById('document-upload-input');
    if (!selectedFile && fileInput && fileInput.files && fileInput.files.length > 0) {
        handleFilesSelect(fileInput.files);
    }
    if (!selectedFiles.length && selectedFile) selectedFiles = [selectedFile];

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
        /* **파일마다 FormData 를 새로 만든다.** 하나를 만들어 file 만 갈아
         * 끼우면 append 가 쌓여 두 번째 요청에 파일이 둘 들어간다. */
        const buildForm = (file) => {
        const formData = new FormData();
        formData.append('file', file);
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
        return formData;
        };

        const csrftoken = getCsrfToken();
        // data-label-id 속성에서 labelId 읽기
        const labelId = parseInt(document.getElementById('smartUploadModal').getAttribute('data-label-id'));
        const uploadUrl = `/products/documents/api/upload/${labelId}/`;
        
        /* 한 장씩 차례로 올린다.
         *
         * 한꺼번에 보내지 않는 까닭이 있다. 서버는 판 번호를 '지금 있는 것 중
         * 가장 큰 것 + 1' 로 매기는데, 동시에 들어오면 같은 번호를 두 번 줄 수
         * 있다. 사진 몇 장 올리는 일에 몇 초 더 드는 것이 값을 잃는 것보다 낫다.
         *
         * **한 장이 실패해도 멈추지 않는다.** 다섯 장 중 셋째가 실패했다고
         * 넷째·다섯째를 버리면, 사용자는 무엇이 올라갔는지 모른 채 처음부터
         * 다시 해야 한다. */
        const uploaded = [];
        const failed = [];
        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            if (selectedFiles.length > 1) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>'
                    + (i + 1) + ' / ' + selectedFiles.length + ' 올리는 중...';
            }
            let res, body;
            try {
                res = await fetch(uploadUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrftoken },
                    body: buildForm(file)
                });
                body = await res.json();
            } catch (err) {
                console.error('[handleSmartUpload]', file.name, err);
                failed.push(file.name);
                continue;
            }
            if (res.ok && body && body.document_id) {
                uploaded.push(body.document_id);
            } else {
                failed.push(file.name + (body && body.error ? ' — ' + body.error : ''));
            }
        }

        const response = { ok: uploaded.length > 0 };
        const data = { document_id: uploaded[0], document_ids: uploaded };
        if (failed.length) {
            showSnackbar(failed.length + '장을 올리지 못했습니다: '
                         + failed.join(' / '), 'error');
        }

        if (response.ok) {
            
            // 모달 닫기
            const modalElement = document.getElementById('smartUploadModal');
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
            
            // 성공 메시지 + 문서함 탭 복원 후 새로고침
            showSnackbar(uploaded.length > 1
                ? uploaded.length + '장을 등록했습니다.'
                : '문서가 성공적으로 등록되었습니다.', 'success');
            sessionStorage.setItem('returnToTab', 'docs');

            /* 영양성분 탭에서 "성적서 첨부" 로 들어온 길이면, 새로고침 뒤에
               **방금 올린 그 문서를 읽는다.** 올린 사람은 값을 넣으러 온
               것이지 파일을 쌓으러 온 것이 아니다.

               그리고 **왔던 자리로 되돌린다.** 문서함 탭으로 데려다 놓으면
               값을 넣고 나서 영양성분 탭을 다시 찾아 들어가야 한다. */
            /* 원료 표시사항을 올렸으면 **새로고침 뒤에 바로 줄 세워 판독한다.**
             *
             * 올린 사람은 사진을 쌓으러 온 것이 아니라 BOM 에 원료를 넣으러
             * 온 것이다. 문서함에 파일만 남기고 끝내면, 판독하려고 한 장씩
             * 다시 찾아 눌러야 한다 — 다섯 장이면 다섯 번이다.
             *
             * 새로고침을 거치는 까닭은 아래 reload 때문이다. 화면이 새로
             * 그려져야 방금 올린 문서가 목록에 서고, 판독 창이 그 문서의
             * 사진을 옆에 놓을 수 있다. */
            try {
                const manyPicked = document.getElementById('document-type-select');
                const pickedOpt = manyPicked
                    ? manyPicked.options[manyPicked.selectedIndex] : null;
                if (pickedOpt && pickedOpt.dataset.multiple === '1' && uploaded.length) {
                    sessionStorage.setItem('ingredientQueue', JSON.stringify(uploaded));
                }
            } catch (e) { /* 못 남겨도 업로드는 끝났다 */ }

            try {
                if (sessionStorage.getItem('specReadAfterUpload') && data.document_id) {
                    sessionStorage.removeItem('specReadAfterUpload');
                    sessionStorage.setItem('specReadDocId', String(data.document_id));
                    sessionStorage.setItem('returnToTab', 'nutrition');
                }
            } catch (e) { /* 못 남겨도 업로드는 끝났다 */ }

            window.location.reload();
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
    
    // 파일 크기 체크 — 한도는 서버와 같다
    if (file.size > (window.MAX_UPLOAD_MB || 30) * 1024 * 1024) {
        showSnackbar('파일 크기는 ' + (window.MAX_UPLOAD_MB || 30)
                     + 'MB 를 초과할 수 없습니다.', 'warning');
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
