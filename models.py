# ============================================
# models.py - نماذج البيانات (Pydantic Models)
# ============================================

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from config import STUDY_TYPES, STUDENT_STATUSES, INSTALLMENT_TYPES


# ===== نماذج الطلاب =====

class StudentBase(BaseModel):
    """الحقوق الأساسية للطالب"""
    name: str = Field(..., min_length=2, max_length=100, description="اسم الطالب")
    study_type: str = Field(default="حضوري", description="نوع الدراسة")
    notes: Optional[str] = Field(default="", description="ملاحظات")
    
    @validator('study_type')
    def validate_study_type(cls, v):
        if v not in STUDY_TYPES:
            raise ValueError(f'نوع الدراسة يجب أن يكون من: {STUDY_TYPES}')
        return v


class StudentCreate(StudentBase):
    """نموذج إنشاء طالب جديد"""
    pass


class StudentUpdate(BaseModel):
    """نموذج تحديث بيانات طالب"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    study_type: Optional[str] = None
    notes: Optional[str] = None


class StudentResponse(StudentBase):
    """نموذج استجابة الطالب (مع ID)"""
    id: int
    barcode: str
    created_at: str
    
    class Config:
        from_attributes = True


# ===== نماذج المدرسين =====

class TeacherBase(BaseModel):
    """الحقوق الأساسية للمدرس"""
    name: str = Field(..., min_length=2, max_length=100, description="اسم المدرس")
    subject: str = Field(..., min_length=2, max_length=50, description="المادة التي يدرسها")
    total_fee: int = Field(default=0, ge=0, description="الأجر الكلي (بالدينار)")
    institute_deduction_type: str = Field(default="percentage", description="نوع نسبة المعهد: percentage أو manual")
    institute_deduction_value: int = Field(default=0, ge=0, description="قيمة نسبة المعهد")
    notes: Optional[str] = Field(default="", description="ملاحظات")


class TeacherCreate(TeacherBase):
    """نموذج إنشاء مدرس جديد"""
    pass


class TeacherUpdate(BaseModel):
    """نموذج تحديث بيانات مدرس"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    subject: Optional[str] = Field(None, min_length=2, max_length=50)
    total_fee: Optional[int] = Field(None, ge=0)
    institute_deduction_type: Optional[str] = None
    institute_deduction_value: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class TeacherResponse(TeacherBase):
    """نموذج استجابة المدرس (مع ID)"""
    id: int
    created_at: str
    
    class Config:
        from_attributes = True


# ===== نماذج الأقساط =====

class InstallmentBase(BaseModel):
    """الحقوق الأساسية للقسط"""
    amount: int = Field(..., gt=0, description="مبلغ القسط (بالدينار)")
    payment_date: str = Field(..., description="تاريخ الدفع")
    installment_type: str = Field(default="القسط الأول", description="نوع القسط")
    notes: Optional[str] = Field(default="", description="ملاحظات")
    
    @validator('installment_type')
    def validate_installment_type(cls, v):
        if v not in INSTALLMENT_TYPES:
            raise ValueError(f'نوع القسط يجب أن يكون من: {INSTALLMENT_TYPES}')
        return v


class InstallmentCreate(InstallmentBase):
    """نموذج إنشاء قسط جديد"""
    student_id: int = Field(..., description="رقم الطالب")
    teacher_id: int = Field(..., description="رقم المدرس")


class InstallmentResponse(InstallmentBase):
    """نموذج استجابة القسط"""
    id: int
    student_id: int
    teacher_id: int
    
    class Config:
        from_attributes = True


# ===== نماذج السحوبات =====

class WithdrawalBase(BaseModel):
    """الحقوق الأساسية للسحب"""
    amount: int = Field(..., gt=0, description="مبلغ السحب (بالدينار)")
    withdrawal_date: str = Field(..., description="تاريخ السحب")
    notes: Optional[str] = Field(default="", description="ملاحظات")


class WithdrawalCreate(WithdrawalBase):
    """نموذج إنشاء سحب جديد"""
    teacher_id: int = Field(..., description="رقم المدرس")


class WithdrawalResponse(WithdrawalBase):
    """نموذج استجابة السحب"""
    id: int
    teacher_id: int
    
    class Config:
        from_attributes = True


# ===== نموذج ربط الطالب بمدرس =====

class StudentTeacherLink(BaseModel):
    """نموذج ربط طالب بمدرس"""
    student_id: int
    teacher_id: int
    study_type: str = "حضوري"
    status: str = "مستمر"
    notes: Optional[str] = ""


# ===== نماذج التقارير =====

class FinancialSummary(BaseModel):
    """ملخص مالي"""
    total_students: int = 0
    active_students: int = 0
    total_teachers: int = 0
    total_installments: int = 0
    total_amount_paid: int = 0
    total_withdrawals: int = 0