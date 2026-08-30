"""
문서함에 붙인 원료 표시사항 사진을 읽어 BOM 원료 한 건으로 만든다.

원료 봉지의 표시사항도 표시사항이라, 완제품 사진에 쓰던 프롬프트를 그대로
쓴다(label/services/ocr_service.py). 다만 읽어낸 값의 **뜻이 다르다**.

    완제품 사진                     원료 사진
    ------------------------------  ------------------------------
    prdlst_nm        제품명          -> 원료명
    prdlst_dcnm      식품유형        -> 원료의 식품유형
    rawmtrl_nm       원재료명        -> 이 원료의 하위 원료(복합원재료)
    bssh_nm          제조원          -> 원료 제조사
    prdlst_report_no 품목보고번호    -> 원료 품목보고번호
    cautions         주의사항        -> 알레르기 문구가 여기 섞여 온다

배합비는 사진에 없다. 그 원료가 완제품에서 몇 %인지는 봉지에 적히지 않는다.
그래서 함량은 비워 두고 BOM 화면에서 사람이 넣는다.
"""
import logging
import re

logger = logging.getLogger(__name__)

# 「식품등의 표시기준」 알레르기 유발물질 22종.
# 주의사항 문구에서 이름이 보이는 것만 골라 붙인다.
ALLERGENS = [
    '알류', '난류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우',
    '돼지고기', '복숭아', '토마토', '아황산류', '호두', '닭고기', '쇠고기',
    '오징어', '조개류', '잣',
]

_VALUE_KEYS = ('value',)


def _val(field):
    """OCR 항목({'value':..,'confidence':..})에서 값만 꺼낸다."""
    if not isinstance(field, dict):
        return (field or '') if isinstance(field, str) else ''
    return (field.get('value') or '').strip()


def allergens_from_text(*texts):
    """주의사항·원재료명 문구에서 알레르기 유발물질 이름을 찾는다."""
    haystack = ' '.join(t or '' for t in texts)
    if not haystack.strip():
        return ''
    hits = [a for a in ALLERGENS if a in haystack]
    # '알류' 와 '난류' 는 같은 것을 가리킨다. 둘 다 잡히면 하나만 남긴다.
    if '알류' in hits and '난류' in hits:
        hits.remove('난류')
    return ', '.join(dict.fromkeys(hits))


def parse_ingredient_photo(ocr_data):
    """
    OCR 결과를 BOM 원료 한 건으로 옮긴다.

    Returns: dict — 값이 없으면 빈 문자열. 실패해도 예외를 내지 않는다.
    """
    data = ocr_data or {}

    name = _val(data.get('prdlst_nm'))
    food_type = _val(data.get('prdlst_dcnm'))
    subs = _val(data.get('rawmtrl_nm'))
    cautions = _val(data.get('cautions'))
    origin = _val(data.get('country_of_origin'))

    return {
        'ingredient_name': name,
        'food_type': food_type,
        'sub_ingredients': subs,
        'manufacturer': _val(data.get('bssh_nm')),
        'report_no': _val(data.get('prdlst_report_no')),
        'origin': origin,
        'allergens': allergens_from_text(cautions, subs),
    }


def read_document_image(document):
    """
    ProductDocument 의 파일을 OCR 에 태운다.

    Returns: (ocr_data 또는 None, 오류 메시지 또는 '')
    """
    from v1.label.services.ocr_service import extract_label_from_image

    if not document.file:
        return None, '문서에 파일이 없습니다.'

    path = str(document.file.path)
    ext = re.sub(r'^.*(\.[^.]+)$', r'\1', path).lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
        # PDF 는 지원하지 않는다. 원료 표시사항은 봉지를 찍은 사진으로 올라온다.
        return None, f'사진 파일만 읽을 수 있습니다 (현재: {ext or "확장자 없음"}).'

    try:
        with document.file.open('rb') as fh:
            result = extract_label_from_image(fh)
    except Exception as exc:
        logger.exception('원료 사진 OCR 실패 (document=%s)', document.pk)
        return None, str(exc)

    if not result.get('success'):
        return None, result.get('error') or '사진을 읽지 못했습니다.'
    return result.get('data') or {}, ''
