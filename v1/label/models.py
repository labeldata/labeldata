from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone  # timezone 모듈 import 추가
from .constants import CATEGORY_CHOICES


class FoodItem(models.Model):
    #컬럼명은 추후 변경할 수 있음. 현재는 api에서 받아오는 값으로 사용
    lcns_no = models.CharField(max_length=11, verbose_name = "인허가번호", help_text="영업에 대한 허가, 등록, 신고번호 11자리", db_index=True , null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name = "제조사명", db_index=True, default="")
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목보고번호", help_text="영업등록 발급연도-영업장 등록번호-영업장 제품번호", db_index=True, primary_key=True)
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", db_index=True, help_text="yyyymmdd", default="")
    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", db_index=True, default="")
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="품목유형명", db_index=True, default="")
    production = models.CharField(max_length=10, verbose_name="생산종료여부", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)   #api 컬럼 명칭은 HIENG_LNTRT_DVS_NM -> yn으로 변경
    child_crtfc_yn = models.CharField(max_length=10, verbose_name="어린이기호식품품질인증여부", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", db_index=True, null=True, blank=True) # null 값 허용
    last_updt_dtm = models.CharField(max_length=8, verbose_name="최종수정일자", null=True, blank=True) # null 값 허용
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True) # null 값 허용
    qlity_mntnc_tmlmt_daycnt = models.CharField(max_length=100, verbose_name="품질유지기한일수", null=True, blank=True)
    usages = models.TextField(max_length=4000, verbose_name="용법", null=True, blank=True) #mysql usage - 키워드로 인해 변경
    prpos = models.CharField(max_length=200, verbose_name="용도", null=True, blank=True)
    dispos = models.CharField(max_length=200, verbose_name="제품형태", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    rawmtrl_ordno = models.TextField(max_length=1000, verbose_name="원재료순서", null=True, blank=True)  #
    rawmtrl_nm_sorted = models.TextField(max_length=1000, verbose_name="원재료명 정렬", null=True, blank=True)  #
    update_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "food_item"
        # lcns_no / prdlst_nm 은 필드의 db_index=True 가, prdlst_report_no 는 PK 가
        # 이미 인덱스를 만든다. 같은 컬럼에 두 벌씩 걸려 있어(인덱스 16MB > 데이터 9.5MB)
        # label/0020 마이그레이션으로 제거했다.
        indexes = [
            models.Index(fields=["last_updt_dtm"], name="idx_last_updt_dtm"),
        ]

    def __str__(self):
        return self.prdlst_report_no
   

class MyPhrase(models.Model):
    user_id = models.ForeignKey(User, related_name="user_phrase", on_delete=models.CASCADE, db_column="user_id", verbose_name="사용자 id")
    my_phrase_id = models.AutoField(primary_key=True)
    my_phrase_name = models.CharField(max_length=200, verbose_name="내 문구명")
    category_name = models.CharField(
        max_length=100,
        verbose_name="문구 카테고리",
        choices=CATEGORY_CHOICES  # 올바른 키워드 인자
    )
    comment_content = models.TextField(max_length=1000, verbose_name="문구 내용")
    note = models.CharField(max_length=200, verbose_name="사용조건", null=True, blank=True)  # 새로운 필드 추가
    create_datetime = models.DateTimeField(auto_now_add=True, null=True, verbose_name="생성일시")
    update_datetime = models.DateTimeField(auto_now=True, verbose_name="수정일시")
    delete_datetime = models.CharField(max_length=8, verbose_name="삭제일자", help_text="yyyymmdd", default="", blank=True)
    delete_YN = models.CharField(max_length=1, verbose_name="삭제 여부", default='N')
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "my_comment_storage"
        ordering = ['display_order', '-update_datetime']

    def __str__(self):
        return f"{self.my_phrase_name}"

    def soft_delete(self):
        """소프트 삭제 메서드"""
        from datetime import datetime
        self.delete_datetime = datetime.now().strftime('%Y%m%d')
        self.delete_YN = 'Y'
        self.save()
        
    
class MyIngredient(models.Model):
    # 내 원료 저장 모델
    user_id = models.ForeignKey(
        User,
        related_name="user_ingredient",
        on_delete=models.CASCADE,
        db_column="user_id",
        verbose_name="사용자 id",
        null=True,    # 추가
        blank=True    # 추가
    )

    #id = 자동생성
    my_ingredient_id = models.AutoField(primary_key=True)
    #키 = 유저id + 문서 종류 + 문서번호로 생성
    #my_ingredient_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name="내 원료키", primary_key=True)
    #my_ingredient_name = models.CharField(max_length=200, verbose_name="내 원료명")
    
    prdlst_report_no = models.CharField(max_length=16, verbose_name="품목보고번호", null=True, blank=True)
    prdlst_nm = models.CharField(max_length=200, verbose_name="원료명", null=True, blank=True)
    bssh_nm = models.CharField(max_length=100, verbose_name="제조사명", null=True, blank=True)
    prms_dt = models.CharField(max_length=8, verbose_name="허가일자", null=True, blank=True)
    food_category = models.CharField(max_length=100, verbose_name="식품구분", null=True, blank=True)
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)
    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="하위 원료", null=True, blank=True)
    induty_cd_nm = models.CharField(max_length=80, verbose_name="업종명", null=True, blank=True)
    hieng_lntrt_dvs_yn = models.CharField(max_length=10, verbose_name="고열량저영양식품여부", null=True, blank=True)

    #ingredient_ratio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="원료 비율(%)", null=True, blank=True)
    ingredient_display_name = models.CharField(max_length=1000, verbose_name="원료 표시명", null=True, blank=True)

    # 요약 타입 추가 Y : foodType, N : ingredientName
    summary_type_flag = models.CharField(max_length=1, verbose_name="요약 타입", default='Y')

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
        return str(self.my_ingredient_id) if self.my_ingredient_id else "새 원료"
    
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

    food_group = models.CharField(max_length=100, verbose_name="식품 대분류", null=True, blank=True)
    food_type = models.CharField(max_length=100, verbose_name="식품 소분류", null=True, blank=True)

    preservation_type = models.CharField(max_length=100, verbose_name="장기보존식품", null=True, blank=True)
    processing_method = models.CharField(max_length=100, verbose_name="제조방법", null=True, blank=True)
    processing_condition = models.CharField(max_length=100, verbose_name="제조방법 조건", null=True, blank=True)

    my_label_name = models.CharField(max_length=200, verbose_name="라벨명")

    # 기존 필드
    prdlst_dcnm = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)
    #food_type = models.CharField(max_length=100, verbose_name="식품유형", null=True, blank=True)

    prdlst_nm = models.CharField(max_length=200, verbose_name="제품명", null=True, blank=True)
    ingredient_info = models.TextField(max_length=1000, verbose_name="특정성분 함량", null=True, blank=True)

    content_weight = models.CharField(max_length=200, verbose_name="내용량", null=True, blank=True)
    weight_calorie = models.CharField(max_length=50, verbose_name="내용량(열량)", null=True, blank=True)

    prdlst_report_no = models.TextField(verbose_name="품목보고번호", null=True, blank=True)
    country_of_origin = models.CharField(max_length=255, verbose_name="원산지", null=True, blank=True)

    storage_method = models.CharField(max_length=300, verbose_name="보관방법", null=True, blank=True)
    frmlc_mtrqlt = models.TextField(max_length=300, verbose_name="포장재질", null=True, blank=True)

    bssh_nm = models.TextField(verbose_name="제조원 소재지", null=True, blank=True)
    #manufacturer_etc = models.CharField(max_length=500, verbose_name="제조원 외", null=True, blank=True)
    distributor_address = models.CharField(max_length=500, verbose_name="유통전문판매원 소재지", null=True, blank=True)
    repacker_address = models.CharField(max_length=500, verbose_name="소분원 소재지", null=True, blank=True)
    importer_address = models.CharField(max_length=500, verbose_name="수입원 소재지", null=True, blank=True)

    pog_daycnt = models.CharField(max_length=200, verbose_name="소비기한", null=True, blank=True)

    rawmtrl_nm = models.TextField(max_length=1000, verbose_name="원재료명", null=True, blank=True)
    rawmtrl_nm_display = models.TextField(max_length=1000, verbose_name="원재료명(표시)", null=True, blank=True)
    
    cautions = models.TextField(max_length=1000, verbose_name="주의사항", null=True, blank=True)
    additional_info = models.TextField(max_length=1000, verbose_name="기타 표시사항", null=True, blank=True)

    #영양성분 관련 컬럼
    nutrition_text = models.TextField(max_length=1000, verbose_name="영양성분 표시", null=True, blank=True)

    serving_size = models.CharField(max_length=10, verbose_name="단위 내용량", null=True, blank=True)
    serving_size_unit = models.CharField(max_length=10, verbose_name="단위 내용량 단위", null=True, blank=True)

    # 포장 **재질**이 아니라 **형태**다. 표시기준의 활자·표시 규정은 거의 전부
    # "어느 면에" 를 전제로 하는데, 그 면은 포장 형태가 정한다 — 봉지는 앞/뒤,
    # 상자는 앞·윗·뒤/양측면. 목록은 label.services.display_panel 에 있다.
    package_form = models.CharField(max_length=20, verbose_name="포장 형태",
                                    null=True, blank=True,
                                    help_text="주표시면·정보표시면이 어디인지를 정한다")
    units_per_package = models.CharField(max_length=10, verbose_name="포장 당 갯수", null=True, blank=True)

    # 1회 섭취참고량. 단위내용량과 다른 값이다 — 단위내용량은 한 개의 양이고
    # 이것은 "한 번에 이만큼 먹는다" 는 식품유형별 기준량이다. 고열량·저영양
    # 판정과 영양강조표시가 이 값을 분모로 쓴다(단위는 serving_size_unit 을 따른다).
    serving_reference = models.CharField(max_length=10, verbose_name="1회 섭취참고량", null=True, blank=True)
    # 고열량·저영양 판정 구분 — 'snack'(간식용) / 'meal'(식사대용) / 빈값(판정 안 함)
    hieng_kind = models.CharField(max_length=10, verbose_name="고열량저영양 판정 구분", null=True, blank=True)
    # 이론치로 표를 만들었다는 사실과 그 근거. 공인기관 성적서 없이 계산한
    # 표는 그 자체가 감사 대상이라, 무엇으로 어떻게 냈는지가 값과 함께 남아야 한다.
    nutrition_source = models.CharField(max_length=20, verbose_name="영양성분 산출 방법", null=True, blank=True)
    nutrition_source_note = models.TextField(max_length=500, verbose_name="영양성분 산출 근거", null=True, blank=True)
    nutrition_tolerance = models.CharField(max_length=10, verbose_name="적용한 허용오차(%)", null=True, blank=True)
    # 오차를 물리기 전의 계산값(이론치). 저장 칸에는 적용값이 들어가므로 이것을
    # 안 남기면 다시 열 때 사람이 넣은 값이 사라진다.
    nutrition_calc_values = models.TextField(verbose_name="영양성분 계산값(JSON)", null=True, blank=True)
    nutrition_display_unit = models.CharField(max_length=10, verbose_name="영양성분 표시 단위", null=True, blank=True)
    basic_display_type = models.CharField(max_length=20, verbose_name="기본형 표시 기준", null=True, blank=True)
    parallel_display_type = models.CharField(max_length=20, verbose_name="병렬형 표시 기준", null=True, blank=True)

    calories = models.CharField(max_length=10, verbose_name="칼로리", null=True, blank=True)
    calories_unit = models.CharField(max_length=10, verbose_name="칼로리 단위", null=True, blank=True)

    natriums = models.CharField(max_length=10, verbose_name="나트륨", null=True, blank=True)
    natriums_unit = models.CharField(max_length=10, verbose_name="나트륨 단위", null=True, blank=True)

    carbohydrates = models.CharField(max_length=10, verbose_name="탄수화물", null=True, blank=True)
    carbohydrates_unit = models.CharField(max_length=10, verbose_name="탄수화물 단위", null=True, blank=True)

    sugars = models.CharField(max_length=10, verbose_name="당류", null=True, blank=True)
    sugars_unit = models.CharField(max_length=10, verbose_name="당류 단위", null=True, blank=True)

    fats = models.CharField(max_length=10, verbose_name="지방", null=True, blank=True)
    fats_unit = models.CharField(max_length=10, verbose_name="지방 단위", null=True, blank=True)

    trans_fats = models.CharField(max_length=10, verbose_name="트랜스지방", null=True, blank=True)
    trans_fats_unit = models.CharField(max_length=10, verbose_name="트랜스지방 단위", null=True, blank=True)

    saturated_fats = models.CharField(max_length=10, verbose_name="포화지방", null=True, blank=True)
    saturated_fats_unit = models.CharField(max_length=10, verbose_name="포화지방 단위", null=True, blank=True)

    cholesterols = models.CharField(max_length=10, verbose_name="콜레스테롤", null=True, blank=True)
    cholesterols_unit = models.CharField(max_length=10, verbose_name="콜레스테롤 단위", null=True, blank=True)

    proteins = models.CharField(max_length=10, verbose_name="단백질", null=True, blank=True)
    proteins_unit = models.CharField(max_length=10, verbose_name="단백질 단위", null=True, blank=True)
    
    # 추가 영양성분 및 단위 필드
    dietary_fiber = models.CharField(max_length=10, verbose_name="식이섬유", null=True, blank=True)
    dietary_fiber_unit = models.CharField(max_length=10, verbose_name="식이섬유 단위", null=True, blank=True)
    calcium = models.CharField(max_length=10, verbose_name="칼슘", null=True, blank=True)
    calcium_unit = models.CharField(max_length=10, verbose_name="칼슘 단위", null=True, blank=True)
    iron = models.CharField(max_length=10, verbose_name="철", null=True, blank=True)
    iron_unit = models.CharField(max_length=10, verbose_name="철 단위", null=True, blank=True)
    magnesium = models.CharField(max_length=10, verbose_name="마그네슘", null=True, blank=True)
    magnesium_unit = models.CharField(max_length=10, verbose_name="마그네슘 단위", null=True, blank=True)
    phosphorus = models.CharField(max_length=10, verbose_name="인", null=True, blank=True)
    phosphorus_unit = models.CharField(max_length=10, verbose_name="인 단위", null=True, blank=True)
    potassium = models.CharField(max_length=10, verbose_name="칼륨", null=True, blank=True)
    potassium_unit = models.CharField(max_length=10, verbose_name="칼륨 단위", null=True, blank=True)
    zinc = models.CharField(max_length=10, verbose_name="아연", null=True, blank=True)
    zinc_unit = models.CharField(max_length=10, verbose_name="아연 단위", null=True, blank=True)
    vitamin_a = models.CharField(max_length=10, verbose_name="비타민A", null=True, blank=True)
    vitamin_a_unit = models.CharField(max_length=10, verbose_name="비타민A 단위", null=True, blank=True)
    vitamin_d = models.CharField(max_length=10, verbose_name="비타민D", null=True, blank=True)
    vitamin_d_unit = models.CharField(max_length=10, verbose_name="비타민D 단위", null=True, blank=True)
    vitamin_c = models.CharField(max_length=10, verbose_name="비타민C", null=True, blank=True)
    vitamin_c_unit = models.CharField(max_length=10, verbose_name="비타민C 단위", null=True, blank=True)
    thiamine = models.CharField(max_length=10, verbose_name="티아민", null=True, blank=True)
    thiamine_unit = models.CharField(max_length=10, verbose_name="티아민 단위", null=True, blank=True)
    riboflavin = models.CharField(max_length=10, verbose_name="리보플라빈", null=True, blank=True)
    riboflavin_unit = models.CharField(max_length=10, verbose_name="리보플라빈 단위", null=True, blank=True)
    niacin = models.CharField(max_length=10, verbose_name="니아신", null=True, blank=True)
    niacin_unit = models.CharField(max_length=10, verbose_name="니아신 단위", null=True, blank=True)
    vitamin_b6 = models.CharField(max_length=10, verbose_name="비타민B6", null=True, blank=True)
    vitamin_b6_unit = models.CharField(max_length=10, verbose_name="비타민B6 단위", null=True, blank=True)
    folic_acid = models.CharField(max_length=10, verbose_name="엽산", null=True, blank=True)
    folic_acid_unit = models.CharField(max_length=10, verbose_name="엽산 단위", null=True, blank=True)
    vitamin_b12 = models.CharField(max_length=10, verbose_name="비타민B12", null=True, blank=True)
    vitamin_b12_unit = models.CharField(max_length=10, verbose_name="비타민B12 단위", null=True, blank=True)

    selenium = models.CharField(max_length=10, verbose_name="셀레늄", null=True, blank=True)
    selenium_unit = models.CharField(max_length=10, verbose_name="셀레늄 단위", null=True, blank=True)

    iodine = models.CharField(max_length=10, verbose_name="요오드", null=True, blank=True)
    iodine_unit = models.CharField(max_length=10, verbose_name="요오드 단위", null=True, blank=True)
    copper = models.CharField(max_length=10, verbose_name="구리", null=True, blank=True)
    copper_unit = models.CharField(max_length=10, verbose_name="구리 단위", null=True, blank=True)
    manganese = models.CharField(max_length=10, verbose_name="망간", null=True, blank=True)
    manganese_unit = models.CharField(max_length=10, verbose_name="망간 단위", null=True, blank=True)
    chromium = models.CharField(max_length=10, verbose_name="크롬", null=True, blank=True)
    chromium_unit = models.CharField(max_length=10, verbose_name="크롬 단위", null=True, blank=True)
    molybdenum = models.CharField(max_length=10, verbose_name="몰리브덴", null=True, blank=True)
    molybdenum_unit = models.CharField(max_length=10, verbose_name="몰리브덴 단위", null=True, blank=True)
    vitamin_e = models.CharField(max_length=10, verbose_name="비타민E", null=True, blank=True)
    vitamin_e_unit = models.CharField(max_length=10, verbose_name="비타민E 단위", null=True, blank=True)
    vitamin_k = models.CharField(max_length=10, verbose_name="비타민K", null=True, blank=True)
    vitamin_k_unit = models.CharField(max_length=10, verbose_name="비타민K 단위", null=True, blank=True)
    biotin = models.CharField(max_length=10, verbose_name="바이오틴", null=True, blank=True)
    biotin_unit = models.CharField(max_length=10, verbose_name="바이오틴 단위", null=True, blank=True)
    pantothenic_acid = models.CharField(max_length=10, verbose_name="판토텐산", null=True, blank=True)
    pantothenic_acid_unit = models.CharField(max_length=10, verbose_name="판토텐산 단위", null=True, blank=True)

    allergens = models.CharField(max_length=1000, verbose_name="알레르기 물질", null=True, blank=True)
    custom_fields = models.JSONField(verbose_name="맞춤항목", null=True, blank=True, default=list)

    create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)
    label_create_YN = models.CharField(max_length=1, verbose_name="표시사항 작성여부", default="N" )
    #ingredient_create_YN = models.CharField(max_length=1, verbose_name="원재료 작성 여부", default="N" )

    report_no_verify_YN = models.CharField(max_length=1, verbose_name="품목보고번호 검증 여부", default="N" )

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

    # 체크박스 상태 저장용 필드 (라벨명 이후 항목)
    chckd_prdlst_dcnm = models.CharField(max_length=1, default='Y', verbose_name='식품유형 체크') # 필수값 추가
    chckd_prdlst_nm = models.CharField(max_length=1, default='Y', verbose_name='제품명 체크')
    chckd_ingredient_info = models.CharField(max_length=1, default='N', verbose_name='특정성분 함량 체크')
    chckd_content_weight = models.CharField(max_length=1, default='Y', verbose_name='내용량 체크')
    chckd_weight_calorie = models.CharField(max_length=1, default='N', verbose_name='내용량(열량) 체크')
    chckd_prdlst_report_no = models.CharField(max_length=1, default='Y', verbose_name='품목보고번호 체크') # 필수값 추가
    chckd_country_of_origin = models.CharField(max_length=1, default='N', verbose_name='원산지 체크')
    chckd_storage_method = models.CharField(max_length=1, default='N', verbose_name='보관방법 체크')
    chckd_frmlc_mtrqlt = models.CharField(max_length=1, default='Y', verbose_name='용기.포장재질 체크') # 필수값 추가
    chckd_bssh_nm = models.CharField(max_length=1, default='Y', verbose_name='제조원 소재지 체크')
    chckd_distributor_address = models.CharField(max_length=1, default='N', verbose_name='유통전문판매원 체크')
    chckd_repacker_address = models.CharField(max_length=1, default='N', verbose_name='소분원 체크')
    chckd_importer_address = models.CharField(max_length=1, default='N', verbose_name='수입원 체크')
    chckd_pog_daycnt = models.CharField(max_length=1, default='Y', verbose_name='소비기한 체크')
    chckd_rawmtrl_nm_display = models.CharField(max_length=1, default='Y', verbose_name='원재료명(표시) 체크') # 필수값 추가
    chckd_cautions = models.CharField(max_length=1, default='Y', verbose_name='주의사항 체크') # 필수값 추가
    chckd_additional_info = models.CharField(max_length=1, default='N', verbose_name='기타표시사항 체크')
    chckd_nutrition_text = models.CharField(max_length=1, default='N', verbose_name='영양성분 체크')

    # 미리보기 설정 저장용 필드들
    prv_layout = models.CharField(max_length=10, verbose_name="레이아웃", null=True, blank=True)
    prv_width = models.CharField(max_length=10, verbose_name="가로", null=True, blank=True)
    prv_length = models.CharField(max_length=10, verbose_name="세로", null=True, blank=True)
    prv_font = models.CharField(max_length=100, verbose_name="글꼴", null=True, blank=True)
    prv_font_size = models.CharField(max_length=10, verbose_name="글꼴 크기", null=True, blank=True)
    prv_letter_spacing = models.CharField(max_length=10, verbose_name="자간", null=True, blank=True)
    prv_line_spacing = models.CharField(max_length=10, verbose_name="행간", null=True, blank=True)

    # 표의 항목 배치 — {'order': [필드…], 'width': {필드: '50%'|'100%'}, 'layout': 'vertical'|'horizontal'}
    #
    # 지금까지 이것만 브라우저의 localStorage 에 있었다. 그것도 라벨별이 아니라
    # 'labelFieldOrder' 키 하나에 담겨서, 한 라벨에서 맞춰 둔 순서가 다른 라벨에
    # 그대로 얹혔고 옆자리 동료는 아예 다른 순서를 봤다. 인쇄물의 모양이라
    # 라벨에 붙어 있어야 한다.
    #
    # 표시/숨김은 여기 없다. 그것은 표시 항목 체크(chckd_*)가 정한다 —
    # 같은 것을 정하는 스위치가 둘이면 어느 날 서로 다른 말을 한다.
    prv_field_layout = models.JSONField(verbose_name="표 항목 배치", null=True, blank=True)


    # 분리배출마크 설정
    prv_recycling_mark_enabled = models.CharField(max_length=1, verbose_name="분리배출마크 적용여부", default='N', null=True, blank=True)
    prv_recycling_mark_type = models.CharField(max_length=50, verbose_name="분리배출마크 종류", null=True, blank=True)
    prv_recycling_mark_position_x = models.CharField(max_length=10, verbose_name="분리배출마크 X좌표", null=True, blank=True)
    prv_recycling_mark_position_y = models.CharField(max_length=10, verbose_name="분리배출마크 Y좌표", null=True, blank=True)
    prv_recycling_mark_text = models.CharField(max_length=200, verbose_name="분리배출마크 추가텍스트", null=True, blank=True)

    class Meta:
        db_table = "my_label"
        indexes = [
            #models.Index(fields=['lcns_no'], name='idx_lcns_no'),
        ]

    def __str__(self):
        return self.my_label_name
    
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
    # 기본 필드
    food_group = models.CharField(max_length=100, verbose_name="식품군", default='default_group')
    food_type = models.CharField(max_length=100, verbose_name="식품유형", primary_key=True, default='default_food_type')

    # Nullable 필드로 변경
    prdlst_dcnm = models.CharField(max_length=10, verbose_name="식품유형명", null=True, blank=True)
    weight_calorie = models.CharField(max_length=10, verbose_name="내용량(열량)", null=True, blank=True)
    prdlst_report_no = models.CharField(max_length=10, verbose_name="품목보고번호", null=True, blank=True)
    country_of_origin = models.CharField(max_length=10, verbose_name="원산지", null=True, blank=True)
    frmlc_mtrqlt = models.CharField(max_length=10, verbose_name="포장재질", null=True, blank=True)
    pog_daycnt = models.CharField(max_length=50, verbose_name="소비기한", null=True, blank=True)
    rawmtrl_nm = models.CharField(max_length=10, verbose_name="원재료명", null=True, blank=True)
    storage_method = models.CharField(max_length=10, verbose_name="보관방법", null=True, blank=True)
    nutritions = models.CharField(max_length=10, verbose_name="영양성분", null=True, blank=True)
    cautions = models.CharField(max_length=10, verbose_name="주의사항", null=True, blank=True)
    type_check = models.CharField(max_length=50, verbose_name="구분", null=True, blank=True)


    relevant_regulations = models.TextField(verbose_name="식품유형별 관련규정", null=True, blank=True)

    class Meta:
        db_table = "food_type"
        indexes = [
            models.Index(fields=['food_type'], name='idx_food_type'),
        ]

    def __str__(self):
        return self.food_type
    
