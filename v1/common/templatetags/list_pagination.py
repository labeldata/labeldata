"""
목록 화면의 페이지네이션을 한 벌로 그리는 태그.

같은 일을 하는 마크업이 화면마다 한 벌씩 있었다. 제품 관리·원료 관리·제품
조회·식품첨가물 DB 넷은 생김새까지 같은데도 각자 40줄씩 베껴 들고 있었고,
게시판은 '이전/다음'만 있는 제 모양, 부적합·처분 알림은 rs-page-btn 이라는
제 이름의 또 다른 모양이었다. 그래서 한쪽만 고쳐지는 일이 실제로 났다 —
'처음/끝' 단추가 어느 화면에는 있고 어느 화면에는 없었다.

태그로 둔 까닭은 **페이지 창을 파이썬에서 고르기 위해서**다. 템플릿에서
paginator.page_range 를 통째로 돌며 {% if %} 로 버리는 방식은 쪽수가 많은
목록에서 눈에 띄게 느리다(v1/common/pagination.py 주석 참고).

    {% load list_pagination %}
    {% list_pagination page_obj qs=querystring_without_page unit='원료'
                       per_page_param='items_per_page' per_page=items_per_page %}
"""
from django import template

from v1.common.pagination import page_window

register = template.Library()

# 페이지당 개수 기본 선택지. 화면이 다른 값을 쓰면 per_page_options 로 넘긴다.
_DEFAULT_PER_PAGE_OPTIONS = '10,25,50,100'


@register.inclusion_tag('includes/_list_pagination.html')
def list_pagination(page_obj, qs='', unit='건', page_param='page',
                    per_page_param='', per_page=None, per_page_options='',
                    total=None, capped=False, aria_label='목록 페이지'):
    """
    page_obj        Django Page 객체
    qs              page 를 뺀 쿼리스트링 (앞의 '&' 없이)
    unit            '전체 12개 <unit>' 자리에 들어갈 명사
    page_param      쪽 번호 파라미터 이름. 부적합·처분 알림은 탭마다 다르다
                    (insp_page / pub_page / page) — 그래서 고정할 수 없다.
    per_page_param  '페이지당' 고르개를 그릴 때 쓸 파라미터 이름.
                    빈 값이면 고르개를 아예 그리지 않는다 — 그 기능이 없는
                    화면에 억지로 붙이지 않는다.
    total           전체 건수. 안 넘기면 paginator.count 를 쓴다.
    capped          건수를 끝까지 세지 않은 경우(제품 조회의 CappedPaginator).
                    '12,345+' 로 적고 왜 그런지 title 로 알려 준다 — 숫자가
                    실제보다 작게 보이는 것을 그냥 두면 안 되기 때문이다.
    """
    if page_obj is None:
        return {'draw': False}
    paginator = page_obj.paginator
    options = [o.strip() for o
               in (per_page_options or _DEFAULT_PER_PAGE_OPTIONS).split(',')
               if o.strip()]
    # 빈 Page 는 그 자체로 거짓이다(len 0). 템플릿에서 {% if page_obj %} 로
    # 가르면 결과가 0건인 화면에서 바가 통째로 사라진다 — 실제로 그랬다.
    return {
        'draw':           True,
        'page_obj':       page_obj,
        'num_pages':      paginator.num_pages,
        'total':          paginator.count if total is None else total,
        'capped':         capped,
        'window':         page_window(page_obj),
        'qs':             qs or '',
        'unit':           unit,
        'page_param':     page_param,
        'per_page_param': per_page_param,
        'per_page':       str(per_page) if per_page is not None else '',
        'per_page_options': options,
        'aria_label':     aria_label,
    }
