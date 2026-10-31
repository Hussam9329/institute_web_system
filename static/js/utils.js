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
 * الحصول على تاريخ اليوم بصيغة YYYY-MM-DD (من توقيت الجهاز المحلي)
 * @returns {string}
 */
function getTodayDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * الحصول على التاريخ والوقت الحالي بصيغة YYYY-MM-DD HH:MM:SS (من توقيت الجهاز المحلي)
 * يُستخدم لإرسال التوقيت المحلي للسيرفر بدلاً من توقيت السيرفر
 * @returns {string}
 */
function getClientDateTime() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * عرض رسالة تنبيه محسّنة
 * @param {string} message - نص الرسالة
 * @param {string} type - نوع الرسالة (success, error, warning, info)
 * @param {number} duration - مدة العرض بالملي ثانية
 */
function showAlert(message, type = 'info', duration = 4000) {
    const allowedTypes = ['success', 'error', 'warning', 'info'];
    if (!allowedTypes.includes(type)) {
        type = 'info';
    }

    const container = document.getElementById('alert-container');
    if (!container) return;

    const icons = {
        success: 'fa-check',
        error: 'fa-xmark',
        warning: 'fa-exclamation',
        info: 'fa-info'
    };

    const alertId = 'alert-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);
    duration = Number(duration) || 4000;

    // الهيكل ثابت؛ نص الرسالة يُضاف كنص فقط (textContent) لمنع حقن HTML
    const alertEl = document.createElement('div');
    alertEl.id = alertId;
    alertEl.className = 'custom-alert ' + type;
    alertEl.setAttribute('role', 'alert');
    alertEl.innerHTML = `
            <div class="d-flex align-items-center gap-3 p-3">
                <div class="alert-icon-wrap">
                    <i class="fas ${icons[type] || icons.info}"></i>
                </div>
                <div class="alert-text"></div>
                <button type="button" class="alert-close-btn">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="alert-progress" style="animation-duration: ${duration}ms;"></div>
    `;
    alertEl.querySelector('.alert-text').textContent = (message === null || message === undefined) ? '' : String(message);
    alertEl.querySelector('.alert-close-btn').addEventListener('click', () => dismissAlert(alertId));

    container.appendChild(alertEl);

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
 * عرض رسالة منع الحذف مع السبب
 * @param {string} reason - سبب المنع (اختياري)
 */
function showDeleteBlocked(reason) {
    const message = reason || 'لا يمكن الحذف لأن هذا السجل مرتبط ببيانات أخرى.';
    showAlert(message, 'warning', 7000);
}

/**
 * معالج النقر على أزرار الحذف المحظورة (data-blocked)
 * يبني رسالة السبب ديناميكياً بناءً على بيانات الزر
 */
document.addEventListener('click', function(e) {
    const btn = e.target.closest('[data-blocked]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const type = btn.dataset.blocked;

    if (type === 'student') {
        const name = btn.dataset.studentName || '';
        const activeLinks = parseInt(btn.dataset.activeLinks) || 0;
        const installments = parseInt(btn.dataset.installments) || 0;
        const reasons = [];
        if (activeLinks > 0) reasons.push('مرتبط بـ ' + activeLinks + ' مدرس نشط');
        if (installments > 0) reasons.push('لديه ' + installments + ' قسط مسجل');
        const reasonText = reasons.join(' و ');
        showDeleteBlocked('لا يمكن حذف الطالب "' + name + '" لأنه ' + reasonText + '. احذف الارتباطات والأقساط أولاً.');
    } else if (type === 'teacher') {
        const name = btn.dataset.teacherName || '';
        const students = parseInt(btn.dataset.studentsCount) || 0;
        const installments = parseInt(btn.dataset.installmentsCount) || 0;
        const withdrawals = parseInt(btn.dataset.withdrawalsCount) || 0;
        const schedule = parseInt(btn.dataset.scheduleCount) || 0;
        const reasons = [];
        if (students > 0) reasons.push('لديه ' + students + ' طالب مرتبط');
        if (installments > 0) reasons.push('لديه ' + installments + ' قسط مسجل');
        if (withdrawals > 0) reasons.push('لديه ' + withdrawals + ' سحب مسجل');
        if (schedule > 0) reasons.push('لديه ' + schedule + ' موعد في الجدول');
        const reasonText = reasons.join(' و ');
        showDeleteBlocked('لا يمكن حذف المدرس "' + name + '" لأنه ' + reasonText + '. احذف جميع الارتباطات أولاً.');
    } else if (type === 'subject') {
        const name = btn.dataset.subjectName || '';
        const teachers = parseInt(btn.dataset.teachersCount) || 0;
        if (name && teachers > 0) {
            showDeleteBlocked('لا يمكن حذف مادة "' + name + '" لأنها مرتبطة بـ ' + teachers + ' مدرس. انقل المدرسين إلى مادة أخرى أو احذف ارتباطهم أولاً.');
        } else {
            showDeleteBlocked();
        }
    } else {
        showDeleteBlocked();
    }
});

/**
 * طلب API عام
 * @param {string} url - عنوان API
 * @param {object} options - خيارات الطلب
 * @returns {Promise<object>}
 */
async function apiRequest(url, options = {}) {
    try {
        // دمج الترويسات بعد بقية الخيارات حتى لا تُستبدل ترويسة التوقيت عند تمرير headers
        const { headers: extraHeaders, ...restOptions } = options;
        const response = await fetch(url, {
            ...restOptions,
            headers: {
                'Content-Type': 'application/json',
                'X-Client-Timestamp': getClientDateTime(),
                ...(extraHeaders || {})
            }
        });

        // انتهاء الجلسة: الخادم يعيد 401 أو يحوّل إلى صفحة تسجيل الدخول (HTML)
        const redirectedToLogin = response.redirected && new URL(response.url, window.location.origin).pathname === '/login';
        if (response.status === 401 || redirectedToLogin) {
            redirectToLoginSoon();
            throw new Error('انتهت الجلسة، يرجى تسجيل الدخول مجدداً');
        }

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            throw new Error('استجابة غير متوقعة من الخادم (' + response.status + ')، يرجى تحديث الصفحة والمحاولة مجدداً');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(getApiErrorMessage(data));
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * استخراج رسالة خطأ مقروءة من استجابة الخادم
 * (FastAPI يعيد detail كمصفوفة كائنات في أخطاء التحقق 422)
 * @param {object} data - جسم الاستجابة
 * @returns {string}
 */
function getApiErrorMessage(data) {
    if (!data || typeof data !== 'object') return 'حدث خطأ';
    const detail = data.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (typeof data.message === 'string' && data.message) return data.message;
    if (Array.isArray(detail) && detail.length) {
        const fields = detail
            .map(item => (item && Array.isArray(item.loc)) ? item.loc[item.loc.length - 1] : '')
            .filter(field => field && field !== 'body');
        const uniqueFields = [...new Set(fields)];
        return 'البيانات المدخلة غير صالحة' + (uniqueFields.length ? ' (' + uniqueFields.join('، ') + ')' : '') + '، يرجى التحقق منها';
    }
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
    return 'حدث خطأ';
}

/**
 * تحويل المستخدم إلى صفحة تسجيل الدخول بعد مهلة قصيرة تكفي لقراءة رسالة الخطأ
 */
let _loginRedirectScheduled = false;
function redirectToLoginSoon() {
    if (_loginRedirectScheduled) return;
    _loginRedirectScheduled = true;
    setTimeout(() => { window.location.href = '/login'; }, 1500);
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
 * آمن داخل محتوى العناصر وداخل قيم السمات (يهرّب علامات الاقتباس أيضاً)
 * @param {*} str - النص المراد تهريبه
 * @returns {string} النص المهرب
 */
const HTML_ESCAPE_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, ch => HTML_ESCAPE_MAP[ch]);
}

// تصدير الدوال للاستخدام العام
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.getTodayDate = getTodayDate;
window.getClientDateTime = getClientDateTime;
window.showAlert = showAlert;
window.dismissAlert = dismissAlert;
window.confirmAction = confirmAction;
window.showDeleteBlocked = showDeleteBlocked;
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