class CountryList(models.Model):
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
    # 기본키 필드 수정
    relation_id = models.CharField(
        max_length=255, 
        primary_key=True, 
        editable=False
    )

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
        # relation_id 생성 로직 개선
        if not self.relation_id or self.relation_id == 'default_relation':
            if self.label_id and self.ingredient_id:
                self.relation_id = f"{self.label_id}a{self.ingredient_id}"
            else:
                self.relation_id = f"temp_{timezone.now().strftime('%Y%m%d%H%M%S')}"  # timezone 사용
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label.my_label_name} - {self.ingredient.my_ingredient_name}"
    

class ImportedFood(models.Model):

    dcl_prduct_se_cd_nm = models.CharField(max_length=100, verbose_name="제품구분", null=True, blank=True)
    bsn_ofc_name = models.CharField(max_length=100, verbose_name="수입업체명", db_index=True)
    prduct_korean_nm = models.CharField(max_length=300, verbose_name="제품명(한글)", db_index=True)
    prduct_nm = models.TextField(verbose_name="제품명(영문)", null=True, blank=True)
    expirde_dtm = models.CharField(max_length=50, verbose_name="유통기한", db_index=True, help_text="yyyymmdd", null=True, blank=True)
    procs_dtm = models.CharField(max_length=8, verbose_name="수입신고일자", help_text="yyyymmdd", null=True, blank=True)
    ovsmnfst_nm = models.CharField(max_length=500, verbose_name="해외제조업소", db_index=True, null=True, blank=True)
    itm_nm = models.CharField(max_length=100, verbose_name="품목", db_index=True, null=True, blank=True)
    xport_ntncd_nm = models.CharField(max_length=100, verbose_name="수출국", db_index=True, null=True, blank=True)
    mnf_ntncn_nm = models.CharField(max_length=100, verbose_name="제조국", null=True, blank=True)
    korlabel = models.TextField(verbose_name="한글표시사항", null=True, blank=True)
    irdnt_nm = models.TextField(verbose_name="원재료명", null=True, blank=True)
    expirde_bdgin_dtm = models.CharField(max_length=8, verbose_name="유통기한", help_text="yyyymmdd", null=True, blank=True)
    expirde_end_dtm = models.CharField(max_length=8, verbose_name="소비기한", db_index=True, help_text="yyyymmdd", null=True, blank=True)

    class Meta:
        db_table = "imported_food"
        # bsn_ofc_name / itm_nm 은 필드의 db_index=True 가 이미 인덱스를 만든다 (중복 제거됨)
        indexes = []

    def __str__(self):
        return self.prduct_korean_nm

