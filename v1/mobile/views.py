from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from v1.regulatory.models import RegulatoryNews
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from .serializers import (
    AppDeviceSerializer, AlertRuleSerializer,
    PushNotificationLogSerializer, BookmarkSerializer,
    RegulatoryNewsSerializer,
)
from .services.push_service import backfill_alerts_for_rule


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

    device, _ = AppDevice.objects.update_or_create(
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
        AppDevice.objects.filter(device_id=device_id).update(user=user)

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
        AppDevice.objects.filter(device_id=device_id).update(user=None)
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

    if request.method == 'GET':
        rules = device.rules.all()
        return Response(AlertRuleSerializer(rules, many=True).data)

    # POST
    max_rules = settings.MOBILE_MEMBER_MAX_RULES if device.user else settings.MOBILE_GUEST_MAX_RULES
    if device.rules.filter(is_active=True).count() >= max_rules:
        return Response({'error': f'최대 {max_rules}개까지 등록 가능합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = AlertRuleSerializer(data=request.data)
    if serializer.is_valid():
        rule = serializer.save(device=device)
        # 신규 키워드 등록 즉시 기존 데이터 전체 매칭 (동기 실행)
        backfill_result = {'created': 0, 'previews': []}
        try:
            backfill_result = backfill_alerts_for_rule(rule)
        except Exception:
            pass  # 백필 실패해도 키워드 등록 자체는 성공 처리
        data = serializer.data
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

    try:
        rule = device.rules.get(pk=rule_id)
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

    logs = device.notifications.select_related('news').all()
    return Response(PushNotificationLogSerializer(logs, many=True).data)


@api_view(['PATCH'])
@permission_classes([AllowAny])
def notification_read(request, device_id, noti_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

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

    try:
        log = device.notifications.get(pk=noti_id)
    except PushNotificationLog.DoesNotExist:
        return Response({'error': '알림을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    log.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([AllowAny])
def notification_read_all(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
    device.notifications.filter(is_read=False).update(is_read=True)
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
