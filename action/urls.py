from django.urls import path
from . import views

app_name = 'action'

urlpatterns = [
    path('list/', views.action_list, name='action_list'),  # 액션 리스트 페이지
    path('create/', views.action_create, name='action_create'),  # 액션 생성 페이지
    path('<int:action_id>/detail/', views.action_detail, name='action_detail'),  # 액션 상세 페이지
    path('<int:action_id>/delete/', views.action_delete, name='action_delete'),  # 액션 삭제
]
