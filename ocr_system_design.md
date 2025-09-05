# OCR 기반 표시사항 자동 입력 시스템 설계안

## 1. 시스템 개요

### 목적
- 사용자가 기존 식품 표시사항 사진을 업로드하면 OCR로 텍스트를 추출
- 추출된 텍스트를 분석하여 표시사항 작성 화면의 각 필드에 자동 입력
- 수동 입력 시간을 대폭 단축하고 정확성 향상

### 작업 흐름
```
1. 사용자 사진 업로드
2. 이미지 전처리 (해상도, 대비 조정)
3. OCR 텍스트 추출
4. 텍스트 파싱 및 분류
5. 각 필드별 데이터 매핑
6. 표시사항 폼에 자동 입력
```

## 2. 기술 스택 선택

### 2.1 OCR 엔진 비교

#### A. Google Cloud Vision API (권장)
**장점:**
- 한글 인식률 높음 (95% 이상)
- 표 형태 데이터 인식 우수
- 다양한 폰트 지원
- JSON 형태 구조화된 결과 제공

**단점:**
- 유료 서비스 (월 1,000회까지 무료)
- 외부 API 의존성

**가격:** 1,000회 이후 $1.50/1,000회

#### B. AWS Textract
**장점:**
- 표 및 폼 구조 인식 탁월
- 다국어 지원
- AWS 생태계 연동

**단점:**
- 한글 지원 제한적
- 비교적 높은 비용

#### C. Azure Computer Vision
**장점:**
- 한글 지원 양호
- OCR + 문서 분석 통합
- 무료 티어 제공

**단점:**
- 복잡한 레이아웃 인식 한계

#### D. Tesseract (오픈소스)
**장점:**
- 완전 무료
- 로컬 처리 가능
- 커스터마이징 가능

**단점:**
- 한글 인식률 상대적으로 낮음 (80-85%)
- 전처리 작업 필요

### 2.2 권장 조합
```
Primary: Google Cloud Vision API
Fallback: Tesseract (비용 절약용)
```

## 3. 구현 아키텍처

### 3.1 시스템 구조
```
Frontend (Vue.js/React)
├── 이미지 업로드 컴포넌트
├── 미리보기 및 편집 영역
└── 결과 확인 및 수정 UI

Backend (Django)
├── 이미지 업로드 처리
├── OCR 처리 서비스
├── 텍스트 파싱 엔진
└── 필드 매핑 로직

External Services
├── Google Cloud Vision API
└── 이미지 저장소 (AWS S3/Local)
```

### 3.2 데이터베이스 설계
```python
class OCRResult(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    label_id = models.ForeignKey(MyLabel, on_delete=models.CASCADE, null=True)
    
    # 원본 이미지 정보
    original_image = models.ImageField(upload_to='ocr_images/')
    processed_image = models.ImageField(upload_to='ocr_processed/', null=True)
    
    # OCR 결과
    raw_text = models.TextField(verbose_name="원본 OCR 텍스트")
    structured_data = models.JSONField(verbose_name="구조화된 데이터")
    confidence_score = models.FloatField(verbose_name="인식 신뢰도")
    
    # 처리 상태
    status = models.CharField(max_length=20, choices=[
        ('processing', '처리중'),
        ('completed', '완료'),
        ('failed', '실패')
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
class OCRFieldMapping(models.Model):
    ocr_result = models.ForeignKey(OCRResult, on_delete=models.CASCADE)
    field_name = models.CharField(max_length=50)
    extracted_text = models.TextField()
    confidence = models.FloatField()
    is_verified = models.BooleanField(default=False)
```

## 4. 상세 구현 방안

### 4.1 Frontend 구현

