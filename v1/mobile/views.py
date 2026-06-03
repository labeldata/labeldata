import logging
import re

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from v1.regulatory.models import RegulatoryNews, InspectionMatch
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from .serializers import (
    AppDeviceSerializer, AlertRuleSerializer,
    PushNotificationLogSerializer, BookmarkSerializer,
    RegulatoryNewsSerializer, InspectionMatchNotificationSerializer,
)
from .services.push_service import backfill_alerts_for_rule, send_immediate_for_rule

logger = logging.getLogger(__name__)

# Android Build.ID 형식: BP2A.250605.031.A3 / QKR1.191246.002 등
_ANDROID_BUILD_ID_RE = re.compile(r'^[A-Z0-9]{4,}\.[0-9]{6}\.[0-9A-Z.]+$')


def _get_device_or_404(device_id):
    try:
        return AppDevice.objects.get(device_id=device_id)
    except AppDevice.DoesNotExist:
        return None


# ── 기기 등록 ────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register_device(request):
    device_id = request.data.get('device_id')
    if not device_id:
        return Response({'error': 'device_id 필수'}, status=status.HTTP_400_BAD_REQUEST)

    # Build.ID 형식 감지 — 이 값은 기기 고유 ID가 아니므로 경고 로그를 남긴다
    if _ANDROID_BUILD_ID_RE.match(device_id):
        logger.warning(
            '[DEVICE_ID] Android Build.ID 형식 감지: device_id=%s platform=%s app_version=%s '
            '(Build.ID는 동일 모델·펌웨어 기기 간 충돌 가능 — 앱에서 UUID로 교체 필요)',
            device_id,
            request.data.get('platform', 'android'),
            request.data.get('app_version', ''),
        )

    # 이미 다른 사용자가 연결된 레코드가 있으면 경고
    existing = AppDevice.objects.filter(device_id=device_id).select_related('user').first()
    if existing and existing.user_id is not None:
        logger.warning(
            '[DEVICE_COLLISION] register_device: device_id=%s 가 이미 user_id=%s(%s)에 연결되어 있음 '
            '— 덮어쓰기 전 충돌 가능성 확인 필요',
            device_id, existing.user_id, existing.user,
        )

    device, created = AppDevice.objects.update_or_create(
        device_id=device_id,
        defaults={
            'platform': request.data.get('platform', 'android'),
            'app_version': request.data.get('app_version', ''),
            'fcm_token': request.data.get('fcm_token'),
        },
    )
    return Response(AppDeviceSerializer(device).data, status=status.HTTP_200_OK)


# ── 인증 ─────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    device_id = request.data.get('device_id')

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': '아이디 또는 비밀번호가 올바르지 않습니다.'}, status=status.HTTP_401_UNAUTHORIZED)

    if device_id:
        # 기기 소유자 교체 여부 감지
        previous = AppDevice.objects.filter(device_id=device_id).select_related('user').first()
        if previous and previous.user_id is not None and previous.user_id != user.pk:
            logger.warning(
                '[USER_HIJACK] login: device_id=%s 의 소유자가 user_id=%s(%s) → user_id=%s(%s) 로 교체됨 '
                '(Build.ID 충돌 또는 기기 공유 의심)',
                device_id,
                previous.user_id, previous.user,
                user.pk, user,
            )
        AppDevice.objects.filter(device_id=device_id).update(user=user)

        # 비회원 상태에서 등록한 device-based 키워드를 user-based로 승격
        # (로그인 후 웹/앱 양쪽에서 동일 키워드가 보이도록)
        try:
            _device = AppDevice.objects.get(device_id=device_id)
            guest_rules = list(
                AlertRule.objects.filter(device=_device, user__isnull=True)
            )
            migrated = 0
            for r in guest_rules:
                dup_exists = AlertRule.objects.filter(
                    user=user,
                    category=r.category,
                    keyword=r.keyword,
                    match_type=r.match_type,
                ).exists()
                if dup_exists:
                    # 웹/다른 기기에 이미 같은 키워드 있음 → 중복 제거
                    r.delete()
                else:
                    r.user = user
                    r.device = None
                    r.save(update_fields=['user', 'device'])
                    migrated += 1
            if migrated:
                logger.info(
                    '[LOGIN] device_id=%s 비회원 키워드 %d개 → user=%s 로 승격',
                    device_id, migrated, user.pk,
                )
        except AppDevice.DoesNotExist:
            pass

    refresh = RefreshToken.for_user(user)
    device_data = None
    if device_id:
        try:
            device = AppDevice.objects.get(device_id=device_id)
            device_data = AppDeviceSerializer(device).data
        except AppDevice.DoesNotExist:
            pass
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'username': user.username,
        'device': device_data,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    device_id = request.data.get('device_id')
    if device_id:
        # user FK를 None으로 먼저 읽어두고 업데이트
        try:
            device = AppDevice.objects.get(device_id=device_id)
            user_obj = device.user  # 로그아웃 전 유저 참조 보존
        except AppDevice.DoesNotExist:
            return Response({'detail': 'ok'})

        AppDevice.objects.filter(device_id=device_id).update(user=None)

        # 비회원 한도(MOBILE_GUEST_MAX_RULES)를 초과하는 키워드를 비활성화
        guest_max = settings.MOBILE_GUEST_MAX_RULES

        if user_obj:
            # 회원 전용(user-based) 규칙에서 초과분 비활성화
            user_rules_qs = AlertRule.objects.filter(
                user=user_obj, is_active=True
            ).order_by('created_at')
            excess_ids = list(user_rules_qs.values_list('id', flat=True)[guest_max:])
            if excess_ids:
                AlertRule.objects.filter(id__in=excess_ids).update(is_active=False)
                logger.info(
                    '[LOGOUT] user=%s 초과 키워드 %d개 비활성화',
                    user_obj.pk, len(excess_ids),
                )
        else:
            # 비회원(device-based) 규칙 초과분 비활성화 (user 없이 등록된 경우)
            excess_ids = list(
                device.rules
                .filter(is_active=True, user__isnull=True)
                .order_by('created_at')
                .values_list('id', flat=True)[guest_max:]
            )
            if excess_ids:
                device.rules.filter(id__in=excess_ids).update(is_active=False)
                logger.info(
                    '[LOGOUT] device_id=%s 초과 키워드 %d개 비활성화',
                    device_id, len(excess_ids),
                )
    return Response({'detail': 'ok'})


