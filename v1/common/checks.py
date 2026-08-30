"""
템플릿 정적 검사 — `manage.py check` 로 함께 돈다.

여러 줄 {# #} 주석은 화면에 그대로 찍힌다.
Django 의 tag_re 는 ({%.*?%}|{{.*?}}|{#.*?#}) 이고 DOTALL 이 아니라서,
{# #} 는 '같은 줄' 안에서 닫힐 때만 주석으로 인식된다. 여러 줄로 쓰면
주석이 아니라 그냥 글자가 되어 사용자 화면에 코드가 노출된다.

눈으로는 잘 안 걸러진다(실제로 두 번 같은 실수를 했다). 배포 전에 도는
manage.py check 에 붙여 자동으로 잡는다.

    python manage.py check          # 문제가 있으면 오류로 보고
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Warning, register

_OPEN = re.compile(r'\{#')


def _template_dirs():
    dirs = []
    for engine in getattr(settings, 'TEMPLATES', []):
        dirs.extend(Path(d) for d in engine.get('DIRS', []))
    # 앱 하위 templates 도 함께 본다
    base = Path(settings.BASE_DIR)
    dirs.extend(p for p in base.glob('*/templates') if p.is_dir())
    return {d.resolve() for d in dirs if d.exists()}


def _multiline_comment_lines(text):
    """여는 {# 의 짝 #} 가 다른 줄에 있는 경우의 줄 번호 목록"""
    bad = []
    for m in _OPEN.finditer(text):
        end = text.find('#}', m.start())
        if end == -1:
            continue
        if '\n' in text[m.start():end]:
            bad.append(text.count('\n', 0, m.start()) + 1)
    return bad


@register()
def check_multiline_template_comments(app_configs, **kwargs):
    """여러 줄 {# #} 주석을 찾아 오류로 보고한다."""
    errors = []
    for root in _template_dirs():
        for path in root.rglob('*.html'):
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for line in _multiline_comment_lines(text):
                errors.append(Error(
                    f'{path.name}:{line} 여러 줄 {{# #}} 주석은 화면에 그대로 출력됩니다.',
                    hint='{% comment %} … {% endcomment %} 로 바꾸거나 한 줄로 줄이세요.',
                    obj=str(path),
                    id='templates.E001',
                ))
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# 제품 관리 화면의 버튼 크기 통일
#
# 탭 7개가 서로 다른 시대의 스타일로 쌓이면서, 문서함 한 화면에만 버튼 크기가
# 13px / 11px / 10px / 기본(14px) 네 종류였고 radius 도 4px / pill / 원형 /
# 기본이 섞여 있었다. products_common.css 에 크기 3단계(.v2-btn / .v2-btn-sm /
# .v2-btn-icon)를 두고 전부 그리로 옮겼다.
#
# 다시 인라인으로 크기를 지정하기 시작하면 같은 상태로 돌아간다. 눈으로는
# "조금 다르다" 정도로만 보여서 리뷰에서 잘 안 걸린다. 경고로 남겨 둔다.
#
# 크기(font-size/padding)만 본다 — 색·표시여부·폭 같은 인라인은 정상적인 쓰임이 많다.
#
# 범위를 제품 상세 화면으로 한정한다. products/ 전체를 보면 아직 정리하지 않은
# 화면(제품 탐색기·BOM·연락처 등)까지 122건이 잡히는데, 배포 때마다 도는
# manage.py check 가 매번 100줄을 뱉으면 아무도 안 읽게 된다. 다른 화면을 정리할
# 때 여기에 파일을 하나씩 추가하는 방식으로 넓힌다.

_CHECKED_TEMPLATES = (
    'product_detail.html',
    '_tab_basic_info.html',
    '_tab_documents.html',
    '_tab_permissions.html',
    '_tab_label.html',
)

_BTN_TAG = re.compile(r'<(?:button|a)\b[^>]*\bclass="[^"]*\bbtn\b[^"]*"[^>]*>', re.I)
_SIZE_IN_STYLE = re.compile(r'style="[^"]*\b(?:font-size|padding)\s*:', re.I)
# 크기를 담당하는 부트스트랩 클래스 (v2-btn-sm 안의 btn-sm 은 제외하려고 경계를 씀)
_BS_SIZE_CLASS = re.compile(r'(?<!-)\bbtn-(?:sm|lg|xs)\b')
_SIZED_BY_CLASS = ('v2-btn', 'v2-chip-btn', 'v2-link-btn', 'product-quick-text-btn')


@register()
def check_product_button_sizing(app_configs, **kwargs):
    """제품 상세 템플릿에서 버튼 크기를 인라인·부트스트랩으로 지정한 곳을 찾는다."""
    warnings = []
    for root in _template_dirs():
        products = root / 'products'
        if not products.is_dir():
            continue
        for name in _CHECKED_TEMPLATES:
            path = products / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for m in _BTN_TAG.finditer(text):
                tag = m.group(0)
                if any(cls in tag for cls in _SIZED_BY_CLASS):
                    continue
                if not (_SIZE_IN_STYLE.search(tag) or _BS_SIZE_CLASS.search(tag)):
                    continue
                line = text.count('\n', 0, m.start()) + 1
                warnings.append(Warning(
                    f'{path.name}:{line} 버튼 크기를 인라인/btn-sm 으로 지정했습니다.',
                    hint='products_common.css 의 .v2-btn / .v2-btn-sm / .v2-btn-icon 중 하나를 쓰세요.',
                    obj=str(path),
                    id='products.W001',
                ))
    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# CSS 캐시 무효화 문자열
#
# ?v=20260222 처럼 손으로 박아 둔 버전은 캐시를 갈아주는 것처럼 보이지만, CSS 를
# 고쳐도 URL 이 그대로라 브라우저는 계속 옛 파일을 쓴다. 실제로 products_common.css
# 를 고쳐 배포했는데 화면이 그대로였고, collectstatic 도 check 도 통과해서
# 원인을 찾는 데 시간이 걸렸다.
#
# STATIC_BUILD_DATE(서버 재시작 시각)를 쓰면 배포할 때마다 자동으로 갈린다.

_FIXED_CSS_VERSION = re.compile(r"\{%\s*static\s+'([^']+\.css)'\s*%\}\?v=(?!\{\{)([^\"'\s]+)")


@register()
def check_static_cache_busting(app_configs, **kwargs):
    """CSS 링크에 고정 버전 문자열을 쓴 곳을 찾는다."""
    warnings = []
    for root in _template_dirs():
        for path in sorted(root.rglob('*.html')):
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for m in _FIXED_CSS_VERSION.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                warnings.append(Warning(
                    f'{path.name}:{line} {m.group(1)} 의 캐시 버전이 고정값(?v={m.group(2)})입니다.',
                    hint='?v={{ STATIC_BUILD_DATE }} 로 바꾸세요. 고정값은 CSS 를 고쳐도 갈리지 않습니다.',
                    obj=str(path),
                    id='templates.W001',
                ))
    return warnings
