/**
 * SearchableSelect v2 — محوّل موحّد لعناصر <select> إلى قوائم منسدلة قابلة للبحث
 *
 * الميزات:
 *   - تصميم موحّد يحل محل جميع الأنظمة السابقة
 *   - القائمة تُضاف إلى document.body بـ position:fixed فلا تُقطع من أي حاوية
 *   - حساب الموقع ديناميكياً مع مراعاة RTL والشاشة
 *   - تمييز نص البحث في النتائج (Highlight)
 *   - دعم كامل للوحة المفاتيح (Arrow, Enter, Escape, Tab)
 *   - دعم ARIA للإتاحة
 *   - تمرير سلس يعمل داخل القائمة بدون تضارب مع المودال
 *   - واجهة برمجية موحّدة: updateOptions(), setValue(), getValue(), open(), close(), destroy()
 *   - دعم renderFn لعرض مخصص للعناصر (أيقونات، نصوص فرعية)
 *   - دعم onChange callback
 *
 * الاستخدام:
 *   1) تلقائي: <select> بعدد خيارات ≥ threshold → يتم التحويل تلقائياً
 *   2) يدوي: <select data-searchable="true"> → يتم التحويل بغض النظر عن عدد الخيارات
 *   3) تعطيل: <select data-searchable="false"> → لا يتم التحويل أبداً
 *   4) برمجي: new SearchableSelect(el, { onChange, renderFn, ... })
 *
 * Data Attributes:
 *   data-searchable="true|false"       — تفعيل/تعطيل التحويل
 *   data-search-placeholder="..."      — نص خانة البحث
 *   data-search-max-height="280"       — أقصى ارتفاع لقائمة الخيارات (بكسل)
 *   data-search-threshold="8"          — حد عدد الخيارات للتحويل التلقائي
 *   data-placeholder="..."             — نص العرض عند عدم الاختيار
 */

