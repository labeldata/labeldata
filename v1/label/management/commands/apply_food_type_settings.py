"""
기존 라벨의 표시 항목(chckd_*)을 식품유형 규칙에 맞춘다.

지금까지 /label/food-type-settings/ 가 없어서 식품유형을 무엇으로 골랐든 새
라벨은 모델 기본값 9개로만 시작했다. 그래서 예를 들어 빵류인데 영양성분·
소비기한 체크가 꺼진 라벨이 쌓여 있다.

인쇄물에서 줄이 사라지는 방향은 최대한 피한다 (services/food_type_settings.py
의 apply_to_label 참고).

    'Y' 표시 대상   -> 켠다
    'D' 해당 없음   -> 값이 비어 있을 때만 끈다 (값이 있으면 보고만)
    'N' 사용자 재량 -> 건드리지 않는다

기본은 미리보기다. 실제로 바꾸려면 --apply 를 붙인다.

    python manage.py apply_food_type_settings
    python manage.py apply_food_type_settings --apply
    python manage.py apply_food_type_settings --label 423 --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from v1.label.models import MyLabel
from v1.label.services import food_type_settings as fts


class Command(BaseCommand):
    help = '기존 표시사항의 표시 항목 체크를 식품유형 규칙에 맞춘다 (기본: 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='실제로 저장한다 (없으면 무엇이 바뀔지만 보여준다)')
        parser.add_argument('--label', type=int, default=None,
                            help='특정 라벨 하나만 (표시사항 번호)')
        parser.add_argument('--limit', type=int, default=0,
                            help='앞에서부터 N건만')

    def handle(self, *args, **options):
        qs = MyLabel.objects.filter(delete_YN='N').exclude(
            food_type__isnull=True).exclude(food_type='')
        if options['label']:
            qs = qs.filter(my_label_id=options['label'])
        qs = qs.order_by('my_label_id')
        if options['limit']:
            qs = qs[:options['limit']]

        labels = list(qs)
        self.stdout.write(f'대상 라벨 {len(labels)}건 (식품유형이 설정된 것만)')
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                '미리보기입니다. 실제로 바꾸려면 --apply 를 붙이세요.\n'))

        changed, skipped, unknown = 0, 0, 0
        kept_total = []

        for label in labels:
            rule = fts.resolve_settings(label.food_group or '', label.food_type or '')
            if not rule['found']:
                unknown += 1
                self.stdout.write(self.style.WARNING(
                    f'  #{label.my_label_id} {label.my_label_name[:28]} '
                    f'— 식품유형 "{label.food_type}" 규칙 없음, 건너뜀'))
                continue

            result = fts.apply_to_label(label, rule['settings'])
            on, off, kept = result['turned_on'], result['turned_off'], result['kept_filled']
            if not (on or off):
                skipped += 1
                continue

            changed += 1
            self.stdout.write(f'  #{label.my_label_id} {label.my_label_name[:28]} ({label.food_type})')
            if on:
                self.stdout.write(self.style.SUCCESS(
                    '      켬  : ' + ', '.join(self._names(on))))
            if off:
                self.stdout.write(
                    '      끔  : ' + ', '.join(self._names(off)) + '  (해당 없음, 값도 비어 있음)')
            if kept:
                kept_total.append((label.my_label_id, kept))

            if options['apply']:
                with transaction.atomic():
                    # update_fields 를 지정해 라벨 저장 시그널(수거검사 소급 매칭)이
                    # 도는 조건을 바꾸지 않는다.
                    label.save(update_fields=list(set(on + off)))

        self.stdout.write('')
        self.stdout.write(f'바뀜 {changed}건 / 그대로 {skipped}건 / 규칙없음 {unknown}건')

        if kept_total:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '아래는 식품유형상 "해당 없음" 인데 값이 들어 있어 끄지 않았습니다. '
                '끄면 인쇄물에서 그 줄이 사라지므로 눈으로 확인하세요.'))
            for label_id, items in kept_total:
                self.stdout.write(f'  #{label_id}: ' + ', '.join(self._names(items)))

        if changed and not options['apply']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('아무것도 저장하지 않았습니다 (--apply 없음).'))

    @staticmethod
    def _names(checkboxes):
        out = []
        for checkbox in checkboxes:
            field = checkbox[len('chckd_'):]
            try:
                out.append(str(MyLabel._meta.get_field(field).verbose_name))
            except Exception:
                out.append(field)
        return out
