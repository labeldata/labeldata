"""
제품 관리 모델 (V2) - V1 MyLabel 테이블 공유
- V1과 V2가 동일한 DB 테이블(my_label) 사용
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


# V1 모델을 직접 사용 (my_label 테이블 공유)
from v1.label.models import MyLabel as Product
from v1.label.models import FoodType, CountryList

# V2 전용 확장 모델
class ProductMetadata(models.Model):
    """
    V2 제품 메타데이터
    - V1 MyLabel을 직접 참조하여 데이터 중복 제거
    - V2 전용 기능만 관리 (폴더, 즐겨찾기, 소프트 삭제 등)
    """
    class Status(models.TextChoices):
        DRAFT      = 'DRAFT',      '작성 중'
        REQUESTING = 'REQUESTING', '자료 요청'
        SUBMITTED  = 'SUBMITTED',  '제출 완료'
        REVIEW     = 'REVIEW',     '검토 중'
        PENDING    = 'PENDING',    '승인 대기'
        CONFIRMED  = 'CONFIRMED',  '승인 완료'
    metadata_id = models.AutoField(primary_key=True, verbose_name="메타데이터 ID")
    
    # 핵심: V1 MyLabel 직접 참조
    label = models.OneToOneField(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name='v2_metadata',
        verbose_name='연결된 표시사항',
        db_column='my_label_id'
    )
    
    # V2 전용: 제품 코드 (자동 생성)
    product_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="제품 코드",
        db_index=True,
        help_text="PRD-{user_id}-{순번}"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="제품 상태"
    )
    
    # V2 전용: 폴더 관리
    folder = models.ForeignKey(
        'ProductFolder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='metadata_items',
        verbose_name='소속 폴더'
    )
    
    # V2 전용: 즐겨찾기
    is_starred = models.BooleanField(
        default=False,
        verbose_name='즐겨찾기',
        db_index=True
    )
    starred_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='즐겨찾기 등록일시'
    )
    
    # V2 전용: 소프트 삭제
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='삭제 여부',
        db_index=True,
        help_text='V2에서만 사용. V1 MyLabel.delete_YN과 별도 관리'
    )
    deleted_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='삭제일시'
    )
    
    # 타임스탬프
    created_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시'
    )
    updated_datetime = models.DateTimeField(
        auto_now=True,
        verbose_name='수정일시'
    )
    
    class Meta:
        db_table = 'v2_product_metadata'
        ordering = ['-updated_datetime']
        indexes = [
            models.Index(fields=['label', 'is_deleted']),
            models.Index(fields=['product_code']),
            models.Index(fields=['is_starred']),
            models.Index(fields=['folder']),
        ]
        verbose_name = 'V2 제품 메타데이터'
        verbose_name_plural = 'V2 제품 메타데이터 목록'
    
    def __str__(self):
        return f"{self.label.my_label_name} ({self.product_code})"
    
    def save(self, *args, **kwargs):
        # 제품 코드 자동 생성
        if not self.product_code:
            user = self.label.user_id
            last_metadata = ProductMetadata.objects.filter(
                label__user_id=user
            ).order_by('-metadata_id').first()
            
            if last_metadata and last_metadata.product_code:
                try:
                    last_num = int(last_metadata.product_code.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.product_code = f"PRD-{user.id}-{next_num:04d}"
        
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """소프트 삭제 (V2에서만)"""
        self.is_deleted = True
        self.deleted_datetime = timezone.now()
        self.save()
    
    def restore(self):
        """복원"""
        self.is_deleted = False
        self.deleted_datetime = None
        self.save()


# ==================== Google Drive 스타일 폴더 시스템 ====================

class ProductFolder(models.Model):
    """
    제품 폴더 (Google Drive 스타일)
    - 재귀적 폴더 구조 지원
    - 사용자별 폴더 관리
    """
    folder_id = models.AutoField(primary_key=True, verbose_name="폴더 ID")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="product_folders",
        verbose_name="소유자"
    )
    
    # 폴더 정보
    name = models.CharField(
        max_length=100,
        verbose_name="폴더명"
    )
    description = models.TextField(
        max_length=500,
        verbose_name="설명",
        null=True,
        blank=True
    )
    color = models.CharField(
        max_length=7,
        default="#6c757d",
        verbose_name="폴더 색상",
        help_text="HEX 색상 코드 (예: #0d6efd)"
    )
    icon = models.CharField(
        max_length=50,
        default="folder",
        verbose_name="아이콘",
        help_text="FontAwesome 아이콘명"
    )
    
    # 재귀적 폴더 구조
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="상위 폴더"
    )
    
    # 정렬 순서
    sort_order = models.IntegerField(
        default=0,
        verbose_name="정렬 순서"
    )
    
    # 상태
    is_system = models.BooleanField(
        default=False,
        verbose_name="시스템 폴더",
        help_text="삭제/이름변경 불가 (휴지통 등)"
    )
    
    # 타임스탬프
    created_datetime = models.DateTimeField(auto_now_add=True)
    updated_datetime = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "v2_product_folder"
        ordering = ['sort_order', 'name']
        unique_together = [['owner', 'name', 'parent']]
        verbose_name = "제품 폴더"
        verbose_name_plural = "제품 폴더 목록"
    
    def __str__(self):
        return f"{self.name}"
    
    def get_full_path(self):
        """전체 경로 반환 (예: 내 폴더 > 2026년 > 신제품)"""
        path_parts = [self.name]
        current = self.parent
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        return " > ".join(path_parts)
    
    def get_ancestors(self):
        """상위 폴더 목록 반환 (breadcrumb용)"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors
    
    def get_descendants(self):
        """하위 폴더 목록 반환 (재귀)"""
        descendants = list(self.children.all())
        for child in self.children.all():
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_all_products(self, include_subfolders=True):
        """폴더 내 모든 제품 반환"""
        products = list(self.products.filter(is_deleted=False))
        if include_subfolders:
            for child in self.children.all():
                products.extend(child.get_all_products(True))
        return products
    
    @classmethod
    def get_or_create_system_folders(cls, user):
        """시스템 폴더 생성 (최초 접속 시)"""
        system_folders = [
            {'name': '중요 문서', 'icon': 'star', 'color': '#ffc107'},
            {'name': '휴지통', 'icon': 'trash', 'color': '#dc3545'},
        ]
        created = []
        for folder_data in system_folders:
            folder, is_new = cls.objects.get_or_create(
                owner=user,
                name=folder_data['name'],
                parent=None,
                defaults={
                    'icon': folder_data['icon'],
                    'color': folder_data['color'],
                    'is_system': True,
                    'sort_order': -1  # 시스템 폴더는 항상 맨 위
                }
            )
            if is_new:
                created.append(folder)
        return created