#### 이미지 업로드 컴포넌트
```html
<!-- OCR 업로드 모달 -->
<div class="modal fade" id="ocrUploadModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">표시사항 사진으로 자동 입력</h5>
      </div>
      <div class="modal-body">
        <!-- 파일 업로드 영역 -->
        <div class="upload-area" id="uploadArea">
          <div class="upload-placeholder">
            <i class="fas fa-camera fa-3x text-muted"></i>
            <p>표시사항 사진을 드래그하거나 클릭하여 업로드하세요</p>
            <p class="text-muted small">JPG, PNG 파일 지원 (최대 5MB)</p>
          </div>
          <input type="file" id="imageInput" accept="image/*" style="display: none;">
        </div>
        
        <!-- 이미지 미리보기 -->
        <div id="imagePreview" style="display: none;">
          <img id="previewImg" class="img-fluid mb-3" style="max-height: 400px;">
          <div class="d-flex justify-content-between">
            <button type="button" class="btn btn-outline-secondary" onclick="resetUpload()">다시 선택</button>
            <button type="button" class="btn btn-primary" onclick="processOCR()" id="processBtn">
              <span id="processText">텍스트 추출하기</span>
              <span id="processSpinner" class="spinner-border spinner-border-sm ms-2" style="display: none;"></span>
            </button>
          </div>
        </div>
        
        <!-- OCR 결과 표시 -->
        <div id="ocrResults" style="display: none;">
          <h6>추출된 텍스트</h6>
          <div class="border p-3 mb-3" style="max-height: 200px; overflow-y: auto;">
            <pre id="extractedText"></pre>
          </div>
          
          <!-- 필드별 매핑 결과 -->
          <h6>자동 분류 결과</h6>
          <div id="fieldMappings"></div>
          
          <div class="d-flex justify-content-end mt-3">
            <button type="button" class="btn btn-secondary me-2" data-bs-dismiss="modal">취소</button>
            <button type="button" class="btn btn-success" onclick="applyOCRResults()">적용하기</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

#### JavaScript 처리 로직
```javascript
// OCR 처리 관련 JavaScript
class OCRProcessor {
    constructor() {
        this.currentFile = null;
        this.ocrResults = null;
        this.initEventListeners();
    }
    
