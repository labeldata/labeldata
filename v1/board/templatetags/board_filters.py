from django import template

register = template.Library()

@register.filter(name='mask_email')
def mask_email(email):
    """
    이메일 주소를 마스킹 처리합니다.
    @ 앞부분의 앞 2글자만 표시하고 나머지는 *로 표시합니다.
    
    예시:
    - user@example.com -> us****
    - admin@example.com -> ad****
    - a@example.com -> a****
    """
    if not email or '@' not in str(email):
        return email
    
    email_str = str(email)
    local_part = email_str.split('@')[0]
    
    if len(local_part) <= 2:
        # 2글자 이하면 첫 글자만 표시
        return local_part[0] + '****'
    else:
        # 앞 2글자만 표시하고 나머지는 ****
        return local_part[:2] + '****'

@register.filter(name='board_author')
def board_author(user):
    """
    게시판에 보일 글쓴이 이름. **한 곳에서 정한다.**

    예전에는 같은 화면 안에서 규칙이 셋으로 갈려 있었다 — 목록은 가리고,
    상세 글쓴이는 가리되 대체값이 없어 이메일 없는 계정이 `****` 만 되고,
    **답변 작성자는 원문 그대로** 나갔다. 가입이
    `create_user(username=email, email=email, …)` 이라 username 이 곧
    이메일이고, 게시판 상세는 로그인 없이도 열리므로 **아무나 남의 이메일
    주소를 읽을 수 있었다.**
    """
    if user is None:
        return '시스템 관리자'
    if getattr(user, 'is_staff', False):
        return '관리자'
    raw = (getattr(user, 'email', '') or getattr(user, 'username', '') or '').strip()
    if not raw:
        return '알 수 없음'
    head = raw.split('@')[0]
    return head[:2] + '****'
