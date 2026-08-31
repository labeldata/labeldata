from django.db import models
from django.contrib.auth.models import User


class ApiKey(models.Model):
    """API 키를 관리하는 모델"""
    key = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="API 키 생성 시간")
    updated_at = models.DateTimeField(auto_now=True, help_text="API 키 갱신 시간")

    def __str__(self):
        return self.key

class ApiEndpoint(models.Model):
    """API 엔드포인트를 관리하는 모델"""
    name = models.CharField(max_length=255, help_text="API 이름")
    url = models.URLField(max_length=500, help_text="API URL")
    start_date = models.CharField(
        max_length=8,
        help_text="시작일자(YYYYMMDD)",
        null=True,
        blank=True,
        default=""
    )
    call_frequency_minutes = models.IntegerField(default=1440, help_text="호출 주기 (분 단위)")  # <- 나중에 삭제 가능
    last_called_at = models.DateTimeField(null=True, blank=True, help_text="마지막 호출 시간")
    last_status = models.CharField(
        max_length=50,
        choices=[("success", "성공"), ("failure", "실패")],
        default="success",
        help_text="마지막 호출 상태"
    )
    api_key = models.ForeignKey(
        'ApiKey',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='endpoints',
        help_text="API 키"
    )
    service_name = models.CharField(
        max_length=50,
        help_text="서비스 이름 (예: I1250)",
        null=True, blank=True
    )
    last_start_position = models.IntegerField(
        default=1,
        help_text="마지막 요청 시작 위치 (중단 후 이어받기용)"
    )
    use_reset_start_position = models.CharField(
        max_length=1,
        choices=[('Y', '초기화'), ('N', '유지')],
        default='Y',
        help_text='API 호출 시 last_start_position을 1로 초기화할지 여부 (Y: 초기화, N: 유지)'
    )

    def __str__(self):
        return self.name

class AdministrativeAction(models.Model):
    """행정처분 정보"""
    company_name = models.CharField(max_length=255, help_text="업체명", default="Unknown Company")
    registration_number = models.CharField(max_length=100, help_text="인허가번호")
    action_name = models.CharField(max_length=255, help_text="행정처분명")
    action_date = models.DateField(help_text="행정처분일")
    details = models.TextField(blank=True, help_text="기타 세부 내용")

    def __str__(self):
        return f"{self.company_name} - {self.action_name} ({self.action_date})"


