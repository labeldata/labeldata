from django.contrib import admin
from .models import Allergen

@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ['name']
