"""
운영 데이터 점검 — 화면을 클릭하지 않고 서버에서 확인한다.

"눈으로 봐야 한다"고 미뤄 둔 것들이 실은 데이터만 읽으면 답이 나온다.
아무것도 고치지 않는다. 읽기만 한다.

    python manage.py check_data_health
    python manage.py check_data_health --only inspection
    python manage.py check_data_health --user someone@example.com

세 가지를 본다.

  inspection  수거검사 알림이 보존돼 있는가
      라벨을 저장할 때마다 InspectionMatch 를 사용자 단위로 전량 삭제하던 버그가
      있었다(03cd6c2 에서 수정). 판정결과 변동(PHASE_JUDGMENT = 부적합 알림)은
      소급 매칭이 다시 만들어 주지 않아서, 지워졌으면 영구 소실이다.
      화면에는 아무것도 드러나지 않는다.

  order       원재료명 표시 순서가 배합비 내림차순인가
      「식품등의 표시기준」은 함량이 많은 순서로 적으라고 한다. 표시 문구를 만드는
      쪽은 정렬하지만(c816f12), 손으로 고친 문구는 그대로 남는다.

  duplicate   같은 원료가 여러 번 등록돼 있는가
      quick_register_ingredient / save_ingredients_to_label 이 매번 새
      MyIngredient 를 만든다. get_or_create 로 바꿀지 판단하려면 실제 규모를
      알아야 한다.
"""
from collections import Counter, defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone


class Command(BaseCommand):
    help = '운영 데이터 점검 (읽기 전용) — 수거검사 알림 / 원재료명 순서 / 원료 중복'

    CHECKS = ('inspection', 'order', 'duplicate')

    def add_arguments(self, parser):
        parser.add_argument('--only', choices=self.CHECKS, default=None,
                            help='한 가지만 본다')
        parser.add_argument('--user', default=None,
                            help='특정 사용자만 (아이디 또는 이메일)')

    def handle(self, *args, **options):
        user = None
        if options['user']:
            key = options['user']
            user = (User.objects.filter(username=key).first()
                    or User.objects.filter(email__iexact=key).first())
            if user is None:
                self.stdout.write(self.style.ERROR(f'사용자를 찾을 수 없습니다: {key}'))
                return
            self.stdout.write(f'대상 사용자: {user.username}')

        todo = [options['only']] if options['only'] else list(self.CHECKS)
        for name in todo:
            getattr(self, f'_check_{name}')(user)
            self.stdout.write('')

    # ── 1. 수거검사 알림 보존 ────────────────────────────────────────────────

    def _check_inspection(self, user):
        self.stdout.write(self.style.MIGRATE_HEADING('── 수거검사 알림 ──'))
        try:
            from v1.regulatory.models import InspectionMatch
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  조회 불가: {exc}'))
            return

        qs = InspectionMatch.objects.all()
        if user:
            qs = qs.filter(user=user)

        total = qs.count()
        if total == 0:
            self.stdout.write('  매칭 이력이 없습니다. (아직 수거검사에 걸린 제품이 없거나 수집 전)')
            return

        judgment = qs.filter(alert_phase=InspectionMatch.PHASE_JUDGMENT)
        collection = qs.filter(alert_phase=InspectionMatch.PHASE_COLLECTION)
        unread = qs.filter(read_yn=False).count()

        self.stdout.write(f'  전체 {total}건 (미확인 {unread}건)')
        self.stdout.write(f'    수거 감지(다시 만들어짐)     : {collection.count()}건')
        self.stdout.write(self.style.SUCCESS(
            f'    판정결과 변동(다시 안 만들어짐): {judgment.count()}건  <- 이게 보존돼야 한다'))

        # 사용자별로 갈라 보여 준다 — 한 사람 것만 사라지는 경우가 있었다
        by_user = Counter(qs.values_list('user__username', flat=True))
        if len(by_user) > 1:
            self.stdout.write('    사용자별:')
            for name, count in by_user.most_common(10):
                j = judgment.filter(user__username=name).count()
                self.stdout.write(f'      {name:<24} {count:4}건 (판정 {j}건)')

        # 판정 알림이 하나도 없으면 원래 없었던 건지 지워진 건지 알 수 없다.
        if judgment.count() == 0:
            self.stdout.write(self.style.WARNING(
                '    판정결과 변동 알림이 0건이다. 원래 없었을 수도 있고 예전에 지워졌을 수도 있다 -\n'
                '    지금부터는 라벨을 저장해도 줄지 않아야 한다. 이 숫자를 적어 두고 저장 후 다시 확인.'))
        else:
            oldest = judgment.order_by('created_at').first()
            self.stdout.write(
                f'    가장 오래된 판정 알림: {oldest.created_at:%Y-%m-%d %H:%M}'
                f' (라벨 저장으로 지워졌다면 최근 것만 남는다)')

    # ── 2. 원재료명 표시 순서 ────────────────────────────────────────────────

    def _check_order(self, user):
        self.stdout.write(self.style.MIGRATE_HEADING('── 원재료명 표시 순서 ──'))
        from v1.label.models import LabelIngredientRelation, MyLabel

        labels = MyLabel.objects.filter(delete_YN='N')
        if user:
            labels = labels.filter(user_id=user)

        ratios = defaultdict(list)
        rows = (LabelIngredientRelation.objects
                .filter(label__in=labels)
                .select_related('ingredient')
                .order_by('relation_sequence')
                .values_list('label_id', 'ingredient__prdlst_nm', 'ingredient_ratio'))
        for label_id, name, ratio in rows:
            ratios[label_id].append((name, ratio))

        checked, bad = 0, []
        for label_id, items in ratios.items():
            known = [(n, float(r)) for n, r in items if r is not None]
            if len(known) < 2:
                continue   # 배합비를 아는 게 2개 미만이면 순서를 따질 수 없다
            checked += 1
            for (n1, r1), (n2, r2) in zip(known, known[1:]):
                if r1 < r2:
                    bad.append((label_id, n1, r1, n2, r2))
                    break

        if checked == 0:
            self.stdout.write('  배합비가 2개 이상 입력된 라벨이 없어 순서를 따질 수 없습니다.')
            return

        self.stdout.write(f'  배합비로 순서를 따질 수 있는 라벨 {checked}건')
        if not bad:
            self.stdout.write(self.style.SUCCESS('  전부 배합비 내림차순입니다.'))
            return

        self.stdout.write(self.style.WARNING(f'  내림차순이 아닌 라벨 {len(bad)}건:'))
        names = dict(labels.values_list('my_label_id', 'my_label_name'))
        for label_id, n1, r1, n2, r2 in bad[:15]:
            self.stdout.write(
                f'    #{label_id} {(names.get(label_id) or "")[:24]}'
                f' - "{n1}"({r1:g}) 다음에 "{n2}"({r2:g})')
        self.stdout.write(
            '    입력 순서 자체는 문제가 아니다. 표시 문구를 만드는 쪽이 정렬하므로'
            ' 인쇄물은 규정을 지킨다.\n'
            '    다만 손으로 고친 최종 문구는 그대로 남으니 위 라벨은 미리보기를 확인할 것.')

    # ── 3. 원료 중복 등록 ────────────────────────────────────────────────────

    def _check_duplicate(self, user):
        self.stdout.write(self.style.MIGRATE_HEADING('── 원료 중복 등록 ──'))
        from v1.label.models import MyIngredient

        qs = MyIngredient.objects.filter(delete_YN='N')
        if user:
            qs = qs.filter(user_id=user)

        total = qs.count()
        if total == 0:
            self.stdout.write('  등록된 원료가 없습니다.')
            return

        # get_or_create 로 바꿀 때 쓸 키와 같은 조합으로 센다
        key = ('user_id', 'prdlst_nm', 'prdlst_report_no', 'prdlst_dcnm')
        groups = (qs.values(*key)
                    .annotate(n=Count('my_ingredient_id'))
                    .filter(n__gt=1)
                    .order_by('-n'))

        dup_groups = list(groups)
        wasted = sum(g['n'] - 1 for g in dup_groups)
        self.stdout.write(f'  전체 원료 {total}건')
        self.stdout.write(f'  같은 키가 겹치는 그룹 {len(dup_groups)}개, 여분 {wasted}건'
                          f' ({wasted / total * 100:.1f}%)')

        if not dup_groups:
            self.stdout.write(self.style.SUCCESS(
                '  중복이 없다. get_or_create 로 바꾸는 작업은 급하지 않다.'))
            return

        self.stdout.write('  많이 겹치는 것부터:')
        for g in dup_groups[:15]:
            self.stdout.write(
                f'    {g["n"]:3}개  {(g["prdlst_nm"] or "(이름 없음)")[:30]:<32}'
                f' {g["prdlst_dcnm"] or "":<14} {g["prdlst_report_no"] or ""}')

        if wasted / total >= 0.1:
            self.stdout.write(self.style.WARNING(
                '  여분이 10%를 넘는다 - get_or_create 로 바꿀 값이 있다.'))
        else:
            self.stdout.write(
                '  여분이 적다. 트랜잭션·검색 상한을 먼저 하고 이건 뒤로 미뤄도 된다.')

        # 언제 손댔는지 — MyIngredient 에는 생성일시가 없고 update_datetime 만 있다
        from datetime import timedelta
        recent = qs.filter(update_datetime__gte=timezone.now() - timedelta(days=30))
        self.stdout.write(f'  최근 30일 안에 저장된 원료 {recent.count()}건')
