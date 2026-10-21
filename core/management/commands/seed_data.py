from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import Product, StockMovement, Supplier, Customer, ShopSettings

SAMPLE_PRODUCTS = [
    {
        'brand': 'Royal Challenge',
        'name': 'Classic Whisky',
        'category': 'Whisky',
        'size_ml': 750,
        'barcode': '890123400001',
        'mrp': Decimal('850.00'),
        'purchase_price': Decimal('680.00'),
        'reorder_level': 12,
        'is_quick_pick': True,
        'opening_stock': 48,
    },
    {
        'brand': "McDowell's",
        'name': 'No. 1 Celebration Rum',
        'category': 'Rum',
        'size_ml': 750,
        'barcode': '890123400002',
        'mrp': Decimal('550.00'),
        'purchase_price': Decimal('420.00'),
        'reorder_level': 15,
        'is_quick_pick': True,
        'opening_stock': 60,
    },
    {
        'brand': 'Magic Moments',
        'name': 'Grain Vodka',
        'category': 'Vodka',
        'size_ml': 750,
        'barcode': '890123400003',
        'mrp': Decimal('620.00'),
        'purchase_price': Decimal('490.00'),
        'reorder_level': 10,
        'is_quick_pick': True,
        'opening_stock': 36,
    },
    {
        'brand': 'Kingfisher',
        'name': 'Strong Premium Beer',
        'category': 'Beer',
        'size_ml': 650,
        'barcode': '890123400004',
        'mrp': Decimal('160.00'),
        'purchase_price': Decimal('125.00'),
        'reorder_level': 24,
        'is_quick_pick': True,
        'opening_stock': 120,
    },
    {
        'brand': 'Blenders Pride',
        'name': 'Rare Select Whisky',
        'category': 'Whisky',
        'size_ml': 750,
        'barcode': '890123400005',
        'mrp': Decimal('1150.00'),
        'purchase_price': Decimal('920.00'),
        'reorder_level': 8,
        'is_quick_pick': False,
        'opening_stock': 24,
    },
    {
        'brand': 'Old Monk',
        'name': 'Legend XXX Rum',
        'category': 'Rum',
        'size_ml': 750,
        'barcode': '890123400006',
        'mrp': Decimal('500.00'),
        'purchase_price': Decimal('380.00'),
        'reorder_level': 12,
        'is_quick_pick': True,
        'opening_stock': 72,
    },
    {
        'brand': 'Bombay Sapphire',
        'name': 'London Dry Gin',
        'category': 'Gin',
        'size_ml': 750,
        'barcode': '890123400007',
        'mrp': Decimal('2400.00'),
        'purchase_price': Decimal('1950.00'),
        'reorder_level': 5,
        'is_quick_pick': False,
        'opening_stock': 12,
    },
    {
        'brand': 'Mansion House',
        'name': 'French Brandy',
        'category': 'Brandy',
        'size_ml': 750,
        'barcode': '890123400008',
        'mrp': Decimal('780.00'),
        'purchase_price': Decimal('620.00'),
        'reorder_level': 10,
        'is_quick_pick': False,
        'opening_stock': 30,
    },
    {
        'brand': 'Sula',
        'name': 'Shiraz Cabernet Red Wine',
        'category': 'Wine',
        'size_ml': 750,
        'barcode': '890123400009',
        'mrp': Decimal('890.00'),
        'purchase_price': Decimal('710.00'),
        'reorder_level': 6,
        'is_quick_pick': False,
        'opening_stock': 18,
    },
    {
        'brand': 'Desi Santra',
        'name': 'Orange Country Liquor',
        'category': 'Country Liquor',
        'size_ml': 180,
        'barcode': '890123400010',
        'mrp': Decimal('80.00'),
        'purchase_price': Decimal('60.00'),
        'reorder_level': 30,
        'is_quick_pick': True,
        'opening_stock': 100,
    },
]

class Command(BaseCommand):
    help = 'Seeds 10 sample liquor products with opening stock and test data'

    def handle(self, *args, **options):
        self.stdout.write("Seeding sample liquor products and test data...")
        admin_user = User.objects.filter(is_superuser=True).first()

        with transaction.atomic():
            # Seed default shop settings if missing
            ShopSettings.get_settings()

            # Seed sample supplier
            supplier, _ = Supplier.objects.get_or_create(
                name="Apex Beverages & Distilleries",
                defaults={
                    'contact_person': 'Anil Kapoor',
                    'phone': '9876543210',
                    'email': 'apexbev@distrib.test',
                    'address': 'Plot 45, Industrial Excise Zone'
                }
            )

            # Seed sample customers
            Customer.objects.get_or_create(
                phone="9988776655",
                defaults={
                    'name': 'Rajesh Sharma',
                    'address': 'Civil Lines, House #14',
                    'credit_limit': Decimal('10000.00'),
                    'current_balance': Decimal('1250.00')
                }
            )
            Customer.objects.get_or_create(
                phone="9811223344",
                defaults={
                    'name': 'Vikram Singh',
                    'address': 'Sector 12 Market',
                    'credit_limit': Decimal('5000.00'),
                    'current_balance': Decimal('0.00')
                }
            )

            # Seed 10 sample products
            created_count = 0
            for item in SAMPLE_PRODUCTS:
                opening_stock = item.pop('opening_stock')
                barcode = item['barcode']

                product, created = Product.objects.get_or_create(
                    barcode=barcode,
                    defaults=item
                )

                if created:
                    created_count += 1
                    # Record StockMovement (live stock is strictly derived from movements!)
                    StockMovement.objects.create(
                        product=product,
                        movement_type='OPENING',
                        quantity=opening_stock,
                        reference_id='SEED-OPENING',
                        created_by=admin_user,
                        notes='Initial opening stock for seed testing'
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {created_count} sample products with opening stock, plus sample supplier and credit customers!"
        ))
