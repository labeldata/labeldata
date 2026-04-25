"""
부적합·처분 모델
- RegulatoryNews: 수집된 부적합 정보
- NewsProductMatch: 부적합 뉴스 ↔ 내 제품 M:N 연결
- InspectionResult: 수거검사(I0460) 원본
- InspectionMatch: 수거검사 ↔ 사용자 매칭 이력
"""
import datetime
from django.db import models
from django.db.models import F
from django.contrib.auth.models import User


class RegulatoryNews(models.Model):
    """수집된 부적합 처분 정보"""

    SOURCE_DOMESTIC = 'domestic'
    SOURCE_IMPORT   = 'import'
    SOURCE_CHOICES  = [
        (SOURCE_DOMESTIC, '국내식품 부적합'),
        (SOURCE_IMPORT,   '수입식품 부적합'),
    ]

    RISK_HIGH = 'HIGH'
    RISK_MED  = 'MED'
    RISK_LOW  = 'LOW'
    RISK_CHOICES = [
        (RISK_HIGH, '중요'),
        (RISK_MED,  '관심'),
        (RISK_LOW,  '일반'),
    ]

    # ── 원본 데이터 ──────────────────────────────────────────────
    api_source = models.CharField(max_length=20, blank=True, default='', verbose_name='API 출처 코드', db_index=True, help_text='수집 API 서비스 ID (I2620/I2640/I0490/I0470/I0480/import)')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, verbose_name='출처', db_index=True)
    external_id = models.CharField(max_length=100, db_index=True, verbose_name='외부 고유번호', help_text='국내: cntntsSn, 수입: API 고유키')
    product_name = models.CharField(max_length=300, verbose_name='부적합 제품명', db_index=True)
    company_name = models.CharField(max_length=200, verbose_name='업체명', blank=True)
    violation_reason = models.TextField(verbose_name='부적합 사유', blank=True)
    raw_detail_text = models.TextField(verbose_name='상세 원문', blank=True)

    # ── AI 분석 결과 ─────────────────────────────────────────────
    ai_keywords = models.JSONField(default=list, verbose_name='AI 추출 키워드', help_text='원재료명 + 검출물질 배열 (매칭 및 UI 표시용)')
    ai_issues = models.JSONField(default=list, blank=True, verbose_name='AI 구조화 이슈', help_text='텍스트에 명시된 원재료 구조화 배열')
    ai_substances = models.JSONField(default=list, blank=True, verbose_name='검출 물질', help_text='텍스트에 명시된 검출 물질명 배열')
    violation_type = models.CharField(max_length=30, blank=True, default='', verbose_name='위반유형 코드', db_index=True)
    ai_summary = models.TextField(blank=True, verbose_name='AI 요약')
    ai_parsed = models.BooleanField(default=False, verbose_name='AI 분석 완료', db_index=True)
    risk_level = models.CharField(max_length=4, choices=RISK_CHOICES, default=RISK_MED, verbose_name='위험도')

    # ── 수집 메타 ────────────────────────────────────────────────
    event_date = models.DateField(null=True, blank=True, verbose_name='발생/처분일', db_index=True, help_text='imp_insp=수입검사부적합일, 국내=처분·회수일')
    collected_date = models.DateField(default=datetime.date.today, verbose_name='수집일', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')

    class Meta:
        db_table  = 'regulatory_news'
        ordering  = [F('event_date').desc(nulls_last=True), '-collected_date', '-created_at']
        verbose_name       = '부적합 정보'
        verbose_name_plural = '부적합 정보 목록'
        unique_together = [('source', 'external_id')]
        indexes = [
            models.Index(fields=['source', 'collected_date']),
            models.Index(fields=['ai_parsed']),
        ]

    def __str__(self):
        return f"[{self.get_source_display()}] {self.product_name}"


class NewsProductMatch(models.Model):
    """부적합 뉴스 ↔ 내 완제품 M:N 연결"""

    news = models.ForeignKey(RegulatoryNews, on_delete=models.CASCADE, related_name='product_matches', verbose_name='부적합 정보')
    product = models.ForeignKey('label.MyLabel', on_delete=models.CASCADE, related_name='regulatory_matches', verbose_name='연관 제품')
    matched_bom = models.ForeignKey('bom.ProductBOM', on_delete=models.SET_NULL, null=True, blank=True, related_name='regulatory_matches', verbose_name='매칭된 BOM 항목')

    matched_keyword = models.CharField(max_length=200, verbose_name='매칭 키워드')
    matched_ingredient = models.CharField(max_length=200, verbose_name='내 원료명')
    match_score = models.FloatField(default=0.0, verbose_name='매칭 점수(0~100)')

    # ── 다차원 위해도 ─────────────────────────────────────────────
    RISK_HIGH = 'HIGH'
    RISK_MED  = 'MED'
    RISK_LOW  = 'LOW'
    RISK_CHOICES = [
        (RISK_HIGH, '중요 (원료+원산지+제조사 일치)'),
        (RISK_MED,  '관심 (원료+원산지 일치)'),
        (RISK_LOW,  '일반 (원료명만 일치)'),
    ]
    risk_level = models.CharField(max_length=4, choices=RISK_CHOICES, default=RISK_LOW, verbose_name='매칭 위해도')
    risk_score = models.IntegerField(default=0, verbose_name='위해도 점수(0~100)')
    risk_reasons = models.JSONField(default=list, blank=True, verbose_name='위해도 산정 근거', help_text='["원료명 일치(마늘종)", "원산지 일치(중국)"]')

    # ── 알림 / 확인 상태 ─────────────────────────────────────────
    read_yn = models.BooleanField(default=False, verbose_name='확인 여부', db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='확인 일시')

    # ── 오탐지 신고 ───────────────────────────────────────────────
    false_positive_yn = models.BooleanField(default=False, verbose_name='오탐지 신고', db_index=True)
    false_positive_at = models.DateTimeField(null=True, blank=True, verbose_name='오탐지 신고 일시')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        db_table       = 'regulatory_news_product_match'
        unique_together = ('news', 'product')
        ordering        = ['-created_at']
        verbose_name        = '부적합-제품 연결'
        verbose_name_plural = '부적합-제품 연결 목록'
        indexes = [
            models.Index(fields=['product', 'read_yn']),
            models.Index(fields=['false_positive_yn']),
        ]

    def __str__(self):
        return f"{self.news} → {self.product}"


class NewsIngredientMatch(models.Model):
    """
    부적합 뉴스 ↔ 원료 보관함(BOM 미연결) 매칭.
    제품에 연결되지 않은 MyIngredient 단독으로 키워드가 매칭된 경우 기록.
    """
    RISK_HIGH = 'HIGH'
    RISK_MED  = 'MED'
    RISK_LOW  = 'LOW'
    RISK_CHOICES = [
        (RISK_HIGH, '중요'),
        (RISK_MED,  '관심'),
        (RISK_LOW,  '일반'),
    ]

    news = models.ForeignKey(RegulatoryNews, on_delete=models.CASCADE, related_name='ingredient_matches', verbose_name='부적합 정보')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ingredient_news_matches', verbose_name='사용자')
    ingredient = models.ForeignKey('label.MyIngredient', on_delete=models.CASCADE, related_name='news_matches', verbose_name='원료')

    matched_keyword = models.CharField(max_length=200, verbose_name='매칭 키워드')
    match_score = models.FloatField(default=0.0, verbose_name='매칭 점수')
    risk_level = models.CharField(max_length=4, choices=RISK_CHOICES, default=RISK_LOW, verbose_name='등급')
    risk_score = models.IntegerField(default=0, verbose_name='위해도 점수')

    read_yn = models.BooleanField(default=False, db_index=True, verbose_name='확인 여부')
    dismissed_yn = models.BooleanField(default=False, db_index=True, verbose_name='해당 없음')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'regulatory_news_ingredient_match'
        unique_together = ('news', 'user', 'ingredient')
        ordering        = ['-created_at']
        verbose_name        = '부적합-원료 연결'
        verbose_name_plural = '부적합-원료 연결 목록'

    def __str__(self):
        return f"{self.news} → {self.ingredient}"


class RegulatoryMatchAction(models.Model):
    """
    뉴스 매칭(제품/원료)에 대한 조치 이력 기록.
    product_match 또는 ingredient_match 중 하나만 설정.
    """
    ACTION_DISMISSED  = 'dismissed'
    ACTION_MONITORING = 'monitoring'
    ACTION_RESOLVED   = 'resolved'
    ACTION_MEMO       = 'memo'
    ACTION_CHOICES = [
        (ACTION_DISMISSED,  '해당 없음'),
        (ACTION_MONITORING, '진행 중'),
        (ACTION_RESOLVED,   '조치 완료'),
        (ACTION_MEMO,       '메모'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='regulatory_actions', verbose_name='사용자')
    product_match = models.ForeignKey(NewsProductMatch, on_delete=models.CASCADE, null=True, blank=True, related_name='actions', verbose_name='제품 매칭')
    ingredient_match = models.ForeignKey(NewsIngredientMatch, on_delete=models.CASCADE, null=True, blank=True, related_name='actions', verbose_name='원료 매칭')

    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='조치 유형')
    memo = models.TextField(blank=True, verbose_name='메모')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='기록일시')

    class Meta:
        db_table = 'regulatory_match_action'
        ordering = ['-created_at']
        verbose_name        = '매칭 조치 이력'
        verbose_name_plural = '매칭 조치 이력 목록'

    def __str__(self):
        target = self.product_match or self.ingredient_match
        return f"[{self.get_action_type_display()}] {target}"


