from django.urls import path, include
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),                               # 루트: V2 신규홈(home_dashboard)으로 이동
    path('v1/home/', views.home_v1, name='home_v1'),                 # V1 기존홈 (표시사항 작성 기능 직접 접근) — 유일한 기존홈 URL
    path('home/', views.home_dashboard, name='home_dashboard'),      # V2 신규홈 메인 대시보드 (메인 주소)
    path('save-label/', views.save_label, name='save_label'),        # 표시사항 저장 API
    path('label/', include('v1.label.urls')),    # 제품 조회, 표시사항 관리 등 (label 앱)
    path('disposition/', include('v1.disposition.urls')),  # 행정처분 (disposition 앱)
]
