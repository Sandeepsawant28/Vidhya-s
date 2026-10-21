// High-Speed Point of Sale (POS) Engine for Barcode Scanners and Cash Register
document.addEventListener('DOMContentLoaded', function () {
    let cart = [];
    let currentPaymentMode = 'CASH';

    const searchInput = document.getElementById('search-input');
    const searchDropdown = document.getElementById('search-dropdown');
    const cartItemsTable = document.getElementById('cart-items-body');
    const subtotalDisplay = document.getElementById('pos-subtotal');
    const grandTotalDisplay = document.getElementById('pos-grand-total');
    const overallDiscountInput = document.getElementById('pos-discount-input');
    const customerSelect = document.getElementById('pos-customer-select');
    const customerWrapper = document.getElementById('pos-customer-wrapper');
    const completeSaleBtn = document.getElementById('complete-sale-btn');

    // Unknown Barcode Modal elements
    const unknownModal = document.getElementById('unknown-barcode-modal');
    const quickBarcodeField = document.getElementById('quick-barcode');
    const quickAddForm = document.getElementById('quick-add-form');
    const cancelModalBtn = document.getElementById('modal-cancel-btn');

    // Split Payment Modal elements
    const splitModal = document.getElementById('split-payment-modal');
    const splitCashInput = document.getElementById('split-cash');
    const splitUpiInput = document.getElementById('split-upi');
    const splitCardInput = document.getElementById('split-card');
    const splitCreditInput = document.getElementById('split-credit');
    const splitTotalCheck = document.getElementById('split-total-check');
    const splitConfirmBtn = document.getElementById('split-confirm-btn');
    const splitCancelBtn = document.getElementById('split-cancel-btn');

    let splitData = { cash: 0, upi: 0, card: 0, credit: 0 };

    // 1. Maintain focus on search bar for barcode scanners
    function refocusSearch() {
        if (
            document.activeElement.tagName !== 'INPUT' && 
            document.activeElement.tagName !== 'SELECT' && 
            document.activeElement.tagName !== 'TEXTAREA' &&
            !unknownModal.classList.contains('open') &&
            !splitModal.classList.contains('open')
        ) {
            searchInput.focus();
        }
    }
    refocusSearch();
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.modal-content') && !e.target.closest('input') && !e.target.closest('select')) {
            refocusSearch();
        }
    });

    // 2. Barcode scanner & search input handling
    let searchDebounceTimer = null;
    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const term = searchInput.value.trim();
            if (!term) return;
            handleSearchTerm(term, true);
        }
    });

    searchInput.addEventListener('input', function () {
        clearTimeout(searchDebounceTimer);
        const term = searchInput.value.trim();
        if (term.length < 2) {
            searchDropdown.style.display = 'none';
            return;
        }
        searchDebounceTimer = setTimeout(() => {
            handleSearchTerm(term, false);
        }, 250);
    });

    function handleSearchTerm(term, isEnterPressed) {
        fetch(`/billing/api/search/?term=${encodeURIComponent(term)}`)
            .then(res => res.json())
            .then(data => {
                const results = data.results || [];
                if (results.length === 1 && (isEnterPressed || results[0].is_exact)) {
                    // Exact barcode match or direct enter
                    addToCart(results[0]);
                    searchInput.value = '';
                    searchDropdown.style.display = 'none';
                    refocusSearch();
                } else if (results.length > 0) {
                    showDropdownResults(results);
                } else if (isEnterPressed) {
                    // Unknown barcode scanned!
                    searchDropdown.style.display = 'none';
                    openUnknownBarcodeModal(term);
                }
            })
            .catch(err => console.error("Search error:", err));
    }

    function showDropdownResults(items) {
        searchDropdown.innerHTML = '';
        items.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'search-item' + (index === 0 ? ' selected' : '');
            div.innerHTML = `
                <div>
                    <strong>${item.brand}</strong> ${item.name} (${item.size_ml}ml)
                    <div style="font-size: 0.75rem; color: #94a3b8;">Barcode: ${item.barcode || 'N/A'} | Stock: ${item.stock}</div>
                </div>
                <div style="font-weight: bold; color: #f59e0b;">₹${item.mrp}</div>
            `;
            div.addEventListener('click', () => {
                addToCart(item);
                searchInput.value = '';
                searchDropdown.style.display = 'none';
                refocusSearch();
            });
            searchDropdown.appendChild(div);
        });
        searchDropdown.style.display = 'block';
    }

    // Hide dropdown when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.search-wrapper')) {
            searchDropdown.style.display = 'none';
        }
    });

    // 3. Quick-pick button clicks
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const product = {
                id: parseInt(this.dataset.id),
                brand: this.dataset.brand,
                name: this.dataset.name,
                size_ml: this.dataset.size,
                mrp: parseFloat(this.dataset.mrp),
                stock: parseInt(this.dataset.stock || 0)
            };
            addToCart(product);
            refocusSearch();
        });
    });

    // 4. Cart management
    function addToCart(product) {
        const existing = cart.find(item => item.id === product.id);
        if (existing) {
            existing.quantity += 1;
        } else {
            cart.push({
                id: product.id,
                brand: product.brand,
                name: product.name,
                size_ml: product.size_ml,
                barcode: product.barcode || '',
                mrp: parseFloat(product.mrp),
                unit_price: parseFloat(product.mrp),
                quantity: 1,
                discount: 0,
                stock: product.stock !== undefined ? parseInt(product.stock) : 999
            });
        }
        renderCart();
    }

    window.updateQty = function (index, delta) {
        cart[index].quantity += delta;
        if (cart[index].quantity <= 0) {
            cart.splice(index, 1);
        }
        renderCart();
        refocusSearch();
    };

    window.setQty = function (index, val) {
        const q = parseInt(val);
        if (!isNaN(q) && q > 0) {
            cart[index].quantity = q;
        } else {
            cart.splice(index, 1);
        }
        renderCart();
        refocusSearch();
    };

    window.removeItem = function (index) {
        cart.splice(index, 1);
        renderCart();
        refocusSearch();
    };

    function renderCart() {
        cartItemsTable.innerHTML = '';
        let subtotal = 0;

        if (cart.length === 0) {
            cartItemsTable.innerHTML = `<tr><td colspan="5" class="text-center" style="color: #64748b; padding: 2rem 0;">Cart is empty. Scan an item or pick above.</td></tr>`;
            subtotalDisplay.innerText = '₹0.00';
            grandTotalDisplay.innerText = '₹0.00';
            return;
        }

        cart.forEach((item, idx) => {
            const lineTotal = (item.unit_price * item.quantity) - item.discount;
            subtotal += lineTotal;

            const isOutOfStock = item.stock < item.quantity;
            const stockWarning = isOutOfStock 
                ? `<span class="badge badge-danger" style="margin-left: 4px; font-size: 0.65rem;" title="Only ${item.stock} in stock!">Low/0 Stock</span>` 
                : '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>
                    <div style="font-weight: 600;">${item.name}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">${item.brand} (${item.size_ml}ml)${stockWarning}</div>
                </td>
                <td class="text-right">₹${item.unit_price.toFixed(2)}</td>
                <td class="text-center">
                    <div style="display: inline-flex; align-items: center; gap: 3px;">
                        <button type="button" class="cart-qty-btn" onclick="updateQty(${idx}, -1)">-</button>
                        <input type="number" value="${item.quantity}" min="1" style="width: 42px; text-align: center; background: #334155; border: 1px solid #475569; color: #fff; border-radius: 4px; font-size: 0.85rem;" onchange="setQty(${idx}, this.value)">
                        <button type="button" class="cart-qty-btn" onclick="updateQty(${idx}, 1)">+</button>
                    </div>
                </td>
                <td class="text-right" style="font-weight: 700; color: #f8fafc;">₹${lineTotal.toFixed(2)}</td>
                <td class="text-center">
                    <button type="button" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 1.1rem;" onclick="removeItem(${idx})">&times;</button>
                </td>
            `;
            cartItemsTable.appendChild(tr);
        });

        const overallDiscount = parseFloat(overallDiscountInput.value) || 0;
        const grandTotal = Math.max(0, subtotal - overallDiscount);

        subtotalDisplay.innerText = `₹${subtotal.toFixed(2)}`;
        grandTotalDisplay.innerText = `₹${grandTotal.toFixed(2)}`;
    }

    overallDiscountInput.addEventListener('input', renderCart);

    // 5. Payment mode selection
    document.querySelectorAll('.pay-mode-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.pay-mode-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentPaymentMode = this.dataset.mode;

            if (currentPaymentMode === 'CREDIT') {
                customerWrapper.style.display = 'block';
            } else if (currentPaymentMode === 'SPLIT') {
                customerWrapper.style.display = 'block';
                openSplitModal();
            } else {
                customerWrapper.style.display = 'none';
            }
        });
    });

    // 6. Split Payment Modal Handling
    function openSplitModal() {
        const grandTotal = parseFloat(grandTotalDisplay.innerText.replace('₹', '')) || 0;
        splitCashInput.value = (grandTotal).toFixed(2);
        splitUpiInput.value = '0.00';
        splitCardInput.value = '0.00';
        splitCreditInput.value = '0.00';
        updateSplitCalculations();
        splitModal.classList.add('open');
    }

    function updateSplitCalculations() {
        const grandTotal = parseFloat(grandTotalDisplay.innerText.replace('₹', '')) || 0;
        const c = parseFloat(splitCashInput.value) || 0;
        const u = parseFloat(splitUpiInput.value) || 0;
        const cd = parseFloat(splitCardInput.value) || 0;
        const cr = parseFloat(splitCreditInput.value) || 0;
        const sum = c + u + cd + cr;

        splitData = { cash: c, upi: u, card: cd, credit: cr };
        const diff = grandTotal - sum;

        if (Math.abs(diff) < 0.01) {
            splitTotalCheck.innerText = `Split matches Grand Total (₹${sum.toFixed(2)})`;
            splitTotalCheck.style.color = '#10b981';
            splitConfirmBtn.disabled = false;
        } else {
            splitTotalCheck.innerText = `Difference: ₹${diff.toFixed(2)} (Split: ₹${sum.toFixed(2)} vs Total: ₹${grandTotal.toFixed(2)})`;
            splitTotalCheck.style.color = '#ef4444';
            splitConfirmBtn.disabled = true;
        }
    }

    [splitCashInput, splitUpiInput, splitCardInput, splitCreditInput].forEach(inp => {
        inp.addEventListener('input', updateSplitCalculations);
    });

    splitConfirmBtn.addEventListener('click', () => {
        splitModal.classList.remove('open');
        refocusSearch();
    });
    splitCancelBtn.addEventListener('click', () => {
        splitModal.classList.remove('open');
        // Switch back to Cash
        document.querySelectorAll('.pay-mode-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('.pay-mode-btn[data-mode="CASH"]').classList.add('active');
        currentPaymentMode = 'CASH';
        customerWrapper.style.display = 'none';
        refocusSearch();
    });

    // 7. Unknown Barcode Modal Handling
    function openUnknownBarcodeModal(barcode) {
        quickBarcodeField.value = barcode;
        unknownModal.classList.add('open');
        document.getElementById('quick-brand').focus();
    }

    cancelModalBtn.addEventListener('click', () => {
        unknownModal.classList.remove('open');
        refocusSearch();
    });

    quickAddForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const formData = new FormData(quickAddForm);

        fetch('/billing/api/quick-add/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                unknownModal.classList.remove('open');
                quickAddForm.reset();
                addToCart(data.product);
                searchInput.value = '';
                refocusSearch();
            } else {
                alert(data.error || 'Failed to add product. Check form inputs.');
            }
        })
        .catch(err => {
            console.error("Error quick adding product:", err);
            alert("Network or server error while adding product.");
        });
    });

    // 8. Complete Sale Checkout
    completeSaleBtn.addEventListener('click', function () {
        if (cart.length === 0) {
            alert("Cart is empty. Please add items before checking out.");
            return;
        }

        const grandTotal = parseFloat(grandTotalDisplay.innerText.replace('₹', '')) || 0;
        const discountAmount = parseFloat(overallDiscountInput.value) || 0;
        const customerId = customerSelect.value || null;

        if (currentPaymentMode === 'CREDIT' && !customerId) {
            alert("Please select a customer for Credit sale.");
            customerSelect.focus();
            return;
        }

        completeSaleBtn.disabled = true;
        completeSaleBtn.innerText = "Processing Sale...";

        const payload = {
            items: cart.map(item => ({
                product_id: item.id,
                quantity: item.quantity,
                unit_price: item.unit_price,
                discount: item.discount
            })),
            payment_mode: currentPaymentMode,
            discount_amount: discountAmount,
            customer_id: customerId,
            cash_paid: currentPaymentMode === 'SPLIT' ? splitData.cash : 0,
            upi_paid: currentPaymentMode === 'SPLIT' ? splitData.upi : 0,
            card_paid: currentPaymentMode === 'SPLIT' ? splitData.card : 0,
            credit_paid: currentPaymentMode === 'SPLIT' ? splitData.credit : 0,
        };

        fetch('/billing/api/process-bill/', {
            method: 'POST',
            body: JSON.stringify(payload),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(res => res.json())
        .then(data => {
            completeSaleBtn.disabled = false;
            completeSaleBtn.innerText = "CHARGE & PRINT (F2 / Enter)";

            if (data.success) {
                // Open thermal slip receipt in popup or new window for printing
                window.open(data.receipt_url, '_blank', 'width=380,height=600,toolbar=0,menubar=0,location=0');
                
                // Reset cart for next customer
                cart = [];
                overallDiscountInput.value = '0';
                renderCart();
                searchInput.value = '';
                refocusSearch();
            } else {
                alert("Sale Error: " + data.error);
            }
        })
        .catch(err => {
            completeSaleBtn.disabled = false;
            completeSaleBtn.innerText = "CHARGE & PRINT (F2 / Enter)";
            console.error("Sale error:", err);
            alert("Failed to complete sale. Check server connection.");
        });
    });

    // Helper: CSRF Cookie reader
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
