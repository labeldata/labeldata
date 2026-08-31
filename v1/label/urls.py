from django.urls import path
from . import views
from . import views_ocr_lab

app_name = 'label'

urlpatterns = [
    # 제품 목록 및 상세
    path('food-items/', views.food_item_list, name='food_item_list'),
    # 반대쪽 탭 배지 건수만 따로 받아간다 (검색 화면을 먼저 띄우기 위해)
    path('food-items/tab-count/', views.food_item_tab_count, name='food_item_tab_count'),
    path('food-items/domestic/', views.food_item_list_domestic, name='food_item_list_domestic'),
    path('food-items/imported/', views.food_item_list_imported, name='food_item_list_imported'),
    path('food-item-detail/<str:prdlst_report_no>/', views.food_item_detail, name='food_item_detail'),
    path('fetch-food-item/<str:prdlst_report_no>/', views.fetch_food_item, name='fetch_food_item'),
    
    # 식품첨가물 검색
    path('food-additives/', views.food_additive_search, name='food_additive_search'),
    path('copy-additives-to-ingredients/', views.copy_additives_to_ingredients, name='copy_additives_to_ingredients'),
    path('request-additive-correction/', views.request_additive_correction, name='request_additive_correction'),

    # 내 표시사항 관리
    path('my-labels/', views.my_label_list, name='my_label_list'),
    path('create-new/', views.create_new_label, name='create_new_label'),
    path('bulk-copy-labels/', views.bulk_copy_labels, name='bulk_copy_labels'),
    path('bulk-delete-labels/', views.bulk_delete_labels, name='bulk_delete_labels'),
    path('save-to-my-label/<str:prdlst_report_no>/', views.save_to_my_label, name='save_to_my_label'),

    # 표시사항 작성
    path("label/create/", views.label_creation, name="label_creation"),
    path('label-creation/<int:label_id>/', views.label_creation, name='label_creation'),
    path('ingredient-popup/', views.ingredient_popup, name='ingredient_popup'),
    path('nutrition-calculator-popup/', views.nutrition_calculator_popup, name='nutrition_calculator_popup'),
    path('save-nutrition/', views.save_nutrition, name='save_nutrition'),
    path('duplicate/<int:label_id>/', views.duplicate_label, name='duplicate_label'),
    path('delete/<int:label_id>/', views.delete_label, name='delete_label'),
    path('preview/', views.preview_popup, name='preview_popup'),
    path('tab-json/', views.label_tab_json, name='label_tab_json'),  
    path('food-types-by-group/', views.food_types_by_group, name='food_types_by_group'),
    # 식품유형 선택용 검색 (농수축산물 1만 건을 화면에 통째로 싣지 않기 위한 것)
    path('food-type-options/', views.food_type_options, name='food_type_options'),
    path('save_preview_settings/', views.save_preview_settings, name='save_preview_settings'),
    path('upload-label-pdf/', views.upload_label_pdf, name='upload_label_pdf'),
    path('log-validation/', views.log_validation, name='log_validation'),
    path('log-pdf-save/', views.log_pdf_save, name='log_pdf_save'),
    path('log-mode-switch/', views.log_mode_switch, name='log_mode_switch'),
    path('log-quick-text/', views.log_quick_text, name='log_quick_text'),
    path('log-custom-field/', views.log_custom_field, name='log_custom_field'),
    path('log-preview-action/', views.log_preview_action, name='log_preview_action'),
    path('log-allergy-auto-detect/', views.log_allergy_auto_detect, name='log_allergy_auto_detect'),

    # 내원료 관리
    path('save-to-my-ingredients/<str:prdlst_report_no>/', views.save_to_my_ingredients, name='save_to_my_ingredients'),
    path('check-my-ingredient/', views.check_my_ingredient, name='check_my_ingredient'),
    path('register-my-ingredient/', views.register_my_ingredient, name='register_my_ingredient'),
    path('my-ingredient-list/', views.my_ingredient_list, name='my_ingredient_list'),
    path('my-ingredient-list-combined/', views.my_ingredient_list_combined, name='my_ingredient_list_combined'),
    path('my-ingredient-detail/<int:ingredient_id>/', views.my_ingredient_detail, name='my_ingredient_detail'),
    path('my-ingredient-detail/', views.my_ingredient_detail, name='my_ingredient_create'),
    path('delete-my-ingredient/<int:ingredient_id>/', views.delete_my_ingredient, name='delete_my_ingredient'),
    path('bulk-delete-my-ingredients/', views.bulk_delete_my_ingredients, name='bulk_delete_my_ingredients'),
    path('bulk-copy-my-ingredients/', views.bulk_copy_my_ingredients, name='bulk_copy_my_ingredients'),
    path('save-ingredients-to-label/<int:label_id>/', views.save_ingredients_to_label, name='save_ingredients_to_label'),
    path('search-ingredient-add-row/', views.search_ingredient_add_row, name='search_ingredient_add_row'),
    path('quick-register-ingredient/', views.quick_register_ingredient, name='quick_register_ingredient'),
    path('verify-ingredients/', views.verify_ingredients, name='verify_ingredients'),
    path('my-ingredient-table-partial/', views.my_ingredient_table_partial, name='my_ingredient_table_partial'),
    path('get-additive-regulation/', views.get_additive_regulation, name='get_additive_regulation'),
    path('api/food-items/count/', views.food_items_count, name='food_items_count'),

    # 엑셀 다운로드
    path('export-labels-excel/', views.export_labels_excel, name='export_labels_excel'),

    # 수입식품 개수 조회
    path('imported_food_count/', views.imported_food_count, name='imported_food_count'),

    # 추가된 URL 패턴
    path('phrases-data/', views.phrases_data_api, name='phrases_data'),
    path('my-ingredient-calculate-page/', views.my_ingredient_calculate_page, name='my_ingredient_calculate_page'),
    path('my-ingredient-pagination-info/', views.my_ingredient_pagination_info, name='my_ingredient_pagination_info'),

    # --- [신규] 엑셀 다운로드/업로드 URL 추가 ---
    path('my-ingredients/download/', views.download_my_ingredients_excel, name='download_my_ingredients_excel'),
    path('my-ingredients/upload/', views.upload_my_ingredients_excel, name='upload_my_ingredients_excel'),
    
    # 저장된 문구 API 패턴
    path('api/recent-usage/', views.get_recent_usage_api, name='recent_usage_api'),
    path('api/auto-fill/', views.auto_fill_api, name='auto_fill_api'),
    path('api/phrases/', views.phrases_api, name='phrases_api'),
    
    # 연결된 원료 조회
    path('linked-labels-count/<int:ingredient_id>/', views.linked_labels_count, name='linked_labels_count'), #삭제했던 url 다시 추가 (원료 관리에서 연결된 표시사항 갯수 확인 용도)
    path('linked-ingredient-count/<int:label_id>/', views.linked_ingredient_count, name='linked_ingredient_count'),
    
    # OCR
    path('ocr-extract/', views.ocr_extract, name='ocr_extract'),

    # 판독 고도화 (관리자 전용) — 정답지를 쌓고, 재고, 프롬프트를 고친다
    path('ocr-lab/', views_ocr_lab.ocr_lab, name='ocr_lab'),
    path('ocr-lab/truth/', views_ocr_lab.truth_create, name='ocr_lab_truth_create'),
    path('ocr-lab/truth/from-label/', views_ocr_lab.truth_from_label,
         name='ocr_lab_truth_from_label'),
    path('ocr-lab/truth/<int:case_id>/', views_ocr_lab.truth_detail,
         name='ocr_lab_truth_detail'),
    path('ocr-lab/truth/<int:case_id>/save/', views_ocr_lab.truth_update,
         name='ocr_lab_truth_update'),
    path('ocr-lab/truth/<int:case_id>/locate/', views_ocr_lab.truth_locate,
         name='ocr_lab_truth_locate'),
    path('ocr-lab/truth/<int:case_id>/reread/', views_ocr_lab.truth_reread,
         name='ocr_lab_truth_reread'),
    path('ocr-lab/truth/<int:case_id>/delete/', views_ocr_lab.truth_delete,
         name='ocr_lab_truth_delete'),
    path('ocr-lab/run/', views_ocr_lab.run_benchmark, name='ocr_lab_run'),
    path('ocr-lab/run/<int:run_id>/', views_ocr_lab.run_detail, name='ocr_lab_run_detail'),
    path('ocr-lab/run/<int:run_id>/brief/', views_ocr_lab.revision_brief,
         name='ocr_lab_revision_brief'),
    path('ocr-lab/run/<int:run_id>/suggest/', views_ocr_lab.prompt_suggest,
         name='ocr_lab_prompt_suggest'),
    path('ocr-lab/prompt/', views_ocr_lab.prompt_save, name='ocr_lab_prompt_save'),
    path('ocr-lab/prompt/<int:version_id>/', views_ocr_lab.prompt_detail,
         name='ocr_lab_prompt_detail'),
    path('ocr-lab/prompt/<int:version_id>/activate/', views_ocr_lab.prompt_activate,
         name='ocr_lab_prompt_activate'),
    path('ocr-lab/prompt/deactivate/', views_ocr_lab.prompt_deactivate,
         name='ocr_lab_prompt_deactivate'),

    # 품목보고번호 검증 관련
    path('verify-report-no/', views.verify_report_no, name='verify_report_no'),

    # 인쇄되는 원재료명 문구 생성 (규칙 기반, 저장은 사용자가)
    path('<int:label_id>/rawmtrl-display/', views.generate_rawmtrl_display, name='generate_rawmtrl_display'),

    # 표시사항 서버측 검증 (클라이언트 우회 방지용 최종 판정)
    path('<int:label_id>/validate/', views.validate_label_server, name='validate_label_server'),

    # 표시사항 AI 2차 검증 (파일럿: 원재료명 표시 순서) — 비용/지연 있어 별도 opt-in 호출
    path('<int:label_id>/validate/ai/', views.validate_label_ai, name='validate_label_ai'),

    # 표시사항 등록 화면 "AI검증" 버튼용 통합 검증(규칙기반 + AI 원재료순서 + AI 요약)
    path('<int:label_id>/validate/ai-review/', views.validate_label_ai_review, name='validate_label_ai_review'),

    # 오늘 AI검증 사용량 조회 (계정 단위, label_id 불필요)
    path('ai-validation-usage/', views.ai_validation_usage, name='ai_validation_usage'),

    # 식품첨가물/혼합제제 필드 설정
    path('get-additive-field-settings/', views.get_additive_field_settings, name='get_additive_field_settings'),

    # 가공식품 식품유형별 표시 항목 규칙 (label_creation.js 가 예전부터 부르던 URL)
    path('food-type-settings/', views.food_type_settings, name='food_type_settings'),
    path('get-food-group/', views.get_food_group, name='get_food_group'),
]