# ============================================
# seed_data.py - سكربت إضافة بيانات تجريبية
# ============================================

import psycopg2
import psycopg2.extras
import random
import string
from datetime import datetime, timedelta

DATABASE_URL = "postgresql://neondb_owner:npg_3fTtMYrvCw9m@ep-muddy-boat-anvp37bx-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# ===== أسماء عربية عشوائية =====
FIRST_NAMES_MALE = [
    "أحمد", "محمد", "علي", "حسين", "عمر", "خالد", "يوسف", "إبراهيم", "حسن", "عبدالله",
    "مصطفى", "كريم", "سعيد", "فارس", "رائد", "طارق", "زياد", "نعيم", "باسم", "جعفر",
    "مهندي", "رضا", "عباس", "ماجد", "وليد", "هشام", "أنس", "بلال", "معاذ", "آدم",
    "زياد", "رياض", "صلاح", "قاسم", "جاسم", "منصور", "نعيم", "شاكر", "عادل", "سامي",
    "رشيد", "حميد", "فهد", "سلمان", "بدر", "نواف", "مشعل", "حمد", "ناصر", "صالح",
    "عطا", "مرتضى", "همام", "درع", "عدي", "مقداد", "حارث", "أسامة", "حمزة", "يعرب",
    "لؤي", "ثامر", "غانم", "صبحي", "عصام", "فاضل", "ذنون", "خضير", "كاظم", "جلال"
]

FIRST_NAMES_FEMALE = [
    "فاطمة", "زينب", "مريم", "سارة", "نور", "هدى", "آية", "رنا", "لينا", "دانا",
    "إيمان", "هبة", "أمل", "دعاء", "رغد", "سلمى", "ياسمين", "روان", "جنى", "لمياء",
    "حنين", "مرام", "بثينة", "شيماء", "إسراء", "ملاك", "آناء", "شفاء", "رئيسة", "عائشة",
    "نادية", "وفاء", "ابتسام", "صفية", "كوثر", "لطيفة", "سمية", "نبيلة", "ثريا", "هند"
]

LAST_NAMES = [
    "الحسيني", "الموسوي", "الجعفري", "الصادقي", "العبيدي", "الخفاجي", "التميمي",
    "الشمري", "الحميداوي", "الحائري", "النجفي", "الكربلائي", "الجبوري", "الدليمي",
    "العاني", "الربيعي", "الخزرجي", "القريشي", "البغدادي", "الكوفي", "الصويري",
    "المالكي", "الهاشمي", "العلوي", "الأميري", "السعدي", "الراشدي", "المعاضيدي",
    "الزبيدي", "الغرباوي", "الشريفي", "النعماني", "الصائغ", "الحكمي", "الفرطوسي",
    "الحنون", "المظفر", "الوائلي", "الكاظمي", "الأعرجي", "البصري", "العميري",
    "المشنوق", "الساري", "الأحمد", "المحمدي", "العلواني", "الزيدي", "الطائي",
    "الكناني", "الحذاء", "المنصوري", "الشماخي", "الفهمي", "الجويلي"
]

# ===== المواد الدراسية =====
SUBJECTS = [
    "رياضيات", "فيزياء", "كيمياء", "لغة عربية", "لغة انجليزية",
    "أحياء", "تاريخ", "جغرافية", "تربية إسلامية", "علوم حاسوب"
]

STUDY_TYPES = ["حضوري", "الكتروني"]  # مدمج not in DB constraint yet


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def generate_name(gender=None):
    if gender is None:
        gender = random.choice(["male", "female"])
    if gender == "male":
        first = random.choice(FIRST_NAMES_MALE)
    else:
        first = random.choice(FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}", gender


def clear_all_data(conn):
    """حذف كل البيانات الموجودة"""
    cursor = conn.cursor()
    try:
        cursor.execute("TRUNCATE TABLE installments, teacher_withdrawals, student_teacher, students, teachers, subjects RESTART IDENTITY CASCADE")
        conn.commit()
        print("  تم حذف جميع البيانات وإعادة تعيين التسلسلات")
    except Exception as e:
        conn.rollback()
        print(f"  خطأ: {e}")
        # fallback
        for table in ["installments", "teacher_withdrawals", "student_teacher", "students", "teachers", "subjects"]:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except:
                pass
        conn.commit()
        for table in ["subjects", "students", "teachers", "installments", "teacher_withdrawals"]:
            try:
                cursor.execute(f"ALTER SEQUENCE {table}_id_seq RESTART WITH 1")
            except:
                pass
        conn.commit()
    cursor.close()


