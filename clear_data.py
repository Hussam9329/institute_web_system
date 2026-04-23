import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_3fTtMYrvCw9m@ep-muddy-boat-anvp37bx-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cursor = conn.cursor()

try:
    cursor.execute("TRUNCATE TABLE installments, teacher_withdrawals, student_teacher, students, teachers, subjects RESTART IDENTITY CASCADE")
    conn.commit()
    print("تم حذف جميع البيانات بنجاح")
except Exception as e:
    conn.rollback()
    print(f"خطأ: {e}")

# Verify
for table in ["subjects", "teachers", "students", "student_teacher", "installments", "teacher_withdrawals"]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"  {table}: {cursor.fetchone()[0]} صف")

cursor.close()
conn.close()
