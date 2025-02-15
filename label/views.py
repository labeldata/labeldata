import json
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Subquery, OuterRef
from .models import FoodItem, MyLabel, MyIngredient, CountryList
from .forms import LabelCreationForm
from venv import logger  #지우지 말 것



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

        MyIngredient.objects.create(
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            prms_dt=food_item.prms_dt or "00000000",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            pog_daycnt=food_item.pog_daycnt or "0",
            frmlc_mtrqlt=food_item.frmlc_mtrqlt or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
        )

        return JsonResponse({"success": True, "message": "내원료로 저장되었습니다."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def ingredient_popup(request):
    rawmtrl_nm = request.GET.get('rawmtrl_nm', '')
    return render(request, 'label/ingredient_popup.html', {'rawmtrl_nm': rawmtrl_nm})


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