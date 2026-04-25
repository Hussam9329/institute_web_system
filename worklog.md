---
Task ID: 1
Agent: Main Agent
Task: Complete remaining tasks for the Institute Management System

Work Log:
- Reviewed all project files: models, routes, templates, services, config
- Identified that tasks 1-8 were already completed in previous sessions
- Updated requirements.txt: added weasyprint==60.2, removed reportlab/arabic-reshaper/python-bidi/Pillow
- Fixed institute deduction thousands logic bug in teachers/form.html:
  - Percentage type: value is stored as-is (10 = 10%), NOT multiplied by 1000
  - Manual type: value is still multiplied by 1000 (entered in thousands)
  - Added dynamic hint text that changes based on deduction type
  - Fixed display value calculation to handle both types correctly
- Fixed hardcoded "50,000" in teachers/detail.html deduction display:
  - Now shows actual percentage when type is percentage
  - Shows actual per-student amount when type is manual
  - Shows "لا يوجد خصم" when no deduction is configured

Stage Summary:
- requirements.txt updated for WeasyPrint-based PDF generation
- Institute deduction logic fixed for percentage vs manual types
- Teacher detail page now shows correct deduction info dynamically

---
Task ID: 2
Agent: Main Agent
Task: Fix all search boxes across the application

Work Log:
- Audited all 6 search boxes in the application
- Found root causes: FastAPI incompatibility with Flask's `request.args.get()`, missing form wrappers, URL cleanup clearing search params
- Fixed students/list.html: Added form wrapper, name="search", value="{{ search }}", submit button, Enter key handler, no-results message for table
- Fixed teachers/list.html: Changed `request.args.get('search', '')` to `{{ search }}`, added no-results message for table, improved JS
- Fixed accounting/index.html: Changed `request.args.get('search', '')` to `{{ search }}`, added form wrapper with submit button, Enter key handler
- Fixed subjects/list.html: Added no-results message for table, improved JS
- Fixed app.js: URL cleanup now preserves search params (only removes msg/error/count/name)
- payments/index.html was already correct (form, name, value all proper)

Stage Summary:
- All search boxes now work with both client-side instant filtering and server-side search on Enter
- FastAPI compatibility fixed (no more request.args.get which is Flask-only)
- URL search params preserved when msg/error alerts are cleared
- "No results" messages added for table views on all pages
