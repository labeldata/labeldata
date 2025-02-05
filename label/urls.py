from django.urls import path
from . import views

app_name = 'label'

urlpatterns = [
    # 제품 목록 및 상세
    path('food-items/', views.food_item_list, name='food_item_list'),
    path('food-item-detail/<str:prdlst_report_no>/', views.food_item_detail, name='food_item_detail'),

    # 게시글
    #path('', views.post_list, name='post_list'),
    # path('post/create/', views.post_create, name='post_create'),
    # path('post/<int:pk>/', views.post_detail, name='post_detail'),
    # path('post/<int:pk>/edit/', views.post_edit, name='post_edit'),
    # path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),
    # path('post/<int:pk>/comment/', views.comment_create, name='comment_create'),
    # path('comment/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    # path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),

    # 내 표시사항 관리
    path('my-labels/', views.my_label_list, name='my_label_list'),
    # 내 표시사항으로 저장 (saveto_my_label 뷰 호출)
    path('saveto_my_label/<str:prdlst_report_no>/', views.saveto_my_label, name='saveto_my_label'),


    # 표시사항 작성
    path("label/create/", views.label_creation, name="label_creation"),
    path('label-creation/<uuid:unique_key>/', views.label_creation, name='label_creation'),

    # 기타 기능
    # path('save-to-my-ingredients/<str:prdlst_report_no>/', views.save_to_my_ingredients, name='save_to_my_ingredients'),
    # path('save-field-order/', views.save_field_order, name='save_field_order'),
]
