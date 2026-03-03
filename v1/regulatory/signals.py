"""
regulatory/signals.py

BOM 원료 또는 원료 보관함이 저장될 때,
해당 유저의 최근 규제 뉴스를 대상으로 자동 재매칭합니다.

[비용 구조]
- AI(OpenAI) 호출: 없음 — ai_parsed=True 뉴스만 대상으로 하여 이미 추출된 keywords 재사용
- 처리 방식: 백그라운드 스레드 (요청 응답 블로킹 없음)
- 매칭 범위: 최근 REMATCH_DAYS일 이내 뉴스 + 해당 유저만
"""
import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# 재매칭 대상 뉴스 기간 (일). 너무 오래된 뉴스는 실효성 낮음
REMATCH_DAYS = 180


def _run_rematch_for_user(user_id: int, trigger_label: str):
    """
    백그라운드 스레드에서 실행.
    해당 유저 × 최근 REMATCH_DAYS일 뉴스에 대해 매칭만 재실행.
    AI 파싱 없음 → 비용 0.
    """
    try:
        from django.contrib.auth.models import User
        from v1.regulatory.models import RegulatoryNews
        from v1.regulatory.services.matcher import (
            find_affected_products,
            find_matching_ingredients_unlinked,
            save_matches,
            save_ingredient_matches,
        )

        user = User.objects.get(pk=user_id)
        cutoff = timezone.now() - timedelta(days=REMATCH_DAYS)
        qs = RegulatoryNews.objects.filter(
            ai_parsed=True,
            collected_date__gte=cutoff,
        )

        matched_count = 0
        for news in qs.iterator():
            # ① 제품 BOM 매칭
            product_matches = find_affected_products(news, user)
            if product_matches:
                matched_count += save_matches(news, product_matches)
            # ② 원료 보관함 단독 매칭
            ing_matches = find_matching_ingredients_unlinked(news, user)
            if ing_matches:
                matched_count += save_ingredient_matches(news, user, ing_matches)

        if matched_count:
            logger.info(
                f'[자동 재매칭] {trigger_label} 저장 → 유저 {user.username} '
                f'신규 매칭 {matched_count}건 (최근 {REMATCH_DAYS}일 뉴스 대상)'
            )

    except Exception as exc:
        logger.error(f'[자동 재매칭] 오류 (user_id={user_id}): {exc}')


def _trigger_rematch(user_id: int, trigger_label: str):
    """데몬 스레드로 재매칭 실행 (요청 응답 즉시 반환)."""
    t = threading.Thread(
        target=_run_rematch_for_user,
        args=(user_id, trigger_label),
        daemon=True,
        name=f'regulatory-rematch-{user_id}',
    )
    t.start()


# ── BOM 원료 저장 시 ──────────────────────────────────────────────────────────

@receiver(post_save, sender='bom.ProductBOM')
def on_bom_saved(sender, instance, created, **kwargs):
    """BOM 행이 추가/수정되면 해당 유저의 규제 매칭 재실행."""
    try:
        user_id = instance.parent_label.user_id_id
    except Exception:
        return
    _trigger_rematch(user_id, f'BOM #{instance.pk}({instance.ingredient_name or ""})')


# ── 원료 보관함(MyIngredient) 저장 시 ──────────────────────────────────────────

@receiver(post_save, sender='label.MyIngredient')
def on_ingredient_saved(sender, instance, created, **kwargs):
    """원료 보관함 원료가 추가/수정되면 해당 유저의 규제 매칭 재실행."""
    try:
        user_id = instance.user_id_id
    except Exception:
        return
    _trigger_rematch(user_id, f'원료 #{instance.pk}({instance.prdlst_nm or ""})')


# ── 제품 기본정보(MyLabel) 업체 필드 변경 시 ──────────────────────────────────

@receiver(post_save, sender='label.MyLabel')
def on_label_saved(sender, instance, created, **kwargs):
    """
    제품(MyLabel)의 bssh_nm·distributor·repacker 변경 시 재매칭.
    행정처분 매칭에 이 필드들을 사용하므로 변경 시 재실행 필요.
    """
    try:
        user_id = instance.user_id_id
    except Exception:
        return
    _trigger_rematch(user_id, f'제품 #{instance.pk}({instance.my_label_name or ""})')
