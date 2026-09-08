"""
**검증 전에, 무엇이 있어야 더 정확한지 알려 준다.**

지금까지 사용자는 올리고 나서야 알았다 — 시안을 JPG 로 올리면 활자 크기가
"값불명" 으로 나오고, 시험성적서가 없으면 영양성분 값을 못 본다. 그때는 이미
판독 비용을 쓴 뒤다.

그래서 검증을 두 갈래로 나누고, 각 갈래가 **무엇을 대상으로 하는지**와
**무엇이 갖춰졌는지**를 미리 보여 준다.

    1차 · 표시문구 검증   우리가 만든 표시사항이 규정에 맞는가
                          대상: 이 화면의 표. 준비물이 따로 없다
    2차 · 디자인시안 검증  받은 시안이 확정한 표시사항과 같은가
                          대상: 문서함의 포장지 시안. 없으면 시작할 수 없다

**갖추라고만 하고 끝내지 않는다.** 무엇이 없으면 무엇을 못 보는지를 함께
말한다 — 그래야 사용자가 "이건 우리 제품에 필요 없다" 를 스스로 정한다.
"""
import logging

logger = logging.getLogger(__name__)

# 2차 검증이 쓰는 문서와, 없으면 못 보는 것.
#
# 순서가 곧 화면 순서다. 시안이 맨 위인 이유는 그것 없이는 2차가 아예
# 시작되지 않기 때문이다.
SECOND_PASS_DOCUMENTS = (
    ('DESIGN_PROOF', '포장지 시안', True,
     '시안 대조 전체, 인쇄될 활자 크기'),
    ('LABEL_DESIGN', '한글표시사항도안', False,
     '시안이 없을 때 이것으로 대신 본다'),
    ('REPORT_MANUFACTURING', '품목제조보고서', False,
     '제품명·식품유형·품목보고번호 대조'),
    ('ANALYSIS_NUTRITION', '영양성분분석서', False,
     '영양성분 값이 성적서와 맞는지'),
)

# 시안 파일 형식마다 볼 수 있는 것이 다르다. 올리기 **전에** 말해 준다 —
# 지금은 올리고 나서야 "값불명" 으로 알게 된다.
FORMAT_NOTES = {
    '.pdf':  ('글자와 활자 크기를 모두 읽습니다.', True),
    '.pptx': ('글자와 활자 크기를 모두 읽습니다.', True),
    '.jpg':  ('글자만 읽습니다 — 활자 크기는 눈으로 확인해야 합니다.', False),
    '.jpeg': ('글자만 읽습니다 — 활자 크기는 눈으로 확인해야 합니다.', False),
    '.png':  ('글자만 읽습니다 — 활자 크기는 눈으로 확인해야 합니다.', False),
}


def _slot_state(label, type_code):
    """이 문서가 문서함에 있는가. (있나, 파일명, 숨겼나)."""
    from v1.products.models import ProductDocument

    document = (ProductDocument.objects
                .filter(label=label, active_yn=True,
                        document_type__type_code=type_code)
                .order_by('-uploaded_datetime')
                .first())
    hidden = False
    try:
        slot = label.document_slots.filter(
            document_type__type_code=type_code).first()
        hidden = bool(slot and slot.hidden_yn)
    except Exception:
        logger.exception('문서 슬롯을 읽지 못했다 (label=%s, type=%s)',
                         getattr(label, 'pk', None), type_code)
    return document, (document.original_filename if document else ''), hidden


def format_note(filename: str):
    """이 파일 형식으로 무엇까지 볼 수 있는가. (문구, 활자를 읽나)."""
    import os

    suffix = os.path.splitext(filename or '')[1].lower()
    return FORMAT_NOTES.get(suffix, ('이 형식은 판독하지 못합니다.', False))


def readiness(label) -> dict:
    """
    두 검증의 준비 상태.

        {'first': {...}, 'second': {...}}

    `first` 는 늘 시작할 수 있다 — 대상이 이 화면의 표이기 때문이다.
    `second` 는 시안이 있어야 시작된다.
    """
    from v1.label.services.validation_service import _CHECKS

    documents = []
    ready = False
    for type_code, name, required, gives in SECOND_PASS_DOCUMENTS:
        document, filename, hidden = _slot_state(label, type_code)
        note, reads_font = format_note(filename) if document else ('', False)
        documents.append({
            'type_code': type_code,
            'name': name,
            'required': required,
            'gives': gives,
            'present': bool(document),
            'filename': filename,
            'hidden': hidden,
            'note': note,
            'reads_font': reads_font,
        })
        if required and document:
            ready = True

    missing = [d['name'] for d in documents
               if not d['present'] and not d['hidden']]

    return {
        'first': {
            'title': '1차 · 표시문구 검증',
            'target': '이 화면의 표시사항',
            'summary': '우리가 만든 표시사항이 규정에 맞는지 봅니다.',
            'check_count': len(_CHECKS),
            'ready': True,
        },
        'second': {
            'title': '2차 · 디자인시안 검증',
            'target': '문서함의 포장지 시안',
            'summary': '받은 시안이 확정한 표시사항과 같은지, 인쇄 규정에 맞는지 봅니다.',
            'ready': ready,
            'blocked_reason': '' if ready else '포장지 시안이 아직 없습니다.',
            'documents': documents,
            'missing': missing,
        },
    }
