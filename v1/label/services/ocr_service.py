"""
OCR 서비스 - GPT-4o mini 기반
이미지에서 식품 표시사항 필드를 추출하고 신뢰도에 따라 후보를 제공합니다.
"""
import io
import base64
import json
import logging
import re
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

실제로 자주 나온 실수들이다. 특히 조심하시오.
- **작업지시서·시안의 표를 라벨로 착각하지 마시오.** 사진 한쪽에 "품명/사이즈/
  발주일/담당자" 같은 제작 정보 표가 있을 수 있다. 그것은 인쇄 지시서다.
  값은 **실제 라벨(원형·사각 도안) 안**에서만 읽으시오.
  예: 지시서 품명이 "PIG더블치즈&바질치킨 샐러드_후면" 이어도, 라벨 안
  제품명이 "더블치즈&바질치킨 샐러드" 면 후자가 답이다.
- 항목명을 값에 넣지 마시오. "포장재질 PET(용기)" 가 아니라 "PET(용기)" 다.
- 알레르기(allergens)와 혼입 주의(cautions)는 다르다.
  "○○ 함유" 는 알레르기, "○○ 혼입 가능성 있음" 은 주의사항이다.
  혼입 가능 물질을 알레르기에 옮겨 적지 마시오.
- **검은 박스 하나에 둘이 같이 있는 경우가 많다.** 두 줄은 서로 다른 것이다.
  "○○ 함유" 는 **그 제품에 실제로 들어 있는** 물질이다 -> allergens (물질 이름만)
  "○○ 혼입가능성 있음" 은 **안 들어 있는데 같은 시설을 쓴** 물질이다 -> cautions
  **한쪽을 다른 쪽에 옮겨 적지 마시오.** 실제로 "함유" 줄을 통째로 주의사항에
  옮겨 적고 알레르기 칸은 절반만 채운 일이 있었다. 두 줄을 다 읽되 각자
  제자리에 넣으시오.
- **주의사항과 기타표시사항은 옮겨 적는 것이지 다시 쓰는 것이 아니다.**
  요약하지도, 말을 다듬지도, 뜻이 같은 다른 문장으로 바꾸지도 마시오.
  실제로 "고객상담실 080-739-8572(수신자 부담)" 을
  "상품명에 대한 문의는 080-739-8572로 하시기 바랍니다" 로 고쳐 쓴 일이 있었다.
  번호는 맞았지만 라벨에 없는 문장이고, 이 결과는 인쇄물에 그대로 들어간다.
  **읽은 글자를 그 순서 그대로, 한 글자도 바꾸지 말고 옮기시오.**
- 업체명·지명 같은 고유명사는 획을 하나씩 확인하시오
  (삼립/삼진, 송정동/성동동 처럼 한 획 차이가 흔하다). 확신이 없으면
  candidates 에 두 후보를 넣고 confidence 를 low 로 두시오.

원재료명(rawmtrl_nm)을 옮길 때 — 여기가 가장 길고 가장 자주 틀리는 항목이다.

  괄호. 열림과 닫힘은 **반드시 짝**이고, 여는 쪽과 닫는 쪽의 종류가 같아야 한다.
    소괄호 ( 는 ) 로, 대괄호 [ 는 ] 로, 중괄호 { 는 } 로 닫는다.
    종류를 바꾸지 마시오 — "정제소금[국산]" 을 "정제소금(국산]" 으로 옮기는
    실수가 잦다. 괄호가 겹쳐 있으면(복합원재료 안의 원산지) 안쪽부터 닫는다.
    다 옮긴 뒤 여는 괄호와 닫는 괄호의 수와 종류가 맞는지 세어 보시오.
    맞지 않으면 그 자리를 잘못 읽은 것이다 — 짝을 지어내 맞추지 말고 그 자리를
    다시 보고, 그래도 안 읽히면 confidence 를 low 로 두시오.

  복합원재료. "쉬레드치즈[모짜렐라, 체다, 혼합제제(...)]" 처럼 한 원재료 안에
    여러 하위 원료가 들어간다. 괄호 안에 **하위 원료를 전부** 넣고 마지막
    것까지 넣은 뒤에 닫는다. 첫 하위 원료만 넣고 닫아 버리면 나머지가 별개의
    원재료로 밀려 나가 **원재료 수가 늘고 함량 순서가 뒤틀린다.**
    실제로 "쉬레드치즈[모짜렐라, 체다, 혼합제제]" 가
    "쉬레드치즈[모짜렐라], 체다, 혼합제제" 로 나온 일이 잦다.

  순서. 라벨에 적힌 **순서 그대로** 옮긴다. 원재료 순서가 곧 함량 순이라
    순서를 바꾸면 다른 뜻이 된다. 보기 좋게 정렬하지 마시오.

  이름. 원재료 이름과 그 뒤의 원산지·복합원재료·함량은 서로 다른 것이다.
    "돼지고기 30%(국내산)" 에서 이름은 "돼지고기", 함량은 "30%",
    원산지는 "(국내산)" 이다. 셋을 뒤섞거나 빠뜨리지 마시오.


