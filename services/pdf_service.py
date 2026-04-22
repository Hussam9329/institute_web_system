# ============================================
# services/pdf_service.py
# خدمة توليد تقارير PDF احترافية
# ============================================

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from arabic_reshaper import reshape
from bidi.algorithm import get_display

from config import (
    STUDENT_PDFS_DIR, TEACHER_PDFS_DIR, RECEIPTS_DIR, REPORTS_DIR,
    format_currency, format_date, APP_TITLE, APP_VERSION
)
from services.finance_service import finance_service
from database import Database


class PDFService:
    """خدمة توليد تقارير PDF احترافية مع دعم اللغة العربية"""
    
    def __init__(self):
        self.db = Database()
        # تسجيل الخط العربي (إذا وجد)
        self._register_arabic_font()
    
    def _register_arabic_font(self):
        """تسجيل خط عربي للـ PDF"""
        # Try multiple font paths
        font_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts', 'arial.ttf'),
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('Arabic', font_path))
                    self.arabic_font = 'Arabic'
                    return
                except:
                    continue
        
        # Fallback
        self.arabic_font = 'Helvetica'
    
    def _arabic_text(self, text: str) -> str:
        """تحويل النص العربي للعرض الصحيح في PDF"""
        if not text:
            return ""
        
        try:
            # Convert Eastern Arabic numerals to Western for proper rendering
            text = str(text)
            
            reshaped_text = reshape(text)
            bidi_text = get_display(reshaped_text)
            return bidi_text
        except:
            return str(text)
    
    def _create_styles(self):
        """إنشاء أنماط النصوص العربية"""
        styles = getSampleStyleSheet()
        
        # عنوان رئيسي
        styles.add(ParagraphStyle(
            name='ArabicTitle',
            fontName=self.arabic_font,
            fontSize=24,
            leading=30,
            alignment=1,  # center
            spaceAfter=20,
            textColor=colors.HexColor('#1a237e')
        ))
        
        # عنوان فرعي
        styles.add(ParagraphStyle(
            name='ArabicSubtitle',
            fontName=self.arabic_font,
            fontSize=16,
            leading=22,
            alignment=1,
            spaceAfter=15,
            textColor=colors.HexColor('#303f9f')
        ))
        
        # نص عادي
        styles.add(ParagraphStyle(
            name='ArabicNormal',
            fontName=self.arabic_font,
            fontSize=11,
            leading=16,
            alignment=2,  # right for RTL
            spaceAfter=8
        ))
        
        # نص bold
        styles.add(ParagraphStyle(
            name='ArabicBold',
            fontName=self.arabic_font,
            fontSize=12,
            leading=18,
            alignment=2,
            spaceAfter=10,
            textColor=colors.HexColor('#212121')
        ))
        
        return styles
    
    def _add_header(self, story, styles, title: str):
        """إضافة رأس الصفحة"""
        # عنوان النظام
        story.append(Paragraph(self._arabic_text(APP_TITLE), styles['ArabicTitle']))
        story.append(Spacer(1, 5))
        
        # خط فاصل
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a237e')))
        story.append(Spacer(1, 15))
        
        # عنوان التقرير
        story.append(Paragraph(self._arabic_text(title), styles['ArabicSubtitle']))
        story.append(Spacer(1, 10))
    
    def _add_footer_info(self, story, styles):
        """إضافة معلومات أسفل التقرير"""
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Spacer(1, 10))
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        footer_text = f"نظام إدارة المعهد || HussamVision"
        story.append(Paragraph(self._arabic_text(footer_text), styles['ArabicNormal']))
        date_text = f"تاريخ الطباعة: {now}"
        story.append(Paragraph(self._arabic_text(date_text), styles['ArabicNormal']))
    
    # =====================================================
    # تقرير الطالب PDF
    # =====================================================
    
    def generate_student_report(self, student_id: int) -> str:
        """
        توليد تقرير PDF شامل للطالب
        
        Returns:
            str: مسار ملف PDF
        """
        # الحصول على بيانات الطالب
        student_query = "SELECT * FROM students WHERE id = %s"
        student_result = self.db.execute_query(student_query, (student_id,))
        
        if not student_result:
            raise Exception("الطالب غير موجود")
        
        student = dict(student_result[0])
        
        # إنشاء المجلدات إذا لم تكن موجودة
        os.makedirs(STUDENT_PDFS_DIR, exist_ok=True)
        
        # إنشاء اسم الملف
        filename = f"student_report_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(STUDENT_PDFS_DIR, filename)
        
        # إنشاء المستند
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        styles = self._create_styles()
        
        # ===== الرأس =====
        self._add_header(story, styles, "تقرير الطالب المالي")
        
        # ===== معلومات الطالب =====
        info_data = [
            [self._arabic_text("القيمة"), self._arabic_text("البيان")],
            [self._arabic_text(student['name']), self._arabic_text("اسم الطالب")],
            [self._arabic_text(student['barcode']), self._arabic_text("الرمز")],
            [self._arabic_text(student['study_type']), self._arabic_text("نوع الدراسة")],
            [self._arabic_text(student['notes'] if student['notes'] else '-'), self._arabic_text("ملاحظات")],
        ]
        
        info_table = Table(info_data, colWidths=[10*cm, 5*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdbdbd')),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # ===== المدرسين والدفعات =====
        teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
        
        if teachers_summary:
            story.append(Paragraph(self._arabic_text("الملخص المالي حسب المدرس"), styles['ArabicBold']))
            story.append(Spacer(1, 10))
            
            # جدول المدرسين
            headers = [
                self._arabic_text("المتبقي"),
                self._arabic_text("المدفوع"),
                self._arabic_text("الأجر الكلي"),
                self._arabic_text("المادة"),
                self._arabic_text("المدرس"),
            ]
            
            table_data = [headers]
            
            total_fee_all = 0
            total_paid_all = 0
            total_remaining_all = 0
            
            for ts in teachers_summary:
                row = [
                    self._arabic_text(format_currency(ts['remaining_balance'])),
                    self._arabic_text(format_currency(ts['paid_total'])),
                    self._arabic_text(format_currency(ts['total_fee'])),
                    self._arabic_text(ts['subject']),
                    self._arabic_text(ts['teacher_name']),
                ]
                table_data.append(row)
                
                total_fee_all += ts['total_fee']
                total_paid_all += ts['paid_total']
                total_remaining_all += ts['remaining_balance']
            
            # صف الإجمالي
            table_data.append([
                self._arabic_text(format_currency(total_remaining_all)),
                self._arabic_text(format_currency(total_paid_all)),
                self._arabic_text(format_currency(total_fee_all)),
                self._arabic_text("---"),
                self._arabic_text("الإجمالي"),
            ])
            
            teachers_table = Table(table_data, colWidths=[3.5*cm, 3.5*cm, 3.5*cm, 3*cm, 4*cm])
            teachers_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#303f9f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#fafafa')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8eaf6')),
                ('FONTNAME', (0, -1), (-1, -1), self.arabic_font),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#90a4ae')),
            ]))
            
            story.append(teachers_table)
        else:
            story.append(Paragraph(self._arabic_text("لا يوجد مدرسين مرتبطين بهذا الطالب"), styles['ArabicNormal']))
        
        # ===== التذييل =====
        self._add_footer_info(story, styles)
        
        # بناء PDF
        doc.build(story)
        
        return filepath
    
    # =====================================================
    # تقرير المدرس PDF
    # =====================================================
    
    def generate_teacher_report(self, teacher_id: int) -> str:
        """
        توليد تقرير PDF شامل للمدرس
        
        Returns:
            str: مسار ملف PDF
        """
        # الحصول على بيانات المدرس
        teacher_query = "SELECT * FROM teachers WHERE id = %s"
        teacher_result = self.db.execute_query(teacher_query, (teacher_id,))
        
        if not teacher_result:
            raise Exception("المدرس غير موجود")
        
        teacher = dict(teacher_result[0])
        
        # الحسابات المالية من خدمة المحاسبة المركزية
        due_info = finance_service.calculate_teacher_due(teacher_id)
        balance_info = finance_service.calculate_teacher_balance(teacher_id)
        students_list = finance_service.get_teacher_students_list(teacher_id)
        recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id)
        
        # إنشاء المجلدات إذا لم تكن موجودة
        os.makedirs(TEACHER_PDFS_DIR, exist_ok=True)
        
        # إنشاء اسم الملف
        filename = f"teacher_report_{teacher_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(TEACHER_PDFS_DIR, filename)
        
        # إنشاء المستند
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        styles = self._create_styles()
        
        # ===== الرأس =====
        self._add_header(story, styles, "تقرير المدرس المالي")
        
        # ===== معلومات المدرس =====
        info_data = [
            [self._arabic_text("القيمة"), self._arabic_text("البيان")],
            [self._arabic_text(teacher['name']), self._arabic_text("اسم المدرس")],
            [self._arabic_text(teacher['subject']), self._arabic_text("المادة")],
            [self._arabic_text(format_currency(teacher['total_fee'])), self._arabic_text("الأجر الكلي")],
            [self._arabic_text(str(len(students_list))), self._arabic_text("عدد الطلاب")],
            [self._arabic_text(teacher['notes'] if teacher['notes'] else '-'), self._arabic_text("ملاحظات")],
        ]
        
        info_table = Table(info_data, colWidths=[10*cm, 5*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdbdbd')),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # ===== الملخص المالي =====
        story.append(Paragraph(self._arabic_text("الملخص المالي"), styles['ArabicBold']))
        story.append(Spacer(1, 10))
        
        financial_data = [
            [self._arabic_text("القيمة"), self._arabic_text("البند")],
            [self._arabic_text(format_currency(due_info['total_received'])), self._arabic_text("إجمالي الاستلامات")],
            [self._arabic_text(str(due_info['paying_students_count'])), self._arabic_text("عدد الطلاب الدافعين")],
            [self._arabic_text(format_currency(due_info['institute_deduction'])), self._arabic_text("إجمالي خصم المعهد")],
            [self._arabic_text(format_currency(balance_info['teacher_due'])), self._arabic_text("مستحق المدرس")],
            [self._arabic_text(format_currency(balance_info['withdrawn_total'])), self._arabic_text("إجمالي المسحوب")],
            [self._arabic_text(format_currency(balance_info['remaining_balance'])), self._arabic_text("الرصيد المتبقي")],
        ]
        
        financial_table = Table(financial_data, colWidths=[8*cm, 7*cm])
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8f5e9')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#c8e6c9')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#81c784')),
        ]))
        
        story.append(financial_table)
        story.append(Spacer(1, 20))
        
        # ===== قائمة الطلاب =====
        if students_list:
            story.append(Paragraph(self._arabic_text("قائمة الطلاب ودفعاتهم"), styles['ArabicBold']))
            story.append(Spacer(1, 10))
            
            headers = [
                self._arabic_text("حالة الدفع"),
                self._arabic_text("المدفوع"),
                self._arabic_text("الحالة"),
                self._arabic_text("اسم الطالب"),
            ]
            
            table_data = [headers]
            
            for student in students_list:
                status_text = "دافع" if student['is_paying'] else "غير دافع"
                row = [
                    self._arabic_text(status_text),
                    self._arabic_text(format_currency(student['paid_total'])),
                    self._arabic_text(student['status']),
                    self._arabic_text(student['name']),
                ]
                table_data.append(row)
            
            students_table = Table(table_data, colWidths=[3.5*cm, 3.5*cm, 3*cm, 5*cm])
            students_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565c0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#64b5f6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#e3f2fd'), colors.white]),
            ]))
            
            story.append(students_table)
        
        # ===== آخر السحوبات =====
        if recent_withdrawals:
            story.append(Spacer(1, 15))
            story.append(Paragraph(self._arabic_text("آخر العمليات"), styles['ArabicBold']))
            story.append(Spacer(1, 10))
            
            headers = [
                self._arabic_text("ملاحظات"),
                self._arabic_text("المبلغ"),
                self._arabic_text("التاريخ"),
            ]
            
            table_data = [headers]
            
            for withdrawal in recent_withdrawals:
                row = [
                    self._arabic_text(withdrawal['notes'] if withdrawal['notes'] else '-'),
                    self._arabic_text(format_currency(withdrawal['amount'])),
                    self._arabic_text(format_date(withdrawal['withdrawal_date'])),
                ]
                table_data.append(row)
            
            withdrawals_table = Table(table_data, colWidths=[6*cm, 4*cm, 4*cm])
            withdrawals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c62828')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ef9a9a')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffebee'), colors.white]),
            ]))
            
            story.append(withdrawals_table)
        
        # ===== التذييل =====
        self._add_footer_info(story, styles)
        
        # بناء PDF
        doc.build(story)
        
        return filepath
    
    # =====================================================
    # وصل الدفع PDF
    # =====================================================
    
    def generate_receipt(self, installment_id: int) -> str:
        """
        توليد وصل دفع PDF
        
        Returns:
            str: مسار ملف PDF
        """
        # الحصول على بيانات القسط
        installment_query = '''
            SELECT i.*, s.name as student_name, t.name as teacher_name
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.id = %s
        '''
        installment_result = self.db.execute_query(installment_query, (installment_id,))
        
        if not installment_result:
            raise Exception("القسط غير موجود")
        
        installment = dict(installment_result[0])
        
        # إنشاء المجلدات إذا لم تكن موجودة
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        
        # إنشاء اسم الملف
        filename = f"receipt_{installment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RECEIPTS_DIR, filename)
        
        # إنشاء المستند
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=3*cm,
            leftMargin=3*cm,
            topMargin=3*cm,
            bottomMargin=3*cm
        )
        
        story = []
        styles = self._create_styles()
        
        # ===== العنوان =====
        story.append(Paragraph(self._arabic_text("وصل دفع رسمي"), styles['ArabicTitle']))
        story.append(Spacer(1, 5))
        story.append(HRFlowable(width="80%", thickness=3, color=colors.HexColor('#1a237e')))
        story.append(Spacer(1, 30))
        
        # ===== معلومات الدفع =====
        receipt_data = [
            [self._arabic_text("القيمة"), self._arabic_text("البيان")],
            [self._arabic_text(installment['student_name']), self._arabic_text("اسم الطالب")],
            [self._arabic_text(installment['teacher_name']), self._arabic_text("اسم المدرس")],
            [self._arabic_text(installment['installment_type']), self._arabic_text("نوع القسط")],
            [self._arabic_text(format_currency(installment['amount'])), self._arabic_text("المبلغ المدفوع")],
            [self._arabic_text(format_date(installment['payment_date'])), self._arabic_text("تاريخ الدفع")],
            [self._arabic_text(installment['notes'] if installment['notes'] else '-'), self._arabic_text("ملاحظات")],
        ]
        
        receipt_table = Table(receipt_data, colWidths=[10*cm, 5*cm])
        receipt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fafafa')),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#3949ab')),
        ]))
        
        story.append(receipt_table)
        story.append(Spacer(1, 40))
        
        # ===== التوقيع والتاريخ =====
        story.append(HRFlowable(width="60%", thickness=1, color=colors.grey))
        story.append(Spacer(1, 10))
        
        now = datetime.now()
        signature_text = f"التاريخ: {now.strftime('%Y/%m/%d')} - الوقت: {now.strftime('%H:%M')}"
        story.append(Paragraph(self._arabic_text(signature_text), styles['ArabicNormal']))
        
        story.append(Spacer(1, 30))
        story.append(Paragraph(self._arabic_text("توقيع المسؤول: ____________________"), styles['ArabicNormal']))
        
        # ===== التذييل =====
        self._add_footer_info(story, styles)
        
        # بناء PDF
        doc.build(story)
        
        return filepath

    # =====================================================
    # تقرير المادة PDF
    # =====================================================

    def generate_subject_report(self, subject_name: str) -> str:
        """توليد تقرير PDF لمادة معينة مع مدرسيها"""
        teachers = self.db.execute_query(
            "SELECT * FROM teachers WHERE subject = %s ORDER BY name", (subject_name,)
        )

        if not teachers:
            raise Exception("لا يوجد مدرسين لهذه المادة")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"subject_{subject_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = self._create_styles()

        self._add_header(story, styles, f"تقرير مادة: {subject_name}")

        info_data = [
            [self._arabic_text("القيمة"), self._arabic_text("البيان")],
            [self._arabic_text(subject_name), self._arabic_text("اسم المادة")],
            [self._arabic_text(str(len(teachers))), self._arabic_text("عدد المدرسين")],
        ]

        info_table = Table(info_data, colWidths=[10*cm, 5*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdbdbd')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))

        # Teachers list
        headers = [self._arabic_text("عدد الطلاب"), self._arabic_text("الأجر"), self._arabic_text("المدرس")]
        table_data = [headers]

        for t in teachers:
            cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            sc = cnt[0]['cnt'] if cnt else 0
            table_data.append([
                self._arabic_text(str(sc)),
                self._arabic_text(format_currency(t['total_fee'])),
                self._arabic_text(t['name']),
            ])

        t_table = Table(table_data, colWidths=[4*cm, 4*cm, 6*cm])
        t_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#303f9f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#90a4ae')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fafafa'), colors.white]),
        ]))
        story.append(t_table)

        self._add_footer_info(story, styles)
        doc.build(story)
        return filepath

    def generate_all_subjects_report(self) -> str:
        """توليد تقرير PDF شامل لجميع المواد مع مدرسيها"""
        subjects = self.db.execute_query("SELECT name FROM subjects ORDER BY name")

        if not subjects:
            raise Exception("لا توجد مواد")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"all_subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = self._create_styles()

        self._add_header(story, styles, "تقرير شامل لجميع المواد")

        for subj in subjects:
            teachers = self.db.execute_query(
                "SELECT id, name, total_fee FROM teachers WHERE subject = %s ORDER BY name", (subj['name'],)
            )

            story.append(Paragraph(self._arabic_text(f"المادة: {subj['name']}"), styles['ArabicBold']))
            story.append(Spacer(1, 8))

            headers = [self._arabic_text("عدد الطلاب"), self._arabic_text("الأجر"), self._arabic_text("المدرس")]
            table_data = [headers]

            for t in teachers:
                cnt = self.db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
                sc = cnt[0]['cnt'] if cnt else 0
                table_data.append([
                    self._arabic_text(str(sc)),
                    self._arabic_text(format_currency(t['total_fee'])),
                    self._arabic_text(t['name']),
                ])

            if not table_data:
                table_data.append([self._arabic_text("لا يوجد مدرسين"), '', ''])

            t_table = Table(table_data, colWidths=[4*cm, 4*cm, 6*cm])
            t_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#303f9f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.arabic_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#90a4ae')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fafafa'), colors.white]),
            ]))
            story.append(t_table)
            story.append(Spacer(1, 15))

        self._add_footer_info(story, styles)
        doc.build(story)
        return filepath


# ===== إنشاء نسخة واحدة من الخدمة =====
pdf_service = PDFService()
