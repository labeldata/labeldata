# -*- coding: utf-8 -*-
"""
배포본에서만 주석을 걷어내는 정적 파일 저장소.

왜
--
우리 JS·CSS 는 **왜 그렇게 했는지**를 주석으로 적어 둔다. 그게 이 저장소의
값나가는 부분이다 — "원산지 굵게와 순위 산정기가 겹쳤다", "초산·젖산이
국가명으로 잡혔다" 같은 것은 남이 몇 달 헤매야 알아낼 내용이다.

그런데 /static/ 은 로그인 없이 누구나 받는다. 재 보니 JS 2.6 MB 에 주석이
156 KB(13%)였고, 압축도 안 된 원본이 그대로 나가고 있었다.

**주석을 지우자는 것이 아니다.** 소스에는 그대로 두고 배포본에서만 지운다.
collectstatic 이 staticfiles/ 로 옮길 때 한 번 훑는다 — 원본 파일은 손대지
않는다.

무엇으로
--------
rjsmin·rcssmin. 파이썬만 쓰므로 서버에 node 를 깔 필요가 없다(배포는
git pull + collectstatic 뿐이다). 이름을 바꾸지 않는 보수적인 압축기라
문자열·정규식·템플릿 리터럴 안의 `//` 나 `/*` 를 주석으로 착각하지 않는다.
직접 정규식으로 지우려다가는 반드시 그걸 틀린다.

끄는 법
-------
    STATIC_MINIFY=0 python manage.py collectstatic --noinput --clear

압축 때문에 무언가 깨지면 이 한 줄로 원본이 그대로 배포된다. 소스는 애초에
건드리지 않으므로 되돌릴 것이 없다.
"""
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.staticfiles.storage import StaticFilesStorage

logger = logging.getLogger(__name__)

# 이미 압축된 것과 남의 코드는 건드리지 않는다. 남의 라이브러리를 다시
# 압축해서 얻을 것은 없고, 깨졌을 때 우리 잘못인지 알기 어려워진다.
SKIP_PARTS = ('/vendor/', '/vendors/', '/lib/', '/libs/', '/dist/')
SKIP_SUFFIX = ('.min.js', '.min.css', 'bootstrap.min.css')


def _should_skip(path):
    lowered = path.replace(chr(92), '/').lower()   # 윈도우 경로 구분자
    return (lowered.endswith(SKIP_SUFFIX)
            or any(part in lowered for part in SKIP_PARTS))


class CommentStrippingStaticFilesStorage(StaticFilesStorage):
    """collectstatic 이 옮긴 뒤 배포본의 주석을 걷어낸다."""

    def post_process(self, paths, dry_run=False, **options):
        if dry_run:
            return

        try:
            from rcssmin import cssmin
            from rjsmin import jsmin
        except ImportError:
            # 없다고 배포를 멈추지 않는다. 주석이 남을 뿐 화면은 돈다.
            logger.warning(
                '[static] rjsmin/rcssmin 이 없어 주석을 그대로 둡니다. '
                'pip install rjsmin rcssmin')
            return

        if not getattr(settings, 'STATIC_MINIFY', True):
            logger.info('[static] STATIC_MINIFY=0 — 원본 그대로 배포합니다.')
            return

        squeeze = {'.js': jsmin, '.css': cssmin}
        before = after = 0

        for path in paths:
            ext = '.js' if path.endswith('.js') else '.css' if path.endswith('.css') else ''
            if not ext or _should_skip(path):
                continue
            try:
                with self.open(path) as handle:
                    source = handle.read().decode('utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning('[static] %s 를 읽지 못해 건너뜁니다: %s', path, exc)
                continue

            packed = squeeze[ext](source)
            # 압축 결과가 빈 것은 무언가 잘못된 것이다 — 원본을 남긴다.
            if not packed.strip():
                logger.warning('[static] %s 압축 결과가 비어 원본을 둡니다.', path)
                continue

            before += len(source.encode('utf-8'))
            after += len(packed.encode('utf-8'))
            self.delete(path)
            self._save(path, ContentFile(packed.encode('utf-8')))
            yield path, path, True

        if before:
            logger.info('[static] 주석·공백 제거: %.0f KB → %.0f KB (%.0f%% 줄임)',
                        before / 1024, after / 1024,
                        (before - after) * 100.0 / before)
