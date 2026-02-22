from django.urls import path
from . import views

app_name = 'v1.common'

urlpatterns = [
    path('logout/', views.logout_view, name='logout'),
    path('api-endpoint/<int:pk>/call/', views.call_api_endpoint, name='call_api_endpoint'),
]
