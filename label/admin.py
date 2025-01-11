from django.contrib import admin
from .models import Post

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "is_api_data", "create_date")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["total_api_posts"] = Post.objects.filter(is_api_data=True).count()
        return super().changelist_view(request, extra_context=extra_context)
