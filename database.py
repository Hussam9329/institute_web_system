import psycopg2
from psycopg2.extras import RealDictCursor
import os

class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """اتصال جديد كل مرة (serverless-safe)"""
        return psycopg2.connect(os.environ.get("DATABASE_URL"), cursor_factory=RealDictCursor)
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                # RealDictCursor يرجع dict مباشرة ← نفس شكل sqlite3.Row
                return results
            else:
                conn.commit()
                return []
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()  # مهم: نغلق الاتصال كل مرة