class InspectionResult(models.Model):
    """
    식약처 수거검사(I0460) 원본 데이터.
    tkawyprno(수거증번호)를 unique key로 사용하며,
    판정결과(jdgmnt_cd_nm) 변동을 감지해 2차 알림을 트리거한다.
    """
    tkawyprno        = models.CharField(max_length=50, unique=True, verbose_name='수거증번호')
    plan_titl        = models.CharField(max_length=200, blank=True, verbose_name='수거계획명')
    bssh_nm          = models.CharField(max_length=200, blank=True, db_index=True, verbose_name='업소명')
    prdtnm           = models.CharField(max_length=300, blank=True, verbose_name='제품명')
    prdlst_report_no = models.CharField(max_length=50,  blank=True, db_index=True, verbose_name='품목보고번호')
    jdgmnt_cd_nm     = models.CharField(max_length=50,  blank=True, verbose_name='판정결과')
    induty_cd_nm     = models.CharField(max_length=100, blank=True, verbose_name='업종')
    site_addr        = models.CharField(max_length=300, blank=True, verbose_name='소재지')
    tkawydtm         = models.CharField(max_length=20,  blank=True, verbose_name='수거일자')
    tkawyspci_typecd_nm = models.CharField(max_length=50, blank=True, verbose_name='검체구분')
    exc_instt_nm     = models.CharField(max_length=100, blank=True, verbose_name='수행기관명')
    last_updt_dtm    = models.CharField(max_length=50,  blank=True, verbose_name='최종수정일시')
    collected_at     = models.DateTimeField(auto_now_add=True, verbose_name='수집일시')

    class Meta:
        db_table            = 'inspection_result'
        ordering            = ['-tkawydtm']
        verbose_name        = '수거검사 결과'
        verbose_name_plural = '수거검사 결과 목록'
        indexes = [
            models.Index(fields=['tkawydtm']),
            models.Index(fields=['last_updt_dtm']),
        ]

    def __str__(self):
        return f"[{self.tkawydtm}] {self.bssh_nm} / {self.prdtnm} ({self.jdgmnt_cd_nm or '판정전'})"


