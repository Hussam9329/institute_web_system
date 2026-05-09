/**
 * SearchableSelect — محوّل تلقائي لعناصر <select> إلى قوائم منسدلة قابلة للبحث
 *
 * التحويل التلقائي: يبحث عن جميع عناصر <select> التي تحتوي على
 * data-searchable="true" أو التي يتجاوز عدد خياراتها data-search-threshold (افتراضي: 8)
 * ويحوّلها إلى قائمة منسدلة احترافية قابلة للبحث مع تمرير سلس.
 *
 * الاستخدام:
 *   1) تلقائي: <select> بعدد خيارات > 8 → يتم التحويل تلقائياً
 *   2) يدوي: <select data-searchable="true"> → يتم التحويل بغض النظر عن عدد الخيارات
 *   3) تعطيل: <select data-searchable="false"> → لا يتم التحويل أبداً
 *
 * خيارات data attributes:
 *   data-searchable="true|false"  — فرض التحويل أو تعطيله
 *   data-search-placeholder="بحث..." — نص حقل البحث
 *   data-search-threshold="8"  — الحد الأدنى لعدد الخيارات للتحويل التلقائي
 *   data-search-max-height="280"  — أقصى ارتفاع للقائمة المنسدلة (px)
 */

(function () {
    'use strict';

    const DEFAULT_THRESHOLD = 8;
    const DEFAULT_MAX_HEIGHT = 280;
    const SEARCH_PLACEHOLDER = 'بحث...';

    class SearchableSelect {
        constructor(selectEl) {
            this.selectEl = selectEl;
            this.options = [];
            this.selectedValue = selectEl.value;
            this.isOpen = false;
            this.searchTerm = '';

            // Read data attributes
            this.placeholder = selectEl.getAttribute('data-search-placeholder') || SEARCH_PLACEHOLDER;
            this.maxHeight = parseInt(selectEl.getAttribute('data-search-max-height')) || DEFAULT_MAX_HEIGHT;

            // Preserve original classes and attributes
            this.originalClasses = selectEl.className;
            this.originalId = selectEl.id;
            this.originalName = selectEl.name;
            this.isRequired = selectEl.hasAttribute('required');
            this.isDisabled = selectEl.hasAttribute('disabled');
            this.onchangeHandler = selectEl.getAttribute('onchange') || '';

            this._collectOptions();
            this._build();
            this._bindEvents();
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
            // Track selected
            const sel = this.options.find(o => o.selected);
            if (sel) this.selectedValue = sel.value;
        }

        _build() {
            // Hide original select
            this.selectEl.style.display = 'none';
            this.selectEl.setAttribute('data-ss-converted', 'true');

            // Create container
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

            // Dropdown panel
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'ss-dropdown';
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

            // No results message
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
            this.container.appendChild(this.dropdown);

            // Render options
            this._renderOptions();
            this._updateCount();
        }

        _renderOptions() {
            this.optionsList.innerHTML = '';
            const term = this.searchTerm.toLowerCase().trim();
            let visibleCount = 0;

            this.options.forEach((opt, idx) => {
                // Filter by search term
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

            // Mark selected
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

            // Keyboard support
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

            // Close on outside click
            document.addEventListener('click', (e) => {
                if (!this.container.contains(e.target)) {
                    this.close();
                }
            });

            // Sync with original select if value changes externally
            const observer = new MutationObserver(() => {
                if (this.selectEl.value !== this.selectedValue) {
                    this._syncFromSelect();
                }
            });
            observer.observe(this.selectEl, { attributes: true, attributeFilter: ['value'] });

            // Watch for child list changes (innerHTML, appendChild, etc.)
            const childObserver = new MutationObserver(() => {
                this._syncFromSelect();
            });
            childObserver.observe(this.selectEl, { childList: true, subtree: true });

            // Intercept .value property setter on the original select
            // This ensures programmatic selectEl.value = x updates the UI
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
            opts[this._focusedIdx].classList.add('ss-focused');
            opts.forEach((o, i) => { if (i !== this._focusedIdx) o.classList.remove('ss-focused'); });
            opts[this._focusedIdx].scrollIntoView({ block: 'nearest' });
        }

        _focusPrevOption() {
            const opts = this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)');
            if (!opts.length) return;
            if (!this._focusedIdx && this._focusedIdx !== 0) this._focusedIdx = opts.length;
            this._focusedIdx = Math.max(this._focusedIdx - 1, 0);
            opts[this._focusedIdx].classList.add('ss-focused');
            opts.forEach((o, i) => { if (i !== this._focusedIdx) o.classList.remove('ss-focused'); });
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

            // Focus search
            setTimeout(() => {
                this.searchInput.focus();
            }, 50);

            // Scroll to selected
            const selEl = this.optionsList.querySelector('.ss-option.selected');
            if (selEl) {
                setTimeout(() => {
                    selEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
                }, 100);
            }

            // If inside a modal, adjust z-index
            const modal = this.container.closest('.modal');
            if (modal) {
                this.dropdown.style.zIndex = '1060';
            }
        }

        close() {
            this.isOpen = false;
            this.dropdown.classList.remove('show');
            this.display.classList.remove('active');
            this.display.setAttribute('aria-expanded', 'false');

            // Reset search
            this.searchTerm = '';
            this.searchInput.value = '';
            this._renderOptions();
            this._focusedIdx = -1;
        }

        /** Update options dynamically (e.g., when teacher list changes) */
        updateOptions(newOptions) {
            // Clear existing
            this.selectEl.innerHTML = '';
            this.options = [];

            // Add new options
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

            // Re-render
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

        /** Destroy and restore original select */
        destroy() {
            this.selectEl.style.display = '';
            this.selectEl.removeAttribute('data-ss-converted');
            this.container.parentNode.insertBefore(this.selectEl, this.container);
            this.container.remove();
        }
    }

    // ===== Auto-initialization =====
    function initAll() {
        const selects = document.querySelectorAll('select');

        selects.forEach(select => {
            // Skip if already converted
            if (select.getAttribute('data-ss-converted') === 'true') return;

            // Skip if explicitly disabled
            if (select.getAttribute('data-searchable') === 'false') return;

            // Check if inside a searchable-select container already
            if (select.closest('.searchable-select')) return;

            // Skip very small selects (< 2 options, like empty placeholder-only)
            const optionCount = select.querySelectorAll('option').length;

            // Check threshold
            const threshold = parseInt(select.getAttribute('data-search-threshold')) || DEFAULT_THRESHOLD;
            const forceSearchable = select.getAttribute('data-searchable') === 'true';

            if (!forceSearchable && optionCount < threshold) return;

            // Convert!
            try {
                new SearchableSelect(select);
            } catch (e) {
                console.warn('SearchableSelect init error:', e);
            }
        });
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    // Also run when new content is loaded (e.g., HTMX, dynamic forms)
    window.SearchableSelect = SearchableSelect;
    window.initSearchableSelects = initAll;

})();
