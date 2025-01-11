from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from label.models import Post, Comment, FoodType, FoodItem
from action.models import AdministrativeAction
from common.models import ApiKey, ApiEndpoint


class BaseAdmin(admin.ModelAdmin):
    """공통 설정 클래스"""
    list_per_page = 20  # 한 페이지에 표시할 항목 수


# @admin.register(Post)
# class PostAdmin(BaseAdmin):
#     list_display = ('title', 'author', 'create_date', 'modify_date')
#     readonly_fields = ('create_date', 'modify_date')  # Post 모델에 있는 필드
#     search_fields = ('title', 'author__username')
#     date_hierarchy = 'create_date'


@admin.register(Comment)
class CommentAdmin(BaseAdmin):
    list_display = ('content', 'author', 'post', 'create_date')
    readonly_fields = ('create_date',)  # Comment 모델에 있는 필드
    search_fields = ('content', 'author__username')
    date_hierarchy = 'create_date'


@admin.register(FoodType)
class FoodTypeAdmin(BaseAdmin):
    list_display = ('name', 'created_at')
    readonly_fields = ('created_at',)  # FoodType 모델에 있는 필드
    search_fields = ('name',)


@admin.register(FoodItem)
class FoodItemAdmin(BaseAdmin):
    list_display = ('product_name', 'manufacturer', 'report_date', 'category')
    search_fields = ('product_name', 'manufacturer')
    date_hierarchy = 'report_date'


@admin.register(AdministrativeAction)
class AdministrativeActionAdmin(BaseAdmin):
    list_display = ('name', 'registration_number', 'action_date')
    search_fields = ('name', 'registration_number')
    date_hierarchy = 'action_date'


@admin.register(ApiKey)
class ApiKeyAdmin(BaseAdmin):
    list_display = ('key',)
    search_fields = ('key',)


@admin.register(ApiEndpoint)
class ApiEndpointAdmin(admin.ModelAdmin):
    """Admin Interface for ApiEndpoint"""
    list_display = ('name', 'url', 'call_frequency_minutes', 'last_called_at', 'trigger_action')
    search_fields = ('name', 'url')
    readonly_fields = ('last_called_at',)

    def trigger_action(self, obj):
        """
        Renders a button to trigger API calls from the admin interface.
        """
        call_url = reverse('common:call_api_endpoint', args=[obj.id])
        return format_html(
            '<a class="button" style="color: white; background-color: #4CAF50; padding: 5px 10px; '
            'text-decoration: none; border-radius: 5px;" href="{}">Call Now</a>',
            call_url
        )
    trigger_action.short_description = 'Trigger API Action'
    trigger_action.allow_tags = True  # Explicitly allowing HTML rendering for older Django versions
