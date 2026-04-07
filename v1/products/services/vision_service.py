"""
Vision AI 서비스 - GPT-4o mini 기반 문서 분석
 
두 가지 그룹으로 분기:
  Group A: 품목제조보고서·표시사항·원산지증명서 → 원재료·배합비 등 정보 추출
  Group B: 시험성적서(COA)                     → 검사 항목 추출 + 적합성 판정
 
결과는 ProductDocument.metadata JSONField에 저장 (모델 변경 없음):
  metadata['ai_status']         : PENDING | PROCESSING | COMPLETED | FAILED
  metadata['ai_group']          : A | B
  metadata['extracted_data']    : AI 추출 결과 dict
  metadata['compliance_status'] : PASS | WARNING | FAIL  (Group B 전용)
  metadata['ai_error']          : 오류 메시지 (FAILED 시)
"""
 
import base64
import io
import json
import logging
import os
import threading
 
from django.conf import settings
from openai import OpenAI
 
logger = logging.getLogger(__name__)
 
# ── 문서 그룹 B 판정 키워드 ──
_GROUP_B_KEYWORDS = ['시험', '성적', '성적서', 'coa', 'test', 'analysis', '분석', '검사결과', '검사성적']
 
# ── Group A 프롬프트: 제품 정보 추출 ──
GROUP_A_PROMPT = """당신은 한국 식품 표시사항, 품목제조보고서, 원산지증명서 등에서 정보를 추출하는 전문가입니다.

아래 지침을 반드시 따르세요:

1. **원재료명 및 함량**: 
   - "원재료명" 또는 "원재료명 및 함량" 항목에서 정확히 추출
   - 각 원재료와 비율(%)을 정확히 대응시키기
   - 예: "히드록시프로필전분 87%" → raw_materials에 추가, blend_ratios에 {"히드록시프로필전분": "87%"} 추가
   - 괄호 안의 설명(예: "탈지분유(우유)")도 포함시키기

2. **제조업소명**: 
   - "제조업소명" 또는 "제조" 항목에서 찾기
   - 회사명과 국가를 모두 포함 (예: "인그리디언(주) 태국")

3. **원산지**:
   - "원산지" 항목에서 각 원재료의 원산지 추출

4. **보관방법**: 
   - "보관방법" 항목에서 전문 추출 (청소년 제품 보관법 등)

5. **없는 항목은 반드시 null로 표기**

응답 형식 (JSON만 응답):
{
  "product_name": "제품명",
  "food_type": "식품유형",
  "manufacturer": "제조업소명",
  "raw_materials": ["원재료1", "원재료2"],
  "blend_ratios": {"원재료1": "87%", "원재료2": "11%"},
  "origins": {"원재료1": "국산", "원재료2": "태국"},
  "allergens": ["대두", "우유"],
  "storage_method": "보관방법 상세",
  "shelf_life": "유통기한"
}

주의: 반드시 JSON만 응답하세요."""
 
# ── Group B 프롬프트: 시험성적서 적합성 판정 ──
GROUP_B_PROMPT = """당신은 한국 식품 시험성적서(COA)에서 검사 결과를 추출하는 전문가입니다.
아래 문서에서 모든 검사 항목과 결과를 빠짐없이 추출하세요.
판정(judgment)은 반드시 PASS 또는 FAIL 중 하나로만 표기하세요.
반드시 JSON으로만 응답하세요.
 
{
  "product_name": "제품명 또는 null",
  "manufacturer": "제조사명 또는 null",
  "test_institution": "시험기관명 또는 null",
  "test_date": "YYYY-MM-DD 또는 null",
  "overall_judgment": "PASS 또는 FAIL",
  "test_items": [
    {
      "item_name": "세균수",
      "standard": "n=5, c=2, m=10^4, M=10^5",
      "result": "음성",
      "judgment": "PASS"
    }
  ]
}"""
 
 
def infer_ai_group(type_name: str, type_code: str = '') -> str:
    """DocumentType 이름/코드로 AI 그룹 추론. B=시험성적서, A=그 외."""
    combined = (type_name + ' ' + type_code).lower()
    if any(kw in combined for kw in _GROUP_B_KEYWORDS):
        return 'B'
    return 'A'
 
 
