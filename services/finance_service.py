# ============================================
# services/finance_service.py
# المحاسبة المركزية - الدوال المالية الموحدة
# 
# مهم جداً: كل الحسابات المالية يجب أن تتم هنا فقط!
# لا تكتب أي معادلة مالية في أي مكان آخر من النظام!
# ============================================

from typing import List, Dict, Any, Optional
from database import Database
from config import format_currency


class FinanceService:
    """خدمة المحاسبة المركزية - المصدر الوحيد للحسابات المالية"""
    
    def __init__(self):
        pass  # لا نحفظ اتصال في الـ constructor لأنه serverless
    
    @property
    def db(self):
        """الحصول على نسخة Database جديدة عند كل طلب"""
        return Database()
    
    # =====================================================
    # دوال حسابات الطلاب
    # =====================================================
    
    def get_student_paid_total(self, student_id: int, teacher_id: int) -> int:
        """
        حساب مجموع ما دفعه طالب لمدرس معين
        
        Args:
            student_id: رقم الطالب
            teacher_id: رقم المدرس
            
        Returns:
            int: مجموع المدفوعات (بالدينار الكامل)
        """
        query = '''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM installments
            WHERE student_id = %s AND teacher_id = %s
        '''
        result = self.db.execute_query(query, (student_id, teacher_id))
        
        if result and len(result) > 0:
            return result[0]['total'] if result[0]['total'] else 0
        return 0
    
    def calculate_student_teacher_balance(self, student_id: int, teacher_id: int) -> Dict[str, Any]:
        """حساب الرصيد المتبقي - يستخدم القسط حسب نوع الدراسة"""
        db = self.db
        
        # الحصول على معلومات المدرس
        query = '''
            SELECT total_fee, fee_in_person, fee_electronic, fee_blended
            FROM teachers WHERE id = %s
        '''
        result = db.execute_query(query, (teacher_id,))
        
        if not result:
            return {'total_fee': 0, 'paid_total': 0, 'remaining_balance': 0}
        
        t = result[0]
        
        # الحصول على نوع الدراسة من جدول الربط
        link_query = '''
            SELECT study_type FROM student_teacher 
            WHERE student_id = %s AND teacher_id = %s
        '''
        link_result = db.execute_query(link_query, (student_id, teacher_id))
        study_type = 'حضوري'
        if link_result:
            study_type = link_result[0].get('study_type', 'حضوري')
        
        # تحديد القسط حسب نوع الدراسة
        if study_type == 'الكتروني' and t.get('fee_electronic', 0) > 0:
            total_fee = t['fee_electronic']
        elif study_type == 'مدمج' and t.get('fee_blended', 0) > 0:
            total_fee = t['fee_blended']
        elif study_type == 'حضوري' and t.get('fee_in_person', 0) > 0:
            total_fee = t['fee_in_person']
        else:
            total_fee = t['total_fee']
        
        paid_total = self.get_student_paid_total(student_id, teacher_id)
        remaining_balance = total_fee - paid_total
        
        return {
            'total_fee': total_fee,
            'paid_total': paid_total,
            'remaining_balance': remaining_balance
        }
    
    def get_student_all_teachers_summary(self, student_id: int) -> List[Dict[str, Any]]:
        """
        الحصول على ملخص مالي للطالب مع جميع مدرسيه
        
        Returns:
            list of dicts: كل dict يمثل مدرس ومعطياته المالية
        """
        # الحصول على قائمة المدرسين المرتبطين بالطالب
        query = '''
            SELECT t.id, t.name, t.subject, t.total_fee, st.study_type as study_type, st.status as link_status
            FROM teachers t
            INNER JOIN student_teacher st ON t.id = st.teacher_id
            WHERE st.student_id = %s
            ORDER BY t.name
        '''
        teachers = self.db.execute_query(query, (student_id,))
        
        summary = []
        for teacher in teachers:
            balance = self.calculate_student_teacher_balance(student_id, teacher['id'])
            summary.append({
                'teacher_id': teacher['id'],
                'teacher_name': teacher['name'],
                'subject': teacher['subject'],
                'total_fee': teacher['total_fee'],
                'paid_total': balance['paid_total'],
                'remaining_balance': balance['remaining_balance'],
                'study_type': teacher.get('study_type', 'حضوري'),
                'status': teacher.get('link_status', 'مستمر')
            })
        
        return summary
    
    # =====================================================
    # دوال حسابات المدرسين
    # =====================================================
    
    def get_teacher_students_paid_total(self, teacher_id: int) -> int:
        """
        حساب إجمالي ما استلمه مدرس من جميع الطلاب
        
        Returns:
            int: مجموع كل الأقساط لهذا المدرس
        """
        query = '''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM installments
            WHERE teacher_id = %s
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if result and len(result) > 0:
            return result[0]['total'] if result[0]['total'] else 0
        return 0
    
    def get_teacher_paying_students_count(self, teacher_id: int) -> int:
        """
        حساب عدد الطلاب الدافعين للمدرس
        
        طالب دافع = أي طالب لديه مجموع دفعات > 0
        
        Returns:
            int: عدد الطلاب الدافعين
        """
        query = '''
            SELECT COUNT(DISTINCT student_id) as count
            FROM installments
            WHERE teacher_id = %s AND amount > 0
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if result and len(result) > 0:
            return result[0]['count'] if result[0]['count'] else 0
        return 0
    
    def get_teacher_total_students_count(self, teacher_id: int) -> int:
        """
        حساب عدد كل الطلاب المرتبطين بالمدرس (دافعين وغير دافعين)
        
        Returns:
            int: إجمالي عدد الطلاب
        """
        query = '''
            SELECT COUNT(*) as count
            FROM student_teacher
            WHERE teacher_id = %s
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if result and len(result) > 0:
            return result[0]['count'] if result[0]['count'] else 0
        return 0
    
    def calculate_institute_deduction(self, teacher_id: int, total_received: int = 0) -> int:
        """
        حساب خصم المعهد - المنطق الجديد:
        - النسبة تُقسم على القسطين الأول والثاني بالتساوي
        - إذا دفع كامل (دفع كامل) يتم استقطاع النسبة كاملة
        - المبلغ اليدوي يُقسم على القسطين بالتساوي أيضاً
        - دفع كامل يستقطع المبلغ اليدوي كامل
        """
        db = self.db
        
        query = '''
            SELECT institute_deduction_type, institute_deduction_value,
                   fee_in_person, fee_electronic, fee_blended,
                   institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
                   teaching_types
            FROM teachers WHERE id = %s
        '''
        result = db.execute_query(query, (teacher_id,))
        if not result:
            return 0
        
        t = result[0]
        deduction_type = t.get('institute_deduction_type') or 'percentage'
        deduction_value = t.get('institute_deduction_value') or 0
        
        if deduction_value <= 0:
            return 0
        
        # Get all installments for this teacher grouped by student
        query = '''
            SELECT student_id, installment_type, amount
            FROM installments
            WHERE teacher_id = %s
        '''
        installments = db.execute_query(query, (teacher_id,))
        if not installments:
            return 0
        
        # Group installments by student
        student_payments = {}
        for inst in installments:
            sid = inst['student_id']
            if sid not in student_payments:
                student_payments[sid] = []
            student_payments[sid].append(inst)
        
        total_deduction = 0
        
        for student_id, payments in student_payments.items():
            has_first = False
            has_second = False
            has_full = False
            first_amount = 0
            second_amount = 0
            full_amount = 0
            
            for p in payments:
                itype = p['installment_type']
                amt = p['amount'] or 0
                if itype == 'القسط الأول':
                    has_first = True
                    first_amount = amt
                elif itype == 'القسط الثاني':
                    has_second = True
                    second_amount = amt
                elif itype == 'دفع كامل':
                    has_full = True
                    full_amount = amt
            
            if has_full:
                # دفع كامل: استقطاع كامل النسبة من المبلغ الكامل
                total_deduction += int((full_amount * deduction_value) / 100)
            else:
                # حساب الخصم لكل قسط بشكل منفصل
                if has_first:
                    total_deduction += int((first_amount * deduction_value) / 200)  # نصف النسبة
                if has_second:
                    total_deduction += int((second_amount * deduction_value) / 200)  # نصف النسبة
        
        return total_deduction
    
    def calculate_teacher_due(self, teacher_id: int) -> Dict[str, Any]:
        """
        حساب مستحق المدرس بعد خصم المعهد
        
        المعادلة: مستحق المدرس = إجمالي الاستلامات - خصم المعهد
        
        Returns:
            dict يحتوي تفاصيل الحساب
        """
        total_received = self.get_teacher_students_paid_total(teacher_id)
        institute_deduction = self.calculate_institute_deduction(teacher_id, total_received)
        teacher_due = total_received - institute_deduction
        
        return {
            'total_received': total_received,
            'institute_deduction': institute_deduction,
            'paying_students_count': self.get_teacher_paying_students_count(teacher_id),
            'teacher_due': teacher_due
        }
    
    def get_teacher_withdrawn_total(self, teacher_id: int) -> int:
        """
        حساب مجموع سحوبات المدرس
        
        Returns:
            int: إجمالي المسحوب
        """
        query = '''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM teacher_withdrawals
            WHERE teacher_id = %s
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if result and len(result) > 0:
            return result[0]['total'] if result[0]['total'] else 0
        return 0
    
    def calculate_teacher_balance(self, teacher_id: int) -> Dict[str, Any]:
        """
        حساب الرصيد المتبقي للمدرس
        
        المعادلة: الرصيد المتبقي = مستحق المدرس - مجموع السحوبات
        
        Returns:
            dict يحتوي:
                - teacher_due: مستحق المدرس
                - withdrawn_total: المسحوب
                - remaining_balance: الرصيد المتبقي
                - can_withdraw: هل يمكنه السحب؟
        """
        due_info = self.calculate_teacher_due(teacher_id)
        withdrawn_total = self.get_teacher_withdrawn_total(teacher_id)
        remaining_balance = due_info['teacher_due'] - withdrawn_total
        
        return {
            'teacher_due': due_info['teacher_due'],
            'withdrawn_total': withdrawn_total,
            'remaining_balance': remaining_balance,
            'can_withdraw': remaining_balance > 0,
            **due_info
        }
    
    def can_teacher_withdraw(self, teacher_id: int, amount: int) -> tuple:
        """
        التحقق مما إذا كان المدرس يمكنه سحب هذا المبلغ
        
        Args:
            teacher_id: رقم المدرس
            amount: المبلغ المطلوب سحبه
            
        Returns:
            tuple: (can_withdraw: bool, message: str, current_balance: int)
        """
        balance_info = self.calculate_teacher_balance(teacher_id)
        current_balance = balance_info['remaining_balance']
        
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر", current_balance
        
        if amount > current_balance:
            return False, f"المبلغ أكبر من الرصيد المتبقي ({format_currency(current_balance)})", current_balance
        
        return True, "يمكن إجراء السحب", current_balance
    
    def get_teacher_recent_withdrawals(self, teacher_id: int, limit: int = 5) -> List[Dict]:
        """
        الحصول على آخر سحوبات المدرس
        
        Args:
            teacher_id: رقم المدرس
            limit: عدد السحوبات المراد عرضها
            
        Returns:
            list: قائمة بأحدث السحوبات
        """
        query = '''
            SELECT id, amount, withdrawal_date, notes
            FROM teacher_withdrawals
            WHERE teacher_id = %s
            ORDER BY withdrawal_date DESC
            LIMIT %s
        '''
        results = self.db.execute_query(query, (teacher_id, limit))
        
        return [dict(row) for row in results] if results else []
    
    def get_teacher_students_list(self, teacher_id: int) -> List[Dict]:
        """قائمة طلاب المدرس مع القسط حسب نوع الدراسة"""
        db = self.db
        
        # الحصول على معلومات المدرس
        teacher_query = 'SELECT total_fee, fee_in_person, fee_electronic, fee_blended FROM teachers WHERE id = %s'
        teacher_result = db.execute_query(teacher_query, (teacher_id,))
        teacher_data = teacher_result[0] if teacher_result else {}
        
        query = '''
            SELECT s.id, s.name, st.study_type as study_type, st.status as status, s.barcode
            FROM students s
            INNER JOIN student_teacher st ON s.id = st.student_id
            WHERE st.teacher_id = %s
            ORDER BY s.name
        '''
        students = db.execute_query(query, (teacher_id,))
        
        result = []
        for student in students:
            study_type = student.get('study_type', 'حضوري')
            
            # تحديد القسط حسب نوع الدراسة
            if study_type == 'الكتروني' and teacher_data.get('fee_electronic', 0) > 0:
                total_fee = teacher_data['fee_electronic']
            elif study_type == 'مدمج' and teacher_data.get('fee_blended', 0) > 0:
                total_fee = teacher_data['fee_blended']
            elif study_type == 'حضوري' and teacher_data.get('fee_in_person', 0) > 0:
                total_fee = teacher_data['fee_in_person']
            else:
                total_fee = teacher_data.get('total_fee', 0)
            
            paid = self.get_student_paid_total(student['id'], teacher_id)
            remaining = total_fee - paid
            result.append({
                **student,
                'total_fee': total_fee,
                'paid_total': paid,
                'remaining_balance': remaining,
                'is_paying': paid > 0
            })
        
        return result
    
    # =====================================================
    # دوال الإحصائيات العامة
    # =====================================================
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """
        الحصول على إحصائيات عامة عن النظام
        
        Returns:
            dict يحتوي جميع الإحصائيات
        """
        stats = {}
        
        try:
            # عدد الطلاب
            result = self.db.execute_query("SELECT COUNT(*) as count FROM students")
            stats['total_students'] = result[0]['count'] if result else 0
            
            # الطلاب المستمرين
            result = self.db.execute_query("SELECT COUNT(*) as count FROM students WHERE status = 'مستمر'")
            stats['active_students'] = result[0]['count'] if result else 0
            
            # الطلاب المنسحبين
            result = self.db.execute_query("SELECT COUNT(*) as count FROM students WHERE status = 'منسحب'")
            stats['withdrawn_students'] = result[0]['count'] if result else 0
            
            # عدد المدرسين
            result = self.db.execute_query("SELECT COUNT(*) as count FROM teachers")
            stats['total_teachers'] = result[0]['count'] if result else 0
            
            # عدد المواد (الفريدة)
            result = self.db.execute_query("SELECT COUNT(DISTINCT subject) as count FROM teachers")
            stats['total_subjects'] = result[0]['count'] if result else 0
            
            # عدد الأقساط
            result = self.db.execute_query("SELECT COUNT(*) as count FROM installments")
            stats['total_installments'] = result[0]['count'] if result else 0
            
            # إجمالي المبالغ المدفوعة
            result = self.db.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM installments")
            stats['total_amount_paid'] = result[0]['total'] if result else 0
            
            # إجمالي السحوبات
            result = self.db.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM teacher_withdrawals")
            stats['total_withdrawals'] = result[0]['total'] if result else 0
        except Exception as e:
            print(f"Error getting statistics: {e}")
            stats = {
                'total_students': 0,
                'active_students': 0,
                'withdrawn_students': 0,
                'total_teachers': 0,
                'total_subjects': 0,
                'total_installments': 0,
                'total_amount_paid': 0,
                'total_withdrawals': 0
            }
        
        return stats


# ===== إنشاء نسخة واحدة من الخدمة (Singleton) =====
finance_service = FinanceService()
