#!/usr/bin/env python3
# ============================================
# clean_database.py - سكربت تنظيف شامل لقاعدة البيانات
# يحذف جميع البيانات التشغيلية ويحافظ على إعدادات النظام
# ============================================

import sys
import os

# إضافة المسار الحالي للمشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database


def clean_database():
    """تنظيف شامل لقاعدة البيانات - حذف جميع البيانات التشغيلية"""
    db = Database()
    
    # ترتيب الحذف يجب أن يحترم القيود الأجنبية (Foreign Keys)
    # نحذف الجداول التي تعتمد على غيرها أولاً
    
    tables_to_clean = [
        # 1. الارتباطات بين الطلاب والمدرسين (تعتمد على students و teachers)
        ("student_teacher", "الارتباطات"),
        # 2. الأقساط (تعتمد على students و teachers)
        ("installments", "الأقساط"),
        # 3. السحوبات (تعتمد على teachers)
        ("teacher_withdrawals", "السحوبات"),
        # 4. الجدول الأسبوعي (يعتمد على rooms و teachers)
        ("weekly_schedule", "الجدول الأسبوعي"),
        # 5. سجل العمليات
        ("operation_logs", "سجل العمليات"),
        # 6. الطلاب
        ("students", "الطلاب"),
        # 7. المدرسين
        ("teachers", "المدرسين"),
        # 8. المواد الدراسية
        ("subjects", "المواد الدراسية"),
        # 9. القاعات
        ("rooms", "القاعات"),
    ]
    
    # تسلسلات يجب إعادة تعيينها بعد الحذف
    sequences_to_reset = [
        ("students_id_seq", "الطلاب"),
        ("teachers_id_seq", "المدرسين"),
        ("subjects_id_seq", "المواد"),
        ("installments_id_seq", "الأقساط"),
        ("teacher_withdrawals_id_seq", "السحوبات"),
        ("rooms_id_seq", "القاعات"),
        ("weekly_schedule_id_seq", "الجدول الأسبوعي"),
        ("operation_logs_id_seq", "سجل العمليات"),
    ]
    
    print("=" * 60)
    print("🧹 بدء تنظيف قاعدة البيانات...")
    print("=" * 60)
    
    # ===== المرحلة 1: حذف البيانات =====
    print("\n📋 المرحلة 1: حذف البيانات")
    print("-" * 40)
    
    for table_name, arabic_name in tables_to_clean:
        try:
            # عدد السجلات قبل الحذف
            count_result = db.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            count = count_result[0]['cnt'] if count_result else 0
            
            if count > 0:
                # حذف جميع البيانات
                db.execute_query(f"DELETE FROM {table_name}")
                print(f"  ✅ {arabic_name} ({table_name}): تم حذف {count} سجل")
            else:
                print(f"  ⏭️  {arabic_name} ({table_name}): فارغ بالفعل")
        except Exception as e:
            print(f"  ❌ {arabic_name} ({table_name}): خطأ - {e}")
    
    # ===== المرحلة 2: إعادة تعيين العدادات (Sequences) =====
    print("\n🔄 المرحلة 2: إعادة تعيين العدادات")
    print("-" * 40)
    
    for seq_name, arabic_name in sequences_to_reset:
        try:
            db.execute_query(f"ALTER SEQUENCE {seq_name} RESTART WITH 1")
            print(f"  ✅ {arabic_name} ({seq_name}): تم إعادة التعيين إلى 1")
        except Exception as e:
            print(f"  ⚠️  {arabic_name} ({seq_name}): تخطي - {e}")
    
    # ===== المرحلة 3: التحقق من النظافة =====
    print("\n🔍 المرحلة 3: التحقق من نظافة قاعدة البيانات")
    print("-" * 40)
    
    all_clean = True
    for table_name, arabic_name in tables_to_clean:
        try:
            count_result = db.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            count = count_result[0]['cnt'] if count_result else 0
            if count == 0:
                print(f"  ✅ {arabic_name}: نظيف (0 سجل)")
            else:
                print(f"  ❌ {arabic_name}: يوجد {count} سجل متبقي!")
                all_clean = False
        except Exception as e:
            print(f"  ⚠️  {arabic_name}: خطأ في التحقق - {e}")
    
    # ===== النتيجة النهائية =====
    print("\n" + "=" * 60)
    if all_clean:
        print("🎉 تم تنظيف قاعدة البيانات بنجاح 100%!")
    else:
        print("⚠️  تم التنظيف مع بعض التحذيرات - راجع النتائج أعلاه")
    print("=" * 60)
    
    # معلومات عن البيانات المحفوظة
    print("\n📌 البيانات المحفوظة (إعدادات النظام):")
    saved_tables = [
        ("users", "المستخدمين"),
        ("roles", "الأدوار"),
        ("permissions", "الصلاحيات"),
        ("role_permissions", "صلاحيات الأدوار"),
    ]
    for table_name, arabic_name in saved_tables:
        try:
            count_result = db.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            count = count_result[0]['cnt'] if count_result else 0
            print(f"  🔒 {arabic_name} ({table_name}): {count} سجل محفوظ")
        except Exception:
            print(f"  🔒 {arabic_name} ({table_name}): محفوظ")


if __name__ == "__main__":
    clean_database()
