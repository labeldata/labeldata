from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class FoodItem(models.Model):
    #컬럼명은 추후 변경할 수 있음. 현재는 api에서 받아오는 값으로 사용
    lcns_no = models.CharField(max_length=11, verbose_name = "인허가번호", help_text="영업에 대한 허가, 등록, 신고번호 11자리", db_index=True , null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name = "제조사명", default="기본제조사명")
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목보고번호", help_text="영업등록 발급연도-영업장 등록번호-영업장 제품번호", db_index=True, primary_key=True)
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
   
#개인 유저가 쓴다면 아래와 같이
class MyPhrase(models.Model):
    # 자주 사용하는 문구 저장 모델
    user_id = models.ForeignKey(User, related_name="user_phrase", on_delete=models.CASCADE, db_column="user_id", verbose_name="사용자 id")

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
    user_id = models.ForeignKey(User, related_name="user_ingredient", on_delete=models.CASCADE, db_column="user_id", verbose_name="사용자 id")

    #id = 자동생성
    my_ingredient_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_ingredient_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name="내 원료키", primary_key=True)
    #my_ingredient_name = models.CharField(max_length=200, verbose_name="내 원료명")
    
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목보고번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="원료명")
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명")
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", null=True, blank=True)
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="하위 원료", null=True, blank=True)
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)

    #ingredient_ratio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="원료 비율(%)", null=True, blank=True)
    ingredient_display_name = models.CharField(max_length=1000, verbose_name="원료 표시명", null=True, blank=True)

    allergens = models.CharField(max_length=1000, verbose_name="알레르기 물질", null=True, blank=True)
    gmo =  models.CharField(max_length=500, verbose_name="GMO", null=True, blank=True)

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
    
    def save(self, *args, **kwargs):
        """search_name이 비어 있을 경우, 기본값으로 id 사용"""
        super().save(*args, **kwargs)
  