class ProductAccessLog(models.Model):
    """
    제품 접근 로그 (최근 열어본 항목)
    - Google Drive의 "최근" 기능 구현
    """
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="product_access_logs"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="access_logs"
    )
    
    accessed_datetime = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=1)
    
    class Meta:
        db_table = "v2_product_access_log"
        ordering = ['-accessed_datetime']
        unique_together = [['user', 'product']]
        verbose_name = "제품 접근 로그"
    
    @classmethod
    def log_access(cls, user, product):
        """접근 로그 기록 (upsert)"""
        log, created = cls.objects.get_or_create(
            user=user,
            product=product,
            defaults={'access_count': 1}
        )
        if not created:
            log.access_count += 1
            log.save(update_fields=['access_count', 'accessed_datetime'])
        return log
    
    @classmethod
    def get_recent_products(cls, user, limit=10):
        """최근 열어본 제품 목록"""
        return cls.objects.filter(
            user=user,
            product__is_deleted=False
        ).select_related('product')[:limit]


# ==================== 문서 관리 (통합) ====================

class DocumentType(models.Model):
    """
    문서 타입 정의
    - 제조 보고서, 성분 분석서, 인증서 등
    - 파일명 키워드 기반 자동 분류
    - 유효기간 자동 설정
    """
    type_id = models.AutoField(primary_key=True, verbose_name="타입 ID")
    type_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="타입 코드",
        help_text="예: CERT_HACCP, ANALYSIS_INGREDIENT"
    )
    type_name = models.CharField(
        max_length=100,
        verbose_name="타입명",
        help_text="예: HACCP 인증서, 성분 분석서"
    )
    description = models.TextField(
        max_length=500,
        verbose_name="설명",
        null=True,
        blank=True
    )
    
    # 파일명 자동 분류 키워드
    detection_keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="자동 분류 키워드",
        help_text="콤마(,)로 구분. 파일명에 이 단어가 있으면 자동 분류 (예: HACCP,해썹,haccp)"
    )
    
    # 만료일 관리
    requires_expiry = models.BooleanField(
        default=False,
        verbose_name="만료일 필수",
        help_text="이 타입의 문서에 만료일이 필수인지"
    )
    default_validity_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="기본 유효 기간 (일)",
        help_text="문서 업로드 시 기본 유효 기간. 0이면 무기한."
    )
    
    # 알림 설정
    expiry_alert_days = models.IntegerField(
        default=30,
        verbose_name="만료 알림 (일 전)",
        help_text="만료 며칠 전에 알림을 보낼지"
    )
    
    # 필수 문서 여부
    is_required = models.BooleanField(
        default=False,
        verbose_name="필수 문서",
        help_text="이 타입의 문서가 반드시 있어야 하는지"
    )
    
    # 상태
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성 상태"
    )
    
    # 정렬 순서
    display_order = models.IntegerField(
        default=0,
        verbose_name="표시 순서"
    )
    
    # 아이콘 (Bootstrap Icons)
    icon = models.CharField(
        max_length=50,
        default='bi-file-earmark',
        verbose_name="아이콘",
        help_text="Bootstrap Icons 클래스명 (예: bi-file-pdf)"
    )
    
    # 카드 색상
    color = models.CharField(
        max_length=20,
        default='#6c757d',
        verbose_name="색상",
        help_text="HEX 색상 코드 (예: #1a73e8)"
    )
    
    created_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name="생성일시"
    )
    
    class Meta:
        db_table = "v2_document_type"
        ordering = ['display_order', 'type_name']
        verbose_name = "문서 타입"
        verbose_name_plural = "문서 타입 목록"
    
    def __str__(self):
        return self.type_name
    
    def get_keywords_list(self):
        """키워드 목록 반환"""
        if not self.detection_keywords:
            return []
        return [k.strip().lower() for k in self.detection_keywords.split(',') if k.strip()]
    
    def matches_filename(self, filename):
        """파일명이 이 타입의 키워드와 일치하는지 확인"""
        if not self.detection_keywords:
            return False
        filename_lower = filename.lower()
        return any(keyword in filename_lower for keyword in self.get_keywords_list())


