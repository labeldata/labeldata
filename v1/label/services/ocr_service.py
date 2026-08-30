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
- additional_info: 위에 없는 기타 표시사항. **제품교환장소, 고객상담실/소비자상담실
    번호, 부정불량식품 신고번호, 질소가스충전 표시, 홈페이지 주소, 환경 문구** 등
    규정 항목에 해당하지 않는 문구를 줄바꿈으로 이어서 적는다
- recycling_mark: 분리배출 표시. 마크 안의 재질 구분과 그 옆/아래 보조 표기를
    함께 적는다. 예: "비닐류 PP / 띠지:PP, 리드지:PET", "플라스틱 OTHER"

영양정보(영양성분표)가 있으면 아래도 채운다. 표에 적힌 **숫자와 단위를 그대로**
옮긴다. 1일 영양성분 기준치 비율(%)은 빼고 값만 적는다.
- nutrition_basis: 표의 기준 표기. 예: "총 내용량 139 g", "100 g당", "1회 제공량 30 g"
- calories: 열량. 예: "182 kcal"
- natriums: 나트륨. 예: "630 mg"
- carbohydrates: 탄수화물. 예: "10 g"
- sugars: 당류. 예: "7 g"
- fats: 지방. 예: "10 g"
- trans_fats: 트랜스지방. 예: "0 g"
- saturated_fats: 포화지방. 예: "4.3 g"
- cholesterols: 콜레스테롤. 예: "25 mg"
- proteins: 단백질. 예: "13 g"

**가장 중요한 규칙 — 지어내지 마시오.**
- 글자가 실제로 읽히지 않으면 절대 값을 만들어 내지 마시오.
  흐리거나 너무 작아 읽을 수 없으면 {"value": null, "confidence": "none"} 으로 두시오.
- 식품 표시사항에 흔히 나오는 문구를 "그럴듯하게" 채우는 것은 **틀린 답**이다.
  이 결과는 법적 표시물에 그대로 들어간다. 빈 값이 잘못된 값보다 낫다.
- 다른 제품에서 본 원재료·주의사항을 옮겨 적지 마시오. 이 사진에 적힌 것만 쓰시오.
- 한 항목의 값에 옆 칸의 항목명이나 내용을 섞지 마시오.
  예: 소비기한 칸에 "별도표기일까지" 만 있으면 옆의 "주의사항" 을 붙이지 마시오.
- 여러 장의 이미지가 주어지면 같은 사진을 확대한 조각들이다. 겹치는 부분은
  한 번만 세고, 조각에서 더 또렷하게 읽힌 쪽을 택하시오.

응답 규칙:
- 텍스트가 명확하게 읽히면: {"value": "실제추출값", "confidence": "high"}
- 글자는 보이는데 확신이 없으면: {"value": null, "confidence": "low", "candidates": ["가능한값1", "가능한값2"]}
- 읽을 수 없거나 이미지에 없으면: {"value": null, "confidence": "none"}

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
  "additional_info": {"value": null, "confidence": "none"},
  "recycling_mark": {"value": null, "confidence": "none"},
  "nutrition_basis": {"value": null, "confidence": "none"},
  "calories": {"value": null, "confidence": "none"},
  "natriums": {"value": null, "confidence": "none"},
  "carbohydrates": {"value": null, "confidence": "none"},
  "sugars": {"value": null, "confidence": "none"},
  "fats": {"value": null, "confidence": "none"},
  "trans_fats": {"value": null, "confidence": "none"},
  "saturated_fats": {"value": null, "confidence": "none"},
  "cholesterols": {"value": null, "confidence": "none"},
  "proteins": {"value": null, "confidence": "none"}
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


# 큰 사진은 조각으로 나눠 보낸다.
#
# detail:high 는 이미지를 2048 박스에 맞춘 뒤 **짧은 변을 768px 로 맞춘다.**
# 그래서 우리가 아무리 큰 사진을 보내도 모델이 보는 해상도는 거기서 멈춘다.
# 2585x1755 짜리 작업지시서를 통째로 보내면 모델은 1131x768 로 본다 - 그 안의
# 원형 라벨은 폭 600px 남짓이고 본문 한 줄이 5px 다. 읽을 수 없다.
# 실제로 원재료명과 주의사항을 통째로 지어내는 일이 있었다.
#
# 조각을 따로 보내면 조각마다 768px 이 다시 배정된다. 2x2 로 나누면 유효
# 해상도가 축마다 두 배가 된다. 겹치게 잘라 경계에 걸친 줄이 잘리지 않게 한다.
TILE_MIN_SIDE = 1400     # 이보다 작으면 나눌 이유가 없다
TILE_OVERLAP = 0.12      # 조각끼리 겹치는 비율


def build_image_payload(image_file, max_size=2000):
    """
    보낼 이미지 목록을 만든다. [전체, 조각1, 조각2, ...]

    전체 사진을 먼저 넣는다 - 어느 칸이 어느 항목인지는 전체 배치를 봐야 안다.
    조각은 글자를 읽기 위한 것이다.
    """
    img = Image.open(image_file)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode != 'RGB':
        img = img.convert('RGB')

    def encode(im):
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    full = img.copy()
    full.thumbnail((max_size, max_size), Image.LANCZOS)
    images = [encode(full)]

    w, h = img.size
    if max(w, h) < TILE_MIN_SIDE:
        return images

    ox, oy = int(w * TILE_OVERLAP), int(h * TILE_OVERLAP)
    halves = [
        (0, 0, w // 2 + ox, h // 2 + oy),
        (w // 2 - ox, 0, w, h // 2 + oy),
        (0, h // 2 - oy, w // 2 + ox, h),
        (w // 2 - ox, h // 2 - oy, w, h),
    ]
    for box in halves:
        tile = img.crop(box)
        tile.thumbnail((max_size, max_size), Image.LANCZOS)
        images.append(encode(tile))
    return images


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
        images = build_image_payload(image_file)

        content = [
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}}
            for b64 in images
        ]
        content.append({
            "type": "text",
            "text": (
                f"이 식품 표시사항에서 정보를 추출해주세요. "
                f"이미지 {len(images)}장은 같은 사진입니다 - 첫 장은 전체 배치이고 "
                f"나머지는 글자를 읽기 위해 확대한 조각입니다. "
                f"읽을 수 없는 항목은 지어내지 말고 none 으로 두세요."
                if len(images) > 1 else
                "이 식품 표시사항 이미지에서 정보를 추출해주세요. "
                "읽을 수 없는 항목은 지어내지 말고 none 으로 두세요."
            ),
        })

        response = client.chat.completions.create(
            model=getattr(settings, 'OCR_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {"success": True, "data": result}

    except Exception as e:
        logger.exception("OCR 처리 실패")
        return {"success": False, "error": str(e)}
