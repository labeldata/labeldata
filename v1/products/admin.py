from django.contrib import admin
from .models import (
    ProductMetadata, ProductFolder, ProductAccessLog,
    DocumentType, ProductDocument,
    ProductComment,
    ProductShare, SharePermission, SharedProductReceipt,
    ProductActivityLog
)

# Product, FoodType, CountryList는 V1 admin에서 관리 (MyLabel로 등록됨)


# ==================== 문서 관리 Admin ====================

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ['type_code', 'type_name', 'requires_expiry', 'default_validity_days', 'expiry_alert_days', 'required_yn', 'active_yn', 'display_order']
    list_editable = ['active_yn', 'display_order', 'required_yn']
    search_fields = ['type_code', 'type_name', 'description', 'detection_keywords']
    list_filter = ['requires_expiry', 'active_yn', 'required_yn']
    ordering = ['display_order', 'type_name']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('type_code', 'type_name', 'description', 'display_order')
        }),
        ('자동 분류', {
            'fields': ('detection_keywords',),
            'description': '파일명에 포함된 키워드로 자동 분류 (콤마로 구분)'
        }),
        ('만료일 관리', {
            'fields': ('requires_expiry', 'default_validity_days', 'expiry_alert_days')
        }),
        ('UI 설정', {
            'fields': ('icon', 'color'),
            'classes': ('collapse',)
        }),
        ('상태', {
            'fields': ('active_yn', 'required_yn')
        }),
    )


@admin.register(ProductDocument)
class ProductDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_id', 'label', 'document_type', 'original_filename', 'file_size', 'issue_date', 'expiry_date', 'uploaded_by', 'uploaded_datetime', 'active_yn']
    search_fields = ['original_filename', 'document_title', 'description']
    list_filter = ['document_type', 'active_yn', 'uploaded_datetime', 'expiry_date']
    date_hierarchy = 'uploaded_datetime'
    readonly_fields = ['uploaded_datetime', 'file_size', 'file_extension']
    
    fieldsets = (
        ('연결 정보', {
            'fields': ('label', 'document_type')
        }),
        ('파일 정보', {
            'fields': ('file', 'original_filename', 'file_size', 'file_extension')
        }),
        ('문서 정보', {
            'fields': ('document_title', 'description', 'issue_date', 'expiry_date')
        }),
        ('메타데이터', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('업로드 정보', {
            'fields': ('uploaded_by', 'uploaded_datetime', 'active_yn'),
            'classes': ('collapse',)
        }),
    )


# ==================== 협업 기능 Admin ====================

@admin.register(ProductComment)
class ProductCommentAdmin(admin.ModelAdmin):
    list_display = ['comment_id', 'label', 'field_name', 'author', 'content_preview', 'resolved_yn', 'created_at']
    search_fields = ['content', 'field_name']
    list_filter = ['resolved_yn', 'created_at', 'author']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = '내용 미리보기'


# ==================== 공유 관리 Admin ====================

class SharePermissionInline(admin.StackedInline):
    model = SharePermission
    can_delete = False


@admin.register(ProductShare)
class ProductShareAdmin(admin.ModelAdmin):
    list_display = ['share_id', 'label', 'share_mode', 'recipient_email', 'recipient_user', 'active_yn', 'share_end_date', 'created_by', 'created_datetime']
    search_fields = ['recipient_email', 'share_message', 'public_token']
    list_filter = ['share_mode', 'active_yn', 'created_datetime']
    date_hierarchy = 'created_datetime'
    readonly_fields = ['public_token', 'created_datetime', 'updated_datetime']
    inlines = [SharePermissionInline]
    
    fieldsets = (
        ('공유 정보', {
            'fields': ('label', 'share_mode', 'share_message')
        }),
        ('수신자 (PRIVATE 모드)', {
            'fields': ('recipient_email', 'recipient_user')
        }),
        ('공개 링크 (PUBLIC 모드)', {
            'fields': ('public_token',)
        }),
        ('공유 기간', {
            'fields': ('share_start_date', 'share_end_date')
        }),
        ('상태', {
            'fields': ('active_yn',)
        }),
        ('시스템 정보', {
            'fields': ('created_by', 'created_datetime', 'updated_datetime'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SharePermission)
class SharePermissionAdmin(admin.ModelAdmin):
    list_display = [
        'permission_id',
        'share',
        'role_code',
        'can_view',
        'can_comment',
        'can_suggest',
        'can_upload_documents',
        'can_edit_label',
        'can_review',
        'can_approve',
        'can_use_as_ingredient',
        'can_download_documents',
    ]
    list_filter = ['role_code', 'can_view', 'can_comment', 'can_suggest', 'can_review', 'can_approve', 'can_use_as_ingredient']


@admin.register(SharedProductReceipt)
class SharedProductReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_id', 'share', 'receiver', 'accepted_yn', 'used_as_ingredient_yn', 'received_datetime']
    search_fields = ['receiver__username', 'receiver__email']
    list_filter = ['accepted_yn', 'used_as_ingredient_yn', 'received_datetime']
    date_hierarchy = 'received_datetime'
    readonly_fields = ['received_datetime']


# ==================== 활동 로그 Admin ====================

@admin.register(ProductActivityLog)
class ProductActivityLogAdmin(admin.ModelAdmin):
    list_display = ['log_id', 'label', 'user', 'action', 'created_at']
    search_fields = ['label__my_label_name', 'user__username', 'user__email']
    list_filter = ['action', 'created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['log_id', 'label', 'user', 'action', 'details', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
