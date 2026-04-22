// ============================================
// app.js - JavaScript رئيسي للتطبيق
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    
    // ===== تحديث الساعة والتاريخ =====
    updateDateTime();
    setInterval(updateDateTime, 1000);
    
    // ===== فحص رسائل URL =====
    checkUrlMessages();
    
    // ===== تهيئة التواريخ =====
    initDateInputs();
    
    // ===== تهيئة tooltips =====
    initTooltips();
    
});

/**
 * تحديث عرض الوقت والتاريخ
 */
function updateDateTime() {
    const datetimeEl = document.getElementById('current-datetime');
    if (!datetimeEl) return;

    const now = new Date();
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    datetimeEl.textContent = now.toLocaleDateString('ar-IQ', options);
}

/**
 * فحص رسائل URL وعرضها
 */
function checkUrlMessages() {
    const params = new URLSearchParams(window.location.search);
    const msg = params.get('msg');
    const error = params.get('error');

    if (msg === 'added') {
        showAlert('✅ تمت الإضافة بنجاح!', 'success');
    } else if (msg === 'updated') {
        showAlert('✅ تم التحديث بنجاح!', 'success');
    } else if (msg === 'deleted') {
        showAlert('✅ تم الحذف بنجاح!', 'success');
    } else if (error === 'not_found') {
        showAlert('❌ العنصر غير موجود!', 'error');
    }

    // تنظيف URL
    if (msg || error) {
        window.history.replaceState({}, '', window.location.pathname);
    }
}

/**
 * تهيئة حقول التاريخ بتاريخ اليوم
 */
function initDateInputs() {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = getTodayDate();

    dateInputs.forEach(input => {
        if (!input.value) {
            input.value = today;
        }
        
        // إضافة حد أقصى (لا يمكن اختيار مستقبل)
        input.max = today;
    });
}

/**
 * تهيئة Tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * التعامل مع أخطاء النموذج
 * @param {Event} event - حدث الإرسال
 * @param {FormElement} form - النموذج
 */
function handleFormError(event, form) {
    event.preventDefault();
    
    // إزالة الأخطاء السابقة
    form.querySelectorAll('.is-invalid').forEach(el => {
        el.classList.remove('is-invalid');
    });
    form.querySelectorAll('.invalid-feedback').forEach(el => {
        el.remove();
    });

    let hasError = false;
    const requiredFields = form.querySelectorAll('[required]');

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = 'هذا الحقل مطلوب';
            field.parentNode.appendChild(feedback);
            
            hasError = true;
        }
    });

    if (hasError) {
        showAlert('يرجى ملء جميع الحقول المطلوبة', 'warning');
        // التركيز على أول حقل خاطئ
        const firstError = form.querySelector('.is-invalid');
        if (firstError) firstError.focus();
    }

    return !hasError;
}

// ===== أحداث عامة =====

// منع إرسال النموذج إذا كان هناك حقول فارغة
document.addEventListener('submit', function(event) {
    const form = event.target;
    if (form.tagName === 'FORM' && !form.hasAttribute('novalidate')) {
        // التحقق الأساسي سيتم بواسطة HTML5 validation
    }
});

// تأكيد قبل مغادرة صفحة بها بيانات غير محفوظة
let formModified = false;
document.addEventListener('input', function(event) {
    if (event.target.tagName === 'INPUT' || 
        event.target.tagName === 'TEXTAREA' || 
        event.target.tagName === 'SELECT') {
        formModified = true;
    }
});

window.addEventListener('beforeunload', function(event) {
    if (formModified) {
        event.preventDefault();
        event.returnValue = '';
    }
});
