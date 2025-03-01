import json
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Subquery, OuterRef
from .models import FoodItem, MyLabel, MyIngredient, CountryList, LabelIngredientRelation, FoodType
from .forms import LabelCreationForm
from venv import logger  #지우지 말 것
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

# ------------------------------------------
# 헬퍼 함수들 (반복되는 코드 최적화)
# ------------------------------------------

def get_search_conditions(request, search_fields):
    """
    Request에서 검색 조건을 추출하고 Q 객체를 생성합니다.
    """
    search_conditions = Q()
    search_values = {}
    for field, query_param in search_fields.items():
        value = request.GET.get(query_param, "").strip()
        if value:
            search_conditions &= Q(**{f"{field}__icontains": value})
            search_values[query_param] = value
    return search_conditions, search_values

def paginate_queryset(queryset, page_number, items_per_page):
    """
    페이징 처리를 수행합니다.
    """
    paginator = Paginator(queryset, items_per_page)
    page_obj = paginator.get_page(page_number)
    page_range = range(max(1, page_obj.number - 5), min(paginator.num_pages + 1, page_obj.number + 5))
    return paginator, page_obj, page_range

def process_sorting(request, default_sort):
    """
    정렬 필드와 정렬 순서를 처리합니다.
    """
    sort_field = request.GET.get("sort", default_sort)
    sort_order = request.GET.get("order", "asc")
    if sort_order == "desc":
        sort_field = f"-{sort_field}"
    return sort_field, sort_order

def get_querystring_without(request, keys):
    """
    요청의 GET 파라미터에서 지정한 키들을 제거한 쿼리 문자열을 반환합니다.
    """
    q = request.GET.copy()
    for key in keys:
        q.pop(key, None)
    return q.urlencode()

# ------------------------------------------
# View 함수들
# ------------------------------------------

@login_required
def food_item_list(request):
    search_fields = {
        "prdlst_nm": "prdlst_nm",
        "bssh_nm": "bssh_nm",
        "prdlst_dcnm": "prdlst_dcnm",
        "pog_daycnt": "pog_daycnt",
        "prdlst_report_no": "prdlst_report_no",
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    sort_field, sort_order = process_sorting(request, "prdlst_nm")
    items_per_page = int(request.GET.get("items_per_page", 10))
    page_number = request.GET.get("page", 1)

    food_items = FoodItem.objects.filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(food_items, page_number, items_per_page)

    querystring_without_page = get_querystring_without(request, ["page"])
    querystring_without_sort = get_querystring_without(request, ["sort", "order"])

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": page_range,
        "search_fields": [
            {"name": "prdlst_report_no", "placeholder": "품목제조번호", "value": search_values.get("prdlst_report_no", "")},
            {"name": "prdlst_nm", "placeholder": "제품명", "value": search_values.get("prdlst_nm", "")},
            {"name": "prdlst_dcnm", "placeholder": "식품유형", "value": search_values.get("prdlst_dcnm", "")},
            {"name": "bssh_nm", "placeholder": "제조사명", "value": search_values.get("bssh_nm", "")},
            {"name": "pog_daycnt", "placeholder": "소비기한", "value": search_values.get("pog_daycnt", "")},
        ],
        "items_per_page": items_per_page,
        "sort_field": sort_field,
        "sort_order": sort_order,
        "querystring_without_page": querystring_without_page,
        "querystring_without_sort": querystring_without_sort,
    }

    return render(request, "label/food_item_list.html", context)


