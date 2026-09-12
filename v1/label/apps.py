from django.apps import AppConfig


class LabelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.label'

    def ready(self):
        # 원료를 저장할 때 영양성분을 붙여 보는 신호. 등록하는 자리는 여기
        # 한 곳이다 — 뷰마다 한 줄씩 넣으면 언젠가 하나를 빠뜨린다.
        from v1.label import signals  # noqa: F401