주의사항(cautions)·기타표시사항(additional_info) 은 **지어내기 가장 쉬운 칸**이다.

  이 두 칸에 들어가는 문구는 회사마다 거의 정해져 있어서, 모델이 "이런 라벨에는
  보통 이런 문장이 있다" 는 것을 이미 알고 있다. 그래서 **사진에서 그 문장을
  못 읽었는데도 그럴듯하게 채우는 일이 실제로 일어났다** — 다른 제품의 보관
  문구와 분쟁해결기준 문구가 통째로 들어갔다.

  **사진에서 그 글자를 직접 읽지 않았으면 적지 마시오.** 흔한 문구일수록
  더 그렇다. 이 칸이 비어 있는 것은 잘못이 아니다.
  라벨에 두 문장만 있으면 두 문장만 적는다.

  어느 칸에 넣을지는 뜻으로 가른다.
    주의사항     섭취·보관·취급 주의, 혼입 가능, 경고, 신고 번호(1399)
    기타표시사항 인증 표시(HACCP·유기농·비건 등), 상담 번호, 교환 장소,
                 홈페이지, 질소가스충전 표시

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


# 조각을 어느 방향으로 자를 것인가.
#
#   'grid'   2x2. 한가운데를 **세로로** 가른다. 오래 쓰던 방식이다.
#   'bands'  가로 띠. 폭은 그대로 두고 **위아래로만** 가른다.
#
# 왜 방향이 문제인가. 표시사항 본문은 **폭 전체를 쓰는 줄**이다. 세로로 자르면
# 모든 줄이 반토막 나서, 왼쪽 조각에 줄의 왼쪽 62%, 오른쪽 조각에 오른쪽 62%가
# 들어간다. 모델이 그 둘을 이어 붙여야 하는데 원재료명처럼 여러 줄로 감기는
# 긴 목록에서 그 봉합이 무너진다.
#
# 실제로 그렇게 무너졌다. 원재료 15개짜리 라벨에서 앞 몇 개는 맞고, 중간부터
# 원산지가 엉뚱한 원료에 붙고, 없는 원료("전분")가 생기고, 7번째에서 멈췄다.
# 같은 사진의 **원재료명 영역만 잘라 한 번에 읽히자 15개가 다 나왔다** —
# 글자가 안 읽힌 게 아니라 봉합이 실패한 것이다.
#
# 해상도는 손해가 아니다. 띠의 높이를 2x2 의 행 높이와 같게 두면 짧은 변이
# 같으므로 API 가 맞추는 배율도 같다. 오히려 이미지 장수가 5장에서 3장으로
# 줄어 호출 비용이 조금 내려간다.
TILE_LAYOUTS = ('grid', 'bands')
MAX_BANDS = 4            # 띠가 늘수록 장수가 늘고 비용이 붙는다


