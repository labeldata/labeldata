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
