# -*- coding: utf-8 -*-
"""
알레르기 자동감지가 실제 원료에서 얼마나 맞히는가.

    python manage.py check_allergen_detect
    python manage.py check_allergen_detect --show 40
    python manage.py check_allergen_detect --scan rawmtrl   # 원재료명까지 읽었다면

아무것도 고치지 않는다. 읽기만 한다.

무엇과 견주는가
──────────────
정답표는 없다. 있는 것은 **사람이 손으로 골라 저장해 둔 알레르기**다. 그러니
여기서 재는 것은 정확도가 아니라 **일치율**이다 — 자동감지가 사람과 같은 것을
고르는가. 사람 쪽이 틀린 칸도 있을 것이므로, 어긋난 것은 수를 세는 데서 그치지
않고 **이름을 그대로 보여 준다.** 어느 쪽이 틀렸는지는 이름을 봐야 안다.

두 벌의 규칙을 따로 잰다
──────────────────────
같은 '자동감지' 인데 화면과 서버가 다르게 판정한다.

    화면(my_ingredient_detail_partial.js)  한 글자 키워드는 낱말 경계를 본다
                                           가짜 친구 목록이 **없다**
    서버(validation_service.check_allergens) 가짜 친구를 지운다
                                           낱말 경계를 **안 본다**

그래서 '아밀라아제' 는 화면에서 밀이 되고 서버에서는 안 되며, '게' 는 서버에서
아무 데나 붙는다. 둘을 나란히 재서 **어느 쪽 규칙이 실제 데이터에서 나은지**를
수로 본다.
"""
import re
from collections import Counter

from django.core.management.base import BaseCommand

from v1.label.constants import ALLERGEN_KEYWORDS
from v1.label.services.allergen_names import canonical
from v1.label.services.validation_service import _drop_false_friends


def detect_screen(text):
    """화면의 규칙. 한 글자는 낱말 경계, 가짜 친구는 안 거른다."""
    found = set()
    for name, keywords in ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            if len(kw) == 1:
                pat = r'(?:^|[\s,():])%s(?:$|[\s,():])' % re.escape(kw)
            else:
                pat = re.escape(kw)
            if re.search(pat, text, re.I):
                found.add(name)
                break
    return found


def detect_server(text):
    """서버의 규칙. 가짜 친구를 지우고, 낱말 경계는 안 본다."""
    found = set()
    for name, keywords in ALLERGEN_KEYWORDS.items():
        scanned = _drop_false_friends(text, name).lower()
        if any(kw.lower() in scanned for kw in keywords):
            found.add(name)
    return found


def detect_both(text):
    """둘을 합친 규칙 — 낱말 경계도 보고 가짜 친구도 지운다."""
    found = set()
    for name, keywords in ALLERGEN_KEYWORDS.items():
        scanned = _drop_false_friends(text, name)
        for kw in keywords:
            if len(kw) == 1:
                pat = r'(?:^|[\s,():])%s(?:$|[\s,():])' % re.escape(kw)
            else:
                pat = re.escape(kw)
            if re.search(pat, scanned, re.I):
                found.add(name)
                break
    return found


RULES = (('화면 규칙', detect_screen),
         ('서버 규칙', detect_server),
         ('둘을 합친 것', detect_both))


class Command(BaseCommand):
    help = '알레르기 자동감지가 사람이 고른 것과 얼마나 맞는지 잰다 (읽기 전용)'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, default=0, help='이 계정만')
        parser.add_argument('--show', type=int, default=25, help='보여 줄 원료 수')
        parser.add_argument('--scan', default='screen',
                            choices=('screen', 'rawmtrl'),
                            help='screen=화면이 실제로 읽는 두 칸, '
                                 'rawmtrl=원재료명까지 더 읽었을 때')

    def handle(self, *args, **opts):
        w = self.stdout.write
        from v1.label.models import MyIngredient

        qs = MyIngredient.objects.exclude(delete_YN='Y')
        if opts['user']:
            qs = qs.filter(user_id_id=opts['user'])

        rows = []
        for ing in qs.only('my_ingredient_id', 'prdlst_nm',
                           'ingredient_display_name', 'rawmtrl_nm', 'allergens'):
            text = '%s %s' % (ing.prdlst_nm or '', ing.ingredient_display_name or '')
            if opts['scan'] == 'rawmtrl':
                text += ' ' + (ing.rawmtrl_nm or '')
            text = text.strip()
            if not text:
                continue
            truth = {canonical(t) for t in re.split(r'[,、，/·]', ing.allergens or '')}
            truth.discard('')
            rows.append((ing, text, truth))

        w('─' * 74)
        w('알레르기 자동감지 — 사람이 골라 둔 것과 견준다')
        w('')
        w('   원료             %6d' % qs.count())
        w('   읽을 글자가 있음  %6d' % len(rows))
        told = [r for r in rows if r[2]]
        w('   사람이 골라 둔 것 %6d  ← 이 만큼만 견줄 수 있다' % len(told))
        w('   읽는 칸: %s' % ('품목명 + 표시명'
                             if opts['scan'] == 'screen' else '품목명 + 표시명 + 원재료명'))

        if not told:
            w('')
            w('   견줄 것이 없다. 알레르기를 저장해 둔 원료가 없다.')
            return

        for label, fn in RULES:
            hit = miss = extra = exact = 0
            miss_kind = Counter()
            extra_kind = Counter()
            for ing, text, truth in told:
                got = fn(text)
                hit += len(got & truth)
                for a in truth - got:
                    miss += 1
                    miss_kind[a] += 1
                for a in got - truth:
                    extra += 1
                    extra_kind[a] += 1
                if got == truth:
                    exact += 1
            total = hit + miss
            w('')
            w('─' * 74)
            w('%s' % label)
            w('')
            w('   맞힌 성분     %6d / %d  (%.0f%%)   ← 사람이 고른 것을 찾아냈다'
              % (hit, total, hit / total * 100 if total else 0))
            w('   놓친 성분     %6d          ← **가장 나쁜 오류다**' % miss)
            w('   더 잡은 성분  %6d          ← 사람이 안 고른 것을 골랐다' % extra)
            w('   원료 통째로 일치 %4d / %d  (%.0f%%)'
              % (exact, len(told), exact / len(told) * 100))
            if miss_kind:
                w('   놓친 것:    ' + ', '.join(
                    '%s %d' % kv for kv in miss_kind.most_common(8)))
            if extra_kind:
                w('   더 잡은 것: ' + ', '.join(
                    '%s %d' % kv for kv in extra_kind.most_common(8)))

        # 어긋난 것은 이름을 보여 준다 — 어느 쪽이 틀렸는지는 이름을 봐야 안다
        w('')
        w('─' * 74)
        w('어긋난 원료 — 합친 규칙 기준. 놓친 것부터')
        w('')
        bad = []
        for ing, text, truth in told:
            got = detect_both(text)
            if got != truth:
                bad.append((len(truth - got), ing, text, truth, got))
        bad.sort(key=lambda t: -t[0])
        w('   %-34s %-16s %s' % ('원료', '사람이 고른 것', '자동감지'))
        w('   ' + '-' * 68)
        for _n, ing, text, truth, got in bad[:opts['show']]:
            mark = '놓침' if truth - got else '더잡음'
            w('   %-34s %-16s %-16s %s'
              % (text[:34], ','.join(sorted(truth))[:16],
                 ','.join(sorted(got))[:16] or '-', mark))
        if len(bad) > opts['show']:
            w('   … 그 밖에 %d 개' % (len(bad) - opts['show']))
        w('─' * 74)