class FoodAdditive(models.Model):
    
    category = models.CharField(max_length=100, verbose_name="식품첨가물 대분류")
    name_kr = models.CharField(max_length=200, verbose_name="식품첨가물 명칭(한글)", primary_key=True)
    name_en = models.CharField(max_length=200, blank=True, null=True, verbose_name="영문명")
    alias_name = models.CharField(max_length=300, blank=True, null=True, verbose_name="이명")
    ins_no = models.CharField(max_length=150, blank=True, null=True, verbose_name="INS No.")
    e_no = models.CharField(max_length=150, blank=True, null=True, verbose_name="E No.")
    cas_no = models.CharField(max_length=100, blank=True, null=True, verbose_name="CAS No.")
    alias_4 = models.CharField(max_length=200, blank=True, null=True, verbose_name="표4 명칭+용도")
    alias_5 = models.CharField(max_length=200, blank=True, null=True, verbose_name="표5 명칭 또는 간략명")
    alias_6 = models.CharField(max_length=200, blank=True, null=True, verbose_name="표6 명칭 또는 간략명 또는 용도")

    short_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="간략명")
    main_purpose = models.CharField(max_length=200, blank=True, null=True, verbose_name="주용도")

    color_agent = models.CharField(max_length=10, blank=True, null=True, verbose_name="착색료")
    sweetener = models.CharField(max_length=10, blank=True, null=True, verbose_name="감미료")
    nutrient_enhancer = models.CharField(max_length=10, blank=True, null=True, verbose_name="영양강화제")
    preservative = models.CharField(max_length=10, blank=True, null=True, verbose_name="보존료")
    antioxidant = models.CharField(max_length=10, blank=True, null=True, verbose_name="산화방지제")
    bleaching_agent = models.CharField(max_length=10, blank=True, null=True, verbose_name="표백제")
    color_fixative = models.CharField(max_length=10, blank=True, null=True, verbose_name="발색제")
    stabilizer = models.CharField(max_length=10, blank=True, null=True, verbose_name="안정제")
    emulsifier = models.CharField(max_length=10, blank=True, null=True, verbose_name="유화제")
    thickener = models.CharField(max_length=10, blank=True, null=True, verbose_name="증점제")
    coagulant = models.CharField(max_length=10, blank=True, null=True, verbose_name="응고제")
    leavening_agent = models.CharField(max_length=10, blank=True, null=True, verbose_name="팽창제")
    sterilizer = models.CharField(max_length=10, blank=True, null=True, verbose_name="살균제")
    coating_agent = models.CharField(max_length=10, blank=True, null=True, verbose_name="피막제")

    notes = models.TextField(blank=True, null=True, verbose_name="비고")

    # ── 표시기준 관련 헬퍼 ───────────────────────────────────────────────────
    # 「식품등의 표시기준」 표4·5·6 에 따른 원재료 표시명 규칙.
    #   표4 = 명칭과 용도를 함께 표시 (예: "D-소비톨(감미료)")
    #   표5 = 명칭 또는 간략명
    #   표6 = 명칭 또는 간략명 또는 용도
    # 용도 플래그는 표4·표6 대상 첨가물에만 채워져 있다.
    PURPOSE_FIELDS = (
        ('color_agent',       '착색료'),
        ('sweetener',         '감미료'),
        ('nutrient_enhancer', '영양강화제'),
        ('preservative',      '보존료'),
        ('antioxidant',       '산화방지제'),
        ('bleaching_agent',   '표백제'),
        ('color_fixative',    '발색제'),
        ('stabilizer',        '안정제'),
        ('emulsifier',        '유화제'),
        ('thickener',         '증점제'),
        ('coagulant',         '응고제'),
        ('leavening_agent',   '팽창제'),
        ('sterilizer',        '살균제'),
        ('coating_agent',     '피막제'),
    )
    TABLE_LABELS = {'4': '명칭+용도', '5': '명칭·간략명', '6': '명칭·간략명·용도'}

    @staticmethod
    def _is_y(value) -> bool:
        return str(value or '').strip().upper() == 'Y'

    @property
    def purposes(self) -> list:
        """용도 플래그가 Y 인 용도명 목록 (예: ['감미료'])"""
        return [label for field, label in self.PURPOSE_FIELDS
                if self._is_y(getattr(self, field, None))]

    @property
    def display_tables(self) -> list:
        """해당되는 표시기준 표 번호 목록 (예: ['4', '5'])"""
        return [num for num, flag in (('4', self.alias_4), ('5', self.alias_5), ('6', self.alias_6))
                if self._is_y(flag)]

    @property
    def display_table_badges(self) -> list:
        """템플릿 표시용 — [{'num': '4', 'label': '명칭+용도'}, ...] (dict 는 템플릿에서 키 조회가 안 된다)"""
        return [{'num': n, 'label': self.TABLE_LABELS[n]} for n in self.display_tables]

    # 간략명 칼럼에 플래그 문자가 섞여 들어온 적이 있어 걸러낸다
    _SHORT_NAME_SENTINELS = {'Y', 'N', '-'}

    @property
    def short_names(self) -> list:
        """간략명 목록 (쉼표 구분 문자열을 분리)"""
        return [t for t in (x.strip() for x in str(self.short_name or '').split(','))
                if t and t not in self._SHORT_NAME_SENTINELS]

    def display_name_options(self) -> list:
        """
        표4·5·6 규칙에 따라 원재료 표시명으로 쓸 수 있는 후보 목록.
        원료 상세의 '식품첨가물 표시규정' 버튼과 첨가물 DB 목록이 같은 값을 쓴다.
        """
        options = []
        def add(v):
            if v and v not in options:
                options.append(v)

        tables = self.display_tables
        if '4' in tables:
            # 표4는 명칭 단독 표시가 불가 — 반드시 "명칭(용도)"
            for purpose in self.purposes:
                add(f'{self.name_kr}({purpose})')
        if '5' in tables:
            add(self.name_kr)
            for sn in self.short_names:
                add(sn)
        if '6' in tables:
            add(self.name_kr)
            for sn in self.short_names:
                add(sn)
            for purpose in self.purposes:
                add(purpose)
        return options

    def default_display_name(self):
        """
        복사·자동입력에 쓸 기본 표시명. 확정할 수 없으면 None 을 돌려주고,
        사용자가 원료 상세에서 직접 고르게 한다.
          - 표4 대상은 명칭만으로는 표시기준 위반이므로 용도가 하나일 때만 확정
          - 표4가 아니면 명칭이 유효한 표시명
        """
        if '4' in self.display_tables:
            purposes = self.purposes
            return f'{self.name_kr}({purposes[0]})' if len(purposes) == 1 else None
        return self.name_kr

    class Meta:
        db_table = "food_additives"
        indexes = [
            models.Index(fields=["name_kr"], name="idx_foodadditive_name_kr"),
        ]

    def __str__(self):
        return self.name_kr

