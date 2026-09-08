from django.contrib import admin

from v1.label.models import AdKeyword


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
