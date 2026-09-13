import logging
import re

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework import status
from django.db import IntegrityError
from django_ratelimit.decorators import ratelimit
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from v1.common import withdrawal
from v1.regulatory.models import RegulatoryNews, InspectionMatch
from .models import AppDevice, AlertRule, PushNotificationLog, Bookmark, AppVersion
from .serializers import (
    AppDeviceSerializer, AlertRuleSerializer,
    PushNotificationLogSerializer, BookmarkSerializer,
    RegulatoryNewsSerializer, RegulatoryNewsDetailSerializer,
    InspectionMatchNotificationSerializer,
)
from .services.push_service import backfill_alerts_for_rule, send_immediate_for_rule

logger = logging.getLogger(__name__)

User = get_user_model()

# Android Build.ID 형식: BP2A.250605.031.A3 / QKR1.191246.002 등
_ANDROID_BUILD_ID_RE = re.compile(r'^[A-Z0-9]{4,}\.[0-9]{6}\.[0-9A-Z.]+$')


# 알림 목록은 두 표를 하나로 합쳐 준다 — PushNotificationLog 와
# InspectionMatch. 둘 다 1부터 도는 제 pk 를 쓰는데 직렬화 결과에서는 둘 다
# 그냥 `id` 라 **네임스페이스가 없었다.** 앱은 그 번호 하나로 원소를 되찾아
# `?type=` 을 정하므로(`notifications_provider.dart` 의 firstWhere), 번호가
# 겹치면 수거검사 알림을 지웠는데 엉뚱한 부적합 알림이 사라졌다.
#
# 수거검사 쪽 번호를 이 값만큼 밀어 **한 목록 안에서 겹치지 않게** 한다.
# 되돌리는 것은 서버가 하므로 앱은 고치지 않아도 된다. 이미 깔려 있는 앱이
# 보내는 원래 pk 도 `?type=inspection` 과 함께 그대로 받는다.
INSPECTION_ID_OFFSET = 1_000_000_000


def _split_notification_id(noti_id, noti_type):
    """(갈래, 그 표에서의 pk) 로 되돌린다."""
    if noti_id is not None and noti_id >= INSPECTION_ID_OFFSET:
        return 'inspection', noti_id - INSPECTION_ID_OFFSET
    return noti_type, noti_id


