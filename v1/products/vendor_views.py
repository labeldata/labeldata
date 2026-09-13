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

from v1.common import uploads

def _vendor_form_context(dr, token, error=''):
    """
    협력사 제출 폼을 다시 그릴 때 쓰는 컨텍스트. **한 곳에서 만든다.**

    오류 재렌더가 두 벌이면 한쪽만 고쳐졌을 때 그 경로에서만 화면이 빈다.
    """
    return {
        'dr': dr,
        'token': token,
        'requested_docs': dr.requested_documents or [],
        'requester_name': dr.requester.get_full_name() or dr.requester.username,
        'product_name': (
            dr.linked_label.my_label_name if dr.linked_label else dr.target_product_name
        ),
        'error': error,
    }


from v1.common import uploads
 
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
 
    #  예전에는 한 번 내면 토큰이 즉시 만료돼 **다시 낼 수 없었다.**
    #  파일을 잘못 냈거나 스캔이 잘렸거나 최신본으로 바꾸려면 협력사가 할 수
    #  있는 것이 없었고, 요청자에게 연락해 새 요청을 받아야 했다. 자료가 한
    #  번에 제대로 오는 경우가 드물다는 걸 생각하면 자주 걸리던 길이다.
    #  기한 안에는 다시 받는다 — 문서함에는 이미 버전이 쌓인다.
 
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
    if _is_expired(dr):
        return render(request, 'vendor/upload_expired.html', {'reason': 'expired'}, status=410)
 
    submitted_files = []
    vendor_name = request.POST.get('vendor_name', '').strip()
    vendor_email = request.POST.get('vendor_email', '').strip() or dr.recipient_email
    notes = request.POST.get('notes', '').strip()
 
    # 업로드된 파일을 **하나도 빠뜨리지 않고** 편다.
    #
    # 예전에는 `request.FILES.items()` 로 돌았다. MultiValueDict.items() 는
    # 키마다 **마지막 값 하나만** 돌려준다 — 범용 칸(`file_0`)은 multiple 이라
    # 여러 개가 오는데, 셋을 붙이면 하나만 저장되고 둘이 조용히 사라졌다.
    # 화면은 고른 파일 전부를 초록 체크와 함께 그려 주고 "제출 완료" 라고
    # 말했으므로 협력사도 요청자도 없어진 것을 알 수 없었다.
    incoming = [(k, f) for k, files in request.FILES.lists() for f in files]

    # 화면은 "PDF, JPG, PNG, DOCX (최대 20MB)" 라고 약속하는데 서버에는
    # 크기·확장자·할당량 검사가 **하나도 없었다.** 로그인도 안 한 협력사가
    # 요청자의 저장 한도를 얼마든지 넘길 수 있었고 .html·.svg 도 그대로
    # 받았다 — 그 파일을 여는 사람은 바로 요청자다.
    # 저장소 표준 한 곳(common/uploads.check)을 그대로 쓴다.
    rejected = []
    accepted = []
    for key, uploaded_file in incoming:
        problem = uploads.check(dr.requester, uploaded_file, kind='서류')
        if problem:
            rejected.append('%s — %s' % (uploaded_file.name, problem))
        else:
            accepted.append((key, uploaded_file))

    if not accepted:
        why = (' / '.join(rejected) if rejected
               else '파일을 하나 이상 첨부해주세요.')
        return render(request, 'vendor/upload_form.html',
                      _vendor_form_context(dr, token, error=why))

    for key, uploaded_file in accepted:
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
 
    #  '수락' 이 아니라 '제출 완료' 다. 예전에는 둘 다 ACCEPTED 라, 하겠다고만
    #  하고 안 낸 건과 실제로 낸 건이 목록에서 구분되지 않았다.
    dr.status = DocumentRequest.STATUS_SUBMITTED
    dr.save(update_fields=['status', 'updated_datetime'])

    if rejected:
        # 일부는 받고 일부는 못 받았다. 조용히 넘기면 협력사는 다 낸 줄 알고
        # 창을 닫는다.
        return render(request, 'vendor/upload_form.html',
                      _vendor_form_context(
                          dr, token,
                          error='%d건을 받았습니다. 다음은 받지 못했습니다 — %s'
                                % (len(accepted), ' / '.join(rejected))))

    return redirect('vendor:upload_complete')
 
 
def vendor_expired_view(request):
    """만료/에러 페이지."""
    reason = request.GET.get('reason', 'invalid')
    return render(request, 'vendor/upload_expired.html', {'reason': reason})
 
 
def vendor_complete_view(request):
    """제출 완료 페이지 + PLG 전환 유도."""
    return render(request, 'vendor/upload_complete.html')