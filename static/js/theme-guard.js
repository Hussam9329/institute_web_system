/* ================================================================
   theme-guard.js
   نسخة خفيفة: تعالج فقط العناصر الجديدة أو مناطق الثيم المهمة، بدل فحص
   الصفحة كلها مع كل تغيير. هذا يحافظ على السلاسة في الجداول والمودالات.
================================================================ */
(function () {
    'use strict';

    const DARK_SAFE_CLASS = 'theme-guard-dark-surface';
    const ON_BRAND_CLASS = 'theme-guard-on-brand';
    const LIGHT_BG_RE = /(background(?:-color)?\s*:\s*)(white|#fff\b|#ffffff\b|#f8fafc\b|#fffbeb\b|#fff8ed\b|#eef2ff\b|#f0f9ff\b|#f0fdf4\b)/i;

    function currentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    }

    function isOnBrand(el) {
        return !!(el && el.closest && el.closest(
            '.dash-welcome,.stat-card,.bg-gradient-blue,.bg-gradient-emerald,.bg-gradient-purple,.bg-gradient-orange,.modal-header.text-white,.card-header[class*="bg-gradient"],.main-footer,.ws-modal .modal-header'
        ));
    }

    function guardElement(el, dark) {
        if (!el || el.nodeType !== 1) return;
        const style = el.getAttribute && el.getAttribute('style');
        if (style && dark && LIGHT_BG_RE.test(style) && !isOnBrand(el)) {
            el.classList.add(DARK_SAFE_CLASS);
        } else if (style) {
            el.classList.remove(DARK_SAFE_CLASS);
        }
        if (el.matches && el.matches('.dash-welcome,.stat-card,.bg-gradient-blue,.bg-gradient-emerald,.bg-gradient-purple,.bg-gradient-orange,.main-footer')) {
            el.classList.add(ON_BRAND_CLASS);
        }
    }

    function guard(root) {
        const scope = root && root.querySelectorAll ? root : document;
        const dark = currentTheme() === 'dark';
        guardElement(scope, dark);
        scope.querySelectorAll('[style],.dash-welcome,.stat-card,.bg-gradient-blue,.bg-gradient-emerald,.bg-gradient-purple,.bg-gradient-orange,.main-footer').forEach(el => guardElement(el, dark));
    }

    function schedule(root) {
        if ('requestIdleCallback' in window) {
            window.requestIdleCallback(() => guard(root), { timeout: 350 });
        } else {
            window.requestAnimationFrame(() => guard(root));
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => schedule(document));
    } else {
        schedule(document);
    }

    window.addEventListener('load', () => schedule(document), { once: true });
    document.addEventListener('shown.bs.modal', e => schedule(e.target || document));
    document.addEventListener('themechange', () => schedule(document));

    let queued = false;
    const pending = new Set();
    const observer = new MutationObserver(mutations => {
        for (const m of mutations) {
            if (m.type === 'attributes') pending.add(m.target);
            for (const node of m.addedNodes) {
                if (node.nodeType === 1) pending.add(node);
            }
        }
        if (queued) return;
        queued = true;
        window.requestAnimationFrame(() => {
            queued = false;
            const nodes = Array.from(pending);
            pending.clear();
            nodes.forEach(node => guard(node));
        });
    });

    observer.observe(document.documentElement, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ['style', 'data-theme']
    });
})();
