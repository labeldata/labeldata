from django.contrib import admin
from django.urls import reverse  # reverse는 이미 import되어 있음
from django.utils.html import format_html  # format_html import 추가
from .models import ApiKey, ApiEndpoint


class BaseAdmin(admin.ModelAdmin):
    # 공통 설정 클래스
    list_per_page = 20  # 한 페이지에 표시할 항목 수

@admin.register(ApiKey)
class ApiKeyAdmin(BaseAdmin):
    # ApiKey 모델 관리
    list_display = ('key',)
    search_fields = ('key',)

@admin.register(ApiEndpoint)
class ApiEndpointAdmin(BaseAdmin):
    # ApiEndpoint 모델 관리
    list_display = ('name', 'service_name', 'short_url', 'start_date', 'last_called_at', 'last_start_position', 'trigger_action')
    search_fields = ('name', 'url', 'service_name')
    readonly_fields = ('last_called_at',)

    def short_url(self, obj):
        # URL을 일정 길이(예: 40자)까지만 표시하고, 전체는 툴팁으로 보여줌. 길면 스크롤 가능하게 스타일 적용
        max_len = 40
        url = obj.url or ""
        display = url if len(url) <= max_len else url[:max_len] + "..."
        return format_html(
            '<div style="max-width:320px; overflow-x:auto; white-space:nowrap;" title="{}">{}</div>',
            url, display
        )
    short_url.short_description = 'URL'

    def trigger_action(self, obj):
        # Renders a button to trigger API calls from the admin interface.
        call_url = reverse('common:call_api_endpoint', args=[obj.id])
        return format_html(
            '<a class="button" style="color: white; background-color: #4CAF50; padding: 5px 10px; '
            'text-decoration: none; border-radius: 5px;" href="{}">Call Now</a>',
            call_url
        )
    trigger_action.short_description = 'Trigger API Action'
