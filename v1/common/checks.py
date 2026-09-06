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
# 범위는 "products/ 안" 이 아니라 "V2 디자인 시스템이 닿는 화면" 이다.
#
# .v2-btn 계열은 products_common.css 에 있고, 그 파일은 base_v2.html 만 읽어들인다.
# 그래서 base.html 을 쓰는 화면에서 .v2-btn 으로 바꾸면 크기 규칙이 통째로 사라진다.
# 실제로 남아 있는 경고 324건 중 300건이 base.html 계열이었다 - 그걸 모르고 바꿨으면
# 표시사항 작성 화면과 홈의 버튼이 전부 스타일 없는 상태가 됐을 것이다.
#
# 그래서 extends 사슬이 base_v2.html 에 닿는 템플릿과, 그런 템플릿이 include 하는
# 부분 템플릿만 본다. 화면이 base_v2 로 옮겨오면 검사 범위도 저절로 따라온다.

_EXTENDS = re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']')
_INCLUDE = re.compile(r'{%\s*include\s+["\']([^"\']+)["\']')

_BTN_TAG = re.compile(r'<(?:button|a)\b[^>]*\bclass="[^"]*\bbtn\b[^"]*"[^>]*>', re.I)
_SIZE_IN_STYLE = re.compile(r'style="[^"]*\b(?:font-size|padding)\s*:', re.I)
# 크기를 담당하는 부트스트랩 클래스 (v2-btn-sm 안의 btn-sm 은 제외하려고 경계를 씀)
_BS_SIZE_CLASS = re.compile(r'(?<!-)\bbtn-(?:sm|lg|xs)\b')
# ─────────────────────────────────────────────────────────────────────────────
# 단추 명부
#
# **제 크기 체계를 갖는 단추들의 이름**이다. 공용 3단계(.v2-btn / .v2-btn-sm /
# .v2-btn-icon)로 안 되는 자리가 있다 — 조밀한 칩, 아이콘 하나짜리, 세로 탭.
# 그런 것은 여기 적는다.
#
# 두 검사가 같은 명부를 본다.
#
#   W001  "제 크기가 있으니 btn-sm 을 겹치지 마라" — 겹치면 두 규칙이 싸운다
#   W002  "명부에 있으니 새로 만든 것이 아니다"
#
# **여기 적는 일이 번거로운 것이 이 명부의 목적이다.** 새 단추를 만들 때
# "공용으로 되나?" 를 한 번 묻게 한다. 실제로 BOM 의 "전체선택"(.pick-all)과
# 화면 되돌리기(.v2-max-exit)가 공용으로 충분한데 새로 만들어졌고, W001 은
# 인라인 크기와 btn-sm 만 보므로 그냥 통과했다. 검사를 통과한 것과 결이 맞는
# 것은 다른 일이다.
_OWN_SIZED_BUTTONS = frozenset({
    # 게시판 구판
    'comment-action-btn', 'del-btn', 'form-action-btn', 'save-btn',
    'submit-btn', 'toolbar-btn',
    # 상단 계정·알림
    'v2-account-logout-btn', 'v2-notif-mark-all',
    # 표시사항·원료·미리보기
    'allergy-btn', 'ag-toggle-btn', 'disp-opt', 'ing-viewctl-btn',
    'panel-btn', 'pv-cond-add', 'pv-cond-clear', 'pv-cond-toggle',
    # 홈
    'app-strip-close', 'upd-strip-close', 'home-switch-btn', 'v2-auth-btn',
    # 제품·문서·BOM·연락처
    'allergen-add-btn', 'allergen-chip', 'allergen-icon-btn',
    'allergen-selectall-btn', 'btn-apply', 'btn-storage-badge',
    'contacts-filter-btn', 'contacts-icon-btn', 'di-name', 'doc-ver-btn',
    'dr-tab-btn', 'gmo-btn', 'panel-toggle-btn', 'product-quick-text-btn',
    'quick-allergen-btn', 'side-panel-toggle', 'summary-type-btn',
    # 부적합·처분 알림
    'kw-add-btn', 'rd-ab-btn', 'rd-act-btn', 'rd-as-edit', 'rd-cond-submit',
    'rd-insp-dismiss-btn', 'rd-insp-guide-btn', 'rd-memo-submit',
    'reg-cond-toggle', 'rf-listctl-dir', 'rkb-chip-del', 'rs-day-btn',
    'rs-quick-resolve', 'rs-risk-chip', 'rs-search-x', 'rs-settings-btn',
    'rs-vtab',
    # 내 정보
    'g-btn-danger', 'g-btn-primary', 'g-btn-secondary',
})