class MyLabel(models.Model):
    # 표시사항 모델
    user_id = models.ForeignKey(User, related_name="user_label", on_delete=models.CASCADE, db_column="user_id", verbose_name="사용자 id")

    #id = 자동생성
    my_label_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_label_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name="내 표시사항 키", primary_key=True)

    food_group = models.CharField(max_length=100, verbose_name="식품군", null=True, blank=True)
    food_type = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)

    preservation_type = models.CharField(max_length=100, verbose_name="장기보존식품", null=True, blank=True)
    processing_method = models.CharField(max_length=100, verbose_name="제조방법", null=True, blank=True)
    processing_condition = models.CharField(max_length=100, verbose_name="제조방법 조건", null=True, blank=True)

    my_label_name = models.CharField(max_length=200, verbose_name="라벨명")

    # 기존 필드
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    #food_type = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)

    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", null=True, blank=True)
    ingredient_info = models.TextField(max_length=1000, verbose_name="성분명 및 함량", null=True, blank=True)

    content_weight = models.CharField(max_length=50, verbose_name="내용량", null=True, blank=True)
    weight_calorie = models.CharField(max_length=50, verbose_name="내용량(열량)", null=True, blank=True)

    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목보고번호", null=True, blank=True)
    country_of_origin = models.CharField(max_length=255, verbose_name="원산지", null=True, blank=True)

    storage_method = models.CharField(max_length=300, verbose_name="보관방법", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)

    bssh_nm = models.CharField(max_length=500, verbose_name="제조원 소재지", null=True, blank=True)
    #manufacturer_etc = models.CharField(max_length=500, verbose_name="제조원 외", null=True, blank=True)
    distributor_address = models.CharField(max_length=500, verbose_name="유통전문판매원 소재지", null=True, blank=True)
    repacker_address = models.CharField(max_length=500, verbose_name="소분원 소재지", null=True, blank=True)
    importer_address = models.CharField(max_length=500, verbose_name="수입원 소재지", null=True, blank=True)

    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", default="기본소비기한", null=True, blank=True)

    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    rawmtrl_nm_display = models.TextField(max_length=1000, verbose_name="원재료명(표시)", null=True, blank=True)
    
    cautions = models.TextField(max_length=1000, verbose_name="주의사항", null=True, blank=True)
    additional_info = models.TextField(max_length=1000, verbose_name="기타 표시사항", null=True, blank=True)

    #relevant_regulations = models.TextField(verbose_name="식품유형별 관련규정", null=True, blank=True)

    calories = models.CharField(max_length=10, verbose_name="칼로리", null=True, blank=True)
    natriums = models.CharField(max_length=10, verbose_name="나트륨", null=True, blank=True)
    carbohydrates = models.CharField(max_length=10, verbose_name="탄수화물", null=True, blank=True)
    sugars = models.CharField(max_length=10, verbose_name="당류", null=True, blank=True)
    fats = models.CharField(max_length=10, verbose_name="지방", null=True, blank=True)
    trans_fats = models.CharField(max_length=10, verbose_name="트랜스지방", null=True, blank=True)
    saturated_fats = models.CharField(max_length=10, verbose_name="포화지방", null=True, blank=True)
    cholesterols = models.CharField(max_length=10, verbose_name="콜레스테롤", null=True, blank=True)
    proteins = models.CharField(max_length=10, verbose_name="단백질", null=True, blank=True)
    
    create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)
    label_create_YN = models.CharField(max_length=1, verbose_name="표시사항 작성여부", default="N" )
    #ingredient_create_YN = models.CharField(max_length=1, verbose_name="원재료 작성 여부", default="N" )

    # 데이터 삭제시 db 삭제가 아니라 플래그 처리로 보이지만 않게
    delete_datetime = models.CharField(max_length=8, verbose_name="삭제일자", help_text="yyyymmdd", default="")
    delete_YN = models.CharField(max_length=1, verbose_name="표시사항 삭제 여부", default="N" )

    # ManyToMany 관계 설정
    ingredients = models.ManyToManyField(
        'MyIngredient',  # 문자열로 참조하여 순환 참조 방지
        through='LabelIngredientRelation',
        through_fields=('label', 'ingredient'),
        related_name='labels',
        verbose_name="연결된 원재료"
    )

    class Meta:
        db_table = "my_label"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.my_label_name
    
    # def update_ingredient_ids(self):
    #     """
    #     ManyToMany 관계(ingredients) 기반으로 캐싱 필드를 업데이트.
    #     """
    #     # ingredients 필드에서 모든 원재료 ID를 가져옴
    #     ids = list(self.ingredients.values_list('my_ingredient_id', flat=True))
    #     # 쉼표 구분 문자열 업데이트
    #     self.ingredient_ids_str = ",".join(map(str, ids))
    #     # JSON 필드 업데이트
    #     self.ingredient_ids_json = ids
    #     self.save(update_fields=["ingredient_ids_str", "ingredient_ids_json"])

    def get_ingredient_queryset(self):
        """
        캐싱 필드가 있으면 이를 사용하여 MyIngredient 객체들을 조회하고,
        그렇지 않으면 ManyToMany 관계를 통해 조회합니다.
        """
        if self.ingredient_ids_json:
            return MyIngredient.objects.filter(my_ingredient_id__in=self.ingredient_ids_json)
        return self.ingredients.all()

    def get_related_ingredient_names(self):
        """
        연결된 모든 원재료의 prdlst_nm을 쉼표로 구분하여 반환합니다.
        """
        return ", ".join(self.ingredients.values_list('prdlst_nm', flat=True))

