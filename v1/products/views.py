# ==================== 제품 관리 Views (V2) ====================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch, Sum, Case, When, IntegerField
from django.db import models
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils import timezone
from django.http import FileResponse, Http404, HttpResponse
from datetime import timedelta, datetime
from urllib.parse import quote
import zipfile
import io
import os
import json

from .models import Product, ProductFolder, ProductAccessLog, ProductMetadata, FoodType, CountryList

# 앱 통합 뷰를 위한 추가 import
from v1.bom.models import ProductBOM
from .models import ProductDocument, ProductComment, ProductShare, SharedProductReceipt, DocumentType, SharePermission, ProductNotification
from v1.label.models import MyLabel

from .forms import ProductForm


# ==================== Google Drive 스타일 탐색기 ====================

@login_required
def product_explorer(request, folder_id=None):
    """Google Drive 스타일 제품 탐색기"""
    user = request.user
    
    # 시스템 폴더 자동 생성 (최초 접속)
    ProductFolder.get_or_create_system_folders(user)
    
    # 현재 폴더
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(ProductFolder, folder_id=folder_id, owner=user)
    
    # 하위 폴더 목록
    subfolders = ProductFolder.objects.filter(
        owner=user,
        parent=current_folder
    ).order_by('sort_order', 'name')
    
    # ─── filter_type: 전체(ALL) / 내 제품(MINE) / 참여 중(COLLAB) ───
    filter_type = request.GET.get('filter', 'ALL')

    # 나에게 공유된 label_id 목록
    shared_to_me_ids = list(
        ProductShare.objects.filter(
            recipient_user=user,
            is_active=True,
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).values_list('label_id', flat=True)
    )
    collab_count = len(set(shared_to_me_ids))

    # 현재 폴더의 제품 목록 (MyLabel 기반)
    if filter_type == 'MINE':
        labels = MyLabel.objects.filter(user_id=user, delete_YN='N')
    elif filter_type == 'COLLAB':
        labels = MyLabel.objects.filter(
            my_label_id__in=shared_to_me_ids, delete_YN='N'
        ).exclude(user_id=user)
    else:  # ALL
        labels = MyLabel.objects.filter(
            Q(user_id=user) | Q(my_label_id__in=shared_to_me_ids),
            delete_YN='N',
        ).distinct()
    labels = labels.order_by('-update_datetime')
    
    # 뷰 타입(grid/list)
    view_type = request.GET.get('view', 'grid')
    
    # 정렬
    sort_by = request.GET.get('sort', '-update_datetime')
    if sort_by in ['my_label_name', '-my_label_name', 'create_datetime', '-create_datetime', 
                   'update_datetime', '-update_datetime']:
        labels = labels.order_by(sort_by)
    
    # 검색
    search_query = request.GET.get('q', '')
    if search_query:
        labels = labels.filter(
            Q(my_label_name__icontains=search_query) |
            Q(prdlst_nm__icontains=search_query) |
            Q(prdlst_dcnm__icontains=search_query)
        )
    
    # 페이지네이션 적용
    per_page = request.GET.get('per_page', '50')
    try:
        per_page = int(per_page)
        if per_page not in [25, 50, 100, 200]:
            per_page = 50
    except (ValueError, TypeError):
        per_page = 50
    
    paginator = Paginator(labels, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # 현재 페이지의 제품만 처리
    current_page_labels = page_obj.object_list
    
    # ProductMetadata에서 즐겨찾기 상태 가져오기
    products_data = []
    metadata_dict = {}
    
    # 한번에 모든 metadata 가져오기
    label_ids = [label.my_label_id for label in current_page_labels]
    metadatas = ProductMetadata.objects.filter(
        label__my_label_id__in=label_ids
    ).select_related('label')
    
    for meta in metadatas:
        metadata_dict[meta.label.my_label_id] = meta
    
    # 각 제품의 문서 개수 가져오기
    document_counts = {}
    doc_counts_qs = ProductDocument.objects.filter(
        label__my_label_id__in=label_ids,
        is_active=True
    ).values('label__my_label_id').annotate(count=Count('document_id'))
    
    for item in doc_counts_qs:
        document_counts[item['label__my_label_id']] = item['count']
    
    # 필수 문서 통계 (ProductDocument 직접 조회 - DocumentSlot 미생성 제품 포함)
    required_doc_type_ids = list(
        DocumentType.objects.filter(is_required=True, is_active=True).values_list('type_id', flat=True)
    )
    required_per_product = len(required_doc_type_ids)  # 모든 제품의 필수스 동일

    # 제품별 실제 등록된 필수 문서 카운트 (is_active=True, document_type__in required)
    filled_agg = (
        ProductDocument.objects.filter(
            label__my_label_id__in=label_ids,
            is_active=True,
            document_type_id__in=required_doc_type_ids,
        )
        .values('label__my_label_id', 'document_type_id')
        .distinct()
    )
    filled_by_label = {}
    for row in filled_agg:
        lid = row['label__my_label_id']
        filled_by_label[lid] = filled_by_label.get(lid, 0) + 1

    document_stats = {}
    for label_id in label_ids:
        total = document_counts.get(label_id, 0)
        filled = filled_by_label.get(label_id, 0)
        document_stats[label_id] = {
            'total': total,
            'required': required_per_product,
            'filled': filled,
            'rate': (filled / required_per_product * 100) if required_per_product > 0 else 100,
        }
    
    # BOM 통계 가져오기
    bom_stats = {}
    from v1.bom.models import ProductBOM
    for label_id in label_ids:
        bom_items = ProductBOM.objects.filter(parent_label__my_label_id=label_id)
        ingredient_count = bom_items.count()
        total_ratio = bom_items.aggregate(total=models.Sum('usage_ratio'))['total'] or 0
        
        bom_stats[label_id] = {
            'count': ingredient_count,
            'ratio': float(total_ratio),
            'complete': total_ratio >= 99.9
        }
    
    # 영양성분 데이터 입력 여부
    nutrition_stats = {}
    for label_id in label_ids:
        # V1 MyLabel의 calories 필드로 확인
        label_obj = next((l for l in current_page_labels if l.my_label_id == label_id), None)
        has_nutrition = False
        if label_obj and label_obj.calories:
            has_nutrition = True
        nutrition_stats[label_id] = has_nutrition
    
    # 권한 부여 인원 통계
    permission_stats = {}
    for label_id in label_ids:
        share_count = ProductShare.objects.filter(
            label__my_label_id=label_id,
            is_active=True
        ).values('recipient_user').distinct().count()
        permission_stats[label_id] = share_count
    
    # 현재 페이지 라벨에서 내가 받은 역할 코드 조회
    my_role_map = {}  # label_id → role_code
    for share in ProductShare.objects.filter(
        recipient_user=user,
        label_id__in=label_ids,
        is_active=True,
    ).select_related('permission'):
        try:
            my_role_map[share.label_id] = share.permission.role_code
        except Exception:
            my_role_map[share.label_id] = 'VIEWER'

    for label in current_page_labels:
        metadata = metadata_dict.get(label.my_label_id)
        is_owned = (label.user_id_id == user.id)
        my_role = None if is_owned else my_role_map.get(label.my_label_id, 'VIEWER')
        products_data.append({
            'label': label,
            'metadata': metadata,
            'is_starred': metadata.is_starred if metadata else False,
            'document_count': document_counts.get(label.my_label_id, 0),
            'document_stats': document_stats.get(label.my_label_id, {'total': 0, 'required': 0, 'filled': 0, 'rate': 0}),
            'bom_stats': bom_stats.get(label.my_label_id, {'count': 0, 'ratio': 0, 'complete': False}),
            'has_nutrition': nutrition_stats.get(label.my_label_id, False),
            'permission_count': permission_stats.get(label.my_label_id, 0),
            'is_owned': is_owned,
            'my_role': my_role,
        })
    
    # 브레드크럼 경로
    breadcrumb = []
    temp_folder = current_folder
    while temp_folder:
        breadcrumb.insert(0, temp_folder)
        temp_folder = temp_folder.parent
    
    # 접근 로그 (최근 열어본 제품에 표시)
    recent_product_ids = ProductAccessLog.objects.filter(
        user=user
    ).values_list('product_id', flat=True)[:50]
    
    # 즐겨찾기 총 개수 (현재 filter_type + 검색어 기준, 페이지네이션 무관)
    starred_count = ProductMetadata.objects.filter(
        label__in=labels,
        is_starred=True,
    ).count()

    # 즐겨찾기 제품 (루트 폴더에서만, 사이드바용)
    starred_items = []
    if not current_folder:
        # ProductMetadata에서 즐겨찾기된 제품의 label 가져오기
        starred_metadata = ProductMetadata.objects.filter(
            label__in=labels,
            is_starred=True
        ).select_related('label').order_by('-starred_datetime')[:10]
        starred_items = [meta.label for meta in starred_metadata]

    # 공유 문서함 요약 (최근 수신)
    shared_receipts = SharedProductReceipt.objects.filter(
        receiver=user
    ).select_related('share__label', 'share__created_by').order_by('-received_datetime')[:5]

    # 만료 예정 문서 요약 (30일 이내)
    today = timezone.now().date()
    alert_date = today + timedelta(days=30)
    expiring_documents = ProductDocument.objects.filter(
        label__user_id=user,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=alert_date
    ).select_related('label', 'document_type').order_by('expiry_date')[:5]
    
    # 승인 대기 및 검토 필요 통계
    approval_pending_count = ProductMetadata.objects.filter(
        label__user_id=user,
        label__delete_YN='N',
        status=ProductMetadata.Status.REQUESTING
    ).count()
    
    review_needed_count = ProductMetadata.objects.filter(
        label__user_id=user,
        label__delete_YN='N',
        status=ProductMetadata.Status.REVIEW
    ).count()
    
    context = {
        'current_folder': current_folder,
        'subfolders': subfolders,
        'products_data': products_data,
        'breadcrumb': breadcrumb,
        'view_type': view_type,
        'search_query': search_query,
        'recent_product_ids': list(recent_product_ids),
        'starred_items': starred_items,
        'shared_receipts': shared_receipts,
        'expiring_documents': expiring_documents,
        'recent_products': products_data[:4],
        'folders': subfolders,
        'files': products_data,
        'approval_pending_count': approval_pending_count,
        'review_needed_count': review_needed_count,
        'page_obj': page_obj,
        'per_page': per_page,
        'total_products_count': paginator.count,
        'filter_type': filter_type,
        'collab_count': collab_count,
        'starred_count': starred_count,
    }
    return render(request, 'products/product_explorer.html', context)


# ==================== 제품 상세 ====================

@login_required
def product_detail(request, product_id):
    """제품 상세 보기 - V2 스타일 (BOM, 문서 등록 등)"""
    # V2에서는 label_id를 product_id로 받음
    # 먼저 직접 MyLabel 조회 시도 (오너)
    shared_share = None
    is_owner = False
    try:
        label = MyLabel.objects.get(my_label_id=product_id, user_id=request.user)
        is_owner = True
    except MyLabel.DoesNotExist:
        # 공유 사용자 접근 허용
        shared_share = ProductShare.objects.filter(
            label__my_label_id=product_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label').first()

        if shared_share:
            label = shared_share.label
        else:
            # MyLabel이 없으면 ProductMetadata를 통해 조회 시도 (오너만 가능)
            try:
                metadata = ProductMetadata.objects.select_related('label').get(
                    metadata_id=product_id,
                    label__user_id=request.user
                )
                label = metadata.label
                is_owner = True
            except ProductMetadata.DoesNotExist:
                # 둘 다 없으면 404
                messages.error(request, '제품을 찾을 수 없습니다.')
                return redirect('products:product_explorer')
    
    # ProductMetadata 자동 생성 (없는 경우 - 오너만 가능)
    try:
        metadata = ProductMetadata.objects.get(label=label)
    except ProductMetadata.DoesNotExist:
        if not is_owner:
            messages.error(request, '제품 메타데이터를 찾을 수 없습니다.')
            return redirect('products:product_explorer')

        # 고유한 product_code 생성
        user_product_count = ProductMetadata.objects.filter(
            label__user_id=request.user
        ).count()

        # 중복되지 않는 고유 코드 찾기
        product_code = None
        max_attempts = 100
        for i in range(max_attempts):
            candidate_code = f"PRD-{request.user.id}-{user_product_count + i + 1:04d}"
            if not ProductMetadata.objects.filter(product_code=candidate_code).exists():
                product_code = candidate_code
                break

        # 고유 코드를 찾지 못한 경우 타임스탬프 추가
        if not product_code:
            import time
            product_code = f"PRD-{request.user.id}-{int(time.time())}"

        # ProductMetadata 생성
        metadata = ProductMetadata.objects.create(
            label=label,
            product_code=product_code,
            is_starred=False
        )
    
    # BOM 정보 조회
    bom_items = ProductBOM.objects.filter(
        parent_label=label,
        is_active=True
    ).select_related('child_label', 'shared_receipt').order_by('level', 'sort_order')
    
    # 문서 정보 조회
    documents = ProductDocument.objects.filter(
        label=label,
        is_active=True
    ).order_by('-uploaded_datetime')
    
    # 문서 타입별 그룹화
    document_types = DocumentType.objects.filter(is_active=True).order_by('display_order', 'type_name')
    documents_by_type = {}
    for dtype in document_types:
        docs = documents.filter(document_type=dtype)
        if docs.exists():
            documents_by_type[dtype] = docs
    
    # 타입 미지정 문서
    untyped_docs = documents.filter(document_type__isnull=True)
    if untyped_docs.exists():
        documents_by_type['기타'] = untyped_docs
    
    # 공유 정보 조회 (현재 제품)
    shares = ProductShare.objects.filter(
        label=label,
        is_active=True
    ).select_related('recipient_user').order_by('-created_datetime')
    share_permissions = SharePermission.objects.filter(share__in=shares)
    permission_map = {permission.share_id: permission for permission in share_permissions}
    for share in shares:
        share.permission_record = permission_map.get(share.share_id)
        share.display_name = (
            share.recipient_name
            or (share.recipient_user.username if share.recipient_user else None)
            or share.recipient_email
            or '미가입'
        )
    
    # 내가 owner인 모든 제품의 공유자 목록 조회 (팔레트용)
    all_shared_users = []
    if is_owner:
        # 현재 사용자가 owner인 모든 제품 찾기
        my_labels = MyLabel.objects.filter(user_id=request.user)
        
        # 이 제품들에 대한 모든 공유 정보
        all_shares = ProductShare.objects.filter(
            label__in=my_labels,
            is_active=True
        ).select_related('recipient_user').order_by('-created_datetime')
        
        # 중복 제거를 위해 email 기준으로 unique한 사용자만
        seen_emails = set()
        for share in all_shares:
            if share.recipient_email not in seen_emails:
                seen_emails.add(share.recipient_email)
                
                # 현재 제품에서의 권한 정보 확인
                current_share = shares.filter(recipient_email=share.recipient_email).first()
                if current_share:
                    share.permission_record = permission_map.get(current_share.share_id)
                    share.share_id = current_share.share_id
                else:
                    share.permission_record = None
                    share.share_id = None
                
                all_shared_users.append(share)
                # 템플릿에서 None.username 조회 방지: display_name 미리 계산
                share.display_name = (
                    share.recipient_name
                    or (share.recipient_user.username if share.recipient_user else None)
                    or share.recipient_email
                    or '미가입'
                )
    elif shared_share:
        # EDITOR 등 공유받은 사용자: 현재 제품의 공유자만 팔레트에 표시
        for share in shares:
            if not hasattr(share, 'display_name'):
                share.display_name = (
                    share.recipient_name
                    or (share.recipient_user.username if share.recipient_user else None)
                    or share.recipient_email
                    or '미가입'
                )
            all_shared_users.append(share)

    # 상태 기반 권한 계산 (역할 기반)
    status = metadata.status

    # ── 단방향 전이 맵 (각 상태에서 이동 가능한 action 키) ──
    # action 키 → Status 값은 product_update_status 뷰에서 정의
    status_actions_map = {
        ProductMetadata.Status.DRAFT:      ['requesting'],
        ProductMetadata.Status.REQUESTING: ['submitted', 'draft'],
        ProductMetadata.Status.SUBMITTED:  ['review', 'requesting'],
        ProductMetadata.Status.REVIEW:     ['pending', 'submitted'],
        ProductMetadata.Status.PENDING:    ['confirmed', 'review'],
        ProductMetadata.Status.CONFIRMED:  ['draft'],   # → 새 버전으로 돌아감
    }

    user_role = 'OWNER' if is_owner else 'VIEWER'
    if shared_share and not is_owner:
        share_permission = SharePermission.objects.filter(share=shared_share).first()
        if share_permission:
            user_role = share_permission.role_code

    role_labels = {
        'OWNER':    '관리자',
        'UPLOADER': '자료 제출',
        'EDITOR':   '공동 작성',
        'REVIEWER': '검토/QA',
        'APPROVER': '최종 승인',
        'VIEWER':   '뷰어',
    }

    available_actions = []
    can_edit = False
    can_upload_documents = False
    can_comment = False
    can_delete_product = False

    # ── 상태별 편집 가능 역할 ──
    # DRAFT           : OWNER, EDITOR
    # REQUESTING      : OWNER, EDITOR, UPLOADER
    # SUBMITTED/REVIEW: OWNER, EDITOR, REVIEWER
    # PENDING         : OWNER, EDITOR, APPROVER
    # CONFIRMED       : OWNER, EDITOR (다른 역할은 수정 불가)

    edit_roles_by_status = {
        ProductMetadata.Status.DRAFT:      {'OWNER', 'EDITOR'},
        ProductMetadata.Status.REQUESTING: {'OWNER', 'EDITOR', 'UPLOADER'},
        ProductMetadata.Status.SUBMITTED:  {'OWNER', 'EDITOR'},
        ProductMetadata.Status.REVIEW:     {'OWNER', 'EDITOR'},
        ProductMetadata.Status.PENDING:    {'OWNER', 'EDITOR', 'APPROVER'},
        ProductMetadata.Status.CONFIRMED:  {'OWNER', 'EDITOR'},
    }
    can_edit = user_role in edit_roles_by_status.get(status, set())

    if user_role == 'OWNER':
        can_upload_documents = True
        can_comment = True
        can_delete_product = True
        available_actions = status_actions_map.get(status, [])
    elif user_role == 'EDITOR':
        can_upload_documents = True
        can_comment = True
        available_actions = status_actions_map.get(status, [])
    elif user_role == 'UPLOADER':
        can_upload_documents = True
        can_comment = True
        if status == ProductMetadata.Status.REQUESTING:
            available_actions = ['submitted']
    elif user_role == 'REVIEWER':
        can_comment = True
        if status in [ProductMetadata.Status.SUBMITTED, ProductMetadata.Status.REVIEW]:
            available_actions = ['pending']
    elif user_role == 'APPROVER':
        can_comment = True
        if status == ProductMetadata.Status.PENDING:
            available_actions = ['confirmed']
    else:  # VIEWER
        can_comment = True
    
    # 댓글 정보 조회
    comments = ProductComment.objects.filter(
        label=label,
        parent__isnull=True
    ).select_related('author').prefetch_related(
        Prefetch('replies', queryset=ProductComment.objects.select_related('author').order_by('created_at'))
    ).order_by('-created_at')

    # 댓글 작성자들의 역할 정보 조회
    author_ids = set()
    for comment in comments:
        if comment.author_id:
            author_ids.add(comment.author_id)
        for reply in comment.replies.all():
            if reply.author_id:
                author_ids.add(reply.author_id)

    author_roles = {}
    if author_ids:
        owner_user_id = label.user_id.id if label.user_id else None
        
        shared_users_permissions = SharePermission.objects.filter(
            share__label=label,
            share__recipient_user_id__in=author_ids,
            share__is_active=True
        ).select_related('share')

        share_roles = {
            p.share.recipient_user_id: role_labels.get(p.role_code, '참여자')
            for p in shared_users_permissions
        }

        for author_id in author_ids:
            if author_id == owner_user_id:
                author_roles[author_id] = role_labels.get('OWNER', '관리자')
            else:
                author_roles[author_id] = share_roles.get(author_id, '참여자')

    # 필드별 댓글 존재 여부
    comment_fields = set(comments.values_list('field_name', flat=True))
    
    # 활동 로그 조회
    from .models import ProductActivityLog
    activity_logs = ProductActivityLog.objects.filter(
        label=label
    ).select_related('user').order_by('-created_at')[:50]  # 최근 50개
    
    # 활동 로그 작성자들의 권한 정보 조회
    activity_author_ids = set()
    for log in activity_logs:
        if log.user_id:
            activity_author_ids.add(log.user_id)
    
    activity_author_roles = {}
    if activity_author_ids:
        owner_user_id = label.user_id.id if label.user_id else None
        
        activity_shared_permissions = SharePermission.objects.filter(
            share__label=label,
            share__recipient_user_id__in=activity_author_ids,
            share__is_active=True
        ).select_related('share')
        
        activity_share_roles = {
            p.share.recipient_user_id: role_labels.get(p.role_code, '참여자')
            for p in activity_shared_permissions
        }
        
        for author_id in activity_author_ids:
            if author_id == owner_user_id:
                activity_author_roles[author_id] = role_labels.get('OWNER', '관리자')
            else:
                activity_author_roles[author_id] = activity_share_roles.get(author_id, '참여자')
    
    # 식품유형과 원산지 목록 추가
    food_types = FoodType.objects.all().order_by('food_group', 'food_type')
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    countries = CountryList.objects.all().order_by('country_name_ko')
    
    # 문서 슬롯 정보 조회
    from .models import DocumentSlot
    
    existing_slot_types = set(
        DocumentSlot.objects.filter(label=label).values_list('document_type_id', flat=True)
    )

    # 필수 문서 슬롯 자동 생성 (최초 접근 시)
    if is_owner:  # 오너만 슬롯 생성 가능
        
        # 모든 필수 문서 타입에 대해 슬롯 생성
        required_types = DocumentType.objects.filter(is_required=True, is_active=True)
        slots_to_create = []
        
        for doc_type in required_types:
            if doc_type.type_id not in existing_slot_types:
                slots_to_create.append(
                    DocumentSlot(
                        label=label,
                        document_type=doc_type
                        # status는 default 값(EMPTY) 사용
                    )
                )
        
        if slots_to_create:
            DocumentSlot.objects.bulk_create(slots_to_create)
    
    document_slots = DocumentSlot.objects.filter(
        label=label,
        is_hidden=False  # 숨겨지지 않은 슬롯만
    ).select_related('document_type', 'current_document').order_by('document_type__display_order')
    
    available_doc_types = DocumentType.objects.filter(
        is_active=True
    ).exclude(type_id__in=existing_slot_types).order_by('display_order', 'type_name')
    
    # 슬롯 상태 업데이트 (만료일 기준)
    for slot in document_slots:
        slot.update_status()
    
    # 슬롯 통계 계산 (숨겨지지 않은 슬롯만)
    total_slots = document_slots.count()
    filled_slots = document_slots.exclude(status=DocumentSlot.SlotStatus.EMPTY).count()
    compliance_rate = (filled_slots / total_slots * 100) if total_slots > 0 else 0
    empty_count = document_slots.filter(status=DocumentSlot.SlotStatus.EMPTY).count()
    expiring_count = document_slots.filter(status=DocumentSlot.SlotStatus.EXPIRING).count()
    expired_count = document_slots.filter(status=DocumentSlot.SlotStatus.EXPIRED).count()
    
    context = {
        'product': label,  # 템플릿에서 product로 참조
        'label': label,
        'latest_version': label,  # V1/V2 호환성을 위해 추가
        'metadata': metadata,
        'bom_items': bom_items,
        'documents': documents,
        'food_types': food_types,
        'food_groups': food_groups,
        'countries': countries,
        'documents_by_type': documents_by_type,
        'document_types': document_types,
        'shares': shares,
        'all_shared_users': all_shared_users,  # 모든 공유자 목록
        'product_status': status,
        'status_choices': ProductMetadata.Status.choices,
        'can_edit': can_edit,
        'can_upload_documents': can_upload_documents,
        'can_comment': can_comment,
        'can_delete_product': can_delete_product,
        'available_actions': available_actions,
        'user_role': user_role,
        'user_role_label': role_labels.get(user_role, '뷰어'),
        'label_owner': label.user_id,  # 실제 라벨 소유자 (EDITOR 팔레트용)
        'comments': comments,
        'comment_fields': comment_fields,
        'author_roles': author_roles,
        'activity_logs': activity_logs,  # 활동 로그 추가
        'activity_author_roles': activity_author_roles,  # 활동 로그 작성자 권한
        'today': timezone.now().date(),
        'warning_date': timezone.now().date() + timedelta(days=30),  # 30일 이내 만료 경고
        # 문서 슬롯 정보
        'document_slots': document_slots,
        'total_slots': total_slots,
        'filled_slots': filled_slots,
        'compliance_rate': compliance_rate,
        'empty_count': empty_count,
        'expiring_count': expiring_count,
        'expired_count': expired_count,
        'available_doc_types': available_doc_types,
        'from_source': request.GET.get('from', ''),
    }
    
    return render(request, 'products/product_detail.html', context)


# ==================== 최근 항목 / 즐겨찾기 ====================

@login_required
def product_recent(request):
    """최근 열어본 항목"""
    recent_logs = ProductAccessLog.objects.filter(
        user=request.user,
        product__delete_YN='N'
    ).select_related('product')[:50]
    
    context = {
        'recent_logs': recent_logs,
        'title': '최근 항목'
    }
    return render(request, 'products/product_recent.html', context)


@login_required
@login_required
def product_favorite(request):
    """즐겨찾기 항목"""
    # ProductMetadata에서 즐겨찾기된 제품 가져오기
    starred_metadata = ProductMetadata.objects.filter(
        label__user_id=request.user,
        label__delete_YN='N',
        is_starred=True
    ).select_related('label').order_by('-starred_datetime')

    products = []
    for meta in starred_metadata:
        label = meta.label
        products.append({
            'product_id': label.my_label_id,
            'product_name': label.my_label_name or label.prdlst_nm,
            'product_code': meta.product_code,
            'description': label.prdlst_dcnm,
            'starred_datetime': meta.starred_datetime,
        })

    context = {
        'products': products,
        'title': '즐겨찾기',
        'is_favorite_view': True,
    }
    return render(request, 'products/product_starred.html', context)


# ==================== 제품 생성/수정/삭제 ====================

@login_required
def product_create(request):
    """제품 생성 (MyLabel 기반)"""
    if request.method == 'POST':
        # MyLabel 직접 생성
        label = MyLabel()
        label.user_id = request.user
        label.my_label_name = request.POST.get('my_label_name', '새 제품')
        label.prdlst_nm = request.POST.get('prdlst_nm', '')
        label.ingredient_info = request.POST.get('ingredient_info', '')
        label.prdlst_dcnm = request.POST.get('prdlst_dcnm', '')
        label.prdlst_report_no = request.POST.get('prdlst_report_no', '')
        label.content_weight = request.POST.get('content_weight', '')
        label.country_of_origin = request.POST.get('country_of_origin', '')
        label.storage_method = request.POST.get('storage_method', '')
        label.frmlc_mtrqlt = request.POST.get('frmlc_mtrqlt', '')
        label.bssh_nm = request.POST.get('bssh_nm', '')
        label.pog_daycnt = request.POST.get('pog_daycnt', '')
        label.rawmtrl_nm = request.POST.get('rawmtrl_nm', '')
        label.cautions = request.POST.get('cautions', '')
        label.additional_info = request.POST.get('additional_info', '')
        label.food_group = request.POST.get('food_group', '')
        label.food_type = request.POST.get('food_type', '')
        label.processing_method = request.POST.get('processing_method', '')
        label.processing_condition = request.POST.get('processing_condition', '')
        label.preservation_type = request.POST.get('preservation_type', '')
        label.distributor_address = request.POST.get('distributor_address', '')
        label.repacker_address = request.POST.get('repacker_address', '')
        label.importer_address = request.POST.get('importer_address', '')
        import json as _json
        raw_cf = request.POST.get('custom_fields_json', '[]')
        try:
            label.custom_fields = _json.loads(raw_cf)
        except Exception:
            label.custom_fields = []
        label.delete_YN = 'N'
        label.save()
        
        # 고유한 product_code 생성
        user_product_count = ProductMetadata.objects.filter(
            label__user_id=request.user
        ).count()
        
        # 중복되지 않는 고유 코드 찾기
        product_code = None
        max_attempts = 100
        for i in range(max_attempts):
            candidate_code = f"PRD-{request.user.id}-{user_product_count + i + 1:04d}"
            if not ProductMetadata.objects.filter(product_code=candidate_code).exists():
                product_code = candidate_code
                break
        
        # 고유 코드를 찾지 못한 경우 타임스탬프 추가
        if not product_code:
            import time
            product_code = f"PRD-{request.user.id}-{int(time.time())}"
        
        # ProductMetadata 생성 (중복 방지)
        metadata, created = ProductMetadata.objects.get_or_create(
            label=label,
            defaults={
                'product_code': product_code,
                'is_starred': False,
            }
        )
        
        # 활동 로그 기록
        if created:
            from .models import ProductActivityLog
            ProductActivityLog.objects.create(
                label=label,
                user=request.user,
                action='CREATED',
                details={
                    'product_code': product_code,
                    'product_name': label.my_label_name,
                }
            )
        
        messages.success(request, '새로운 제품이 생성되었습니다.')
        # 생성 후 워크스페이스의 기본정보 탭으로 바로 이동
        return redirect('products:product_detail_new', product_id=label.my_label_id)
    
    # GET: 폼 렌더링
    food_types = FoodType.objects.all().order_by('food_group', 'food_type')
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    countries = CountryList.objects.all().order_by('country_name_ko')
    
    context = {
        'product': None,  # 새 제품 생성이므로 None
        'title': '새 제품 만들기',
        'food_types': food_types,
        'food_groups': food_groups,
        'countries': countries,
    }
    return render(request, 'products/product_form.html', context)


@login_required
def product_update(request, product_id):
    """제품 수정"""
    # V2에서는 label_id를 product_id로 받음
    # 먼저 직접 MyLabel 조회 시도
    try:
        label = MyLabel.objects.get(my_label_id=product_id, user_id=request.user)
    except MyLabel.DoesNotExist:
        # MyLabel이 없으면 ProductMetadata를 통해 조회 시도
        try:
            metadata = ProductMetadata.objects.select_related('label').get(
                metadata_id=product_id,
                label__user_id=request.user
            )
            label = metadata.label
        except ProductMetadata.DoesNotExist:
            # 둘 다 없으면 404
            messages.error(request, '제품을 찾을 수 없습니다.')
            return redirect('products:product_explorer')
    
    if request.method == 'POST':
        # MyLabel 필드 업데이트
        label.my_label_name = request.POST.get('my_label_name', label.my_label_name)
        label.prdlst_nm = request.POST.get('prdlst_nm', label.prdlst_nm)
        label.ingredient_info = request.POST.get('ingredient_info', label.ingredient_info)
        label.prdlst_dcnm = request.POST.get('prdlst_dcnm', label.prdlst_dcnm)
        label.prdlst_report_no = request.POST.get('prdlst_report_no', label.prdlst_report_no)
        label.content_weight = request.POST.get('content_weight', label.content_weight)
        label.country_of_origin = request.POST.get('country_of_origin', label.country_of_origin)
        label.storage_method = request.POST.get('storage_method', label.storage_method)
        label.frmlc_mtrqlt = request.POST.get('frmlc_mtrqlt', label.frmlc_mtrqlt)
        label.bssh_nm = request.POST.get('bssh_nm', label.bssh_nm)
        label.pog_daycnt = request.POST.get('pog_daycnt', label.pog_daycnt)
        label.rawmtrl_nm = request.POST.get('rawmtrl_nm', label.rawmtrl_nm)
        label.cautions = request.POST.get('cautions', label.cautions)
        label.additional_info = request.POST.get('additional_info', label.additional_info)
        label.food_group = request.POST.get('food_group', label.food_group)
        label.food_type = request.POST.get('food_type', label.food_type)
        label.processing_method = request.POST.get('processing_method', label.processing_method)
        label.processing_condition = request.POST.get('processing_condition', label.processing_condition)
        label.preservation_type = request.POST.get('preservation_type', label.preservation_type)
        label.distributor_address = request.POST.get('distributor_address', label.distributor_address)
        label.repacker_address = request.POST.get('repacker_address', label.repacker_address)
        label.importer_address = request.POST.get('importer_address', label.importer_address)
        import json as _json
        raw_cf = request.POST.get('custom_fields_json', None)
        if raw_cf is not None:
            try:
                label.custom_fields = _json.loads(raw_cf)
            except Exception:
                label.custom_fields = []
        label.save()
        
        messages.success(request, '제품이 수정되었습니다.')
        return redirect('products:product_detail_new', product_id=label.my_label_id)
    
    # 식품유형과 원산지 목록 추가
    food_types = FoodType.objects.all().order_by('food_group', 'food_type')
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    countries = CountryList.objects.all().order_by('country_name_ko')
    
    context = {
        'product': label,
        'label': label,
        'title': '제품 수정',
        'food_types': food_types,
        'food_groups': food_groups,
        'countries': countries,
    }
    return render(request, 'products/product_form.html', context)


@login_required
@require_POST
def product_update_fields(request, product_id):
    """제품 정보 필드 업데이트 (AJAX)"""
    label = MyLabel.objects.filter(my_label_id=product_id, user_id=request.user).first()
    shared_share = None
    is_owner = False
    if label:
        is_owner = True
    else:
        shared_share = ProductShare.objects.filter(
            label__my_label_id=product_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label').first()

        if shared_share:
            label = shared_share.label
        else:
            return JsonResponse({'success': False, 'error': '제품을 찾을 수 없습니다'}, status=404)

    metadata = ProductMetadata.objects.filter(label=label).first()
    user_role = 'OWNER' if is_owner else 'VIEWER'
    if shared_share and not is_owner:
        share_permission = SharePermission.objects.filter(share=shared_share).first()
        if share_permission:
            user_role = share_permission.role_code

    if user_role not in ['OWNER', 'EDITOR']:
        return JsonResponse({'success': False, 'error': '수정 권한이 없습니다.'}, status=403)

    if user_role == 'EDITOR' and metadata and metadata.status not in [
        ProductMetadata.Status.DRAFT,
        ProductMetadata.Status.REQUESTING,
    ]:
        return JsonResponse({'success': False, 'error': '현재 상태에서는 수정할 수 없습니다.'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # 허용된 필드만 업데이트
        allowed_fields = [
            'my_label_name', 'prdlst_dcnm', 'prdlst_nm', 'content_weight',
            'country_of_origin', 'pog_daycnt', 'storage_method', 'bssh_nm',
            'rawmtrl_nm', 'cautions', 'additional_info', 'ingredient_info',
            'prdlst_report_no', 'frmlc_mtrqlt',
            'food_group', 'food_type', 'processing_method', 'processing_condition',
            'preservation_type', 'distributor_address', 'repacker_address', 'importer_address',
            'allergens',
        ]
        
        # 변경된 필드 추적
        changed_fields = []
        field_labels = {
            'my_label_name': '라벨명',
            'prdlst_dcnm': '식품유형',
            'prdlst_nm': '제품명',
            'content_weight': '내용량',
            'country_of_origin': '원산지',
            'pog_daycnt': '소비기한',
            'storage_method': '보관방법',
            'bssh_nm': '제조원',
            'rawmtrl_nm': '원재료명',
            'cautions': '주의사항',
            'additional_info': '기타표시사항',
            'ingredient_info': '특정성분 함량',
            'prdlst_report_no': '품목보고번호',
            'frmlc_mtrqlt': '용기·포장재질',
            'food_group': '식품유형(대분류)',
            'food_type': '식품유형(소분류)',
            'processing_method': '제조방법',
            'processing_condition': '제조방법 상세',
            'preservation_type': '장기보존식품',
            'distributor_address': '유통전문판매원',
            'repacker_address': '소분원',
            'importer_address': '수입원',
            'allergens': '알레르기 성분',
        }
        
        for field_name in allowed_fields:
            if field_name in data:
                old_value = getattr(label, field_name, '')
                new_value = data[field_name]
                if str(old_value) != str(new_value):
                    changed_fields.append(field_labels.get(field_name, field_name))
                setattr(label, field_name, data[field_name])
        
        # 맞춤항목 JSON 처리
        if 'custom_fields_json' in data:
            import json as _json
            raw_cf = data['custom_fields_json']
            try:
                label.custom_fields = _json.loads(raw_cf) if isinstance(raw_cf, str) else raw_cf
            except Exception:
                label.custom_fields = []
            changed_fields.append('맞춤항목')
        
        label.save()
        
        # 변경사항이 있으면 활동 로그 생성
        if changed_fields:
            from .models import ProductActivityLog
            ProductActivityLog.objects.create(
                label=label,
                user=request.user,
                action='INFO_UPDATED',
                details={
                    'changed_fields': changed_fields
                }
            )
        
        return JsonResponse({'success': True, 'message': '저장되었습니다'})
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def product_update_status(request, product_id):
    """제품 상태 업데이트 (워크플로우)"""
    label = MyLabel.objects.filter(my_label_id=product_id, user_id=request.user).first()
    shared_share = None
    is_owner = False
    if label:
        is_owner = True
    else:
        shared_share = ProductShare.objects.filter(
            label__my_label_id=product_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label').first()

        if shared_share:
            label = shared_share.label
        else:
            return JsonResponse({'success': False, 'error': '제품을 찾을 수 없습니다'}, status=404)

    metadata = get_object_or_404(ProductMetadata, label=label)
    user_role = 'OWNER' if is_owner else 'VIEWER'
    if shared_share and not is_owner:
        share_permission = SharePermission.objects.filter(share=shared_share).first()
        if share_permission:
            user_role = share_permission.role_code

    new_status = request.POST.get('status', '').strip()
    valid_statuses = {choice[0] for choice in ProductMetadata.Status.choices}
    if new_status not in valid_statuses:
        return JsonResponse({'success': False, 'error': '잘못된 상태입니다.'}, status=400)

    transitions = {
        ProductMetadata.Status.DRAFT:      {ProductMetadata.Status.REQUESTING},
        ProductMetadata.Status.REQUESTING: {ProductMetadata.Status.SUBMITTED, ProductMetadata.Status.DRAFT},
        ProductMetadata.Status.SUBMITTED:  {ProductMetadata.Status.REVIEW, ProductMetadata.Status.REQUESTING},
        ProductMetadata.Status.REVIEW:     {ProductMetadata.Status.PENDING, ProductMetadata.Status.SUBMITTED},
        ProductMetadata.Status.PENDING:    {ProductMetadata.Status.CONFIRMED, ProductMetadata.Status.REVIEW},
        ProductMetadata.Status.CONFIRMED:  {ProductMetadata.Status.DRAFT},
    }
    allowed_targets = transitions.get(metadata.status, set())
    if new_status not in allowed_targets:
        return JsonResponse({'success': False, 'error': '현재 상태에서 변경할 수 없습니다.'}, status=400)

    # 해당 단계 전이에 필요한 담당자 확인
    # (새 상태에 해당하는 권한자가 없으면 일부 전이 차단)
    status_required_roles = {
        ProductMetadata.Status.REQUESTING: ['UPLOADER'],
        ProductMetadata.Status.SUBMITTED:  [],  # 누구나 제출 가능
        ProductMetadata.Status.REVIEW:     ['REVIEWER'],
        ProductMetadata.Status.PENDING:    ['APPROVER'],
        ProductMetadata.Status.CONFIRMED:  [],
    }
    required_roles = status_required_roles.get(new_status, [])
    if required_roles:
        has_required = SharePermission.objects.filter(
            share__label=label,
            share__is_active=True,
            role_code__in=required_roles
        ).filter(
            Q(share__share_end_date__isnull=True) | Q(share__share_end_date__gt=timezone.now())
        ).exists()
        if not has_required:
            role_names = {'UPLOADER': '자료 제출', 'REVIEWER': '검토자', 'APPROVER': '승인자'}
            required_label = ', '.join(role_names.get(r, r) for r in required_roles)
            status_label_map = {
                ProductMetadata.Status.REQUESTING: '자료 요청',
                ProductMetadata.Status.REVIEW:     '검토 중',
                ProductMetadata.Status.PENDING:    '승인 대기',
            }
            return JsonResponse({
                'success': False,
                'error': f'"{status_label_map.get(new_status, new_status)}" 단계로 이동하려면 "{required_label}" 권한을 가진 담당자가 필요합니다.',
            }, status=400)

    action_to_status = {
        'requesting': ProductMetadata.Status.REQUESTING,
        'submitted':  ProductMetadata.Status.SUBMITTED,
        'review':     ProductMetadata.Status.REVIEW,
        'pending':    ProductMetadata.Status.PENDING,
        'confirmed':  ProductMetadata.Status.CONFIRMED,
        'draft':      ProductMetadata.Status.DRAFT,
    }

    # 역할별 허용 행동
    status_actions_map_view = {
        ProductMetadata.Status.DRAFT:      ['requesting'],
        ProductMetadata.Status.REQUESTING: ['submitted', 'draft'],
        ProductMetadata.Status.SUBMITTED:  ['review', 'requesting'],
        ProductMetadata.Status.REVIEW:     ['pending', 'submitted'],
        ProductMetadata.Status.PENDING:    ['confirmed', 'review'],
        ProductMetadata.Status.CONFIRMED:  ['draft'],
    }
    if user_role == 'OWNER':
        available_actions = status_actions_map_view.get(metadata.status, [])
    elif user_role == 'EDITOR':
        available_actions = status_actions_map_view.get(metadata.status, [])
    elif user_role == 'UPLOADER':
        available_actions = ['submitted'] if metadata.status == ProductMetadata.Status.REQUESTING else []
    elif user_role == 'REVIEWER':
        available_actions = ['pending'] if metadata.status in [
            ProductMetadata.Status.SUBMITTED, ProductMetadata.Status.REVIEW] else []
    elif user_role == 'APPROVER':
        available_actions = ['confirmed'] if metadata.status == ProductMetadata.Status.PENDING else []
    else:
        available_actions = []

    if new_status not in {action_to_status.get(a) for a in available_actions}:
        return JsonResponse({'success': False, 'error': '상태 변경 권한이 없습니다.'}, status=403)

    # ── CONFIRMED → DRAFT: 새 버전 번호 증가 ──
    old_status = metadata.status
    old_status_label = metadata.get_status_display()

    if old_status == ProductMetadata.Status.CONFIRMED and new_status == ProductMetadata.Status.DRAFT:
        metadata.status = new_status
        if hasattr(metadata, 'version'):
            metadata.version = (metadata.version or 1) + 1
            metadata.save(update_fields=['status', 'version', 'updated_datetime'])
        else:
            metadata.save(update_fields=['status', 'updated_datetime'])
    else:
        metadata.status = new_status
        metadata.save(update_fields=['status', 'updated_datetime'])

    # ── 활동 로그 기록 ──
    from .models import ProductActivityLog
    ProductActivityLog.objects.create(
        label=label,
        user=request.user,
        action='STATUS_CHANGED',
        details={
            'old_status': old_status,
            'old_status_label': old_status_label,
            'new_status': new_status,
            'new_status_label': metadata.get_status_display(),
        }
    )

    # ── 새 상태에서 담당 역할을 가진 공유자에게 인앱 알림 발송 ──
    notify_roles = {
        ProductMetadata.Status.REQUESTING: ['UPLOADER'],
        ProductMetadata.Status.SUBMITTED:  ['REVIEWER', 'EDITOR', 'OWNER'],
        ProductMetadata.Status.REVIEW:     ['REVIEWER'],
        ProductMetadata.Status.PENDING:    ['APPROVER'],
        ProductMetadata.Status.CONFIRMED:  ['OWNER', 'EDITOR'],
        ProductMetadata.Status.DRAFT:      ['OWNER', 'EDITOR'],
    }
    new_status_label = metadata.get_status_display()
    product_name = label.my_label_name or label.prdlst_nm or '제품'
    for nrole in notify_roles.get(new_status, []):
        if nrole in ('OWNER',):
            # 소유자 직접 알림
            if label.user_id and label.user_id != request.user:
                ProductNotification.objects.create(
                    label=label,
                    recipient=label.user_id,
                    message=f'[{product_name}] 상태가 "{new_status_label}"으(로) 변경되었습니다.',
                    status_code=new_status,
                )
        else:
            perm_qs = SharePermission.objects.filter(
                share__label=label,
                share__is_active=True,
                role_code=nrole,
            ).filter(
                Q(share__share_end_date__isnull=True) | Q(share__share_end_date__gt=timezone.now())
            ).select_related('share__recipient_user')
            for perm in perm_qs:
                recipient = perm.share.recipient_user
                if recipient and recipient != request.user:
                    ProductNotification.objects.create(
                        label=label,
                        recipient=recipient,
                        message=f'[{product_name}] 상태가 "{new_status_label}"으(로) 변경되었습니다. 귀하의 작업이 필요합니다.',
                        status_code=new_status,
                    )

    return JsonResponse({
        'success': True,
        'status': metadata.status,
        'status_label': metadata.get_status_display()
    })


@login_required
def product_delete(request, product_id):
    """제품 삭제 (휴지통으로 이동)"""
    # V2에서는 label_id를 product_id로 받음
    try:
        label = MyLabel.objects.get(my_label_id=product_id, user_id=request.user)
    except MyLabel.DoesNotExist:
        try:
            metadata = ProductMetadata.objects.select_related('label').get(
                metadata_id=product_id,
                label__user_id=request.user
            )
            label = metadata.label
        except ProductMetadata.DoesNotExist:
            messages.error(request, '제품을 찾을 수 없습니다.')
            return redirect('products:product_explorer')
    
    if request.method == 'POST':
        # 소프트 삭제
        label.delete_YN = 'Y'
        from datetime import datetime
        label.delete_datetime = datetime.now().strftime('%Y%m%d')
        label.save()
        
        messages.success(request, '제품이 삭제되었습니다.')
        return redirect('products:product_explorer')
    
    messages.info(request, '삭제는 확인 화면 없이 바로 처리됩니다.')
    return redirect('products:product_detail_new', product_id=label.my_label_id)


@login_required
@require_POST
def bulk_delete_products(request):
    """제품 일괄 삭제 (AJAX)"""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return JsonResponse({'success': False, 'message': '삭제할 제품이 선택되지 않았습니다.'})
        
        # 사용자 소유의 제품만 삭제
        labels = MyLabel.objects.filter(
            my_label_id__in=product_ids,
            user_id=request.user,
            delete_YN='N'
        )
        
        deleted_count = 0
        for label in labels:
            label.delete_YN = 'Y'
            from datetime import datetime
            label.delete_datetime = datetime.now().strftime('%Y%m%d')
            label.save()
            deleted_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}개 제품이 삭제되었습니다.',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_POST
def bulk_copy_products(request):
    """제품 일괄 복사 (AJAX)"""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return JsonResponse({'success': False, 'message': '복사할 제품이 선택되지 않았습니다.'})
        
        # 사용자 소유의 제품만 복사
        labels = MyLabel.objects.filter(
            my_label_id__in=product_ids,
            user_id=request.user,
            delete_YN='N'
        )
        
        copied_count = 0
        for original_label in labels:
            # 새 라벨 생성
            new_label = MyLabel.objects.create(
                user_id=request.user,
                my_label_name=f"{original_label.my_label_name} (복사본)",
                prdlst_nm=original_label.prdlst_nm,
                prdlst_dcnm=original_label.prdlst_dcnm,
                food_type=original_label.food_type,
                calories=original_label.calories,
                carbohydrates=original_label.carbohydrates,
                proteins=original_label.proteins,
                fats=original_label.fats,
                natriums=original_label.natriums,
                sugars=original_label.sugars,
                saturated_fats=original_label.saturated_fats,
                trans_fats=original_label.trans_fats,
                cholesterols=original_label.cholesterols,
                allergens=original_label.allergens,
                delete_YN='N'
            )
            
            # ProductMetadata 복사
            try:
                original_meta = ProductMetadata.objects.get(label=original_label)
                
                # 고유한 product_code 생성
                user_product_count = ProductMetadata.objects.filter(
                    label__user_id=request.user
                ).count()
                
                product_code = None
                for i in range(100):
                    candidate_code = f"PRD-{request.user.id}-{user_product_count + i + 1:04d}"
                    if not ProductMetadata.objects.filter(product_code=candidate_code).exists():
                        product_code = candidate_code
                        break
                
                if not product_code:
                    import time
                    product_code = f"PRD-{request.user.id}-{int(time.time())}"
                
                ProductMetadata.objects.create(
                    label=new_label,
                    product_code=product_code,
                    is_starred=False
                )
            except ProductMetadata.DoesNotExist:
                pass
            
            # BOM 데이터 복사
            original_bom = ProductBOM.objects.filter(parent_label=original_label)
            for bom_item in original_bom:
                ProductBOM.objects.create(
                    parent_label=new_label,
                    child_label=bom_item.child_label,
                    shared_receipt=bom_item.shared_receipt,
                    ingredient_name=bom_item.ingredient_name,
                    raw_material_name=bom_item.raw_material_name,
                    sub_ingredients=bom_item.sub_ingredients,
                    food_type=bom_item.food_type,
                    usage_ratio=bom_item.usage_ratio,
                    manufacturer=bom_item.manufacturer,
                    allergens=bom_item.allergens,
                    gmo=bom_item.gmo,
                    report_no=bom_item.report_no,
                    origin=bom_item.origin,
                    origin_detail=bom_item.origin_detail,
                    is_additive=bom_item.is_additive,
                    additive_role=bom_item.additive_role,
                    is_gmo=bom_item.is_gmo,
                    notes=bom_item.notes
                )
            
            copied_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{copied_count}개 제품이 복사되었습니다.',
            'copied_count': copied_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# ==================== 폴더 관리 ====================

@login_required
@require_POST
def folder_create(request):
    """폴더 생성 (AJAX)"""
    folder_name = request.POST.get('folder_name', '').strip()
    parent_id = request.POST.get('parent_id')
    
    if not folder_name:
        return JsonResponse({'success': False, 'error': '폴더명을 입력하세요.'})
    
    parent_folder = None
    if parent_id:
        parent_folder = get_object_or_404(ProductFolder, folder_id=parent_id, owner=request.user)
    
    folder = ProductFolder.objects.create(
        owner=request.user,
        name=folder_name,
        parent=parent_folder
    )
    
    return JsonResponse({
        'success': True,
        'folder_id': folder.folder_id,
        'name': folder.name
    })


@login_required
@require_POST
def folder_rename(request, folder_id):
    """폴더 이름 변경 (AJAX)"""
    folder = get_object_or_404(ProductFolder, folder_id=folder_id, owner=request.user)
    new_name = request.POST.get('new_name', '').strip()
    
    if not new_name:
        return JsonResponse({'success': False, 'error': '폴더명을 입력하세요.'})
    
    folder.name = new_name
    folder.save()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def folder_delete(request, folder_id):
    """폴더 삭제 (AJAX)"""
    folder = get_object_or_404(ProductFolder, folder_id=folder_id, owner=request.user)
    
    # 하위 항목이 있는지 확인
    if folder.children.exists() or folder.products.exists():
        return JsonResponse({'success': False, 'error': '폴더에 항목이 있어 삭제할 수 없습니다.'})
    
    folder.delete()
    return JsonResponse({'success': True})


# ==================== 제품 이동 ====================

@login_required
@require_POST
def product_move(request, product_id):
    """제품을 다른 폴더로 이동 (AJAX)"""
    product = get_object_or_404(Product, product_id=product_id, owner=request.user)
    folder_id = request.POST.get('folder_id')
    
    if folder_id:
        folder = get_object_or_404(ProductFolder, folder_id=folder_id, owner=request.user)
        product.folder = folder
    else:
        product.folder = None
    
    product.save()
    return JsonResponse({'success': True})


# ==================== 즐겨찾기 토글 ====================

@login_required
@require_POST
def product_favorite_toggle(request, product_id):
    """즐겨찾기 토글 (AJAX) - ProductMetadata 기반"""
    try:
        label = MyLabel.objects.get(my_label_id=product_id, user_id=request.user)
    except MyLabel.DoesNotExist:
        return JsonResponse({'success': False, 'error': '제품을 찾을 수 없습니다'}, status=404)
    
    # ProductMetadata 가져오기 또는 생성
    try:
        metadata = ProductMetadata.objects.get(label=label)
    except ProductMetadata.DoesNotExist:
        # 메타데이터가 없으면 생성
        user_product_count = ProductMetadata.objects.filter(
            label__user_id=request.user
        ).count()
        
        product_code = None
        for i in range(100):
            candidate_code = f"PRD-{request.user.id}-{user_product_count + i + 1:04d}"
            if not ProductMetadata.objects.filter(product_code=candidate_code).exists():
                product_code = candidate_code
                break
        
        if not product_code:
            import time
            product_code = f"PRD-{request.user.id}-{int(time.time())}"
        
        metadata = ProductMetadata.objects.create(
            label=label,
            product_code=product_code,
            is_starred=False
        )
    
    # 즐겨찾기 토글
    metadata.is_starred = not metadata.is_starred
    if metadata.is_starred:
        metadata.starred_datetime = timezone.now()
    else:
        metadata.starred_datetime = None
    metadata.save()
    
    return JsonResponse({
        'success': True,
        'is_starred': metadata.is_starred
    })


# ==================== 휴지통 ====================

@login_required
def product_trash(request):
    """휴지통 목록"""
    messages.info(request, '휴지통 화면은 준비 중입니다.')
    return redirect('products:product_explorer')


@login_required
@require_POST
def product_restore(request, product_id):
    """제품 복원"""
    product = get_object_or_404(Product, product_id=product_id, owner=request.user, is_deleted=True)
    
    product.is_deleted = False
    product.deleted_datetime = None
    product.save()
    
    messages.success(request, '제품이 복원되었습니다.')
    return redirect('products:product_trash')


@login_required
@require_POST
def product_permanent_delete(request, product_id):
    """제품 영구 삭제"""
    product = get_object_or_404(Product, product_id=product_id, owner=request.user, is_deleted=True)
    
    product.delete()
    
    messages.success(request, '제품이 영구 삭제되었습니다.')
    return redirect('products:product_trash')


# ==================== 검색 ====================

@login_required
def product_search(request):
    """전체 제품 검색"""
    query = request.GET.get('q', '').strip()
    if query:
        return redirect(f"{reverse('products:product_explorer')}?q={quote(query)}")
    return redirect('products:product_explorer')


# ==================== 공유/협업 ====================

@login_required
def sharing_inbox(request):
    """공동작업 - 나에게 권한이 부여된 제품 목록"""
    status_filter = request.GET.get('status', '')
    role_filter   = request.GET.get('role', '')

    # ProductShare 기반으로 직접 조회 (recipient_user 또는 이메일 매칭 모두 포함)
    my_shares = ProductShare.objects.filter(
        Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email),
        is_active=True,
    ).filter(
        Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
    ).select_related(
        'label', 'created_by', 'permission',
    ).order_by('-share_start_date')

    # label_id → ProductMetadata 매핑 (status 조회용)
    label_ids = list({s.label_id for s in my_shares})
    metadata_map = {
        m.label_id: m
        for m in ProductMetadata.objects.filter(label_id__in=label_ids)
    }

    # 역할별 할 일 매핑
    def _action_needed(role_code, status):
        mapping = {
            ('UPLOADER',  'REQUESTING'): ('업로드', 'bi bi-upload',        'text-primary'),
            ('REVIEWER',  'SUBMITTED'):  ('검토 필요', 'bi bi-eye',         'text-warning'),
            ('REVIEWER',  'REVIEW'):     ('검토 중',   'bi bi-eye-fill',    'text-warning'),
            ('APPROVER',  'PENDING'):    ('승인 대기', 'bi bi-check-circle', 'text-danger'),
            ('EDITOR',    'DRAFT'):      ('편집 가능', 'bi bi-pencil',       'text-success'),
            ('EDITOR',    'REQUESTING'): ('편집 가능', 'bi bi-pencil',       'text-success'),
        }
        hit = mapping.get((role_code, status))
        return hit if hit else (None, None, None)

    # 각 share에 metadata + action 속성 추가
    result_shares = []
    for share in my_shares:
        share.metadata = metadata_map.get(share.label_id)
        perm = getattr(share, 'permission', None)
        role_code = perm.role_code if perm else 'VIEWER'
        status = share.metadata.status if share.metadata else 'DRAFT'
        share.role_code = role_code
        share.action_label, share.action_icon, share.action_style = _action_needed(role_code, status)
        result_shares.append(share)

    # 전체 상태별 카운트 (필터 적용 전 — 역할 필터 먼저 적용 후 집계)
    # 역할 필터 먼저 적용
    if role_filter:
        role_filtered = [s for s in result_shares if s.role_code == role_filter]
    else:
        role_filtered = result_shares

    # 상태별 카운트: 역할 필터 이후 기준으로 집계해야 카드 수치와 리스트가 일치
    status_counts = {}
    for share in role_filtered:
        s = share.metadata.status if share.metadata else 'DRAFT'
        status_counts[s] = status_counts.get(s, 0) + 1

    total_count = len(role_filtered)

    # 상태 필터 적용
    filtered = role_filtered
    if status_filter:
        filtered = [
            s for s in filtered
            if (s.metadata and s.metadata.status == status_filter)
            or (not s.metadata and status_filter == 'DRAFT')
        ]

    context = {
        'received_shares': filtered,
        'title': '공동작업',
        'status_filter': status_filter,
        'role_filter': role_filter,
        'status_counts': status_counts,
        'total_count': total_count,
        'filtered_count': len(filtered),
        'Status': ProductMetadata.Status,
        'role_choices': SharePermission.ROLE_CHOICES,
    }
    return render(request, 'products/sharing/inbox.html', context)


@login_required
def product_detail_new(request, product_id):
    """제품 상세 (새 스타일)"""
    # product_detail과 동일하게 처리
    return product_detail(request, product_id)


@login_required
@xframe_options_sameorigin
def nutrition_workspace(request, label_id):
    """영양성분 입력 워크스페이스 (오너 + 공유 사용자 접근 가능)"""
    from v1.label.models import MyLabel
    from datetime import datetime

    # 오너 우선 조회
    is_owner = False
    can_edit = False
    try:
        label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user, delete_YN='N')
        is_owner = True
        can_edit = True
    except MyLabel.DoesNotExist:
        # 공유 사용자 접근 허용
        shared_share = ProductShare.objects.filter(
            label__my_label_id=label_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label', 'permission').first()

        if not shared_share:
            from django.http import Http404
            raise Http404('접근 권한이 없습니다.')
        label = shared_share.label
        perm = getattr(shared_share, 'permission', None)
        can_edit = bool(perm and perm.can_edit_label)

    context = {
        'label': label,
        'LABEL_ID': label.my_label_id,
        'STATIC_BUILD_DATE': datetime.now().strftime('%Y%m%d%H%M%S'),
        'can_edit': can_edit,
    }
    return render(request, 'products/nutrition_editor.html', context)


@login_required
def nutrition_data_api(request, label_id):
    """영양성분 데이터 조회 API (오너 + 공유 사용자)"""
    from v1.label.models import MyLabel

    try:
        label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user, delete_YN='N')
    except MyLabel.DoesNotExist:
        shared_share = ProductShare.objects.filter(
            label__my_label_id=label_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label').first()
        if not shared_share:
            from django.http import Http404
            raise Http404('접근 권한이 없습니다.')
        label = shared_share.label
    
    data = {
        # 기본 설정
        'serving_size': label.serving_size or '',
        'serving_size_unit': label.serving_size_unit or 'g',
        'units_per_package': label.units_per_package or '',
        'nutrition_display_unit': label.nutrition_display_unit or 'basic',
        'basic_display_type': label.basic_display_type or '',
        'parallel_display_type': label.parallel_display_type or '',
        
        # 필수 영양성분 9가지
        'calories': label.calories or '',
        'natriums': label.natriums or '',
        'carbohydrates': label.carbohydrates or '',
        'sugars': label.sugars or '',
        'fats': label.fats or '',
        'trans_fats': label.trans_fats or '',
        'saturated_fats': label.saturated_fats or '',
        'cholesterols': label.cholesterols or '',
        'proteins': label.proteins or '',
        
        # 추가 영양성분
        'dietary_fiber': label.dietary_fiber or '',
        'calcium': label.calcium or '',
        'iron': label.iron or '',
        'magnesium': label.magnesium or '',
        'phosphorus': label.phosphorus or '',
        'potassium': label.potassium or '',
        'zinc': label.zinc or '',
        'vitamin_a': label.vitamin_a or '',
        'vitamin_d': label.vitamin_d or '',
        'vitamin_c': label.vitamin_c or '',
        'thiamine': label.thiamine or '',
        'riboflavin': label.riboflavin or '',
        'niacin': label.niacin or '',
        'vitamin_b6': label.vitamin_b6 or '',
        'folic_acid': label.folic_acid or '',
        'vitamin_b12': label.vitamin_b12 or '',
    }
    
    return JsonResponse(data)


@login_required
@require_POST
def nutrition_save_api(request, label_id):
    """영양성분 데이터 저장 API (오너 + 쓰기 권한 공유 사용자)"""
    from v1.label.models import MyLabel
    import json

    try:
        label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user, delete_YN='N')
    except MyLabel.DoesNotExist:
        shared_share = ProductShare.objects.filter(
            label__my_label_id=label_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label', 'permission').first()
        if not shared_share:
            return JsonResponse({'status': 'error', 'message': '접근 권한이 없습니다.'}, status=403)
        # can_edit_label 권한 확인 (오타 수정: can_edit → can_edit_label)
        perm = getattr(shared_share, 'permission', None)
        if not perm or not perm.can_edit_label:
            return JsonResponse({'status': 'error', 'message': '영양성분 편집 권한이 없습니다.'}, status=403)
        label = shared_share.label
    
    try:
        data = json.loads(request.body)
        
        # 기본 설정
        label.serving_size = data.get('serving_size', '') or '100'
        label.serving_size_unit = data.get('serving_size_unit', 'g') or 'g'
        label.units_per_package = data.get('units_per_package', '') or '1'
        label.nutrition_display_unit = data.get('nutrition_display_unit', 'basic') or 'basic'
        label.basic_display_type = data.get('basic_display_type', 'total') or 'total'
        label.parallel_display_type = data.get('parallel_display_type', 'unit_total') or 'unit_total'
        
        # 필수 영양성분 9가지
        label.calories = data.get('calories', '')
        label.natriums = data.get('natriums', '')
        label.carbohydrates = data.get('carbohydrates', '')
        label.sugars = data.get('sugars', '')
        label.fats = data.get('fats', '')
        label.trans_fats = data.get('trans_fats', '')
        label.saturated_fats = data.get('saturated_fats', '')
        label.cholesterols = data.get('cholesterols', '')
        label.proteins = data.get('proteins', '')
        
        # 추가 영양성분
        label.dietary_fiber = data.get('dietary_fiber', '')
        label.calcium = data.get('calcium', '')
        label.iron = data.get('iron', '')
        label.magnesium = data.get('magnesium', '')
        label.phosphorus = data.get('phosphorus', '')
        label.potassium = data.get('potassium', '')
        label.zinc = data.get('zinc', '')
        label.vitamin_a = data.get('vitamin_a', '')
        label.vitamin_d = data.get('vitamin_d', '')
        label.vitamin_c = data.get('vitamin_c', '')
        label.thiamine = data.get('thiamine', '')
        label.riboflavin = data.get('riboflavin', '')
        label.niacin = data.get('niacin', '')
        label.vitamin_b6 = data.get('vitamin_b6', '')
        label.folic_acid = data.get('folic_acid', '')
        label.vitamin_b12 = data.get('vitamin_b12', '')
        
        label.save(update_fields=[
            'serving_size', 'serving_size_unit', 'units_per_package',
            'nutrition_display_unit', 'basic_display_type', 'parallel_display_type',
            'calories', 'natriums', 'carbohydrates', 'sugars', 'fats',
            'trans_fats', 'saturated_fats', 'cholesterols', 'proteins',
            'dietary_fiber', 'calcium', 'iron', 'magnesium', 'phosphorus',
            'potassium', 'zinc', 'vitamin_a', 'vitamin_d', 'vitamin_c',
            'thiamine', 'riboflavin', 'niacin', 'vitamin_b6', 'folic_acid', 'vitamin_b12',
        ])
        
        return JsonResponse({'status': 'success', 'message': '저장되었습니다.'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ==================== 공유 상세 기능 (Stub) ====================

@login_required
def received_share_detail(request, receipt_id):
    """받은 공유 상세"""
    get_object_or_404(SharedProductReceipt, receipt_id=receipt_id, receiver=request.user)
    messages.info(request, '공유 상세 화면은 준비 중입니다.')
    return redirect('products:inbox')


@login_required
@require_POST
def received_share_accept(request, receipt_id):
    """공유 수락"""
    receipt = get_object_or_404(SharedProductReceipt, receipt_id=receipt_id, receiver=request.user)
    receipt.is_accepted = True
    receipt.accepted_datetime = timezone.now()
    receipt.save()
    messages.success(request, '공유를 수락했습니다.')
    return redirect('products:inbox')


@login_required
@require_POST
def use_as_ingredient(request, receipt_id):
    """원료로 사용"""
    receipt = get_object_or_404(SharedProductReceipt, receipt_id=receipt_id, receiver=request.user)
    receipt.is_used_as_ingredient = True
    receipt.save()
    messages.success(request, '원료로 등록했습니다.')
    return redirect('products:inbox')


def _get_editor_share_for_label(request, label):
    """요청 사용자가 해당 label에 EDITOR 역할로 공유받은 share를 반환. 없으면 None."""
    return ProductShare.objects.filter(
        label=label,
        is_active=True,
        sharepermission__role_code='EDITOR',
    ).filter(
        Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
    ).filter(
        Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
    ).select_related('sharepermission').first()


@login_required
@require_http_methods(["GET", "POST"])
def share_create(request, label_id):
    """공유 생성 – 소유자 또는 EDITOR 역할 공유자가 접근 가능"""
    # 소유자 확인
    label = MyLabel.objects.filter(
        my_label_id=label_id,
        user_id=request.user,
        delete_YN='N'
    ).first()

    if not label:
        # EDITOR 공유 접근 확인
        label = get_object_or_404(MyLabel, my_label_id=label_id, delete_YN='N')
        if not _get_editor_share_for_label(request, label):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

    if request.method == 'GET':
        target_url = f"{reverse('products:product_detail', kwargs={'product_id': label_id})}#tab-share"
        return redirect(target_url)

    email = request.POST.get('email', '').strip()
    role_code = request.POST.get('role', 'VIEWER')
    expiration_date = request.POST.get('expiration_date')
    recipient_name = request.POST.get('name', '').strip()
    recipient_company = request.POST.get('company', '').strip()

    if not email:
        return JsonResponse({'success': False, 'error': '이메일은 필수입니다.'}, status=400)

    if role_code not in dict(SharePermission.ROLE_CHOICES):
        return JsonResponse({'success': False, 'error': '잘못된 역할입니다.'}, status=400)

    share_end_date = None
    if expiration_date:
        try:
            end_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
            share_end_date = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        except ValueError:
            return JsonResponse({'success': False, 'error': '만료일 형식이 올바르지 않습니다.'}, status=400)

    existing_share = ProductShare.objects.filter(
        label=label,
        recipient_email__iexact=email
    ).order_by('-created_datetime').first()

    recipient_user = User.objects.filter(email__iexact=email).first()

    if existing_share and existing_share.is_active:
        return JsonResponse({'success': False, 'error': '이미 공유된 사용자입니다.'}, status=400)

    if existing_share and not existing_share.is_active:
        share = existing_share
        share.is_active = True
        share.recipient_email = email
        share.recipient_user = recipient_user
        share.recipient_name = recipient_name
        share.recipient_company = recipient_company
        share.share_end_date = share_end_date
        share.save()
    else:
        share = ProductShare.objects.create(
            label=label,
            share_mode='PRIVATE',
            recipient_email=email,
            recipient_user=recipient_user,
            recipient_name=recipient_name,
            recipient_company=recipient_company,
            share_end_date=share_end_date,
            created_by=request.user
        )

    permission, _ = SharePermission.objects.get_or_create(share=share)
    permission.apply_role_defaults(role_code=role_code, save=True)

    if recipient_user:
        SharedProductReceipt.objects.get_or_create(share=share, receiver=recipient_user)

    # 활동 로그 생성
    from .models import ProductActivityLog
    ProductActivityLog.objects.create(
        label=label,
        user=request.user,
        action='SHARE_CREATED',
        details={
            'recipient_email': email,
            'recipient_name': recipient_name,
            'role': role_code,
            'role_label': permission.role_label
        }
    )

    return JsonResponse({'success': True, 'message': f'{email}님을 초대했습니다.'})


@login_required
def share_detail(request, share_id):
    """공유 상세"""
    messages.info(request, '공유 상세 기능은 준비 중입니다.')
    return redirect('products:inbox')


@login_required
@require_POST
def share_revoke(request, share_id):
    """공유 취소 – 소유자 또는 EDITOR(본인 제외) 접근 가능"""
    share = ProductShare.objects.filter(share_id=share_id, label__user_id=request.user).first()
    if not share:
        share = get_object_or_404(ProductShare, share_id=share_id)
        editor_share = _get_editor_share_for_label(request, share.label)
        if not editor_share:
            return JsonResponse({'success': False, 'error': '권한이 없습니다.'}, status=403)
        if share.share_id == editor_share.share_id:
            return JsonResponse({'success': False, 'error': '자신의 공유는 취소할 수 없습니다.'}, status=403)
    
    # 활동 로그 생성 (삭제 전에 정보 저장)
    from .models import ProductActivityLog
    ProductActivityLog.objects.create(
        label=share.label,
        user=request.user,
        action='SHARE_DELETED',
        details={
            'recipient_email': share.recipient_email,
            'recipient_name': share.recipient_name
        }
    )
    
    share.is_active = False
    share.save(update_fields=['is_active', 'updated_datetime'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def share_update_permission(request, share_id):
    """공유 권한 수정 – 소유자 또는 EDITOR(본인 제외) 접근 가능"""
    share = ProductShare.objects.filter(share_id=share_id, label__user_id=request.user).first()
    if not share:
        share = get_object_or_404(ProductShare, share_id=share_id)
        editor_share = _get_editor_share_for_label(request, share.label)
        if not editor_share:
            return JsonResponse({'success': False, 'error': '권한이 없습니다.'}, status=403)
        if share.share_id == editor_share.share_id:
            return JsonResponse({'success': False, 'error': '자신의 권한은 변경할 수 없습니다.'}, status=403)
    role_code = request.POST.get('role', '').strip()

    if role_code not in dict(SharePermission.ROLE_CHOICES):
        return JsonResponse({'success': False, 'error': '잘못된 역할입니다.'}, status=400)

    permission, _ = SharePermission.objects.get_or_create(share=share)
    permission.apply_role_defaults(role_code=role_code, save=True)

    # 활동 로그 생성
    from .models import ProductActivityLog
    ProductActivityLog.objects.create(
        label=share.label,
        user=request.user,
        action='SHARE_UPDATED',
        details={
            'recipient_email': share.recipient_email,
            'recipient_name': share.recipient_name,
            'role': role_code,
            'role_label': permission.role_label,
            'change_type': 'permission'
        }
    )

    return JsonResponse({'success': True, 'role_label': permission.role_label})


@login_required
@require_http_methods(["POST"])
def share_update_info(request, share_id):
    """공유 멤버 정보 수정 – 소유자 또는 EDITOR(본인 제외) 접근 가능"""
    share = ProductShare.objects.filter(share_id=share_id, label__user_id=request.user).first()
    if not share:
        share = get_object_or_404(ProductShare, share_id=share_id)
        editor_share = _get_editor_share_for_label(request, share.label)
        if not editor_share:
            return JsonResponse({'success': False, 'error': '권한이 없습니다.'}, status=403)
        if share.share_id == editor_share.share_id:
            return JsonResponse({'success': False, 'error': '자신의 정보는 변경할 수 없습니다.'}, status=403)
    
    name = request.POST.get('name', '').strip()
    company = request.POST.get('company', '').strip()
    role_code = request.POST.get('role', '').strip()
    
    # 이름, 회사 업데이트
    share.recipient_name = name
    share.recipient_company = company
    share.save()
    
    # 역할 업데이트
    if role_code and role_code in dict(SharePermission.ROLE_CHOICES):
        permission, _ = SharePermission.objects.get_or_create(share=share)
        permission.apply_role_defaults(role_code=role_code, save=True)
    
    # 활동 로그 생성
    from .models import ProductActivityLog
    detail_info = {
        'recipient_email': share.recipient_email,
        'name': name,
        'company': company,
        'change_type': 'info'
    }
    if role_code:
        detail_info['role'] = role_code
        detail_info['role_label'] = permission.role_label
    
    ProductActivityLog.objects.create(
        label=share.label,
        user=request.user,
        action='SHARE_UPDATED',
        details=detail_info
    )
    
    return JsonResponse({
        'success': True, 
        'message': '변경사항이 저장되었습니다.',
        'name': share.recipient_name,
        'company': share.recipient_company
    })


def public_share_view(request, share_token):
    """공개 공유 보기"""
    messages.info(request, '공개 공유 기능은 준비 중입니다.')
    return redirect('products:product_list')


# ==================== 문서 관리 ====================

# 문서 타입 자동 감지
def detect_document_type(filename):
    """파일명을 분석하여 적절한 문서 타입을 자동 감지"""
    all_types = DocumentType.objects.filter(is_active=True).exclude(detection_keywords='')
    
    for dtype in all_types:
        if dtype.matches_filename(filename):
            return dtype
    
    # 분류 실패 시 '기타' 타입 반환 (없으면 자동 생성)
    other_type, created = DocumentType.objects.get_or_create(
        type_code='OTHER',
        defaults={
            'type_name': '기타',
            'icon': 'bi-file-earmark',
            'color': '#6c757d',
            'is_required': False,
            'default_validity_days': 365,
            'detection_keywords': '',
            'is_active': True
        }
    )
    return other_type


@login_required
def document_type_list(request):
    """문서 타입 목록 (관리자 전용 - Admin 사용 권장)"""
    if not request.user.is_staff:
        messages.warning(request, '문서 타입은 관리자만 조회할 수 있습니다. Django Admin을 이용해주세요.')
        return redirect('/admin/documents/documenttype/')
    
    types = DocumentType.objects.filter(is_active=True).order_by('display_order', 'type_name')
    
    context = {
        'types': types,
    }
    
    return render(request, 'products/documents/type_list.html', context)


@login_required
def document_type_create(request):
    """문서 타입 생성 (Django Admin 사용 권장)"""
    if not request.user.is_staff:
        messages.error(request, '권한이 없습니다.')
        return redirect('products:document_type_list')
    
    messages.info(request, 'Django Admin에서 문서 타입을 관리해주세요.')
    return redirect('/admin/documents/documenttype/add/')


@login_required
def document_type_update(request, type_id):
    """문서 타입 수정 (Django Admin 사용 권장)"""
    if not request.user.is_staff:
        messages.error(request, '권한이 없습니다.')
        return redirect('products:document_type_list')
    
    messages.info(request, 'Django Admin에서 문서 타입을 수정해주세요.')
    return redirect(f'/admin/documents/documenttype/{type_id}/change/')


@login_required
def document_types_api(request):
    """문서 타입 목록 API (드롭존 생성용)"""
    types = DocumentType.objects.filter(is_active=True).order_by('display_order')
    
    data = [{
        'type_id': t.type_id,
        'type_code': t.type_code,
        'type_name': t.type_name,
        'icon': t.icon,
        'color': t.color,
        'is_required': t.is_required,
        'default_validity_days': t.default_validity_days,
        'detection_keywords': t.detection_keywords,
    } for t in types]
    
    return JsonResponse({'types': data})


@login_required
@require_POST
def document_upload_api(request, label_id):
    """
    스마트 문서 업로드 API
    - document_type_id가 있으면 해당 타입으로 저장
    - slot_id가 있으면 해당 슬롯에 연결
    - 없으면 파일명 분석하여 자동 분류
    - 유효기간 자동 계산
    """
    import traceback
    from django.db.models import Max

    try:
        # 오너 우선 조회, 실패 시 공유 사용자 확인
        try:
            label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user, delete_YN='N')
        except MyLabel.DoesNotExist:
            shared_share = ProductShare.objects.filter(
                label__my_label_id=label_id,
                is_active=True,
            ).filter(
                Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
            ).filter(
                Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
            ).select_related('label', 'permission').first()

            if not shared_share:
                return JsonResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status=403)

            perm = getattr(shared_share, 'permission', None)
            if not perm or not perm.can_upload_documents:
                role_label = perm.role_code if perm else 'VIEWER'
                return JsonResponse({
                    'success': False,
                    'error': f'문서 업로드 권한이 없습니다. (현재 역할: {role_label})\n문서 업로드는 오너, 편집자, 자료 제출자만 가능합니다.'
                }, status=403)

            label = shared_share.label
        
        uploaded_file = request.FILES.get('file')
        document_type_id = request.POST.get('document_type') or request.POST.get('document_type_id')
        slot_id = request.POST.get('slot_id')  # 슬롯 ID 추가
        expiry_date_str = request.POST.get('expiry_date')
        expiry_unlimited = request.POST.get('expiry_unlimited', 'false') == 'true'
        description = request.POST.get('description', '')
        notification_enabled = request.POST.get('notification_enabled', 'false') == 'true'

        expiry_date = None
        if expiry_date_str:
            from datetime import datetime
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': '만료일 형식이 올바르지 않습니다.'
                }, status=400)
        
        # 파일 유효성 검사
        if not uploaded_file:
            return JsonResponse({
                'success': False,
                'error': '파일을 선택해주세요.'
            }, status=400)
        
        # 파일 크기 제한 (50MB)
        if uploaded_file.size > 50 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': '파일 크기는 50MB를 초과할 수 없습니다.'
            }, status=400)
        
        # 슬롯 정보 조회 (있는 경우)
        slot = None
        if slot_id:
            from .models import DocumentSlot
            slot = get_object_or_404(DocumentSlot, slot_id=slot_id, label=label)
            # 슬롯이 있으면 document_type은 슬롯의 타입 사용
            document_type = slot.document_type
        else:
            # 문서 타입 결정 (지정 vs 자동 분류)
            auto_detected = False
            if document_type_id:
                document_type = get_object_or_404(DocumentType, type_id=document_type_id, is_active=True)
            else:
                # 파일명 기반 자동 분류
                document_type = detect_document_type(uploaded_file.name)
                auto_detected = True
                
                if not document_type:
                    return JsonResponse({
                        'success': False,
                        'error': '문서 타입을 자동으로 분류할 수 없습니다. 직접 선택해주세요.'
                    }, status=400)
        
        # 기존 문서가 슬롯에 있는 경우 버전 관리
        parent_document = None
        version_number = 1
        if slot and slot.current_document:
            parent_document = slot.current_document
            # 같은 부모의 최신 버전 번호 찾기
            latest_version = ProductDocument.objects.filter(
                Q(document_id=parent_document.document_id) | Q(parent_document=parent_document)
            ).aggregate(Max('version'))['version__max'] or 1
            version_number = latest_version + 1
        
        # 문서 생성
        metadata = {'expiry_unlimited': True} if expiry_unlimited else {}

        document = ProductDocument.objects.create(
            label=label,
            document_type=document_type,
            slot=slot,  # 슬롯 연결
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            expiry_date=expiry_date if expiry_date else None,
            description=description,
            uploaded_by=request.user,
            parent_document=parent_document,
            version=version_number,
            expiry_notification_enabled=notification_enabled,
            metadata=metadata
        )
        
        # 슬롯 업데이트 (current_document 설정 및 상태 업데이트)
        if slot:
            slot.current_document = document
            slot.save()  # save()에서 update_status() 호출
        
        # 활동 로그 생성
        from .models import ProductActivityLog
        log_details = {
            'file_name': uploaded_file.name,
            'document_type': document_type.type_name,
            'file_size': uploaded_file.size
        }
        if slot:
            log_details['slot_id'] = slot.slot_id
            log_details['action_type'] = 'slot_upload'
        if version_number > 1:
            log_details['version'] = version_number
            log_details['previous_version'] = version_number - 1
        
        ProductActivityLog.objects.create(
            label=label,
            user=request.user,
            action='DOCUMENT_UPLOADED',
            details=log_details
        )
        
        # 응답 메시지 구성
        if slot:
            message = f"'{document_type.type_name}' 슬롯에 문서가 업로드되었습니다."
            if version_number > 1:
                message += f" (버전 {version_number})"
        elif 'auto_detected' in locals() and auto_detected:
            message = f"'{document_type.type_name}'(으)로 자동 분류되었습니다."
        else:
            message = '문서가 업로드되었습니다.'
        
        response_data = {
            'success': True,
            'document_id': document.document_id,
            'filename': document.original_filename,
            'file_size': document.file_size,
            'document_type': document.document_type.type_name,
            'document_type_id': document.document_type.type_id,
            'expiry_date': document.expiry_date.isoformat() if document.expiry_date else None,
            'uploaded_at': document.uploaded_datetime.strftime('%Y-%m-%d %H:%M'),
            'message': message,
            'version': version_number
        }
        
        # 슬롯 정보 추가
        if slot:
            response_data['slot'] = {
                'slot_id': slot.slot_id,
                'status': slot.status,
                'document_type': slot.document_type.type_name
            }
        elif 'auto_detected' in locals():
            response_data['auto_detected'] = auto_detected
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # 상세한 에러 로깅
        error_trace = traceback.format_exc()
        print(f"[Document Upload Error] {error_trace}")
        
        return JsonResponse({
            'success': False,
            'error': f'업로드 중 오류가 발생했습니다: {str(e)}'
        }, status=500)


@login_required
@require_POST
def document_delete_api(request, document_id):
    """문서 삭제 AJAX API - JSON 응답 반환"""
    try:
        document = get_object_or_404(
            ProductDocument,
            document_id=document_id,
            label__user_id=request.user,
            is_active=True
        )
        
        # 삭제 전 정보 저장
        file_name = document.original_filename
        document_type_name = document.document_type.type_name if document.document_type else '미분류'
        label = document.label
        
        # Soft Delete
        document.is_active = False
        document.save()
        
        # 활동 로그 생성
        from .models import ProductActivityLog
        ProductActivityLog.objects.create(
            label=label,
            user=request.user,
            action='DOCUMENT_DELETED',
            details={
                'file_name': file_name,
                'document_type': document_type_name
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': '문서가 삭제되었습니다.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'삭제 중 오류가 발생했습니다: {str(e)}'
        }, status=500)


@login_required
@require_POST
def bulk_download(request):
    """
    선택한 문서들을 ZIP으로 일괄 다운로드
    
    POST 데이터:
    - document_ids: 다운로드할 문서 ID 목록 (comma-separated 또는 JSON 배열)
    - organize_by: 폴더 구성 방식 ('product', 'type', 'flat')
    """
    import json
    
    # 문서 ID 파싱
    document_ids_raw = request.POST.get('document_ids', '')
    organize_by = request.POST.get('organize_by', 'product')
    
    if not document_ids_raw:
        return JsonResponse({
            'success': False,
            'error': '다운로드할 문서를 선택해주세요.'
        }, status=400)
    
    # JSON 배열 또는 콤마 구분 처리
    try:
        if document_ids_raw.startswith('['):
            document_ids = json.loads(document_ids_raw)
        else:
            document_ids = [int(id.strip()) for id in document_ids_raw.split(',') if id.strip()]
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({
            'success': False,
            'error': '잘못된 문서 ID 형식입니다.'
        }, status=400)
    
    if not document_ids:
        return JsonResponse({
            'success': False,
            'error': '다운로드할 문서를 선택해주세요.'
        }, status=400)
    
    # 문서 조회 (사용자 소유 확인)
    documents = ProductDocument.objects.filter(
        document_id__in=document_ids,
        label__user_id=request.user,
        is_active=True
    ).select_related('label', 'document_type')
    
    if not documents.exists():
        return JsonResponse({
            'success': False,
            'error': '다운로드 가능한 문서가 없습니다.'
        }, status=404)
    
    # ZIP 파일 생성
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        used_filenames = {}  # 중복 파일명 처리용
        
        for doc in documents:
            try:
                # 파일 경로 구성
                if organize_by == 'product':
                    product_name = _sanitize_filename(doc.label.my_label_name or doc.label.prdlst_nm or '제품')
                    folder = product_name
                elif organize_by == 'type':
                    type_name = _sanitize_filename(doc.document_type.type_name)
                    folder = type_name
                else:
                    folder = ''
                
                # 파일명 생성 (중복 처리)
                original_name = doc.original_filename
                
                if organize_by == 'type':
                    display_name = f"{_sanitize_filename(doc.label.my_label_name or doc.label.prdlst_nm or '제품')}_{original_name}"
                elif organize_by == 'flat':
                    display_name = f"{_sanitize_filename(doc.label.my_label_name or doc.label.prdlst_nm or '제품')}_{_sanitize_filename(doc.document_type.type_name)}_{original_name}"
                else:
                    display_name = original_name
                
                # 전체 경로
                if folder:
                    arcname = f"{folder}/{display_name}"
                else:
                    arcname = display_name
                
                # 중복 파일명 처리
                if arcname in used_filenames:
                    used_filenames[arcname] += 1
                    base, ext = os.path.splitext(arcname)
                    arcname = f"{base}_{used_filenames[arcname]}{ext}"
                else:
                    used_filenames[arcname] = 0
                
                # 파일 추가
                zip_file.writestr(arcname, doc.file.read())
                
            except Exception as e:
                continue
    
    # ZIP 응답
    zip_buffer.seek(0)
    
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"documents_{timestamp}.zip"
    
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    
    return response


@login_required
@require_POST
def bulk_download_version(request, label_id):
    """특정 표시사항의 모든 문서를 ZIP으로 다운로드"""
    label = get_object_or_404(
        MyLabel,
        my_label_id=label_id,
        user_id=request.user
    )
    
    documents = ProductDocument.objects.filter(
        label=label,
        is_active=True
    ).select_related('document_type')
    
    if not documents.exists():
        return JsonResponse({
            'success': False,
            'error': '다운로드 가능한 문서가 없습니다.'
        }, status=404)
    
    # ZIP 파일 생성
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        used_filenames = {}
        
        for doc in documents:
            try:
                type_name = _sanitize_filename(doc.document_type.type_name)
                original_name = doc.original_filename
                
                arcname = f"{type_name}/{original_name}"
                
                # 중복 처리
                if arcname in used_filenames:
                    used_filenames[arcname] += 1
                    base, ext = os.path.splitext(arcname)
                    arcname = f"{base}_{used_filenames[arcname]}{ext}"
                else:
                    used_filenames[arcname] = 0
                
                zip_file.writestr(arcname, doc.file.read())
                
            except Exception:
                continue
    
    zip_buffer.seek(0)
    
    product_name = _sanitize_filename(label.my_label_name or label.prdlst_nm or '제품')
    timestamp = timezone.now().strftime('%Y%m%d')
    zip_filename = f"{product_name}_{timestamp}.zip"
    
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    
    return response


@login_required
def document_detail(request, document_id):
    """문서 상세"""
    document = get_object_or_404(
        ProductDocument.objects.select_related('label', 'document_type', 'uploaded_by'),
        document_id=document_id,
        label__user_id=request.user
    )
    
    context = {
        'document': document,
    }
    
    return render(request, 'products/documents/document_detail.html', context)


@login_required
def document_download(request, document_id):
    """문서 다운로드"""
    document = get_object_or_404(
        ProductDocument,
        document_id=document_id,
        label__user_id=request.user,
        is_active=True
    )
    
    try:
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.original_filename
        )
    except FileNotFoundError:
        raise Http404("파일을 찾을 수 없습니다.")


@login_required
def expiring_documents(request):
    """만료 예정 문서 목록"""
    today = timezone.now().date()
    alert_date = today + timedelta(days=30)
    
    documents = ProductDocument.objects.filter(
        label__user_id=request.user,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=alert_date
    ).select_related('label', 'document_type').order_by('expiry_date')
    
    context = {
        'documents': documents,
        'today': today,
    }
    
    return render(request, 'products/documents/expiring_documents.html', context)


@login_required
def expired_documents(request):
    """만료된 문서 목록"""
    today = timezone.now().date()
    
    documents = ProductDocument.objects.filter(
        label__user_id=request.user,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=today
    ).select_related('label', 'document_type').order_by('-expiry_date')
    
    context = {
        'documents': documents,
        'today': today,
    }
    
    return render(request, 'products/documents/expired_documents.html', context)


def _sanitize_filename(name):
    """파일/폴더명에 사용할 수 없는 문자 제거"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()[:50]  # 50자 제한


# ==================== 협업 기능 (Stub) ====================

def _get_label_access(request, label_id):
    """댓글용 접근 권한 확인 (오너 또는 공유 사용자)"""
    try:
        label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user)
        return label, 'OWNER'
    except MyLabel.DoesNotExist:
        shared_share = ProductShare.objects.filter(
            label__my_label_id=label_id,
            is_active=True
        ).filter(
            Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
        ).select_related('label').first()

        if not shared_share:
            return None, None

        share_permission = SharePermission.objects.filter(share=shared_share).first()
        role = share_permission.role_code if share_permission else 'VIEWER'
        return shared_share.label, role

@login_required
def comment_list(request, label_id):
    """댓글 목록 API"""
    label, role = _get_label_access(request, label_id)
    if not label:
        return JsonResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status=403)

    comments = ProductComment.objects.filter(label=label, is_resolved=False).select_related('author').order_by('-created_at')
    payload = []
    for comment in comments:
        payload.append({
            'comment_id': comment.comment_id,
            'author': comment.author.username,
            'content': comment.content,
            'created_at': comment.created_at.isoformat()
        })

    return JsonResponse({'success': True, 'comments': payload})


@login_required
@require_POST
def comment_create(request, label_id):
    """댓글 생성 API"""
    label, role = _get_label_access(request, label_id)
    if not label:
        return JsonResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status=403)

    if role not in ['OWNER', 'UPLOADER', 'EDITOR', 'REVIEWER', 'APPROVER']:
        return JsonResponse({'success': False, 'error': '댓글 작성 권한이 없습니다.'}, status=403)

    content = request.POST.get('content', '').strip()
    field_name = request.POST.get('field_name', '').strip() or None
    parent_id = request.POST.get('parent_id')
    if not content:
        return JsonResponse({'success': False, 'error': '댓글 내용을 입력해주세요.'}, status=400)

    parent_comment = None
    if parent_id:
        parent_comment = get_object_or_404(ProductComment, comment_id=parent_id, label=label)

    comment = ProductComment.objects.create(
        label=label,
        author=request.user,
        content=content,
        field_name=field_name,
        parent=parent_comment
    )
    
    # 활동 로그 기록
    from .models import ProductActivityLog
    ProductActivityLog.objects.create(
        label=label,
        user=request.user,
        action='COMMENT_ADDED',
        details={
            'comment_id': comment.comment_id,
            'field_name': field_name,
            'content': content[:100],  # 처음 100자만 저장
            'is_reply': parent_id is not None,
        }
    )

    display_name = comment.author.get_full_name().strip() or comment.author.email

    return JsonResponse({
        'success': True,
        'comment': {
            'comment_id': comment.comment_id,
            'author': comment.author.username,
            'display_name': display_name,
            'email': comment.author.email,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'field_name': comment.field_name,
            'parent_id': comment.parent_id
        }
    })


@login_required
@require_POST
def comment_resolve(request, comment_id):
    """댓글 해결 API"""
    comment = get_object_or_404(ProductComment, comment_id=comment_id)
    if comment.author != request.user and comment.label.user_id != request.user:
        return JsonResponse({'success': False, 'error': '권한이 없습니다.'}, status=403)

    comment.resolve(request.user)
    return JsonResponse({'success': True})


@login_required
@require_POST
def comment_delete(request, comment_id):
    """댓글 삭제 API"""
    comment = get_object_or_404(ProductComment, comment_id=comment_id)
    if comment.author != request.user and comment.label.user_id != request.user:
        return JsonResponse({'success': False, 'error': '권한이 없습니다.'}, status=403)

    comment.delete()
    return JsonResponse({'success': True})


@login_required
def suggestion_list(request, label_id):
    """제안 목록 API"""
    return JsonResponse({'suggestions': []})


@login_required
@require_POST
def suggestion_create(request, label_id):
    """제안 생성 API"""
    return JsonResponse({'success': False, 'message': '준비 중입니다.'})


@login_required
@require_POST
def suggestion_process(request, suggestion_id):
    """제안 처리 API"""
    return JsonResponse({'success': False, 'message': '준비 중입니다.'})


@login_required
def mentionable_users(request, label_id):
    """멘션 가능 사용자 API"""
    return JsonResponse({'users': []})


@login_required
@require_POST
def bulk_delete_documents(request):
    """문서 일괄 삭제"""
    import json
    from .models import ProductActivityLog
    
    try:
        data = json.loads(request.body)
        document_ids = data.get('document_ids', [])
        
        if not document_ids:
            return JsonResponse({
                'success': False,
                'error': '삭제할 문서를 선택해주세요.'
            }, status=400)
        
        # 권한 확인 및 삭제
        documents = ProductDocument.objects.filter(
            document_id__in=document_ids,
            label__user_id=request.user,
            is_active=True
        )
        
        deleted_count = 0
        for document in documents:
            file_name = document.original_filename
            document_type_name = document.document_type.type_name if document.document_type else '미분류'
            label = document.label
            
            # Soft Delete
            document.is_active = False
            document.save()
            
            # 활동 로그 생성
            ProductActivityLog.objects.create(
                label=label,
                user=request.user,
                action='DOCUMENT_DELETED',
                details={
                    'file_name': file_name,
                    'document_type': document_type_name
                }
            )
            
            deleted_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}개의 문서가 삭제되었습니다.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'삭제 중 오류가 발생했습니다: {str(e)}'
        }, status=500)


@login_required
@require_POST
def toggle_document_notification(request, document_id):
    """문서 만료일 알림 토글"""
    import json
    
    try:
        document = get_object_or_404(
            ProductDocument,
            document_id=document_id,
            label__user_id=request.user,
            is_active=True
        )
        
        # 알림 토글
        document.expiry_notification_enabled = not document.expiry_notification_enabled
        document.save()
        
        return JsonResponse({
            'success': True,
            'enabled': document.expiry_notification_enabled
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def document_versions(request, document_id):
    """문서 버전 이력 조회"""
    try:
        document = get_object_or_404(
            ProductDocument,
            document_id=document_id,
            label__user_id=request.user
        )
        
        # 현재 문서의 모든 버전 조회 (parent_document가 같거나 자기 자신이 parent인 경우)
        if document.parent_document:
            parent_id = document.parent_document.document_id
        else:
            parent_id = document.document_id
        
        versions = ProductDocument.objects.filter(
            Q(document_id=parent_id) |
            Q(parent_document_id=parent_id)
        ).order_by('-version')
        
        version_list = []
        for v in versions:
            version_list.append({
                'version': v.version,
                'filename': v.original_filename,
                'uploaded_by': v.uploaded_by.username if v.uploaded_by else '알 수 없음',
                'uploaded_date': v.uploaded_datetime.strftime('%Y-%m-%d %H:%M'),
                'file_url': f'/v2/products/documents/{v.document_id}/',
                'is_current': v.document_id == document.document_id
            })
        
        return JsonResponse({
            'success': True,
            'versions': version_list
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def document_update(request, document_id):
    """문서 메타데이터 업데이트 (구분, 발행일, 만료일, 설명)"""
    import json
    
    try:
        document = get_object_or_404(
            ProductDocument,
            document_id=document_id,
            label__user_id=request.user
        )
        
        data = json.loads(request.body)
        
        # 문서 타입 변경 (슬롯 재연결 포함)
        if 'document_type_id' in data:
            old_document_type = document.document_type
            new_document_type = get_object_or_404(DocumentType, type_id=data['document_type_id'])
            
            if old_document_type != new_document_type:
                from .models import DocumentSlot
                
                # 기존 슬롯 저장
                old_slot = document.slot
                
                # 새 타입으로 변경
                document.document_type = new_document_type
                
                # 슬롯 재연결
                if new_document_type.is_required:
                    # 필수 문서: 해당 타입의 슬롯 찾기/생성
                    new_slot, created = DocumentSlot.objects.get_or_create(
                        label=document.label,
                        document_type=new_document_type
                    )
                    document.slot = new_slot
                else:
                    # 일반 문서: 슬롯 연결 해제
                    document.slot = None
                
                # 문서 저장
                document.save()
                
                # 기존 슬롯 상태 업데이트
                if old_slot:
                    # current_document가 이 문서였다면 교체
                    if old_slot.current_document == document:
                        # 같은 슬롯의 다른 활성 문서 찾기
                        replacement = ProductDocument.objects.filter(
                            slot=old_slot,
                            is_active=True
                        ).exclude(document_id=document.document_id).order_by('-uploaded_datetime').first()
                        old_slot.current_document = replacement
                    old_slot.update_status()
                    old_slot.save()
                
                # 새 슬롯 상태 업데이트
                if document.slot:
                    # 이 문서가 가장 최신인지 확인
                    latest_doc = ProductDocument.objects.filter(
                        slot=document.slot,
                        is_active=True
                    ).order_by('-uploaded_datetime').first()
                    
                    if latest_doc == document:
                        document.slot.current_document = document
                    document.slot.update_status()
                    document.slot.save()
            else:
                document.document_type = new_document_type
        
        # 발행일 변경
        if 'issue_date' in data:
            if data['issue_date']:
                from datetime import datetime
                document.issue_date = datetime.strptime(data['issue_date'], '%Y-%m-%d').date()
            else:
                document.issue_date = None
        
        # 만료일 변경
        if 'expiry_date' in data:
            if data['expiry_date']:
                from datetime import datetime
                document.expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
            else:
                document.expiry_date = None
        
        # 설명 변경
        if 'description' in data:
            document.description = data['description']
        
        # 만료 알림 설정 변경
        if 'expiry_notification_enabled' in data:
            document.expiry_notification_enabled = data['expiry_notification_enabled']
        
        document.save()
        
        # 연결된 슬롯이 있으면 상태 업데이트
        if document.slot:
            document.slot.update_status()
            document.slot.save()
        
        return JsonResponse({
            'success': True,
            'message': '문서 정보가 업데이트되었습니다.',
            'document': {
                'document_id': document.document_id,
                'document_type': document.document_type.type_name,
                'issue_date': document.issue_date.strftime('%Y-%m-%d') if document.issue_date else None,
                'expiry_date': document.expiry_date.strftime('%Y-%m-%d') if document.expiry_date else None,
                'description': document.description,
                'expiry_notification_enabled': document.expiry_notification_enabled
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def toggle_slot_visibility(request, slot_id):
    """슬롯 숨김/표시 토글"""
    from .models import DocumentSlot
    
    try:
        slot = get_object_or_404(
            DocumentSlot,
            slot_id=slot_id,
            label__user_id=request.user
        )
        
        # 필수 문서는 숨길 수 없음
        if slot.document_type.is_required:
            return JsonResponse({
                'success': False,
                'error': '필수 문서 슬롯은 숨길 수 없습니다.'
            }, status=400)
        
        # 숨김 상태 토글
        slot.is_hidden = not slot.is_hidden
        slot.save()
        
        # 활동 로그
        from .models import ProductActivityLog
        ProductActivityLog.objects.create(
            label=slot.label,
            user=request.user,
            action='SLOT_VISIBILITY_CHANGED',
            details={
                'slot_id': slot.slot_id,
                'document_type': slot.document_type.type_name,
                'is_hidden': slot.is_hidden
            }
        )
        
        return JsonResponse({
            'success': True,
            'is_hidden': slot.is_hidden
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def add_document_slot(request, label_id):
    """문서 슬롯 추가 (필수 문서 확장)"""
    import json

    try:
        label = get_object_or_404(
            MyLabel,
            my_label_id=label_id,
            user_id=request.user
        )

        data = json.loads(request.body)
        document_type_id = data.get('document_type_id')
        if not document_type_id:
            return JsonResponse({
                'success': False,
                'error': '문서 종류를 선택해주세요.'
            }, status=400)

        document_type = get_object_or_404(DocumentType, type_id=document_type_id, is_active=True)

        slot = DocumentSlot.objects.filter(label=label, document_type=document_type).first()
        if slot:
            if slot.is_hidden:
                slot.is_hidden = False
                slot.save()
                message = '숨겨진 문서가 다시 표시됩니다.'
            else:
                message = '이미 추가된 문서입니다.'
        else:
            slot = DocumentSlot.objects.create(label=label, document_type=document_type)
            message = '문서가 추가되었습니다.'

        return JsonResponse({
            'success': True,
            'message': message,
            'slot_id': slot.slot_id,
            'document_type': document_type.type_name
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'문서 추가 중 오류가 발생했습니다: {str(e)}'
        }, status=500)


# ==================== 알림 (Notifications) ====================

@login_required
def notification_list(request):
    """읽지 않은 알림 목록 + 최근 알림 반환 (JSON)"""
    qs = ProductNotification.objects.filter(
        recipient=request.user
    ).select_related('label').order_by('-created_at')[:30]

    unread_count = ProductNotification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    items = []
    for n in qs:
        items.append({
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'status_code': n.status_code,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
            'label_id': n.label_id,
            'label_name': (n.label.my_label_name or n.label.prdlst_nm or '') if n.label else '',
            'url': f'/products/{n.label.my_label_id}/' if n.label else '',
        })

    return JsonResponse({'notifications': items, 'unread': unread_count})


@login_required
@require_POST
def notification_mark_read(request):
    """알림 읽음 처리 – 특정 id 또는 전체"""
    import json
    try:
        body = json.loads(request.body)
        notification_id = body.get('id')
    except (ValueError, AttributeError):
        notification_id = None

    if notification_id:
        ProductNotification.objects.filter(
            id=notification_id, recipient=request.user
        ).update(is_read=True)
    else:
        ProductNotification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)

    unread_count = ProductNotification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    return JsonResponse({'success': True, 'unread': unread_count})
