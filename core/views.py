import os
import json
import csv
import sqlite3
import shutil
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db import transaction
from django.db.models import Sum, F, Q, Count, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings
import openpyxl

from .models import (
    ShopSettings, Product, StockMovement, Supplier, 
    Purchase, PurchaseItem, Customer, Bill, BillItem, 
    CreditPayment, AuditLog, CATEGORY_CHOICES, PAYMENT_MODES
)
from .forms import (
    SetupWizardForm, ProductForm, QuickAddProductForm, 
    SupplierForm, CustomerForm, CreditPaymentForm, 
    ShopSettingsForm, ProductExcelImportForm
)
from .decorators import owner_required, is_owner_user
from .utils import (
    log_audit, generate_bill_number, export_queryset_to_excel, 
    get_local_ip, get_client_ip
)

# ==========================================
# 1. SETUP WIZARD & AUTHENTICATION
# ==========================================

def setup_wizard_view(request):
    """First-run setup wizard. Only accessible when no superuser exists."""
    if User.objects.filter(is_superuser=True).exists():
        messages.info(request, "Setup is already completed. Please log in.")
        return redirect('login')

    if request.method == 'POST':
        form = SetupWizardForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # 1. Create or update Shop Settings
                settings_obj = ShopSettings.get_settings()
                settings_obj.shop_name = form.cleaned_data['shop_name']
                settings_obj.address = form.cleaned_data['address']
                settings_obj.phone = form.cleaned_data['phone']
                settings_obj.licence_number = form.cleaned_data['licence_number']
                settings_obj.gst_number = form.cleaned_data['gst_number']
                settings_obj.save()

                # 2. Ensure Groups exist
                owner_group, _ = Group.objects.get_or_create(name='Owner')
                cashier_group, _ = Group.objects.get_or_create(name='Cashier')

                # 3. Create Owner User
                username = form.cleaned_data['owner_username']
                password = form.cleaned_data['owner_password']
                owner_user = User.objects.create_superuser(
                    username=username,
                    email='',
                    password=password
                )
                owner_user.groups.add(owner_group)

                # Log setup completion
                AuditLog.objects.create(
                    user=owner_user,
                    action="SETUP_COMPLETED",
                    details=f"Initial setup completed for store: {settings_obj.shop_name}",
                    ip_address=get_client_ip(request)
                )

                # Log the owner in directly
                login(request, owner_user)
                messages.success(request, f"Welcome to {settings_obj.shop_name}! Initial setup is complete.")
                return redirect('dashboard')
    else:
        form = SetupWizardForm()

    return render(request, 'setup.html', {'form': form})


def user_login_view(request):
    """Login view with role redirection."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            log_audit(request, "LOGIN", f"User logged in: {user.username}")
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'login.html')


def user_logout_view(request):
    """Logs out user and redirects to login."""
    if request.user.is_authenticated:
        log_audit(request, "LOGOUT", f"User logged out: {request.user.username}")
    logout(request)
    return redirect('login')


def manifest_view(request):
    """Serves PWA web app manifest."""
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='application/manifest+json')
    except Exception:
        return HttpResponse('{}', content_type='application/manifest+json')


def sw_view(request):
    """Serves PWA service worker script."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='application/javascript')
    except Exception:
        return HttpResponse('// sw not found', content_type='application/javascript')


def logo_view(request):
    """Direct fallback to serve store logo."""
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpg')
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            return HttpResponse(f.read(), content_type='image/jpeg')
    return HttpResponse(status=404)


# ==========================================
# 2. DASHBOARD & WI-FI NETWORK INFO
# ==========================================

def format_indian_currency(val):
    """Formats numeric values into Indian numbering system (e.g. 1,25,000.00)."""
    if val is None:
        return '0.00'
    d = Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    s = f'{d:.2f}'
    parts = s.split('.')
    integer_part, decimal_part = parts[0], parts[1]
    is_negative = integer_part.startswith('-')
    if is_negative:
        integer_part = integer_part[1:]
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        other_digits = integer_part[:-3]
        grouped = []
        while other_digits:
            grouped.insert(0, other_digits[-2:])
            other_digits = other_digits[:-2]
        res = ','.join(grouped) + ',' + last_three
    else:
        res = integer_part
    if is_negative:
        res = '-' + res
    return f'{res}.{decimal_part}'


