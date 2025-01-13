from django.urls import path
from . import views

app_name = 'action'

urlpatterns = [
    path('list/', views.action_list, name='action_list'),  # 행정처분 목록
    path('create/', views.action_create, name='action_create'),  # 행정처분 생성
    path('<int:action_id>/detail/', views.action_detail, name='action_detail'),  # 행정처분 상세
    path('<int:action_id>/delete/', views.action_delete, name='action_delete'),  # 행정처분 삭제
]
