"""
OpenAI 도달 여부·응답시간 점검.

AI검증이 느리거나 실패할 때 원인이 "키가 틀렸는지 / 네트워크가 막혔는지 /
그냥 느린지" 를 서버에서 바로 가려내기 위한 것이다. 웹 요청으로 확인하려면
PythonAnywhere 의 300초 제한에 먼저 걸려서 원인을 못 본다.

    python manage.py check_openai
    python manage.py check_openai --timeout 5      # 더 짧게 끊어보기
    python manage.py check_openai --repeat 3       # 편차 확인
    python manage.py check_openai --label 123      # 실제 라벨로 전 구간 측정

더미 프롬프트에 max_tokens=1 이라 기본 점검 비용은 사실상 0이다.
--label 은 실제 AI검증을 한 번 돌리므로 그 계정의 일일 사용 횟수를 1회 쓴다.
"""
import time

from django.core.management.base import BaseCommand

from v1.label.services.ai_validation_service import (
    REASON_MESSAGES,
    REASON_OK,
    _ai_max_retries,
    _ai_timeout,
    get_openai_client,
)


class Command(BaseCommand):
    help = 'OpenAI API 도달 여부와 응답시간을 점검한다 (AI검증 장애 진단용)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout', type=float, default=None,
            help='이번 점검에만 쓸 타임아웃(초). 기본은 settings 값.',
        )
        parser.add_argument(
            '--repeat', type=int, default=1,
            help='반복 횟수 (응답시간 편차 확인용)',
        )
        parser.add_argument(
            '--label', type=int, default=None,
            help='이 라벨로 실제 AI검증을 한 번 돌려 구간별 시간과 결과를 본다 '
                 '(일일 사용 횟수 1회 소모)',
        )

    def handle(self, *args, **options):
        from django.conf import settings

        key = getattr(settings, 'OPENAI_API_KEY', '') or ''
        self.stdout.write('── 설정 ──')
        self.stdout.write(f'  OPENAI_API_KEY : {"설정됨" if key else "없음"} '
                          f'(길이 {len(key)}, 접두 {key[:7] if key else "-"})')
        self.stdout.write(f'  타임아웃        : {_ai_timeout()}초')
        self.stdout.write(f'  재시도 상한     : {_ai_max_retries()}회')

        client, reason = get_openai_client()
        if client is None:
            self.stdout.write(self.style.ERROR(
                f'\n클라이언트를 만들지 못했습니다 — {REASON_MESSAGES.get(reason, reason)}'))
            return

        timeout = options['timeout']
        if timeout:
            client = client.with_options(timeout=timeout)
            self.stdout.write(f'  (이번 점검 타임아웃 {timeout}초로 덮어씀)')

        self.stdout.write('\n── 호출 ──')
        oks, times = 0, []
        for i in range(1, options['repeat'] + 1):
            t0 = time.time()
            try:
                client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{'role': 'user', 'content': 'ping'}],
                    max_tokens=1,
                )
                dt = time.time() - t0
                times.append(dt)
                oks += 1
                self.stdout.write(self.style.SUCCESS(f'  {i}) 성공  {dt:.2f}초'))
            except Exception as exc:
                dt = time.time() - t0
                self.stdout.write(self.style.ERROR(
                    f'  {i}) 실패  {dt:.2f}초  {type(exc).__name__}: {str(exc)[:160]}'))

        self.stdout.write('\n── 판정 ──')
        if oks == 0:
            self.stdout.write(self.style.ERROR(
                '  전부 실패했습니다. AI검증은 규칙 기반 결과만 돌려주고 있을 것입니다.\n'
                '  401/403 이면 키 문제, 연결/타임아웃이면 서버에서 api.openai.com 으로\n'
                '  나가는 경로가 막혀 있을 가능성이 큽니다.'))
            return

        avg = sum(times) / len(times)
        worst = max(times)
        self.stdout.write(f'  성공 {oks}/{options["repeat"]}회, 평균 {avg:.2f}초, 최대 {worst:.2f}초')
        # AI검증은 이 호출을 4번 한다 (독립 3개는 병렬, 요약 1개는 그 뒤)
        est = worst * 2
        self.stdout.write(f'  AI검증 1회 예상 소요 ≈ {est:.1f}초 (독립 3개 병렬 + 요약 1개)')
        if worst > _ai_timeout():
            self.stdout.write(self.style.WARNING(
                f'  최대 응답시간이 타임아웃({_ai_timeout()}초)을 넘습니다 — '
                f'AI검증이 자주 "확인하지 못함" 으로 끝날 수 있습니다.'))
        elif est > 60:
            self.stdout.write(self.style.WARNING('  응답이 느린 편입니다.'))
        else:
            self.stdout.write(self.style.SUCCESS('  정상 범위입니다.'))
        if reason != REASON_OK:
            self.stdout.write(f'  (참고: {reason})')

        if options['label']:
            self._run_full(options['label'])

    # ─────────────────────────────────────────────────────────────────────────

    def _run_full(self, label_id):
        """실제 라벨로 AI검증 전 구간을 돌려 어디서 시간이 가는지 본다."""
        from v1.label.models import MyLabel
        from v1.label.services.ai_validation_service import run_full_review
        from v1.label.services.validation_service import validate_label

        label = MyLabel.objects.filter(my_label_id=label_id).select_related('user_id').first()
        if not label:
            self.stdout.write(self.style.ERROR(f'\n라벨 #{label_id} 을 찾을 수 없습니다.'))
            return

        self.stdout.write(f'\n── 실제 검증: #{label.my_label_id} {label.my_label_name} ──')
        self.stdout.write(f'  원재료명(최종표시) {len(label.rawmtrl_nm_display or "")}자 / '
                          f'원재료명(참고) {len(label.rawmtrl_nm or "")}자')
        self.stdout.write(f'  제품명: {label.prdlst_nm or "(비어 있음)"}')

        t0 = time.time()
        rule = validate_label(label)
        t_rule = time.time() - t0
        self.stdout.write(f'\n  규칙 기반 검증 : {t_rule:.2f}초, 이슈 {rule["issue_count"]}건 '
                          f'(검증 항목 {len(rule["checked_regulations"])}종)')

        t0 = time.time()
        result = run_full_review(label, label.user_id)
        t_full = time.time() - t0
        self.stdout.write(f'  통합 검증 전체 : {t_full:.2f}초 '
                          f'(캐시적중={result.get("from_cache")}, 한도차단={result.get("blocked")})')

        if result.get('blocked'):
            self.stdout.write(self.style.WARNING(
                f'  일일 한도에 걸렸습니다: {result["usage"].get("message")}'))
            return

        self.stdout.write('\n  AI 항목 판정')
        for key, name in (
            ('ingredient_order_checked', '원재료 표시 순서'),
            ('allergen_ai_checked',      '알레르기(AI)'),
            ('name_ingredient_checked',  '제품명-원재료 일치성'),
        ):
            ok = result.get(key)
            mark = self.style.SUCCESS('확인함') if ok else self.style.WARNING('확인 못함')
            self.stdout.write(f'    {name:<22} {mark}')

        for u in result.get('unchecked', []):
            self.stdout.write(f'    └ {u["label"]}: {u["message"]} [{u["reason"]}]')

        self.stdout.write('\n  결과 요약')
        self.stdout.write(f'    전체 판정 : {"적합" if result.get("ok") else "확인 필요"}')
        for row in result.get('categories', []):
            state = '적합' if row['ok'] else '재검토'
            self.stdout.write(f'    {row["label"]:<26} {state}')
            for e in row.get('errors', [])[:2]:
                self.stdout.write(f'        - {e[:100]}')
        self.stdout.write(f'\n    AI 요약: {(result.get("summary") or "")[:200]}')

        if t_full > 60:
            self.stdout.write(self.style.WARNING(
                f'\n  {t_full:.0f}초 걸렸습니다. PythonAnywhere 웹 요청 제한(300초)에는 '
                f'못 미치지만 사용자가 기다리기엔 깁니다.'))
