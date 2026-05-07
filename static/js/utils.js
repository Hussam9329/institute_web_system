// ============================================
// utils.js - دوال مساعدة عامة
// ============================================

/**
 * تنسيق المبلغ بالدينار العراقي
 * @param {number} amount - المبلغ (integer)
 * @returns {string} المبلغ منسق
 */
function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '0د.ع';
    return amount.toLocaleString('en-US').replace(/,/g, '.') + 'د.ع';
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
 */
function toFullAmount(thousands) {
    return (parseInt(thousands) || 0) * 1000;
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

// ============================================
// Searchable Select Component
// ============================================

/**
 * تحويل عنصر select إلى قائمة منسدلة مع بحث مباشر
 * يدعم العمل داخل Bootstrap modal بشكل صحيح
 * @param {string} selectId - معرف عنصر select الأصلي
 * @param {object} options - خيارات إضافية { placeholder, searchPlaceholder, onChange }
 * @returns {object} - واجهة التحكم بالمكوّن { setValue, refresh, clear, destroy }
 */
function makeSearchableSelect(selectId, options = {}) {
    const originalSelect = document.getElementById(selectId);
    if (!originalSelect) return null;

    const placeholder = options.placeholder || originalSelect.querySelector('option[value=""]')?.textContent || '-- اختر --';
    const searchPlaceholder = options.searchPlaceholder || 'بحث...';
    const onChangeCallback = options.onChange || null;

    // التحقق مما إذا كنا داخل Bootstrap modal
    const modalParent = originalSelect.closest('.modal');
    const isInsideModal = !!modalParent;

    // إخفاء الـ select الأصلي
    originalSelect.style.display = 'none';

    // إنشاء الحاوي
    const container = document.createElement('div');
    container.className = 'searchable-select';
    container.id = selectId + '_ss';

    // إنشاء العرض
    const display = document.createElement('div');
    display.className = 'ss-display';
    display.innerHTML = '<span class="ss-placeholder">' + placeholder + '</span><i class="fas fa-chevron-down ss-arrow"></i>';

    // إنشاء القائمة المنسدلة
    const dropdown = document.createElement('div');
    dropdown.className = 'ss-dropdown';

    // إنشاء خانة البحث
    const searchWrap = document.createElement('div');
    searchWrap.className = 'ss-search-wrap';
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'ss-search-input';
    searchInput.placeholder = searchPlaceholder;
    searchInput.autocomplete = 'off';
    searchWrap.appendChild(searchInput);

    // إنشاء قائمة الخيارات
    const optionsList = document.createElement('div');
    optionsList.className = 'ss-options';

    // عداد النتائج
    const countDiv = document.createElement('div');
    countDiv.className = 'ss-count';

    dropdown.appendChild(searchWrap);
    dropdown.appendChild(optionsList);
    dropdown.appendChild(countDiv);

    container.appendChild(display);
    container.appendChild(dropdown);

    // إدراج بعد الـ select الأصلي
    originalSelect.parentNode.insertBefore(container, originalSelect.nextSibling);

    // ===== وظائف =====

    function getOptions() {
        const opts = [];
        originalSelect.querySelectorAll('option').forEach(function(opt) {
            opts.push({
                value: opt.value,
                text: opt.textContent,
                dataFee: opt.dataset.fee || ''
            });
        });
        return opts;
    }

    function renderOptions(filter) {
        const allOpts = getOptions();
        const query = (filter || '').toLowerCase().trim();
        optionsList.innerHTML = '';
        let visibleCount = 0;

        allOpts.forEach(function(opt) {
            if (!opt.value) return; // تخطي الخيار الفارغ
            if (query && !opt.text.toLowerCase().includes(query)) return;

            const item = document.createElement('div');
            item.className = 'ss-option';
            if (opt.value === originalSelect.value) item.classList.add('selected');
            item.textContent = opt.text;
            item.dataset.value = opt.value;
            if (opt.dataFee) item.dataset.fee = opt.dataFee;

            item.addEventListener('click', function() {
                selectOption(opt.value, opt.text);
            });

            optionsList.appendChild(item);
            visibleCount++;
        });

        if (visibleCount === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'ss-no-results';
            noResults.textContent = 'لا توجد نتائج';
            optionsList.appendChild(noResults);
        }

        const totalOptions = allOpts.filter(function(o) { return o.value; }).length;
        if (query) {
            countDiv.textContent = visibleCount + ' من ' + totalOptions;
        } else {
            countDiv.textContent = totalOptions + ' عنصر';
        }
    }

    function selectOption(value, text) {
        originalSelect.value = value;
        const selectedSpan = display.querySelector('.ss-selected-text') || display.querySelector('.ss-placeholder');
        if (selectedSpan) {
            if (value) {
                selectedSpan.className = 'ss-selected-text';
                selectedSpan.textContent = text;
            } else {
                selectedSpan.className = 'ss-placeholder';
                selectedSpan.textContent = placeholder;
            }
        } else {
            // أول مرة
            display.innerHTML = '<span class="ss-selected-text">' + text + '</span><i class="fas fa-chevron-down ss-arrow"></i>';
        }

        closeDropdown();

        // تشغيل حدث change على الـ select الأصلي
        const event = new Event('change', { bubbles: true });
        originalSelect.dispatchEvent(event);

        // استدعاء callback مخصص
        if (onChangeCallback) onChangeCallback(value);
    }

    /**
     * حساب موقع القائمة المنسدلة عندما تكون داخل modal
     * يستخدم position: fixed لتجنب القص بسبب overflow على modal-content
     */
    function positionDropdownInModal() {
        var rect = display.getBoundingClientRect();
        var spaceBelow = window.innerHeight - rect.bottom;
        var estimatedHeight = 300;

        dropdown.style.position = 'fixed';
        dropdown.style.width = rect.width + 'px';

        // تحديد الاتجاه: أسفل أو أعلى العنصر
        if (spaceBelow < estimatedHeight && rect.top > spaceBelow) {
            // عرض القائمة فوق العنصر
            dropdown.style.top = 'auto';
            dropdown.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
        } else {
            // عرض القائمة تحت العنصر
            dropdown.style.top = (rect.bottom + 4) + 'px';
            dropdown.style.bottom = 'auto';
        }

        // تحديد الموقع الأفقي (يدعم RTL و LTR)
        dropdown.style.left = rect.left + 'px';
        dropdown.style.right = 'auto';
    }

    /**
     * إعادة تعيين أنماط position: fixed بعد إغلاق القائمة
     */
    function resetDropdownPosition() {
        dropdown.style.position = '';
        dropdown.style.top = '';
        dropdown.style.bottom = '';
        dropdown.style.left = '';
        dropdown.style.right = '';
        dropdown.style.width = '';
    }

    function openDropdown() {
        dropdown.classList.add('show');
        display.classList.add('active');
        searchInput.value = '';
        renderOptions('');

        // داخل modal: استخدام position: fixed لتجنب القص
        if (isInsideModal) {
            positionDropdownInModal();
        }

        setTimeout(function() { searchInput.focus(); }, 50);
    }

    function closeDropdown() {
        dropdown.classList.remove('show');
        display.classList.remove('active');

        // إعادة تعيين الأنماط عند الإغلاق
        if (isInsideModal) {
            resetDropdownPosition();
        }
    }

    function toggleDropdown() {
        if (dropdown.classList.contains('show')) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    // ===== الأحداث =====

    display.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        toggleDropdown();
    });

    // منع Bootstrap modal من سرقة الأحداث
    display.addEventListener('mousedown', function(e) {
        e.stopPropagation();
    });

    // منع إغلاق المودال عند التفاعل مع القائمة المنسدلة
    searchInput.addEventListener('mousedown', function(e) {
        e.stopPropagation();
    });

    optionsList.addEventListener('mousedown', function(e) {
        e.stopPropagation();
    });

    // منع حدث السكرول (wheel) من الانتقال للـ modal واغلاق القائمة
    optionsList.addEventListener('wheel', function(e) {
        e.stopPropagation();
    });

    // منع سكرول اللمس من الانتقال للـ modal (للموبايل)
    optionsList.addEventListener('touchmove', function(e) {
        e.stopPropagation();
    });

    // منع سكرول القائمة المنسدلة ككل من الانتقال للـ modal
    dropdown.addEventListener('wheel', function(e) {
        e.stopPropagation();
    });

    dropdown.addEventListener('touchmove', function(e) {
        e.stopPropagation();
    });

    // منع Bootstrap modal من سرقة الـ focus عند التفاعل مع القائمة المنسدلة
    // هذا يحل مشكلة enforceFocus في Bootstrap 5
    container.addEventListener('focusin', function(e) {
        e.stopPropagation();
    });

    // منع سرقة الـ focus من القائمة المنسدلة نفسها (عند position: fixed)
    dropdown.addEventListener('focusin', function(e) {
        e.stopPropagation();
    });

    searchInput.addEventListener('input', function() {
        renderOptions(this.value);
    });

    searchInput.addEventListener('click', function(e) {
        e.stopPropagation();
    });

    // إغلاق عند النقر خارج القائمة
    document.addEventListener('click', function(e) {
        if (!container.contains(e.target) && !dropdown.contains(e.target)) {
            closeDropdown();
        }
    });

    // إغلاق بـ Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && dropdown.classList.contains('show')) {
            closeDropdown();
        }
    });

    // داخل modal: إغلاق القائمة عند تمرير الـ modal (لأن position: fixed لا يتبع التمرير)
    // لكن لا نغلق اذا كان السكرول جاي من داخل القائمة المنسدلة نفسها
    if (isInsideModal && modalParent) {
        modalParent.addEventListener('scroll', function(e) {
            if (dropdown.classList.contains('show')) {
                // تحقق اذا كان مصدر السكرول من داخل القائمة المنسدلة
                if (dropdown.contains(e.target) || container.contains(e.target)) {
                    return; // لا تغلق - السكرول من داخل القائمة
                }
                closeDropdown();
            }
        }, true);

        // إغلاق عند إغلاق الـ modal نفسه
        modalParent.addEventListener('hidden.bs.modal', function() {
            closeDropdown();
        });
    }

    // إعادة حساب الموقع عند تغيير حجم النافذة
    if (isInsideModal) {
        window.addEventListener('resize', function() {
            if (dropdown.classList.contains('show')) {
                positionDropdownInModal();
            }
        });
    }

    // مراقبة تغييرات الـ select الأصلي (مثلاً عند إعادة تحميل الخيارات)
    const observer = new MutationObserver(function() {
        const currentVal = originalSelect.value;
        const currentOpt = originalSelect.querySelector('option[value="' + currentVal + '"]');
        if (currentVal && currentOpt) {
            const selectedSpan = display.querySelector('.ss-selected-text') || display.querySelector('.ss-placeholder');
            if (selectedSpan) {
                selectedSpan.className = 'ss-selected-text';
                selectedSpan.textContent = currentOpt.textContent;
            }
        } else {
            const placeholderEl = display.querySelector('.ss-placeholder') || display.querySelector('.ss-selected-text');
            if (placeholderEl) {
                placeholderEl.className = 'ss-placeholder';
                placeholderEl.textContent = placeholder;
            }
        }
        if (dropdown.classList.contains('show')) {
            renderOptions(searchInput.value);
        }
    });
    observer.observe(originalSelect, { childList: true, subtree: true, attributes: true });

    // ===== واجهة التحكم =====

    return {
        setValue: function(value) {
            originalSelect.value = value;
            const opt = originalSelect.querySelector('option[value="' + value + '"]');
            if (opt) {
                selectOption(value, opt.textContent);
            }
        },
        refresh: function() {
            const currentVal = originalSelect.value;
            const currentOpt = originalSelect.querySelector('option[value="' + currentVal + '"]');
            if (currentVal && currentOpt) {
                const selectedSpan = display.querySelector('.ss-selected-text') || display.querySelector('.ss-placeholder');
                if (selectedSpan) {
                    selectedSpan.className = 'ss-selected-text';
                    selectedSpan.textContent = currentOpt.textContent;
                }
            } else {
                const placeholderEl = display.querySelector('.ss-placeholder') || display.querySelector('.ss-selected-text');
                if (placeholderEl) {
                    placeholderEl.className = 'ss-placeholder';
                    placeholderEl.textContent = placeholder;
                }
            }
        },
        clear: function() {
            originalSelect.value = '';
            const placeholderEl = display.querySelector('.ss-placeholder') || display.querySelector('.ss-selected-text');
            if (placeholderEl) {
                placeholderEl.className = 'ss-placeholder';
                placeholderEl.textContent = placeholder;
            }
        },
        destroy: function() {
            observer.disconnect();
            container.remove();
            originalSelect.style.display = '';
        }
    };
}

window.makeSearchableSelect = makeSearchableSelect;