class FoodType(models.Model):
    
    food_group = models.CharField(max_length=100, verbose_name="식품군", default='default_group')
    #food_category = models.CharField(max_length=100, verbose_name="식품분류", default='default_category')
    food_type = models.CharField(max_length=100, verbose_name="식품유형", db_index=True, primary_key=True)

    weight_calorie = models.CharField(max_length=1, verbose_name="내용량(열량)", null=True, blank=True)
    prdlst_report_no = models.CharField(max_length=1, verbose_name="품목보고번호", null=True, blank=True)
    frmlc_mtrqlt = models.CharField(max_length=1, verbose_name="포장재질", null=True, blank=True)
    pog_daycnt  = models.CharField(max_length=1, verbose_name="소비기한", null=True, blank=True)

    rawmtrl_nm = models.CharField(max_length=1, verbose_name="원재료명", null=True, blank=True)
    storage_method = models.CharField(max_length=1, verbose_name="보관방법", null=True, blank=True)

    calories = models.CharField(max_length=1, verbose_name="칼로리", null=True, blank=True)
    natriums = models.CharField(max_length=1, verbose_name="나트륨", null=True, blank=True)
    carbohydrates = models.CharField(max_length=1, verbose_name="탄수화물", null=True, blank=True)
    sugars = models.CharField(max_length=1, verbose_name="당류", null=True, blank=True)
    fats = models.CharField(max_length=1, verbose_name="지방", null=True, blank=True)
    trans_fats = models.CharField(max_length=1, verbose_name="트랜스지방", null=True, blank=True)
    saturated_fats = models.CharField(max_length=1, verbose_name="포화지방", null=True, blank=True)
    cholesterols = models.CharField(max_length=1, verbose_name="콜레스테롤", null=True, blank=True)
    proteins = models.CharField(max_length=1, verbose_name="단백질", null=True, blank=True)

    cautions = models.CharField(max_length=1, verbose_name="주의사항", null=True, blank=True)

    type_check = models.CharField(max_length=1, verbose_name="구분", null=True, blank=True)

    class Meta:
        db_table = "Food_Type"
        indexes = [
            models.Index(fields=['food_type'], name='idx_food_type'),
        ]

    def __str__(self):
        return self.prdlst_dcnm    
    
class CountryList(models.Model):
    # 국가명 목록, 외교부_국가표준코드_20250102.csv
    country_code = models.CharField(max_length=3, verbose_name="국가코드 alpha3" , null=True, blank=True)
    country_code2 = models.CharField(max_length=2, verbose_name="국가코드 alpha2" , primary_key=True)
    numeric_code = models.CharField(max_length=3, verbose_name="국가코드 숫자" , null=True, blank=True)
    country_name_en = models.CharField(max_length=50, verbose_name="영문 국가명" , null=True, blank=True)
    country_name_ko = models.CharField(max_length=50, verbose_name="한글 국가명" , null=True, blank=True)

    class Meta:
        db_table = "country_list"
        indexes = [
            models.Index(fields=['country_code2'], name='idx_country_code2'),
        ]
        
    def __str__(self):
        return self.country_name_ko

class LabelIngredientRelation(models.Model):
    # 새로운 기본키 필드 (라벨ID와 원재료ID를 조합)
    relation_id = models.CharField(max_length=255, primary_key=True, editable=False)
    
    # 기본 관계 필드
    label = models.ForeignKey(MyLabel, on_delete=models.CASCADE, related_name='ingredient_relations')
    ingredient = models.ForeignKey(
        'MyIngredient', 
        on_delete=models.CASCADE, 
        related_name='label_relations',
        to_field='my_ingredient_id'  # my_ingredient_id를 외래 키로 사용
    )
    
    # 추가 필드들
    ingredient_ratio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="원료 비율(%)", null=True, blank=True)
    relation_sequence = models.IntegerField(verbose_name="원재료 순서", default=1)
    
    # 메타데이터
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "label_ingredient_relation"
        unique_together = ('label', 'ingredient')
        ordering = ['ingredient_ratio']
        verbose_name = "라벨-원료 관계"
        verbose_name_plural = "라벨-원료 관계들"

    def save(self, *args, **kwargs):
        # label과 ingredient가 모두 설정된 후에 relation_id를 생성합니다.
        if not self.relation_id and self.label_id and self.ingredient_id:
            self.relation_id = f"{self.label_id}a{self.ingredient_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label.my_label_name} - {self.ingredient.my_ingredient_name}"