# ── 부적합 피드 ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def news_list(request):
    qs = RegulatoryNews.objects.filter(ai_parsed=True)

    source = request.query_params.get('source')
    if source:
        qs = qs.filter(source=source)

    q = request.query_params.get('q', '').strip()
    if q:
        qs = qs.filter(Q(product_name__icontains=q) | Q(company_name__icontains=q))

    page = max(int(request.query_params.get('page', 1)), 1)
    page_size = 20
    offset = (page - 1) * page_size
    total = qs.count()
    items = qs[offset:offset + page_size]

    return Response({
        'count': total,
        'num_pages': (total + page_size - 1) // page_size,
        'page': page,
        'results': RegulatoryNewsSerializer(items, many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def news_detail(request, pk):
    try:
        news = RegulatoryNews.objects.get(pk=pk)
    except RegulatoryNews.DoesNotExist:
        return Response({'error': '존재하지 않는 정보입니다.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RegulatoryNewsSerializer(news).data)


# ── 알림 규칙 ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def rules_list(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    owner_user = device.user  # 로그인이면 User, 비회원이면 None

    if request.method == 'GET':
        if owner_user:
            rules = AlertRule.objects.filter(user=owner_user).order_by('-created_at')
        else:
            rules = device.rules.filter(user__isnull=True).order_by('-created_at')
        return Response(AlertRuleSerializer(rules, many=True).data)

    # POST — 신규 키워드 등록
    max_rules = settings.MOBILE_MEMBER_MAX_RULES if owner_user else settings.MOBILE_GUEST_MAX_RULES

    if owner_user:
        active_count = AlertRule.objects.filter(user=owner_user, is_active=True).count()
    else:
        active_count = device.rules.filter(user__isnull=True, is_active=True).count()

    if active_count >= max_rules:
        return Response({'error': f'최대 {max_rules}개까지 등록 가능합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = AlertRuleSerializer(data=request.data)
    if serializer.is_valid():
        vd = serializer.validated_data
        if owner_user:
            rule, created = AlertRule.objects.get_or_create(
                user=owner_user,
                category=vd['category'],
                keyword=vd['keyword'],
                match_type=vd['match_type'],
                defaults={'is_active': True, 'device': None},
            )
            if not created and not rule.is_active:
                rule.is_active = True
                rule.save(update_fields=['is_active'])
                created = True
        else:
            rule, created = AlertRule.objects.get_or_create(
                device=device,
                user=None,
                category=vd['category'],
                keyword=vd['keyword'],
                match_type=vd['match_type'],
                defaults={'is_active': True},
            )

        if not created:
            return Response({'error': '이미 등록된 키워드입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        backfill_result = {'created': 0, 'previews': [], 'log_ids': []}
        try:
            backfill_result = backfill_alerts_for_rule(rule)
            send_immediate_for_rule(rule, backfill_result.get('log_ids', []))
        except Exception:
            pass
        data = dict(AlertRuleSerializer(rule).data)
        data['matched_count'] = backfill_result.get('created', 0)
        data['previews'] = backfill_result.get('previews', [])
        return Response(data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@permission_classes([AllowAny])
def rule_detail(request, device_id, rule_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    owner_user = device.user

    try:
        if owner_user:
            rule = AlertRule.objects.get(pk=rule_id, user=owner_user)
        else:
            rule = AlertRule.objects.get(pk=rule_id, device=device, user__isnull=True)
    except AlertRule.DoesNotExist:
        return Response({'error': '규칙을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        serializer = AlertRuleSerializer(rule, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    rule.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── 보관함 ───────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def bookmarks_list(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        bookmarks = device.bookmarks.select_related('news').all()
        return Response(BookmarkSerializer(bookmarks, many=True).data)

    max_bookmarks = settings.MOBILE_MEMBER_MAX_BOOKMARKS if device.user else settings.MOBILE_GUEST_MAX_BOOKMARKS
    if device.bookmarks.count() >= max_bookmarks:
        return Response({'error': f'최대 {max_bookmarks}개까지 저장 가능합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    news_id = request.data.get('news_id')
    try:
        news = RegulatoryNews.objects.get(pk=news_id)
    except RegulatoryNews.DoesNotExist:
        return Response({'error': '존재하지 않는 뉴스입니다.'}, status=status.HTTP_404_NOT_FOUND)

    bookmark, created = Bookmark.objects.get_or_create(device=device, news=news)
    return Response(BookmarkSerializer(bookmark).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def bookmark_detail(request, device_id, bookmark_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        bookmark = device.bookmarks.get(pk=bookmark_id)
    except Bookmark.DoesNotExist:
        return Response({'error': '스크랩을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    bookmark.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── 알림 내역 ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def notifications_list(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    # 일반 알림 (키워드·제품·원료 매칭)
    # sent_at IS NOT NULL: 배치 발송 완료된 항목만 표시 (신규 키워드 즉시 발송분 포함)
    logs = (
        device.notifications
        .filter(sent_at__isnull=False)
        .select_related('news', 'rule_triggered')
    )
    log_data = PushNotificationLogSerializer(logs, many=True).data

    # 수거검사 알림 — 기기 소유 사용자의 InspectionMatch (fcm_sent_at 있는 것만)
    insp_data = []
    if device.user_id:
        insp_matches = (
            InspectionMatch.objects
            .filter(
                user_id=device.user_id,
                notified_at__isnull=False,
            )
            .select_related('inspection')
            .order_by('-notified_at')
        )
        insp_data = InspectionMatchNotificationSerializer(insp_matches, many=True).data

    # 두 목록을 created_at 내림차순으로 병합
    merged = sorted(
        list(log_data) + list(insp_data),
        key=lambda x: x.get('created_at') or '',
        reverse=True,
    )
    return Response(merged)


@api_view(['PATCH'])
@permission_classes([AllowAny])
def notification_read(request, device_id, noti_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    noti_type = request.query_params.get('type', 'log')

    if noti_type == 'inspection':
        if not device.user_id:
            return Response({'error': '로그인 필요'}, status=status.HTTP_403_FORBIDDEN)
        try:
            match = InspectionMatch.objects.get(pk=noti_id, user_id=device.user_id)
        except InspectionMatch.DoesNotExist:
            return Response({'error': '알림을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        match.read_yn = True
        match.save(update_fields=['read_yn'])
    else:
        try:
            log = device.notifications.get(pk=noti_id)
        except PushNotificationLog.DoesNotExist:
            return Response({'error': '알림을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        log.is_read = True
        log.save(update_fields=['is_read'])

    return Response({'detail': 'ok'})


@api_view(['DELETE'])
@permission_classes([AllowAny])
def notification_delete(request, device_id, noti_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    noti_type = request.query_params.get('type', 'log')

    if noti_type == 'inspection':
        if not device.user_id:
            return Response({'error': '로그인 필요'}, status=status.HTTP_403_FORBIDDEN)
        try:
            InspectionMatch.objects.get(pk=noti_id, user_id=device.user_id).delete()
        except InspectionMatch.DoesNotExist:
            return Response({'error': '알림을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
    else:
        try:
            device.notifications.get(pk=noti_id).delete()
        except PushNotificationLog.DoesNotExist:
            return Response({'error': '알림을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([AllowAny])
def notification_read_all(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
    # 발송 완료된 항목만 읽음 처리 (sent_at IS NOT NULL)
    device.notifications.filter(is_read=False, sent_at__isnull=False).update(is_read=True)
    if device.user_id:
        InspectionMatch.objects.filter(
            user_id=device.user_id, read_yn=False,
            notified_at__isnull=False,
        ).update(read_yn=True)
    return Response({'detail': 'ok'})


# ── 앱 버전 ───────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def version_check(request):
    """Flutter 앱 버전 체크 — { force_update, latest_version, store_url, message }"""
    platform = request.query_params.get('platform', 'android')
    current = request.query_params.get('version', '0.0.0')
    try:
        v = AppVersion.objects.get(platform=platform)
    except AppVersion.DoesNotExist:
        return Response({'force_update': False, 'latest_version': current, 'store_url': '', 'message': ''})

    try:
        def _ver(s):
            return tuple(int(x) for x in s.split('.')[:3])
        force_update = _ver(current) < _ver(v.min_version)
    except Exception:
        force_update = False

    return Response({
        'force_update': force_update,
        'latest_version': v.latest_version,
        'store_url': v.store_url,
        'message': v.force_message or '',
    })
