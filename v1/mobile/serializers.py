from rest_framework import serializers
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from v1.regulatory.models import RegulatoryNews


class RegulatoryNewsSerializer(serializers.ModelSerializer):
    source_display = serializers.SerializerMethodField()
    risk_level_display = serializers.SerializerMethodField()

    class Meta:
        model = RegulatoryNews
        fields = [
            'id', 'source', 'source_display', 'product_name', 'company_name',
            'violation_reason', 'ai_summary', 'risk_level', 'risk_level_display',
            'ai_keywords', 'violation_type', 'event_date', 'collected_date',
        ]

    def get_source_display(self, obj):
        return obj.get_source_display()

    def get_risk_level_display(self, obj):
        return obj.get_risk_level_display()


class AppDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppDevice
        fields = ['id', 'device_id', 'platform', 'app_version', 'fcm_token']


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

    class Meta:
        model = PushNotificationLog
        fields = ['id', 'news', 'is_read', 'created_at']


class BookmarkSerializer(serializers.ModelSerializer):
    news = RegulatoryNewsSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'news', 'memo', 'created_at']


class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersion
        fields = ['platform', 'min_version', 'latest_version', 'store_url', 'force_message']
