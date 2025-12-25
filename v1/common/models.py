from django.db import models
from django.contrib.auth.models import User


# 카테고리 및 액션 상수 정의
CATEGORY_CHOICES = [
    ('label', '표시사항'),
    ('ingredient', '원료'),
    ('preview', '미리보기'),
    ('validation', '검증'),
    ('search', '조회'),
    ('calculator', '계산기'),
    ('board', '게시판'),
]

ACTION_CHOICES = [
    # 표시사항 관련 (7개)
    ('label_save', '표시사항 저장'),
    ('label_create', '표시사항 생성'),
    ('label_update', '표시사항 수정'),
    ('label_delete', '표시사항 삭제'),
    ('label_view', '표시사항 조회'),
    ('label_copy', '표시사항 복사'),
    ('label_write', '표시사항 작성'),
    
    # 원료 관련 (7개)
    ('ingredient_save', '원료 저장'),
    ('ingredient_create', '원료 생성'),
    ('ingredient_update', '원료 수정'),
    ('ingredient_delete', '원료 삭제'),
    ('ingredient_view', '원료 조회'),
    ('ingredient_link', '원료 연결'),
    ('ingredient_copy', '원료 복사'),
    
    # 영양성분 계산기 (2개)
    ('calculator_calc', '영양성분 계산'),
    ('calculator_save', '영양성분 저장'),
    
    # 조회 (3개)
    ('search_domestic', '국내제품 조회'),
    ('search_import', '수입제품 조회'),
    ('search_additive', '식품첨가물 조회'),
    
    # 조회 복사 (2개)
    ('search_label_copy', '검색에서 표시사항 복사'),
    ('search_ingredient_copy', '검색에서 내원료 복사'),
    
    # 게시판 (2개)
    ('board_post', '게시글 작성'),
    ('board_comment', '댓글 작성'),
    
    # 표시사항 작성 세부기능 (8개)
    ('validation_report', '품목보고번호 검증'),
    ('allergen_auto_detect', '알레르기 감지'),
    ('ingredient_table_input', '원재료 표로 입력'),
    ('ingredient_quick_register', '원재료 빠른 등록'),
    ('caution_quick_add', '주의문구 빠른 등록'),
    ('other_text_quick_add', '기타문구 빠른 등록'),
    ('custom_field_use', '맞춤항목 등록'),
    ('mode_switch', '간편/상세 전환'),
    ('selection_copy', '선택 복사'),
    
    # 미리보기 팝업 세부기능 (7개)
    ('preview_view', '미리보기 팝업'),
    ('preview_table_settings', '표 설정'),
    ('preview_order', '항목 순서'),
    ('preview_text_transform', '텍스트 변환'),
    ('preview_recycling_mark', '분리배출마크'),
    ('validation_nutrition', '규정 검증'),
    ('preview_pdf_save', 'PDF 저장'),
    ('preview_settings_save', '설정 저장'),
]


class ApiKey(models.Model):
    """API 키를 관리하는 모델"""
    key = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="API 키 생성 시간")
    updated_at = models.DateTimeField(auto_now=True, help_text="API 키 갱신 시간")

    def __str__(self):
        return self.key

class ApiEndpoint(models.Model):
    """API 엔드포인트를 관리하는 모델"""
    name = models.CharField(max_length=255, help_text="API 이름")
    url = models.URLField(max_length=500, help_text="API URL")
    start_date = models.CharField(
        max_length=8,
        help_text="시작일자(YYYYMMDD)",
        null=True,
        blank=True,
        default=""
    )
    call_frequency_minutes = models.IntegerField(default=1440, help_text="호출 주기 (분 단위)")  # <- 나중에 삭제 가능
    last_called_at = models.DateTimeField(null=True, blank=True, help_text="마지막 호출 시간")
    last_status = models.CharField(
        max_length=50,
        choices=[("success", "성공"), ("failure", "실패")],
        default="success",
        help_text="마지막 호출 상태"
    )
    api_key = models.ForeignKey(
        'ApiKey', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='endpoints',
        help_text="API 키"
    )
    service_name = models.CharField(
        max_length=50,
        help_text="서비스 이름 (예: I1250)",
        null=True, blank=True  # 필수 아님으로 변경
    )
    last_start_position = models.IntegerField(
        default=1,
        help_text="마지막 요청 시작 위치 (중단 후 이어받기용)"
    )
    use_reset_start_position = models.CharField(
        max_length=1,
        choices=[('Y', '초기화'), ('N', '유지')],
        default='Y',
        help_text='API 호출 시 last_start_position을 1로 초기화할지 여부 (Y: 초기화, N: 유지)'
    )

    def __str__(self):
        return self.name

class AdministrativeAction(models.Model):
    """행정처분 정보"""
    company_name = models.CharField(max_length=255, help_text="업체명", default="Unknown Company")
    registration_number = models.CharField(max_length=100, help_text="인허가번호")
    action_name = models.CharField(max_length=255, help_text="행정처분명")
    action_date = models.DateField(help_text="행정처분일")
    details = models.TextField(blank=True, help_text="기타 세부 내용")

    def __str__(self):
        return f"{self.company_name} - {self.action_name} ({self.action_date})"


class UserActivityLog(models.Model):
    """사용자 활동 로그 추적"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, help_text="활동 카테고리")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, help_text="수행 액션")
    target_id = models.IntegerField(null=True, blank=True, help_text="대상 객체 ID")
    # ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP 주소")
    # user_agent = models.TextField(null=True, blank=True, help_text="User Agent")
    created_at = models.DateTimeField(auto_now_add=True, help_text="생성 시간")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'category']),
            models.Index(fields=['created_at']),
            models.Index(fields=['category', 'action']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_category_display()} - {self.get_action_display()}"