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
 
 
# PDF 에서 글자를 이만큼도 못 뽑으면 텍스트 레이어가 없는 것(스캔본)으로 본다.
# 도장·서명만 벡터로 들어간 스캔 PDF 가 몇 글자를 흘리는 경우가 있어서, 있고
# 없고가 아니라 양으로 가른다.
PDF_TEXT_MIN_CHARS = 40
# 프롬프트에 실을 원문의 상한. 품목제조보고서 두 장이면 보통 3~5천 자다.
# 상한이 없으면 표가 빽빽한 문서에서 입력 토큰이 폭발한다.
PDF_TEXT_MAX_CHARS = 12000


def extract_pdf_text(file_path: str, max_pages: int = 2) -> str:
    """
    PDF 에 박혀 있는 텍스트 레이어를 그대로 읽는다.

    **이걸 안 쓰면 공짜로 정확한 글자를 버리는 셈이다.** 인쇄용 라벨 도안과
    품목제조보고서는 대개 문서 프로그램에서 뽑은 PDF 라 글자가 그대로 들어 있다.
    지금까지는 그걸 그림으로 되돌려(_pdf_to_base64_images) 모델에게 다시 읽혔다 —
    확실한 원문을 버리고 오독 가능성이 있는 경로로 돌아간 것이다.

    스캔한 PDF 는 텍스트 레이어가 없으므로 빈 문자열이 나온다. 그때는 예전처럼
    그림으로만 읽는다.

    Returns: 페이지별 텍스트를 이어 붙인 문자열 (없으면 '')
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error('PyMuPDF(fitz) 미설치 — PDF 텍스트 레이어를 읽지 못한다')
        return ''

    try:
        with fitz.open(file_path) as doc:
            parts = []
            for page_num in range(min(max_pages, len(doc))):
                text = (doc[page_num].get_text() or '').strip()
                if text:
                    parts.append(text)
        joined = '\n\n'.join(parts).strip()
    except Exception:
        logger.exception('PDF 텍스트 레이어 추출 실패 (file=%s)', file_path)
        return ''

    # 너무 적으면 스캔본이다. 몇 글자를 "원문" 이라고 넘기면 모델이 그 조각을
    # 믿고 나머지를 지어낼 수 있다.
    return joined if len(joined) >= PDF_TEXT_MIN_CHARS else ''


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
 
 
def _call_vision_api(images_b64: list, prompt: str, pdf_text: str = '') -> dict:
    """
    OpenAI gpt-4o-mini Vision API 호출 및 JSON 파싱.

    pdf_text 가 있으면 함께 넘긴다 — PDF 에 박혀 있는 원문이라 그림에서 읽은
    글자보다 언제나 정확하다. 모델은 배치 판단에만 그림을 쓴다.
    """
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
    if pdf_text:
        # 글자는 이쪽이 정답이다. 모델은 "어느 항목이 어느 칸인지" 를 판단하는 데
        # 그림을 쓰고, 값 자체는 원문에서 그대로 옮기게 한다. 그림만 줬을 때
        # 업체명·지명의 획을 잘못 읽던 것이 여기서 사라진다.
        content.append({
            "type": "text",
            "text": (
                "아래는 이 PDF 에 실제로 박혀 있는 텍스트입니다. "
                "**글자는 이 원문을 그대로 옮기시오** — 그림에서 다시 읽지 마시오. "
                "그림은 어느 글자가 어느 항목의 값인지(표의 행·열, 칸의 배치)를 "
                "판단하는 데만 쓰시오. "
                "원문에 없는 값은 지어내지 마시오.\n\n"
                f"=== PDF 원문 ===\n{pdf_text[:PDF_TEXT_MAX_CHARS]}"
            ),
        })
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
        #
        # PDF 는 글자를 먼저 뽑는다. 문서 프로그램에서 만든 PDF 는 원문이 그대로
        # 들어 있어서, 그림으로 되돌려 읽히면 확실한 값을 버리고 오독 가능성이
        # 있는 경로로 돌아가게 된다. 스캔본이면 빈 문자열이 오고 예전 그대로다.
        pdf_text = ''
        if ext == '.pdf':
            pdf_text = extract_pdf_text(file_path, max_pages=2)
            images_b64 = _pdf_to_base64_images(file_path, max_pages=2)
        else:
            img = _image_to_base64(file_path)
            images_b64 = [img] if img else []
 
        if not images_b64:
            raise ValueError("처리 가능한 이미지를 생성하지 못했습니다.")
 
        prompt = GROUP_B_PROMPT if ai_group == 'B' else GROUP_A_PROMPT
        extracted = _call_vision_api(images_b64, prompt, pdf_text=pdf_text)
 
        meta['ai_status'] = 'COMPLETED'
        meta['extracted_data'] = extracted
        # 원문을 썼는지 남긴다. 정확도를 나눠 볼 때 "그림만 봤을 때" 와
        # "원문을 함께 봤을 때" 를 구분할 수 없으면 효과를 잴 수 없다.
        meta['pdf_text_used'] = bool(pdf_text)
        if ai_group == 'B':
            meta['compliance_status'] = _compliance_check(extracted)
 
    except Exception:
        logger.exception("Vision AI 처리 실패 (document_id=%s)", document_id)
        meta['ai_status'] = 'FAILED'
        import traceback
        meta['ai_error'] = traceback.format_exc()[-500:]  # 최대 500자
 
    doc.metadata = meta
    doc.save(update_fields=['metadata'])
 
 
def _process_and_close(document_id: int) -> None:
    """
    스레드에서 도는 몫. 끝나면 **DB 커넥션을 닫는다.**

    요청 밖에서 연 커넥션은 아무도 닫아 주지 않는다 - Django 는 요청이 끝날 때만
    정리한다. 이걸 빠뜨린 백그라운드 작업들 때문에 커넥션이 쌓여 계정 한도(79)를
    넘겼고, 그 순간 사이트 전체가 500 이 났다. 문서 판독은 수십 초가 걸려서
    커넥션을 오래 잡고 있는 쪽이라 특히 그렇다.

    process_document_vision 자체에 넣지 않는 이유는, 그쪽은 요청 안에서 그대로
    불릴 수도 있어서다. 그때 닫으면 남의 커넥션을 끊는다.
    """
    from django.db import connections
    try:
        process_document_vision(document_id)
    finally:
        try:
            connections.close_all()
        except Exception:
            logger.exception("Vision AI 커넥션 정리 실패 (document_id=%s)", document_id)


def process_document_vision_async(document_id: int) -> None:
    """백그라운드 스레드에서 Vision AI 처리 실행."""
    t = threading.Thread(
        target=_process_and_close,
        args=(document_id,),
        daemon=True,
    )
    t.start()