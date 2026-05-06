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
        showAlert('تمت الإضافة بنجاح', 'success');
    } else if (msg === 'updated') {
        showAlert('تم التحديث بنجاح', 'success');
    } else if (msg === 'deleted') {
        showAlert('تم الحذف بنجاح', 'success');
    } else if (msg === 'updated_locked') {
        showAlert('تم تحديث الاسم والمادة فقط. لا يمكن تغيير الأقساط والنسب لوجود مدفوعات مسجلة.', 'warning');
    } else if (msg === 'updated_new_type_added') {
        showAlert('تم إضافة نوع التدريس الجديد بنجاح. لا يمكن تغيير البيانات الأخرى لوجود طلاب مرتبطين.', 'success');
    } else if (msg === 'updated_no_change') {
        showAlert('لم يتم تغيير أي بيانات. لا يمكن التعديل بعد ارتباط الطلاب - يمكنك فقط إضافة نوع تدريسي جديد.', 'info');
    } else if (error === 'not_found') {
        showAlert('العنصر المطلوب غير موجود', 'error');
    } else if (error === 'exists') {
        showAlert('هذا العنصر موجود مسبقاً', 'warning');
    } else if (error === 'has_teachers') {
        const count = params.get('count') || 0;
        showAlert('لا يمكن الحذف - يوجد ' + count + ' مدرسين مرتبطين بهذه المادة', 'error');
    } else if (error === 'has_students') {
        const count = params.get('count') || 0;
        const name = params.get('name') || '';
        showAlert('لا يمكن حذف المدرس "' + name + '" - يوجد ' + count + ' طالب مرتبط به', 'error');
    } else if (error === 'no_teaching_type') {
        showAlert('يجب اختيار نوع تدريس واحد على الأقل', 'warning');
    } else if (error === 'cannot_remove_type') {
        showAlert('لا يمكن حذف نوع تدريس مرتبط بطلاب! يمكنك فقط إضافة أنواع تدريس جديدة.', 'error');
    }

    // تنظيف URL - فقط إزالة msg و error مع الحفاظ على باقي المعاملات
    if (msg || error) {
        const params = new URLSearchParams(window.location.search);
        params.delete('msg');
        params.delete('error');
        params.delete('count');
        params.delete('name');
        const remaining = params.toString();
        const newUrl = window.location.pathname + (remaining ? '?' + remaining : '');
        window.history.replaceState({}, '', newUrl);
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


