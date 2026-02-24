from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # ==================== 탐색기 ====================
    path('explorer/', views.product_explorer, name='product_explorer'),
    path('explorer/folder/<int:folder_id>/', views.product_explorer, name='product_explorer_folder'),
    
    # ==================== 폴더 관리 ====================
    path('api/folders/create/', views.folder_create, name='folder_create'),
    path('api/folders/<int:folder_id>/rename/', views.folder_rename, name='folder_rename'),
    path('api/folders/<int:folder_id>/delete/', views.folder_delete, name='folder_delete'),
    
    # ==================== 제품 관리 ====================
    path('', views.product_explorer, name='product_list'),
    path('create/', views.product_create, name='product_create'),
    path('<int:product_id>/', views.product_detail, name='product_detail'),
    path('<int:product_id>/new/', views.product_detail_new, name='product_detail_new'),
    path('<int:product_id>/update/', views.product_update, name='product_update'),
    path('<int:product_id>/update-fields/', views.product_update_fields, name='product_update_fields'),
    path('<int:product_id>/delete/', views.product_delete, name='product_delete'),
    
    # ==================== 제품 편집기 (Editors) ====================
    path('labels/<int:label_id>/nutrition/', views.nutrition_workspace, name='nutrition_editor'),
    path('api/nutrition/<int:label_id>/', views.nutrition_data_api, name='nutrition_data_api'),
    path('api/nutrition/<int:label_id>/save/', views.nutrition_save_api, name='nutrition_save_api'),
    
    # ==================== 제품 액션 ====================
    path('api/products/<int:product_id>/favorite/', views.product_favorite_toggle, name='product_favorite_toggle'),
    path('<int:product_id>/toggle-star/', views.product_favorite_toggle, name='product_toggle_star'),
    path('api/products/<int:product_id>/move/', views.product_move, name='product_move'),
    path('api/products/<int:product_id>/status/', views.product_update_status, name='product_update_status'),
    path('api/bulk-delete/', views.bulk_delete_products, name='bulk_delete_products'),
    path('api/bulk-copy/', views.bulk_copy_products, name='bulk_copy_products'),
    
    # ==================== 최근/즐겨찾기 ====================
    path('recent/', views.product_recent, name='product_recent'),
    path('favorite/', views.product_favorite, name='product_favorite'),
    path('starred/', views.product_favorite, name='product_starred'),
    
    # ==================== 휴지통 ====================
    path('trash/', views.product_trash, name='product_trash'),
    path('<int:product_id>/restore/', views.product_restore, name='product_restore'),
    path('<int:product_id>/permanent-delete/', views.product_permanent_delete, name='product_permanent_delete'),
    
    # ==================== 검색 ====================
    path('search/', views.product_search, name='product_search'),
    
    # ==================== 공유/협업 (Sharing) ====================
    path('inbox/', views.sharing_inbox, name='inbox'),
    path('inbox/<int:receipt_id>/', views.received_share_detail, name='received_share_detail'),
    path('inbox/<int:receipt_id>/accept/', views.received_share_accept, name='received_share_accept'),
    path('inbox/<int:receipt_id>/use-as-ingredient/', views.use_as_ingredient, name='use_as_ingredient'),
    
    path('share/create/<int:label_id>/', views.share_create, name='share_create'),
    path('share/<int:share_id>/', views.share_detail, name='share_detail'),
    path('share/<int:share_id>/revoke/', views.share_revoke, name='share_revoke'),
    path('share/<int:share_id>/update-permission/', views.share_update_permission, name='share_update_permission'),
    path('share/<int:share_id>/update-info/', views.share_update_info, name='share_update_info'),
    path('share/public/<uuid:share_token>/', views.public_share_view, name='public_share_view'),
    
    # ==================== 문서 관리 (Documents) ====================
    path('documents/types/', views.document_type_list, name='document_type_list'),
    path('documents/types/create/', views.document_type_create, name='document_type_create'),
    path('documents/types/<int:type_id>/update/', views.document_type_update, name='document_type_update'),
    
    path('documents/api/types/', views.document_types_api, name='document_types_api'),
    path('documents/api/upload/<int:label_id>/', views.document_upload_api, name='document_upload_api'),
    path('documents/api/<int:document_id>/delete/', views.document_delete_api, name='document_delete_api'),
    path('documents/api/<int:document_id>/update/', views.document_update, name='document_update'),
    path('documents/api/bulk-download/', views.bulk_download, name='bulk_download'),
    path('documents/api/bulk-download/label/<int:label_id>/', views.bulk_download_version, name='bulk_download_version'),
    path('documents/api/bulk-delete/', views.bulk_delete_documents, name='bulk_delete_documents'),
    path('documents/<int:document_id>/toggle-notification/', views.toggle_document_notification, name='toggle_document_notification'),
    path('documents/<int:document_id>/versions/', views.document_versions, name='document_versions'),
    path('documents/<int:document_id>/delete/', views.document_delete_api, name='document_delete'),
    
    path('documents/<int:document_id>/', views.document_detail, name='document_detail'),
    path('documents/<int:document_id>/download/', views.document_download, name='document_download'),
    path('documents/expiring/', views.expiring_documents, name='expiring_documents'),
    path('documents/expired/', views.expired_documents, name='expired_documents'),
    
    # ==================== 문서 슬롯 (Document Slots) ====================
    path('slots/<int:slot_id>/toggle-visibility/', views.toggle_slot_visibility, name='toggle_slot_visibility'),
    path('slots/<int:slot_id>/remove/', views.remove_document_slot, name='remove_document_slot'),
    path('slots/add/<int:label_id>/', views.add_document_slot, name='add_document_slot'),
    
    # ==================== 협업 기능 (Collaboration) ====================
    path('collaboration/label/<int:label_id>/comments/', views.comment_list, name='comment_list'),
    path('collaboration/label/<int:label_id>/comments/create/', views.comment_create, name='comment_create'),
    path('collaboration/comments/<int:comment_id>/resolve/', views.comment_resolve, name='comment_resolve'),
    path('collaboration/comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    
    path('collaboration/label/<int:label_id>/suggestions/', views.suggestion_list, name='suggestion_list'),
    path('collaboration/label/<int:label_id>/suggestions/create/', views.suggestion_create, name='suggestion_create'),
    path('collaboration/suggestions/<int:suggestion_id>/process/', views.suggestion_process, name='suggestion_process'),
    
    path('collaboration/label/<int:label_id>/mentionable/', views.mentionable_users, name='mentionable_users'),
    
    # ==================== 알림 (Notifications) ====================
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-read/', views.notification_mark_read, name='notification_mark_read'),

    # ==================== 연락처 관리 (Contacts) ====================
    path('contacts/', views.contacts, name='contacts'),
    path('contacts/api/list/', views.contacts_api_list, name='contacts_api_list'),
    path('contacts/api/shares/', views.contacts_api_shares, name='contacts_api_shares'),
    path('contacts/api/doc-requests/', views.contacts_api_doc_requests, name='contacts_api_doc_requests'),
    path('contacts/api/received-doc-requests/', views.contacts_api_received_doc_requests, name='contacts_api_received_doc_requests'),
    path('doc-requests/<int:req_id>/submit/', views.doc_request_submit, name='doc_request_submit'),

    # ==================== 문서 요청 관리 (Document Requests) ====================
    path('doc-requests/', views.doc_requests_dashboard, name='doc_requests_dashboard'),
    path('doc-requests/<int:req_id>/cancel/', views.doc_request_cancel, name='doc_request_cancel'),
    path('doc-requests/<int:req_id>/accept/', views.doc_request_accept, name='doc_request_accept'),
    path('contacts/api/doc-types/', views.api_doc_types, name='api_doc_types'),
    path('contacts/api/send-doc-request/', views.api_send_doc_request, name='api_send_doc_request'),
]