class AiValidationUsage(models.Model):
    """
    AI검증 일일 사용량. 사용자·날짜마다 한 행.

    원래 파일 캐시에 있었다. CACHES['default'] 는 항목이 MAX_ENTRIES 를 넘으면
    Django 가 1/3 을 잘라내는데(FileBasedCache._cull), 그때 카운터가 같이 날아가면
    **한도가 조용히 초기화된다.** 유료 기능의 사용량이 캐시 정리에 좌우되면 안 된다.

    한동안 활동 로그(UserActivityLog)에 소비 기록을 남기고 세는 방식을 썼는데,
    그건 마이그레이션이 깨져 있어 새 테이블을 못 만들던 때의 임시방편이었다.
    이제 migrate 가 돌므로 제 자리를 만든다.

    행을 세지 않고 count 를 올린다 — 하루 한 행이라 조회가 항상 한 건이고,
    F('count') + 1 은 DB 가 원자적으로 처리한다.

    label 앱이 아니라 여기 있는 이유: 사용량 집계는 도메인이라기보다 인프라이고,
    label 앱은 아직 모델과 마이그레이션이 어긋난 곳이 있어(인덱스 5건 등) 새
    마이그레이션을 만들면 그것까지 함께 담긴다.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='ai_validation_usage', verbose_name='사용자')
    used_date = models.DateField(verbose_name='사용일',
                                 help_text='서버 시간대 기준 날짜')
    count = models.PositiveIntegerField(default=0, verbose_name='사용 횟수')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_validation_usage'
        verbose_name = 'AI검증 사용량'
        verbose_name_plural = 'AI검증 사용량'
        constraints = [
            models.UniqueConstraint(fields=['user', 'used_date'],
                                    name='uniq_ai_usage_user_date'),
        ]
        indexes = [
            models.Index(fields=['used_date'], name='idx_ai_usage_date'),
        ]

    def __str__(self):
        return f'{self.user} {self.used_date} {self.count}회'


class OcrCorrection(models.Model):
    """
    사진 판독 결과를 사용자가 어떻게 고쳤는지 남긴다.

    지금까지 이 기록이 한 건도 없었다. 그래서 "무엇을 얼마나 틀리는지" 를
    셀 수도 없었고, 프롬프트를 고쳐도 나아졌는지 알 수 없었다. 튜닝을 하려
    해도 학습 데이터가 없다 - 원본과 정답의 쌍이 안 쌓이기 때문이다.

    쌓이면 세 가지에 쓴다.
      1. 어느 항목이 자주 틀리는지 (ocr_corrections --stats)
      2. 자주 틀리는 패턴을 프롬프트에 예시로 넣기 (지금 하는 것)
      3. 나중에 실제 튜닝을 할 때의 학습셋

    사용자가 고치지 않고 그대로 쓴 것도 남긴다(corrected=False). 정답률을
    재려면 맞은 것도 세야 한다.
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='ocr_corrections', verbose_name='사용자')
    field = models.CharField(max_length=40, verbose_name='항목')
    ocr_value = models.TextField(blank=True, default='', verbose_name='판독값')
    final_value = models.TextField(blank=True, default='', verbose_name='사용자가 쓴 값')
    corrected = models.BooleanField(default=False, verbose_name='고쳤는지')
    confidence = models.CharField(max_length=10, blank=True, default='',
                                  verbose_name='판독 확신도')
    model = models.CharField(max_length=40, blank=True, default='',
                             verbose_name='판독 모델')
    # 어떤 방식으로 읽었는지. 'crop'(영역을 골랐다) / 'whole'(사진 전체).
    # 방식을 나눠 재지 않으면 "영역을 고르는 게 나은가" 를 영영 답할 수 없다.
    variant = models.CharField(max_length=20, blank=True, default='',
                               verbose_name='판독 방식')
    # 그 값이 어디서 왔는지. 'photo'(사진만) / 'api'(사진이 못 읽어 등록 정보로
    # 채웠다) / 'both'(둘이 같은 말을 했다) / 'conflict'(둘이 달랐다).
    # 나눠 재지 않으면 "품목보고 대조가 정확도를 올렸는가" 를 답할 수 없다.
    source = models.CharField(max_length=20, blank=True, default='',
                              verbose_name='값의 출처')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_correction'
        verbose_name = '판독 교정 이력'
        verbose_name_plural = '판독 교정 이력'
        indexes = [
            models.Index(fields=['field', 'corrected'], name='idx_ocr_corr_field'),
            models.Index(fields=['created_at'], name='idx_ocr_corr_date'),
            models.Index(fields=['model', 'variant'], name='idx_ocr_corr_how'),
        ]

    def __str__(self):
        mark = '고침' if self.corrected else '그대로'
        return f'{self.field} {mark}'


