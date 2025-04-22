from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('v1.main.urls')),  # 메인 앱 URL
    path('common/', include('v1.common.urls', namespace='common')),  # common 앱 URL
    path('admin/', admin.site.urls),  # 관리자 페이지
    path('label/', include('v1.label.urls', namespace='label')),  # label 앱 URL
    path('disposition/', include('v1.disposition.urls', namespace='disposition')),  # disposition 앱 URL
    path('user-management/', include('v1.user_management.urls', namespace='user_management')),  # user_management 앱
]
