from django.urls import path
from . import views

urlpatterns = [
    # Setup & Authentication
    path('setup/', views.setup_wizard_view, name='setup_wizard'),
    path('login/', views.user_login_view, name='login'),
    path('logout/', views.user_logout_view, name='logout'),
    path('manifest.json', views.manifest_view, name='manifest'),
    path('sw.js', views.sw_view, name='sw'),

    # Home & Wi-Fi LAN access info
    path('', views.dashboard_view, name='dashboard'),
    path('network-info/', views.network_info_view, name='network_info'),

    # Inventory
    path('inventory/', views.product_list_view, name='product_list'),
    path('inventory/add/', views.product_create_view, name='product_create'),
    path('inventory/<int:product_id>/edit/', views.product_edit_view, name='product_edit'),
    path('inventory/export/', views.product_export_excel_view, name='product_export'),
    path('inventory/import/', views.product_import_excel_view, name='product_import'),

    # Purchases
    path('purchases/', views.purchase_list_view, name='purchase_list'),
    path('purchases/entry/', views.purchase_entry_view, name='purchase_entry'),
    path('purchases/<int:purchase_id>/', views.purchase_detail_view, name='purchase_detail'),

    # Billing (POS)
    path('billing/', views.pos_view, name='pos'),
    path('billing/api/search/', views.api_search_products, name='api_search_products'),
    path('billing/api/quick-add/', views.api_quick_add_product, name='api_quick_add_product'),
    path('billing/api/process-bill/', views.api_process_bill, name='api_process_bill'),
    path('billing/receipt/<int:bill_id>/', views.receipt_view, name='receipt'),
    path('billing/bills/', views.bill_list_view, name='bill_list'),
    path('billing/bills/<int:bill_id>/cancel/', views.bill_cancel_view, name='bill_cancel'),

    # Credit Customers & Ledger
    path('customers/', views.customer_list_view, name='customer_list'),
    path('customers/add/', views.customer_create_view, name='customer_create'),
    path('customers/<int:customer_id>/ledger/', views.customer_ledger_view, name='customer_ledger'),
    path('customers/payment/', views.credit_payment_create_view, name='credit_payment_create'),

    # Owner Reports
    path('reports/daily-sales/', views.report_daily_sales_view, name='report_daily_sales'),
    path('reports/daily-closing/', views.report_daily_closing_view, name='report_daily_closing'),
    path('reports/profit-by-brand/', views.report_profit_by_brand_view, name='report_profit_by_brand'),
    path('reports/low-stock/', views.report_low_stock_view, name='report_low_stock'),
    path('reports/fast-slow-movers/', views.report_fast_slow_movers_view, name='report_fast_slow_movers'),
    path('reports/credit-outstanding/', views.report_credit_outstanding_view, name='report_credit_outstanding'),

    # Shop Settings & Backups
    path('settings/shop/', views.shop_settings_view, name='shop_settings'),
    path('settings/backups/', views.backup_management_view, name='backup_management'),
    path('settings/audit-log/', views.audit_log_view, name='audit_log'),
]
