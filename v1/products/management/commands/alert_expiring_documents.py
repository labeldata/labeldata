# -*- coding: utf-8 -*-
"""
유효기간이 끝나가는 문서를 제품 주인에게 알린다.

    python manage.py alert_expiring_documents            # 무엇이 나갈지만 보여 준다
    python manage.py alert_expiring_documents --send     # 실제로 보낸다

「알림 설정」 은 지금까지 **적히기만 했다.** 문서 타입마다 "30일 전" 이라고
화면에 적어 두었고(문서 타입 관리의 「알림 설정」 열), 그 창을 판정하는
`ProductDocument.needs_alert()` 도 있었는데 **부르는 데가 한 곳도 없었다.**
사용자는 알림이 온다고 읽고 있었고 한 통도 나간 적이 없다. 이 커맨드가
그 함수의 첫 호출자다.

**창 안이라고 매일 보내지 않는다.** 설정이 30일이면 30번 보내는 꼴이고,
그러면 사람은 읽지 않는 법을 익힌다. 말하는 날을 정해 둔다 — 설정한 날,
그리고 7·3·1·0 일 전. 설정이 그보다 짧으면 그 아래만 쓴다.

하루에 두 번 돌아도 같은 제품에 두 번 가지 않는다. 그날 만든 인앱 알림이
있으면 건너뛴다 — 보낸 날짜를 적을 칸을 새로 만들지 않은 까닭은, 운영에서
`migrate` 가 아직 돌지 않기 때문이다.

제품 하나에 문서 여러 건이 걸리면 **메일 한 통에 묶는다.** 받는 사람은
제품 주인이다(공유받은 사람은 갱신할 권한이 없을 수 있다).
"""
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from v1.products.models import ProductDocument, ProductNotification

STATUS_CODE = 'DOC_EXPIRY'


def sent_today(label_id, recipient, today):
    """
    오늘 이미 말했나.

    `created_at__date=today` 로 쓰면 안 된다. USE_TZ 가 켜져 있어 Django 가
    DB 에게 `CONVERT_TZ` 로 시간대를 바꿔 달라고 하는데, **MySQL 에 시간대
    표가 올라가 있지 않으면 그 함수가 NULL 을 돌려준다.** 그러면 조건이 아무
    행에도 안 맞아 "오늘 보낸 적 없다" 가 되고, 예약이 하루 두 번이면 같은
    메일이 두 번 간다. SQLite(시험)는 파이썬에서 바꾸므로 시험만으로는 안
    드러난다. 하루의 경계를 여기서 계산해 범위로 묻는다.
    """
    start = timezone.make_aware(datetime.combine(today, time.min))
    return ProductNotification.objects.filter(
        label_id=label_id, recipient=recipient, status_code=STATUS_CODE,
        created_at__gte=start, created_at__lt=start + timedelta(days=1),
    ).exists()


def speak_days(alert_days):
    """오늘이 말할 날인지 가리는 날짜들."""
    return sorted({d for d in (alert_days, 7, 3, 1, 0) if 0 <= d <= alert_days})


def when_text(days_left):
    if days_left == 0:
        return '오늘까지입니다'
    return '%d일 남았습니다' % days_left


class Command(BaseCommand):
    help = '유효기간이 끝나가는 문서를 제품 주인에게 알린다.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true',
                            help='실제로 발송한다 (없으면 미리보기)')

    def handle(self, *args, **options):
        send = options['send']
        today = timezone.localdate()

        docs = (ProductDocument.objects
                .filter(active_yn=True,
                        expiry_date__isnull=False,
                        label__delete_YN='N')
                .select_related('label', 'label__user_id', 'document_type')
                .order_by('expiry_date'))

        # 제품별로 묶는다. 문서 세 건이 같은 날 걸리면 메일은 한 통이다.
        buckets = {}
        for doc in docs:
            if not doc.needs_alert():
                continue
            days_left = doc.days_until_expiry()
            if days_left not in speak_days(doc.document_type.expiry_alert_days):
                continue
            buckets.setdefault(doc.label_id, []).append(doc)

        self.stdout.write('오늘 말할 제품 %d건' % len(buckets))

        sent = skipped = 0
        for label_id, group in buckets.items():
            label = group[0].label
            owner = label.user_id
            if sent_today(label_id, owner, today):
                skipped += 1
                continue

            product = label.my_label_name or '제품'
            soonest = min(d.days_until_expiry() for d in group)
            message = '「%s」 문서 %d건의 유효기간이 %s' % (
                product, len(group), when_text(soonest))

            if not send:
                self.stdout.write('  [미리보기] %s → %s' % (
                    owner.email or '(메일 없음)', message))
                continue

            ProductNotification.objects.create(
                label=label, recipient=owner,
                message=message, status_code=STATUS_CODE,
            )
            if owner.email:
                self._mail(owner.email, product, group)
            sent += 1

        if send:
            self.stdout.write(self.style.SUCCESS(
                '%d건 알림, %d건 건너뜀(오늘 이미 보냄)' % (sent, skipped)))
        else:
            self.stdout.write('미리보기입니다. 실제로 보내려면 --send 를 붙이세요.')

    def _mail(self, to_email, product, group):
        from django.conf import settings
        from django.urls import reverse
        from v1.products.views import _render_email, _send_email_safe

        site = getattr(settings, 'SITE_URL', 'https://www.ezlabeling.com')
        subject = '[EzLabeling] 문서 유효기간 안내 — %s' % product
        ctx = {
            'subject': subject,
            'product_name': product,
            'detail_url': '%s%s' % (site, reverse('products:expiring_documents')),
            'documents': [{
                'type_name': d.document_type.type_name,
                'expiry_date': d.expiry_date,
                'days_left': d.days_until_expiry(),
                'when': when_text(d.days_until_expiry()),
            } for d in group],
        }
        txt, html = _render_email('emails/document_expiry_alert.html', ctx)
        _send_email_safe(subject=subject, body=txt,
                         to_email=to_email, html_body=html)
