from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

from v1.common.media_access import protected_media_serve
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
# 업로드 파일(/media/) 서빙
# 주의: django.conf.urls.static.static()은 DEBUG=False일 때 내부적으로 빈 리스트를
# 반환한다(Django 자체 안전장치). 운영 서버는 DEBUG=False라서 그 호출로는
# MEDIA_URL 라우팅이 전혀 등록되지 않아 업로드 파일이 404가 났었다(PA Static files
# 매핑에도 /media/가 없으면 완전히 접근 불가). DEBUG 여부와 무관하게 등록한다.
#
# 다만 예전처럼 static_serve 를 그대로 걸면 인증 없이 누구나 파일을 받아갈 수 있다.
# 협력업체 규격서·성적서가 URL 만 알면 노출되고 공유를 해제해도 막히지 않았다.
# 권한을 확인하는 protected_media_serve 를 대신 사용한다.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', protected_media_serve, name='protected_media'),
]

# 커스텀 에러 핸들러 (DEBUG=False일 때만 작동)
handler404 = 'v1.common.views.custom_404'
handler403 = 'v1.common.views.custom_403'
handler500 = 'v1.common.views.custom_500'
