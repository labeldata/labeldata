"""
만들어만 놓고 손대지 않은 "임시 - 제품명 - N" 라벨을 치운다.

신규 작성 버튼을 누르면 그 시점에 이미 MyLabel 이 만들어진다. 그래서 화면만
열어 보고 나간 사용자마다 빈 라벨이 하나씩 남고, 제품 목록에 섞여 보인다.

**지우지 않는다. delete_YN 을 'Y' 로 바꿀 뿐이다.**
MyLabel 을 실제로 지우면 BOM·문서함·공유·알림까지 CASCADE 로 함께 사라진다.
앱은 어차피 delete_YN='N' 만 보여주므로 화면에서 사라지는 결과는 같고,
잘못 골랐을 때 되돌릴 수 있다.

무엇을 "손대지 않았다" 고 볼지는 필드를 나열하지 않고 **모델 기본값과 비교**해서
정한다. 필드가 늘어도 이 커맨드를 고칠 일이 없고, 사용자가 뭐라도 입력했으면
기본값과 달라지므로 후보에서 빠진다.

기본은 미리보기다. 실제로 바꾸려면 --apply 를 붙여야 한다.

    python manage.py cleanup_temp_labels                  # 미리보기
    python manage.py cleanup_temp_labels --days 60        # 60일 지난 것만
    python manage.py cleanup_temp_labels --apply
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from v1.label.models import MyLabel

TEMP_PREFIX = '임시 - 제품명 - '

# 내용과 무관한 필드. 이것들이 달라도 "손댔다" 고 보지 않는다.
SKIP_FIELDS = {
    'my_label_id', 'user_id', 'my_label_name',
    'create_datetime', 'update_datetime',
    'delete_YN', 'delete_datetime',
    'display_order',
}


def untouched_fields_match(label, blank):
    """저장 안 한 기본값 인스턴스와 견줘 하나라도 다르면 False."""
    for field in MyLabel._meta.fields:
        if field.name in SKIP_FIELDS:
            continue
        if getattr(label, field.attname, None) != getattr(blank, field.attname, None):
            return False
    return True


class Command(BaseCommand):
    help = '만들어만 놓고 손대지 않은 임시 라벨을 숨김 처리한다 (기본: 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='마지막 수정이 이 일수보다 오래된 것만 (기본 30)')
        parser.add_argument('--apply', action='store_true',
                            help='실제로 delete_YN 을 Y 로 바꾼다')
        parser.add_argument('--limit', type=int, default=0,
                            help='처리 개수 상한 (0 이면 전부)')

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)

        candidates = (
            MyLabel.objects
            .filter(my_label_name__startswith=TEMP_PREFIX,
                    delete_YN='N',
                    update_datetime__lt=cutoff)
            .order_by('my_label_id')
        )

        self.stdout.write(f'  이름이 "{TEMP_PREFIX}N" 이고 {days}일 이상 조용한 라벨: '
                          f'{candidates.count()}건')

        blank = MyLabel()   # 저장하지 않는다. 기본값을 읽기 위한 것뿐이다.
        targets, kept = [], []

        for label in candidates.iterator():
            reason = self._why_keep(label, blank)
            if reason:
                kept.append((label, reason))
            else:
                targets.append(label)
            if options['limit'] and len(targets) >= options['limit']:
                break

        for label, reason in kept[:10]:
            self.stdout.write(f'    남김 #{label.my_label_id}: {reason}')
        if len(kept) > 10:
            self.stdout.write(f'    ... 남기는 것 {len(kept)}건')

        self.stdout.write(self.style.WARNING(
            f'  숨길 대상: {len(targets)}건 / 내용이 있어 남기는 것: {len(kept)}건'))

        if not targets:
            return
        for label in targets[:10]:
            self.stdout.write(f'    #{label.my_label_id} {label.my_label_name} '
                              f'(마지막 수정 {label.update_datetime:%Y-%m-%d})')
        if len(targets) > 10:
            self.stdout.write(f'    ... 외 {len(targets) - 10}건')

        if not options['apply']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '  미리보기다. 실제로 숨기려면 --apply 를 붙여라.'))
            return

        ids = [label.my_label_id for label in targets]
        with transaction.atomic():
            # update() 를 쓴다 — save() 는 post_save 시그널을 깨워
            # 수거검사 소급 매칭을 라벨마다 한 번씩 돌린다.
            changed = MyLabel.objects.filter(my_label_id__in=ids).update(
                delete_YN='Y',
                delete_datetime=timezone.now().strftime('%Y%m%d'),
            )
        self.stdout.write(self.style.SUCCESS(f'  숨김 처리 {changed}건'))

    @staticmethod
    def _why_keep(label, blank):
        """남겨야 하는 이유를 돌려준다. 지워도 되면 빈 문자열."""
        if label.ingredient_relations.exists():
            return '원재료가 연결돼 있음'
        if label.bom_items.filter(active_yn=True).exists():
            return 'BOM 이 있음'
        if label.v2_documents.exists():
            return '문서함에 파일이 있음'
        if label.v2_shares.exists():
            return '다른 사용자와 공유됨'
        if not untouched_fields_match(label, blank):
            return '입력된 내용이 있음'
        return ''