def _rate_limited(request):
    """
    `@ratelimit(block=True)` 은 `Ratelimited`(PermissionDenied 의 자식)를
    던진다. 그 데코레이터가 `@api_view` **바깥**에 있어 DRF 예외 처리를
    안 타고 Django 코어로 올라가고, 이 저장소의 handler403 이 그것을
    **HTML 404** 로 바꾼다. 앱은 JSON 을 기대하므로 "알 수 없는 오류" 만
    보고 자기가 횟수를 넘긴 줄 모른다.

    그래서 막는 것은 `block=False` 로 표시만 하게 두고, 여기서 JSON 429 로
    답한다.
    """
    if getattr(request, 'limited', False):
        return Response(
            {'error': '시도가 너무 잦습니다. 잠시 후 다시 시도해 주세요.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS)
    return None


def _get_device_or_404(device_id):
    try:
        return AppDevice.objects.get(device_id=device_id)
    except AppDevice.DoesNotExist:
        return None


def device_access_error(request, device):
    """
    이 요청이 이 기기의 자료에 닿아도 되는가. 안 되면 할 말을 돌려준다.

    ── 지금 인증은 사실상 device_id 하나다 ────────────────────────────────

    `login` 이 JWT 를 발급하는데 **이 앱의 어느 뷰도 그것을 검사하지
    않는다** — `request.user` 가 `v1/mobile/views.py` 에 한 번도 나오지
    않았다. 소유자 판정을 전부 URL 의 `device_id` → `AppDevice.user` 로만
    했다. `device_id` 는 경로에 들어 있어 프록시·액세스 로그·Referer 에
    그대로 남는 값인데 그것이 유일한 자격증명이었다.

    게다가 그 값을 **클라이언트가 정한다.** 길이·형식 검사가 없어 일부
    기기가 Android `Build.ID` 를 쓰고 있고(그래서 아래 탐지 코드가 있다),
    그 값은 같은 모델·같은 펌웨어면 모두 같다 — 악의 없이도 이미 서로의
    알림함이 보인다.

    ── 왜 기본값이 꺼짐인가 ──────────────────────────────────────────────

    막으려면 앱이 Authorization 헤더를 보내야 한다. 지금 배포된 앱이 그렇게
    하는지 이 저장소만으로는 알 수 없다. 켜 놓고 안 보내면 **모든 사용자가
    그 자리에서 앱을 못 쓴다.**

    그래서 판정은 여기 두되 기본은 끈다. 앱이 헤더를 싣는 판을 배포한 뒤
    `.env` 에 `MOBILE_REQUIRE_AUTH=True` 를 넣으면 그날부터 막힌다.
    **토큰을 보낸 요청은 지금도 검사한다** — 남의 토큰으로 남의 기기를
    만지는 길은 오늘 닫힌다.
    """
    from django.conf import settings as _settings

    if device is None or device.user_id is None:
        return None                      # 비회원 기기 — 기기 자체가 신원이다

    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        if user.pk != device.user_id:
            # 남의 기기다. 토큰을 새로 받아도 달라지지 않으므로 403.
            return ('이 기기의 자료에 접근할 권한이 없습니다.', 403)
        return None

    if getattr(_settings, 'MOBILE_REQUIRE_AUTH', False):
        # **401 이다, 403 이 아니다.** 자격증명이 아예 없는 것이라
        # 앱이 토큰을 새로 받아 다시 시도할 수 있는 상황이다 —
        # api_client.dart 의 onError 가 401 에서만 _tryRefreshToken 을
        # 부르고, 실패하면 clearTokens 로 로그인 화면으로 돌린다.
        # 403 을 주면 그 흐름을 못 타고 막다른 길이 된다.
        return ('로그인이 필요합니다.', 401)
    return None


def _mark_read_for_web(user, news):
    """
    웹과 같은 기준으로 읽음을 남긴다.

    규칙을 여기에 다시 적지 않는다 — 웹이 이미 세 표(제품·원료·키워드)를
    함께 내리고 배지 캐시까지 지우는 함수를 갖고 있다. 그것을 부른다.
    한쪽만 고쳐지는 일을 막는 유일한 방법이다.
    """
    if user is None or news is None:
        return
    from v1.regulatory.views import _mark_news_read

    _mark_news_read(user, news)


def _rule_quota_error(owner_user, device):
    """
    키워드를 하나 더 **활성**으로 둘 수 있는가. 안 되면 할 말을 돌려준다.

    등록(POST)과 다시 켜기(PATCH) 두 길이 같은 것을 물어야 한다. 예전에는
    POST 에만 있어서, 만들고 끄기를 반복한 뒤 전부 켜면 상한이 사라졌다.
    """
    from django.conf import settings as _settings

    if owner_user:
        limit = _settings.MOBILE_MEMBER_MAX_RULES
        active = AlertRule.objects.filter(user=owner_user, is_active=True).count()
    else:
        limit = _settings.MOBILE_GUEST_MAX_RULES
        active = device.rules.filter(user__isnull=True, is_active=True).count()
    if active >= limit:
        return '최대 %d개까지 등록 가능합니다.' % limit
    return None


# ── 기기 등록 ────────────────────────────────────────────────────────────────

# 기기를 무제한으로 만들 수 있으면 게스트 키워드·보관함 한도가 뜻을 잃는다
# (한도가 기기당이라 기기를 늘리면 늘어난다). 사람이 쓰는 속도를 넉넉히
# 넘는 선에서 끊는다.
@ratelimit(key='ip', rate='30/m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_device(request):
    limited = _rate_limited(request)
    if limited:
        return limited

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

    # **보낸 칸만 고친다.** 앱은 이 엔드포인트를 서로 다른 두 곳에서
    # 부르고 보내는 칸이 겹치지 않는다 — 시작할 때는 platform·app_version,
    # FCM 토큰이 바뀔 때는 fcm_token. 예전에는 defaults 에 세 칸을 다 넣어,
    # 한쪽이 부를 때마다 **다른 쪽이 넣어 둔 값이 지워졌다.**
    #
    #   · iPhone 의 platform 이 DB 에서 영구히 'android' 가 됐다
    #   · app_version 이 늘 빈 문자열이라 어느 기기가 어느 판인지 몰랐다
    #   · 앱을 켤 때마다 fcm_token 이 한 번 NULL 이 됐다 — 그 틈에 발송
    #     배치가 돌면 그 기기는 다음 실행까지 푸시를 못 받는다
    device, created = AppDevice.objects.get_or_create(
        device_id=device_id,
        defaults={
            'platform': request.data.get('platform') or 'android',
            'app_version': request.data.get('app_version') or '',
            'fcm_token': request.data.get('fcm_token') or None,
        },
    )
    if not created:
        changed = []
        for field in ('platform', 'app_version', 'fcm_token'):
            value = request.data.get(field)
            # 빈 값은 "지워 달라" 가 아니라 "이번엔 안 보냈다" 로 읽는다.
            if value in (None, ''):
                continue
            if getattr(device, field) != value:
                setattr(device, field, value)
                changed.append(field)
        # `last_active_at` 은 auto_now 라 **저장할 때만** 올라간다. 바뀐 칸이
        # 없다고 건너뛰면 그 값이 멈춘다 — 푸시 보낼 기기를 고르는 기준이고
        # (push_service 의 order_by('-last_active_at')) 오래 안 쓴 기기를
        # 치우는 기준이기도 하다. 그래서 부를 때마다 올린다.
        device.save(update_fields=changed + ['last_active_at'])
    return Response(AppDeviceSerializer(device).data, status=status.HTTP_200_OK)


# ── 인증 ─────────────────────────────────────────────────────────────────────

# 웹 로그인은 막혀 있는데(user_management.views.login_view 의 20/m) **같은
# 자격증명을 쓰는 앱 로그인은 안 막혀 있었다.** 같은 집 뒷문에 자물쇠를 안
# 단 셈이라, 초당 수백 번 비밀번호를 시도해도 아무것도 세지 않았다.
@ratelimit(key='ip', rate='20/m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    limited = _rate_limited(request)
    if limited:
        return limited

    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    device_id = request.data.get('device_id')

    user = authenticate(request, username=username, password=password)
    if user is None:
        # **비밀번호가 맞는데 인증만 안 된 경우를 갈라 준다.**
        #
        # 인증 전 계정은 is_active=False 라 authenticate 가 None 을 준다.
        # 그것을 "아이디 또는 비밀번호가 올바르지 않습니다" 로 옮기면, 방금
        # 가입한 사람이 비밀번호를 틀린 줄 알고 계속 다시 친다 — 20회/분에
        # 걸리면 "시도가 너무 잦습니다" 로 원인에서 더 멀어진다.
        # 웹은 같은 자리에서 인증 안내를 한다.
        #
        # 비밀번호를 **먼저 확인한다.** 그러지 않으면 아이디만으로
        # 계정 존재 여부를 알 수 있게 된다.
        pending = User.objects.filter(username=username, is_active=False).first()
        if pending is not None and pending.check_password(password):
            return Response(
                {'error': '이메일 인증이 완료되지 않았습니다. '
                          '가입할 때 받은 메일의 링크를 눌러 주세요.'},
                status=status.HTTP_403_FORBIDDEN)
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
            # **한도를 보면서 올린다.**
            #
            # 예전에는 검사가 없었다. 회원 한도를 채운 사람이 로그아웃 →
            # 비회원으로 몇 개 더 추가 → 재로그인 하면 한도를 넘은 상태가
            # 만들어졌고, 활성 규칙 수는 수집 때마다의 전건 매칭 부하로
            # 그대로 이어진다.
            #
            # 넘치는 것은 **지우지 않고 꺼서** 올린다 — 사용자가 만든 것이다.
            # 다른 것을 지우면 화면에서 켤 수 있다.
            member_max = getattr(settings, 'MOBILE_MEMBER_MAX_RULES', 30)
            active_now = AlertRule.objects.filter(
                user=user, is_active=True).count()
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
                    if r.is_active:
                        if active_now >= member_max:
                            r.is_active = False
                        else:
                            active_now += 1
                    r.save(update_fields=['user', 'device', 'is_active'])
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

        # ── 로그아웃은 **이 기기의 연결을 끊는 일**이다 ────────────────────
        #
        # 예전에는 여기서 `AlertRule.objects.filter(user=user_obj)` 로
        # **그 계정의 키워드 전체**를 훑어, 비회원 한도(5개)를 넘는 것을
        # `is_active=False` 로 껐다. 세 가지가 한꺼번에 잘못됐다.
        #
        #   · 범위 — device 조건이 없어, 폰 두 대 쓰는 사람이 한 대에서
        #     로그아웃하면 **다른 폰과 웹의 키워드까지** 꺼졌다
        #   · 되돌릴 길 — 껐다가 다시 켜 주는 코드가 앱에도 웹에도 없다.
        #     로그인해도 비회원 규칙만 승격시킬 뿐이다. 회원이 등록한
        #     키워드 25개가 사실상 사라지고 사용자가 복구할 수 없었다
        #   · 알림 없음 — 목록에는 남아 있고 알림만 안 온다. 원인을
        #     짐작할 수 없다
        #
        # 회원 규칙은 **계정의 것**이지 기기의 것이 아니다. 기기를 떼는
        # 일이 계정 자료를 지울 이유가 없다. 손대지 않는다.
        #
        # 비회원 규칙은 그 기기에 매달려 있으므로 한도가 뜻을 갖는다.
        guest_max = settings.MOBILE_GUEST_MAX_RULES
        excess_ids = list(
            device.rules
            .filter(is_active=True, user__isnull=True)
            .order_by('created_at')
            .values_list('id', flat=True)[guest_max:]
        )
        if excess_ids:
            device.rules.filter(id__in=excess_ids).update(is_active=False)
            logger.info(
                '[LOGOUT] device_id=%s 비회원 초과 키워드 %d개 비활성화',
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

    # 주소창에 무엇이든 올 수 있다. `int('abc')` 가 그대로 올라가면 DRF 가
    # 잡지 않아 **HTML 500** 이 나가고, JSON 을 기대하는 앱은 파싱에서 죽는다.
    # 웹에서 같은 자리를 고쳤는데(`?id=abc`) 앱은 안 봤다.
    try:
        page = max(int(request.query_params.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    # 아주 큰 수는 그대로 OFFSET 으로 들어가 드라이버에서 터진다
    page = min(page, 100000)
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
    return Response(RegulatoryNewsDetailSerializer(news).data)


# ── 알림 규칙 ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def rules_list(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    owner_user = device.user  # 로그인이면 User, 비회원이면 None

    if request.method == 'GET':
        if owner_user:
            rules = AlertRule.objects.filter(user=owner_user).order_by('-created_at')
        else:
            rules = device.rules.filter(user__isnull=True).order_by('-created_at')
        return Response(AlertRuleSerializer(rules, many=True).data)

    # POST — 신규 키워드 등록
    over = _rule_quota_error(owner_user, device)
    if over:
        return Response({'error': over}, status=status.HTTP_400_BAD_REQUEST)

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

        # 웹의 같은 자리는 이미 고쳤다(regulatory.views.alert_rules_api).
        # 삼키면 created=0 이 되고 앱은 그것을 "일치하는 정보가 없습니다" 로
        # 읽는다 — 실패와 0건은 사용자에게 전혀 다른 말이다.
        backfill_result = {'created': 0, 'previews': [], 'log_ids': []}
        backfill_failed = False
        try:
            backfill_result = backfill_alerts_for_rule(rule)
            send_immediate_for_rule(rule, backfill_result.get('log_ids', []))
        except Exception:
            backfill_failed = True
            logger.exception('[키워드 소급] rule=%s 실패', rule.pk)
        data = dict(AlertRuleSerializer(rule).data)
        data['matched_count'] = backfill_result.get('created', 0)
        data['previews'] = backfill_result.get('previews', [])
        # 앱이 "최근 90일 기준입니다"·"100건에서 잘렸습니다"·"소급이 실패했다"
        # 를 말할 수 있어야 한다. 웹은 이미 이 셋을 받는다.
        data['window_days'] = backfill_result.get('window_days')
        data['capped'] = backfill_result.get('capped', False)
        data['backfill_failed'] = backfill_failed
        return Response(data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@permission_classes([AllowAny])
def rule_detail(request, device_id, rule_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    owner_user = device.user

    try:
        if owner_user:
            rule = AlertRule.objects.get(pk=rule_id, user=owner_user)
        else:
            rule = AlertRule.objects.get(pk=rule_id, device=device, user__isnull=True)
    except AlertRule.DoesNotExist:
        return Response({'error': '규칙을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        was_active = rule.is_active
        was_keyword = rule.keyword

        # **다시 켤 때도 한도를 본다.**
        #
        # 한도 검사가 POST 에만 있었다. 30개를 만들고 전부 끈 뒤 또 30개를
        # 만들고… 를 반복한 다음 전부 PATCH 로 켜면 **활성 규칙 수에 상한이
        # 사라진다.** 활성 규칙은 수집 때마다 전건 RapidFuzz 매칭을 도므로
        # 서버 부하로 바로 이어진다.
        turning_on = (not was_active
                      and str(request.data.get('is_active', '')).lower()
                      in ('true', '1'))
        if turning_on:
            over = _rule_quota_error(owner_user, device)
            if over:
                return Response({'error': over}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AlertRuleSerializer(rule, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except IntegrityError:
            # unique_together(device/user, category, keyword, match_type) 인데
            # device·user 가 serializer 필드에 없어 DRF 가 그 검사를 못 붙인다.
            # 같은 키워드로 바꾸면 IntegrityError 가 그대로 올라가 500 이 났다.
            return Response({'error': '이미 등록된 키워드입니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        rule.refresh_from_db()
        # 규칙을 껐으면(is_active=False) 그 키워드로 예약돼 있던 푸시를 거두고,
        # 그 키워드로 걸린 매칭도 미확인에서 내린다. 끄고 나서도 낮 배치에
        # 울리거나 배지에 숫자가 남아 있으면, 껐다는 사실을 못 믿게 된다.
        #
        # **키워드를 바꾼 경우에도 거둔다.** 예전에는 끄기와 지우기에만
        # 걸려 있었다. 문자열만 바꾸면 옛 키워드로 만들어진 예약 푸시가
        # 그대로 남아 낮 배치에 나갔고, 본문에는 **더 이상 없는 키워드**가
        # 찍혔다(trigger_label 은 생성 시점 값이다).
        changed_target = rule.keyword != was_keyword
        if (not rule.is_active) or changed_target:
            _cancel_rule_pushes(owner_user, device, rule)
            _mark_rule_matches_read(rule)

        data = dict(AlertRuleSerializer(rule).data)

        # **키워드를 바꿨으면 소급도 다시 돈다.**
        #
        # POST 는 등록 직후 최근 90일을 훑는데 PATCH 는 거두기만 했다.
        # '우유' 를 '치즈' 로 고치면 최근 90일에 치즈 부적합이 있어도 0건이
        # 되고, 같은 것을 지웠다 새로 등록하면 90일치가 다 걸린다 — 같은
        # 결과를 얻는 두 길이 다르게 동작했다.
        if changed_target and rule.is_active:
            backfill_result = {'created': 0, 'previews': [], 'log_ids': []}
            backfill_failed = False
            try:
                backfill_result = backfill_alerts_for_rule(rule)
                send_immediate_for_rule(rule, backfill_result.get('log_ids', []))
            except Exception:
                backfill_failed = True
                logger.exception('[키워드 소급] 변경 rule=%s 실패', rule.pk)
            data['matched_count'] = backfill_result.get('created', 0)
            data['previews'] = backfill_result.get('previews', [])
            data['window_days'] = backfill_result.get('window_days')
            data['capped'] = backfill_result.get('capped', False)
            data['backfill_failed'] = backfill_failed
        return Response(data)

    # 지우기 전에 예약된 푸시를 거둔다.
    # PushNotificationLog.rule_triggered 는 SET_NULL 이라, 먼저 지우면 로그가
    # "누가 부른 알림인지" 만 잃은 채 발송 대기에 남는다 — 웹의 키워드 삭제와
    # 같은 처리다(regulatory.views.alert_rule_delete_api).
    _cancel_rule_pushes(owner_user, device, rule)
    rule.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


def _cancel_rule_pushes(owner_user, device, rule) -> None:
    """로그인 사용자는 기기 여러 대를 함께, 비회원은 그 기기 하나만 거둔다."""
    from v1.mobile.services.push_service import cancel_pending_logs

    if owner_user:
        cancel_pending_logs(user=owner_user, rule=rule)
    else:
        cancel_pending_logs(device=device, rule=rule)


def _mark_rule_matches_read(rule) -> None:
    """꺼진 키워드로 걸린 매칭은 배지에서 내린다 (지우지는 않는다 — 다시 켤 수 있다)."""
    from django.utils import timezone
    from v1.regulatory.models import NewsKeywordMatch

    NewsKeywordMatch.objects.filter(rule=rule, read_yn=False).update(
        read_yn=True, read_at=timezone.now())


# ── 보관함 ───────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def bookmarks_list(request, device_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    if request.method == 'GET':
        bookmarks = device.bookmarks.select_related('news').all()
        return Response(BookmarkSerializer(bookmarks, many=True).data)

    max_bookmarks = settings.MOBILE_MEMBER_MAX_BOOKMARKS if device.user else settings.MOBILE_GUEST_MAX_BOOKMARKS
    if device.bookmarks.count() >= max_bookmarks:
        return Response({'error': f'최대 {max_bookmarks}개까지 저장 가능합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    news_id = request.data.get('news_id')
    try:
        news_id = int(news_id)
    except (TypeError, ValueError):
        return Response({'error': '존재하지 않는 뉴스입니다.'},
                        status=status.HTTP_404_NOT_FOUND)
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

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

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

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

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
        # 같은 목록 안에서 두 표의 pk 가 겹치지 않게 민다. 되돌리는 것은
        # notification_read / notification_delete 가 한다.
        for item in insp_data:
            item['id'] = item['id'] + INSPECTION_ID_OFFSET

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

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    noti_type, noti_id = _split_notification_id(
        noti_id, request.query_params.get('type', 'log'))

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
        # **읽음은 사람 단위다.** 웹 배지는 NewsKeywordMatch 를 세는데
        # 예전에는 기기의 로그만 바꿨다 — 앱에서 다 읽어도 웹 숫자가 그대로였고
        # 반대도 마찬가지였다. 웹과 같은 함수를 부른다(캐시도 그쪽이 지운다).
        _mark_read_for_web(device.user, log.news)

    return Response({'detail': 'ok'})


@api_view(['DELETE'])
@permission_classes([AllowAny])
def notification_delete(request, device_id, noti_id):
    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    noti_type, noti_id = _split_notification_id(
        noti_id, request.query_params.get('type', 'log'))

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

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])
    # 발송 완료된 항목만 읽음 처리 (sent_at IS NOT NULL)
    unread = list(device.notifications
                  .filter(is_read=False, sent_at__isnull=False)
                  .values_list('news_id', flat=True))
    device.notifications.filter(is_read=False, sent_at__isnull=False).update(is_read=True)
    if device.user_id and unread:
        # 웹 배지와 같은 표를 함께 내린다 — 위 notification_read 의 주석 참고
        from v1.regulatory.models import RegulatoryNews

        for news in RegulatoryNews.objects.filter(pk__in=set(unread)):
            _mark_read_for_web(device.user, news)
    if device.user_id:
        InspectionMatch.objects.filter(
            user_id=device.user_id, read_yn=False,
            notified_at__isnull=False,
        ).update(read_yn=True)
    return Response({'detail': 'ok'})


# ── 토큰 재발급 ───────────────────────────────────────────────────────────────

@ratelimit(key='ip', rate='60/m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """
    앱의 인터셉터는 **401 을 받으면 무조건** 이 경로를 친다
    (`api_client.dart:80-96`). 그런데 서버에 이 라우트가 없었다.

    없으면 Django 가 HTML 404 를 주고, 앱의 `catch (_)` 가 그것을 잡아
    `clearTokens()` 로 **리프레시 토큰까지 지운다.** 사용자는 조용히
    로그아웃되고 화면은 여전히 로그인한 것처럼 보인다. 액세스 토큰 수명이
    7일이므로 8일째 앱을 켜는 모든 사용자가 이 길을 탔다.

    그리고 이것 때문에 `MOBILE_REQUIRE_AUTH` 를 켤 수 없었다 — 켜는 순간
    토큰이 만료된 사용자가 전부 여기로 와서 튕긴다.

    실패는 **401** 로 답한다. 앱이 그때 토큰을 지우고 다시 로그인시키는 것이
    맞다. 400/404 면 앱이 그 판단을 못 한다.
    """
    limited = _rate_limited(request)
    if limited:
        return limited

    raw = (request.data or {}).get('refresh')
    if not raw:
        return Response({'error': '리프레시 토큰이 필요합니다.'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        refresh = RefreshToken(raw)
        access = str(refresh.access_token)
    except (TokenError, KeyError, TypeError, ValueError):
        return Response({'error': '다시 로그인해 주세요.'},
                        status=status.HTTP_401_UNAUTHORIZED)
    return Response({'access': access})


# ── 회원 탈퇴 ─────────────────────────────────────────────────────────────────

@ratelimit(key='ip', rate='10/m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([AllowAny])
def account_delete(request):
    """
    앱의 [회원 탈퇴] 가 부르는 경로. 이것도 서버에 없어서 **버튼이 늘
    "알 수 없는 오류" 로 끝났다.**

    빠뜨려도 되는 기능이 아니다 — 개인정보처리방침이 "[내 정보/설정 →
    회원 탈퇴] 기능을 통해 직접 계정 삭제 및 정보 파기를 요청할 수
    있습니다" 라고 적어 두었고, "기기 식별 정보는 즉시 파기됩니다" 라고
    약속했다. 앱스토어 심사 필수 항목이기도 하다.

    **여기서 하는 일**

    · 비밀번호를 다시 확인한다(앱이 받아서 보낸다)
    · 그 계정의 **기기 정보를 그 자리에서 지운다** — AppDevice 를 지우면
      보관함·알림 내역이 함께 지워진다(FK CASCADE). 알림 키워드도 지운다
    · 계정을 비활성으로 돌린다 — 웹·앱 어느 쪽으로도 다시 못 들어온다

    **두 단계로 나눈다.** 그 계정이 만든 표시사항·제품·원료는 이 자리에서
    지우지 않는다 — 지금은 누구인지 알 수 없는 껍데기만 남고, 정해진 기간이
    지나면 `purge_withdrawn` 이 그것까지 완전히 지운다. 기간과 그 법적
    근거는 `v1/common/withdrawal.py` 머리말에 적었다(기본 5일).
    """
    limited = _rate_limited(request)
    if limited:
        return limited

    device_id = (request.data or {}).get('device_id')
    password = (request.data or {}).get('password') or ''

    device = _get_device_or_404(device_id) if device_id else None
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'},
                        status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    if not device.user_id:
        return Response({'error': '로그인한 계정이 없습니다.'},
                        status=status.HTTP_403_FORBIDDEN)

    user = device.user
    if not user.check_password(password):
        return Response({'error': '비밀번호가 맞지 않습니다.'},
                        status=status.HTTP_400_BAD_REQUEST)

    withdrawal.withdraw(user)
    logger.info('[ACCOUNT_DELETE] user_id=%s 앱에서 탈퇴 처리 (파기 예정 %d일 뒤)',
                user.pk, withdrawal.purge_days())
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

    def _ver(text):
        """
        '1.0.11' · '1.2' · '1.0.11+17' 을 모두 (1, 0, 11) 꼴로 읽는다.

        예전에는 `tuple(int(x) for x in s.split('.')[:3])` 였다. 두 가지가
        걸렸다.
          · 자리 수가 다르면 오탐 — `(1,2) < (1,2,0)` 은 True 다. 최소
            버전이 1.2.0 인데 1.2 로 보고하면 최신인데도 강제 업데이트가 뜬다
          · Flutter 의 `x.y.z+build` 표기가 오면 int() 가 던지고, 그것을
            except 가 삼켜 **강제 업데이트가 아무에게도 안 걸린다**
            (지금 앱은 info.version 만 보내 3자리라 안 걸리지만, 관리자가
             min_version 에 그 꼴을 넣으면 그 순간 조용히 무력화된다)
        세 자리로 채워 견준다.
        """
        head = str(text or '').split('+')[0].split('-')[0]
        parts = []
        for chunk in head.split('.')[:3]:
            digits = ''.join(c for c in chunk if c.isdigit())
            parts.append(int(digits) if digits else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    force_update = _ver(current) < _ver(v.min_version)

    return Response({
        'force_update': force_update,
        'latest_version': v.latest_version,
        'store_url': v.store_url,
        'message': v.force_message or '',
    })


# ── 알림 받지 않기(뮤트) — 회원 전용 ──────────────────────────────────────────
#
# 웹의 /regulatory/api/alert-mutes/ 와 같은 일을 한다. 판정·정리·푸시 거두기는
# 모두 regulatory.services.mute 한 곳에 있으므로, 여기서는 기기→사용자를
# 풀어 주고 그 서비스를 부르기만 한다. 규칙이 두 벌이 되면 웹에서 끈 것과
# 앱에서 끈 것이 서로 다르게 동작한다.
#
# AlertMute 는 user 에만 붙는다(AlertRule 과 달리 device 갈래가 없다).
# 그래서 이 API 는 로그인한 기기만 받는다 — 비회원은 403.

def _mute_user_or_error(device):
    """뮤트는 사용자에 붙는다. 비회원 기기면 (None, 403 응답)."""
    if device.user_id is None:
        return None, Response(
            {'error': '로그인이 필요합니다. 받지 않기는 계정에 저장됩니다.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return device.user, None


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def alert_mutes_list(request, device_id):
    """
    GET  /mobile/devices/<device_id>/alert-mutes/  — 내 받지 않기 목록
    POST /mobile/devices/<device_id>/alert-mutes/  — 등록 + 기존 알림 정리
    Body(POST): {"scope": "keyword|ingredient|company", "value": "...", "memo": ""}
    """
    from django.core.cache import cache

    from v1.regulatory.models import AlertMute, normalize_mute_value
    from v1.regulatory.services import mute as mute_service

    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    user, denied = _mute_user_or_error(device)
    if denied:
        return denied

    if request.method == 'GET':
        return Response({'mutes': [
            mute_service.mute_payload(m)
            for m in AlertMute.objects.filter(user=user).order_by('-created_at')
        ]})

    scope = (request.data.get('scope') or '').strip()
    value = (request.data.get('value') or '').strip()
    memo  = (request.data.get('memo')  or '').strip()[:200]

    if scope not in mute_service.VALID_SCOPES:
        return Response({'error': '유효하지 않은 제외 기준'}, status=status.HTTP_400_BAD_REQUEST)
    if not value:
        return Response({'error': '끌 값이 비어 있습니다'}, status=status.HTTP_400_BAD_REQUEST)
    if len(value) > 200:
        return Response({'error': '200자 이내로 입력해주세요'}, status=status.HTTP_400_BAD_REQUEST)

    # 직접 등록한 알림 키워드와 정면으로 부딪히면 어느 쪽이 이겼는지 화면에서
    # 설명할 수 없다. 끄는 것이 아니라 그 키워드를 지우도록 되돌려 보낸다
    # (웹 regulatory.views.alert_mutes_api 와 같은 처리).
    conflict = [
        r for r in AlertRule.objects.filter(user=user, is_active=True)
        if normalize_mute_value(r.keyword) == normalize_mute_value(value)
    ]
    if conflict:
        return Response({
            'error': f'"{value}" 은(는) 직접 등록한 알림 키워드입니다. '
                     f'알림 설정에서 키워드를 삭제해 주세요.',
            'conflict_rule_ids': [r.id for r in conflict],
        }, status=status.HTTP_409_CONFLICT)

    try:
        result = mute_service.apply_mute(user, scope, value, memo)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    cache.delete(f'regulatory_alert_count_{user.id}')
    return Response(
        {
            'created':        result['created'],
            'hidden':         result['hidden'],
            'push_cancelled': result['push_cancelled'],
            'mute':           mute_service.mute_payload(result['mute']),
        },
        status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@permission_classes([AllowAny])
def alert_mute_detail(request, device_id, mute_id):
    """
    DELETE /mobile/devices/<device_id>/alert-mutes/<mute_id>/ — 해제

    앞으로 오는 것부터 다시 받는다. 이미 치워 둔 지난 알림은 되살리지 않는다
    (오탐지 처리와 같은 성질 — 되살리면 정리한 목록이 갑자기 불어난다).
    """
    from django.core.cache import cache

    from v1.regulatory.models import AlertMute

    device = _get_device_or_404(device_id)
    if device is None:
        return Response({'error': '기기를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    denied = device_access_error(request, device)
    if denied:
        return Response({'error': denied[0]}, status=denied[1])

    user, denied = _mute_user_or_error(device)
    if denied:
        return denied

    try:
        mute = AlertMute.objects.get(pk=mute_id, user=user)
    except AlertMute.DoesNotExist:
        return Response({'error': '규칙을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

    mute.delete()
    cache.delete(f'regulatory_alert_count_{user.id}')
    return Response(status=status.HTTP_204_NO_CONTENT)
