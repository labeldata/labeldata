# -*- coding: utf-8 -*-
"""
시험성적서 사진에서 **영양성분 값**을 읽는다.

왜 이것이 특별한가
──────────────────
원료 영양성분의 출처에는 등급이 있다.

    A  spec_ocr    업체 시험성적서
    B  report_no   품목보고번호가 식약처 DB 와 정확히 일치
    C  picked      후보 중 사람이 고름 / manual 직접 입력

**공공 DB 로 채운 값은 영원히 C 다.** 식약처 DB 의 밀가루는 "일반적인 밀가루"
이지 "우리가 쓰는 그 밀가루" 가 아니기 때문이다. 이론치로 만든 영양성분표는
그 자체가 감사 대상이라 "이 숫자가 어디서 왔는가" 가 값만큼 중요하다.

`SOURCE_SPEC_OCR` 은 모델에 처음부터 정의돼 있었다. **그 값을 넣는 화면만
없었다.** 그리고 그 종이는 이미 우리 문서함에 쌓이고 있다.

표시사항 판독과 무엇이 다른가
─────────────────────────────
표시사항 사진은 **인쇄된 라벨**이고, 성적서는 **시험 결과표**다. 읽는 것이
다르다.

    표시사항   제품명·원재료명·소비기한… 글이 대부분
    성적서     항목 | 결과 | 단위 | 시험방법 이 줄지어 선 **표**

그래서 프롬프트를 따로 둔다. 표시사항 프롬프트로 성적서를 읽히면 제품명 칸에
시험기관 이름이 들어오는 식으로 어긋난다.

기준량을 반드시 읽는다
──────────────────────
성적서는 100 g 당으로만 오지 않는다. 1 회 제공량당·1 kg 당·제품 전체당이
섞여 있다. **기준량을 모르면 그 값은 쓸 수 없다** — 100 g 당으로 바꿔야
배합 계산에 들어간다. 못 읽으면 비워 두고 사람에게 묻는다. 100 으로
가정하면 조용히 몇 배씩 틀린다.
"""
import base64
import io as _io
import json
import logging
import re

logger = logging.getLogger(__name__)

# 읽어 올 성분. MyIngredientNutrition.VALUE_FIELDS 와 같아야 한다 — 여기서
# 늘리면 저장이 못 받고, 저기서 늘리면 여기가 못 읽는다.
FIELDS = (
    ('calories', '열량', 'kcal'),
    ('carbohydrates', '탄수화물', 'g'),
    ('sugars', '당류', 'g'),
    ('proteins', '단백질', 'g'),
    ('fats', '지방', 'g'),
    ('saturated_fats', '포화지방', 'g'),
    ('trans_fats', '트랜스지방', 'g'),
    ('cholesterols', '콜레스테롤', 'mg'),
    ('natriums', '나트륨', 'mg'),
    ('dietary_fiber', '식이섬유', 'g'),
    ('sugar_alcohols', '당알콜', 'g'),
)

PROMPT = (
    '이 이미지는 식품 **시험성적서**(또는 규격서)입니다. 영양성분 시험 결과를 '
    '읽어 JSON 으로만 답하세요.\n\n'
    '읽을 것\n'
    + ''.join('  %s (%s)\n' % (ko, unit) for _f, ko, unit in FIELDS) +
    '\n'
    '규칙\n'
    '1. **적혀 있는 것만** 읽으세요. 표에 없는 항목은 null 로 두세요. '
    '0 으로 적지 마세요 — 모르는 것과 0 은 다릅니다.\n'
    '2. 단위를 위 목록에 맞춰 환산하세요. mg 로 적힌 나트륨은 그대로, '
    'g 으로 적혀 있으면 1000 을 곱하세요.\n'
    '3. "불검출", "ND", "-", "<0.1" 은 0 으로 보지 말고 null 로 두세요.\n'
    '4. **기준량을 반드시 읽으세요.** "100g당", "1회 제공량(30g)당", "1kg당" '
    '등이 표 머리나 각주에 있습니다. basis_amount 에 숫자, basis_unit 에 '
    'g 또는 mL 을 넣으세요. 찾지 못하면 둘 다 null 로 두세요 — '
    '**추측하지 마세요.**\n'
    '5. 시험기관·시험번호·접수일 같은 것은 읽지 마세요. 영양성분만 봅니다.\n\n'
    '형식 (다른 말 없이 이 JSON 만)\n'
    '{"basis_amount": 100, "basis_unit": "g", '
    '"values": {"calories": 380, "carbohydrates": 70.2, ...}}'
)

