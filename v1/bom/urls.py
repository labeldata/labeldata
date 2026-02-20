from django.urls import path
from django.shortcuts import render
from . import views

app_name = 'bom'

def bom_index(request):
    """BOM 메인 페이지 - 안내 메시지"""
    return render(request, 'products/bom_index.html', {'message': 'BOM 관리를 사용하려면 제품 버전을 선택하세요.'})

urlpatterns = [
    path('', bom_index, name='index'),
    path('label/<int:label_id>/workspace/', views.bom_workspace, name='bom_workspace'),
    path('label/<int:label_id>/editor/', views.bom_editor, name='bom_editor'),
    path('api/label/<int:label_id>/data/', views.bom_data_api, name='bom_data_api'),
    path('api/label/<int:label_id>/save/', views.bom_save_api, name='bom_save_api'),
    path('api/label/<int:label_id>/load-from-label/', views.bom_load_from_label_api, name='bom_load_from_label'),
    path('api/label/<int:label_id>/load/', views.api_load_from_label, name='api_load_from_label'),
    path('api/ingredients/search/', views.api_ingredient_search, name='api_ingredient_search'),
    path('api/ingredients/<int:ingredient_id>/', views.api_ingredient_detail, name='api_ingredient_detail'),
    path('api/palette/', views.api_palette_list, name='api_palette_list'),
    path('api/label/<int:label_id>/nutrition/', views.bom_calculate_nutrition, name='bom_calculate_nutrition'),
    path('api/autocomplete/', views.bom_autocomplete, name='bom_autocomplete'),
]
