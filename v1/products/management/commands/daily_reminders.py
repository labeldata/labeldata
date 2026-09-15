# -*- coding: utf-8 -*-
"""
하루 한 번 나가는 알림을 **한 줄로** 묶는다.

    python manage.py daily_reminders            # 무엇이 나갈지만 보여 준다
    python manage.py daily_reminders --send     # 실제로 보낸다

왜 묶었나. PythonAnywhere 의 예약 작업(Tasks)에는 **개수 상한**이 있고 이미
꽉 찼다. 새 알림을 하나 붙일 때마다 자리를 하나 달라고 해야 하는데, 그
자리가 없다. 그래서 예약에는 이 커맨드 하나만 걸고, 앞으로 늘어나는 것은
여기 목록에 더한다 — **예약을 건드리지 않고 알림을 늘릴 수 있다.**

하나가 실패해도 나머지는 보낸다. 묶었다는 이유로 같이 죽으면 묶은 것이
손해다. 무엇이 실패했는지는 마지막 줄에 모아서 적는다.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

# 여기에 더하면 예약은 그대로 두고 알림만 늘어난다.
REMINDERS = [
    ('alert_expiring_documents', '문서 유효기간 만료 알림'),
    ('remind_doc_requests', '자료 요청 기한 독촉'),
]


class Command(BaseCommand):
    help = '하루 한 번 나가는 알림을 모아서 돌린다.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true',
                            help='실제로 발송한다 (없으면 미리보기)')

    def handle(self, *args, **options):
        send = options['send']
        failed = []

        for name, label in REMINDERS:
            self.stdout.write('── %s (%s)' % (label, name))
            try:
                call_command(name, send=send, stdout=self.stdout,
                             stderr=self.stderr)
            except Exception as exc:
                # 여기서 멈추면 뒤에 선 알림이 통째로 못 나간다.
                failed.append((name, exc))
                self.stderr.write(self.style.ERROR(
                    '  %s 가 실패했다: %s' % (name, exc)))

        if failed:
            self.stderr.write(self.style.ERROR(
                '%d개 실패: %s' % (len(failed), ', '.join(n for n, _ in failed))))
        else:
            self.stdout.write(self.style.SUCCESS(
                '%d개 모두 돌았다.' % len(REMINDERS)))
