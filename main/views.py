from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from label.models import FoodItem
from action.models import AdministrativeAction
from label.forms import LabelForm

@login_required
def home(request):
    """메인 화면 및 통합 검색"""
    search_query = request.GET.get('q', '')
    # food_items = FoodItem.objects.filter(product_name__icontains=search_query).order_by('-report_date') # product_name, report_date 변경경
    food_items = FoodItem.objects.filter(prdlst_nm__icontains=search_query).order_by('-last_updt_dtm')
    actions = AdministrativeAction.objects.filter(action_name__icontains=search_query).order_by('-action_date')

    # 페이징 처리
    paginator_food = Paginator(food_items, 5)
    paginator_actions = Paginator(actions, 5)
    food_page = paginator_food.get_page(request.GET.get('food_page'))
    action_page = paginator_actions.get_page(request.GET.get('action_page'))

    return render(request, 'main/home.html', {
        'food_page': food_page,
        'action_page': action_page,
        'search_query': search_query,
    })

@login_required
def food_item_detail(request, pk):
    """제품 상세 정보와 행정처분 표시"""
    food_item = get_object_or_404(FoodItem, pk=pk)
    actions = AdministrativeAction.objects.filter(registration_number=food_item.registration_number)
    return render(request, 'main/food_item_detail.html', {'food_item': food_item, 'actions': actions})

@login_required
def label_create_or_edit(request, pk=None):
    """라벨 생성 및 수정"""
    label = get_object_or_404(FoodItem, pk=pk) if pk else None

    if request.method == "POST":
        form = LabelForm(request.POST, instance=label)
        if form.is_valid():
            form.save()
            return redirect('main:home')
    else:
        form = LabelForm(instance=label)

    return render(request, 'main/label_form.html', {'form': form})
