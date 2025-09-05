/**
 * OCR 처리 관련 JavaScript
 * 이미지 업로드, OCR 처리, 결과 적용 기능
 */

class OCRProcessor {
    constructor() {
        this.currentFile = null;
        this.ocrResults = null;
        this.isProcessing = false;
        
        // 필드명 매핑 (한글 라벨)
        this.fieldLabels = {
            'product_name': '제품명',
            'prdlst_nm': '제품명',
            'ingredients': '원재료명',
            'rawmtrl_nm_display': '원재료명(표시)',
            'allergens': '알레르기 유발요소',
            'ingredient_info': '특정성분함량',
            'expiry_date': '유통기한',
            'pog_daycnt': '소비기한',
            'storage_method': '보관방법',
            'manufacturer': '제조업체',
            'bssh_nm': '제조원',
            'nutrition_facts': '영양성분',
            'nutrition_text': '영양성분',
            'weight': '중량',
            'content_weight': '내용량',
            'prdlst_dcnm': '식품유형',
            'country_of_origin': '원산지',
            'cautions': '주의사항',
            'distributor_address': '유통업체',
            'repacker_address': '소분원',
            'importer_address': '수입원',
            'frmlc_mtrqlt': '용기.포장재질',
            'prdlst_report_no': '품목보고번호',
            'additional_info': '기타표시사항'
        };
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // 사진 촬영용 업로드 영역
        const uploadArea = document.getElementById('uploadArea');
        const imageInput = document.getElementById('imageInput');
        
        // 파일 선택용 업로드 영역
        const fileUploadArea = document.getElementById('fileUploadArea');
        const fileInput = document.getElementById('fileInput');
        
        // 사진 촬영 영역 이벤트
        if (uploadArea && imageInput) {
            this.setupUploadArea(uploadArea, imageInput, 'camera');
        }
        
        // 파일 선택 영역 이벤트
        if (fileUploadArea && fileInput) {
            this.setupUploadArea(fileUploadArea, fileInput, 'file');
        }
        
        // 모달 리셋 이벤트
        const modal = document.getElementById('ocrUploadModal');
        if (modal) {
            modal.addEventListener('hidden.bs.modal', () => {
                this.resetUpload();
            });
        }
    }
    
    setupUploadArea(uploadArea, inputElement, type) {
        // 드래그 앤 드롭 이벤트
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        uploadArea.addEventListener('drop', (event) => this.handleDrop(event, inputElement));
        
        // 클릭 이벤트
        uploadArea.addEventListener('click', () => {
            if (!this.isProcessing) {
                inputElement.click();
            }
        });
        
        // 파일 선택 이벤트
        inputElement.addEventListener('change', (event) => this.handleFileSelect(event, type));
    }
    
    handleDragOver(event) {
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.classList.add('dragover');
    }
    
    handleDragLeave(event) {
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.classList.remove('dragover');
    }
    
    handleDrop(event, inputElement) {
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.classList.remove('dragover');
        
        const files = event.dataTransfer.files;
        if (files.length > 0) {
            this.validateAndPreviewFile(files[0]);
            // 선택된 파일을 input에도 설정
            const dt = new DataTransfer();
            dt.items.add(files[0]);
            inputElement.files = dt.files;
        }
    }
    
    handleFileSelect(event, type) {
        const file = event.target.files[0];
        if (file) {
            this.validateAndPreviewFile(file, type);
        }
    }
    