def seed_subjects(conn):
    """إضافة المواد الدراسية"""
    cursor = conn.cursor()
    subjects_map = {}
    today = datetime.now().strftime("%Y-%m-%d")
    
    for name in SUBJECTS:
        cursor.execute(
            "INSERT INTO subjects (name, created_at) VALUES (%s, %s) RETURNING id",
            (name, today)
        )
        sid = cursor.fetchone()[0]
        subjects_map[name] = sid
        print(f"  مادة: {name} (ID: {sid})")
    
    conn.commit()
    cursor.close()
    return subjects_map


def seed_teachers(conn, subjects_map):
    """إضافة المدرسين - 7-9 لكل مادة"""
    cursor = conn.cursor()
    teachers_data = {}  # subject_name -> list of (teacher_id, teacher_name)
    today = datetime.now().strftime("%Y-%m-%d")
    
    all_teacher_names = set()
    
    for subject_name, subject_id in subjects_map.items():
        num_teachers = random.randint(7, 9)
        teachers_data[subject_name] = []
        
        # Generate unique teacher names
        available_names = [n for n in FIRST_NAMES_MALE if n not in all_teacher_names]
        if len(available_names) < num_teachers:
            available_names = FIRST_NAMES_MALE  # fallback
        
        selected_first = random.sample(available_names, num_teachers)
        
        for i in range(num_teachers):
            first = selected_first[i]
            last = random.choice(LAST_NAMES)
            teacher_name = f"{first} {last}"
            all_teacher_names.add(first)
            
            total_fee = random.randint(500, 1500) * 1000  # 500,000 - 1,500,000 IQD
            teaching_type = random.choice(STUDY_TYPES)
            pct = random.randint(10, 25)
            
            cursor.execute("""
                INSERT INTO teachers (name, subject, total_fee, notes, created_at,
                    teaching_types, institute_deduction_type, institute_deduction_value,
                    fee_in_person, fee_electronic, fee_blended,
                    institute_pct_in_person, institute_pct_electronic, institute_pct_blended)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                teacher_name, subject_name, total_fee, "بيانات تجريبية", today,
                teaching_type, "percentage", pct,
                total_fee, total_fee, total_fee,
                pct, pct, pct
            ))
            tid = cursor.fetchone()[0]
            teachers_data[subject_name].append((tid, teacher_name))
            print(f"    مدرس: {teacher_name} - {subject_name} ({num_teachers})")
    
    conn.commit()
    cursor.close()
    return teachers_data


def seed_students(conn, teachers_data):
    """إضافة الطلاب - 40-50 لكل مدرس"""
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Track all created students to avoid duplicates and allow cross-teacher linking
    all_students = []  # list of student_id
    student_name_counter = {}  # track used names
    
    for subject_name, teacher_list in teachers_data.items():
        for teacher_id, teacher_name in teacher_list:
            num_students = random.randint(40, 50)
            
            # Generate students for this teacher
            for i in range(num_students):
                student_name, gender = generate_name()
                
                # Make name somewhat unique by adding a number if too common
                name_key = student_name
                if name_key in student_name_counter:
                    student_name_counter[name_key] += 1
                    # Add a distinguishing title
                    student_name = f"{student_name}"
                else:
                    student_name_counter[name_key] = 1
                
                study_type = random.choice(STUDY_TYPES)
                has_card = random.choice([0, 0, 0, 1])  # 25% chance
                has_badge = random.choice([0, 0, 0, 1])  # 25% chance
                status = "مستمر" if random.random() > 0.1 else "منسحب"  # 10% withdraw chance
                
                # Generate barcode
                barcode = f"STU-{datetime.now().year}-{str(len(all_students) + 1).zfill(6)}"
                
                cursor.execute("""
                    INSERT INTO students (name, study_type, has_card, has_badge, status, barcode, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (student_name, study_type, has_card, has_badge, status, barcode, "بيانات تجريبية", today))
                
                student_id = cursor.fetchone()[0]
                all_students.append(student_id)
                
                # Link student to teacher
                link_status = status  # if student is منسحب, link is منسحب
                cursor.execute("""
                    INSERT INTO student_teacher (student_id, teacher_id, study_type, status)
                    VALUES (%s, %s, %s, %s)
                """, (student_id, teacher_id, study_type, link_status))
            
            print(f"    {teacher_name}: {num_students} طالب")
            conn.commit()  # Commit per teacher to avoid huge transactions
    
    cursor.close()
    return all_students


def seed_installments(conn, teachers_data):
    """إضافة أقساط تجريبية لبعض الطلاب"""
    cursor = conn.cursor()
    
    for subject_name, teacher_list in teachers_data.items():
        for teacher_id, teacher_name in teacher_list:
            # Get students linked to this teacher
            cursor.execute("""
                SELECT st.student_id, s.name FROM student_teacher st
                JOIN students s ON st.student_id = s.id
                WHERE st.teacher_id = %s AND st.status = 'مستمر'
                ORDER BY RANDOM() LIMIT 15
            """, (teacher_id,))
            
            students = cursor.fetchall()
            if not students:
                continue
            
            for student_row in students:
                student_id = student_row[0]
                
                # Randomly add 1-2 installments
                num_installments = random.choice([1, 1, 1, 2])
                
                for inst_idx in range(num_installments):
                    amount = random.randint(50, 300) * 1000  # 50,000 - 300,000 IQD
                    
                    # Random date in last 3 months
                    days_ago = random.randint(1, 90)
                    payment_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    
                    if num_installments == 1:
                        inst_type = random.choice(["القسط الأول", "القسط الثاني", "دفع كامل"])
                    else:
                        inst_type = "القسط الأول" if inst_idx == 0 else "القسط الثاني"
                    
                    cursor.execute("""
                        INSERT INTO installments (student_id, teacher_id, amount, payment_date, installment_type, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (student_id, teacher_id, amount, payment_date, inst_type, "قسط تجريبي"))
            
            conn.commit()
    
    cursor.close()


def print_stats(conn):
    """طباعة إحصائيات البيانات"""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("SELECT COUNT(*) as cnt FROM subjects")
    print(f"\n===== الإحصائيات =====")
    print(f"  المواد: {cursor.fetchone()['cnt']}")
    
    cursor.execute("SELECT COUNT(*) as cnt FROM teachers")
    print(f"  المدرسين: {cursor.fetchone()['cnt']}")
    
    cursor.execute("SELECT COUNT(*) as cnt FROM students")
    print(f"  الطلاب: {cursor.fetchone()['cnt']}")
    
    cursor.execute("SELECT COUNT(*) as cnt FROM student_teacher")
    print(f"  الارتباطات: {cursor.fetchone()['cnt']}")
    
    cursor.execute("SELECT COUNT(*) as cnt FROM installments")
    print(f"  الأقساط: {cursor.fetchone()['cnt']}")
    
    # Per-subject stats
    print(f"\n  --- لكل مادة ---")
    cursor.execute("""
        SELECT t.subject, COUNT(DISTINCT t.id) as teachers, 
               COUNT(DISTINCT st.student_id) as students
        FROM teachers t
        LEFT JOIN student_teacher st ON st.teacher_id = t.id
        GROUP BY t.subject
        ORDER BY t.subject
    """)
    for row in cursor.fetchall():
        print(f"    {row['subject']}: {row['teachers']} مدرس, {row['students']} طالب")
    
    cursor.close()


def main():
    print("===== بدء إضافة البيانات التجريبية =====\n")
    
    print("[1/5] حذف البيانات القديمة...")
    conn = get_connection()
    clear_all_data(conn)
    conn.close()
    
    print("\n[2/5] إضافة المواد الدراسية...")
    conn = get_connection()
    subjects_map = seed_subjects(conn)
    conn.close()
    
    print(f"\n[3/5] إضافة المدرسين (7-9 لكل مادة)...")
    conn = get_connection()
    teachers_data = seed_teachers(conn, subjects_map)
    conn.close()
    
    print(f"\n[4/5] إضافة الطلاب (40-50 لكل مدرس)...")
    conn = get_connection()
    students_list = seed_students(conn, teachers_data)
    conn.close()
    
    print(f"\n[5/5] إضافة أقساط تجريبية...")
    conn = get_connection()
    seed_installments(conn, teachers_data)
    conn.close()
    
    print("\n===== الإحصائيات النهائية =====")
    conn = get_connection()
    print_stats(conn)
    conn.close()
    
    print("\n✅ تمت إضافة البيانات التجريبية بنجاح!")


if __name__ == "__main__":
    main()
