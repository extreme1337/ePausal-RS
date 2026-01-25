// ePauša RS - Main JavaScript

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Load dark mode preference
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add('dark-mode');
    }
    
    // Initialize password match check
    initPasswordMatch();
    
    // Initialize card name capitalize
    initCardNameCapitalize();
});

// ============================================
// DARK MODE
// ============================================
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDark);
    
    // Update icon
    const icon = document.querySelector('.dark-mode-toggle i');
    if (icon) {
        icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// ============================================
// LANGUAGE SWITCHER
// ============================================
function changeLanguage(lang) {
    window.location.href = `/change-language/${lang}/`;
}

// ============================================
// FORM HELPERS
// ============================================
function toggleForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.classList.toggle('hidden');
    }
}

function toggleNewInvoice() {
    toggleForm('newInvoiceForm');
}

function toggleNewPayment() {
    toggleForm('newPaymentForm');
}

// ============================================
// AJAX HELPERS
// ============================================
async function submitFormAjax(formId, url, successCallback) {
    const form = document.getElementById(formId);
    const formData = new FormData(form);
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (successCallback) {
                successCallback(data);
            }
        } else {
            alert('❌ Greška: ' + (data.error || 'Nepoznata greška'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Greška pri slanju zahtjeva');
    }
}

// ============================================
// INBOX - Confirm All
// ============================================
async function confirmAll() {
    const formData = new FormData();
    formData.append('confirm_all', 'true');
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        const response = await fetch(window.location.href, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Uvezeno ${data.count} prihoda iz Email Inbox-a!`);
            window.location.reload();
        }
    } catch (error) {
        alert('❌ Greška pri potvrđivanju');
    }
}

// ============================================
// ADMIN - Retry/Skip
// ============================================
async function retryRequest(id) {
    try {
        const response = await fetch(`/admin/retry/${id}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Request uspješno izvršen!');
            window.location.reload();
        } else {
            alert('❌ Request ponovo neuspješan');
        }
    } catch (error) {
        alert('❌ Greška');
    }
}

