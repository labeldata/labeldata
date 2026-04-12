from django.contrib import admin
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion, AnalyticsEvent


@admin.register(AppDevice)
class AppDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'platform', 'app_version', 'user', 'last_active_at')
    list_filter = ('platform',)
    search_fields = ('device_id', 'user__username')


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('device', 'category', 'keyword', 'match_type', 'is_active', 'created_at')
    list_filter = ('category', 'match_type', 'is_active')
    search_fields = ('keyword',)


@admin.register(PushNotificationLog)
class PushNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('device', 'news', 'is_read', 'created_at')
    list_filter = ('is_read',)


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('device', 'news', 'created_at')


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ('platform', 'latest_version', 'min_version', 'updated_at')


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('device', 'event_name', 'created_at')
    list_filter = ('event_name',)