    initEventListeners() {
        // 드래그 앤 드롭 지원
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('drop', this.handleDrop.bind(this));
        uploadArea.addEventListener('click', () => {
            document.getElementById('imageInput').click();
        });
        
        // 파일 선택 처리
        document.getElementById('imageInput').addEventListener('change', this.handleFileSelect.bind(this));
    }
    
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.validateAndPreviewFile(file);
        }
    }
    
    validateAndPreviewFile(file) {
        // 파일 검증
        if (!file.type.startsWith('image/')) {
            alert('이미지 파일만 업로드 가능합니다.');
            return;
        }
        
        if (file.size > 5 * 1024 * 1024) { // 5MB 제한
            alert('파일 크기는 5MB 이하여야 합니다.');
            return;
        }
        
        this.currentFile = file;
        
        // 미리보기 표시
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('previewImg').src = e.target.result;
            document.getElementById('uploadArea').style.display = 'none';
            document.getElementById('imagePreview').style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
    
    async processOCR() {
        if (!this.currentFile) return;
        
        const processBtn = document.getElementById('processBtn');
        const processText = document.getElementById('processText');
        const processSpinner = document.getElementById('processSpinner');
        
        // UI 상태 변경
        processBtn.disabled = true;
        processText.textContent = '처리 중...';
        processSpinner.style.display = 'inline-block';
        
        try {
            // FormData로 파일 전송
            const formData = new FormData();
            formData.append('image', this.currentFile);
            formData.append('label_id', document.getElementById('label_id').value);
            
            const response = await fetch('/label/ocr-process/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayOCRResults(result.data);
            } else {
                throw new Error(result.error || 'OCR 처리 실패');
            }
            
        } catch (error) {
            alert('OCR 처리 중 오류가 발생했습니다: ' + error.message);
        } finally {
            // UI 상태 복원
            processBtn.disabled = false;
            processText.textContent = '텍스트 추출하기';
            processSpinner.style.display = 'none';
        }
    }
    
    displayOCRResults(data) {
        // 원본 텍스트 표시
        document.getElementById('extractedText').textContent = data.raw_text;
        
        // 필드별 매핑 결과 표시
        const mappingsContainer = document.getElementById('fieldMappings');
        mappingsContainer.innerHTML = '';
        
        Object.entries(data.field_mappings).forEach(([fieldName, mapping]) => {
            if (mapping.text) {
                const fieldDiv = this.createFieldMappingUI(fieldName, mapping);
                mappingsContainer.appendChild(fieldDiv);
            }
        });
        
        this.ocrResults = data;
        
        // 결과 영역 표시
        document.getElementById('imagePreview').style.display = 'none';
        document.getElementById('ocrResults').style.display = 'block';
    }
    
    createFieldMappingUI(fieldName, mapping) {
        const fieldLabels = {
            'prdlst_nm': '제품명',
            'prdlst_dcnm': '식품유형',
            'content_weight': '내용량',
            'country_of_origin': '원산지',
            'bssh_nm': '제조원',
            'storage_method': '보관방법',
            'rawmtrl_nm': '원재료명',
            'cautions': '주의사항'
        };
        
        const div = document.createElement('div');
        div.className = 'card mb-2';
        div.innerHTML = `
            <div class="card-body py-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${fieldLabels[fieldName] || fieldName}</strong>
                        <div class="text-muted small">신뢰도: ${(mapping.confidence * 100).toFixed(1)}%</div>
                    </div>
                    <div class="flex-grow-1 mx-3">
                        <input type="text" class="form-control form-control-sm" 
                               value="${mapping.text}" 
                               data-field="${fieldName}">
                    </div>
                    <div class="form-check">
                        <input type="checkbox" class="form-check-input" 
                               id="apply_${fieldName}" 
                               ${mapping.confidence > 0.8 ? 'checked' : ''}>
                        <label class="form-check-label" for="apply_${fieldName}">적용</label>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    }
    
    applyOCRResults() {
        if (!this.ocrResults) return;
        
        // 체크된 필드들을 실제 폼에 적용
        document.querySelectorAll('#fieldMappings input[type="checkbox"]:checked').forEach(checkbox => {
            const fieldName = checkbox.id.replace('apply_', '');
            const textInput = document.querySelector(`#fieldMappings input[data-field="${fieldName}"]`);
            const formField = document.querySelector(`input[name="${fieldName}"], textarea[name="${fieldName}"]`);
            
            if (textInput && formField && textInput.value.trim()) {
                formField.value = textInput.value.trim();
                
                // 연관된 체크박스도 자동으로 체크
                const relatedCheckbox = document.querySelector(`input[id="chk_${fieldName}"]`);
                if (relatedCheckbox) {
                    relatedCheckbox.checked = true;
                }
                
                // 필드 하이라이트 효과
                formField.style.backgroundColor = '#e8f5e8';
                setTimeout(() => {
                    formField.style.backgroundColor = '';
                }, 2000);
            }
        });
        
        // 모달 닫기
        const modal = bootstrap.Modal.getInstance(document.getElementById('ocrUploadModal'));
        modal.hide();
        
        // 성공 메시지
        const appliedCount = document.querySelectorAll('#fieldMappings input[type="checkbox"]:checked').length;
        alert(`${appliedCount}개 필드가 자동으로 입력되었습니다.`);
    }
    
    resetUpload() {
        this.currentFile = null;
        this.ocrResults = null;
        document.getElementById('uploadArea').style.display = 'block';
        document.getElementById('imagePreview').style.display = 'none';
        document.getElementById('ocrResults').style.display = 'none';
        document.getElementById('imageInput').value = '';
    }
}

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    window.ocrProcessor = new OCRProcessor();
});
```

### 4.2 Backend 구현

#### Django Views
```python
# views.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
import os
from .services.ocr_service import OCRService
from .services.text_parser import LabelTextParser

logger = logging.getLogger(__name__)

