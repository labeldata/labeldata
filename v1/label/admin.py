from django.contrib import admin

from v1.label.models import AdKeyword, NutritionAnomaly


@admin.register(AdKeyword)
class AdKeywordAdmin(admin.ModelAdmin):
    """
    부당표시 키워드. 사내 기준을 여기서 넣는다.

    owner 를 비우면 **모든 사용자**에게 적용되는 공용 기본이 된다. 회사마다
    기준이 달라서(법에 없는 말까지 막는 목록이 흔하다) 사내 기준은 반드시
    owner 를 채워야 한다.

    법정 금지어는 여기 없다 — `constants.AD_KEYWORDS_BUILTIN` 에 코드로 있다.
    데이터로만 두면 행이 지워졌을 때 검사가 조용히 죽는다.
    """
    list_display = ('grade', 'keyword', 'match_strings', 'owner', 'active_yn')
    list_filter = ('grade', 'active_yn', 'owner')
    search_fields = ('keyword', 'match_strings', 'note')
    list_editable = ('active_yn',)
    fieldsets = (
        (None, {'fields': ('owner', 'grade', 'keyword', 'match_strings', 'active_yn')}),
        ('조건부(YELLOW)일 때', {
            'fields': ('note',),
            'description': '무엇을 갖춰야 쓸 수 있는지. 검증 결과에 그대로 보여 줍니다.',
        }),
    )


@admin.register(NutritionAnomaly)
class NutritionAnomalyAdmin(admin.ModelAdmin):
    """
    영양성분DB 에서 이상해 보이는 행. 판정은 `check_nutrition_anomaly` 가 한다.

    **고치는 화면이 아니다.** 여기 있는 것은 "그럴 수가 없다" 는 판정이지
    진실이 아니다 — 원본이 부실한 것일 수도, 우리 매핑이 밀린 것일 수도,
    정말 그런 제품일 수도 있다. 그래서 읽기만 하게 둔다. 고칠 곳은 원본
    행(영양성분DB)이거나 매핑(`services/mfds_nutrition.py`)이다.

    보는 순서는 **심각도 → 규칙**이다. '그럴 수 없음'(A1~A5)은 성분끼리
    어긋난 것이라 원재료를 몰라도 확실하고, '봐야 함'은 상위 원료로 미루어
    짐작한 것이라 그 제품을 실제로 봐야 한다.
    """

    list_display = ('severity', 'rule_code', 'food_name', 'food_type',
                    'maker_nm', 'detail', 'report_no')
    list_filter = ('severity', 'rule_code', 'food_type')
    search_fields = ('food_name', 'maker_nm', 'report_no', 'detail')
    list_select_related = ('nutrition',)
    date_hierarchy = 'checked_at'
    list_per_page = 50

    # 판정은 커맨드가 넣는다. 사람이 여기서 만들거나 고치면 다음 판정에
    # 덮여 사라지므로, 아예 못 하게 한다.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
