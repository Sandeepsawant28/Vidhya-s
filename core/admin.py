from django.contrib import admin
from .models import (
    ShopSettings, Product, StockMovement, Supplier, 
    Purchase, PurchaseItem, Customer, Bill, BillItem, 
    CreditPayment, AuditLog
)

class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 0
    readonly_fields = ['cost_price']

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'created_at', 'created_by', 'total_amount', 'payment_mode', 'status']
    list_filter = ['status', 'payment_mode', 'created_at']
    search_fields = ['bill_number', 'customer__name', 'customer__phone']
    inlines = [BillItemInline]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['brand', 'name', 'category', 'size_ml', 'barcode', 'mrp', 'purchase_price', 'current_stock', 'is_quick_pick']
    list_filter = ['category', 'is_quick_pick', 'is_active']
    search_fields = ['brand', 'name', 'barcode']

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'reference_id', 'created_by', 'created_at']
    list_filter = ['movement_type', 'created_at']
    search_fields = ['product__name', 'reference_id']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'credit_limit', 'current_balance']
    search_fields = ['name', 'phone']

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'supplier', 'date', 'total_amount', 'created_by']
    list_filter = ['date']
    search_fields = ['invoice_number', 'supplier__name']

@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'payment_mode', 'date', 'received_by']
    list_filter = ['payment_mode', 'date']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'ip_address']
    list_filter = ['action', 'timestamp']
    search_fields = ['action', 'details', 'user__username']
    readonly_fields = ['timestamp', 'user', 'action', 'details', 'ip_address']

admin.site.register(ShopSettings)
admin.site.register(Supplier)
