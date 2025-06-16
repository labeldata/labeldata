from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from v1.common import views as common_views  # common views import 추가

urlpatterns = [
    path('', include('v1.main.urls')),  # 메인 앱 URL
    path('common/', include('v1.common.urls', namespace='common')),  # common 앱 URL
    path('admin/', admin.site.urls),  # 관리자 페이지
    path('label/', include('v1.label.urls', namespace='label')),  # label 앱 URL
    path('disposition/', include('v1.disposition.urls', namespace='disposition')),  # disposition 앱 URL
    path('user-management/', include('v1.user_management.urls', namespace='user_management')),  # user_management 앱
    path('board/', include('v1.board.urls', namespace='board')),  # Register 'board' namespace
    
    # 에러 페이지 테스트용 URL (개발 환경에서 커스텀 에러 페이지 확인용)
    path('test/404/', common_views.test_404, name='test_404'),
    path('test/403/', common_views.test_403, name='test_403'),
    path('test/500/', common_views.test_500, name='test_500'),
]

# 정적 파일 서빙 (개발 환경과 에러 페이지 테스트를 위해 항상 활성화)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 커스텀 에러 핸들러 (DEBUG=False일 때만 작동)
handler404 = 'v1.common.views.custom_404'
handler403 = 'v1.common.views.custom_403'
handler500 = 'v1.common.views.custom_500'
