"""
Management Command: send_pending_alerts

수집 시점에 쌓인 미발송 알림을 사용자별·유형별로 묶어 FCM 일괄 발송한다.

━━━ 발송 대상 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PushNotificationLog.sent_at IS NULL
    → 부적합·처분 키워드/제품/원료 매칭 알림
  InspectionMatch.alert_phase=PHASE_COLLECTION & fcm_sent_at IS NULL
    → 수거검사 신규 접수 알림

  ※ 수거검사 판정변동(PHASE_JUDGMENT)은 수집 즉시 발송하므로 여기서 처리 안 함

━━━ PA 스케줄러 등록 (UTC 기준) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  01:00 UTC (10:00 KST) — 새벽 수집분 전체 발송
  05:00 UTC (14:00 KST) — 오전 이후 추가분 발송
  08:00 UTC (17:00 KST) — 퇴근 전 최종 발송

사용법:
  python manage.py send_pending_alerts
  python manage.py send_pending_alerts --dry-run   # 실제 발송 없이 대상 건수만 출력
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '미발송 알림을 사용자별로 묶어 FCM 일괄 발송 (일 3회: 10시·14시·17시 KST)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='실제 발송 없이 대상 건수만 출력',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now_kst = timezone.now().astimezone(
            __import__('zoneinfo').ZoneInfo('Asia/Seoul')
        )
        self.stdout.write(
            f'[{now_kst:%Y-%m-%d %H:%M KST}] send_pending_alerts 시작'
            + (' (dry-run)' if dry_run else '')
        )

        # ── 1. 부적합·처분 배치 알림 ──────────────────────────────────────────
        from v1.mobile.models import PushNotificationLog

        pending_reg = PushNotificationLog.objects.filter(sent_at__isnull=True)
        reg_count = pending_reg.count()
        self.stdout.write(f'  부적합·처분 미발송: {reg_count}건')

        if reg_count == 0:
            reg_result = {'users': 0, 'fcm_sent': 0, 'logs_marked': 0}
        elif dry_run:
            # dry-run: 기기별·유형별 집계만 출력
            self._print_regulatory_preview(pending_reg)
            reg_result = {'users': 0, 'fcm_sent': 0, 'logs_marked': 0}
        else:
            from v1.mobile.services.push_service import send_regulatory_batch_alerts
            reg_result = send_regulatory_batch_alerts()
            self.stdout.write(self.style.SUCCESS(
                f'  → 부적합·처분 FCM {reg_result["fcm_sent"]}건 발송 '
                f'/ 로그 {reg_result["logs_marked"]}건 처리 '
                f'/ {reg_result["users"]}명'
            ))

        # ── 2. 수거검사 신규 배치 알림 ────────────────────────────────────────
        from v1.regulatory.models import InspectionMatch
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=3)
        pending_insp = InspectionMatch.objects.filter(
            alert_phase=InspectionMatch.PHASE_COLLECTION,
            notified_at__isnull=False,
            fcm_sent_at__isnull=True,
            inspection__collected_at__gte=cutoff,
        )
        insp_count = pending_insp.count()
        self.stdout.write(f'  수거검사 신규 미발송: {insp_count}건')

        if insp_count == 0:
            insp_result = {'users': 0, 'fcm_sent': 0}
        elif dry_run:
            self._print_inspection_preview(pending_insp)
            insp_result = {'users': 0, 'fcm_sent': 0}
        else:
            from v1.mobile.services.push_service import send_inspection_fcm_batch
            insp_result = send_inspection_fcm_batch()
            self.stdout.write(self.style.SUCCESS(
                f'  → 수거검사 FCM {insp_result["fcm_sent"]}건 발송 '
                f'/ {insp_result["users"]}명'
            ))

        # ── 최종 요약 ─────────────────────────────────────────────────────────
        total_fcm = reg_result['fcm_sent'] + insp_result['fcm_sent']
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'완료: FCM 총 {total_fcm}건 발송'
            ))
            logger.info(
                f'[send_pending_alerts] 완료 — 부적합FCM={reg_result["fcm_sent"]} '
                f'수거FCM={insp_result["fcm_sent"]} 총={total_fcm}'
            )

    def _print_regulatory_preview(self, pending_qs) -> None:
        """dry-run용: 기기별 미발송 건수 출력."""
        from django.db.models import Count
        rows = (
            pending_qs
            .values('device__user__username', 'trigger_type')
            .annotate(cnt=Count('id'))
            .order_by('device__user__username', 'trigger_type')
        )
        for row in rows:
            user = row['device__user__username'] or '(비로그인)'
            self.stdout.write(
                f'    {user} / {row["trigger_type"]}: {row["cnt"]}건'
            )

    def _print_inspection_preview(self, pending_qs) -> None:
        """dry-run용: 사용자별 수거검사 미발송 건수 출력."""
        from django.db.models import Count
        rows = (
            pending_qs
            .values('user__username')
            .annotate(cnt=Count('id'))
            .order_by('user__username')
        )
        for row in rows:
            self.stdout.write(
                f'    {row["user__username"]}: 수거검사 {row["cnt"]}건'
            )