async function skipRequest(id) {
    try {
        const response = await fetch(`/admin/skip/${id}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Request preskočen');
            window.location.reload();
        }
    } catch (error) {
        alert('❌ Greška');
    }
}

// ============================================
// DRAG & DROP FILE UPLOAD
// ============================================
function setupDragDrop(dropZoneId, fileInputId, uploadCallback) {
    const dropZone = document.getElementById(dropZoneId);
    const fileInput = document.getElementById(fileInputId);
    
    if (!dropZone || !fileInput) return;
    
    // Click to upload
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Drag over
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-blue-500', 'bg-blue-50');
    });
    
    // Drag leave
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-blue-500', 'bg-blue-50');
    });
    
    // Drop
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-blue-500', 'bg-blue-50');
        
        const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
        if (files.length > 0 && uploadCallback) {
            uploadCallback(files);
        } else {
            alert('Molimo upload-ujte samo PDF fajlove');
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0 && uploadCallback) {
            uploadCallback(files);
        }
    });
}

// ============================================
// REGISTRATION FORM - PASSWORD MATCH
// ============================================
function initPasswordMatch() {
    const passwordConfirm = document.getElementById('password_confirm');
    if (!passwordConfirm) return;

    passwordConfirm.addEventListener('input', function() {
        const password = document.getElementById('password').value;
        const confirm = this.value;
        const matchEl = document.getElementById('passwordMatch');
        
        if (!matchEl) return;
        
        if (confirm.length === 0) {
            matchEl.textContent = '';
            return;
        }
        
        if (password === confirm) {
            matchEl.textContent = '✓ Lozinke se poklapaju';
            matchEl.className = 'text-xs mt-1 text-green-600';
        } else {
            matchEl.textContent = '✗ Lozinke se ne poklapaju';
            matchEl.className = 'text-xs mt-1 text-red-600';
        }
    });
}

// ============================================
// JIB FORMATTING (13 cifara)
// ============================================
function formatJIB(input) {
    // Ukloni sve osim cifara
    let value = input.value.replace(/\D/g, '');
    
    // Ograniči na 13
    value = value.substring(0, 13);
    
    input.value = value;
    
    // Update counter
    const counter = document.getElementById('jibCount');
    if (counter) {
        counter.textContent = value.length;
    }
    
    // Validacija boje
    if (value.length === 13) {
        input.classList.remove('border-red-500');
        input.classList.add('border-green-500');
    } else if (value.length > 0) {
        input.classList.remove('border-green-500');
        input.classList.add('border-yellow-500');
    } else {
        input.classList.remove('border-green-500', 'border-yellow-500');
    }
}

// ============================================
// RAČUN FORMATTING (XXX-XXX-XXXXXXXXXXX-XX)
// ============================================
function formatRacun(input) {
    // Ukloni sve osim cifara
    let value = input.value.replace(/\D/g, '');
    
    // Ograniči na 18 cifara
    value = value.substring(0, 18);
    
    // Dodaj crtice
    let formatted = '';
    if (value.length > 0) {
        formatted = value.substring(0, 3);
    }
    if (value.length > 3) {
        formatted += '-' + value.substring(3, 6);
    }
    if (value.length > 6) {
        formatted += '-' + value.substring(6, 17);
    }
    if (value.length > 17) {
        formatted += '-' + value.substring(17, 19);
    }
    
    input.value = formatted;
    
    // Validacija
    if (value.length === 18) {
        input.classList.remove('border-red-500');
        input.classList.add('border-green-500');
    } else if (value.length > 0) {
        input.classList.remove('border-green-500');
        input.classList.add('border-yellow-500');
    } else {
        input.classList.remove('border-green-500', 'border-yellow-500');
    }
}

// ============================================
// CARD NUMBER FORMATTING (XXXX XXXX XXXX XXXX)
// ============================================
function formatCardNumber(input) {
    // Ukloni sve osim cifara
    let value = input.value.replace(/\D/g, '');
    
    // Ograniči na 16
    value = value.substring(0, 16);
    
    // Dodaj razmake svakih 4 cifre
    let formatted = '';
    for (let i = 0; i < value.length; i++) {
        if (i > 0 && i % 4 === 0) {
            formatted += ' ';
        }
        formatted += value[i];
    }
    
    input.value = formatted;
    
    // Detect card type
    const label = input.parentElement.querySelector('label');
    if (!label) return;
    
    if (value.startsWith('4')) {
        label.innerHTML = 'Broj kartice * <span class="text-blue-600 text-xs ml-2">Visa</span>';
    } else if (value.startsWith('5')) {
        label.innerHTML = 'Broj kartice * <span class="text-orange-600 text-xs ml-2">Mastercard</span>';
    } else {
        label.innerHTML = 'Broj kartice *';
    }
}

// ============================================
// EXPIRY DATE FORMATTING (MM/YY)
// ============================================
function formatExpiry(input) {
    // Ukloni sve osim cifara
    let value = input.value.replace(/\D/g, '');
    
    // Ograniči na 4
    value = value.substring(0, 4);
    
    // Dodaj / poslije 2 cifre
    if (value.length >= 2) {
        input.value = value.substring(0, 2) + '/' + value.substring(2);
    } else {
        input.value = value;
    }
    
    // Validacija mjeseca
    const month = parseInt(value.substring(0, 2));
    if (value.length >= 2) {
        if (month < 1 || month > 12) {
            input.classList.add('border-red-500');
        } else {
            input.classList.remove('border-red-500');
        }
    }
}

// ============================================
// CVV FORMATTING (3 cifre)
// ============================================
function formatCVV(input) {
    // Samo cifre
    let value = input.value.replace(/\D/g, '');
    
    // Max 3
    input.value = value.substring(0, 3);
}

// ============================================
// AUTO-CAPITALIZE CARD NAME
// ============================================
function initCardNameCapitalize() {
    const cardName = document.getElementById('card_name');
    if (!cardName) return;
    
    cardName.addEventListener('input', function() {
        this.value = this.value.toUpperCase();
    });
}

// ============================================
// FORM VALIDATION
// ============================================
function validateForm() {
    const ime = document.getElementById('ime')?.value.trim();
    const prezime = document.getElementById('prezime')?.value.trim();
    const email = document.getElementById('email')?.value.trim();
    const password = document.getElementById('password')?.value;
    const passwordConfirm = document.getElementById('password_confirm')?.value;
    const jib = document.getElementById('jib')?.value.replace(/\D/g, '');
    const racun = document.getElementById('racun')?.value.replace(/\D/g, '');
    const cardNumber = document.getElementById('card_number')?.value.replace(/\D/g, '');
    const cardExpiry = document.getElementById('card_expiry')?.value;
    const cardCVV = document.getElementById('card_cvv')?.value;
    const cardName = document.getElementById('card_name')?.value.trim();
    
    // Password match
    if (password && passwordConfirm && password !== passwordConfirm) {
        alert('❌ Lozinke se ne poklapaju');
        return false;
    }
    
    // Password length
    if (password && password.length < 8) {
        alert('❌ Lozinka mora imati najmanje 8 karaktera');
        return false;
    }
    
    // JIB validation
    if (jib && jib.length !== 13) {
        alert('❌ JIB mora imati tačno 13 cifara');
        document.getElementById('jib')?.focus();
        return false;
    }
    
    // Racun validation
    if (racun && racun.length !== 18) {
        alert('❌ Broj računa mora imati 18 cifara');
        document.getElementById('racun')?.focus();
        return false;
    }
    
    // Card number validation
    if (cardNumber && cardNumber.length !== 16) {
        alert('❌ Broj kartice mora imati 16 cifara');
        document.getElementById('card_number')?.focus();
        return false;
    }
    
    // Expiry validation
    if (cardExpiry && !/^\d{2}\/\d{2}$/.test(cardExpiry)) {
        alert('❌ Datum isteka mora biti u formatu MM/YY');
        document.getElementById('card_expiry')?.focus();
        return false;
    }
    
    if (cardExpiry) {
        const [month, year] = cardExpiry.split('/');
        if (parseInt(month) < 1 || parseInt(month) > 12) {
            alert('❌ Mjesec mora biti između 01 i 12');
            document.getElementById('card_expiry')?.focus();
            return false;
        }
    }
    
    // CVV validation
    if (cardCVV && cardCVV.length !== 3) {
        alert('❌ CVV mora imati 3 cifre');
        document.getElementById('card_cvv')?.focus();
        return false;
    }
    
    // Card name validation
    if (cardName && cardName.length < 3) {
        alert('❌ Unesite ime i prezime sa kartice');
        document.getElementById('card_name')?.focus();
        return false;
    }
    
    // Combine ime + prezime
    if (ime && prezime) {
        const fullName = ime + ' ' + prezime;
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'full_name';
        hiddenInput.value = fullName;
        document.querySelector('form')?.appendChild(hiddenInput);
    }
    
    // Show loading
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Procesiranje...';
    }
    
    return true;
}

// ============================================
// VALIDATION HELPERS
// ============================================
function validateJIB(jib) {
    return /^\d{13}$/.test(jib);
}

function validateRacun(racun) {
    return /^\d{3}-\d{3}-\d{11}-\d{2}$/.test(racun);
}

function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ============================================
// HELPERS
// ============================================
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function showLoading(show = true) {
    let loader = document.getElementById('globalLoader');
    
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'globalLoader';
        loader.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        loader.innerHTML = '<div class="spinner"></div>';
        document.body.appendChild(loader);
    }
    
    loader.style.display = show ? 'flex' : 'none';
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('sr-RS', {
        style: 'currency',
        currency: 'BAM',
        minimumFractionDigits: 2
    }).format(amount);
}

function formatDate(date) {
    return new Intl.DateTimeFormat('sr-RS').format(new Date(date));
}

// ============================================
// NOTIFICATIONS
// ============================================
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white animate-fade-in z-50 ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 'bg-blue-500'
    }`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} mr-2"></i>
        ${message}
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// ============================================
// PRICING CALCULATOR
// ============================================
function calculatePrice(basePrice, billingPeriod, promoCode) {
    let price = basePrice;
    
    // Annual discount (17%)
    if (billingPeriod === 'yearly') {
        price = basePrice * 10; // 10 mjeseci cijena
    }
    
    // Promo code discount
    const promoCodes = {
        'EARLYBIRD100': { discount: 1.0, duration: 6 },
        'REFERRAL20': { discount: 0.2, duration: 999 },
        'FRIEND50': { discount: 0.5, duration: 3 },
        'LAUNCH2026': { discount: 0.3, duration: 6 }
    };
    
    if (promoCode && promoCodes[promoCode.toUpperCase()]) {
        const promo = promoCodes[promoCode.toUpperCase()];
        price = price * (1 - promo.discount);
    }
    
    return Math.round(price);
}

// ============================================
// STRIPE INTEGRATION
// ============================================
async function processPayment(planName, amount, cardElement) {
    showLoading(true);
    
    // Simulate payment processing
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    showLoading(false);
    
    return {
        success: true,
        message: 'Plaćanje uspješno!'
    };
}

// ============================================
// CHART INITIALIZATION
// ============================================
function initChart(canvasId, chartData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    return new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

// ============================================
// EXPORT TO PDF/CSV
// ============================================
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ============================================
// AUTO-SAVE FORM
// ============================================
function autoSaveForm(formId, storageKey) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    // Load saved data
    const saved = localStorage.getItem(storageKey);
    if (saved) {
        const data = JSON.parse(saved);
        Object.keys(data).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) input.value = data[key];
        });
    }
    
    // Save on change
    form.addEventListener('input', () => {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        localStorage.setItem(storageKey, JSON.stringify(data));
    });
    
    // Clear on submit
    form.addEventListener('submit', () => {
        localStorage.removeItem(storageKey);
    });
}