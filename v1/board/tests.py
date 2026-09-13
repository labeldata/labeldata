# -*- coding: utf-8 -*-
"""게시판 — 목록 쪽수·글쓰기 폼."""
from django.contrib.auth.models import User
from django.test import TestCase



class 게시판_쪽수와_오류_표시(TestCase):
    """
    · `?per_page=abc` 는 ValueError, `?per_page=0` 은 ZeroDivisionError —
      주소의 값을 검증 없이 Paginator 로 넘겼다. 둘 다 500 이다.
    · `?per_page=99999` 는 목록을 통째로 한 쪽에 그린다
    · clean() 이 만든 검증 오류('제목을 입력해주세요' 등)는 칸에 붙지 않는
      비필드 오류인데, 화면에 그 자리가 없어 **한 번도 뜨지 않았다** —
      저장을 눌렀는데 아무 일도 안 일어난 것처럼 보인다
    · «공지사항» 체크박스가 장식이었다. 바로 옆 «구분» select 가 같은 것을
      정하고 form_valid 가 그 값으로 is_notice 를 무조건 덮어썼다
    """

    def setUp(self):
        self.user = User.objects.create_user(username='bdu', password='x')
        self.staff = User.objects.create_user(
            username='bds', password='x', is_staff=True)
        self.client.force_login(self.user)

    # ── 쪽수 ────────────────────────────────────────────────────────────────
    def test_이상한_per_page_에_500_이_아니다(self):
        for q in ('abc', '0', '-1', '', '99999999999999999999'):
            r = self.client.get('/board/?per_page=' + q)
            self.assertEqual(r.status_code, 200, f'per_page={q}')

    def test_고르개에_없는_수는_기본값으로_돈다(self):
        r = self.client.get('/board/?per_page=99999')
        self.assertEqual(r.context['paginator'].per_page, 10)

    def test_고르개에_있는_수는_그대로_쓴다(self):
        r = self.client.get('/board/?per_page=20')
        self.assertEqual(r.context['paginator'].per_page, 20)

    def test_화면의_고르개가_실제로_쓰인_값을_켠다(self):
        """주소에 적힌 것을 그대로 넣으면 abc 일 때 아무것도 안 켜진다."""
        self.assertEqual(self.client.get('/board/?per_page=abc').context['per_page'], '10')
        self.assertEqual(self.client.get('/board/?per_page=20').context['per_page'], '20')

    # ── 비필드 오류 ─────────────────────────────────────────────────────────
    def test_칸에_안_붙는_오류도_화면에_뜬다(self):
        r = self.client.post('/board/create/',
                             {'category': '오류 제보', 'title': '  ', 'content': '  '})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['form'].non_field_errors())
        self.assertIn('non_field_errors', self._form_block())

    def _form_block(self):
        from pathlib import Path

        from django.conf import settings as dj

        return (Path(dj.BASE_DIR) / 'templates/board/form.html'
                ).read_text(encoding='utf-8')

    # ── 공지사항 ────────────────────────────────────────────────────────────
    def test_장식_체크박스를_걷어냈다(self):
        from v1.board.views import BoardForm

        self.assertNotIn('is_notice', BoardForm.Meta.fields)
        self.assertNotIn('{{ form.is_notice }}', self._form_block())

    def test_구분으로_공지사항이_정해진다(self):
        from v1.board.models import Board

        self.client.force_login(self.staff)
        self.client.post('/board/create/',
                         {'category': '공지사항', 'title': '알림', 'content': '내용'})
        b = Board.objects.get(title='알림')
        self.assertTrue(b.is_notice)

    def test_일반_구분은_공지가_되지_않는다(self):
        from v1.board.models import Board

        self.client.force_login(self.staff)
        self.client.post('/board/create/',
                         {'category': '기능 요청', 'title': '바람', 'content': '내용'})
        b = Board.objects.get(title__contains='바람')
        self.assertFalse(b.is_notice)

    def test_일반_사용자는_공지를_못_쓴다(self):
        from v1.board.models import Board

        r = self.client.post('/board/create/',
                             {'category': '공지사항', 'title': '몰래', 'content': '내용'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Board.objects.filter(title='몰래').exists())


class 알림_드롭다운이_남의_글자를_실행하지_않는다(TestCase):
    """
    알림 문구를 템플릿 문자열로 지어 `innerHTML` 에 꽂았다. 그 문구에는
    **다른 사용자가 친 자유 문자열**이 들어간다 — 반려 사유, 바꾼 사람 이름,
    제품명이 그대로 온다(ProductNotification.objects.create).

    이름에 작은따옴표 하나만 들어가도 `onclick` 이 깨졌고,
    `<img src=x onerror=…>` 면 스크립트가 돌았다. 이 조각은 **모든 V2
    화면**의 topbar 에 있다.
    """

    JS = 'templates/includes/_topbar_account.html'

    def _js(self):
        import re
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / self.JS).read_text(encoding='utf-8')
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        return re.sub(r'^\s*//.*$', '', text, flags=re.M)

    def test_문자열로_마크업을_짓지_않는다(self):
        js = self._js()
        i = js.index('function renderNotifications')
        block = js[i:js.index('function fetchNotifications')]
        # 값이 마크업 문자열 안으로 들어가는 자리가 없어야 한다
        self.assertNotIn('${n.message}', block)
        self.assertNotIn('${n.label_name}', block)
        self.assertNotIn('onclick="notifRead', block)

    def test_값을_textContent_로_넣는다(self):
        js = self._js()
        i = js.index('function renderNotifications')
        block = js[i:js.index('function fetchNotifications')]
        self.assertIn('msg.textContent = n.message', block)
        self.assertIn('createElement', block)
        self.assertIn("addEventListener('click'", block)

    def test_읽음_처리가_실패해도_가려던_곳으로_간다(self):
        js = self._js()
        i = js.index('window.notifRead')
        block = js[i:i + 900]
        self.assertIn('.catch(', block)
        self.assertIn('function go()', block)


