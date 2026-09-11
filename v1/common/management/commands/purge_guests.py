# -*- coding: utf-8 -*-
"""
지난 게스트 계정과 그가 만든 것을 치운다.

    python manage.py purge_guests            # 무엇이 지워질지만 보여 준다
    python manage.py purge_guests --apply    # 실제로 지운다
    python manage.py purge_guests --hours 48 --apply

**기본이 미리보기다.** 계정을 지우는 일은 되돌릴 수 없으므로, 손이 한 번 더
가게 둔다 — `--apply` 를 적는 번거로움이 그 목적이다.

왜 치우는가
──────────
방문마다 새 계정을 내주므로(common/guest.py) 그냥 두면 User 와 그가 만든
제품·원료가 끝없이 쌓인다. 둘러보기는 한 자리에서 끝나는 일이라 하루면 넉넉하다.

무엇이 함께 지워지는가
────────────────────
MyLabel·MyIngredient 는 user 에 `on_delete=CASCADE` 로 매달려 있어 계정과 함께
사라진다. 그래서 미리보기에서 **그 수를 먼저 보여 준다** — 숫자를 보고 놀랄 일이
있으면 지우기 전에 멈출 수 있다.

옛 공용 계정(guest@labeasylabel.com)은 건드리지 않는다. 그 계정으로 들어와 있는
사람이 있을 수 있고, 지우면 그 사람이 만든 것이 함께 사라진다.
"""
from django.core.management.base import BaseCommand

from v1.common.guest import GUEST_TTL_HOURS, LEGACY_GUEST_EMAIL, stale_guests


class Command(BaseCommand):
    help = '지난 게스트 계정을 치운다 (기본은 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=GUEST_TTL_HOURS,
                            help='이만큼 지난 것을 치운다 (기본 %d)' % GUEST_TTL_HOURS)
        parser.add_argument('--apply', action='store_true',
                            help='실제로 지운다. 없으면 보여 주기만 한다')

    def handle(self, *args, **opts):
        from v1.label.models import MyIngredient, MyLabel

        w = self.stdout.write
        hours = opts['hours']
        qs = stale_guests(hours)
        ids = list(qs.values_list('id', flat=True))

        w('─' * 62)
        w('지난 게스트 계정 — %d 시간 넘은 것' % hours)
        w('')
        w('   계정      %6d' % len(ids))
        if not ids:
            w('')
            w('   치울 것이 없다.')
            w('─' * 62)
            return

        labels = MyLabel.objects.filter(user_id__in=ids).count()
        ings = MyIngredient.objects.filter(user_id__in=ids).count()
        w('   제품      %6d  ← 계정과 함께 사라진다' % labels)
        w('   원료      %6d  ← 계정과 함께 사라진다' % ings)
        w('')
        w('   옛 공용 계정(%s)은 건드리지 않는다.' % LEGACY_GUEST_EMAIL)

        if not opts['apply']:
            w('')
            w('   보여 주기만 했다. 실제로 지우려면 --apply 를 붙인다.')
            w('─' * 62)
            return

        deleted, _detail = qs.delete()
        w('')
        w('   지웠다. 줄 %d 개 (매달린 것 포함)' % deleted)
        w('─' * 62)
