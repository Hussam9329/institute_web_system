# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية - ReportLab + دعم عربي كامل
# تصميم RTL هندسي دقيق - محاذاة وهوامش وجداول محسوبة
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
    format_currency, format_date, format_report_datetime, format_report_date, format_report_time, APP_TITLE, BASE_DIR
)
from services.finance_service import finance_service
from database import Database


# ===== تسجيل الخطوط - DejaVu Sans (يدعم العربية + لاتيني) =====
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")
pdfmetrics.registerFont(TTFont('Calibri', os.path.join(FONT_DIR, 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('Calibri-Bold', os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')))

addMapping('Calibri', 0, 0, 'Calibri')
addMapping('Calibri', 1, 0, 'Calibri-Bold')


# ===== نظام الأبعاد الهندسي - محسوب بدقة =====
# أبعاد A4 بالـ points
A4_W, A4_H = A4  # (595.28, 841.89) pt

# هوامش دقيقة ومتناظرة
MARGIN_SIDE = 15 * mm   # 42.52 pt
MARGIN_TOP = 12 * mm    # 33.96 pt
MARGIN_BOTTOM = 18 * mm # 50.95 pt (مساحة للشريط السفلي)

# عرض المحتوى الفعلي (المنطقة المتاحة للمحتوى)
CONTENT_W = A4_W - 2 * MARGIN_SIDE  # 510.24 pt

# هوامش وصل الدفع (A5)
RECEIPT_MARGIN = 10 * mm
RECEIPT_CONTENT_W = A4_W - 2 * RECEIPT_MARGIN  # 538.58 pt

# نظام المسافات (مضاعفات قاعدة 3pt)
SP_XS = 3
SP_SM = 6
SP_MD = 10
SP_LG = 14
SP_XL = 20


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
CENTER = 1


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
    """شريط تذييل احترافي مع رقم صفحة واسم النظام"""
    def __init__(self, canvas, doc):
        self.canvas = canvas
        self.doc = doc

    def __call__(self, canvas, doc):
        canvas.saveState()

        # الشريط الرئيسي (سميك)
        canvas.setStrokeColor(C.PRIMARY)
        canvas.setLineWidth(2.5)
        x_left = MARGIN_SIDE
        x_right = A4_W - MARGIN_SIDE
        y_line = MARGIN_BOTTOM - 4 * mm
        canvas.line(x_left, y_line, x_right, y_line)

        # الشريط الثانوي (رفيع)
        canvas.setStrokeColor(C.ACCENT)
        canvas.setLineWidth(0.6)
        canvas.line(x_left, y_line - 1.5 * mm, x_right, y_line - 1.5 * mm)

        # رقم الصفحة - وسط
        canvas.setFont('Calibri', 7)
        canvas.setFillColor(C.MUTED)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(A4_W / 2, y_line - 5 * mm, str(page_num))

        # التاريخ - يسار
        canvas.setFont('Calibri', 6)
        canvas.drawString(x_left, y_line - 5 * mm, format_report_date())

        # اسم النظام - يمين
        canvas.setFont('Calibri', 6)
        canvas.drawRightString(x_right, y_line - 5 * mm, "HussamVision")

        canvas.restoreState()


class PDFService:
    """خدمة توليد تقارير PDF احترافية بدعم كامل للعربية و RTL - تصميم هندسي دقيق"""

    def __init__(self):
        self.db = Database()

    # ===== Helpers احترافية =====
    def _safe_text(self, value, fallback='-'):
        """تنظيف النصوص ومنع None والفراغات"""
        if value is None:
            return fallback
        s = str(value).strip()
        return s if s else fallback

    def _truncate(self, text, max_len=90):
        """قص ناعم للنص الطويل للحفاظ على الشكل"""
        s = self._safe_text(text, '')
        return s if len(s) <= max_len else (s[:max_len - 1] + '…')

    def _status_badge(self, text, kind='info'):
        """شارة حالة لعرض رسائل قصيرة بشكل احترافي"""
        color_map = {
            'info': (C.INFO_BG, C.INFO, C.INFO),
            'success': (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            'warning': (C.WARNING_BG, C.WARNING, C.WARNING),
            'danger': (C.DANGER_BG, C.DANGER, C.DANGER),
        }
        bg, fg, border = color_map.get(kind, color_map['info'])

        s = ParagraphStyle(
            f'badge_{kind}',
            fontName='Calibri-Bold', fontSize=8, alignment=CENTER,
            textColor=fg, leading=11
        )
        badge = Table([[ar_para(text, s)]], colWidths=[CONTENT_W])
        badge.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg),
            ('BOX', (0, 0), (-1, -1), 0.8, border),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        return badge

    # ===== أنماط الطباعة =====
    def _get_styles(self):
        """أنماط طباعة RTL بخط Calibri (DejaVu Sans)"""
        styles = {}

        styles['title'] = ParagraphStyle(
            'title', fontName='Calibri-Bold', fontSize=20, alignment=CENTER,
            textColor=C.WHITE, spaceAfter=2, leading=26
        )
        styles['subtitle'] = ParagraphStyle(
            'subtitle', fontName='Calibri', fontSize=10, alignment=CENTER,
            textColor=colors.HexColor('#93c5fd'), spaceAfter=0, leading=14
        )
        styles['report_title'] = ParagraphStyle(
            'report_title', fontName='Calibri-Bold', fontSize=15, alignment=RTL,
            textColor=C.PRIMARY, spaceBefore=4, spaceAfter=2, leading=20
        )
        styles['section'] = ParagraphStyle(
            'section', fontName='Calibri-Bold', fontSize=10, alignment=RTL,
            textColor=C.WHITE, spaceBefore=SP_SM, spaceAfter=0, leading=15,
            borderPadding=(5, 8, 5, 8)
        )
        styles['normal'] = ParagraphStyle(
            'normal', fontName='Calibri', fontSize=9, alignment=RTL,
            textColor=C.TEXT, leading=13
        )
        styles['normal_center'] = ParagraphStyle(
            'normal_center', fontName='Calibri', fontSize=9, alignment=CENTER,
            textColor=C.TEXT, leading=13
        )
        styles['bold'] = ParagraphStyle(
            'bold', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
            textColor=C.DARK, leading=13
        )
        styles['bold_center'] = ParagraphStyle(
            'bold_center', fontName='Calibri-Bold', fontSize=9, alignment=CENTER,
            textColor=C.DARK, leading=13
        )
        styles['small'] = ParagraphStyle(
            'small', fontName='Calibri', fontSize=7, alignment=RTL,
            textColor=C.MUTED, leading=10
        )
        styles['small_center'] = ParagraphStyle(
            'small_center', fontName='Calibri', fontSize=7, alignment=CENTER,
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
            'kpi_value', fontName='Calibri-Bold', fontSize=13, alignment=CENTER,
            textColor=C.DARK, leading=17
        )
        styles['kpi_label'] = ParagraphStyle(
            'kpi_label', fontName='Calibri', fontSize=7, alignment=CENTER,
            textColor=C.TEXT_SECONDARY, leading=10
        )
        styles['footer_text'] = ParagraphStyle(
            'footer_text', fontName='Calibri', fontSize=7, alignment=CENTER,
            textColor=C.MUTED, leading=10
        )
        styles['date_style'] = ParagraphStyle(
            'date_line', fontName='Calibri', fontSize=8, alignment=RTL,
            textColor=C.TEXT_SECONDARY, leading=11
        )
        return styles

    # ===== مكونات التصميم الهندسي - RTL =====

    def _build_header(self, styles, subtitle_text, report_type_icon=""):
        """رأس احترافي - عرض دقيق = CONTENT_W"""
        elements = []

        header_content = []
        if report_type_icon:
            header_content.append(ar_para(report_type_icon, ParagraphStyle(
                'icon', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
                textColor=C.HEADER_ACCENT, leading=13
            )))
        header_content.append(ar_para(APP_TITLE, styles['title']))
        header_content.append(ar_para(subtitle_text, styles['subtitle']))
        header_content.append(ar_para("تقارير مالية دقيقة • تنسيق احترافي • دعم RTL كامل", ParagraphStyle(
            'header_micro', fontName='Calibri', fontSize=7, alignment=CENTER,
            textColor=colors.HexColor('#bfdbfe'), leading=10
        )))

        header_table = Table([[header_content]], colWidths=[CONTENT_W])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.PRIMARY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)

        # شريط ألوان ثنائي
        half_w = CONTENT_W / 2
        accent_table = Table([['', '']], colWidths=[half_w, half_w])
        accent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), C.ACCENT),
            ('BACKGROUND', (1, 0), (1, 0), C.PRIMARY_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 1.5, C.ACCENT),
        ]))
        elements.append(accent_table)

        now = format_report_datetime()
        elements.append(Spacer(1, SP_SM))
        elements.append(ar_para(f"تاريخ التقرير: {now}", styles['date_style']))
        elements.append(Spacer(1, SP_MD))

        return elements

    def _build_kpi_cards(self, kpi_data, styles):
        """بطاقات ملونة للمؤشرات الرئيسية - أبعاد دقيقة ومحاذاة مثالية"""
        elements = []
        num_cards = len(kpi_data)
        if num_cards == 0:
            return elements

        card_width = CONTENT_W / num_cards
        gap = 3  # مسافة بين البطاقات

        cards = []
        for idx, (label, value, text_color, bg_color, border_color) in enumerate(kpi_data):
            inner_w = card_width - gap * 2

            val_style = ParagraphStyle(
                f'kv_{idx}', fontName='Calibri-Bold', fontSize=13, alignment=CENTER,
                textColor=text_color, leading=17
            )
            lbl_style = ParagraphStyle(
                f'kl_{idx}', fontName='Calibri', fontSize=7, alignment=CENTER,
                textColor=C.TEXT_SECONDARY, leading=10
            )

            card = Table(
                [[ar_para(str(value), val_style)],
                 [ar_para(label, lbl_style)]],
                colWidths=[inner_w]
            )
            card.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ('TOPPADDING', (0, 0), (0, 0), 8),
                ('BOTTOMPADDING', (0, -1), (0, -1), 7),
                ('TOPPADDING', (0, 1), (0, 1), 1),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('LINEABOVE', (0, 0), (-1, 0), 3, border_color),
                ('BOX', (0, 0), (-1, -1), 0.3, C.BORDER),
            ]))
            cards.append(card)

        kpi_row = Table([cards], colWidths=[card_width] * num_cards)
        kpi_row.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), gap / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), gap / 2),
        ]))
        elements.append(kpi_row)
        elements.append(Spacer(1, SP_MD))
        return elements

    def _build_section_header(self, title, styles, icon=""):
        """رأس قسم - عرض دقيق = CONTENT_W"""
        elements = []
        title_text = f"{icon}  {title}" if icon else title

        section_table = Table([[ar_para(title_text, styles['section'])]], colWidths=[CONTENT_W])
        section_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.ACCENT),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [3, 3, 3, 3]),
        ]))
        elements.append(section_table)
        elements.append(Spacer(1, SP_SM))
        return elements

    def _build_info_cards(self, data, styles, columns=2):
        """بطاقات معلومات منظمة - عرض محسوب بدقة"""
        elements = []
        card_width = CONTENT_W / columns
        gap = 3

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

            inner_w = card_width - gap * 2
            cell = Table(
                [[ar_para(label, lbl_style)],
                 [ar_para(self._safe_text(value, '-'), val_style)]],
                colWidths=[inner_w]
            )
            cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), C.WHITE),
                ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
                ('TOPPADDING', (0, 0), (0, 0), 6),
                ('BOTTOMPADDING', (0, -1), (0, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ]))

            current_row.append(cell)
            if len(current_row) == columns:
                rows_data.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < columns:
                inner_w = card_width - gap * 2
                empty = Table([['']], colWidths=[inner_w])
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
            ('LEFTPADDING', (0, 0), (-1, -1), gap / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), gap / 2),
            ('TOPPADDING', (0, 0), (-1, -1), gap / 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), gap / 2),
        ]))
        elements.append(info_table)
        return elements

    def _build_info_table(self, data, styles):
        """جدول معلومات احترافي - RTL (البيان يمين، القيمة يسار) - عرض دقيق"""
        col_label = CONTENT_W * 0.30  # 30% للبيان
        col_value = CONTENT_W * 0.70  # 70% للقيمة

        table_data = []
        for i, (label, value) in enumerate(data):
            lbl_style = ParagraphStyle(
                f'tl_{i}', fontName='Calibri', fontSize=9, alignment=RTL,
                textColor=C.TEXT_SECONDARY, leading=13
            )
            val_style = ParagraphStyle(
                f'tv_{i}', fontName='Calibri-Bold', fontSize=9, alignment=RTL,
                textColor=C.DARK, leading=13
            )
            table_data.append([
                ar_para(self._safe_text(value), val_style),
                ar_para(self._safe_text(label), lbl_style)
            ])

        t = Table(table_data, colWidths=[col_value, col_label], hAlign='RIGHT')
        style_cmds = [
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C.WHITE, C.LIGHT_BG]),
            ('BOX', (0, 0), (-1, -1), 1, C.PRIMARY_LIGHT),
            ('WORDWRAP', (0, 0), (-1, -1), 'RTL'),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

    def _build_data_table(self, headers, rows, styles, col_widths=None):
        """جدول بيانات احترافي - RTL
        يتم عكس ترتيب الأعمدة تلقائياً لعرض RTL صحيح.
        col_widths: تُمرّر بالترتيب المنطقي (متوافق مع headers) ويتم عكسها تلقائياً.
        """
        headers_rtl = list(reversed(headers))
        rows_rtl = [list(reversed(row)) for row in rows]

        if col_widths:
            col_widths_rtl = list(reversed(col_widths))
        else:
            col_widths_rtl = None

        header_style = ParagraphStyle(
            'th', fontName='Calibri-Bold', fontSize=8, alignment=CENTER,
            textColor=C.WHITE, leading=12
        )
        table_data = [[ar_para(h, header_style) for h in headers_rtl]]

        for r_idx, row in enumerate(rows_rtl):
            styled_row = []
            for c_idx, cell in enumerate(row):
                cell_style = ParagraphStyle(
                    f'td_{r_idx}_{c_idx}',
                    fontName='Calibri', fontSize=8, alignment=RTL,
                    textColor=C.TEXT, leading=12
                )
                styled_row.append(ar_para(self._safe_text(cell), cell_style))
            table_data.append(styled_row)

        t = Table(
            table_data,
            colWidths=col_widths_rtl,
            repeatRows=1,
            splitByRow=1,
            hAlign='RIGHT'
        )

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Calibri-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Calibri'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('LEFTPADDING', (0, 1), (-1, -1), 6),
            ('RIGHTPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, 0), 6),
            ('RIGHTPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.LIGHT_BG]),
            ('BOX', (0, 0), (-1, -1), 1, C.PRIMARY_LIGHT),
            ('WORDWRAP', (0, 0), (-1, -1), 'RTL'),
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
            rightMargin=MARGIN_SIDE, leftMargin=MARGIN_SIDE,
            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM
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
            ("اسم الطالب", self._truncate(student.get('name'), 40)),
            ("الرمز", self._safe_text(student.get('barcode'))),
            ("عدد المدرسين", str(num_teachers)),
            ("ملاحظات", self._truncate(student.get('notes') or 'لا توجد ملاحظات', 90)),
        ], styles, columns=2))
        elements.append(Spacer(1, SP_LG))

        elements.extend(self._build_section_header("التفاصيل المالية حسب المدرس", styles))

        if teachers_summary:
            headers = ["#", "المدرس", "المادة", "نوع الدراسة", "الأجر", "المدفوع", "المتبقي", "النسبة"]
            rows = []

            for i, ts in enumerate(teachers_summary, 1):
                pct = int((ts['paid_total'] / ts['total_fee']) * 100) if ts['total_fee'] > 0 else 0
                rows.append([
                    str(i),
                    self._truncate(ts.get('teacher_name'), 28),
                    self._truncate(ts.get('subject'), 22),
                    self._truncate(ts.get('study_type', 'حضوري'), 14),
                    format_currency(ts.get('total_fee', 0)),
                    format_currency(ts.get('paid_total', 0)),
                    format_currency(ts.get('remaining_balance', 0)),
                    f"{pct}%"
                ])

            total_pct = int((total_paid_all / total_fee_all) * 100) if total_fee_all > 0 else 0
            rows.append([
                "",
                "الإجمالي",
                "",
                "",
                format_currency(total_fee_all),
                format_currency(total_paid_all),
                format_currency(total_remaining_all),
                f"{total_pct}%"
            ])

            # أعمدة محسوبة بدقة: المجموع = CONTENT_W
            cw = [30, 95, 82, 63, 68, 68, 68, 36]
            assert sum(cw) == int(CONTENT_W), f"Column widths sum {sum(cw)} != {int(CONTENT_W)}"

            t = self._build_data_table(headers, rows, styles, col_widths=cw)

            total_cmds = [
                ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
                ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 8),
                ('TEXTCOLOR', (0, -1), (-1, -1), C.PRIMARY_DARK),
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, C.PRIMARY),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 7),
                ('TOPPADDING', (0, -1), (-1, -1), 7),
            ]
            t.setStyle(TableStyle(total_cmds))
            elements.append(t)
        else:
            elements.append(self._status_badge("لا يوجد مدرسين مرتبطين بهذا الطالب", "warning"))

        try:
            installments = self.db.execute_query('''
                SELECT i.*, t.name as teacher_name, t.subject
                FROM installments i
                JOIN teachers t ON i.teacher_id = t.id
                WHERE i.student_id = %s
                ORDER BY i.payment_date DESC
            ''', (student_id,))

            if installments:
                elements.append(Spacer(1, SP_LG))
                elements.extend(self._build_section_header("سجل المدفوعات التفصيلي", styles))

                inst_headers = ["#", "المدرس", "المادة", "المبلغ", "النوع", "التاريخ", "ملاحظات"]
                inst_rows = []
                for i, inst in enumerate(installments, 1):
                    inst_rows.append([
                        str(i),
                        self._truncate(inst.get('teacher_name'), 24),
                        self._truncate(inst.get('subject'), 20),
                        format_currency(inst.get('amount', 0)),
                        self._truncate(inst.get('installment_type'), 14),
                        format_date(inst.get('payment_date')),
                        self._truncate(inst.get('notes') or '-', 34)
                    ])

                cw = [30, 95, 78, 68, 60, 82, 97]
                elements.append(self._build_data_table(
                    inst_headers, inst_rows, styles, col_widths=cw
                ))
            else:
                elements.append(Spacer(1, SP_MD))
                elements.append(self._status_badge("لا يوجد سجل مدفوعات لهذا الطالب", "info"))
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
            rightMargin=MARGIN_SIDE, leftMargin=MARGIN_SIDE,
            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM
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
            ("اسم المدرس", self._truncate(teacher.get('name'), 40)),
            ("المادة", self._truncate(teacher.get('subject'), 28)),
            ("الأجر الكلي", format_currency(teacher.get('total_fee', 0))),
            ("عدد الطلاب", str(len(students_list))),
            ("ملاحظات", self._truncate(teacher.get('notes') or 'لا توجد ملاحظات', 90)),
        ], styles, columns=2))
        elements.append(Spacer(1, SP_LG))

        elements.extend(self._build_section_header("التفاصيل المالية", styles))
        elements.append(self._build_info_table([
            ("إجمالي الاستلامات", format_currency(balance_info['total_received'])),
            ("عدد الطلاب الدافعين", str(balance_info['paying_students_count'])),
            ("إجمالي خصم المعهد", format_currency(balance_info['institute_deduction'])),
            ("مستحق المدرس", format_currency(balance_info['teacher_due'])),
            ("إجمالي المسحوب", format_currency(balance_info['withdrawn_total'])),
            ("الرصيد المتبقي", format_currency(balance_info['remaining_balance'])),
        ], styles))
        elements.append(Spacer(1, SP_LG))

        if students_list:
            elements.extend(self._build_section_header("قائمة الطلاب ودفعاتهم", styles))
            headers = ["#", "الطالب", "نوع الدراسة", "الحالة", "المدفوع", "المتبقي", "حالة الدفع"]
            rows = []
            for i, s in enumerate(students_list, 1):
                status = "دافع" if s.get('is_paying') else "غير دافع"
                rows.append([
                    str(i),
                    self._truncate(s.get('name'), 30),
                    self._truncate(s.get('study_type', 'حضوري'), 14),
                    self._truncate(s.get('status', 'مستمر'), 14),
                    format_currency(s.get('paid_total', 0)),
                    format_currency(s.get('remaining_balance', 0)),
                    status
                ])
            cw = [28, 98, 72, 52, 80, 80, 100]
            elements.append(self._build_data_table(
                headers, rows, styles, col_widths=cw
            ))
        else:
            elements.append(self._status_badge("لا يوجد طلاب مرتبطين بهذا المدرس", "warning"))

        if recent_withdrawals:
            elements.append(Spacer(1, SP_LG))
            elements.extend(self._build_section_header("سجل السحوبات", styles))
            headers = ["#", "المبلغ", "التاريخ", "ملاحظات"]
            rows = [[
                str(i),
                format_currency(w.get('amount', 0)),
                format_date(w.get('withdrawal_date')),
                self._truncate(w.get('notes') or '-', 44)
            ] for i, w in enumerate(recent_withdrawals, 1)]
            cw = [30, 140, 140, 200]
            elements.append(self._build_data_table(
                headers, rows, styles, col_widths=cw
            ))
        else:
            elements.append(Spacer(1, SP_MD))
            elements.append(self._status_badge("لا يوجد سجل سحوبات حتى الآن", "info"))

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

        # استخدام finance_service لحساب القسط مع تطبيق الخصم
        from services.finance_service import finance_service
        balance = finance_service.calculate_student_teacher_balance(
            installment['student_id'], installment['teacher_id']
        )
        total_fee = balance['total_fee']           # القسط بعد الخصم
        original_fee = balance.get('original_fee', total_fee)  # القسط الأصلي قبل الخصم
        total_paid = balance['paid_total']
        remaining_balance = balance['remaining_balance']
        discount_info = balance.get('discount_info', {'discount_type': 'none', 'discount_value': 0, 'institute_waiver': 0})
        discount_amount = original_fee - total_fee if original_fee > total_fee else 0
        discount_type = discount_info.get('discount_type', 'none')
        discount_value = discount_info.get('discount_value', 0)

        filename = f"receipt_{installment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RECEIPTS_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        styles = self._get_styles()

        page_w, page_h = 210 * mm, 148 * mm
        usable_w = RECEIPT_CONTENT_W

        doc = SimpleDocTemplate(
            filepath, pagesize=(page_w, page_h),
            rightMargin=RECEIPT_MARGIN, leftMargin=RECEIPT_MARGIN,
            topMargin=8 * mm, bottomMargin=8 * mm,
        )

        elements = []

        # رأس الوصل - عرض دقيق = usable_w
        header_table = Table([[ar(APP_TITLE)]], colWidths=[usable_w])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, -1), C.WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Calibri-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(header_table)

        receipt_title_table = Table([[ar("وصل دفع رسمي")]], colWidths=[usable_w])
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

        elements.append(Spacer(1, SP_SM))

        card_gap = 3
        card_w = (usable_w - card_gap * 4) / 3  # 3 بطاقات مع 4 فواصل

        lbl_s = ParagraphStyle('rl', fontName='Calibri', fontSize=7, alignment=RTL, textColor=C.TEXT_SECONDARY, leading=10)
        val_s = ParagraphStyle('rv', fontName='Calibri-Bold', fontSize=9, alignment=RTL, textColor=C.DARK, leading=13)

        def _make_card(label, value, bg=C.WHITE, border=C.BORDER):
            cell = Table(
                [[ar_para(label, lbl_s)], [ar_para(self._safe_text(value), val_s)]],
                colWidths=[card_w]
            )
            cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg),
                ('BOX', (0, 0), (-1, -1), 0.8, border),
                ('TOPPADDING', (0, 0), (0, 0), 5),
                ('BOTTOMPADDING', (0, -1), (0, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            return cell

        row1 = [
            _make_card("اسم الطالب", self._truncate(installment.get('student_name'), 26)),
            _make_card("الرمز", installment.get('barcode')),
            _make_card("اسم المدرس", self._truncate(installment.get('teacher_name'), 26)),
        ]
        row2 = [
            _make_card("المادة", self._truncate(installment.get('subject'), 22)),
            _make_card("نوع القسط", self._truncate(installment.get('installment_type'), 16)),
            _make_card("تاريخ الدفع", format_date(installment.get('payment_date'))),
        ]

        info_grid = Table([row1, row2], colWidths=[card_w + card_gap * 2] * 3)
        info_grid.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('TOPPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), card_gap / 2),
        ]))
        elements.append(info_grid)

        # بطاقة المبلغ المدفوع
        elements.append(Spacer(1, SP_SM))
        amount_cell = Table(
            [[ar_para("المبلغ المدفوع", ParagraphStyle(
                'al', fontName='Calibri', fontSize=8, alignment=CENTER, textColor=C.WHITE, leading=12
            ))],
             [ar_para(format_currency(installment.get('amount', 0)), ParagraphStyle(
                'av', fontName='Calibri-Bold', fontSize=16, alignment=CENTER, textColor=C.WHITE, leading=22
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

        # الملخص المالي
        elements.append(Spacer(1, SP_SM))

        # معلومات الخصم إذا وُجد
        if discount_type != 'none' and discount_amount > 0:
            disc_lbl_s = ParagraphStyle('dl', fontName='Calibri-Bold', fontSize=8, alignment=CENTER, textColor=colors.HexColor('#92400e'), leading=12)
            disc_val_s = ParagraphStyle('dv', fontName='Calibri', fontSize=7, alignment=CENTER, textColor=colors.HexColor('#78350f'), leading=10)
            disc_text = ""
            if discount_type == 'percentage':
                disc_text = f"خصم {discount_value}% — القسط الأصلي: {format_currency(original_fee)} ← بعد الخصم: {format_currency(total_fee)} (توفير {format_currency(discount_amount)})"
            elif discount_type == 'custom':
                disc_text = f"خصم {discount_value}% — القسط الأصلي: {format_currency(original_fee)} ← بعد الخصم: {format_currency(total_fee)} (توفير {format_currency(discount_amount)})"
            elif discount_type == 'fixed':
                disc_text = f"خصم مبلغ ثابت {format_currency(discount_value)} — القسط الأصلي: {format_currency(original_fee)} ← بعد الخصم: {format_currency(total_fee)} (توفير {format_currency(discount_amount)})"
            elif discount_type == 'free':
                disc_text = "الطالب مجاني — معفي من الدفع بالكامل"
            disc_cell = Table(
                [[ar_para("معلومات الخصم", disc_lbl_s)], [ar_para(disc_text, disc_val_s)]],
                colWidths=[usable_w]
            )
            disc_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
                ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#fbbf24')),
                ('TOPPADDING', (0, 0), (0, 0), 4),
                ('BOTTOMPADDING', (0, -1), (0, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(disc_cell)
            elements.append(Spacer(1, SP_XS))

        if remaining_balance > 0:
            bal_color, bal_bg, bal_border = C.DANGER, C.DANGER_BG, C.DANGER
        elif remaining_balance == 0:
            bal_color, bal_bg, bal_border = C.SUCCESS, C.SUCCESS_BG, C.SUCCESS
        else:
            bal_color, bal_bg, bal_border = C.WARNING, C.WARNING_BG, C.WARNING

        fee_label = "القسط بعد الخصم" if (discount_type != 'none' and discount_amount > 0) else "القسط الكلي"
        summary_cards = [
            _make_card(fee_label, format_currency(total_fee), C.LIGHT_BG, C.BORDER),
            _make_card("إجمالي المدفوع", format_currency(total_paid), C.LIGHT_BG, C.BORDER),
        ]

        bal_val_s = ParagraphStyle('bv', fontName='Calibri-Bold', fontSize=11, alignment=CENTER, textColor=bal_color, leading=15)
        bal_lbl_s = ParagraphStyle('bl', fontName='Calibri-Bold', fontSize=8, alignment=CENTER, textColor=bal_color, leading=12)
        bal_card = Table(
            [[ar_para("المبلغ المتبقي", bal_lbl_s)], [ar_para(format_currency(remaining_balance), bal_val_s)]],
            colWidths=[card_w]
        )
        bal_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bal_bg),
            ('BOX', (0, 0), (-1, -1), 1.5, bal_border),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, -1), (0, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        summary_cards.append(bal_card)

        summary_table = Table([summary_cards], colWidths=[card_w + card_gap * 2] * 3)
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('TOPPADDING', (0, 0), (-1, -1), card_gap / 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), card_gap / 2),
        ]))
        elements.append(summary_table)

        has_notes = bool(installment.get('notes') and str(installment['notes']).strip())
        if has_notes:
            elements.append(Spacer(1, SP_XS))
            note_lbl = ParagraphStyle('nl', fontName='Calibri', fontSize=7, alignment=RTL, textColor=C.TEXT_SECONDARY, leading=10)
            note_val = ParagraphStyle('nv', fontName='Calibri', fontSize=8, alignment=RTL, textColor=C.TEXT, leading=12)
            note_cell = Table(
                [[ar_para("ملاحظات", note_lbl)], [ar_para(self._truncate(installment['notes'], 220), note_val)]],
                colWidths=[usable_w]
            )
            note_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), C.LIGHT_BG),
                ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
                ('TOPPADDING', (0, 0), (0, 0), 3),
                ('BOTTOMPADDING', (0, -1), (0, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ]))
            elements.append(note_cell)

        # التذييل
        elements.append(Spacer(1, SP_MD))
        now = datetime.now()
        footer_s = ParagraphStyle('ft', fontName='Calibri', fontSize=7, alignment=CENTER, textColor=C.MUTED, leading=10)
        elements.append(ar_para(f"التاريخ: {format_report_date()} - الوقت: {format_report_time()}", footer_s))
        elements.append(Spacer(1, SP_MD))
        elements.append(HRFlowable(width="35%", thickness=0.5, color=C.DARK, spaceBefore=0, spaceAfter=2))
        elements.append(ar_para("توقيع المسؤول", ParagraphStyle('sig', fontName='Calibri', fontSize=7, alignment=CENTER, textColor=C.TEXT_SECONDARY, leading=10)))
        elements.append(Spacer(1, SP_XS))
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
            rightMargin=MARGIN_SIDE, leftMargin=MARGIN_SIDE,
            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM
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
            ("اسم المادة", self._truncate(subject_name, 28), C.DARK, C.ACCENT_BG, C.ACCENT),
            ("عدد المدرسين", str(len(teachers)), C.INFO, C.INFO_BG, C.INFO),
            ("إجمالي الطلاب", str(total_students), C.PRIMARY, C.ACCENT_BG, C.PRIMARY),
            ("إجمالي الأجور", format_currency(total_fees), C.SUCCESS, C.SUCCESS_BG, C.SUCCESS),
        ], styles))

        elements.extend(self._build_section_header("قائمة المدرسين", styles))
        headers = ["#", "المدرس", "الأجر الكلي", "عدد الطلاب"]
        rows = []
        for i, (t, sc) in enumerate(teacher_data, 1):
            rows.append([str(i), self._truncate(t.get('name'), 36), format_currency(t.get('total_fee', 0)), str(sc)])

        cw = [30, 160, 240, 80]
        t = self._build_data_table(headers, rows, styles, col_widths=cw)

        total_cmds = [
            ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
            ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('TEXTCOLOR', (0, -1), (-1, -1), C.PRIMARY_DARK),
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
            rightMargin=MARGIN_SIDE, leftMargin=MARGIN_SIDE,
            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM
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
                    rows.append([str(i), self._truncate(t.get('name'), 36), format_currency(t.get('total_fee', 0)), str(sc)])

                cw = [30, 160, 240, 80]
                t = self._build_data_table(headers, rows, styles, col_widths=cw)

                total_cmds = [
                    ('BACKGROUND', (0, -1), (-1, -1), C.ACCENT_BG),
                    ('FONTNAME', (0, -1), (-1, -1), 'Calibri-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('TEXTCOLOR', (0, -1), (-1, -1), C.PRIMARY_DARK),
                    ('LINEABOVE', (0, -1), (-1, -1), 1.5, C.PRIMARY),
                ]
                t.setStyle(TableStyle(total_cmds))
                elements.append(t)
            else:
                elements.append(self._status_badge("لا يوجد مدرسين لهذه المادة", "warning"))

            if idx < len(subject_details) - 1:
                elements.append(Spacer(1, SP_MD))

        doc.build(elements, onFirstPage=PageNumberCanvas, onLaterPages=PageNumberCanvas)
        return filepath


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
