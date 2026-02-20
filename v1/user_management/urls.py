# user_management/urls.py
from django.urls import path
from . import views

app_name = 'user_management'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('signup-done/', views.signup_done_view, name='signup_done'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('password-reset-request/', views.password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/document/delete/<int:pk>/', views.delete_company_document, name='delete_company_document'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
]

