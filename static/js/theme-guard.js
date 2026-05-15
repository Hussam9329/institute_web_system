/* ============================================================================
   theme-guard.js
   حارس تباين وتشذيب ألوان وقت التشغيل.
   يعالج العناصر المبنية ديناميكياً أو ذات inline-style حتى لا تختفي النصوص.
============================================================================ */
(function () {
    'use strict';

    const ROOT = document.documentElement;
    const MIN_CONTRAST = 4.5;
    let scheduled = false;

    function parseRGB(value) {
        if (!value || value === 'transparent') return null;
        const m = value.match(/rgba?\(([^)]+)\)/i);
        if (!m) return null;
        const parts = m[1].split(',').map(v => parseFloat(v.trim()));
        if (parts.length < 3) return null;
        return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
    }

    function luminance(c) {
        function channel(v) {
            v /= 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
    }

    function contrast(a, b) {
        const la = luminance(a);
        const lb = luminance(b);
        const hi = Math.max(la, lb);
        const lo = Math.min(la, lb);
        return (hi + 0.05) / (lo + 0.05);
    }

    function effectiveBackground(el) {
        let node = el;
        while (node && node.nodeType === 1) {
            const bg = parseRGB(getComputedStyle(node).backgroundColor);
            if (bg && bg.a > 0.05) return bg;
            node = node.parentElement;
        }
        return ROOT.getAttribute('data-theme') === 'dark'
            ? { r: 7, g: 17, b: 29, a: 1 }
            : { r: 234, g: 240, b: 247, a: 1 };
    }

    function hasVisibleText(el) {
        if (!el || ['SCRIPT', 'STYLE', 'META', 'LINK', 'IMG', 'SVG', 'CANVAS', 'PATH'].includes(el.tagName)) return false;
        if (el.matches('input, textarea, select, option, button')) return true;
        const text = (el.textContent || '').replace(/\s+/g, '');
        return text.length > 0 && Array.from(el.children).length < 8;
    }

    function isTableElement(el) {
        return el.matches('table, thead, tbody, tfoot, tr, td, th') || !!el.closest('table, .table');
    }

    function fixElement(el) {
        if (!(el instanceof Element)) return;
        if (el.closest('.print-only, .receipt-print, [data-theme-guard="off"]')) return;

        const theme = ROOT.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        const cs = getComputedStyle(el);
        const bg = parseRGB(cs.backgroundColor);
        const fg = parseRGB(cs.color);

        if (theme === 'dark' && bg && bg.a > 0.2) {
            const lum = luminance(bg);
            // أي سطح فاتح جداً في الدارك يتحول لسطح داكن. الجداول لها سطحها الخاص.
            if (lum > 0.62) {
                el.style.setProperty('background-color', isTableElement(el) ? 'var(--app-table-row-bg)' : 'var(--app-surface)', 'important');
                el.style.setProperty('border-color', 'var(--app-border)', 'important');
            }
        }

        if (hasVisibleText(el) && fg) {
            const effBg = effectiveBackground(el);
            if (contrast(fg, effBg) < MIN_CONTRAST) {
                if (theme === 'dark') {
                    el.style.setProperty('color', 'var(--app-text)', 'important');
                } else {
                    // إذا الخلفية غامقة في النهاري، النص يصير فاتح؛ غير ذلك نص داكن واضح.
                    el.style.setProperty('color', luminance(effBg) < 0.35 ? '#F8FAFC' : 'var(--app-text)', 'important');
                }
            }
        }
    }

    function runGuard() {
        scheduled = false;
        const nodes = document.body ? document.body.querySelectorAll('*') : [];
        nodes.forEach(fixElement);
    }

    function scheduleGuard() {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(runGuard);
    }

    document.addEventListener('DOMContentLoaded', scheduleGuard);
    window.addEventListener('load', scheduleGuard);
    document.addEventListener('shown.bs.modal', scheduleGuard);
    document.addEventListener('shown.bs.dropdown', scheduleGuard);

    const themeObserver = new MutationObserver(scheduleGuard);
    themeObserver.observe(ROOT, { attributes: true, attributeFilter: ['data-theme'] });

    document.addEventListener('input', scheduleGuard, true);
    document.addEventListener('change', scheduleGuard, true);

    const bodyReady = setInterval(function () {
        if (!document.body) return;
        clearInterval(bodyReady);
        const domObserver = new MutationObserver(scheduleGuard);
        domObserver.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] });
        scheduleGuard();
    }, 20);
})();
