# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية - ReportLab + دعم عربي
# متوافق مع Vercel Serverless
# ============================================

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

import arabic_reshaper
from bidi.algorithm import get_display

from config import (
    STUDENT_PDFS_DIR, TEACHER_PDFS_DIR, RECEIPTS_DIR, REPORTS_DIR,
    format_currency, format_date, APP_TITLE, BASE_DIR
)
from services.finance_service import finance_service
from database import Database


# ===== تسجيل الخط العربي =====
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")

pdfmetrics.registerFont(TTFont('DejaVu', FONT_PATH))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', FONT_PATH))
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.lib.fonts import addMapping
addMapping('DejaVu', 0, 0, 'DejaVu')
addMapping('DejaVu', 1, 0, 'DejaVu-Bold')

# ===== ألوان التصميم =====
PRIMARY = colors.HexColor('#312e81')
SECONDARY = colors.HexColor('#4338ca')
ACCENT = colors.HexColor('#6366f1')
SUCCESS = colors.HexColor('#059669')
DANGER = colors.HexColor('#dc2626')
WARNING = colors.HexColor('#d97706')
LIGHT_BG = colors.HexColor('#f8fafc')
BORDER_COLOR = colors.HexColor('#e2e8f0')
TEXT_MUTED = colors.HexColor('#94a3b8')
WHITE = colors.white


