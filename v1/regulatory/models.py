"""
부적합·처분 모델
- RegulatoryNews: 수집된 부적합 정보
- NewsProductMatch: 부적합 뉴스 ↔ 내 제품 M:N 연결
"""
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
    collected_date = models.DateField(auto_now_add=True, verbose_name='수집일', db_index=True)
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
        (ACTION_MONITORING, '모니터링 중'),
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
