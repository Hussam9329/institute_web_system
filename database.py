# ============================================
# database.py - إدارة قاعدة البيانات PostgreSQL (Neon)
# ============================================

import psycopg2
import psycopg2.extras
import os
from config import DATABASE_URL

class Database:
    """إدارة اتصال وقاعدة البيانات PostgreSQL"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات PostgreSQL"""
        connection = psycopg2.connect(DATABASE_URL)
        connection.autocommit = False
        return connection
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """تنفيذ استعلام وإرجاع النتائج"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute(query, params)
            
            # إذا كان الاستعلام SELECT، أرجع النتائج
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT'):
                results = cursor.fetchall()
                return results
            # إذا كان الاستعلام يحتوي على RETURNING (INSERT/UPDATE/DELETE)
            elif 'RETURNING' in query_upper:
                results = cursor.fetchall()
                conn.commit()
                return results
            else:
                conn.commit()
                return []
                
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()


def init_db():
    """تهيئة قاعدة البيانات - إنشاء الجداول إذا لم تكن موجودة"""
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # جدول المواد الدراسية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                study_type VARCHAR(20) CHECK(study_type IN ('حضوري', 'الكتروني', 'مدمج')) DEFAULT 'حضوري',
                has_badge INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'مستمر',
                barcode VARCHAR(50) UNIQUE NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                subject VARCHAR(50) NOT NULL,
                total_fee INTEGER NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_teacher (
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                study_type VARCHAR(20) DEFAULT 'حضوري',
                status VARCHAR(20) DEFAULT 'مستمر',
                notes TEXT DEFAULT '',
                PRIMARY KEY (student_id, teacher_id),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS installments (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                installment_type VARCHAR(30) NOT NULL DEFAULT 'القسط الأول',
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_withdrawals (
                id SERIAL PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                withdrawal_date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        
        # ===== ALTER TABLE - إضافة أعمدة جديدة للجداول الموجودة =====
        alter_statements = [
            # إصلاح CHECK constraint لجدول الطلاب - إضافة 'مدمج' و 'غير مربوط'
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_study_type_check",
            "ALTER TABLE students ADD CONSTRAINT students_study_type_check CHECK(study_type IN ('حضوري', 'الكتروني', 'مدمج'))",
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_status_check",
            "ALTER TABLE students ADD CONSTRAINT students_status_check CHECK(status IN ('مستمر', 'منسحب', 'غير مربوط'))",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_type VARCHAR(20) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_value INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'مستمر'",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS study_type VARCHAR(20) DEFAULT 'حضوري'",
            # أعمدة أنواع التدريس المتعددة
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS teaching_types TEXT DEFAULT 'حضوري'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_blended INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_blended INTEGER DEFAULT 0",
            # نوع الخصم لكل نوع تدريس: percentage أو manual
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_in_person VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_electronic VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_blended VARCHAR(10) DEFAULT 'percentage'",
            # المبلغ اليدوي للخصم لكل نوع تدريس
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_blended INTEGER DEFAULT 0",
        ]
        
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
                conn.commit()
            except Exception:
                conn.rollback()
                pass  # العمود موجود مسبقاً
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_db():
    """Dependency للحصول على اتصال قاعدة البيانات في FastAPI"""
    db = Database()
    try:
        yield db.get_connection()
    finally:
        pass
