from django.urls import path
from . import views

app_name = 'label_editor'

urlpatterns = [
    path('<int:label_id>/layout/', views.layout_get, name='layout_get'),
    path('<int:label_id>/layout/save/', views.layout_save, name='layout_save'),
    path('<int:label_id>/images/', views.image_list, name='image_list'),
    path('<int:label_id>/images/upload/', views.image_upload, name='image_upload'),
]
