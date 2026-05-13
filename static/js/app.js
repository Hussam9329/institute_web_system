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

// ===== أحداث عامة =====

// منع إرسال النموذج إذا كان هناك حقول فارغة
document.addEventListener('submit', function(event) {
    const form = event.target;
    if (form.tagName === 'FORM' && !form.hasAttribute('novalidate')) {
        // التحقق الأساسي سيتم بواسطة HTML5 validation
    }
});


// ===== Smart Sort Toolbar =====
(function () {
    function getSortDirection(sortKey) {
        const parts = String(sortKey || '').split('-');
        return parts[1] || 'asc';
    }

    function decorateSmartSortChip(chip, sortKey) {
        if (!chip) return;
        const direction = getSortDirection(sortKey || chip.dataset.sortCycle?.split(',')[0]);
        chip.dataset.activeDirection = direction;

        let icon = chip.querySelector('.sort-direction-icon');
        if (!icon) {
            icon = document.createElement('i');
            icon.className = 'fas fa-arrow-down sort-direction-icon';
            chip.appendChild(icon);
        }
        icon.title = direction === 'asc' ? 'تصاعدي' : 'تنازلي';
    }

    function animateSortedLists(toolbar) {
        const containers = [
            document.querySelector('tbody'),
            document.getElementById('studentCards'),
            document.getElementById('teacherCards'),
            document.getElementById('subjectCards'),
            document.getElementById('paymentCards'),
            document.getElementById('accountingCards'),
            document.getElementById('withdrawalCards')
        ].filter(Boolean);

        toolbar?.classList.add('sorting');
        containers.forEach(el => {
            el.classList.remove('sort-animating');
            void el.offsetWidth;
            el.classList.add('sort-animating');
        });
        window.setTimeout(() => toolbar?.classList.remove('sorting'), 180);
    }

    window.applySmartSort = function (button) {
        const toolbar = button?.closest('.smart-sort-toolbar');
        if (!toolbar) return;

        const cycle = (button.dataset.sortCycle || '').split(',').map(v => v.trim()).filter(Boolean);
        if (!cycle.length) return;

        const currentSort = toolbar.dataset.currentSort || cycle[0];
        const isActive = button.classList.contains('active');
        let nextSort = cycle[0];

        if (isActive) {
            const currentIndex = cycle.indexOf(currentSort);
            nextSort = cycle[(currentIndex + 1) % cycle.length] || cycle[0];
        }

        toolbar.dataset.currentSort = nextSort;
        toolbar.querySelectorAll('.smart-sort-chip').forEach(chip => {
            chip.classList.toggle('active', chip === button);
            decorateSmartSortChip(chip, chip === button ? nextSort : chip.dataset.sortCycle?.split(',')[0]);
        });

        if (typeof window.applySorting === 'function') {
            window.applySorting(nextSort);
            animateSortedLists(toolbar);
        }
    };

    window.getActiveSmartSortText = function () {
        const active = document.querySelector('.smart-sort-toolbar .smart-sort-chip.active');
        if (!active) return '';
        const direction = getSortDirection(active.closest('.smart-sort-toolbar')?.dataset.currentSort || active.dataset.sortCycle);
        const label = active.innerText.replace(/[\n\r]+/g, ' ').trim();
        return label + (direction === 'asc' ? ' تصاعدي' : ' تنازلي');
    };

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.smart-sort-toolbar').forEach(toolbar => {
            const active = toolbar.querySelector('.smart-sort-chip.active') || toolbar.querySelector('.smart-sort-chip');
            if (!active) return;
            const initialSort = toolbar.dataset.currentSort || active.dataset.sortCycle?.split(',')[0];
            toolbar.dataset.currentSort = initialSort;
            toolbar.querySelectorAll('.smart-sort-chip').forEach(chip => {
                decorateSmartSortChip(chip, chip === active ? initialSort : chip.dataset.sortCycle?.split(',')[0]);
            });
            if (typeof window.applySorting === 'function' && initialSort) {
                window.applySorting(initialSort);
            }
        });
    });
})();