def _band_count(width, height):
    """
    띠를 몇 개로 나눌 것인가.

    띠가 가로로 길어야(높이 <= 폭) 짧은 변이 높이가 되고, 그래야 2x2 와 같은
    배율을 받는다. 세로로 긴 라벨은 그만큼 더 나눈다.
    """
    if width <= 0 or height <= 0:
        return 2
    return max(2, min(MAX_BANDS, -(-height // width)))


def build_image_regions(image_file, max_size=2000, layout='grid'):
    """
    보낼 이미지와 **그 이미지가 원본의 어디인지**를 함께 만든다.

    전체 사진을 먼저 넣는다 - 어느 칸이 어느 항목인지는 전체 배치를 봐야 안다.
    조각은 글자를 읽기 위한 것이다.

    조각을 우리가 잘랐으니 원본에서의 자리는 **확실하다.** 그래서 모델이
    "2번 조각의 여기" 라고만 답해도 원본 좌표로 되돌릴 수 있다. 위치 표시가
    이 값 위에 선다.

    layout 은 조각을 자르는 방향이다 (TILE_LAYOUTS 참고). 'bands' 는 줄을
    끊지 않는다 — 긴 원재료명처럼 여러 줄로 감기는 값에서 차이가 크다.

    Returns: [{'b64', 'box': (left, top, right, bottom), 'label'} ...]
             box 는 원본 픽셀. 첫 항목은 사진 전체다.
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

    w, h = img.size
    full = img.copy()
    full.thumbnail((max_size, max_size), Image.LANCZOS)
    regions = [{'b64': encode(full), 'box': (0, 0, w, h), 'label': '사진 전체'}]

    if max(w, h) < TILE_MIN_SIDE:
        return regions

    ox, oy = int(w * TILE_OVERLAP), int(h * TILE_OVERLAP)

    if layout == 'bands':
        # 폭은 그대로 두고 위아래로만 가른다. 줄이 끊기지 않는다.
        count = _band_count(w, h)
        step = h / count
        pieces = []
        for i in range(count):
            top = max(0, int(i * step) - (oy if i else 0))
            bottom = min(h, int((i + 1) * step) + (oy if i < count - 1 else 0))
            pieces.append((f'가로 띠 {i + 1}/{count}', (0, top, w, bottom)))
    else:
        pieces = [
            ('왼쪽 위',     (0, 0, w // 2 + ox, h // 2 + oy)),
            ('오른쪽 위',   (w // 2 - ox, 0, w, h // 2 + oy)),
            ('왼쪽 아래',   (0, h // 2 - oy, w // 2 + ox, h)),
            ('오른쪽 아래', (w // 2 - ox, h // 2 - oy, w, h)),
        ]

    for label, box in pieces:
        tile = img.crop(box)
        tile.thumbnail((max_size, max_size), Image.LANCZOS)
        regions.append({'b64': encode(tile), 'box': box, 'label': f'조각 {label}'})
    return regions


def build_image_payload(image_file, max_size=2000, layout='grid'):
    """보낼 이미지 목록만. [전체, 조각1, 조각2, ...]"""
    return [region['b64']
            for region in build_image_regions(image_file, max_size, layout)]


# 작업지시서·도안 파일 이름이 제품명에 붙어 온다. 프롬프트에 예시까지 넣어
# 두었는데도 "더블치즈&바질치킨 샐러드_후면" 이 그대로 나왔다.
# 설득이 안 되는 것은 코드로 뗀다 — 이런 접미사로 끝나는 제품명은 없다.
_DESIGN_SUFFIX = re.compile(
    r'[\s_\-]*(후면|전면|앞면|뒷면|back|front|시안|도안|출력용|인쇄용)\s*$',
    re.IGNORECASE)


# 사진에서 읽지 않을 항목.
#
# 주의사항과 기타표시사항은 무엇을 해도 흔들렸다. 상용 문구 목록을 프롬프트에
# 실으면 그 문장을 지어내고, 빼면 새 문장을 지어내고, 전용 칸을 만들면 옆
# 칸(알레르기)을 망쳤다. 편차가 80을 넘는 회차도 있었다.
#
# 그런데 이 두 칸에는 **이미 사용자용 빠른 입력 버튼 스물여덟 개**가 있다.
# 두어 번 눌러 정확한 문장을 넣을 수 있다. 지어낸 문구가 법적 표시물에
# 들어가는 위험이, 버튼 두 번 누르는 수고보다 크다.
#
# 그래서 기본으로 읽지 않는다. `.env` 에 OCR_READ_FREETEXT=True 를 넣거나
# 측정 화면에서 켜서 견줄 수 있다 — 나중에 모델이 나아지면 되돌릴 자리다.
FREETEXT_FIELDS = ('cautions', 'additional_info')


def drop_freetext(data, read_freetext=None):
    """
    자유 문구 칸을 비운다. **값이 없는 것과 구분해서 표시한다.**

    `skipped` 를 남겨야 채점이 이 칸을 0점이 아니라 **채점 제외**로 다룰 수
    있다. 일부러 안 읽은 것을 "못 읽었다" 로 세면 평균이 거짓말을 한다.
    """
    if read_freetext is None:
        read_freetext = getattr(settings, 'OCR_READ_FREETEXT', False)
    if read_freetext:
        return data

    data = dict(data or {})
    for key in FREETEXT_FIELDS:
        if key in data:
            data[key] = {'value': None, 'confidence': 'none', 'skipped': True}
    return data


def strip_design_suffix(data):
    """제품명 끝에 붙은 도안 표기를 뗀다. **원본은 건드리지 않는다.**"""
    data = dict(data or {})
    item = data.get('prdlst_nm')
    value = item.get('value') if isinstance(item, dict) else item
    text = str(value or '').strip()
    if not text:
        return data

    stripped = _DESIGN_SUFFIX.sub('', text).strip()
    if stripped and stripped != text:
        item = dict(item) if isinstance(item, dict) else {'value': stripped,
                                                          'confidence': 'high'}
        item['value'] = stripped
        item['snapped_from'] = text
        item['snapped_note'] = '제품명 끝의 도안 표기를 뗐습니다.'
        data['prdlst_nm'] = item
    return data


def learned_hints():
    """
    지금까지 사용자가 고친 이력에서 뽑은 주의사항.

    쌓인 게 없으면 빈 문자열이다. 조회에 실패해도 판독은 계속돼야 하므로
    조용히 넘어간다.
    """
    try:
        from v1.label.services.ocr_learning import hints_text
        return hints_text()
    except Exception:
        logger.exception('판독 힌트를 붙이지 못했다')
        return ''


def active_prompt(version=None):
    """
    이번 판독에 쓸 프롬프트.

    관리자 화면에서 켜 둔 판이 있으면 그것을, 없으면 이 파일의 SYSTEM_PROMPT 를
    쓴다. 조회에 실패해도 판독은 그대로 돌아야 하므로 조용히 기본값으로 내려간다.
    """
    try:
        from v1.label.services.ocr_prompt import resolve
        return resolve(version)
    except Exception:
        logger.exception('활성 프롬프트를 가져오지 못했다 - 기본 프롬프트로 읽는다')
        return SYSTEM_PROMPT


# ── 표시면별로 잘라 보내기 ────────────────────────────────────────────────
#
# 사진 하나에 영역 하나로는 부족했다. 포장 사진에는 주표시면과 일괄표시면이
# 따로 떨어져 있어서, 둘을 다 담으려면 사이의 빈 곳까지 넣어야 하고 그만큼
# 해상도가 다시 낮아진다. 게다가 어느 값이 어느 면에서 나온 것인지도 알 수 없다.
#
# 그래서 화면(photo_cropper.js)에서 면마다 하나씩 고르게 하고, 그 면이 무엇인지
# 이름을 붙여 보낸다. 이름이 붙으면 **그 조각에서 무엇을 찾을지 짚어 줄 수 있다.**
# key 는 photo_cropper.js 의 ROLES 와 같아야 한다 — 화면에서 고른 이름과 모델이
# 받는 지시가 어긋나면 사용자가 본 설명과 실제 판독이 달라진다.
REGION_ROLES = {
    'main':      ('주표시면',      '제품명, 내용량, 내용량(열량), 특정성분 함량'),
    'info':      ('일괄표시면',    '식품유형, 품목보고번호, 원재료명, 제조원·수입원, '
                                   '소비기한, 보관방법, 포장재질'),
    'rawmtrl':   ('원재료명 영역', '원재료명 및 함량, 알레르기 표시'),
    'nutrition': ('영양성분표',    '열량, 나트륨, 탄수화물, 당류, 지방, 트랜스지방, '
                                   '포화지방, 콜레스테롤, 단백질'),
    'recycle':   ('분리배출마크',  '분리배출 표시(재질 구분)'),
    'other':     ('표시사항 일부', ''),
    'whole':     ('사진 전체',     ''),
}

# 한 번에 보낼 이미지 장수 상한. 장수가 곧 비용이고, 너무 많으면 모델이
# 어느 장을 보고 있는지도 흐려진다.
MAX_REGION_IMAGES = 8

# 조각으로 더 나눌 만한 면. 원재료명처럼 여러 줄로 감기는 긴 목록이 있는
# 쪽만 나눈다 — 제품명 몇 줄뿐인 주표시면을 나누면 장수만 늘고 얻는 게 없다.
_DENSE_ROLES = ('info', 'rawmtrl', 'other', 'whole')


def build_multi_regions(parts, max_size=2000, layout='grid'):
    """
    표시면별 이미지 목록을 모델에 보낼 순서대로 만든다.

    parts: [(file, role), ...] — role 은 REGION_ROLES 의 key.

    영역이 하나뿐이면 예전과 똑같이 (전체 + 조각) 을 만든다. 그동안 그 경로로
    맞춰 온 판독 품질을 건드리지 않기 위해서다.

    여럿이면 면마다 그 면 하나를 통째로 넣고, 글자가 빽빽한 면(일괄표시면·
    원재료명)만 추가로 띠를 나눈다. 이미 사람이 면 단위로 잘라 준 뒤라
    2x2 조각까지 붙일 이유가 없다 — 장수만 늘고 어느 장이 무엇인지 흐려진다.

    Returns: [{'b64', 'box', 'label'} ...] — build_image_regions 와 같은 모양.
    """
    if len(parts) == 1:
        image_file, role = parts[0]
        title = REGION_ROLES.get(role, REGION_ROLES['other'])[0]
        regions = build_image_regions(image_file, max_size, layout)
        # 면 이름을 앞에 붙여 준다 — 지시문이 그 이름으로 조각을 가리킨다
        for region in regions:
            region['role'] = role
            region['label'] = f'{title} {region["label"]}'
        return regions[:MAX_REGION_IMAGES]

    fulls, tiles = [], []
    for image_file, role in parts:
        title = REGION_ROLES.get(role, REGION_ROLES['other'])[0]
        # 글자가 빽빽한 면은 가로 띠로 나눈다. 표시사항 본문은 폭 전체를 쓰는
        # 줄이라, 세로로 가르면 모든 줄이 반토막 나 봉합이 무너진다.
        regions = build_image_regions(
            image_file, max_size, 'bands' if role in _DENSE_ROLES else 'grid')
        head, rest = regions[0], regions[1:]
        head['role'] = role
        head['label'] = title
        fulls.append(head)
        if role not in _DENSE_ROLES:
            continue
        for region in rest:
            region['role'] = role
            region['label'] = f'{title} {region["label"]}'
            tiles.append(region)

    room = max(0, MAX_REGION_IMAGES - len(fulls))
    return fulls + tiles[:room]


def region_instructions(regions):
    """
    "몇 번째 장이 무엇이고 거기서 뭘 찾아야 하는지" 를 적은 지시문.

    조각을 우리가 잘랐으니 순서도 우리가 안다. 모델에게 장 번호로 말해 주면
    "어느 사진 얘기냐" 로 흔들리지 않는다.
    """
    lines = []
    for i, region in enumerate(regions, start=1):
        role = region.get('role') or 'other'
        _, wants = REGION_ROLES.get(role, REGION_ROLES['other'])
        line = f'{i}) {region["label"]}'
        if wants and not region['label'].startswith(REGION_ROLES.get(role, ("",))[0] + ' 조각'):
            line += f' — 여기서 찾을 항목: {wants}'
        lines.append(line)
    return '\n'.join(lines)


def extract_label_from_parts(parts, model=None, prompt_version=None,
                             use_hints=True, layout='grid', read_freetext=None):
    """
    표시면별로 잘라 온 사진들에서 한 번에 필드를 뽑는다.

    parts: [(file, role), ...]

    여러 장을 **한 번의 호출로** 보낸다. 면마다 따로 부르면 같은 항목을 두 면이
    서로 다르게 답할 때 어느 쪽을 믿을지 정할 근거가 없고, 값을 합치는 규칙을
    우리가 또 만들어야 한다. 한 번에 보여 주면 모델이 그 자리에서 맞춘다.
    """
    if not parts:
        return {"success": False, "error": "이미지가 없습니다."}
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY,
                        max_retries=getattr(settings, 'OCR_MAX_RETRIES', 5))
        regions = build_multi_regions(parts, layout=layout)

        content = [
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{r['b64']}", "detail": "high"}}
            for r in regions
        ]
        content.append({
            "type": "text",
            "text": (
                f"이 식품 표시사항에서 정보를 추출해주세요.\n"
                f"이미지 {len(regions)}장은 **같은 제품**의 서로 다른 부분입니다.\n"
                f"{region_instructions(regions)}\n"
                f"각 장에 적힌 것만 읽으세요. 어느 장에도 없는 항목은 지어내지 말고 "
                f"none 으로 두세요. 한 줄이나 한 목록이 조각 경계에서 끊겼으면 "
                f"이웃한 조각에서 그 나머지를 찾아 **이어 붙이세요.** 이을 수 없으면 "
                f"거기서 끊고 confidence 를 low 로 두세요 - 특히 원재료명은 끊긴 자리를 "
                f"메우려다 없는 원료나 없는 원산지를 만들기 쉽습니다."
            ),
        })

        system = active_prompt(prompt_version)
        if use_hints:
            system += learned_hints()

        response = client.chat.completions.create(
            model=model or getattr(settings, 'OCR_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        result = drop_freetext(strip_design_suffix(result), read_freetext)
        return {"success": True, "data": result,
                "regions": [r['label'] for r in regions]}

    except Exception as e:
        logger.exception("OCR 처리 실패 (표시면 %s장)", len(parts))
        return {"success": False, "error": str(e)}


def extract_label_from_image(image_file, model=None, prompt_version=None,
                             use_hints=True, want_boxes=False, layout='grid',
                             read_freetext=None):
    """
    GPT-4o mini를 사용해 표시사항 이미지에서 필드를 추출합니다.

    model / prompt_version 은 **측정용 덮어쓰기**다. 정확도 화면이 판끼리
    견주려면 같은 사진을 다른 판으로 읽어 봐야 한다. 평소 판독은 둘 다 비우고
    부르므로 설정값과 활성 판을 그대로 쓴다.

    use_hints=False 면 교정 이력 힌트를 붙이지 않는다 - 프롬프트 자체의 힘만
    재고 싶을 때 쓴다(힌트가 섞이면 무엇이 점수를 올렸는지 알 수 없다).

    want_boxes=True 면 **읽은 자리**도 함께 받아 원본 픽셀 좌표로 돌려준다
    (`data[항목]['box'] = [x, y, w, h]`). 기본은 꺼져 있다 - 좌표를 요구하면
    항목마다 숫자 네 개를 더 뱉게 되고 그만큼 값에 쓸 주의가 갈린다. **값이
    본질이고 위치는 편의다.** 관리자 화면에서 앞뒤를 재 보기 전에는 평소
    판독에 켜지 않는다.

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
        # 429(분당 토큰 한도)를 만나면 SDK 가 서버가 알려 준 시간만큼 기다렸다
        # 다시 부른다. 기본값 2회로는 모자랐다 — 측정에서 회차 3을 걸었는데
        # 2회와 3회가 모두 429 로 죽고 1회만 성공했다. 표에는 "3회" 로 뜨는데
        # 실제로는 한 번이라, 편차가 0 으로 나와 "안정적" 으로 보인다.
        # **측정이 조용히 거짓말을 한다.**
        #
        # 사진 한 장 판독이 6~7만 토큰이라, 분당 20만 토큰 한도면 **분당 세 번**
        # 이 한계다. 기다리는 것 말고 할 수 있는 일이 없다.
        client = OpenAI(api_key=settings.OPENAI_API_KEY,
                        max_retries=getattr(settings, 'OCR_MAX_RETRIES', 5))
        regions = build_image_regions(image_file, layout=layout)
        images = [region['b64'] for region in regions]

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
                f"나머지는 글자를 읽기 위해 확대한 조각입니다"
                f"({', '.join(r['label'] for r in regions[1:])}). "
                f"한 줄이나 한 목록이 조각 경계에서 끊겼으면 이웃한 조각에서 "
                f"그 나머지를 찾아 **이어 붙이세요.** 이을 수 없으면 지어내지 말고 "
                f"거기서 끊고 confidence 를 low 로 두세요 - 특히 원재료명은 "
                f"끊긴 자리를 메우려다 없는 원료나 없는 원산지를 만들기 쉽습니다. "
                f"읽을 수 없는 항목은 지어내지 말고 none 으로 두세요."
                if len(images) > 1 else
                "이 식품 표시사항 이미지에서 정보를 추출해주세요. "
                "읽을 수 없는 항목은 지어내지 말고 none 으로 두세요."
            ),
        })

        system = active_prompt(prompt_version)
        if use_hints:
            system += learned_hints()
        if want_boxes:
            from v1.label.services.ocr_boxes import PROMPT_ADDENDUM
            system += PROMPT_ADDENDUM

        response = client.chat.completions.create(
            model=model or getattr(settings, 'OCR_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        result = drop_freetext(strip_design_suffix(result), read_freetext)

        if want_boxes:
            # 조각 좌표를 원본 좌표로 되돌린다. 조각을 우리가 잘랐으니 이
            # 계산은 확실하다 - 틀릴 여지는 모델이 준 상자 쪽에만 있다.
            from v1.label.services.ocr_boxes import attach
            result, located = attach(result, regions)
            return {"success": True, "data": result, "boxes_found": located}

        return {"success": True, "data": result}

    except Exception as e:
        logger.exception("OCR 처리 실패")
        return {"success": False, "error": str(e)}