class DocumentSlot(models.Model):
    """
    제품별 필수 문서 슬롯 (Smart Slot)
    - 제품 생성 시 필수 문서 타입별로 자동 생성
    - 문서가 등록되면 해당 슬롯과 연결
    """
    
    class SlotStatus(models.TextChoices):
        EMPTY = 'EMPTY', '미등록'
        VALID = 'VALID', '정상'
        EXPIRING = 'EXPIRING', '만료임박'
        EXPIRED = 'EXPIRED', '만료됨'
    
    slot_id = models.AutoField(primary_key=True, verbose_name="슬롯 ID")
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name="document_slots",
        verbose_name="표시사항"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name="문서 타입"
    )
    
    # 현재 활성 문서 (최신 버전)
    current_document = models.ForeignKey(
        'ProductDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_slot",
        verbose_name="현재 문서"
    )
    
    # 슬롯 상태
    status = models.CharField(
        max_length=20,
        choices=SlotStatus.choices,
        default=SlotStatus.EMPTY,
        verbose_name="상태"
    )
    
    # 슬롯 숨김 (사용자가 "해당 없음" 선택 시)
    is_hidden = models.BooleanField(
        default=False,
        verbose_name="숨김",
        help_text="이 슬롯이 숨겨졌는지 (준수율 계산에서 제외)"
    )
    
    # 메타 정보
    created_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name="생성일시"
    )
    updated_datetime = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일시"
    )
    
    class Meta:
        db_table = "v2_document_slot"
        ordering = ['document_type__display_order', 'document_type__type_name']
        unique_together = [['label', 'document_type']]
        indexes = [
            models.Index(fields=['label', 'status']),
        ]
        verbose_name = "문서 슬롯"
        verbose_name_plural = "문서 슬롯"
    
    def __str__(self):
        return f"{self.label.korean_label_name} - {self.document_type.type_name}"
    
    def update_status(self):
        """슬롯 상태 업데이트"""
        if not self.current_document:
            self.status = self.SlotStatus.EMPTY
        elif self.current_document.expiry_date:
            from django.utils import timezone
            from datetime import timedelta
            
            today = timezone.now().date()
            expiry_date = self.current_document.expiry_date
            
            if expiry_date < today:
                self.status = self.SlotStatus.EXPIRED
            elif expiry_date <= today + timedelta(days=30):
                self.status = self.SlotStatus.EXPIRING
            else:
                self.status = self.SlotStatus.VALID
        else:
            self.status = self.SlotStatus.VALID  # 무기한 문서
        
        self.save()
        return self.status


