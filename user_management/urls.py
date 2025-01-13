# user_management/urls.py
from django.urls import path
from . import views

app_name = 'user_management'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
]
