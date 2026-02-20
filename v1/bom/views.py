# ==================== BOM Views (V2) ====================

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
import json

from .models import ProductBOM
from v1.label.models import MyLabel, MyIngredient
from v1.label.utils import GMO_LIST


def _resolve_label_and_permission(request, label_id):
    """
    (label, is_owner, can_edit) 반환.
    접근 권한 없으면 JsonResponse(status=403)을 반환함.
    - 오너: (label, True, True)
    - 공유(can_edit_label=True): (label, False, True)
    - 공유(can_edit_label=False): (label, False, False)
    - 권한 없음: 403 JsonResponse
    """
    from django.utils import timezone
    from v1.products.models import ProductShare, SharePermission

    try:
        label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user, delete_YN='N')
        return label, True, True
    except MyLabel.DoesNotExist:
        pass

    shared_share = ProductShare.objects.filter(
        label__my_label_id=label_id,
        is_active=True,
    ).filter(
        Q(recipient_user=request.user) | Q(recipient_email__iexact=request.user.email)
    ).filter(
        Q(share_end_date__isnull=True) | Q(share_end_date__gt=timezone.now())
    ).select_related('label', 'permission').first()

    if not shared_share:
        return None, False, False

    perm = getattr(shared_share, 'permission', None)
    can_edit = bool(perm and perm.can_edit_label)
    return shared_share.label, False, can_edit


# ==================== BOM 편집기 (Google Sheets 스타일) ====================

@login_required
@xframe_options_sameorigin
def bom_workspace(request, label_id):
    """BOM 통합 워크스페이스 (오너 + 공유 사용자 접근 가능)"""
    label, is_owner, can_edit = _resolve_label_and_permission(request, label_id)
    if label is None:
        from django.http import Http404
        raise Http404('접근 권한이 없습니다.')

    my_labels = MyLabel.objects.filter(
        user_id=request.user,
        delete_YN='N'
    ).order_by('-update_datetime')

    context = {
        'label': label,
        'product': label,
        'my_labels': my_labels,
        'gmo_list': GMO_LIST,
        'can_edit': can_edit,
        'is_owner': is_owner,
    }

    return render(request, 'products/bom_detail.html', context)


@login_required
@xframe_options_sameorigin
def bom_editor(request, label_id):
    """BOM 통합 워크스페이스로 이동"""
    return bom_workspace(request, label_id)


@login_required
def api_ingredient_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    results = []

    my_ingredients = MyIngredient.objects.filter(
        user_id=request.user,
        delete_YN='N'
    ).filter(
        Q(ingredient_display_name__icontains=query) |
        Q(prdlst_nm__icontains=query)
    ).order_by('-update_datetime')[:10]

    for ingredient in my_ingredients:
        prdlst_nm = ingredient.prdlst_nm or ''
        display_name = ingredient.ingredient_display_name or ''
        # 자동완성/팔레트 표시명 = 원료명(prdlst_nm) 우선
        name = prdlst_nm or display_name
        if not name:
            continue
        results.append({
            'name': name,                                     # 원료명 (자동완성 키 & ingredient_name 컨럼에 입력되는 값)
            'type': 'ingredient',
            'origin': '',
            'allergen': ingredient.allergens or '',
            'raw_material_name': display_name or prdlst_nm,  # 원재료 표시명 (ingredient_display_name 우선)
            'allergens': ingredient.allergens or '',
            'food_type': ingredient.prdlst_dcnm or '',
            'gmo': ingredient.gmo or '',
            'is_gmo': bool(ingredient.gmo),
            'report_no': ingredient.prdlst_report_no or '',
            'manufacturer': ingredient.bssh_nm or '',
            'id': ingredient.my_ingredient_id
        })

    from v1.products.models import SharedProductReceipt
    shared_receipts = SharedProductReceipt.objects.filter(
        receiver=request.user,
        is_accepted=True,
        share__permission__can_use_as_ingredient=True
    ).filter(
        Q(share__label__my_label_name__icontains=query) |
        Q(share__label__prdlst_nm__icontains=query)
    ).select_related('share__label', 'share__created_by').order_by('-received_datetime')[:5]

    for receipt in shared_receipts:
        label = receipt.share.label
        raw_material_name = label.rawmtrl_nm_display or label.rawmtrl_nm or label.my_label_name or label.prdlst_nm or ''
        results.append({
            'name': label.my_label_name or label.prdlst_nm,
            'type': 'shared',
            'origin': label.country_of_origin or '',
            'allergen': getattr(label, 'allergens', '') or '',
            'raw_material_name': raw_material_name,
            'allergens': getattr(label, 'allergens', '') or '',
            'food_type': label.prdlst_dcnm or '',
            'is_gmo': False,
            'report_no': label.prdlst_report_no or '',
            'manufacturer': label.bssh_nm or '',
            'owner': receipt.share.created_by.username,
            'id': label.my_label_id,
            'receipt_id': receipt.receipt_id
        })

    return JsonResponse({'results': results})


