import sqlite3
from datetime import datetime, timedelta
import random
import bcrypt

DB_NAME = "diploma_tracker.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with schema and seed data"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quadrants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color_hex TEXT NOT NULL,
            display_order INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quadrant_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            max_points INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quadrant_id) REFERENCES quadrants(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_objective_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            objective_id INTEGER NOT NULL,
            current_points INTEGER DEFAULT 0,
            completion_percentage REAL DEFAULT 0,
            status TEXT DEFAULT 'not_started',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, objective_id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (objective_id) REFERENCES objectives(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            objective_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'submitted',
            submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (objective_id) REFERENCES objectives(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            feedback TEXT,
            decision TEXT NOT NULL,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES evidence_submissions(id),
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        seed_data(conn)
    
    conn.close()

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_data(conn):
    """Seed database with realistic test data"""
    cursor = conn.cursor()
    
    # Seed quadrants
    quadrants = [
        ("Academic", "#E74C3C", 1),
        ("Internship", "#9B59B6", 2),
        ("National Identity", "#2ECC71", 3),
        ("Leadership", "#F39C12", 4)
    ]
    
    for name, color, order in quadrants:
        cursor.execute(
            "INSERT INTO quadrants (name, color_hex, display_order) VALUES (?, ?, ?)",
            (name, color, order)
        )
    
    # Seed objectives (4 per quadrant)
    objectives = [
        # Academic (quadrant_id=1)
        (1, "Advanced Mathematics Project", "Complete a comprehensive mathematics research project demonstrating advanced problem-solving skills"),
        (1, "Research Essay", "Write a 3000-word research essay on a topic of academic interest with proper citations"),
        (1, "Laboratory Report", "Conduct and document a scientific experiment with detailed methodology and analysis"),
        (1, "Presentation Skills", "Deliver a professional academic presentation to peers and faculty"),
        
        # Internship (quadrant_id=2)
        (2, "Industry Internship Report", "Complete 40 hours of internship and submit comprehensive reflection report"),
        (2, "Professional Portfolio", "Create a professional portfolio showcasing skills and achievements"),
        (2, "Mentor Reflection", "Document learning experiences and feedback from industry mentor"),
        (2, "Career Planning", "Develop a detailed 5-year career plan with actionable steps"),
        
        # National Identity (quadrant_id=3)
        (3, "Community Service Project", "Lead or participate in a community service initiative benefiting local community"),
        (3, "Cultural Research", "Research and present on Saudi cultural heritage and traditions"),
        (3, "National Heritage Study", "Study and document significant aspects of Saudi national history"),
        (3, "Leadership in Heritage", "Organize an event celebrating Saudi national identity"),
        
        # Leadership (quadrant_id=4)
        (4, "Team Project Leadership", "Lead a team of 5+ students in completing a significant project"),
        (4, "Peer Mentorship", "Mentor younger students and document their progress over one semester"),
        (4, "Initiative Proposal", "Develop and pitch a new school initiative to administration"),
        (4, "Leadership Reflection", "Write a comprehensive reflection on leadership experiences and growth")
    ]
    
    for quad_id, title, desc in objectives:
        cursor.execute(
            "INSERT INTO objectives (quadrant_id, title, description, max_points) VALUES (?, ?, ?, ?)",
            (quad_id, title, desc, 100)
        )
    
    # Seed teachers
    password_hash = hash_password("password123")
    teachers = [
        ("teacher1", "teacher1@miskschools.edu.sa", "Dr. Sarah Johnson", "teacher"),
        ("teacher2", "teacher2@miskschools.edu.sa", "Mr. Ahmed Al-Rashid", "teacher")
    ]
    
    for username, email, full_name, role in teachers:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name) VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, role, full_name)
        )
    
    # Seed students with realistic Saudi/international names
    students = [
        ("student1", "ahmed.aldosari@student.misk.sa", "Ahmed Al-Dosari"),
        ("student2", "fatima.almansouri@student.misk.sa", "Fatima Al-Mansouri"),
        ("student3", "mohammed.alharbi@student.misk.sa", "Mohammed Al-Harbi"),
        ("student4", "sara.alghamdi@student.misk.sa", "Sara Al-Ghamdi"),
        ("student5", "abdullah.alotaibi@student.misk.sa", "Abdullah Al-Otaibi"),
        ("student6", "noura.alqahtani@student.misk.sa", "Noura Al-Qahtani"),
        ("student7", "khalid.almutairi@student.misk.sa", "Khalid Al-Mutairi"),
        ("student8", "lama.alshehri@student.misk.sa", "Lama Al-Shehri"),
        ("student9", "omar.alzahrani@student.misk.sa", "Omar Al-Zahrani"),
        ("student10", "huda.alenezi@student.misk.sa", "Huda Al-Enezi"),
        ("student11", "faisal.aldawsari@student.misk.sa", "Faisal Al-Dawsari"),
        ("student12", "maha.albalawi@student.misk.sa", "Maha Al-Balawi"),
        ("student13", "turki.alsubaie@student.misk.sa", "Turki Al-Subaie"),
        ("student14", "reem.alshammari@student.misk.sa", "Reem Al-Shammari"),
        ("student15", "saud.alajmi@student.misk.sa", "Saud Al-Ajmi"),
        ("student16", "layla.alsalem@student.misk.sa", "Layla Al-Salem"),
        ("student17", "bandar.almalki@student.misk.sa", "Bandar Al-Malki"),
        ("student18", "aisha.alhabib@student.misk.sa", "Aisha Al-Habib"),
        ("student19", "nawaf.alrashid@student.misk.sa", "Nawaf Al-Rashid"),
        ("student20", "shahad.alkhalifa@student.misk.sa", "Shahad Al-Khalifa")
    ]
    
    for username, email, full_name in students:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name) VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, "student", full_name)
        )
    
    conn.commit()
    
    # Get student IDs
    cursor.execute("SELECT id FROM users WHERE role='student'")
    student_ids = [row[0] for row in cursor.fetchall()]
    
    # Get objective IDs
    cursor.execute("SELECT id FROM objectives")
    objective_ids = [row[0] for row in cursor.fetchall()]
    
    # Seed realistic progress data for each student
    for student_id in student_ids:
        # Each student has varied completion across objectives
        for obj_id in objective_ids:
            # Random completion (15-95%)
            completion = random.choice([0, 15, 25, 40, 55, 65, 75, 85, 95, 100])
            status = "not_started"
            
            if completion == 0:
                status = "not_started"
            elif completion < 50:
                status = "in_progress"
            elif completion < 100:
                status = "pending_review"
            else:
                status = "approved"
            
            cursor.execute(
                """INSERT INTO student_objective_progress 
                   (student_id, objective_id, current_points, completion_percentage, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, obj_id, completion, completion, status)
            )
    
    # Seed evidence submissions (realistic distribution)
    file_types = ["report.pdf", "presentation.pptx", "video.mp4", "essay.docx", "project.pdf"]
    statuses = ["submitted", "under_review", "approved", "rejected"]
    
    # Generate 60-80 submissions across all students
    num_submissions = random.randint(60, 80)
    
    for _ in range(num_submissions):
        student_id = random.choice(student_ids)
        obj_id = random.choice(objective_ids)
        file_name = random.choice(file_types)
        file_path = f"/uploads/submission_{random.randint(1000, 9999)}_{file_name}"
        description = random.choice([
            "My completed work for this objective",
            "Evidence of my learning and achievement",
            "Project submission with detailed analysis",
            "Final version of my work",
            "Comprehensive report on this topic"
        ])
        status = random.choice(statuses)
        
        # Submission date in last 30 days
        days_ago = random.randint(0, 30)
        submission_date = datetime.now() - timedelta(days=days_ago)
        
        cursor.execute(
            """INSERT INTO evidence_submissions 
               (student_id, objective_id, file_path, file_name, description, status, submission_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, obj_id, file_path, file_name, description, status, submission_date)
        )
        
        submission_id = cursor.lastrowid
        
        # Add reviews for some submissions (30-50% have reviews)
        if random.random() < 0.4:
            teacher_id = random.choice([3, 4])  # teacher1 or teacher2
            rating = random.randint(2, 5)
            decision = "approved" if rating >= 3 else "rejected"
            feedback = random.choice([
                "Excellent work, well researched",
                "Good effort, meets requirements",
                "Outstanding presentation",
                "Needs more detail in analysis section",
                "Great initiative and creativity"
            ])
            
            cursor.execute(
                """INSERT INTO evidence_reviews 
                   (submission_id, teacher_id, rating, feedback, decision)
                   VALUES (?, ?, ?, ?, ?)""",
                (submission_id, teacher_id, rating, feedback, decision)
            )
    
    conn.commit()
    print(" Seed data created successfully")