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