    validateAndPreviewFile(file, type = 'camera') {
        // 파일 유형 검증
        if (!file.type.startsWith('image/')) {
            this.showError('이미지 파일만 업로드 가능합니다.');
            return;
        }
        
        // 파일 크기 검증 (카메라: 5MB, 파일: 10MB)
        const maxSize = type === 'file' ? 10 * 1024 * 1024 : 5 * 1024 * 1024;
        const maxSizeText = type === 'file' ? '10MB' : '5MB';
        
        if (file.size > maxSize) {
            this.showError(`파일 크기는 ${maxSizeText} 이하여야 합니다.`);
            return;
        }
        
        this.currentFile = file;
        
        // 이미지 미리보기 생성
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('previewImg').src = e.target.result;
            this.showStep('imagePreview');
        };
        reader.readAsDataURL(file);
    }
    
    async processOCR() {
        if (!this.currentFile || this.isProcessing) {
            return;
        }
        
        this.isProcessing = true;
        this.updateProcessButton('처리 중...', true);
        
        try {
            // FormData 생성
            const formData = new FormData();
            formData.append('image', this.currentFile);
            
            const labelId = document.getElementById('label_id')?.value;
            if (labelId) {
                formData.append('label_id', labelId);
            }
            
            // OCR 처리 요청
            const response = await fetch('/label/ocr-process/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: formData
            });
            
            // 응답 상태 확인
            if (!response.ok) {
                const errorText = await response.text();
                console.error('서버 응답 오류:', response.status, errorText);
                throw new Error(`서버 오류 (${response.status}): ${response.statusText}`);
            }
            
            // Content-Type 확인
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const responseText = await response.text();
                console.error('예상치 못한 응답 형식:', contentType);
                console.error('응답 내용:', responseText.substring(0, 500));
                throw new Error('서버에서 올바르지 않은 응답 형식을 반환했습니다.');
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.displayOCRResults(result.data);
            } else {
                throw new Error(result.error || 'OCR 처리에 실패했습니다.');
            }
            
        } catch (error) {
            console.error('OCR 처리 오류:', error);
            this.showError('OCR 처리 중 오류가 발생했습니다: ' + error.message);
        } finally {
            this.isProcessing = false;
            this.updateProcessButton('텍스트 추출하기', false);
        }
    }
    
    displayOCRResults(data) {
        // 원본 텍스트 표시
        const extractedTextElement = document.getElementById('extractedText');
        if (extractedTextElement) {
            extractedTextElement.textContent = data.raw_text || '텍스트를 추출할 수 없습니다.';
        }
        
        // 필드별 매핑 결과 표시
        const mappingsContainer = document.getElementById('fieldMappings');
        if (mappingsContainer) {
            mappingsContainer.innerHTML = '';
            
            const fieldMappings = data.field_mappings || {};
            
            if (Object.keys(fieldMappings).length === 0) {
                mappingsContainer.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                        <p>인식된 필드가 없습니다.<br>다른 이미지를 시도해보세요.</p>
                    </div>
                `;
            } else {
                // 필드별로 UI 생성
                Object.entries(fieldMappings).forEach(([fieldName, mapping]) => {
                    if (mapping.text) {
                        const fieldDiv = this.createFieldMappingUI(fieldName, mapping);
                        mappingsContainer.appendChild(fieldDiv);
                    }
                });
            }
        }
        
        this.ocrResults = data;
        this.showStep('ocrResults');
    }
    
    createFieldMappingUI(fieldName, mapping) {
        const fieldLabel = this.fieldLabels[fieldName] || fieldName;
        const confidence = (mapping.confidence || 0) * 100;
        const confidenceClass = this.getConfidenceClass(confidence);
        
        const div = document.createElement('div');
        div.className = 'field-mapping-item border rounded p-3 mb-2';
        
        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <strong class="field-label">${fieldLabel}</strong>
                    <span class="badge confidence-badge ${confidenceClass} ms-2">
                        신뢰도 ${confidence.toFixed(1)}%
                    </span>
                </div>
                <div class="form-check">
                    <input type="checkbox" class="form-check-input" 
                           id="apply_${fieldName}" 
                           ${confidence > 70 ? 'checked' : ''}>
                    <label class="form-check-label" for="apply_${fieldName}">
                        적용
                    </label>
                </div>
            </div>
            <div class="extracted-text-container">
                <textarea class="form-control extracted-text-input" 
                          data-field="${fieldName}" 
                          rows="${this.getTextareaRows(mapping.text)}"
                          placeholder="추출된 텍스트를 확인하고 수정하세요...">${mapping.text}</textarea>
            </div>
        `;
        
        return div;
    }
    
    getConfidenceClass(confidence) {
        if (confidence >= 80) return 'confidence-high';
        if (confidence >= 60) return 'confidence-medium';
        return 'confidence-low';
    }
    
    getTextareaRows(text) {
        const lineCount = (text.match(/\n/g) || []).length + 1;
        return Math.min(Math.max(lineCount, 1), 4);
    }
    
    applyOCRResults() {
        if (!this.ocrResults) {
            return;
        }
        
        let appliedCount = 0;
        const checkedFields = document.querySelectorAll('#fieldMappings input[type="checkbox"]:checked');
        
        checkedFields.forEach(checkbox => {
            const fieldName = checkbox.id.replace('apply_', '');
            const textInput = document.querySelector(`#fieldMappings textarea[data-field="${fieldName}"]`);
            
            if (textInput && textInput.value.trim()) {
                const success = this.applyFieldValue(fieldName, textInput.value.trim());
                if (success) {
                    appliedCount++;
                }
            }
        });
        
        // 모달 닫기
        const modal = bootstrap.Modal.getInstance(document.getElementById('ocrUploadModal'));
        if (modal) {
            modal.hide();
        }
        
        // 결과 메시지
        if (appliedCount > 0) {
            this.showSuccessMessage(`${appliedCount}개 필드가 자동으로 입력되었습니다.`);
        } else {
            this.showWarningMessage('적용된 필드가 없습니다.');
        }
    }
    
    applyFieldValue(fieldName, value) {
        try {
            // 필드명 매핑 (서버에서 오는 필드명을 실제 폼 필드명으로 변환)
            const fieldMapping = {
                'product_name': 'prdlst_nm',
                'ingredients': 'rawmtrl_nm_display',
                'allergens': 'rawmtrl_nm_display', // 알레르기 정보는 원재료명에 포함
                'expiry_date': 'pog_daycnt',
                'manufacturer': 'bssh_nm',
                'nutrition_facts': 'nutrition_text',
                'weight': 'content_weight'
            };
            
            // 매핑된 필드명 사용하거나 원래 필드명 사용
            const actualFieldName = fieldMapping[fieldName] || fieldName;
            
            // 해당 필드 찾기
            const formField = document.querySelector(`input[name="${actualFieldName}"], textarea[name="${actualFieldName}"]`);
            
            if (formField) {
                // 기존 값이 있으면 추가, 없으면 새로 설정
                if (actualFieldName === 'rawmtrl_nm_display' && formField.value.trim()) {
                    // 원재료명에 알레르기 정보 추가
                    if (fieldName === 'allergens') {
                        formField.value += `\n\n※ 알레르기 유발요소: ${value}`;
                    } else {
                        formField.value = value;
                    }
                } else {
                    formField.value = value;
                }
                
                // 관련 체크박스 자동 체크
                const checkbox = document.querySelector(`input[id="chk_${actualFieldName}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                }
                
                // 시각적 피드백
                this.highlightField(formField);
                
                console.log(`필드 적용 성공: ${fieldName} -> ${actualFieldName} = ${value}`);
                return true;
            } else {
                console.warn(`필드를 찾을 수 없습니다: ${fieldName} (매핑: ${actualFieldName})`);
                return false;
            }
        } catch (error) {
            console.error(`필드 적용 오류 (${fieldName}):`, error);
            return false;
        }
    }
    
    highlightField(field) {
        // 필드 하이라이트 효과
        const originalBg = field.style.backgroundColor;
        field.style.backgroundColor = '#d4edda';
        field.style.transition = 'background-color 0.3s ease';
        
        // 스크롤하여 필드가 보이도록
        field.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // 2초 후 원래 색상으로 복원
        setTimeout(() => {
            field.style.backgroundColor = originalBg;
            setTimeout(() => {
                field.style.transition = '';
            }, 300);
        }, 2000);
    }
    
    resetUpload() {
        this.currentFile = null;
        this.ocrResults = null;
        this.isProcessing = false;
        
        // UI 초기화
        this.showStep('uploadArea');
        
        // 모든 input 필드 초기화
        const imageInput = document.getElementById('imageInput');
        const fileInput = document.getElementById('fileInput');
        
        if (imageInput) imageInput.value = '';
        if (fileInput) fileInput.value = '';
        
        // 결과 영역 초기화
        const extractedText = document.getElementById('extractedText');
        const fieldMappings = document.getElementById('fieldMappings');
        
        if (extractedText) extractedText.textContent = '';
        if (fieldMappings) fieldMappings.innerHTML = '';
        
        // 탭을 첫 번째 탭으로 리셋
        const firstTab = document.querySelector('#uploadTabs .nav-link');
        if (firstTab) {
            const tab = new bootstrap.Tab(firstTab);
            tab.show();
        }
        
        this.updateProcessButton('텍스트 추출하기', false);
    }
    
    showStep(stepId) {
        // 탭 컨텐츠 영역과 단계별 영역 숨기기
        const uploadTabsContent = document.getElementById('uploadTabsContent');
        const imagePreview = document.getElementById('imagePreview');
        const ocrResults = document.getElementById('ocrResults');
        
        // 모든 단계 숨기기
        if (uploadTabsContent) uploadTabsContent.style.display = 'none';
        if (imagePreview) imagePreview.style.display = 'none';
        if (ocrResults) ocrResults.style.display = 'none';
        
        // 해당 단계만 표시
        if (stepId === 'uploadArea') {
            if (uploadTabsContent) uploadTabsContent.style.display = 'block';
        } else {
            const targetElement = document.getElementById(stepId);
            if (targetElement) {
                targetElement.style.display = 'block';
            }
        }
    }
    
    updateProcessButton(text, showSpinner) {
        const btn = document.getElementById('processBtn');
        const textElement = document.getElementById('processText');
        const spinner = document.getElementById('processSpinner');
        
        if (btn) btn.disabled = showSpinner;
        if (textElement) textElement.innerHTML = `<i class="fas fa-magic me-1"></i>${text}`;
        if (spinner) spinner.style.display = showSpinner ? 'inline-block' : 'none';
    }
    
    showError(message) {
        alert(`오류: ${message}`);
    }
    
    showSuccessMessage(message) {
        // 임시로 alert 사용, 추후 토스트 메시지로 변경 가능
        alert(message);
    }
    
    showWarningMessage(message) {
        alert(message);
    }
    
    getCookie(name) {
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
}

// 전역 함수들 (HTML에서 호출)
window.processOCR = function() {
    if (window.ocrProcessor) {
        window.ocrProcessor.processOCR();
    }
};

window.applyOCRResults = function() {
    if (window.ocrProcessor) {
        window.ocrProcessor.applyOCRResults();
    }
};

window.resetUpload = function() {
    if (window.ocrProcessor) {
        window.ocrProcessor.resetUpload();
    }
};

// DOM 로드 완료 시 OCR 프로세서 초기화
document.addEventListener('DOMContentLoaded', function() {
    window.ocrProcessor = new OCRProcessor();
    console.log('OCR 프로세서가 초기화되었습니다.');
});