@login_required
def dashboard_view(request):
    """
    Store dashboard view with efficient aggregations:
    - Greeting by time of day & date
    - Hero today's sales with yesterday comparison & bill count
    - Today's sales by payment mode (Cash, UPI, Card, Credit)
    - Flat 7-day sales bar chart
    - Up to 6 lowest stock items at or below reorder level
    - Recent 5 completed bills
    - Credit outstanding total
    - Today's profit (Owner only)
    """
    now = timezone.localtime()
    today = now.date()
    yesterday = today - timedelta(days=1)
    is_owner = is_owner_user(request.user)

    # 1. Greeting by time of day
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # 2. Today's sales & bill count
    today_bills = Bill.objects.filter(created_at__date=today, status='COMPLETED')
    today_sales = today_bills.aggregate(total=Coalesce(Sum('total_amount'), Decimal('0.00')))['total']
    today_bills_count = today_bills.count()
    formatted_today_sales = format_indian_currency(today_sales)
    today_bills_label = f"{today_bills_count} bill" if today_bills_count == 1 else f"{today_bills_count} bills"

    # Yesterday comparison
    yesterday_sales = Bill.objects.filter(created_at__date=yesterday, status='COMPLETED').aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']
    sales_diff = today_sales - yesterday_sales
    if sales_diff > 0:
        sales_diff_text = f"Up ₹{format_indian_currency(sales_diff)} from yesterday"
        sales_diff_dir = "up"
    elif sales_diff < 0:
        sales_diff_text = f"Down ₹{format_indian_currency(abs(sales_diff))} from yesterday"
        sales_diff_dir = "down"
    else:
        sales_diff_text = "Equal to yesterday"
        sales_diff_dir = "equal"

    # 3. Today by payment mode (Cash, UPI, Card, Credit)
    modes_agg = today_bills.aggregate(
        cash=Coalesce(Sum('cash_paid'), Decimal('0.00')),
        upi=Coalesce(Sum('upi_paid'), Decimal('0.00')),
        card=Coalesce(Sum('card_paid'), Decimal('0.00')),
        credit=Coalesce(Sum('credit_paid'), Decimal('0.00')),
    )
    payment_modes = [
        {'name': 'Cash', 'amount': modes_agg['cash'], 'formatted': format_indian_currency(modes_agg['cash'])},
        {'name': 'UPI', 'amount': modes_agg['upi'], 'formatted': format_indian_currency(modes_agg['upi'])},
        {'name': 'Card', 'amount': modes_agg['card'], 'formatted': format_indian_currency(modes_agg['card'])},
        {'name': 'Credit', 'amount': modes_agg['credit'], 'formatted': format_indian_currency(modes_agg['credit'])},
    ]
    for m in payment_modes:
        m['pct'] = int((m['amount'] / today_sales) * 100) if today_sales > 0 else 0

    # 4. Last 7 days sales (flat bar chart query)
    start_7_days = today - timedelta(days=6)
    sales_7_qs = (
        Bill.objects.filter(
            created_at__date__gte=start_7_days,
            created_at__date__lte=today,
            status='COMPLETED'
        )
        .values('created_at__date')
        .annotate(daily_total=Coalesce(Sum('total_amount'), Decimal('0.00')))
    )
    sales_7_map = {row['created_at__date']: row['daily_total'] for row in sales_7_qs}
    max_day_sale = max([sales_7_map.get(start_7_days + timedelta(days=i), Decimal('0.00')) for i in range(7)] or [Decimal('1.00')])

    last_7_days = []
    for i in range(7):
        day = start_7_days + timedelta(days=i)
        day_total = sales_7_map.get(day, Decimal('0.00'))
        pct = int((day_total / max_day_sale) * 100) if max_day_sale > 0 else 0
        is_current = (day == today)
        last_7_days.append({
            'date': day,
            'day_name': 'Today' if is_current else day.strftime('%a'),
            'day_num': day.strftime('%d'),
            'total': day_total,
            'formatted': format_indian_currency(day_total),
            'height_pct': max(4, pct) if day_total > 0 else 0,
            'is_today': is_current,
        })

    # 5. Low stock: 6 lowest products at or below reorder level
    low_stock_qs = (
        Product.objects.filter(is_active=True)
        .annotate(calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0))
        .filter(calculated_stock__lte=F('reorder_level'))
        .order_by('calculated_stock')
    )
    low_stock_count = low_stock_qs.count()
    low_stock_items = []
    for p in low_stock_qs[:6]:
        reorder = p.reorder_level if p.reorder_level > 0 else 1
        pct = max(5, min(100, int((p.calculated_stock / reorder) * 100)))
        low_stock_items.append({
            'brand': p.brand,
            'name': p.name,
            'size_ml': p.size_ml,
            'stock': p.calculated_stock,
            'reorder': p.reorder_level,
            'pct': pct,
        })

    # 6. Recent 5 bills
    recent_bills_qs = (
        Bill.objects.filter(status='COMPLETED')
        .select_related('created_by')
        .order_by('-created_at')[:5]
    )
    recent_bills = []
    for b in recent_bills_qs:
        local_dt = timezone.localtime(b.created_at)
        recent_bills.append({
            'id': b.id,
            'bill_number': b.bill_number,
            'time_str': local_dt.strftime('%H:%M'),
            'date_str': local_dt.strftime('%d %b'),
            'is_today': (local_dt.date() == today),
            'amount': b.total_amount,
            'formatted': format_indian_currency(b.total_amount),
            'payment_mode': b.get_payment_mode_display(),
            'cashier': b.created_by.username if b.created_by else 'Staff',
        })

    # 7. Total outstanding credit
    total_credit = Customer.objects.aggregate(
        total=Coalesce(Sum('current_balance'), Decimal('0.00'))
    )['total']
    formatted_total_credit = format_indian_currency(total_credit)

    # 8. Owner only: today's profit
    today_profit = Decimal('0.00')
    today_margin = "0.0%"
    if is_owner:
        profit_agg = BillItem.objects.filter(
            bill__created_at__date=today,
            bill__status='COMPLETED'
        ).aggregate(
            revenue=Coalesce(Sum('total_price'), Decimal('0.00')),
            cost=Coalesce(Sum(F('quantity') * F('cost_price'), output_field=DecimalField(max_digits=12, decimal_places=2)), Decimal('0.00'))
        )
        t_rev = profit_agg['revenue']
        t_cost = profit_agg['cost']
        today_profit = t_rev - t_cost
        if t_rev > 0:
            today_margin = f"{((today_profit / t_rev) * 100):.1f}%"
    formatted_today_profit = format_indian_currency(today_profit)

    context = {
        # Preserved variables
        'today': today,
        'today_sales': today_sales,
        'today_bills_count': today_bills_count,
        'low_stock_count': low_stock_count,
        'total_credit': total_credit,
        'is_owner': is_owner,
        'local_ip': get_local_ip(),

        # Redesign specific variables
        'greeting': greeting,
        'today_bills_label': today_bills_label,
        'formatted_today_sales': formatted_today_sales,
        'yesterday_sales': yesterday_sales,
        'sales_diff_text': sales_diff_text,
        'sales_diff_dir': sales_diff_dir,
        'payment_modes': payment_modes,
        'last_7_days': last_7_days,
        'low_stock_items': low_stock_items,
        'recent_bills': recent_bills,
        'formatted_total_credit': formatted_total_credit,
        'today_profit': today_profit,
        'today_profit_formatted': formatted_today_profit,
        'today_margin': today_margin,
    }
    return render(request, 'dashboard.html', context)


@login_required
def network_info_view(request):
    """Displays local IP address and instructions to connect phones over shop Wi-Fi."""
    local_ip = get_local_ip()
    url = f"http://{local_ip}:8000"
    return render(request, 'network_info.html', {'local_ip': local_ip, 'phone_url': url})


# ==========================================
# 3. INVENTORY MANAGEMENT
# ==========================================

@login_required
def product_list_view(request):
    """Searchable product catalog showing live calculated stock."""
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    low_stock = request.GET.get('low_stock', '')

    products = Product.objects.filter(is_active=True).annotate(
        calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
    ).order_by('brand', 'name')

    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(brand__icontains=query) | 
            Q(barcode__icontains=query)
        )
    if category:
        products = products.filter(category=category)
    if low_stock == '1':
        products = [p for p in products if p.calculated_stock <= p.reorder_level]

    context = {
        'products': products,
        'query': query,
        'selected_category': category,
        'categories': CATEGORY_CHOICES,
        'low_stock_filter': low_stock,
    }
    return render(request, 'inventory/list.html', context)


