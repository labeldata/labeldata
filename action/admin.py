# action/admin.py
from django.contrib import admin
from .models import AdministrativeAction

@admin.register(AdministrativeAction)
class AdministrativeActionAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'action_name', 'action_date')
    search_fields = ('company_name', 'action_name')
