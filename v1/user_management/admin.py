from django.contrib import admin
from .models import UserProfile, CompanyDocument


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'license_number', 'is_email_verified', 'is_paid']
    search_fields = ['user__email', 'company_name', 'license_number']
    list_filter = ['is_email_verified', 'is_paid']


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'doc_type', 'doc_name', 'uploaded_at']
    search_fields = ['user__email', 'doc_name']
    list_filter = ['doc_type']
    readonly_fields = ['uploaded_at']
