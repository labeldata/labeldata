import json
import re  # 정규식 처리를 위해 추가
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
from django.conf import settings  # Django settings import 추가
from .models import FoodItem, MyLabel, MyIngredient, CountryList, LabelIngredientRelation, FoodType, MyPhrase, AgriculturalProduct, FoodAdditive, ImportedFood, ExpiryRecommendation
from .forms import LabelCreationForm, MyIngredientsForm
from venv import logger  # 지우지 않음
from django.utils.safestring import mark_safe
from .constants import DEFAULT_PHRASES, FIELD_REGULATIONS, CATEGORY_CHOICES
from django.core.cache import cache
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta  # datetime과 timedelta를 import 추가
from rapidfuzz import fuzz  # fuzzywuzzy 대신 rapidfuzz 사용
from django.utils import timezone  # 추가
import openpyxl
from openpyxl.utils import get_column_letter

# ------------------------------------------
# 헬퍼 함수들 (반복되는 코드 최적화)
# ------------------------------------------

def get_expiry_recommendations():
    """
    ExpiryRecommendation 데이터를 캐시와 함께 가져오는 헬퍼 함수
    캐시 타임아웃: 1시간
    """
    cache_key = 'expiry_recommendations_dict'
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # DB에서 데이터를 가져와서 딕셔너리 형태로 변환
    recommendations = {}
    for item in ExpiryRecommendation.objects.all():
        recommendations[item.food_type] = {
            'shelf_life': item.shelf_life,
            'unit': item.unit
        }
    
    # 1시간 동안 캐시
    cache.set(cache_key, recommendations, 3600)
    return recommendations
def get_search_conditions(request, search_fields):
    """
    Request에서 검색 조건을 추출하고 Q 객체를 생성합니다.
    """
    search_conditions = Q()
    search_values = {}
    for field, query_param in search_fields.items():
        value = request.GET.get(query_param, "").strip()
        if value:
            # 원료 표시명, 알레르기, GMO 검색에서 쉼표/플러스 구분 검색 지원
            if field in ["ingredient_display_name", "allergens", "gmo"]:
                # 플러스(+)로 구분하여 AND 검색
                if '+' in value:
                    # 플러스로 구분된 경우 AND 검색 (모든 조건이 만족되어야 함)
                    search_terms = [term.strip() for term in value.split('+') if term.strip()]
                    if search_terms:
                        # 각 검색어에 대해 AND 조건으로 LIKE 검색
                        field_conditions = Q()
                        for term in search_terms:
                            field_conditions &= Q(**{f"{field}__icontains": term})
                        search_conditions &= field_conditions
                # 쉼표로 구분하여 OR 검색
                elif ',' in value:
                    # 여러 검색어가 있는 경우 OR 검색
                    search_terms = [term.strip() for term in value.split(',') if term.strip()]
                    if search_terms:
                        # 각 검색어에 대해 OR 조건으로 LIKE 검색
                        field_conditions = Q()
                        for term in search_terms:
                            field_conditions |= Q(**{f"{field}__icontains": term})
                        search_conditions &= field_conditions
                else:
                    # 단일 검색어인 경우 기존 LIKE 검색
                    search_conditions &= Q(**{f"{field}__icontains": value})
            else:
                # 다른 필드는 기존 방식 유지 (원재료명 포함)
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

def to_bool(val):
    """imported_mode 값을 명확히 True/False로 변환"""
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "on", "yes", "y")
    return False

# ------------------------------------------
# View 함수들
# ------------------------------------------

@login_required
def food_item_list(request):
    # 국내제품/수입제품 구분
    food_category = request.GET.get("food_category", "domestic")
    # 검색 필드
    search_fields = {
        "prdlst_nm": "prdlst_nm",
        "bssh_nm": "bssh_nm",
        "prdlst_dcnm": "prdlst_dcnm",
        "pog_daycnt": "pog_daycnt",
        "prdlst_report_no": "prdlst_report_no",
        "frmlc_mtrqlt": "frmlc_mtrqlt",
        "rawmtrl_nm": "rawmtrl_nm",
    }
    imported_search_fields = {
        "prduct_korean_nm": "prdlst_nm",
        "itm_nm": "prdlst_dcnm",
        "xport_ntncd_nm": "xport_ntncd_nm",
        "bsn_ofc_name": "bsn_ofc_name",
        "ovsmnfst_nm": "bssh_nm",
        "expirde_dtm": "pog_daycnt",
        "rawmtrl_nm": "rawmtrl_nm",
    }
    # 정렬조건 변경
    if food_category == "imported":
        # 수입제품: 단일 컬럼 정렬만 허용 (기본: -expirde_dtm)
        sort_field, sort_order = process_sorting(request, "-expirde_dtm")
        items_per_page = int(request.GET.get("items_per_page", 10))
        page_number = request.GET.get("page", 1)
        imported_mode = True
        imported_conditions = Q()
        imported_search_values = {}
        has_search_params = False # 검색 파라미터 유무 플래그 추가
        for model_field, query_param in imported_search_fields.items():
            value = request.GET.get(query_param, "").strip()
            if value:
                imported_conditions &= Q(**{f"{model_field}__icontains": value})
                imported_search_values[query_param] = value
                has_search_params = True # 검색 파라미터가 하나라도 있으면 True
        
        if has_search_params:
            # 단일 컬럼 정렬 적용
            imported_items_qs = ImportedFood.objects.filter(imported_conditions).order_by(sort_field)
        else:
            imported_items_qs = ImportedFood.objects.none() # 검색 조건 없으면 빈 쿼리셋

        total_count = imported_items_qs.count()
        paginator, page_obj, page_range = paginate_queryset(imported_items_qs, page_number, items_per_page)
        search_values = imported_search_values
    else:
        # 국내제품: 단일 컬럼 정렬만 허용 (기본: -prms_dt)
        sort_field, sort_order = process_sorting(request, "-prms_dt")
        items_per_page = int(request.GET.get("items_per_page", 10))
        page_number = request.GET.get("page", 1)
        search_conditions, search_values = get_search_conditions(request, search_fields)
        has_search_params = any(search_values.values()) # 검색 파라미터 유무 확인

        if has_search_params:
            # 단일 컬럼 정렬 적용
            food_items_qs = FoodItem.objects.filter(search_conditions).order_by(sort_field)
        else:
            food_items_qs = FoodItem.objects.none() # 검색 조건 없으면 빈 쿼리셋
            
        total_count = food_items_qs.count()
        paginator, page_obj, page_range = paginate_queryset(food_items_qs, page_number, items_per_page)
        # imported_mode 변수를 domestic 케이스에서도 정의
        imported_mode = False 

    querystring_without_page = get_querystring_without(request, ["page"])
    querystring_without_sort = get_querystring_without(request, ["sort", "order"])

    # 검색 조건이 있는지 확인 (위에서 이미 계산된 has_search_params 사용)
    # search_result_count는 total_count를 사용하되, 검색 조건이 있었을 때만 의미가 있음
    search_result_count = total_count if has_search_params else None

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": page_range,
        "search_values": search_values,
        "food_category": food_category,
        "items_per_page": items_per_page,
        "sort_field": sort_field.lstrip('-') if isinstance(sort_field, str) else sort_field, # 정렬 필드에서 '-' 제거
        "sort_order": sort_order,
        "querystring_without_page": querystring_without_page,
        "querystring_without_sort": querystring_without_sort,
        "imported_mode": imported_mode, # food_category 값에 따라 설정된 imported_mode 사용
        "imported_items": page_obj if imported_mode else [], # imported_mode가 True일 때만 imported_items 전달
        "search_result_count": search_result_count,
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
        "storage_method": "storage_method",
        "frmlc_mtrqlt": "frmlc_mtrqlt",
        "pog_daycnt": "pog_daycnt",  # 소비기한 검색 추가
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    # 표시사항 관리: 작성일 내림차순, 라벨명 오름차순(가나다순)
    sort_field, sort_order = process_sorting(request, "-update_datetime")
    # ↓ 추가: report_no_verify_yn → report_no_verify_YN로 변환
    if sort_field.lstrip('-') == 'report_no_verify_yn':
        sort_field = sort_field.replace('report_no_verify_yn', 'report_no_verify_YN')
    items_per_page = int(request.GET.get("items_per_page", 10))
    page_number = request.GET.get("page", 1)

    ingredient_id = request.GET.get("ingredient_id")
    ingredient_name = None

    # 품보 신고 상태 필터 추가
    prdlst_report_status = request.GET.get("prdlst_report_status", "").strip()
    if prdlst_report_status == "completed":
        search_conditions &= Q(report_no_verify_YN="Y")
    elif prdlst_report_status == "pending":
        search_conditions &= Q(report_no_verify_YN="N")

    if ingredient_id:
        linked_label_ids = LabelIngredientRelation.objects.filter(ingredient_id=ingredient_id).values_list("label_id", flat=True)
        labels = MyLabel.objects.filter(user_id=request.user, my_label_id__in=linked_label_ids).filter(search_conditions).order_by(sort_field)
        try:
            ingredient_obj = MyIngredient.objects.get(my_ingredient_id=ingredient_id)
            ingredient_name = ingredient_obj.prdlst_nm or ingredient_obj.ingredient_display_name or ingredient_id
        except MyIngredient.DoesNotExist:
            ingredient_name = ingredient_id
    else:
        labels = MyLabel.objects.filter(user_id=request.user).filter(search_conditions).order_by(sort_field)

    total_count = labels.count()
    paginator, page_obj, page_range = paginate_queryset(labels, page_number, items_per_page)
    querystring_without_sort = get_querystring_without(request, ["sort", "order"])

    # 항상 총 건수 표시 (검색 조건 유무와 관계없이)
    search_result_count = total_count

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
            {"name": "storage_method", "placeholder": "보관조건", "value": search_values.get("storage_method", "")},
            {"name": "frmlc_mtrqlt", "placeholder": "포장재질", "value": search_values.get("frmlc_mtrqlt", "")},
            {"name": "pog_daycnt", "placeholder": "소비기한", "value": search_values.get("pog_daycnt", "")},
        ],
        "items_per_page": items_per_page,
        "sort_field": sort_field,
        "sort_order": sort_order,
        "querystring_without_sort": querystring_without_sort,
        "ingredient_id": ingredient_id,
        "ingredient_name": ingredient_name,
        "search_result_count": search_result_count,  # 검색 결과 건수 추가
        "prdlst_report_status": prdlst_report_status,  # 품보 신고 상태 추가
    }

    return render(request, "label/my_label_list.html", context)

