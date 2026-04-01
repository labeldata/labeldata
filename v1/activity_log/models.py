from django.db import models
from django.contrib.auth.models import User


CATEGORY_CHOICES = [
    ('label', '표시사항'),
    ('ingredient', '원료'),
    ('preview', '미리보기'),
    ('validation', '검증'),
    ('search', '조회'),
    ('calculator', '계산기'),
    ('board', '게시판'),
    ('ui', 'UI 버전'),
    # V2 신규
    ('regulatory', '부적합/처분 알림'),
    ('product', '제품 관리'),
    ('bom', 'BOM'),
    ('sharing', '공유/권한'),
    ('document', '서류 요청'),
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

    # 표시사항 작성 세부기능 (9개)
    ('validation_report', '품목보고번호 검증'),
    ('allergen_auto_detect', '알레르기 감지(표시)'),
    ('allergy_auto_detect', '알레르기 감지(원료)'),
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

    # UI 버전 사용
    ('ui_v1_session', 'V1 홈 방문'),
    ('ui_v2_session', 'V2 홈 방문'),

    # 부적합/처분 알림 (V2)
    ('regulatory_view', '부적합/처분 알림 조회'),   # 레거시, 미사용
    ('regulatory_detail', '알림 상세 조회'),
    ('regulatory_action', '알림 조치'),

    # 제품 관리 (V2)
    ('product_create', '제품 생성'),
    ('product_view', '제품 탐색기 조회'),           # 레거시, 미사용
    ('workflow_status_change', '워크플로우 상태 변경'),
    ('nutrition_view', '영양성분 편집기 사용'),

    # BOM (V2)
    ('bom_view', 'BOM 조회'),
    ('bom_save', 'BOM 저장'),

    # 공유/권한 (V2)
    ('share_create', '공유/권한 부여'),
    ('share_accept', '공유 수락'),
    ('share_use_ingredient', '공유 원료로 사용'),

    # 서류 요청 (V2)
    ('doc_request_send', '서류 요청 전송'),
    ('doc_request_accept', '서류 수락'),
]


class UserActivityLog(models.Model):
    """사용자 활동 로그 추적"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, help_text='활동 카테고리')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, help_text='수행 액션')
    target_id = models.IntegerField(null=True, blank=True, help_text='대상 객체 ID')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성 시간')

    class Meta:
        ordering = ['-created_at']
        db_table = 'common_useractivitylog'
        indexes = [
            models.Index(fields=['user', 'category'], name='common_user_user_id_b61948_idx'),
            models.Index(fields=['created_at'], name='common_user_created_038ee9_idx'),
            models.Index(fields=['category', 'action'], name='common_user_categor_2ba2f3_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_category_display()} - {self.get_action_display()}"
