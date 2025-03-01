from django.urls import path
from . import views

app_name = 'label'

urlpatterns = [
    # 제품 목록 및 상세
    path('food-items/', views.food_item_list, name='food_item_list'),
    path('food-item-detail/<str:prdlst_report_no>/', views.food_item_detail, name='food_item_detail'),
    path('fetch-food-item/<str:prdlst_report_no>/', views.fetch_food_item, name='fetch_food_item'),

    # 내 표시사항 관리
    path('my-labels/', views.my_label_list, name='my_label_list'),
    # 내 표시사항으로 저장 (saveto_my_label 뷰 호출)
    path('saveto_my_label/<str:prdlst_report_no>/', views.saveto_my_label, name='saveto_my_label'),

    # 표시사항 작성
    path("label/create/", views.label_creation, name="label_creation"),
    # path('label-creation/<uuid:unique_key>/', views.label_creation, name='label_creation_uuid'),
    path('label-creation/<int:label_id>/', views.label_creation, name='label_creation'),
    path('ingredient-popup/', views.ingredient_popup, name='ingredient_popup'),
    
    # 내원료 관리
    path('save-to-my-ingredients/<str:prdlst_report_no>/', views.save_to_my_ingredients, name='save_to_my_ingredients'),
    path('check-my-ingredients/', views.check_my_ingredients, name='check_my_ingredients'),
    path('my-ingredient-list/', views.my_ingredient_list, name='my_ingredient_list'),
    path('my-ingredient-detail/<int:ingredient_id>/', views.my_ingredient_detail, name='my_ingredient_detail'),
    path('my-ingredient-detail/', views.my_ingredient_detail, name='my_ingredient_create'),
    path('save-ingredients/<int:label_id>/', views.save_ingredients_to_label, name='save_ingredients_to_label'),
    path('save-my-ingredient/', views.save_my_ingredient, name='save_my_ingredient'),
    path('save-ingredients-to-label/<int:label_id>/', views.save_ingredients_to_label, name='save_ingredients_to_label'),
    path('search-ingredient-add-row/', views.search_ingredient_add_row, name='search_ingredient_add_row'),
    #path('delete-my-ingredient/<int:my_ingredient_id>/', views.delete_my_ingredient, name='delete_my_ingredient'),
    # verify_ingredients URL 추가
    path('verify-ingredients/', views.verify_ingredients, name='verify_ingredients'),
    
]