@login_required
def food_item_detail(request, prdlst_report_no):
    """
    제품 상세 팝업: 가공식품/식품첨가물/수입식품 모두 지원.
    - 수입식품: ImportedFood에서 제품명(한글) 또는 pk로 조회
    - 일반식품: FoodItem에서 품목보고번호로 조회
    """
    # 수입식품: ImportedFood의 prduct_korean_nm 또는 pk(일반적으로 id)로 조회
    imported_item = None
    imported_mode = False

    # 우선 ImportedFood에서 prdlst_report_no와 일치하는 prduct_korean_nm이 있는지 확인
    try:
        imported_item = ImportedFood.objects.get(prduct_korean_nm=prdlst_report_no)
        imported_mode = True
    except ImportedFood.DoesNotExist:
        try:
            imported_item = ImportedFood.objects.get(pk=prdlst_report_no)
            imported_mode = True
        except (ImportedFood.DoesNotExist, ValueError):
            imported_item = None
            imported_mode = False

    if imported_mode and imported_item:
        context = {
            "item": imported_item,
            "imported_mode": True,
        }
        return render(request, "label/food_item_detail.html", context)

    # 일반식품
    food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
    context = {
        "item": food_item,
        "imported_mode": False,
        # "actions": ... # 필요시 추가
    }
    return render(request, "label/food_item_detail.html", context)


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
        imported_item = None
        food_item = None

        data = json.loads(request.body) if request.body else {}
        imported_mode = to_bool(data.get("imported_mode", False))
        confirm_flag = data.get("confirm", False)

        if imported_mode:
            imported_item = ImportedFood.objects.filter(pk=prdlst_report_no).first()
            if not imported_item:
                return JsonResponse({"success": False, "error": "해당 수입식품 ID에 대한 데이터를 찾을 수 없습니다."}, status=404)
        else:
            food_item = FoodItem.objects.filter(prdlst_report_no=prdlst_report_no).first()
            if not food_item:
                return JsonResponse({"success": False, "error": "해당 품목제조번호에 대한 데이터를 찾을 수 없습니다."}, status=404)

        if imported_mode and imported_item:
            # 수입식품 라벨 중복 체크(제품명+수입업체명+사용자)
            existing_label = MyLabel.objects.filter(prdlst_nm=imported_item.prduct_korean_nm, bssh_nm=imported_item.bsn_ofc_name, user_id=request.user).first()
            if existing_label and not confirm_flag:
                return JsonResponse({
                    "success": False,
                    "confirm_required": True,
                    "message": "이미 내 라벨에 저장된 수입식품입니다. 저장하시겠습니까?"
                }, status=200)
            # 저장
            MyLabel.objects.create(
                user_id=request.user,
                my_label_name=f"임시 - {imported_item.prduct_korean_nm}",
                prdlst_nm=imported_item.prduct_korean_nm or "미정",
                prdlst_dcnm=imported_item.itm_nm or "미정",
                bssh_nm=imported_item.bsn_ofc_name or "미정",
                pog_daycnt=imported_item.expirde_dtm or imported_item.expirde_end_dtm or "",
                rawmtrl_nm=imported_item.irdnt_nm or "미정",
                importer_address=imported_item.bsn_ofc_name or "",
                country_of_origin=imported_item.xport_ntncd_nm or imported_item.mnf_ntncn_nm or "",
                # 기타 필드는 필요시 추가
            )
            return JsonResponse({"success": True, "message": "내 표시사항으로 저장되었습니다."})

        # 일반식품 로직
        existing_label = MyLabel.objects.filter(prdlst_report_no=prdlst_report_no, user_id=request.user).first()
        if existing_label and not confirm_flag:
            return JsonResponse(
                {"success": False, "confirm_required": True, "message": "이미 내 라벨에 저장된 항목입니다. 저장하시겠습니까?"}, status=200
            )
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

        # 라벨명을 POST 데이터에서 직접 추출하여 폼에 설정
        my_label_name = request.POST.get('my_label_name', '').strip()
        if my_label_name:
            # POST 데이터를 복사하여 수정
            post_data = request.POST.copy()
            post_data['my_label_name'] = my_label_name
            
            # 폼을 새로 생성하여 라벨명이 포함되도록 함
            if label_id:
                form = LabelCreationForm(post_data, instance=label)
            else:
                form = LabelCreationForm(post_data)

        if form.is_valid():
            label = form.save(commit=False)
            label.user_id = request.user
            
            # 라벨명 다시 한번 확인하여 설정
            if my_label_name:
                label.my_label_name = my_label_name
            
            # hidden 필드에서 식품유형 정보 가져오기
            label.food_group = request.POST.get('food_group')
            label.food_type = request.POST.get('food_type')
            
            # 체크박스 상태 처리
            checkbox_fields = [field for field in request.POST.keys() if field.startswith('chk_')]
            for field_name in checkbox_fields:
                model_field = 'chckd_' + field_name[4:]  # chk_ -> chckd_
                if hasattr(label, model_field):
                    setattr(label, model_field, 'Y')
            
            # 체크되지 않은 체크박스는 N으로 설정
            all_checkbox_fields = [
                'chckd_prdlst_dcnm', 'chckd_prdlst_nm', 'chckd_ingredient_info',
                'chckd_content_weight', 'chckd_weight_calorie', 'chckd_prdlst_report_no',
                'chckd_country_of_origin', 'chckd_storage_method', 'chckd_frmlc_mtrqlt',
                'chckd_bssh_nm', 'chckd_distributor_address', 'chckd_repacker_address',
                'chckd_importer_address', 'chckd_pog_daycnt', 'chckd_rawmtrl_nm_display',
                'chckd_cautions', 'chckd_additional_info', 'chckd_nutrition_text'
            ]
            
            for field_name in all_checkbox_fields:
                if hasattr(label, field_name):
                    corresponding_checkbox = 'chk_' + field_name[6:]  # chckd_ -> chk_
                    if corresponding_checkbox not in checkbox_fields:
                        setattr(label, field_name, 'N')

            # 품목보고번호 변경 시 검증여부 N으로 초기화
            if label_id:
                orig_label = MyLabel.objects.get(my_label_id=label_id)
                if orig_label.prdlst_report_no != label.prdlst_report_no:
                    label.report_no_verify_YN = 'N'
            else:
                # 신규 생성 시에도 무조건 N
                label.report_no_verify_YN = 'N'

            label.save()
            # 모든 메시지 제거
            return redirect('label:label_creation', label_id=label.my_label_id)
        else:
            messages.error(request, '입력 정보에 오류가 있습니다.')
    else:
        has_ingredient_relations = False
        
        if label_id:
            # 기존 라벨 편집
            label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
            has_ingredient_relations = label.ingredient_relations.exists()
            # 연결된 원료 개수 구하기
            count_ingredient_relations = LabelIngredientRelation.objects.filter(label_id=label.my_label_id).count()

            # 내 원료에 연결된 원재료명 가져오기
            if has_ingredient_relations:
                relations = LabelIngredientRelation.objects.filter(
                    label_id=label.my_label_id
                ).select_related('ingredient').order_by('relation_sequence')
                
                # 원재료명 정보를 생성 (순서대로)
                ingredients_info = []
                allergens_set = set()
                gmo_set = set()
                shellfish_collected = set()
                shellfish_pattern = re.compile(r'^조개류\(([^)]+)\)$')  # 조개류 패턴 정규식

                # 향료/동일 용도 카운터
                flavor_counter = {}
                purpose_counter = {}

                for relation in relations:
                    ingredient = relation.ingredient
                    food_category = getattr(ingredient, 'food_category', None) or getattr(ingredient, 'food_group', None) or ''
                    display_name = ingredient.ingredient_display_name or ingredient.prdlst_nm or ""
                    # display_name이 콤마로 여러 개일 때 최대 5개까지만 표시 (팝업과 동일)
                    if display_name and "," in display_name:
                        display_name = ", ".join([x.strip() for x in display_name.split(",")][:5])
                    food_type = ingredient.prdlst_dcnm or ""
                    ratio = None
                    try:
                        ratio = float(relation.ingredient_ratio) if relation.ingredient_ratio is not None else None
                    except Exception:
                        ratio = None

                    # 혼합제제(식품첨가물) 처리
                    if food_category == 'additive' and '혼합제제' in display_name:
                        ingredients_info.append(f"혼합제제[{display_name}]")
                        continue

                    # 향료/동일 용도(영양강화제 등) 번호 붙이기
                    # 향료: "향료" 또는 "향료(00향)" 형태
                    if food_category == 'additive' and (display_name.startswith('향료') or re.match(r'^향료(\(.+\))?$', display_name)):
                        flavor_counter[display_name] = flavor_counter.get(display_name, 0) + 1
                        count = flavor_counter[display_name]
                        suffix = f"{count}" if count > 1 else ""
                        ingredients_info.append(f"향료{suffix}{display_name[2:] if display_name.startswith('향료') else ''}")
                        continue
                    # 동일 용도(예: 영양강화제, 산화방지제 등) 번호 붙이기
                    m = re.match(r'^([가-힣]+제)(\(.+\))?$', display_name)
                    if food_category == 'additive' and m:
                        purpose = m.group(1)
                        purpose_counter[purpose] = purpose_counter.get(purpose, 0) + 1
                        count = purpose_counter[purpose]
                        suffix = f"{count}" if count > 1 else ""
                        ingredients_info.append(f"{purpose}{suffix}{m.group(2) or ''}")
                        continue

                    # 정제수는 식품유형만 표시(팝업과 동일)
                    if display_name == '정제수':
                        summary_item = food_type or display_name
                    # 팝업과 동일하게: 첨가물 또는 비율 5% 이상이면 식품유형[원재료명], 그 외는 식품유형만 표시
                    elif (food_category == 'additive') or (ratio is not None and ratio >= 5):
                        if food_type and display_name:
                            summary_item = f"{food_type}[{display_name}]"
                        elif food_type:
                            summary_item = food_type
                        else:
                            summary_item = display_name
                    else:
                        summary_item = food_type or display_name
                    if summary_item:
                        ingredients_info.append(summary_item)
                    # 알레르기/GMO 수집
                    if ingredient.allergens:
                        allergen_list = ingredient.allergens.split(',')
                        for allergen in allergen_list:
                            allergen = allergen.strip() if allergen else ""
                            if not allergen:
                                continue
                            match = shellfish_pattern.match(allergen)
                            if match:
                                # 조개류(홍합,전복) 형태 처리
                                items = [item.strip() for item in match.group(1).split(',') if item.strip()]
                                shellfish_collected.update(items)
                            elif '조개류' in allergen:
                                allergens_set.add(allergen)
                            else:
                                allergens_set.add(allergen)
                    if ingredient.gmo:
                        for g in ingredient.gmo.split(','):
                            g = g.strip() if g else ""
                            if g:
                                gmo_set.add(g)  # GMO를 별도 집합에 추가
                
                # 조개류 항목이 있으면 통합
                if shellfish_collected:
                    shellfish_str = f"조개류({', '.join(sorted(shellfish_collected))})"
                    allergens_set.add(shellfish_str)
                
                # 콤마로 연결하여 원재료명(참고) 필드에 설정
                rawmtrl_nm_str = ", ".join(ingredients_info)
                # 알레르기/GMO 요약 추가 (각각 별도 대괄호로 분리)
                summary_parts = []
                if allergens_set:
                    # 문자열로 안전하게 변환
                    allergens_list = [str(allergen) for allergen in sorted(allergens_set) if allergen]
                    if allergens_list:
                        summary_parts.append(f"[알레르기 성분: {', '.join(allergens_list)}]")
                if gmo_set:
                    # 문자열로 안전하게 변환
                    gmo_list = [str(gmo) for gmo in sorted(gmo_set) if gmo]
                    if gmo_list:
                        summary_parts.append(f"[GMO: {', '.join(gmo_list)}]")
                if summary_parts:
                    rawmtrl_nm_str += f"  {' '.join(summary_parts)}"
                label.rawmtrl_nm = rawmtrl_nm_str
            
            if request.method == 'POST':
                # POST 요청 처리
                form = LabelCreationForm(request.POST, instance=label)
                
                if form.is_valid():
                    label = form.save(commit=False)  # commit=False를 올바르게 사용
                    label.user_id = request.user
                    
                    # hidden 필드에서 식품유형 정보 가져오기
                    label.food_group = request.POST.get('food_group')
                    label.food_type = request.POST.get('food_type')
                    
                    # 변경 사항 저장
                    label.save()
                    # 메시지 제거
                    return redirect('label:label_creation', label_id=label.my_label_id)
                else:
                    messages.error(request, '입력 정보에 오류가 있습니다.')
            else:
                # GET 요청 처리
                form = LabelCreationForm(instance=label)
        else:
            # 새 라벨 생성
            if request.method == 'POST':
                # POST 요청 처리
                form = LabelCreationForm(request.POST)
                
                if form.is_valid():
                    label = form.save(commit=False)  # commit=False를 올바르게 사용
                    label.user_id = request.user
                    
                    # hidden 필드에서 식품유형 정보 가져오기
                    label.food_group = request.POST.get('food_group')
                    label.food_type = request.POST.get('food_type')
                    
                    # 변경 사항 저장
                    label.save()
                    # 메시지 제거
                    return redirect('label:label_creation', label_id=label.my_label_id)
                else:
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
            'count_ingredient_relations': count_ingredient_relations,
            'regulations_json': json.dumps(FIELD_REGULATIONS, ensure_ascii=False)  # 추가
        }
        return render(request, 'label/label_creation.html', context)


