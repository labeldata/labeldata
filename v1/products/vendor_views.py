"""
협력사 포털 뷰 - 매직 링크 기반 문서 업로드
회원가입 없이 upload_token(UUID hex)으로 접근하는 standalone 화면
"""
 
import os
import logging
from datetime import date
 
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_POST
from django.utils import timezone
 
logger = logging.getLogger(__name__)
 
 
def _get_doc_request(token: str):
    """upload_token으로 DocumentRequest 조회. 없으면 None 반환."""
    from v1.products.models import DocumentRequest
    try:
        result = DocumentRequest.objects.select_related('requester', 'linked_label').get(
            upload_token=token
        )
        logger.info(f"✓ DocumentRequest 찾음: token={token}, status={result.status}")
        return result
    except DocumentRequest.DoesNotExist:
        # DEBUG: 해당 토큰이 있는지 확인
        exists = DocumentRequest.objects.filter(upload_token=token).exists()
        all_tokens = list(DocumentRequest.objects.values_list('upload_token', flat=True)[:5])
        logger.warning(f"✗ DocumentRequest 없음: token={token}, exists={exists}")
        logger.info(f"  DB의 최근 5개 토큰: {all_tokens}")
        return None
 
 
def _is_expired(dr) -> bool:
    """만료 여부 확인. due_date를 링크 만료일로 활용."""
    if not dr.due_date:
        return False
    return dr.due_date < date.today()
 
 
def vendor_upload_view(request, token):
    """
    GET: 협력사 문서 업로드 폼
    - GNB/사이드바 없는 standalone 화면
    - 요청된 문서 목록과 파일 첨부 UI만 표시
    """
    dr = _get_doc_request(token)
 
    if dr is None:
        return render(request, 'vendor/upload_expired.html', {
            'reason': 'invalid',
        }, status=404)
 
    if dr.status == dr.STATUS_CANCELLED:
        return render(request, 'vendor/upload_expired.html', {
            'reason': 'cancelled',
        }, status=410)
 
    if dr.status == dr.STATUS_ACCEPTED:
        return render(request, 'vendor/upload_expired.html', {
            'reason': 'already_submitted',
        }, status=410)
 
    if _is_expired(dr):
        return render(request, 'vendor/upload_expired.html', {
            'reason': 'expired',
        }, status=410)
 
    requested_docs = dr.requested_documents or []
 
    return render(request, 'vendor/upload_form.html', {
        'dr': dr,
        'token': token,
        'requested_docs': requested_docs,
        'requester_name': dr.requester.get_full_name() or dr.requester.username,
        'product_name': (
            dr.linked_label.my_label_name if dr.linked_label else dr.target_product_name
        ),
    })
 
 
@require_POST
def vendor_submit_view(request, token):
    """
    POST: 파일 제출 처리
    1. 토큰 재검증
    2. DocumentSubmission + ProductDocument 생성
    3. status → ACCEPTED (토큰 즉시 만료)
    4. Vision AI 비동기 처리 트리거
    5. 완료 페이지로 redirect
    """
    from v1.products.models import DocumentRequest, DocumentSubmission, ProductDocument, DocumentType
    try:
        from v1.products.services.vision_service import process_document_vision_async, infer_ai_group
    except ImportError as e:
        logger.error(f"Import 오류: {e}")
        # Fallback: 함수 없을 때 대체 처리
        def infer_ai_group(type_name, type_code=None):
            return 'A'  # 기본값
        def process_document_vision_async(doc_id):
            pass  # 비동기 처리 건너뜀
 
    dr = _get_doc_request(token)
 
    # 재검증
    if dr is None or dr.status == dr.STATUS_CANCELLED:
        return render(request, 'vendor/upload_expired.html', {'reason': 'invalid'}, status=410)
    if dr.status == dr.STATUS_ACCEPTED:
        return render(request, 'vendor/upload_expired.html', {'reason': 'already_submitted'}, status=410)
    if _is_expired(dr):
        return render(request, 'vendor/upload_expired.html', {'reason': 'expired'}, status=410)
 
    submitted_files = []
    vendor_name = request.POST.get('vendor_name', '').strip()
    vendor_email = request.POST.get('vendor_email', '').strip() or dr.recipient_email
    notes = request.POST.get('notes', '').strip()
 
    # 업로드된 파일 처리
    for key, uploaded_file in request.FILES.items():
        # key 형식: "file_<type_id>" 또는 "file_0" 등
        type_id = None
        if key.startswith('file_'):
            try:
                type_id = int(key.split('_', 1)[1])
            except (ValueError, IndexError):
                pass
 
        # DocumentType 조회 (없으면 첫 번째 활성 타입 사용)
        doc_type = None
        if type_id:
            doc_type = DocumentType.objects.filter(type_id=type_id, active_yn=True).first()
        if not doc_type:
            doc_type = DocumentType.objects.filter(active_yn=True).order_by('display_order').first()
 
        if not doc_type:
            logger.warning("활성 DocumentType 없음 - 파일 저장 건너뜀")
            continue
 
        # DocumentSubmission 저장
        submission = DocumentSubmission.objects.create(
            request=dr,
            document_type=doc_type.type_name,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            submitted_by_email=vendor_email,
            submitted_by_name=vendor_name,
            notes=notes,
        )
 
        # 연결된 제품이 있으면 ProductDocument도 자동 생성
        if dr.linked_label:
            _, ext = os.path.splitext(uploaded_file.name)
            ai_group = infer_ai_group(doc_type.type_name, doc_type.type_code)
 
            # 파일 포인터 리셋 후 ProductDocument에 저장
            uploaded_file.seek(0)
            product_doc = ProductDocument.objects.create(
                label=dr.linked_label,
                document_type=doc_type,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                file_extension=ext.lower(),
                document_title=doc_type.type_name,
                description=f"협력사 제출: {vendor_name or vendor_email}",
                uploaded_by=None,  # 비회원 제출
                metadata={
                    'ai_status': 'PENDING',
                    'ai_group': ai_group,
                    'vendor_submission_id': submission.submission_id,
                    'submitted_by_email': vendor_email,
                    'submitted_by_name': vendor_name,
                },
            )
            submitted_files.append(product_doc.document_id)
 
            # Vision AI 비동기 처리 트리거
            process_document_vision_async(product_doc.document_id)
 
    if not submitted_files and not request.FILES:
        # 파일 없이 제출 → 폼으로 돌아감
        dr_data = {
            'dr': dr,
            'token': token,
            'requested_docs': dr.requested_documents or [],
            'requester_name': dr.requester.get_full_name() or dr.requester.username,
            'product_name': (
                dr.linked_label.my_label_name if dr.linked_label else dr.target_product_name
            ),
            'error': '파일을 하나 이상 첨부해주세요.',
        }
        return render(request, 'vendor/upload_form.html', dr_data)
 
    # status → ACCEPTED (토큰 즉시 만료 - 재사용 차단)
    dr.status = DocumentRequest.STATUS_ACCEPTED
    dr.save(update_fields=['status', 'updated_datetime'])
 
    return redirect('vendor:upload_complete')
 
 
def vendor_expired_view(request):
    """만료/에러 페이지."""
    reason = request.GET.get('reason', 'invalid')
    return render(request, 'vendor/upload_expired.html', {'reason': reason})
 
 
def vendor_complete_view(request):
    """제출 완료 페이지 + PLG 전환 유도."""
    return render(request, 'vendor/upload_complete.html')