@login_required
def api_palette_list(request):
    query = request.GET.get('q', '').strip()

    my_ingredients = MyIngredient.objects.filter(
        user_id=request.user,
        delete_YN='N'
    )

    if query:
        my_ingredients = my_ingredients.filter(
            Q(ingredient_display_name__icontains=query) |
            Q(prdlst_nm__icontains=query)
        )

    my_ingredients = my_ingredients.order_by('-update_datetime')[:50]

    my_items = []
    for ingredient in my_ingredients:
        prdlst_nm = ingredient.prdlst_nm or ''
        display_name = ingredient.ingredient_display_name or ''
        name = prdlst_nm or display_name  # 원료명 우선
        if not name:
            continue
        my_items.append({
            'name': name,
            'prdlst_nm': prdlst_nm,
            'origin': '',
            'allergen': ingredient.allergens or '',
            'raw_material_name': display_name or prdlst_nm,  # 원재료 표시명 우선
            'allergens': ingredient.allergens or '',
            'food_type': ingredient.prdlst_dcnm or '',
            'gmo': ingredient.gmo or '',
            'is_gmo': bool(ingredient.gmo),
            'report_no': ingredient.prdlst_report_no or '',
            'manufacturer': ingredient.bssh_nm or '',
            'type': 'ingredient',
            'ingredient_id': ingredient.my_ingredient_id
        })

    from v1.products.models import SharedProductReceipt
    shared_receipts = SharedProductReceipt.objects.filter(
        receiver=request.user,
        is_accepted=True,
        share__permission__can_use_as_ingredient=True
    )

    if query:
        shared_receipts = shared_receipts.filter(
            Q(share__label__my_label_name__icontains=query) |
            Q(share__label__prdlst_nm__icontains=query)
        )

    shared_receipts = shared_receipts.select_related(
        'share__label',
        'share__created_by'
    ).order_by('-received_datetime')[:50]

    shared_items = []
    for receipt in shared_receipts:
        label = receipt.share.label
        raw_material_name = label.rawmtrl_nm_display or label.rawmtrl_nm or label.my_label_name or label.prdlst_nm or ''
        shared_items.append({
            'name': label.my_label_name or label.prdlst_nm,
            'prdlst_nm': label.prdlst_nm or '',
            'origin': label.country_of_origin or '',
            'allergen': getattr(label, 'allergens', '') or '',
            'raw_material_name': raw_material_name,
            'allergens': getattr(label, 'allergens', '') or '',
            'food_type': label.prdlst_dcnm or '',
            'gmo': '',
            'is_gmo': False,
            'report_no': label.prdlst_report_no or '',
            'manufacturer': label.bssh_nm or '',
            'type': 'shared',
            'label_id': label.my_label_id,
            'receipt_id': receipt.receipt_id,
            'owner': receipt.share.created_by.username
        })

    recent_items = my_items[:12]

    my_labels = MyLabel.objects.filter(
        user_id=request.user,
        delete_YN='N'
    )

    if query:
        my_labels = my_labels.filter(
            Q(my_label_name__icontains=query) |
            Q(prdlst_nm__icontains=query)
        )

    my_labels = my_labels.order_by('-update_datetime')[:30]

    label_items = []
    for label in my_labels:
        label_items.append({
            'label_id': label.my_label_id,
            'name': label.my_label_name or label.prdlst_nm,
            'updated_at': label.update_datetime.strftime('%Y-%m-%d') if label.update_datetime else ''
        })

    return JsonResponse({
        'recent': recent_items,
        'my': my_items,
        'shared': shared_items,
        'labels': label_items
    })


