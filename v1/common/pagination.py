"""
목록 화면의 페이지 단추를 고르는 규칙.

부적합·처분 알림이 제 views.py 안에 `_page_window` 로 들고 있던 것을 여기로
옮겼다. 같은 계산을 다른 화면도 해야 하는데(공용 페이지네이션 조각이 전부
이 창을 쓴다), 한쪽 앱 안에 두면 다른 앱이 import 하기가 어색하다.
"""


def page_window(page_obj, radius=2):
    """
    페이지 단추에 실제로 그려질 것만 골라 둔다 — [1, …, 8, 9, 10, 11, 12, …, 120] 꼴.

    예전에는 템플릿이 paginator.page_range 를 통째로 돌면서 {% if %} 사슬로 대부분을
    버렸다. 수거검사 공개 목록은 원본 전체가 모수라 6만 건이면 3,000쪽이고, 단추
    일곱 개를 그리자고 3,000번을 돌며 |add 필터를 만 오천 번 태웠다. 실측으로 이
    화면 렌더 시간의 3분의 2가 여기였다(news_list.html 77ms 중 62ms). 원본은 계속
    쌓이므로 이 비용도 계속 는다.

    고르는 규칙은 예전 {% if %} 사슬과 같은 순서·같은 결과다.
      ① 현재 쪽  ② 현재 ±2  ③ 첫 쪽·끝 쪽  ④ 현재 ±3 자리에만 '…'
    """
    if page_obj is None:
        return []
    last = page_obj.paginator.num_pages
    cur  = page_obj.number
    candidates = {1, last, cur - radius - 1, cur + radius + 1}
    candidates.update(range(cur - radius, cur + radius + 1))

    window = []
    for n in sorted(c for c in candidates if 1 <= c <= last):
        if n == cur:
            window.append({'n': n, 'active': True})
        elif cur - radius <= n <= cur + radius:
            window.append({'n': n})
        elif n == 1 or n == last:
            window.append({'n': n})
        elif n in (cur - radius - 1, cur + radius + 1):
            window.append({'ellipsis': True})
    return window
