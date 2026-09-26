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


def kill_stray_chromes():
    """
    **우리가 띄운 헤드리스 크롬만** 닫는다.

    하위 프로세스가 끊기면 그 안의 `chrome.close()` 가 돌지 않아 크롬이 남는다.
    남은 것들이 기계를 붙들면 뒤에 오는 시험이 줄줄이 시간 초과로 붉어진다.

    사람이 쓰는 크롬은 건드리지 않는다 — `--user-data-dir` 에 우리가 만든
    임시 프로필(`ezchrome-`)이 적혀 있는 것만 고른다. 닫은 개수를 돌려준다.
    """
    if os.name != 'nt':
        subprocess.run(['pkill', '-f', 'ezchrome-'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    query = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
             "Where-Object { $_.CommandLine -like '*ezchrome-*' } | "
             "Select-Object -ExpandProperty ProcessId")
    try:
        found = subprocess.run(['powershell', '-NoProfile', '-Command', query],
                               capture_output=True, timeout=60)
    except Exception:
        return 0
    pids = [w for w in found.stdout.decode('utf-8', 'replace').split() if w.isdigit()]
    for pid in pids:
        subprocess.run(['taskkill', '/PID', pid, '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return len(pids)


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


# ══════════════════════════════════════════════════════════════════════════
#  아래 넷은 **문자열 시험이 못 보는 것**만 본다.
#
#  "그 자리에 markBomEdited() 가 적혀 있다" 는 원본을 읽으면 안다. 그런데
#  정말로 빗장이 서는지는 **눌러 봐야** 안다 — 처리기가 앞에서 돌아 나가거나,
#  다른 곳에서 bomEdited 를 되돌리거나, 단추가 가려져 눌리지 않을 수 있다.
#  그 셋은 원본에 다 적혀 있어도 일어난다.
# ══════════════════════════════════════════════════════════════════════════


def _bom_rows(label, user, ratios=(3, 7, 25)):
    from v1.bom.models import ProductBOM
    names = ['설탕', '밀가루', '버터', '소금', '물엿']
    for i, ratio in enumerate(ratios):
        ProductBOM.objects.create(
            parent_label=label, created_by=user, ingredient_name=names[i % len(names)],
            raw_material_name=names[i % len(names)], usage_ratio=ratio,
            sort_order=i, active_yn=True)


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 배합_화면에서_고친_적이_실제로_선다(StaticLiveServerTestCase):
    """
    `bomEdited` 가 서 있지 않으면 탭을 떠날 때 `saveIfEdited` 가 아무것도 하지
    않는다 — 고친 것이 조용히 사라진다. 그 빗장을 `afterChange` 하나가 세우는데
    그것은 `loadData`·`palette`·`syncPanel` 을 건너뛴다.

    여기서는 **눌러 보고** `saveIfEdited()` 가 건너뛰는지 묻는다. 건너뛴다고
    답하면 그 길에서 고친 것은 사라진다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        self.user = User.objects.create_user('browser', password='x')
        from v1.label.models import MyIngredient, MyLabel
        self.label = MyLabel.objects.create(user_id=self.user, my_label_name='눌러 보는 제품')
        # 보관함에 한 줄 — [추가] 를 누르는 길이 살아 있어야 그 시험을 할 수 있다
        MyIngredient.objects.create(user_id=self.user, prdlst_nm='보관함 원료',
                                    prdlst_dcnm='기타가공품', delete_YN='N')
        # 배합비가 **올라가는** 순서다 — 정렬을 누르면 순서가 실제로 바뀐다
        _bom_rows(self.label, self.user, ratios=(3, 7, 25))
        self.url = (f'{self.live_server_url}/bom/label/{self.label.my_label_id}'
                    f'/editor/?__as=browser')

    # 표가 뜬 뒤여야 누를 수 있다.
    #
    # `hot` 은 화면 안쪽 변수다(전역이 아니다). 시험을 위해 전역을 새로 만들지
    # 않는다 — 사람이 쓰는 길로만 몬다. 줄을 고르는 것도 칸을 실제로 누른다.
    _READY = """(function(){
        return !!(window.saveIfEdited && window.clearAllRows
                  && document.querySelector('#bom-grid .ht_master .htCore tbody tr td'));
    })()"""

    # 칸을 누른다 — 핸슨테이블은 mousedown 으로 고른다
    _PICK = """(function(){
        var tr = document.querySelector('#bom-grid .ht_master .htCore tbody tr');
        var td = tr && tr.querySelector('td');
        if (!td) return 'NO CELL';
        ['mousedown', 'mouseup', 'click'].forEach(function (t) {
            td.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true,
                                                view: window, button: 0}));
        });
        return 'picked';
    })()"""

    _ASK = "window.saveIfEdited().then(r => JSON.stringify({skipped: !!(r && r.skipped)}))"

    def _fresh(self, chrome):
        chrome.goto(self.url, settle=2.0)
        if not chrome.wait_for(self._READY, timeout=30):
            if not chrome.js("typeof Handsontable !== 'undefined'"):
                self.skipTest('핸슨테이블 CDN 을 받지 못했다')
            self.fail('배합표가 뜨지 않았다')

    def _skipped_after(self, chrome, action):
        self._fresh(chrome)
        self.assertEqual(chrome.js(action + "; 'done'"), 'done', action)
        time.sleep(0.6)
        return json.loads(chrome.js(self._ASK))['skipped']

    def test_눌러_보고_묻는다(self):
        """
        **한 시험으로 몰아 둔 까닭.** StaticLiveServerTestCase 는
        TransactionTestCase 라, 시험 하나가 끝날 때마다 표를 전부 비운다. 그
        값이 화면 한 번 여는 값보다 크다 — 갈래마다 시험을 따로 두면 같은
        것을 보면서 걸리는 시간이 몇 배가 된다. 짚는 자리마다 문구를 단다.
        """
        chrome = Chrome(port=9341)
        try:
            # ⓪ 빗장 자체가 살아 있는가 — 아래가 뜻을 갖기 위한 전제다
            self._fresh(chrome)
            self.assertTrue(json.loads(chrome.js(self._ASK))['skipped'],
                            '아무것도 안 했는데 저장하려 든다')
            # ① 보관함에서 넣기 — 카드의 [추가] 를 실제로 누른다.
            #    끌어 놓기는 합성 DragEvent 의 dataTransfer 가 보호 모드라
            #    `getData` 가 빈 글자를 돌려준다 — 같은 `addItemToGrid` 로
            #    들어가는 [추가] 단추로 본다.
            self._fresh(chrome)
            self.assertTrue(chrome.wait_for(
                "!!document.querySelector('.palette-card button')", timeout=20),
                '보관함 카드가 그려지지 않았다')
            chrome.js("document.querySelector('.palette-card button').click(); 'done'")
            time.sleep(0.8)
            landed = chrome.js(
                "[...document.querySelectorAll('#bom-grid .ht_master .htCore tbody tr')]"
                ".map(tr => tr.innerText).join('|')")
            self.assertIn('보관함 원료', landed, '카드를 눌렀는데 줄이 안 생겼다')
            self.assertFalse(json.loads(chrome.js(self._ASK))['skipped'],
                             '보관함에서 넣은 줄')

            # ② 배합비 순 정렬 (지금 표는 오름차순이라 순서가 바뀐다)
            self.assertFalse(self._skipped_after(chrome, 'window.sortBomByRatio()'), '정렬')

            # ③ 표시명 기준(모든 줄에 함께)
            basis = ("document.querySelector("
                     "'#sheet-summary-type .v2-seg-btn[data-value=\"원재료명\"]').click()")
            self.assertFalse(self._skipped_after(chrome, basis), '표시명 기준')

            # ④ '이 원료만' — 줄을 고른 뒤라야 걸린다
            only = (self._PICK
                    + "; document.getElementById('summaryTypeIngredientName').click()")
            self.assertFalse(self._skipped_after(chrome, only), '이 원료만')

            # ⑤ 전체 지우기 (물어보는 창은 건너뛴다)
            self.assertFalse(self._skipped_after(chrome, 'window.clearAllRows({ask: false})'),
                             '전체 지우기')

            # ⑥ 알레르기 고르기 — 그 칸을 감춰 두면 표를 거치지 않는다
            allergen = (self._PICK + "; document.querySelector("
                        "'#allergen-quick-buttons .quick-allergen-btn').click()")
            self.assertFalse(self._skipped_after(chrome, allergen), '알레르기 고르기')

            # ⑦ 바뀐 것이 없으면 말하지 않는다 — 이미 배합비 순인 표에서
            #    정렬을 누른 것은 고친 것이 아니다
            self._fresh(chrome)
            chrome.js('window.sortBomByRatio()')       # 여기서 내림차순이 된다
            time.sleep(0.6)
            # 저장해 빗장을 내린 다음, 이미 정렬된 표에서 한 번 더 누른다
            chrome.js(self._ASK)
            time.sleep(1.2)
            chrome.js('window.sortBomByRatio()')
            time.sleep(0.6)
            self.assertTrue(json.loads(chrome.js(self._ASK))['skipped'],
                            '순서가 그대로인데 고친 것으로 셌다')

            # ⑧ 단독으로 열면 부모가 하던 단추를 감춘다
            got = json.loads(chrome.js("""(function(){
                var photo = document.getElementById('bomPhotoRegisterBtn');
                var copy = document.getElementById('bomCopyRawmtrlBtn');
                return JSON.stringify({
                    photoThere: !!photo,
                    photoShown: !!(photo && photo.offsetParent !== null),
                    copyShown: !!(copy && copy.offsetParent !== null),
                    deadPanel: !!document.getElementById('context-view')});
            })()"""))
            self.assertTrue(got['photoThere'], got)
            self.assertFalse(got['photoShown'], '단독 화면에서 [사진으로 등록]이 보인다')
            self.assertFalse(got['deadPanel'], '죽은 상세 상자가 남아 있다')
        finally:
            chrome.close()


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 읽기_전용으로_열면_배합표를_고칠_수_없다(StaticLiveServerTestCase):
    """
    표는 readOnly 로 서지만 표 **밖**의 단추는 그대로였다. 불러오기·정렬·전체
    지우기는 `loadData` 로 표를 통째로 바꾸므로 readOnly 를 지나간다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        from v1.label.models import MyLabel
        from v1.products.models import ProductShare, SharePermission

        owner = User.objects.create_user('owner', password='x', email='owner@example.com')
        User.objects.create_user('viewer', password='x', email='viewer@example.com')
        label = MyLabel.objects.create(user_id=owner, my_label_name='빌려 보는 제품')
        _bom_rows(label, owner)
        share = ProductShare.objects.create(
            label=label, recipient_email='viewer@example.com',
            created_by=owner, active_yn=True)
        SharePermission.objects.create(share=share, role_code='VIEWER',
                                       can_edit_label=False)
        self.url = (f'{self.live_server_url}/bom/label/{label.my_label_id}'
                    f'/editor/?__as=viewer')

    def test_고치는_단추가_없고_고르는_단추는_잠긴다(self):
        chrome = Chrome(port=9342)
        try:
            chrome.goto(self.url, settle=2.0)
            if not chrome.wait_for(
                    "!!document.querySelector('#bom-grid .ht_master .htCore tbody tr td')",
                    timeout=30):
                if not chrome.js("typeof Handsontable !== 'undefined'"):
                    self.skipTest('핸슨테이블 CDN 을 받지 못했다')
                self.fail('배합표가 뜨지 않았다')

            got = json.loads(chrome.js("""(function(){
                var shown = sel => {
                    var el = document.querySelector(sel);
                    return !!(el && el.offsetParent !== null);
                };
                var picks = [...document.querySelectorAll(
                    '#allergen-quick-buttons .quick-allergen-btn, #gmoBtnList .gmo-btn,'
                    + ' .summary-type-btn, #allergenToggleBtn, #gmoToggleBtn')];
                return JSON.stringify({
                    load:  shown('[data-bs-target="#loadLabelModal"]'),
                    clear: shown('[onclick="clearAllRows()"]'),
                    sort:  shown('[onclick="sortBomByRatio()"]'),
                    copy:  shown('#bomCopyRawmtrlBtn'),
                    basis: shown('#sheet-summary-type'),
                    readonlyBadge: document.body.textContent.indexOf('읽기 전용') >= 0,
                    picks: picks.length,
                    locked: picks.filter(b => b.disabled).length});
            })()"""))
            for key in ('load', 'clear', 'sort', 'copy', 'basis'):
                self.assertFalse(got[key], f'읽기 전용인데 {key} 단추가 보인다: {got}')
            self.assertTrue(got['readonlyBadge'], got)
            self.assertGreater(got['picks'], 5, got)
            self.assertEqual(got['picks'], got['locked'],
                             f'고르는 단추가 눌린다: {got}')

            # 코드로도 막혔는가 — 창을 열어 둔 채 권한이 바뀌는 길이 있다
            grid = ("[...document.querySelectorAll('#bom-grid .ht_master .htCore tbody tr')]"
                    ".map(tr => tr.innerText).join('|')")
            before = chrome.js(grid)
            chrome.js('window.sortBomByRatio(); window.clearAllRows({ask: false})')
            time.sleep(0.8)
            after = chrome.js(grid)
            self.assertEqual(before, after, '읽기 전용인데 표가 바뀌었다')
        finally:
            chrome.close()


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 영양성분_화면이_사람_말로_말한다(StaticLiveServerTestCase):
    """
    표가 그려지기 전 사용자가 보는 자리에 "LABEL_ID: 3", "📡 API 호출 중" 이
    적혀 있었다. 그리고 '1조각' 과 '1회량' 은 다른 값인데 그 말이 없었다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        from v1.label.models import MyLabel
        u = User.objects.create_user('nut', password='x')
        label = MyLabel.objects.create(user_id=u, my_label_name='영양성분 제품')
        self.url = (f'{self.live_server_url}/products/labels/{label.my_label_id}'
                    f'/nutrition/?__as=nut')

    def test_문구와_1조각_안내(self):
        chrome = Chrome(port=9343)
        try:
            chrome.goto(self.url, settle=3.0)
            # `#loadStatus` 는 **표가 그려지면 사라진다** — resultDisplay 를
            # 통째로 갈아 끼우기 때문이다. 그것을 기다리면 붉어진다.
            self.assertTrue(chrome.wait_for(
                "!!document.getElementById('parallelHint')"
                " && !!document.querySelector('#styleButtons [data-style=\"parallel\"]')",
                timeout=25), '영양성분 화면이 뜨지 않았다')
            time.sleep(2)
            text = chrome.js('document.body.innerText')
            for gone in ('LABEL_ID', '📡', '페이지 상태'):
                self.assertNotIn(gone, text, f'{gone} 이 화면에 보인다')

            # 병행표시를 골랐을 때만 '1조각' 안내가 뜬다
            got = json.loads(chrome.js(r"""(function(){
                var hint = document.getElementById('parallelHint');
                var was = hint.hidden;
                document.querySelector('#styleButtons [data-style="parallel"]').click();
                var on = hint.hidden;
                document.querySelector('#styleButtons [data-style="basic"]').click();
                return JSON.stringify({before: was, whenParallel: on, after: hint.hidden,
                                       text: hint.textContent.replace(/\s+/g, ' ').trim()});
            })()"""))
            self.assertTrue(got['before'], got)
            self.assertFalse(got['whenParallel'], got)
            self.assertTrue(got['after'], got)
            self.assertIn('단위내용량', got['text'])
            self.assertIn('1회 섭취참고량', got['text'])
        finally:
            chrome.close()


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 검증_설정_되돌리기가_정말_되돌린다(StaticLiveServerTestCase):
    """
    [이 탭 값 되돌리기]는 탭 줄에서 이 탭 안으로 옮겼다. 옮기며 둘이 딸려
    나왔다 — 글꼴 기본값의 꼴이 목록 값과 달라 되돌리면 **글꼴 칸이 빈칸**이
    됐고(selectedIndex = -1), 항목명 칸은 되돌리는 목록에 없었다. 원본을 읽어
    서는 빈칸이 되는지 알 수 없다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        from v1.label.models import MyLabel
        u = User.objects.create_user('pv', password='x')
        label = MyLabel.objects.create(user_id=u, my_label_name='미리보기 제품',
                                       prdlst_nm='미리보기 제품')
        self.url = (f'{self.live_server_url}/label/preview/?label_id={label.my_label_id}'
                    f'&in_tab=1&__as=pv')

    def test_되돌려도_글꼴과_항목명_칸이_비지_않는다(self):
        chrome = Chrome(port=9344)
        try:
            chrome.goto(self.url, settle=3.0)
            self.assertTrue(chrome.wait_for(
                "!!document.getElementById('resetSettingsBtn')", timeout=20),
                '되돌리기 단추가 없다')

            got = json.loads(chrome.js(r"""(function(){
                var btn = document.getElementById('resetSettingsBtn');
                var pane = btn.closest('.preview-tab-content');
                document.querySelector('.preview-tab[data-tab="table-settings"]').click();
                var font = document.getElementById('fontFamilySelect');
                var col = document.getElementById('labelColWidthInput');
                font.value = "'Nanum Gothic', sans-serif";
                col.value = '40';
                btn.click();
                return JSON.stringify({
                    pane: pane && pane.id,
                    inTabStrip: !!btn.closest('.preview-tabs'),
                    name: btn.textContent.replace(/\s+/g, ' ').trim(),
                    font: font.value, fontIndex: font.selectedIndex, col: col.value});
            })()"""))
            self.assertEqual(got['pane'], 'table-settings-content', got)
            self.assertFalse(got['inTabStrip'], got)
            self.assertIn('되돌리기', got['name'])
            self.assertGreaterEqual(got['fontIndex'], 0, f'글꼴 칸이 빈칸이 됐다: {got}')
            self.assertTrue(got['font'], got)
            self.assertEqual(got['col'], '24', f'항목명 칸이 되돌아오지 않았다: {got}')

            # 항목 순서 탭의 동작 줄 — '모두' 가 이름에 있고 넷 다 곁말이 있다
            acts = json.loads(chrome.js(r"""(function(){
                document.querySelector('.preview-tab[data-tab="field-order"]').click();
                var btns = [...document.querySelectorAll('#field-order-content .settings-action')];
                return JSON.stringify({
                    names: btns.map(b => b.textContent.replace(/\s+/g, ' ').trim()),
                    tips: btns.filter(b => b.title).length,
                    shown: btns.filter(b => b.offsetParent !== null).length});
            })()"""))
            self.assertEqual(acts['shown'], 4, acts)
            self.assertEqual(acts['tips'], 4, acts)
            self.assertEqual(acts['names'],
                             ['처음 순서로', '모두 켜기·끄기', '모두 반 칸', '모두 한 줄'], acts)
        finally:
            chrome.close()


