from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class FoodType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="활성 상태")

    def __str__(self):
        return self.name

class Post(models.Model):
    title = models.CharField(max_length=200)
    api_data = models.JSONField(null=True, blank=True, help_text="API에서 가져온 데이터")
    is_api_data = models.BooleanField(default=False, help_text="이 데이터가 API에서 가져온 데이터인지 여부")
    food_type = models.ForeignKey(FoodType, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    manufacturer = models.CharField(max_length=100, db_index=True)
    ingredients = models.TextField()
    storage_conditions = models.CharField(max_length=100)
    precautions = models.TextField(blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000, help_text="댓글 내용 (최대 1000자)")
    create_date = models.DateTimeField(default=now)
    modify_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"

class FoodItem(models.Model):
    
    #product_name = models.CharField(max_length=255, help_text="제품 이름", db_index=True)
    #manufacturer_name = models.CharField(max_length=255, help_text="제조사 이름", db_index=True)
    #report_date = models.DateField(help_text="신고일")
    #category = models.CharField(max_length=255, help_text="카테고리")
    #additional_details = models.JSONField(blank=True, null=True, help_text="추가 세부사항 (JSON 형식)")
    
    #컬럼명은 추후 변경할 수 있음. 현재는 api에서 받아오는 값으로 사용
    lcns_no = models.CharField(max_length=11, verbose_name = "인허가번호", help_text="영업에 대한 허가, 등록, 신고번호 11자리", db_index=True , null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name = "제조사명", default="기본제조사명")
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목제조번호", help_text="영업등록 발급연도-영업장 등록번호-영업장 제품번호", db_index=True, null=True, blank=True)
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", help_text="yyyymmdd", default="yyyymmdd")
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", db_index=True, default="기본제품명")
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="품목유형명", default="기본품목유형명")
    production = models.CharField(max_length=10, verbose_name="생산종료여부", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)   #api 컬럼 명칭은 HIENG_LNTRT_DVS_NM -> yn으로 변경
    child_crtfc_yn = models.CharField(max_length=10, verbose_name="어린이기호식품품질인증여부", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", default="기본소비기한")
    last_updt_dtm = models.CharField(max_length=8, verbose_name="최종수정일자", default="yyyymmdd")
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", default="기본업종명")
    qlity_mntnc_tmlmt_daycnt = models.CharField(max_length=100, verbose_name="품질유지기한일수", null=True, blank=True)
    usages = models.TextField(max_length=4000, verbose_name="용법", null=True, blank=True) #mysql usage - 키워드로 인해 변경
    prpos = models.CharField(max_length=200, verbose_name="용도", null=True, blank=True)
    dispos = models.CharField(max_length=200, verbose_name="제품형태", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)

    class Meta:
        db_table = 'Food_Item'
        indexes = [
            models.Index(fields=['lcns_no'], name='idx_lcns_no'),
            models.Index(fields=['prdlst_report_no'], name='idx_prdlst_report_no'),
            models.Index(fields=['prdlst_nm'], name='idx_prdlst_nm'),
        ]

    def __str__(self):
        return self.product_name


class Label(models.Model):

    #food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="labels", null=False)
    content_weight = models.CharField(max_length=50, help_text="내용량(열량)")
    manufacturer_address = models.CharField(max_length=255, help_text="제조원 소재지")
    storage_method = models.TextField(help_text="보관방법")

    def __str__(self):
        return f"Label for {self.food_item.product_name}"
