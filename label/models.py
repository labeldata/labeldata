from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
import uuid

class FoodType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="활성 상태")

    def __str__(self):
        return self.name

class Post(models.Model):

    #외래키 연결 금지

    title = models.CharField(max_length=200)
    api_data = models.JSONField(null=True, blank=True, help_text="API에서 가져온 데이터")
    is_api_data = models.BooleanField(default=False, help_text="이 데이터가 API에서 가져온 데이터인지 여부")
    #food_type = models.ForeignKey(FoodType, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    manufacturer = models.CharField(max_length=100, db_index=True)
    ingredients = models.TextField()
    storage_conditions = models.CharField(max_length=100)
    precautions = models.TextField(blank=True, null=True)
    #author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class Comment(models.Model):
    #외래키 연결 금지

    #post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    #author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000, help_text="댓글 내용 (최대 1000자)")
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"

class FoodItem(models.Model):
        
    #컬럼명은 추후 변경할 수 있음. 현재는 api에서 받아오는 값으로 사용
    lcns_no = models.CharField(max_length=11, verbose_name = "인허가번호", help_text="영업에 대한 허가, 등록, 신고번호 11자리", db_index=True , null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name = "제조사명", default="기본제조사명")
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목제조번호", help_text="영업등록 발급연도-영업장 등록번호-영업장 제품번호", db_index=True, primary_key=True)
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", help_text="yyyymmdd", default="yyyymmdd")
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", db_index=True, default="기본제품명")
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="품목유형명", default="기본품목유형명")
    production = models.CharField(max_length=10, verbose_name="생산종료여부", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)   #api 컬럼 명칭은 HIENG_LNTRT_DVS_NM -> yn으로 변경
    child_crtfc_yn = models.CharField(max_length=10, verbose_name="어린이기호식품품질인증여부", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", default="기본소비기한", null=True, blank=True) # null 값 허용
    last_updt_dtm = models.CharField(max_length=8, verbose_name="최종수정일자", default="yyyymmdd", null=True, blank=True) # null 값 허용
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", default="기본업종명", null=True, blank=True) # null 값 허용
    qlity_mntnc_tmlmt_daycnt = models.CharField(max_length=100, verbose_name="품질유지기한일수", null=True, blank=True)
    usages = models.TextField(max_length=4000, verbose_name="용법", null=True, blank=True) #mysql usage - 키워드로 인해 변경
    prpos = models.CharField(max_length=200, verbose_name="용도", null=True, blank=True)
    dispos = models.CharField(max_length=200, verbose_name="제품형태", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    update_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Food_Item'
        indexes = [
            models.Index(fields=['lcns_no'], name='idx_lcns_no'),
            models.Index(fields=['prdlst_report_no'], name='idx_prdlst_report_no'),
            models.Index(fields=['prdlst_nm'], name='idx_prdlst_nm'),
        ]

    def __str__(self):
        return self.prdlst_nm

class MyProduct(models.Model):
    """내제품 관리 모델"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="사용자")
    unique_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name="고유 키", null=True, blank=True)
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목제조번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명")
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="품목유형명")
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명")
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)
    qlity_mntnc_tmlmt_daycnt = models.CharField(max_length=100, verbose_name="품질유지기한일수", null=True, blank=True)
    content_weight = models.CharField(max_length=50, verbose_name="내용량(열량)", null=True, blank=True)
    manufacturer_address = models.CharField(max_length=255, verbose_name="제조원 소재지", null=True, blank=True)
    storage_method = models.TextField(verbose_name="보관방법", null=True, blank=True)
    distributor_name = models.CharField(max_length=200, verbose_name="유통전문판매원", null=True, blank=True)
    distributor_address = models.CharField(max_length=255, verbose_name="유통전문판매원 소재지", null=True, blank=True)
    
    # ✅ 추가된 필드
    origin = models.CharField(max_length=100, verbose_name="원산지", null=True, blank=True)
    importer_address = models.CharField(max_length=255, verbose_name="수입원 및 소재지", null=True, blank=True)
    
    warnings = models.TextField(verbose_name="주의사항", null=True, blank=True)
    additional_info = models.TextField(verbose_name="기타 표시사항", null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    label_created = models.BooleanField(default=False, verbose_name="표시사항 작성 여부")

    def __str__(self):
        return self.prdlst_nm or f"제품 (고유 키: {self.unique_key})"

class Allergen(models.Model):
    """알레르기 물질 목록"""
    name = models.CharField(max_length=50, unique=True, verbose_name="알레르기 물질")

    def __str__(self):
        return self.name     

class FrequentlyUsedText(models.Model):
    """자주 사용하는 문구 저장 모델"""
    category = models.CharField(max_length=100, verbose_name="문구 카테고리")  # 예: '주의사항', '기타 표시사항'
    text = models.TextField(verbose_name="문구 내용")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.category}] {self.text[:50]}"
  
class MyIngredients(models.Model):
    """내원료 저장 모델"""
    prdlst_report_no = models.CharField(max_length=16, unique=True, verbose_name="품목제조번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명")
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명")
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", null=True, blank=True)
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)

    def __str__(self):
        return self.prdlst_nm
  
class Label(models.Model):
    """표시사항 모델"""
    my_product = models.ForeignKey(MyProduct, on_delete=models.CASCADE, related_name="labels", verbose_name="연결된 내제품")

    # 기존 필드
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목제조번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", null=True, blank=True)
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="품목유형명", null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    storage_method = models.TextField(verbose_name="보관방법", null=True, blank=True)
    content_weight = models.CharField(max_length=50, verbose_name="내용량(열량)", null=True, blank=True)
    manufacturer_address = models.CharField(max_length=255, verbose_name="제조원 소재지", null=True, blank=True)

    # 추가 필드
    origin = models.CharField(max_length=100, verbose_name="원산지", null=True, blank=True)
    importer_address = models.CharField(max_length=255, verbose_name="수입원 및 소재지", null=True, blank=True)

    # 관계 설정
    allergens = models.ManyToManyField(Allergen, blank=True, verbose_name="알레르기 물질")
    ingredients = models.ManyToManyField(MyIngredients, blank=True, related_name="labels", verbose_name="연결된 원재료")  # 추가됨

    distributor_name = models.CharField(max_length=200, verbose_name="유통전문판매원", null=True, blank=True)
    distributor_address = models.CharField(max_length=255, verbose_name="유통전문판매원 소재지", null=True, blank=True)
    warnings = models.TextField(verbose_name="주의사항", null=True, blank=True)
    additional_info = models.TextField(verbose_name="기타 표시사항", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Label for {self.my_product.prdlst_nm if self.my_product else 'Unknown Product'}"

class LabelOrder(models.Model):
    """표시사항 필드 순서 관리 모델"""
    label = models.OneToOneField(Label, on_delete=models.CASCADE, related_name="order", verbose_name="연결된 라벨")  # 변경됨
    order = models.TextField(verbose_name="필드 순서 (JSON 형식)")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.label.my_product.prdlst_nm}의 필드 순서"