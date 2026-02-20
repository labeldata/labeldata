from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'v1.products'
    label = 'products'  # app_label 고정 (DB 테이블명 불변)
    verbose_name = '제품 관리'