@login_required
def my_label_list(request):
    search_fields = {
        "my_label_name": "my_label_name",
        "prdlst_report_no": "prdlst_report_no",
        "prdlst_nm": "prdlst_nm",
        "prdlst_dcnm": "prdlst_dcnm",
        "bssh_nm": "bssh_nm",
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    sort_field, sort_order = process_sorting(request, "my_label_name")
    items_per_page = int(request.GET.get("items_per_page", 10))
    page_number = request.GET.get("page", 1)

    labels = MyLabel.objects.filter(user_id=request.user).filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(labels, page_number, items_per_page)
    querystring_without_sort = get_querystring_without(request, ["sort", "order"])

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": page_range,
        "search_fields": [
            {"name": "prdlst_report_no", "placeholder": "품목제조번호", "value": search_values.get("prdlst_report_no", "")},
            {"name": "prdlst_nm", "placeholder": "제품명", "value": search_values.get("prdlst_nm", "")},
            {"name": "my_label_name", "placeholder": "라벨명", "value": search_values.get("my_label_name", "")},
            {"name": "prdlst_dcnm", "placeholder": "식품유형", "value": search_values.get("prdlst_dcnm", "")},
            {"name": "bssh_nm", "placeholder": "제조사명", "value": search_values.get("bssh_nm", "")},
        ],
        "items_per_page": items_per_page,
        "sort_field": sort_field,
        "sort_order": sort_order,
        "querystring_without_sort": querystring_without_sort,
    }

    return render(request, "label/my_label_list.html", context)


@login_required
def food_item_detail(request, prdlst_report_no):
    food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
    return render(request, "label/food_item_detail.html", {"item": food_item})


FOODITEM_MYLABEL_MAPPING = {
    'prdlst_report_no': 'prdlst_report_no',
    'prdlst_nm': 'prdlst_nm',
    'prdlst_dcnm': 'prdlst_dcnm',
    'bssh_nm': 'bssh_nm',
    'rawmtrl_nm': 'rawmtrl_nm',
}


