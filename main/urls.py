from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),  # 메인 화면
    path('food-item/<int:pk>/', views.food_item_detail, name='food_item_detail'),  # 제품 상세 정보
    path('label/create/', views.label_create_or_edit, name='label_create'),  # 라벨 생성
    path('label/<int:pk>/edit/', views.label_create_or_edit, name='label_edit'),  # 라벨 수정
]