class InspectionMatch(models.Model):
    """
    수거검사 결과 ↔ 사용자 매칭 이력.
    alert_phase:
      1 = 신규 수거 감지 (최초 매칭)
      2 = 판정결과 변동 감지
    match_reason:
      label_no   = 내제품 품목보고번호 일치
      license_no = 내정보 인허가번호 포함
      company    = 내정보 회사명 포함
    """
    PHASE_COLLECTION = 1
    PHASE_JUDGMENT   = 2
    PHASE_CHOICES = [
        (PHASE_COLLECTION, '수거 감지'),
        (PHASE_JUDGMENT,   '판정결과 변동'),
    ]

    REASON_LABEL   = 'label_no'
    REASON_LICENSE = 'license_no'
    REASON_COMPANY = 'company'
    REASON_CHOICES = [
        (REASON_LABEL,   '내제품 품목보고번호 일치'),
        (REASON_LICENSE, '인허가번호 포함'),
        (REASON_COMPANY, '회사명 포함'),
    ]

    inspection  = models.ForeignKey(InspectionResult, on_delete=models.CASCADE,
                                    related_name='matches', verbose_name='수거검사')
    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='inspection_matches', verbose_name='사용자')
    label       = models.ForeignKey('label.MyLabel', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='inspection_matches',
                                    verbose_name='매칭 제품')

    alert_phase   = models.IntegerField(choices=PHASE_CHOICES, verbose_name='알림 단계')
    match_reason  = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name='매칭 사유')
    matched_value = models.CharField(max_length=100, blank=True, verbose_name='매칭된 값',
                                     help_text='품목보고번호, 인허가번호, 회사명 중 실제 매칭된 값')
    prev_judgment = models.CharField(max_length=50, blank=True, verbose_name='이전 판정결과',
                                     help_text='2차 알림 메시지용')

    notified_at = models.DateTimeField(null=True, blank=True, verbose_name='알림 발송일시')
    read_yn     = models.BooleanField(default=False, db_index=True, verbose_name='확인 여부')
    read_at     = models.DateTimeField(null=True, blank=True, verbose_name='확인 일시')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'inspection_match'
        ordering            = ['-created_at']
        verbose_name        = '수거검사 매칭'
        verbose_name_plural = '수거검사 매칭 목록'
        indexes = [
            models.Index(fields=['user', 'read_yn']),
            models.Index(fields=['inspection', 'user', 'alert_phase']),
        ]

    def __str__(self):
        return f"[{self.get_alert_phase_display()}] {self.inspection} → {self.user}"
