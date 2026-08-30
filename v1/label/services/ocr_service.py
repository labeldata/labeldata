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
- prdlst_dcnm: 식품유형 (예: 과자류, 음료류, 즉석섭취식품)
- content_weight: 내용량. 열량이 괄호로 함께 적혀 있으면 **그대로 포함**한다
    예: "139 g(182 kcal)", "200g", "500mL"
- weight_calorie: 내용량과 별도 칸에 열량만 따로 적혀 있을 때만
    예: 100kcal/100g. 내용량 칸에 함께 있으면 여기는 none
- prdlst_report_no: 품목보고번호 (예: 20240123456789, 20170415080-1271)
- country_of_origin: 원산지. 원재료마다 붙은 원산지가 아니라 제품 전체의 원산지 칸
- bssh_nm: 제조원 / **업소명 및 소재지** / 제조업소명 (업체명 + 주소 전체)
    라벨마다 이름이 다르다: "제조원", "업소명 및 소재지", "제조업소명", "제조사"
- distributor_address: 유통전문판매원 소재지 (업체명 + 주소 전체)
- repacker_address: 소분원 소재지 (업체명 + 주소 전체, 없으면 none)
- importer_address: 수입원 소재지 (업체명 + 주소 전체, 없으면 none)
- storage_method: 보관방법 (예: 냉장(0~10 ℃)에서 보관, 직사광선을 피해 실온 보관)
- rawmtrl_nm: 원재료명 항목의 내용 **전체**. 길어도 끊지 말고 끝까지 적는다.
    괄호와 대괄호 안의 하위 원료·원산지·함량을 모두 그대로 옮긴다.
    **다만 아래 allergens 에 해당하는 "○○ 함유" 문구는 여기서 뺀다**
- allergens: 알레르기 유발물질 주의문구. 원재료명 아래나 옆에 **별도 칸**(대개
    검은 바탕에 흰 글씨)으로 "우유, 대두, 밀, 토마토 함유" 처럼 적힌다.
    "함유" 를 뺀 물질 이름만 쉼표로 이어 적는다. 예: "우유, 대두, 밀, 토마토"
    같은 제조시설 문구(주의사항)는 여기가 아니라 cautions 다
- ingredient_info: 특정성분 함량 (예: 홍삼농축액 30%)
- frmlc_mtrqlt: 포장재질 (예: PET(용기, 리드지), PE(드레싱), PP, 종이)
- pog_daycnt: 소비기한 / 유통기한 (예: 별도표기일까지, 제조일로부터 12개월)
- cautions: 주의사항 칸의 내용 전체. 같은 제조시설 혼입 가능 문구,
    섭취·보관 주의, 용기 팽창 주의 등
- additional_info: 위에 없는 기타 표시사항. 제품교환장소, 소비자상담실 번호,
    부정불량식품 신고번호, 분리배출 안내 등을 이어서 적는다

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
  "allergens": {"value": null, "confidence": "none"},
  "ingredient_info": {"value": null, "confidence": "none"},
  "frmlc_mtrqlt": {"value": null, "confidence": "none"},
  "pog_daycnt": {"value": null, "confidence": "none"},
  "cautions": {"value": null, "confidence": "none"},
  "additional_info": {"value": null, "confidence": "none"}
}
"""


def preprocess_image(image_file, max_size=2000):
    """
    이미지를 리사이즈하고 base64로 인코딩합니다.

    예전에는 1024px / quality 85 였다. 표시사항은 글씨가 작고 빽빽해서 - 특히
    원형 용기 라벨은 곡면에 맞춰 줄을 촘촘히 넣는다 - 그 크기로 줄이면 원재료명
    같은 긴 줄이 뭉개진다. 실제로 소비기한·보관방법·주의사항이 통째로 안 읽히고
    원재료명이 중간에서 끊겼다.

    2000px / quality 92 로 올린다. 입력 토큰이 늘어 호출 비용이 몇 배가 되지만
    한 장에 1원이 안 되는 구간이고, 못 읽으면 사람이 손으로 다시 치는 쪽이
    훨씬 비싸다.
    """
    img = Image.open(image_file)

    # 스마트폰 EXIF 회전 정보 반영
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # JPEG 저장을 위해 RGB 변환
    if img.mode not in ('RGB',):
        img = img.convert('RGB')

    # 비율 유지하며 리사이즈. 원본이 더 작으면 키우지 않는다(없는 정보는 안 생긴다).
    img.thumbnail((max_size, max_size), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=92)
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
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {"success": True, "data": result}

    except Exception as e:
        logger.exception("OCR 처리 실패")
        return {"success": False, "error": str(e)}