@login_required
@csrf_exempt
def save_to_my_ingredients(request, prdlst_report_no=None):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body) if request.body else {}
        imported_mode = to_bool(data.get("imported_mode", False))
        confirm = data.get("confirm", False)

        food_item = None
        imported_item = None

        if imported_mode:
            imported_item = ImportedFood.objects.filter(pk=prdlst_report_no).first()
            if not imported_item:
                return JsonResponse({"success": False, "error": "해당 수입식품 ID에 대한 데이터를 찾을 수 없습니다."}, status=404)
            prdlst_dcnm = (imported_item.itm_nm or "").strip()
            prdlst_nm = (imported_item.prduct_korean_nm or "").strip()
            rawmtrl_nm = imported_item.irdnt_nm or "미정"
            # 수입식품도 식품유형에 따라 가공식품/첨가물로 구분
            if prdlst_dcnm and FoodType.objects.filter(food_type=prdlst_dcnm).exists():
                food_category = "processed"
            else:
                food_category = "additive"
            # 제조사명 필드: ovsmnfst_nm (수입식품 테이블에서 제조사명)
            bssh_nm_value = imported_item.ovsmnfst_nm or "미정"
        else:
            food_item = FoodItem.objects.filter(prdlst_report_no=prdlst_report_no).first()
            if not food_item:
                return JsonResponse({"success": False, "error": "해당 품목제조번호에 대한 데이터를 찾을 수 없습니다."}, status=404)
            prdlst_dcnm = (food_item.prdlst_dcnm or "").strip()
            prdlst_nm = (food_item.prdlst_nm or "").strip()
            rawmtrl_nm = food_item.rawmtrl_nm or "미정"
            if prdlst_dcnm and FoodType.objects.filter(food_type=prdlst_dcnm).exists():
                food_category = "processed"
            else:
                food_category = "additive"
            bssh_nm_value = food_item.bssh_nm or "미정"

        # 중복 확인 로직 추가
        if not confirm:
            existing_ingredient = MyIngredient.objects.filter(
                user_id=request.user,
                prdlst_nm=prdlst_nm,
                delete_YN='N'
            ).first()
            
            if existing_ingredient:
                return JsonResponse({
                    "success": False,
                    "confirm_required": True,
                    "message": f"동일한 이름의 내원료 '{prdlst_nm}'가 이미 존재합니다. 그래도 저장하시겠습니까?"
                })

        # ------------------- 추천 로직 통합 -------------------
        mixture_types = [
            "L-글루탐산나트륨제제",
            "면류첨가알칼리제",
            "발색제제",
            "보존료제제",
            "사카린나트륨제제",
            "타르색소제제",
            "팽창제제",
            "향료제제",
            "혼합제제",
        ]
        ingredient_display_name = prdlst_nm or "미정"
        # 1. 향료, 천연향료, 합성향료 (단, "향료제제"는 제외)
        if (
            food_category == "additive"
            and any(x in prdlst_dcnm for x in ["향료", "천연향료", "합성향료"])
            and "향료제제" not in prdlst_dcnm
        ):
            # 천연향료/합성향료는 식품유형을 '향료'로 저장
            if any(x in prdlst_dcnm for x in ["천연향료", "합성향료"]):
                prdlst_dcnm_for_save = "향료"
                # 00향 추출은 제품명(prdlst_nm)에서, 한글만 추출(띄어쓰기, 영문, 숫자 제외)
                m = re.search(r'([가-힣]+)향', prdlst_nm)
                flavor_name = m.group(1).strip() if m else ""
                if flavor_name:
                    ingredient_display_name = f"{prdlst_dcnm} or {prdlst_dcnm}({flavor_name}향)"
                else:
                    ingredient_display_name = prdlst_dcnm
            else:
                prdlst_dcnm_for_save = prdlst_dcnm
                m = re.search(r'([가-힣]+)향', prdlst_nm)
                flavor_name = m.group(1).strip() if m else ""
                if flavor_name:
                    ingredient_display_name = f"향료 or 향료({flavor_name}향)"
                else:
                    ingredient_display_name = "향료"
        # 2. 혼합제제류(지정된 식품유형 포함)는 "식품유형[원재료명]"으로 표시
        elif (
            food_category == "additive"
            and any(mix in prdlst_dcnm for mix in mixture_types)
        ):
            prdlst_dcnm_for_save = prdlst_dcnm
            ingredient_display_name = f"{prdlst_dcnm}[{rawmtrl_nm}]" if rawmtrl_nm else prdlst_dcnm
        # 3. 표4,5,6 추천 로직 (위 두 조건에 해당하지 않는 식품첨가물만)
        elif food_category == "additive":
            prdlst_dcnm_for_save = prdlst_dcnm
            try:
                additive = FoodAdditive.objects.get(name_kr=prdlst_dcnm)
                display_candidates = set()
                table_types = set()
                # 명칭(주용도)
                if additive.name_kr and additive.main_purpose:
                    display_candidates.add(f"{additive.name_kr}({additive.main_purpose})")
                if additive.name_kr:
                    display_candidates.add(additive.name_kr)
                if additive.short_name:
                    for s in str(additive.short_name).split(","):
                        s = s.strip()
                        if s and s not in {"Y", "N", "-"}:
                            display_candidates.add(s)
                if additive.main_purpose:
                    for s in str(additive.main_purpose).split(","):
                        s = s.strip()
                        if s and s not in {"Y", "N", "-"}:
                            display_candidates.add(s)
                if additive.alias_4:
                    table_types.add("4")
                    for val in str(additive.alias_4).split(","):
                        val = val.strip()
                        if val and val not in {"Y", "N", "-"}:
                            display_candidates.add(val)
                if additive.alias_5:
                    table_types.add("5")
                    for val in str(additive.alias_5).split(","):
                        val = val.strip()
                        if val and val not in {"Y", "N", "-"}:
                            display_candidates.add(val)
                if additive.alias_6:
                    table_types.add("6")
                    for val in str(additive.alias_6).split(","):
                        val = val.strip()
                        if val and val not in {"Y", "N", "-"}:
                            display_candidates.add(val)
                # 정렬
                ordered = []
                if additive.name_kr and additive.main_purpose:
                    nm_purp = f"{additive.name_kr}({additive.main_purpose})"
                    if nm_purp in display_candidates:
                        ordered.append(nm_purp)
                        display_candidates.discard(nm_purp)
                if additive.name_kr and additive.name_kr in display_candidates:
                    ordered.append(additive.name_kr)
                    display_candidates.discard(additive.name_kr)
                if additive.short_name:
                    for s in str(additive.short_name).split(","):
                        s = s.strip()
                        if s and s in display_candidates:
                            ordered.append(s)
                            display_candidates.discard(s)
                if additive.main_purpose:
                    for s in str(additive.main_purpose).split(","):
                        s = s.strip()
                        if s and s in display_candidates:
                            ordered.append(s)
                            display_candidates.discard(s)
                for val in sorted(display_candidates):
                    ordered.append(val)
                if ordered:
                    ingredient_display_name = " or ".join(ordered)
                if table_types:
                    tables = [f"표 {t}" for t in sorted(table_types)]
                    ingredient_display_name += f"\n※ 이 식품첨가물은 {', '.join(tables)}에 해당하는 원료입니다."
            except FoodAdditive.DoesNotExist:
                ingredient_display_name = rawmtrl_nm or "미정"
        else:
            prdlst_dcnm_for_save = prdlst_dcnm
            ingredient_display_name = rawmtrl_nm or "미정"
        # ---------------------------------------------------

        MyIngredient.objects.create(
            user_id=request.user,
            prdlst_report_no=None if imported_mode else food_item.prdlst_report_no,
            prdlst_nm=prdlst_nm or "미정",
            bssh_nm=bssh_nm_value,
            prms_dt="" if imported_mode else (food_item.prms_dt or "00000000"),
            food_category=food_category,
            prdlst_dcnm=prdlst_dcnm_for_save if 'prdlst_dcnm_for_save' in locals() else (prdlst_dcnm or "미정"),
            pog_daycnt=(imported_item.expirde_dtm if imported_mode else food_item.pog_daycnt) or "0",
            frmlc_mtrqlt="" if imported_mode else (food_item.frmlc_mtrqlt or "미정"),
            rawmtrl_nm=rawmtrl_nm or "미정",
            ingredient_display_name=ingredient_display_name,
            delete_YN="N"
        )
        # 메시지 제거 - JSON 응답만 반환
        return JsonResponse({"success": True, "message": "내 원료로 저장되었습니다."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)



def ingredient_popup(request):
    label_id = request.GET.get('label_id')
    ingredients_data = []
    has_relations = False
    if label_id:
        # relation_sequence 순서로 명시적 정렬 (모델의 기본 ordering 무시)
        relations = LabelIngredientRelation.objects.filter(label_id=label_id).select_related('ingredient').order_by('relation_sequence')
        for relation in relations:
            ingredient = relation.ingredient
            food_category = getattr(ingredient, 'food_category', None) or getattr(ingredient, 'food_group', None) or ''
            ingredients_data.append({
                'my_ingredient_id': ingredient.my_ingredient_id,
                'ingredient_name': ingredient.prdlst_nm,
                'prdlst_report_no': ingredient.prdlst_report_no or '',
                'ratio': float(relation.ingredient_ratio) if relation.ingredient_ratio else '',
                'food_type': ingredient.prdlst_dcnm or '',
                'food_category': food_category,
                'display_name': ingredient.ingredient_display_name,
                'allergen': ingredient.allergens or '',
                'gmo': ingredient.gmo or '',
                'manufacturer': ingredient.bssh_nm or ''
            })
        if relations.exists():
            has_relations = True  # 관계 데이터가 있는 경우 플래그 설정
    # 국가 목록 데이터 추가
    country_list = list(CountryList.objects.values('country_name_ko').order_by('country_name_ko'))
    country_names = [country['country_name_ko'] for country in country_list]
    context = {
        'saved_ingredients': ingredients_data,
        'has_relations': has_relations,
        'country_names': country_names,  # 국가 목록 추가
        'food_types': list(FoodType.objects.all().values('food_type')),
        'agricultural_products': list(AgriculturalProduct.objects.all().values(name_kr=F('rprsnt_rawmtrl_nm'))),
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
        return JsonResponse({'exists': False, 'error': 'Invalid request method'}, status=400)
    try:
        data = json.loads(request.body)
        prdlst_nm = data.get('prdlst_nm', '').strip()
        exists = False
        if prdlst_nm:
            exists = MyIngredient.objects.filter(user_id=request.user, prdlst_nm=prdlst_nm, delete_YN='N').exists()
        return JsonResponse({'exists': exists})
    except Exception as e:
        return JsonResponse({'exists': False, 'error': str(e)}, status=500)
    
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
    # 기존: search_conditions &= Q(delete_YN='N') & Q(user_id=request.user)
    search_conditions &= Q(delete_YN='N') & (Q(user_id=request.user) | Q(user_id__isnull=True))
    sort_field, sort_order = process_sorting(request, 'prdlst_nm')
    # ↓ 추가: report_no_verify_yn → report_no_verify_YN로 변환
    if sort_field.lstrip('-') == 'report_no_verify_yn':
        sort_field = sort_field.replace('report_no_verify_yn', 'report_no_verify_YN')
    items_per_page = int(request.GET.get('items_per_page', 10))
    page_number = request.GET.get('page', 1)
    # 원료관리: 식품구분 오름차순(가나다순), 식품유형 오름차순(가나다순), 원재료명 오름차순
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
    label_id = request.GET.get('label_id')
    search_fields = {
        'prdlst_nm': 'prdlst_nm',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
        'allergens': 'allergens',
        'gmo': 'gmo',
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    search_conditions &= Q(delete_YN='N') & (Q(user_id=request.user) | Q(user_id__isnull=True))

    # 식품구분(카테고리) 검색 지원
    food_category = request.GET.get('food_category', '').strip()
    if food_category:
        search_conditions &= Q(food_category=food_category)

    sort_field, sort_order = process_sorting(request, 'prdlst_nm')
    items_per_page = int(request.GET.get('items_per_page', 10))
    page_number = request.GET.get('page', 1)

    if label_id:
        # 라벨에 연결된 원료만 조회
        ingredient_ids = LabelIngredientRelation.objects.filter(label_id=label_id).values_list('ingredient_id', flat=True)
        my_ingredients = MyIngredient.objects.filter(my_ingredient_id__in=ingredient_ids).filter(search_conditions).order_by(sort_field)
        # 라벨명 가져오기
        label_name = None
        try:
            label_obj = MyLabel.objects.get(my_label_id=label_id)
            label_name = label_obj.my_label_name
        except MyLabel.DoesNotExist:
            label_name = None
    else:
        my_ingredients = MyIngredient.objects.filter(search_conditions).order_by(sort_field)
        label_name = None

    total_count = my_ingredients.count()
    paginator, page_obj, page_range = paginate_queryset(my_ingredients, page_number, items_per_page)
    querystring_without_page = get_querystring_without(request, ['page'])
    querydict_sort = request.GET.copy()
    querydict_sort.pop('sort', None)
    querydict_sort.pop('order', None)
    querystring_without_sort = querydict_sort.urlencode()

    # 검색 조건이 있는지 확인
    has_search_conditions = any(search_values.values()) or food_category
    search_result_count = total_count if has_search_conditions else None

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
            {'name': 'allergens', 'placeholder': '알레르기', 'value': search_values.get('allergens', '')},
            {'name': 'gmo', 'placeholder': 'GMO', 'value': search_values.get('gmo', '')},
        ],
        'items_per_page': items_per_page,
        'sort_field': sort_field.lstrip('-'),
        'sort_order': sort_order,
        'querystring_without_page': querystring_without_page,
        'querystring_without_sort': querystring_without_sort,
        'label_id': label_id,
        'label_name': label_name,
        'search_result_count': search_result_count,  # 검색 결과 건수 추가
    }
    return render(request, 'label/my_ingredient_list_combined.html', context)

@login_required
def my_ingredient_detail(request, ingredient_id=None):
    # POST일 때 my_ingredient_id 우선 활용
    my_ingredient_id = request.POST.get('my_ingredient_id') or ingredient_id
    if my_ingredient_id:
        # user_id는 request.user 또는 None도 허용 (공용 원료 지원)
        ingredient = get_object_or_404(MyIngredient, my_ingredient_id=my_ingredient_id)
        mode = 'edit'
    else:
        ingredient = MyIngredient(user_id=request.user, delete_YN='N')
        mode = 'create'

    if request.method == 'POST':
        # 공용 원료(user_id=None)는 수정 불가
        if getattr(ingredient, 'user_id', None) is None:
            msg = '공용 원료는 수정할 수 없습니다.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': msg})
            else:
                messages.error(request, msg)
                return redirect('label:my_ingredient_detail', ingredient_id=ingredient.my_ingredient_id)
        # 중복 체크: 신규 등록(생성)일 때만 동일한 이름의 내 원료가 이미 존재하면 에러 반환
        prdlst_nm = request.POST.get('prdlst_nm', '').strip()
        ignore_duplicate = request.POST.get('ignore_duplicate', '').upper() == 'Y'
        if prdlst_nm and mode == 'create' and not ignore_duplicate:
            duplicate_qs = MyIngredient.objects.filter(user_id=request.user, prdlst_nm=prdlst_nm, delete_YN='N')
            if duplicate_qs.exists():
                msg = '동일한 이름의 원료가 이미 존재합니다.'
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': msg}, status=400)
                else:
                    messages.error(request, msg)
                    return redirect('label:my_ingredient_detail', ingredient_id=ingredient.my_ingredient_id)
        form = MyIngredientsForm(request.POST, instance=ingredient)
        if form.is_valid():
            new_ingredient = form.save(commit=False)
            new_ingredient.user_id = request.user
            new_ingredient.save()
            # AJAX 요청 시 ingredient_id 항상 반환
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': '내 원료가 성공적으로 저장되었습니다.',
                    'ingredient_id': new_ingredient.my_ingredient_id
                })
            # 메시지 제거
            return redirect('label:my_ingredient_detail', ingredient_id=new_ingredient.my_ingredient_id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # 폼 에러를 문자열로 반환
                errors = {field: str(error) for field, error in form.errors.items()}
                return JsonResponse({'success': False, 'errors': errors, 'message': '입력값 오류'})
    else:
        form = MyIngredientsForm(instance=ingredient)

    context = {
        'ingredient': ingredient,
        'form': form,
        'mode': mode,
        'food_types': list(FoodType.objects.all().values('food_type')),
        'agricultural_products': list(AgriculturalProduct.objects.all().values(name_kr=F('rprsnt_rawmtrl_nm'))),
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
            # "정제수"는 공용 MyIngredient(user_id=None, prdlst_nm='정제수')와만 연결
            if ingredient_data.get('ingredient_name') == "정제수":
                ingredient = MyIngredient.objects.filter(user_id=None, prdlst_nm="정제수", delete_YN='N').first()
                if not ingredient:
                    # 공용 정제수 원료가 없으면 이 원료는 건너뜀
                    continue
                relation = LabelIngredientRelation(
                    label=label,
                    ingredient=ingredient,
                    relation_sequence=sequence
                )
                try:
                    ratio_value = ingredient_data.get('ratio', '')
                    if ratio_value and ratio_value.strip():
                        relation.ingredient_ratio = Decimal(ratio_value)
                except (ValueError, InvalidOperation):
                    pass
                relation.save()
                continue

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
        # 메시지 제거 - JSON 응답만 반환
        return JsonResponse({'success': True, 'message': '저장되었습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def delete_my_ingredient(request, ingredient_id):
    # 게스트 사용자는 삭제 불가
    if request.user.username == 'guest@labeasylabel.com':
        return JsonResponse({'success': False, 'error': '게스트 계정은 삭제 기능을 사용할 수 없습니다.'})
        
    if request.method == 'POST':
        try:
            ingredient = get_object_or_404(MyIngredient, my_ingredient_id=ingredient_id, user_id=request.user)
            # 공용 원료(user_id=None)는 삭제 불가
            if getattr(ingredient, 'user_id', None) is None:
                return JsonResponse({'success': False, 'error': '공용 원료는 삭제할 수 없습니다.'})
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
        food_category = data.get('food_category', '').strip()
        
        # 기존: qs = MyIngredient.objects.filter(user_id=request.user, delete_YN='N')
        qs = MyIngredient.objects.filter(delete_YN='N').filter(Q(user_id=request.user) | Q(user_id__isnull=True))
        if name:
            qs = qs.filter(prdlst_nm__icontains=name)
        if report:
            qs = qs.filter(prdlst_report_no__icontains=report)
        if food_type:
            qs = qs.filter(prdlst_dcnm__icontains=food_type)
        if manufacturer:
            qs = qs.filter(bssh_nm__icontains=manufacturer)
        if food_category:
            qs = qs.filter(food_category=food_category)
        
        ingredients = list(qs.values(
            'prdlst_nm',
            'prdlst_report_no',
            'prdlst_dcnm',
            'bssh_nm',
            'ingredient_display_name',
            'my_ingredient_id',
            'food_category',  # 식품 구분 필드 추가
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
    # 쉼표 없는 정수로 반환
    return JsonResponse({'total': total, 'new': new_count})

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
        prdlst_nm = data.get('ingredient_name', '').strip()
        # 중복 체크: 동일한 이름의 내 원료가 이미 존재하면 에러 반환
        if MyIngredient.objects.filter(user_id=request.user, prdlst_nm=prdlst_nm, delete_YN='N').exists():
            return JsonResponse({'success': False, 'error': '동일한 이름의 원료가 이미 존재합니다.'}, status=400)
        MyIngredient.objects.create(
            user_id=request.user,
            prdlst_nm=prdlst_nm,
            prdlst_report_no=data.get('prdlst_report_no', ''),
            prdlst_dcnm=data.get('food_type', ''),
            ingredient_display_name=data.get('display_name', ''),
            bssh_nm=data.get('manufacturer', ''),
            delete_YN='N'
        )
        # 메시지 제거 - JSON 응답만 반환
        return JsonResponse({'success': True})
    except Exception as e:
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
    # 게스트 사용자는 삭제 불가
    if request.user.username == 'guest@labeasylabel.com':
        messages.error(request, '게스트 계정은 삭제 기능을 사용할 수 없습니다.')
        return redirect('label:my_label_list')
        
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
@login_required
@csrf_exempt
def bulk_delete_labels(request):
    # 게스트 사용자는 삭제 불가
    if request.user.username == 'guest@labeasylabel.com':
        return JsonResponse({"success": False, "error": "게스트 계정은 삭제 기능을 사용할 수 없습니다."})
        
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
        category_name = data.get('category_name', '').strip()
        
        # 유효한 카테고리인지 확인
        valid_categories = [choice[0] for choice in CATEGORY_CHOICES]
        if not category_name or category_name not in valid_categories:
            return JsonResponse({
                'success': False, 
                'error': f'카테고리 값이 올바르지 않습니다. 받은 값: "{category_name}", 유효한 값: {valid_categories}'
            })

        if action == 'create':
            # 신규 문구 생성
            new_phrase = MyPhrase.objects.create(
                user_id=request.user,
                my_phrase_name=data.get('my_phrase_name'),
                category_name=category_name,
                comment_content=data.get('comment_content'),
                note=data.get('note', ''),
                display_order=data.get('order', 0),  # display_order 추가
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
                category_name_change = change.get('category_name', '').strip()
                if not category_name_change or category_name_change not in valid_categories:
                    return JsonResponse({
                        'success': False, 
                        'error': f'카테고리 값이 올바르지 않습니다. 받은 값: "{category_name_change}", 유효한 값: {valid_categories}'
                    })
                
                phrase = MyPhrase.objects.get(
                    my_phrase_id=change['id'],
                    user_id=request.user
                )
                phrase.my_phrase_name = change.get('my_phrase_name', phrase.my_phrase_name)
                phrase.comment_content = change.get('comment_content', phrase.comment_content)
                phrase.note = change.get('note', phrase.note)
                phrase.category_name = category_name_change
                phrase.display_order = change.get('order', phrase.display_order)  # display_order 업데이트
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
        return JsonResponse({'success': False, 'error': '문구를 찾을 수 없습니다.'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '잘못된 데이터 형식입니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'오류 발생: {str(e)}'})

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

def phrase_popup(request):
    """자주 사용하는 문구 팝업"""
    phrases_data = {}
    categories = CATEGORY_CHOICES
    
    # CATEGORY_CHOICES에서 정의된 모든 카테고리에 대한 빈 리스트 초기화
    for category_code, _ in categories:
        phrases_data[category_code] = []
    
    # 사용자 문구만 가져오기 (display_order 순으로 정렬)
    user_phrases = MyPhrase.objects.filter(
        user_id=request.user, 
        delete_YN='N'
    ).order_by('category_name', 'display_order', 'my_phrase_name')

    # 유효한 카테고리 코드 목록 생성
    valid_categories = {choice[0] for choice in CATEGORY_CHOICES}

    for phrase in user_phrases:
        category = phrase.category_name
        
        # 유효한 카테고리가 아닌 경우 처리
        if category not in valid_categories:
            # 로그는 개발 환경에서만 출력하도록 제한
            if hasattr(settings, 'DEBUG') and settings.DEBUG:
                try:
                    print(f"Warning: Unknown category in MyPhrase: {category} (ID: {phrase.my_phrase_id})")
                except Exception:
                    pass
            
            # 알 수 없는 카테고리는 'additional'로 분류하거나 건너뛰기
            # 옵션 1: 건너뛰기 (현재 방식)
            continue
            
            # 옵션 2: 'additional' 카테고리로 분류
            # if 'additional' in phrases_data:
            #     category = 'additional'
            # else:
            #     continue
        
        # phrases_data에 해당 카테고리가 없으면 초기화 (동적 카테고리 지원)
        if category not in phrases_data:
            phrases_data[category] = []
            
        phrases_data[category].append({
            'id': phrase.my_phrase_id,
            'name': phrase.my_phrase_name,
            'content': phrase.comment_content,
            'note': phrase.note or '',
            'order': phrase.display_order or 0,
            'is_custom': True
        })
    
    context = {
        'phrases_json': json.dumps(phrases_data),
        'categories': categories
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
            ('rawmtrl_nm', '원재료명(참고)'),
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

        # 영양성분 데이터 nutrition_data (계산기와 동일 구조)
        nutrition_data = {
            'serving_size': label.serving_size or '',
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

        # 국가명 목록 추가 - 안전한 JSON 변환
        country_list = list(CountryList.objects.all().values_list('country_name_ko', flat=True))
        # None 값 제거 및 빈 문자열 제거
        country_list = [country for country in country_list if country and country.strip()]
        
        context = {
            'label': label,  # label 객체를 context에 추가
            'preview_items': preview_items,
            'nutrition_items': nutrition_items,
            'allergens': list(set(allergens)),  # 중복 제거
            'origins': list(set(origins)),       # 중복 제거
            'nutrition_data': json.dumps(nutrition_data, ensure_ascii=False),
            'country_list': json.dumps(country_list, ensure_ascii=False),  # JSON 직렬화
            'expiry_recommendation_json': json.dumps(get_expiry_recommendations(), ensure_ascii=False)  # 소비기한 권장 데이터 추가

        }
        
        return render(request, 'label/label_preview.html', context)
        
    except MyLabel.DoesNotExist:
        return JsonResponse({'success': False, 'error': '라벨을 찾을 수 없습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@csrf_exempt
def export_labels_excel(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    try:
        data = json.loads(request.body)
        label_ids = data.get('label_ids', [])
        if not label_ids:
            return JsonResponse({'success': False, 'error': '선택된 라벨이 없습니다.'}, status=400)
        labels = MyLabel.objects.filter(my_label_id__in=label_ids, user_id=request.user, delete_YN='N').order_by('my_label_id')
        if not labels.exists():
            return JsonResponse({'success': False, 'error': '다운로드할 데이터가 없습니다.'}, status=400)

        import openpyxl
        from openpyxl.styles import Font

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "표시사항"

        headers = [
            '번호', '품목보고번호', '제품명', '라벨명', '식품유형', '제조사명', '최종수정일자',
            '성분명 및 함량', '내용량', '내용량(열량)', '원산지', '보관방법', '포장재질',
            '유통전문판매원', '소분원', '수입원', '소비기한', '원재료명(표시)', '원재료명(참고)', '주의사항', '기타표시사항', '영양성분'

        ]
        ws.append(headers)

        font = Font(size=10)
        ws.column_dimensions[openpyxl.utils.get_column_letter(1)].width = 4
       
        for col_idx in range(2, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 10
        for col in ws.iter_cols(min_row=1, max_row=1, max_col=len(headers)):
            for cell in col:
                cell.font = font

        for idx, label in enumerate(labels, start=1):
            update_dt = ''
            if label.update_datetime:
                update_dt = label.update_datetime.strftime('%y-%m-%d %H:%M')
            row = [
                idx,
                label.prdlst_report_no,
                label.prdlst_nm,
                label.my_label_name,
                label.prdlst_dcnm,
                label.bssh_nm,
                update_dt,
                label.ingredient_info,
                label.content_weight,
                label.weight_calorie,
                label.country_of_origin,
                label.storage_method,
                label.frmlc_mtrqlt,
                label.distributor_address,
                label.repacker_address,
                label.importer_address,
                label.pog_daycnt,
                label.rawmtrl_nm_display,
                label.rawmtrl_nm,
                label.cautions,
                label.additional_info,
                label.nutrition_text,
            ]
            ws.append(row)
            for cell in ws[ws.max_row]:
                cell.font = font

        # 파일명: LabelData_표시사항_사용자ID_다운받은년월일.xlsx
        today_str = now().strftime('%y%m%d')
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            user_id = getattr(request.user, 'pk', 'user')
        filename = f'LabelData_표시사항_{user_id}_{today_str}.xlsx'
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def my_ingredient_table_partial(request):
    search_fields = {
        'prdlst_nm': 'prdlst_nm',
        'prdlst_report_no': 'prdlst_report_no',
        'prdlst_dcnm': 'prdlst_dcnm',
        'bssh_nm': 'bssh_nm',
        'ingredient_display_name': 'ingredient_display_name',
    }
    search_conditions, search_values = get_search_conditions(request, search_fields)
    # 기존: search_conditions &= Q(delete_YN='N') & Q(user_id=request.user)
    search_conditions &= Q(delete_YN='N') & (Q(user_id=request.user) | Q(user_id__isnull=True))
    sort_field, sort_order = process_sorting(request, 'prdlst_nm')
    my_ingredients = MyIngredient.objects.filter(search_conditions).order_by(sort_field)
    paginator, page_obj, page_range = paginate_queryset(my_ingredients, request.GET.get('page', 1), request.GET.get('items_per_page', 10))
    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range': page_range,
    }
    return render(request, 'label/my_ingredient_table.html', context)

@require_POST
@login_required
def save_preview_settings(request):
    """미리보기 설정(prv_*) 저장"""
    try:
        data = json.loads(request.body)
        label_id = data.get('label_id')
        label = get_object_or_404(MyLabel, my_label_id=label_id, user_id=request.user)
        # 입력값 저장
        label.prv_layout = data.get('layout')
        label.prv_width = data.get('width')
        label.prv_length = data.get('length')
        label.prv_font = data.get('font')
        label.prv_font_size = data.get('font_size')
        label.prv_letter_spacing = data.get('letter_spacing')
        label.prv_line_spacing = data.get('line_spacing')
        label.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def imported_food_count(request):
    total = ImportedFood.objects.count()
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    # expirde_dtm, expirde_end_dtm, procs_dtm 중 하나라도 최근 1주일 이내인 경우 신규로 간주
    new_count = ImportedFood.objects.filter(
        Q(expirde_dtm__gte=one_week_ago) |
        Q(expirde_end_dtm__gte=one_week_ago) |
        Q(procs_dtm__gte=one_week_ago)
    ).count()
    # 쉼표 없는 정수로 반환
    return JsonResponse({'total': total, 'new': new_count})

@login_required
@csrf_exempt
def linked_labels_count(request, ingredient_id):
    """
    특정 내원료(ingredient_id)와 연결된 표시사항(LabelIngredientRelation) 개수 반환
    """
    count = LabelIngredientRelation.objects.filter(ingredient_id=ingredient_id).count()
    return JsonResponse({'count': count})

@login_required
@csrf_exempt
def linked_ingredient_count(request, label_id):
    """
    Returns the count of ingredients linked to a given label (MyLabel).
    """
    try:
        count = LabelIngredientRelation.objects.filter(label_id=label_id).count()
        return JsonResponse({'count': count})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
@login_required
def verify_report_no(request):
    import json
    data = json.loads(request.body)
    label_id = data.get('label_id')
    prdlst_report_no = data.get('prdlst_report_no', '').strip()
    if not label_id or not prdlst_report_no:
        return JsonResponse({'verified': False, 'error': '필수값 누락'})
    try:
        label = MyLabel.objects.get(pk=label_id, user_id=request.user)
    except MyLabel.DoesNotExist:
        return JsonResponse({'verified': False, 'error': '라벨을 찾을 수 없습니다.'})
    exists = FoodItem.objects.filter(prdlst_report_no=prdlst_report_no).exists()
    if exists:
        label.report_no_verify_YN = 'Y'
        label.save(update_fields=['report_no_verify_YN'])
        return JsonResponse({'verified': True})
    else:
        return JsonResponse({'verified': False})

@csrf_exempt
@require_POST
@login_required
def update_report_no(request):
    try:
        data = json.loads(request.body)
        label_id = data.get('label_id')
        prdlst_report_no = data.get('prdlst_report_no', '').strip()
        if not label_id or not prdlst_report_no:
            return JsonResponse({'success': False, 'error': '필수값 누락'}, status=400)
        label = MyLabel.objects.get(my_label_id=label_id)
        # 품목보고번호가 변경된 경우에만 업데이트
        if label.prdlst_report_no != prdlst_report_no:
            label.prdlst_report_no = prdlst_report_no
            label.report_no_verify_YN = 'N'
            label.save(update_fields=['prdlst_report_no', 'report_no_verify_YN'])
        return JsonResponse({'success': True})
    except MyLabel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Label not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def phrases_data_api(request):
    """내 문구 데이터 JSON 반환 (AJAX)"""
    phrases_data = {}
    categories = CATEGORY_CHOICES
    for category_code, _ in categories:
        phrases_data[category_code] = []
    user_phrases = MyPhrase.objects.filter(
        user_id=request.user,
        delete_YN='N'
    ).order_by('category_name', 'display_order')
    for phrase in user_phrases:
        category = phrase.category_name
        if category not in phrases_data:
            continue
        phrases_data[category].append({
            'id': phrase.my_phrase_id,
            'name': phrase.my_phrase_name,
            'content': phrase.comment_content,
            'note': phrase.note or '',
            'order': phrase.display_order
        })
    return JsonResponse({'success': True, 'phrases': phrases_data})

@login_required
def my_ingredient_calculate_page(request):
    """신규 등록된 원료의 페이지 위치 계산"""
    ingredient_id = request.GET.get('ingredient_id')
    if not ingredient_id:
        return JsonResponse({'success': False, 'error': '원료 ID가 필요합니다.'})
    
    try:
        # 검색 조건 가져오기
        search_fields = {
            'prdlst_nm': 'prdlst_nm',
            'prdlst_report_no': 'prdlst_report_no',
            'prdlst_dcnm': 'prdlst_dcnm',
            'bssh_nm': 'bssh_nm',
            'ingredient_display_name': 'ingredient_display_name',
        }
        search_conditions, search_values = get_search_conditions(request, search_fields)
        search_conditions &= Q(delete_YN='N') & (Q(user_id=request.user) | Q(user_id__isnull=True))

        # 식품구분(카테고리) 검색 지원
        food_category = request.GET.get('food_category', '').strip()
        if food_category:
            search_conditions &= Q(food_category=food_category)

        # 알레르기, GMO 검색조건 추가
        allergens = request.GET.get('allergens', '').strip()
        if allergens:
            search_conditions &= Q(allergens__icontains=allergens)
        gmo = request.GET.get('gmo', '').strip()
        if gmo:
            search_conditions &= Q(gmo__icontains=gmo)
        
        items_per_page = int(request.GET.get('items_per_page', 10))
        
        # 전체 원료 리스트에서 해당 원료의 위치 찾기
        my_ingredients = MyIngredient.objects.filter(search_conditions).order_by('-prms_dt', 'food_category', 'prdlst_nm')
        
        # 해당 원료의 인덱스 찾기
        ingredient_index = None
        for index, ingredient in enumerate(my_ingredients):
            if str(ingredient.my_ingredient_id) == str(ingredient_id):
                ingredient_index = index
                break
        
        if ingredient_index is not None:
            # 페이지 계산 (0부터 시작하는 인덱스를 1부터 시작하는 페이지로 변환)
            target_page = (ingredient_index // items_per_page) + 1
            return JsonResponse({
                'success': True, 
                'page': target_page,
                'index': ingredient_index,
                'total_items': my_ingredients.count()
            })
        else:
            return JsonResponse({'success': False, 'error': '해당 원료를 찾을 수 없습니다.'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def my_ingredient_pagination_info(request):
    """페이지네이션 정보 반환"""
    try:
        search_fields = {
            'prdlst_nm': 'prdlst_nm',
            'prdlst_report_no': 'prdlst_report_no',
            'prdlst_dcnm': 'prdlst_dcnm',
            'bssh_nm': 'bssh_nm',
            'ingredient_display_name': 'ingredient_display_name',
        }
        search_conditions, search_values = get_search_conditions(request, search_fields)
        search_conditions &= Q(delete_YN='N') & (Q(user_id=request.user) | Q(user_id__isnull=True))

        # 식품구분(카테고리) 검색 지원
        food_category = request.GET.get('food_category', '').strip()
        if food_category:
            search_conditions &= Q(food_category=food_category)

        # 알레르기, GMO 검색조건 추가
        allergens = request.GET.get('allergens', '').strip()
        if allergens:
            search_conditions &= Q(allergens__icontains=allergens)
        gmo = request.GET.get('gmo', '').strip()
        if gmo:
            search_conditions &= Q(gmo__icontains=gmo)

        items_per_page = int(request.GET.get('items_per_page', 10))
        page_number = request.GET.get('page', 1)
        sort_field, sort_order = process_sorting(request, 'prdlst_nm')
        if sort_field.lstrip('-') == 'report_no_verify_yn':
            sort_field = sort_field.replace('report_no_verify_yn', 'report_no_verify_YN')

        my_ingredients = MyIngredient.objects.filter(search_conditions).order_by(sort_field)
        paginator, page_obj, page_range = paginate_queryset(my_ingredients, page_number, items_per_page)

        return JsonResponse({
            'success': True,
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'item_count': len(page_obj.object_list),
            'total_items': paginator.count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
