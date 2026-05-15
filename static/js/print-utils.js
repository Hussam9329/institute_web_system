/**
 * print-utils.js - Professional Print Utility for Institute Web System
 * Generates A4-optimized reports matching base_report.html design
 * Captures current filtered/sorted data from list pages
 */

const PrintUtils = {
    getActiveSortLabel() {
        if (typeof window.getActiveSmartSortText === 'function') {
            const smartSortText = window.getActiveSmartSortText();
            if (smartSortText) return smartSortText;
        }
        const select = document.getElementById('sortBySelect');
        if (select && select.value) {
            return select.options[select.selectedIndex]?.text || '';
        }
        return '';
    },

    // CSS styles matching base_report.html for consistent professional output
    getReportCSS() {
        return `
        <style>
            :root {
                --primary: #6366f1; --primary-light: #818cf8; --primary-dark: #4f46e5;
                --primary-darker: #3730a3; --secondary: #8b5cf6; --secondary-light: #a78bfa;
                --secondary-dark: #7c3aed; --sidebar-dark: #1e1b4b; --success: #10b981;
                --success-light: #34d399; --danger: #ef4444; --danger-light: #f87171;
                --warning: #f59e0b; --warning-light: #fbbf24; --info: #06b6d4;
                --dark: #0f172a; --muted: #64748b; --muted-light: #94a3b8;
                --light: #f1f5f9; --white: #ffffff; --border: #e2e8f0;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'NotoArabic', 'Segoe UI', system-ui, -apple-system, sans-serif;
                background: var(--light); color: var(--dark); line-height: 1.7; direction: rtl;
            }
            .report-toolbar {
                background: linear-gradient(135deg, var(--sidebar-dark) 0%, var(--primary-darker) 100%);
                padding: 12px 24px; display: flex; align-items: center; justify-content: space-between;
                position: sticky; top: 0; z-index: 100;
                box-shadow: 0 4px 20px rgba(30, 27, 75, 0.3);
            }
            .toolbar-brand { display: flex; align-items: center; gap: 10px; color: var(--white); }
            .toolbar-brand i { font-size: 20px; color: var(--secondary-light); }
            .toolbar-brand span { font-weight: 700; font-size: 16px; }
            .toolbar-actions { display: flex; gap: 6px; align-items: center; }
            .toolbar-btn-group {
                display: flex; gap: 4px; align-items: center;
                background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 4px;
            }
            .toolbar-btn {
                position: relative; border: none; padding: 7px 14px; border-radius: 9px;
                font-family: 'NotoArabic', sans-serif; font-weight: 600; font-size: 12px;
                cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                display: flex; align-items: center; gap: 5px; white-space: nowrap;
                color: rgba(255, 255, 255, 0.9); background: transparent;
            }
            .toolbar-btn i { font-size: 13px; transition: transform 0.3s ease; }
            .toolbar-btn:hover { background: rgba(255, 255, 255, 0.15); transform: translateY(-1px); }
            .toolbar-btn:hover i { transform: scale(1.15); }
            .toolbar-btn:active { transform: translateY(0) scale(0.97); }
            .toolbar-divider { width: 1px; height: 28px; background: rgba(255, 255, 255, 0.15); margin: 0 4px; }
            .btn-print {
                background: linear-gradient(135deg, var(--secondary-light), var(--secondary)) !important;
                color: var(--white) !important; padding: 8px 18px !important; border-radius: 9px !important;
                font-family: 'NotoArabic', sans-serif !important; font-weight: 700 !important; font-size: 13px !important;
                cursor: pointer !important; border: none !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                display: flex !important; align-items: center !important; gap: 7px !important;
                box-shadow: 0 2px 10px rgba(139, 92, 246, 0.3) !important;
            }
            .btn-print:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 24px rgba(139, 92, 246, 0.5) !important;
                background: linear-gradient(135deg, var(--secondary), var(--secondary-dark)) !important;
            }
            .btn-print:active { transform: translateY(0) scale(0.97) !important; }
            .btn-print i { font-size: 14px !important; animation: printPulse 2s ease infinite; }
            @keyframes printPulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
            .btn-close-report {
                background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1); padding: 7px 14px; border-radius: 9px;
                font-family: 'NotoArabic', sans-serif; font-weight: 500; font-size: 12px;
                cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                text-decoration: none; display: flex; align-items: center; gap: 5px;
            }
            .btn-close-report:hover {
                background: rgba(255, 255, 255, 0.18); color: var(--white);
                border-color: rgba(255, 255, 255, 0.25); transform: translateY(-1px);
            }
            .report-container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
            .report-card {
                background: var(--white); border-radius: 20px;
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06); overflow: hidden;
            }
            .report-header {
                background: linear-gradient(135deg, var(--sidebar-dark) 0%, var(--primary-darker) 50%, var(--primary-dark) 100%);
                padding: 28px 32px; color: var(--white); position: relative; overflow: hidden;
            }
            .report-header::before {
                content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
                background: linear-gradient(90deg, var(--secondary), var(--primary-light), var(--secondary-light));
            }
            .report-header::after {
                content: ''; position: absolute; top: -50%; left: -20%; width: 300px; height: 300px;
                background: radial-gradient(circle, rgba(139, 92, 246, 0.15), transparent 70%);
                border-radius: 50%;
            }
            .report-title { font-size: 22px; font-weight: 800; margin-bottom: 4px; position: relative; }
            .report-subtitle { font-size: 13px; font-weight: 400; opacity: 0.8; }
            .report-date { font-size: 11px; opacity: 0.6; margin-top: 8px; }
            .kpi-grid {
                display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 12px; padding: 20px 24px;
            }
            .kpi-card {
                border-radius: 14px; padding: 14px 16px; text-align: center;
                position: relative; overflow: hidden;
            }
            .kpi-card::before {
                content: ''; position: absolute; top: 0; right: 0; left: 0; height: 3px;
            }
            .kpi-value { font-size: 18px; font-weight: 800; line-height: 1.4; }
            .kpi-label { font-size: 11px; font-weight: 500; opacity: 0.7; margin-top: 2px; }
            .kpi-accent { background: #eff6ff; color: var(--primary); }
            .kpi-accent::before { background: var(--primary); }
            .kpi-success { background: #ecfdf5; color: var(--success); }
            .kpi-success::before { background: var(--success); }
            .kpi-danger { background: #fef2f2; color: var(--danger); }
            .kpi-danger::before { background: var(--danger); }
            .kpi-warning { background: #fffbeb; color: var(--warning); }
            .kpi-warning::before { background: var(--warning); }
            .kpi-info { background: #f0f9ff; color: var(--info); }
            .kpi-info::before { background: var(--info); }
            .kpi-purple { background: #f5f3ff; color: var(--secondary); }
            .kpi-purple::before { background: var(--secondary); }
            .report-section { padding: 0 24px; margin-top: 20px; }
            .section-title {
                background: linear-gradient(135deg, var(--secondary), var(--primary));
                color: var(--white); padding: 8px 16px; border-radius: 10px;
                font-size: 13px; font-weight: 700; margin-bottom: 12px;
                display: flex; align-items: center; gap: 8px;
            }
            .section-title i { font-size: 12px; opacity: 0.8; }
            .report-table-wrapper { border-radius: 14px; overflow: hidden; border: 1px solid var(--border); }
            .report-table { width: 100%; border-collapse: collapse; font-size: 13px; }
            .report-table thead th {
                background: linear-gradient(135deg, var(--primary), var(--primary-dark));
                color: var(--white); padding: 10px 14px; font-weight: 700;
                font-size: 12px; text-align: right; white-space: nowrap;
            }
            .report-table thead th.text-center { text-align: center; }
            .report-table tbody td { padding: 9px 14px; border-bottom: 1px solid var(--light); vertical-align: middle; }
            .report-table tbody tr:nth-child(even) { background: #fafbfc; }
            .report-table .total-row { background: #eff6ff !important; font-weight: 700; }
            .report-table .total-row td { border-top: 2px solid var(--primary-light); }
            .footer-text {
                text-align: center; padding: 16px 24px; font-size: 11px;
                color: var(--muted); border-top: 1px solid var(--light);
            }
            .badge-paid { background: #ecfdf5; color: #059669; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
            .badge-unpaid { background: #fef2f2; color: #dc2626; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
            .badge-continue { background: #eff6ff; color: var(--primary); padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
            .badge-withdrawn { background: #fffbeb; color: #d97706; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }

            /* ===== PRINT MODE ===== */
            @media print {
                *, *::before, *::after {
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                    color-adjust: exact !important;
                }
                body { background: white !important; font-size: 11pt; line-height: 1.5; }
                @page { size: A4 portrait; margin: 8mm 10mm 12mm 10mm; }
                .report-toolbar, .no-print, .btn-close-report { display: none !important; }
                .report-container { max-width: 100% !important; margin: 0 !important; padding: 0 !important; }
                .report-card { box-shadow: none !important; border-radius: 0 !important; overflow: visible !important; }
                .report-header { border-radius: 0 !important; padding: 16px 20px !important; page-break-after: avoid !important; }
                .report-header::after { display: none !important; }
                .report-title { font-size: 18pt !important; }
                .report-subtitle { font-size: 11pt !important; }
                .report-date { font-size: 9pt !important; margin-top: 4px !important; }
                .kpi-grid { display: grid !important; grid-template-columns: repeat(4, 1fr) !important; gap: 6px !important; padding: 12px 16px !important; page-break-inside: avoid !important; }
                .kpi-card { border-radius: 6px !important; padding: 10px 8px !important; border: 1px solid #e2e8f0 !important; page-break-inside: avoid !important; }
                .kpi-card::before { height: 2px !important; }
                .kpi-value { font-size: 13pt !important; }
                .kpi-label { font-size: 8pt !important; }
                .report-section { padding: 0 16px !important; margin-top: 14px !important; page-break-inside: avoid !important; }
                .section-title { border-radius: 6px !important; padding: 6px 12px !important; font-size: 10pt !important; margin-bottom: 8px !important; page-break-after: avoid !important; }
                .report-table-wrapper { border-radius: 6px !important; border: 1px solid #cbd5e1 !important; overflow: visible !important; page-break-inside: auto !important; }
                .report-table { font-size: 9pt !important; width: 100% !important; }
                .report-table thead { display: table-header-group !important; }
                .report-table thead th { padding: 6px 8px !important; font-size: 8pt !important; page-break-inside: avoid !important; }
                .report-table tbody td { padding: 5px 8px !important; font-size: 9pt !important; }
                .report-table tbody tr { page-break-inside: avoid !important; }
                .footer-text { border-top: 1px solid #e2e8f0 !important; padding: 8px 16px !important; font-size: 8pt !important; }
            }
            @media (max-width: 768px) {
                .report-toolbar { padding: 10px 16px; }
                .report-container { margin: 12px auto; padding: 0 10px; }
                .kpi-grid { grid-template-columns: repeat(2, 1fr); }
            }
        </style>
        <link href="/static/vendor/fontawesome-all.min.css" rel="stylesheet">`;
    },

    /**
     * Build a full report HTML page
     * @param {Object} config - { title, subtitle, kpis: [{value, label, class}], sections: [{title, icon, tableHTML}], filters }
     */
    buildReport(config) {
        const now = new Date();
        const dateStr = now.toLocaleDateString('ar-IQ', { year: 'numeric', month: 'long', day: 'numeric' });
        const timeStr = now.toLocaleTimeString('ar-IQ', { hour: '2-digit', minute: '2-digit' });

        let kpiHTML = '';
        if (config.kpis && config.kpis.length > 0) {
            kpiHTML = '<div class="kpi-grid">';
            config.kpis.forEach(kpi => {
                kpiHTML += `<div class="kpi-card ${kpi.cls || 'kpi-accent'}">
                    <div class="kpi-value">${kpi.value}</div>
                    <div class="kpi-label">${kpi.label}</div>
                </div>`;
            });
            kpiHTML += '</div>';
        }

        let filtersHTML = '';
        if (config.filters && config.filters.length > 0) {
            filtersHTML = '<div class="report-section"><div class="section-title"><i class="fas fa-filter"></i>الفلاتر المطبقة</div>';
            filtersHTML += '<div style="display:flex;flex-wrap:wrap;gap:6px;padding:0 0 8px 0;">';
            config.filters.forEach(f => {
                filtersHTML += `<span style="background:#eef2ff;color:#4f46e5;border:1px solid #c7d2fe;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;">${f}</span>`;
            });
            filtersHTML += '</div></div>';
        }

        let sectionsHTML = '';
        if (config.sections) {
            config.sections.forEach(sec => {
                sectionsHTML += `<div class="report-section" style="${sec.style || ''}">
                    <div class="section-title"><i class="fas fa-${sec.icon || 'table'}"></i>${sec.title}</div>
                    ${sec.content || ''}
                </div>`;
            });
        }

        return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>${config.title} - نظام إدارة المعهد</title>
    ${this.getReportCSS()}
</head>
<body>
    <div class="report-toolbar no-print">
        <div class="toolbar-brand">
            <i class="fas fa-chart-bar"></i>
            <span>نظام إدارة المعهد</span>
        </div>
        <div class="toolbar-actions">
            <button class="btn-print" onclick="smartPrint()">
                <i class="fas fa-print"></i>طباعة
            </button>
            <div class="toolbar-divider"></div>
            <button class="btn-close-report" onclick="window.close()">
                <i class="fas fa-arrow-right"></i>إغلاق
            </button>
        </div>
    </div>
    <div class="report-container">
        <div class="report-card">
            <div class="report-header">
                <div class="report-title">${config.title}</div>
                <div class="report-subtitle">${config.subtitle || ''}</div>
                <div class="report-date">تاريخ التقرير: ${dateStr} - ${timeStr}</div>
            </div>
            ${kpiHTML}
            ${filtersHTML}
            ${sectionsHTML}
            <div class="footer-text">نظام إدارة المعهد - Visions</div>
        </div>
    </div>
    <script>
        function smartPrint() {
            const tables = document.querySelectorAll('.report-table');
            tables.forEach(table => {
                const thead = table.querySelector('thead');
                const tfoot = table.querySelector('tfoot');
                if (thead && !tfoot) {
                    const newTfoot = document.createElement('tfoot');
                    newTfoot.innerHTML = thead.innerHTML;
                    newTfoot.setAttribute('role', 'repeat-header');
                    table.appendChild(newTfoot);
                }
            });
            window.print();
            setTimeout(() => {
                document.querySelectorAll('tfoot[role="repeat-header"]').forEach(el => el.remove());
            }, 500);
        }
    </script>
</body>
</html>`;
    },

    /**
     * Open a new window with the report
     */
    openReport(config) {
        const html = this.buildReport(config);
        const win = window.open('', '_blank', 'width=900,height=700');
        if (win) {
            win.document.write(html);
            win.document.close();
        }
    },

    /**
     * Collect visible rows from a table (after client-side filtering)
     * Returns array of cell text values
     */
    getVisibleTableRows(tableSelector, rowSelector) {
        const rows = [];
        document.querySelectorAll(tableSelector + ' ' + rowSelector).forEach(row => {
            if (row.style.display === 'none') return;
            const cells = [];
            row.querySelectorAll('td').forEach(td => {
                cells.push(td.textContent.trim());
            });
            rows.push(cells);
        });
        return rows;
    },

    /**
     * Collect visible card items (after client-side filtering)
     */
    getVisibleCards(cardSelector) {
        const items = [];
        document.querySelectorAll(cardSelector).forEach(card => {
            if (card.style.display === 'none') return;
            const data = {};
            for (const key in card.dataset) {
                data[key] = card.dataset[key];
            }
            // Also collect text content of specific elements
            items.push(data);
        });
        return items;
    },

    /**
     * Build a report-table HTML from headers and rows
     */
    buildTableHTML(headers, rows, options = {}) {
        let html = '<div class="report-table-wrapper"><table class="report-table">';
        html += '<thead><tr>';
        headers.forEach((h, i) => {
            const align = options.aligns && options.aligns[i] ? options.aligns[i] : '';
            html += `<th${align ? ' class="text-center"' : ''}>${h}</th>`;
        });
        html += '</tr></thead><tbody>';

        rows.forEach((row, idx) => {
            html += `<tr${options.totalRow && idx === rows.length - 1 ? ' class="total-row"' : ''}>`;
            row.forEach((cell, i) => {
                const align = options.aligns && options.aligns[i] ? ' style="text-align:center"' : '';
                html += `<td${align}>${cell}</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        return html;
    },

    // ===== PAGE-SPECIFIC PRINT FUNCTIONS =====

    /**
     * Print Students List
     */
    printStudents() {
        const visibleRows = [];
        const allRows = document.querySelectorAll('.student-row');
        let totalPaid = 0, totalRemaining = 0, count = 0;

        allRows.forEach(row => {
            if (row.style.display === 'none') return;
            count++;
            totalPaid += parseInt(row.dataset.paid) || 0;
            totalRemaining += parseInt(row.dataset.remaining) || 0;

            const cells = row.querySelectorAll('td');
            const name = cells[1] ? cells[1].textContent.trim().split('\n')[0].trim() : '';
            const status = row.dataset.status || '';
            const paid = parseInt(row.dataset.paid) || 0;
            const remaining = parseInt(row.dataset.remaining) || 0;

            visibleRows.push([
                count,
                name,
                `<span class="badge-${status === 'مستمر' ? 'paid' : status === 'منسحب' ? 'unpaid' : 'withdrawn'}">${status}</span>`,
                formatCurrency(paid),
                remaining > 0 ? `<span style="color:var(--danger);font-weight:700">${formatCurrency(remaining)}</span>` : '<span style="color:var(--success)"><i class="fas fa-check-circle"></i></span>'
            ]);
        });

        if (visibleRows.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        // Add totals row
        visibleRows.push([
            '', 'الإجمالي', '', formatCurrency(totalPaid),
            totalRemaining > 0 ? `<span style="color:var(--danger);font-weight:700">${formatCurrency(totalRemaining)}</span>` : '<span style="color:var(--success)">0</span>'
        ]);

        // Collect active filters
        const filters = [];
        const searchVal = document.getElementById('studentLiveSearch')?.value;
        if (searchVal) filters.push('بحث: ' + searchVal);
        const statusFilter = document.getElementById('filterStatus')?.value;
        if (statusFilter) filters.push('الحالة: ' + statusFilter);
        const paymentFilter = document.getElementById('filterPayment')?.value;
        if (paymentFilter) filters.push('الدفع: ' + paymentFilter);
        const teacherFilter = document.getElementById('filterTeacher');
        if (teacherFilter && teacherFilter.value) filters.push('المدرس: ' + teacherFilter.options[teacherFilter.selectedIndex].text);
        const studyTypeFilter = document.getElementById('filterStudyType')?.value;
        if (studyTypeFilter) filters.push('نوع الدراسة: ' + studyTypeFilter);
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        this.openReport({
            title: 'تقرير الطلاب',
            subtitle: `${count} طالب مسجل`,
            kpis: [
                { value: count, label: 'إجمالي الطلاب', cls: 'kpi-accent' },
                { value: formatCurrency(totalPaid), label: 'إجمالي المدفوع', cls: 'kpi-success' },
                { value: formatCurrency(totalRemaining), label: 'إجمالي المتبقي', cls: totalRemaining > 0 ? 'kpi-danger' : 'kpi-success' },
                { value: totalPaid + totalRemaining > 0 ? Math.round(totalPaid / (totalPaid + totalRemaining) * 100) + '%' : '0%', label: 'نسبة الدفع', cls: 'kpi-warning' }
            ],
            filters: filters,
            sections: [{
                title: 'قائمة الطلاب',
                icon: 'users',
                content: this.buildTableHTML(
                    ['#', 'اسم الطالب', 'الحالة', 'المدفوع', 'المتبقي'],
                    visibleRows,
                    { aligns: ['', '', 'text-center', 'text-center', 'text-center'], totalRow: true }
                )
            }]
        });
    },

    /**
     * Print Teachers List - includes institute rate, institute deduction, teacher due, withdrawn
     */
    printTeachers() {
        const visibleRows = [];
        const allRows = document.querySelectorAll('.teacher-row');
        let totalReceived = 0, totalRemaining = 0, totalDeduction = 0, totalTeacherDue = 0, totalWithdrawn = 0, count = 0;

        allRows.forEach(row => {
            if (row.style.display === 'none') return;
            count++;
            totalReceived += parseInt(row.dataset.received) || 0;
            totalRemaining += parseInt(row.dataset.remaining) || 0;
            totalDeduction += parseInt(row.dataset.deduction) || 0;
            totalTeacherDue += parseInt(row.dataset.teacherDue) || 0;
            totalWithdrawn += parseInt(row.dataset.withdrawn) || 0;

            const cells = row.querySelectorAll('td');
            const name = cells[1] ? cells[1].textContent.trim().split('\n')[0].trim() : '';
            const subject = row.dataset.subject || '';
            const received = parseInt(row.dataset.received) || 0;
            const rateDisplay = row.dataset.rateDisplay || '';
            const deduction = parseInt(row.dataset.deduction) || 0;
            const teacherDue = parseInt(row.dataset.teacherDue) || 0;
            const withdrawn = parseInt(row.dataset.withdrawn) || 0;
            const remaining = parseInt(row.dataset.remaining) || 0;
            const students = parseInt(row.dataset.students) || 0;
            const feeDisplay = row.dataset.feeDisplay || '';

            visibleRows.push([
                count,
                name,
                `<span class="badge-continue">${subject}</span>`,
                students,
                formatCurrency(received),
                feeDisplay || '-',
                rateDisplay || '-',
                `<span style="color:var(--danger);font-weight:600">${formatCurrency(deduction)}</span>`,
                `<span style="color:var(--info);font-weight:600">${formatCurrency(teacherDue)}</span>`,
                `<span style="color:var(--warning);font-weight:600">${formatCurrency(withdrawn)}</span>`,
                remaining > 0 ? `<span style="color:var(--success);font-weight:700">${formatCurrency(remaining)}</span>` : '<span style="color:var(--muted)">0</span>'
            ]);
        });

        if (visibleRows.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        visibleRows.push([
            '', 'الإجمالي', '', '', formatCurrency(totalReceived), '', '',
            `<span style="color:var(--danger);font-weight:700">${formatCurrency(totalDeduction)}</span>`,
            `<span style="color:var(--info);font-weight:700">${formatCurrency(totalTeacherDue)}</span>`,
            `<span style="color:var(--warning);font-weight:700">${formatCurrency(totalWithdrawn)}</span>`,
            totalRemaining > 0 ? formatCurrency(totalRemaining) : '0'
        ]);

        const filters = [];
        const searchVal = document.getElementById('teacherLiveSearch')?.value;
        if (searchVal) filters.push('بحث: ' + searchVal);
        const subjectFilter = document.querySelector('select[name="subject"]');
        if (subjectFilter && subjectFilter.value) filters.push('المادة: ' + subjectFilter.options[subjectFilter.selectedIndex].text);
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        this.openReport({
            title: 'تقرير المدرسين الشامل',
            subtitle: `${count} مدرس مسجل`,
            kpis: [
                { value: count, label: 'إجمالي المدرسين', cls: 'kpi-success' },
                { value: formatCurrency(totalReceived), label: 'إجمالي المدفوع', cls: 'kpi-accent' },
                { value: formatCurrency(totalDeduction), label: 'إجمالي خصم المعهد', cls: 'kpi-danger' },
                { value: formatCurrency(totalTeacherDue), label: 'إجمالي مستحق المدرسين', cls: 'kpi-info' },
                { value: formatCurrency(totalWithdrawn), label: 'إجمالي المسحوب', cls: 'kpi-warning' },
                { value: formatCurrency(totalRemaining), label: 'إجمالي متبقي المدرسين', cls: totalRemaining > 0 ? 'kpi-success' : 'kpi-purple' }
            ],
            filters: filters,
            sections: [{
                title: 'قائمة المدرسين - التفاصيل المالية الشاملة',
                icon: 'chalkboard-teacher',
                content: this.buildTableHTML(
                    ['#', 'المدرس', 'المادة', 'الطلاب', 'المدفوع', 'قسط الأستاذ', 'نسبة المعهد', 'خصم المعهد', 'مستحق المدرس', 'المسحوب', 'المتبقي'],
                    visibleRows,
                    { aligns: ['', '', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center'], totalRow: true }
                )
            }]
        });
    },

    /**
     * Print Subjects List
     */
    printSubjects() {
        const visibleRows = [];
        const allRows = document.querySelectorAll('.subject-row');
        let totalTeachers = 0, count = 0;

        allRows.forEach(row => {
            if (row.style.display === 'none') return;
            count++;
            totalTeachers += parseInt(row.dataset.teachers) || 0;

            const cells = row.querySelectorAll('td');
            const name = cells[1] ? cells[1].textContent.trim() : '';
            const teachers = parseInt(row.dataset.teachers) || 0;

            visibleRows.push([count, name, teachers + ' مدرس']);
        });

        if (visibleRows.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        const filters = [];
        const searchVal = document.getElementById('subjectLiveSearch')?.value;
        if (searchVal) filters.push('بحث: ' + searchVal);
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        this.openReport({
            title: 'تقرير المواد الدراسية',
            subtitle: `${count} مادة مسجلة`,
            kpis: [
                { value: count, label: 'إجمالي المواد', cls: 'kpi-purple' },
                { value: totalTeachers, label: 'إجمالي المدرسين', cls: 'kpi-accent' }
            ],
            filters: filters,
            sections: [{
                title: 'قائمة المواد الدراسية',
                icon: 'book-open',
                content: this.buildTableHTML(
                    ['#', 'المادة', 'عدد المدرسين'],
                    visibleRows,
                    { aligns: ['', '', 'text-center'] }
                )
            }]
        });
    },

    /**
     * Print Payments/Installments List - includes financial summary with deductions
     */
    printPayments() {
        const visibleRows = [];
        const allRows = document.querySelectorAll('.payment-row');
        let totalAmount = 0, totalRemaining = 0, count = 0;
        const studentSet = new Set();

        allRows.forEach(row => {
            if (row.style.display === 'none') return;
            count++;
            totalAmount += parseInt(row.dataset.amount) || 0;
            totalRemaining += parseInt(row.dataset.remaining) || 0;

            const cells = row.querySelectorAll('td');
            const name = cells[1] ? cells[1].textContent.trim().split('\n')[0].trim() : '';
            const teacher = cells[2] ? cells[2].textContent.trim() : '';
            const subject = cells[3] ? cells[3].textContent.trim() : '';
            const amount = parseInt(row.dataset.amount) || 0;
            const remaining = parseInt(row.dataset.remaining) || 0;
            const type = row.dataset.type || '';
            const date = cells[7] ? cells[7].textContent.trim() : '';

            if (row.dataset.name) studentSet.add(row.dataset.name);

            visibleRows.push([
                count,
                name,
                teacher,
                `<span class="badge-continue">${subject}</span>`,
                formatCurrency(amount),
                remaining > 0 ? `<span style="color:var(--danger);font-weight:700">${formatCurrency(remaining)}</span>` : '<span style="color:var(--success)"><i class="fas fa-check-circle"></i></span>',
                `<span class="badge-continue">${type}</span>`,
                date
            ]);
        });

        if (visibleRows.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        visibleRows.push([
            '', 'الإجمالي', '', '', formatCurrency(totalAmount),
            totalRemaining > 0 ? formatCurrency(totalRemaining) : '0', '', ''
        ]);

        const filters = [];
        // Check all filter checkboxes and values
        const filterChecks = document.querySelectorAll('.filter-checkbox');
        filterChecks.forEach(chk => {
            if (chk.checked) {
                const target = document.getElementById(chk.dataset.target);
                if (target && target.value) {
                    const label = chk.closest('.sf-field, [class*="col-"]')?.querySelector('label')?.textContent?.trim() || '';
                    filters.push(label + ': ' + target.value);
                }
            }
        });
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        // Collect financial summary stats from the page header cards
        const summaryCards = document.querySelectorAll('.bg-gradient-emerald, .bg-gradient-blue, .bg-gradient-purple');
        let totalPaidFromCards = totalAmount;
        let totalOperations = count;
        let totalPayers = studentSet.size;
        summaryCards.forEach(card => {
            const valueText = card.querySelector('h5')?.textContent?.trim() || '';
        });

        this.openReport({
            title: 'تقرير الأقساط والمدفوعات الشامل',
            subtitle: `${count} عملية دفع`,
            kpis: [
                { value: formatCurrency(totalAmount), label: 'إجمالي المدفوعات', cls: 'kpi-success' },
                { value: count, label: 'عدد العمليات', cls: 'kpi-accent' },
                { value: studentSet.size, label: 'الدافعون', cls: 'kpi-purple' },
                { value: formatCurrency(totalRemaining), label: 'إجمالي المتبقي', cls: totalRemaining > 0 ? 'kpi-danger' : 'kpi-success' }
            ],
            filters: filters,
            sections: [{
                title: 'سجل الأقساط والمدفوعات',
                icon: 'money-check-alt',
                content: this.buildTableHTML(
                    ['#', 'الطالب', 'المدرس', 'المادة', 'المبلغ', 'المتبقي', 'النوع', 'التاريخ'],
                    visibleRows,
                    { aligns: ['', '', '', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center'], totalRow: true }
                )
            }]
        });
    },

    /**
     * Print Withdrawals List
     */
    printWithdrawals() {
        const visibleRows = [];
        const allRows = document.querySelectorAll('.withdrawal-row');
        let totalAmount = 0, count = 0;

        allRows.forEach(row => {
            if (row.style.display === 'none') return;
            count++;
            totalAmount += parseInt(row.dataset.amount) || 0;

            const cells = row.querySelectorAll('td');
            const name = cells[1] ? cells[1].textContent.trim() : '';
            const subject = cells[2] ? cells[2].textContent.trim() : '';
            const amount = parseInt(row.dataset.amount) || 0;
            const date = cells[4] ? cells[4].textContent.trim() : '';
            const notes = cells[5] ? cells[5].textContent.trim() : '-';

            visibleRows.push([
                count,
                name,
                `<span class="badge-continue">${subject}</span>`,
                `<span style="color:var(--warning);font-weight:700">${formatCurrency(amount)}</span>`,
                date,
                notes
            ]);
        });

        if (visibleRows.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        visibleRows.push([
            '', 'الإجمالي', '', formatCurrency(totalAmount), '', ''
        ]);

        const filters = [];
        const dateFrom = document.getElementById('w_filter_date_from')?.value;
        const dateTo = document.getElementById('w_filter_date_to')?.value;
        if (dateFrom) filters.push('من: ' + dateFrom);
        if (dateTo) filters.push('إلى: ' + dateTo);
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        this.openReport({
            title: 'تقرير السحوبات',
            subtitle: `${count} عملية سحب`,
            kpis: [
                { value: formatCurrency(totalAmount), label: 'إجمالي المسحوبات', cls: 'kpi-warning' },
                { value: count, label: 'عدد العمليات', cls: 'kpi-accent' }
            ],
            filters: filters,
            sections: [{
                title: 'سجل السحوبات',
                icon: 'hand-holding-usd',
                content: this.buildTableHTML(
                    ['#', 'المدرس', 'المادة', 'المبلغ', 'التاريخ', 'ملاحظات'],
                    visibleRows,
                    { aligns: ['', '', 'text-center', 'text-center', 'text-center', ''], totalRow: true }
                )
            }]
        });
    },

    /**
     * Print Accounting Page - comprehensive with deductions, teacher due, withdrawn
     */
    printAccounting() {
        const visibleCards = [];
        const allCards = document.querySelectorAll('.accounting-card');
        let totalReceived = 0, totalDeduction = 0, totalTeacherDue = 0, totalWithdrawn = 0, totalRemaining = 0, totalStudents = 0, count = 0;

        allCards.forEach(card => {
            if (card.style.display === 'none') return;
            count++;
            const received = parseInt(card.dataset.received) || 0;
            const deduction = parseInt(card.dataset.deduction) || 0;
            const teacherDue = parseInt(card.dataset.teacherDue) || 0;
            const withdrawn = parseInt(card.dataset.withdrawn) || 0;
            const remaining = parseInt(card.dataset.remaining) || 0;
            const students = parseInt(card.dataset.students) || 0;
            totalReceived += received;
            totalDeduction += deduction;
            totalTeacherDue += teacherDue;
            totalWithdrawn += withdrawn;
            totalRemaining += remaining;
            totalStudents += students;

            visibleCards.push({
                name: card.dataset.name || '',
                subject: card.dataset.subject || '',
                received: received,
                deduction: deduction,
                teacherDue: teacherDue,
                withdrawn: withdrawn,
                remaining: remaining,
                students: students
            });
        });

        if (visibleCards.length === 0) {
            showAlert('لا توجد بيانات للطباعة', 'warning');
            return;
        }

        const rows = visibleCards.map((c, i) => [
            i + 1,
            c.name,
            `<span class="badge-continue">${c.subject}</span>`,
            c.students,
            formatCurrency(c.received),
            `<span style="color:var(--danger);font-weight:600">${formatCurrency(c.deduction)}</span>`,
            `<span style="color:var(--info);font-weight:600">${formatCurrency(c.teacherDue)}</span>`,
            `<span style="color:var(--warning);font-weight:600">${formatCurrency(c.withdrawn)}</span>`,
            c.remaining > 0 ? `<span style="color:var(--success);font-weight:700">${formatCurrency(c.remaining)}</span>` : '<span style="color:var(--muted)">0</span>'
        ]);

        rows.push([
            '', 'الإجمالي', '', totalStudents, formatCurrency(totalReceived),
            `<span style="color:var(--danger);font-weight:700">${formatCurrency(totalDeduction)}</span>`,
            `<span style="color:var(--info);font-weight:700">${formatCurrency(totalTeacherDue)}</span>`,
            `<span style="color:var(--warning);font-weight:700">${formatCurrency(totalWithdrawn)}</span>`,
            totalRemaining > 0 ? formatCurrency(totalRemaining) : '0'
        ]);

        const filters = [];
        const searchVal = document.getElementById('accountingLiveSearch')?.value;
        if (searchVal) filters.push('بحث: ' + searchVal);
        const dateFrom = document.getElementById('acc_filter_date_from')?.value;
        const dateTo = document.getElementById('acc_filter_date_to')?.value;
        if (dateFrom) filters.push('من: ' + dateFrom);
        if (dateTo) filters.push('إلى: ' + dateTo);
        const sortText = this.getActiveSortLabel();
        if (sortText) filters.push('الترتيب: ' + sortText);

        this.openReport({
            title: 'تقرير محاسبة المدرسين الشامل',
            subtitle: `${count} مدرس`,
            kpis: [
                { value: count, label: 'المدرسين', cls: 'kpi-accent' },
                { value: totalStudents, label: 'الطلاب الكلي', cls: 'kpi-success' },
                { value: formatCurrency(totalReceived), label: 'إجمالي المدفوع', cls: 'kpi-accent' },
                { value: formatCurrency(totalDeduction), label: 'إجمالي خصم المعهد', cls: 'kpi-danger' },
                { value: formatCurrency(totalTeacherDue), label: 'إجمالي مستحق المدرسين', cls: 'kpi-info' },
                { value: formatCurrency(totalWithdrawn), label: 'إجمالي المسحوب', cls: 'kpi-warning' },
                { value: formatCurrency(totalRemaining), label: 'إجمالي المتبقي', cls: 'kpi-purple' }
            ],
            filters: filters,
            sections: [{
                title: 'ملخص محاسبة المدرسين - التفاصيل الشاملة',
                icon: 'calculator',
                content: this.buildTableHTML(
                    ['#', 'المدرس', 'المادة', 'الطلاب', 'المدفوع', 'خصم المعهد', 'مستحق المدرس', 'المسحوب', 'المتبقي'],
                    rows,
                    { aligns: ['', '', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center', 'text-center'], totalRow: true }
                )
            }]
        });
    },

    /**
     * Print Statistics Page with selective info - includes deductions and institute rates
     */
    printStats() {
        // Get stats data from the page
        const statsRows = document.querySelectorAll('.stats-detail-table tbody tr');
        const allData = [];
        statsRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                allData.push({
                    label: cells[0].textContent.trim(),
                    value: cells[1].textContent.trim()
                });
            }
        });

        // Collect KPI data from stat cards
        const statCards = document.querySelectorAll('.main-stat-card');
        const kpis = [];
        statCards.forEach(card => {
            const label = card.querySelector('.ms-label')?.textContent?.trim() || '';
            const value = card.querySelector('.ms-value')?.textContent?.trim() || '';
            const icon = card.querySelector('.ms-icon i')?.className?.replace('fas fa-', '') || 'chart-bar';
            let cls = 'kpi-accent';
            if (card.classList.contains('ms-success')) cls = 'kpi-success';
            else if (card.classList.contains('ms-purple')) cls = 'kpi-purple';
            else if (card.classList.contains('ms-warning')) cls = 'kpi-warning';
            kpis.push({ value: value, label: label, cls: cls });
        });

        // Financial summary
        const finItems = document.querySelectorAll('.fin-stat-item');
        const finRows = [];
        finItems.forEach(item => {
            const label = item.querySelector('.fin-stat-label')?.textContent?.trim() || '';
            const value = item.querySelector('.fin-stat-value')?.textContent?.trim() || '';
            const badge = item.querySelector('.badge')?.textContent?.trim() || '';
            finRows.push([label, value, badge]);
        });

        // Net revenue
        const netBox = document.querySelector('.net-box');
        const netLabel = netBox?.querySelector('.net-box-label')?.textContent?.trim() || '';
        const netValue = netBox?.querySelector('.net-box-value')?.textContent?.trim() || '';
        const netSub = netBox?.querySelector('.net-box-sub')?.textContent?.trim() || '';

        // Build detail table rows
        const detailRows = allData.map(d => [d.label, d.value]);

        // Check which checkboxes are selected
        const printCheckboxes = document.querySelectorAll('.print-select-cb');
        let selectedData = allData;
        let selectedFinRows = finRows;
        let includeKPIs = true;
        let includeDetail = true;
        let includeFinancial = true;
        let includeDeductions = true;
        let includeTeacherDue = true;

        if (printCheckboxes.length > 0) {
            includeKPIs = document.getElementById('print_cb_kpis')?.checked !== false;
            includeDetail = document.getElementById('print_cb_detail')?.checked !== false;
            includeFinancial = document.getElementById('print_cb_financial')?.checked !== false;
            includeDeductions = document.getElementById('print_cb_deductions')?.checked !== false;
            includeTeacherDue = document.getElementById('print_cb_teacher_due')?.checked !== false;

            // Filter detail rows based on individual checkboxes
            selectedData = [];
            allData.forEach((d, i) => {
                const cb = document.getElementById('print_cb_detail_' + i);
                if (!cb || cb.checked) selectedData.push(d);
            });

            selectedFinRows = [];
            finRows.forEach((r, i) => {
                const cb = document.getElementById('print_cb_fin_' + i);
                if (!cb || cb.checked) selectedFinRows.push(r);
            });
        }

        const sections = [];

        if (includeDetail && selectedData.length > 0) {
            sections.push({
                title: 'جدول الإحصائيات التفصيلية',
                icon: 'table',
                content: this.buildTableHTML(
                    ['البند', 'القيمة'],
                    selectedData.map(d => [d.label, `<span style="font-weight:700">${d.value}</span>`]),
                    { aligns: ['', 'text-center'] }
                )
            });
        }

        if (includeFinancial && selectedFinRows.length > 0) {
            const finTableRows = selectedFinRows.map(r => [r[0], `<span style="font-weight:700">${r[1]}</span>`, r[2]]);
            sections.push({
                title: 'الملخص المالي',
                icon: 'coins',
                content: this.buildTableHTML(
                    ['البند', 'المبلغ', 'ملاحظة'],
                    finTableRows,
                    { aligns: ['', 'text-center', 'text-center'] }
                )
            });
        }

        // خصم المعهد (إيرادات المعهد)
        if (includeDeductions) {
            // استخراج بيانات الخصم من جدول التفاصيل أو من البطاقات المالية
            const deductionData = allData.find(d => d.label.includes('خصم المعهد') || d.label.includes('استقطاع'));
            const totalDeduction = deductionData ? deductionData.value : '';
            if (totalDeduction) {
                sections.push({
                    title: 'إيرادات المعهد (الاستقطاعات)',
                    icon: 'building',
                    content: `<div style="text-align:center;padding:20px;background:#ecfdf5;border-radius:14px;border:2px solid rgba(16,185,129,0.25);">
                        <div style="font-size:11px;color:var(--muted);margin-bottom:4px;">إجمالي إيرادات المعهد (الاستقطاعات)</div>
                        <div style="font-size:28px;font-weight:900;color:var(--success);">${totalDeduction}</div>
                        <div style="font-size:12px;color:var(--muted);margin-top:4px;">نسبة المعهد المستقطعة من المدفوعات</div>
                    </div>`
                });
            }
        }

        // مستحق المدرسين
        if (includeTeacherDue) {
            const teacherDueData = allData.find(d => d.label.includes('مستحق المدرس'));
            const totalTeacherDue = teacherDueData ? teacherDueData.value : '';
            if (totalTeacherDue) {
                sections.push({
                    title: 'مستحق المدرسين',
                    icon: 'user-tie',
                    content: `<div style="text-align:center;padding:20px;background:rgba(6,182,212,0.06);border-radius:14px;border:2px solid rgba(6,182,212,0.25);">
                        <div style="font-size:11px;color:var(--muted);margin-bottom:4px;">إجمالي مستحق المدرسين (بعد خصم المعهد)</div>
                        <div style="font-size:28px;font-weight:900;color:var(--info);">${totalTeacherDue}</div>
                        <div style="font-size:12px;color:var(--muted);margin-top:4px;">المدفوعات - خصم المعهد = مستحق المدرسين</div>
                    </div>`
                });
            }
        }

        // Add comprehensive financial summary KPIs if deductions are included
        const enhancedKpis = includeKPIs ? [...kpis] : [];
        if (includeDeductions && includeKPIs) {
            // Already have the stat cards, add institute-specific KPIs
            const deductionData = allData.find(d => d.label.includes('خصم المعهد') || d.label.includes('استقطاع'));
            if (deductionData) {
                enhancedKpis.push({ value: deductionData.value, label: 'خصم المعهد', cls: 'kpi-danger' });
            }
        }

        this.openReport({
            title: 'التقرير الإحصائي الشامل',
            subtitle: 'نظرة شاملة على أداء المعهد مع التفاصيل المالية',
            kpis: enhancedKpis,
            sections: sections
        });
    }
};
