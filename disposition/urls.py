from django.urls import path
from . import views

app_name = 'v1.disposition'

urlpatterns = [
    path('list/', views.disposition_list, name='list'),
    path('create/', views.disposition_create, name='create'),
    path('<int:disposition_id>/detail/', views.disposition_detail, name='detail'),
    path('<int:disposition_id>/delete/', views.disposition_delete, name='delete'),
    path('crawl/<int:setting_id>/', views.crawl_dispositions, name='crawl_dispositions'),
]
