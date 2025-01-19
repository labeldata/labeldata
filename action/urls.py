from django.urls import path
from . import views

app_name = 'action'

urlpatterns = [
    path('list/', views.action_list, name='action_list'),
    path('create/', views.action_create, name='action_create'),
    path('<int:action_id>/detail/', views.action_detail, name='action_detail'),
    path('<int:action_id>/delete/', views.action_delete, name='action_delete'),
    path('crawl/<int:setting_id>/', views.crawl_actions, name='crawl_actions'),
]
