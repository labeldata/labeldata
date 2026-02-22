from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from v1.user_management.models import UserProfile


GUEST_EMAIL    = 'guest@labeasylabel.com'
GUEST_PASSWORD = 'rptmxmfhrmdls1!'


class Command(BaseCommand):
    help = '게스트 계정이 없으면 자동으로 생성합니다. (개발/배포 환경 초기 세팅용)'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username=GUEST_EMAIL,
            defaults={
                'email': GUEST_EMAIL,
                'is_active': True,
            }
        )

        if created:
            user.set_password(GUEST_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'[✓] 게스트 계정 생성 완료: {GUEST_EMAIL}'))
        else:
            # 기존 계정이라도 비밀번호·활성 상태 보정
            changed = False
            if not user.check_password(GUEST_PASSWORD):
                user.set_password(GUEST_PASSWORD)
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                user.save()
                self.stdout.write(self.style.WARNING(f'[~] 게스트 계정 보정 완료: {GUEST_EMAIL}'))
            else:
                self.stdout.write(f'[=] 게스트 계정 이미 존재함: {GUEST_EMAIL}')

        # UserProfile 보정 (이메일 인증 필수)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.is_email_verified:
            profile.is_email_verified = True
            profile.save()
            self.stdout.write(self.style.WARNING('    → 이메일 인증 상태 보정 완료'))
