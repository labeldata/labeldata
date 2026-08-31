"""
빠른 입력 버튼(자주 사용하는 문구)을 화면에 뿌리는 태그.

목록 자체는 `v1.label.services.label_phrases` 한 곳에 있다. 화면과 판독
프롬프트가 **같은 목록**을 봐야 한다 — 두 벌로 두면 문구를 하나 고쳤을 때
버튼만 바뀌고 판독은 옛 문장을 계속 기다린다.
"""
from django import template

from v1.label.services.label_phrases import phrases_for

register = template.Library()


@register.simple_tag
def quick_phrases(field):
    """주의사항/기타표시사항 칸에 붙일 문구 목록."""
    return phrases_for(field)
