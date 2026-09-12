from django.urls import path
from v1.regulatory import views

app_name = 'regulatory'

urlpatterns = [
    # 메인 목록 (Split View)
    path('', views.news_list, name='list'),
    # 상세 (독립 페이지)
    path('<int:pk>/', views.news_detail, name='detail'),
    # API
    path('api/mark-false-positive/', views.mark_false_positive, name='mark_false_positive'),
    path('api/save-action/', views.save_match_action, name='save_action'),
    path('api/mark-all-resolved/', views.mark_all_resolved, name='mark_all_resolved'),
    path('api/mark-all-news-resolved/', views.mark_all_news_resolved, name='mark_all_news_resolved'),
    # 탭 단위 모두 읽음 (부적합 / 행정처분 / 수거검사 / 전체 공용)
    path('api/mark-tab-read/', views.mark_tab_read, name='mark_tab_read'),
    # 알림 제외(뮤트) — "이 키워드 때문에 오는 알림은 그만"
    path('api/alert-mutes/', views.alert_mutes_api, name='alert_mutes'),
    path('api/alert-mutes/<int:mute_id>/delete/', views.alert_mute_delete_api, name='alert_mute_delete'),
    # AlertRule 관리 (웹에서 앱 알림 키워드 추가/삭제)
    path('api/alert-rules/', views.alert_rules_api, name='alert_rules'),
    path('api/alert-rules/<int:rule_id>/delete/', views.alert_rule_delete_api, name='alert_rule_delete'),
    # 수거검사(I0460) API
    path('api/inspection/mark-all-read/', views.inspection_mark_all_read, name='inspection_mark_all_read'),
    path('api/inspection/dismiss/', views.inspection_dismiss, name='inspection_dismiss'),
    path('api/save-insp-profile/', views.save_insp_profile, name='save_insp_profile'),
    # 수거검사 외부 export API (GAS 등 사내 연동용, 키 인증)
    path('api/inspection/export/', views.inspection_export_api, name='inspection_export'),
]
