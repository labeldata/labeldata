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
        self.proc = subprocess.Popen(
            [chrome_path(), '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
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
        self.send('Page.enable')
        self.send('Page.navigate', url=url)
        time.sleep(settle)

    def shot(self, path):
        data = self.send('Page.captureScreenshot', format='png')['data']
        Path(path).write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.kill()


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
                return new Promise(res => setTimeout(() => {
                  const top = sel => [...document.querySelectorAll(sel)].map(tr => Math.round(tr.getBoundingClientRect().top));
                  res(JSON.stringify({
                    master: top('#bom-grid .ht_master .htCore tbody tr'),
                    left: top('#bom-grid .ht_clone_left .htCore tbody tr'),
                    scrollTop: holder.scrollTop }));
                }, 800));
            })()"""
            for scroll in (0, 300):
                raw = chrome.js(geo % scroll)
                self.assertNotEqual(raw, 'NO GRID', '표가 그려지지 않았다')
                got = json.loads(raw)
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
