from django.contrib import admin
from django.urls import reverse  # reverse는 이미 import되어 있음
from django.utils.html import format_html  # format_html import 추가
from .models import ApiKey, ApiEndpoint, UserActivityLog    


class BaseAdmin(admin.ModelAdmin):
    # 공통 설정 클래스
    list_per_page = 20  # 한 페이지에 표시할 항목 수

@admin.register(ApiKey)
class ApiKeyAdmin(BaseAdmin):
    # ApiKey 모델 관리
    list_display = ('key',)
    search_fields = ('key',)

@admin.register(ApiEndpoint)
class ApiEndpointAdmin(BaseAdmin):
    # ApiEndpoint 모델 관리
    list_display = ('name', 'service_name', 'short_url', 'start_date', 'last_called_at', 'last_start_position', 'trigger_action')
    search_fields = ('name', 'url', 'service_name')
    readonly_fields = ('last_called_at',)

    def short_url(self, obj):
        # URL을 일정 길이(예: 40자)까지만 표시하고, 전체는 툴팁으로 보여줌. 길면 스크롤 가능하게 스타일 적용
        max_len = 40
        url = obj.url or ""
        display = url if len(url) <= max_len else url[:max_len] + "..."
        return format_html(
            '<div style="max-width:320px; overflow-x:auto; white-space:nowrap;" title="{}">{}</div>',
            url, display
        )
    short_url.short_description = 'URL'

    def trigger_action(self, obj):
        # Renders a button to trigger API calls from the admin interface.
        call_url = reverse('common:call_api_endpoint', args=[obj.id])
        return format_html(
            '<a class="button" style="color: white; background-color: #4CAF50; padding: 5px 10px; '
            'text-decoration: none; border-radius: 5px;" href="{}">Call Now</a>',
            call_url
        )
    trigger_action.short_description = 'Trigger API Action'

# --- 아래 사용자 관리자 설정 코드를 추가 ---
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count, Q, Prefetch

# MyLabel, MyIngredient 모델을 import 합니다.
from v1.label.models import MyLabel, MyIngredient

# Django의 기본 UserAdmin을 상속받아 CustomUserAdmin 클래스 정의
class CustomUserAdmin(UserAdmin):
    """
    사용자 관리자 페이지 커스터마이징
    - 표시사항 수, 내 원료 수, 활동일수, 최근 접속일, 가입일 필드 추가
    """
    # 1. 사용자 목록에 표시할 항목과 순서 변경
    list_display = (
        'username', 
        'is_staff', 
        'get_date_joined',      # 가입일
        'get_last_login',       # 최근 접속일
        'activity_day_count',   # 접속일수
        'my_label_count', 
        'my_ingredient_count'
    )
    
    # 2. 상세 정보 화면 설정 (기존과 동일)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # 상세 정보 화면에서 읽기 전용으로 표시할 필드
    readonly_fields = ('last_login', 'date_joined')

    def get_queryset(self, request):
        """
        Queryset을 가져올 때, annotate와 prefetch_related를 사용하여 필요한 값들을 미리 계산합니다.
        """
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _my_label_count=Count('user_label', distinct=True),
            _my_ingredient_count=Count('user_ingredient', filter=Q(user_ingredient__delete_YN='N'), distinct=True)
        ).prefetch_related(
            'user_label',
            'user_ingredient'
        )
        return queryset

    def my_label_count(self, obj):
        return obj._my_label_count
    
    def my_ingredient_count(self, obj):
        return obj._my_ingredient_count

    def activity_day_count(self, obj):
        """
        표시사항과 내원료의 수정 날짜를 합쳐 중복을 제거한 후, 순수한 활동일수를 계산합니다.
        """
        label_dates = {label.update_datetime.date() for label in obj.user_label.all() if label.update_datetime}
        ingredient_dates = {ingredient.update_datetime.date() for ingredient in obj.user_ingredient.all() if ingredient.update_datetime}
        
        total_activity_dates = label_dates.union(ingredient_dates)
        
        return len(total_activity_dates)

    # --- 항목명 변경 및 정렬 기능 유지를 위한 메소드 추가 ---
    def get_date_joined(self, obj):
        return obj.date_joined
    
    def get_last_login(self, obj):
        return obj.last_login

    # 각 열의 제목을 설정합니다.
    my_label_count.short_description = '표시사항 수'
    my_label_count.admin_order_field = '_my_label_count'
    
    my_ingredient_count.short_description = '내 원료 수'
    my_ingredient_count.admin_order_field = '_my_ingredient_count'

    activity_day_count.short_description = '접속일수'  # 활동일수 -> 접속일수

    get_date_joined.short_description = '가입일'  # 등록일 -> 가입일
    get_date_joined.admin_order_field = 'date_joined'  # 정렬 기능 유지

    get_last_login.short_description = '최근 접속일'  # 마지막 로그인 -> 최근 접속일
    get_last_login.admin_order_field = 'last_login'  # 정렬 기능 유지


