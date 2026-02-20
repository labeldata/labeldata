from django.contrib import admin
from .models import ProductBOM


@admin.register(ProductBOM)
class ProductBOMAdmin(admin.ModelAdmin):
    list_display = ['bom_id', 'parent_label', 'ingredient_name', 'level', 'usage_ratio', 'usage_amount', 'usage_unit', 'is_active', 'created_datetime']
    search_fields = ['ingredient_name', 'notes', 'parent_label__my_label_name']
    list_filter = ['level', 'is_active', 'created_datetime']
    readonly_fields = ['created_datetime', 'updated_datetime']
    
    fieldsets = (
        ('제품 관계', {
            'fields': ('parent_label', 'child_label', 'shared_receipt', 'ingredient_name')
        }),
        ('배합 정보', {
            'fields': ('usage_ratio', 'usage_amount', 'usage_unit')
        }),
        ('계층 정보', {
            'fields': ('level', 'sort_order')
        }),
        ('추가 정보', {
            'fields': ('notes', 'is_active')
        }),
        ('시스템 정보', {
            'fields': ('created_by', 'created_datetime', 'updated_datetime'),
            'classes': ('collapse',)
        }),
    )
