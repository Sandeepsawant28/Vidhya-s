from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal

CATEGORY_CHOICES = [
    ('Whisky', 'Whisky'),
    ('Rum', 'Rum'),
    ('Vodka', 'Vodka'),
    ('Gin', 'Gin'),
    ('Brandy', 'Brandy'),
    ('Beer', 'Beer'),
    ('Wine', 'Wine'),
    ('Country Liquor', 'Country Liquor'),
    ('Other', 'Other'),
]

PAYMENT_MODES = [
    ('CASH', 'Cash'),
    ('UPI', 'UPI'),
    ('CARD', 'Card'),
    ('CREDIT', 'Credit'),
    ('SPLIT', 'Split'),
]

BILL_STATUS_CHOICES = [
    ('COMPLETED', 'Completed'),
    ('CANCELLED', 'Cancelled'),
]

MOVEMENT_TYPE_CHOICES = [
    ('PURCHASE', 'Purchase (Stock In)'),
    ('SALE', 'Sale (Stock Out)'),
    ('OPENING', 'Opening Stock'),
    ('CANCEL', 'Bill Cancel (Stock In)'),
    ('DAMAGE', 'Damage / Wastage (Stock Out)'),
    ('ADJUSTMENT', 'Stock Adjustment'),
]

class ShopSettings(models.Model):
    """Holds store profile details and configuration."""
    shop_name = models.CharField(max_length=200, default="My Liquor Shop")
    address = models.TextField(blank=True, default="Main Market, Shop No. 1")
    phone = models.CharField(max_length=50, blank=True, default="")
    licence_number = models.CharField(max_length=100, blank=True, default="")
    gst_number = models.CharField(max_length=50, blank=True, default="")
    secondary_backup_path = models.CharField(
        max_length=255, 
        blank=True, 
        default="", 
        help_text="Optional USB drive folder or external path (e.g. D:\\LiquorBackups)"
    )
    receipt_footer = models.TextField(
        default="Thank you! Please visit again.\nLiquor once sold will not be exchanged or returned."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shop Setting"
        verbose_name_plural = "Shop Settings"

    def __str__(self):
        return self.shop_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class Product(models.Model):
    """Liquor Item details. Stock is NOT stored here; it is calculated from StockMovement."""
    brand = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=150, help_text="e.g. Royal Challenge Classic")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Whisky', db_index=True)
    size_ml = models.PositiveIntegerField(help_text="Volume in ml (e.g. 750, 375, 180, 500, 650)")
    barcode = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Maximum Retail Price in ₹")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost price per bottle in ₹")
    reorder_level = models.PositiveIntegerField(default=10, help_text="Alert if stock falls to or below this level")
    is_quick_pick = models.BooleanField(default=False, help_text="Display as quick-click button on billing screen")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['brand', 'name', 'size_ml']

    def __str__(self):
        return f"{self.brand} {self.name} ({self.size_ml}ml) - ₹{self.mrp}"

    @property
    def current_stock(self):
        """Calculates live stock by summing all StockMovements for this product."""
        total = self.stock_movements.aggregate(total=Sum('quantity'))['total']
        return total if total is not None else 0

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class StockMovement(models.Model):
    """
    Every addition and deduction of stock is recorded here.
    Positive quantity = Stock In (Purchase, Opening, Bill Cancel).
    Negative quantity = Stock Out (Sale, Breakage, Damage).
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.IntegerField(help_text="Positive for additions (+), negative for sales/deductions (-)")
    reference_id = models.CharField(max_length=100, blank=True, help_text="Bill No or Purchase Invoice No")
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type}: {self.product.name} ({self.quantity:+d})"


class Supplier(models.Model):
    """Distributor or liquor supplier."""
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Purchase(models.Model):
    """Stock purchase entry from supplier."""
    supplier = models.ForeignKey(Supplier, null=True, on_delete=models.SET_NULL, related_name='purchases')
    invoice_number = models.CharField(max_length=100, db_index=True)
    date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Purchase Inv #{self.invoice_number} ({self.date})"


class PurchaseItem(models.Model):
    """Line items for a purchase invoice."""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_items')
    quantity = models.PositiveIntegerField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Customer(models.Model):
    """Credit customer profile and ledger balance."""
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, unique=True, db_index=True)
    address = models.TextField(blank=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone}) - Bal: ₹{self.current_balance}"


class Bill(models.Model):
    """Sales receipt issued to customer."""
    bill_number = models.CharField(max_length=50, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bills')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='bills')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='CASH')
    cash_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    upi_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    card_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    credit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=BILL_STATUS_CHOICES, default='COMPLETED')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='cancelled_bills')
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.bill_number} - ₹{self.total_amount} ({self.get_payment_mode_display()})"


class BillItem(models.Model):
    """Individual product sold inside a bill."""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='bill_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="MRP at time of sale")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Purchase price at time of sale for profit math")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class CreditPayment(models.Model):
    """Payment received from a credit customer."""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=[('CASH', 'Cash'), ('UPI', 'UPI')], default='CASH')
    date = models.DateField(default=timezone.now)
    reference_note = models.CharField(max_length=150, blank=True)
    received_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"₹{self.amount} from {self.customer.name} on {self.date}"


class AuditLog(models.Model):
    """Immutable audit trail for critical shop events."""
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    details = models.TextField()
    ip_address = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_name}: {self.action}"
