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