@override_settings(MIDDLEWARE=list(_st.MIDDLEWARE) + ['v1.common.browser_checks.AutoLoginForTests'])
class 원료_관리_화면의_단추가_하는_일로_불린다(StaticLiveServerTestCase):
    """
    등록 화면의 [연결 표시사항]은 처리기가 붙지 않는 단추였다 — 마크업에서
    뺐지만, 그 화면이 **AJAX 로 갈아 끼우는 칸**이라 정말 없는지는 그려 봐야
    안다. 선택 동작 줄의 이름도 함께 본다.
    """

    def setUp(self):
        if not chrome_path() or websocket is None:
            self.skipTest('헤드리스 크롬 또는 websocket-client 가 없다')
        from v1.label.models import MyIngredient
        u = User.objects.create_user('ing', password='x')
        MyIngredient.objects.create(user_id=u, prdlst_nm='시험 원료', delete_YN='N')
        self.url = f'{self.live_server_url}/label/my-ingredient-list-combined/?__as=ing'

    def test_선택_동작_줄과_등록_화면의_단추(self):
        chrome = Chrome(port=9345)
        try:
            chrome.goto(self.url, settle=3.0)
            got = json.loads(chrome.js(r"""(function(){
                var pick = sel => document.querySelector(sel);
                return JSON.stringify({
                    copy: pick('#bulkCopyBtn').textContent.replace(/\s+/g, ' ').trim(),
                    export: pick('#bulkExportBtn').textContent.replace(/\s+/g, ' ').trim(),
                    copyTip: pick('#bulkCopyBtn').title,
                    exportTip: pick('#bulkExportBtn').title,
                    excelMenu: !!pick('#excelBtn')});
            })()"""))
            self.assertEqual(got['copy'], '사본 만들기', got)
            self.assertEqual(got['export'], '선택만 엑셀로', got)
            self.assertIn('_복사', got['copyTip'])
            self.assertIn('[엑셀]', got['exportTip'])

            # 등록 폼을 그려 본다 — 그 칸은 AJAX 로 갈아 끼운다
            # 이 화면의 등록 폼은 [신규 원료]가 `detailContent` 에 실어 온다
            # (list_combined.js 의 loadNewIngredientForm 은 여기 실리지 않는다).
            self.assertTrue(chrome.wait_for("""(function(){
                var btn = document.getElementById('newBtn');
                if (!btn) return false;
                if (!window.__askedNew) { window.__askedNew = 1; btn.click(); }
                return !!document.querySelector('#detailContent form');
            })()""", timeout=25), '등록 폼이 그려지지 않았다')
            form = json.loads(chrome.js("""(function(){
                var box = document.getElementById('detailContent');
                return JSON.stringify({
                    linked: !!box.querySelector('#linkedLabelsBtn'),
                    head: (box.querySelector('h5') || {}).textContent || ''});
            })()"""))
            self.assertIn('등록', form['head'], form)
            self.assertFalse(form['linked'], '등록 화면에 [연결 표시사항] 단추가 남아 있다')
        finally:
            chrome.close()
