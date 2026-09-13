# -*- coding: utf-8 -*-
"""
탈퇴한 지 기간이 지난 계정과 그가 만든 것을 완전히 지운다.

    python manage.py purge_withdrawn            # 무엇이 지워질지만 보여 준다
    python manage.py purge_withdrawn --apply    # 실제로 지운다
    python manage.py purge_withdrawn --days 30 --apply

**기본이 미리보기다.** 되돌릴 수 없는 일이므로 손이 한 번 더 가게 둔다 —
`--apply` 를 적는 번거로움이 그 목적이다(purge_guests 와 같은 규약).

탈퇴하는 **그 순간에** 개인을 가리키는 것은 이미 지워져 있다
(common/withdrawal.py 의 withdraw). 여기서 지우는 것은 그 뒤에 남은
익명 껍데기와, 그 계정에 매달려 있던 표시사항·제품·원료다.

기간의 근거는 「개인정보 보호법」 시행령 제16조 제1항(지체 없이 = 정당한
사유가 없으면 5일 이내)이다. 자세한 것은 common/withdrawal.py 의 머리말.
"""
from django.core.management.base import BaseCommand

from v1.common.withdrawal import purge_days, stale_withdrawn


class Command(BaseCommand):
    help = '탈퇴 후 기간이 지난 계정을 완전히 지운다 (기본은 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=None,
            help='이만큼 지난 것을 지운다 (기본 %d — settings.ACCOUNT_PURGE_DAYS)'
                 % purge_days())
        parser.add_argument('--apply', action='store_true',
                            help='실제로 지운다. 없으면 보여 주기만 한다')

    def handle(self, *args, **opts):
        from v1.label.models import MyIngredient, MyLabel

        w = self.stdout.write
        days = opts['days'] if opts['days'] is not None else purge_days()
        qs = stale_withdrawn(days)
        ids = list(qs.values_list('id', flat=True))

        w('─' * 62)
        w('탈퇴 계정 파기 — 탈퇴 후 %d 일 지난 것' % days)
        w('')
        w('   계정      %6d' % len(ids))
        if not ids:
            w('')
            w('   지울 것이 없다.')
            w('─' * 62)
            return

        labels = MyLabel.objects.filter(user_id__in=ids).count()
        ings = MyIngredient.objects.filter(user_id__in=ids).count()
        w('   제품      %6d  ← 계정과 함께 사라진다' % labels)
        w('   원료      %6d  ← 계정과 함께 사라진다' % ings)
        w('')
        w('   개인 식별 정보는 탈퇴한 그 순간에 이미 지웠다.')
        w('   여기서 지우는 것은 남은 익명 껍데기와 그가 만든 것이다.')

        if not opts['apply']:
            w('')
            w('   보여 주기만 했다. 실제로 지우려면 --apply 를 붙인다.')
            w('─' * 62)
            return

        deleted, _detail = qs.delete()
        w('')
        w('   지웠다. 줄 %d 개 (매달린 것 포함)' % deleted)
        w('─' * 62)
