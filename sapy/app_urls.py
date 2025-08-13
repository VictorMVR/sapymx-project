from django.urls import path
from . import views

app_name = 'sapy'

urlpatterns = [
    # Aplicaciones
    path('applications/', views.application_list, name='application_list'),
    path('applications/new/', views.application_create, name='application_create'),
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    path('applications/<int:pk>/edit/', views.application_edit, name='application_edit'),
    path('applications/<int:pk>/delete/', views.application_delete, name='application_delete'),
    path('applications/<int:pk>/deploy/', views.application_deploy, name='application_deploy'),
    path('applications/<int:pk>/status/', views.application_status, name='application_status'),
    path('applications/<int:pk>/tables/', views.application_tables, name='application_tables'),
    path('applications/<int:app_pk>/tables/<int:table_pk>/', views.application_table_detail, name='application_table_detail'),
    path('applications/<int:pk>/tables/search/', views.application_tables_search, name='application_tables_search'),
    # Menús por aplicación
    path('applications/<int:pk>/menus/', views.application_menus, name='application_menus'),
    path('applications/<int:pk>/menus/search/', views.application_menus_search, name='application_menus_search'),
    path('applications/<int:pk>/pages/', views.application_pages, name='application_pages'),
    path('applications/<int:pk>/pages/search/', views.application_pages_search, name='application_pages_search'),

    # Logs de deployment
    path('applications/<int:pk>/logs/<int:log_pk>/', views.deployment_log_detail, name='deployment_log_detail'),
    path('applications/<int:pk>/logs/<int:log_pk>/stream/', views.deployment_log_stream, name='deployment_log_stream'),

    # Utilidades
    path('test-script/', views.test_script_connection, name='test_script'),

    # DB schema
    path('db/tables/', views.db_table_list, name='db_table_list'),
    path('db/tables/new/', views.db_table_create, name='db_table_create'),
    path('db/tables/<int:pk>/', views.db_table_detail, name='db_table_detail'),
    path('db/tables/<int:pk>/edit/', views.db_table_edit, name='db_table_edit'),
    path('db/tables/<int:pk>/toggle-active/', views.db_table_toggle_active, name='db_table_toggle_active'),
    path('db/tables/<int:pk>/reorder/', views.db_table_reorder, name='db_table_reorder'),
    path('db/tables/<int:pk>/delete/', views.db_table_delete, name='db_table_delete'),
    path('db/tables/<int:pk>/columns/new/', views.db_column_create, name='db_column_create'),
    path('db/columns/<int:col_pk>/edit/', views.db_column_edit, name='db_column_edit'),
    path('db/columns/<int:col_pk>/delete/', views.db_column_delete, name='db_column_delete'),

    # Datos y toggle activo
    path('db/tables/<int:pk>/data/', views.db_table_data_list, name='db_table_data_list'),
    path('db/tables/<int:pk>/data/<int:row_id>/toggle/activo/', views.db_table_toggle_activo, name='db_table_toggle_activo'),

    # Todas las columnas BD
    path('db/columns/', views.db_column_list, name='db_column_list'),
    path('db/columns/<int:pk>/edit/', views.db_column_edit_standalone, name='db_column_edit_standalone'),
    # path('db/columns/<int:pk>/delete/', views.db_column_delete_standalone, name='db_column_delete_standalone'),
    path('db/columns/migrate-ui/', views.migrate_columns_ui, name='migrate_columns_ui'),
    
    # Desvincular columnas de tablas
    path('db/table-columns/<int:pk>/delete/', views.db_table_column_delete, name='db_table_column_delete'),

    # Plantillas de columnas BD - ELIMINADAS

    # Páginas
    path('pages/', views.pages_list, name='pages_list'),
    path('pages/<int:page_id>/', views.page_detail, name='page_detail'),
    path('pages/<int:page_id>/update/', views.page_update, name='page_update'),
    path('pages/page-table/<int:page_table_id>/column-override/save/', views.page_table_column_override_save, name='page_table_column_override_save'),
    path('pages/modal/<int:modal_id>/update/', views.modal_update, name='modal_update'),
    path('pages/modal/<int:modal_id>/field-override/save/', views.modal_form_field_override_save, name='modal_form_field_override_save'),
    path('pages/generate-from-dbtable/', views.page_generate_from_dbtable, name='page_generate_from_dbtable'),
    path('pages/<int:page_id>/effective-config/', views.page_effective_config, name='page_effective_config'),

    # Menús
    path('pages/menus/', views.menus_list, name='menus_list'),
    path('pages/menus/new/', views.menu_create, name='menu_create'),
    path('pages/menus/<int:menu_id>/', views.menu_detail, name='menu_detail'),
    path('pages/menus/<int:menu_id>/update/', views.menu_update, name='menu_update'),
    path('pages/menus/<int:menu_id>/assign/', views.menu_assign_page, name='menu_assign_page'),
    path('pages/menus/<int:menu_id>/unassign/', views.menu_unassign_page, name='menu_unassign_page'),
    path('pages/menus/<int:menu_id>/pages/search/', views.menu_pages_search, name='menu_pages_search'),
    path('pages/menus/<int:menu_id>/pages/reorder/', views.menu_pages_reorder, name='menu_pages_reorder'),
    path('pages/menus/<int:menu_id>/page/update/', views.menu_page_update, name='menu_page_update'),

    # Catálogo de íconos (para picker)
    path('icons/search/', views.icons_search, name='icons_search'),
    path('icons/', views.icons_list, name='icons_list'),
    path('icons/import/', views.icons_import, name='icons_import'),
]
