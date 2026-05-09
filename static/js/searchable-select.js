/**
 * SearchableSelect v3 — قوائم منسدلة قابلة للبحث بتصميم احترافي
 *
 * مبني من الصفر لتوفير أفضل تجربة مستخدم:
 *   - تصميم نظيف ومريح للعين
 *   - بحث ذكي مع ترتيب حسب الصلة
 *   - حركة سلسة عند الفتح والإغلاق
 *   - دعم كامل للوحة المفاتيح
 *   - دعم RTL والعربية
 *   - position:fixed لمنع القص من أي حاوية
 *   - واجهة برمجية: updateOptions(), setValue(), getValue(), open(), close(), destroy()
 *
 * الاستخدام:
 *   تلقائي:  <select> بعدد خيارات ≥ 8 → تحويل تلقائي
 *   يدوي:    <select data-searchable="true">
 *   تعطيل:   <select data-searchable="false">
 *   برمجي:   new SearchableSelect(el, { onChange, renderFn, ... })
 */

(function () {
    'use strict';

    const DEFAULT_THRESHOLD = 8;
    const DEFAULT_MAX_HEIGHT = 280;
    const SEARCH_PLACEHOLDER = 'بحث...';
    const NO_RESULTS_TEXT = 'لا توجد نتائج';

    const instances = [];

    // ─── إزالة التشكيل العربي ───
    function normalizeArabic(str) {
        return str
            .replace(/[\u064B-\u065F\u0670]/g, '')
            .replace(/[\u0622\u0623\u0625]/g, '\u0627')
            .replace(/\u0629/g, '\u0647')
            .replace(/\u0649/g, '\u064A');
    }

    // ─── ترتيب حسب الصلة ───
    function relevanceScore(text, term) {
        const nt = normalizeArabic(text.toLowerCase());
        const nq = normalizeArabic(term.toLowerCase());
        if (nt === nq) return 100;
        if (nt.startsWith(nq)) return 80;
        const i = nt.indexOf(nq);
        if (i === 0) return 70;
        if (i > 0) return 50 + (20 - Math.min(i, 20));
        return 0;
    }

    // ─── تمييز نص البحث ───
    function highlightMatch(text, term) {
        if (!term) return escapeHtml(text);
        const ni = normalizeArabic(text.toLowerCase()).indexOf(normalizeArabic(term.toLowerCase()));
        if (ni === -1) return escapeHtml(text);
        return escapeHtml(text.substring(0, ni))
            + '<mark class="ss-highlight">' + escapeHtml(text.substring(ni, ni + term.length)) + '</mark>'
            + escapeHtml(text.substring(ni + term.length));
    }

    function escapeHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    }

    let _zCounter = 99999;
    function nextZ() { return ++_zCounter; }

    function debounce(fn, ms) {
        let t;
        return function (...a) { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); };
    }

    // ═══════════════════════════════════════
    //  الفئة الرئيسية
    // ═══════════════════════════════════════
    class SearchableSelect {
        constructor(selectEl, userOpts = {}) {
            if (!selectEl || selectEl.tagName !== 'SELECT') return;
            if (selectEl.getAttribute('data-ss-converted') === 'true') return;

            this.selectEl = selectEl;
            this.options = [];
            this.selectedValue = selectEl.value;
            this.isOpen = false;
            this.searchTerm = '';
            this._focusedIdx = -1;
            this._z = nextZ();
            this._destroyed = false;

            this.config = {
                placeholder: selectEl.getAttribute('data-placeholder') || userOpts.placeholder || SEARCH_PLACEHOLDER,
                searchPlaceholder: selectEl.getAttribute('data-search-placeholder') || userOpts.searchPlaceholder || SEARCH_PLACEHOLDER,
                maxHeight: parseInt(selectEl.getAttribute('data-search-max-height')) || userOpts.maxHeight || DEFAULT_MAX_HEIGHT,
                emptyText: userOpts.emptyText || NO_RESULTS_TEXT,
                onChange: userOpts.onChange || null,
                renderFn: userOpts.renderFn || null,
            };

            this.originalId = selectEl.id;
            this.isRequired = selectEl.hasAttribute('required');
            this.isDisabled = selectEl.hasAttribute('disabled');
            this.onchangeHandler = selectEl.getAttribute('onchange') || '';

            this._collectOptions();
            this._build();
            this._bindEvents();
            instances.push(this);
        }

        // ─── جمع الخيارات ───
        _collectOptions() {
            this.options = [];
            this.selectEl.querySelectorAll('option').forEach((opt, i) => {
                this.options.push({
                    value: opt.value,
                    text: opt.textContent.trim(),
                    selected: opt.selected,
                    disabled: opt.disabled,
                    dataFee: opt.dataset.fee || '',
                    dataBalance: opt.dataset.balance || '',
                    _index: i,
                });
            });
            const sel = this.options.find(o => o.selected);
            if (sel) this.selectedValue = sel.value;
        }

        // ─── بناء الواجهة ───
        _build() {
            // إخفاء الأصلي
            this.selectEl.style.display = 'none';
            this.selectEl.setAttribute('data-ss-converted', 'true');

            // الحاوي
            this.container = document.createElement('div');
            this.container.className = 'searchable-select';
            if (this.isDisabled) this.container.classList.add('ss-disabled');
            if (this.originalId) this.container.setAttribute('data-ss-for', this.originalId);
            this.selectEl.parentNode.insertBefore(this.container, this.selectEl.nextSibling);
            this.container.appendChild(this.selectEl);

            // زر التفعيل
            const selectedOpt = this.options.find(o => o.value === this.selectedValue);

            this.display = document.createElement('div');
            this.display.className = 'ss-display';
            if (this.isRequired && !this.selectedValue) this.display.classList.add('ss-empty');
            this.display.setAttribute('tabindex', '0');
            this.display.setAttribute('role', 'combobox');
            this.display.setAttribute('aria-expanded', 'false');
            this.display.setAttribute('aria-haspopup', 'listbox');
            if (this.originalId) this.display.setAttribute('aria-controls', 'ss-lb-' + this.originalId);

            this.displayInner = document.createElement('span');
            this.displayInner.className = selectedOpt ? 'ss-selected-text' : 'ss-placeholder';
            this.displayInner.textContent = selectedOpt ? selectedOpt.text : this.config.placeholder;

            this.clearBtn = document.createElement('button');
            this.clearBtn.type = 'button';
            this.clearBtn.className = 'ss-clear-btn';
            this.clearBtn.setAttribute('tabindex', '-1');
            this.clearBtn.setAttribute('aria-label', 'مسح');
            this.clearBtn.innerHTML = '<i class="fas fa-times"></i>';
            this.clearBtn.style.display = this.selectedValue ? '' : 'none';

            this.arrow = document.createElement('span');
            this.arrow.className = 'ss-arrow';
            this.arrow.innerHTML = '<i class="fas fa-chevron-down"></i>';

            this.display.appendChild(this.displayInner);
            this.display.appendChild(this.clearBtn);
            this.display.appendChild(this.arrow);
            this.container.appendChild(this.display);

            // اللوحة المنسدلة — على body
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'ss-dropdown';
            this.dropdown.setAttribute('role', 'listbox');
            if (this.originalId) this.dropdown.id = 'ss-lb-' + this.originalId;

            // البحث
            this.searchWrap = document.createElement('div');
            this.searchWrap.className = 'ss-search-wrap';

            this.searchInput = document.createElement('input');
            this.searchInput.type = 'text';
            this.searchInput.className = 'ss-search-input';
            this.searchInput.placeholder = this.config.searchPlaceholder;
            this.searchInput.setAttribute('autocomplete', 'off');
            this.searchInput.setAttribute('spellcheck', 'false');

            const searchIcon = document.createElement('i');
            searchIcon.className = 'fas fa-search ss-search-icon';

            this.searchWrap.appendChild(searchIcon);
            this.searchWrap.appendChild(this.searchInput);
            this.dropdown.appendChild(this.searchWrap);

            // الخيارات
            this.optionsList = document.createElement('div');
            this.optionsList.className = 'ss-options';
            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            this.dropdown.appendChild(this.optionsList);

            // لا نتائج
            this.noResults = document.createElement('div');
            this.noResults.className = 'ss-no-results';
            this.noResults.innerHTML = '<i class="fas fa-search ss-no-results-icon"></i><span>' + this.config.emptyText + '</span>';
            this.noResults.style.display = 'none';
            this.dropdown.appendChild(this.noResults);

            // العداد
            this.countFooter = document.createElement('div');
            this.countFooter.className = 'ss-count';
            this.dropdown.appendChild(this.countFooter);

            document.body.appendChild(this.dropdown);
            this._renderOptions();
            this._updateCount();
        }

        // ─── حساب موقع القائمة ───
        _positionDropdown() {
            const rect = this.display.getBoundingClientRect();
            const dd = this.dropdown;
            const vH = window.innerHeight;
            const vW = window.innerWidth;

            if (rect.width === 0 && rect.height === 0) {
                const cr = this.container.getBoundingClientRect();
                if (cr.width > 0) return this._applyPosition(cr);
                dd.style.cssText = 'position:fixed;z-index:' + this._z + ';display:block;top:20%;left:50%;transform:translateX(-50%);width:280px';
                return;
            }
            this._applyPosition(rect);
        }

        _applyPosition(rect) {
            const dd = this.dropdown;
            const vH = window.innerHeight;
            const vW = window.innerWidth;
            const GAP = 6;
            const PAD = 8;

            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            const ddH = dd.offsetHeight > 50 ? dd.offsetHeight : 320;

            const below = vH - rect.bottom - GAP;
            const above = rect.top - GAP;
            let top, left, optMH = this.config.maxHeight;

            if (below >= Math.min(ddH, 200)) {
                top = rect.bottom + GAP;
                if (below < ddH) optMH = Math.max(below - 90, 80);
            } else if (above >= Math.min(ddH, 200)) {
                top = Math.max(rect.top - ddH - GAP, PAD);
                if (above < ddH) optMH = Math.max(above - 90, 80);
            } else {
                top = rect.bottom + GAP;
                optMH = Math.max(vH - top - PAD - 90, 80);
            }

            this.optionsList.style.maxHeight = optMH + 'px';

            const width = Math.max(rect.width, 200);
            left = rect.left;

            // RTL
            if (document.documentElement.dir === 'rtl' || document.documentElement.getAttribute('dir') === 'rtl') {
                left = rect.right - width;
            }
            if (left + width > vW - PAD) left = vW - width - PAD;
            if (left < PAD) left = PAD;

            dd.style.cssText = 'position:fixed;z-index:' + this._z + ';display:block;top:' + top + 'px;left:' + left + 'px;width:' + width + 'px';
        }

        // ─── عرض الخيارات ───
        _renderOptions() {
            this.optionsList.innerHTML = '';
            const term = this.searchTerm;
            const nq = term ? normalizeArabic(term.toLowerCase().trim()) : '';
            let visible = 0;

            // ترتيب بالصلة عند البحث
            let items = this.options.map((o, i) => ({ o, i }));
            if (nq) {
                items.forEach(it => {
                    const nt = normalizeArabic(it.o.text.toLowerCase());
                    const nv = normalizeArabic(it.o.value.toLowerCase());
                    let s = 0;
                    if (nt.includes(nq)) s = relevanceScore(it.o.text, term);
                    else if (nv.includes(nq)) s = relevanceScore(it.o.value, term) * 0.5;
                    if (it.o.value === this.selectedValue && it.o.value) s += 10;
                    it.s = s;
                });
                items.sort((a, b) => {
                    if (!a.o.value && b.o.value) return -1;
                    if (a.o.value && !b.o.value) return 1;
                    return (b.s || 0) - (a.s || 0);
                });
            }

            for (const { o } of items) {
                if (nq) {
                    const nt = normalizeArabic(o.text.toLowerCase());
                    const nv = normalizeArabic(o.value.toLowerCase());
                    if (!nt.includes(nq) && !nv.includes(nq)) continue;
                }
                visible++;

                const el = document.createElement('div');
                el.className = 'ss-option';
                el.setAttribute('data-value', o.value);
                if (o.value === this.selectedValue) {
                    el.classList.add('selected');
                    el.setAttribute('aria-selected', 'true');
                }
                if (o.disabled) el.classList.add('ss-option-disabled');

                el.innerHTML = this.config.renderFn ? this.config.renderFn(o, term) : highlightMatch(o.text, term);

                if (!o.disabled) {
                    el.addEventListener('click', e => { e.stopPropagation(); this._selectOption(o); });
                }
                this.optionsList.appendChild(el);
            }

            this.noResults.style.display = visible === 0 ? '' : 'none';
            this._updateCount(visible);
            this._focusedIdx = -1;
        }

        _updateCount(vis) {
            if (vis === undefined) vis = this.optionsList.querySelectorAll('.ss-option').length;
            const total = this.options.filter(o => o.value).length;
            this.countFooter.textContent = this.searchTerm ? (vis + ' من ' + total) : (total + ' خيار');
        }

        // ─── اختيار ───
        _selectOption(opt) {
            const prev = this.selectedValue;
            this.selectedValue = opt.value;
            this.selectEl.value = opt.value;

            this.displayInner.className = opt.value ? 'ss-selected-text' : 'ss-placeholder';
            this.displayInner.textContent = opt.text || this.config.placeholder;
            this.display.classList.remove('ss-empty');
            this.clearBtn.style.display = opt.value ? '' : 'none';

            this.optionsList.querySelectorAll('.ss-option').forEach(e => {
                e.classList.remove('selected');
                e.removeAttribute('aria-selected');
            });
            const sel = this.optionsList.querySelector('[data-value="' + CSS.escape(opt.value) + '"]');
            if (sel) { sel.classList.add('selected'); sel.setAttribute('aria-selected', 'true'); }

            this.selectEl.dispatchEvent(new Event('change', { bubbles: true }));

            if (this.onchangeHandler) {
                try { new Function('value', this.onchangeHandler)(opt.value); } catch (e) { /* */ }
            }
            if (this.config.onChange) {
                try { this.config.onChange(opt.value, opt, prev); } catch (e) { /* */ }
            }

            this.close();
        }

        // ─── الأحداث ───
        _bindEvents() {
            // نقر على الزر
            this.display.addEventListener('click', e => {
                e.stopPropagation();
                if (this.isDisabled) return;
                if (this.clearBtn.contains(e.target)) { this._clearSelection(); return; }
                this.isOpen ? this.close() : this.open();
            });

            // لوحة مفاتيح على الزر
            this.display.addEventListener('keydown', e => {
                if (this.isDisabled) return;
                switch (e.key) {
                    case 'Enter': case ' ': e.preventDefault(); this.isOpen ? this.close() : this.open(); break;
                    case 'Escape': this.close(); break;
                    case 'ArrowDown': e.preventDefault(); this.isOpen ? this._focusNext() : this.open(); break;
                    case 'ArrowUp': e.preventDefault(); this.isOpen ? this._focusPrev() : this.open(); break;
                    case 'Tab': if (this.isOpen) this.close(); break;
                }
            });

            this.clearBtn.addEventListener('mousedown', e => { e.stopPropagation(); e.preventDefault(); });

            // كتابة البحث
            this.searchInput.addEventListener('input', () => {
                this.searchTerm = this.searchInput.value;
                this._renderOptions();
            });

            // لوحة مفاتيح البحث
            this.searchInput.addEventListener('keydown', e => {
                switch (e.key) {
                    case 'Escape': e.preventDefault(); this.close(); this.display.focus(); break;
                    case 'ArrowDown': e.preventDefault(); this._focusNext(); break;
                    case 'ArrowUp': e.preventDefault(); this._focusPrev(); break;
                    case 'Enter': e.preventDefault(); this._selectFocused(); break;
                    case 'Tab': if (this.isOpen) this.close(); break;
                }
            });

            // منع انتشار الأحداث من القائمة
            this.dropdown.addEventListener('wheel', e => {
                e.preventDefault();
                e.stopPropagation();
                this.optionsList.scrollTop += e.deltaY || 0;
            }, { passive: false });

            this.dropdown.addEventListener('touchmove', e => e.stopPropagation(), { passive: true });
            this.dropdown.addEventListener('mousedown', e => e.stopPropagation());
            this.dropdown.addEventListener('click', e => e.stopPropagation());
            this.dropdown.addEventListener('focusin', e => e.stopPropagation());
            this.container.addEventListener('focusin', e => e.stopPropagation());

            // مراقبة التغييرات
            this._observer = new MutationObserver(() => this._syncFromSelect());
            this._observer.observe(this.selectEl, { childList: true, subtree: true, attributes: true });

            // اعتراض value
            const self = this;
            const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
            if (desc) {
                Object.defineProperty(this.selectEl, 'value', {
                    get() { return desc.get.call(this); },
                    set(v) { desc.set.call(this, v); if (this.getAttribute('data-ss-converted') === 'true') self._syncFromSelect(); },
                    configurable: true
                });
                this._intercepted = true;
            }

            // إغلاق المودال
            const modal = this.container.closest('.modal');
            if (modal) modal.addEventListener('hidden.bs.modal', () => { if (this.isOpen) this.close(); });
        }

        // ─── التنقل ───
        _visOpts() { return this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)'); }

        _focusNext() {
            const o = this._visOpts(); if (!o.length) return;
            this._focusedIdx = Math.min((this._focusedIdx < 0 ? 0 : this._focusedIdx + 1), o.length - 1);
            this._applyFocus(o);
        }

        _focusPrev() {
            const o = this._visOpts(); if (!o.length) return;
            this._focusedIdx = Math.max((this._focusedIdx < 0 ? o.length - 1 : this._focusedIdx - 1), 0);
            this._applyFocus(o);
        }

        _applyFocus(o) {
            o.forEach(e => e.classList.remove('ss-focused'));
            if (this._focusedIdx >= 0 && this._focusedIdx < o.length) {
                o[this._focusedIdx].classList.add('ss-focused');
                o[this._focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'instant' });
            }
        }

        _selectFocused() {
            const o = this._visOpts();
            if (!o.length || this._focusedIdx < 0) return;
            const val = o[this._focusedIdx].getAttribute('data-value');
            const opt = this.options.find(x => x.value === val);
            if (opt) this._selectOption(opt);
        }

        // ─── مسح ───
        _clearSelection() {
            const prev = this.selectedValue;
            this.selectedValue = '';
            this.selectEl.value = '';
            this.displayInner.className = 'ss-placeholder';
            this.displayInner.textContent = this.config.placeholder;
            this.clearBtn.style.display = 'none';
            if (this.isRequired) this.display.classList.add('ss-empty');

            this.optionsList.querySelectorAll('.ss-option.selected').forEach(e => {
                e.classList.remove('selected'); e.removeAttribute('aria-selected');
            });

            this.selectEl.dispatchEvent(new Event('change', { bubbles: true }));
            if (this.onchangeHandler) { try { new Function('value', this.onchangeHandler)(''); } catch (e) { /* */ } }
            if (this.config.onChange) { try { this.config.onChange('', null, prev); } catch (e) { /* */ } }

            if (this.isOpen) { this.searchTerm = ''; this.searchInput.value = ''; this._renderOptions(); }
        }

        // ─── مزامنة ───
        _syncFromSelect() {
            this._collectOptions();
            const sel = this.options.find(o => o.value === this.selectEl.value);
            if (sel) {
                this.selectedValue = sel.value;
                this.displayInner.className = 'ss-selected-text';
                this.displayInner.textContent = sel.text;
                this.clearBtn.style.display = sel.value ? '' : 'none';
            } else {
                this.selectedValue = '';
                this.displayInner.className = 'ss-placeholder';
                this.displayInner.textContent = this.config.placeholder;
                this.clearBtn.style.display = 'none';
            }
            this.display.classList.toggle('ss-empty', this.isRequired && !this.selectedValue);
            this._renderOptions();
            this._updateCount();
        }

        // ─── فتح ───
        open() {
            if (this._destroyed || this.isDisabled) return;
            instances.forEach(i => { if (i !== this && i.isOpen) i.close(); });

            this.isOpen = true;
            this._z = nextZ();
            this.display.classList.add('active');
            this.display.setAttribute('aria-expanded', 'true');

            // مودال؟
            const modal = this.container.closest('.modal');
            if (modal) this.dropdown.classList.add('in-modal');

            this._positionDropdown();
            requestAnimationFrame(() => this._positionDropdown());

            setTimeout(() => { if (!this._destroyed) this.searchInput.focus(); }, 40);

            const selEl = this.optionsList.querySelector('.ss-option.selected');
            if (selEl) setTimeout(() => selEl.scrollIntoView({ block: 'center', behavior: 'instant' }), 80);
        }

        // ─── إغلاق ───
        close() {
            this.isOpen = false;
            this.display.classList.remove('active');
            this.display.setAttribute('aria-expanded', 'false');
            this.dropdown.classList.remove('in-modal');
            this.dropdown.style.display = 'none';

            this.searchTerm = '';
            this.searchInput.value = '';
            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            this._renderOptions();
            this._focusedIdx = -1;
        }

        // ═══ واجهة برمجية ═══
        updateOptions(newOpts) {
            this.selectEl.innerHTML = '';
            this.options = [];
            newOpts.forEach(o => {
                const el = document.createElement('option');
                el.value = o.value; el.textContent = o.text;
                if (o.selected) el.selected = true;
                if (o.disabled) el.disabled = true;
                if (o.dataFee) el.dataset.fee = o.dataFee;
                if (o.dataBalance) el.dataset.balance = o.dataBalance;
                this.selectEl.appendChild(el);
                this.options.push({ value: o.value, text: o.text, selected: o.selected || false, disabled: o.disabled || false, dataFee: o.dataFee || '', dataBalance: o.dataBalance || '', _index: this.options.length });
            });
            this.selectedValue = this.selectEl.value;
            this._syncFromSelect();
        }

        setValue(v) { this.selectEl.value = v; this._syncFromSelect(); }
        getValue() { return this.selectedValue; }
        getSelectedText() { const s = this.options.find(o => o.value === this.selectedValue); return s ? s.text : ''; }

        setDisabled(d) {
            this.isDisabled = d;
            this.container.classList.toggle('ss-disabled', d);
            if (d && this.isOpen) this.close();
        }

        destroy() {
            this._destroyed = true;
            if (this._observer) this._observer.disconnect();
            this.selectEl.style.display = '';
            this.selectEl.removeAttribute('data-ss-converted');
            if (this._intercepted) delete this.selectEl.value;
            if (this.container.parentNode) this.container.parentNode.insertBefore(this.selectEl, this.container);
            this.container.remove();
            this.dropdown.remove();
            const i = instances.indexOf(this);
            if (i > -1) instances.splice(i, 1);
        }
    }

    // ═══ أحداث عامة ═══
    document.addEventListener('click', e => {
        instances.forEach(i => {
            if (i.isOpen && !i.display.contains(e.target) && !i.dropdown.contains(e.target)) i.close();
        });
    });

    document.addEventListener('wheel', e => {
        for (const i of instances) {
            if (i.isOpen && i.dropdown.contains(e.target)) {
                e.preventDefault();
                e.stopPropagation();
                i.optionsList.scrollTop += e.deltaY || 0;
                return;
            }
        }
    }, { passive: false, capture: true });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            const o = instances.find(i => i.isOpen);
            if (o) { o.close(); o.display.focus(); }
        }
    });

    const reposition = debounce(() => instances.forEach(i => { if (i.isOpen) i._positionDropdown(); }), 16);
    window.addEventListener('scroll', e => {
        instances.forEach(i => { if (i.isOpen && !i.dropdown.contains(e.target)) i._positionDropdown(); });
    }, true);
    window.addEventListener('resize', reposition);

    // ═══ تهيئة تلقائية ═══
    function initAll() {
        document.querySelectorAll('select').forEach(sel => {
            if (sel.getAttribute('data-ss-converted') === 'true') return;
            if (sel.getAttribute('data-searchable') === 'false') return;
            if (sel.closest('.searchable-select')) return;
            const count = sel.querySelectorAll('option').length;
            const threshold = parseInt(sel.getAttribute('data-search-threshold')) || DEFAULT_THRESHOLD;
            if (sel.getAttribute('data-searchable') !== 'true' && count < threshold) return;
            try { new SearchableSelect(sel); } catch (e) { console.warn('SS init error:', e); }
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
    else initAll();

    // ═══ تصدير ═══
    window.SearchableSelect = SearchableSelect;
    window.initSearchableSelects = initAll;

    window.makeSearchableSelect = function (id, opts = {}) {
        const sel = document.getElementById(id);
        if (!sel) return null;
        const inst = new SearchableSelect(sel, { onChange: opts.onChange, placeholder: opts.placeholder, searchPlaceholder: opts.searchPlaceholder });
        return {
            setValue: v => inst.setValue(v),
            getValue: () => inst.getValue(),
            refresh: () => inst._syncFromSelect(),
            clear: () => inst._clearSelection(),
            destroy: () => inst.destroy(),
            open: () => inst.open(),
            close: () => inst.close(),
            updateOptions: o => inst.updateOptions(o),
            _instance: inst,
        };
    };
})();