@login_required
@csrf_exempt
def ocr_process(request):
    """
    업로드된 이미지를 OCR 처리하여 텍스트 추출 및 필드 매핑
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '잘못된 요청 방식'})
    
    try:
        # 파일 검증
        if 'image' not in request.FILES:
            return JsonResponse({'success': False, 'error': '이미지 파일이 없습니다.'})
        
        image_file = request.FILES['image']
        label_id = request.POST.get('label_id')
        
        # 파일 크기 및 형식 검증
        if image_file.size > 5 * 1024 * 1024:  # 5MB
            return JsonResponse({'success': False, 'error': '파일 크기는 5MB 이하여야 합니다.'})
        
        if not image_file.content_type.startswith('image/'):
            return JsonResponse({'success': False, 'error': '이미지 파일만 업로드 가능합니다.'})
        
        # OCR 결과 객체 생성
        ocr_result = OCRResult.objects.create(
            user_id=request.user,
            label_id_id=label_id if label_id else None,
            original_image=image_file,
            status='processing'
        )
        
        try:
            # OCR 서비스 실행
            ocr_service = OCRService()
            text_data = ocr_service.extract_text(ocr_result.original_image.path)
            
            # 텍스트 파싱 및 필드 매핑
            parser = LabelTextParser()
            field_mappings = parser.parse_label_text(text_data['text'])
            
            # 결과 저장
            ocr_result.raw_text = text_data['text']
            ocr_result.structured_data = {
                'field_mappings': field_mappings,
                'ocr_metadata': text_data.get('metadata', {})
            }
            ocr_result.confidence_score = text_data.get('confidence', 0.0)
            ocr_result.status = 'completed'
            ocr_result.save()
            
            # 필드별 매핑 결과 저장
            for field_name, mapping in field_mappings.items():
                if mapping.get('text'):
                    OCRFieldMapping.objects.create(
                        ocr_result=ocr_result,
                        field_name=field_name,
                        extracted_text=mapping['text'],
                        confidence=mapping.get('confidence', 0.0)
                    )
            
            return JsonResponse({
                'success': True,
                'data': {
                    'ocr_id': ocr_result.id,
                    'raw_text': text_data['text'],
                    'field_mappings': field_mappings,
                    'confidence': text_data.get('confidence', 0.0)
                }
            })
            
        except Exception as e:
            ocr_result.status = 'failed'
            ocr_result.save()
            raise e
            
    except Exception as e:
        logger.error(f"OCR 처리 오류: {str(e)}")
        return JsonResponse({
            'success': False, 
            'error': f'OCR 처리 중 오류가 발생했습니다: {str(e)}'
        })
```

#### OCR 서비스 클래스
```python
# services/ocr_service.py
from google.cloud import vision
import io
import os
from PIL import Image, ImageEnhance
import cv2
import numpy as np
from django.conf import settings

class OCRService:
    def __init__(self):
        self.vision_client = None
        if hasattr(settings, 'GOOGLE_CLOUD_VISION_CREDENTIALS'):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.GOOGLE_CLOUD_VISION_CREDENTIALS
            self.vision_client = vision.ImageAnnotatorClient()
    
    def extract_text(self, image_path):
        """
        이미지에서 텍스트 추출
        """
        try:
            # 이미지 전처리
            processed_image_path = self.preprocess_image(image_path)
            
            # Primary: Google Cloud Vision API
            if self.vision_client:
                result = self.extract_with_google_vision(processed_image_path)
                if result['success']:
                    return result
            
            # Fallback: Tesseract
            return self.extract_with_tesseract(processed_image_path)
            
        except Exception as e:
            raise Exception(f"OCR 처리 실패: {str(e)}")
    
    def preprocess_image(self, image_path):
        """
        OCR 정확도 향상을 위한 이미지 전처리
        """
        # OpenCV로 이미지 읽기
        image = cv2.imread(image_path)
        
        # 그레이스케일 변환
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 노이즈 제거
        denoised = cv2.medianBlur(gray, 3)
        
        # 대비 향상
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 이진화
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 처리된 이미지 저장
        processed_path = image_path.replace('.', '_processed.')
        cv2.imwrite(processed_path, binary)
        
        return processed_path
    
    def extract_with_google_vision(self, image_path):
        """
        Google Cloud Vision API를 사용한 텍스트 추출
        """
        try:
            with io.open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # 문서 텍스트 검출 (구조 정보 포함)
            response = self.vision_client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Google Vision API 오류: {response.error.message}')
            
            # 전체 텍스트
            full_text = response.full_text_annotation.text if response.full_text_annotation else ""
            
            # 블록별 텍스트 (구조 정보)
            blocks = []
            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        block_text = ""
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                block_text += word_text + " "
                        
                        if block_text.strip():
                            blocks.append({
                                'text': block_text.strip(),
                                'confidence': block.confidence,
                                'bounding_box': self.get_bounding_box(block.bounding_box)
                            })
            
            return {
                'success': True,
                'text': full_text,
                'confidence': response.full_text_annotation.pages[0].confidence if response.full_text_annotation and response.full_text_annotation.pages else 0.0,
                'metadata': {
                    'blocks': blocks,
                    'engine': 'google_vision'
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_with_tesseract(self, image_path):
        """
        Tesseract를 사용한 텍스트 추출 (Fallback)
        """
        try:
            import pytesseract
            from PIL import Image
            
            # Tesseract 설정 (한글 지원)
            config = '--oem 3 --psm 6 -l kor+eng'
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, config=config)
            
            return {
                'success': True,
                'text': text,
                'confidence': 0.8,  # Tesseract는 전체 신뢰도 제공 안함
                'metadata': {
                    'engine': 'tesseract'
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Tesseract 처리 실패: {str(e)}'
            }
    
    def get_bounding_box(self, bounding_box):
        """
        Google Vision API의 bounding_box를 좌표로 변환
        """
        vertices = []
        for vertex in bounding_box.vertices:
            vertices.append({'x': vertex.x, 'y': vertex.y})
        return vertices
```

#### 텍스트 파싱 엔진
```python
# services/text_parser.py
import re
from typing import Dict, Any

class LabelTextParser:
    def __init__(self):
        # 필드별 키워드 패턴 정의
        self.field_patterns = {
            'prdlst_nm': {
                'keywords': ['제품명', '상품명', '품명'],
                'patterns': [
                    r'제품명\s*[:\-]?\s*([^\n\r]+)',
                    r'상품명\s*[:\-]?\s*([^\n\r]+)',
                    r'품명\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'prdlst_dcnm': {
                'keywords': ['식품유형', '식품의 유형'],
                'patterns': [
                    r'식품유형\s*[:\-]?\s*([^\n\r]+)',
                    r'식품의\s*유형\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'content_weight': {
                'keywords': ['내용량', '중량', '용량'],
                'patterns': [
                    r'내용량\s*[:\-]?\s*([0-9,]+\s*[gkmlL]+)',
                    r'중량\s*[:\-]?\s*([0-9,]+\s*[gkmlL]+)',
                    r'(\d+(?:,\d+)*(?:\.\d+)?\s*(?:g|kg|ml|L|mL))'
                ]
            },
            'country_of_origin': {
                'keywords': ['원산지', '원산국'],
                'patterns': [
                    r'원산지\s*[:\-]?\s*([^\n\r]+)',
                    r'원산국\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'bssh_nm': {
                'keywords': ['제조원', '제조업체', '제조사'],
                'patterns': [
                    r'제조원\s*[:\-]?\s*([^\n\r]+)',
                    r'제조업체\s*[:\-]?\s*([^\n\r]+)',
                    r'제조사\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'storage_method': {
                'keywords': ['보관방법', '보존방법', '저장방법'],
                'patterns': [
                    r'보관방법\s*[:\-]?\s*([^\n\r]+)',
                    r'보존방법\s*[:\-]?\s*([^\n\r]+)',
                    r'저장방법\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'rawmtrl_nm': {
                'keywords': ['원재료명', '원료', '성분'],
                'patterns': [
                    r'원재료명?\s*[:\-]?\s*([^\n\r]+(?:\n[^가-힣]*)*)',
                    r'원료\s*[:\-]?\s*([^\n\r]+)',
                    r'성분\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'cautions': {
                'keywords': ['주의사항', '주의', '경고'],
                'patterns': [
                    r'주의사항\s*[:\-]?\s*([^\n\r]+(?:\n[^가-힣]*)*)',
                    r'주의\s*[:\-]?\s*([^\n\r]+)',
                    r'경고\s*[:\-]?\s*([^\n\r]+)'
                ]
            },
            'pog_daycnt': {
                'keywords': ['소비기한', '유통기한', '제조일자'],
                'patterns': [
                    r'소비기한\s*[:\-]?\s*([^\n\r]+)',
                    r'유통기한\s*[:\-]?\s*([^\n\r]+)',
                    r'제조일자\s*[:\-]?\s*([^\n\r]+)',
                    r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})',
                    r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)'
                ]
            }
        }
    
    def parse_label_text(self, text: str) -> Dict[str, Any]:
        """
        OCR로 추출된 텍스트를 분석하여 각 필드별로 분류
        """
        if not text:
            return {}
        
        results = {}
        
        for field_name, config in self.field_patterns.items():
            extracted_data = self.extract_field_data(text, config)
            if extracted_data:
                results[field_name] = extracted_data
        
        return results
    
    def extract_field_data(self, text: str, config: Dict) -> Dict[str, Any]:
        """
        특정 필드에 대한 데이터 추출
        """
        best_match = None
        highest_confidence = 0.0
        
        # 정규식 패턴으로 매칭 시도
        for pattern in config['patterns']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                extracted_text = match.group(1).strip() if match.groups() else match.group(0).strip()
                
                if extracted_text:
                    # 신뢰도 계산
                    confidence = self.calculate_confidence(extracted_text, config)
                    
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        best_match = {
                            'text': self.clean_extracted_text(extracted_text),
                            'confidence': confidence,
                            'matched_pattern': pattern
                        }
        
        return best_match
    
    def calculate_confidence(self, text: str, config: Dict) -> float:
        """
        추출된 텍스트의 신뢰도 계산
        """
        confidence = 0.5  # 기본 신뢰도
        
        # 키워드 포함 여부로 신뢰도 증가
        for keyword in config['keywords']:
            if keyword in text:
                confidence += 0.2
        
        # 텍스트 길이 고려 (너무 짧거나 길면 신뢰도 감소)
        if 2 <= len(text) <= 100:
            confidence += 0.1
        elif len(text) > 200:
            confidence -= 0.2
        
        # 특수 문자만 있으면 신뢰도 감소
        if re.match(r'^[^\w\s가-힣]+$', text):
            confidence -= 0.3
        
        return min(1.0, max(0.0, confidence))
    
    def clean_extracted_text(self, text: str) -> str:
        """
        추출된 텍스트 정리 (불필요한 문자 제거 등)
        """
        # 앞뒤 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로 통합
        text = re.sub(r'\s+', ' ', text)
        
        # 특정 불필요한 문자 제거
        text = re.sub(r'[:\-]\s*$', '', text)  # 끝의 콜론, 하이픈 제거
        
        return text
```

### 4.3 UI 통합

#### 표시사항 작성 화면에 OCR 버튼 추가
```html
<!-- label_creation.html에 추가 -->
<div class="d-flex align-items-center ms-auto label-header-actions" style="gap: 10px;">
  <!-- 기존 버튼들... -->
  
  <!-- OCR 업로드 버튼 추가 -->
  <button type="button" class="btn btn-outline-info btn-sm" 
          data-bs-toggle="modal" data-bs-target="#ocrUploadModal"
          title="사진으로 자동 입력">
    <i class="fas fa-camera"></i> 사진 인식
  </button>
  
  <!-- 기존 저장/미리보기 버튼들... -->
</div>
```

## 5. 성능 최적화 방안

### 5.1 이미지 최적화
```python
def optimize_image_for_ocr(image_path):
    """
    OCR 처리를 위한 이미지 최적화
    """
    from PIL import Image
    
    with Image.open(image_path) as img:
        # 적절한 해상도로 리사이징 (300 DPI 권장)
        if img.width > 2000:
            ratio = 2000 / img.width
            new_size = (2000, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # JPEG 품질 최적화
        optimized_path = image_path.replace('.', '_optimized.')
        img.save(optimized_path, format='JPEG', quality=95, optimize=True)
        
        return optimized_path
```

### 5.2 비동기 처리
```python
# Celery를 사용한 비동기 OCR 처리
from celery import shared_task

@shared_task
def process_ocr_async(ocr_result_id):
    """
    OCR 처리를 백그라운드에서 비동기로 실행
    """
    try:
        ocr_result = OCRResult.objects.get(id=ocr_result_id)
        ocr_service = OCRService()
        
        # OCR 처리
        text_data = ocr_service.extract_text(ocr_result.original_image.path)
        
        # 결과 저장
        parser = LabelTextParser()
        field_mappings = parser.parse_label_text(text_data['text'])
        
        ocr_result.raw_text = text_data['text']
        ocr_result.structured_data = {'field_mappings': field_mappings}
        ocr_result.status = 'completed'
        ocr_result.save()
        
        # 웹소켓으로 실시간 결과 전송
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'ocr_user_{ocr_result.user_id.id}',
            {
                'type': 'ocr_complete',
                'data': {
                    'ocr_id': ocr_result.id,
                    'field_mappings': field_mappings
                }
            }
        )
        
    except Exception as e:
        ocr_result.status = 'failed'
        ocr_result.save()
        raise e
```

## 6. 보안 고려사항

### 6.1 파일 업로드 보안
```python
def validate_uploaded_image(image_file):
    """
    업로드된 이미지 파일 보안 검증
    """
    from PIL import Image
    import magic
    
    # MIME 타입 검증
    file_type = magic.from_buffer(image_file.read(1024), mime=True)
    if not file_type.startswith('image/'):
        raise ValueError('이미지 파일이 아닙니다.')
    
    # 이미지 파일 구조 검증
    try:
        with Image.open(image_file) as img:
            img.verify()
    except Exception:
        raise ValueError('손상된 이미지 파일입니다.')
    
    # 파일 크기 제한
    if image_file.size > 5 * 1024 * 1024:
        raise ValueError('파일 크기가 너무 큽니다.')
```

### 6.2 개인정보 보호
```python
def anonymize_ocr_data(text):
    """
    OCR 추출 텍스트에서 개인정보 마스킹
    """
    import re
    
    # 전화번호 마스킹
    text = re.sub(r'(\d{2,3}-)?\d{3,4}-\d{4}', '***-****-****', text)
    
    # 이메일 마스킹
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***', text)
    
    return text
```

## 7. 테스트 전략

### 7.1 단위 테스트
```python
# tests/test_ocr_service.py
import unittest
from django.test import TestCase
from label.services.ocr_service import OCRService
from label.services.text_parser import LabelTextParser

class OCRServiceTest(TestCase):
    def setUp(self):
        self.ocr_service = OCRService()
        self.parser = LabelTextParser()
    
    def test_text_extraction(self):
        """텍스트 추출 테스트"""
        # 테스트 이미지로 OCR 실행
        result = self.ocr_service.extract_text('test_images/sample_label.jpg')
        self.assertTrue(result['success'])
        self.assertIn('제품명', result['text'])
    
    def test_field_parsing(self):
        """필드 파싱 테스트"""
        sample_text = """
        제품명: 테스트 과자
        식품유형: 과자류
        내용량: 100g
        원산지: 대한민국
        """
        
        results = self.parser.parse_label_text(sample_text)
        
        self.assertEqual(results['prdlst_nm']['text'], '테스트 과자')
        self.assertEqual(results['prdlst_dcnm']['text'], '과자류')
        self.assertEqual(results['content_weight']['text'], '100g')
```

## 8. 비용 및 운영 고려사항

### 8.1 OCR API 비용 관리
```python
class OCRUsageTracker:
    """OCR 사용량 추적 및 비용 관리"""
    
    @staticmethod
    def track_usage(user, service_type, cost=0):
        OCRUsage.objects.create(
            user=user,
            service_type=service_type,
            cost=cost,
            timestamp=timezone.now()
        )
    
    @staticmethod
    def get_monthly_usage(user):
        """사용자의 월간 OCR 사용량 조회"""
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        
        usage = OCRUsage.objects.filter(
            user=user,
            timestamp__gte=start_date
        ).aggregate(
            total_requests=Count('id'),
            total_cost=Sum('cost')
        )
        
        return usage
```

### 8.2 캐싱 전략
```python
from django.core.cache import cache

def get_cached_ocr_result(image_hash):
    """이미지 해시 기반 OCR 결과 캐싱"""
    cache_key = f'ocr_result_{image_hash}'
    return cache.get(cache_key)

def cache_ocr_result(image_hash, result, timeout=3600):
    """OCR 결과 캐시 저장"""
    cache_key = f'ocr_result_{image_hash}'
    cache.set(cache_key, result, timeout)
```

## 9. 결론 및 권장사항

### 9.1 구현 우선순위
1. **Phase 1**: Google Vision API + 기본 필드 파싱
2. **Phase 2**: UI 개선 + 사용자 피드백 반영
3. **Phase 3**: Tesseract 통합 + 성능 최적화

### 9.2 예상 효과
- **작업 시간 단축**: 70-80% 시간 절약
- **정확성 향상**: 95% 이상 OCR 정확도
- **사용자 만족도**: 자동화를 통한 편의성 증대

### 9.3 위험 요소 및 대응
- **OCR 정확도 한계**: 수동 검토 및 수정 기능 필수
- **API 비용**: 월간 사용량 제한 및 Fallback 방식 구현
- **개인정보 이슈**: 데이터 마스킹 및 자동 삭제 정책

이 OCR 시스템을 통해 사용자들이 기존 표시사항 사진만으로도 빠르고 정확하게 새로운 표시사항을 작성할 수 있게 될 것입니다.
