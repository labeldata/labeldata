# -*- coding: utf-8 -*-
"""
브라우저로 JS 를 **실제로 읽어** 문법 오류를 잡는다.

이 저장소의 화면 시험은 원본 문자열을 찾는 것이라, 괄호 하나가 빠진 채로 배포된
일이 여러 번 있었다(괄호 개수 세기로는 문자열·정규식 안의 괄호를 가르지 못한다).
헤드리스 크롬이 있으면 정적 JS 전부와 주요 화면(렌더한 HTML 의 인라인 JS)을
읽혀 SyntaxError 만 건진다 — 실행 오류(fetch 실패 등)는 file:// 에서 당연히
나므로 세지 않는다. 크롬이 없는 곳(운영 서버)에서는 건너뛴다.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

_CHROME_CANDIDATES = [
    os.environ.get('CHROME_PATH', ''),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
]
_HARNESS_HEAD = (
    '<script>window.__errs=[];'
    'window.onerror=function(m,s,l,c){window.__errs.push(String(m)+" @ "+String(s||"")+":"+l+":"+c);'
    'document.documentElement.setAttribute("data-errs",JSON.stringify(window.__errs));return true;};'
    'window.addEventListener("load",function(){document.documentElement.setAttribute("data-errs",JSON.stringify(window.__errs));'
    'document.documentElement.setAttribute("data-loaded","1");});'
    '</script>'
)
_STATIC_DIR = Path(settings.BASE_DIR) / 'static'


def chrome_path():
    for cand in _CHROME_CANDIDATES:
        if cand and os.path.exists(cand):
            return cand
    return shutil.which('chrome') or shutil.which('google-chrome') or shutil.which('chromium')


def run_chrome(html_path: Path, timeout=120, want_dom=False):
    """
    페이지를 읽혀 window.onerror 로 잡힌 오류 문장을 돌려준다.

    **제 프로필을 새로 쓴다.** `--user-data-dir` 을 안 주면 크롬은 기본 프로필에
    붙는데, 사람이 크롬을 띄워 두었거나 앞선 시험의 헤드리스 판이 남아 있으면
    `--dump-dom` 이 돌아오지 않는다 — 그러면 시간 초과로 붉어지고, 붉은 문장은
    "인라인 JS 가 문법에 안 맞다" 를 가리킨다(문법과 아무 상관이 없다).
    실제로 브라우저 시험 뒤에 이 시험 넷이 한꺼번에 그렇게 무너졌다.
    """
    exe = chrome_path()
    profile = tempfile.mkdtemp(prefix='ezjs-')
    cmd = [exe, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
           f'--user-data-dir={profile}', '--no-default-browser-check',
           '--disable-extensions', '--allow-file-access-from-files', '--mute-audio',
           '--virtual-time-budget=4000', '--dump-dom', html_path.as_uri()]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    dom = out.stdout.decode('utf-8', errors='replace')
    m = re.search(r'data-errs="([^"]*)"', dom)
    if not m:
        raise AssertionError('크롬이 페이지를 읽지 못했다: ' + (out.stderr.decode('utf-8', 'replace')[-500:]))
    errs = json.loads(html.unescape(m.group(1)))
    return (errs, dom) if want_dom else errs


def syntax_errors(errs):
    return [e for e in errs if 'SyntaxError' in e]


def static_js_files():
    return sorted(p for p in _STATIC_DIR.rglob('*.js') if p.is_file())


class 브라우저가_JS_를_읽는다(TestCase):
    """크롬이 없으면 건너뛴다. 있으면 문법 오류는 여기서 걸린다 — 배포 전에."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chrome = chrome_path()
        cls.tmp = Path(tempfile.mkdtemp(prefix='jsharness-'))

    def setUp(self):
        if not self.chrome:
            self.skipTest('헤드리스 크롬이 없다')
        self.user = User.objects.create_user(username='jsharness', password='x')
        self.client.force_login(self.user)

    def test_고장난_JS_는_잡힌다(self):
        """이 장치가 조용히 초록이면 아무 소용이 없다 — 일부러 깨뜨려 잡히는지 본다."""
        page = self.tmp / 'broken.html'
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8">{_HARNESS_HEAD}</head>'
                        '<body><script>function broken( {</script>'
                        '<script>window.__fine = 1;</script></body></html>', encoding='utf-8')
        errs = run_chrome(page)
        self.assertEqual(len(syntax_errors(errs)), 1, errs)

    def test_정적_JS_전부가_문법에_맞다(self):
        """
        **실행하지 않고 읽기만 한다** — `new Function(원문)`. 파일 46개를 한 페이지에
        <script> 로 넣어 실행하면 어느 하나가 location.reload() 를 돌려 영영 끝나지
        않는다(실제로 그랬다). 파싱만 하면 SyntaxError 는 그대로 잡히고 아무것도
        돌지 않는다.
        """
        files = static_js_files()
        self.assertGreater(len(files), 30)
        listing = json.dumps([[p.relative_to(_STATIC_DIR).as_posix(), p.as_uri()] for p in files])
        runner = (
            '<script>(async function(){'
            f'var files={listing};'
            'for (var i=0;i<files.length;i++){'
            '  var name=files[i][0], url=files[i][1], text="";'
            '  try { text = await (await fetch(url)).text(); }'
            '  catch (e) { window.__errs.push("READ " + name + ": " + e); continue; }'
            # ES 모듈(vite 번들, 압축돼 한 줄)은 Function 으로 못 읽는다 — 번들 폴더와 import/export 꼴은 건너뛴다
            '  if (name.indexOf("label_editor/") === 0 || /(^|[;}\\s])(import|export)\\s*[{*(\\w"\']/.test(text)) { window.__skipped = (window.__skipped||0) + 1; continue; }'
            '  try { new Function(text); }'
            '  catch (e) { window.__errs.push(String(e.name) + ": " + name + ": " + e.message); }'
            '}'
            'document.documentElement.setAttribute("data-errs", JSON.stringify(window.__errs));'
            'document.documentElement.setAttribute("data-parsed", String(files.length));'
            '})();</script>'
        )
        page = self.tmp / 'static_all.html'
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8">{_HARNESS_HEAD}</head>'
                        f'<body>{runner}</body></html>', encoding='utf-8')
        errs, dom = run_chrome(page, want_dom=True)
        self.assertIn(f'data-parsed="{len(files)}"', dom, '전부 읽기 전에 끝났다')
        bad = [e for e in errs if e.startswith('SyntaxError') or e.startswith('READ')]
        self.assertEqual(bad, [], '\n'.join(bad))

    def _render_and_check(self, name, url):
        res = self.client.get(url, follow=True)
        self.assertEqual(res.status_code, 200, (name, res.status_code))
        text = res.content.decode('utf-8')
        # /static/... 를 파일 주소로 — 판(?v=...)은 file:// 에서 뜻이 없다
        base = _STATIC_DIR.as_uri() + '/'
        text = re.sub(r'(["\'])/static/([^"\'?]+)(\?[^"\']*)?\1',
                      lambda m: m.group(1) + base + m.group(2) + m.group(1), text)
        text = re.sub(r'<head([^>]*)>', lambda m: f'<head{m.group(1)}>{_HARNESS_HEAD}', text, count=1)
        page = self.tmp / f'{name}.html'
        page.write_text(text, encoding='utf-8')
        bad = syntax_errors(run_chrome(page))
        self.assertEqual(bad, [], f'{name}: ' + '\n'.join(bad))

    def test_제품_화면의_인라인_JS_가_문법에_맞다(self):
        from v1.label.models import MyLabel

        res = self.client.get(reverse('products:product_create'))
        self.assertEqual(res.status_code, 302)
        label = MyLabel.objects.filter(user_id=self.user).latest('my_label_id')
        self._render_and_check('product_detail', res['Location'])
        self._render_and_check('bom_editor', reverse('bom:bom_editor', kwargs={'label_id': label.my_label_id}))
        self._render_and_check('label_preview',
                               reverse('label:preview_popup') + f'?label_id={label.my_label_id}&in_tab=1')

    def test_원료_관리_화면의_인라인_JS_가_문법에_맞다(self):
        self._render_and_check('my_ingredients', reverse('label:my_ingredient_list_combined'))
