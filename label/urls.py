from django.urls import path
from . import views

app_name = 'label'

urlpatterns = [
    path('food-items/', views.food_item_list, name='food_item_list'),  # 제품 목록
    path('', views.post_list, name='post_list'),
    path('label/create/', views.label_create_or_edit, name='label_create'),  # 표시사항 등록
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),
    path('post/<int:pk>/comment/', views.comment_create, name='comment_create'),
    path('comment/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
]
