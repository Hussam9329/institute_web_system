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
    const isNegative = amount < 0;
    const absAmount = Math.abs(amount);
    const formatted = absAmount.toLocaleString('en-US').replace(/,/g, '.');
    return isNegative ? '-' + formatted + ' د.ع' : formatted + ' د.ع';
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
 * عرض رسالة تنبيه محسّنة
 * @param {string} message - نص الرسالة
 * @param {string} type - نوع الرسالة (success, error, warning, info)
 * @param {number} duration - مدة العرض بالملي ثانية
 */
function showAlert(message, type = 'info', duration = 4000) {
    const container = document.getElementById('alert-container');
    if (!container) return;

    const icons = {
        success: 'fa-check',
        error: 'fa-xmark',
        warning: 'fa-exclamation',
        info: 'fa-info'
    };

    const alertId = 'alert-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);

    const alertHTML = `
        <div id="${alertId}" class="custom-alert ${type}" role="alert">
            <div class="d-flex align-items-center gap-3 p-3">
                <div class="alert-icon-wrap">
                    <i class="fas ${icons[type] || icons.info}"></i>
                </div>
                <div class="alert-text">${message}</div>
                <button type="button" class="alert-close-btn" onclick="dismissAlert('${alertId}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="alert-progress" style="animation-duration: ${duration}ms;"></div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', alertHTML);

    // إخفاء تلقائي بعد المدة المحددة
    setTimeout(() => {
        dismissAlert(alertId);
    }, duration);
}

/**
 * إزالة تنبيه مع أنيميشن خروج
 * @param {string} alertId - معرف التنبيه
 */
function dismissAlert(alertId) {
    const alertEl = document.getElementById(alertId);
    if (!alertEl) return;

    // إزالة من DOM مباشرة
    if (alertEl.parentNode) {
        alertEl.parentNode.removeChild(alertEl);
    }
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

/**
 * تحويل المبلغ المدخل (بالألف) إلى القيمة الفعلية
 * مثال: 150 → 150000
 * يستخدم معالجة السلسلة النصية لتجنب أخطاء الفاصلة العائمة في JavaScript
 * (مثال: 0.3 * 1000 = 299.999... بدون هذه المعالجة)
 */
function toFullAmount(thousands) {
    const str = String(thousands).trim();
    if (!str || str === '0') return 0;
    const val = parseFloat(str);
    if (isNaN(val) || val <= 0) return 0;

    // معالجة السلسلة النصية لتجنب أخطاء الفاصلة العائمة
    if (str.includes('.')) {
        const [intPart, decPart] = str.split('.');
        const paddedDec = (decPart + '000').substring(0, 3);
        const result = parseInt(intPart + paddedDec, 10);
        return result > 0 ? result : 0;
    }
    return val * 1000;
}

/**
 * تصدير جدول HTML إلى ملف CSV
 * @param {string} tableId - معرف الجدول
 * @param {string} filename - اسم الملف بدون الامتداد
 */
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    if (!table) {
        showAlert('الجدول غير موجود', 'error');
        return;
    }

    const rows = table.querySelectorAll('tbody tr');
    if (!rows || rows.length === 0) {
        showAlert('لا توجد بيانات للتصدير', 'warning');
        return;
    }

    const csvRows = [];

    // استخراج عناوين الأعمدة من thead
    const headerCells = table.querySelectorAll('thead th');
    const headers = [];
    headerCells.forEach(th => {
        // إزالة أي عناصر HTML داخل th والحصول على النص فقط
        headers.push(th.textContent.trim().replace(/"/g, '""'));
    });
    csvRows.push(headers.join(','));

    // استخراج صفوف البيانات من tbody (فقط الصفوف المرئية)
    rows.forEach(row => {
        // تخطي صفوف الإجمالي أو الصفوف المخفية
        if (row.style.display === 'none') return;
        if (row.closest('tfoot')) return;

        const cells = row.querySelectorAll('td');
        const rowData = [];
        cells.forEach(cell => {
            // الحصول على النص وتنظيفه
            let text = cell.textContent.trim();
            // إزالة المسافات المتعددة
            text = text.replace(/\s+/g, ' ');
            // تنسيق النصوص التي تحتوي فواصل أو علامات اقتباس
            if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                text = '"' + text.replace(/"/g, '""') + '"';
            }
            rowData.push(text);
        });
        csvRows.push(rowData.join(','));
    });

    if (csvRows.length <= 1) {
        showAlert('لا توجد بيانات للتصدير', 'warning');
        return;
    }

    // إضافة UTF-8 BOM لدعم العربية في Excel
    const BOM = '\uFEFF';
    const csvContent = BOM + csvRows.join('\n');

    // إنشاء رابط التحميل
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename + '.csv';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

    showAlert('تم تصدير البيانات بنجاح', 'success');
}

/**
 * تهريب HTML لمنع هجمات XSS
 * @param {string} str - النص المراد تهريبه
 * @returns {string} النص المهرب
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// تصدير الدوال للاستخدام العام
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.getTodayDate = getTodayDate;
window.showAlert = showAlert;
window.dismissAlert = dismissAlert;
window.confirmAction = confirmAction;
window.apiRequest = apiRequest;
window.populateSelect = populateSelect;
window.toggleButtonLoading = toggleButtonLoading;
window.copyToClipboard = copyToClipboard;
window.printElement = printElement;
window.toFullAmount = toFullAmount;
window.exportTableToCSV = exportTableToCSV;
window.escapeHtml = escapeHtml;

// ============================================
// Searchable Select Component
// NOTE: تم نقل makeSearchableSelect إلى searchable-select.js الموحّد
// الواجهة متوافقة تماماً — window.makeSearchableSelect لا تزال متاحة من هناك
// ============================================