(function () {
    'use strict';

    // ===== الثوابت =====
    const DEFAULT_THRESHOLD = 8;
    const DEFAULT_MAX_HEIGHT = 280;
    const SEARCH_PLACEHOLDER = 'بحث...';
    const NO_RESULTS_TEXT = 'لا توجد نتائج';
    const ANIMATION_DURATION = 180; // ms — يتطابق مع CSS transition

    // ===== سجلّ جميع النسخ =====
    const instances = [];

    // ===== إزالة التشكيل العربي للبحث =====
    function normalizeArabic(str) {
        return str
            .replace(/[\u064B-\u065F\u0670]/g, '') // حركات (فتحة، ضمة، كسرة، تنوين...)
            .replace(/[\u0622\u0623\u0625]/g, '\u0627') // أ، إ، آ ← ا
            .replace(/\u0629/g, '\u0647')               // ة ← ه
            .replace(/\u0649/g, '\u064A');              // ى ← ي
    }

    // ===== تمييز نص البحث =====
    function highlightMatch(text, term) {
        if (!term) return escapeHtml(text);
        const normalizedText = normalizeArabic(text.toLowerCase());
        const normalizedTerm = normalizeArabic(term.toLowerCase());

        const idx = normalizedText.indexOf(normalizedTerm);
        if (idx === -1) return escapeHtml(text);

        const before = text.substring(0, idx);
        const match = text.substring(idx, idx + term.length);
        const after = text.substring(idx + term.length);

        return escapeHtml(before) + '<mark class="ss-highlight">' + escapeHtml(match) + '</mark>' + escapeHtml(after);
    }

    // ===== تحويل HTML =====
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ===== إدارة الـ z-index =====
    let _zCounter = 99999;
    function nextZIndex() {
        return ++_zCounter;
    }

    // ===== Debounce =====
    function debounce(fn, delay) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // ==========================================================
    //  الفئة الرئيسية
    // ==========================================================
    class SearchableSelect {
        /**
         * @param {HTMLSelectElement} selectEl — عنصر الـ select الأصلي
         * @param {Object} [userOptions={}]
         * @param {Function} [userOptions.onChange]  — callback عند تغيير القيمة
         * @param {Function} [userOptions.renderFn]  — دالة عرض مخصّصة (opt) => HTML string
         * @param {string}   [userOptions.placeholder]
         * @param {string}   [userOptions.searchPlaceholder]
         * @param {number}   [userOptions.maxHeight]
         * @param {string}   [userOptions.emptyText]
         */
        constructor(selectEl, userOptions = {}) {
            if (!selectEl || selectEl.tagName !== 'SELECT') {
                console.warn('SearchableSelect: عنصر غير صالح', selectEl);
                return;
            }
            if (selectEl.getAttribute('data-ss-converted') === 'true') return;

            this.selectEl = selectEl;
            this.options = [];
            this.selectedValue = selectEl.value;
            this.isOpen = false;
            this.searchTerm = '';
            this._focusedIdx = -1;
            this._currentZIndex = nextZIndex();
            this._destroyed = false;

            // خيارات مدمجة مع data attributes
            this.config = {
                placeholder: selectEl.getAttribute('data-placeholder') || userOptions.placeholder || SEARCH_PLACEHOLDER,
                searchPlaceholder: selectEl.getAttribute('data-search-placeholder') || userOptions.searchPlaceholder || SEARCH_PLACEHOLDER,
                maxHeight: parseInt(selectEl.getAttribute('data-search-max-height')) || userOptions.maxHeight || DEFAULT_MAX_HEIGHT,
                emptyText: userOptions.emptyText || NO_RESULTS_TEXT,
                onChange: userOptions.onChange || null,
                renderFn: userOptions.renderFn || null,
            };

            // الحفاظ على الخصائص الأصلية
            this.originalClasses = selectEl.className;
            this.originalId = selectEl.id;
            this.originalName = selectEl.name;
            this.isRequired = selectEl.hasAttribute('required');
            this.isDisabled = selectEl.hasAttribute('disabled');
            this.onchangeHandler = selectEl.getAttribute('onchange') || '';

            // بناء الواجهة
            this._collectOptions();
            this._build();
            this._bindEvents();

            instances.push(this);
        }

        // ===== جمع الخيارات من الـ select =====
        _collectOptions() {
            const opts = this.selectEl.querySelectorAll('option');
            this.options = [];
            opts.forEach((opt, idx) => {
                this.options.push({
                    value: opt.value,
                    text: opt.textContent.trim(),
                    selected: opt.selected,
                    disabled: opt.disabled,
                    // بيانات إضافية من data attributes
                    dataFee: opt.dataset.fee || '',
                    dataBalance: opt.dataset.balance || '',
                    _index: idx,
                });
            });
            const sel = this.options.find(o => o.selected);
            if (sel) this.selectedValue = sel.value;
        }

        // ===== بناء DOM =====
        _build() {
            // إخفاء الـ select الأصلي
            this.selectEl.style.display = 'none';
            this.selectEl.setAttribute('data-ss-converted', 'true');

            // ─── الحاوي (inline, يحمل زر التفعيل فقط) ───
            this.container = document.createElement('div');
            this.container.className = 'searchable-select';
            if (this.isDisabled) this.container.classList.add('ss-disabled');
            if (this.originalId) this.container.setAttribute('data-ss-for', this.originalId);

            // إدراج بعد الـ select
            this.selectEl.parentNode.insertBefore(this.container, this.selectEl.nextSibling);
            this.container.appendChild(this.selectEl);

            // ─── زر التفعيل (display trigger) ───
            this.display = document.createElement('div');
            this.display.className = 'ss-display';
            if (this.isRequired && !this.selectedValue) this.display.classList.add('ss-empty');
            this.display.setAttribute('tabindex', '0');
            this.display.setAttribute('role', 'combobox');
            this.display.setAttribute('aria-expanded', 'false');
            this.display.setAttribute('aria-haspopup', 'listbox');
            this.display.setAttribute('aria-autocomplete', 'list');
            if (this.originalId) this.display.setAttribute('aria-controls', 'ss-listbox-' + this.originalId);

            const selectedOpt = this.options.find(o => o.value === this.selectedValue);
            const displayText = selectedOpt ? selectedOpt.text : this.config.placeholder;

            this.displayInner = document.createElement('span');
            this.displayInner.className = selectedOpt ? 'ss-selected-text' : 'ss-placeholder';
            this.displayInner.textContent = displayText;

            this.arrow = document.createElement('i');
            this.arrow.className = 'fas fa-chevron-down ss-arrow';

            // أيقونة مسح الاختيار (clear button)
            this.clearBtn = document.createElement('button');
            this.clearBtn.type = 'button';
            this.clearBtn.className = 'ss-clear-btn';
            this.clearBtn.setAttribute('tabindex', '-1');
            this.clearBtn.setAttribute('aria-label', 'مسح الاختيار');
            this.clearBtn.innerHTML = '<i class="fas fa-times"></i>';
            this.clearBtn.style.display = this.selectedValue ? 'flex' : 'none';

            this.display.appendChild(this.displayInner);
            this.display.appendChild(this.clearBtn);
            this.display.appendChild(this.arrow);
            this.container.appendChild(this.display);

            // ─── اللوحة المنسدلة — تُضاف إلى document.body ───
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'ss-dropdown ss-dropdown-fixed';
            this.dropdown.setAttribute('role', 'listbox');
            this.dropdown.setAttribute('aria-label', 'قائمة الخيارات');
            if (this.originalId) this.dropdown.id = 'ss-listbox-' + this.originalId;

            // ─── شريط البحث ───
            this.searchWrap = document.createElement('div');
            this.searchWrap.className = 'ss-search-wrap';

            const searchIcon = document.createElement('i');
            searchIcon.className = 'fas fa-search ss-search-icon';

            this.searchInput = document.createElement('input');
            this.searchInput.type = 'text';
            this.searchInput.className = 'ss-search-input';
            this.searchInput.placeholder = this.config.searchPlaceholder;
            this.searchInput.setAttribute('autocomplete', 'off');
            this.searchInput.setAttribute('aria-label', 'بحث في الخيارات');
            this.searchInput.setAttribute('spellcheck', 'false');

            this.searchWrap.appendChild(searchIcon);
            this.searchWrap.appendChild(this.searchInput);
            this.dropdown.appendChild(this.searchWrap);

            // ─── قائمة الخيارات ───
            this.optionsList = document.createElement('div');
            this.optionsList.className = 'ss-options';
            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            this.optionsList.setAttribute('role', 'group');

            // ─── لا توجد نتائج ───
            this.noResults = document.createElement('div');
            this.noResults.className = 'ss-no-results';
            this.noResults.setAttribute('role', 'status');
            this.noResults.innerHTML = '<i class="fas fa-folder-open ss-no-results-icon"></i><span>' + this.config.emptyText + '</span>';
            this.noResults.style.display = 'none';

            // ─── عدّاد النتائج ───
            this.countFooter = document.createElement('div');
            this.countFooter.className = 'ss-count';
            this.countFooter.setAttribute('role', 'status');

            this.dropdown.appendChild(this.optionsList);
            this.dropdown.appendChild(this.noResults);
            this.dropdown.appendChild(this.countFooter);

            // إضافة إلى body
            document.body.appendChild(this.dropdown);

            // عرض الخيارات
            this._renderOptions();
            this._updateCount();
        }

        // ===== حساب موقع القائمة المنسدلة =====
        _positionDropdown() {
            const rect = this.display.getBoundingClientRect();
            const dd = this.dropdown;
            const viewH = window.innerHeight;
            const viewW = window.innerWidth;

            // إذا كان الزر غير مرئي (مثلاً داخل لوحة مطوية)
            if (rect.width === 0 && rect.height === 0) {
                const containerRect = this.container.getBoundingClientRect();
                if (containerRect.width > 0 && containerRect.height > 0) {
                    return this._positionFromRect(containerRect);
                }
                dd.style.top = Math.max(viewH * 0.2, 20) + 'px';
                dd.style.left = Math.max((viewW - 280) / 2, 8) + 'px';
                dd.style.width = '280px';
                return;
            }

            this._positionFromRect(rect);
        }

        _positionFromRect(rect) {
            const dd = this.dropdown;
            const viewH = window.innerHeight;
            const viewW = window.innerWidth;
            const GAP = 4;
            const MIN_PAD = 8;

            // حساب الارتفاع المتوقع للقائمة
            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            const ddHeight = dd.offsetHeight > 50 ? dd.offsetHeight : Math.min(dd.scrollHeight, this.config.maxHeight + 120) || 300;

            const spaceBelow = viewH - rect.bottom - GAP;
            const spaceAbove = rect.top - GAP;

            let top, left, width;
            let optionsMaxHeight = this.config.maxHeight;

            // تحديد الاتجاه: أسفل أو أعلى
            if (spaceBelow >= Math.min(ddHeight, 200)) {
                top = rect.bottom + GAP;
                if (spaceBelow < ddHeight) {
                    const searchHeight = 52;
                    const countHeight = 36;
                    const available = spaceBelow - searchHeight - countHeight - MIN_PAD;
                    optionsMaxHeight = Math.max(available, 100);
                }
            } else if (spaceAbove >= Math.min(ddHeight, 200)) {
                top = Math.max(rect.top - ddHeight - GAP, MIN_PAD);
                if (rect.top - GAP - MIN_PAD < ddHeight) {
                    const searchHeight = 52;
                    const countHeight = 36;
                    const available = (rect.top - GAP - MIN_PAD) - searchHeight - countHeight;
                    optionsMaxHeight = Math.max(available, 100);
                }
            } else {
                top = rect.bottom + GAP;
                const searchHeight = 52;
                const countHeight = 36;
                const available = (viewH - top - MIN_PAD) - searchHeight - countHeight;
                optionsMaxHeight = Math.max(available, 80);
            }

            this.optionsList.style.maxHeight = optionsMaxHeight + 'px';

            width = Math.max(rect.width, 200);
            left = rect.left;

            // RTL: محاذاة للحافة اليمنى
            if (document.documentElement.dir === 'rtl' || document.documentElement.getAttribute('dir') === 'rtl') {
                left = rect.right - width;
            }

            // منع الخروج عن الشاشة
            if (left + width > viewW - MIN_PAD) {
                left = viewW - width - MIN_PAD;
            }
            if (left < MIN_PAD) {
                left = MIN_PAD;
            }

            dd.style.top = top + 'px';
            dd.style.left = left + 'px';
            dd.style.width = width + 'px';
        }

        // ===== عرض الخيارات =====
        _renderOptions() {
            this.optionsList.innerHTML = '';
            const term = this.searchTerm;
            const normalizedTerm = term ? normalizeArabic(term.toLowerCase().trim()) : '';
            let visibleCount = 0;

            this.options.forEach((opt, idx) => {
                // تصفية حسب البحث
                if (normalizedTerm) {
                    const normalizedText = normalizeArabic(opt.text.toLowerCase());
                    const normalizedValue = normalizeArabic(opt.value.toLowerCase());
                    if (!normalizedText.includes(normalizedTerm) && !normalizedValue.includes(normalizedTerm)) {
                        return;
                    }
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
                }

                // عرض مخصص أو عادي مع تمييز
                if (this.config.renderFn) {
                    optEl.innerHTML = this.config.renderFn(opt, term);
                } else {
                    optEl.innerHTML = highlightMatch(opt.text, term);
                }

                if (!opt.disabled) {
                    optEl.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this._selectOption(opt);
                    });
                }

                this.optionsList.appendChild(optEl);
            });

            this.noResults.style.display = visibleCount === 0 ? 'flex' : 'none';
            this._updateCount(visibleCount);
            this._focusedIdx = -1;
        }

        // ===== تحديث العدّاد =====
        _updateCount(visibleCount) {
            if (visibleCount === undefined) {
                visibleCount = this.optionsList.querySelectorAll('.ss-option').length;
            }
            const total = this.options.filter(o => o.value).length; // استثناء الخيار الفارغ
            if (this.searchTerm) {
                this.countFooter.textContent = visibleCount + ' من ' + total;
            } else {
                this.countFooter.textContent = total + ' خيار';
            }
        }

        // ===== اختيار خيار =====
        _selectOption(opt) {
            const prevValue = this.selectedValue;
            this.selectedValue = opt.value;
            this.selectEl.value = opt.value;

            // تحديث العرض
            this.displayInner.className = opt.value ? 'ss-selected-text' : 'ss-placeholder';
            this.displayInner.textContent = opt.text || this.config.placeholder;
            this.display.classList.remove('ss-empty');

            // تحديث زر المسح
            this.clearBtn.style.display = opt.value ? 'flex' : 'none';

            // تحديث التحديد في القائمة
            this.optionsList.querySelectorAll('.ss-option').forEach(el => {
                el.classList.remove('selected');
                el.setAttribute('aria-selected', 'false');
            });
            const selEl = this.optionsList.querySelector(`[data-value="${CSS.escape(opt.value)}"]`);
            if (selEl) {
                selEl.classList.add('selected');
                selEl.setAttribute('aria-selected', 'true');
            }

            // إطلاق حدث change على الـ select الأصلي
            const event = new Event('change', { bubbles: true });
            this.selectEl.dispatchEvent(event);

            // تنفيذ onchange handler من HTML attribute
            if (this.onchangeHandler) {
                try {
                    new Function('value', this.onchangeHandler)(opt.value);
                } catch (e) {
                    console.warn('SearchableSelect onchange error:', e);
                }
            }

            // تنفيذ callback مخصّص
            if (this.config.onChange && typeof this.config.onChange === 'function') {
                try {
                    this.config.onChange(opt.value, opt, prevValue);
                } catch (e) {
                    console.warn('SearchableSelect onChange callback error:', e);
                }
            }

            this.close();
        }

        // ===== ربط الأحداث =====
        _bindEvents() {
            // ─── زر التفعيل: نقر ───
            this.display.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.isDisabled) return;
                // إذا نقر على زر المسح
                if (this.clearBtn.contains(e.target)) {
                    this._clearSelection();
                    return;
                }
                this.isOpen ? this.close() : this.open();
            });

            // ─── زر التفعيل: لوحة المفاتيح ───
            this.display.addEventListener('keydown', (e) => {
                if (this.isDisabled) return;
                switch (e.key) {
                    case 'Enter':
                    case ' ':
                        e.preventDefault();
                        this.isOpen ? this.close() : this.open();
                        break;
                    case 'Escape':
                        this.close();
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        if (!this.isOpen) this.open();
                        else this._focusNextOption();
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        if (!this.isOpen) this.open();
                        else this._focusPrevOption();
                        break;
                    case 'Tab':
                        if (this.isOpen) this.close();
                        break;
                }
            });

            // ─── زر المسح ───
            this.clearBtn.addEventListener('mousedown', (e) => {
                e.stopPropagation();
                e.preventDefault();
            });

            // ─── حقل البحث: كتابة ───
            this.searchInput.addEventListener('input', () => {
                this.searchTerm = this.searchInput.value;
                this._renderOptions();
            });

            // ─── حقل البحث: لوحة المفاتيح ───
            this.searchInput.addEventListener('keydown', (e) => {
                switch (e.key) {
                    case 'Escape':
                        e.preventDefault();
                        this.close();
                        this.display.focus();
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        this._focusNextOption();
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        this._focusPrevOption();
                        break;
                    case 'Enter':
                        e.preventDefault();
                        this._selectFocusedOption();
                        break;
                    case 'Tab':
                        if (this.isOpen) this.close();
                        break;
                    case 'Backspace':
                        // مسح الاختيار عند مسح كل النص
                        if (this.searchInput.value === '' && this.selectedValue) {
                            // لا نمسح تلقائياً — فقط نظهر الكل
                            this.searchTerm = '';
                            this._renderOptions();
                        }
                        break;
                }
            });

            // ─── القائمة المنسدلة: منع انتشار الأحداث ───
            // NOTE: wheel scrolling is handled by the GLOBAL capture-phase handler below.
            // The instance-level handler here is kept as a fallback for edge cases.
            this.dropdown.addEventListener('wheel', (e) => {
                e.preventDefault();   // block page/modal scroll
                e.stopPropagation(); // stop event bubbling
                this.optionsList.scrollTop += e.deltaY || 0;
            }, { passive: false });

            this.dropdown.addEventListener('touchmove', (e) => {
                e.stopPropagation();
            }, { passive: true });

            this.dropdown.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });

            this.dropdown.addEventListener('click', (e) => {
                e.stopPropagation();
            });

            // ─── منع سرقة الـ focus من المودال ───
            this.dropdown.addEventListener('focusin', (e) => {
                e.stopPropagation();
            });

            this.container.addEventListener('focusin', (e) => {
                e.stopPropagation();
            });

            // ─── مراقبة تغييرات الـ select الأصلي ───
            this._childObserver = new MutationObserver(() => {
                this._syncFromSelect();
            });
            this._childObserver.observe(this.selectEl, { childList: true, subtree: true, attributes: true });

            // ─── اعتراض .value على الـ select الأصلي ───
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

            // ─── عند إغلاق المودال ───
            const modal = this.container.closest('.modal');
            if (modal) {
                modal.addEventListener('hidden.bs.modal', () => {
                    if (this.isOpen) this.close();
                });
            }
        }

        // ===== التنقل بلوحة المفاتيح =====
        _getVisibleOptions() {
            return this.optionsList.querySelectorAll('.ss-option:not(.ss-option-disabled)');
        }

        _focusNextOption() {
            const opts = this._getVisibleOptions();
            if (!opts.length) return;
            if (this._focusedIdx < 0) this._focusedIdx = -1;
            this._focusedIdx = Math.min(this._focusedIdx + 1, opts.length - 1);
            this._applyFocus(opts);
        }

        _focusPrevOption() {
            const opts = this._getVisibleOptions();
            if (!opts.length) return;
            if (this._focusedIdx < 0) this._focusedIdx = opts.length;
            this._focusedIdx = Math.max(this._focusedIdx - 1, 0);
            this._applyFocus(opts);
        }

        _applyFocus(opts) {
            opts.forEach(o => o.classList.remove('ss-focused'));
            if (this._focusedIdx >= 0 && this._focusedIdx < opts.length) {
                opts[this._focusedIdx].classList.add('ss-focused');
                opts[this._focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                // تحديث aria-activedescendant
                const val = opts[this._focusedIdx].getAttribute('data-value');
                this.display.setAttribute('aria-activedescendant', 'ss-opt-' + val);
            }
        }

        _selectFocusedOption() {
            const opts = this._getVisibleOptions();
            if (!opts.length || this._focusedIdx < 0) return;
            const el = opts[this._focusedIdx];
            const value = el.getAttribute('data-value');
            const opt = this.options.find(o => o.value === value);
            if (opt) this._selectOption(opt);
        }

        // ===== مسح الاختيار =====
        _clearSelection() {
            const prevValue = this.selectedValue;
            this.selectedValue = '';
            this.selectEl.value = '';

            this.displayInner.className = 'ss-placeholder';
            this.displayInner.textContent = this.config.placeholder;
            this.clearBtn.style.display = 'none';

            if (this.isRequired) this.display.classList.add('ss-empty');

            // تحديث التحديد في القائمة
            this.optionsList.querySelectorAll('.ss-option.selected').forEach(el => {
                el.classList.remove('selected');
                el.setAttribute('aria-selected', 'false');
            });

            // إطلاق حدث change
            const event = new Event('change', { bubbles: true });
            this.selectEl.dispatchEvent(event);

            if (this.onchangeHandler) {
                try {
                    new Function('value', this.onchangeHandler)('');
                } catch (e) { /* silent */ }
            }

            if (this.config.onChange && typeof this.config.onChange === 'function') {
                try {
                    this.config.onChange('', null, prevValue);
                } catch (e) { /* silent */ }
            }

            if (this.isOpen) {
                this.searchTerm = '';
                this.searchInput.value = '';
                this._renderOptions();
            }
        }

        // ===== مزامنة من الـ select الأصلي =====
        _syncFromSelect() {
            this._collectOptions();
            const sel = this.options.find(o => o.value === this.selectEl.value);
            if (sel) {
                this.selectedValue = sel.value;
                this.displayInner.className = 'ss-selected-text';
                this.displayInner.textContent = sel.text;
                this.clearBtn.style.display = sel.value ? 'flex' : 'none';
            } else {
                this.selectedValue = '';
                this.displayInner.className = 'ss-placeholder';
                this.displayInner.textContent = this.config.placeholder;
                this.clearBtn.style.display = 'none';
            }
            if (this.isRequired && !this.selectedValue) {
                this.display.classList.add('ss-empty');
            } else {
                this.display.classList.remove('ss-empty');
            }
            this._renderOptions();
            this._updateCount();
        }

        // ===== فتح القائمة =====
        open() {
            if (this._destroyed || this.isDisabled) return;

            // إغلاق أي قائمة مفتوحة أخرى
            instances.forEach(inst => {
                if (inst !== this && inst.isOpen) inst.close();
            });

            this.isOpen = true;
            this._currentZIndex = nextZIndex();

            this.dropdown.classList.add('show');
            this.dropdown.style.zIndex = this._currentZIndex;
            this.display.classList.add('active');
            this.display.setAttribute('aria-expanded', 'true');

            // تحقق من المودال
            const modal = this.container.closest('.modal');
            if (modal) {
                this.dropdown.classList.add('in-modal');
            }

            // حساب الموقع
            this._positionDropdown();
            requestAnimationFrame(() => this._positionDropdown());

            // التركيز على حقل البحث
            setTimeout(() => {
                if (!this._destroyed) {
                    this.searchInput.focus();
                }
            }, 60);

            // التمرير للخيار المحدد
            const selEl = this.optionsList.querySelector('.ss-option.selected');
            if (selEl) {
                setTimeout(() => {
                    selEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
                }, 120);
            }
        }

        // ===== إغلاق القائمة =====
        close() {
            this.isOpen = false;
            this.dropdown.classList.remove('show');
            this.dropdown.classList.remove('in-modal');
            this.display.classList.remove('active');
            this.display.setAttribute('aria-expanded', 'false');
            this.display.removeAttribute('aria-activedescendant');

            // إعادة تعيين البحث
            this.searchTerm = '';
            this.searchInput.value = '';
            this.optionsList.style.maxHeight = this.config.maxHeight + 'px';
            this._renderOptions();
            this._focusedIdx = -1;
        }

        // ==========================================================
        //  واجهة برمجية عامة (Public API)
        // ==========================================================

        /** تحديث الخيارات ديناميكياً */
        updateOptions(newOptions) {
            this.selectEl.innerHTML = '';
            this.options = [];

            newOptions.forEach(opt => {
                const optionEl = document.createElement('option');
                optionEl.value = opt.value;
                optionEl.textContent = opt.text;
                if (opt.selected) optionEl.selected = true;
                if (opt.disabled) optionEl.disabled = true;
                if (opt.dataFee) optionEl.dataset.fee = opt.dataFee;
                if (opt.dataBalance) optionEl.dataset.balance = opt.dataBalance;
                this.selectEl.appendChild(optionEl);

                this.options.push({
                    value: opt.value,
                    text: opt.text,
                    selected: opt.selected || false,
                    disabled: opt.disabled || false,
                    dataFee: opt.dataFee || '',
                    dataBalance: opt.dataBalance || '',
                    _index: this.options.length,
                });
            });

            this.selectedValue = this.selectEl.value;
            this._syncFromSelect();
        }

        /** تعيين قيمة */
        setValue(value) {
            this.selectEl.value = value;
            this._syncFromSelect();
        }

        /** الحصول على القيمة الحالية */
        getValue() {
            return this.selectedValue;
        }

        /** الحصول على نص الاختيار الحالي */
        getSelectedText() {
            const sel = this.options.find(o => o.value === this.selectedValue);
            return sel ? sel.text : '';
        }

        /** تعطيل/تفعيل */
        setDisabled(disabled) {
            this.isDisabled = disabled;
            if (disabled) {
                this.container.classList.add('ss-disabled');
                if (this.isOpen) this.close();
            } else {
                this.container.classList.remove('ss-disabled');
            }
        }

        /** تدمير */
        destroy() {
            this._destroyed = true;
            if (this._childObserver) this._childObserver.disconnect();

            this.selectEl.style.display = '';
            this.selectEl.removeAttribute('data-ss-converted');

            // إزالة اعتراض value
            if (this._valueInterceptor) {
                delete this.selectEl.value; // يُعيد الأصل من prototype
            }

            if (this.container.parentNode) {
                this.container.parentNode.insertBefore(this.selectEl, this.container);
            }
            this.container.remove();
            this.dropdown.remove();

            const idx = instances.indexOf(this);
            if (idx > -1) instances.splice(idx, 1);
        }
    }

    // ==========================================================
    //  أحداث عامة
    // ==========================================================

    // إغلاق عند النقر خارج القائمة
    document.addEventListener('click', (e) => {
        instances.forEach(inst => {
            if (inst.isOpen && !inst.display.contains(e.target) && !inst.dropdown.contains(e.target)) {
                inst.close();
            }
        });
    });

    // ★ معالج wheel عام (capture phase + passive:false)
    // عندما يكون المؤشر داخل قائمة مفتوحة:
    //   1) preventDefault() يمنع تمرير الصفحة/المودال
    //   2) نمرّر التمرير يدوياً إلى .ss-options
    // استخدام capture:true يضمن التنفيذ قبل أي معالج آخر.
    document.addEventListener('wheel', (e) => {
        for (const inst of instances) {
            if (inst.isOpen && inst.dropdown.contains(e.target)) {
                e.preventDefault();   // منع تمرير الصفحة/المودال
                e.stopPropagation(); // منع وصول الحدث للصفحة
                inst.optionsList.scrollTop += e.deltaY || 0;
                return;
            }
        }
    }, { passive: false, capture: true });

    // إغلاق بـ Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openInst = instances.find(inst => inst.isOpen);
            if (openInst) {
                openInst.close();
                openInst.display.focus();
            }
        }
    });

    // إعادة حساب الموقع عند التمرير/تغيير الحجم
    const debouncedReposition = debounce(() => {
        instances.forEach(inst => {
            if (inst.isOpen) inst._positionDropdown();
        });
    }, 16);

    window.addEventListener('scroll', (e) => {
        // إعادة حساب فقط إذا كان الهدف حاوية أصلية (مودال، لوحة قابلة للتمرير)
        instances.forEach(inst => {
            if (inst.isOpen) {
                // إذا كان التمرير من داخل القائمة نفسها — لا نعيد الحساب
                if (inst.dropdown.contains(e.target)) return;
                inst._positionDropdown();
            }
        });
    }, true); // capture phase

    window.addEventListener('resize', debouncedReposition);

    // ==========================================================
    //  التهيئة التلقائية
    // ==========================================================
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

    // ==========================================================
    //  تصدير الواجهة العامة
    // ==========================================================
    window.SearchableSelect = SearchableSelect;
    window.initSearchableSelects = initAll;

    /**
     * makeSearchableSelect — واجهة متوافقة مع النظام القديم
     * توفر نفس API القديم مع استخدام SearchableSelect الجديد
     */
    window.makeSearchableSelect = function (selectId, options = {}) {
        const select = document.getElementById(selectId);
        if (!select) return null;

        const instance = new SearchableSelect(select, {
            onChange: options.onChange || null,
            placeholder: options.placeholder || undefined,
            searchPlaceholder: options.searchPlaceholder || undefined,
        });

        // واجهة متوافقة مع النظام القديم
        return {
            setValue: (value) => instance.setValue(value),
            getValue: () => instance.getValue(),
            refresh: () => instance._syncFromSelect(),
            clear: () => instance._clearSelection(),
            destroy: () => instance.destroy(),
            // واجهة إضافية
            open: () => instance.open(),
            close: () => instance.close(),
            updateOptions: (opts) => instance.updateOptions(opts),
            _instance: instance,
        };
    };

})();