class AgriculturalProduct(models.Model):
    # 농수산물 모델
    lclas_nm = models.CharField(max_length=500, blank=True, null=True, verbose_name="대분류")
    mlsfc_nm = models.CharField(max_length=500, blank=True, null=True, verbose_name="중분류")
    rprsnt_rawmtrl_nm = models.CharField(max_length=500, null=True, blank=True, verbose_name="명칭")
    rawmtrl_ncknm = models.CharField(max_length=500, blank=True, null=True, verbose_name="이명")
    eng_nm = models.CharField(max_length=500, blank=True, null=True, verbose_name="영문명")
    scnm = models.TextField(blank=True, null=True, verbose_name="학명")
    regn_cd_nm = models.CharField(max_length=500, blank=True, null=True, verbose_name="부위명")
    rawmtrl_stats_cd_nm = models.CharField(max_length=500, blank=True, null=True, verbose_name="상태명")
    use_cnd_nm = models.TextField(blank=True, null=True, verbose_name="사용 조건")

    class Meta:
        db_table = "agricultural_product"
        indexes = [
            models.Index(fields=["rprsnt_rawmtrl_nm"], name="idx_rprsnt_rawmtrl_nm")
        ]

    def __str__(self):
        return self.rprsnt_rawmtrl_nm


class ExpiryRecommendation(models.Model):
    """소비기한 권장 정보 모델"""
    food_type = models.CharField(max_length=100, verbose_name="식품유형", primary_key=True)
    shelf_life = models.CharField(max_length=10, verbose_name="권장 소비기한", help_text="숫자 또는 '제품별'")
    unit = models.CharField(max_length=10, verbose_name="단위", null=True, blank=True, help_text="months, days 등")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = "expiry_recommendation"
        indexes = [
            models.Index(fields=["food_type"], name="idx_expiry_food_type"),
        ]
        verbose_name = "소비기한 권장정보"
        verbose_name_plural = "소비기한 권장정보"

    def __str__(self):
        if self.unit:
            return f"{self.food_type}: {self.shelf_life}{self.unit}"
        return f"{self.food_type}: {self.shelf_life}"


