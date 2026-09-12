"""
업로드 파일(/media/) 접근 통제.

이전에는 config/urls.py 가 static_serve 로 /media/ 전체를 아무 검사 없이 서빙했다.
DEBUG=False 에서 업로드 파일이 404 나던 문제를 고치려던 것인데, 그 과정에서
접근 통제가 통째로 빠졌다. 비로그인 상태에서 URL 만 알면 협력업체 규격서·성적서가
그대로 내려받아졌고, 공유를 해제해도 막히지 않았다.

여기서는 경로 앞부분으로 소유 모델을 찾아 권한을 확인한 뒤에만 파일을 넘긴다.

설계 원칙
  - 기본은 거부. 규칙을 못 찾으면 로그인 사용자에게만 허용한다.
  - 민감 파일(제품 문서·제출물·회사 서류)은 소유자 또는 유효한 공유 권한자만.
  - 공유는 active_yn / 기간 / can_download_documents 를 모두 본다.
  - 협력사 매직링크(vendor) 업로드 화면은 파일을 내려받지 않으므로 영향 없다.
"""
import logging
import posixpath

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django.views.static import serve as static_serve

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 공유 권한 확인
# ─────────────────────────────────────────────────────────────────────────────

def _live_shares(user, label):
    """이 사용자가 이 표시사항에 대해 갖고 있는 살아 있는 공유."""
    from v1.products.models import ProductShare
    return ProductShare.objects.filter(
        label=label,
        active_yn=True,
        share_mode='PRIVATE',
        permission__can_download_documents=True,
    ).filter(
        Q(recipient_user=user) | Q(recipient_email__iexact=user.email)
    ).filter(
        Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
    )


def user_can_download_label_files(user, label, document=None) -> bool:
    """
    해당 표시사항(label)의 첨부 파일을 내려받을 수 있는가.

    **문서를 함께 넘겨라.** 문서함은 여러 회사의 서류가 함께 쌓이는 자리다.
    예전에는 이 함수에 문서 인자가 아예 없어서, 시험성적서 하나 내라고 부른
    협력업체가 그 제품의 **모든 것**을 받을 수 있었다 — 다른 협력업체의
    규격서, 아직 안 나온 포장지 도안, 품목제조보고서.

    document 를 안 주면 "이 제품에서 무엇이든 받을 수 있는가" 를 묻는 것이라,
    문서함 전체 보기가 꺼진 사람에게는 거짓이 된다. 한 건을 판정할 때는 반드시
    그 문서를 넘겨야 한다.
    """
    if label is None or not user.is_authenticated:
        return False
    if label.user_id_id == user.id:
        return True

    shares = list(_live_shares(user, label).select_related('permission')[:5])
    if not shares:
        return False
    if any(getattr(s.permission, 'can_view_all_documents', True) for s in shares):
        return True

    # 전체 보기가 꺼진 사람 — 자기가 올린 것만
    if document is None:
        return False
    return getattr(document, 'uploaded_by_id', None) == user.id


def visible_documents(user, label, queryset):
    """
    이 사용자에게 보여도 되는 문서만 남긴다.

    목록에서 거르지 않으면 파일은 못 받아도 **무엇이 있는지는 다 보인다.**
    거래처 이름과 서류 종류가 그대로 드러나므로 그것만으로도 새는 것이다.
    """
    if label is None or not user.is_authenticated:
        return queryset.none()
    if label.user_id_id == user.id:
        return queryset

    shares = list(_live_shares(user, label).select_related('permission')[:5])
    if any(getattr(s.permission, 'can_view_all_documents', True) for s in shares):
        return queryset
    if not shares:
        # 내려받기 권한이 아예 없는 공유(뷰어 등)는 여기서 거르지 않는다.
        # 목록을 보는 것과 파일을 받는 것은 다른 문이고, 그 문은 위 함수가 지킨다.
        return queryset
    return queryset.filter(uploaded_by=user)


# ─────────────────────────────────────────────────────────────────────────────
# 경로별 접근 규칙
# 각 함수는 (request, 저장경로) -> bool
# ─────────────────────────────────────────────────────────────────────────────

def _check_product_document(request, path) -> bool:
    from v1.products.models import ProductDocument
    doc = (ProductDocument.objects
           .select_related('label')
           .filter(file=path)
           .first())
    if not doc:
        return False
    return user_can_download_label_files(request.user, doc.label, doc)


def _check_doc_submission(request, path) -> bool:
    """협력사가 제출한 파일 — 요청한 사람과 제출한 사람만"""
    from v1.products.models import DocumentSubmission
    sub = (DocumentSubmission.objects
           .select_related('request')
           .filter(file=path)
           .first())
    if not sub:
        return False
    email = (request.user.email or '').lower()
    if sub.request.requester_id == request.user.id:
        return True
    if email and (sub.submitted_by_email or '').lower() == email:
        return True
    # 요청에 연결된 제품을 공유받은 사람도 열람 가능
    return user_can_download_label_files(request.user, getattr(sub.request, 'linked_label', None))


