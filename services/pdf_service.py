# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية - WeasyPrint + HTML
# ============================================

import os
from datetime import datetime
from weasyprint import HTML

from config import (
    STUDENT_PDFS_DIR, TEACHER_PDFS_DIR, RECEIPTS_DIR, REPORTS_DIR,
    format_currency, format_date, APP_TITLE
)
from services.finance_service import finance_service
from database import Database


class PDFService:
    """خدمة توليد تقارير PDF احترافية باستخدام WeasyPrint مع دعم كامل للغة العربية"""

    def __init__(self):
        self.db = Database()

    def _generate_pdf(self, html_content: str, filepath: str, pagesize: str = 'A4') -> str:
        """تحويل HTML إلى PDF باستخدام WeasyPrint"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if pagesize == 'A5-landscape':
            page_css = '@page { size: 148mm 105mm; margin: 8mm; }'
        else:
            page_css = '@page { size: A4; margin: 15mm 20mm; }'

        full_html = f'''
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
            <style>
                {page_css}
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: 'Cairo', 'DejaVu Sans', sans-serif;
                    direction: rtl;
                    text-align: right;
                    color: #1e293b;
                    line-height: 1.8;
                    font-size: 11pt;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #312e81;
                }}
                .header h1 {{
                    font-size: 18pt;
                    color: #312e81;
                    margin-bottom: 4px;
                }}
                .header .subtitle {{
                    font-size: 13pt;
                    color: #4338ca;
                    font-weight: 600;
                }}
                .header .line {{
                    height: 2px;
                    background: linear-gradient(90deg, #312e81, #6366f1, #312e81);
                    margin: 8px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px solid #e2e8f0;
                    font-size: 9pt;
                    color: #94a3b8;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                    font-size: 10pt;
                }}
                th {{
                    background: #312e81;
                    color: white;
                    padding: 8px 10px;
                    font-weight: 700;
                    text-align: center;
                    white-space: nowrap;
                }}
                td {{
                    padding: 7px 10px;
                    border-bottom: 1px solid #e2e8f0;
                    text-align: center;
                }}
                tr:nth-child(even) {{ background: #f8fafc; }}
                .info-table td {{ text-align: right; }}
                .info-table th {{ text-align: right; width: 120px; background: #4338ca; }}
                .text-success {{ color: #059669; font-weight: 700; }}
                .text-danger {{ color: #dc2626; font-weight: 700; }}
                .text-primary {{ color: #312e81; font-weight: 700; }}
                .text-muted {{ color: #94a3b8; }}
                .badge {{
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 9pt;
                    font-weight: 600;
                }}
                .badge-success {{ background: #d1fae5; color: #065f46; }}
                .badge-danger {{ background: #fee2e2; color: #991b1b; }}
                .badge-info {{ background: #e0e7ff; color: #3730a3; }}
                .section-title {{
                    font-size: 12pt;
                    font-weight: 700;
                    color: #312e81;
                    margin: 15px 0 8px 0;
                    padding: 5px 10px;
                    background: #eef2ff;
                    border-radius: 6px;
                    border-right: 4px solid #4338ca;
                }}
                .total-row {{ background: #eef2ff !important; font-weight: 700; }}
                .receipt-box {{
                    border: 2px solid #312e81;
                    border-radius: 12px;
                    padding: 15px;
                    max-width: 100%;
                }}
                .receipt-title {{
                    text-align: center;
                    font-size: 16pt;
                    color: #312e81;
                    font-weight: 800;
                    margin-bottom: 10px;
                }}
                .receipt-info {{
                    display: flex;
                    justify-content: space-between;
                    padding: 6px 0;
                    border-bottom: 1px dashed #cbd5e1;
                }}
                .receipt-info .label {{ color: #64748b; font-weight: 600; }}
                .receipt-info .value {{ font-weight: 700; color: #1e293b; }}
                .signature-area {{
                    text-align: center;
                    margin-top: 25px;
                    padding-top: 15px;
                    border-top: 1px solid #e2e8f0;
                }}
                .signature-line {{
                    display: inline-block;
                    width: 200px;
                    border-bottom: 1px solid #1e293b;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        '''
        
        HTML(string=full_html).write_pdf(filepath)
        return filepath

    # =====================================================
    # تقرير الطالب PDF
    # =====================================================

    def generate_student_report(self, student_id: int) -> str:
        student_result = self.db.execute_query("SELECT * FROM students WHERE id = %s", (student_id,))
        if not student_result:
            raise Exception("الطالب غير موجود")
        student = dict(student_result[0])

        filename = f"student_report_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(STUDENT_PDFS_DIR, filename)

        teachers_summary = finance_service.get_student_all_teachers_summary(student_id)

        html = f'''
        <div class="header">
            <h1>{APP_TITLE}</h1>
            <div class="line"></div>
            <div class="subtitle">تقرير الطالب المالي</div>
        </div>

        <table class="info-table">
            <tr><th>البيان</th><td>القيمة</td></tr>
            <tr><td>اسم الطالب</td><td><strong>{student['name']}</strong></td></tr>
            <tr><td>الرمز</td><td>{student['barcode']}</td></tr>
            <tr><td>نوع الدراسة</td><td>{student['study_type']}</td></tr>
            <tr><td>ملاحظات</td><td>{student['notes'] or '-'}</td></tr>
        </table>

        <div class="section-title">الملخص المالي حسب المدرس</div>
        '''

        if teachers_summary:
            html += '''
            <table>
                <tr>
                    <th>المدرس</th>
                    <th>المادة</th>
                    <th>الأجر الكلي</th>
                    <th>المدفوع</th>
                    <th>المتبقي</th>
                </tr>
            '''
            total_fee_all = total_paid_all = total_remaining_all = 0
            for ts in teachers_summary:
                total_fee_all += ts['total_fee']
                total_paid_all += ts['paid_total']
                total_remaining_all += ts['remaining_balance']
                remaining_class = 'text-success' if ts['remaining_balance'] <= 0 else 'text-danger'
                html += f'''
                <tr>
                    <td><strong>{ts['teacher_name']}</strong></td>
                    <td><span class="badge badge-info">{ts['subject']}</span></td>
                    <td>{format_currency(ts['total_fee'])}</td>
                    <td class="text-success">{format_currency(ts['paid_total'])}</td>
                    <td class="{remaining_class}">{format_currency(ts['remaining_balance'])}</td>
                </tr>
                '''
            html += f'''
                <tr class="total-row">
                    <td colspan="2"><strong>الإجمالي</strong></td>
                    <td>{format_currency(total_fee_all)}</td>
                    <td class="text-success">{format_currency(total_paid_all)}</td>
                    <td class="{'text-success' if total_remaining_all <= 0 else 'text-danger'}">{format_currency(total_remaining_all)}</td>
                </tr>
            </table>
            '''
        else:
            html += '<p style="text-align:center;color:#94a3b8;margin:20px 0;">لا يوجد مدرسين مرتبطين بهذا الطالب</p>'

        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        html += f'''
        <div class="footer">
            نظام إدارة المعهد || HussamVision<br>
            تاريخ الطباعة: {now}
        </div>
        '''

        return self._generate_pdf(html, filepath)

    # =====================================================
    # تقرير المدرس PDF
    # =====================================================

    def generate_teacher_report(self, teacher_id: int) -> str:
        teacher_result = self.db.execute_query("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
        if not teacher_result:
            raise Exception("المدرس غير موجود")
        teacher = dict(teacher_result[0])

        due_info = finance_service.calculate_teacher_due(teacher_id)
        balance_info = finance_service.calculate_teacher_balance(teacher_id)
        students_list = finance_service.get_teacher_students_list(teacher_id)
        recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit=20)

        filename = f"teacher_report_{teacher_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(TEACHER_PDFS_DIR, filename)

        html = f'''
        <div class="header">
            <h1>{APP_TITLE}</h1>
            <div class="line"></div>
            <div class="subtitle">تقرير المدرس المالي</div>
        </div>

        <table class="info-table">
            <tr><th>البيان</th><td>القيمة</td></tr>
            <tr><td>اسم المدرس</td><td><strong>{teacher['name']}</strong></td></tr>
            <tr><td>المادة</td><td>{teacher['subject']}</td></tr>
            <tr><td>الأجر الكلي</td><td>{format_currency(teacher['total_fee'])}</td></tr>
            <tr><td>عدد الطلاب</td><td>{len(students_list)}</td></tr>
            <tr><td>ملاحظات</td><td>{teacher['notes'] or '-'}</td></tr>
        </table>

        <div class="section-title">الملخص المالي</div>
        <table class="info-table">
            <tr><th>البند</th><td>القيمة</td></tr>
            <tr><td>إجمالي الاستلامات</td><td class="text-primary">{format_currency(due_info['total_received'])}</td></tr>
            <tr><td>عدد الطلاب الدافعين</td><td>{due_info['paying_students_count']}</td></tr>
            <tr><td>إجمالي خصم المعهد</td><td class="text-danger">{format_currency(due_info['institute_deduction'])}</td></tr>
            <tr><td>مستحق المدرس</td><td class="text-success">{format_currency(balance_info['teacher_due'])}</td></tr>
            <tr><td>إجمالي المسحوب</td><td class="text-danger">{format_currency(balance_info['withdrawn_total'])}</td></tr>
            <tr><td>الرصيد المتبقي</td><td class="text-success">{format_currency(balance_info['remaining_balance'])}</td></tr>
        </table>
        '''

        if students_list:
            html += '''
            <div class="section-title">قائمة الطلاب ودفعاتهم</div>
            <table>
                <tr>
                    <th>اسم الطالب</th>
                    <th>نوع الدراسة</th>
                    <th>الحالة</th>
                    <th>المدفوع</th>
                    <th>المتبقي</th>
                    <th>حالة الدفع</th>
                </tr>
            '''
            for s in students_list:
                status_text = "دافع" if s['is_paying'] else "غير دافع"
                status_class = "badge-success" if s['is_paying'] else "badge-danger"
                remaining_class = 'text-success' if s['remaining_balance'] <= 0 else 'text-danger'
                html += f'''
                <tr>
                    <td><strong>{s['name']}</strong></td>
                    <td>{s['study_type']}</td>
                    <td>{s.get('status', 'مستمر')}</td>
                    <td class="text-success">{format_currency(s['paid_total'])}</td>
                    <td class="{remaining_class}">{format_currency(s['remaining_balance'])}</td>
                    <td><span class="badge {status_class}">{status_text}</span></td>
                </tr>
                '''
            html += '</table>'

        if recent_withdrawals:
            html += '''
            <div class="section-title">آخر السحوبات</div>
            <table>
                <tr><th>المبلغ</th><th>التاريخ</th><th>ملاحظات</th></tr>
            '''
            for w in recent_withdrawals:
                html += f'''
                <tr>
                    <td class="text-danger">{format_currency(w['amount'])}</td>
                    <td>{format_date(w['withdrawal_date'])}</td>
                    <td>{w['notes'] or '-'}</td>
                </tr>
                '''
            html += '</table>'

        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        html += f'''
        <div class="footer">
            نظام إدارة المعهد || HussamVision<br>
            تاريخ الطباعة: {now}
        </div>
        '''

        return self._generate_pdf(html, filepath)

    # =====================================================
    # وصل الدفع PDF - A5 بالعرض
    # =====================================================

    def generate_receipt(self, installment_id: int) -> str:
        installment_query = '''
            SELECT i.*, s.name as student_name, t.name as teacher_name, t.subject
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.id = %s
        '''
        installment_result = self.db.execute_query(installment_query, (installment_id,))
        if not installment_result:
            raise Exception("القسط غير موجود")
        installment = dict(installment_result[0])

        filename = f"receipt_{installment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RECEIPTS_DIR, filename)

        now = datetime.now()
        date_str = now.strftime('%Y/%m/%d')
        time_str = now.strftime('%H:%M')

        html = f'''
        <div class="receipt-box">
            <div class="receipt-title">وصل دفع رسمي</div>
            <div style="height:2px;background:linear-gradient(90deg,#312e81,#6366f1,#312e81);margin-bottom:12px;"></div>

            <div class="receipt-info"><span class="label">اسم الطالب</span><span class="value">{installment['student_name']}</span></div>
            <div class="receipt-info"><span class="label">اسم المدرس</span><span class="value">{installment['teacher_name']}</span></div>
            <div class="receipt-info"><span class="label">المادة</span><span class="value">{installment['subject']}</span></div>
            <div class="receipt-info"><span class="label">نوع القسط</span><span class="value">{installment['installment_type']}</span></div>
            <div class="receipt-info"><span class="label">المبلغ المدفوع</span><span class="value" style="font-size:14pt;color:#059669;">{format_currency(installment['amount'])}</span></div>
            <div class="receipt-info"><span class="label">تاريخ الدفع</span><span class="value">{format_date(installment['payment_date'])}</span></div>
            <div class="receipt-info"><span class="label">ملاحظات</span><span class="value">{installment['notes'] or '-'}</span></div>

            <div class="signature-area">
                <div style="font-size:9pt;color:#94a3b8;">التاريخ: {date_str} - الوقت: {time_str}</div>
                <div class="signature-line"></div>
                <div style="font-size:9pt;color:#64748b;">توقيع المسؤول</div>
            </div>
        </div>

        <div style="text-align:center;margin-top:10px;font-size:8pt;color:#94a3b8;">
            نظام إدارة المعهد || HussamVision
        </div>
        '''

        return self._generate_pdf(html, filepath, pagesize='A5-landscape')

    # =====================================================
    # تقرير المادة PDF
    # =====================================================

    def generate_subject_report(self, subject_name: str) -> str:
        teachers = self.db.execute_query(
            "SELECT * FROM teachers WHERE subject = %s ORDER BY name", (subject_name,)
        )
        if not teachers:
            raise Exception("لا يوجد مدرسين لهذه المادة")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"subject_{subject_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        html = f'''
        <div class="header">
            <h1>{APP_TITLE}</h1>
            <div class="line"></div>
            <div class="subtitle">تقرير مادة: {subject_name}</div>
        </div>

        <table class="info-table">
            <tr><th>البيان</th><td>القيمة</td></tr>
            <tr><td>اسم المادة</td><td><strong>{subject_name}</strong></td></tr>
            <tr><td>عدد المدرسين</td><td>{len(teachers)}</td></tr>
        </table>

        <div class="section-title">قائمة المدرسين</div>
        <table>
            <tr><th>#</th><th>المدرس</th><th>الأجر الكلي</th><th>عدد الطلاب</th></tr>
        '''
        for i, t in enumerate(teachers, 1):
            cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            sc = cnt[0]['cnt'] if cnt else 0
            html += f'''
            <tr>
                <td>{i}</td>
                <td><strong>{t['name']}</strong></td>
                <td class="text-primary">{format_currency(t['total_fee'])}</td>
                <td>{sc}</td>
            </tr>
            '''
        html += '</table>'

        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        html += f'''
        <div class="footer">
            نظام إدارة المعهد || HussamVision<br>
            تاريخ الطباعة: {now}
        </div>
        '''

        return self._generate_pdf(html, filepath)

    def generate_all_subjects_report(self) -> str:
        subjects = self.db.execute_query("SELECT name FROM subjects ORDER BY name")
        if not subjects:
            raise Exception("لا توجد مواد")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"all_subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        html = f'''
        <div class="header">
            <h1>{APP_TITLE}</h1>
            <div class="line"></div>
            <div class="subtitle">تقرير شامل لجميع المواد</div>
        </div>
        '''

        for subj in subjects:
            teachers = self.db.execute_query(
                "SELECT id, name, total_fee FROM teachers WHERE subject = %s ORDER BY name", (subj['name'],)
            )
            html += f'''
            <div class="section-title">المادة: {subj['name']} ({len(teachers)} مدرس)</div>
            <table>
                <tr><th>#</th><th>المدرس</th><th>الأجر</th><th>الطلاب</th></tr>
            '''
            if teachers:
                for i, t in enumerate(teachers, 1):
                    cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
                    sc = cnt[0]['cnt'] if cnt else 0
                    html += f'''
                    <tr>
                        <td>{i}</td>
                        <td><strong>{t['name']}</strong></td>
                        <td class="text-primary">{format_currency(t['total_fee'])}</td>
                        <td>{sc}</td>
                    </tr>
                    '''
            else:
                html += '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">لا يوجد مدرسين</td></tr>'
            html += '</table>'

        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        html += f'''
        <div class="footer">
            نظام إدارة المعهد || HussamVision<br>
            تاريخ الطباعة: {now}
        </div>
        '''

        return self._generate_pdf(html, filepath)


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