@login_required
def api_ingredient_detail(request, ingredient_id):
    ingredient = get_object_or_404(
        MyIngredient,
        my_ingredient_id=ingredient_id,
        user_id=request.user,
        delete_YN='N'
    )

    prdlst_nm = ingredient.prdlst_nm or ''
    display_name = ingredient.ingredient_display_name or ''

    return JsonResponse({
        'success': True,
        'ingredient_id': ingredient.my_ingredient_id,
        'name': prdlst_nm or display_name,          # 원료명
        'raw_material_name': display_name or prdlst_nm,  # 원재료 표시명
        'food_type': ingredient.prdlst_dcnm or '',
        'manufacturer': ingredient.bssh_nm or '',
        'report_no': ingredient.prdlst_report_no or '',
        'allergens': ingredient.allergens or '',
        'gmo': ingredient.gmo or ''
    })


@login_required
def api_load_from_label(request, label_id):
    label = get_object_or_404(
        MyLabel,
        my_label_id=label_id,
        user_id=request.user
    )

    raw_text = (label.rawmtrl_nm_display or label.rawmtrl_nm or '').strip()
    if not raw_text:
        return JsonResponse({'success': True, 'data': []})

    import re
    ingredients = [item.strip() for item in re.split(r'[\n,]+', raw_text) if item.strip()]

    data = []
    label_name = label.my_label_name or label.prdlst_nm or ''
    for name in ingredients:
        data.append({
            'ingredient_name': name,
            'raw_material_name': name,
            'sub_ingredients': '',
            'allergens': getattr(label, 'allergens', '') or '',
            'origin_detail': label.country_of_origin or '',
            'food_type': label.prdlst_dcnm or '',
            'is_additive': False,
            'additive_role': '',
            'is_gmo': False,
            'report_no': label.prdlst_report_no or '',
            'manufacturer': label.bssh_nm or '',
            'source_label_id': label.my_label_id,
            'mixing_ratio': None,
            'origin': '',
            'allergen': getattr(label, 'allergens', '') or '',
            'notes': f"라벨 '{label_name}'에서 가져옴"
        })

    return JsonResponse({'success': True, 'data': data})


@login_required
def bom_data_api(request, label_id):
    """BOM Data API for Handsontable (오너 + 공유 사용자 접근 가능)"""
    label, is_owner, can_edit = _resolve_label_and_permission(request, label_id)
    if label is None:
        return JsonResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status=403)
    
    boms = ProductBOM.objects.filter(
        parent_label=label,
        is_active=True
    ).select_related(
        'child_label',
        'shared_receipt__share__label'
    ).order_by('level', 'sort_order')
    
    data = []
    for bom in boms:
        # 원료 소스 판단
        if bom.child_label:
            ingredient_name = bom.child_label.my_label_name or bom.child_label.prdlst_nm
            ingredient_code = bom.child_label.prdlst_report_no or ''
            source_type = 'my'
            source_id = bom.child_label.my_label_id
            shared_owner = ''
        elif bom.shared_receipt:
            shared_label = bom.shared_receipt.share.label
            ingredient_name = shared_label.my_label_name or shared_label.prdlst_nm
            ingredient_code = shared_label.prdlst_report_no or ''
            source_type = 'shared'
            source_id = bom.shared_receipt.receipt_id
            shared_owner = bom.shared_receipt.share.created_by.username
        else:
            ingredient_name = bom.ingredient_name
            ingredient_code = ''
            source_type = 'ingredient' if bom.source_ingredient_id else 'manual'
            source_id = None
            shared_owner = ''
        
        data.append({
            'bom_id': bom.bom_id,
            'ingredient_name': bom.ingredient_name or ingredient_name,
            'ingredient_code': ingredient_code,
            'source_type': source_type,
            'source_id': source_id,
            'shared_owner': shared_owner,
            'content_ratio': float(bom.usage_ratio) if bom.usage_ratio else None,
            'origin': bom.origin or '',
            'allergen': bom.allergens or bom.allergen or '',
            'raw_material_name': bom.raw_material_name or '',
            'sub_ingredients': bom.sub_ingredients or '',
            'allergens': bom.allergens or bom.allergen or '',
            'gmo': bom.gmo or '',
            'origin_detail': bom.origin_detail or '',
            'food_type': bom.food_type or '',
            'is_additive': bom.is_additive,
            'additive_role': bom.additive_role or '',
            'is_gmo': bom.is_gmo,
            'report_no': bom.report_no or '',
            'manufacturer': bom.manufacturer or '',
            'source_label_id': bom.source_ingredient_id,
            'notes': bom.notes or '',
            'summary_type': bom.summary_type or '\uc2dd\ud488\uc720\ud615',
            'level': bom.level,
            'sort_order': bom.sort_order,
            # \ub808\uac70\uc2dc \ud544\ub4dc
            'mixing_ratio': float(bom.usage_ratio) if bom.usage_ratio else None,
            'usage_amount': float(bom.usage_amount) if bom.usage_amount else None,
            'usage_unit': bom.usage_unit or 'g',
        })
    
    return JsonResponse({
        'success': True,
        'data': data,
        'label_id': label_id,
        'product_name': label.my_label_name or label.prdlst_nm,
        'can_edit': can_edit,
    })


