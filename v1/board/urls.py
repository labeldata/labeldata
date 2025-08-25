from django.urls import path
from . import views

app_name = 'board'

urlpatterns = [
    path('', views.BoardListView.as_view(), name='list'),
    path('<int:pk>/', views.BoardDetailView.as_view(), name='detail'),
    path('create/', views.BoardCreateView.as_view(), name='create'),
    path('<int:pk>/update/', views.BoardUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.BoardDeleteView.as_view(), name='delete'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:pk>/edit/', views.edit_comment, name='edit_comment'),
    path('comment/<int:pk>/delete/', views.delete_comment, name='delete_comment'),
    path('<int:pk>/download/', views.download_file, name='download_file'),
]