from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


# class FoodType(models.Model):
#     name = models.CharField(max_length=200, unique=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     is_active = models.BooleanField(default=True, help_text="활성 상태")

#     def __str__(self):
#         return self.name

# class Post(models.Model):

#     #외래키 연결 금지
#     title = models.CharField(max_length=200)
#     api_data = models.JSONField(null=True, blank=True, help_text="API에서 가져온 데이터")
#     is_api_data = models.BooleanField(default=False, help_text="이 데이터가 API에서 가져온 데이터인지 여부")
#     #food_type = models.ForeignKey(FoodType, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
#     manufacturer = models.CharField(max_length=100, db_index=True)
#     ingredients = models.TextField()
#     storage_conditions = models.CharField(max_length=100)
#     precautions = models.TextField(blank=True, null=True)
#     #author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
#     create_date = models.DateTimeField(default=now)
#     modify_date = models.DateTimeField(null=True, blank=True)

#     def __str__(self):
#         return self.title


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
        db_table = "food_item"
        indexes = [
            models.Index(fields=["lcns_no"], name="idx_lcns_no"),
            models.Index(fields=["prdlst_report_no"], name="idx_prdlst_report_no"),
            models.Index(fields=["prdlst_nm"], name="idx_prdlst_nm"),
        ]

    def __str__(self):
        return self.prdlst_report_no

class Allergen(models.Model):
    # 알레르기 물질 목록
    allergen_name = models.CharField(max_length=50, unique=True, verbose_name="알레르기 물질")

    class Meta:
        db_table = "allergen"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.allergen_name     

    
#개인 유저가 쓴다면 아래와 같이
class MyPhrase(models.Model):
    # 자주 사용하는 문구 저장 모델
    user_id = models.ForeignKey(User, related_name="user_phrase", on_delete=models.CASCADE, db_column="id", verbose_name="사용자 id")

    #id = 자동생성
    my_phrase_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_phrase_key = models.CharField(max_length=50, unique=True, verbose_name="내 문구키", primary_key=True)
    my_phrase_name = models.CharField(max_length=200, verbose_name="내 문구명")

    category_name = models.CharField(max_length=100, verbose_name="문구 카테고리")  # 예: '주의사항', '기타 표시사항'
    comment_content = models.TextField(max_length=1000, verbose_name="문구 내용")

    #create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)

    # 데이터 삭제시 db 삭제가 아니라 플래그 처리로 보이지만 않게
    delete_datetime = models.CharField(max_length=8, verbose_name="삭제일자", help_text="yyyymmdd", default="")
    delete_YN = models.CharField(max_length=1, verbose_name="내 제품 삭제 여부" )

    class Meta:
        db_table = "my_comment_storage"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.my_phrase_id
    
class MyIngredient(models.Model):
    # 내 원료 저장 모델
    user_id = models.ForeignKey(User, related_name="user_ingredient", on_delete=models.CASCADE, db_column="id", verbose_name="사용자 id")

    #id = 자동생성
    my_ingredient_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_ingredient_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name="내 원료키", primary_key=True)
    my_ingredient_name = models.CharField(max_length=200, verbose_name="내 원료명")
    
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목제조번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명")
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명")
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", null=True, blank=True)
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)

    update_datetime = models.DateTimeField(auto_now=True)

    # 데이터 삭제시 db 삭제가 아니라 플래그 처리로 보이지만 않게
    delete_datetime = models.CharField(max_length=8, verbose_name="삭제일자", help_text="yyyymmdd", default="")
    delete_YN = models.CharField(max_length=1, verbose_name="내 제품 삭제 여부" )

    class Meta:
        db_table = "my_ingredient"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.my_ingredient_id
  
class MyLabel(models.Model):
    # 표시사항 모델
    user_id = models.ForeignKey(User, related_name="user_label", on_delete=models.CASCADE, db_column="id", verbose_name="사용자 id")

    #id = 자동생성
    my_label_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_label_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name="내 표시사항 키", primary_key=True)
    my_label_name = models.CharField(max_length=200, verbose_name="라벨명")

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
    country_of_origin = models.CharField(max_length=100, verbose_name="원산지", null=True, blank=True)
    importer_address = models.CharField(max_length=255, verbose_name="수입원 및 소재지", null=True, blank=True)

    # 관계 설정
    #allergens = models.ManyToManyField(Allergen, blank=True, verbose_name="알레르기 물질")
    #ingredients = models.ManyToManyField(MyIngredients, blank=True, related_name="labels", verbose_name="연결된 원재료")  # 추가됨

    distributor_name = models.CharField(max_length=200, verbose_name="유통전문판매원", null=True, blank=True)
    distributor_address = models.CharField(max_length=255, verbose_name="유통전문판매원 소재지", null=True, blank=True)
    cautions = models.TextField(verbose_name="주의사항", null=True, blank=True)
    additional_info = models.TextField(verbose_name="기타 표시사항", null=True, blank=True)

    create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)
    label_create_YN = models.CharField(max_length=1, verbose_name="표시 사항 작성 여부", default="N" )

    # 데이터 삭제시 db 삭제가 아니라 플래그 처리로 보이지만 않게
    delete_datetime = models.CharField(max_length=8, verbose_name="삭제일자", help_text="yyyymmdd", default="")
    delete_YN = models.CharField(max_length=1, verbose_name="내 제품 삭제 여부", default="N" )

    class Meta:
        db_table = "my_label"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.my_label_id

# 추후 업무에 필요한 모델은 추후 재 작성
# class LabelOrder(models.Model):
#     """표시사항 필드 순서 관리 모델"""
#     label = models.OneToOneField(Label, on_delete=models.CASCADE, related_name="order", verbose_name="연결된 라벨")  # 변경됨
#     order = models.TextField(verbose_name="필드 순서 (JSON 형식)")
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.label.my_product.prdlst_nm}의 필드 순서"