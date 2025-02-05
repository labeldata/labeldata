import json
from venv import logger  #지우지 말 것
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import FoodItem, MyLabel, MyIngredient, Allergen
from .forms import LabelCreationForm
from django.core.paginator import Paginator
from django.http import JsonResponse
import uuid



def food_item_list(request):
    # 제품 목록
    search_query = request.GET.get("prdlst_nm", "").strip()
    manufacturer_query = request.GET.get("bssh_nm", "").strip()
    items_per_page = request.GET.get("items_per_page", 10)

    try:
        items_per_page = int(items_per_page)
    except ValueError:
        items_per_page = 10

    items = FoodItem.objects.filter(
        prdlst_nm__icontains=search_query,
        bssh_nm__icontains=manufacturer_query,
        ).order_by("-last_updt_dtm")

    paginator = Paginator(items, items_per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # 동적 페이지 범위 설정
    current_page = page_obj.number
    total_pages = paginator.num_pages
    page_range = range(max(1, current_page - 5), min(total_pages + 1, current_page + 5))

    return render(
        request,
        "label/food_item_list.html",
        {
            "page_obj": page_obj,
            "paginator": paginator,
            "page_range": page_range,
            "search_query": search_query,
            "items_per_page": items_per_page,
            "manufacturer_query": manufacturer_query,
        },
    )


def food_item_detail(request, prdlst_report_no):
    # 제품 상세 정보 팝업
    food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
    #my_product_yn = MyProduct.objects.filter(prdlst_report_no=prdlst_report_no, user=request.user).first()

    return render(request, 'label/food_item_detail.html', {'item': food_item,  })

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
    # FoodItem 데이터를 MyLabel로 복사 (내 표시사항으로 저장)
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    try:
        # 이미 존재하는 경우 체크
        existing_label = MyLabel.objects.filter(prdlst_report_no=prdlst_report_no, user_id=request.user).first()
        if existing_label:
            print("🔸 이미 내 라벨에 존재하는 제품")
            return JsonResponse({'success': False, 'error': '이미 내 라벨에 저장된 항목입니다.'}, status=400)
        
        # FoodItem 조회
        food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
        print(f"🔹 FoodItem 찾음: {food_item.prdlst_nm} ({food_item.prdlst_report_no})")
       

        # FOODITEM_MYLABEL_MAPPING을 사용하여 FoodItem의 데이터를 복사할 딕셔너리 생성
        data = {}
        for food_field, mylabel_field in FOODITEM_MYLABEL_MAPPING.items():
            data[mylabel_field] = getattr(food_item, food_field, '')
        # 필요하다면 기본값 처리 (예: 빈 문자열 대신 "미정" 등)

        # MyLabel 생성 시 user, my_label_name 등 추가 필드를 함께 지정
        my_label = MyLabel.objects.create(
            user_id=request.user,
            my_label_name="임시 - " + food_item.prdlst_nm,
            **data
        )

        print(f"✅ MyLabel 저장 완료: {my_label.prdlst_nm}")
        return JsonResponse({'success': True, 'message': '내 표시사항으로 저장되었습니다.'})

    except Exception as e:
        print(f"❌ MyLabel 저장 실패: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def my_label_list(request):
    # 제품 목록
    search_query = request.GET.get("prdlst_nm", "").strip()
    manufacturer_query = request.GET.get("bssh_nm", "").strip()
    items_per_page = request.GET.get("items_per_page", 10)

    try:
        items_per_page = int(items_per_page)
    except ValueError:
        items_per_page = 10

    items = FoodItem.objects.filter(
        prdlst_nm__icontains=search_query,
        bssh_nm__icontains=manufacturer_query,
        ).order_by("-last_updt_dtm")

    paginator = Paginator(items, items_per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # 동적 페이지 범위 설정
    current_page = page_obj.number
    total_pages = paginator.num_pages
    page_range = range(max(1, current_page - 5), min(total_pages + 1, current_page + 5))

    return render(
        request,
        "label/food_item_list.html",
        {
            "page_obj": page_obj,
            "paginator": paginator,
            "page_range": page_range,
            "search_query": search_query,
            "items_per_page": items_per_page,
            "manufacturer_query": manufacturer_query,
        },
    )



@login_required
def label_creation(request, unique_key):
    # 표시사항 작성 및 수정
    my_product = get_object_or_404(MyLabel, unique_key=unique_key, user=request.user)
    
    # 기존 Label이 있는지 확인
    label, created = MyLabel.objects.get_or_create(my_product=my_product)
    
    # 초기 데이터 설정
    initial_data = {
        "prdlst_report_no": my_product.prdlst_report_no,
        "prdlst_nm": my_product.prdlst_nm,
        "prdlst_dcnm": my_product.prdlst_dcnm,
        "bssh_nm": my_product.bssh_nm,
        "rawmtrl_nm": my_product.rawmtrl_nm,
        "content_weight": my_product.content_weight,
        "manufacturer_address": my_product.manufacturer_address,
        "storage_method": my_product.storage_method,
        "distributor_name": my_product.distributor_name,
        "distributor_address": my_product.distributor_address,
        "warnings": my_product.warnings,
        "additional_info": my_product.additional_info,
        "origin": my_product.origin,
        "importer_address": my_product.importer_address,
    }

    # 기존 Label 데이터가 없을 경우, MyProduct 데이터를 기반으로 Label 생성
    if created:
        for field, value in initial_data.items():
            setattr(label, field, value)
        label.save()

    if request.method == "POST":
        form = LabelCreationForm(request.POST, instance=label)
        if form.is_valid():
            form.save()
            my_product.label_created = True
            my_product.save()
            messages.success(request, "표시사항이 성공적으로 저장되었습니다.")
            return redirect("label:my_product_list")
    else:
        form = LabelCreationForm(instance=label)

    return render(request, "label/label_creation.html", {
        "form": form, 
        "my_product": my_product, 
        "allergens": Allergen.objects.all(), #  알레르기 물질 리스트 전달
        "label": label
    })


@login_required
@csrf_exempt  # fetch 요청에서 CSRF 문제를 해결
def save_to_my_ingredients(request, prdlst_report_no=None):
    # 내원료 저장
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    if not prdlst_report_no:
        return JsonResponse({'success': False, 'error': '품목제조번호가 없습니다.'}, status=400)

    try:
        # FoodItem 객체 가져오기
        food_item = FoodItem.objects.filter(prdlst_report_no=prdlst_report_no).first()
        
        if not food_item:
            print(f" 오류: 품목제조번호 {prdlst_report_no} 에 해당하는 FoodItem이 존재하지 않습니다.")
            return JsonResponse({'success': False, 'error': '해당 품목제조번호에 대한 데이터를 찾을 수 없습니다.'}, status=404)

        print(f" FoodItem 조회 성공: {food_item.prdlst_nm} ({food_item.prdlst_report_no})")

        # MyIngredients 객체 생성
        my_ingredient = MyIngredient.objects.create(
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            prms_dt=food_item.prms_dt or "00000000",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            pog_daycnt=food_item.pog_daycnt or "0",
            frmlc_mtrqlt=food_item.frmlc_mtrqlt or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
        )

        print(f" MyIngredients 저장 완료: {my_ingredient.prdlst_nm} ({my_ingredient.prdlst_report_no})")
        return JsonResponse({'success': True, 'message': '내원료로 저장되었습니다.'})

    except Exception as e:
        print(f" 내원료 저장 중 오류 발생: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @login_required
# @csrf_exempt
# def save_field_order(request):
#     """드래그 앤 드롭 필드 순서 저장"""
#     if request.method == "POST":
#         try:
#             data = json.loads(request.body)
#             order = data.get("order", [])

#             if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
#                 return JsonResponse({'success': False, 'error': 'Invalid order format'}, status=400)

#             # LabelOrder 업데이트
#             LabelOrder.objects.update_or_create(
#                 user=request.user,
#                 defaults={'order': json.dumps(order)}
#             )
#             return JsonResponse({'success': True, 'message': '필드 순서가 저장되었습니다.'})
#         except Exception as e:
#             return JsonResponse({'success': False, 'error': str(e)}, status=500)
#     return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)