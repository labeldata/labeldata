from django.urls import path, include
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),  # 메인 화면
    path('label/', include('label.urls')),    # 제품 조회, 표시사항 관리 등 (label 앱)
    path('disposition/', include('disposition.urls')),  # 행정처분 (disposition 앱)
]