# 크기를 공용이 정해 주는 것들. 이 이름이 붙어 있으면 새로 만든 단추가 아니다.
_SHARED_BUTTON_CLASSES = frozenset({
    'btn',                       # 부트스트랩 + .v2-btn 계열
    'v2-action-btn', 'v2-action-btn-outline', 'v2-sidebar-toggle',
    'v2-seg-btn', 'act-btn',
    # 부트스트랩이 제 컴포넌트로 크기를 주는 것
    'btn-close', 'nav-link', 'accordion-button', 'navbar-toggler',
    'page-link', 'dropdown-item', 'dropdown-toggle', 'list-group-item',
})

_SIZED_BY_CLASS = ('v2-btn', 'v2-chip-btn', 'v2-link-btn') + tuple(
    sorted(_OWN_SIZED_BUTTONS))


def _v2_templates():
    """products_common.css 가 실제로 닿는 템플릿 (경로, 본문) 을 모은다."""
    text = {}
    for root in _template_dirs():
        for path in root.rglob('*.html'):
            try:
                text.setdefault(
                    str(path.relative_to(root)).replace(chr(92), '/'),
                    (path, path.read_text(encoding='utf-8')))
            except (OSError, UnicodeDecodeError):
                continue

    def reaches_v2(rel):
        seen = set()
        while rel and rel not in seen:
            if rel == 'base_v2.html':
                return True
            seen.add(rel)
            m = _EXTENDS.search(text[rel][1]) if rel in text else None
            rel = m.group(1) if m else None
        return False

    found = {r for r in text if reaches_v2(r)}
    # include 를 타고 부분 템플릿까지 넓힌다
    pending = list(found)
    while pending:
        for inc in _INCLUDE.findall(text[pending.pop()][1]):
            if inc in text and inc not in found:
                found.add(inc)
                pending.append(inc)
    return [(rel, *text[rel]) for rel in sorted(found)]


@register()
def check_product_button_sizing(app_configs, **kwargs):
    """V2 화면에서 버튼 크기를 인라인·부트스트랩으로 지정한 곳을 찾는다."""
    warnings = []
    for rel, path, text in _v2_templates():
        for m in _BTN_TAG.finditer(text):
            tag = m.group(0)
            if any(cls in tag for cls in _SIZED_BY_CLASS):
                continue
            if not (_SIZE_IN_STYLE.search(tag) or _BS_SIZE_CLASS.search(tag)):
                continue
            line = text.count('\n', 0, m.start()) + 1
            warnings.append(Warning(
                f'{rel}:{line} 버튼 크기를 인라인/btn-sm 으로 지정했습니다.',
                hint='products_common.css 의 .v2-btn / .v2-btn-sm / .v2-btn-icon 중 하나를 쓰세요.',
                obj=str(path),
                id='products.W001',
            ))
    return warnings


_BUTTON_TAG = re.compile(r'<button\b[^>]*>', re.I)
_CLASS_ATTR = re.compile(r'\bclass="([^"]*)"', re.I)
_DJANGO_TAG = re.compile(r'{%.*?%}|{{.*?}}', re.S)


