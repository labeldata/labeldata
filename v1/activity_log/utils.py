from v1.activity_log.models import UserActivityLog


def log_activity(request, category, action, target_id=None):
    """
    사용자 활동 로그 헬퍼 — 실패해도 기능에 영향 없음
    """
    try:
        if request.user.is_authenticated:
            UserActivityLog.objects.create(
                user=request.user,
                category=category,
                action=action,
                target_id=target_id,
            )
    except Exception:
        pass
