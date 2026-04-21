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
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # AUTOINCREMENT → SERIAL
        # INTEGER → INTEGER أو BIGINT
        # CHECK IN (...) → نفس الشيء يعمل في PostgreSQL
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                study_type VARCHAR(20) CHECK(study_type IN ('حضوري', 'الكتروني')) DEFAULT 'حضوري',
                has_card INTEGER NOT NULL DEFAULT 0,
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
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_db():
    """Dependency للحصول على اتصال قاعدة البيانات في FastAPI"""
    db = Database()
    try:
        yield db.get_connection()
    finally:
        pass  # لا نغلق الاتصال هنا لأنه singleton