_NUM = re.compile(r'-?\d+(?:\.\d+)?')


def _num(v):
    """숫자만 꺼낸다. 못 꺼내면 None — 0 으로 적으면 거짓말이 된다."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    text = str(v).strip()
    if not text or text.lower() in ('nd', 'n/d', '-', 'null', '불검출'):
        return None
    m = _NUM.search(text.replace(',', ''))
    return float(m.group()) if m else None


def to_per_100(values, basis_amount, basis_unit):
    """
    기준량을 100 으로 맞춘다. 맞출 수 없으면 (None, 까닭).

    **기준량을 모르면 손대지 않는다.** 100 으로 가정하면 1 회 제공량 30 g
    성적서가 그대로 들어와 값이 3.3 배 낮아지는데, 터지지 않으니 아무도 모른다.
    """
    if basis_amount is None or not basis_unit:
        return None, '성적서의 기준량(100g당 등)을 읽지 못했습니다.'
    try:
        amount = float(basis_amount)
    except (TypeError, ValueError):
        return None, '기준량을 숫자로 읽지 못했습니다.'
    if amount <= 0:
        return None, '기준량이 0 이하입니다.'
    if str(basis_unit).strip().lower() not in ('g', 'ml', 'mL'.lower()):
        return None, '기준 단위가 g·mL 이 아닙니다 (%s).' % basis_unit

    factor = 100.0 / amount
    out = {}
    for key, _ko, _unit in FIELDS:
        v = _num(values.get(key))
        out[key] = None if v is None else round(v * factor, 3)
    return out, ''


def read(image_fh, tag='spec_nutrition'):
    """
    성적서 사진 하나를 읽어 {values, basis_amount, basis_unit, error} 를 낸다.

    값은 **100 g(mL) 당으로 환산해서** 낸다. 환산할 수 없으면 values 는 비고
    error 에 까닭이 담긴다 — 사람이 기준량을 알려 주면 다시 부르면 된다.
    """
    from v1.label.services.ai_validation_service import call_openai

    try:
        raw = image_fh.read()
    except Exception as exc:
        return {'values': {}, 'basis_amount': None, 'basis_unit': '',
                'error': '파일을 읽지 못했습니다: %s' % exc}
    if not raw:
        return {'values': {}, 'basis_amount': None, 'basis_unit': '',
                'error': '빈 파일입니다.'}

    b64 = base64.b64encode(raw).decode('ascii')
    content = [
        {"type": "image_url",
         "image_url": {"url": "data:image/jpeg;base64,%s" % b64, "detail": "high"}},
        {"type": "text", "text": PROMPT},
    ]
    body, reason = call_openai(tag, content, max_tokens=900, json_mode=True)
    if body is None:
        return {'values': {}, 'basis_amount': None, 'basis_unit': '',
                'error': reason or '판독하지 못했습니다.'}
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return {'values': {}, 'basis_amount': None, 'basis_unit': '',
                    'error': '판독 결과를 읽지 못했습니다.'}

    amount = _num(body.get('basis_amount'))
    unit = str(body.get('basis_unit') or '').strip()
    values, why = to_per_100(body.get('values') or {}, amount, unit)
    return {
        'values': values or {},
        'basis_amount': amount,
        'basis_unit': unit,
        'error': why,
    }
