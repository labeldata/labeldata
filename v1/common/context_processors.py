from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def static_build_date(request):
    return {'STATIC_BUILD_DATE': getattr(settings, 'STATIC_BUILD_DATE', '')}

def ui_mode(request):
    """UI 모드(V1/V2) 컨텍스트 프로세서.
    세션의 'ui_mode' 값('v1' 또는 'v2')을 읽어 템플릿에 제공합니다.
    - ui_mode : 현재 UI 모드 문자열
    - ui_base : 해당 모드에 맞는 베이스 템플릿 이름
    """
    mode = request.session.get('ui_mode', 'v2')
    if mode == 'v1':
        base = 'base.html'
    else:
        base = 'base_v2.html'
    return {
        'ui_mode': mode,
        'ui_base': base,
    }

def board_notifications(request):
    """게시판 알림 카운트 - 세션 기반 (모델 수정 없음)
    
    세션 만료(12시간) 고려:
    - 세션이 있으면: 마지막 게시판 방문 시간 기준
    - 세션 만료 시: last_login 사용 (최대 12시간 전까지만)
    - 둘 다 없으면: 기본값 (3일 전)
    """
    notification_count = 0
    
    if request.user.is_authenticated:
        from v1.board.models import Board, Comment
        
        # 세션 만료 시간 (12시간)
        session_duration = timedelta(hours=12)
        now = timezone.now()
        
        # 마지막 방문 시간 결정
        last_visit_dt = None
        
        # 1. 세션에서 확인 (가장 정확)
        last_visit = request.session.get('board_last_visit')
        if last_visit:
            try:
                last_visit_dt = timezone.datetime.fromisoformat(last_visit)
                if timezone.is_naive(last_visit_dt):
                    last_visit_dt = timezone.make_aware(last_visit_dt)
                
                # 세션이 너무 오래되었으면 무시 (12시간 초과)
                if now - last_visit_dt > session_duration:
                    last_visit_dt = None
            except (ValueError, TypeError):
                last_visit_dt = None
        
        # 2. 세션에 없거나 만료되었으면 last_login 사용
        if not last_visit_dt and request.user.last_login:
            # last_login도 12시간 이내일 때만 사용
            if now - request.user.last_login <= session_duration:
                last_visit_dt = request.user.last_login
        
        # 3. 둘 다 없거나 오래되었으면 기본값 (3일 전)
        if not last_visit_dt:
            last_visit_dt = now - timedelta(days=3)
        
        # 1. 공지글 알림 (전체 사용자) - 최대 7일
        seven_days_ago = now - timedelta(days=7)
        new_notices = Board.objects.filter(
            is_notice=True,
            created_at__gte=max(last_visit_dt, seven_days_ago)
        ).count()
        notification_count += new_notices
        
        # 2. 새 게시글 알림 (관리자만) - 최대 3일
        if request.user.is_staff:
            three_days_ago = now - timedelta(days=3)
            new_posts = Board.objects.filter(
                is_notice=False,
                created_at__gte=max(last_visit_dt, three_days_ago)
            ).count()
            notification_count += new_posts
        
        # 3. 새 답변 알림 (작성자에게만) - 최대 5일
        five_days_ago = now - timedelta(days=5)
        new_comments = Comment.objects.filter(
            board__author=request.user,
            created_at__gte=max(last_visit_dt, five_days_ago)
        ).exclude(author=request.user).count()
        notification_count += new_comments
    
    return {'board_notification_count': notification_count}