class AdKeyword(models.Model):
    """
    부당한 표시·광고 키워드. **등급마다 판정이 다르다.**

    지금까지 이 검사는 `constants.FORBIDDEN_PHRASES` 네 단어였고, 걸리면 전부
    같은 무게로 막았다. 그렇게 둔 이유가 ai_validation_service 주석에 적혀
    있다 — 예외 조건 판단("이 제품에 '천연' 을 써도 되는가")은 사실 추출이
    아니라 법적 평가 그 자체라 AI 에 맡길 수 없고, 그래서 보수적으로 전부
    플래그했다.

    그 막다른 골목은 **AI 없이** 풀린다. 판정이 아니라 표 조회로 바꾸면 된다.

        RED     어떤 경우에도 쓸 수 없다            -> 지적. 확정을 막는다
        YELLOW  근거가 있으면 쓸 수 있다            -> 지적이되 막지 않고, 조건을 보여 준다
        GREEN   써도 되는 말                        -> 세지 않는다. **예외 사전이다**

    GREEN 이 예외 사전인 것이 중요하다. 예전 `_FORBIDDEN_EXCEPTIONS`
    ('자연치즈' · '천연향료')가 하던 일이 그것이다 — 문구에서 먼저 지우고
    나머지에서 RED·YELLOW 를 찾는다. '천연향료' 안의 '천연' 을 세지 않는다.

    **owner 가 비면 공용 기본이고, 채워져 있으면 그 사람의 사내 기준이다.**
    회사마다 기준이 다르다 — 어떤 회사는 법에 없는 말도 위험하다고 막는다
    (예: "NON-GMO 는 법적으로 가능해도 Risk 가 있어 불가"). 그런 목록을 공용
    기본으로 깔면 다른 회사에 **틀린 규칙**이 된다. 그래서 공용 기본에는
    법정 금지어만 둔다.
    """

    RED = 'RED'
    YELLOW = 'YELLOW'
    GREEN = 'GREEN'
    GRADE_CHOICES = [
        (RED, '위험 — 사용 불가'),
        (YELLOW, '조건부 — 근거 확보 시 가능'),
        (GREEN, '사용 가능'),
    ]

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='ad_keywords', verbose_name='사내 기준 소유자',
        help_text='비워 두면 모든 사용자에게 적용되는 공용 기본입니다.')
    grade = models.CharField(max_length=6, choices=GRADE_CHOICES, default=RED,
                             verbose_name='등급', db_index=True)
    keyword = models.CharField(max_length=100, verbose_name='키워드',
                               help_text='사람이 읽는 이름. 화면에 이 이름이 나옵니다.')
    match_strings = models.CharField(
        max_length=500, verbose_name='매칭 문자열',
        help_text='문구에서 실제로 찾을 말. 여러 개면 · 로 구분합니다. '
                  '비워 두면 키워드를 그대로 찾습니다.')
    note = models.TextField(blank=True, default='', verbose_name='비고',
                            help_text='조건부(YELLOW)일 때 무엇을 갖춰야 하는지. '
                                      '화면에 그대로 보여 줍니다.')
    active_yn = models.BooleanField(default=True, verbose_name='사용', db_index=True)
    created_datetime = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        db_table = 'label_ad_keyword'
        ordering = ['grade', 'keyword']
        indexes = [models.Index(fields=['owner', 'active_yn'])]
        verbose_name = '부당표시 키워드'
        verbose_name_plural = '부당표시 키워드'

    def __str__(self):
        return f'[{self.grade}] {self.keyword}'

    def strings(self):
        """실제로 찾을 말들. 매칭 문자열이 비면 키워드를 쓴다."""
        raw = (self.match_strings or '').strip() or (self.keyword or '')
        return [s.strip() for s in raw.split('·') if s.strip()]