@login_required
@require_POST
def bom_save_api(request, label_id):
    """BOM Save API (오너 + can_edit_label 공유 사용자만 허용)"""
    label, is_owner, can_edit = _resolve_label_and_permission(request, label_id)
    if label is None:
        return JsonResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status=403)
    if not can_edit:
        return JsonResponse({'success': False, 'error': 'BOM 편집 권한이 없습니다. (현재 권한으로는 BOM을 수정할 수 없습니다.)'}, status=403)

    import logging
    logger = logging.getLogger(__name__)
    try:
        from v1.label.models import LabelIngredientRelation, MyIngredient as MI
        from v1.products.models import SharedProductReceipt

        data = json.loads(request.body)
        bom_items = data.get('items', [])

        # 기존 BOM 비활성화
        ProductBOM.objects.filter(parent_label=label).update(is_active=False)

        for idx, item in enumerate(bom_items):
            if not item.get('ingredient_name'):
                continue

            bom_id     = item.get('bom_id')
            source_type = item.get('source_type', 'manual')
            source_id  = item.get('source_id')
            sl_id      = item.get('source_label_id')  # JS가 보내는 my_ingredient_id

            # ── source_ingredient (FK) 결정 ────────────────────────────────
            source_ingredient = None

            if source_type == 'ingredient' and sl_id:
                # 내 원료 보관함에서 선택한 원료
                source_ingredient = MI.objects.filter(
                    my_ingredient_id=int(sl_id), delete_YN='N'
                ).first()

            elif source_type == 'manual':
                # 직접 입력 → 기존 BOM의 source_ingredient 재사용 또는 새로 생성
                existing_mi = None
                if bom_id:
                    existing_bom = ProductBOM.objects.filter(bom_id=bom_id).first()
                    if existing_bom:
                        existing_mi = existing_bom.source_ingredient

                if existing_mi:
                    # 기존 원료 정보 동기화
                    existing_mi.prdlst_nm              = item.get('ingredient_name', '')
                    existing_mi.ingredient_display_name = (item.get('raw_material_name') or
                                                           item.get('ingredient_name', ''))
                    existing_mi.prdlst_dcnm            = item.get('food_type', '')
                    existing_mi.allergens               = item.get('allergens', '')
                    existing_mi.gmo                    = item.get('gmo', '')
                    existing_mi.bssh_nm                = item.get('manufacturer', '')
                    existing_mi.save()
                    source_ingredient = existing_mi
                else:
                    # 새 원료 자동 생성
                    source_ingredient = MI.objects.create(
                        user_id                = request.user,
                        prdlst_nm              = item.get('ingredient_name', ''),
                        ingredient_display_name = (item.get('raw_material_name') or
                                                   item.get('ingredient_name', '')),
                        prdlst_dcnm            = item.get('food_type', ''),
                        allergens               = item.get('allergens', ''),
                        gmo                    = item.get('gmo', ''),
                        bssh_nm                = item.get('manufacturer', ''),
                        delete_YN              = 'N',
                    )
            # ──────────────────────────────────────────────────────────────

            # child_label / shared_receipt
            child_label    = None
            shared_receipt = None
            if source_type == 'internal' and source_id:
                child_label = MyLabel.objects.filter(
                    my_label_id=source_id, user_id=request.user
                ).first()
            elif source_type == 'shared' and source_id:
                shared_receipt = SharedProductReceipt.objects.filter(
                    receipt_id=source_id, receiver=request.user
                ).first()

            common_fields = dict(
                ingredient_name  = item.get('ingredient_name'),
                usage_ratio      = item.get('content_ratio') or item.get('mixing_ratio'),
                origin           = item.get('origin', ''),
                allergen         = item.get('allergens') or item.get('allergen') or '',
                raw_material_name= item.get('raw_material_name') or '',
                sub_ingredients  = item.get('sub_ingredients') or '',
                allergens        = item.get('allergens') or item.get('allergen') or '',
                gmo              = item.get('gmo') or '',
                origin_detail    = item.get('origin_detail') or '',
                food_type        = item.get('food_type') or '',
                is_additive      = bool(item.get('is_additive')),
                additive_role    = item.get('additive_role') or '',
                is_gmo           = bool(item.get('is_gmo')),
                report_no        = item.get('report_no') or '',
                manufacturer     = item.get('manufacturer') or '',
                source_ingredient= source_ingredient,
                notes            = item.get('notes', ''),
                summary_type     = item.get('summary_type', '식품유형'),
                level            = item.get('level', 1),
                sort_order       = idx,
                is_active        = True,
                child_label      = child_label,
                shared_receipt   = shared_receipt,
            )

            if bom_id:
                bom = ProductBOM.objects.filter(bom_id=bom_id).first()
                if bom:
                    for k, v in common_fields.items():
                        setattr(bom, k, v)
                    bom.save()
                    continue

            ProductBOM.objects.create(
                parent_label=label,
                created_by=request.user,
                **common_fields
            )

        # ── LabelIngredientRelation 동기화 (source_ingredient FK 기반) ──────
        saved_boms = ProductBOM.objects.filter(
            parent_label=label, is_active=True
        ).select_related('source_ingredient')

        valid_ing_ids = {
            b.source_ingredient_id for b in saved_boms if b.source_ingredient_id
        }
        LabelIngredientRelation.objects.filter(label=label).exclude(
            ingredient_id__in=valid_ing_ids
        ).delete()

        seq = 1
        for bom in saved_boms:
            if not bom.source_ingredient_id:
                continue
            LabelIngredientRelation.objects.update_or_create(
                label=label,
                ingredient_id=bom.source_ingredient_id,
                defaults={
                    'ingredient_ratio': bom.usage_ratio,
                    'relation_sequence': seq,
                }
            )
            seq += 1
        # ──────────────────────────────────────────────────────────────────

        return JsonResponse({'success': True, 'message': 'BOM이 저장되었습니다'})

    except Exception as e:
        logger.exception('[BOM 저장] 예외 발생')
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def bom_load_from_label_api(request, label_id):
    """BOM Load from Label API"""
    label = get_object_or_404(
        MyLabel,
        my_label_id=label_id,
        user_id=request.user
    )
    
    data = []
    
    # 표시사항에서 원재료 추출
    # rawmtrl_nm: 원재료명 (쉼표 또는 줄바꿈 구분)
    # rawmtrl_nm_display: 표시용 원재료명
    # allergens: 알레르기 유발 물질
    # country_of_origin: 원산지
    
    if label.rawmtrl_nm:
        # 원재료명 파싱 (쉼표, 줄바꿈 구분)
        import re
        raw_text = label.rawmtrl_nm.strip()
        # 쉼표나 줄바꿈으로 분리
        ingredients = re.split(r'[,\n]+', raw_text)
        
        # 알레르기 정보 (전체)
        allergens_text = label.allergens or ''
        
        # 원산지 정보 (전체)
        origin_text = label.country_of_origin or ''
        
        for idx, ing in enumerate(ingredients):
            ing_name = ing.strip()
            if not ing_name:
                continue
            
            # 함량 추출 (괄호 안 숫자% 형식)
            ratio = None
            ratio_match = re.search(r'\((\d+(?:\.\d+)?)\s*%?\)', ing_name)
            if ratio_match:
                ratio = float(ratio_match.group(1))
                # 함량 부분 제거
                ing_name = re.sub(r'\(\d+(?:\.\d+)?\s*%?\)', '', ing_name).strip()
            
            # 원산지 추출 (괄호 안 "국산", "미국산" 등)
            origin = ''
            origin_match = re.search(r'\((국산|외국산|[가-힣]+산)\)', ing_name)
            if origin_match:
                origin = origin_match.group(1)
                ing_name = re.sub(r'\([가-힣]+산\)', '', ing_name).strip()
            
            # 알레르기 정보 추출
            allergen = ''
            allergen_keywords = ['우유', '대두', '밀', '땅콩', '견과류', '계란', '생선', '조개류', '새우', '게']
            for keyword in allergen_keywords:
                if keyword in ing_name or keyword in allergens_text:
                    if allergen:
                        allergen += ', '
                    allergen += keyword
            
            data.append({
                'ingredient_name': ing_name,
                'content_ratio': ratio,
                'origin': origin or origin_text,  # 개별 원산지가 없으면 전체 원산지 사용
                'allergen': allergens_text or allergen,
                'raw_material_name': ing_name,
                'sub_ingredients': '',
                'allergens': allergens_text or allergen,
                'origin_detail': origin or origin_text,
                'food_type': label.prdlst_dcnm or '',
                'is_additive': False,
                'additive_role': '',
                'is_gmo': False,
                'report_no': label.prdlst_report_no or '',
                'manufacturer': label.bssh_nm or '',
                'source_label_id': label.my_label_id,
                'notes': ''
            })
    
    return JsonResponse({
        'success': True,
        'data': data,
        'label_id': label_id
    })


