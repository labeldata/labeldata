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
