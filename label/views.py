import json
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Subquery, OuterRef
from .models import FoodItem, MyLabel, MyIngredient, CountryList, LabelIngredientRelation
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
def label_creation(request, label_id):
    label = get_object_or_404(MyLabel, my_label_id=label_id)
    label = MyLabel.objects.annotate(
        country_name_ko=Subquery(
            CountryList.objects.filter(
                country_code2=OuterRef('country_of_origin')
            ).values('country_name_ko')[:1]
        )
    ).get(my_label_id=label_id)

    
    form = LabelCreationForm(request.POST or None, instance=label)
    # FoodItem의 식품유형(prdlst_dcnm) 정보를 중복없이 가져오기
    food_types = FoodItem.objects.values_list('prdlst_dcnm', flat=True).distinct().order_by('prdlst_dcnm')
    country_list = CountryList.objects.all()
    
    if request.method == "POST" and form.is_valid():
        form.save()
        # messages.success(request, "표시사항이 성공적으로 저장되었습니다.")
        # 현재 페이지를 새로 고침 (현재 URL로 리다이렉트)
        return redirect(request.path + "?saved=1")
    
    return render(request, "label/label_creation.html", {
        "form": form,
        "label": label,
        "food_types": food_types,
        "country_list": country_list
    })


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
    if label_id:
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
                'prdlst_report_no': relation.prdlst_report_no or '',
                'ratio': float(relation.ingredient_ratio) if relation.ingredient_ratio else '',
                'food_type': relation.prdlst_dcnm or '',
                'origin': relation.country_of_origin or '',
                'display_name': relation.ingredient_display_name or relation.ingredient.my_ingredient_name,
                'allergen': relation.allergen or '',
                'gmo': relation.gmo or '',
                'manufacturer': relation.bssh_nm or ''
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
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        search_name = data.get('search_name', '').strip()
        
        if not search_name:
            return JsonResponse({'success': False, 'error': '검색어가 없습니다.'})
        
        # 사용자의 내 원료에서 search_name으로 검색
        found_ingredient = MyIngredient.objects.filter(
            user_id=request.user,
            search_name=search_name,  # search_name으로 정확히 일치하는 항목 검색
            delete_YN='N'
        ).values(
            'my_ingredient_name',
            'ingredient_display_name',
            'prdlst_report_no', 
            'prdlst_dcnm', 
            'bssh_nm',
            'ingredient_ratio',
            'search_name'
        ).first()
        
        if found_ingredient:
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
        return JsonResponse({'success': False, 'error': str(e)})


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
        
        print(f"Received data: {ingredients_data}")  # 디버깅용
        
        # 라벨 가져오기
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        print(f"Found label: {label.my_label_id}")  # 디버깅용
        
        # 기존 관계 삭제
        LabelIngredientRelation.objects.filter(label=label).delete()
        print("Deleted existing relations")  # 디버깅용
        
        # 새로운 관계 생성
        for idx, ingredient_data in enumerate(ingredients_data):
            print(f"Processing ingredient {idx + 1}: {ingredient_data}")  # 디버깅용
            
            if not ingredient_data.get('ingredient_name'):
                print(f"Skipping empty ingredient at index {idx}")
                continue
                
            # 내 원료 찾기 또는 생성
            my_ingredient, created = MyIngredient.objects.get_or_create(
                user_id=request.user,
                my_ingredient_name=ingredient_data['ingredient_name'],
                defaults={'delete_YN': 'N'}
            )
            print(f"{'Created' if created else 'Found'} ingredient: {my_ingredient.my_ingredient_id}")  # 디버깅용
            
            # 비율 처리
            try:
                ratio = float(ingredient_data.get('ratio', 0))
            except (ValueError, TypeError) as e:
                print(f"Error converting ratio: {e}")  # 디버깅용
                ratio = 0
                
            try:
                # 관계 생성
                relation = LabelIngredientRelation.objects.create(
                    label=label,
                    ingredient=my_ingredient,
                    ingredient_ratio=ratio,
                    prdlst_dcnm=ingredient_data.get('food_type', ''),
                    country_of_origin=ingredient_data.get('origin', ''),
                    ingredient_display_name=ingredient_data.get('display_name', ''),
                    allergen=ingredient_data.get('allergen', ''),
                    gmo=ingredient_data.get('gmo', ''),
                    bssh_nm=ingredient_data.get('manufacturer', '')
                )
                print(f"Created relation: {relation.id}")  # 디버깅용
            except Exception as e:
                print(f"Error creating relation: {str(e)}")  # 디버깅용
                raise
        
        return JsonResponse({
            'success': True,
            'message': '저장되었습니다.'
        })
        
    except Exception as e:
        import traceback
        print(f"Error saving ingredients: {str(e)}")
        print(traceback.format_exc())  # 상세 에러 스택 출력
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
            search_name = data.get('search_name')
            if search_name:
                existing_ingredient = MyIngredient.objects.filter(
                    search_name=search_name
                ).exclude(my_ingredient_id=data.get('my_ingredient_id')).first()
                
                if existing_ingredient:
                    return JsonResponse({
                        'success': False,
                        'error': '이미 존재하는 검색용 이름입니다. 다른 검색용 이름을 입력해주세요.'
                    })
            
            # 현재 내 원료 정보 업데이트
            my_ingredient = MyIngredient.objects.filter(
                user_id=request.user,
                my_ingredient_id=data.get('my_ingredient_id')
            ).update(
                my_ingredient_name=data['my_ingredient_name'],
                prdlst_report_no=data.get('prdlst_report_no'),
                prdlst_dcnm=data.get('prdlst_dcnm'),
                ingredient_display_name=data.get('ingredient_display_name'),
                bssh_nm=data.get('bssh_nm'),
                search_name=search_name
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