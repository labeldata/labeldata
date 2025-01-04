from django.contrib import admin
from .models import FoodType
from django.urls import reverse
from django.utils.html import format_html

@admin.register(FoodType)
class FoodTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at', 'update_food_types_button')
    search_fields = ('name',)

    def update_food_types_button(self, obj):
        url = reverse('label:update_food_types')  # API 갱신 URL
        return format_html('<a class="button" href="{}">API 데이터 갱신</a>', url)

    update_food_types_button.short_description = "API 데이터 갱신"
    update_food_types_button.allow_tags = True