# 기존의 User 관리자 등록을 해제하고 CustomUserAdmin으로 재등록
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ============================================
# 사용자 활동 로그 관리
# ============================================

@admin.register(UserActivityLog)
class UserActivityLogAdmin(BaseAdmin):
    """사용자 활동 로그 관리 (대시보드 데이터 소스)"""
    list_display = ('user', 'category', 'action', 'target_id', 'created_at')
    list_filter = ('category', 'action', 'created_at')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

# ============================================
# Label 앱 모델 관리
# ============================================

from v1.board.models import Board, Comment

@admin.register(MyLabel)
class MyLabelAdmin(BaseAdmin):
    """내 표시사항 관리 (소프트 삭제 지원)"""
    list_display = ('my_label_id', 'my_label_name', 'user_id', 'food_type', 'delete_YN', 'update_datetime')
    search_fields = ('my_label_name', 'food_type', 'user_id__username')
    list_filter = ('delete_YN', 'food_type')
    readonly_fields = ('create_datetime', 'update_datetime')
    actions = ['soft_delete_selected', 'restore_selected']
    
    def soft_delete_selected(self, request, queryset):
        """선택된 항목을 소프트 삭제"""
        from datetime import datetime
        updated = queryset.update(
            delete_YN='Y',
            delete_datetime=datetime.now().strftime('%Y%m%d')
        )
        self.message_user(request, f'{updated}개의 표시사항이 삭제되었습니다.')
    soft_delete_selected.short_description = '선택된 표시사항 삭제'
    
    def restore_selected(self, request, queryset):
        """선택된 항목을 복원"""
        updated = queryset.update(
            delete_YN='N',
            delete_datetime=''
        )
        self.message_user(request, f'{updated}개의 표시사항이 복원되었습니다.')
    restore_selected.short_description = '선택된 표시사항 복원'

@admin.register(MyIngredient)
class MyIngredientAdmin(BaseAdmin):
    """내 원료 관리 (소프트 삭제 지원)"""
    list_display = ('my_ingredient_id', 'prdlst_nm', 'user_id', 'bssh_nm', 'delete_YN', 'update_datetime')
    search_fields = ('prdlst_nm', 'bssh_nm', 'user_id__username')
    list_filter = ('delete_YN',)
    readonly_fields = ('update_datetime',)
    actions = ['soft_delete_selected', 'restore_selected']
    
    def soft_delete_selected(self, request, queryset):
        """선택된 항목을 소프트 삭제"""
        from datetime import datetime
        updated = queryset.update(
            delete_YN='Y',
            delete_datetime=datetime.now().strftime('%Y%m%d')
        )
        self.message_user(request, f'{updated}개의 원료가 삭제되었습니다.')
    soft_delete_selected.short_description = '선택된 원료 삭제'
    
    def restore_selected(self, request, queryset):
        """선택된 항목을 복원"""
        updated = queryset.update(
            delete_YN='N',
            delete_datetime=''
        )
        self.message_user(request, f'{updated}개의 원료가 복원되었습니다.')
    restore_selected.short_description = '선택된 원료 복원'

# ============================================
# Board 앱 모델 관리
# ============================================

class CommentInline(admin.TabularInline):
    """게시글 댓글 인라인 편집"""
    model = Comment
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = ('author', 'content', 'created_at')

@admin.register(Board)
class BoardAdmin(BaseAdmin):
    """게시판 관리 (댓글 인라인 포함)"""
    list_display = ('title', 'author', 'is_notice', 'views', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    list_filter = ('is_notice', 'is_hidden', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'views')
    inlines = [CommentInline]

# ============================================
# Django Admin 사이트 설정
# ============================================

admin.site.site_header = "EZLABELING 관리자"
admin.site.site_title = "EZLABELING Admin"
admin.site.index_title = "관리자 페이지"