@register()
def check_button_component_registry(app_configs, **kwargs):
    """
    공용 단추도 아니고 명부에도 없는 단추를 찾는다.

    이름이 아예 없는 <button> 은 보지 않는다 — 무엇을 등록하라고 할지가 없다.
    """
    warnings = []
    for rel, path, text in _v2_templates():
        for m in _BUTTON_TAG.finditer(text):
            attr = _CLASS_ATTR.search(m.group(0))
            if not attr:
                continue
            # 클래스 안에 {% if %} 가 섞여 온다. 태그를 걷고 이름만 본다
            names = [w for w in _DJANGO_TAG.sub(' ', attr.group(1)).split()
                     if w and not w.startswith(('{', '}'))]
            if not names:
                continue
            known = set(names)
            if known & _SHARED_BUTTON_CLASSES or known & _OWN_SIZED_BUTTONS:
                continue
            line = text.count('\n', 0, m.start()) + 1
            warnings.append(Warning(
                f'{rel}:{line} "{names[0]}" 는 공용 단추도, 명부에 오른 것도 '
                f'아닙니다.',
                hint='products_common.css 의 .v2-btn / .v2-btn-sm / '
                     '.v2-btn-icon / .v2-seg-btn 중 하나를 쓰세요. 제 크기 '
                     '체계가 꼭 필요하면 v1/common/checks.py 의 '
                     '_OWN_SIZED_BUTTONS 에 이름을 적으세요 — 적기 번거로운 '
                     '것이 그 명부의 목적입니다.',
                obj=str(path),
                id='products.W002',
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


# ─────────────────────────────────────────────────────────────────────────────
# 마이그레이션 의존 대상이 실제로 있는가
#
# regulatory.0001_initial 이 bom.0002_rename_is_fields 를 의존했는데 그 파일이
# 서버에 없었다(이름이 0002_rename_fields 였다). 그래서 서버에서는 migrate 가
# 그래프조차 만들지 못하고 NodeNotFoundError 로 죽었고, 넉 달 동안 아무도
# 마이그레이션을 돌리지 못했다.
#
# 원인은 .gitignore 가 migrations/ 를 빼고 있어서 배포된 곳마다 파일 구성이
# 갈라진 것이었다. 그 규칙은 걷어냈지만, 의존 대상이 사라지는 사고는 파일을
# 지우거나 이름을 바꿀 때도 난다.
#
# manage.py check 는 DB 없이도 돌고 마이그레이션 그래프를 만들지 않는다.
# 여기서 파일만 읽어 대조하면 배포 전에 잡을 수 있다.

@register()
def check_migration_dependencies(app_configs, **kwargs):
    """마이그레이션이 의존하는 대상 파일이 실제로 있는지 확인한다."""
    from django.db.migrations.loader import MigrationLoader

    try:
        loader = MigrationLoader(None, load=False)
        loader.load_disk()
    except Exception:
        return []   # 여기서 죽으면 check 자체를 못 쓴다. 조용히 넘어간다.

    disk = set(loader.disk_migrations)
    errors = []
    for (app, name), migration in sorted(loader.disk_migrations.items()):
        for dep in migration.dependencies:
            if dep[0] == '__setting__' or dep[1] in ('__first__', '__latest__'):
                continue
            if dep in disk:
                continue
            have = sorted(n for a, n in disk if a == dep[0])
            errors.append(Error(
                f'{app}.{name} 이 없는 마이그레이션 {dep[0]}.{dep[1]} 을 의존합니다.',
                hint=(f'{dep[0]} 에 있는 파일: {", ".join(have) or "(없음)"}. '
                      '이 상태에서는 migrate 가 그래프를 만들지 못하고 죽습니다.'),
                id='migrations.E001',
            ))
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# 템플릿이 컴파일되는가
#
# products/documents/expired_documents.html 이 {{ ...|abs }} 를 쓰고 있었다.
# Django 에 abs 필터는 없다. 그 페이지(/products/documents/expired/)는 열기만
# 하면 TemplateSyntaxError 로 죽었는데, 아무도 몰랐다 - 열어 본 사람이 없었으니까.
#
# 존재하지 않는 필터·태그, 닫히지 않은 블록은 전부 컴파일 단계에서 걸린다.
# 렌더링이 아니라 컴파일만 하므로 DB 도 컨텍스트도 필요 없고 빠르다.

@register()
def check_templates_compile(app_configs, **kwargs):
    """모든 템플릿이 컴파일되는지 확인한다."""
    from django.template import TemplateSyntaxError
    from django.template.loader import get_template

    errors = []
    for root in _template_dirs():
        for path in sorted(root.rglob('*.html')):
            rel = str(path.relative_to(root)).replace(chr(92), '/')
            try:
                get_template(rel)
            except TemplateSyntaxError as exc:
                errors.append(Error(
                    f'{rel} 이 컴파일되지 않습니다: {exc}',
                    hint='이 템플릿을 쓰는 화면은 열면 500 이 납니다.',
                    obj=str(path),
                    id='templates.E002',
                ))
            except Exception:
                # 로더가 못 찾는 경우(앱 하위 templates 중복 등)는 여기서 다루지
                # 않는다. 문법 오류만 본다.
                continue
    return errors
