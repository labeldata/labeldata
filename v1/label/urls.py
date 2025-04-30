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
    path('bulk-copy-labels/', views.bulk_copy_labels, name='bulk_copy_labels'),
    path('bulk-delete-labels/', views.bulk_delete_labels, name='bulk_delete_labels'),
    path('save-to-my-label/<str:prdlst_report_no>/', views.save_to_my_label, name='save_to_my_label'),

    # 표시사항 작성
    path("label/create/", views.label_creation, name="label_creation"),
    path('label-creation/<int:label_id>/', views.label_creation, name='label_creation'),
    path('ingredient-popup/', views.ingredient_popup, name='ingredient_popup'),
    path('nutrition-popup/', views.nutrition_calculator_popup, name='nutrition_popup'),
    path('nutrition-calculator-popup/', views.nutrition_calculator_popup, name='nutrition_calculator_popup'),
    path('save-nutrition/', views.save_nutrition, name='save_nutrition'),
    path('duplicate/<int:label_id>/', views.duplicate_label, name='duplicate_label'),
    path('delete/<int:label_id>/', views.delete_label, name='delete_label'),
    path('phrases/manage/', views.manage_phrases, name='manage_phrase'),
    path('phrases/reorder/', views.reorder_phrases, name='reorder_phrases'),
    path('phrases/', views.phrase_popup, name='phrase_popup'),
    path('phrases/suggestions/', views.phrase_suggestions, name='phrase_suggestions'),  # 추가
    path('preview/', views.preview_popup, name='preview_popup'),  
    path('food-types-by-group/', views.food_types_by_group, name='food_types_by_group'),
    path('get-food-group/', views.get_food_group, name='get_food_group'),
    path('food-type-settings/', views.food_type_settings, name='food_type_settings'),
    path('save_preview_settings/', views.save_preview_settings, name='save_preview_settings'),

    # 내원료 관리
    path('save-to-my-ingredients/<str:prdlst_report_no>/', views.save_to_my_ingredients, name='save_to_my_ingredients'),
    path('check-my-ingredient/', views.check_my_ingredient, name='check_my_ingredient'),
    path('register-my-ingredient/', views.register_my_ingredient, name='register_my_ingredient'),
    path('my-ingredient-list/', views.my_ingredient_list, name='my_ingredient_list'),
    path('my-ingredient-list-combined/', views.my_ingredient_list_combined, name='my_ingredient_list_combined'),
    path('my-ingredient-detail/<int:ingredient_id>/', views.my_ingredient_detail, name='my_ingredient_detail'),
    path('my-ingredient-detail/', views.my_ingredient_detail, name='my_ingredient_create'),
    path('delete-my-ingredient/<int:ingredient_id>/', views.delete_my_ingredient, name='delete_my_ingredient'),
    path('save-ingredients-to-label/<int:label_id>/', views.save_ingredients_to_label, name='save_ingredients_to_label'),
    path('search-ingredient-add-row/', views.search_ingredient_add_row, name='search_ingredient_add_row'),
    path('verify-ingredients/', views.verify_ingredients, name='verify_ingredients'),
    path('my-ingredient-table-partial/', views.my_ingredient_table_partial, name='my_ingredient_table_partial'),
    path('api/food-items/count/', views.food_items_count, name='food_items_count'),
]