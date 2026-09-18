# -*- coding: utf-8 -*-
"""
만료 알림이 **어느 판**을 가리키는가.

화면이 서로 다른 말을 하고 있었다
─────────────────────────────────
문서함은 한 문서의 여러 판을 한 줄로 묶어 **최신 판만** 보여 준다
(`views._group_versions`). 그런데 만료를 세는 자리들은 `active_yn=True` 인
행을 전부 셌다. 옛 판은 새 판이 올라와도 지워지지 않으므로
(`active_yn=False` 는 **삭제**할 때만 붙는다) 그 행들이 그대로 남아 있다.

    v1 <- v2 <- ... <- v7        문서함은 v7 을 보여 준다
    v3 의 만료일 2026-10-01      알림은 v3 을 가리킨다

운영에서 그대로 나왔다. 「만료 예정 문서」가 '겉바속쫀브라우니_주표시면1.jpg'
를 13일 남았다고 알렸는데, 문서함에서 같은 문서를 열면 **무기한**이었다.
사용자는 만료일을 찾을 수가 없다 — 화면에 없는 판의 날짜이기 때문이다.

그래서 규칙을 한 곳에 둔다
──────────────────────────
여섯 자리가 같은 질의를 저마다 손으로 적고 있었다(대시보드 칩·제품조회 거르기·
제품조회 목록·만료 예정·만료됨·알림 메일). 하나를 고치면 나머지 다섯이 조용히
어긋난다. 이 모듈이 그 조건의 유일한 자리다.
"""
from datetime import timedelta

from django.utils import timezone

from v1.products.models import EXPIRING_SOON_DAYS, ProductDocument


def superseded_ids():
    """
    새 판이 올라와 더 이상 현재가 아닌 판의 id.

    판은 **줄로 이어진다**(v1 <- v2 <- v3). 그래서 '나를 가리키는 살아 있는
    판이 있으면 나는 옛 판' 이다. 지워진 판은 나를 밀어내지 못하므로
    `active_yn=True` 인 자식만 센다 — 새 판을 올렸다가 지우면 옛 판이 다시
    현재가 되는 것이 맞다.
    """
    return (ProductDocument.objects
            .filter(active_yn=True, parent_document__isnull=False)
            .values_list('parent_document_id', flat=True))


def current_documents(user=None):
    """살아 있는 **현재 판**만. 문서함이 보여 주는 것과 같은 집합이다."""
    qs = ProductDocument.objects.filter(active_yn=True).exclude(
        document_id__in=superseded_ids())
    if user is not None:
        qs = qs.filter(label__user_id=user)
    return qs


def expiring(user=None, days=EXPIRING_SOON_DAYS, today=None):
    """오늘부터 `days` 일 안에 만료되는 현재 판. 이미 지난 것은 빼고."""
    today = today or timezone.localdate()
    return (current_documents(user)
            .filter(expiry_date__isnull=False,
                    expiry_date__gte=today,
                    expiry_date__lte=today + timedelta(days=days))
            .select_related('label', 'document_type')
            .order_by('expiry_date'))


def expired(user=None, today=None):
    """이미 만료된 현재 판. 늦은 것부터 보여 준다."""
    today = today or timezone.localdate()
    return (current_documents(user)
            .filter(expiry_date__isnull=False, expiry_date__lt=today)
            .select_related('label', 'document_type')
            .order_by('-expiry_date'))
