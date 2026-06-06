from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.http import HttpResponse
from v1.common import views as common_views  # common views import 추가

def robots_txt(request):
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /user-management/\n"
        "Disallow: /api/\n"
    )
    return HttpResponse(content, content_type="text/plain")

urlpatterns = [
    path('sitemap.xml', TemplateView.as_view(template_name='sitemap.xml', content_type='application/xml'), name='sitemap'),
    path('robots.txt', cache_page(60 * 60 * 24)(robots_txt), name='robots'),

    path('', include('v1.main.urls')),  # 메인 앱 URL
    path('dashboard/', common_views.dashboard_view, name='dashboard'),  # 관리자 통계 대시보드
    path('common/', include('v1.common.urls', namespace='common')),  # common 앱 URL
    path('lbdt-manage/', admin.site.urls),  # 관리자 페이지 (URL 난독화)
    path('label/', include('v1.label.urls', namespace='label')),  # label 앱 URL
    path('disposition/', include('v1.disposition.urls', namespace='disposition')),  # disposition 앱 URL
    path('user-management/', include('v1.user_management.urls', namespace='user_management')),  # user_management 앱
    path('board/', include('v1.board.urls', namespace='board')),  # Register 'board' namespace
    
    # 제품 관리 + BOM 앱 URL (v1으로 통합 완료, 레거시 URL 경로 유지)
    path('products/', include('v1.products.urls', namespace='products')),
    # v2 템플릿 호환: /v2/products/ 경로로 동일한 뷰들을 접근 가능하게 alias 추가
    path('v2/products/', include(('v1.products.urls', 'products'), namespace='products_v2')),
    path('bom/', include('v1.bom.urls', namespace='bom')),
    path('regulatory/', include('v1.regulatory.urls', namespace='regulatory')),  # 부적합.처분 알림
    path('vendor/', include('v1.products.vendor_urls', namespace='vendor')),     # 협력사 매직링크 포털
    # 마이그레이션은 자동으로 처리됨 (표시사항 저장 시 제품 자동 생성)

    # 라벨 에디터 API
    path('api/label-editor/', include('v1.label_editor.urls', namespace='label_editor')),

    # 모바일 앱 API
    path('api/mobile/', include('v1.mobile.urls', namespace='mobile')),
]

# 정적 파일 서빙 (개발 환경과 에러 페이지 테스트를 위해 항상 활성화)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 커스텀 에러 핸들러 (DEBUG=False일 때만 작동)
handler404 = 'v1.common.views.custom_404'
handler403 = 'v1.common.views.custom_403'
handler500 = 'v1.common.views.custom_500'
