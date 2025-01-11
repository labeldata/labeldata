from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'common'

urlpatterns = [
    # 사용자 인증 관련
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # API 호출 관련
    path('call_api/<int:endpoint_id>/', views.call_api_endpoint, name='call_api_endpoint'),
]
