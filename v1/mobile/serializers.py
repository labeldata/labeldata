from rest_framework import serializers
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from v1.regulatory.models import RegulatoryNews


class RegulatoryNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryNews
        fields = [
            'id', 'source', 'product_name', 'company_name',
            'violation_reason', 'ai_summary', 'risk_level',
            'ai_keywords', 'event_date', 'collected_date',
        ]


class AppDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppDevice
        fields = ['id', 'device_id', 'platform', 'app_version', 'fcm_token']


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = ['id', 'category', 'keyword', 'match_type', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


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
