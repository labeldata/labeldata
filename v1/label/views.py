import json
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from .models import FoodItem, MyLabel, MyIngredient, CountryList, LabelIngredientRelation, FoodType, MyPhrase, AgriculturalProduct, FoodAdditive
from .forms import LabelCreationForm, MyIngredientsForm
from venv import logger  # 지우지 않음
from django.utils.safestring import mark_safe
from .constants import DEFAULT_PHRASES, FIELD_REGULATIONS, CATEGORY_CHOICES  # FIELD_REGULATIONS 및 CATEGORY_CHOICES 추가
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta  # datetime과 timedelta를 import 추가
from rapidfuzz import fuzz  # fuzzywuzzy 대신 rapidfuzz 사용
from django.utils import timezone  # 추가

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
    if request.method == 'POST':
        if label_id:
            label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
            form = LabelCreationForm(request.POST, instance=label)
        else:
            form = LabelCreationForm(request.POST)

        if form.is_valid():
            label = form.save(commit=False)
            label.user_id = request.user
            
            # 체크박스 상태 처리 수정
            for field_name in form.cleaned_data:
                if field_name.startswith('chk_'):
                    model_field = 'chckd_' + field_name[4:]  # chk_ -> chckd_
                    if hasattr(label, model_field):
                        setattr(label, model_field, 'Y' if form.cleaned_data[field_name] else 'N')
            
            label.save()
            return redirect('label:label_creation', label_id=label.my_label_id)
    
    has_ingredient_relations = False
    
    if label_id:
        # 기존 라벨 편집
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        has_ingredient_relations = label.ingredient_relations.exists()
        
        # 내 원료에 연결된 원재료명 가져오기
        if has_ingredient_relations:
            # 내 원료 관계 조회 (순서대로)
            relations = LabelIngredientRelation.objects.filter(
                label_id=label.my_label_id
            ).select_related('ingredient').order_by('relation_sequence')
            
            # 원재료명 정보를 생성 (순서대로)
            ingredients_info = []
            for relation in relations:
                ingredient = relation.ingredient
                # 원재료명 또는 원재료 표시명을 사용 (비율 제외)
                ingredient_name = ingredient.ingredient_display_name or ingredient.prdlst_nm or ""
                ingredients_info.append(ingredient_name)
            
            # 콤마로 연결하여 원재료명(참고) 필드에 설정
            label.rawmtrl_nm = ", ".join(ingredients_info)
        
        if request.method == 'POST':
            # POST 요청 처리
            form = LabelCreationForm(request.POST, instance=label)
            
            # 디버깅 로그
            print("POST 데이터:", request.POST)
            print("food_group:", request.POST.get('food_group'))
            print("food_type:", request.POST.get('food_type'))
            
            if form.is_valid():
                label = form.save(commit=False)  # commit=False를 올바르게 사용
                label.user_id = request.user
                
                # hidden 필드에서 식품유형 정보 가져오기
                label.food_group = request.POST.get('food_group')
                label.food_type = request.POST.get('food_type')
                
                # 변경 사항 저장
                label.save()
                messages.success(request, '표시사항이 성공적으로 수정되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
            else:
                print("폼 오류:", form.errors)
                messages.error(request, '입력 정보에 오류가 있습니다.')
        else:
            # GET 요청 처리
            form = LabelCreationForm(instance=label)
    else:
        # 새 라벨 생성
        if request.method == 'POST':
            # POST 요청 처리
            form = LabelCreationForm(request.POST)
            
            # 디버깅 로그
            print("POST 데이터:", request.POST)
            print("food_group:", request.POST.get('food_group'))
            print("food_type:", request.POST.get('food_type'))
            
            if form.is_valid():
                label = form.save(commit=False)  # commit=False를 올바르게 사용
                label.user_id = request.user
                
                # hidden 필드에서 식품유형 정보 가져오기
                label.food_group = request.POST.get('food_group')
                label.food_type = request.POST.get('food_type')
                
                # 변경 사항 저장
                label.save()
                messages.success(request, '새 표시사항이 성공적으로 작성되었습니다.')
                return redirect('label:label_creation', label_id=label.my_label_id)
            else:
                print("폼 오류:", form.errors)
                messages.error(request, '입력 정보에 오류가 있습니다.')
        else:
            # GET 요청 처리
            form = LabelCreationForm()
    
    # 식품유형 대분류 목록 조회
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    
    # 소분류 목록 필터링 (초기 로드 시)
    current_food_group = getattr(label, 'food_group', '') if label_id else ''
    
    if current_food_group:
        # 선택된 대분류가 있는 경우 해당 대분류에 속하는 소분류만 가져옴
        food_types = FoodType.objects.filter(food_group=current_food_group).values('food_type', 'food_group').order_by('food_type')
    else:
        # 대분류가 선택되지 않은 경우 모든 소분류 가져옴
        food_types = FoodType.objects.values('food_type', 'food_group').order_by('food_type')
        
    # 자주 사용하는 문구 불러오기
    user_phrases = MyPhrase.objects.filter(user_id=request.user, delete_YN='N').order_by('category_name', 'display_order')

    phrases_data = {}
    for phrase in user_phrases:
        category = phrase.category_name
        if category not in phrases_data:
            phrases_data[category] = []
        phrases_data[category].append({
            'id': phrase.my_phrase_id,
            'name': phrase.my_phrase_name,
            'content': phrase.comment_content,
            'note': phrase.note or '',
            'order': phrase.display_order
        })

    phrases_json = json.dumps(phrases_data, ensure_ascii=False)

    context = {
        'form': form,
        'label': label if label_id else None,
        'food_types': food_types,
        'food_groups': food_groups,
        'country_list': CountryList.objects.all(),
        'has_ingredient_relations': has_ingredient_relations,
        'phrases_json': phrases_json,  
        'regulations_json': json.dumps(FIELD_REGULATIONS, ensure_ascii=False)  # 추가
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
    rawmtrl_nm_display = request.GET.get('rawmtrl_nm_display', '')
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
        if not relations.exists() and rawmtrl_nm_display:
            raw_materials = [rm.strip() for rm in rawmtrl_nm_display.split(',') if rm.strip()]
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
    # 국가 목록 데이터 추가
    country_list = list(CountryList.objects.values('country_name_ko').order_by('country_name_ko'))
    country_names = [country['country_name_ko'] for country in country_list]
    
    context = {
        'saved_ingredients': ingredients_data,
        'has_relations': has_relations,
        'country_names': country_names,  # 국가 목록 추가
        'food_types': list(FoodType.objects.all().values('food_type')),
        'agricultural_products': list(AgriculturalProduct.objects.all().values('name_kr')),
        'food_additives': list(FoodAdditive.objects.all().values('name_kr'))
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
        
        if prdlst_report_no:
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_report_no=prdlst_report_no,
                delete_YN='N'
            )
            existing_ingredients = list(qs.values(
                'my_ingredient_id',
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
            candidates = list(qs.values(
                'my_ingredient_id',
                'prdlst_nm',
                'prdlst_report_no',
                'prdlst_dcnm',
                'bssh_nm',
                'ingredient_display_name'
            ))
            threshold = 70
            filtered = []
            for ingredient in candidates:
                candidate_name = ingredient.get('ingredient_display_name', '')
                score = fuzz.ratio(candidate_name.lower(), display_name.lower())
                if score >= threshold:
                    ingredient['similarity'] = score
                    filtered.append(ingredient)
            existing_ingredients = sorted(filtered, key=lambda x: x['similarity'], reverse=True)

        exists = len(existing_ingredients) > 0
        return JsonResponse({'exists': exists, 'ingredients': existing_ingredients})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def my_ingredient_list(request):
    search_fields = {
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
    search_fields = {
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
    return render(request, 'label/my_ingredient_list_combined.html', context)

@login_required
def my_ingredient_detail(request, ingredient_id=None):
    # POST일 때 my_ingredient_id 우선 활용
    my_ingredient_id = request.POST.get('my_ingredient_id') or ingredient_id
    if my_ingredient_id:
        ingredient = get_object_or_404(MyIngredient, my_ingredient_id=my_ingredient_id, user_id=request.user)
        mode = 'edit'
    else:
        ingredient = MyIngredient(user_id=request.user, delete_YN='N')
        mode = 'create'

    if request.method == 'POST':
        form = MyIngredientsForm(request.POST, instance=ingredient)
        if form.is_valid():
            new_ingredient = form.save(commit=False)
            new_ingredient.user_id = request.user
            new_ingredient.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': '내 원료가 성공적으로 저장되었습니다.',
                    'ingredient_id': new_ingredient.my_ingredient_id
                })
            messages.success(request, '저장되었습니다.')
            return redirect('label:my_ingredient_detail', ingredient_id=new_ingredient.my_ingredient_id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                errors = {field: str(error) for field, error in form.errors.items()}
                return JsonResponse({'success': False, 'errors': errors})
    else:
        form = MyIngredientsForm(instance=ingredient)

    context = {
        'ingredient': ingredient,
        'form': form,
        'mode': mode,
        'food_types': list(FoodType.objects.all().values('food_type')),
        'agricultural_products': list(AgriculturalProduct.objects.all().values('name_kr')),
        'food_additives': list(FoodAdditive.objects.all().values('name_kr')),
    }

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

        # 기존 연결 관계를 모두 삭제
        LabelIngredientRelation.objects.filter(label_id=label.my_label_id).delete()

        # 새로운 원재료 정보 저장
        for sequence, ingredient_data in enumerate(ingredients_data, start=1):
            # 원재료 ID가 있는 경우 기존 원재료 사용
            my_ingredient_id = ingredient_data.get('my_ingredient_id')
            
            # 원재료 ID가 없거나 빈 문자열인 경우 새 원재료 생성
            if not my_ingredient_id:
                # 새 원재료 생성
                ingredient = MyIngredient.objects.create(
                    user_id=request.user,
                    prdlst_nm=ingredient_data.get('ingredient_name', ''),
                    prdlst_report_no=ingredient_data.get('prdlst_report_no', ''),
                    prdlst_dcnm=ingredient_data.get('food_type', ''),
                    ingredient_display_name=ingredient_data.get('display_name', ''),
                    bssh_nm=ingredient_data.get('manufacturer', ''),
                    allergens=ingredient_data.get('allergen', ''),
                    gmo=ingredient_data.get('gmo', ''),
                    delete_YN='N'
                )
            else:
                # 기존 원재료 사용
                try:
                    ingredient = MyIngredient.objects.get(my_ingredient_id=my_ingredient_id)
                except MyIngredient.DoesNotExist:
                    # 원재료가 존재하지 않는 경우 새로 생성
                    ingredient = MyIngredient.objects.create(
                        user_id=request.user,
                        prdlst_nm=ingredient_data.get('ingredient_name', ''),
                        prdlst_report_no=ingredient_data.get('prdlst_report_no', ''),
                        prdlst_dcnm=ingredient_data.get('food_type', ''),
                        ingredient_display_name=ingredient_data.get('display_name', ''),
                        bssh_nm=ingredient_data.get('manufacturer', ''),
                        allergens=ingredient_data.get('allergen', ''),
                        gmo=ingredient_data.get('gmo', ''),
                        delete_YN='N'
                    )
            
            # 원재료와 라벨 사이의 관계 생성
            relation = LabelIngredientRelation(
                label=label,
                ingredient=ingredient,
                relation_sequence=sequence
            )
            
            # 비율 설정
            try:
                ratio_value = ingredient_data.get('ratio', '')
                if ratio_value and ratio_value.strip():
                    relation.ingredient_ratio = Decimal(ratio_value)
            except (ValueError, InvalidOperation):
                # 숫자가 아닌 값이 들어온 경우 비율 설정 안함
                pass
                
            # 관계 저장
            relation.save()
        
        # 원재료명 업데이트 (참고사항에 "원산지 표시대상" 포함된 항목만)
        origin_targets = []
        for ingredient_data in ingredients_data:
            notes = ingredient_data.get('notes', '')
            if notes and '원산지 표시대상' in notes:
                display_name = ingredient_data.get('display_name') or ingredient_data.get('ingredient_name')
                if display_name:
                    origin_targets.append(display_name)
        
        # 원산지 표시대상 원재료명을 라벨에 저장
        if origin_targets:
            label.country_of_origin = ', '.join(origin_targets)
            
        label.save()
        return JsonResponse({'success': True, 'message': '저장되었습니다.'})
    except Exception as e:
        import traceback
        print(traceback.format_exc())  # 서버 로그에 상세 오류 출력
        return JsonResponse({'success': False, 'error': f'저장 중 오류가 발생했습니다: {str(e)}'})

@login_required
@csrf_exempt
def delete_my_ingredient(request, ingredient_id):
    if request.method == 'POST':
        try:
            ingredient = get_object_or_404(MyIngredient, my_ingredient_id=ingredient_id, user_id=request.user)
            LabelIngredientRelation.objects.filter(ingredient_id=ingredient.my_ingredient_id).delete()
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
        
        ingredients = list(qs.values(
            'prdlst_nm',
            'prdlst_report_no',
            'prdlst_dcnm',
            'bssh_nm',
            'ingredient_display_name',
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
        ing_data = data.get("ingredient", {})
        if isinstance(ing_data, list):
            if len(ing_data) == 1:
                ing_data = ing_data[0]
            else:
                return JsonResponse({"success": False, "error": "Expected a single ingredient dictionary."}, status=400)
        
        results = []
        
        prdlst_report_no = str(ing_data.get("prdlst_report_no", "")).strip()
        
        if prdlst_report_no:
            qs = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_report_no=prdlst_report_no,
                delete_YN="N"
            )
            if qs.exists():
                record = qs.values(
                    "my_ingredient_id",
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
    total_formatted = f"{total:,}"
    return JsonResponse({'total': total_formatted, 'new': new_count})

@login_required
def my_labels_count(request):
    total = MyLabel.objects.filter(user_id=request.user).count()
    one_week_ago = datetime.now() - timedelta(days=7)
    new_count = MyLabel.objects.filter(user_id=request.user, update_datetime__gte=one_week_ago).count()
    total_formatted = f"{total:,}"
    return JsonResponse({'total': total_formatted, 'new': new_count})

@login_required
def my_ingredients_count(request):
    total = MyIngredient.objects.filter(user_id=request.user, delete_YN='N').count()
    one_week_ago = datetime.now() - timedelta(days=7)
    new_count = MyIngredient.objects.filter(user_id=request.user, delete_YN='N', update_datetime__gte=one_week_ago).count()
    total_formatted = f"{total:,}"
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
            bssh_nm=data.get('manufacturer', ''),
            delete_YN='N'
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


@login_required
def nutrition_calculator_popup(request):
    label_id = request.GET.get('label_id')
    
    nutrition_data = {
        'serving_size': '',
        'serving_size_unit': 'g',
        'units_per_package': '1',
        'display_unit': 'unit',
        'nutrients': {}
    }
    
    if label_id:
        try:
            label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
            
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
    original.pk = None  
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
                new_label.pk = None  
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
        
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        
        label.serving_size = data.get('serving_size', '')
        label.serving_size_unit = data.get('serving_size_unit', '')
        label.units_per_package = data.get('units_per_package', '')
        label.nutrition_display_unit = data.get('nutrition_display_unit', '')
        
        label.nutrition_text = data.get('nutritions', '')
        
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
        
        label.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def food_types_by_group(request):
    group = request.GET.get('group', '')
    
    if group:
        # 대분류가 있으면 해당 대분류의 소분류만 반환
        food_types = FoodType.objects.filter(food_group=group).values('food_type', 'food_group').order_by('food_type')
    else:
        # 대분류가 없으면 모든 소분류 반환
        food_types = FoodType.objects.values('food_type', 'food_group').order_by('food_type')
    
    return JsonResponse({
        'success': True,
        'food_types': list(food_types)
    })

@login_required
def get_food_group(request):
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

@login_required
def food_type_settings(request):
    food_type = request.GET.get('food_type', '')
    
    if not food_type:
        return JsonResponse({
            'success': False,
            'error': '식품유형이 제공되지 않았습니다.'
        })
    
    try:
        ft = FoodType.objects.filter(food_type=food_type).first()
        
        if not ft:
            return JsonResponse({
                'success': False,
                'error': '해당 식품유형을 찾을 수 없습니다.'
            })
        
        settings = {}
        
        checkbox_fields = [
            'prdlst_dcnm', 'rawmtrl_nm', 'nutritions', 'cautions', 'frmlc_mtrqlt',
            'pog_daycnt', 'storage_method', 'weight_calorie', 'country_of_origin',
            'additional_info', 'prdlst_report_no'
        ]
        
        for field in checkbox_fields:
            if hasattr(ft, field):
                value = getattr(ft, field, 'N') or 'N'
                settings[field] = value
        
        pog_daycnt_value = ft.pog_daycnt
        
        if pog_daycnt_value:
            if ',' in pog_daycnt_value:
                options = [option.strip() for option in pog_daycnt_value.split(',') if option.strip()]
                if options:
                    settings['pog_daycnt_options'] = options
                    settings['pog_daycnt'] = 'Y'  # 옵션이 있으면 활성화
                else:
                    settings['pog_daycnt'] = 'N'  # 옵션이 없으면 비활성화
            else:
                settings['pog_daycnt'] = pog_daycnt_value  # 직접 값 사용
                settings['pog_daycnt_options'] = [pog_daycnt_value] if pog_daycnt_value != 'D' else []
        else:
            settings['pog_daycnt'] = 'N'  # 값이 없으면 비활성화
        
        # 관련 규정 정보 추가
        if hasattr(ft, 'relevant_regulations'):
            settings['relevant_regulations'] = ft.relevant_regulations or ""
        
        return JsonResponse({
            'success': True,
            'settings': settings
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@csrf_exempt
def manage_phrases(request):
    """문구 추가/수정/삭제 처리"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            # 신규 문구 생성
            new_phrase = MyPhrase.objects.create(
                user_id=request.user,
                my_phrase_name=data.get('my_phrase_name'),
                category_name=data.get('category_name'),
                comment_content=data.get('comment_content'),
                note=data.get('note', ''),
                delete_YN='N'
            )
            return JsonResponse({
                'success': True,
                'message': '문구가 저장되었습니다.',
                'id': new_phrase.my_phrase_id
            })

        elif action == 'update':
            # 기존 문구 수정 로직
            changes = data if isinstance(data, list) else [data]
            for change in changes:
                phrase = MyPhrase.objects.get(
                    my_phrase_id=change['id'],
                    user_id=request.user
                )
                phrase.my_phrase_name = change.get('name', phrase.my_phrase_name)
                phrase.comment_content = change.get('content', phrase.comment_content)
                phrase.note = change.get('note', phrase.note)
                phrase.save()
            return JsonResponse({'success': True})

        elif action == 'delete':
            # 문구 삭제 로직
            phrase = MyPhrase.objects.get(
                my_phrase_id=data['id'],
                user_id=request.user
            )
            phrase.delete_YN = 'Y'
            phrase.delete_datetime = timezone.now().strftime('%Y%m%d')
            phrase.save()
            return JsonResponse({'success': True})

        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})

    except MyPhrase.DoesNotExist:
        logger.error("Phrase not found")
        return JsonResponse({'success': False, 'error': '문구를 찾을 수 없습니다.'})
    except json.JSONDecodeError:
        logger.error("Invalid JSON data")
        return JsonResponse({'success': False, 'error': '잘못된 데이터 형식입니다.'})
    except Exception as e:
        logger.error(f"manage_phrases error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
@csrf_exempt
def reorder_phrases(request):
    """문구 순서 변경 처리"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        updates = data.get('updates', [])
        logger.info(f"Reordering phrases: {updates}")
        
        for update in updates:
            phrase = MyPhrase.objects.get(
                my_phrase_id=update['id'],
                user_id=request.user
            )
            phrase.display_order = update['order']
            phrase.save()
            
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"reorder_phrases error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@never_cache
def phrase_popup(request):
    """자주 사용하는 문구 팝업"""
    phrases_data = {}
    
    # 사용자 문구만 가져오기
    user_phrases = MyPhrase.objects.filter(
        user_id=request.user, 
        delete_YN='N'
    ).order_by('category_name', 'display_order')
    
    # CATEGORY_CHOICES에서 정의된 모든 카테고리에 대한 빈 리스트 초기화
    categories = CATEGORY_CHOICES
    for category_code, _ in categories:
        phrases_data[category_code] = []
    
    # 사용자 문구 추가
    for phrase in user_phrases:
        category = phrase.category_name
        phrases_data[category].append({
            'id': phrase.my_phrase_id,
            'name': phrase.my_phrase_name,
            'content': phrase.comment_content,
            'note': phrase.note or '',
            'order': phrase.display_order,
            'is_custom': True
        })

    context = {
        'phrases_json': json.dumps(phrases_data),
        'categories': categories  # CATEGORY_CHOICES 전체 전달
    }
    
    return render(request, 'label/phrase_popup.html', context)

@login_required
def phrase_suggestions(request):
    """추천 문구 제공"""
    try:
        category = request.GET.get('category')
        if not category:
            return JsonResponse({'success': False, 'error': '카테고리가 제공되지 않았습니다.'})
        suggestions = DEFAULT_PHRASES.get(category, [])
        return JsonResponse({'success': True, 'suggestions': suggestions})
    except Exception as e:
        logger.error(f"phrase_suggestions error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def preview_popup(request):
    """표시사항 미리보기 팝업"""
    label_id = request.GET.get('label_id')
    
    if not label_id:
        return JsonResponse({'success': False, 'error': '라벨 ID가 제공되지 않았습니다.'})
    
    try:
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        
        # 미리보기 항목 구성
        preview_items = []
        field_mappings = [
            ('my_label_name', '라벨명'),
            ('prdlst_dcnm', '식품유형'),
            ('prdlst_nm', '제품명'),
            ('ingredient_info', '성분명 및 함량'),
            ('content_weight', '내용량'),
            ('weight_calorie', '내용량(열량)'),
            ('prdlst_report_no', '품목보고번호'),
            ('country_of_origin', '원산지'),
            ('storage_method', '보관방법'),
            ('frmlc_mtrqlt', '포장재질'),
            ('bssh_nm', '제조원 소재지'),
            ('distributor_address', '유통전문판매원'),
            ('repacker_address', '소분원'),
            ('importer_address', '수입원'),
            ('pog_daycnt', '소비기한'),
            ('rawmtrl_nm_display', '원재료명'),
            ('cautions', '주의사항'),
            ('additional_info', '기타표시사항')
        ]

        for field, label_text in field_mappings:
            value = getattr(label, field)
            if value:
                preview_items.append({
                    'id': len(preview_items) + 1,
                    'label': label_text,
                    'value': value
                })

        # 영양성분 정보 구성
        nutrition_items = []
        if label.nutrition_text:
            nutrition_fields = [
                ('calories', '열량', 'kcal'),
                ('natriums', '나트륨', 'mg'),
                ('carbohydrates', '탄수화물', 'g'),
                ('sugars', '당류', 'g'),
                ('fats', '지방', 'g'),
                ('trans_fats', '트랜스지방', 'g'),
                ('saturated_fats', '포화지방', 'g'),
                ('cholesterols', '콜레스테롤', 'mg'),
                ('proteins', '단백질', 'g')
            ]
            
            for field, label_text, unit in nutrition_fields:
                value = getattr(label, field)
                if value:
                    unit_value = getattr(label, f'{field}_unit', unit)
                    nutrition_items.append({
                        'label': label_text,
                        'value': f'{value}{unit_value}',
                        'dv': ''  # 영양성분 기준치 대비 비율 (필요한 경우 계산)
                    })

        # 알레르기 유발물질과 원산지 표시대상 목록
        allergens = []  # 알레르기 유발물질 목록
        origins = []    # 원산지 표시대상 목록
        
        # 연결된 원재료에서 알레르기 유발물질과 원산지 표시대상 추출
        ingredient_relations = label.ingredient_relations.select_related('ingredient')
        for relation in ingredient_relations:
            if relation.ingredient.allergens:
                allergens.extend(relation.ingredient.allergens.split(','))
            # 원산지 표시대상 로직 추가 (필요한 경우)

        context = {
            'preview_items': preview_items,
            'nutrition_items': nutrition_items,
            'allergens': list(set(allergens)),  # 중복 제거
            'origins': list(set(origins))       # 중복 제거
        }
        
        return render(request, 'label/label_preview.html', context)
        
    except MyLabel.DoesNotExist:
        return JsonResponse({'success': False, 'error': '라벨을 찾을 수 없습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@csrf_exempt
def bulk_copy_labels(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '잘못된 요청 방식입니다.'}, status=405)
    
    try:
        data = json.loads(request.body)
        label_ids = data.get('label_ids', [])
        if not label_ids:
            return JsonResponse({'success': False, 'error': '선택된 라벨이 없습니다.'}, status=400)

        copied_labels = []
        for label_id in label_ids:
            original_label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
            
            # 라벨 복사
            new_label = MyLabel.objects.create(
                user_id=request.user,
                my_label_name=f"{original_label.my_label_name} (복사본)",
                food_group=original_label.food_group,
                food_type=original_label.food_type,
                preservation_type=original_label.preservation_type,
                processing_method=original_label.processing_method,
                processing_condition=original_label.processing_condition,
                prdlst_dcnm=original_label.prdlst_dcnm,
                prdlst_nm=original_label.prdlst_nm,
                prdlst_report_no=original_label.prdlst_report_no,
                rawmtrl_nm=original_label.rawmtrl_nm,
                rawmtrl_nm_display=original_label.rawmtrl_nm_display,
                content_weight=original_label.content_weight,
                storage_method=original_label.storage_method,
                country_of_origin=original_label.country_of_origin,
                frmlc_mtrqlt=original_label.frmlc_mtrqlt,
                bssh_nm=original_label.bssh_nm,
                distributor_address=original_label.distributor_address,
                repacker_address=original_label.repacker_address,
                importer_address=original_label.importer_address,
                cautions=original_label.cautions,
                additional_info=original_label.additional_info,
                label_create_YN='Y',
                ingredient_create_YN=original_label.ingredient_create_YN,
                delete_YN='N'
            )
            copied_labels.append(new_label.my_label_id)

        return JsonResponse({
            'success': True, 
            'message': f'{len(copied_labels)}개의 라벨이 복사되었습니다.',
            'copied_labels': copied_labels
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def bulk_delete_labels(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '잘못된 요청 방식입니다.'}, status=405)
    
    try:
        data = json.loads(request.body)
        label_ids = data.get('label_ids', [])
        if not label_ids:
            return JsonResponse({'success': False, 'error': '선택된 라벨이 없습니다.'}, status=400)

        # 실제 삭제가 아닌 flag 처리
        current_time = now().strftime('%Y%m%d')
        deleted_count = MyLabel.objects.filter(
            my_label_id__in=label_ids,
            user_id=request.user
        ).update(
            delete_YN='Y',
            delete_datetime=current_time
        )

        return JsonResponse({
            'success': True, 
            'message': f'{deleted_count}개의 라벨이 삭제되었습니다.',
            'deleted_count': deleted_count
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)