@login_required
def product_create_view(request):
    """Create new product with optional opening stock."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        opening_stock = request.POST.get('opening_stock', '0').strip()
        if form.is_valid():
            with transaction.atomic():
                product = form.save()
                qty = int(opening_stock) if opening_stock.isdigit() else 0
                if qty > 0:
                    StockMovement.objects.create(
                        product=product,
                        movement_type='OPENING',
                        quantity=qty,
                        reference_id='INITIAL-SETUP',
                        created_by=request.user,
                        notes='Opening stock on product creation'
                    )
                log_audit(request, "PRODUCT_CREATE", f"Created product: {product.brand} {product.name} (Qty: {qty})")
                messages.success(request, f"Product '{product.name}' added successfully.")
                return redirect('product_list')
    else:
        form = ProductForm()

    return render(request, 'inventory/form.html', {'form': form, 'title': 'Add New Product', 'is_edit': False})


@login_required
def product_edit_view(request, product_id):
    """Edit existing product. Cashiers cannot change MRP or purchase price."""
    product = get_object_or_404(Product, id=product_id)
    is_owner = is_owner_user(request.user)

    if request.method == 'POST':
        old_mrp = product.mrp
        old_cost = product.purchase_price
        form = ProductForm(request.POST, instance=product)

        # Restrict cashiers from editing prices
        if not is_owner:
            form.fields['mrp'].disabled = True
            form.fields['purchase_price'].disabled = True

        if form.is_valid():
            p = form.save(commit=False)
            if not is_owner:
                p.mrp = old_mrp
                p.purchase_price = old_cost
            p.save()

            price_note = ""
            if is_owner and (old_mrp != p.mrp or old_cost != p.purchase_price):
                price_note = f" (Price updated: MRP ₹{old_mrp} -> ₹{p.mrp}, Cost ₹{old_cost} -> ₹{p.purchase_price})"

            log_audit(request, "PRODUCT_EDIT", f"Edited product #{p.id} {p.brand} {p.name}{price_note}")
            messages.success(request, f"Product '{p.name}' updated successfully.")
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
        if not is_owner:
            form.fields['mrp'].disabled = True
            form.fields['purchase_price'].disabled = True

    return render(request, 'inventory/form.html', {'form': form, 'product': product, 'title': 'Edit Product', 'is_edit': True})


@login_required
def product_export_excel_view(request):
    """Exports entire product master with live stock to Excel."""
    products = Product.objects.filter(is_active=True).annotate(
        calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
    ).order_by('brand', 'name')

    is_owner = is_owner_user(request.user)
    if is_owner:
        headers = ['ID', 'Brand', 'Name', 'Category', 'Size (ml)', 'Barcode', 'MRP (₹)', 'Cost Price (₹)', 'Live Stock', 'Reorder Level', 'Quick Pick']
    else:
        headers = ['ID', 'Brand', 'Name', 'Category', 'Size (ml)', 'Barcode', 'MRP (₹)', 'Live Stock', 'Reorder Level', 'Quick Pick']

    rows = []
    for p in products:
        if is_owner:
            rows.append([
                p.id, p.brand, p.name, p.category, p.size_ml, p.barcode or '',
                p.mrp, p.purchase_price, p.calculated_stock, p.reorder_level, 'Yes' if p.is_quick_pick else 'No'
            ])
        else:
            rows.append([
                p.id, p.brand, p.name, p.category, p.size_ml, p.barcode or '',
                p.mrp, p.calculated_stock, p.reorder_level, 'Yes' if p.is_quick_pick else 'No'
            ])

    filename = f"products_inventory_{timezone.localtime().strftime('%Y%m%d_%H%M')}.xlsx"
    return export_queryset_to_excel(filename, 'Products Inventory', headers, rows)


@login_required
@owner_required
def product_import_excel_view(request):
    """Import or update product master from Excel (.xlsx) or CSV."""
    if request.method == 'POST':
        form = ProductExcelImportForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            filename = uploaded_file.name.lower()
            created_count = 0
            updated_count = 0
            errors = []

            try:
                if filename.endswith('.xlsx'):
                    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                    ws = wb.active
                    rows = list(ws.iter_rows(values_only=True))
                    if not rows:
                        messages.error(request, "Excel file is empty.")
                        return redirect('product_import')
                    # Expected format: Brand, Name, Category, Size_ml, Barcode, MRP, Purchase_Price, Reorder_Level, Opening_Stock
                    header = [str(c).strip().lower() if c else '' for c in rows[0]]
                    data_rows = rows[1:]
                elif filename.endswith('.csv'):
                    decoded_file = uploaded_file.read().decode('utf-8', errors='ignore').splitlines()
                    reader = csv.reader(decoded_file)
                    data_rows = list(reader)
                    if not data_rows:
                        messages.error(request, "CSV file is empty.")
                        return redirect('product_import')
                    header = [str(c).strip().lower() for c in data_rows[0]]
                    data_rows = data_rows[1:]
                else:
                    messages.error(request, "Unsupported file format. Please upload .xlsx or .csv")
                    return redirect('product_import')

                with transaction.atomic():
                    for idx, row in enumerate(data_rows, start=2):
                        if not row or not any(row):
                            continue
                        try:
                            # Map columns by index:
                            # 0: Brand, 1: Name, 2: Category, 3: Size, 4: Barcode, 5: MRP, 6: Purchase_Price, 7: Reorder, 8: Opening Stock
                            brand = str(row[0]).strip() if len(row) > 0 and row[0] is not None else "General"
                            name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                            if not name:
                                continue
                            category = str(row[2]).strip() if len(row) > 2 and row[2] is not None else "Other"
                            size_ml = int(row[3]) if len(row) > 3 and str(row[3]).isdigit() else 750
                            barcode = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
                            if barcode == '' or barcode == 'None':
                                barcode = None
                            mrp = Decimal(str(row[5])) if len(row) > 5 and row[5] is not None else Decimal('0.00')
                            cost = Decimal(str(row[6])) if len(row) > 6 and row[6] is not None else Decimal('0.00')
                            reorder = int(row[7]) if len(row) > 7 and str(row[7]).isdigit() else 10
                            opening_stock = int(row[8]) if len(row) > 8 and str(row[8]).isdigit() else 0

                            product = None
                            if barcode:
                                product = Product.objects.filter(barcode=barcode).first()
                            if not product:
                                product = Product.objects.filter(brand__iexact=brand, name__iexact=name, size_ml=size_ml).first()

                            if product:
                                product.mrp = mrp
                                product.purchase_price = cost
                                product.category = category
                                if barcode:
                                    product.barcode = barcode
                                product.reorder_level = reorder
                                product.save()
                                updated_count += 1
                            else:
                                product = Product.objects.create(
                                    brand=brand,
                                    name=name,
                                    category=category,
                                    size_ml=size_ml,
                                    barcode=barcode,
                                    mrp=mrp,
                                    purchase_price=cost,
                                    reorder_level=reorder
                                )
                                created_count += 1
                                if opening_stock > 0:
                                    StockMovement.objects.create(
                                        product=product,
                                        movement_type='OPENING',
                                        quantity=opening_stock,
                                        reference_id='EXCEL-IMPORT',
                                        created_by=request.user,
                                        notes='Opening stock from Excel import'
                                    )
                        except Exception as row_err:
                            errors.append(f"Row {idx}: {str(row_err)}")

                log_audit(request, "PRODUCT_IMPORT", f"Imported products: {created_count} created, {updated_count} updated.")
                messages.success(request, f"Import complete: {created_count} created, {updated_count} updated.")
                if errors:
                    messages.warning(request, f"{len(errors)} rows had errors. Check log for details.")
                return redirect('product_list')

            except Exception as e:
                messages.error(request, f"Error processing import file: {e}")
                return redirect('product_import')
    else:
        form = ProductExcelImportForm()

    return render(request, 'inventory/import.html', {'form': form})


# ==========================================
# 4. PURCHASE ENTRY
# ==========================================

@login_required
@owner_required
def purchase_list_view(request):
    """View supplier purchase invoices."""
    purchases = Purchase.objects.all().select_related('supplier', 'created_by').order_by('-date', '-created_at')
    return render(request, 'purchase/list.html', {'purchases': purchases})


@login_required
@owner_required
def purchase_entry_view(request):
    """Enter stock purchase invoice. Automatically increases stock via StockMovement."""
    suppliers = Supplier.objects.all().order_by('name')
    products = Product.objects.filter(is_active=True).order_by('brand', 'name')

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        invoice_number = request.POST.get('invoice_number', '').strip()
        purchase_date = request.POST.get('date', '').strip() or timezone.now().date().isoformat()
        notes = request.POST.get('notes', '').strip()
        items_json = request.POST.get('items_json', '[]')

        try:
            items_data = json.loads(items_json)
        except Exception:
            messages.error(request, "Invalid items data provided.")
            return redirect('purchase_entry')

        if not items_data:
            messages.error(request, "Please add at least one product item to the invoice.")
            return redirect('purchase_entry')

        supplier = Supplier.objects.filter(id=supplier_id).first() if supplier_id else None

        with transaction.atomic():
            purchase = Purchase.objects.create(
                supplier=supplier,
                invoice_number=invoice_number,
                date=purchase_date,
                notes=notes,
                created_by=request.user
            )

            total_inv_amount = Decimal('0.00')

            for item in items_data:
                prod_id = item.get('product_id')
                qty = int(item.get('quantity', 1))
                price = Decimal(str(item.get('purchase_price', 0)))
                line_total = (price * Decimal(qty)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                prod = get_object_or_404(Product, id=prod_id)

                # Create PurchaseItem
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=prod,
                    quantity=qty,
                    purchase_price=price,
                    total_cost=line_total
                )

                # Update product cost price if changed
                if prod.purchase_price != price:
                    prod.purchase_price = price
                    prod.save(update_fields=['purchase_price', 'updated_at'])

                # Record StockMovement (Stock IN: +qty)
                StockMovement.objects.create(
                    product=prod,
                    movement_type='PURCHASE',
                    quantity=qty,
                    reference_id=f"INV-{invoice_number}",
                    created_by=request.user,
                    notes=f"Purchase from {supplier.name if supplier else 'Direct'}"
                )

                total_inv_amount += line_total

            purchase.total_amount = total_inv_amount
            purchase.save(update_fields=['total_amount'])

            log_audit(request, "PURCHASE_ENTRY", f"Recorded Purchase #{purchase.id} Inv: {invoice_number} (₹{total_inv_amount})")
            messages.success(request, f"Purchase invoice '{invoice_number}' saved successfully. Stock updated.")
            return redirect('purchase_detail', purchase_id=purchase.id)

    return render(request, 'purchase/entry.html', {'suppliers': suppliers, 'products': products})


@login_required
@owner_required
def purchase_detail_view(request, purchase_id):
    """View details of a purchase invoice."""
    purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'created_by'), id=purchase_id)
    items = purchase.items.select_related('product').all()
    return render(request, 'purchase/detail.html', {'purchase': purchase, 'items': items})


# ==========================================
# 5. BILLING SCREEN (POINT OF SALE)
# ==========================================

@login_required
def pos_view(request):
    """High-speed Point of Sale interface designed for barcode scanners and touchscreens."""
    quick_picks = Product.objects.filter(is_active=True, is_quick_pick=True).annotate(
        calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
    ).order_by('brand', 'name')

    customers = Customer.objects.all().order_by('name')

    context = {
        'quick_picks': quick_picks,
        'customers': customers,
        'payment_modes': PAYMENT_MODES,
    }
    return render(request, 'billing/pos.html', context)


@login_required
def api_search_products(request):
    """
    Lightning-fast JSON API for the barcode search bar.
    Searches exact barcode or partial brand/name matches.
    """
    term = request.GET.get('term', '').strip()
    if not term:
        return JsonResponse({'results': []})

    # Exact barcode match takes absolute precedence
    exact_match = Product.objects.filter(barcode=term, is_active=True).first()
    if exact_match:
        return JsonResponse({
            'results': [{
                'id': exact_match.id,
                'brand': exact_match.brand,
                'name': exact_match.name,
                'size_ml': exact_match.size_ml,
                'barcode': exact_match.barcode,
                'mrp': str(exact_match.mrp),
                'stock': exact_match.current_stock,
                'is_exact': True,
            }]
        })

    # Otherwise search partial brand or product name
    matches = Product.objects.filter(
        Q(name__icontains=term) | Q(brand__icontains=term) | Q(barcode__icontains=term),
        is_active=True
    ).annotate(
        calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
    )[:15]

    results = []
    for p in matches:
        results.append({
            'id': p.id,
            'brand': p.brand,
            'name': p.name,
            'size_ml': p.size_ml,
            'barcode': p.barcode or '',
            'mrp': str(p.mrp),
            'stock': p.calculated_stock,
            'is_exact': False,
        })

    return JsonResponse({'results': results})


@login_required
def api_quick_add_product(request):
    """
    Modal quick-add API when an unknown barcode is scanned at the checkout register.
    Allows staff to define the product without leaving or clearing their current cart.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    form = QuickAddProductForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    barcode = form.cleaned_data['barcode'].strip()
    if Product.objects.filter(barcode=barcode).exists():
        return JsonResponse({'success': False, 'error': 'This barcode is already assigned to another item.'}, status=400)

    with transaction.atomic():
        product = Product.objects.create(
            barcode=barcode,
            brand=form.cleaned_data['brand'],
            name=form.cleaned_data['name'],
            category=form.cleaned_data['category'],
            size_ml=form.cleaned_data['size_ml'],
            mrp=form.cleaned_data['mrp'],
            purchase_price=form.cleaned_data['purchase_price'],
            reorder_level=10,
            is_active=True
        )

        opening_qty = form.cleaned_data['opening_stock']
        if opening_qty > 0:
            StockMovement.objects.create(
                product=product,
                movement_type='OPENING',
                quantity=opening_qty,
                reference_id='BARCODE-LINK-INIT',
                created_by=request.user,
                notes='Initial stock on quick barcode link'
            )

        log_audit(request, "QUICK_ADD_PRODUCT", f"Quick added product: {product.brand} {product.name} ({barcode})")

    return JsonResponse({
        'success': True,
        'product': {
            'id': product.id,
            'brand': product.brand,
            'name': product.name,
            'size_ml': product.size_ml,
            'barcode': product.barcode,
            'mrp': str(product.mrp),
            'stock': product.current_stock,
        }
    })