def _check_doc_request_attachment(request, path) -> bool:
    """자료 요청에 첨부한 양식 — 요청자와 수신자만"""
    from v1.products.models import DocumentRequest
    dr = DocumentRequest.objects.filter(attachment=path).first()
    if not dr:
        return False
    email = (request.user.email or '').lower()
    if dr.requester_id == request.user.id:
        return True
    return bool(email) and (dr.recipient_email or '').lower() == email


def _check_company_document(request, path) -> bool:
    from v1.user_management.models import CompanyDocument
    return CompanyDocument.objects.filter(doc_file=path, user=request.user).exists()


def _check_editor_image(request, path) -> bool:
    from v1.label_editor.models import EditorImage
    img = EditorImage.objects.select_related('label').filter(file=path).first()
    if not img:
        return False
    return user_can_download_label_files(request.user, img.label)


def _allow_authenticated(request, path) -> bool:
    """로그인 사용자면 허용 (게시판 첨부·프로필 이미지 등 준공개 자원)"""
    return request.user.is_authenticated


# 앞부분이 긴 것부터 검사한다
ACCESS_RULES = (
    ('v2/product_documents/', _check_product_document),
    ('doc_submissions/',      _check_doc_submission),
    ('doc_requests/',         _check_doc_request_attachment),
    ('company_documents/',    _check_company_document),
    ('label_editor/',         _check_editor_image),
    ('board_files/',          _allow_authenticated),
    ('board_images/',         _allow_authenticated),
    ('profiles/',             _allow_authenticated),
    ('label_attachments/',    _allow_authenticated),
)


@login_required
def protected_media_serve(request, path):
    """
    권한을 확인한 뒤 /media/ 파일을 서빙한다.

    규칙이 없는 경로는 로그인 사용자에게만 허용한다(기본 거부에 가깝게).
    권한이 없으면 존재 여부를 흘리지 않도록 403 이 아니라 404 를 돌려준다.
    """
    from django.conf import settings

    # 상위 디렉터리 탈출 방지 (static_serve 도 막지만 한 번 더 확인)
    normalized = posixpath.normpath(path.replace('\\', '/')).lstrip('/')
    if normalized.startswith('../') or normalized == '..':
        raise Http404

    checker = _allow_authenticated
    for prefix, fn in ACCESS_RULES:
        if normalized.startswith(prefix):
            checker = fn
            break

    try:
        allowed = checker(request, normalized)
    except Exception:
        logger.exception('[미디어 접근] 권한 확인 실패: %s', normalized)
        allowed = False

    if not allowed:
        logger.warning('[미디어 접근] 거부: user=%s path=%s', request.user, normalized)
        raise Http404

    return static_serve(request, normalized, document_root=settings.MEDIA_ROOT)


def downloadable_label_scopes(user):
    """
    내려받기가 허용된 '공유받은' 표시사항을 두 갈래로 나눈다.

    반환 (문서함 전체를 볼 수 있는 label_id, 본인이 올린 것만 볼 수 있는 label_id).

    같은 표시사항에 공유가 여러 건이면 넓은 쪽이 이긴다 —
    user_can_download_label_files 가 any() 로 판정하는 것과 같은 규칙이다.
    """
    if not user.is_authenticated:
        return set(), set()
    from v1.products.models import ProductShare
    rows = (
        ProductShare.objects.filter(
            active_yn=True,
            share_mode='PRIVATE',
            permission__can_download_documents=True,
        ).filter(
            Q(recipient_user=user) | Q(recipient_email__iexact=user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).values_list('label_id', 'permission__can_view_all_documents')
    )
    see_all, own_only = set(), set()
    for label_id, can_see_all in rows:
        (see_all if can_see_all else own_only).add(label_id)
    return see_all, own_only - see_all


def visible_documents_for_user(user, queryset):
    """
    **여러 표시사항이 섞인** 문서 목록을 거른다.

    visible_documents() 는 한 표시사항 안에서만 판정한다. 일괄 다운로드처럼
    여러 제품의 문서가 한 번에 넘어오는 자리에서는 이쪽을 써야 한다.
    label 단위 목록(downloadable_label_ids)만 보고 거르면 문서함 전체 보기가
    통째로 무시된다 — 협력업체가 남의 규격서를 ZIP 으로 받아 갔다.
    """
    if not user.is_authenticated:
        return queryset.none()
    see_all, own_only = downloadable_label_scopes(user)
    return queryset.filter(
        Q(label__user_id=user)
        | Q(label__my_label_id__in=see_all)
        | (Q(label__my_label_id__in=own_only) & Q(uploaded_by=user))
    )
