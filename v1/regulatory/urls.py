from django.urls import path
from v1.regulatory import views

app_name = 'regulatory'

urlpatterns = [
    # 메인 목록 (Split View)
    path('', views.news_list, name='list'),
    # 상세 (독립 페이지)
    path('<int:pk>/', views.news_detail, name='detail'),
    # API
    path('api/unread-count/', views.unread_count_api, name='unread_count'),
    path('api/mark-read/', views.mark_as_read, name='mark_read'),
    path('api/mark-false-positive/', views.mark_false_positive, name='mark_false_positive'),
    path('api/save-action/', views.save_match_action, name='save_action'),
]
