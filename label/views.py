import json
from venv import logger  #지우지 말 것
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import FoodItem, MyLabel, MyProduct, MyIngredient, Allergen
from .forms import LabelCreationForm
from django.core.paginator import Paginator
from django.http import JsonResponse
import uuid


# @login_required
# def post_create(request):
#     """게시글 생성"""
#     if request.method == 'POST':
#         form = PostForm(request.POST)
#         if form.is_valid():
#             post = form.save(commit=False)
#             post.author = request.user
#             post.save()
#             messages.success(request, "게시글이 생성되었습니다.")
#             return redirect('label:post_list')
#     else:
#         form = PostForm()
#     return render(request, 'label/post_form.html', {'form': form})


# @login_required
# def post_edit(request, pk):
#     """게시글 수정"""
#     post = get_object_or_404(Post, pk=pk)
#     if request.user != post.author:
#         messages.error(request, "수정 권한이 없습니다.")
#         return redirect('label:post_list')

#     if request.method == 'POST':
#         form = PostForm(request.POST, instance=post)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "게시글이 수정되었습니다.")
#             return redirect('label:post_detail', pk=post.pk)
#     else:
#         form = PostForm(instance=post)
#     return render(request, 'label/post_form.html', {'form': form})


# @login_required
# def post_delete(request, pk):
#     """게시글 삭제"""
#     post = get_object_or_404(Post, pk=pk)
#     if request.user != post.author:
#         messages.error(request, "삭제 권한이 없습니다.")
#         return redirect('label:post_list')

#     if request.method == 'POST':
#         post.delete()
#         messages.success(request, "게시글이 삭제되었습니다.")
#         return redirect('label:post_list')

#     return render(request, 'label/post_confirm_delete.html', {'post': post})


# def post_list(request):
#     """게시글 목록"""
#     search_query = request.GET.get('q', '')
#     posts = Post.objects.filter(title__icontains=search_query) if search_query else Post.objects.all()
#     posts = posts.order_by('-create_date')
#     paginator = Paginator(posts, 10)
#     page_obj = paginator.get_page(request.GET.get('page'))

#     return render(request, 'label/post_list.html', {
#         'page_obj': page_obj,
#         'search_query': search_query,
#     })


# def post_detail(request, pk):
#     """게시글 상세보기"""
#     post = get_object_or_404(Post, pk=pk)
#     return render(request, 'label/post_detail.html', {'post': post})


# @login_required
# def comment_create(request, pk):
#     """댓글 생성"""
#     post = get_object_or_404(Post, pk=pk)
#     if request.method == 'POST':
#         form = CommentForm(request.POST)
#         if form.is_valid():
#             comment = form.save(commit=False)
#             comment.post = post
#             comment.author = request.user
#             comment.save()
#             messages.success(request, "댓글이 작성되었습니다.")
#             return redirect('label:post_detail', pk=pk)
#     else:
#         form = CommentForm()
#     return render(request, 'label/comment_form.html', {'form': form})


# @login_required
# def comment_edit(request, comment_id):
#     """댓글 수정"""
#     comment = get_object_or_404(Comment, pk=comment_id)
#     if request.user != comment.author:
#         messages.error(request, "수정 권한이 없습니다.")
#         return redirect('label:post_list')

#     if request.method == 'POST':
#         form = CommentForm(request.POST, instance=comment)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "댓글이 수정되었습니다.")
#             return redirect('label:post_detail', pk=comment.post.pk)
#     else:
#         form = CommentForm(instance=comment)
#     return render(request, 'label/comment_form.html', {'form': form})


# @login_required
# def comment_delete(request, comment_id):
#     """댓글 삭제"""
#     comment = get_object_or_404(Comment, pk=comment_id)
#     if request.user != comment.author:
#         messages.error(request, "삭제 권한이 없습니다.")
#         return redirect('label:post_list')

#     if request.method == 'POST':
#         comment.delete()
#         messages.success(request, "댓글이 삭제되었습니다.")
#         return redirect('label:post_detail', pk=comment.post.pk)

#     return render(request, 'label/comment_confirm_delete.html', {'comment': comment})


