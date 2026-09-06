from django.urls import path
from . import views

app_name = 'v1.common'

urlpatterns = [
    path('logout/', views.logout_view, name='logout'),
    path('api-endpoint/<int:pk>/call/', views.call_api_endpoint, name='call_api_endpoint'),
    # 표 화면이 "이 사람은 칸을 이 순서로 본다" 를 남기는 자리
    path('grid-order/', views.grid_order_save, name='grid_order_save'),
]
