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



# 공통 함수: 검색 조건 생성
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


@login_required
def food_item_list(request):
    # 검색 조건 필드 매핑
    search_fields = {
        "prdlst_nm": "prdlst_nm",
        "bssh_nm": "bssh_nm",
        "prdlst_dcnm": "prdlst_dcnm",
        "pog_daycnt": "pog_daycnt",
        "prdlst_report_no": "prdlst_report_no",
    }
    # 검색 조건 및 값 추출
    search_conditions, search_values = get_search_conditions(request, search_fields)

    # 정렬 및 페이징
    sort_field = request.GET.get("sort", "prdlst_nm")
    sort_order = request.GET.get("order", "asc")
    items_per_page = int(request.GET.get("items_per_page", 10))
    page_number = request.GET.get("page", 1)

    if sort_order == "desc":
        sort_field = f"-{sort_field}"

    # 데이터 필터링
    food_items = FoodItem.objects.filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(food_items, page_number, items_per_page)

    # GET 파라미터에서 'page' 제거한 쿼리 문자열 (pagination 용)
    querydict_page = request.GET.copy()
    querydict_page.pop("page", None)
    querystring_without_page = querydict_page.urlencode()

    # GET 파라미터에서 'sort'와 'order' 제거한 쿼리 문자열 (정렬 링크 용)
    querydict_sort = request.GET.copy()
    querydict_sort.pop("sort", None)
    querydict_sort.pop("order", None)
    querystring_without_sort = querydict_sort.urlencode()

    # 컨텍스트 생성
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
    # 검색 조건 필드 매핑
    search_fields = {
        "my_label_name": "my_label_name",
        "prdlst_report_no": "prdlst_report_no",
        "prdlst_nm": "prdlst_nm",
        "prdlst_dcnm": "prdlst_dcnm",
        "bssh_nm": "bssh_nm",
    }
    # 검색 조건 및 값 추출
    search_conditions, search_values = get_search_conditions(request, search_fields)

    # 정렬 및 페이징
    sort_field = request.GET.get("sort", "my_label_name")
    sort_order = request.GET.get("order", "asc")
    items_per_page = int(request.GET.get("items_per_page", 10))
    page_number = request.GET.get("page", 1)

    if sort_order == "desc":
        sort_field = f"-{sort_field}"

    # 데이터 필터링
    labels = MyLabel.objects.filter(user_id=request.user).filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(labels, page_number, items_per_page)

    # GET 파라미터에서 'sort'와 'order' 제거한 쿼리 문자열 (정렬 링크용)
    querydict_sort = request.GET.copy()
    querydict_sort.pop("sort", None)
    querydict_sort.pop("order", None)
    querystring_without_sort = querydict_sort.urlencode()

    # 컨텍스트 생성
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


