from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('v1.main.urls')),  # 메인 앱 URL
    path('common/', include('v1.common.urls', namespace='common')),  # common 앱 URL
    path('admin/', admin.site.urls),  # 관리자 페이지
    path('label/', include('v1.label.urls', namespace='label')),  # label 앱 URL
    path('disposition/', include('v1.disposition.urls', namespace='disposition')),  # disposition 앱 URL
    path('user-management/', include('v1.user_management.urls', namespace='user_management')),  # user_management 앱
]

# 개발 환경에서 static 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
