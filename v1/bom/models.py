"""
BOM (Bill of Materials) 모델 (V2)
- 다단계 제품 구성 관리
- 트리 구조로 원료 관계 표현
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class ProductBOM(models.Model):
    """
    제품 구성 정보 (BOM)
    - V1 MyLabel을 직접 참조하여 데이터 중복 제거
    - 내 제품 or 공유받은 제품을 원료로 사용 가능
    """
    bom_id = models.AutoField(primary_key=True, verbose_name="BOM ID")
    
    # 완제품 (부모) - V1 MyLabel 직접 참조
    parent_label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name="bom_items",
        verbose_name="완제품 표시사항"
    )
    
    # 원료 (자식) - 내 제품 (V1 MyLabel)
    child_label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="used_in_boms",
        verbose_name="원료 표시사항",
        help_text="내가 소유한 표시사항을 원료로 사용"
    )
    
    # 원료 (자식) - 공유받은 제품
    shared_receipt = models.ForeignKey(
        'products.SharedProductReceipt',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="used_in_boms",
        verbose_name="공유받은 원료",
        help_text="공유받은 제품을 원료로 사용"
    )
    
    # 원료 정보 (child_version과 shared_receipt 중 하나는 필수 - 또는 단순 텍스트 입력)
    ingredient_name = models.CharField(
        max_length=200,
        verbose_name="원재료명",
        help_text="표시용 원재료명"
    )

    # 표시사항 핵심 정보
    raw_material_name = models.TextField(
        verbose_name="표시용 원료명",
        null=True,
        blank=True,
        help_text="라벨에 표시될 명칭 (예: 정백당 -> 설탕)"
    )
    sub_ingredients = models.TextField(
        verbose_name="복합원재료 내역",
        null=True,
        blank=True,
        help_text="예: 탈지대두, 소맥, 천일염"
    )
    allergens = models.CharField(
        max_length=255,
        verbose_name="알레르기 정보",
        null=True,
        blank=True,
        help_text="대두, 밀, 우유 등"
    )
    gmo = models.CharField(
        max_length=255,
        verbose_name="GMO 성분",
        null=True,
        blank=True,
        help_text="대두, 옥수수 등 선택된 GMO 성분"
    )
    origin_detail = models.CharField(
        max_length=255,
        verbose_name="원산지 상세",
        null=True,
        blank=True,
        help_text="예: 국산 50%, 수입산 50%"
    )
    food_type = models.CharField(
        max_length=100,
        verbose_name="식품유형",
        null=True,
        blank=True,
        help_text="예: 소스류, 과채가공품"
    )

    # 규제/검증용 정보
    is_additive = models.BooleanField(
        default=False,
        verbose_name="식품첨가물 여부"
    )
    additive_role = models.CharField(
        max_length=100,
        verbose_name="첨가물 용도",
        null=True,
        blank=True,
        help_text="예: 보존료, 착색료"
    )
    is_gmo = models.BooleanField(
        default=False,
        verbose_name="GMO 여부"
    )
    report_no = models.CharField(
        max_length=50,
        verbose_name="품목보고번호",
        null=True,
        blank=True
    )
    manufacturer = models.CharField(
        max_length=200,
        verbose_name="제조사/수입사",
        null=True,
        blank=True
    )
    source_ingredient = models.ForeignKey(
        'label.MyIngredient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_usages',
        verbose_name="연동 원료",
        help_text="내 원료 보관함의 원료 (직접 입력 시 자동 생성됨)"
    )
    
    # 함량/배합 정보
    usage_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="함량 (%)",
        null=True,
        blank=True,
        help_text="전체 제품 중 이 원료의 함량 비율"
    )
    
    # 원산지 정보
    origin = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="원산지",
        help_text="예: 국내산, 미국산"
    )
    
    # 알레르기 정보
    allergen = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="알레르기",
        help_text="알레르기 유발 물질"
    )
    
    # 레거시 필드 (호환성 유지)
    usage_amount = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="사용량",
        help_text="실제 사용량 (숫자) - 레거시"
    )
    usage_unit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="사용량 단위",
        help_text="g, kg, ml, L 등 - 레거시"
    )
    
    # 계층 정보
    level = models.IntegerField(
        default=1,
        verbose_name="레벨",
        help_text="1=직접 원료, 2=원료의 원료, ..."
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name="정렬 순서",
        help_text="같은 레벨 내에서의 순서"
    )
    
    # 추가 정보
    notes = models.TextField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name="비고"
    )

    summary_type = models.CharField(
        max_length=20,
        default='식품유형',
        verbose_name="표시명 기준",
        help_text="원재료 표시명 생성 시 사용할 기준 (식품유형 / 원재료명)"
    )

    # 상태
    is_active = models.BooleanField(
        default=True,
        verbose_name="활성 상태"
    )
    
    # 메타 정보
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="v2_created_boms",
        verbose_name="생성자"
    )
    created_datetime = models.DateTimeField(
        auto_now_add=True,
        verbose_name="생성일시"
    )
    updated_datetime = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일시"
    )
    
    class Meta:
        db_table = "v2_product_bom"
        ordering = ['parent_label', 'level', 'sort_order']
        indexes = [
            models.Index(fields=['parent_label', 'level']),
            models.Index(fields=['child_label']),
            models.Index(fields=['shared_receipt']),
        ]
        verbose_name = "제품 BOM"
        verbose_name_plural = "제품 BOM 목록"
    
    def __str__(self):
        return f"{self.parent_label.my_label_name} > {self.ingredient_name}"
    
    def clean(self):
        """유효성 검증"""
        # child_label과 shared_receipt 중 정확히 하나만 있어야 함
        if not self.child_label and not self.shared_receipt:
            raise ValidationError("내 제품 또는 공유받은 제품 중 하나는 필수입니다.")
        
        if self.child_label and self.shared_receipt:
            raise ValidationError("내 제품과 공유받은 제품을 동시에 선택할 수 없습니다.")
        
        # 순환 참조 방지
        if self.child_label:
            if self._creates_circular_reference():
                raise ValidationError("순환 참조가 발생합니다. 이 원료를 추가할 수 없습니다.")
    
    def _creates_circular_reference(self):
        """순환 참조 확인"""
        if not self.child_label:
            return False
        
        # child_label이 parent_label과 같으면 자기 참조
        if self.child_label == self.parent_label:
            return True
        
        # child_label의 BOM을 재귀적으로 확인
        def check_descendants(label):
            child_boms = ProductBOM.objects.filter(parent_label=label, is_active=True)
            for bom in child_boms:
                if bom.child_label == self.parent_label:
                    return True
                if bom.child_label and check_descendants(bom.child_label):
                    return True
            return False
        
        return check_descendants(self.child_label)
    
    def get_ingredient_product(self):
        """원료 제품 정보 반환"""
        if self.child_label:
            return self.child_label
        elif self.shared_receipt:
            return self.shared_receipt.share.label
        return None
    
    def get_all_descendants(self):
        """모든 하위 원료 (재귀)"""
        descendants = []
        ingredient = self.get_ingredient_product()
        
        if ingredient:
            child_boms = ProductBOM.objects.filter(
                parent_label=ingredient,
                is_active=True
            )
            
            for child_bom in child_boms:
                descendants.append(child_bom)
                descendants.extend(child_bom.get_all_descendants())
        
        return descendants