@login_required
def api_process_bill(request):
    """
    Completes checkout inside a single atomic transaction.
    Blocks selling above MRP, deducts live stock, records audit.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required.'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)

    items = data.get('items', [])
    if not items:
        return JsonResponse({'success': False, 'error': 'Cart is empty.'}, status=400)

    payment_mode = data.get('payment_mode', 'CASH').upper()
    customer_id = data.get('customer_id')
    discount_amount = Decimal(str(data.get('discount_amount', '0.00')))
    cash_paid = Decimal(str(data.get('cash_paid', '0.00')))
    upi_paid = Decimal(str(data.get('upi_paid', '0.00')))
    card_paid = Decimal(str(data.get('card_paid', '0.00')))
    credit_paid = Decimal(str(data.get('credit_paid', '0.00')))

    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id).first()

    with transaction.atomic():
        # Calculate subtotal and validate items
        subtotal = Decimal('0.00')
        bill_items_to_create = []

        for item in items:
            prod_id = item.get('product_id')
            qty = int(item.get('quantity', 1))
            unit_price = Decimal(str(item.get('unit_price', '0.00')))
            item_discount = Decimal(str(item.get('discount', '0.00')))

            if qty <= 0:
                return JsonResponse({'success': False, 'error': 'Quantity must be at least 1.'}, status=400)

            product = get_object_or_404(Product, id=prod_id)

            # Block selling above MRP
            if unit_price > product.mrp:
                return JsonResponse({
                    'success': False, 
                    'error': f"Price violation: '{product.name}' cannot be sold above MRP (₹{product.mrp})."
                }, status=400)

            line_total = ((unit_price * Decimal(qty)) - item_discount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if line_total < 0:
                line_total = Decimal('0.00')

            subtotal += line_total
            bill_items_to_create.append({
                'product': product,
                'quantity': qty,
                'unit_price': unit_price,
                'discount': item_discount,
                'total_price': line_total,
                'cost_price': product.purchase_price,
            })

        grand_total = (subtotal - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if grand_total < 0:
            grand_total = Decimal('0.00')

        # Payment split validation
        if payment_mode == 'CASH':
            cash_paid = grand_total
            upi_paid = card_paid = credit_paid = Decimal('0.00')
        elif payment_mode == 'UPI':
            upi_paid = grand_total
            cash_paid = card_paid = credit_paid = Decimal('0.00')
        elif payment_mode == 'CARD':
            card_paid = grand_total
            cash_paid = upi_paid = credit_paid = Decimal('0.00')
        elif payment_mode == 'CREDIT':
            if not customer:
                return JsonResponse({'success': False, 'error': 'A customer must be selected for Credit sales.'}, status=400)
            credit_paid = grand_total
            cash_paid = upi_paid = card_paid = Decimal('0.00')
        elif payment_mode == 'SPLIT':
            split_sum = cash_paid + upi_paid + card_paid + credit_paid
            if split_sum != grand_total:
                return JsonResponse({
                    'success': False, 
                    'error': f"Split total (₹{split_sum}) does not match Grand Total (₹{grand_total})."
                }, status=400)
            if credit_paid > 0 and not customer:
                return JsonResponse({'success': False, 'error': 'Customer must be selected if paying part on credit.'}, status=400)

        # Generate unique Bill Number
        bill_number = generate_bill_number()

        # Create Bill record
        bill = Bill.objects.create(
            bill_number=bill_number,
            created_by=request.user,
            customer=customer,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total_amount=grand_total,
            payment_mode=payment_mode,
            cash_paid=cash_paid,
            upi_paid=upi_paid,
            card_paid=card_paid,
            credit_paid=credit_paid,
            status='COMPLETED'
        )

        # Create BillItems and StockMovements
        for bi in bill_items_to_create:
            BillItem.objects.create(
                bill=bill,
                product=bi['product'],
                quantity=bi['quantity'],
                unit_price=bi['unit_price'],
                discount=bi['discount'],
                total_price=bi['total_price'],
                cost_price=bi['cost_price']
            )

            # Record Stock Out (-qty)
            StockMovement.objects.create(
                product=bi['product'],
                movement_type='SALE',
                quantity=-bi['quantity'],
                reference_id=bill.bill_number,
                created_by=request.user,
                notes=f"Bill #{bill.bill_number}"
            )

        # Update Customer balance if credit was used
        if credit_paid > 0 and customer:
            customer.current_balance = (customer.current_balance + credit_paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            customer.save(update_fields=['current_balance'])

        log_audit(request, "SALE_COMPLETED", f"Issued {bill.bill_number}: ₹{grand_total} via {payment_mode}")

    return JsonResponse({
        'success': True,
        'bill_id': bill.id,
        'bill_number': bill.bill_number,
        'receipt_url': f"/billing/receipt/{bill.id}/?autoprint=1"
    })


@login_required
def receipt_view(request, bill_id):
    """
    Printable 80mm thermal receipt formatted specifically for POS slip printers.
    Includes shop details, line items, breakdown, and return policy footer.
    """
    bill = get_object_or_404(Bill.objects.select_related('customer', 'created_by'), id=bill_id)
    items = bill.items.select_related('product').all()
    autoprint = request.GET.get('autoprint', '0') == '1'

    context = {
        'bill': bill,
        'items': items,
        'autoprint': autoprint,
    }
    return render(request, 'billing/receipt.html', context)


@login_required
def bill_list_view(request):
    """Search and browse historical bills."""
    query = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date', '').strip()
    status_filter = request.GET.get('status', '').strip()

    bills = Bill.objects.all().select_related('customer', 'created_by').order_by('-created_at')

    if query:
        bills = bills.filter(
            Q(bill_number__icontains=query) | 
            Q(customer__name__icontains=query) | 
            Q(customer__phone__icontains=query)
        )
    if date_filter:
        bills = bills.filter(created_at__date=date_filter)
    if status_filter:
        bills = bills.filter(status=status_filter)

    context = {
        'bills': bills[:100],  # Limit to 100 recent for speed
        'query': query,
        'date_filter': date_filter,
        'status_filter': status_filter,
    }
    return render(request, 'billing/bill_list.html', context)


@login_required
@owner_required
def bill_cancel_view(request, bill_id):
    """
    Bill Cancellation (Owner Only).
    Reverses stock reduction via StockMovement, returns credit balance, and logs audit.
    """
    bill = get_object_or_404(Bill, id=bill_id)

    if bill.status == 'CANCELLED':
        messages.warning(request, f"Bill #{bill.bill_number} is already cancelled.")
        return redirect('bill_list')

    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '').strip()
        if not reason:
            messages.error(request, "A cancellation reason is required.")
            return render(request, 'billing/cancel_confirm.html', {'bill': bill})

        with transaction.atomic():
            bill.status = 'CANCELLED'
            bill.cancelled_at = timezone.now()
            bill.cancelled_by = request.user
            bill.cancellation_reason = reason
            bill.save()

            # Return stock items
            for item in bill.items.all():
                StockMovement.objects.create(
                    product=item.product,
                    movement_type='CANCEL',
                    quantity=item.quantity,  # Positive quantity restores stock
                    reference_id=f"CANCEL-{bill.bill_number}",
                    created_by=request.user,
                    notes=f"Stock return on bill cancellation: {reason}"
                )

            # Reverse customer credit if used
            if bill.credit_paid > 0 and bill.customer:
                bill.customer.current_balance = (bill.customer.current_balance - bill.credit_paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                bill.customer.save(update_fields=['current_balance'])

            log_audit(
                request, 
                "BILL_CANCEL", 
                f"Cancelled {bill.bill_number} (₹{bill.total_amount}). Reason: {reason}"
            )

        messages.success(request, f"Bill #{bill.bill_number} cancelled successfully. Inventory restored.")
        return redirect('bill_list')

    return render(request, 'billing/cancel_confirm.html', {'bill': bill})


# ==========================================
# 6. CREDIT CUSTOMERS & PAYMENTS
# ==========================================

@login_required
def customer_list_view(request):
    """Browse credit customers and outstanding balances."""
    query = request.GET.get('q', '').strip()
    customers = Customer.objects.all().order_by('name')
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))

    return render(request, 'customers/list.html', {'customers': customers, 'query': query})


@login_required
def customer_create_view(request):
    """Add a new customer for credit sales."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            c = form.save()
            log_audit(request, "CUSTOMER_CREATE", f"Created customer: {c.name} ({c.phone})")
            messages.success(request, f"Customer '{c.name}' added.")
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/form.html', {'form': form, 'title': 'Add Credit Customer'})


