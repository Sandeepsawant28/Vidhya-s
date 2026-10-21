from django import forms
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Product, Supplier, Customer, CreditPayment, ShopSettings, CATEGORY_CHOICES

class SetupWizardForm(forms.Form):
    """Form used strictly during the first launch to create the store and owner."""
    shop_name = forms.CharField(
        max_length=200, 
        initial="My Liquor Shop",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Royal Wine & Beer Shop'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Shop Address, Main Road'}),
        required=True
    )
    phone = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact phone number'})
    )
    licence_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'State Liquor Licence / FL Number'})
    )
    gst_number = forms.CharField(
        max_length=50, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GSTIN (Optional)'})
    )
    owner_username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Owner login username'})
    )
    owner_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Minimum 6 characters'}),
        min_length=6
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Re-enter password'}),
        min_length=6
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('owner_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match. Please re-enter carefully.')
        return cleaned_data


class ProductForm(forms.ModelForm):
    """Complete product management form."""
    class Meta:
        model = Product
        fields = [
            'brand', 'name', 'category', 'size_ml', 
            'barcode', 'mrp', 'purchase_price', 
            'reorder_level', 'is_quick_pick', 'is_active'
        ]
        widgets = {
            'brand': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. McDowell\'s'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. No. 1 Celebration'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'size_ml': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '750'}),
            'barcode': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Scan or enter barcode'}),
            'mrp': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '10'}),
            'is_quick_pick': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_mrp(self):
        mrp = self.cleaned_data.get('mrp')
        if mrp is not None and mrp <= 0:
            raise forms.ValidationError("MRP must be greater than zero.")
        return mrp

    def clean_purchase_price(self):
        purchase_price = self.cleaned_data.get('purchase_price')
        if purchase_price is not None and purchase_price < 0:
            raise forms.ValidationError("Purchase price cannot be negative.")
        return purchase_price


class QuickAddProductForm(forms.Form):
    """Modal quick-add form when an unknown barcode is scanned at the cash register."""
    barcode = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-input', 'readonly': 'readonly', 'id': 'quick-barcode'})
    )
    brand = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-input', 'id': 'quick-brand'}))
    name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input', 'id': 'quick-name'}))
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, widget=forms.Select(attrs={'class': 'form-select', 'id': 'quick-category'}))
    size_ml = forms.IntegerField(initial=750, widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'quick-size'}))
    mrp = forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'id': 'quick-mrp'}))
    purchase_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        initial=Decimal('0.00'), 
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'id': 'quick-purchase-price'})
    )
    opening_stock = forms.IntegerField(
        initial=10, 
        widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'quick-opening-stock'})
    )


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Supplier/Distributor Name'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Agent / Sales Rep'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact Phone'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email (optional)'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Address'}),
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'credit_limit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Customer Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Mobile Number'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Customer Address'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
        }


class CreditPaymentForm(forms.ModelForm):
    class Meta:
        model = CreditPayment
        fields = ['customer', 'amount', 'payment_mode', 'date', 'reference_note']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': 'Amount paid in ₹'}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'reference_note': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. GPay UPI Ref 123456'}),
        }


class ShopSettingsForm(forms.ModelForm):
    class Meta:
        model = ShopSettings
        fields = ['shop_name', 'address', 'phone', 'licence_number', 'gst_number', 'secondary_backup_path', 'receipt_footer']
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'licence_number': forms.TextInput(attrs={'class': 'form-input'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-input'}),
            'secondary_backup_path': forms.TextInput(attrs={'class': 'form-input', 'placeholder': r'e.g. E:\ShopBackups'}),
            'receipt_footer': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }


class ProductExcelImportForm(forms.Form):
    """Form for importing product catalog from an Excel (.xlsx) or CSV file."""
    file = forms.FileField(
        label="Select Excel (.xlsx) or CSV File",
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.xlsx, .csv'})
    )