@receiver(pre_save, sender=MyLabel)
def stash_prev_report_no(sender, instance, **kwargs):
    """
    저장 직전 DB에 들어 있던 품목보고번호를 인스턴스에 담아둔다.
    post_save에서 "번호가 실제로 바뀐 저장"만 골라내기 위한 것 — 라벨 저장은
    대부분 폼 전체 저장이라 update_fields가 비어 있어 그것만으로는 판별할 수 없다.
    """
    if not instance.pk:
        instance._prev_prdlst_report_no = None
        return
    try:
        instance._prev_prdlst_report_no = (
            sender.objects.filter(pk=instance.pk)
            .values_list('prdlst_report_no', flat=True)
            .first()
        )
    except Exception:
        # 조회 실패 시엔 "안 바뀐 것"으로 두고 넘어간다.
        # 소급 매칭은 놓쳐도 스케줄러가 다시 잡지만, 과다 실행은 알림 중복을 만든다.
        instance._prev_prdlst_report_no = instance.prdlst_report_no


@receiver(post_save, sender=MyLabel)
def backfill_inspection_on_label_save(sender, instance, created, update_fields, **kwargs):
    """
    MyLabel의 품목보고번호가 실제로 새로 입력되거나 바뀔 때만 수거검사 소급 매칭 실행.
    삭제된 제품(delete_YN='Y')은 스킵.

    여기서 InspectionMatch를 사용자 단위로 전량 삭제하면 안 된다 —
      - PHASE_JUDGMENT(판정결과 변동 = 부적합 알림)는 backfill_inspection_matches()가
        다시 만들어주지 않는다(수거감지 PHASE_COLLECTION만 생성). 지우면 영구 소실이다.
      - 전량 삭제하면 collector의 중복 검사(already)가 항상 빗나가서, 저장할 때마다
        같은 건이 pending_push에 다시 담겨 FCM 푸시가 재발송된다.
    그래서 번호가 바뀐 이 라벨의 수거감지 매칭만 정리하고 재매칭한다.
    """
    if instance.delete_YN == 'Y':
        return
    if not instance.prdlst_report_no:
        return
    if update_fields and 'prdlst_report_no' not in update_fields:
        return
    prev = getattr(instance, '_prev_prdlst_report_no', None)
    if not created and prev == instance.prdlst_report_no:
        return  # 품목보고번호는 그대로 — 다른 필드만 바뀐 저장이므로 재매칭할 이유가 없다
    try:
        from v1.regulatory.models import InspectionMatch
        from v1.regulatory.services.collector import backfill_inspection_matches
        # 옛 번호 기준으로 이 라벨에 붙어 있던 수거감지 매칭만 정리한다.
        # 다른 라벨의 매칭과 판정 알림(PHASE_JUDGMENT)은 건드리지 않는다.
        InspectionMatch.objects.filter(
            user=instance.user_id,
            label=instance,
            alert_phase=InspectionMatch.PHASE_COLLECTION,
        ).delete()
        # 웹 요청 안이므로 FCM 발송은 백그라운드로 넘긴다(저장 응답 지연 방지).
        backfill_inspection_matches(instance.user_id, push_async=True)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('[I0460 소급] MyLabel 트리거 오류')


