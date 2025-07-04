from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'v1.common'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='common/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api-endpoint/<int:pk>/call/', views.call_api_endpoint, name='call_api_endpoint'),
    
    # 에러 페이지 테스트용 URL
    path('test/404/', views.test_404, name='test_404'),
    path('test/403/', views.test_403, name='test_403'),
    path('test/500/', views.test_500, name='test_500'),
]