@login_required
def bom_calculate_nutrition(request, label_id):
    """BOM 기반 영양성분 계산 API"""
    label = get_object_or_404(
        MyLabel,
        my_label_id=label_id,
        user_id=request.user
    )
    
    # POST body에서 임시 BOM 데이터 받기 (저장 전 계산용)
    if request.method == 'POST':
        try:
            temp_data = json.loads(request.body)
            bom_items = temp_data.get('items', [])
        except:
            bom_items = []
    else:
        # DB에서 저장된 BOM 가져오기
        bom_items = list(ProductBOM.objects.filter(
            parent_label=label,
            is_active=True
        ).values('ingredient_name', 'usage_ratio', 'usage_amount'))
    
    # 영양성분 초기화 (향후 구현)
    nutrition = {
        'calories': 0,
        'carbohydrate': 0,
        'protein': 0,
        'fat': 0,
        'sodium': 0,
        'sugars': 0,
    }
    
    total_ratio = sum(float(item.get('usage_ratio') or item.get('content_ratio') or 0) for item in bom_items)
    
    # TODO: 원재료별 영양성분 DB에서 조회 후 계산
    # 현재는 더미 데이터 반환
    
    return JsonResponse({
        'success': True,
        'nutrition': nutrition,
        'total_ratio': total_ratio,
        'is_valid': abs(total_ratio - 100) < 0.01 if total_ratio > 0 else True
    })