class PublicFoodNutrition(models.Model):
    """
    식약처 식품영양성분DB 적재본 (data.go.kr FoodNtrCpntDbInfo02).

    **정답이 아니라 기본값이다.** 여기 있는 밀가루는 "일반적인 밀가루"이지
    "우리가 쓰는 그 밀가루"가 아니다. 원료 영양성분의 출처 우선순위는

        사내 시험성적서 > 공급업체 Spec > 이 표 > 유사 원료 추정

    이고, 이 표가 하는 일은 **빈 칸을 미리 채워 두는 것**이다. 사람이 덮어쓰면
    그 값이 이긴다.

    성분 이름은 API 의 AMT_NUM 번호가 아니라 **우리 이름**으로 저장한다
    (nutrition_calc·constants 가 쓰는 것과 같은 이름). 번호를 우리 이름으로
    옮기는 일은 적재 한 곳에서만 일어나야 한다 — 화면과 계산이 저마다 번호를
    풀면 한 곳만 밀려도 알 수 없다. 매핑은 services/mfds_nutrition.py 에 있다.

    원문(raw)을 통째로 남긴다. 157 개 성분 중 20 여 개만 컬럼으로 꺼냈는데,
    아미노산·지방산이 필요해지는 날 API 를 다시 639 번 부르지 않기 위해서다.
    """

    BASIS_G = 'g'
    BASIS_ML = 'mL'
    BASIS_CHOICES = [(BASIS_G, '100g 기준'), (BASIS_ML, '100mL 기준')]

    VERIFY_PASS = 'pass'
    VERIFY_FAIL = 'fail'
    VERIFY_SKIP = 'skip'
    VERIFY_CHOICES = [
        (VERIFY_PASS, '검산 통과'),
        (VERIFY_FAIL, '검산 어긋남'),
        (VERIFY_SKIP, '잴 수 없음'),
    ]

    # ── 식별 ────────────────────────────────────────────────────────────
    food_cd = models.CharField(max_length=40, unique=True, verbose_name='식품코드')
    food_nm_kr = models.CharField(max_length=300, verbose_name='식품명', db_index=True)
    db_grp_nm = models.CharField(max_length=30, null=True, blank=True, db_index=True,
                                 verbose_name='데이터구분명',
                                 help_text='가공식품 / 음식 / 원재료성')
    db_class_nm = models.CharField(max_length=30, null=True, blank=True,
                                   verbose_name='품목대표·상용제품')
    food_cat1_nm = models.CharField(max_length=100, null=True, blank=True,
                                    verbose_name='식품대분류명')

    # ── 조인 키 ─────────────────────────────────────────────────────────
    # 가공식품 행에는 표본 1,500 건에서 100 % 채워져 있었다. MyIngredient 도
    # 같은 번호를 들고 있으므로, 사 오는 원료는 이름이 아니라 이 번호로 붙는다.
    # 숫자가 아닌 값('2020_DNSP_04044')은 빈 문자열로 두어 조인에서 뺀다.
    item_report_no = models.CharField(max_length=30, null=True, blank=True, db_index=True,
                                      verbose_name='품목제조보고번호')
    maker_nm = models.CharField(max_length=200, null=True, blank=True, verbose_name='업체명')
    imp_yn = models.CharField(max_length=10, null=True, blank=True, verbose_name='수입여부')
    nation_nm = models.CharField(max_length=100, null=True, blank=True, verbose_name='원산지국명')

    # ── 기준량 ──────────────────────────────────────────────────────────
    # 100 g 만 오는 것이 아니다. 표본의 19 % 가 100 mL 였다. 부피 기준은 비중을
    # 모르면 중량 배합에 쓸 수 없으므로 단위를 그대로 남기고 자동 채움에서 뺀다.
    basis_amount = models.FloatField(null=True, blank=True, verbose_name='기준량')
    basis_unit = models.CharField(max_length=5, null=True, blank=True, choices=BASIS_CHOICES,
                                  verbose_name='기준 단위',
                                  help_text='비면 원본 기준량을 읽지 못한 행')

    # ── 성분 (기준량당) ─────────────────────────────────────────────────
    calories = models.FloatField(null=True, blank=True, verbose_name='에너지(kcal)')
    proteins = models.FloatField(null=True, blank=True, verbose_name='단백질(g)')
    fats = models.FloatField(null=True, blank=True, verbose_name='지방(g)')
    carbohydrates = models.FloatField(null=True, blank=True, verbose_name='탄수화물(g)')
    sugars = models.FloatField(null=True, blank=True, verbose_name='당류(g)')
    dietary_fiber = models.FloatField(null=True, blank=True, verbose_name='식이섬유(g)')
    sugar_alcohols = models.FloatField(null=True, blank=True, verbose_name='당알콜(g)')
    natriums = models.FloatField(null=True, blank=True, verbose_name='나트륨(mg)')
    cholesterols = models.FloatField(null=True, blank=True, verbose_name='콜레스테롤(mg)')
    saturated_fats = models.FloatField(null=True, blank=True, verbose_name='포화지방산(g)')
    trans_fats = models.FloatField(null=True, blank=True, verbose_name='트랜스지방산(g)')
    calcium = models.FloatField(null=True, blank=True, verbose_name='칼슘(mg)')
    iron = models.FloatField(null=True, blank=True, verbose_name='철(mg)')
    phosphorus = models.FloatField(null=True, blank=True, verbose_name='인(mg)')
    potassium = models.FloatField(null=True, blank=True, verbose_name='칼륨(mg)')
    magnesium = models.FloatField(null=True, blank=True, verbose_name='마그네슘(mg)')
    selenium = models.FloatField(null=True, blank=True, verbose_name='셀레늄(μg)')
    zinc = models.FloatField(null=True, blank=True, verbose_name='아연(mg)')
    moisture = models.FloatField(null=True, blank=True, verbose_name='수분(g)',
                                 help_text='수율 검산의 근거 — 표시 성분은 아니다')
    ash = models.FloatField(null=True, blank=True, verbose_name='회분(g)')
    refuse_rate = models.FloatField(null=True, blank=True, verbose_name='폐기율(%)')

    # ── 신뢰도·출처 ─────────────────────────────────────────────────────
    # 등급을 새로 발명하지 않는다. 원본이 이미 '분석'과 '계산'을 가르고 있다.
    crt_mth_nm = models.CharField(max_length=30, null=True, blank=True, db_index=True,
                                  verbose_name='데이터생성방법명')
    sub_ref_name = models.CharField(max_length=200, null=True, blank=True, verbose_name='출처명')
    research_ymd = models.CharField(max_length=20, null=True, blank=True,
                                    verbose_name='데이터생성일자',
                                    help_text='"3년 경과" 같은 오래됨 경고에 쓴다')
    update_date = models.CharField(max_length=20, null=True, blank=True, verbose_name='데이터수정일자')

    # ── 검산 ────────────────────────────────────────────────────────────
    # AMT_NUM 번호를 하나 밀려 읽어도 예외가 나지 않는다. 그래서 적재할 때마다
    # 질량 합과 열량 재계산으로 스스로 재고, 그 결과를 행에 남긴다.
    verify_status = models.CharField(max_length=10, default=VERIFY_SKIP, choices=VERIFY_CHOICES,
                                     db_index=True, verbose_name='검산 결과')
    verify_note = models.CharField(max_length=200, null=True, blank=True, verbose_name='검산 사유')

    raw = models.JSONField(null=True, blank=True, verbose_name='원문',
                           help_text='꺼내지 않은 성분 130여 종이 여기 남아 있다')
    fetched_at = models.DateTimeField(auto_now=True, verbose_name='적재일시')

    class Meta:
        db_table = 'public_food_nutrition'
        verbose_name = '식약처 영양성분'
        verbose_name_plural = '식약처 영양성분'
        indexes = [
            models.Index(fields=['db_grp_nm', 'verify_status']),
        ]

    def __str__(self):
        return '%s (%s)' % (self.food_nm_kr, self.food_cd)

    @property
    def usable_for_recipe(self):
        """
        배합 자동 채움에 쓸 수 있는 행인가.

        중량(g) 기준이어야 하고, 검산에서 어긋나지 않아야 한다. 'skip'(잴 수
        없음)은 막지 않는다 — 원본에 빈 칸이 많아 못 잰 것이지 틀린 것이 아니다.
        """
        return self.basis_unit == self.BASIS_G and self.verify_status != self.VERIFY_FAIL


