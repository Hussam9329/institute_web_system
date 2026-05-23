# ============================================
# services/deletion_guard_service.py
# خدمة مركزية لمنع الحذف - جميع قواعد الحماية في مكان واحد
# ============================================

import logging
from database import Database
from trial_mode import is_trial_username

logger = logging.getLogger(__name__)


class DeletionGuardResult:
    """نتيجة فحص إمكانية الحذف - موحدة لجميع أنواع الكيانات"""

    def __init__(self, allowed: bool, message: str, reason_code: str = "", details: dict = None):
        self.allowed = allowed
        self.success = allowed  # ملائمة للواجهة
        self.message = message
        self.reason_code = reason_code
        self.details = details or {}

    def to_dict(self) -> dict:
        """تحويل النتيجة إلى قاموس للاستخدام في API"""
        return {
            "allowed": self.allowed,
            "success": self.success,
            "message": self.message,
            "reason_code": self.reason_code,
            "details": self.details,
        }


class DeletionGuardService:
    """خدمة مركزية لفحص إمكانية حذف أي كيان قبل تنفيذ الحذف"""

    # ===== المواد الدراسية =====

    def can_delete_subject(self, subject_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف مادة دراسية.
        القاعدة: لا يمكن حذف مادة مرتبطة بمدرسين.
        """
        db = Database()
        try:
            subject_info = db.execute_query("SELECT name FROM subjects WHERE id = %s", (subject_id,))
            if not subject_info:
                return DeletionGuardResult(
                    allowed=False,
                    message="المادة غير موجودة",
                    reason_code="subject_not_found",
                )

            subject_name = subject_info[0]['name']
            teachers_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM teachers WHERE subject = %s",
                (subject_name,)
            )
            cnt = teachers_count[0]['cnt'] if teachers_count else 0

            if cnt > 0:
                return DeletionGuardResult(
                    allowed=False,
                    message=f"لا يمكن حذف مادة \"{subject_name}\" لأنها مرتبطة بـ {cnt} مدرس. انقل المدرسين إلى مادة أخرى أو احذف ارتباطهم أولاً.",
                    reason_code="subject_has_teachers",
                    details={"subject_name": subject_name, "teachers_count": cnt},
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف المادة",
                reason_code="",
                details={"subject_name": subject_name},
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف المادة {subject_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== الطلاب =====

    def can_delete_student(self, student_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف طالب.
        القواعد:
        - لا يمكن حذف طالب مرتبط بمدرسين نشطين.
        - لا يمكن حذف طالب لديه أقساط.
        """
        db = Database()
        try:
            student_info = db.execute_query("SELECT name FROM students WHERE id = %s", (student_id,))
            if not student_info:
                return DeletionGuardResult(
                    allowed=False,
                    message="الطالب غير موجود",
                    reason_code="student_not_found",
                )

            student_name = student_info[0]['name']
            reasons = []

            # فحص الروابط النشطة مع المدرسين
            active_links = db.execute_query(
                "SELECT COUNT(*) as cnt FROM student_teacher WHERE student_id = %s AND status = 'مستمر'",
                (student_id,)
            )
            active_cnt = active_links[0]['cnt'] if active_links else 0
            if active_cnt > 0:
                reasons.append(f"مرتبط بـ {active_cnt} مدرس نشط")

            # فحص الأقساط
            installments_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s",
                (student_id,)
            )
            inst_cnt = installments_count[0]['cnt'] if installments_count else 0
            if inst_cnt > 0:
                reasons.append(f"لديه {inst_cnt} قسط مسجل")

            if reasons:
                reason_text = " و ".join(reasons)
                return DeletionGuardResult(
                    allowed=False,
                    message=f"لا يمكن حذف الطالب \"{student_name}\" لأنه {reason_text}. احذف الارتباطات والأقساط أولاً.",
                    reason_code="student_has_dependencies",
                    details={
                        "student_name": student_name,
                        "active_links": active_cnt,
                        "installments_count": inst_cnt,
                    },
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف الطالب",
                reason_code="",
                details={"student_name": student_name},
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف الطالب {student_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== المدرسين =====

    def can_delete_teacher(self, teacher_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف مدرس.
        القواعد:
        - لا يمكن حذف مدرس لديه طالبات.
        - لا يمكن حذف مدرس لديه أقساط.
        - لا يمكن حذف مدرس لديه سحوبات.
        - لا يمكن حذف مدرس لديه مواعيد في الجدول.
        """
        db = Database()
        try:
            teacher_info = db.execute_query("SELECT name, subject FROM teachers WHERE id = %s", (teacher_id,))
            if not teacher_info:
                return DeletionGuardResult(
                    allowed=False,
                    message="المدرس غير موجود",
                    reason_code="teacher_not_found",
                )

            teacher_name = teacher_info[0]['name']
            reasons = []

            # فحص الطلاب المرتبطين (حالة مستمر)
            active_students = db.execute_query(
                "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s AND status = 'مستمر'",
                (teacher_id,)
            )
            students_cnt = active_students[0]['cnt'] if active_students else 0
            if students_cnt > 0:
                reasons.append(f"لديه {students_cnt} طالب مرتبط")

            # فحص الأقساط
            installments_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM installments WHERE teacher_id = %s",
                (teacher_id,)
            )
            inst_cnt = installments_count[0]['cnt'] if installments_count else 0
            if inst_cnt > 0:
                reasons.append(f"لديه {inst_cnt} قسط مسجل")

            # فحص السحوبات
            withdrawals_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM teacher_withdrawals WHERE teacher_id = %s",
                (teacher_id,)
            )
            with_cnt = withdrawals_count[0]['cnt'] if withdrawals_count else 0
            if with_cnt > 0:
                reasons.append(f"لديه {with_cnt} سحب مسجل")

            # فحص مواعيد الجدول
            schedule_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM weekly_schedule WHERE teacher_id = %s",
                (teacher_id,)
            )
            sched_cnt = schedule_count[0]['cnt'] if schedule_count else 0
            if sched_cnt > 0:
                reasons.append(f"لديه {sched_cnt} موعد في الجدول")

            if reasons:
                reason_text = " و ".join(reasons)
                return DeletionGuardResult(
                    allowed=False,
                    message=f"لا يمكن حذف المدرس \"{teacher_name}\" لأنه {reason_text}. احذف جميع الارتباطات أولاً.",
                    reason_code="teacher_has_dependencies",
                    details={
                        "teacher_name": teacher_name,
                        "active_students": students_cnt,
                        "installments_count": inst_cnt,
                        "withdrawals_count": with_cnt,
                        "schedule_count": sched_cnt,
                    },
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف المدرس",
                reason_code="",
                details={"teacher_name": teacher_name},
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف المدرس {teacher_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== الأقساط =====

    def can_delete_installment(self, installment_id: int, user: dict = None) -> DeletionGuardResult:
        """
        فحص إمكانية حذف قسط.
        القاعدة: لا يمكن حذف قسط إلا إذا كان المستخدم بدور "مدير عام".
        """
        db = Database()
        try:
            installment = db.execute_query("SELECT * FROM installments WHERE id = %s", (installment_id,))

            if not installment:
                return DeletionGuardResult(
                    allowed=False,
                    message="القسط غير موجود",
                    reason_code="installment_not_found",
                )

            # فحص صلاحية المستخدم
            if not user:
                return DeletionGuardResult(
                    allowed=False,
                    message="يجب تسجيل الدخول أولاً",
                    reason_code="not_authenticated",
                )

            user_role = user.get('role_name', '')
            username = user.get('username', '')
            # الحسابات التجريبية ومدير العام يمكنهم حذف الأقساط
            if user_role != 'مدير عام' and not is_trial_username(username):
                return DeletionGuardResult(
                    allowed=False,
                    message="لا يمكن حذف القسط! فقط مدير النظام (مدير عام) يمكنه حذف الأقساط المدفوعة",
                    reason_code="installment_requires_admin",
                    details={"user_role": user_role},
                )

            inst_data = dict(installment[0])

            # منع حذف القسط إذا كان المدرس قد سحب مستحقاته بعد تسجيله
            locked_withdrawal = db.execute_query(
                """
                SELECT id, amount, withdrawal_date
                FROM teacher_withdrawals
                WHERE teacher_id = %s
                  AND withdrawal_date >= %s
                ORDER BY withdrawal_date ASC
                LIMIT 1
                """,
                (inst_data["teacher_id"], inst_data["payment_date"])
            )

            if locked_withdrawal:
                w = locked_withdrawal[0]
                return DeletionGuardResult(
                    allowed=False,
                    message=(
                        "لا يمكن حذف هذا القسط لأن المدرس سحب مستحقاته بعد تسجيله. "
                        f"تاريخ القسط: {inst_data['payment_date']}، "
                        f"وأول سحب لاحق/مطابق بتاريخ: {w['withdrawal_date']}."
                    ),
                    reason_code="installment_locked_by_teacher_withdrawal",
                    details={
                        "installment_id": installment_id,
                        "teacher_id": inst_data["teacher_id"],
                        "payment_date": str(inst_data["payment_date"]),
                        "withdrawal_id": w["id"],
                        "withdrawal_date": str(w["withdrawal_date"]),
                        "withdrawal_amount": float(w["amount"]) if w.get("amount") is not None else None,
                    },
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف القسط",
                reason_code="",
                details={"installment": inst_data},
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف القسط {installment_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== السحوبات =====

    def can_delete_withdrawal(self, withdrawal_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف سحب.
        القاعدة: يمكن حذف أي سحب موجود.
        """
        db = Database()
        try:
            existing = db.execute_query("SELECT id FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
            if not existing:
                return DeletionGuardResult(
                    allowed=False,
                    message="السحب غير موجود",
                    reason_code="withdrawal_not_found",
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف السحب",
                reason_code="",
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف السحب {withdrawal_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== القاعات =====

    def can_delete_room(self, room_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف قاعة.
        القاعدة: لا يمكن حذف قاعة مستخدمة في الجدول الأسبوعي.
        """
        db = Database()
        try:
            room_info = db.execute_query("SELECT name FROM rooms WHERE id = %s", (room_id,))
            if not room_info:
                return DeletionGuardResult(
                    allowed=False,
                    message="القاعة غير موجودة",
                    reason_code="room_not_found",
                )

            room_name = room_info[0]['name']

            # فحص وجود محاضرات مرتبطة
            schedule_count = db.execute_query(
                "SELECT COUNT(*) as cnt FROM weekly_schedule WHERE room_id = %s",
                (room_id,)
            )
            cnt = schedule_count[0]['cnt'] if schedule_count else 0

            if cnt > 0:
                return DeletionGuardResult(
                    allowed=False,
                    message=f"لا يمكن حذف القاعة \"{room_name}\" لأنها مستخدمة في {cnt} موعد في الجدول الأسبوعي. احذف أو انقل المواعيد أولاً.",
                    reason_code="room_has_schedule",
                    details={"room_name": room_name, "schedule_count": cnt},
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف القاعة",
                reason_code="",
                details={"room_name": room_name},
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف القاعة {room_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )

    # ===== الجدول الأسبوعي =====

    def can_delete_weekly_schedule(self, lecture_id: int) -> DeletionGuardResult:
        """
        فحص إمكانية حذف موعد من الجدول الأسبوعي.
        القاعدة: لا يمكن حذف موعد غير موجود.
        """
        db = Database()
        try:
            existing = db.execute_query("SELECT id FROM weekly_schedule WHERE id = %s", (lecture_id,))
            if not existing:
                return DeletionGuardResult(
                    allowed=False,
                    message="الموعد غير موجود في الجدول",
                    reason_code="schedule_not_found",
                )

            return DeletionGuardResult(
                allowed=True,
                message="يمكن حذف الموعد",
                reason_code="",
            )
        except Exception as e:
            logger.error(f"خطأ في فحص حذف الموعد {lecture_id}: {e}")
            return DeletionGuardResult(
                allowed=False,
                message=f"خطأ في فحص إمكانية الحذف: {str(e)}",
                reason_code="error",
            )


# ===== نسخة وحيدة (Singleton) =====
_deletion_guard_service = DeletionGuardService()
