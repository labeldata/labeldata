from django.contrib import admin
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion


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


# AnalyticsEvent 는 admin 에 걸지 않는다 — **행을 만드는 코드가 없다.**
#
# 앱에도 서버에도 이 표에 쓰는 곳이 0이었다(앱의 logEvent 는 부르는 곳이
# 없었고 그것이 치던 라우트도 없었다. 앱 쪽은 걷어냈다). 메뉴만 있으면
# "지표가 쌓이고 있다" 고 믿게 되는데 영원히 비어 있다.
#
# 표 자체는 남긴다 — 지우려면 마이그레이션이 필요한데 이 저장소의
# 마이그레이션 그래프는 갈라져 있다(settings_test 머리말). 지표를 다시
# 하기로 하면 그때 여기부터 살리면 된다.
