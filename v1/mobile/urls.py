from django.urls import path
from . import views

app_name = 'mobile'

urlpatterns = [
    # 기기
    path('device/register/', views.register_device, name='register_device'),

    # 인증
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),

    # 부적합 피드
    path('news/', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),

    # 알림 규칙
    path('devices/<str:device_id>/rules/', views.rules_list, name='rules_list'),
    path('devices/<str:device_id>/rules/<int:rule_id>/', views.rule_detail, name='rule_detail'),

    # 보관함
    path('devices/<str:device_id>/bookmarks/', views.bookmarks_list, name='bookmarks_list'),
    path('devices/<str:device_id>/bookmarks/<int:bookmark_id>/', views.bookmark_detail, name='bookmark_detail'),

    # 알림 내역
    path('devices/<str:device_id>/notifications/', views.notifications_list, name='notifications_list'),
    path('devices/<str:device_id>/notifications/read-all/', views.notification_read_all, name='notification_read_all'),
    path('devices/<str:device_id>/notifications/<int:noti_id>/read/', views.notification_read, name='notification_read'),
    path('devices/<str:device_id>/notifications/<int:noti_id>/', views.notification_delete, name='notification_delete'),

    # 앱 버전
    path('version-check/', views.version_check, name='version_check'),
]