class ProductDocument(models.Model):
    """
    제품별 첨부 문서
    - V1 MyLabel을 직접 참조하여 데이터 중복 제거
    - 각 표시사항에 여러 문서 첨부 가능
    - 문서별 만료일 관리
    """
    document_id = models.AutoField(primary_key=True, verbose_name="문서 ID")
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name="v2_documents",
        verbose_name="표시사항"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="문서 타입"
    )
    
    # 슬롯 연결 (필수 문서인 경우)
    slot = models.ForeignKey(
        DocumentSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="문서 슬롯"
    )
    
    # 파일 정보
    file = models.FileField(
        upload_to='v2/product_documents/%Y/%m/%d/',
        verbose_name="파일"
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name="원본 파일명"
    )
    file_size = models.BigIntegerField(
        verbose_name="파일 크기 (bytes)",
        default=0
    )
    file_extension = models.CharField(
        max_length=10,
        verbose_name="파일 확장자",
        blank=True
    )
    
    # 문서 정보
    document_title = models.CharField(
        max_length=200,
        verbose_name="문서 제목",
        null=True,
        blank=True
    )
    description = models.TextField(
        max_length=1000,
        verbose_name="설명",
        null=True,
        blank=True
    )
    
    # 만료일 관리
    issue_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="발행일"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="만료일"
    )
    expiry_notification_enabled = models.BooleanField(
        default=True,
        verbose_name="만료일 알림"
    )
    expiry_notification_days = models.IntegerField(
        default=30,
        verbose_name="만료 알림 기간(일)"
    )
    
    # 버전 관리
    version = models.IntegerField(
        default=1,
        verbose_name="버전"
    )
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versions',
        verbose_name="원본 문서"
    )
    replaced_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaces',
        verbose_name="대체된 문서"
    )
    
    # 메타데이터
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="메타데이터",
        help_text="추가 정보를 JSON으로 저장"
    )
    
    # 업로드 정보
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="v2_uploaded_documents",
        verbose_name="업로드자"
    )
    uploaded_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name="업로드일시"
    )
    
    # 상태
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성 상태"
    )
    
    class Meta:
        db_table = "v2_product_document"
        ordering = ['-uploaded_datetime']
        indexes = [
            models.Index(fields=['label', 'document_type']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = "제품 문서"
        verbose_name_plural = "제품 문서 목록"
    
    def __str__(self):
        return f"{self.document_type.type_name} - {self.original_filename}"
    
    def save(self, *args, **kwargs):
        # 파일 확장자 자동 추출
        if self.file and not self.file_extension:
            import os
            _, ext = os.path.splitext(self.original_filename)
            self.file_extension = ext.lower()
        
        # 유효기간 자동 설정 (무기한 지정 시 제외)
        expiry_unlimited = False
        if isinstance(self.metadata, dict):
            expiry_unlimited = self.metadata.get('expiry_unlimited', False)

        if not self.expiry_date and not expiry_unlimited and self.document_type and self.document_type.default_validity_days:
            from datetime import timedelta

            self.expiry_date = timezone.now().date() + timedelta(days=self.document_type.default_validity_days)
        
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """만료 여부 확인"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    def days_until_expiry(self):
        """만료까지 남은 일수"""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    def needs_alert(self):
        """만료 알림 필요 여부"""
        if not self.expiry_date or not self.document_type.expiry_alert_days:
            return False
        days_left = self.days_until_expiry()
        return days_left is not None and 0 <= days_left <= self.document_type.expiry_alert_days


# ==================== 협업 기능 (통합) ====================

class ProductComment(models.Model):
    """
    Google Docs 스타일의 필드별 댓글
    - V1 MyLabel을 직접 참조하여 데이터 중복 제거
    """
    comment_id = models.AutoField(primary_key=True)
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE, 
        related_name="v2_comments",
        verbose_name="표시사항"
    )
    
    # 어떤 필드에 달린 댓글인지 (예: 'prdlst_nm', 'rawmtrl_nm')
    # null이면 문서 전체에 대한 댓글
    field_name = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        verbose_name="대상 필드",
        db_index=True
    )
    
    # 댓글 작성자
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name="product_comments",
        verbose_name="작성자"
    )
    
    # 댓글 내용
    content = models.TextField(
        verbose_name="내용",
        max_length=2000
    )
    
    # 해결 여부 (Google Docs의 'Resolve')
    is_resolved = models.BooleanField(
        default=False,
        verbose_name="해결됨"
    )
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="resolved_comments",
        verbose_name="해결자"
    )
    resolved_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="해결 일시"
    )
    
    # 상위 댓글 (답글용)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name="상위 댓글"
    )
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "v2_product_comment"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['label', 'field_name']),
            models.Index(fields=['is_resolved']),
        ]
        verbose_name = "제품 댓글"
        verbose_name_plural = "제품 댓글 목록"

    def __str__(self):
        field_info = f" on {self.field_name}" if self.field_name else ""
        return f"{self.author.username}{field_info}: {self.content[:30]}"
    
    def get_replies(self):
        """답글 목록 반환"""
        return self.replies.filter(is_resolved=False).order_by('created_at')
    
    def resolve(self, user):
        """댓글 해결 처리"""
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()


class CommentMention(models.Model):
    """
    댓글 내 @멘션
    - 멘션된 사용자에게 알림 발송
    """
    mention_id = models.AutoField(primary_key=True)
    comment = models.ForeignKey(
        ProductComment,
        on_delete=models.CASCADE,
        related_name="mentions",
        verbose_name="댓글"
    )
    mentioned_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comment_mentions",
        verbose_name="멘션된 사용자"
    )
    
    # 알림 발송 여부
    is_notified = models.BooleanField(
        default=False,
        verbose_name="알림 발송됨"
    )
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="알림 발송 일시"
    )
    
    # 읽음 여부
    is_read = models.BooleanField(
        default=False,
        verbose_name="읽음"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="읽음 일시"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "v2_comment_mention"
        unique_together = [['comment', 'mentioned_user']]
        verbose_name = "댓글 멘션"
        verbose_name_plural = "댓글 멘션 목록"

    def __str__(self):
        return f"@{self.mentioned_user.username} in comment #{self.comment_id}"


class SuggestionMode(models.Model):
    """
    Google Docs 스타일 제안 모드
    - 필드 값 변경 제안
    - 승인/거절 워크플로우
    """
    suggestion_id = models.AutoField(primary_key=True)
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name="v2_suggestions",
        verbose_name="표시사항"
    )
    
    # 제안자
    suggested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="field_suggestions",
        verbose_name="제안자"
    )
    
    # 대상 필드
    field_name = models.CharField(
        max_length=100,
        verbose_name="대상 필드"
    )
    
    # 변경 내용
    original_value = models.TextField(
        verbose_name="원본 값",
        null=True,
        blank=True
    )
    suggested_value = models.TextField(
        verbose_name="제안 값"
    )
    
    # 제안 사유
    reason = models.TextField(
        verbose_name="제안 사유",
        max_length=1000,
        null=True,
        blank=True
    )
    
    # 상태
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('accepted', '승인'),
        ('rejected', '거절'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="상태"
    )
    
    # 처리자/처리일시
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_suggestions",
        verbose_name="처리자"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="처리 일시"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "v2_suggestion_mode"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['label', 'field_name']),
            models.Index(fields=['status']),
        ]
        verbose_name = "필드 변경 제안"
        verbose_name_plural = "필드 변경 제안 목록"

    def __str__(self):
        return f"{self.field_name}: {self.suggested_value[:30]} ({self.status})"
    
    def accept(self, user):
        """제안 승인 및 값 적용"""
        # 라벨에 값 적용
        if hasattr(self.label, self.field_name):
            setattr(self.label, self.field_name, self.suggested_value)
            self.label.save(update_fields=[self.field_name])
        
        self.status = 'accepted'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
    
    def reject(self, user):
        """제안 거절"""
        self.status = 'rejected'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()


# ==================== 공유 및 권한 관리 (통합) ====================

class ProductShare(models.Model):
    """
    제품 공유 정보
    - V1 MyLabel을 직접 참조하여 데이터 중복 제거
    - 특정 표시사항을 특정 이메일과 공유
    """
    SHARE_MODE_CHOICES = [
        ('PRIVATE', '비공개 (권한 관리)'),
        ('PUBLIC', '공개 링크'),
    ]
    
    share_id = models.AutoField(primary_key=True, verbose_name="공유 ID")
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name="v2_shares",
        verbose_name="표시사항"
    )
    
    # 공유 모드
    share_mode = models.CharField(
        max_length=20,
        choices=SHARE_MODE_CHOICES,
        default='PRIVATE',
        verbose_name="공유 모드"
    )
    
    # 공유 대상 (PRIVATE 모드)
    recipient_email = models.EmailField(
        max_length=255,
        verbose_name="수신자 이메일",
        null=True,
        blank=True,
        db_index=True,
        help_text="PRIVATE 모드에서만 사용"
    )
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="v2_received_shares",
        verbose_name="수신자 (회원)",
        help_text="이메일이 회원인 경우 자동 연결"
    )
    recipient_name = models.CharField(
        max_length=100,
        verbose_name="수신자 이름",
        null=True,
        blank=True,
        help_text="초대 시 입력한 이름 (선택)"
    )
    recipient_company = models.CharField(
        max_length=200,
        verbose_name="수신자 회사명",
        null=True,
        blank=True,
        help_text="초대 시 입력한 회사명 (선택)"
    )
    
    # 공개 링크 (PUBLIC 모드)
    public_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="공개 토큰",
        help_text="PUBLIC 모드에서 사용하는 고유 URL 토큰"
    )
    
    # 공유 정보
    share_message = models.TextField(
        max_length=1000,
        verbose_name="공유 메시지",
        null=True,
        blank=True
    )
    
    # 공유 기간
    share_start_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="공유 시작일"
    )
    share_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="공유 종료일",
        help_text="null이면 무기한"
    )
    
    # 상태
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성 상태"
    )
    
    # 생성자
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="v2_created_shares",
        verbose_name="공유자"
    )
    
    # 타임스탬프
    created_datetime = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_datetime = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = "v2_product_share"
        ordering = ['-created_datetime']
        indexes = [
            models.Index(fields=['recipient_email']),
            models.Index(fields=['public_token']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = "제품 공유"
        verbose_name_plural = "제품 공유 목록"

    def __str__(self):
        if self.share_mode == 'PUBLIC':
            return f"공개 링크: {self.label}"
        return f"{self.label} → {self.recipient_email or self.recipient_user}"
    
    def is_expired(self):
        """공유가 만료되었는지 확인"""
        if not self.share_end_date:
            return False
        return timezone.now() > self.share_end_date


class SharePermission(models.Model):
    """공유 권한 설정"""
    ROLE_CHOICES = [
        ('VIEWER', '단순 조회'),
        ('UPLOADER', '자료 제출'),
        ('EDITOR', '공동 편집'),
        ('REVIEWER', '검토자'),
        ('APPROVER', '승인자'),
    ]
    ROLE_DEFAULTS = {
        'VIEWER': {
            'can_view': True,
            'can_comment': True,
            'can_suggest': False,
            'can_use_as_ingredient': False,
            'can_download_documents': True,
            'can_upload_documents': False,
            'can_edit_label': False,
            'can_review': False,
            'can_approve': False,
        },
        'UPLOADER': {
            'can_view': True,
            'can_comment': False,
            'can_suggest': False,
            'can_use_as_ingredient': False,
            'can_download_documents': True,
            'can_upload_documents': True,
            'can_edit_label': False,
            'can_review': False,
            'can_approve': False,
        },
        'EDITOR': {
            'can_view': True,
            'can_comment': True,
            'can_suggest': True,
            'can_use_as_ingredient': True,
            'can_download_documents': True,
            'can_upload_documents': True,
            'can_edit_label': True,
            'can_review': True,
            'can_approve': False,
        },
        'REVIEWER': {
            'can_view': True,
            'can_comment': True,
            'can_suggest': False,
            'can_use_as_ingredient': False,
            'can_download_documents': True,
            'can_upload_documents': False,
            'can_edit_label': False,
            'can_review': True,
            'can_approve': False,
        },
        'APPROVER': {
            'can_view': True,
            'can_comment': True,
            'can_suggest': False,
            'can_use_as_ingredient': True,
            'can_download_documents': True,
            'can_upload_documents': False,
            'can_edit_label': False,
            'can_review': True,
            'can_approve': True,
        },
    }
    permission_id = models.AutoField(primary_key=True, verbose_name="권한 ID")
    share = models.OneToOneField(
        ProductShare,
        on_delete=models.CASCADE,
        related_name="permission",
        verbose_name="공유"
    )

    role_code = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='VIEWER',
        verbose_name="역할"
    )
    
    # 보기 권한
    can_view = models.BooleanField(
        default=True,
        verbose_name="보기"
    )
    
    # 댓글 권한
    can_comment = models.BooleanField(
        default=True,
        verbose_name="댓글 작성"
    )
    
    # 제안 권한
    can_suggest = models.BooleanField(
        default=False,
        verbose_name="수정 제안"
    )

    # 문서 업로드 권한
    can_upload_documents = models.BooleanField(
        default=False,
        verbose_name="문서 업로드"
    )

    # 제품 정보 수정 권한
    can_edit_label = models.BooleanField(
        default=False,
        verbose_name="정보 수정"
    )

    # 검토 권한
    can_review = models.BooleanField(
        default=False,
        verbose_name="검토"
    )

    # 승인 권한
    can_approve = models.BooleanField(
        default=False,
        verbose_name="승인"
    )
    
    # 원료로 사용 권한
    can_use_as_ingredient = models.BooleanField(
        default=True,
        verbose_name="원료로 사용",
        help_text="BOM에서 이 제품을 원료로 추가할 수 있는지"
    )
    
    # 다운로드 권한
    can_download_documents = models.BooleanField(
        default=True,
        verbose_name="문서 다운로드"
    )

    class Meta:
        db_table = "v2_share_permission"
        verbose_name = "공유 권한"
        verbose_name_plural = "공유 권한 목록"

    def __str__(self):
        return f"{self.share} 권한 ({self.role_code})"

    @property
    def role_label(self):
        return dict(self.ROLE_CHOICES).get(self.role_code, self.role_code)

    def apply_role_defaults(self, role_code=None, save=True):
        role = role_code or self.role_code
        defaults = self.ROLE_DEFAULTS.get(role)
        if not defaults:
            return
        self.role_code = role
        for field, value in defaults.items():
            setattr(self, field, value)
        if save:
            self.save()


class SharedProductReceipt(models.Model):
    """공유받은 제품 수령 기록"""
    receipt_id = models.AutoField(primary_key=True, verbose_name="수령 ID")
    share = models.ForeignKey(
        ProductShare,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="공유",
        db_column="share_id"
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="v2_received_products",
        verbose_name="수신자",
        db_column="receiver_id"
    )
    
    # 수신 일시 (DB 컬럼명: received_datetime)
    received_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name="수신일시"
    )
    
    # 수락 여부
    is_accepted = models.BooleanField(
        default=False,
        verbose_name="수락 여부"
    )
    accepted_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="수락 일시"
    )
    
    # 원료로 사용 여부 (DB 컬럼명: is_used_as_ingredient)
    is_used_as_ingredient = models.BooleanField(
        default=False,
        verbose_name="원료로 사용됨"
    )
    
    # 수신자 메모
    receiver_note = models.TextField(
        blank=True,
        verbose_name="수신자 메모"
    )

    class Meta:
        db_table = "v2_shared_product_receipt"
        unique_together = [['share', 'receiver']]
        ordering = ['-received_datetime']
        verbose_name = "공유 수령"
        verbose_name_plural = "공유 수령 목록"

    def __str__(self):
        status = "수락됨" if self.is_accepted else "대기중"
        return f"{self.receiver.username} ← {self.share.label} ({status})"
    
    def accept(self):
        """공유 수락"""
        self.is_accepted = True
        self.accepted_datetime = timezone.now()
        self.save()


class ShareAccessLog(models.Model):
    """공유 접근 로그"""
    log_id = models.AutoField(primary_key=True, verbose_name="로그 ID")
    share = models.ForeignKey(
        ProductShare,
        on_delete=models.CASCADE,
        related_name="access_logs",
        verbose_name="공유"
    )
    accessed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="v2_share_accesses",
        verbose_name="접근자"
    )
    accessed_ip = models.GenericIPAddressField(
        verbose_name="접근 IP",
        null=True,
        blank=True
    )
    accessed_datetime = models.DateTimeField(auto_now_add=True, verbose_name="접근일시")
    
    # 접근 정보
    user_agent = models.CharField(
        max_length=500,
        verbose_name="User Agent",
        null=True,
        blank=True
    )
    action = models.CharField(
        max_length=50,
        verbose_name="행동",
        help_text="view, download, comment 등"
    )

    class Meta:
        db_table = "v2_share_access_log"
        ordering = ['-accessed_datetime']
        indexes = [
            models.Index(fields=['share', 'accessed_datetime']),
        ]
        verbose_name = "공유 접근 로그"
        verbose_name_plural = "공유 접근 로그 목록"

    def __str__(self):
        user_info = self.accessed_by.username if self.accessed_by else self.accessed_ip
        return f"{user_info} - {self.share} ({self.action})"


class ProductNotification(models.Model):
    """
    제품 상태 변경 알림
    - 상태가 바뀌면 해당 단계 권한자에게 인앱 알림 생성
    """
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='표시사항'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_notifications',
        verbose_name='수신자'
    )
    message = models.CharField(max_length=500, verbose_name='알림 메시지')
    status_code = models.CharField(max_length=20, verbose_name='관련 상태',
                                   blank=True, default='')
    is_read = models.BooleanField(default=False, verbose_name='읽음 여부', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        db_table = 'v2_product_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['label', 'created_at']),
        ]
        verbose_name = '제품 알림'
        verbose_name_plural = '제품 알림 목록'

    def __str__(self):
        return f"{self.recipient.username} ← {self.label} ({self.status_code})"


class ProductActivityLog(models.Model):
    """
    제품 활동 로그
    - 제품 생성, 상태 변경, 댓글 작성 등의 이력 기록
    """
    ACTION_CHOICES = [
        ('CREATED', '제품 생성'),
        ('STATUS_CHANGED', '상태 변경'),
        ('COMMENT_ADDED', '댓글 작성'),
        ('INFO_UPDATED', '정보 수정'),
        ('DOCUMENT_UPLOADED', '문서 업로드'),
        ('DOCUMENT_DELETED', '문서 삭제'),
        ('SHARE_CREATED', '공유 생성'),
        ('SHARE_UPDATED', '공유 수정'),
        ('SHARE_DELETED', '공유 삭제'),
    ]
    
    log_id = models.AutoField(primary_key=True, verbose_name="로그 ID")
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name='activity_logs',
        verbose_name='표시사항'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_activities',
        verbose_name='사용자'
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        verbose_name='활동'
    )
    details = models.JSONField(
        verbose_name='상세정보',
        null=True,
        blank=True,
        help_text='상태 변경 전/후, 댓글 내용 등'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시'
    )
    
    class Meta:
        db_table = 'v2_product_activity_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['label', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action']),
        ]
        verbose_name = '제품 활동 로그'
        verbose_name_plural = '제품 활동 로그 목록'
    
    def __str__(self):
        username = self.user.username if self.user else '시스템'
        return f"{username} - {self.get_action_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
