from django.contrib import admin
from .models import UserActivityLog


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    """사용자 활동 로그 관리 (대시보드 데이터 소스)"""
    list_display = ('user', 'category', 'action', 'target_id', 'created_at')
    list_filter = ('category', 'action', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
