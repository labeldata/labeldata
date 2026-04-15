from rest_framework import serializers
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from v1.regulatory.models import RegulatoryNews


_API_SOURCE_LABELS = {
    'I2620':      '국내 검사부적합',
    'I2640':      '국내 검사부적합',
    'I0490':      '국내 회수·판매중지',
    'imp_insp':   '수입 부적합',
    'import':     '수입 회수·판매중지',
    'I0470':      '국내 행정처분',
    'I0480':      '국내 행정처분',
    'I0482':      '수입 행정처분',
    'saol_admin': '지자체 행정처분',
}


class RegulatoryNewsSerializer(serializers.ModelSerializer):
    source_display = serializers.SerializerMethodField()
    risk_level_display = serializers.SerializerMethodField()

    class Meta:
        model = RegulatoryNews
        fields = [
            'id', 'source', 'source_display', 'api_source',
            'product_name', 'company_name',
            'violation_reason', 'ai_summary', 'risk_level', 'risk_level_display',
            'ai_keywords', 'violation_type', 'event_date', 'collected_date',
        ]

    def get_source_display(self, obj):
        return _API_SOURCE_LABELS.get(obj.api_source) or obj.get_source_display()

    def get_risk_level_display(self, obj):
        return obj.get_risk_level_display()


class AppDeviceSerializer(serializers.ModelSerializer):
    max_rules = serializers.SerializerMethodField()
    max_bookmarks = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = AppDevice
        fields = ['id', 'device_id', 'platform', 'app_version', 'fcm_token', 'max_rules', 'max_bookmarks', 'username']

    def get_max_rules(self, obj):
        from django.conf import settings
        return settings.MOBILE_MEMBER_MAX_RULES if obj.user else settings.MOBILE_GUEST_MAX_RULES

    def get_max_bookmarks(self, obj):
        from django.conf import settings
        return settings.MOBILE_MEMBER_MAX_BOOKMARKS if obj.user else settings.MOBILE_GUEST_MAX_BOOKMARKS

    def get_username(self, obj):
        return obj.user.get_username() if obj.user else None


class AlertRuleSerializer(serializers.ModelSerializer):
    category_display = serializers.SerializerMethodField()
    match_type_display = serializers.SerializerMethodField()

    class Meta:
        model = AlertRule
        fields = ['id', 'category', 'category_display', 'keyword', 'match_type', 'match_type_display', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_match_type_display(self, obj):
        return obj.get_match_type_display()


class PushNotificationLogSerializer(serializers.ModelSerializer):
    news = RegulatoryNewsSerializer(read_only=True)
    rule_keyword = serializers.SerializerMethodField()

    class Meta:
        model = PushNotificationLog
        fields = ['id', 'news', 'rule_keyword', 'trigger_type', 'trigger_label', 'is_read', 'created_at']

    def get_rule_keyword(self, obj):
        if obj.rule_triggered is None:
            return None
        return {
            'keyword': obj.rule_triggered.keyword,
            'category': obj.rule_triggered.category,
            'match_type': obj.rule_triggered.match_type,
        }


class BookmarkSerializer(serializers.ModelSerializer):
    news = RegulatoryNewsSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'news', 'memo', 'created_at']


class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersion
        fields = ['platform', 'min_version', 'latest_version', 'store_url', 'force_message']
