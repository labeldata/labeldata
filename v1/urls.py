from django.urls import path, include

urlpatterns = [
    # ...existing code...
    path('board/', include('v1.board.urls', namespace='board')),  # Register 'board' namespace
]