def ar(text):
    """تحويل النص العربي لعرض صحيح في PDF"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def ar_para(text, style):
    """إنشاء فقرة عربية"""
    return Paragraph(ar(text), style)


class PDFService:
    """خدمة توليد تقارير PDF احترافية بدعم كامل للعربية"""

    def __init__(self):
        self.db = Database()

    # ===== أنماط الطباعة =====
    def _get_styles(self):
        """إنشاء أنماط الطباعة العربية"""
        styles = {}
        styles['title'] = ParagraphStyle(
            'title', fontName='DejaVu-Bold', fontSize=18, alignment=2,
            textColor=PRIMARY, spaceAfter=4
        )
        styles['subtitle'] = ParagraphStyle(
            'subtitle', fontName='DejaVu', fontSize=12, alignment=2,
            textColor=SECONDARY, spaceAfter=6
        )
        styles['section'] = ParagraphStyle(
            'section', fontName='DejaVu-Bold', fontSize=12, alignment=2,
            textColor=PRIMARY, spaceBefore=12, spaceAfter=6,
            backColor=colors.HexColor('#eef2ff'), borderPadding=5
        )
        styles['normal'] = ParagraphStyle(
            'normal', fontName='DejaVu', fontSize=10, alignment=2,
            textColor=colors.HexColor('#1e293b'), leading=16
        )
        styles['normal_center'] = ParagraphStyle(
            'normal_center', fontName='DejaVu', fontSize=10, alignment=1,
            textColor=colors.HexColor('#1e293b'), leading=16
        )
        styles['small'] = ParagraphStyle(
            'small', fontName='DejaVu', fontSize=8, alignment=2,
            textColor=TEXT_MUTED, leading=12
        )
        styles['small_center'] = ParagraphStyle(
            'small_center', fontName='DejaVu', fontSize=8, alignment=1,
            textColor=TEXT_MUTED, leading=12
        )
        styles['success'] = ParagraphStyle(
            'success', fontName='DejaVu-Bold', fontSize=10, alignment=2,
            textColor=SUCCESS
        )
        styles['danger'] = ParagraphStyle(
            'danger', fontName='DejaVu-Bold', fontSize=10, alignment=2,
            textColor=DANGER
        )
        styles['primary'] = ParagraphStyle(
            'primary', fontName='DejaVu-Bold', fontSize=10, alignment=2,
            textColor=PRIMARY
        )
        return styles

    def _header(self, styles, subtitle_text):
        """إنشاء رأس التقرير"""
        elements = []
        elements.append(ar_para(APP_TITLE, styles['title']))
        elements.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=4))
        elements.append(ar_para(subtitle_text, styles['subtitle']))
        elements.append(Spacer(1, 8))
        return elements

    def _footer(self, styles):
        """إنشاء تذييل التقرير"""
        elements = []
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=4))
        elements.append(ar_para(f"نظام إدارة المعهد || HussamVision", styles['small_center']))
        elements.append(ar_para(f"تاريخ الطباعة: {now}", styles['small_center']))
        return elements

    def _info_table(self, data, styles):
        """إنشاء جدول معلومات"""
        table_data = [[ar_para("البيان", styles['normal']), ar_para("القيمة", styles['normal'])]]
        for label, value in data:
            table_data.append([
                ar_para(str(label), styles['normal']),
                ar_para(str(value), styles['normal'])
            ])
        t = Table(table_data, colWidths=[120, 370])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ]))
        return t

    def _data_table(self, headers, rows, styles, col_widths=None):
        """إنشاء جدول بيانات"""
        table_data = [[ar_para(h, styles['normal']) for h in headers]]
        for row in rows:
            table_data.append([ar_para(str(c), styles['normal_center']) for c in row])

        t = Table(table_data, colWidths=col_widths)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

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
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        styles = self._get_styles()
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)

        teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
        elements = self._header(styles, "تقرير الطالب المالي")

        elements.append(self._info_table([
            ("اسم الطالب", student['name']),
            ("الرمز", student['barcode']),
            ("نوع الدراسة", student['study_type']),
            ("ملاحظات", student['notes'] or '-'),
        ], styles))
        elements.append(Spacer(1, 10))

        elements.append(ar_para("الملخص المالي حسب المدرس", styles['section']))
        if teachers_summary:
            headers = ["المدرس", "المادة", "الأجر الكلي", "المدفوع", "المتبقي"]
            rows = []
            total_fee_all = total_paid_all = total_remaining_all = 0
            for ts in teachers_summary:
                total_fee_all += ts['total_fee']
                total_paid_all += ts['paid_total']
                total_remaining_all += ts['remaining_balance']
                rows.append([
                    ts['teacher_name'], ts['subject'],
                    format_currency(ts['total_fee']),
                    format_currency(ts['paid_total']),
                    format_currency(ts['remaining_balance'])
                ])
            rows.append(["الإجمالي", "", format_currency(total_fee_all), format_currency(total_paid_all), format_currency(total_remaining_all)])

            t = self._data_table(headers, rows, styles, col_widths=[100, 80, 80, 80, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eef2ff')),
                ('FONTNAME', (0, -1), (-1, -1), 'DejaVu-Bold'),
            ]))
            elements.append(t)
        else:
            elements.append(ar_para("لا يوجد مدرسين مرتبطين بهذا الطالب", styles['normal_center']))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath

    # =====================================================
    # تقرير المدرس PDF
    # =====================================================
    def generate_teacher_report(self, teacher_id: int) -> str:
        teacher_result = self.db.execute_query("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
        if not teacher_result:
            raise Exception("المدرس غير موجود")
        teacher = dict(teacher_result[0])

        balance_info = finance_service.calculate_teacher_balance(teacher_id)
        students_list = finance_service.get_teacher_students_list(teacher_id)
        recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit=20)

        filename = f"teacher_report_{teacher_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(TEACHER_PDFS_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        styles = self._get_styles()
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)

        elements = self._header(styles, "تقرير المدرس المالي")

        elements.append(self._info_table([
            ("اسم المدرس", teacher['name']),
            ("المادة", teacher['subject']),
            ("الأجر الكلي", format_currency(teacher['total_fee'])),
            ("عدد الطلاب", str(len(students_list))),
            ("ملاحظات", teacher['notes'] or '-'),
        ], styles))
        elements.append(Spacer(1, 10))

        elements.append(ar_para("الملخص المالي", styles['section']))
        elements.append(self._info_table([
            ("إجمالي الاستلامات", format_currency(balance_info['total_received'])),
            ("عدد الطلاب الدافعين", str(balance_info['paying_students_count'])),
            ("إجمالي خصم المعهد", format_currency(balance_info['institute_deduction'])),
            ("مستحق المدرس", format_currency(balance_info['teacher_due'])),
            ("إجمالي المسحوب", format_currency(balance_info['withdrawn_total'])),
            ("الرصيد المتبقي", format_currency(balance_info['remaining_balance'])),
        ], styles))
        elements.append(Spacer(1, 10))

        if students_list:
            elements.append(ar_para("قائمة الطلاب ودفعاتهم", styles['section']))
            headers = ["الطالب", "نوع الدراسة", "الحالة", "المدفوع", "المتبقي", "حالة الدفع"]
            rows = []
            for s in students_list:
                status = "دافع" if s['is_paying'] else "غير دافع"
                rows.append([
                    s['name'], s['study_type'],
                    s.get('status', 'مستمر'),
                    format_currency(s['paid_total']),
                    format_currency(s['remaining_balance']),
                    status
                ])
            elements.append(self._data_table(headers, rows, styles, col_widths=[80, 60, 60, 70, 70, 60]))

        if recent_withdrawals:
            elements.append(Spacer(1, 10))
            elements.append(ar_para("آخر السحوبات", styles['section']))
            headers = ["المبلغ", "التاريخ", "ملاحظات"]
            rows = [[format_currency(w['amount']), format_date(w['withdrawal_date']), w['notes'] or '-'] for w in recent_withdrawals]
            elements.append(self._data_table(headers, rows, styles, col_widths=[100, 100, 240]))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath

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
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # A5 بالعرض
        page_w, page_h = landscape(A4)
        receipt_w = page_w * 0.75
        receipt_h = page_h * 0.7

        styles = self._get_styles()
        styles['receipt_title'] = ParagraphStyle(
            'receipt_title', fontName='DejaVu-Bold', fontSize=16, alignment=1,
            textColor=PRIMARY, spaceAfter=6
        )
        styles['receipt_info'] = ParagraphStyle(
            'receipt_info', fontName='DejaVu', fontSize=10, alignment=2,
            textColor=colors.HexColor('#1e293b'), leading=18
        )
        styles['receipt_label'] = ParagraphStyle(
            'receipt_label', fontName='DejaVu', fontSize=10, alignment=2,
            textColor=TEXT_MUTED
        )

        doc = SimpleDocTemplate(
            filepath, pagesize=landscape((210*mm, 148*mm)),
            rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm
        )

        elements = []

        # عنوان الوصل
        elements.append(ar_para("وصل دفع رسمي", styles['receipt_title']))
        elements.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=8))

        # معلومات الوصل
        info_data = [
            ("اسم الطالب", installment['student_name']),
            ("اسم المدرس", installment['teacher_name']),
            ("المادة", installment['subject']),
            ("نوع القسط", installment['installment_type']),
            ("المبلغ المدفوع", format_currency(installment['amount'])),
            ("تاريخ الدفع", format_date(installment['payment_date'])),
            ("ملاحظات", installment['notes'] or '-'),
        ]

        table_data = []
        for label, value in info_data:
            table_data.append([
                ar_para(label, styles['receipt_label']),
                ar_para(value, styles['receipt_info'])
            ])

        t = Table(table_data, colWidths=[120, 350])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t)

        # التوقيع
        elements.append(Spacer(1, 25))
        now = datetime.now()
        elements.append(ar_para(f"التاريخ: {now.strftime('%Y/%m/%d')} - الوقت: {now.strftime('%H:%M')}", styles['small_center']))
        elements.append(HRFlowable(width="40%", thickness=0.5, color=colors.HexColor('#1e293b'), spaceBefore=30, spaceAfter=2))
        elements.append(ar_para("توقيع المسؤول", styles['small_center']))
        elements.append(Spacer(1, 10))
        elements.append(ar_para("نظام إدارة المعهد || HussamVision", styles['small_center']))

        doc.build(elements)
        return filepath

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

        styles = self._get_styles()
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)

        elements = self._header(styles, f"تقرير مادة: {subject_name}")
        elements.append(self._info_table([
            ("اسم المادة", subject_name),
            ("عدد المدرسين", str(len(teachers))),
        ], styles))
        elements.append(Spacer(1, 10))

        elements.append(ar_para("قائمة المدرسين", styles['section']))
        headers = ["#", "المدرس", "الأجر الكلي", "عدد الطلاب"]
        rows = []
        for i, t in enumerate(teachers, 1):
            cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            sc = cnt[0]['cnt'] if cnt else 0
            rows.append([str(i), t['name'], format_currency(t['total_fee']), str(sc)])
        elements.append(self._data_table(headers, rows, styles, col_widths=[30, 150, 100, 80]))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath

    def generate_all_subjects_report(self) -> str:
        subjects = self.db.execute_query("SELECT name FROM subjects ORDER BY name")
        if not subjects:
            raise Exception("لا توجد مواد")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"all_subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        styles = self._get_styles()
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)

        elements = self._header(styles, "تقرير شامل لجميع المواد")

        for subj in subjects:
            teachers = self.db.execute_query(
                "SELECT id, name, total_fee FROM teachers WHERE subject = %s ORDER BY name", (subj['name'],)
            )
            elements.append(ar_para(f"المادة: {subj['name']} ({len(teachers)} مدرس)", styles['section']))

            if teachers:
                headers = ["#", "المدرس", "الأجر", "الطلاب"]
                rows = []
                for i, t in enumerate(teachers, 1):
                    cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
                    sc = cnt[0]['cnt'] if cnt else 0
                    rows.append([str(i), t['name'], format_currency(t['total_fee']), str(sc)])
                elements.append(self._data_table(headers, rows, styles, col_widths=[30, 150, 100, 80]))
            else:
                elements.append(ar_para("لا يوجد مدرسين", styles['normal_center']))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
