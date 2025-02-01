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
    list_display = ('name', 'service_name', 'url', 'call_frequency_minutes', 'last_called_at', 'trigger_action')
    search_fields = ('name', 'url', 'service_name')
    readonly_fields = ('last_called_at',)

    def trigger_action(self, obj):
        
        # Renders a button to trigger API calls from the admin interface.
        
        # reverse 함수를 사용하여 URL 생성
        call_url = reverse('common:call_api_endpoint', args=[obj.id])
        # print(self, obj)
        # format_html로 안전한 HTML 렌더링
        return format_html(
            '<a class="button" style="color: white; background-color: #4CAF50; padding: 5px 10px; '
            'text-decoration: none; border-radius: 5px;" href="{}">Call Now</a>',
            call_url
        )
    trigger_action.short_description = 'Trigger API Action'
