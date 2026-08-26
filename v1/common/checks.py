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
from django.core.checks import Error, register

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
