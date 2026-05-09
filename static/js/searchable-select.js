/**
 * SearchableSelect — محوّل تلقائي لعناصر <select> إلى قوائم منسدلة قابلة للبحث
 *
 * الإصلاحات:
 *   - القائمة تُضاف إلى document.body بـ position:fixed فلا تُقطع من أي حاوية
 *   - حساب الموقع ديناميكياً مع مراعاة RTL والشاشة
 *   - التمرير السلس يعمل داخل القائمة بدون تضارب مع المودال
 *
 * الاستخدام:
 *   1) تلقائي: <select> بعدد خيارات > 8 → يتم التحويل تلقائياً
 *   2) يدوي: <select data-searchable="true"> → يتم التحويل بغض النظر عن عدد الخيارات
 *   3) تعطيل: <select data-searchable="false"> → لا يتم التحويل أبداً
 */

(function () {
    'use strict';

    const DEFAULT_THRESHOLD = 8;
    const DEFAULT_MAX_HEIGHT = 280;
    const SEARCH_PLACEHOLDER = 'بحث...';

    // Track all instances for global event handling
    const instances = [];

    class SearchableSelect {
        constructor(selectEl) {
            this.selectEl = selectEl;
            this.options = [];
            this.selectedValue = selectEl.value;
            this.isOpen = false;
            this.searchTerm = '';
            this._focusedIdx = -1;

            // Read data attributes
            this.placeholder = selectEl.getAttribute('data-search-placeholder') || SEARCH_PLACEHOLDER;
            this.maxHeight = parseInt(selectEl.getAttribute('data-search-max-height')) || DEFAULT_MAX_HEIGHT;

            // Preserve original attributes
            this.originalClasses = selectEl.className;
            this.originalId = selectEl.id;
            this.originalName = selectEl.name;
            this.isRequired = selectEl.hasAttribute('required');
            this.isDisabled = selectEl.hasAttribute('disabled');
            this.onchangeHandler = selectEl.getAttribute('onchange') || '';

            this._collectOptions();
            this._build();
            this._bindEvents();

            instances.push(this);
        }

        _collectOptions() {
            const opts = this.selectEl.querySelectorAll('option');
            this.options = [];
            opts.forEach(opt => {
                this.options.push({
                    value: opt.value,
                    text: opt.textContent.trim(),
                    selected: opt.selected,
                    disabled: opt.disabled
                });
            });
            const sel = this.options.find(o => o.selected);
            if (sel) this.selectedValue = sel.value;
        }

        _build() {
            // Hide original select
            this.selectEl.style.display = 'none';
            this.selectEl.setAttribute('data-ss-converted', 'true');

            // Container (inline, holds the trigger only)
            this.container = document.createElement('div');
            this.container.className = 'searchable-select';
            if (this.isDisabled) this.container.classList.add('ss-disabled');

            // Insert after select
            this.selectEl.parentNode.insertBefore(this.container, this.selectEl.nextSibling);
            this.container.appendChild(this.selectEl);

            // Display trigger
            this.display = document.createElement('div');
            this.display.className = 'ss-display';
            if (this.isRequired && !this.selectedValue) this.display.classList.add('ss-empty');
            this.display.setAttribute('tabindex', '0');
            this.display.setAttribute('role', 'combobox');
            this.display.setAttribute('aria-expanded', 'false');
            this.display.setAttribute('aria-haspopup', 'listbox');

            const selectedOpt = this.options.find(o => o.value === this.selectedValue);
            const displayText = selectedOpt ? selectedOpt.text : (this.selectEl.getAttribute('data-placeholder') || this.placeholder);

            this.displayInner = document.createElement('span');
            this.displayInner.className = selectedOpt ? 'ss-selected-text' : 'ss-placeholder';
            this.displayInner.textContent = displayText;

            this.arrow = document.createElement('i');
            this.arrow.className = 'fas fa-chevron-down ss-arrow';

            this.display.appendChild(this.displayInner);
            this.display.appendChild(this.arrow);
            this.container.appendChild(this.display);

            // ===== Dropdown panel — appended to document.body =====
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'ss-dropdown ss-dropdown-fixed';
            this.dropdown.setAttribute('role', 'listbox');

            // Search input
            this.searchWrap = document.createElement('div');
            this.searchWrap.className = 'ss-search-wrap';

            this.searchInput = document.createElement('input');
            this.searchInput.type = 'text';
            this.searchInput.className = 'ss-search-input';
            this.searchInput.placeholder = this.placeholder;
            this.searchInput.setAttribute('autocomplete', 'off');
            this.searchInput.setAttribute('aria-label', 'بحث في الخيارات');

            this.searchWrap.appendChild(this.searchInput);
            this.dropdown.appendChild(this.searchWrap);

            // Options list
            this.optionsList = document.createElement('div');
            this.optionsList.className = 'ss-options';
            this.optionsList.style.maxHeight = this.maxHeight + 'px';

            // No results
            this.noResults = document.createElement('div');
            this.noResults.className = 'ss-no-results';
            this.noResults.textContent = 'لا توجد نتائج';
            this.noResults.style.display = 'none';

            // Count footer
            this.countFooter = document.createElement('div');
            this.countFooter.className = 'ss-count';

            this.dropdown.appendChild(this.optionsList);
            this.dropdown.appendChild(this.noResults);
            this.dropdown.appendChild(this.countFooter);

            // Append to body so it's never clipped by overflow:hidden
            document.body.appendChild(this.dropdown);

            // Render options
            this._renderOptions();
            this._updateCount();
        }

        _positionDropdown() {
            const rect = this.display.getBoundingClientRect();
            const dd = this.dropdown;
            const viewH = window.innerHeight;
            const viewW = window.innerWidth;

            // Estimate dropdown height
            const ddHeight = Math.min(dd.scrollHeight, this.maxHeight + 120) || 300;

            // Position below or above
            let top, left, width;

            if (rect.bottom + ddHeight + 8 > viewH) {
                // Not enough room below → open above
                top = rect.top - ddHeight - 4;
                if (top < 4) top = 4; // Fallback if also no room above
            } else {
                top = rect.bottom + 4;
            }

            width = Math.max(rect.width, 200);
            left = rect.left;

            // Prevent going off-screen right
            if (left + width > viewW - 8) {
                left = viewW - width - 8;
            }
            // Prevent going off-screen left
            if (left < 8) {
                left = 8;
            }

            dd.style.top = top + 'px';
            dd.style.left = left + 'px';
            dd.style.width = width + 'px';
        }

        _renderOptions() {
            this.optionsList.innerHTML = '';
            const term = this.searchTerm.toLowerCase().trim();
            let visibleCount = 0;

            this.options.forEach((opt, idx) => {
                if (term && !opt.text.toLowerCase().includes(term) && !opt.value.toLowerCase().includes(term)) {
                    return;
                }
                visibleCount++;

                const optEl = document.createElement('div');
                optEl.className = 'ss-option';
                optEl.setAttribute('role', 'option');
                optEl.setAttribute('data-value', opt.value);
                optEl.setAttribute('data-index', idx);

                if (opt.value === this.selectedValue) {
                    optEl.classList.add('selected');
                    optEl.setAttribute('aria-selected', 'true');
                }

                if (opt.disabled) {
                    optEl.classList.add('ss-option-disabled');
                    optEl.style.opacity = '0.5';
                    optEl.style.cursor = 'not-allowed';
                }

                optEl.textContent = opt.text;

                if (!opt.disabled) {
                    optEl.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this._selectOption(opt);
                    });
                }

                this.optionsList.appendChild(optEl);
            });

            this.noResults.style.display = visibleCount === 0 ? 'block' : 'none';
            this._updateCount(visibleCount);
        }

        _updateCount(visibleCount) {
            if (visibleCount === undefined) {
                visibleCount = this.optionsList.querySelectorAll('.ss-option').length;
            }
            const total = this.options.length;
            if (this.searchTerm) {
                this.countFooter.textContent = visibleCount + ' من ' + total;
            } else {
                this.countFooter.textContent = total + ' خيار';
            }
        }

        _selectOption(opt) {
            this.selectedValue = opt.value;
            this.selectEl.value = opt.value;

            // Update display
            this.displayInner.className = 'ss-selected-text';
            this.displayInner.textContent = opt.text;
            this.display.classList.remove('ss-empty');

            // Mark selected in list
            this.optionsList.querySelectorAll('.ss-option').forEach(el => {
                el.classList.remove('selected');
                el.setAttribute('aria-selected', 'false');
            });
            const selEl = this.optionsList.querySelector(`[data-value="${CSS.escape(opt.value)}"]`);
            if (selEl) {
                selEl.classList.add('selected');
                selEl.setAttribute('aria-selected', 'true');
            }

            // Fire change event on original select
            const event = new Event('change', { bubbles: true });
            this.selectEl.dispatchEvent(event);

            // Call onchange handler if set
            if (this.onchangeHandler) {
                try {
                    new Function('value', this.onchangeHandler)(opt.value);
                } catch (e) {
                    console.warn('SearchableSelect onchange error:', e);
                }
            }

            this.close();
        }

        _bindEvents() {
            // Toggle on click
            this.display.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.isDisabled) return;
                this.isOpen ? this.close() : this.open();
            });

            // Keyboard support on trigger
            this.display.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (this.isDisabled) return;
                    this.isOpen ? this.close() : this.open();
                } else if (e.key === 'Escape') {
                    this.close();
                }
            });

            // Search input
            this.searchInput.addEventListener('input', () => {
                this.searchTerm = this.searchInput.value;
                this._renderOptions();
            });

            this.searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this.close();
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this._focusNextOption();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this._focusPrevOption();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    this._selectFocusedOption();
                }
            });

            // Prevent scroll propagation from dropdown to modal
            this.dropdown.addEventListener('wheel', (e) => {
                e.stopPropagation();
            }, { passive: true });

            this.dropdown.addEventListener('touchmove', (e) => {
                e.stopPropagation();
            }, { passive: true });

            // Prevent modal close when interacting with dropdown
            this.dropdown.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });

            this.dropdown.addEventListener('click', (e) => {
                e.stopPropagation();
            });

            // Watch for child list changes (innerHTML, appendChild, etc.)
            const childObserver = new MutationObserver(() => {
                this._syncFromSelect();
            });
            childObserver.observe(this.selectEl, { childList: true, subtree: true });

            // Intercept .value property setter on the original select
            const self = this;
            const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
            if (originalDescriptor) {
                Object.defineProperty(this.selectEl, 'value', {
                    get() { return originalDescriptor.get.call(this); },
                    set(newValue) {
                        originalDescriptor.set.call(this, newValue);
                        if (this.getAttribute('data-ss-converted') === 'true') {
                            self._syncFromSelect();
                        }
                    },
                    configurable: true
                });
                this._valueInterceptor = true;
            }
        }

        _focusNextOption() {
            const opts = this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)');
            if (!opts.length) return;
            if (!this._focusedIdx && this._focusedIdx !== 0) this._focusedIdx = -1;
            this._focusedIdx = Math.min(this._focusedIdx + 1, opts.length - 1);
            opts.forEach(o => o.classList.remove('ss-focused'));
            opts[this._focusedIdx].classList.add('ss-focused');
            opts[this._focusedIdx].scrollIntoView({ block: 'nearest' });
        }

        _focusPrevOption() {
            const opts = this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)');
            if (!opts.length) return;
            if (!this._focusedIdx && this._focusedIdx !== 0) this._focusedIdx = opts.length;
            this._focusedIdx = Math.max(this._focusedIdx - 1, 0);
            opts.forEach(o => o.classList.remove('ss-focused'));
            opts[this._focusedIdx].classList.add('ss-focused');
            opts[this._focusedIdx].scrollIntoView({ block: 'nearest' });
        }

        _selectFocusedOption() {
            const opts = this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)');
            if (!opts.length || this._focusedIdx < 0) return;
            const el = opts[this._focusedIdx];
            const value = el.getAttribute('data-value');
            const opt = this.options.find(o => o.value === value);
            if (opt) this._selectOption(opt);
        }

        _syncFromSelect() {
            this._collectOptions();
            const sel = this.options.find(o => o.value === this.selectEl.value);
            if (sel) {
                this.selectedValue = sel.value;
                this.displayInner.className = 'ss-selected-text';
                this.displayInner.textContent = sel.text;
            } else {
                this.selectedValue = '';
                this.displayInner.className = 'ss-placeholder';
                this.displayInner.textContent = this.selectEl.getAttribute('data-placeholder') || this.placeholder;
            }
            this._renderOptions();
            this._updateCount();
        }

        open() {
            this.isOpen = true;
            this.dropdown.classList.add('show');
            this.display.classList.add('active');
            this.display.setAttribute('aria-expanded', 'true');

            // Check if inside a modal
            const modal = this.container.closest('.modal');
            if (modal) {
                this.dropdown.classList.add('in-modal');
            }

            // Position dropdown relative to trigger
            this._positionDropdown();

            // Focus search
            setTimeout(() => {
                this.searchInput.focus();
            }, 60);

            // Scroll to selected
            const selEl = this.optionsList.querySelector('.ss-option.selected');
            if (selEl) {
                setTimeout(() => {
                    selEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
                }, 120);
            }
        }

        close() {
            this.isOpen = false;
            this.dropdown.classList.remove('show');
            this.dropdown.classList.remove('in-modal');
            this.display.classList.remove('active');
            this.display.setAttribute('aria-expanded', 'false');

            // Reset search
            this.searchTerm = '';
            this.searchInput.value = '';
            this._renderOptions();
            this._focusedIdx = -1;
        }

        /** Update options dynamically */
        updateOptions(newOptions) {
            this.selectEl.innerHTML = '';
            this.options = [];

            newOptions.forEach(opt => {
                const optionEl = document.createElement('option');
                optionEl.value = opt.value;
                optionEl.textContent = opt.text;
                if (opt.selected) optionEl.selected = true;
                if (opt.disabled) optionEl.disabled = true;
                this.selectEl.appendChild(optionEl);

                this.options.push({
                    value: opt.value,
                    text: opt.text,
                    selected: opt.selected || false,
                    disabled: opt.disabled || false
                });
            });

            this.selectedValue = this.selectEl.value;
            const sel = this.options.find(o => o.selected);
            if (sel) {
                this.displayInner.className = 'ss-selected-text';
                this.displayInner.textContent = sel.text;
            } else {
                this.displayInner.className = 'ss-placeholder';
                this.displayInner.textContent = this.selectEl.getAttribute('data-placeholder') || this.placeholder;
            }
            this._renderOptions();
            this._updateCount();
        }

        destroy() {
            this.selectEl.style.display = '';
            this.selectEl.removeAttribute('data-ss-converted');
            this.container.parentNode.insertBefore(this.selectEl, this.container);
            this.container.remove();
            this.dropdown.remove();
            const idx = instances.indexOf(this);
            if (idx > -1) instances.splice(idx, 1);
        }
    }

    // ===== Global event handlers =====

    // Close all on outside click
    document.addEventListener('click', (e) => {
        instances.forEach(inst => {
            if (inst.isOpen && !inst.display.contains(e.target) && !inst.dropdown.contains(e.target)) {
                inst.close();
            }
        });
    });

    // Reposition on scroll/resize
    function repositionAll() {
        instances.forEach(inst => {
            if (inst.isOpen) inst._positionDropdown();
        });
    }
    window.addEventListener('scroll', repositionAll, true); // capture phase to catch modal scrolls
    window.addEventListener('resize', repositionAll);

    // ===== Auto-initialization =====
    function initAll() {
        const selects = document.querySelectorAll('select');

        selects.forEach(select => {
            if (select.getAttribute('data-ss-converted') === 'true') return;
            if (select.getAttribute('data-searchable') === 'false') return;
            if (select.closest('.searchable-select')) return;

            const optionCount = select.querySelectorAll('option').length;
            const threshold = parseInt(select.getAttribute('data-search-threshold')) || DEFAULT_THRESHOLD;
            const forceSearchable = select.getAttribute('data-searchable') === 'true';

            if (!forceSearchable && optionCount < threshold) return;

            try {
                new SearchableSelect(select);
            } catch (e) {
                console.warn('SearchableSelect init error:', e);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    window.SearchableSelect = SearchableSelect;
    window.initSearchableSelects = initAll;

})();
