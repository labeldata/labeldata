# -*- coding: utf-8 -*-
"""
포장지 시안을 문서함에 남긴다.

**들어오는 길이 둘이다.**

    2차 검증   시안을 올려 표시사항과 대조한다 (design_compare)
    불러오기   기본 정보 탭에서 사진으로 값을 채운다 (ocr 판독)

예전에는 앞의 길만 파일을 남겼다. 그래서 불러오기로 시안을 읽어 값을 다
채워 놓고도 **문서함에는 아무것도 없었다** — 2차 검증을 하려면 같은 파일을
다시 올려야 했고, 사용자는 "아까 올린 그 사진" 을 찾아 헤맸다.

한 벌로 둔다. 두 벌이면 판(version)을 세는 규칙이나 슬롯에 꽂는 규칙이
갈라지고, 어느 날 한쪽만 고쳐진다.
"""
from v1.products.models import (DocumentSlot, DocumentType, ProductDocument)

TYPE_CODE = 'DESIGN_PROOF'


def document_type():
    """포장지 시안 문서 종류. 없으면 만든다(계정마다 종류 목록이 다르다)."""
    doc_type, _created = DocumentType.objects.get_or_create(
        type_code=TYPE_CODE,
        defaults={
            'type_name': '포장지 시안',
            'description': '디자인 담당자가 만든 포장지 시안. 표시사항과 대조한 기록이 함께 남는다',
            'required_yn': False,
            'active_yn': True,
            'display_order': 1,
            'icon': 'bi-image',
            'color': '#1a73e8',
            'detection_keywords': '시안,도안,포장지',
            'expiry_alert_days': 0,
            'requires_expiry': False,
        },
    )
    return doc_type


def save(label, upload, user, source, extra=None):
    """
    시안 한 장을 남긴다. 같은 제품에 이미 있으면 **다음 판**으로 잇는다.

    Returns: 만든 ProductDocument
    """
    doc_type = document_type()
    latest = (ProductDocument.objects
              .filter(label=label, document_type=doc_type, active_yn=True)
              .order_by('-version', '-uploaded_datetime')
              .first())

    metadata = {'expiry_unlimited': True, 'source': source}
    if extra:
        metadata.update(extra)

    document = ProductDocument.objects.create(
        label=label,
        document_type=doc_type,
        file=upload,
        original_filename=getattr(upload, 'name', '') or '시안',
        file_size=getattr(upload, 'size', 0) or 0,
        uploaded_by=user,
        parent_document=latest,
        version=(latest.version + 1) if latest else 1,
        metadata=metadata,
    )

    # 필수 문서 칸이 있으면 꽂는다. 문서함에 올린 것과 같은 규칙이다 —
    # 목록에는 보이는데 칸은 "없음" 이라고 말하면 무엇을 더 해야 하는지
    # 알 수가 없다. **없는 칸을 새로 만들지는 않는다.**
    slot = DocumentSlot.objects.filter(
        label=label, document_type=doc_type, hidden_yn=False).first()
    if slot:
        slot.current_document = document
        slot.update_status()
        slot.save()
        document.slot = slot
        document.save(update_fields=['slot'])

    return document
