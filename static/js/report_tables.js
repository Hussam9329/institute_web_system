/* ============================================
   report_tables.js
   وظائف تفاعلية لجداول التقارير:
   بحث، فرز، فلترة، Pagination، تصدير
   ============================================ */

(function() {
    'use strict';

    // ===== الإعدادات العامة =====
    const DEFAULT_PAGE_SIZE = 15;
    const CURRENCY = 'د.ع';

    // ===== حالة كل جدول =====
    const tableStates = new Map();

    // ===== تهيئة جدول تفاعلي =====
    window.initReportTable = function(tableId, options = {}) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const state = {
            table: table,
            pageSize: options.pageSize || DEFAULT_PAGE_SIZE,
            currentPage: 1,
            sortCol: -1,
            sortAsc: true,
            searchVal: '',
            filters: {},
            totalRowSelector: options.totalRowSelector || '.total-row',
            dataColTypes: options.dataColTypes || [],   // 'number', 'date', 'text'
            currencyCols: options.currencyCols || [],
            dateCols: options.dateCols || [],
        };

        tableStates.set(tableId, state);

        // تهيئة colspan الأصلي
        initColspans(table);

        // تهيئة Pagination
        updatePagination(tableId);

        // تهيئة الفلاتر
        bindFilters(tableId, options);

        // تهيئة التلميحات
        initCellTooltips(table);

        // إخفاء تحميل
        hideLoading(tableId);
    };

    // ===== colspan =====
    function initColspans(table) {
        const totalCols = table.querySelectorAll('thead th').length;
        const rows = table.querySelectorAll('tbody tr, tfoot tr');
        rows.forEach(row => {
            const tds = row.querySelectorAll('td, th');
            let colIdx = 0;
            tds.forEach(td => {
                const cs = parseInt(td.getAttribute('colspan')) || 1;
                td.dataset.origColspan = cs;
                td.dataset.colStart = colIdx;
                colIdx += cs;
            });
        });
    }

    function updateColspans(table) {
        const ths = table.querySelectorAll('thead th');
        const hiddenCols = [];
        ths.forEach((th, i) => { hiddenCols[i] = th.classList.contains('col-hidden'); });

        const rows = table.querySelectorAll('tbody tr, tfoot tr');
        rows.forEach(row => {
            const tds = row.querySelectorAll('td, th');
            tds.forEach(td => {
                const origCs = parseInt(td.dataset.origColspan) || 1;
                if (origCs <= 1) return;
                const colStart = parseInt(td.dataset.colStart) || 0;
                let hiddenCount = 0;
                for (let i = colStart; i < colStart + origCs && i < ths.length; i++) {
                    if (hiddenCols[i]) hiddenCount++;
                }
                const newCs = origCs - hiddenCount;
                if (newCs <= 0) {
                    td.style.display = 'none';
                } else {
                    td.style.display = '';
                    td.setAttribute('colspan', newCs);
                }
            });
        });
    }

    // ===== إظهار/إخفاء الأعمدة =====
    window.toggleColumn = function(checkbox) {
        const tIdx = parseInt(checkbox.dataset.table);
        const colIdx = parseInt(checkbox.dataset.col);
        const tables = document.querySelectorAll('.report-table');
        const table = tables[tIdx];
        if (!table) return;

        const show = checkbox.checked;
        checkbox.closest('.col-toggle').classList.toggle('active', show);

        const ths = table.querySelectorAll('thead th');
        if (ths[colIdx]) ths[colIdx].classList.toggle('col-hidden', !show);

        table.querySelectorAll('tbody tr').forEach(row => {
            const tds = row.querySelectorAll('td');
            if (tds[colIdx]) tds[colIdx].classList.toggle('col-hidden', !show);
        });

        table.querySelectorAll('tfoot th').forEach(th => {
            // handled by colspan
        });

        updateColspans(table);

        // إعادة حساب الإجماليات والـ pagination
        const tableId = table.id;
        if (tableId && tableStates.has(tableId)) {
            tableStates.get(tableId).currentPage = 1;
            applyAllFilters(tableId);
        }
    };

    window.buildCustomizeControls = function(panelId) {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.classList.toggle('open');
        if (!panel.classList.contains('open')) return;

        const container = panel.querySelector('.customize-columns');
        if (!container) return;
        container.innerHTML = '';

        document.querySelectorAll('.report-table').forEach((table, tIdx) => {
            table.querySelectorAll('thead th').forEach((th, colIdx) => {
                const label = th.textContent.trim();
                if (!label) return;
                const toggle = document.createElement('label');
                toggle.className = 'col-toggle active';
                toggle.innerHTML = `<input type="checkbox" checked data-table="${tIdx}" data-col="${colIdx}" onchange="toggleColumn(this)"> ${label}`;
                container.appendChild(toggle);
            });
        });
    };

    // ===== البحث =====
    window.reportSearch = function(input, tableId) {
        const state = tableStates.get(tableId);
        if (!state) return;
        state.searchVal = input.value.trim().toLowerCase();
        state.currentPage = 1;
        applyAllFilters(tableId);
    };

    // ===== الفرز =====
    window.reportSort = function(th, tableId, colIdx) {
        const state = tableStates.get(tableId);
        if (!state) return;

        // تبديل الاتجاه
        if (state.sortCol === colIdx) {
            state.sortAsc = !state.sortAsc;
        } else {
            state.sortCol = colIdx;
            state.sortAsc = true;
        }

        // تحديث الأيقونات
        state.table.querySelectorAll('thead th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(state.sortAsc ? 'sort-asc' : 'sort-desc');

        applyAllFilters(tableId);
    };

    // ===== الفلترة =====
    function bindFilters(tableId, options) {
        // يتم ربطها من القالب مباشرة عبر onchange
    }

    window.reportFilter = function(selectOrInput, tableId, filterKey) {
        const state = tableStates.get(tableId);
        if (!state) return;
        state.filters[filterKey] = selectOrInput.value;
        state.currentPage = 1;
        applyAllFilters(tableId);
    };

    window.resetFilters = function(tableId) {
        const state = tableStates.get(tableId);
        if (!state) return;
        state.searchVal = '';
        state.filters = {};
        state.sortCol = -1;
        state.sortAsc = true;
        state.currentPage = 1;

        // إعادة حقول الفلتر
        const wrapper = state.table.closest('.report-section') || state.table.closest('.report-card');
        if (wrapper) {
            wrapper.querySelectorAll('.report-filters select, .report-filters input[type="date"]').forEach(el => el.value = '');
            wrapper.querySelectorAll('.report-search-box input').forEach(el => el.value = '');
        }

        state.table.querySelectorAll('thead th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));

        applyAllFilters(tableId);
    };

    // ===== تطبيق كل الفلاتر =====
    function applyAllFilters(tableId) {
        const state = tableStates.get(tableId);
        if (!state) return;

        const tbody = state.table.querySelector('tbody');
        const totalRow = tbody.querySelector(state.totalRowSelector);
        const rows = Array.from(tbody.querySelectorAll('tr:not(.total-row)'));

        // فلترة
        const filtered = rows.filter(row => {
            // بحث نصي
            if (state.searchVal) {
                const rowText = row.textContent.toLowerCase();
                if (!rowText.includes(state.searchVal)) return false;
            }

            // فلاتر مخصصة
            for (const [key, val] of Object.entries(state.filters)) {
                if (!val) continue;
                const cellIdx = getFilterColIndex(state.table, key);
                if (cellIdx < 0) continue;
                const td = row.querySelectorAll('td')[cellIdx];
                if (!td) continue;
                const cellText = td.textContent.trim();
                if (key === 'date_from' || key === 'date_to') {
                    const cellDate = extractDate(td.textContent.trim());
                    if (key === 'date_from' && cellDate && cellDate < val) return false;
                    if (key === 'date_to' && cellDate && cellDate > val) return false;
                } else {
                    if (cellText !== val) return false;
                }
            }
            return true;
        });

        // فرز
        if (state.sortCol >= 0) {
            filtered.sort((a, b) => {
                const aTd = a.querySelectorAll('td')[state.sortCol];
                const bTd = b.querySelectorAll('td')[state.sortCol];
                const aVal = aTd ? (parseFloat(aTd.dataset.value) || aTd.textContent.trim()) : '';
                const bVal = bTd ? (parseFloat(bTd.dataset.value) || bTd.textContent.trim()) : '';

                if (!isNaN(aVal) && !isNaN(bVal)) {
                    return state.sortAsc ? aVal - bVal : bVal - aVal;
                }
                const aStr = String(aVal), bStr = String(bVal);
                return state.sortAsc ? aStr.localeCompare(bStr, 'ar') : bStr.localeCompare(aStr, 'ar');
            });
        }

        // إخفاء/إظهار
        rows.forEach(row => row.classList.add('row-hidden'));
        filtered.forEach(row => row.classList.remove('row-hidden'));

        // Pagination
        updatePagination(tableId, filtered.length);

        // تحديث الإجماليات الديناميكية
        updateDynamicSummary(tableId, filtered);

        // تحديث عداد الصفوف
        updateRowCount(tableId, filtered.length, rows.length);
    }

    function getFilterColIndex(table, filterKey) {
        const mapping = {
            'teacher': 1, 'subject': 2, 'status': 4, 'type': 4,
            'study_type': 3, 'discount_type': 5
        };
        return mapping[filterKey] !== undefined ? mapping[filterKey] : -1;
    }

    function extractDate(text) {
        const m = text.match(/(\d{4})[-\/](\d{2})[-\/](\d{2})/);
        if (m) return `${m[1]}-${m[2]}-${m[3]}`;
        const m2 = text.match(/(\d{2})[-\/](\d{2})[-\/](\d{4})/);
        if (m2) return `${m2[3]}-${m2[2]}-${m2[1]}`;
        return null;
    }

    // ===== Pagination =====
    function updatePagination(tableId, totalFiltered) {
        const state = tableStates.get(tableId);
        if (!state) return;

        const tbody = state.table.querySelector('tbody');
        const visibleRows = Array.from(tbody.querySelectorAll('tr:not(.total-row):not(.row-hidden)'));
        const total = totalFiltered !== undefined ? totalFiltered : visibleRows.length;
        const totalPages = Math.max(1, Math.ceil(total / state.pageSize));

        if (state.currentPage > totalPages) state.currentPage = totalPages;

        // إخفاء/إظهار الصفوف حسب الصفحة
        const startIdx = (state.currentPage - 1) * state.pageSize;
        visibleRows.forEach((row, i) => {
            row.style.display = (i >= startIdx && i < startIdx + state.pageSize) ? '' : 'none';
        });

        // بناء أزرار Pagination
        const paginationEl = document.getElementById(tableId + '_pagination');
        if (!paginationEl) return;

        let html = '';
        if (totalPages > 1) {
            html += `<button class="pagination-btn" onclick="reportPage('${tableId}', ${state.currentPage - 1})" ${state.currentPage <= 1 ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>`;

            const maxBtns = 5;
            let startP = Math.max(1, state.currentPage - 2);
            let endP = Math.min(totalPages, startP + maxBtns - 1);
            if (endP - startP < maxBtns - 1) startP = Math.max(1, endP - maxBtns + 1);

            for (let p = startP; p <= endP; p++) {
                html += `<button class="pagination-btn ${p === state.currentPage ? 'active' : ''}" onclick="reportPage('${tableId}', ${p})">${p}</button>`;
            }

            html += `<button class="pagination-btn" onclick="reportPage('${tableId}', ${state.currentPage + 1})" ${state.currentPage >= totalPages ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>`;
            html += `<span class="pagination-info">${state.currentPage} / ${totalPages}</span>`;
        }

        // حجم الصفحة
        html += `<span class="pagination-size"><label>عرض:</label><select onchange="reportPageSize('${tableId}', this.value)"><option value="10" ${state.pageSize === 10 ? 'selected' : ''}>10</option><option value="15" ${state.pageSize === 15 ? 'selected' : ''}>15</option><option value="25" ${state.pageSize === 25 ? 'selected' : ''}>25</option><option value="50" ${state.pageSize === 50 ? 'selected' : ''}>50</option><option value="999" ${state.pageSize === 999 ? 'selected' : ''}>الكل</option></select></span>`;

        paginationEl.innerHTML = html;
    }

    window.reportPage = function(tableId, page) {
        const state = tableStates.get(tableId);
        if (!state) return;
        state.currentPage = page;
        applyAllFilters(tableId);
    };

    window.reportPageSize = function(tableId, size) {
        const state = tableStates.get(tableId);
        if (!state) return;
        state.pageSize = parseInt(size) || DEFAULT_PAGE_SIZE;
        state.currentPage = 1;
        applyAllFilters(tableId);
    };

    // ===== تحديث الإجماليات الديناميكية =====
    function updateDynamicSummary(tableId, filteredRows) {
        const summaryMode = document.querySelector('input[name="summary_mode"]:checked');
        const isFiltered = summaryMode ? summaryMode.value === 'filtered' : false;

        if (!isFiltered) return; // إذا "كل البيانات" لا نحدث

        // حساب من الصفوف المفلترة
        let totalFee = 0, totalPaid = 0, totalOriginal = 0;
        filteredRows.forEach(row => {
            const tds = row.querySelectorAll('td');
            // data-value على خلايا المبالغ
            tds.forEach(td => {
                const dv = td.dataset.value;
                if (dv !== undefined && td.dataset.field) {
                    const val = parseFloat(dv) || 0;
                    if (td.dataset.field === 'original_fee') totalOriginal += val;
                    if (td.dataset.field === 'fee_after_discount') totalFee += val;
                    if (td.dataset.field === 'paid') totalPaid += val;
                }
            });
        });

        const remaining = totalPaid - totalFee;
        const pct = totalFee > 0 ? Math.round((totalPaid / totalFee) * 100) : 0;
        const overpayment = Math.max(0, remaining);

        // تحديث الكارتات
        updateCard('card_total_required', formatNum(totalFee));
        updateCard('card_total_paid', formatNum(totalPaid));
        updateCard('card_remaining', formatNum(Math.abs(remaining)), remaining > 0 ? 'danger' : 'success');
        updateCard('card_overpayment', formatNum(overpayment));
        updateCard('card_pct', pct + '%');

        // تحديث Progress Bar
        const bar = document.querySelector('.progress-bar-fill');
        const barLabel = document.querySelector('.progress-bar-label');
        if (bar) {
            const width = Math.min(pct, 100);
            bar.style.width = width + '%';
            bar.classList.toggle('over-100', pct > 100);
        }
        if (barLabel) {
            const pctSpan = barLabel.querySelector('.pct-value');
            if (pctSpan) {
                pctSpan.textContent = pct > 100 ? `+${pct}%` : `${pct}%`;
                pctSpan.classList.toggle('pct-over', pct > 100);
            }
        }

        // تحديث شريط الإجماليات اللزج
        updateStickySummary(totalFee, totalPaid, remaining, pct);
    }

    function updateCard(id, value, colorClass) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = value;
        if (colorClass) {
            el.className = 'card-value';
            el.classList.add(colorClass === 'danger' ? 'text-danger' : 'text-success');
        }
    }

    function updateStickySummary(fee, paid, remaining, pct) {
        const bar = document.getElementById('stickySummary');
        if (!bar) return;
        bar.querySelector('.sv-fee').textContent = formatNum(fee) + ' ' + CURRENCY;
        bar.querySelector('.sv-paid').textContent = formatNum(paid) + ' ' + CURRENCY;
        bar.querySelector('.sv-remaining').textContent = formatNum(Math.abs(remaining)) + ' ' + CURRENCY;
        const remEl = bar.querySelector('.sv-remaining');
        remEl.className = 'si-value ' + (remaining > 0 ? 'danger' : 'success');
        bar.querySelector('.sv-pct').textContent = pct + '%';
    }

    function formatNum(n) {
        if (n === 0) return '0';
        const absN = Math.abs(n);
        const formatted = absN.toLocaleString('en').replace(/,/g, '.');
        return n < 0 ? '-' + formatted : formatted;
    }

    // ===== عداد الصفوف =====
    function updateRowCount(tableId, visible, total) {
        const el = document.getElementById(tableId + '_count');
        if (!el) return;
        if (visible === total) {
            el.innerHTML = `<strong>${visible}</strong> صف`;
        } else {
            el.innerHTML = `<strong>${visible}</strong> من ${total} صف`;
        }
    }

    // ===== تبديل إجمالي (كل البيانات / المفلترة) =====
    window.toggleSummaryMode = function(radio) {
        const tableId = radio.dataset.table;
        applyAllFilters(tableId);
    };

    // ===== طي/فتح الأقسام =====
    window.toggleSection = function(header) {
        header.closest('.report-section').classList.toggle('section-collapsed');
    };

    // ===== تصدير Excel =====
    window.exportExcel = function(tableId, fileName) {
        const table = document.getElementById(tableId);
        if (!table) return;

        let csv = '\uFEFF'; // BOM for UTF-8
        const rows = table.querySelectorAll('tr');

        rows.forEach(row => {
            if (row.classList.contains('row-hidden') && !row.classList.contains('total-row')) return;
            const cols = row.querySelectorAll('th, td');
            const rowData = [];
            cols.forEach(col => {
                if (col.classList.contains('col-hidden')) return;
                let text = col.textContent.trim().replace(/"/g, '""');
                rowData.push('"' + text + '"');
            });
            csv += rowData.join(',') + '\n';
        });

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

    // ===== تلميح الخلايا =====
    let activeTooltip = null;

    function initCellTooltips(table) {
        if (!document.getElementById('cellTooltip')) {
            const tip = document.createElement('div');
            tip.id = 'cellTooltip';
            tip.className = 'cell-tooltip';
            document.body.appendChild(tip);
        }
        activeTooltip = document.getElementById('cellTooltip');

        table.querySelectorAll('tbody td').forEach(td => {
            td.addEventListener('mouseenter', handleCellHover);
            td.addEventListener('mouseleave', handleCellLeave);
        });

        requestAnimationFrame(() => detectTruncatedCells(table));
    }

    function detectTruncatedCells(table) {
        table.querySelectorAll('tbody td').forEach(td => {
            const isTruncated = td.scrollWidth > td.clientWidth + 2;
            td.classList.toggle('cell-truncated', isTruncated);
        });
    }

    function handleCellHover(e) {
        const td = e.currentTarget;
        if (!td.classList.contains('cell-truncated') || !activeTooltip) return;
        const text = td.textContent.trim();
        if (!text) return;

        activeTooltip.textContent = text;
        const rect = td.getBoundingClientRect();
        let left = rect.left + rect.width / 2 - 50;
        let top = rect.bottom + 8;

        if (left < 8) left = 8;
        if (left + 300 > window.innerWidth) left = window.innerWidth - 316;
        if (top + 60 > window.innerHeight) top = rect.top - 50;

        activeTooltip.style.left = left + 'px';
        activeTooltip.style.top = top + 'px';
        activeTooltip.classList.add('visible');
    }

    function handleCellLeave() {
        if (activeTooltip) activeTooltip.classList.remove('visible');
    }

    // ===== Loading =====
    function showLoading(tableId) {
        const wrapper = document.getElementById(tableId + '_wrapper');
        if (wrapper) wrapper.querySelector('.report-table-wrapper')?.classList.add('loading');
    }

    function hideLoading(tableId) {
        const wrapper = document.getElementById(tableId + '_wrapper');
        if (wrapper) wrapper.querySelector('.report-table-wrapper')?.classList.remove('loading');
    }

    // ===== طباعة =====
    function smartPrint() {
        document.querySelectorAll('.report-table .col-hidden').forEach(el => {
            el.setAttribute('data-was-hidden', 'true');
            el.classList.remove('col-hidden');
        });
        document.querySelectorAll('.report-table tbody tr.row-hidden').forEach(el => {
            el.setAttribute('data-was-hidden', 'true');
            el.classList.remove('row-hidden');
        });
        document.querySelectorAll('.report-table tbody tr[style*="display: none"]').forEach(el => {
            el.setAttribute('data-was-page-hidden', 'true');
            el.style.display = '';
        });

        document.querySelectorAll('[data-orig-colspan]').forEach(td => {
            const origCs = parseInt(td.dataset.origColspan) || 1;
            td.setAttribute('colspan', origCs);
            td.style.display = '';
        });

        const tables = document.querySelectorAll('.report-table');
        let isWide = false;
        tables.forEach(table => {
            if (table.querySelectorAll('thead th').length > 6) isWide = true;
        });
        if (isWide) document.body.classList.add('wide-report');

        tables.forEach(table => {
            const thead = table.querySelector('thead');
            if (thead && !table.querySelector('tfoot')) {
                const newTfoot = document.createElement('tfoot');
                newTfoot.innerHTML = thead.innerHTML;
                newTfoot.setAttribute('role', 'repeat-header');
                table.appendChild(newTfoot);
            }
        });

        window.print();

        setTimeout(() => {
            document.querySelectorAll('tfoot[role="repeat-header"]').forEach(el => el.remove());
            document.body.classList.remove('wide-report');

            document.querySelectorAll('[data-was-hidden="true"]').forEach(el => {
                el.removeAttribute('data-was-hidden');
                el.classList.add('col-hidden');
            });
            document.querySelectorAll('.report-table tbody tr[data-was-hidden="true"]').forEach(el => {
                el.removeAttribute('data-was-hidden');
                el.classList.add('row-hidden');
            });
            document.querySelectorAll('[data-was-page-hidden="true"]').forEach(el => {
                el.removeAttribute('data-was-page-hidden');
                el.style.display = 'none';
            });

            document.querySelectorAll('.report-table').forEach(table => {
                updateColspans(table);
            });

            // إعادة Pagination
            tableStates.forEach((state, id) => applyAllFilters(id));
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

})();
