# ============================================
# services/finance_service.py
# المحاسبة المركزية - الدوال المالية الموحدة
# 
# ⚠️ مهم جداً: كل الحسابات المالية يجب أن تتم هنا فقط!
# لا تكتب أي معادلة مالية في أي مكان آخر من النظام!
# ============================================

from typing import List, Dict, Any, Optional
from database import Database
from config import INSTITUTE_DEDUCTION_PER_STUDENT, format_currency


class FinanceService:
    """خدمة المحاسبة المركزية - المصدر الوحيد للحسابات المالية"""
    
    def __init__(self):
        self.db = Database()
    
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
            WHERE student_id = ? AND teacher_id = ?
        '''
        result = self.db.execute_query(query, (student_id, teacher_id))
        
        if result and len(result) > 0:
            return result[0]['total'] if result[0]['total'] else 0
        return 0
    
    def calculate_student_teacher_balance(self, student_id: int, teacher_id: int) -> Dict[str, Any]:
        """
        حساب الرصيد المتبقي على الطالب عند مدرس معين
        
        المعادلة: المتبقي = total_fee - مجموع الأقساط المدفوعة
        
        Returns:
            dict يحتوي:
                - total_fee: الأجر الكلي
                - paid_total: المدفوع
                - remaining_balance: المتبقي
        """
        # الحصول على total_fee للمدرس
        query = '''
            SELECT total_fee FROM teachers WHERE id = ?
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if not result:
            return {
                'total_fee': 0,
                'paid_total': 0,
                'remaining_balance': 0
            }
        
        total_fee = result[0]['total_fee']
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
            SELECT t.id, t.name, t.subject, t.total_fee
            FROM teachers t
            INNER JOIN student_teacher st ON t.id = st.teacher_id
            WHERE st.student_id = ?
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
                'remaining_balance': balance['remaining_balance']
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
            WHERE teacher_id = ?
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
            WHERE teacher_id = ? AND amount > 0
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
            COUNT(*) as count
            FROM student_teacher
            WHERE teacher_id = ?
        '''
        result = self.db.execute_query(
            f'SELECT {query}', 
            (teacher_id,)
        )
        
        if result and len(result) > 0:
            return result[0]['count'] if result[0]['count'] else 0
        return 0
    
    def calculate_institute_deduction(self, teacher_id: int) -> int:
        """
        حساب خصم المعهد لهذا المدرس
        
        المعادلة: عدد الطلاب الدافعين × INSTITUTE_DEDUCTION_PER_STUDENT (50000)
        
        Returns:
            int: مبلغ الخصم (بالدينار)
        """
        paying_count = self.get_teacher_paying_students_count(teacher_id)
        deduction = paying_count * INSTITUTE_DEDUCTION_PER_STUDENT
        return deduction
    
    def calculate_teacher_due(self, teacher_id: int) -> Dict[str, Any]:
        """
        حساب مستحق المدرس بعد خصم المعهد
        
        المعادلة: مستحق المدرس = إجمالي الاستلامات - خصم المعهد
        
        Returns:
            dict يحتوي تفاصيل الحساب
        """
        total_received = self.get_teacher_students_paid_total(teacher_id)
        institute_deduction = self.calculate_institute_deduction(teacher_id)
        teacher_due = total_received - institute_deduction
        
        return {
            'total_received': total_received,
            'institute_deduction': institute_deduction,
            'paying_students_count': self.get_teacher_paying_students_count(teacher_id),
            'deduction_per_student': INSTITUTE_DEDUCTION_PER_STUDENT,
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
            WHERE teacher_id = ?
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
            return False, "❌ المبلغ يجب أن يكون أكبر من صفر", current_balance
        
        if amount > current_balance:
            return False, f"❌ المبلغ أكبر من الرصيد المتبقي ({format_currency(current_balance)})", current_balance
        
        return True, "✅ يمكن إجراء السحب", current_balance
    
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
            WHERE teacher_id = ?
            ORDER BY withdrawal_date DESC
            LIMIT ?
        '''
        results = self.db.execute_query(query, (teacher_id, limit))
        
        return [dict(row) for row in results] if results else []
    
    def get_teacher_students_list(self, teacher_id: int) -> List[Dict]:
        """
        الحصول على قائمة طلاب المدرس مع ملخص دفعات كل طالب
        
        Returns:
            list: قائمة الطلاب مع معلوماتهم المالية
        """
        query = '''
            SELECT s.id, s.name, s.study_type, s.status, s.barcode
            FROM students s
            INNER JOIN student_teacher st ON s.id = st.student_id
            WHERE st.teacher_id = ?
            ORDER BY s.name
        '''
        students = self.db.execute_query(query, (teacher_id,))
        
        result = []
        for student in students:
            paid = self.get_student_paid_total(student['id'], teacher_id)
            result.append({
                **student,
                'paid_total': paid,
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
        
        return stats


# ===== إنشاء نسخة واحدة من الخدمة (Singleton) =====
finance_service = FinanceService()