# -*- coding: utf-8 -*-
"""
'여러 건' 구분에 잘못 쌓인 **판 사슬을 푼다.**

    python manage.py unchain_multiple_documents --dry-run   # 몇 건인지만
    python manage.py unchain_multiple_documents             # 풀어 준다

왜 생겼나
─────────
업로드는 슬롯이 없는 구분을 전부 '같은 구분의 옛 문서에 판으로 붙이기' 로
다뤘다. 원료 표시사항에는 슬롯이 없으므로, 사진을 셋 올리면 이렇게 됐다.

    크림치즈 사진  v1
    설탕 사진      v2   <- 크림치즈의 '새 판'
    밀가루 사진    v3

문서함 목록에는 밀가루 한 줄만 남고 앞의 둘은 판 접힘 속으로 들어간다.
**지운 적도 없는데 사라진 것으로 보인다.** 게다가 만료 알림은 현재 판만
보므로(doc_expiry) 앞의 둘은 알림에서도 빠진다.

규칙은 `DocumentType.multiple_yn` 으로 고쳤다. 이 명령은 **이미 쌓여 버린 것**
을 푼다 — 판을 지우는 것이 아니라 사슬만 끊어 저마다 제 문서로 세운다.
파일도 이름도 그대로다.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from v1.products.models import DocumentType, ProductDocument


class Command(BaseCommand):
    help = "'여러 건' 구분에 잘못 쌓인 판 사슬을 푼다"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='몇 건인지만 세고 고치지 않는다')
        parser.add_argument('--sample', type=int, default=0,
                            help='몇 건을 눈으로 보여 줄지')

    def handle(self, *args, **opts):
        dry, w = opts['dry_run'], self.stdout.write

        codes = list(DocumentType.objects
                     .filter(multiple_yn=True)
                     .values_list('type_code', 'type_name'))
        if not codes:
            w("'여러 건' 으로 표시된 구분이 없습니다.")
            return
        for code, name in codes:
            w('여러 건 구분: %s (%s)' % (name, code))

        chained = (ProductDocument.objects
                   .filter(document_type__multiple_yn=True,
                           parent_document__isnull=False)
                   .select_related('label', 'document_type')
                   .order_by('label_id', 'document_id'))

        total = chained.count()
        for doc in chained[:opts['sample']]:
            w('    · %s | %s | v%s'
              % (doc.label.my_label_name or doc.label.prdlst_nm or '',
                 doc.original_filename or '', doc.version))

        if not total:
            w(self.style.SUCCESS('풀 것이 없습니다.'))
            return

        if dry:
            w(self.style.SUCCESS('%d 건의 사슬을 풀 수 있습니다.' % total))
            w('세기만 했습니다. 고치려면 --dry-run 을 빼세요.')
            return

        # 판을 지우지 않는다. 사슬만 끊고 저마다 제 문서로 세운다.
        with transaction.atomic():
            done = (ProductDocument.objects
                    .filter(document_type__multiple_yn=True,
                            parent_document__isnull=False)
                    .update(parent_document=None, version=1))
        w(self.style.SUCCESS('%d 건을 저마다 제 문서로 세웠습니다.' % done))
