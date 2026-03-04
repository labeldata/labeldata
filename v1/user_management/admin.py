from django.contrib import admin
from .models import UserProfile, CompanyDocument


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'license_number', 'email_verified_yn', 'paid_yn']
    search_fields = ['user__email', 'company_name', 'license_number']
    list_filter = ['email_verified_yn', 'paid_yn']


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'doc_type', 'doc_name', 'uploaded_at']
    search_fields = ['user__email', 'doc_name']
    list_filter = ['doc_type']
    readonly_fields = ['uploaded_at']
