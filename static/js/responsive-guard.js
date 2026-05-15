/* ================================================================
   responsive-guard.js
   حارس خفيف للاستجابة: يلف الجداول غير الملفوفة، ويمنع بقاء عرض الجدول
   الأسبوعي الثقيل كخيار افتراضي على الشاشات الصغيرة.
================================================================ */
(function () {
    'use strict';

    const MOBILE_QUERY = '(max-width: 767.98px)';
    const media = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;

    function wrapNakedTables(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll('main table').forEach(table => {
            if (table.closest('.table-responsive,.ai-responsive-table-wrap,.ws-grid-scroll,.report-table-wrapper')) return;
            if (table.classList.contains('ws-grid')) return;
            const wrapper = document.createElement('div');
            wrapper.className = 'ai-responsive-table-wrap';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });
    }

    function markWideActionBars(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll('.d-flex').forEach(el => {
            const children = el.children ? el.children.length : 0;
            if (children >= 3 && !el.classList.contains('ai-flex-safe')) {
                el.classList.add('ai-flex-safe');
            }
        });
    }

    function preferWeeklyListOnMobile() {
        if (!media || !media.matches) return;
        if (!document.body || !document.getElementById('gridWrap') || !document.getElementById('listWrap')) return;
        if (window.__weeklyManualViewChoice) return;
        if (typeof window.setView === 'function') {
            window.setView('list', true);
        }
    }

    function run(root) {
        wrapNakedTables(root || document);
        markWideActionBars(root || document);
        preferWeeklyListOnMobile();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => run(document));
    } else {
        run(document);
    }
    window.addEventListener('load', () => run(document), { once: true });

    if (media && media.addEventListener) {
        media.addEventListener('change', () => preferWeeklyListOnMobile());
    }

    let queued = false;
    const observer = new MutationObserver(mutations => {
        if (queued) return;
        queued = true;
        window.requestAnimationFrame(() => {
            queued = false;
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (node.nodeType === 1) run(node);
                }
            }
        });
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
