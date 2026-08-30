"""
새 표시사항/제품의 임시 이름을 짓는다.

표시사항 작성과 제품 관리가 각각 "새로 만들기" 를 갖고 있는데, 둘이 같은 규칙을
써야 한다. cleanup_temp_labels 가 이 이름을 보고 손대지 않은 빈 것을 치우기
때문이다 - 이름이 갈라지면 한쪽은 영영 안 치워진다.
"""
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr

BASE_NAME = '임시 - 제품명'
PREFIX = f'{BASE_NAME} - '


def next_temp_label_name(user):
    """
    "임시 - 제품명 - N" 의 다음 번호를 붙인 이름.

    번호는 DB 가 구한다. 예전에는 그 이름으로 시작하는 라벨을 전부 가져와
    파이썬 정규식으로 최대값을 찾았다. 이탈한 빈 라벨이 쌓이는 화면이라 목록이
    계속 길어지고, 신규 작성 버튼이 그만큼 느려진다.

    숫자가 아닌 꼬리는 MySQL·SQLite 모두 0 으로 변환하므로 최대값을 흔들지 않는다.
    """
    from v1.label.models import MyLabel

    top = (
        MyLabel.objects
        .filter(user_id=user, my_label_name__startswith=PREFIX)
        .annotate(seq=Cast(Substr('my_label_name', len(PREFIX) + 1), IntegerField()))
        .aggregate(top=Max('seq'))['top'] or 0
    )
    return f'{PREFIX}{top + 1}'
