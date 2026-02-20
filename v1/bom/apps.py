from django.apps import AppConfig


class BomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.bom'
    label = 'bom'  # app_label 고정 (DB 테이블명 불변)
    verbose_name = 'BOM 관리'
