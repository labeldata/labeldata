# -*- coding: utf-8 -*-
"""
헤드리스 크롬을 DevTools 프로토콜로 몰아 **화면을 실제로 돌려 본다.**

문자열 시험은 코드가 그 자리에 있는지만 본다. 배합표의 줄 번호가 내용과
어긋나는 것 같은 일은 그려 봐야 안다. 여기서는 라이브 서버에 화면을 띄우고,
표를 스크롤한 뒤 본문 판과 왼쪽 번호 판의 줄 위치를 잰다.

크롬이나 websocket-client 가 없으면(운영 서버) 건너뛴다.
로컬: `pip install websocket-client` (requirements 에는 넣지 않는다 — 시험 전용).
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from django.conf import settings as _st
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

try:
    import requests
    import websocket
except ImportError:      # pragma: no cover — 운영 서버
    requests = websocket = None

_CHROME_CANDIDATES = [
    os.environ.get('CHROME_PATH', ''),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
]


def chrome_path():
    for cand in _CHROME_CANDIDATES:
        if cand and os.path.exists(cand):
            return cand
    return shutil.which('chrome') or shutil.which('google-chrome') or shutil.which('chromium')


class AutoLoginForTests:
    """시험 전용 미들웨어 — `?__as=<username>` 이면 그 사용자로 로그인한다.
    크롬에 세션 쿠키를 심을 길이 없어서다. 시험 설정에서만 끼운다."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = request.GET.get('__as')
        if name:
            user = User.objects.filter(username=name).first()
            if user:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return self.get_response(request)