class MyIngredientNutrition(models.Model):
    """
    내 원료의 영양성분 — 배합 계산이 딛고 서는 자리.

    MyIngredient 에는 영양성분 칸이 하나도 없다. 그래서 BOM 이 원료 보관함을
    가리키면 배합 계산이 빈손으로 돌아온다(실제로 여덟 줄 전부 그랬다).
    이 표가 그 칸이다.

    **값보다 출처가 중요하다.** 이론치로 만든 표는 그 자체가 감사 대상이라,
    "이 숫자가 어디서 왔는가" 를 값과 함께 남겨야 한다. source_kind 가 그것이고,
    컨설팅이 A~E 로 매기자던 신뢰도 등급이 여기서 자연스럽게 나온다.

        spec_ocr    업체 시험성적서 (가장 정확하다)
        report_no   품목제조보고번호가 식약처 DB 와 정확히 일치
        picked      후보 중 사람이 고른 식약처 DB 행
        manual      사람이 직접 입력
        negligible  배합비가 작아 표시값을 못 바꾼다고 판정된 것

    picked 는 자동 확정이 아니다. '버터' 라는 이름으로 동명 항목이 열두 건이고
    열량이 164 ~ 761 kcal(4.6 배)이라, 이름만으로는 어느 것인지 알 수 없다.
    사람이 한 번 고르면 그 선택을 여기 남겨 다시 묻지 않는다.

    public_row 를 값 복사가 아니라 FK 로 잡는다. 식약처 DB 가 갱신됐을 때
    **어느 행을 보고 정한 값인지** 추적할 수 있어야 하기 때문이다.
    """

    SOURCE_SPEC_OCR = 'spec_ocr'
    SOURCE_REPORT_NO = 'report_no'
    SOURCE_PICKED = 'picked'
    SOURCE_MANUAL = 'manual'
    SOURCE_NEGLIGIBLE = 'negligible'
    SOURCE_CHOICES = [
        (SOURCE_SPEC_OCR, '업체 시험성적서'),
        (SOURCE_REPORT_NO, '품목보고번호 일치'),
        (SOURCE_PICKED, '식약처DB에서 고름'),
        (SOURCE_MANUAL, '직접 입력'),
        (SOURCE_NEGLIGIBLE, '영향 없음으로 확정'),
    ]

    # 신뢰도 등급 — 등급을 따로 저장하지 않고 출처에서 끌어낸다.
    # 두 곳에 두면 언젠가 서로 어긋난다.
    GRADE = {
        SOURCE_SPEC_OCR: 'A',
        SOURCE_REPORT_NO: 'B',
        SOURCE_PICKED: 'C',
        SOURCE_MANUAL: 'C',
        SOURCE_NEGLIGIBLE: '-',
    }

    ingredient = models.OneToOneField('label.MyIngredient', on_delete=models.CASCADE,
                                      related_name='nutrition', verbose_name='원료')
    source_kind = models.CharField(max_length=20, choices=SOURCE_CHOICES,
                                   default=SOURCE_MANUAL, db_index=True,
                                   verbose_name='값의 출처')
    public_row = models.ForeignKey('label.PublicFoodNutrition', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='picked_by_ingredients',
                                   verbose_name='본 식약처 행',
                                   help_text='값을 베낀 것이 아니라 어느 행을 보았는지를 남긴다')
    source_note = models.CharField(max_length=300, null=True, blank=True,
                                   verbose_name='근거', help_text='성적서 번호·발급일 등')

    picked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='picked_ingredient_nutritions',
                                  verbose_name='고른 사람')
    picked_at = models.DateTimeField(null=True, blank=True, verbose_name='고른 때')

    # ── 성분 (100 g 당) ─────────────────────────────────────────────────
    # 이름을 nutrition_calc·nutrition_recipe 와 똑같이 둔다. 옮겨 담는 자리가
    # 생기면 거기서 밀린다.
    calories = models.FloatField(null=True, blank=True, verbose_name='열량(kcal)')
    carbohydrates = models.FloatField(null=True, blank=True, verbose_name='탄수화물(g)')
    sugars = models.FloatField(null=True, blank=True, verbose_name='당류(g)')
    proteins = models.FloatField(null=True, blank=True, verbose_name='단백질(g)')
    fats = models.FloatField(null=True, blank=True, verbose_name='지방(g)')
    saturated_fats = models.FloatField(null=True, blank=True, verbose_name='포화지방(g)')
    trans_fats = models.FloatField(null=True, blank=True, verbose_name='트랜스지방(g)')
    cholesterols = models.FloatField(null=True, blank=True, verbose_name='콜레스테롤(mg)')
    natriums = models.FloatField(null=True, blank=True, verbose_name='나트륨(mg)')
    dietary_fiber = models.FloatField(null=True, blank=True, verbose_name='식이섬유(g)')
    sugar_alcohols = models.FloatField(null=True, blank=True, verbose_name='당알콜(g)')
    moisture = models.FloatField(null=True, blank=True, verbose_name='수분(g)',
                                 help_text='수율 검산에 쓴다 — 표시 성분은 아니다')
    ash = models.FloatField(null=True, blank=True, verbose_name='회분(g)')

    created_datetime = models.DateTimeField(auto_now_add=True, verbose_name='등록일시')
    update_datetime = models.DateTimeField(auto_now=True, verbose_name='수정일시')

    class Meta:
        db_table = 'my_ingredient_nutrition'
        verbose_name = '내 원료 영양성분'
        verbose_name_plural = '내 원료 영양성분'

    def __str__(self):
        return '%s (%s)' % (self.ingredient_id, self.get_source_kind_display())

    @property
    def grade(self):
        """신뢰도 등급. 출처가 정한다."""
        return self.GRADE.get(self.source_kind, 'C')

    def as_values(self, fields):
        """
        배합 계산이 쓰는 모양으로 돌려준다.

        빈 칸은 0 이 아니라 None 이다 — 모르는 것과 없는 것은 다르고, 0 으로
        내려보내면 합계가 조용히 낮아진다.
        """
        return {f: getattr(self, f, None) for f in fields}