def _pdf_to_base64_images(file_path: str, max_pages: int = 2) -> list:
    """PDF → JPEG Base64 이미지 목록 변환 (PyMuPDF 사용)."""
    images = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        pages_to_process = min(max_pages, len(doc))
        for page_num in range(pages_to_process):
            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)  # 2x 해상도 렌더링
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes('jpeg')
            images.append(base64.b64encode(img_bytes).decode('utf-8'))
        doc.close()
    except ImportError:
        logger.error("PyMuPDF(fitz) 미설치. requirements.txt에 PyMuPDF를 추가하세요.")
    except Exception:
        logger.exception("PDF 변환 실패 (file=%s)", file_path)
    return images
 
 
def _image_to_base64(file_path: str) -> str | None:
    """이미지 파일 → JPEG Base64 문자열 변환."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(file_path)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((1024, 1024), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception:
        logger.exception("이미지 변환 실패 (file=%s)", file_path)
        return None
 
 
def _call_vision_api(images_b64: list, prompt: str) -> dict:
    """OpenAI gpt-4o-mini Vision API 호출 및 JSON 파싱."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
 
    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img}",
                "detail": "high",
            },
        }
        for img in images_b64
    ]
    content.append({"type": "text", "text": "이 문서에서 정보를 추출해주세요."})
 
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
 
 
def _compliance_check(extracted: dict) -> str:
    """
    Group B 후처리: PASS / WARNING / FAIL 판정.
      FAIL    - test_items 중 FAIL 항목 존재 또는 overall_judgment == FAIL
      WARNING - test_items 비어 있거나 overall_judgment 누락
      PASS    - 모든 항목 통과 + overall_judgment == PASS
    """
    test_items = extracted.get('test_items') or []
    overall = str(extracted.get('overall_judgment', '')).upper()
 
    if not test_items:
        return 'WARNING'
 
    has_fail = any(str(item.get('judgment', '')).upper() == 'FAIL' for item in test_items)
    if has_fail or overall == 'FAIL':
        return 'FAIL'
 
    if overall == 'PASS':
        return 'PASS'
 
    return 'WARNING'
 
 
def process_document_vision(document_id: int) -> None:
    """
    Vision AI 처리 메인 함수.
    ProductDocument.metadata에 결과 저장 (모델 변경 없음).
    백그라운드 스레드에서 실행됨.
    """
    from v1.products.models import ProductDocument  # 순환 import 방지
 
    try:
        doc = ProductDocument.objects.get(pk=document_id)
    except ProductDocument.DoesNotExist:
        logger.error("ProductDocument %s 없음", document_id)
        return
 
    meta = dict(doc.metadata) if doc.metadata else {}
    meta['ai_status'] = 'PROCESSING'
    doc.metadata = meta
    doc.save(update_fields=['metadata'])
 
    try:
        file_path = doc.file.path
        ext = os.path.splitext(file_path)[1].lower()
        ai_group = meta.get('ai_group', 'A')
 
        # 파일 → 이미지 변환 (PDF는 최대 2페이지만 처리 - 토큰 폭탄 방지)
        if ext == '.pdf':
            images_b64 = _pdf_to_base64_images(file_path, max_pages=2)
        else:
            img = _image_to_base64(file_path)
            images_b64 = [img] if img else []
 
        if not images_b64:
            raise ValueError("처리 가능한 이미지를 생성하지 못했습니다.")
 
        prompt = GROUP_B_PROMPT if ai_group == 'B' else GROUP_A_PROMPT
        extracted = _call_vision_api(images_b64, prompt)
 
        meta['ai_status'] = 'COMPLETED'
        meta['extracted_data'] = extracted
        if ai_group == 'B':
            meta['compliance_status'] = _compliance_check(extracted)
 
    except Exception:
        logger.exception("Vision AI 처리 실패 (document_id=%s)", document_id)
        meta['ai_status'] = 'FAILED'
        import traceback
        meta['ai_error'] = traceback.format_exc()[-500:]  # 최대 500자
 
    doc.metadata = meta
    doc.save(update_fields=['metadata'])
 
 
def process_document_vision_async(document_id: int) -> None:
    """백그라운드 스레드에서 Vision AI 처리 실행."""
    t = threading.Thread(
        target=process_document_vision,
        args=(document_id,),
        daemon=True,
    )
    t.start()