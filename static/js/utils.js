// ============================================
// utils.js - دوال مساعدة عامة
// ============================================

/**
 * تنسيق المبلغ بالدينار العراقي
 * @param {number} amount - المبلغ (integer)
 * @returns {string} المبلغ منسق
 */
function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '0 د.ع';
    return amount.toLocaleString('ar-IQ') + ' د.ع';
}

/**
 * تنسيق التاريخ
 * @param {string} dateStr - التاريخ بصيغة YYYY-MM-DD
 * @returns {string} التاريخ بصيغة DD/MM/YYYY
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

/**
 * الحصول على تاريخ اليوم بصيغة YYYY-MM-DD
 * @returns {string}
 */
function getTodayDate() {
    const today = new Date();
    return today.toISOString().split('T')[0];
}

/**
 * عرض رسالة تنبيه
 * @param {string} message - نص الرسالة
 * @param {string} type - نوع الرسالة (success, error, warning, info)
 * @param {number} duration - مدة العرض بالملي ثانية
 */
function showAlert(message, type = 'info', duration = 4000) {
    const container = document.getElementById('alert-container');
    if (!container) return;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const alertHTML = `
        <div class="custom-alert ${type} shadow-lg mb-3" role="alert">
            <div class="d-flex align-items-center gap-3 p-3">
                <i class="fas ${icons[type]} fa-lg"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close btn-close-white" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', alertHTML);

    // إخفاء تلقائي بعد المدة المحددة
    setTimeout(() => {
        const alerts = container.querySelectorAll('.custom-alert');
        if (alerts.length > 0) {
            alerts[0].remove();
        }
    }, duration);
}

/**
 * تأكيد عملية قبل التنفيذ
 * @param {string} message - رسالة التأكيد
 * @returns {boolean}
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * طلب API عام
 * @param {string} url - عنوان API
 * @param {object} options - خيارات الطلب
 * @returns {Promise<object>}
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'حدث خطأ');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * تحميل قائمة منselect
 * @param {string} selectId - معرف عنصر select
 * @param {Array} items - عناصر القائمة
 * @param {string} valueField - حقل القيمة
 * @param {string} textField - حقل النص
 */
function populateSelect(selectId, items, valueField = 'id', textField = 'name') {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = '<option value="">-- اختر --</option>';
    
    items.forEach(item => {
        const option = document.createElement('option');
        option.value = item[valueField];
        option.textContent = item[textField];
        select.appendChild(option);
    });
}

/**
 * تعطيل/تفعيل زر مؤقتاً
 * @param {string} buttonId - معرف الزر
 * @param {boolean} disable - حالة التعطيل
 * @param {string} text - النص البديل
 */
function toggleButtonLoading(buttonId, disable = true, text = 'جاري المعالجة...') {
    const button = document.getElementById(buttonId);
    if (!button) return;

    if (disable) {
        button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${text}`;
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
    }
}

/**
 * نسخ نص للحافظة
 * @param {string} text - النص المراد نسخه
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showAlert('تم النسخ بنجاح!', 'success');
    } catch (error) {
        console.error('Copy failed:', error);
        showAlert('فشل في النسخ', 'error');
    }
}

/**
 * فتح طباعة نافذة
 * @param {string} elementId - معرف العنصر المراد طباعته
 */
function printElement(elementId) {
    const content = document.getElementById(elementId);
    if (!content) return;

    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html dir="rtl">
        <head>
            <title>طباعة</title>
            <link rel="stylesheet" href="/static/css/print.css">
            <style>
                body { font-family: 'Cairo', sans-serif; }
            </style>
        </head>
        <body>
            ${content.innerHTML}
        </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
}

// تصدير الدوال للاستخدام العام
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.getTodayDate = getTodayDate;
window.showAlert = showAlert;
window.confirmAction = confirmAction;
window.apiRequest = apiRequest;
window.populateSelect = populateSelect;
window.toggleButtonLoading = toggleButtonLoading;
window.copyToClipboard = copyToClipboard;
window.printElement = printElement;