@login_required
def customer_ledger_view(request, customer_id):
    """Full statement of customer's credit bills and payments received."""
    customer = get_object_or_404(Customer, id=customer_id)
    bills = customer.bills.all().order_by('-created_at')
    payments = customer.payments.all().order_by('-date', '-created_at')

    return render(request, 'customers/ledger.html', {
        'customer': customer,
        'bills': bills,
        'payments': payments,
    })


@login_required
def credit_payment_create_view(request):
    """Record payment received from a customer, reducing outstanding balance."""
    initial = {}
    customer_id = request.GET.get('customer')
    if customer_id:
        initial['customer'] = customer_id

    if request.method == 'POST':
        form = CreditPaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.received_by = request.user
                payment.save()

                # Deduct customer balance
                cust = payment.customer
                cust.current_balance = (cust.current_balance - payment.amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                cust.save(update_fields=['current_balance'])

                log_audit(
                    request, 
                    "CREDIT_PAYMENT", 
                    f"Received ₹{payment.amount} from {cust.name} via {payment.payment_mode}"
                )

            messages.success(request, f"Payment of ₹{payment.amount} recorded for {cust.name}.")
            return redirect('customer_ledger', customer_id=cust.id)
    else:
        form = CreditPaymentForm(initial=initial)

    return render(request, 'customers/payment_form.html', {'form': form})


# ==========================================
# 7. OWNER REPORTS (WITH EXCEL EXPORT)
# ==========================================

@login_required
@owner_required
def report_daily_sales_view(request):
    """Sales report broken down by payment mode."""
    start_date = request.GET.get('start_date', timezone.localtime().date().isoformat())
    end_date = request.GET.get('end_date', timezone.localtime().date().isoformat())

    bills = Bill.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status='COMPLETED'
    )

    summary = bills.aggregate(
        total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
        cash_total=Coalesce(Sum('cash_paid'), Decimal('0.00')),
        upi_total=Coalesce(Sum('upi_paid'), Decimal('0.00')),
        card_total=Coalesce(Sum('card_paid'), Decimal('0.00')),
        credit_total=Coalesce(Sum('credit_paid'), Decimal('0.00')),
        bill_count=Count('id')
    )

    if request.GET.get('export') == 'excel':
        headers = ['Bill No', 'Date Time', 'Cashier', 'Customer', 'Payment Mode', 'Subtotal (₹)', 'Discount (₹)', 'Grand Total (₹)']
        rows = []
        for b in bills.order_by('-created_at'):
            rows.append([
                b.bill_number, b.created_at, b.created_by.username,
                b.customer.name if b.customer else 'Walk-in',
                b.get_payment_mode_display(), b.subtotal, b.discount_amount, b.total_amount
            ])
        # Summary row
        rows.append([])
        rows.append(['TOTALS', '', '', '', '', '', '', summary['total_sales']])
        return export_queryset_to_excel(f"daily_sales_{start_date}_to_{end_date}.xlsx", "Daily Sales", headers, rows)

    return render(request, 'reports/daily_sales.html', {
        'bills': bills.order_by('-created_at'),
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
@owner_required
def report_daily_closing_view(request):
    """End-of-day register closing report."""
    target_date = request.GET.get('date', timezone.localtime().date().isoformat())
    
    bills = Bill.objects.filter(created_at__date=target_date, status='COMPLETED')
    credit_payments = CreditPayment.objects.filter(date=target_date)

    sales_summary = bills.aggregate(
        total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
        cash_sales=Coalesce(Sum('cash_paid'), Decimal('0.00')),
        upi_sales=Coalesce(Sum('upi_paid'), Decimal('0.00')),
        card_sales=Coalesce(Sum('card_paid'), Decimal('0.00')),
        credit_sales=Coalesce(Sum('credit_paid'), Decimal('0.00')),
        total_bills=Count('id')
    )

    credit_summary = credit_payments.aggregate(
        cash_collected=Coalesce(Sum('amount', filter=Q(payment_mode='CASH')), Decimal('0.00')),
        upi_collected=Coalesce(Sum('amount', filter=Q(payment_mode='UPI')), Decimal('0.00')),
        total_collected=Coalesce(Sum('amount'), Decimal('0.00')),
    )

    # Net drawer cash = cash from sales + cash from credit settlements
    net_cash_in_drawer = sales_summary['cash_sales'] + credit_summary['cash_collected']
    net_upi_received = sales_summary['upi_sales'] + credit_summary['upi_collected']

    if request.GET.get('export') == 'excel':
        headers = ['Category', 'Cash (₹)', 'UPI (₹)', 'Card (₹)', 'Credit (₹)', 'Total (₹)']
        rows = [
            ['Counter Sales', sales_summary['cash_sales'], sales_summary['upi_sales'], sales_summary['card_sales'], sales_summary['credit_sales'], sales_summary['total_sales']],
            ['Customer Credit Settlements', credit_summary['cash_collected'], credit_summary['upi_collected'], 0, 0, credit_summary['total_collected']],
            ['NET TOTAL IN DRAWER / ACCOUNTS', net_cash_in_drawer, net_upi_received, sales_summary['card_sales'], 0, net_cash_in_drawer + net_upi_received + sales_summary['card_sales']]
        ]
        return export_queryset_to_excel(f"closing_report_{target_date}.xlsx", "Daily Closing", headers, rows)

    return render(request, 'reports/daily_closing.html', {
        'target_date': target_date,
        'sales_summary': sales_summary,
        'credit_summary': credit_summary,
        'net_cash_in_drawer': net_cash_in_drawer,
        'net_upi_received': net_upi_received,
    })


@login_required
@owner_required
def report_profit_by_brand_view(request):
    """Profitability report grouped by brand."""
    start_date = request.GET.get('start_date', (timezone.localtime().date() - timedelta(days=30)).isoformat())
    end_date = request.GET.get('end_date', timezone.localtime().date().isoformat())

    bill_items = BillItem.objects.filter(
        bill__created_at__date__gte=start_date,
        bill__created_at__date__lte=end_date,
        bill__status='COMPLETED'
    ).select_related('product')

    brand_stats = {}
    for item in bill_items:
        brand = item.product.brand
        if brand not in brand_stats:
            brand_stats[brand] = {
                'brand': brand,
                'bottles_sold': 0,
                'revenue': Decimal('0.00'),
                'cost': Decimal('0.00'),
                'profit': Decimal('0.00'),
            }
        qty = item.quantity
        rev = item.total_price
        cost = (item.cost_price * Decimal(qty)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        brand_stats[brand]['bottles_sold'] += qty
        brand_stats[brand]['revenue'] += rev
        brand_stats[brand]['cost'] += cost
        brand_stats[brand]['profit'] += (rev - cost)

    results = list(brand_stats.values())
    for r in results:
        r['margin'] = ((r['profit'] / r['revenue']) * 100).quantize(Decimal('0.1')) if r['revenue'] > 0 else Decimal('0.0')

    results.sort(key=lambda x: x['profit'], reverse=True)

    if request.GET.get('export') == 'excel':
        headers = ['Brand', 'Bottles Sold', 'Total Revenue (₹)', 'Total Cost (₹)', 'Gross Profit (₹)', 'Margin %']
        rows = [[r['brand'], r['bottles_sold'], r['revenue'], r['cost'], r['profit'], f"{r['margin']}%"] for r in results]
        return export_queryset_to_excel(f"profit_by_brand_{start_date}_to_{end_date}.xlsx", "Profit by Brand", headers, rows)

    return render(request, 'reports/profit_by_brand.html', {
        'results': results,
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
@owner_required
def report_low_stock_view(request):
    """Critical low stock report."""
    products = Product.objects.filter(is_active=True).annotate(
        calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
    ).order_by('brand', 'name')

    low_stock_items = [p for p in products if p.calculated_stock <= p.reorder_level]

    if request.GET.get('export') == 'excel':
        headers = ['Brand', 'Product Name', 'Category', 'Size (ml)', 'Barcode', 'Current Stock', 'Reorder Level', 'Deficit']
        rows = []
        for p in low_stock_items:
            rows.append([
                p.brand, p.name, p.category, p.size_ml, p.barcode or '',
                p.calculated_stock, p.reorder_level, max(0, p.reorder_level - p.calculated_stock)
            ])
        return export_queryset_to_excel(f"low_stock_alert_{timezone.localtime().strftime('%Y%m%d')}.xlsx", "Low Stock Alert", headers, rows)

    return render(request, 'reports/low_stock.html', {'low_stock_items': low_stock_items})


@login_required
@owner_required
def report_fast_slow_movers_view(request):
    """Fast and slow moving liquor items over the last 30 days."""
    cutoff = timezone.localtime().date() - timedelta(days=30)
    
    items = BillItem.objects.filter(
        bill__created_at__date__gte=cutoff,
        bill__status='COMPLETED'
    ).values(
        'product__id', 'product__brand', 'product__name', 'product__size_ml', 'product__mrp'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total_price')
    ).order_by('-total_sold')

    if request.GET.get('export') == 'excel':
        headers = ['Brand', 'Product Name', 'Size (ml)', 'MRP (₹)', 'Bottles Sold (30 Days)', 'Revenue (₹)']
        rows = []
        for i in items:
            rows.append([
                i['product__brand'], i['product__name'], i['product__size_ml'],
                i['product__mrp'], i['total_sold'], i['total_revenue']
            ])
        return export_queryset_to_excel("fast_slow_movers_30days.xlsx", "Fast Slow Movers", headers, rows)

    return render(request, 'reports/fast_slow_movers.html', {'items': items})


@login_required
@owner_required
def report_credit_outstanding_view(request):
    """Outstanding credit balances for all customers."""
    customers = Customer.objects.filter(current_balance__gt=0).order_by('-current_balance')
    total_balance = customers.aggregate(total=Coalesce(Sum('current_balance'), Decimal('0.00')))['total']

    if request.GET.get('export') == 'excel':
        headers = ['Customer Name', 'Phone', 'Address', 'Credit Limit (₹)', 'Outstanding Balance (₹)']
        rows = [[c.name, c.phone, c.address, c.credit_limit, c.current_balance] for c in customers]
        rows.append([])
        rows.append(['TOTAL OUTSTANDING', '', '', '', total_balance])
        return export_queryset_to_excel("credit_outstanding.xlsx", "Credit Balances", headers, rows)

    return render(request, 'reports/credit_outstanding.html', {
        'customers': customers,
        'total_balance': total_balance,
    })


# ==========================================
# 8. SETTINGS, BACKUP, & AUDIT LOG
# ==========================================

@login_required
@owner_required
def shop_settings_view(request):
    """Update store details, licence numbers, and backup destination."""
    settings_obj = ShopSettings.get_settings()
    if request.method == 'POST':
        form = ShopSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            log_audit(request, "SETTINGS_UPDATE", "Updated shop settings and profile.")
            messages.success(request, "Store settings saved successfully.")
            return redirect('shop_settings')
    else:
        form = ShopSettingsForm(instance=settings_obj)
    return render(request, 'settings/shop_settings.html', {'form': form})


@login_required
@owner_required
def backup_management_view(request):
    """
    Backup and restore management.
    Uses SQLite's live backup API for 100% corruption-free online backups.
    """
    backup_dir = os.path.join(settings.DATA_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # 1. Action: Manual "Backup Now"
    if request.method == 'POST' and 'action_backup' in request.POST:
        now_str = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        dest_filename = f"shop_{now_str}.db"
        dest_path = os.path.join(backup_dir, dest_filename)

        source_db = settings.DATABASES['default']['NAME']
        try:
            # Safely use SQLite's backup API
            src_conn = sqlite3.connect(source_db)
            dst_conn = sqlite3.connect(dest_path)
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # Optional copy to USB / secondary drive
            shop_settings = ShopSettings.get_settings()
            secondary = shop_settings.secondary_backup_path.strip()
            sec_msg = ""
            if secondary and os.path.exists(secondary):
                sec_path = os.path.join(secondary, dest_filename)
                shutil.copy2(dest_path, sec_path)
                sec_msg = f" Also copied to secondary drive ({secondary})."

            log_audit(request, "BACKUP_NOW", f"Created backup: {dest_filename}")
            messages.success(request, f"Backup created successfully: {dest_filename}.{sec_msg}")
        except Exception as e:
            messages.error(request, f"Backup failed: {e}")
        return redirect('backup_management')

    # 2. Action: "Restore From Backup"
    if request.method == 'POST' and 'action_restore' in request.POST:
        uploaded_backup = request.FILES.get('backup_file')
        if not uploaded_backup:
            messages.error(request, "Please choose a valid .db backup file to restore.")
            return redirect('backup_management')

        source_db = settings.DATABASES['default']['NAME']
        temp_restore_path = os.path.join(backup_dir, 'temp_restore.db')

        try:
            with open(temp_restore_path, 'wb+') as dest:
                for chunk in uploaded_backup.chunks():
                    dest.write(chunk)

            # Validate that the uploaded file is a genuine SQLite database
            test_conn = sqlite3.connect(temp_restore_path)
            cursor = test_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_product';")
            if not cursor.fetchone():
                test_conn.close()
                os.remove(temp_restore_path)
                messages.error(request, "Invalid backup file: Core database tables are missing.")
                return redirect('backup_management')
            test_conn.close()

            # Pre-restore safety snapshot
            safety_file = os.path.join(backup_dir, f"pre_restore_safety_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            if os.path.exists(source_db):
                shutil.copy2(source_db, safety_file)

            # Restore using backup API
            res_src = sqlite3.connect(temp_restore_path)
            res_dst = sqlite3.connect(source_db)
            with res_dst:
                res_src.backup(res_dst)
            res_dst.close()
            res_src.close()

            if os.path.exists(temp_restore_path):
                os.remove(temp_restore_path)

            log_audit(request, "BACKUP_RESTORE", f"Restored database from uploaded backup: {uploaded_backup.name}")
            messages.success(request, "Database restored successfully! All data has been updated.")
        except Exception as e:
            messages.error(request, f"Restore failed: {e}")
        return redirect('backup_management')

    # List existing backups in C:\ProgramData\LiquorShop\backups
    existing_backups = []
    for f in os.listdir(backup_dir):
        if f.endswith('.db') and not f.startswith('temp_'):
            full_p = os.path.join(backup_dir, f)
            stat = os.stat(full_p)
            existing_backups.append({
                'filename': f,
                'size_kb': round(stat.st_size / 1024, 1),
                'created_at': datetime.fromtimestamp(stat.st_mtime),
            })
    existing_backups.sort(key=lambda x: x['created_at'], reverse=True)

    return render(request, 'settings/backup_management.html', {
        'existing_backups': existing_backups,
        'data_dir': settings.DATA_DIR,
    })


@login_required
@owner_required
def audit_log_view(request):
    """View tamper-evident audit trail."""
    query = request.GET.get('q', '').strip()
    logs = AuditLog.objects.all().select_related('user')
    if query:
        logs = logs.filter(Q(action__icontains=query) | Q(details__icontains=query))
    return render(request, 'settings/audit_log.html', {'logs': logs[:200], 'query': query})
