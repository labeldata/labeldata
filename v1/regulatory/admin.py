from django.contrib import admin
from v1.regulatory.models import (
    RegulatoryNews, NewsProductMatch,
    NewsIngredientMatch, RegulatoryMatchAction,
)


@admin.register(RegulatoryNews)
class RegulatoryNewsAdmin(admin.ModelAdmin):
    list_display  = ('product_name', 'company_name', 'source', 'risk_level',
                     'ai_parsed', 'collected_date')
    list_filter   = ('source', 'risk_level', 'ai_parsed', 'collected_date')
    search_fields = ('product_name', 'company_name', 'violation_reason')
    readonly_fields = ('ai_keywords', 'ai_summary', 'collected_date', 'created_at', 'updated_at')
    ordering = ('-collected_date',)


@admin.register(NewsProductMatch)
class NewsProductMatchAdmin(admin.ModelAdmin):
    list_display  = ('news', 'product', 'matched_keyword', 'match_score',
                     'is_read', 'created_at')
    list_filter   = ('is_read', 'created_at')
    search_fields = ('matched_keyword', 'matched_ingredient',
                     'news__product_name', 'product__my_label_name')
    ordering = ('-created_at',)


@admin.register(NewsIngredientMatch)
class NewsIngredientMatchAdmin(admin.ModelAdmin):
    list_display  = ('news', 'user', 'ingredient', 'matched_keyword',
                     'risk_level', 'is_read', 'is_dismissed', 'created_at')
    list_filter   = ('risk_level', 'is_read', 'is_dismissed', 'created_at')
    search_fields = ('matched_keyword', 'news__product_name',
                     'ingredient__prdlst_nm', 'user__username')
    raw_id_fields = ('news', 'user', 'ingredient')
    ordering      = ('-created_at',)


@admin.register(RegulatoryMatchAction)
class RegulatoryMatchActionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'action_type', 'product_match', 'ingredient_match',
                     'memo', 'created_at')
    list_filter   = ('action_type', 'created_at')
    search_fields = ('memo', 'user__username',
                     'product_match__news__product_name',
                     'ingredient_match__news__product_name')
    raw_id_fields = ('user', 'product_match', 'ingredient_match')
    ordering      = ('-created_at',)