# FoodItem의 필드와 MyLabel의 필드명이 동일하다면 단순 매핑도 가능하고,
# 만약 다르다면 아래와 같이 FoodItem의 필드명을 key, MyLabel의 필드명을 value로 지정합니다.
FOODITEM_MYLABEL_MAPPING = {
    'prdlst_report_no': 'prdlst_report_no',
    'prdlst_nm': 'prdlst_nm',
    'prdlst_dcnm': 'prdlst_dcnm',
    'bssh_nm': 'bssh_nm',
    'rawmtrl_nm': 'rawmtrl_nm',
    # 추가 필드가 필요하면 여기에 넣으세요.
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

        # user_id 추가 및 my_ingredient_name 설정
        MyIngredient.objects.create(
            user_id=request.user,  # 현재 로그인한 사용자 추가
            my_ingredient_name=f"임시 - {food_item.prdlst_nm}",  # 기본 이름 설정
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            prms_dt=food_item.prms_dt or "00000000",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            pog_daycnt=food_item.pog_daycnt or "0",
            frmlc_mtrqlt=food_item.frmlc_mtrqlt or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
            delete_YN="N"  # 삭제 여부 기본값 설정
        )

        return JsonResponse({"success": True, "message": "내원료로 저장되었습니다."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def ingredient_popup(request):
    rawmtrl_nm = request.GET.get('rawmtrl_nm', '')
    label_id = request.GET.get('label_id')
    
    ingredients_data = []
    if (label_id):
        # 1. LabelIngredientRelation에서 저장된 데이터 가져오기
        relations = LabelIngredientRelation.objects.filter(
            label_id=label_id
        ).select_related('ingredient')
        
        saved_ingredient_names = set()  # 이미 처리된 원재료명 추적
        
        # 저장된 관계 데이터 처리
        for relation in relations:
            saved_ingredient_names.add(relation.ingredient.my_ingredient_name)
            ingredients_data.append({
                'ingredient_name': relation.ingredient.my_ingredient_name,
                'prdlst_report_no': relation.ingredient.prdlst_report_no or '',  # MyIngredient의 값 사용
                'ratio': float(relation.ingredient_ratio) if relation.ingredient_ratio else '',
                'food_type': relation.ingredient.prdlst_dcnm or '',  # MyIngredient의 값 사용
                'origin': relation.country_of_origin or '',
                'display_name': relation.ingredient.ingredient_display_name,  # MyIngredient의 값 사용
                'allergen': relation.allergen or '',
                'gmo': relation.gmo or '',
                'manufacturer': relation.ingredient.bssh_nm or ''
            })
        
        # 2. 관계 테이블에 없는 원재료는 MyLabel의 rawmtrl_nm에서 가져오기
        if not relations.exists() and rawmtrl_nm:
            raw_materials = [rm.strip() for rm in rawmtrl_nm.split(',') if rm.strip()]
            for material in raw_materials:
                if material not in saved_ingredient_names:
                    # MyIngredient에서 해당 원재료명과 일치하는 데이터 찾기
                    my_ingredient = MyIngredient.objects.filter(
                        user_id=request.user,
                        my_ingredient_name=material,
                        delete_YN='N'
                    ).first()

                    if my_ingredient:
                        # MyIngredient에 있는 경우 해당 데이터 사용
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
                        # MyIngredient에 없는 경우 기본 데이터만 표시
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
            'prdlst_nm',          # 원재료명 입력에 사용
            'ingredient_display_name',
            'prdlst_report_no', 
            'prdlst_dcnm', 
            'bssh_nm',
            'ingredient_ratio',
            'rawmtrl_nm'          # 원재료명(표시명)에 사용
        ).first()
        
        if found_ingredient:
            # rawmtrl_nm이 없는 경우 None 대신 빈 문자열 반환
            if found_ingredient['rawmtrl_nm'] is None:
                found_ingredient['rawmtrl_nm'] = ''
                
            return JsonResponse({
                'success': True,
                'ingredient': found_ingredient
            })
        else:
            return JsonResponse({
                'success': False,
                'error': '해당하는 원료를 찾을 수 없습니다.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })


@login_required
def my_ingredient_list(request):
    # 검색 조건 필드 매핑
    search_fields = {
        'my_ingredient_name': 'my_ingredient_name',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
    }
    # 검색 조건 및 값 추출
    search_conditions, search_values = get_search_conditions(request, search_fields)

    # 기본 검색 조건에 삭제되지 않은 항목만 표시하도록 추가
    search_conditions &= Q(delete_YN='N')
    # 현재 로그인한 사용자의 데이터만 표시
    search_conditions &= Q(user_id=request.user)

    # 정렬 및 페이징
    sort_field = request.GET.get('sort', 'my_ingredient_name')
    sort_order = request.GET.get('order', 'asc')
    items_per_page = int(request.GET.get('items_per_page', 10))
    page_number = request.GET.get('page', 1)

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    # 데이터 필터링
    my_ingredients = MyIngredient.objects.filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(my_ingredients, page_number, items_per_page)

    # GET 파라미터 처리
    querydict_page = request.GET.copy()
    querydict_page.pop('page', None)
    querystring_without_page = querydict_page.urlencode()

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
        
        # 라벨 가져오기
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        
        # ingredient_create_YN을 'Y'로 업데이트
        label.ingredient_create_YN = 'Y'
        
        # 원재료명 목록과 ingredient_names 추적
        ingredient_names = []  # ingredient_ids_str용
        processed_ingredient_ids = []  # 처리된 ingredient ID 목록
        
        for ingredient_data in ingredients_data:
            if not ingredient_data.get('ingredient_name'):
                continue
            
            ingredient_name = ingredient_data['ingredient_name']
            ingredient_names.append(ingredient_name)  # ingredient_ids_str용
                
            # 내 원료 찾기 또는 생성
            my_ingredient, created = MyIngredient.objects.get_or_create(
                user_id=request.user,
                my_ingredient_name=ingredient_name,
                defaults={
                    'delete_YN': 'N',
                    'prdlst_report_no': ingredient_data.get('prdlst_report_no', ''),
                    'ingredient_display_name': ingredient_data.get('display_name', ''),
                }
            )
            
            # 현재 처리된 ingredient ID 추가
            processed_ingredient_ids.append(my_ingredient.my_ingredient_id)
            
            # 비율 값 안전하게 처리
            try:
                ratio = float(ingredient_data.get('ratio', 0))
            except (ValueError, TypeError):
                ratio = 0
            
            # 관계 데이터 생성 또는 업데이트
            LabelIngredientRelation.objects.update_or_create(
                label_id=label.my_label_id,
                ingredient_id=my_ingredient.my_ingredient_id,
                defaults={
                    'ingredient_ratio': ratio,
                    'allergen': ingredient_data.get('allergen', ''),
                    'gmo': ingredient_data.get('gmo', ''),
                }
            )
        
        # 삭제된 행에 해당하는 관계 삭제
        LabelIngredientRelation.objects.filter(
            label_id=label.my_label_id
        ).exclude(
            ingredient_id__in=processed_ingredient_ids
        ).delete()
        
        # MyLabel의 rawmtrl_nm과 ingredient_ids_str 필드 업데이트
        label.ingredient_ids_str = ','.join(ingredient_names)  # 원재료명으로 저장
        label.save()
        
        return JsonResponse({
            'success': True,
            'message': '저장되었습니다.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'저장 중 오류가 발생했습니다: {str(e)}'
        })


@login_required
def save_food_item(request, prdlst_report_no):
    try:
        # 기존 FoodItem 조회
        food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
        
        # 사용자의 저장된 제품 목록에 추가
        SavedFoodItem.objects.get_or_create(
            user=request.user,
            food_item=food_item,
            defaults={
                'saved_at': now()
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': '제품이 성공적으로 저장되었습니다.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def save_my_ingredient(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 필수 필드 검증
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
            
            return JsonResponse({
                'success': True,
                'message': '내 원료가 성공적으로 저장되었습니다.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
            
    return JsonResponse({
        'success': False,
        'error': '잘못된 요청입니다.'
    })


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