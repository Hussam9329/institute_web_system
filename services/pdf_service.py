# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية - ReportLab + دعم عربي
# متوافق مع Vercel Serverless
# ============================================

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
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
PRIMARY = colors.HexColor('#1e1b4b')
SECONDARY = colors.HexColor('#312e81')
ACCENT = colors.HexColor('#6366f1')
SUCCESS = colors.HexColor('#059669')
DANGER = colors.HexColor('#dc2626')
WARNING = colors.HexColor('#d97706')
LIGHT_BG = colors.HexColor('#f8fafc')
BORDER_COLOR = colors.HexColor('#e2e8f0')
TEXT_MUTED = colors.HexColor('#94a3b8')
WHITE = colors.white
DARK = colors.HexColor('#0f172a')


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
            'title', fontName='DejaVu-Bold', fontSize=20, alignment=2,
            textColor=PRIMARY, spaceAfter=4
        )
        styles['subtitle'] = ParagraphStyle(
            'subtitle', fontName='DejaVu', fontSize=11, alignment=2,
            textColor=SECONDARY, spaceAfter=6
        )
        styles['section'] = ParagraphStyle(
            'section', fontName='DejaVu-Bold', fontSize=13, alignment=2,
            textColor=WHITE, spaceBefore=12, spaceAfter=6,
            backColor=PRIMARY, borderPadding=8,
            leftIndent=6, rightIndent=6
        )
        styles['normal'] = ParagraphStyle(
            'normal', fontName='DejaVu', fontSize=10, alignment=2,
            textColor=DARK, leading=16
        )
        styles['normal_center'] = ParagraphStyle(
            'normal_center', fontName='DejaVu', fontSize=10, alignment=1,
            textColor=DARK, leading=16
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
        styles['badge_success'] = ParagraphStyle(
            'badge_success', fontName='DejaVu-Bold', fontSize=9, alignment=1,
            textColor=WHITE, backColor=SUCCESS, borderPadding=3
        )
        styles['badge_danger'] = ParagraphStyle(
            'badge_danger', fontName='DejaVu-Bold', fontSize=9, alignment=1,
            textColor=WHITE, backColor=DANGER, borderPadding=3
        )
        styles['badge_info'] = ParagraphStyle(
            'badge_info', fontName='DejaVu-Bold', fontSize=9, alignment=1,
            textColor=WHITE, backColor=ACCENT, borderPadding=3
        )
        return styles

    def _header(self, styles, subtitle_text):
        """إنشاء رأس التقرير مع شريط ملون"""
        elements = []
        
        # شريط علوي ملون
        header_data = [[ar(APP_TITLE)]]
        header_table = Table(header_data, colWidths=[520])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, -1), WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [4, 4, 0, 0]),
        ]))
        elements.append(header_table)
        
        # العنوان الفرعي
        elements.append(ar_para(subtitle_text, styles['subtitle']))
        elements.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=8))
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
        """إنشاء جدول معلومات احترافي"""
        table_data = [[ar_para("البيان", styles['normal']), ar_para("القيمة", styles['normal'])]]
        for label, value in data:
            table_data.append([
                ar_para(str(label), styles['normal']),
                ar_para(str(value), styles['normal'])
            ])
        t = Table(table_data, colWidths=[140, 350])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]))
        return t

    def _data_table(self, headers, rows, styles, col_widths=None):
        """إنشاء جدول بيانات احترافي"""
        table_data = [[ar_para(h, styles['normal']) for h in headers]]
        for row in rows:
            table_data.append([ar_para(str(c), styles['normal_center']) for c in row])

        t = Table(table_data, colWidths=col_widths)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

    # =====================================================
    # تقرير الطالب PDF - احترافي
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
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)

        teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
        
        # ===== رأس التقرير =====
        elements = self._header(styles, f"تقرير الطالب المالي")

        # ===== معلومات الطالب =====
        elements.append(Spacer(1, 8))
        elements.append(ar_para("معلومات الطالب", styles['section']))
        elements.append(Spacer(1, 6))
        
        elements.append(self._info_table([
            ("اسم الطالب", student['name']),
            ("الرمز", student['barcode']),
            ("ملاحظات", student['notes'] or '-'),
        ], styles))
        elements.append(Spacer(1, 12))

        # ===== الملخص المالي حسب المدرس =====
        elements.append(ar_para("الملخص المالي حسب المدرس", styles['section']))
        elements.append(Spacer(1, 6))
        
        if teachers_summary:
            headers = ["#", "المدرس", "المادة", "نوع الدراسة", "الحالة", "الأجر", "المدفوع", "المتبقي"]
            rows = []
            total_fee_all = total_paid_all = total_remaining_all = 0
            
            for i, ts in enumerate(teachers_summary, 1):
                total_fee_all += ts['total_fee']
                total_paid_all += ts['paid_total']
                total_remaining_all += ts['remaining_balance']
                rows.append([
                    str(i),
                    ts['teacher_name'], 
                    ts['subject'],
                    ts.get('study_type', 'حضوري'),
                    ts.get('status', 'مستمر'),
                    format_currency(ts['total_fee']),
                    format_currency(ts['paid_total']),
                    format_currency(ts['remaining_balance'])
                ])
            
            # صف الإجمالي
            rows.append([
                "", "الإجمالي", "", "", "",
                format_currency(total_fee_all), 
                format_currency(total_paid_all),
                format_currency(total_remaining_all)
            ])

            t = self._data_table(headers, rows, styles, col_widths=[20, 75, 60, 55, 45, 75, 75, 75])
            
            # تنسيق صف الإجمالي
            total_style_cmds = [
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eef2ff')),
                ('FONTNAME', (0, -1), (-1, -1), 'DejaVu-Bold'),
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, PRIMARY),
            ]
            t.setStyle(TableStyle(total_style_cmds))
            elements.append(t)
        else:
            elements.append(ar_para("لا يوجد مدرسين مرتبطين بهذا الطالب", styles['normal_center']))

        # ===== سجل المدفوعات التفصيلي =====
        try:
            installments = self.db.execute_query('''
                SELECT i.*, t.name as teacher_name, t.subject
                FROM installments i
                JOIN teachers t ON i.teacher_id = t.id
                WHERE i.student_id = %s
                ORDER BY i.payment_date DESC
            ''', (student_id,))
            
            if installments:
                elements.append(Spacer(1, 16))
                elements.append(ar_para("سجل المدفوعات التفصيلي", styles['section']))
                elements.append(Spacer(1, 6))
                
                inst_headers = ["#", "المدرس", "المبلغ", "النوع", "التاريخ", "ملاحظات"]
                inst_rows = []
                for i, inst in enumerate(installments, 1):
                    inst_rows.append([
                        str(i),
                        inst['teacher_name'],
                        format_currency(inst['amount']),
                        inst['installment_type'],
                        format_date(inst['payment_date']),
                        inst['notes'] or '-'
                    ])
                elements.append(self._data_table(inst_headers, inst_rows, styles, col_widths=[25, 90, 85, 70, 80, 140]))
        except:
            pass

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath

    # =====================================================
    # تقرير المدرس PDF - احترافي
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
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)

        # ===== رأس التقرير =====
        elements = self._header(styles, f"تقرير المدرس المالي")

        # ===== معلومات المدرس =====
        elements.append(Spacer(1, 8))
        elements.append(ar_para("معلومات المدرس", styles['section']))
        elements.append(Spacer(1, 6))
        
        elements.append(self._info_table([
            ("اسم المدرس", teacher['name']),
            ("المادة", teacher['subject']),
            ("الأجر الكلي", format_currency(teacher['total_fee'])),
            ("عدد الطلاب", str(len(students_list))),
            ("ملاحظات", teacher['notes'] or '-'),
        ], styles))
        elements.append(Spacer(1, 12))

        # ===== الملخص المالي =====
        elements.append(ar_para("الملخص المالي", styles['section']))
        elements.append(Spacer(1, 6))
        
        elements.append(self._info_table([
            ("إجمالي الاستلامات", format_currency(balance_info['total_received'])),
            ("عدد الطلاب الدافعين", str(balance_info['paying_students_count'])),
            ("إجمالي خصم المعهد", format_currency(balance_info['institute_deduction'])),
            ("مستحق المدرس", format_currency(balance_info['teacher_due'])),
            ("إجمالي المسحوب", format_currency(balance_info['withdrawn_total'])),
            ("الرصيد المتبقي", format_currency(balance_info['remaining_balance'])),
        ], styles))
        elements.append(Spacer(1, 12))

        # ===== قائمة الطلاب =====
        if students_list:
            elements.append(ar_para("قائمة الطلاب ودفعاتهم", styles['section']))
            elements.append(Spacer(1, 6))
            headers = ["#", "الطالب", "نوع الدراسة", "الحالة", "المدفوع", "المتبقي", "حالة الدفع"]
            rows = []
            for i, s in enumerate(students_list, 1):
                status = "دافع" if s['is_paying'] else "غير دافع"
                rows.append([
                    str(i),
                    s['name'], 
                    s.get('study_type', 'حضوري'),
                    s.get('status', 'مستمر'),
                    format_currency(s['paid_total']),
                    format_currency(s['remaining_balance']),
                    status
                ])
            elements.append(self._data_table(headers, rows, styles, col_widths=[20, 90, 55, 50, 70, 70, 60]))

        # ===== آخر السحوبات =====
        if recent_withdrawals:
            elements.append(Spacer(1, 12))
            elements.append(ar_para("آخر السحوبات", styles['section']))
            elements.append(Spacer(1, 6))
            headers = ["#", "المبلغ", "التاريخ", "ملاحظات"]
            rows = [[str(i), format_currency(w['amount']), format_date(w['withdrawal_date']), w['notes'] or '-'] for i, w in enumerate(recent_withdrawals, 1)]
            elements.append(self._data_table(headers, rows, styles, col_widths=[25, 100, 100, 265]))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath

    # =====================================================
    # وصل الدفع PDF - A5 بالعرض
    # =====================================================
    def generate_receipt(self, installment_id: int) -> str:
        installment_query = '''
            SELECT i.*, s.name as student_name, s.barcode, t.name as teacher_name, t.subject
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.id = %s
        '''
        installment_result = self.db.execute_query(installment_query, (installment_id,))
        if not installment_result:
            raise Exception("القسط غير موجود")
        installment = dict(installment_result[0])

        # Get teacher info and student's study type
        teacher_info_query = '''
            SELECT t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   st.study_type
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            LEFT JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE i.id = %s
        '''
        teacher_info_result = self.db.execute_query(teacher_info_query, (installment_id,))
        teacher_info = teacher_info_result[0] if teacher_info_result else {}
        study_type = teacher_info.get('study_type', 'حضوري')

        # Determine total fee based on study type
        if study_type == 'الكتروني' and teacher_info.get('fee_electronic', 0) > 0:
            total_fee = teacher_info['fee_electronic']
        elif study_type == 'مدمج' and teacher_info.get('fee_blended', 0) > 0:
            total_fee = teacher_info['fee_blended']
        elif study_type == 'حضوري' and teacher_info.get('fee_in_person', 0) > 0:
            total_fee = teacher_info['fee_in_person']
        else:
            total_fee = teacher_info.get('total_fee', 0)

        # Get total paid by this student for this teacher
        paid_query = '''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM installments
            WHERE student_id = %s AND teacher_id = %s
        '''
        paid_result = self.db.execute_query(paid_query, (installment['student_id'], installment['teacher_id']))
        total_paid = paid_result[0]['total'] if paid_result else 0
        remaining_balance = total_fee - total_paid

        filename = f"receipt_{installment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RECEIPTS_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # ── Receipt-specific compact styles ──
        styles = self._get_styles()
        lbl_style = ParagraphStyle(
            'r_lbl', fontName='DejaVu', fontSize=9, alignment=2,
            textColor=TEXT_MUTED, leading=13
        )
        val_style = ParagraphStyle(
            'r_val', fontName='DejaVu', fontSize=9, alignment=2,
            textColor=DARK, leading=13
        )
        val_bold_style = ParagraphStyle(
            'r_val_bold', fontName='DejaVu-Bold', fontSize=9, alignment=2,
            textColor=DARK, leading=13
        )
        sum_label_style = ParagraphStyle(
            'sum_lbl', fontName='DejaVu', fontSize=9, alignment=1,
            textColor=SECONDARY, leading=13
        )
        sum_value_style = ParagraphStyle(
            'sum_val', fontName='DejaVu-Bold', fontSize=10, alignment=1,
            textColor=DARK, leading=14
        )

        # Balance colour based on remaining amount
        if remaining_balance > 0:
            bal_color = DANGER
            bal_bg = colors.HexColor('#fef2f2')
            bal_border = DANGER
        elif remaining_balance == 0:
            bal_color = SUCCESS
            bal_bg = colors.HexColor('#f0fdf4')
            bal_border = SUCCESS
        else:
            bal_color = WARNING
            bal_bg = colors.HexColor('#fffbeb')
            bal_border = WARNING

        bal_style = ParagraphStyle(
            'bal_val', fontName='DejaVu-Bold', fontSize=11, alignment=1,
            textColor=bal_color, leading=15
        )
        bal_label_style = ParagraphStyle(
            'bal_lbl', fontName='DejaVu-Bold', fontSize=9, alignment=1,
            textColor=bal_color, leading=13
        )

        # ── A5 landscape (210 mm × 148 mm) ──
        doc = SimpleDocTemplate(
            filepath, pagesize=(210 * mm, 148 * mm),
            rightMargin=10 * mm, leftMargin=10 * mm,
            topMargin=8 * mm, bottomMargin=8 * mm,
        )

        elements = []

        # ═══════════════════════════════════════════
        # 1. Header bar
        # ═══════════════════════════════════════════
        header_data = [[ar("وصل دفع رسمي")]]
        header_table = Table(header_data, colWidths=[190 * mm])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, -1), WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROUNDEDCORNERS', [4, 4, 0, 0]),
        ]))
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=4))

        # ═══════════════════════════════════════════
        # 2. Basic info table (single-column, label : value)
        # ═══════════════════════════════════════════
        info_data = [
            ("اسم الطالب", installment['student_name']),
            ("الرمز", installment['barcode']),
            ("اسم المدرس", installment['teacher_name']),
            ("المادة", installment['subject']),
            ("نوع القسط", installment['installment_type']),
            ("المبلغ المدفوع", format_currency(installment['amount'])),
            ("تاريخ الدفع", format_date(installment['payment_date'])),
            # Financial summary – inserted before ملاحظات
            ("القسط الكلي", format_currency(total_fee)),
            ("إجمالي المدفوع", format_currency(total_paid)),
            ("المبلغ المتبقي", format_currency(remaining_balance)),
        ]

        # Add notes row only when notes exist
        has_notes = bool(installment.get('notes') and str(installment['notes']).strip())
        if has_notes:
            info_data.append(("ملاحظات", installment['notes']))

        # Build table rows with per-row styling
        financial_start = 7  # index of "القسط الكلي" row
        balance_idx = 9       # index of "المبلغ المتبقي" row

        table_rows = []
        for idx, (label, value) in enumerate(info_data):
            # Determine styles for this row
            if idx == balance_idx:
                # Remaining balance – bold + coloured
                row_lbl = bal_label_style
                row_val = bal_style
            elif financial_start <= idx <= balance_idx:
                # Other financial summary rows – bold values
                row_lbl = sum_label_style
                row_val = sum_value_style
            elif label == "المبلغ المدفوع":
                row_lbl = lbl_style
                row_val = val_bold_style
            else:
                row_lbl = lbl_style
                row_val = val_style

            table_rows.append([
                ar_para(label, row_lbl),
                ar_para(str(value), row_val),
            ])

        info_t = Table(table_rows, colWidths=[55 * mm, 135 * mm])

        # ── Table styling ──
        style_cmds = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]

        # Alternating backgrounds for basic-info rows (0–6)
        for i in range(financial_start):
            style_cmds.append(
                ('BACKGROUND', (0, i), (-1, i), WHITE if i % 2 == 0 else LIGHT_BG)
            )

        # Financial summary rows (7–9): light blue tint
        style_cmds.append(('BACKGROUND', (0, financial_start), (-1, balance_idx - 1),
                           colors.HexColor('#eef2ff')))

        # Balance row (9): coloured background
        style_cmds.append(('BACKGROUND', (0, balance_idx), (-1, balance_idx), bal_bg))

        # Thick separator line above financial summary
        style_cmds.append(('LINEABOVE', (0, financial_start), (-1, financial_start),
                           1.5, ACCENT))

        # Thick coloured border around balance value cell for emphasis
        style_cmds.append(('BOX', (1, balance_idx), (1, balance_idx), 2, bal_border))

        # Notes row background
        if has_notes:
            style_cmds.append(
                ('BACKGROUND', (0, balance_idx + 1), (-1, balance_idx + 1), LIGHT_BG)
            )

        info_t.setStyle(TableStyle(style_cmds))
        elements.append(info_t)

        # ═══════════════════════════════════════════
        # 3. Footer – date, signature, system name
        # ═══════════════════════════════════════════
        elements.append(Spacer(1, 10))
        now = datetime.now()
        elements.append(ar_para(
            f"التاريخ: {now.strftime('%Y/%m/%d')} - الوقت: {now.strftime('%H:%M')}",
            styles['small_center'],
        ))
        elements.append(HRFlowable(
            width="30%", thickness=0.5, color=DARK, spaceBefore=15, spaceAfter=2,
        ))
        elements.append(ar_para("توقيع المسؤول", styles['small_center']))
        elements.append(Spacer(1, 4))
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
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)

        elements = self._header(styles, f"تقرير مادة: {subject_name}")
        
        elements.append(Spacer(1, 8))
        elements.append(ar_para("معلومات المادة", styles['section']))
        elements.append(Spacer(1, 6))
        elements.append(self._info_table([
            ("اسم المادة", subject_name),
            ("عدد المدرسين", str(len(teachers))),
        ], styles))
        elements.append(Spacer(1, 12))

        elements.append(ar_para("قائمة المدرسين", styles['section']))
        elements.append(Spacer(1, 6))
        headers = ["#", "المدرس", "الأجر الكلي", "عدد الطلاب"]
        rows = []
        for i, t in enumerate(teachers, 1):
            cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            sc = cnt[0]['cnt'] if cnt else 0
            rows.append([str(i), t['name'], format_currency(t['total_fee']), str(sc)])
        elements.append(self._data_table(headers, rows, styles, col_widths=[25, 150, 100, 80]))

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
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)

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
                elements.append(self._data_table(headers, rows, styles, col_widths=[25, 150, 100, 80]))
            else:
                elements.append(ar_para("لا يوجد مدرسين", styles['normal_center']))

        elements.extend(self._footer(styles))
        doc.build(elements)
        return filepath


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
