"""
OCR 서비스 - GPT-4o mini 기반
이미지에서 식품 표시사항 필드를 추출하고 신뢰도에 따라 후보를 제공합니다.
"""
import io
import base64
import json
import logging
from PIL import Image, ImageOps
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 한국 식품 표시사항 이미지에서 정보를 추출하는 전문가입니다.

아래 필드들을 이미지에서 찾아 추출하세요:
- prdlst_nm: 제품명 (예: 홍삼정과, 참치통조림)
- prdlst_dcnm: 식품유형 (예: 과자류, 음료류, 절임식품)
- content_weight: 내용량 (예: 200g, 500mL, 1kg)
- weight_calorie: 내용량(열량) (예: 100kcal/100g, 1회 제공량 200mL당 50kcal)
- prdlst_report_no: 품목보고번호 (예: 20240123456789)
- country_of_origin: 원산지 (예: 대한민국, 중국산)
- bssh_nm: 제조원 소재지 (업체명 + 주소 전체)
- distributor_address: 유통전문판매원 소재지 (업체명 + 주소 전체)
- repacker_address: 소분원 소재지 (업체명 + 주소 전체, 없으면 none)
- importer_address: 수입원 소재지 (업체명 + 주소 전체, 없으면 none)
- storage_method: 보관방법 (예: 냉장보관, 직사광선을 피해 실온 보관)
- rawmtrl_nm: 원재료명 (원재료명 항목의 내용 전체)
- ingredient_info: 특정성분 함량 (예: 홍삼농축액 30%)
- frmlc_mtrqlt: 포장재질 (예: PP, PE, 종이)
- pog_daycnt: 소비기한 (예: 제조일로부터 12개월, 2025.12.31)
- cautions: 주의사항 (알레르기, 섭취 주의 등)
- additional_info: 기타 표시사항 (위 항목에 해당하지 않는 기타 안내문구)

응답 규칙:
- 텍스트가 명확하게 읽히면: {"value": "실제추출값", "confidence": "high"}
- 불명확하거나 여러 해석이 가능하면: {"value": null, "confidence": "low", "candidates": ["가능한값1", "가능한값2", "가능한값3"]}
- 이미지에 해당 항목이 없으면: {"value": null, "confidence": "none"}

반드시 아래 키를 모두 포함한 JSON으로만 응답하세요:
{
  "prdlst_nm": {"value": null, "confidence": "none"},
  "prdlst_dcnm": {"value": null, "confidence": "none"},
  "content_weight": {"value": null, "confidence": "none"},
  "weight_calorie": {"value": null, "confidence": "none"},
  "prdlst_report_no": {"value": null, "confidence": "none"},
  "country_of_origin": {"value": null, "confidence": "none"},
  "bssh_nm": {"value": null, "confidence": "none"},
  "distributor_address": {"value": null, "confidence": "none"},
  "repacker_address": {"value": null, "confidence": "none"},
  "importer_address": {"value": null, "confidence": "none"},
  "storage_method": {"value": null, "confidence": "none"},
  "rawmtrl_nm": {"value": null, "confidence": "none"},
  "ingredient_info": {"value": null, "confidence": "none"},
  "frmlc_mtrqlt": {"value": null, "confidence": "none"},
  "pog_daycnt": {"value": null, "confidence": "none"},
  "cautions": {"value": null, "confidence": "none"},
  "additional_info": {"value": null, "confidence": "none"}
}
"""


def preprocess_image(image_file, max_size=1024):
    """이미지를 리사이즈하고 base64로 인코딩합니다."""
    img = Image.open(image_file)

    # 스마트폰 EXIF 회전 정보 반영
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # JPEG 저장을 위해 RGB 변환
    if img.mode not in ('RGB',):
        img = img.convert('RGB')

    # 비율 유지하며 리사이즈
    img.thumbnail((max_size, max_size), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def extract_label_from_image(image_file):
    """
    GPT-4o mini를 사용해 표시사항 이미지에서 필드를 추출합니다.

    Returns:
        dict: {
            "success": True,
            "data": {
                "prdlst_nm": {"value": "...", "confidence": "high"},
                "rawmtrl_nm": {"value": null, "confidence": "low", "candidates": [...]},
                ...
            }
        }
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        image_data = preprocess_image(image_file)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": "이 식품 표시사항 이미지에서 정보를 추출해주세요."
                        }
                    ]
                }
            ],
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {"success": True, "data": result}

    except Exception as e:
        logger.exception("OCR 처리 실패")
        return {"success": False, "error": str(e)}
