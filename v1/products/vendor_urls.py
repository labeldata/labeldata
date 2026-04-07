from django.urls import path
from . import vendor_views

app_name = 'vendor'

urlpatterns = [
    # ⚠️ 중요: 정확한 경로를 먼저 정의 (동적 경로는 나중에)
    path('upload/expired/', vendor_views.vendor_expired_view, name='upload_expired'),
    path('upload/complete/', vendor_views.vendor_complete_view, name='upload_complete'),
    # 동적 경로 (마지막에)
    path('upload/<str:token>/submit/', vendor_views.vendor_submit_view, name='upload_submit'),
    path('upload/<str:token>/', vendor_views.vendor_upload_view, name='upload_form'),
]