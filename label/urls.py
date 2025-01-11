from django.urls import path
from . import views

app_name = 'label'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:post_id>/delete/', views.post_delete, name='post_delete'),
    path('post/<int:post_id>/comment/', views.comment_create, name='comment_create'),
    path('comment/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    path('update-food-types/', views.update_food_types, name='update_food_types'), #API 뷰뷰
    path('post/<int:post_id>/like/', views.post_like, name='post_like'),
    path('post/<int:post_id>/unlike/', views.post_unlike, name='post_unlike'),
]