# ============================================
# services/finance_service.py
# المحاسبة المركزية - الدوال المالية الموحدة
# محسّن: استعلامات مجمعة بدلاً من N+1
# 
# مهم جداً: كل الحسابات المالية يجب أن تتم هنا فقط!
# لا تكتب أي معادلة مالية في أي مكان آخر من النظام!
# ============================================

from typing import List, Dict, Any, Optional
import logging
from database import Database
from config import format_currency

logger = logging.getLogger(__name__)


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
        """حساب مجموع ما دفعه طالب لمدرس معين"""
        query = '''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM installments
            WHERE student_id = %s AND teacher_id = %s
        '''
        result = self.db.execute_query(query, (student_id, teacher_id))
        
        if result and len(result) > 0:
            return result[0]['total'] if result[0]['total'] else 0
        return 0
    
    def _get_discount_info(self, student_id: int, teacher_id: int) -> Dict[str, Any]:
        """الحصول على معلومات الخصم لربط طالب-مدرس"""
        db = self.db
        query = '''
            SELECT discount_type, discount_value, institute_waiver, discount_notes
            FROM student_teacher 
            WHERE student_id = %s AND teacher_id = %s
        '''
        result = db.execute_query(query, (student_id, teacher_id))
        if result:
            return {
                'discount_type': result[0].get('discount_type', 'none'),
                'discount_value': result[0].get('discount_value', 0) or 0,
                'institute_waiver': result[0].get('institute_waiver', 0) or 0,
                'discount_notes': result[0].get('discount_notes', '') or '',
            }
        return {'discount_type': 'none', 'discount_value': 0, 'institute_waiver': 0, 'discount_notes': ''}
    
    def _apply_discount_to_fee(self, total_fee: int, discount_info: Dict) -> int:
        """تطبيق الخصم على القسط الكلي وإرجاء القسط الفعلي (بتقريب عادل)"""
        discount_type = discount_info.get('discount_type', 'none')
        discount_value = discount_info.get('discount_value', 0)
        
        if discount_type == 'free':
            return 0
        elif discount_type == 'percentage' and discount_value > 0:
            discount_amount = round(total_fee * discount_value / 100)
            return max(0, total_fee - discount_amount)
        elif discount_type == 'fixed' and discount_value > 0:
            return max(0, total_fee - discount_value)
        elif discount_type == 'custom' and discount_value > 0:
            discount_amount = round(total_fee * discount_value / 100)
            return max(0, total_fee - discount_amount)
        return total_fee
    
    def calculate_student_teacher_balance(self, student_id: int, teacher_id: int) -> Dict[str, Any]:
        """حساب الرصيد المتبقي - يستخدم القسط حسب نوع الدراسة مع الخصم"""
        db = self.db
        
        # استعلام واحد يجمع بيانات المدرس والربط والمدفوعات
        query = '''
            SELECT t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   st.study_type, st.discount_type, st.discount_value, st.institute_waiver,
                   COALESCE(i.paid, 0) as paid_total
            FROM teachers t
            INNER JOIN student_teacher st ON st.teacher_id = t.id AND st.student_id = %s
            LEFT JOIN (
                SELECT teacher_id, student_id, COALESCE(SUM(amount), 0) as paid
                FROM installments
                WHERE student_id = %s AND teacher_id = %s
                GROUP BY teacher_id, student_id
            ) i ON i.teacher_id = t.id AND i.student_id = %s
            WHERE t.id = %s
        '''
        result = db.execute_query(query, (student_id, student_id, teacher_id, student_id, teacher_id))
        
        if not result:
            return {'total_fee': 0, 'paid_total': 0, 'remaining_balance': 0, 'original_fee': 0, 'discount_info': {'discount_type': 'none', 'discount_value': 0, 'institute_waiver': 0, 'discount_notes': ''}}
        
        r = result[0]
        study_type = r.get('study_type', 'حضوري') or 'حضوري'
        discount_info = {
            'discount_type': r.get('discount_type', 'none') or 'none',
            'discount_value': r.get('discount_value', 0) or 0,
            'institute_waiver': r.get('institute_waiver', 0) or 0,
            'discount_notes': r.get('discount_notes', '') or '',
        }
        
        # تحديد القسط حسب نوع الدراسة
        if study_type == 'الكتروني' and r.get('fee_electronic', 0) > 0:
            original_fee = r['fee_electronic']
        elif study_type == 'مدمج' and r.get('fee_blended', 0) > 0:
            original_fee = r['fee_blended']
        elif study_type == 'حضوري' and r.get('fee_in_person', 0) > 0:
            original_fee = r['fee_in_person']
        else:
            original_fee = r['total_fee']
        
        effective_fee = self._apply_discount_to_fee(original_fee, discount_info)
        paid_total = r['paid_total']
        remaining_balance = effective_fee - paid_total
        has_overpayment = remaining_balance < 0
        display_remaining = max(0, remaining_balance)
        
        return {
            'total_fee': effective_fee,
            'original_fee': original_fee,
            'paid_total': paid_total,
            'remaining_balance': display_remaining,
            'has_overpayment': has_overpayment,
            'overpayment_amount': abs(remaining_balance) if has_overpayment else 0,
            'discount_info': discount_info
        }
    
    # ===== تحسين رئيسي: حساب أرصدة كل الطلاب دفعة واحدة =====
    
    def get_students_balances_batch(self, student_ids: list) -> Dict[int, Dict]:
        """
        حساب أرصدة مجموعة طلاب في استعلام واحد بدلاً من N استعلام
        يُرجع dict: {student_id: {total_fees, total_paid, total_remaining}}
        """
        if not student_ids:
            return {}
        
        db = self.db
        placeholders = ','.join(['%s'] * len(student_ids))
        
        # استعلام واحد يجلب كل الأرصدة لكل الطلاب
        query = f'''
            SELECT st.student_id, st.teacher_id, st.study_type,
                   st.discount_type, st.discount_value, st.institute_waiver,
                   t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   COALESCE(i.paid, 0) as paid_total
            FROM student_teacher st
            INNER JOIN teachers t ON t.id = st.teacher_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(amount), 0) as paid
                FROM installments
                WHERE installments.student_id = st.student_id AND installments.teacher_id = st.teacher_id
            ) i ON true
            WHERE st.student_id IN ({placeholders}) AND st.status = 'مستمر'
        '''
        
        try:
            results = db.execute_query(query, tuple(student_ids))
        except Exception:
            # Fallback: إذا لم يدعم LATERAL، نستخدم استعلام بديل
            try:
                query2 = f'''
                    SELECT st.student_id, st.teacher_id, st.study_type,
                           st.discount_type, st.discount_value, st.institute_waiver,
                           t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended
                    FROM student_teacher st
                    INNER JOIN teachers t ON t.id = st.teacher_id
                    WHERE st.student_id IN ({placeholders}) AND st.status = 'مستمر'
                '''
                results = db.execute_query(query2, tuple(student_ids))
                
                # استعلام المدفوعات دفعة واحدة
                paid_query = f'''
                    SELECT student_id, teacher_id, COALESCE(SUM(amount), 0) as paid_total
                    FROM installments
                    WHERE student_id IN ({placeholders})
                    GROUP BY student_id, teacher_id
                '''
                paid_results = db.execute_query(paid_query, tuple(student_ids))
                paid_map = {}
                if paid_results:
                    for p in paid_results:
                        paid_map[(p['student_id'], p['teacher_id'])] = p['paid_total']
                
                # دمج المدفوعات
                for r in results:
                    r['paid_total'] = paid_map.get((r['student_id'], r['teacher_id']), 0)
            except Exception as e:
                print(f"Error in batch balance: {e}")
                return {}
        
        if not results:
            return {}
        
        # حساب الأرصدة لكل طالب
        student_balances = {}
        for r in results:
            sid = r['student_id']
            study_type = r.get('study_type', 'حضوري') or 'حضوري'
            discount_info = {
                'discount_type': r.get('discount_type', 'none') or 'none',
                'discount_value': r.get('discount_value', 0) or 0,
                'institute_waiver': r.get('institute_waiver', 0) or 0,
            }
            
            # تحديد القسط حسب نوع الدراسة
            if study_type == 'الكتروني' and r.get('fee_electronic', 0) > 0:
                original_fee = r['fee_electronic']
            elif study_type == 'مدمج' and r.get('fee_blended', 0) > 0:
                original_fee = r['fee_blended']
            elif study_type == 'حضوري' and r.get('fee_in_person', 0) > 0:
                original_fee = r['fee_in_person']
            else:
                original_fee = r['total_fee']
            
            effective_fee = self._apply_discount_to_fee(original_fee, discount_info)
            paid = r['paid_total']
            remaining = max(0, effective_fee - paid)
            
            if sid not in student_balances:
                student_balances[sid] = {'total_fees': 0, 'total_paid': 0, 'total_remaining': 0}
            
            student_balances[sid]['total_fees'] += effective_fee
            student_balances[sid]['total_paid'] += paid
            student_balances[sid]['total_remaining'] += remaining
        
        return student_balances
    
    def get_student_all_teachers_summary(self, student_id: int) -> List[Dict[str, Any]]:
        """الحصول على ملخص مالي للطالب مع جميع مدرسيه"""
        query = '''
            SELECT t.id, t.name, t.subject, t.total_fee, st.study_type as study_type, st.status as link_status,
                   st.discount_type, st.discount_value, st.institute_waiver, st.discount_notes,
                   t.fee_in_person, t.fee_electronic, t.fee_blended,
                   COALESCE(i.paid, 0) as paid_total
            FROM teachers t
            INNER JOIN student_teacher st ON t.id = st.teacher_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(amount), 0) as paid
                FROM installments
                WHERE installments.student_id = %s AND installments.teacher_id = t.id
            ) i ON true
            WHERE st.student_id = %s
            ORDER BY t.name
        '''
        
        try:
            teachers = self.db.execute_query(query, (student_id, student_id))
        except Exception:
            # Fallback بدون LATERAL
            query2 = '''
                SELECT t.id, t.name, t.subject, t.total_fee, st.study_type as study_type, st.status as link_status,
                       st.discount_type, st.discount_value, st.institute_waiver, st.discount_notes,
                       t.fee_in_person, t.fee_electronic, t.fee_blended
                FROM teachers t
                INNER JOIN student_teacher st ON t.id = st.teacher_id
                WHERE st.student_id = %s
                ORDER BY t.name
            '''
            teachers = self.db.execute_query(query2, (student_id,))
            # إضافة المدفوعات
            for t in teachers:
                t['paid_total'] = self.get_student_paid_total(student_id, t['id'])
        
        summary = []
        for teacher in teachers:
            study_type = teacher.get('study_type', 'حضوري') or 'حضوري'
            discount_info = {
                'discount_type': teacher.get('discount_type', 'none') or 'none',
                'discount_value': teacher.get('discount_value', 0) or 0,
                'institute_waiver': teacher.get('institute_waiver', 0) or 0,
                'discount_notes': teacher.get('discount_notes', '') or '',
            }
            
            if study_type == 'الكتروني' and teacher.get('fee_electronic', 0) > 0:
                original_fee = teacher['fee_electronic']
            elif study_type == 'مدمج' and teacher.get('fee_blended', 0) > 0:
                original_fee = teacher['fee_blended']
            elif study_type == 'حضوري' and teacher.get('fee_in_person', 0) > 0:
                original_fee = teacher['fee_in_person']
            else:
                original_fee = teacher['total_fee']
            
            effective_fee = self._apply_discount_to_fee(original_fee, discount_info)
            paid_total = teacher['paid_total']
            remaining_balance = effective_fee - paid_total
            has_overpayment = remaining_balance < 0
            display_remaining = max(0, remaining_balance)
            
            summary.append({
                'teacher_id': teacher['id'],
                'teacher_name': teacher['name'],
                'subject': teacher['subject'],
                'total_fee': effective_fee,
                'original_fee': original_fee,
                'paid_total': paid_total,
                'remaining_balance': display_remaining,
                'has_overpayment': has_overpayment,
                'overpayment_amount': abs(remaining_balance) if has_overpayment else 0,
                'study_type': study_type,
                'status': teacher.get('link_status', 'مستمر'),
                'discount_info': discount_info
            })
        
        return summary
    
    # =====================================================
    # دوال حسابات المدرسين
    # =====================================================
    
    def get_teacher_students_paid_total(self, teacher_id: int) -> int:
        """حساب إجمالي ما استلمه مدرس من جميع الطلاب"""
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
        """حساب عدد الطلاب الدافعين للمدرس"""
        query = '''
            SELECT COUNT(DISTINCT student_id) as count
            FROM installments
            WHERE teacher_id = %s AND amount > 0
        '''
        result = self.db.execute_query(query, (teacher_id,))
        
        if result and len(result) > 0:
            return result[0]['count'] if result[0]['count'] else 0
        return 0
    
    def calculate_institute_deduction(self, teacher_id: int, total_received: int = 0) -> int:
        """
        حساب خصم المعهد - يدعم نسبة مئوية أو مبلغ يدوي لكل نوع تدريس
        """
        db = self.db
        
        query = '''
            SELECT institute_deduction_type, institute_deduction_value,
                   fee_in_person, fee_electronic, fee_blended,
                   institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
                   inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
                   inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
                   teaching_types
            FROM teachers WHERE id = %s
        '''
        result = db.execute_query(query, (teacher_id,))
        if not result:
            return 0
        
        t = result[0]
        
        # Get all installments with study type and discount info for this teacher
        query = '''
            SELECT i.student_id, i.installment_type, i.amount,
                   COALESCE(i.for_installment, '') as for_installment,
                   COALESCE(st.study_type, 'حضوري') as study_type,
                   COALESCE(st.discount_type, 'none') as discount_type,
                   COALESCE(st.discount_value, 0) as discount_value,
                   COALESCE(st.institute_waiver, 0) as institute_waiver
            FROM installments i
            LEFT JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE i.teacher_id = %s
        '''
        installments = db.execute_query(query, (teacher_id,))
        
        # Also get "free without waiver" students
        free_no_waiver_query = '''
            SELECT st.student_id, st.study_type, st.discount_type, st.discount_value, st.institute_waiver
            FROM student_teacher st
            WHERE st.teacher_id = %s AND st.discount_type = 'free' AND (st.institute_waiver = 0 OR st.institute_waiver IS NULL)
        '''
        free_no_waiver_students = db.execute_query(free_no_waiver_query, (teacher_id,))
        if not installments and not free_no_waiver_students:
            return 0
        
        # Group installments by student
        student_payments = {}
        if installments:
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
            has_splits_first = False
            has_splits_second = False
            study_type = 'حضوري'
            discount_type = 'none'
            discount_value = 0
            institute_waiver = 0
            
            for p in payments:
                study_type = p.get('study_type', 'حضوري') or 'حضوري'
                discount_type = p.get('discount_type', 'none') or 'none'
                discount_value = p.get('discount_value', 0) or 0
                institute_waiver = p.get('institute_waiver', 0) or 0
                itype = p['installment_type']
                if itype == 'القسط الأول':
                    has_first = True
                elif itype == 'القسط الثاني':
                    has_second = True
                elif itype == 'دفع كامل':
                    has_full = True
                elif itype == 'دفعات':
                    for_inst = p.get('for_installment', '')
                    if for_inst == 'القسط الثاني':
                        has_splits_second = True
                    else:
                        has_splits_first = True
            
            ded_type, ded_value = self._get_deduction_for_study_type(t, study_type)
            
            if discount_type == 'free' and institute_waiver:
                continue
            
            if discount_type == 'free' and not institute_waiver:
                student_total_fee = self._get_fee_for_study_type(t, study_type)
                if student_total_fee > 0 and ded_value > 0:
                    if ded_type == 'manual':
                        total_deduction += ded_value
                    else:
                        total_deduction += round((student_total_fee * ded_value) / 100)
                continue

            if ded_value <= 0:
                continue
            
            fee_for_deduction = self._get_fee_for_study_type(t, study_type)
            
            discount_info_for_calc = {
                'discount_type': discount_type,
                'discount_value': discount_value,
                'institute_waiver': institute_waiver
            }
            effective_fee = self._apply_discount_to_fee(fee_for_deduction, discount_info_for_calc)
            total_paid_by_student = sum(p['amount'] for p in payments)
            
            is_effectively_full_payment = effective_fee > 0 and total_paid_by_student >= effective_fee
            first_installment_total = sum(p['amount'] for p in payments
                if p['installment_type'] == 'القسط الأول'
                or (p['installment_type'] == 'دفعات' and p.get('for_installment', '') != 'القسط الثاني'))
            is_first_equals_full = (has_first or has_splits_first) and not has_second and not has_full and not has_splits_second and first_installment_total >= effective_fee and effective_fee > 0
            
            if ded_type == 'manual':
                half_ded = ded_value // 2
                other_half_ded = ded_value - half_ded
                
                if is_effectively_full_payment or is_first_equals_full:
                    total_deduction += ded_value
                elif has_full:
                    total_deduction += ded_value
                elif has_first and has_second:
                    total_deduction += ded_value
                elif has_first and has_splits_second:
                    total_deduction += ded_value
                elif has_splits_first and has_second:
                    total_deduction += ded_value
                elif has_splits_first and has_splits_second:
                    total_deduction += ded_value
                elif has_first or has_splits_first:
                    total_deduction += half_ded
                elif has_second or has_splits_second:
                    total_deduction += other_half_ded
            else:
                full_deduction = round((fee_for_deduction * ded_value) / 100)
                half_deduction = full_deduction // 2
                other_half_deduction = full_deduction - half_deduction
                
                if is_effectively_full_payment or is_first_equals_full:
                    total_deduction += full_deduction
                elif has_full:
                    total_deduction += full_deduction
                elif has_first and has_second:
                    total_deduction += full_deduction
                elif has_first and has_splits_second:
                    total_deduction += full_deduction
                elif has_splits_first and has_second:
                    total_deduction += full_deduction
                elif has_splits_first and has_splits_second:
                    total_deduction += full_deduction
                elif has_first or has_splits_first:
                    total_deduction += half_deduction
                elif has_second or has_splits_second:
                    total_deduction += other_half_deduction
        
        # معالجة الطلاب مجاني بدون تنازل بدون أقساط
        if free_no_waiver_students:
            students_with_payments = set(student_payments.keys()) if student_payments else set()
            
            for fw_student in free_no_waiver_students:
                fw_sid = fw_student['student_id']
                if fw_sid in students_with_payments:
                    continue
                
                fw_study_type = fw_student.get('study_type', 'حضوري') or 'حضوري'
                ded_type, ded_value = self._get_deduction_for_study_type(t, fw_study_type)
                student_total_fee = self._get_fee_for_study_type(t, fw_study_type)
                
                if student_total_fee > 0 and ded_value > 0:
                    if ded_type == 'manual':
                        total_deduction += ded_value
                    else:
                        total_deduction += round((student_total_fee * ded_value) / 100)
        
        return total_deduction
    
    # ===== تحسين رئيسي: حساب خصم المعهد لكل المدرسين دفعة واحدة =====
    
    def calculate_institute_deduction_batch(self, teacher_ids: list) -> Dict[int, int]:
        """
        حساب خصم المعهد لعدة مدرسين دفعة واحدة
        يُرجع dict: {teacher_id: deduction_amount}
        """
        if not teacher_ids:
            return {}
        
        result = {}
        for tid in teacher_ids:
            try:
                result[tid] = self.calculate_institute_deduction(tid)
            except Exception as e:
                logger.error(f"خطأ في حساب خصم المعهد للمدرس {tid}: {e}")
                result[tid] = 0
        return result
    
    def _get_deduction_for_study_type(self, teacher_data: dict, study_type: str) -> tuple:
        """إرجاع (نوع الخصم, القيمة) حسب نوع الدراسة"""
        type_map = {
            'حضوري': ('in_person', 'pct_in_person', 'ded_type_in_person', 'ded_manual_in_person'),
            'الكتروني': ('electronic', 'pct_electronic', 'ded_type_electronic', 'ded_manual_electronic'),
            'مدمج': ('blended', 'pct_blended', 'ded_type_blended', 'ded_manual_blended'),
        }

        keys = type_map.get(study_type, type_map['حضوري'])
        ded_type = teacher_data.get('inst_' + keys[2]) or 'percentage'

        fallback_pct = teacher_data.get('institute_deduction_value', 0) or 0

        if ded_type == 'manual':
            manual_val = teacher_data.get('inst_' + keys[3]) or 0
            if manual_val > 0:
                return ('manual', manual_val)
            if fallback_pct > 0:
                return ('percentage', fallback_pct)
            return ('manual', 0)
        else:
            pct_val = teacher_data.get('institute_' + keys[1]) or 0
            if pct_val > 0:
                return ('percentage', pct_val)
            if fallback_pct > 0:
                return ('percentage', fallback_pct)
            return ('percentage', 0)
    
    def _get_fee_for_study_type(self, teacher_data: dict, study_type: str) -> int:
        """إرجاع القسط الكلي حسب نوع الدراسة"""
        if study_type == 'الكتروني' and teacher_data.get('fee_electronic', 0) > 0:
            return teacher_data['fee_electronic']
        elif study_type == 'مدمج' and teacher_data.get('fee_blended', 0) > 0:
            return teacher_data['fee_blended']
        elif study_type == 'حضوري' and teacher_data.get('fee_in_person', 0) > 0:
            return teacher_data['fee_in_person']
        return teacher_data.get('total_fee', 0)
    
    def calculate_teacher_due(self, teacher_id: int) -> Dict[str, Any]:
        """حساب مستحق المدرس بعد خصم المعهد"""
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
        """حساب مجموع سحوبات المدرس"""
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
        """حساب الرصيد المتبقي للمدرس"""
        due_info = self.calculate_teacher_due(teacher_id)
        withdrawn_total = self.get_teacher_withdrawn_total(teacher_id)
        remaining_balance = due_info['teacher_due'] - withdrawn_total
        has_over_withdrawal = remaining_balance < 0
        display_remaining = max(0, remaining_balance)
        
        return {
            'teacher_due': due_info['teacher_due'],
            'withdrawn_total': withdrawn_total,
            'remaining_balance': display_remaining,
            'has_over_withdrawal': has_over_withdrawal,
            'over_withdrawal_amount': abs(remaining_balance) if has_over_withdrawal else 0,
            'can_withdraw': remaining_balance > 0,
            **due_info
        }
    
    def can_teacher_withdraw(self, teacher_id: int, amount: int) -> tuple:
        """التحقق مما إذا كان المدرس يمكنه سحب هذا المبلغ"""
        balance_info = self.calculate_teacher_balance(teacher_id)
        current_balance = balance_info['remaining_balance']
        
        if amount <= 0:
            return False, "المبلغ يجب أن يكون أكبر من صفر", current_balance
        
        if amount > current_balance:
            return False, f"المبلغ أكبر من الرصيد المتبقي ({format_currency(current_balance)})", current_balance
        
        return True, "يمكن إجراء السحب", current_balance
    
    def get_all_withdrawals(self, limit: int = 100) -> List[Dict]:
        """الحصول على جميع السحوبات مع اسم المدرس"""
        query = '''
            SELECT w.id, w.teacher_id, w.amount, w.withdrawal_date, w.notes,
                   t.name as teacher_name, t.subject
            FROM teacher_withdrawals w
            JOIN teachers t ON w.teacher_id = t.id
            ORDER BY w.withdrawal_date DESC
            LIMIT %s
        '''
        results = self.db.execute_query(query, (limit,))
        
        return [dict(row) for row in results] if results else []
    
    def get_teacher_recent_withdrawals(self, teacher_id: int, limit: int = 5) -> List[Dict]:
        """الحصول على آخر سحوبات المدرس"""
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
        """قائمة طلاب المدرس مع القسط حسب نوع الدراسة والخصم - محسّنة باستعلام واحد"""
        db = self.db
        
        # استعلام واحد يجمع كل البيانات
        query = '''
            SELECT s.id, s.name, st.study_type as study_type, st.status as status, s.barcode,
                   st.discount_type, st.discount_value, st.institute_waiver,
                   t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   COALESCE(i.paid, 0) as paid_total
            FROM students s
            INNER JOIN student_teacher st ON s.id = st.student_id
            INNER JOIN teachers t ON t.id = st.teacher_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(amount), 0) as paid
                FROM installments
                WHERE installments.student_id = s.id AND installments.teacher_id = %s
            ) i ON true
            WHERE st.teacher_id = %s
            ORDER BY s.name
        '''
        
        try:
            students = db.execute_query(query, (teacher_id, teacher_id))
        except Exception:
            # Fallback بدون LATERAL
            query2 = '''
                SELECT s.id, s.name, st.study_type as study_type, st.status as status, s.barcode,
                       st.discount_type, st.discount_value, st.institute_waiver,
                       t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended
                FROM students s
                INNER JOIN student_teacher st ON s.id = st.student_id
                INNER JOIN teachers t ON t.id = st.teacher_id
                WHERE st.teacher_id = %s
                ORDER BY s.name
            '''
            students = db.execute_query(query2, (teacher_id,))
            for s in students:
                s['paid_total'] = self.get_student_paid_total(s['id'], teacher_id)
        
        result = []
        for student in students:
            study_type = student.get('study_type', 'حضوري')
            discount_info = {
                'discount_type': student.get('discount_type', 'none') or 'none',
                'discount_value': student.get('discount_value', 0) or 0,
                'institute_waiver': student.get('institute_waiver', 0) or 0,
            }
            
            if study_type == 'الكتروني' and student.get('fee_electronic', 0) > 0:
                original_fee = student['fee_electronic']
            elif study_type == 'مدمج' and student.get('fee_blended', 0) > 0:
                original_fee = student['fee_blended']
            elif study_type == 'حضوري' and student.get('fee_in_person', 0) > 0:
                original_fee = student['fee_in_person']
            else:
                original_fee = student['total_fee']
            
            effective_fee = self._apply_discount_to_fee(original_fee, discount_info)
            paid = student['paid_total']
            remaining = effective_fee - paid
            has_overpayment = remaining < 0
            display_remaining = max(0, remaining)
            result.append({
                **student,
                'total_fee': effective_fee,
                'original_fee': original_fee,
                'paid_total': paid,
                'remaining_balance': display_remaining,
                'has_overpayment': has_overpayment,
                'overpayment_amount': abs(remaining) if has_overpayment else 0,
                'is_paying': paid > 0,
                'discount_info': discount_info
            })
        
        return result
    
    # ===== تحسين رئيسي: حساب المطلوب الكلي لعدة مدرسين دفعة واحدة =====
    
    def get_teachers_total_fees_batch(self, teacher_ids: list) -> Dict[int, int]:
        """
        حساب المطلوب الكلي (مجموع أقساط الطلاب المستمرين) لعدة مدرسين
        استعلام واحد بدلاً من N استعلام
        """
        if not teacher_ids:
            return {}
        
        db = self.db
        placeholders = ','.join(['%s'] * len(teacher_ids))
        
        # استعلام يحسب القسط الفعلي لكل رابط طالب-مدرس للمدرسين المحددين
        query = f'''
            SELECT st.teacher_id,
                   CASE
                       WHEN st.study_type = 'الكتروني' AND t.fee_electronic > 0 THEN
                           CASE st.discount_type
                               WHEN 'free' THEN 0
                               WHEN 'percentage' THEN GREATEST(0, t.fee_electronic - ROUND(t.fee_electronic * COALESCE(st.discount_value, 0) / 100))
                               WHEN 'fixed' THEN GREATEST(0, t.fee_electronic - COALESCE(st.discount_value, 0))
                               WHEN 'custom' THEN GREATEST(0, t.fee_electronic - ROUND(t.fee_electronic * COALESCE(st.discount_value, 0) / 100))
                               ELSE t.fee_electronic
                           END
                       WHEN st.study_type = 'مدمج' AND t.fee_blended > 0 THEN
                           CASE st.discount_type
                               WHEN 'free' THEN 0
                               WHEN 'percentage' THEN GREATEST(0, t.fee_blended - ROUND(t.fee_blended * COALESCE(st.discount_value, 0) / 100))
                               WHEN 'fixed' THEN GREATEST(0, t.fee_blended - COALESCE(st.discount_value, 0))
                               WHEN 'custom' THEN GREATEST(0, t.fee_blended - ROUND(t.fee_blended * COALESCE(st.discount_value, 0) / 100))
                               ELSE t.fee_blended
                           END
                       WHEN st.study_type = 'حضوري' AND t.fee_in_person > 0 THEN
                           CASE st.discount_type
                               WHEN 'free' THEN 0
                               WHEN 'percentage' THEN GREATEST(0, t.fee_in_person - ROUND(t.fee_in_person * COALESCE(st.discount_value, 0) / 100))
                               WHEN 'fixed' THEN GREATEST(0, t.fee_in_person - COALESCE(st.discount_value, 0))
                               WHEN 'custom' THEN GREATEST(0, t.fee_in_person - ROUND(t.fee_in_person * COALESCE(st.discount_value, 0) / 100))
                               ELSE t.fee_in_person
                           END
                       ELSE
                           CASE st.discount_type
                               WHEN 'free' THEN 0
                               WHEN 'percentage' THEN GREATEST(0, t.total_fee - ROUND(t.total_fee * COALESCE(st.discount_value, 0) / 100))
                               WHEN 'fixed' THEN GREATEST(0, t.total_fee - COALESCE(st.discount_value, 0))
                               WHEN 'custom' THEN GREATEST(0, t.total_fee - ROUND(t.total_fee * COALESCE(st.discount_value, 0) / 100))
                               ELSE t.total_fee
                           END
                   END as effective_fee
            FROM student_teacher st
            INNER JOIN teachers t ON t.id = st.teacher_id
            WHERE st.teacher_id IN ({placeholders}) AND st.status = 'مستمر'
        '''
        
        try:
            results = db.execute_query(query, tuple(teacher_ids))
            fees_map = {}
            for r in results:
                tid = r['teacher_id']
                if tid not in fees_map:
                    fees_map[tid] = 0
                fees_map[tid] += r['effective_fee']
            return fees_map
        except Exception as e:
            logger.error(f"خطأ في حساب الأقساط الكلية للمدرسين: {e}")
            return {tid: 0 for tid in teacher_ids}
    
    # ===== حساب مستحق المدرس المتوقع دفعة واحدة =====
    
    def calculate_expected_teacher_due_batch(self, teacher_ids: list) -> Dict[int, Dict]:
        """
        حساب مستحق المدرس المتوقع لعدة مدرسين دفعة واحدة
        المعادلة: (عدد الحضوريين × قسط الحضوري) + (عدد الالكترونيين × قسط الالكتروني) + (عدد المدمجين × قسط المدمج) - خصم المعهد
        يُرجع dict: {teacher_id: {total_fees, expected_deduction, teacher_due, student_counts}}
        """
        if not teacher_ids:
            return {}
        
        # تهيئة النتائج أولاً - ضمان وجود نتائج حتى لو فشلت الاستعلامات
        result = {}
        for tid in teacher_ids:
            result[tid] = {
                'total_fees': 0,
                'expected_deduction': 0,
                'teacher_due': 0,
                'in_person_count': 0,
                'electronic_count': 0,
                'blended_count': 0,
            }
        
        try:
            db = self.db
            placeholders = ','.join(['%s'] * len(teacher_ids))
            
            # جلب بيانات المدرسين (أقساط + خصومات المعهد)
            teachers_query = f'''
                SELECT id, total_fee, fee_in_person, fee_electronic, fee_blended,
                       institute_deduction_type, institute_deduction_value,
                       institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
                       inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
                       inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
                       teaching_types
                FROM teachers WHERE id IN ({placeholders})
            '''
            teachers_data = db.execute_query(teachers_query, tuple(teacher_ids))
            teachers_map = {t['id']: t for t in teachers_data} if teachers_data else {}
            
            # جلب جميع روابط الطلاب مع أنواع الدراسة والخصومات
            links_query = f'''
                SELECT st.teacher_id, st.student_id, st.study_type, 
                       st.discount_type, st.discount_value, st.institute_waiver
                FROM student_teacher st
                WHERE st.teacher_id IN ({placeholders}) AND st.status = 'مستمر'
            '''
            links = db.execute_query(links_query, tuple(teacher_ids))
            
            if not links:
                return result
            
            for link in links:
                try:
                    tid = link['teacher_id']
                    teacher = teachers_map.get(tid)
                    if not teacher:
                        logger.warning(f"المدرس {tid} موجود في روابط الطلاب لكن غير موجود في بيانات المدرسين")
                        continue
                    
                    study_type = link.get('study_type', 'حضوري') or 'حضوري'
                    discount_type = link.get('discount_type', 'none') or 'none'
                    discount_value = link.get('discount_value', 0) or 0
                    institute_waiver = link.get('institute_waiver', 0) or 0
                    
                    # عدد الطلاب حسب النوع
                    if study_type == 'حضوري':
                        result[tid]['in_person_count'] += 1
                    elif study_type == 'الكتروني':
                        result[tid]['electronic_count'] += 1
                    elif study_type == 'مدمج':
                        result[tid]['blended_count'] += 1
                    
                    # القسط حسب نوع الدراسة
                    fee = self._get_fee_for_study_type(teacher, study_type)
                    
                    # تطبيق خصم الطالب
                    discount_info = {
                        'discount_type': discount_type,
                        'discount_value': discount_value,
                        'institute_waiver': institute_waiver,
                    }
                    effective_fee = self._apply_discount_to_fee(fee, discount_info)
                    
                    # إضافة للإجمالي
                    result[tid]['total_fees'] += effective_fee
                    
                    # حساب خصم المعهد لهذا الطالب
                    ded_type, ded_value = self._get_deduction_for_study_type(teacher, study_type)
                    
                    if ded_value > 0 and effective_fee > 0:
                        # تخطي الطلاب مجانيين مع تنازل المعهد
                        if discount_type == 'free' and institute_waiver:
                            pass  # لا خصم
                        elif ded_type == 'manual':
                            # المبلغ اليدوي هو المبلغ الكامل للقسطين معاً
                            result[tid]['expected_deduction'] += ded_value
                        else:
                            # نسبة مئوية من القسط الفعلي
                            result[tid]['expected_deduction'] += round(effective_fee * ded_value / 100)
                except Exception as link_err:
                    logger.error(f"خطأ في حساب رابط الطالب {link.get('student_id')} للمدرس {link.get('teacher_id')}: {link_err}")
                    continue
            
            # حساب المستحق
            for tid in teacher_ids:
                r = result[tid]
                r['teacher_due'] = r['total_fees'] - r['expected_deduction']
            
        except Exception as e:
            logger.error(f"خطأ في حساب مستحق المدرسين المتوقع: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # محاولة حساب فردي لكل مدرس
            for tid in teacher_ids:
                try:
                    individual_result = self._calculate_expected_teacher_due_single(tid)
                    result[tid] = individual_result
                except Exception as inner_e:
                    logger.error(f"خطأ في الحساب الفردي للمدرس {tid}: {inner_e}")
        
        return result
    
    def _calculate_expected_teacher_due_single(self, teacher_id: int) -> Dict:
        """حساب مستحق المدرس المتوقع بشكل فردي - fallback عند فشل الحساب المجمّع"""
        db = self.db
        
        # جلب بيانات المدرس
        teacher_data = db.execute_query(
            "SELECT id, total_fee, fee_in_person, fee_electronic, fee_blended, "
            "institute_deduction_type, institute_deduction_value, "
            "institute_pct_in_person, institute_pct_electronic, institute_pct_blended, "
            "inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended, "
            "inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended, "
            "teaching_types FROM teachers WHERE id = %s",
            (teacher_id,)
        )
        if not teacher_data:
            return {'total_fees': 0, 'expected_deduction': 0, 'teacher_due': 0,
                    'in_person_count': 0, 'electronic_count': 0, 'blended_count': 0}
        
        teacher = teacher_data[0]
        
        # جلب روابط الطلاب
        links = db.execute_query(
            "SELECT student_id, study_type, discount_type, discount_value, institute_waiver "
            "FROM student_teacher WHERE teacher_id = %s AND status = 'مستمر'",
            (teacher_id,)
        ) or []
        
        r = {'total_fees': 0, 'expected_deduction': 0, 'teacher_due': 0,
             'in_person_count': 0, 'electronic_count': 0, 'blended_count': 0}
        
        for link in links:
            study_type = link.get('study_type', 'حضوري') or 'حضوري'
            discount_type = link.get('discount_type', 'none') or 'none'
            discount_value = link.get('discount_value', 0) or 0
            institute_waiver = link.get('institute_waiver', 0) or 0
            
            if study_type == 'حضوري':
                r['in_person_count'] += 1
            elif study_type == 'الكتروني':
                r['electronic_count'] += 1
            elif study_type == 'مدمج':
                r['blended_count'] += 1
            
            fee = self._get_fee_for_study_type(teacher, study_type)
            discount_info = {
                'discount_type': discount_type,
                'discount_value': discount_value,
                'institute_waiver': institute_waiver,
            }
            effective_fee = self._apply_discount_to_fee(fee, discount_info)
            r['total_fees'] += effective_fee
            
            ded_type, ded_value = self._get_deduction_for_study_type(teacher, study_type)
            if ded_value > 0 and effective_fee > 0:
                if discount_type == 'free' and institute_waiver:
                    pass
                elif ded_type == 'manual':
                    r['expected_deduction'] += ded_value
                else:
                    r['expected_deduction'] += round(effective_fee * ded_value / 100)
        
        r['teacher_due'] = r['total_fees'] - r['expected_deduction']
        return r
    
    # =====================================================
    # دوال الإحصائيات العامة - محسّنة بسرعة فائقة
    # =====================================================
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """
        الحصول على إحصائيات عامة عن النظام - محسّنة باستعلام واحد
        """
        db = self.db
        stats = {}
        
        try:
            # ===== استعلام واحد يجلب كل الإحصائيات الأساسية =====
            stats_query = '''
                SELECT
                    (SELECT COUNT(*) FROM students) as total_students,
                    (SELECT COUNT(DISTINCT s.id) FROM students s INNER JOIN student_teacher st ON st.student_id = s.id WHERE st.status = 'مستمر') as active_students,
                    (SELECT COUNT(*) FROM students s WHERE NOT EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id)) as unlinked_students,
                    (SELECT COUNT(*) FROM teachers) as total_teachers,
                    (SELECT COUNT(DISTINCT subject) FROM teachers) as total_subjects,
                    (SELECT COUNT(*) FROM installments) as total_installments,
                    (SELECT COALESCE(SUM(amount), 0) FROM installments) as total_amount_paid,
                    (SELECT COALESCE(SUM(amount), 0) FROM teacher_withdrawals) as total_withdrawals
            '''
            result = db.execute_query(stats_query)
            if result:
                r = result[0]
                stats['total_students'] = r['total_students']
                stats['active_students'] = r['active_students']
                stats['withdrawn_students'] = 0
                stats['unlinked_students'] = r['unlinked_students']
                stats['total_teachers'] = r['total_teachers']
                stats['total_subjects'] = r['total_subjects']
                stats['total_installments'] = r['total_installments']
                stats['total_amount_paid'] = r['total_amount_paid']
                stats['total_withdrawals'] = r['total_withdrawals']
            else:
                stats = {
                    'total_students': 0, 'active_students': 0, 'withdrawn_students': 0,
                    'unlinked_students': 0, 'total_teachers': 0, 'total_subjects': 0,
                    'total_installments': 0, 'total_amount_paid': 0, 'total_withdrawals': 0
                }
        except Exception as e:
            print(f"Error getting statistics: {e}")
            stats = {
                'total_students': 0, 'active_students': 0, 'withdrawn_students': 0,
                'unlinked_students': 0, 'total_teachers': 0, 'total_subjects': 0,
                'total_installments': 0, 'total_amount_paid': 0, 'total_withdrawals': 0
            }
        
        # صافي الإيرادات = مجموع خصم المعهد من جميع المدرسين
        total_institute_deduction = 0
        try:
            all_teachers = db.execute_query("SELECT id FROM teachers")
            if all_teachers:
                teacher_ids = [t['id'] for t in all_teachers]
                deduction_map = self.calculate_institute_deduction_batch(teacher_ids)
                total_institute_deduction = sum(deduction_map.values())
        except:
            pass
        
        stats['total_institute_deduction'] = total_institute_deduction
        
        # عدد الطلاب غير المسددين - استعلام محسّن
        try:
            unpaid_query = '''
                SELECT COUNT(DISTINCT st.student_id) as unpaid_count
                FROM student_teacher st
                WHERE st.status = 'مستمر'
                AND EXISTS (
                    SELECT 1 FROM installments i
                    WHERE i.student_id = st.student_id AND i.teacher_id = st.teacher_id
                )
                AND (
                    CASE
                        WHEN st.study_type = 'الكتروني' AND (SELECT fee_electronic FROM teachers WHERE id = st.teacher_id) > 0
                            THEN (SELECT fee_electronic FROM teachers WHERE id = st.teacher_id)
                        WHEN st.study_type = 'مدمج' AND (SELECT fee_blended FROM teachers WHERE id = st.teacher_id) > 0
                            THEN (SELECT fee_blended FROM teachers WHERE id = st.teacher_id)
                        WHEN st.study_type = 'حضوري' AND (SELECT fee_in_person FROM teachers WHERE id = st.teacher_id) > 0
                            THEN (SELECT fee_in_person FROM teachers WHERE id = st.teacher_id)
                        ELSE (SELECT total_fee FROM teachers WHERE id = st.teacher_id)
                    END
                    >
                    COALESCE((SELECT SUM(amount) FROM installments WHERE student_id = st.student_id AND teacher_id = st.teacher_id), 0)
                )
            '''
            unpaid_result = db.execute_query(unpaid_query)
            stats['unpaid_students'] = unpaid_result[0]['unpaid_count'] if unpaid_result else 0
        except:
            stats['unpaid_students'] = 0
        
        return stats


# ===== إنشاء نسخة واحدة من الخدمة (Singleton) =====
finance_service = FinanceService()


def sync_student_status(student_id: int):
    """تحديث حالة الطالب في جدول students بناءً على روابط student_teacher"""
    db = Database()
    try:
        result = db.execute_query('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'منسحب' THEN 1 ELSE 0 END) as withdrawn
            FROM student_teacher 
            WHERE student_id = %s
        ''', (student_id,))
        
        if not result or result[0]['total'] == 0:
            new_status = 'غير مربوط'
        elif result[0]['withdrawn'] == result[0]['total']:
            new_status = 'منسحب'
        else:
            new_status = 'مستمر'
        
        db.execute_query("UPDATE students SET status = %s WHERE id = %s", (new_status, student_id))
    except Exception:
        pass
