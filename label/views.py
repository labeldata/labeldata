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
from .forms import LabelCreationForm, MyIngredientsForm
from venv import logger  #지우지 말 것
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from rapidfuzz import fuzz  # rapidfuzz 라이브러리 import

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
def save_to_my_label(request, prdlst_report_no):
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
    has_ingredient_relations = False
    form = None  # form 변수를 함수 시작 부분에서 초기화
    
    if label_id:
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        
        # 관계 테이블 존재 여부 확인
        has_ingredient_relations = label.ingredient_relations.exists()
        
        if request.method == 'POST':
            form = LabelCreationForm(request.POST, instance=label)
            if form.is_valid():
                label = form.save(commit=False)
                
                # 원재료명(참고) 필드 업데이트 - 관계 테이블에서 원재료 가져오기
                if has_ingredient_relations:
                    raw_materials = []
                    for relation in label.ingredient_relations.all().order_by('relation_sequence'):
                        if relation.ingredient.ingredient_display_name:
                            # 비율 부분을 제거하고 원재료명만 추가
                            raw_materials.append(relation.ingredient.ingredient_display_name)
                    
                    # 콤마로 구분된 원재료명 참고 문자열 생성
                    if raw_materials:
                        label.rawmtrl_nm = ", ".join(raw_materials)
                
                # 식품유형 값 설정
                label.food_group = request.POST.get('food_group', '')
                label.food_type = request.POST.get('food_type', '')
                
                # 장기보존식품 설정 (radio로 동작하는 체크박스)
                label.preservation_type = request.POST.get('preservation_type', '')
                
                # 제조방법 설정 (radio로 동작하는 체크박스)
                label.processing_method = request.POST.get('processing_method', '')
                
                # 조건 상세 설정
                label.processing_condition = request.POST.get('processing_condition', '')
                
                label.save()
                messages.success(request, '저장되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
        else:
            # GET 요청 시: 관계 데이터가 있으면 원재료명(참고) 필드를 자동으로 채움
            if has_ingredient_relations:
                raw_materials = []
                for relation in label.ingredient_relations.all().order_by('relation_sequence'):
                    if relation.ingredient.ingredient_display_name:
                        # 비율 부분을 제거하고 원재료명만 추가
                        raw_materials.append(relation.ingredient.ingredient_display_name)
                
                # 원재료명(참고) 필드 값 설정
                if raw_materials:
                    label.rawmtrl_nm = ", ".join(raw_materials)
                    # 이미 저장된 라벨이므로 변경사항 바로 저장
                    label.save(update_fields=['rawmtrl_nm'])

            form = LabelCreationForm(instance=label)
    else:
        if request.method == 'POST':
            form = LabelCreationForm(request.POST)
            if form.is_valid():
                label = form.save(commit=False)
                label.user_id = request.user
                
                # 식품유형 값 설정
                label.food_group = request.POST.get('food_group', '')
                label.food_type = request.POST.get('food_type', '')
                
                # 장기보존식품 설정
                label.preservation_type = request.POST.get('preservation_type', '')
                
                # 제조방법 설정
                label.processing_method = request.POST.get('processing_method', '')
                
                # 조건 상세 설정
                label.processing_condition = request.POST.get('processing_condition', '')
                
                label.save()
                messages.success(request, '저장되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
        else:
            form = LabelCreationForm()
            label = None

    # 식품유형 대분류 목록 조회
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    
    # 식품유형 소분류 목록 조회 (대분류 정보 포함)
    food_types = FoodType.objects.values('food_type', 'food_group').order_by('food_type')
    
    context = {
        'form': form,  # 이제 form은 항상 할당되어 있음
        'label': label if 'label' in locals() else None,  # label 변수가 있는지 확인
        'food_types': food_types,  # 대분류 정보 포함
        'food_groups': food_groups,
        'country_list': CountryList.objects.all(),
        'has_ingredient_relations': has_ingredient_relations,
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
            #my_ingredient_name=f"임시 - {food_item.prdlst_nm}",
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
    has_relations = False
    if label_id:
        relations = LabelIngredientRelation.objects.filter(label_id=label_id).select_related('ingredient')
        #saved_ingredient_names = set()
        for relation in relations:
            #saved_ingredient_names.add(relation.ingredient.my_ingredient_name)
            ingredients_data.append({
                'my_ingredient_id': relation.ingredient.my_ingredient_id,
                'ingredient_name': relation.ingredient.prdlst_nm,
                'prdlst_report_no': relation.ingredient.prdlst_report_no or '',
                'ratio': float(relation.ingredient_ratio) if relation.ingredient_ratio else '',
                'food_type': relation.ingredient.prdlst_dcnm or '',
                #'origin': relation.country_of_origin or '',
                'display_name': relation.ingredient.ingredient_display_name,
                'allergen': relation.ingredient.allergens or '',
                'gmo': relation.ingredient.gmo or '',
                'manufacturer': relation.ingredient.bssh_nm or ''
            })
        if relations.exists():
            has_relations = True  # 관계 데이터가 있는 경우 플래그 설정
        if not relations.exists() and rawmtrl_nm:
            raw_materials = [rm.strip() for rm in rawmtrl_nm.split(',') if rm.strip()]
            for material in raw_materials:
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
        #'saved_ingredients': mark_safe(json.dumps(ingredients_data, ensure_ascii=False))
        'saved_ingredients': ingredients_data,
        'has_relations': has_relations  # 플래그를 템플릿으로 전달
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
def check_my_ingredient(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    try:
        data = json.loads(request.body)
        prdlst_report_no = data.get('prdlst_report_no', '').strip()
        food_type = data.get('food_type', '').strip()
        display_name = data.get('display_name', '').strip()
        
        # 우선 DB에서 기본 필터링 적용: 품목보고번호가 있다면 기초 필터를 그대로, 없으면 검색 범위를 넓게 가져옵니다.
        if prdlst_report_no:
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_report_no=prdlst_report_no,
                delete_YN='N'
            )
            # 필요한 필드만 선택하여 리스트로 변환
            existing_ingredients = list(qs.values(
                'my_ingredient_id',  # 추가된 부분: my_ingredient_id 필드 포함
                'prdlst_nm',
                'prdlst_report_no',
                'prdlst_dcnm',
                'bssh_nm',
                'ingredient_display_name'
            ))
        else:
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_dcnm=food_type,
                delete_YN='N'
            )
            # 후보 데이터를 모두 가져옵니다.
            candidates = list(qs.values(
                'my_ingredient_id',  # 추가된 부분: my_ingredient_id 필드 포함
                'prdlst_nm',
                'prdlst_report_no',
                'prdlst_dcnm',
                'bssh_nm',
                'ingredient_display_name'
            ))
            # rapidfuzz를 사용한 유사도 계산
            threshold = 70  # 유사도 임계값 (0-100 사이의 점수, 상황에 따라 조절)
            filtered = []
            for ingredient in candidates:
                candidate_name = ingredient.get('ingredient_display_name', '')
                # 예시로 fuzz.ratio 사용 (간단한 비교)
                score = fuzz.ratio(candidate_name.lower(), display_name.lower())
                if score >= threshold:
                    ingredient['similarity'] = score
                    filtered.append(ingredient)
            # 유사도 점수가 높은 순으로 정렬
            existing_ingredients = sorted(filtered, key=lambda x: x['similarity'], reverse=True)

        exists = len(existing_ingredients) > 0
        return JsonResponse({'exists': exists, 'ingredients': existing_ingredients})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def my_ingredient_list(request):
    search_fields = {
        #'my_ingredient_name': 'my_ingredient_name',
        'prdlst_nm': 'prdlst_nm',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    search_conditions &= Q(delete_YN='N') & Q(user_id=request.user)
    sort_field, sort_order = process_sorting(request, 'prdlst_nm')
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
            {'name': 'prdlst_nm', 'placeholder': '원재료명', 'value': search_values.get('prdlst_nm', '')},
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
def my_ingredient_list_combined(request):
    # 검색 필드 정의 (검색 시 활용할 파라미터)
    search_fields = {
        'prdlst_nm': 'prdlst_nm',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
    }
    # GET 파라미터로부터 검색 조건 추출
    search_conditions, search_values = get_search_conditions(request, search_fields)
    # 삭제되지 않은 현재 사용자의 원료만 조회
    search_conditions &= Q(delete_YN='N') & Q(user_id=request.user)
    
    # 정렬 설정
    sort_field, sort_order = process_sorting(request, 'prdlst_nm')
    # 페이징 처리 관련 변수 설정
    items_per_page = int(request.GET.get('items_per_page', 10))
    page_number = request.GET.get('page', 1)
    
    # 쿼리셋 생성
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
        # 템플릿에서 검색 필터 폼을 그리기 위한 항목 리스트
        'search_fields': [
            {'name': 'prdlst_nm', 'placeholder': '원재료명', 'value': search_values.get('prdlst_nm', '')},
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
    return render(request, 'label/my_ingredient_list_combined.html', context)

@login_required
def my_ingredient_detail(request, ingredient_id=None):
    if ingredient_id:
        # 기존 원료 수정
        ingredient = get_object_or_404(MyIngredient, my_ingredient_id=ingredient_id, user_id=request.user)
        mode = 'edit'
    else:
        # 새 원료 생성
        ingredient = MyIngredient(user_id=request.user, delete_YN='N')  # 기본값으로 객체 생성
        mode = 'create'

    if request.method == 'POST':
        # JSON 요청 처리
        if request.headers.get('content-type') == 'application/json':
            try:
                data = json.loads(request.body)
                my_ingredient_id = data.get('my_ingredient_id')
                
                if my_ingredient_id:
                    # 기존 원료 수정
                    ingredient = get_object_or_404(MyIngredient, my_ingredient_id=my_ingredient_id, user_id=request.user)
                    
                # 원료 데이터 업데이트
                ingredient.prdlst_nm = data.get('prdlst_nm', '')
                ingredient.prdlst_report_no = data.get('prdlst_report_no', '')
                ingredient.prdlst_dcnm = data.get('prdlst_dcnm', '')
                ingredient.bssh_nm = data.get('bssh_nm', '')
                ingredient.ingredient_display_name = data.get('ingredient_display_name', '')
                ingredient.allergens = data.get('allergens', '')
                ingredient.gmo = data.get('gmo', '')
                ingredient.user_id = request.user
                ingredient.delete_YN = 'N'
                
                ingredient.save()
                return JsonResponse({
                    'success': True, 
                    'message': '내 원료가 성공적으로 저장되었습니다.',
                    'ingredient_id': ingredient.my_ingredient_id
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        # 일반 폼 제출 처리
        form = MyIngredientsForm(request.POST, instance=ingredient)
        if form.is_valid():
            new_ingredient = form.save(commit=False)
            new_ingredient.user_id = request.user
            new_ingredient.save()
            
            # AJAX 요청인 경우 JSON 응답
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': '내 원료가 성공적으로 저장되었습니다.',
                    'ingredient_id': new_ingredient.my_ingredient_id
                })
            
            # 일반 요청인 경우 리다이렉트
            messages.success(request, '저장되었습니다.')
            return redirect('label:my_ingredient_detail', ingredient_id=new_ingredient.my_ingredient_id)
        else:
            # 폼이 유효하지 않은 경우
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                errors = {field: str(error) for field, error in form.errors.items()}
                return JsonResponse({'success': False, 'errors': errors})
    else:
        form = MyIngredientsForm(instance=ingredient)

    context = {
        'ingredient': ingredient,
        'form': form,
        'mode': mode
    }
    
    # AJAX 요청인지 확인
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'label/my_ingredient_detail_partial.html', context)
    else:
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

        # 기존 관계 삭제
        LabelIngredientRelation.objects.filter(label_id=label.my_label_id).delete()

        # ingredients_data 순서를 기준으로 순번(relation_sequence) 저장
        for sequence, ingredient_data in enumerate(ingredients_data, start=1):
            try:
                ratio = float(ingredient_data.get('ratio', 0))
            except (ValueError, TypeError):
                ratio = 0

            LabelIngredientRelation.objects.update_or_create(
                label_id=label.my_label_id,
                ingredient_id=ingredient_data['my_ingredient_id'],
                defaults={
                    'ingredient_ratio': ratio,
                    'relation_sequence': sequence  # 순번 저장
                }
            )
        label.save()
        return JsonResponse({'success': True, 'message': '저장되었습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'저장 중 오류가 발생했습니다: {str(e)}'})
    

@login_required
@csrf_exempt
def delete_my_ingredient(request, ingredient_id):
    if request.method == 'POST':
        try:
            ingredient = get_object_or_404(MyIngredient, my_ingredient_id=ingredient_id, user_id=request.user)
            # 관계 테이블의 데이터 삭제
            LabelIngredientRelation.objects.filter(ingredient_id=ingredient.my_ingredient_id).delete()
            # 원료 삭제 (delete_YN을 'Y'로 설정)
            ingredient.delete_YN = 'Y'
            ingredient.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

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
            'ingredient_display_name',  # 원료 표시명
            'my_ingredient_id'
        ))

        if ingredients:
            return JsonResponse({'success': True, 'ingredients': ingredients})
        else:
            return JsonResponse({'success': False, 'error': '검색 결과가 없습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
        results = []  # 결과 값을 저장할 리스트
        
        # 단일 dict이므로 한 번만 처리합니다.
        prdlst_report_no = str(ing_data.get("prdlst_report_no", "")).strip()
        
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
                    #"my_ingredient_name",
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
                    #"my_ingredient_name",
                    "prdlst_report_no",
                    "prdlst_nm",
                    "prdlst_dcnm",
                    "ingredient_display_name",
                    "delete_YN"
                ).first()
                results.append(record)
            else:
                results.append({})
        return JsonResponse({"success": True, "results": results})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
def food_items_count(request):
    total = FoodItem.objects.count()
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    new_count = FoodItem.objects.filter(last_updt_dtm__gte=one_week_ago).count()
    total_formatted = f"{total:,}"  # 예: 1,234
    return JsonResponse({'total': total_formatted, 'new': new_count})

@login_required
def my_labels_count(request):
    # 사용자의 MyLabel 총 건수
    total = MyLabel.objects.filter(user_id=request.user).count()
    # 최근 1주일 이내 갱신된 MyLabel 건수 (update_datetime은 DateTimeField)
    one_week_ago = datetime.now() - timedelta(days=7)
    new_count = MyLabel.objects.filter(user_id=request.user, update_datetime__gte=one_week_ago).count()
    total_formatted = f"{total:,}"  # 3자리마다 쉼표 추가
    return JsonResponse({'total': total_formatted, 'new': new_count})



@login_required
@csrf_exempt
def register_my_ingredient(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        MyIngredient.objects.create(
            user_id=request.user,
            prdlst_nm=data.get('ingredient_name', ''),
            prdlst_report_no=data.get('prdlst_report_no', ''),
            prdlst_dcnm=data.get('food_type', ''),
            ingredient_display_name=data.get('display_name', ''),
            #allergen=data.get('allergen', ''),
            #gmo=data.get('gmo', ''),
            bssh_nm=data.get('manufacturer', ''),
            delete_YN='N'
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


@login_required
def nutrition_calculator_popup(request):
    """영양성분 계산기 팝업 뷰"""
    label_id = request.GET.get('label_id')
    
    # 기본 빈 데이터 초기화
    nutrition_data = {
        'serving_size': '',
        'serving_size_unit': 'g',
        'units_per_package': '1',
        'display_unit': 'unit',
        'nutrients': {}
    }
    
    # 라벨 ID가 있으면 영양성분 데이터 가져오기
    if label_id:
        try:
            label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
            
            # 영양성분 데이터 준비
            nutrition_data = {
                'serving_size': label.serving_size,
                'serving_size_unit': label.serving_size_unit or 'g',
                'units_per_package': label.units_per_package or '1',
                'display_unit': label.nutrition_display_unit or 'unit',
                'nutrients': {
                    'calorie': {
                        'value': label.calories,
                        'unit': label.calories_unit or 'kcal'
                    },
                    'natrium': {
                        'value': label.natriums,
                        'unit': label.natriums_unit or 'mg'
                    },
                    'carbohydrate': {
                        'value': label.carbohydrates,
                        'unit': label.carbohydrates_unit or 'g'
                    },
                    'sugar': {
                        'value': label.sugars,
                        'unit': label.sugars_unit or 'g'
                    },
                    'afat': {
                        'value': label.fats,
                        'unit': label.fats_unit or 'g'
                    },
                    'transfat': {
                        'value': label.trans_fats,
                        'unit': label.trans_fats_unit or 'g'
                    },
                    'satufat': {
                        'value': label.saturated_fats,
                        'unit': label.saturated_fats_unit or 'g'
                    },
                    'cholesterol': {
                        'value': label.cholesterols,
                        'unit': label.cholesterols_unit or 'mg'
                    },
                    'protein': {
                        'value': label.proteins,
                        'unit': label.proteins_unit or 'g'
                    }
                }
            }
        except Exception as e:
            print(f"영양성분 데이터 로딩 중 오류: {str(e)}")
    
    # None 값을 빈 문자열로 변환 (JSON 직렬화 오류 방지)
    for key, value in nutrition_data.items():
        if value is None:
            nutrition_data[key] = ''
    
    for nutrient_name, nutrient_data in nutrition_data.get('nutrients', {}).items():
        for key, value in nutrient_data.items():
            if value is None:
                nutrient_data[key] = ''
    
    context = {
        'nutrition_data': json.dumps(nutrition_data)
    }
    return render(request, 'label/nutrition_calculator_popup.html', context)

def duplicate_label(request, label_id):
    original = get_object_or_404(MyLabel, my_label_id=label_id)  
    original.pk = None  # 
    original.my_label_name += " (복사본)"
    original.save()
    return redirect('label:label_creation', label_id=original.my_label_id)

def delete_label(request, label_id):
    label = get_object_or_404(MyLabel, my_label_id=label_id)
    label.delete()
    return redirect('label:my_label_list')

@login_required
@csrf_exempt
def bulk_copy_labels(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ids = data.get("label_ids", [])
            for label_id in ids:
                original = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
                new_label = MyLabel.objects.get(pk=original.pk)
                new_label.pk = None  # 새로운 PK 생성
                new_label.my_label_name += " (복사본)"
                new_label.save()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request method"})

@login_required
@csrf_exempt
def bulk_delete_labels(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ids = data.get("label_ids", [])
            MyLabel.objects.filter(my_label_id__in=ids, user_id=request.user).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request method"})
    

@login_required
@csrf_exempt
def save_nutrition(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        label_id = data.get('label_id')
        
        # 라벨 ID로 해당 라벨 조회
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        
        # 영양성분 관련 필드 업데이트
        label.serving_size = data.get('serving_size', '')
        label.serving_size_unit = data.get('serving_size_unit', '')
        label.units_per_package = data.get('units_per_package', '')
        label.nutrition_display_unit = data.get('nutrition_display_unit', '')
        
        # 영양성분 텍스트 필드에 nutritions 값 설정 (중요!)
        label.nutrition_text = data.get('nutritions', '')
        
        # 각 영양소 값 업데이트
        label.calories = data.get('calories', '')
        label.calories_unit = data.get('calories_unit', '')
        label.natriums = data.get('natriums', '')
        label.natriums_unit = data.get('natriums_unit', '')
        label.carbohydrates = data.get('carbohydrates', '')
        label.carbohydrates_unit = data.get('carbohydrates_unit', '')
        label.sugars = data.get('sugars', '')
        label.sugars_unit = data.get('sugars_unit', '')
        label.fats = data.get('fats', '')
        label.fats_unit = data.get('fats_unit', '')
        label.trans_fats = data.get('trans_fats', '')
        label.trans_fats_unit = data.get('trans_fats_unit', '')
        label.saturated_fats = data.get('saturated_fats', '')
        label.saturated_fats_unit = data.get('saturated_fats_unit', '')
        label.cholesterols = data.get('cholesterols', '')
        label.cholesterols_unit = data.get('cholesterols_unit', '')
        label.proteins = data.get('proteins', '')
        label.proteins_unit = data.get('proteins_unit', '')
        
        # 변경사항 저장
        label.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def food_types_by_group(request):
    """대분류에 해당하는 소분류 목록을 반환"""
    group = request.GET.get('group', '')
    
    if group:
        food_types = FoodType.objects.filter(food_group=group).values('food_type', 'food_group').order_by('food_type')
    else:
        food_types = FoodType.objects.values('food_type', 'food_group').order_by('food_type')
    
    return JsonResponse({
        'success': True,
        'food_types': list(food_types)
    })

@login_required
def get_food_group(request):
    """소분류에 해당하는 대분류를 반환"""
    food_type = request.GET.get('food_type', '')
    
    if food_type:
        try:
            food_group = FoodType.objects.filter(food_type=food_type).values_list('food_group', flat=True).first()
            return JsonResponse({
                'success': True,
                'food_group': food_group or ''
            })
        except FoodType.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '해당하는 식품유형을 찾을 수 없습니다.'
            })
    else:
        return JsonResponse({
            'success': False,
            'error': '식품유형이 제공되지 않았습니다.'
        })

