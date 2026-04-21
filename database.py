# ============================================
# database.py - إدارة قاعدة البيانات SQLite
# ============================================

import sqlite3
import os
from datetime import datetime
from config import DATABASE_NAME, BASE_DIR, get_current_date

class Database:
    """إدارة اتصال وقاعدة البيانات"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connection = None
        return cls._instance
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        if self.connection is None:
            db_path = os.path.join(BASE_DIR, DATABASE_NAME)
            self.connection = sqlite3.connect(db_path)
            self.connection.row_factory = sqlite3.Row  # إرجاع النتائج كـ dictionary
        return self.connection
    
    def close(self):
        """إغلاق الاتصال"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """تنفيذ استعلام وإرجاع النتائج"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            conn.commit()
            
            # إذا كان الاستعلام SELECT، أرجع النتائج
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                return []
                
        except Exception as e:
            conn.rollback()
            raise e


def init_db():
    """
    تهيئة قاعدة البيانات وإنشاء الجداول
    هذه الدالة آمنة للتشغيل المتكرر
    """
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # ===== جدول الطلاب =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                study_type TEXT CHECK(study_type IN ('حضوري', 'الكتروني')) DEFAULT 'حضوري',
                has_card INTEGER NOT NULL DEFAULT 0,
                has_badge INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'مستمر',
                barcode TEXT UNIQUE NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        # ===== جدول المدرسين =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                total_fee INTEGER NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        # ===== جدول العلاقة بين الطلاب والمدرسين =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_teacher (
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                PRIMARY KEY (student_id, teacher_id),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        # ===== جدول الأقساط =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS installments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                installment_type TEXT NOT NULL DEFAULT 'القسط الأول',
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        # ===== جدول سحوبات المدرسين =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                withdrawal_date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        print("✅ تم تهيئة قاعدة البيانات بنجاح!")
        
    except Exception as e:
        print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
        raise e


def get_db():
    """Dependency للحصول على اتصال قاعدة البيانات في FastAPI"""
    db = Database()
    try:
        yield db.get_connection()
    finally:
        pass  # لا نغلق الاتصال هنا لأنه singleton