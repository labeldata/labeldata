"""
기한이 다가오거나 지난 자료 요청을 챙긴다.

`due_date` 는 지금까지 **적히기만 했다.** 협력사 링크 만료 판정과 연락처 화면의
빨간 글씨, 두 군데에서만 쓰였다. 기한 하루 전에 알리는 것도, 지난 뒤 다시
말해 주는 것도 없어서 "그거 아직 안 왔어요" 를 사람이 기억해서 챙기고 있었다.
같이 일할 때 가장 자주 하는 말이 그것이다.

무엇을 보내나
  - 기한 임박: 받는 사람에게 "N일 남았습니다"
  - 기한 초과: 받는 사람에게 "N일 지났습니다" + 요청한 사람에게 "아직 안 왔습니다"

**하루에 한 번만 보낸다.** 같은 요청으로 매일 같은 메일이 가면 사람은 읽지 않는
법을 익힌다. 보낸 날짜를 요청에 적어 두고 그날 것은 건너뛴다.

이미 낸 것(SUBMITTED)·거절·취소는 보지 않는다. 챙길 것은 아직 안 온 것뿐이다.

기본은 미리보기다. 실제로 보내려면 --send 를 붙여야 한다.

    python manage.py remind_doc_requests                 # 미리보기
    python manage.py remind_doc_requests --before 3      # 3일 전부터 알림
    python manage.py remind_doc_requests --send
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from v1.products.models import DocumentRequest


class Command(BaseCommand):
    help = '기한이 임박하거나 지난 자료 요청에 알림을 보낸다.'

    def add_arguments(self, parser):
        parser.add_argument('--before', type=int, default=1,
                            help='기한 며칠 전부터 알릴지 (기본 1)')
        parser.add_argument('--send', action='store_true',
                            help='실제로 발송한다 (없으면 미리보기)')

    def handle(self, *args, **options):
        before = options['before']
        send = options['send']
        today = timezone.localdate()

        pending = (DocumentRequest.objects
                   .filter(status__in=DocumentRequest.STATUS_OUTSTANDING,
                           due_date__isnull=False)
                   .select_related('requester', 'linked_label')
                   .order_by('due_date'))

        due_soon, overdue = [], []
        for dr in pending:
            left = (dr.due_date - today).days
            if left < 0:
                overdue.append(dr)
            elif left <= before:
                due_soon.append(dr)

        self.stdout.write('기한 임박 %d건, 기한 초과 %d건' % (len(due_soon), len(overdue)))

        sent = skipped = 0
        for dr in due_soon + overdue:
            if dr.reminded_on == today:
                skipped += 1
                continue
            left = (dr.due_date - today).days
            if not send:
                self.stdout.write('  [미리보기] %s → %s (%s)'
                                  % (dr.recipient_email, dr.due_date,
                                     '%d일 지남' % -left if left < 0 else '%d일 남음' % left))
                continue
            if self._notify(dr, left):
                sent += 1

        if send:
            DocumentRequest.objects.filter(
                request_id__in=[d.request_id for d in due_soon + overdue]
            ).exclude(reminded_on=today).update(reminded_on=today)
            self.stdout.write(self.style.SUCCESS(
                '%d건 발송, %d건 건너뜀(오늘 이미 보냄)' % (sent, skipped)))
        else:
            self.stdout.write('미리보기입니다. 실제로 보내려면 --send 를 붙이세요.')

    def _notify(self, dr, days_left):
        """받는 사람과 (기한이 지났으면) 요청한 사람에게 알린다."""
        from django.conf import settings
        from v1.products.views import _render_email, _send_email_safe

        site = getattr(settings, 'SITE_URL', 'https://labeldata.pythonanywhere.com')
        product = (dr.linked_label.my_label_name if dr.linked_label
                   else dr.target_product_name) or '제품'
        overdue = days_left < 0
        when = '%d일 지났습니다' % -days_left if overdue else (
            '오늘까지입니다' if days_left == 0 else '%d일 남았습니다' % days_left)

        subject = '[EzLabeling] 자료 제출 기한 %s — %s' % (
            '초과' if overdue else '안내', product)
        ctx = {
            'subject': subject, 'product_name': product,
            'due_date': dr.due_date, 'when': when, 'overdue': overdue,
            'upload_url': '%s/vendor/upload/%s/' % (site, dr.upload_token),
            'requester_name': dr.requester.get_full_name() or dr.requester.username,
        }
        txt, html = _render_email('emails/doc_request_reminder.html', ctx)
        _send_email_safe(subject=subject, body=txt,
                         to_email=dr.recipient_email, html_body=html)

        if overdue and dr.requester.email:
            r_subject = '[EzLabeling] 자료가 아직 오지 않았습니다 — %s' % product
            r_ctx = dict(ctx, subject=r_subject, to_requester=True,
                         recipient_email=dr.recipient_email)
            r_txt, r_html = _render_email('emails/doc_request_reminder.html', r_ctx)
            _send_email_safe(subject=r_subject, body=r_txt,
                             to_email=dr.requester.email, html_body=r_html)
        return True