class 게시판_권한_거부가_빈_화면이_아니다(TestCase):
    """
    `HttpResponseForbidden` 을 **return** 하면 그 응답이 그대로 브라우저로
    간다 — Django 의 handler403 은 **예외**가 올라올 때만 돈다. 그래서 남의
    글 주소로 수정·삭제를 열면 본문 0바이트짜리 **완전히 빈 흰 화면**이 떴다.
    돌아갈 링크도 사이드바도 없었다.

    이 저장소는 403 을 404 로 위장하기로 정해 두었는데(custom_403)
    게시판만 그 규약 밖에 있었다.
    """

    def setUp(self):
        from v1.board.models import Board

        self.author = User.objects.create_user(username='bauth', password='x')
        self.other = User.objects.create_user(username='both', password='x')
        self.post = Board.objects.create(
            title='[기능 요청] 남의 글', content='내용', author=self.author)
        self.secret = Board.objects.create(
            title='[오류 제보] 비밀', content='내용',
            author=self.author, is_hidden=True)

    def test_남의_글_수정은_빈_화면이_아니다(self):
        self.client.force_login(self.other)
        r = self.client.get('/board/%d/update/' % self.post.pk)
        self.assertNotEqual(r.status_code, 200)
        # 빈 본문이면 안 된다 — 오류 화면이 그려져야 한다
        self.assertGreater(len(r.content), 200)

    def test_남의_글_삭제도_마찬가지다(self):
        self.client.force_login(self.other)
        r = self.client.get('/board/%d/delete/' % self.post.pk)
        self.assertNotEqual(r.status_code, 200)
        self.assertGreater(len(r.content), 200)

    def test_남의_비밀글은_여전히_못_본다(self):
        self.client.force_login(self.other)
        r = self.client.get('/board/%d/' % self.secret.pk)
        self.assertNotEqual(r.status_code, 200)
        self.assertGreater(len(r.content), 200)

    def test_작성자는_제_글을_연다(self):
        self.client.force_login(self.author)
        self.assertEqual(
            self.client.get('/board/%d/' % self.secret.pk).status_code, 200)
        self.assertEqual(
            self.client.get('/board/%d/update/' % self.post.pk).status_code, 200)

    def test_남은_HttpResponseForbidden_이_없다(self):
        from pathlib import Path

        from django.conf import settings as dj

        text = (Path(dj.BASE_DIR) / 'board/views.py').read_text(encoding='utf-8')
        # 왜 그랬는지 적은 문서화 주석에도 그 이름이 나온다 — 코드만 본다
        self.assertNotIn('return HttpResponseForbidden', text)
        self.assertNotIn('import HttpResponseForbidden', text)


class 비밀글_첨부는_미디어_주소로도_새지_않는다(TestCase):
    """
    게시판 뷰(download_file)는 `is_hidden` 을 검사하는데 미디어 쪽 규칙은
    `_allow_authenticated` — **로그인 여부만** 봤다. 문 하나는 잠그고 다른
    문은 열어 둔 셈이다.

    게다가 화면이 스스로 그 우회로를 그려 준다 — detail 의 <img> 와 form 의
    첨부 링크가 원본 /media/ 주소를 쓴다.
    """

    def setUp(self):
        from v1.board.models import Board

        self.author = User.objects.create_user(username='mauth', password='x')
        self.other = User.objects.create_user(username='moth', password='x')
        self.staff = User.objects.create_user(
            username='mstaff', password='x', is_staff=True)
        self.secret = Board.objects.create(
            title='비밀', content='내용', author=self.author, is_hidden=True,
            attachment='board_files/secret.pdf')
        self.open_post = Board.objects.create(
            title='공개', content='내용', author=self.author,
            attachment='board_files/open.pdf')

    def _allowed(self, user, path):
        from django.test import RequestFactory

        from v1.common.media_access import _check_board_file

        req = RequestFactory().get('/media/' + path)
        req.user = user
        return _check_board_file(req, path)

    def test_남은_비밀글_첨부를_못_받는다(self):
        self.assertFalse(self._allowed(self.other, 'board_files/secret.pdf'))

    def test_작성자는_받는다(self):
        self.assertTrue(self._allowed(self.author, 'board_files/secret.pdf'))

    def test_관리자도_받는다(self):
        self.assertTrue(self._allowed(self.staff, 'board_files/secret.pdf'))

    def test_공개글_첨부는_로그인만_하면_받는다(self):
        self.assertTrue(self._allowed(self.other, 'board_files/open.pdf'))

    def test_어느_글에도_안_붙은_파일은_막는다(self):
        self.assertFalse(self._allowed(self.staff, 'board_files/nowhere.pdf'))

    def test_규칙표가_그_함수를_쓴다(self):
        from v1.common.media_access import ACCESS_RULES, _check_board_file

        rules = dict(ACCESS_RULES)
        self.assertIs(rules['board_files/'], _check_board_file)
        self.assertIs(rules['board_images/'], _check_board_file)
