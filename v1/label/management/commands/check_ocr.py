"""
OCR 경로를 서버에서 직접 짚어 본다.

화면에서 "사진을 읽는 중 오류가 발생했습니다" 만 보고는 어디가 막혔는지 알 수
없다. 브라우저 -> Django -> Pillow -> OpenAI 중 어디서 끊겼는지 하나씩 확인한다.

    python manage.py check_ocr                    # 설정과 연결만 확인
    python manage.py check_ocr --image label.jpg  # 실제 사진으로 끝까지

--image 를 주면 OpenAI 를 실제로 부른다(비용이 든다). 안 주면 키와 연결만 본다.
"""
import io
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'OCR 경로(설정·Pillow·OpenAI)를 단계별로 점검한다'

    def add_arguments(self, parser):
        parser.add_argument('--image', help='실제로 읽어 볼 사진 경로')
        parser.add_argument('--raw', action='store_true',
                            help='추출 결과를 그대로 출력')

    def handle(self, *args, **options):
        ok = True

        # 1. API 키
        key = getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
        if key:
            self.stdout.write(self.style.SUCCESS(
                f'  [1] OPENAI_API_KEY 있음 (...{key[-4:]}, {len(key)}자)'))
        else:
            ok = False
            self.stdout.write(self.style.ERROR('  [1] OPENAI_API_KEY 가 비어 있다'))

        # 2. 라이브러리
        try:
            from PIL import Image  # noqa: F401
            import PIL
            self.stdout.write(self.style.SUCCESS(f'  [2] Pillow {PIL.__version__}'))
        except Exception as exc:
            ok = False
            self.stdout.write(self.style.ERROR(f'  [2] Pillow 를 못 쓴다: {exc}'))

        try:
            import openai
            self.stdout.write(self.style.SUCCESS(f'  [3] openai {openai.__version__}'))
        except Exception as exc:
            ok = False
            self.stdout.write(self.style.ERROR(f'  [3] openai 를 못 쓴다: {exc}'))

        # 4. 바깥으로 나가는 연결. PythonAnywhere 무료 계정은 화이트리스트 밖을
        #    막는다. 그러면 여기서 걸린다.
        if key:
            try:
                from openai import OpenAI
                started = time.time()
                OpenAI(api_key=key, timeout=20).models.list()
                self.stdout.write(self.style.SUCCESS(
                    f'  [4] api.openai.com 연결 OK ({time.time() - started:.1f}초)'))
            except Exception as exc:
                ok = False
                self.stdout.write(self.style.ERROR(f'  [4] OpenAI 연결 실패: {exc}'))
                self.stdout.write(
                    '      호스팅이 바깥 연결을 막고 있으면 여기서 걸린다.')

        path = options['image']
        if not path:
            self.stdout.write('')
            self.stdout.write('  사진까지 확인하려면: --image /경로/사진.jpg')
            if not ok:
                raise CommandError('위 단계 중 실패가 있다.')
            return

        if not os.path.isfile(path):
            raise CommandError(f'파일이 없다: {path}')

        size_mb = os.path.getsize(path) / 1024 / 1024
        self.stdout.write('')
        self.stdout.write(f'  사진: {path} ({size_mb:.1f}MB)')
        if size_mb > 10:
            self.stdout.write(self.style.ERROR(
                '  10MB 를 넘는다. 화면에서는 올리기 전에 막힌다.'))

        # 5. 전처리
        try:
            from v1.label.services.ocr_service import preprocess_image
            with open(path, 'rb') as fh:
                started = time.time()
                b64 = preprocess_image(io.BytesIO(fh.read()))
            self.stdout.write(self.style.SUCCESS(
                f'  [5] 전처리 OK (base64 {len(b64) / 1024:.0f}KB, '
                f'{time.time() - started:.1f}초)'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  [5] 전처리 실패: {exc}'))
            raise CommandError('전처리에서 끊겼다.')

        # 6. 실제 추출
        from v1.label.services.ocr_service import extract_label_from_image
        with open(path, 'rb') as fh:
            started = time.time()
            result = extract_label_from_image(io.BytesIO(fh.read()))
        elapsed = time.time() - started

        if not result.get('success'):
            self.stdout.write(self.style.ERROR(
                f'  [6] 추출 실패 ({elapsed:.1f}초): {result.get("error")}'))
            raise CommandError('OpenAI 호출에서 끊겼다.')

        data = result.get('data') or {}
        found = [(k, v) for k, v in data.items()
                 if isinstance(v, dict) and v.get('value')]
        self.stdout.write(self.style.SUCCESS(
            f'  [6] 추출 OK ({elapsed:.1f}초), 값이 있는 항목 {len(found)}/{len(data)}개'))

        for field, item in found:
            value = str(item.get('value'))
            if len(value) > 60:
                value = value[:60] + '...'
            mark = ' ' if item.get('confidence') == 'high' else '?'
            self.stdout.write(f'      {mark} {field:20} {value}')

        empty = [k for k, v in data.items()
                 if isinstance(v, dict) and not v.get('value')]
        if empty:
            self.stdout.write(f'      (못 읽음: {", ".join(empty)})')

        if options['raw']:
            import json
            self.stdout.write('')
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