@login_required
def saveto_my_label(request, prdlst_report_no):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

    try:
        existing_label = MyLabel.objects.filter(prdlst_report_no=prdlst_report_no, user_id=request.user).first()
        data = json.loads(request.body) if request.body else {}
        confirm_flag = data.get("confirm", False)

        if existing_label and not confirm_flag:
            return JsonResponse(
                {"success": False, "confirm_required": True, "message": "이미 내 라벨에 저장된 항목입니다. 저장하시겠습니까?"}, status=200
            )

        food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
        data_mapping = {field: getattr(food_item, field, "") for field in FOODITEM_MYLABEL_MAPPING.keys()}

        if existing_label and confirm_flag:
            MyLabel.objects.create(user_id=request.user, my_label_name=f"임시 - {food_item.prdlst_nm}", **data_mapping)
            return JsonResponse({"success": True, "message": "내 표시사항으로 저장되었습니다."})

        MyLabel.objects.create(user_id=request.user, my_label_name=f"임시 - {food_item.prdlst_nm}", **data_mapping)
        return JsonResponse({"success": True, "message": "내 표시사항으로 저장되었습니다."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def label_creation(request, label_id=None):
    disable_rawmtrl = False
    if label_id:
        label = get_object_or_404(MyLabel, my_label_id=label_id)
        
        if request.method == 'POST':
            form = LabelCreationForm(request.POST, instance=label)
            if form.is_valid():
                label = form.save(commit=False)
                # 관계 테이블에 연결된 데이터가 있으면 원재료명(rawmtrl_nm)을 갱신
                if label.ingredient_relations.exists():
                    raw_materials = [
                        relation.ingredient.prdlst_nm 
                        for relation in label.ingredient_relations.all()
                        if relation.ingredient.prdlst_nm  # 실제 값이 있는 경우만
                    ]
                    if raw_materials:
                        # join 후 앞뒤 공백 제거
                        label.rawmtrl_nm = ', '.join(raw_materials).strip()
                # elif label.ingredient_ids_str:
                #     raw_materials = [name.strip() for name in label.ingredient_ids_str.split(',')]
                #     label.rawmtrl_nm = ', '.join(raw_materials)
                label.save()
                messages.success(request, '저장되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
        else:
            # GET 요청 시: 관계 데이터가 있고 실제로 원재료명이 존재하면 입력란을 disable 처리
            if label.ingredient_relations.exists():
                raw_materials = [
                    relation.ingredient.prdlst_nm 
                    for relation in label.ingredient_relations.all()
                    if relation.ingredient.prdlst_nm  # 실제 값이 있는 경우만
                ]
                if raw_materials:
                    label.rawmtrl_nm = ', '.join(raw_materials).strip()
                    disable_rawmtrl = True  # 실제 데이터가 있는 경우에만 disable 처리
            print(label.rawmtrl_nm)
            form = LabelCreationForm(instance=label)
    else:
        if request.method == 'POST':
            form = LabelCreationForm(request.POST)
            if form.is_valid():
                label = form.save(commit=False)
                label.user_id = request.user
                label.save()
                messages.success(request, '저장되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
        else:
            form = LabelCreationForm()
            label = None
        disable_rawmtrl = False

    context = {
        'form': form,
        'label': label,
        'food_types': FoodType.objects.all(),
        'country_list': CountryList.objects.all(),
        'disable_rawmtrl': disable_rawmtrl,  # 템플릿으로 전달할 플래그
    }
    return render(request, 'label/label_creation.html', context)


@login_required
@csrf_exempt
def save_to_my_ingredients(request, prdlst_report_no=None):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

    try:
        food_item = FoodItem.objects.filter(prdlst_report_no=prdlst_report_no).first()
        if not food_item:
            return JsonResponse({"success": False, "error": "해당 품목제조번호에 대한 데이터를 찾을 수 없습니다."}, status=404)

        MyIngredient.objects.create(
            user_id=request.user,
            my_ingredient_name=f"임시 - {food_item.prdlst_nm}",
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            prms_dt=food_item.prms_dt or "00000000",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            pog_daycnt=food_item.pog_daycnt or "0",
            frmlc_mtrqlt=food_item.frmlc_mtrqlt or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
            delete_YN="N"
        )
        return JsonResponse({"success": True, "message": "내원료로 저장되었습니다."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def ingredient_popup(request):
    rawmtrl_nm = request.GET.get('rawmtrl_nm', '')
    label_id = request.GET.get('label_id')
    
    ingredients_data = []
    if label_id:
        relations = LabelIngredientRelation.objects.filter(label_id=label_id).select_related('ingredient')
        saved_ingredient_names = set()
        for relation in relations:
            saved_ingredient_names.add(relation.ingredient.my_ingredient_name)
            ingredients_data.append({
                'ingredient_name': relation.ingredient.my_ingredient_name,
                'prdlst_report_no': relation.ingredient.prdlst_report_no or '',
                'ratio': float(relation.ingredient_ratio) if relation.ingredient_ratio else '',
                'food_type': relation.ingredient.prdlst_dcnm or '',
                'origin': relation.country_of_origin or '',
                'display_name': relation.ingredient.ingredient_display_name,
                'allergen': relation.allergen or '',
                'gmo': relation.gmo or '',
                'manufacturer': relation.ingredient.bssh_nm or ''
            })
        if not relations.exists() and rawmtrl_nm:
            raw_materials = [rm.strip() for rm in rawmtrl_nm.split(',') if rm.strip()]
            for material in raw_materials:
                if material not in saved_ingredient_names:
                    my_ingredient = MyIngredient.objects.filter(
                        user_id=request.user,
                        my_ingredient_name=material,
                        delete_YN='N'
                    ).first()
                    if my_ingredient:
                        ingredients_data.append({
                            'ingredient_name': my_ingredient.my_ingredient_name,
                            'prdlst_report_no': my_ingredient.prdlst_report_no or '',
                            'ratio': float(my_ingredient.ingredient_ratio) if my_ingredient.ingredient_ratio else '',
                            'food_type': my_ingredient.prdlst_dcnm or '',
                            'origin': '',
                            'display_name': my_ingredient.ingredient_display_name or my_ingredient.my_ingredient_name,
                            'allergen': '',
                            'gmo': '',
                            'manufacturer': my_ingredient.bssh_nm or ''
                        })
                    else:
                        ingredients_data.append({
                            'ingredient_name': material,
                            'prdlst_report_no': '',
                            'ratio': '',
                            'food_type': '',
                            'origin': '',
                            'display_name': material,
                            'allergen': '',
                            'gmo': '',
                            'manufacturer': ''
                        })

    context = {
        'rawmtrl_nm': rawmtrl_nm,
        'saved_ingredients': mark_safe(json.dumps(ingredients_data, ensure_ascii=False))
    }
    return render(request, 'label/ingredient_popup.html', context)


def fetch_food_item(request, prdlst_report_no):
    try:
        food_item = FoodItem.objects.get(prdlst_report_no=prdlst_report_no)
        data = {
            'success': True,
            'prdlst_nm': food_item.prdlst_nm,
            'prdlst_dcnm': food_item.prdlst_dcnm,
            'rawmtrl_nm': food_item.rawmtrl_nm,
            'bssh_nm': food_item.bssh_nm,
        }
    except FoodItem.DoesNotExist:
        data = {'success': False}
    return JsonResponse(data)


@login_required
@csrf_exempt
def check_my_ingredients(request):
    try:
        data = json.loads(request.body)
        prdlst_nm = data.get('prdlst_nm', '').strip()
        
        if not prdlst_nm:
            return JsonResponse({'success': False, 'error': '검색어가 없습니다.'})
        
        # prdlst_nm 검색하여 원재료 찾기
        found_ingredient = MyIngredient.objects.filter(
            user_id=request.user,
            prdlst_nm=prdlst_nm,
            delete_YN='N'
        ).values(
            'my_ingredient_name',
            'prdlst_nm',
            'ingredient_display_name',
            'prdlst_report_no', 
            'prdlst_dcnm', 
            'bssh_nm',
            'ingredient_ratio',
            'rawmtrl_nm'          # 원재료명(표시명)에 사용
        ).first()
        if found_ingredient:
            if found_ingredient['rawmtrl_nm'] is None:
                found_ingredient['rawmtrl_nm'] = ''
            return JsonResponse({'success': True, 'ingredient': found_ingredient})
        else:
            return JsonResponse({'success': False, 'error': '해당하는 원료를 찾을 수 없습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
        

@login_required
def my_ingredient_list(request):
    search_fields = {
        'my_ingredient_name': 'my_ingredient_name',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    search_conditions &= Q(delete_YN='N') & Q(user_id=request.user)
    sort_field, sort_order = process_sorting(request, 'my_ingredient_name')
    items_per_page = int(request.GET.get('items_per_page', 10))
    page_number = request.GET.get('page', 1)
    my_ingredients = MyIngredient.objects.filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(my_ingredients, page_number, items_per_page)
    querystring_without_page = get_querystring_without(request, ['page'])
    querydict_sort = request.GET.copy()
    querydict_sort.pop('sort', None)
    querydict_sort.pop('order', None)
    querystring_without_sort = querydict_sort.urlencode()

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range': page_range,
        'search_fields': [
            {'name': 'my_ingredient_name', 'placeholder': '내 원료명', 'value': search_values.get('my_ingredient_name', '')},
            {'name': 'prdlst_report_no', 'placeholder': '품목제조번호', 'value': search_values.get('prdlst_report_no', '')},
            {'name': 'prdlst_dcnm', 'placeholder': '식품유형', 'value': search_values.get('prdlst_dcnm', '')},
            {'name': 'bssh_nm', 'placeholder': '제조사명', 'value': search_values.get('bssh_nm', '')},
            {'name': 'ingredient_display_name', 'placeholder': '원료 표시명', 'value': search_values.get('ingredient_display_name', '')},
        ],
        'items_per_page': items_per_page,
        'sort_field': sort_field.lstrip('-'),
        'sort_order': sort_order,
        'querystring_without_page': querystring_without_page,
        'querystring_without_sort': querystring_without_sort,
    }
    return render(request, 'label/my_ingredient_list.html', context)


@login_required
def my_ingredient_detail(request, ingredient_id=None):
    if ingredient_id:
        ingredient = get_object_or_404(MyIngredient, my_ingredient_id=ingredient_id, user_id=request.user)
    else:
        ingredient = None

    if request.method == 'POST':
        # POST 처리 로직은 추후 구현
        pass

    context = {
        'ingredient': ingredient,
        'mode': 'edit' if ingredient else 'create'
    }
    return render(request, 'label/my_ingredient_detail.html', context)


@login_required
@csrf_exempt
def save_ingredients_to_label(request, label_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    try:
        data = json.loads(request.body)
        ingredients_data = data.get('ingredients', [])
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        label.ingredient_create_YN = 'Y'
        ingredient_names = []
        processed_ingredient_ids = []
        for ingredient_data in ingredients_data:
            if not ingredient_data.get('ingredient_name'):
                continue
            ingredient_name = ingredient_data['ingredient_name']
            ingredient_names.append(ingredient_name)
            my_ingredient, created = MyIngredient.objects.get_or_create(
                user_id=request.user,
                my_ingredient_name=ingredient_name,
                defaults={
                    'delete_YN': 'N',
                    'prdlst_report_no': ingredient_data.get('prdlst_report_no', ''),
                    'ingredient_display_name': ingredient_data.get('display_name', ''),
                }
            )
            processed_ingredient_ids.append(my_ingredient.my_ingredient_id)
            try:
                ratio = float(ingredient_data.get('ratio', 0))
            except (ValueError, TypeError):
                ratio = 0
            LabelIngredientRelation.objects.update_or_create(
                label_id=label.my_label_id,
                ingredient_id=my_ingredient.my_ingredient_id,
                defaults={
                    'ingredient_ratio': ratio,
                    'allergen': ingredient_data.get('allergen', ''),
                    'gmo': ingredient_data.get('gmo', ''),
                }
            )
        LabelIngredientRelation.objects.filter(label_id=label.my_label_id).exclude(ingredient_id__in=processed_ingredient_ids).delete()
        label.ingredient_ids_str = ','.join(ingredient_names)
        label.save()
        return JsonResponse({'success': True, 'message': '저장되었습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'저장 중 오류가 발생했습니다: {str(e)}'})

@login_required
def save_food_item(request, prdlst_report_no):
    try:
        food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
        SavedFoodItem.objects.get_or_create(
            user=request.user,
            food_item=food_item,
            defaults={'saved_at': now()}
        )
        return JsonResponse({'success': True, 'message': '제품이 성공적으로 저장되었습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def save_my_ingredient(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not data.get('my_ingredient_name'):
                return JsonResponse({
                    'success': False,
                    'error': '내 원료명은 필수 입력 항목입니다.'
                })
            
            # 검색용 이름 중복 체크
            
            # 현재 내 원료 정보 업데이트
            my_ingredient = MyIngredient.objects.filter(
                user_id=request.user,
                my_ingredient_id=data.get('my_ingredient_id')
            ).update(
                my_ingredient_name=data['my_ingredient_name'],
                prdlst_report_no=data.get('prdlst_report_no'),
                prdlst_dcnm=data.get('prdlst_dcnm'),
                ingredient_display_name=data.get('ingredient_display_name'),
                bssh_nm=data.get('bssh_nm')
            )
            return JsonResponse({'success': True, 'message': '내 원료가 성공적으로 저장되었습니다.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
@csrf_exempt
def search_ingredient_add_row(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        name = data.get('ingredient_name', '').strip()
        report = data.get('prdlst_report_no', '').strip()
        food_type = data.get('food_type', '').strip()
        manufacturer = data.get('manufacturer', '').strip()
        
        qs = MyIngredient.objects.filter(user_id=request.user, delete_YN='N')
        if name:
            qs = qs.filter(prdlst_nm__icontains=name)
        if report:
            qs = qs.filter(prdlst_report_no__icontains=report)
        if food_type:
            qs = qs.filter(prdlst_dcnm__icontains=food_type)
        if manufacturer:
            qs = qs.filter(bssh_nm__icontains=manufacturer)
        
        # 여러 건 리스트로 반환 (각 결과에 대해 필요한 필드만)
        ingredients = list(qs.values(
            'prdlst_nm',         # 원료명
            'prdlst_report_no',
            'prdlst_dcnm',       # 식품유형
            'bssh_nm',           # 제조사
        ))

        
        
        if ingredients:
            print(ingredients)
            return JsonResponse({'success': True,'ingredients': ingredients})
        else:
            return JsonResponse({'success': False, 'error': '검색 결과가 없습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @login_required
# @csrf_exempt
# def verify_ingredients(request):
#     if request.method != "POST":
#         return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)
#     try:
#         data = json.loads(request.body)
#         ingredient = data.get("ingredient", [])
#         print(ingredient)
#         results = []  # 각 원재료 행별 존재 여부(예: true: 이미 존재)
#         for ing in ingredient:
#             print("1")
#             prdlst_report_no = ing.get("prdlst_report_no", "").strip()
#             if prdlst_report_no:
#                 exists = MyIngredient.objects.filter(
#                     user_id=request.user,
#                     prdlst_report_no=prdlst_report_no,
#                     delete_YN="N"
#                 ).exists()
#             else:
#                 exists = MyIngredient.objects.filter(
#                     user_id=request.user,
#                     prdlst_nm=ing.get("ingredient_name", "").strip(),
#                     prdlst_dcnm=ing.get("food_type", "").strip(),
#                     ingredient_display_name=ing.get("display_name", "").strip(),
#                     delete_YN="N"
#                 ).exists()
#             results.append(exists)

            
#         return JsonResponse({"success": True, "results": results})
#     except Exception as e:
#         return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@csrf_exempt
def verify_ingredients(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)
    try:
        data = json.loads(request.body)
        # ingredient 키에 해당하는 데이터가 전달되었는지 확인
        ing_data = data.get("ingredient", {})
        # 만약 ing_data가 리스트라면, 단일 항목만 전달하는 것으로 간주하고 dict로 변환합니다.
        if isinstance(ing_data, list):
            if len(ing_data) == 1:
                ing_data = ing_data[0]
            else:
                # 여러 항목이 넘어오면 에러를 반환하거나 원하는 방식으로 처리합니다.
                return JsonResponse({"success": False, "error": "Expected a single ingredient dictionary."}, status=400)
        
        # 이제 ing_data는 dict로 보장됩니다.
        print("Received ingredient data:", ing_data)
        results = []  # 결과 값을 저장할 리스트
        
        # 단일 dict이므로 한 번만 처리합니다.
        prdlst_report_no = str(ing_data.get("prdlst_report_no", "")).strip()
        print("prdlst_report_no:", prdlst_report_no)
        
        if prdlst_report_no:
            # 품목보고번호가 있는 경우 해당 번호를 기준으로 MyIngredient 레코드를 검색합니다.
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_report_no=prdlst_report_no,
                delete_YN="N"
            )
            if qs.exists():
                # 검색된 레코드의 필요한 필드들만 values()로 가져옵니다.
                record = qs.values(
                    "my_ingredient_id",
                    "my_ingredient_name",
                    "prdlst_report_no",
                    "prdlst_nm",
                    "prdlst_dcnm",
                    "ingredient_display_name",
                    "delete_YN"
                ).first()
                results.append(record)
            else:
                results.append({})
        else:
            # 품목보고번호가 없으면 원재료명, 식품유형, 원재료(표시명)를 기준으로 검색합니다.
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_nm=ing_data.get("ingredient_name", "").strip(),
                prdlst_dcnm=ing_data.get("food_type", "").strip(),
                ingredient_display_name=ing_data.get("display_name", "").strip(),
                delete_YN="N"
            )
            if qs.exists():
                record = qs.values(
                    "my_ingredient_id",
                    "my_ingredient_name",
                    "prdlst_report_no",
                    "prdlst_nm",
                    "prdlst_dcnm",
                    "ingredient_display_name",
                    "delete_YN"
                ).first()
                results.append(record)
            else:
                results.append({})
        print("Results:", results)
        return JsonResponse({"success": True, "results": results})
    except Exception as e:
        print("Error in verify_ingredients:", str(e))
        return JsonResponse({"success": False, "error": str(e)}, status=500)