# -*- coding: utf-8 -*-
"""
오래 쓰지 않은 **비회원 기기**와 거기 매달린 것을 치운다.

    python manage.py purge_stale_devices             # 무엇이 지워질지만
    python manage.py purge_stale_devices --apply
    python manage.py purge_stale_devices --days 180 --apply

**기본이 미리보기다**(purge_guests·purge_withdrawn 과 같은 규약).

왜 필요한가
──────────
개인정보처리방침이 이렇게 적어 두었다 —

    "비회원은 모바일 앱을 삭제하는 즉시 기기 연동 데이터가 파기됩니다."

그런데 **서버는 앱이 지워진 것을 알 수 없다.** 앱 삭제는 서버에 아무것도
보내지 않으므로 `AppDevice` 행과 거기 매달린 보관함·알림 내역·알림 키워드가
그대로 남는다. 지우는 코드가 저장소 어디에도 없었다 — 방침이 약속한 파기가
한 번도 일어나지 않았다.

알 수 있는 것은 "언제 마지막으로 이 기기가 서버를 불렀는가"(`last_active_at`)
뿐이다. 그래서 **오래 잠잠한 비회원 기기**를 치운다. 기본 90일로 둔다 —
계절마다 한 번 열어 보는 사람을 지우지 않으면서, 지워진 앱을 무한정 들고
있지도 않을 만한 자리다.

**회원 기기는 건드리지 않는다.** 그쪽은 계정에 매달려 있고, 탈퇴하면
`withdraw()` 가 그 자리에서 지운다.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

DEFAULT_DAYS = 90


class Command(BaseCommand):
    help = '오래 쓰지 않은 비회원 기기를 치운다 (기본은 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=DEFAULT_DAYS,
                            help='이만큼 잠잠한 것을 치운다 (기본 %d)' % DEFAULT_DAYS)
        parser.add_argument('--apply', action='store_true',
                            help='실제로 지운다. 없으면 보여 주기만 한다')

    def handle(self, *args, **opts):
        from v1.mobile.models import AlertRule, AppDevice, Bookmark, PushNotificationLog

        w = self.stdout.write
        days = opts['days']
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = AppDevice.objects.filter(user__isnull=True, last_active_at__lt=cutoff)
        ids = list(qs.values_list('id', flat=True))

        w('─' * 62)
        w('잠잠한 비회원 기기 — %d 일 넘게 부른 적 없는 것' % days)
        w('')
        w('   기기      %6d' % len(ids))
        if not ids:
            w('')
            w('   치울 것이 없다.')
            w('─' * 62)
            return

        w('   보관함    %6d  ← 기기와 함께 사라진다'
          % Bookmark.objects.filter(device_id__in=ids).count())
        w('   알림 내역 %6d  ← 기기와 함께 사라진다'
          % PushNotificationLog.objects.filter(device_id__in=ids).count())
        w('   알림 키워드 %4d  ← 기기와 함께 사라진다'
          % AlertRule.objects.filter(device_id__in=ids, user__isnull=True).count())
        w('')
        w('   회원 기기는 건드리지 않는다 — 탈퇴할 때 함께 지운다.')

        if not opts['apply']:
            w('')
            w('   보여 주기만 했다. 실제로 지우려면 --apply 를 붙인다.')
            w('─' * 62)
            return

        deleted, _detail = qs.delete()
        w('')
        w('   지웠다. 줄 %d 개 (매달린 것 포함)' % deleted)
        w('─' * 62)