class OcrPromptVersion(models.Model):
    """
    판독 프롬프트의 판(版).

    지금까지 프롬프트는 ocr_service.py 안의 상수 하나였다. 고치려면 배포를 해야
    했고, 고치고 나면 **이전 것과 견줄 방법이 없었다** — 어느 판이 몇 점이었는지
    아무 데도 남지 않았다.

    판을 DB 에 두면 세 가지가 된다.
      1. 배포 없이 고치고 되돌린다 (활성 판 하나만 쓰인다)
      2. 판마다 점수를 남겨 견준다 (OcrBenchmarkRun 이 매긴다)
      3. 자동으로 초안을 만들어 둘 수 있다 — **사람이 켜기 전에는 안 쓰인다**

    켜져 있는 판이 없으면 코드에 박힌 기본 프롬프트를 쓴다. 그래서 이 표가
    비어 있어도, DB 가 없어도 판독은 그대로 돈다.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=80, verbose_name='판 이름')
    prompt = models.TextField(verbose_name='프롬프트 전문')
    note = models.TextField(blank=True, default='', verbose_name='무엇을 바꿨는가')
    # 켜져 있는 판은 하나뿐이다. activate() 가 나머지를 끈다.
    active = models.BooleanField(default=False, verbose_name='사용 중')
    # 자동으로 만든 초안인지. 사람이 쓴 것과 섞이면 무엇을 검토해야 할지 모른다.
    auto_generated = models.BooleanField(default=False, verbose_name='자동 초안')
    based_on = models.ForeignKey('self', null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name='revisions', verbose_name='바탕이 된 판')
    # 마지막으로 잰 점수. 재 본 적이 없으면 None — 0 점과 구분해야 한다.
    last_score = models.FloatField(null=True, blank=True, verbose_name='최근 점수')
    last_scored_at = models.DateTimeField(null=True, blank=True, verbose_name='최근 측정 시각')
    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='ocr_prompts', verbose_name='만든 사람')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_prompt_version'
        verbose_name = '판독 프롬프트 판'
        verbose_name_plural = '판독 프롬프트 판'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name}{" (사용 중)" if self.active else ""}'

    def activate(self):
        """이 판만 켠다. 켜져 있는 판은 언제나 하나뿐이어야 한다."""
        OcrPromptVersion.objects.filter(active=True).exclude(pk=self.pk).update(active=False)
        if not self.active:
            self.active = True
            self.save(update_fields=['active'])


class OcrTruthCase(models.Model):
    """
    정답을 적어 둔 사진 한 장. 정확도를 재는 자.

    사람이 화면에서 열 번 눌러 재는 것은 느리고, 무엇보다 사람마다 다르게 고친다.
    정답을 한 번 적어 두면 몇 번이든 같은 잣대로 잴 수 있다.

    파일로 재는 길(management/commands/ocr_benchmark.py)이 이미 있지만 서버에
    파일을 올려 둘 수 있는 사람만 쓸 수 있었다. 같은 일을 화면에서 하게 한다.

    정답은 세 곳에서 온다.
      - 손으로 적는다
      - 판독 결과를 초안으로 받아 고친다
      - **실제로 쓰인 표시사항에서 가져온다** — 사람이 검증하고 적합 판정까지 낸
        값이라 가장 믿을 만한 정답이다
    """
    class Source(models.TextChoices):
        MANUAL = 'manual', '직접 입력'
        DRAFT = 'draft', '판독 초안을 수정'
        LABEL = 'label', '검증된 표시사항에서'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, verbose_name='이름')
    image = models.ImageField(upload_to='ocr_truth/%Y/%m/', verbose_name='표시사항 사진')
    # 이 영역만 잘라 읽는 방식도 함께 재려면 [x, y, 너비, 높이] (원본 픽셀).
    crop_box = models.JSONField(null=True, blank=True, verbose_name='읽을 영역')
    # 품목보고번호가 있으면 등록 정보 대조의 효과도 함께 잴 수 있다.
    report_no = models.CharField(max_length=32, blank=True, default='',
                                 verbose_name='품목보고번호')
    expected = models.JSONField(default=dict, verbose_name='정답')
    source = models.CharField(max_length=10, choices=Source.choices,
                              default=Source.MANUAL, verbose_name='정답의 출처')
    # 사람이 정답이라고 확인했는가. 확인 전 초안을 채점에 쓰면 자기 답을 자기가
    # 채점하는 꼴이 된다.
    verified = models.BooleanField(default=False, verbose_name='정답 확인됨')
    note = models.TextField(blank=True, default='', verbose_name='메모')
    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='ocr_truth_cases', verbose_name='등록한 사람')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ocr_truth_case'
        verbose_name = '판독 정답지'
        verbose_name_plural = '판독 정답지'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def field_count(self):
        """채점 대상 항목 수 — 값이 비어 있는 항목은 그 라벨에 없는 것이라 뺀다."""
        return sum(1 for v in (self.expected or {}).values() if str(v or '').strip())


class OcrBenchmarkRun(models.Model):
    """
    정답지로 한 번 재 본 결과.

    **한 번 돌린 결과로 판단하면 안 된다.** 같은 사진도 매번 다르게 읽힌다.
    그래서 회차(runs)와 편차까지 남겨 두고, 판을 바꾼 전후를 견줄 수 있게 한다.
    """
    id = models.AutoField(primary_key=True)
    prompt_version = models.ForeignKey(OcrPromptVersion, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='benchmark_runs',
                                       verbose_name='프롬프트 판')
    model = models.CharField(max_length=40, verbose_name='모델')
    # 'whole' 사진 전체 / 'crop' 정답지에 적힌 영역만
    variant = models.CharField(max_length=20, default='whole', verbose_name='판독 방식')
    # 품목보고 등록 정보 대조를 켜고 쟀는가. 대조의 기여를 따로 재려면 필요하다.
    use_api = models.BooleanField(default=False, verbose_name='등록 정보 대조')
    case_count = models.IntegerField(default=0, verbose_name='정답지 수')
    runs = models.IntegerField(default=1, verbose_name='회차')
    mean_score = models.FloatField(default=0.0, verbose_name='평균 점수')
    # 항목별 평균·최저·최고·편차와 사진별 상세. 화면이 표로 그린다.
    detail = models.JSONField(default=dict, verbose_name='상세')
    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='ocr_benchmark_runs', verbose_name='실행한 사람')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_benchmark_run'
        verbose_name = '판독 정확도 측정'
        verbose_name_plural = '판독 정확도 측정'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.model} {self.mean_score}점'
