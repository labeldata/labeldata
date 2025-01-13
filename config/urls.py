# 수정된 config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('main.urls')),  # 메인 앱 URL
    path('common/', include('common.urls', namespace='common')),  # common 앱 URL
    path('admin/', admin.site.urls),  # 관리자 페이지
    path('label/', include('label.urls', namespace='label')),  # label 앱 URL
    path('action/', include('action.urls', namespace='action')),  # action 앱 URL
    path('user-management/', include('user_management.urls', namespace='user_management')),  # user_management 앱
]