@login_required
def bom_autocomplete(request):
    """원재료 자동완성 API"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    results = []
    
    # 내 제품에서 검색
    my_labels = MyLabel.objects.filter(
        user_id=request.user
    ).filter(
        Q(my_label_name__icontains=query) |
        Q(prdlst_nm__icontains=query)
    )[:10]
    
    for lbl in my_labels:
        results.append({
            'id': f'my_{lbl.my_label_id}',
            'text': lbl.my_label_name or lbl.prdlst_nm,
            'code': lbl.prdlst_report_no or '',
            'type': 'my',
            'label_id': lbl.my_label_id
        })
    
    # 공유받은 제품에서 검색
    from v1.products.models import SharedProductReceipt
    shared = SharedProductReceipt.objects.filter(
        receiver=request.user,
        is_accepted=True,
        share__permission__can_use_as_ingredient=True
    ).filter(
        Q(share__label__my_label_name__icontains=query) |
        Q(share__label__prdlst_nm__icontains=query)
    ).select_related('share__label', 'share__created_by')[:10]
    
    for s in shared:
        label = s.share.label
        results.append({
            'id': f'shared_{s.receipt_id}',
            'text': f'{label.my_label_name or label.prdlst_nm} (from {s.share.created_by.username})',
            'code': label.prdlst_report_no or '',
            'type': 'shared',
            'receipt_id': s.receipt_id
        })

    return JsonResponse({'results': results})

