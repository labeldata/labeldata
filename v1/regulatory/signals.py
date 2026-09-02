"""
regulatory/signals.py

BOM 원료 또는 원료 보관함이 저장될 때,
해당 유저의 최근 규제 뉴스를 대상으로 자동 재매칭합니다.

[비용 구조]
- AI(OpenAI) 호출: 없음 — ai_parsed=True 뉴스만 대상으로 하여 이미 추출된 keywords 재사용
- 처리 방식: 백그라운드 (요청 응답 블로킹 없음)
- 매칭 범위: 최근 REMATCH_DAYS일 이내 뉴스 + 해당 유저만

[2026-09-02] 이 파일이 사이트 전체를 멈춰 세웠다. 커넥션을 안 닫았고, 저장마다
스레드를 새로 띄웠고, 뉴스 한 건마다 DB 를 다시 읽었다. 셋 다 "백그라운드니까
괜찮다" 는 가정에서 나왔다. 무엇을 어떻게 바꿨는지 아래 주석에 남긴다.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.cache import cache
from django.db import connections
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# 재매칭 대상 뉴스 기간 (일). 너무 오래된 뉴스는 실효성 낮음
REMATCH_DAYS = 180

# 동시에 도는 재매칭 수.
#
# 원래 저장 한 번에 스레드 하나였다. 자동 저장이 30초마다 돌고 BOM 은 한 번에
# 여러 행이 저장되니 순식간에 수십 개가 떠서 저마다 DB 커넥션을 잡았고,
# 계정 커넥션 한도(79)를 넘긴 순간 **사이트 전체가 500** 이 났다. 저장이 몇 번
# 들어오든 동시에 도는 것은 둘까지다.
#
# 풀의 일꾼은 데몬 스레드가 아니라, 서버를 내릴 때 돌던 재매칭 한 번을
# 기다린다. 아래 build_match_cache_for_user 로 한 번이 짧아졌으니 그만큼은
# 기다려도 된다.
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='regulatory-rematch')

# 재매칭은 "지금 이 유저의 상태 전체" 를 다시 보는 일이라, 몇 번을 돌리든
# 결과가 같다. 그래서 이미 예약된 것이 있으면 새로 잡지 않고 그 한 번에
# 묻어 간다. 도는 사이에 또 바뀌었으면 dirty 를 세워 끝난 뒤 한 번만 더 돈다.
#
# 파일 캐시라 여러 워커 프로세스 사이에서 add 가 완전히 원자적이지는 않다.
# 어긋나 봐야 같은 재매칭이 한 번 더 도는 것뿐이라 그대로 둔다.
_COALESCE_TTL = 600  # 초


def _pending_key(user_id):
    return f'regulatory:rematch:pending:{user_id}'


def _dirty_key(user_id):
    return f'regulatory:rematch:dirty:{user_id}'


def _run_rematch_for_user(user_id: int, trigger_label: str):
    """
    풀의 일꾼에서 실행.
    해당 유저 × 최근 REMATCH_DAYS일 뉴스에 대해 매칭만 재실행.
    AI 파싱 없음 → 비용 0.
    """
    try:
        from django.contrib.auth.models import User
        from v1.regulatory.models import RegulatoryNews
        from v1.regulatory.services.matcher import (
            build_match_cache_for_user,
            find_affected_products,
            find_matching_ingredients_unlinked,
            save_matches,
            save_ingredient_matches,
        )

        user = User.objects.get(pk=user_id)

        # 이 유저의 BOM·원료·제품·연락처·오탐패턴을 **한 번에** 읽어 둔다.
        #
        # 안 넘기면 find_affected_products 가 뉴스 한 건마다 그 다섯 가지를
        # 다시 읽는다. 180일치면 뉴스 수만큼 반복되고, 그동안 커넥션을 잡고
        # 있다. 배치 명령은 진작 build_user_match_cache() 로 이걸 피하고
        # 있었는데 시그널 경로만 맨손이었다.
        entry = build_match_cache_for_user(user)

        cutoff = timezone.now() - timedelta(days=REMATCH_DAYS)
        qs = RegulatoryNews.objects.filter(
            ai_parsed=True,
            collected_date__gte=cutoff,
        )

        matched_count = 0
        for news in qs.iterator():
            # ① 제품 BOM 매칭
            product_matches = find_affected_products(
                news, user,
                prefetched_boms=entry['boms'],
                prefetched_ingredients=entry['ingredients'],
                fp_patterns=entry['fp_patterns'],
                prefetched_labels=entry['labels'],
                prefetched_contacts=entry['contacts'],
            )
            if product_matches:
                matched_count += save_matches(news, product_matches)
            # ② 원료 보관함 단독 매칭
            ing_matches = find_matching_ingredients_unlinked(
                news, user,
                prefetched_ingredients=entry['ingredients'],
                fp_patterns=entry['fp_patterns'],
            )
            if ing_matches:
                matched_count += save_ingredient_matches(news, user, ing_matches)

        if matched_count:
            logger.info(
                f'[자동 재매칭] {trigger_label} 저장 → 유저 {user.username} '
                f'신규 매칭 {matched_count}건 (최근 {REMATCH_DAYS}일 뉴스 대상)'
            )

    except Exception as exc:
        logger.error(f'[자동 재매칭] 오류 (user_id={user_id}): {exc}')

    finally:
        # **커넥션을 닫는다.** 요청 밖에서 연 커넥션은 아무도 닫아 주지 않는다
        # (Django 는 요청이 끝날 때만 정리한다). 이걸 빠뜨려 커넥션이 쌓였고,
        # 계정 한도를 넘긴 순간 사이트 전체가 500 이 났다. collector.py 와
        # user_management/views.py 의 백그라운드 작업은 진작 닫고 있었다.
        try:
            connections.close_all()
        except Exception:
            logger.exception('[자동 재매칭] 커넥션 정리 실패 (user_id=%s)', user_id)

        cache.delete(_pending_key(user_id))
        if cache.get(_dirty_key(user_id)):
            # 도는 사이에 또 바뀌었다. 지금 회차가 그걸 봤는지 알 수 없으니
            # 한 번만 더 돈다 - 그 사이 몇 번이 바뀌었든 한 번이면 된다.
            cache.delete(_dirty_key(user_id))
            _trigger_rematch(user_id, f'{trigger_label} 외 변경분')


def _trigger_rematch(user_id: int, trigger_label: str):
    """재매칭을 예약한다 (요청 응답 즉시 반환). 이미 잡혀 있으면 묻어 간다."""
    if not cache.add(_pending_key(user_id), trigger_label, _COALESCE_TTL):
        cache.set(_dirty_key(user_id), True, _COALESCE_TTL)
        return
    try:
        _POOL.submit(_run_rematch_for_user, user_id, trigger_label)
    except Exception:
        # 풀이 닫혔다(서버 종료 중). 예약 자리를 비워 두지 않으면 다음 기동까지
        # 그 유저의 재매칭이 통째로 막힌다.
        cache.delete(_pending_key(user_id))
        logger.exception('[자동 재매칭] 예약 실패 (user_id=%s)', user_id)


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
#
# 매칭이 실제로 읽는 MyLabel 필드는 이것뿐이다 (matcher 의
# _find_product_level_matches 와 _find_admin_matches 가 보는 것). 원재료명·
# 주의사항·영양성분이 바뀐 저장은 매칭 결과를 한 글자도 바꾸지 못한다.
#
# 예전에는 **모든 저장**에 재매칭이 걸렸다. 화면의 자동 저장이 30초 유휴마다
# 도는데(label_creation.js AUTOSAVE_IDLE_MS), 그때마다 180일치 뉴스를 통째로
# 다시 훑었다. 아래 on_label_saved 의 docstring 은 원래부터 "bssh_nm·
# distributor·repacker 변경 시" 라고 적혀 있었다 - 주석이 맞고 코드가 틀렸던
# 것이라 코드를 주석에 맞춘다. 다만 감시 대상은 셋이 아니라 매칭이 실제로
# 읽는 아홉이다.
_MATCH_FIELDS = (
    'my_label_name', 'prdlst_nm', 'food_type', 'prdlst_dcnm',
    'bssh_nm', 'distributor_address', 'repacker_address', 'importer_address',
    'delete_YN',
)

# DB 에서 읽어 온 값을 인스턴스에 붙여 둔다. 저장할 때 이 값과 견주면
# 매칭에 쓰이는 필드가 실제로 바뀌었는지 질의 한 번 없이 알 수 있다.
_SNAPSHOT_ATTR = '_regulatory_match_snapshot'


def _match_snapshot(instance):
    """
    매칭 대상 필드 값 묶음. 견줄 수 없으면 None.

    **미조회(deferred) 필드는 건드리지 않는다.** .only()/.defer() 로 읽어 온
    인스턴스에서 빠진 필드를 읽으면 그 자리에서 DB 를 한 번 더 친다. post_init
    는 인스턴스 하나마다 도니 목록 한 번에 쿼리가 행 수만큼 붙는다 - 지금
    고치고 있는 것과 똑같은 종류의 사고다.

    그런 인스턴스는 None 을 돌려 "견줄 수 없다" 고 말한다. 아래 on_label_saved
    는 그때 예전처럼 재매칭을 돌린다 - 놓치는 것보다 한 번 더 도는 편이 낫다.
    """
    if instance.get_deferred_fields() & set(_MATCH_FIELDS):
        return None
    return tuple(getattr(instance, f, None) for f in _MATCH_FIELDS)


@receiver(post_init, sender='label.MyLabel')
def remember_match_fields(sender, instance, **kwargs):
    """DB 에서 읽은 직후의 매칭 대상 필드 값을 기억해 둔다."""
    try:
        setattr(instance, _SNAPSHOT_ATTR, _match_snapshot(instance))
    except Exception:
        pass


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

    if not created:
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            # 무엇을 저장했는지 저장한 쪽이 알려 준 경우 - 그대로 믿는다.
            if not (set(update_fields) & set(_MATCH_FIELDS)):
                return
        else:
            before = getattr(instance, _SNAPSHOT_ATTR, None)
            # 스냅샷이 없으면(코드에서 직접 만든 인스턴스, 일부 필드만 읽어 온
            # 인스턴스) 판단할 근거가 없다. 그때는 예전처럼 돈다 - 놓치는 것보다
            # 한 번 더 도는 편이 낫다.
            if before is not None and before == _match_snapshot(instance):
                return

    setattr(instance, _SNAPSHOT_ATTR, _match_snapshot(instance))
    _trigger_rematch(user_id, f'제품 #{instance.pk}({instance.my_label_name or ""})')
