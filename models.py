# ============================================
# models.py - نماذج البيانات (Pydantic Models)
# ============================================

from pydantic import BaseModel, Field
from typing import Optional


# ===== نماذج نظام الصلاحيات =====

class RoleCreate(BaseModel):
    """نموذج إنشاء دور جديد"""
    name: str = Field(..., min_length=2, max_length=50, description="اسم الدور")
    description: Optional[str] = Field(default="", description="وصف الدور")

class RoleUpdate(BaseModel):
    """نموذج تحديث دور"""
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = None

class UserCreate(BaseModel):
    """نموذج إنشاء مستخدم جديد"""
    username: str = Field(..., min_length=3, max_length=50, description="اسم المستخدم")
    full_name: str = Field(..., min_length=2, max_length=100, description="الاسم الكامل")
    password: str = Field(..., min_length=4, description="كلمة المرور")
    role_id: int = Field(..., description="رقم الدور")

class UserUpdate(BaseModel):
    """نموذج تحديث مستخدم"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    password: Optional[str] = Field(None, min_length=4)
    role_id: Optional[int] = None
    is_active: Optional[int] = None

class RolePermissionsUpdate(BaseModel):
    """نموذج تحديث صلاحيات دور"""
    permission_ids: list[int] = Field(..., description="قائمة معرفات الصلاحيات")
