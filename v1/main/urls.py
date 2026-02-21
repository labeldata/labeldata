from django.urls import path, include
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),                               # 루트: 인증 → v2 대시보드, 비인증 → v1 홈
    path('v1/home/', views.home_v1, name='home_v1'),                 # V1 홈 (표시사항 작성 기능 직접 접근)
    path('home/', views.home_dashboard, name='home_dashboard'),      # V2 메인 대시보드
    path('home-switch/', views.home_switcher, name='home_switcher'), # V1↔V2 홈화면 전환 페이지
    path('save-label/', views.save_label, name='save_label'),        # 표시사항 저장 API
    path('label/', include('v1.label.urls')),    # 제품 조회, 표시사항 관리 등 (label 앱)
    path('disposition/', include('v1.disposition.urls')),  # 행정처분 (disposition 앱)
]
