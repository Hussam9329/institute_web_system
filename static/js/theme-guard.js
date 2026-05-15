/* ================================================================
   theme-guard.js
   حارس تباين خفيف للعناصر التي تُنشأ ديناميكياً أو تحتوي inline styles.
   لا يبدل التصميم، فقط يضيف كلاس مساعد ويمنع الأبيض كخلفية في الوضع الليلي.
================================================================ */
(function () {
    'use strict';

    const DARK_SAFE_CLASS = 'theme-guard-dark-surface';
    const ON_BRAND_CLASS = 'theme-guard-on-brand';

    function theme() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    }

    function looksWhite(value) {
        if (!value) return false;
        const v = String(value).replace(/\s+/g, '').toLowerCase();
        return v.includes('background:white') ||
               v.includes('background-color:white') ||
               v.includes('background:#fff') ||
               v.includes('background-color:#fff') ||
               v.includes('background:#ffffff') ||
               v.includes('background-color:#ffffff') ||
               v.includes('background:#f8fafc') ||
               v.includes('background:#fffbeb') ||
               v.includes('background:#fff8ed') ||
               v.includes('background:#eef2ff') ||
               v.includes('background:#f0f9ff') ||
               v.includes('background:#f0fdf4');
    }

    function isOnBrand(el) {
        if (!el || !el.closest) return false;
        return !!el.closest('.dash-welcome,.stat-card,.bg-gradient-blue,.bg-gradient-emerald,.bg-gradient-purple,.bg-gradient-orange,.modal-header.text-white,.card-header[class*="bg-gradient"],.main-footer');
    }

    function guard(root) {
        const scope = root && root.querySelectorAll ? root : document;
        const dark = theme() === 'dark';

        scope.querySelectorAll('[style]').forEach(el => {
            const style = el.getAttribute('style') || '';
            if (dark && looksWhite(style) && !isOnBrand(el)) {
                el.classList.add(DARK_SAFE_CLASS);
            } else {
                el.classList.remove(DARK_SAFE_CLASS);
            }
        });

        scope.querySelectorAll('.dash-welcome,.stat-card,.bg-gradient-blue,.bg-gradient-emerald,.bg-gradient-purple,.bg-gradient-orange,.main-footer').forEach(el => {
            el.classList.add(ON_BRAND_CLASS);
        });
    }

    function run() { guard(document); }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }

    window.addEventListener('load', run);
    document.addEventListener('shown.bs.modal', run);
    document.addEventListener('hidden.bs.modal', run);
    document.addEventListener('themechange', run);

    const observer = new MutationObserver(mutations => {
        let needsRun = false;
        for (const m of mutations) {
            if (m.type === 'attributes' || m.addedNodes.length) { needsRun = true; break; }
        }
        if (needsRun) window.requestAnimationFrame(run);
    });

    observer.observe(document.documentElement, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ['class', 'style', 'data-theme']
    });
})();