class Chrome:
    """DevTools 로 모는 헤드리스 크롬 한 장."""

    def __init__(self, port=9333, size='1300,900'):
        # **제 방을 하나 새로 쓴다.** 프로필을 안 주면 크롬은 이미 떠 있는
        # 판(사람이 쓰던 창이든 앞 시험이 남긴 것이든)에 붙어 버린다 — 그러면
        # 우리가 띄운 것이 아닌 창을 몰게 되고, 끝에 그것을 닫을 수도 없다.
        self._profile = tempfile.mkdtemp(prefix='ezchrome-')
        self.proc = subprocess.Popen(
            [chrome_path(), '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
             f'--user-data-dir={self._profile}', '--no-default-browser-check',
             f'--remote-debugging-port={port}', f'--window-size={size}', '--hide-scrollbars', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(60):
            try:
                pages = requests.get(f'http://127.0.0.1:{port}/json', timeout=1).json()
                page = next(p for p in pages if p['type'] == 'page')
                break
            except Exception:
                time.sleep(0.25)
        if page is None:
            self.close()
            raise RuntimeError('크롬 DevTools 에 붙지 못했다')
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'], suppress_origin=True)
        self.n = 0

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == self.n:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result', {})

    def js(self, expr):
        r = self.send('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')

    def goto(self, url, settle=4.0):
        """
        **다 실렸는지 보고 나서 쉰다.**

        예전에는 navigate 뒤에 고정으로 `settle` 초를 쉬었다. 이 화면들은
        <head> 에서 CDN(부트스트랩·핸슨테이블)을 받는데, 그것이 느린 날에는
        4 초가 지나도 브라우저가 아직 <head> 에 머물러 `document.body` 조차
        없다 — 그러면 시험은 화면 탓이 아닌 일로 붉어지고, 붉은 까닭이
        '표가 그려지지 않았다' 로 적혀 사람을 엉뚱한 곳으로 보낸다.

        readyState 가 complete 가 될 때까지 본 다음, 그 뒤에 `settle` 만큼
        쉰다(DOMContentLoaded 뒤에 도는 초기화가 있다). 빠른 날에는 예전과
        걸리는 시간이 같다.
        """
        self.send('Page.enable')
        self.send('Page.navigate', url=url)
        self.wait_loaded(timeout=max(settle * 6, 30))
        time.sleep(settle)

    def wait_loaded(self, timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.js('document.readyState === "complete" && !!document.body'):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def wait_for(self, expr, timeout=20.0):
        """`expr` 이 참이 될 때까지 기다린다(참이 됐는지 돌려준다)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.js(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def shot(self, path):
        data = self.send('Page.captureScreenshot', format='png')['data']
        Path(path).write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        # **딸린 것까지 닫는다.** 크롬은 자식 프로세스를 여럿 띄우는데
        # `proc.kill()` 은 띄운 것 하나만 죽인다 — 남은 것들이 디버깅 포트를
        # 붙들고 있으면 다음 시험이 붙지 못하거나, 붙은 뒤 소켓이 끊긴다
        # (실제로 '소켓이 끊겼다' 로 붉어졌다).
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.proc.kill()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(self._profile, ignore_errors=True)


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 배합표를_그려_본다(StaticLiveServerTestCase):
    """
    배합 탭(iframe) 의 표를 스크롤한 뒤 본문 판과 왼쪽 번호 판의 줄 위치가
    같은지 본다. autoRowSize 를 켜 두었을 때 접힌 줄에서 몇 px 씩 어긋나
    내려갈수록 번호가 밀렸다 — 그 회귀를 여기서 잡는다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')

    def test_줄_번호_판이_본문과_같은_자리에_선다(self):
        from v1.bom.models import ProductBOM
        from v1.label.models import MyLabel

        u = User.objects.create_user('browser', password='x')
        lab = MyLabel.objects.create(user_id=u, my_label_name='그려 보는 제품')
        long = ('베이컨스타일탑핑[베이컨류{돼지고기 }, 돼지고기/외국산, 천일염, '
                '혼합제제(폴리인산나트륨, 메타인산나트륨, 피로인산나트륨), L-글루탐산나트륨 ]')
        names = ['크림치즈스프레드', '올리고당', long, '할라피뇨페퍼/멕시코산[할라피뇨, 천일염, 초산]',
                 '리큐르', '레몬주스', '구연산삼나트륨', '폴리인산나트륨', '크라프트 크림치즈(Kraft Cream Cheese)',
                 '크림치즈스프레드제품', '크림치즈스프레드 베이컨할라피뇨', '소금 & 우유크림 랑드샤']
        for i, name in enumerate(names):
            ProductBOM.objects.create(
                parent_label=lab, created_by=u, ingredient_name=name,
                raw_material_name=(long if i in (2, 8, 10, 11) else name),
                food_type=('유가공품 > 치즈류(*축산물가공품) > 가공치즈' if i == 10 else ''),
                manufacturer=('(주)샤니 경기도 화성시 정남면 재갈길 160' if i in (8, 10, 11) else ''),
                allergens=('밀, 대두, 우유, 알류, 쇠고기' if i == 11 else ''),
                sort_order=i, active_yn=True)

        url = f'{self.live_server_url}/bom/label/{lab.my_label_id}/editor/?__as=browser'
        chrome = Chrome()
        try:
            chrome.goto(url)
            geo = """(function(){
                const holder = document.querySelector('#bom-grid .ht_master .wtHolder');
                if (!holder) return 'NO GRID';
                holder.scrollTop = %d;
                /* **글꼴이 다 실린 뒤에 잰다.** 글꼴이 바뀌면 줄 높이가 바뀌고,
                   그 사이에 재면 본문 판은 새 높이, 왼쪽 판은 옛 높이로 잡혀
                   '번호가 어긋난다' 로 붉어진다 — 화면 탓이 아닌 붉음이다. */
                return document.fonts.ready.then(() => new Promise(res => setTimeout(() => {
                  const top = sel => [...document.querySelectorAll(sel)].map(tr => Math.round(tr.getBoundingClientRect().top));
                  res(JSON.stringify({
                    master: top('#bom-grid .ht_master .htCore tbody tr'),
                    left: top('#bom-grid .ht_clone_left .htCore tbody tr'),
                    scrollTop: holder.scrollTop }));
                }, 800)));
            })()"""
            # 표가 아예 없으면 **화면 탓이 아니다.** 핸슨테이블은 CDN 에서
            # 오는데, 그것을 못 받은 날에도 '표가 그려지지 않았다' 로 붉어져
            # 사람을 엉뚱한 곳으로 보냈다. 받았는지 먼저 묻는다.
            if not chrome.js("typeof Handsontable !== 'undefined'"):
                self.skipTest('핸슨테이블 CDN 을 받지 못했다 — 이 시험은 그것이 있어야 한다')

            for scroll in (0, 300):
                #
                # **가라앉은 값을 본다.** 글꼴·칸 너비가 늦게 실리면 본문 판이
                # 먼저 줄고 왼쪽 판이 한 그림 뒤에 따라온다 — 그 틈에 재면
                # 어긋난 것으로 잡힌다. 진짜 회귀는 기다려도 가라앉지 않으므로
                # 이 되풀이가 지켜 주는 것은 그대로다.
                got = None
                for _ in range(6):
                    raw = chrome.js(geo % scroll)
                    self.assertNotEqual(raw, 'NO GRID', '표가 그려지지 않았다')
                    got = json.loads(raw)
                    if got['master'] == got['left']:
                        break
                    time.sleep(0.5)
                self.assertGreater(len(got['master']), 5, got)
                self.assertEqual(got['master'], got['left'],
                                 f'scrollTop={scroll}: 본문 줄과 번호 판 줄의 위치가 다르다')

            # 칸 고르기 단추는 표 왼쪽 위 모서리 안에 있고, 누르면 판이 열린다
            corner = chrome.js("""(function(){
                const all = [...document.querySelectorAll('.bom-cornerbtn')];
                if (!all.length) return 'NO BUTTON';
                // '.bom-cornerbtn' 자신도 corner 를 품은 이름이라, 겹침판 이름으로 고른다
                const CORNER = '.ht_clone_top_left_corner, .ht_clone_top_inline_start_corner';
                const btn = all.find(b => b.closest(CORNER)) || all[0];
                const th = btn.closest('th');
                const panel = document.getElementById('bom-col-picker');
                const before = panel.hidden;
                btn.click();
                return JSON.stringify({inCorner: !!(th && th.closest(CORNER)),
                                       before: before, after: panel.hidden,
                                       items: panel.querySelectorAll('input[data-col]').length});
            })()""")
            self.assertNotEqual(corner, 'NO BUTTON', '모서리 단추가 없다')
            c = json.loads(corner)
            self.assertTrue(c['inCorner'], c)
            self.assertTrue(c['before'] and not c['after'], c)
            self.assertGreater(c['items'], 5, c)
        finally:
            chrome.close()


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 도움말이_틀_안을_가리킨다(StaticLiveServerTestCase):
    """
    제품 상세의 배합 탭에서 [이 화면 사용법] 을 열면 첫 걸음이 **배합 탭**의
    것이고, 강조 테두리가 iframe 안의 표(#bom-grid) 위에 놓이는지 본다.
    문자열 시험으로는 좌표를 더하는 셈이 맞는지 알 수 없다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')

    def test_배합_탭에서_열면_표를_가리킨다(self):
        from django.test import Client

        from v1.bom.models import ProductBOM
        from v1.label.models import MyLabel

        u = User.objects.create_user('coach', password='x')
        c = Client(); c.force_login(u)
        purl = c.get('/products/create/')['Location']          # 임시 제품 하나
        lab = MyLabel.objects.filter(user_id=u).latest('my_label_id')
        for i, name in enumerate(['설탕', '밀가루', '버터']):
            ProductBOM.objects.create(parent_label=lab, created_by=u, ingredient_name=name,
                                      usage_ratio=30, sort_order=i, active_yn=True)

        url = f'{self.live_server_url}{purl}{"&" if "?" in purl else "?"}__as=coach'
        chrome = Chrome(port=9334)
        try:
            chrome.goto(url, settle=4.0)
            # 불러오기 창이 저절로 뜬다(새 제품) — 닫고 배합 탭으로
            chrome.js("""(function(){
                document.querySelectorAll('.modal.show').forEach(m => bootstrap.Modal.getOrCreateInstance(m).hide());
                var t = document.querySelector('button[data-bs-target="#tab-bom"]');
                if (t) bootstrap.Tab.getOrCreateInstance(t).show();
                return 'tab';
            })()""")
            # iframe 이 실리고 표가 그려질 때까지 — 고정 시간으로 기다리면
            # CDN 이 느린 날 여기서 붉어진다(그리고 '표가 없다' 로 적힌다)
            #
            # **자리를 잡을 때까지** 본다. 칸이 생긴 것만으로는 이르다 — 탭을
            # 막 펼친 직후에는 폭이 0 이라, 재면 강조 테두리와 표의 자리가
            # 둘 다 0 으로 잡히고 '가리키지 못했다' 로 붉어진다.
            ready = """(function(){
                var f = document.getElementById('bomEditorFrame');
                if (!f || !f.contentDocument) return false;
                if (f.contentDocument.readyState !== 'complete') return false;
                var g = f.contentDocument.getElementById('bom-grid');
                if (!g) return false;
                var r = g.getBoundingClientRect();
                return r.width > 100 && r.height > 50;
            })()"""
            if not chrome.wait_for(ready, timeout=40):
                # 핸슨테이블은 CDN 에서 온다 — 못 받은 날은 화면 탓이 아니다
                got_hot = chrome.js("""(function(){
                    var f = document.getElementById('bomEditorFrame');
                    var w = f && f.contentWindow;
                    return !!(w && typeof w.Handsontable !== 'undefined');
                })()""")
                if not got_hot:
                    self.skipTest('배합표(핸슨테이블 CDN)를 받지 못했다')
                self.fail('배합표가 자리를 잡지 못했다')
            time.sleep(2)
            raw = chrome.js("""(function(){
                if (!window.ezCoach) return 'NO COACH';
                window.ezCoach.start('detail');
                return new Promise(res => setTimeout(() => {
                    const spot = document.querySelector('.ezc-spot');
                    const box = document.querySelector('.ezc-box');
                    const frame = document.getElementById('bomEditorFrame');
                    const grid = frame && frame.contentDocument && frame.contentDocument.getElementById('bom-grid');
                    if (!spot || !box || !grid) return res(JSON.stringify({spot: !!spot, box: !!box, grid: !!grid}));
                    const s = spot.getBoundingClientRect(), g = grid.getBoundingClientRect(), f = frame.getBoundingClientRect();
                    res(JSON.stringify({title: (box.querySelector('b')||{}).textContent,
                        spot: [Math.round(s.left), Math.round(s.top), Math.round(s.width), Math.round(s.height)],
                        grid: [Math.round(g.left + f.left), Math.round(g.top + f.top), Math.round(g.width), Math.round(g.height)]}));
                }, 1500));
            })()""")
            got = json.loads(raw)
            self.assertIn('title', got, got)
            self.assertEqual(got['title'], '표 — 엑셀처럼 바로 칩니다', got)     # 지금 보는 탭의 첫 걸음
            sx, sy, sw, sh = got['spot']; gx, gy, gw, gh = got['grid']
            # 강조 테두리(padding 6)가 표를 감싼다
            self.assertLessEqual(abs(sx - (gx - 6)), 3, got)
            self.assertLessEqual(abs(sy - (gy - 6)), 3, got)
            self.assertLessEqual(abs(sw - (gw + 12)), 3, got)
        finally:
            chrome.close()
