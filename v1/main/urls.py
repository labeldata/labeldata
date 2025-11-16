from django.urls import path, include
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),  # 메인 화면 (표시사항 작성 기능 포함)
    path('save/', views.save_label, name='save_label'),  # 표시사항 저장 API
    path('label/', include('v1.label.urls')),    # 제품 조회, 표시사항 관리 등 (label 앱)
    path('disposition/', include('v1.disposition.urls')),  # 행정처분 (disposition 앱)
]
