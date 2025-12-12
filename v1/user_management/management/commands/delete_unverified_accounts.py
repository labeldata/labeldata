"""
미인증 계정 자동 삭제 배치 작업

가입 후 48시간 이내에 이메일 인증을 하지 않은 계정을 삭제합니다.
PythonAnywhere 스케줄러에서 매일 오전 1시에 실행하도록 설정하세요.

실행 방법:
python manage.py delete_unverified_accounts

수동 실행 (dry-run):
python manage.py delete_unverified_accounts --dry-run
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from v1.user_management.models import UserProfile


class Command(BaseCommand):
    help = '가입 후 48시간 이내에 이메일 인증을 하지 않은 계정을 삭제합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 삭제하지 않고 삭제 대상만 출력합니다.',
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=48,
            help='삭제 기준 시간 (기본: 48시간)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hours = options['hours']
        
        # 현재 시간으로부터 지정된 시간 이전
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        self.stdout.write(f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] 미인증 계정 삭제 배치 시작")
        self.stdout.write(f"삭제 기준: {hours}시간 전 ({cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # 삭제 대상 조회
        # 1. is_active=False (미인증 상태)
        # 2. email_verification_sent_at이 cutoff_time보다 이전
        unverified_users = User.objects.filter(
            is_active=False,
            profile__email_verification_sent_at__lt=cutoff_time,
            profile__is_email_verified=False
        ).select_related('profile')
        
        count = unverified_users.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("삭제 대상 계정이 없습니다."))
            return
        
        # 삭제 대상 목록 출력
        self.stdout.write(f"\n삭제 대상 계정 ({count}개):")
        for user in unverified_users:
            sent_at = user.profile.email_verification_sent_at
            if sent_at:
                time_diff = timezone.now() - sent_at
                hours_passed = int(time_diff.total_seconds() / 3600)
                self.stdout.write(
                    f"  - {user.email} (가입: {sent_at.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"경과: {hours_passed}시간)"
                )
            else:
                self.stdout.write(f"  - {user.email} (발송 시간 정보 없음)")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN 모드] 실제 삭제하지 않습니다."))
            return
        
        # 실제 삭제 수행
        # User를 삭제하면 UserProfile도 CASCADE로 자동 삭제됨
        deleted_count, _ = unverified_users.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ {deleted_count}개의 미인증 계정이 삭제되었습니다."
            )
        )
        self.stdout.write(f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] 배치 작업 완료")
