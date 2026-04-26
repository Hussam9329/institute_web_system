# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية متقدمة - ReportLab + دعم عربي
# خط Calibri + تصميم RTL كامل
# ============================================

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

import arabic_reshaper
from bidi.algorithm import get_display

from config import (
    STUDENT_PDFS_DIR, TEACHER_PDFS_DIR, RECEIPTS_DIR, REPORTS_DIR,
    format_currency, format_date, APP_TITLE, BASE_DIR
)
from services.finance_service import finance_service
from database import Database


# ===== تسجيل خطوط Calibri (Carlito - بديل متوافق) =====
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")
pdfmetrics.registerFont(TTFont('Calibri', os.path.join(FONT_DIR, 'Calibri.ttf')))
pdfmetrics.registerFont(TTFont('Calibri-Bold', os.path.join(FONT_DIR, 'Calibri-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Calibri-Italic', os.path.join(FONT_DIR, 'Calibri-Italic.ttf')))
pdfmetrics.registerFont(TTFont('Calibri-BoldItalic', os.path.join(FONT_DIR, 'Calibri-BoldItalic.ttf')))

addMapping('Calibri', 0, 0, 'Calibri')
addMapping('Calibri', 1, 0, 'Calibri-Bold')
addMapping('Calibri', 0, 1, 'Calibri-Italic')
addMapping('Calibri', 1, 1, 'Calibri-BoldItalic')


# ===== نظام الألوان الحديث =====
class ThemeColors:
    PRIMARY = colors.HexColor('#1e3a5f')
    PRIMARY_LIGHT = colors.HexColor('#2d5a8e')
    PRIMARY_DARK = colors.HexColor('#0f1f33')
    ACCENT = colors.HexColor('#2563eb')
    ACCENT_LIGHT = colors.HexColor('#3b82f6')
    ACCENT_BG = colors.HexColor('#eff6ff')
    SECONDARY = colors.HexColor('#475569')
    MUTED = colors.HexColor('#94a3b8')
    BORDER = colors.HexColor('#cbd5e1')
    LIGHT_BG = colors.HexColor('#f8fafc')
    CARD_BG = colors.HexColor('#ffffff')
    SUBTLE_BG = colors.HexColor('#f1f5f9')
    SUCCESS = colors.HexColor('#059669')
    SUCCESS_BG = colors.HexColor('#ecfdf5')
    SUCCESS_LIGHT = colors.HexColor('#d1fae5')
    DANGER = colors.HexColor('#dc2626')
    DANGER_BG = colors.HexColor('#fef2f2')
    DANGER_LIGHT = colors.HexColor('#fee2e2')
    WARNING = colors.HexColor('#d97706')
    WARNING_BG = colors.HexColor('#fffbeb')
    WARNING_LIGHT = colors.HexColor('#fef3c7')
    INFO = colors.HexColor('#0284c7')
    INFO_BG = colors.HexColor('#f0f9ff')
    INFO_LIGHT = colors.HexColor('#e0f2fe')
    DARK = colors.HexColor('#0f172a')
    TEXT = colors.HexColor('#1e293b')
    TEXT_SECONDARY = colors.HexColor('#64748b')
    WHITE = colors.white
    HEADER_ACCENT = colors.HexColor('#60a5fa')

C = ThemeColors

# محاذاة RTL - اليمين
RTL = 2


def ar(text):
    """تحويل النص العربي لعرض صحيح في PDF"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def ar_para(text, style):
    """إنشاء فقرة عربية"""
    return Paragraph(ar(text), style)


class PageNumberCanvas:
    """إضافة أرقام الصفحات والشريط السفلي"""
    def __init__(self, canvas, doc):
        self.canvas = canvas
        self.doc = doc

    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(C.PRIMARY)
        canvas.setLineWidth(2)
        canvas.line(15*mm, 10*mm, A4[0] - 15*mm, 10*mm)
        canvas.setStrokeColor(C.ACCENT)
        canvas.setLineWidth(0.5)
        canvas.line(15*mm, 9*mm, A4[0] - 15*mm, 9*mm)
        canvas.setFont('Calibri', 7)
        canvas.setFillColor(C.MUTED)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(A4[0] / 2, 5*mm, str(page_num))
        canvas.setFont('Calibri', 6)
        system_text = "HussamVision"
        canvas.drawRightString(A4[0] - 15*mm, 5*mm, system_text)
        canvas.restoreState()


class PDFService:
    """خدمة توليد تقارير PDF احترافية متقدمة بدعم كامل للعربية و RTL"""

    def __init__(self):
        self.db = Database()

    # ===== أنماط الطباعة =====
    def _get_styles(self):
        """أنماط طباعة RTL بخط Calibri"""
        styles = {}
        styles['title'] = ParagraphStyle(
            'title', fontName='Calibri-Bold', fontSize=22, alignment=RTL,
            textColor=C.WHITE, spaceAfter=2, leading=28
        )
        styles['subtitle'] = ParagraphStyle(
            'subtitle', fontName='Calibri', fontSize=11, alignment=RTL,
            textColor=colors.HexColor('#93c5fd'), spaceAfter=0, leading=16
        )
        styles['report_title'] = ParagraphStyle(
            'report_title', fontName='Calibri-Bold', fontSize=16, alignment=RTL,
            textColor=C.PRIMARY, spaceBefore=4, spaceAfter=2, leading=22
        )
        styles['section'] = ParagraphStyle(
            'section', fontName='Calibri-Bold', fontSize=11, alignment=RTL,
            textColor=C.WHITE, spaceBefore=10, spaceAfter=0, leading=16,
            backColor=C.ACCENT, borderPadding=(6, 10, 6, 10)
        )
        styles['normal'] = ParagraphStyle(
            'normal', fontName='Calibri', fontSize=9, alignment=RTL,
            textColor=C.TEXT, leading=14
        )
        styles['normal_center'] = ParagraphStyle(
            'normal_center', fontName='Calibri', fontSize=9, alignment=1,
            textColor=C.TEXT, leading=14
        )
        styles['bold'] = ParagraphStyle(
            'bold', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
            textColor=C.DARK, leading=14
        )
        styles['bold_center'] = ParagraphStyle(
            'bold_center', fontName='Calibri-Bold', fontSize=9, alignment=1,
            textColor=C.DARK, leading=14
        )
        styles['small'] = ParagraphStyle(
            'small', fontName='Calibri', fontSize=7, alignment=RTL,
            textColor=C.MUTED, leading=10
        )
        styles['small_center'] = ParagraphStyle(
            'small_center', fontName='Calibri', fontSize=7, alignment=1,
            textColor=C.MUTED, leading=10
        )
        styles['success'] = ParagraphStyle(
            'success', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
            textColor=C.SUCCESS, leading=13
        )
        styles['danger'] = ParagraphStyle(
            'danger', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
            textColor=C.DANGER, leading=13
        )
        styles['warning'] = ParagraphStyle(
            'warning', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
            textColor=C.WARNING, leading=13
        )
        styles['kpi_value'] = ParagraphStyle(
            'kpi_value', fontName='Calibri-Bold', fontSize=14, alignment=RTL,
            textColor=C.DARK, leading=18
        )
        styles['kpi_label'] = ParagraphStyle(
            'kpi_label', fontName='Calibri', fontSize=7, alignment=RTL,
            textColor=C.TEXT_SECONDARY, leading=10
        )
        styles['footer_text'] = ParagraphStyle(
            'footer_text', fontName='Calibri', fontSize=7, alignment=1,
            textColor=C.MUTED, leading=10
        )
        return styles

    # ===== مكونات التصميم - RTL =====

    def _build_header(self, styles, subtitle_text, report_type_icon=""):
        """رأس احترافي متدرج الألوان - RTL"""
        elements = []

        header_content = []
        if report_type_icon:
            header_content.append(ar_para(report_type_icon, ParagraphStyle(
                'icon', fontName='Calibri-Bold', fontSize=10, alignment=RTL,
                textColor=C.HEADER_ACCENT, leading=14
            )))
        header_content.append(ar_para(APP_TITLE, styles['title']))
        header_content.append(ar_para(subtitle_text, styles['subtitle']))

        header_data = [[header_content]]
        header_table = Table(header_data, colWidths=[520])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.PRIMARY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)

        accent_data = [['', '']]
        accent_table = Table(accent_data, colWidths=[260, 260])
        accent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), C.ACCENT),
            ('BACKGROUND', (1, 0), (1, 0), C.PRIMARY_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 2, C.ACCENT),
        ]))
        elements.append(accent_table)

        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        elements.append(Spacer(1, 6))
        date_style = ParagraphStyle(
            'date_line', fontName='Calibri', fontSize=8, alignment=RTL,
            textColor=C.TEXT_SECONDARY, leading=12
        )
        elements.append(ar_para(f"تاريخ التقرير: {now}", date_style))
        elements.append(Spacer(1, 8))

        return elements

    def _build_kpi_cards(self, kpi_data, styles):
        """بطاقات ملونة للمؤشرات الرئيسية - RTL"""
        elements = []
        num_cards = len(kpi_data)
        if num_cards == 0:
            return elements

        total_width = 520
        card_width = total_width / num_cards
        spacing = 4

        cards = []
        for label, value, text_color, bg_color, border_color in kpi_data:
            val_style = ParagraphStyle(
                f'kv_{label}', fontName='Calibri-Bold', fontSize=13, alignment=RTL,
                textColor=text_color, leading=17
            )
            lbl_style = ParagraphStyle(
                f'kl_{label}', fontName='Calibri', fontSize=7, alignment=RTL,
                textColor=C.TEXT_SECONDARY, leading=10
            )

            card_content = Table(
                [[ar_para(str(value), val_style)],
                 [ar_para(label, lbl_style)]],
                colWidths=[card_width - spacing * 2]
            )
            card_content.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ('TOPPADDING', (0, 0), (0, 0), 8),
                ('BOTTOMPADDING', (0, -1), (0, -1), 8),
                ('TOPPADDING', (0, 1), (0, 1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('LINEABOVE', (0, 0), (-1, 0), 3, border_color),
            ]))
            cards.append(card_content)

        kpi_row = Table([cards], colWidths=[card_width] * num_cards)
        kpi_row.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), spacing / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), spacing / 2),
        ]))
        elements.append(kpi_row)
        elements.append(Spacer(1, 10))
        return elements

    def _build_section_header(self, title, styles, icon=""):
        """رأس قسم احترافي - RTL"""
        elements = []
        title_text = f"{icon}  {title}" if icon else title

        section_data = [[ar_para(title_text, styles['section'])]]
        section_table = Table(section_data, colWidths=[520])
        section_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.ACCENT),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [3, 3, 3, 3]),
        ]))
        elements.append(section_table)
        elements.append(Spacer(1, 6))
        return elements

    def _build_info_cards(self, data, styles, columns=2):
        """بطاقات معلومات منظمة - RTL"""
        elements = []
        card_width = 520 / columns
        padding = 4

        rows_data = []
        current_row = []
        for i, (label, value) in enumerate(data):
            lbl_style = ParagraphStyle(
                f'il_{i}', fontName='Calibri', fontSize=8, alignment=RTL,
                textColor=C.TEXT_SECONDARY, leading=11
            )
            val_style = ParagraphStyle(
                f'iv_{i}', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
                textColor=C.DARK, leading=13
            )

            cell = Table(
                [[ar_para(label, lbl_style)],
                 [ar_para(str(value), val_style)]],
                colWidths=[card_width - padding * 2]
            )
            cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), C.WHITE),
                ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
                ('TOPPADDING', (0, 0), (0, 0), 6),
                ('BOTTOMPADDING', (0, -1), (0, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))

            current_row.append(cell)
            if len(current_row) == columns:
                rows_data.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < columns:
                empty = Table([['']], colWidths=[card_width - padding * 2])
                empty.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), C.WHITE),
                    ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
                ]))
                current_row.append(empty)
            rows_data.append(current_row)

        info_table = Table(rows_data, colWidths=[card_width] * columns)
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), padding / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), padding / 2),
            ('TOPPADDING', (0, 0), (-1, -1), padding / 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), padding / 2),
        ]))
        elements.append(info_table)
        return elements

    def _build_info_table(self, data, styles):
        """جدول معلومات احترافي - RTL (البيان يمين، القيمة يسار)"""
        table_data = []
        for label, value in data:
            lbl_style = ParagraphStyle(
                f'tl_{label}', fontName='Calibri', fontSize=9, alignment=RTL,
                textColor=C.TEXT_SECONDARY, leading=13
            )
            val_style = ParagraphStyle(
                f'tv_{label}', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
                textColor=C.DARK, leading=13
            )
            # RTL: البيان يمين، القيمة يسار
            table_data.append([
                ar_para(str(value), val_style),
                ar_para(str(label), lbl_style)
            ])

        t = Table(table_data, colWidths=[360, 160])
        style_cmds = [
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C.WHITE, C.LIGHT_BG]),
            ('BOX', (0, 0), (-1, -1), 1, C.PRIMARY_LIGHT),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

    def _build_data_table(self, headers, rows, styles, col_widths=None):
        """جدول بيانات احترافي - RTL (الأعمدة معكوسة يميناً)"""
        # عكس ترتيب الأعمدة لـ RTL
        headers_rtl = list(reversed(headers))
        rows_rtl = [list(reversed(row)) for row in rows]

        # رأس الجدول
        header_style = ParagraphStyle(
            'th', fontName='Calibri-Bold', fontSize=8, alignment=RTL,
            textColor=C.WHITE, leading=12
        )
        table_data = [[ar_para(h, header_style) for h in headers_rtl]]

        # بيانات الصفوف
        for row in rows_rtl:
            styled_row = []
            for cell in row:
                cell_style = ParagraphStyle(
                    f'td_{cell}', fontName='Calibri', fontSize=8, alignment=RTL,
                    textColor=C.TEXT, leading=12
                )
                styled_row.append(ar_para(str(cell), cell_style))
            table_data.append(styled_row)

        t = Table(table_data, colWidths=col_widths)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Calibri-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Calibri'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 1), (-1, -1), 4),
            ('RIGHTPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.LIGHT_BG]),
            ('BOX', (0, 0), (-1, -1), 1, C.PRIMARY_LIGHT),
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
        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm
        )

        teachers_summary = finance_service.get_student_all_teachers_summary(student_id)

        total_fee_all = sum(ts['total_fee'] for ts in teachers_summary) if teachers_summary else 0
        total_paid_all = sum(ts['paid_total'] for ts in teachers_summary) if teachers_summary else 0
        total_remaining_all = sum(ts['remaining_balance'] for ts in teachers_summary) if teachers_summary else 0
        num_teachers = len(teachers_summary)
        payment_pct = int((total_paid_all / total_fee_all) * 100) if total_fee_all > 0 else 0

        elements = self._build_header(styles, "تقرير الطالب المالي الشامل", "")

        elements.extend(self._build_kpi_cards([
            ("إجمالي الأجور", format_currency(total_fee_all), C.DARK, C.ACCENT_BG, C.ACCENT),
            ("إجمالي المدفوع", format_currency(total_paid_all), C.SUCCESS, C.SUCCESS_BG, C.SUCCESS),
            ("إجمالي المتبقي", format_currency(total_remaining_all),
             C.DANGER if total_remaining_all > 0 else C.SUCCESS,
             C.DANGER_BG if total_remaining_all > 0 else C.SUCCESS_BG,
             C.DANGER if total_remaining_all > 0 else C.SUCCESS),
            ("نسبة الدفع", f"{payment_pct}%",
             C.SUCCESS if payment_pct >= 100 else C.WARNING,
             C.SUCCESS_BG if payment_pct >= 100 else C.WARNING_BG,
             C.SUCCESS if payment_pct >= 100 else C.WARNING),
        ], styles))

        elements.extend(self._build_section_header("معلومات الطالب", styles))
        elements.extend(self._build_info_cards([
            ("اسم الطالب", student['name']),
            ("الرمز", student['barcode']),
            ("عدد المدرسين", str(num_teachers)),
            ("ملاحظات", student['notes'] or 'لا توجد ملاحظات'),
        ], styles, columns=2))
        elements.append(Spacer(1, 12))

        elements.extend(self._build_section_header("التفاصيل المالية حسب المدرس", styles))

        if teachers_summary:
            headers = ["#", "المدرس", "المادة", "نوع الدراسة", "الأجر", "المدفوع", "المتبقي", "النسبة"]
            rows = []

            for i, ts in enumerate(teachers_summary, 1):
                pct = int((ts['paid_total'] / ts['total_fee']) * 100) if ts['total_fee'] > 0 else 0
                rows.append([
                    str(i),
                    ts['teacher_name'],
                    ts['subject'],
                    ts.get('study_type', 'حضوري'),
                    format_currency(ts['total_fee']),
                    format_currency(ts['paid_total']),
                    format_currency(ts['remaining_balance']),
                    f"{pct}%"
                ])

            total_pct = int((total_paid_all / total_fee_all) * 100) if total_fee_all > 0 else 0
            rows.append(["", "الإجمالي", "", "", format_currency(total_fee_all),
                        format_currency(total_paid_all), format_currency(total_remaining_all), f"{total_pct}%"])

            t = self._build_data_table(headers, rows, styles, col_widths=[40, 75, 75, 55, 52, 75, 75, 22])

            total_cmds = [
                ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
                ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 8),
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, C.PRIMARY),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
                ('TOPPADDING', (0, -1), (-1, -1), 8),
            ]
            t.setStyle(TableStyle(total_cmds))
            elements.append(t)
        else:
            elements.append(ar_para("لا يوجد مدرسين مرتبطين بهذا الطالب", styles['normal_center']))

        try:
            installments = self.db.execute_query('''
                SELECT i.*, t.name as teacher_name, t.subject
                FROM installments i
                JOIN teachers t ON i.teacher_id = t.id
                WHERE i.student_id = %s
                ORDER BY i.payment_date DESC
            ''', (student_id,))

            if installments:
                elements.append(Spacer(1, 14))
                elements.extend(self._build_section_header("سجل المدفوعات التفصيلي", styles))

                inst_headers = ["#", "المدرس", "المادة", "المبلغ", "النوع", "التاريخ", "ملاحظات"]
                inst_rows = []
                for i, inst in enumerate(installments, 1):
                    inst_rows.append([
                        str(i),
                        inst['teacher_name'],
                        inst['subject'],
                        format_currency(inst['amount']),
                        inst['installment_type'],
                        format_date(inst['payment_date']),
                        inst['notes'] or '-'
                    ])
                elements.append(self._build_data_table(
                    inst_headers, inst_rows, styles,
                    col_widths=[130, 68, 60, 70, 55, 75, 22]
                ))
        except Exception:
            pass

        doc.build(elements, onFirstPage=PageNumberCanvas, onLaterPages=PageNumberCanvas)
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
        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm
        )

        elements = self._build_header(styles, "تقرير المدرس المالي الشامل", "")

        remaining = balance_info['remaining_balance']
        elements.extend(self._build_kpi_cards([
            ("إجمالي الاستلامات", format_currency(balance_info['total_received']), C.DARK, C.ACCENT_BG, C.ACCENT),
            ("مستحق المدرس", format_currency(balance_info['teacher_due']), C.INFO, C.INFO_BG, C.INFO),
            ("إجمالي المسحوب", format_currency(balance_info['withdrawn_total']), C.WARNING, C.WARNING_BG, C.WARNING),
            ("الرصيد المتبقي", format_currency(remaining),
             C.DANGER if remaining > 0 else C.SUCCESS,
             C.DANGER_BG if remaining > 0 else C.SUCCESS_BG,
             C.DANGER if remaining > 0 else C.SUCCESS),
        ], styles))

        elements.extend(self._build_section_header("معلومات المدرس", styles))
        elements.extend(self._build_info_cards([
            ("اسم المدرس", teacher['name']),
            ("المادة", teacher['subject']),
            ("الأجر الكلي", format_currency(teacher['total_fee'])),
            ("عدد الطلاب", str(len(students_list))),
            ("ملاحظات", teacher['notes'] or 'لا توجد ملاحظات'),
        ], styles, columns=2))
        elements.append(Spacer(1, 12))

        elements.extend(self._build_section_header("التفاصيل المالية", styles))
        elements.append(self._build_info_table([
            ("إجمالي الاستلامات", format_currency(balance_info['total_received'])),
            ("عدد الطلاب الدافعين", str(balance_info['paying_students_count'])),
            ("إجمالي خصم المعهد", format_currency(balance_info['institute_deduction'])),
            ("مستحق المدرس", format_currency(balance_info['teacher_due'])),
            ("إجمالي المسحوب", format_currency(balance_info['withdrawn_total'])),
            ("الرصيد المتبقي", format_currency(balance_info['remaining_balance'])),
        ], styles))
        elements.append(Spacer(1, 12))

        if students_list:
            elements.extend(self._build_section_header("قائمة الطلاب ودفعاتهم", styles))
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
            elements.append(self._build_data_table(
                headers, rows, styles,
                col_widths=[55, 72, 72, 50, 55, 95, 22]
            ))

        if recent_withdrawals:
            elements.append(Spacer(1, 12))
            elements.extend(self._build_section_header("سجل السحوبات", styles))
            headers = ["#", "المبلغ", "التاريخ", "ملاحظات"]
            rows = [[str(i), format_currency(w['amount']), format_date(w['withdrawal_date']), w['notes'] or '-']
                    for i, w in enumerate(recent_withdrawals, 1)]
            elements.append(self._build_data_table(
                headers, rows, styles,
                col_widths=[265, 100, 100, 25]
            ))

        doc.build(elements, onFirstPage=PageNumberCanvas, onLaterPages=PageNumberCanvas)
        return filepath

    # =====================================================
    # وصل الدفع PDF - RTL
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

        if study_type == 'الكتروني' and teacher_info.get('fee_electronic', 0) > 0:
            total_fee = teacher_info['fee_electronic']
        elif study_type == 'مدمج' and teacher_info.get('fee_blended', 0) > 0:
            total_fee = teacher_info['fee_blended']
        elif study_type == 'حضوري' and teacher_info.get('fee_in_person', 0) > 0:
            total_fee = teacher_info['fee_in_person']
        else:
            total_fee = teacher_info.get('total_fee', 0)

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

        styles = self._get_styles()

        page_w, page_h = 210 * mm, 148 * mm
        usable_w = page_w - 20 * mm

        doc = SimpleDocTemplate(
            filepath, pagesize=(page_w, page_h),
            rightMargin=10*mm, leftMargin=10*mm,
            topMargin=8*mm, bottomMargin=8*mm,
        )

        elements = []

        # رأس الوصل
        header_data = [[ar(APP_TITLE)]]
        header_table = Table(header_data, colWidths=[usable_w])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, -1), C.WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Calibri-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 13),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(header_table)

        receipt_title_data = [[ar("وصل دفع رسمي")]]
        receipt_title_table = Table(receipt_title_data, colWidths=[usable_w])
        receipt_title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.ACCENT),
            ('TEXTCOLOR', (0, 0), (-1, -1), C.WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Calibri-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(receipt_title_table)

        # بطاقات المعلومات - RTL
        elements.append(Spacer(1, 6))

        card_w = usable_w / 3 - 3
        lbl_s = ParagraphStyle('rl', fontName='Calibri', fontSize=7, alignment=RTL, textColor=C.TEXT_SECONDARY, leading=10)
        val_s = ParagraphStyle('rv', fontName='Calibri-Bold', fontSize=9, alignment=RTL, textColor=C.DARK, leading=13)

        def _make_card(label, value, bg=C.WHITE, border=C.BORDER):
            cell = Table(
                [[ar_para(label, lbl_s)], [ar_para(str(value), val_s)]],
                colWidths=[card_w]
            )
            cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg),
                ('BOX', (0, 0), (-1, -1), 0.8, border),
                ('TOPPADDING', (0, 0), (0, 0), 4),
                ('BOTTOMPADDING', (0, -1), (0, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            return cell

        row1 = [
            _make_card("اسم الطالب", installment['student_name']),
            _make_card("الرمز", installment['barcode']),
            _make_card("اسم المدرس", installment['teacher_name']),
        ]
        row2 = [
            _make_card("المادة", installment['subject']),
            _make_card("نوع القسط", installment['installment_type']),
            _make_card("تاريخ الدفع", format_date(installment['payment_date'])),
        ]

        info_grid = Table([row1, row2], colWidths=[card_w + 3] * 3)
        info_grid.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ]))
        elements.append(info_grid)

        # بطاقة المبلغ المدفوع
        elements.append(Spacer(1, 4))
        amount_cell = Table(
            [[ar_para("المبلغ المدفوع", ParagraphStyle(
                'al', fontName='Calibri', fontSize=8, alignment=RTL, textColor=C.WHITE, leading=12
            ))],
             [ar_para(format_currency(installment['amount']), ParagraphStyle(
                'av', fontName='Calibri-Bold', fontSize=16, alignment=RTL, textColor=C.WHITE, leading=22
            ))]],
            colWidths=[usable_w]
        )
        amount_cell.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.ACCENT),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, -1), (0, -1), 7),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]))
        elements.append(amount_cell)

        # الملخص المالي - RTL
        elements.append(Spacer(1, 4))

        if remaining_balance > 0:
            bal_color, bal_bg, bal_border = C.DANGER, C.DANGER_BG, C.DANGER
        elif remaining_balance == 0:
            bal_color, bal_bg, bal_border = C.SUCCESS, C.SUCCESS_BG, C.SUCCESS
        else:
            bal_color, bal_bg, bal_border = C.WARNING, C.WARNING_BG, C.WARNING

        summary_cards = [
            _make_card("القسط الكلي", format_currency(total_fee), C.LIGHT_BG, C.BORDER),
            _make_card("إجمالي المدفوع", format_currency(total_paid), C.LIGHT_BG, C.BORDER),
        ]

        bal_val_s = ParagraphStyle('bv', fontName='Calibri-Bold', fontSize=11, alignment=RTL, textColor=bal_color, leading=15)
        bal_lbl_s = ParagraphStyle('bl', fontName='Calibri-Bold', fontSize=8, alignment=RTL, textColor=bal_color, leading=12)
        bal_card = Table(
            [[ar_para("المبلغ المتبقي", bal_lbl_s)], [ar_para(format_currency(remaining_balance), bal_val_s)]],
            colWidths=[card_w]
        )
        bal_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bal_bg),
            ('BOX', (0, 0), (-1, -1), 1.5, bal_border),
            ('TOPPADDING', (0, 0), (0, 0), 4),
            ('BOTTOMPADDING', (0, -1), (0, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        summary_cards.append(bal_card)

        summary_table = Table([summary_cards], colWidths=[card_w + 3] * 3)
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ]))
        elements.append(summary_table)

        has_notes = bool(installment.get('notes') and str(installment['notes']).strip())
        if has_notes:
            elements.append(Spacer(1, 3))
            note_lbl = ParagraphStyle('nl', fontName='Calibri', fontSize=7, alignment=RTL, textColor=C.TEXT_SECONDARY, leading=10)
            note_val = ParagraphStyle('nv', fontName='Calibri', fontSize=8, alignment=RTL, textColor=C.TEXT, leading=12)
            note_cell = Table(
                [[ar_para("ملاحظات", note_lbl)], [ar_para(installment['notes'], note_val)]],
                colWidths=[usable_w]
            )
            note_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), C.LIGHT_BG),
                ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
                ('TOPPADDING', (0, 0), (0, 0), 3),
                ('BOTTOMPADDING', (0, -1), (0, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(note_cell)

        # التذييل
        elements.append(Spacer(1, 8))
        now = datetime.now()
        footer_s = ParagraphStyle('ft', fontName='Calibri', fontSize=7, alignment=RTL, textColor=C.MUTED, leading=10)
        elements.append(ar_para(f"التاريخ: {now.strftime('%Y/%m/%d')} - الوقت: {now.strftime('%H:%M')}", footer_s))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="35%", thickness=0.5, color=C.DARK, spaceBefore=0, spaceAfter=2))
        elements.append(ar_para("توقيع المسؤول", ParagraphStyle('sig', fontName='Calibri', fontSize=7, alignment=1, textColor=C.TEXT_SECONDARY, leading=10)))
        elements.append(Spacer(1, 4))
        elements.append(ar_para("نظام إدارة المعهد || HussamVision", footer_s))

        doc.build(elements)
        return filepath

    # =====================================================
    # تقرير المادة PDF - RTL
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
        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm
        )

        elements = self._build_header(styles, f"تقرير مادة: {subject_name}", "")

        total_students = 0
        total_fees = 0
        teacher_data = []
        for t in teachers:
            cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            sc = cnt[0]['cnt'] if cnt else 0
            total_students += sc
            total_fees += t['total_fee']
            teacher_data.append((t, sc))

        elements.extend(self._build_kpi_cards([
            ("اسم المادة", subject_name, C.DARK, C.ACCENT_BG, C.ACCENT),
            ("عدد المدرسين", str(len(teachers)), C.INFO, C.INFO_BG, C.INFO),
            ("إجمالي الطلاب", str(total_students), C.PRIMARY, C.ACCENT_BG, C.PRIMARY),
            ("إجمالي الأجور", format_currency(total_fees), C.SUCCESS, C.SUCCESS_BG, C.SUCCESS),
        ], styles))

        elements.extend(self._build_section_header("قائمة المدرسين", styles))
        headers = ["#", "المدرس", "الأجر الكلي", "عدد الطلاب"]
        rows = []
        for i, (t, sc) in enumerate(teacher_data, 1):
            rows.append([str(i), t['name'], format_currency(t['total_fee']), str(sc)])

        t = self._build_data_table(headers, rows, styles, col_widths=[100, 120, 180, 30])

        total_cmds = [
            ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
            ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, C.PRIMARY),
        ]
        t.setStyle(TableStyle(total_cmds))
        elements.append(t)

        doc.build(elements, onFirstPage=PageNumberCanvas, onLaterPages=PageNumberCanvas)
        return filepath

    # =====================================================
    # تقرير شامل لجميع المواد PDF - RTL
    # =====================================================
    def generate_all_subjects_report(self) -> str:
        subjects = self.db.execute_query("SELECT name FROM subjects ORDER BY name")
        if not subjects:
            raise Exception("لا توجد مواد")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"all_subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        styles = self._get_styles()
        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm
        )

        total_subjects = len(subjects)
        total_teachers = 0
        total_students = 0
        total_fees = 0

        subject_details = []
        for subj in subjects:
            teachers = self.db.execute_query(
                "SELECT id, name, total_fee FROM teachers WHERE subject = %s ORDER BY name", (subj['name'],)
            )
            subj_students = 0
            subj_fees = 0
            teacher_list = []
            for t in teachers:
                cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
                sc = cnt[0]['cnt'] if cnt else 0
                subj_students += sc
                subj_fees += t['total_fee']
                teacher_list.append((t, sc))

            total_teachers += len(teachers)
            total_students += subj_students
            total_fees += subj_fees
            subject_details.append({
                'name': subj['name'],
                'teachers': teacher_list,
                'student_count': subj_students,
                'fee_total': subj_fees,
            })

        elements = self._build_header(styles, "تقرير شامل لجميع المواد", "")

        elements.extend(self._build_kpi_cards([
            ("عدد المواد", str(total_subjects), C.DARK, C.ACCENT_BG, C.ACCENT),
            ("عدد المدرسين", str(total_teachers), C.INFO, C.INFO_BG, C.INFO),
            ("إجمالي الطلاب", str(total_students), C.PRIMARY, C.ACCENT_BG, C.PRIMARY),
            ("إجمالي الأجور", format_currency(total_fees), C.SUCCESS, C.SUCCESS_BG, C.SUCCESS),
        ], styles))

        for idx, subj in enumerate(subject_details):
            elements.extend(self._build_section_header(
                f"المادة: {subj['name']} ({len(subj['teachers'])} مدرس)", styles
            ))

            if subj['teachers']:
                headers = ["#", "المدرس", "الأجر", "الطلاب"]
                rows = []
                for i, (t, sc) in enumerate(subj['teachers'], 1):
                    rows.append([str(i), t['name'], format_currency(t['total_fee']), str(sc)])

                t = self._build_data_table(headers, rows, styles, col_widths=[100, 120, 180, 30])

                total_cmds = [
                    ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
                    ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('LINEABOVE', (0, -1), (-1, -1), 1.5, C.PRIMARY),
                ]
                t.setStyle(TableStyle(total_cmds))
                elements.append(t)
            else:
                elements.append(ar_para("لا يوجد مدرسين", styles['normal_center']))

            if idx < len(subject_details) - 1:
                elements.append(Spacer(1, 8))

        doc.build(elements, onFirstPage=PageNumberCanvas, onLaterPages=PageNumberCanvas)
        return filepath


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
