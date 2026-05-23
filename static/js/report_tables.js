/* ============================================
   report_tables.js
   وظائف تفاعلية لكارتات التقارير:
   بحث، فلترة، Pagination، تصدير، تخصيص
   ============================================ */

(function() {
    'use strict';

    // ===== الإعدادات العامة =====
    const DEFAULT_PAGE_SIZE = 12;
    const CURRENCY = 'د.ع';

    // ===== حالة كل شبكة كارتات =====
    const gridStates = new Map();

    // ===== تهيئة شبكة كارتات تفاعلية =====
    window.initCardGrid = function(gridId, options = {}) {
        const grid = document.getElementById(gridId);
        if (!grid) return;

        const state = {
            grid: grid,
            gridId: gridId,
            pageSize: options.pageSize || DEFAULT_PAGE_SIZE,
            currentPage: 1,
            searchVal: '',
            filters: {},
            totalCardSelector: options.totalCardSelector || '.total-card',
            currencyFields: options.currencyFields || [],
            searchableFields: options.searchableFields || []
        };

        gridStates.set(gridId, state);

        // تهيئة Pagination
        updateCardPagination(gridId);

        // إخفاء الكارتات حسب الصفحة الأولى
        applyCardFilters(gridId);
    };

    // ===== البحث =====
    window.cardSearch = function(input, gridId) {
        const state = gridStates.get(gridId);
        if (!state) return;
        state.searchVal = input.value.trim().toLowerCase();
        state.currentPage = 1;
        applyCardFilters(gridId);
    };

    // ===== الفلترة =====
    window.cardFilter = function(selectOrInput, gridId, filterKey) {
        const state = gridStates.get(gridId);
        if (!state) return;
        state.filters[filterKey] = selectOrInput.value;
        state.currentPage = 1;
        applyCardFilters(gridId);
    };

    window.resetCardFilters = function(gridId) {
        const state = gridStates.get(gridId);
        if (!state) return;
        state.searchVal = '';
        state.filters = {};
        state.currentPage = 1;

        // إعادة حقول الفلتر
        const section = state.grid.closest('.report-section') || state.grid.closest('.report-card');
        if (section) {
            section.querySelectorAll('.report-filters select, .report-filters input[type="date"]').forEach(el => el.value = '');
            section.querySelectorAll('.report-search-box input').forEach(el => el.value = '');
        }

        applyCardFilters(gridId);
    };

    // ===== تطبيق كل الفلاتر =====
    function applyCardFilters(gridId) {
        const state = gridStates.get(gridId);
        if (!state) return;

        const allCards = Array.from(state.grid.querySelectorAll('.finance-card:not(.total-card), .payment-card'));
        const totalCard = state.grid.querySelector(state.totalCardSelector);

        // فلترة
        const filtered = allCards.filter(card => {
            // بحث نصي
            if (state.searchVal) {
                const cardText = card.textContent.toLowerCase();
                if (!cardText.includes(state.searchVal)) return false;
            }

            // فلاتر مخصصة
            for (const [key, val] of Object.entries(state.filters)) {
                if (!val) continue;

                if (key === 'date_from' || key === 'date_to') {
                    const cardDate = card.dataset.date || '';
                    if (!cardDate) continue;
                    if (key === 'date_from' && cardDate < val) return false;
                    if (key === 'date_to' && cardDate > val) return false;
                } else if (key === 'teacher') {
                    const cardVal = card.dataset.teacher || '';
                    if (cardVal !== val) return false;
                } else if (key === 'subject') {
                    const cardVal = card.dataset.subject || '';
                    if (cardVal !== val) return false;
                } else if (key === 'status') {
                    const cardVal = card.dataset.status || '';
                    if (cardVal !== val) return false;
                } else if (key === 'type') {
                    const cardVal = card.dataset.type || '';
                    if (cardVal !== val) return false;
                } else if (key === 'study_type') {
                    const cardVal = card.dataset.studyType || '';
                    if (cardVal !== val) return false;
                }
            }
            return true;
        });

        // إخفاء/إظهار الكارتات
        allCards.forEach(card => card.classList.add('card-hidden'));
        filtered.forEach(card => card.classList.remove('card-hidden'));

        // إظهار كارت الإجمالي دائماً
        if (totalCard) totalCard.classList.remove('card-hidden');

        // Pagination
        updateCardPagination(gridId, filtered);

        // تحديث الإجماليات الديناميكية
        updateDynamicSummary(gridId, filtered);

        // تحديث عداد الكارتات
        updateCardCount(gridId, filtered.length, allCards.length);
    }

    // ===== Pagination =====
    function updateCardPagination(gridId, filteredCards) {
        const state = gridStates.get(gridId);
        if (!state) return;

        const allCards = filteredCards || Array.from(state.grid.querySelectorAll('.finance-card:not(.total-card):not(.card-hidden), .payment-card:not(.card-hidden)'));
        const total = allCards.length;
        const totalPages = Math.max(1, Math.ceil(total / state.pageSize));

        if (state.currentPage > totalPages) state.currentPage = totalPages;

        // إخفاء/إظهار الكارتات حسب الصفحة
        const startIdx = (state.currentPage - 1) * state.pageSize;
        allCards.forEach((card, i) => {
            if (i >= startIdx && i < startIdx + state.pageSize) {
                card.classList.remove('card-hidden');
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });

        // بناء أزرار Pagination
        const paginationEl = document.getElementById(gridId + '_pagination');
        if (!paginationEl) return;

        let html = '';
        if (totalPages > 1) {
            html += `<button class="pagination-btn" onclick="cardPage('${gridId}', ${state.currentPage - 1})" ${state.currentPage <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>`;

            const maxBtns = 5;
            let startP = Math.max(1, state.currentPage - 2);
            let endP = Math.min(totalPages, startP + maxBtns - 1);
            if (endP - startP < maxBtns - 1) startP = Math.max(1, endP - maxBtns + 1);

            for (let p = startP; p <= endP; p++) {
                html += `<button class="pagination-btn ${p === state.currentPage ? 'active' : ''}" onclick="cardPage('${gridId}', ${p})">${p}</button>`;
            }

            html += `<button class="pagination-btn" onclick="cardPage('${gridId}', ${state.currentPage + 1})" ${state.currentPage >= totalPages ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>`;
            html += `<span class="pagination-info">${state.currentPage} / ${totalPages}</span>`;
        }

        // حجم الصفحة
        html += `<span class="pagination-size"><label>عرض:</label><select onchange="cardPageSize('${gridId}', this.value)"><option value="8" ${state.pageSize === 8 ? 'selected' : ''}>8</option><option value="12" ${state.pageSize === 12 ? 'selected' : ''}>12</option><option value="24" ${state.pageSize === 24 ? 'selected' : ''}>24</option><option value="50" ${state.pageSize === 50 ? 'selected' : ''}>50</option><option value="999" ${state.pageSize === 999 ? 'selected' : ''}>الكل</option></select></span>`;

        paginationEl.innerHTML = html;
    }

    window.cardPage = function(gridId, page) {
        const state = gridStates.get(gridId);
        if (!state) return;
        state.currentPage = page;
        applyCardFilters(gridId);
    };

    window.cardPageSize = function(gridId, size) {
        const state = gridStates.get(gridId);
        if (!state) return;
        state.pageSize = parseInt(size) || DEFAULT_PAGE_SIZE;
        state.currentPage = 1;
        applyCardFilters(gridId);
    };

    // ===== تحديث الإجماليات الديناميكية =====
    function updateDynamicSummary(gridId, filteredCards) {
        const summaryMode = document.querySelector('input[name="summary_mode"]:checked');
        const isFiltered = summaryMode ? summaryMode.value === 'filtered' : false;

        if (!isFiltered) return;

        // حساب من الكارتات المفلترة
        let totalFee = 0, totalPaid = 0, totalOriginal = 0, totalRemaining = 0;

        filteredCards.forEach(card => {
            card.querySelectorAll('.data-field-value[data-field]').forEach(el => {
                const val = parseFloat(el.dataset.value) || 0;
                const field = el.dataset.field;
                if (field === 'original_fee') totalOriginal += val;
                if (field === 'fee_after_discount') totalFee += val;
                if (field === 'paid') totalPaid += val;
                if (field === 'remaining') totalRemaining += val;
            });
        });

        const remaining = totalRemaining;
        const pct = totalFee > 0 ? Math.round((totalPaid / totalFee) * 100) : 0;

        // تحديث الكارتات
        updateSummaryCard('card_total_required', formatNum(totalFee));
        updateSummaryCard('card_total_paid', formatNum(totalPaid));
        updateSummaryCard('card_remaining', formatNum(Math.abs(remaining)));
        updateSummaryCard('card_pct', pct + '%');

        // تحديث Progress Bar
        const bar = document.querySelector('.progress-bar-fill');
        if (bar) {
            bar.style.width = Math.min(pct, 100) + '%';
            bar.classList.toggle('over-100', pct > 100);
        }

        const barLabel = document.querySelector('.progress-bar-label');
        if (barLabel) {
            const pctSpan = barLabel.querySelector('.pct-value');
            if (pctSpan) {
                pctSpan.textContent = pct > 100 ? `+${pct}%` : `${pct}%`;
                pctSpan.classList.toggle('pct-over', pct > 100);
            }
        }

        // تحديث شريط الإجماليات اللزج
        updateStickySummary(totalFee, totalPaid, remaining, pct);

        // تحديث كارت الإجمالي
        const totalCard = document.querySelector('.finance-card.total-card');
        if (totalCard) {
            totalCard.querySelectorAll('.data-field-value[data-field]').forEach(el => {
                const field = el.dataset.field;
                if (field === 'original_fee') el.textContent = formatNum(totalOriginal) + ' ' + CURRENCY;
                if (field === 'fee_after_discount') el.textContent = formatNum(totalFee) + ' ' + CURRENCY;
                if (field === 'paid') el.textContent = formatNum(totalPaid) + ' ' + CURRENCY;
                if (field === 'remaining') el.textContent = formatNum(Math.abs(remaining)) + ' ' + CURRENCY;
                if (field === 'percentage') el.textContent = pct + '%';
            });
        }
    }

    function updateSummaryCard(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = value;
    }

    function updateStickySummary(fee, paid, remaining, pct) {
        const bar = document.getElementById('stickySummary');
        if (!bar) return;
        const feeEl = bar.querySelector('.sv-fee');
        const paidEl = bar.querySelector('.sv-paid');
        const remEl = bar.querySelector('.sv-remaining');
        const pctEl = bar.querySelector('.sv-pct');
        if (feeEl) feeEl.textContent = formatNum(fee) + ' ' + CURRENCY;
        if (paidEl) paidEl.textContent = formatNum(paid) + ' ' + CURRENCY;
        if (remEl) {
            remEl.textContent = formatNum(Math.abs(remaining)) + ' ' + CURRENCY;
            remEl.className = 'si-value ' + (remaining > 0 ? 'danger' : 'success');
        }
        if (pctEl) pctEl.textContent = pct + '%';
    }

    function formatNum(n) {
        if (n === 0) return '0';
        const absN = Math.abs(n);
        const formatted = absN.toLocaleString('en').replace(/,/g, '.');
        return n < 0 ? '-' + formatted : formatted;
    }

    // ===== عداد الكارتات =====
    function updateCardCount(gridId, visible, total) {
        const el = document.getElementById(gridId + '_count');
        if (!el) return;
        if (visible === total) {
            el.innerHTML = `<strong>${visible}</strong> كارت`;
        } else {
            el.innerHTML = `<strong>${visible}</strong> من ${total} كارت`;
        }
    }

    // ===== تبديل إجمالي =====
    window.toggleSummaryMode = function(radio) {
        const gridId = radio.dataset.section;
        if (gridId) {
            // نبحث عن gridId المقابل
            gridStates.forEach((state, id) => {
                const section = state.grid.closest('.report-section');
                if (section && section.id === gridId) {
                    applyCardFilters(id);
                }
            });
        }
    };

    // ===== طي/فتح الأقسام =====
    window.toggleSection = function(header) {
        header.closest('.report-section').classList.toggle('section-collapsed');
    };

    // ===== تخصيص الحقول =====
    window.buildCustomizeControls = function(panelId) {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.classList.toggle('open');
        if (!panel.classList.contains('open')) return;

        const container = panel.querySelector('.customize-columns');
        if (!container) return;
        container.innerHTML = '';

        // جمع كل الحقول الفريدة من الكارتات
        const fieldsMap = new Map();

        document.querySelectorAll('.finance-card:not(.total-card) .data-field, .payment-card .data-field').forEach(field => {
            const fieldName = field.dataset.field;
            if (!fieldName || fieldsMap.has(fieldName)) return;
            const labelEl = field.querySelector('.data-field-label');
            if (!labelEl) return;
            const labelText = labelEl.textContent.trim();
            fieldsMap.set(fieldName, labelText);
        });

        fieldsMap.forEach((label, fieldName) => {
            const toggle = document.createElement('label');
            toggle.className = 'col-toggle active';
            toggle.innerHTML = `<input type="checkbox" checked data-field="${fieldName}" onchange="toggleField(this)"> ${label}`;
            container.appendChild(toggle);
        });

        // إضافة قسم تخصيص الأقسام
        const sectionsContainer = document.createElement('div');
        sectionsContainer.className = 'customize-sections';
        sectionsContainer.innerHTML = '<h6><i class="fas fa-layer-group"></i> إظهار / إخفاء الأقسام</h6>';

        document.querySelectorAll('.report-section').forEach((section, idx) => {
            const titleEl = section.querySelector('.section-title span') || section.querySelector('.section-title');
            if (!titleEl) return;
            const titleText = titleEl.textContent.trim();
            const toggle = document.createElement('label');
            toggle.className = 'col-toggle active';
            toggle.innerHTML = `<input type="checkbox" checked data-section-idx="${idx}" onchange="toggleReportSection(this, ${idx})"> ${titleText}`;
            sectionsContainer.appendChild(toggle);
        });

        container.appendChild(sectionsContainer);
    };

    window.toggleField = function(checkbox) {
        const fieldName = checkbox.dataset.field;
        const show = checkbox.checked;
        checkbox.closest('.col-toggle').classList.toggle('active', show);

        // إخفاء/إظهار الحقل في كل الكارتات
        document.querySelectorAll(`.data-field[data-field="${fieldName}"]`).forEach(field => {
            field.classList.toggle('field-hidden', !show);
        });
    };

    window.toggleReportSection = function(checkbox, idx) {
        const show = checkbox.checked;
        checkbox.closest('.col-toggle').classList.toggle('active', show);

        const sections = document.querySelectorAll('.report-section');
        if (sections[idx]) {
            sections[idx].style.display = show ? '' : 'none';
        }
    };

    // ===== تصدير Excel =====
    window.exportExcel = function(gridId, fileName) {
        const grid = document.getElementById(gridId);
        if (!grid) return;

        let csv = '\uFEFF'; // BOM for UTF-8

        // جمع أسماء الحقول المرئية
        const firstCard = grid.querySelector('.finance-card:not(.total-card)') || grid.querySelector('.payment-card');
        if (!firstCard) return;

        const visibleFields = [];
        const fieldLabels = [];
        firstCard.querySelectorAll('.data-field:not(.field-hidden)').forEach(field => {
            const fieldName = field.dataset.field;
            if (!fieldName) return;
            const labelEl = field.querySelector('.data-field-label');
            visibleFields.push(fieldName);
            fieldLabels.push(labelEl ? labelEl.textContent.trim() : fieldName);
        });

        // رأس CSV
        // إضافة أعمدة إضافية حسب نوع الكارت
        const isFinance = !!grid.querySelector('.finance-card');
        if (isFinance) {
            csv += '"المدرس","المادة","الحالة",' + fieldLabels.map(l => `"${l}"`).join(',') + '\n';
        } else {
            csv += '"المدرس","المادة",' + fieldLabels.map(l => `"${l}"`).join(',') + '\n';
        }

        // بيانات الكارتات
        grid.querySelectorAll('.finance-card:not(.total-card):not(.card-hidden), .payment-card:not(.card-hidden)').forEach(card => {
            const teacher = card.dataset.teacher || '';
            const subject = card.dataset.subject || '';
            const status = card.dataset.status || '';
            let row = '';

            if (isFinance) {
                row = `"${teacher}","${subject}","${status}",`;
            } else {
                row = `"${teacher}","${subject}",`;
            }

            const values = [];
            visibleFields.forEach(fieldName => {
                const fieldEl = card.querySelector(`.data-field[data-field="${fieldName}"]`);
                if (fieldEl) {
                    const valueEl = fieldEl.querySelector('.data-field-value');
                    values.push('"' + (valueEl ? valueEl.textContent.trim().replace(/"/g, '""') : '') + '"');
                } else {
                    values.push('""');
                }
            });

            csv += row + values.join(',') + '\n';
        });

        // كارت الإجمالي
        const totalCard = grid.querySelector('.total-card');
        if (totalCard) {
            csv += '"الإجمالي","","",';
            const totalValues = [];
            visibleFields.forEach(fieldName => {
                const fieldEl = totalCard.querySelector(`.data-field[data-field="${fieldName}"]`);
                if (fieldEl) {
                    const valueEl = fieldEl.querySelector('.data-field-value');
                    totalValues.push('"' + (valueEl ? valueEl.textContent.trim().replace(/"/g, '""') : '') + '"');
                } else {
                    totalValues.push('""');
                }
            });
            csv += totalValues.join(',') + '\n';
        }

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = (fileName || 'تقرير') + '.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    };

    // ===== تصدير PDF (طباعة محسنة) =====
    window.exportPDF = function() {
        smartPrint();
    };

    // ===== طباعة ذكية =====
    function smartPrint() {
        // إظهار كل الكارتات المخفية بالـ pagination فقط (وليس بالفلتر أو التخصيص)
        gridStates.forEach((state, gridId) => {
            const allCards = state.grid.querySelectorAll('.finance-card:not(.total-card), .payment-card');
            const filteredCards = Array.from(allCards).filter(card => !card.classList.contains('card-hidden'));

            // الكارتات المفلترة تبقى ظاهرة، لكن نعرض الكل (بدون pagination)
            filteredCards.forEach(card => {
                card.style.display = '';
            });

            // الكارتات المخفية بالفلتر تبقى مخفية
            allCards.forEach(card => {
                if (card.classList.contains('card-hidden')) {
                    card.setAttribute('data-was-filtered', 'true');
                }
            });
        });

        // فتح الأقسام المطوية
        document.querySelectorAll('.section-collapsed').forEach(section => {
            section.classList.add('temp-open');
            section.classList.remove('section-collapsed');
        });

        window.print();

        setTimeout(() => {
            // إعادة الكارتات المفلترة
            document.querySelectorAll('[data-was-filtered="true"]').forEach(el => {
                el.removeAttribute('data-was-filtered');
            });

            // إعادة الأقسام المطوية
            document.querySelectorAll('.temp-open').forEach(section => {
                section.classList.remove('temp-open');
                section.classList.add('section-collapsed');
            });

            // إعادة Pagination
            gridStates.forEach((state, id) => applyCardFilters(id));
        }, 500);
    }

    // ===== شريط الإجماليات اللزج =====
    window.initStickySummary = function() {
        const summaryEl = document.querySelector('.summary-cards');
        const stickyEl = document.getElementById('stickySummary');
        if (!summaryEl || !stickyEl) return;

        const observer = new IntersectionObserver(
            ([entry]) => {
                stickyEl.classList.toggle('visible', !entry.isIntersecting);
            },
            { threshold: 0, rootMargin: '-100px 0px 0px 0px' }
        );
        observer.observe(summaryEl);
    };

    // ===== دالة initReportTable محفوظة للتوافق مع التقارير الأخرى =====
    window.initReportTable = function(tableId, options = {}) {
        // للتوافق مع تقارير أخرى لا تزال تستخدم الجداول
        const table = document.getElementById(tableId);
        if (!table) return;
        // يمكن إضافة دعم الجداول لاحقاً إذا لزم
    };

    // ===== دوال التوافق مع القوالب القديمة =====
    window.reportSearch = function(input, tableId) {
        // تحويل إلى cardSearch إذا كان الهدف كارتات
        const gridEl = document.getElementById(tableId);
        if (gridEl && gridEl.classList.contains('data-cards-grid')) {
            cardSearch(input, tableId);
        }
    };

    window.reportFilter = function(selectOrInput, tableId, filterKey) {
        const gridEl = document.getElementById(tableId);
        if (gridEl && gridEl.classList.contains('data-cards-grid')) {
            cardFilter(selectOrInput, tableId, filterKey);
        }
    };

    window.resetFilters = function(tableId) {
        const gridEl = document.getElementById(tableId);
        if (gridEl && gridEl.classList.contains('data-cards-grid')) {
            resetCardFilters(tableId);
        }
    };

})();
