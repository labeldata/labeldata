from django.contrib import admin
from label.models import Post, Comment, FoodType, FoodItem

#어드민에서 관리할 필요 없는 모델들 주석 처리

class BaseAdmin(admin.ModelAdmin):
    """공통 설정 클래스"""
    #list_per_page = 20  # 한 페이지에 표시할 항목 수


@admin.register(Post)
class PostAdmin(BaseAdmin):
    """Post 모델 관리"""
    #list_display = ('title', 'author', 'create_date', 'modify_date')
    #readonly_fields = ('create_date', 'modify_date')  # 수정 불가 필드
    #search_fields = ('title', 'author__username')
    #date_hierarchy = 'create_date'


@admin.register(Comment)
class CommentAdmin(BaseAdmin):
    """Comment 모델 관리"""
    #list_display = ('content', 'author', 'post', 'create_date')
    #readonly_fields = ('create_date',)
    #search_fields = ('content', 'author__username')
    #date_hierarchy = 'create_date'


@admin.register(FoodType)
class FoodTypeAdmin(BaseAdmin):
    """FoodType 모델 관리"""
    #list_display = ('name', 'created_at')
    #readonly_fields = ('created_at',)
    #search_fields = ('name',)


@admin.register(FoodItem)
class FoodItemAdmin(BaseAdmin):
    """FoodItem 모델 관리"""
    #list_display = ('product_name', 'manufacturer_name', 'report_date', 'category')
    #search_fields = ('product_name', 'manufacturer_name')
    #date_hierarchy = 'report_date'