# def food_item_list(request):
    # """제품 목록"""
    # '''
    # 검색 조건 추가 및 페이징 개선
    # 1. 검색 기능 추가: prdlst_nm로 제품명을 검색할 수 있도록 조건 추가.
    # 2. 페이지네이션 범위 계산: current_page를 기준으로 앞뒤 5페이지 범위로 설정.
    # 3. 템플릿에서 page_range와 검색 조건 search_query를 활용 가능하도록 컨텍스트에 포함.
    # '''

    # # 페이지당 항목 수 동적 처리
    # items_per_page = request.GET.get('items_per_page', 10)  # 기본값 10
    # try:
    #     items_per_page = int(items_per_page)
    # except ValueError:
    #     items_per_page = 10

    # search_query = request.GET.get('prdlst_nm', '').strip()
    # manufacturer_query = request.GET.get('bssh_nm', '').strip()

    # # 검색 조건
    # # 제품명
    # search_query = request.GET.get('prdlst_nm', '').strip()
    # # 제조사명
    # manufacturer_query = request.GET.get('bssh_nm', '').strip()

    # # 검색 조건 없는 경우 모든 데이터 조회
    # items = FoodItem.objects.filter(
    #     prdlst_nm__icontains=search_query, 
    #     bssh_nm__icontains=manufacturer_query
    # ).order_by('-last_updt_dtm')

    # #items = items.order_by('-last_updt_dtm')  # 최신순 정렬

    # paginator = Paginator(items, items_per_page)
    # current_page = request.GET.get('page', 1)
    # page_obj = paginator.get_page(current_page)

    # # 페이지네이션 범위 계산
    # current_page_num = page_obj.number
    # start_range = max(current_page_num - 5, 1)
    # end_range = min(current_page_num + 5, paginator.num_pages) + 1

    # page_range = range(start_range, end_range)

    # #print(page_obj)

    # return render(request, 'label/food_item_list.html', {
    #     'page_obj': page_obj,
    #     'page_range': page_range,
    #     'search_query': search_query,
    #     'items_per_page': items_per_page,
    # })


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
    my_product = MyProduct.objects.filter(prdlst_report_no=prdlst_report_no, user=request.user).first()

    return render(request, 'label/food_item_detail.html', {'item': my_product if my_product else food_item,})


@login_required
def save_my_product(request, prdlst_report_no):
    # FoodItem 데이터를 MyProduct로 복사
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    try:
        # FoodItem 조회
        food_item = get_object_or_404(FoodItem, prdlst_report_no=prdlst_report_no)
        print(f"🔹 FoodItem 찾음: {food_item.prdlst_nm} ({food_item.prdlst_report_no})")

        # 이미 존재하는 경우 체크
        existing_product = MyProduct.objects.filter(prdlst_report_no=prdlst_report_no, user=request.user).first()
        if existing_product:
            print("🔸 이미 내제품에 존재하는 제품")
            return JsonResponse({'success': False, 'error': '이미 내제품에 저장된 항목입니다.'}, status=400)

        # 고유키 생성
        unique_key = uuid.uuid4()
        print(f"🟢 새로운 Unique Key 생성: {unique_key}")

        # MyProduct 생성
        my_product = MyProduct.objects.create(
            user=request.user,
            unique_key=unique_key,
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
            induty_cd_nm=food_item.induty_cd_nm or "미정",
            hieng_lntrt_dvs_yn=food_item.hieng_lntrt_dvs_yn or "N",
            qlity_mntnc_tmlmt_daycnt=food_item.qlity_mntnc_tmlmt_daycnt or "0",
            content_weight="",
            manufacturer_address="",
            storage_method="",
            label_created=False
        )

        print(f"✅ MyProduct 저장 완료: {my_product.prdlst_nm} (Key: {my_product.unique_key})")
        return JsonResponse({'success': True, 'message': '내제품으로 저장되었습니다.'})

    except Exception as e:
        print(f"❌ MyProduct 저장 실패: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def my_product_list(request):
    # 내제품 관리 페이지
    products = MyProduct.objects.filter(user=request.user).order_by("-updated_at")

    # 🔹 unique_key가 없는 데이터가 있다면 UUID 자동 생성
    for product in products:
        if not product.unique_key:
            product.unique_key = uuid.uuid4()
            product.save()

    return render(request, "label/my_products_list.html", {"products": products})


@login_required
def label_creation(request, unique_key):
    # 표시사항 작성 및 수정
    my_product = get_object_or_404(MyProduct, unique_key=unique_key, user=request.user)
    
    # 기존 Label이 있는지 확인
    label, created = Label.objects.get_or_create(my_product=my_product)
    
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
        "allergens": Allergen.objects.all(), # ✅ 알레르기 물질 리스트 전달
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
            print(f"❌ 오류: 품목제조번호 {prdlst_report_no} 에 해당하는 FoodItem이 존재하지 않습니다.")
            return JsonResponse({'success': False, 'error': '해당 품목제조번호에 대한 데이터를 찾을 수 없습니다.'}, status=404)

        print(f"✅ FoodItem 조회 성공: {food_item.prdlst_nm} ({food_item.prdlst_report_no})")

        # MyIngredients 객체 생성
        my_ingredient = MyIngredients.objects.create(
            prdlst_report_no=food_item.prdlst_report_no,
            prdlst_nm=food_item.prdlst_nm or "미정",
            bssh_nm=food_item.bssh_nm or "미정",
            prms_dt=food_item.prms_dt or "00000000",
            prdlst_dcnm=food_item.prdlst_dcnm or "미정",
            pog_daycnt=food_item.pog_daycnt or "0",
            frmlc_mtrqlt=food_item.frmlc_mtrqlt or "미정",
            rawmtrl_nm=food_item.rawmtrl_nm or "미정",
        )

        print(f"✅ MyIngredients 저장 완료: {my_ingredient.prdlst_nm} ({my_ingredient.prdlst_report_no})")
        return JsonResponse({'success': True, 'message': '내원료로 저장되었습니다.'})

    except Exception as e:
        print(f"❌ 내원료 저장 중 오류 발생: {str(e)}")
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