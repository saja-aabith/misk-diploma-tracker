import sqlite3
from datetime import datetime, timedelta
import random
import bcrypt

DB_NAME = "diploma_tracker.db"

# Fixed seed so that the random-looking 4-digit student ID suffixes (and
# any other random choices made during seeding) are stable across DB
# rebuilds. Demo rehearsal credentials stay valid; two developers
# rebuilding locally get identical seeded users.
MISK_TRACKER_SEED = 2026

# Misk Core quadrant content (Chunk 21).
# The table named `quadrants` now contains 5 rows: the original four plus
# Misk Core. The name is a slight historical misnomer — Misk Core is the
# "fifth criterion" that connects the other four, not a corner — but we
# accept that to keep the schema additive and the code simple. The center
# is the visual treatment for Misk Core, not a corner badge.
MISK_CORE_QUADRANT = {
    "name": "Misk Core",
    "color_hex": "#02664b",  # MISK school green
    "display_order": 5,
}

MISK_CORE_OBJECTIVES = [
    (
        "Co-Curricular Activities Programme (CCAP)",
        "Sustained participation in school CCAP strands such as sports teams, "
        "performing arts, MUN, debate, or service clubs, evidenced through "
        "teacher confirmation, photos, or reflections.",
    ),
    (
        "Trips & Visits",
        "Engagement with school trips, cultural visits, residentials, or "
        "external programmes that broaden experience beyond the classroom.",
    ),
    (
        "Competitions & Awards",
        "Participation in inter-school, regional, national, or international "
        "competitions, with achievements, certificates, or reflections "
        "documented.",
    ),
    (
        "Project 10",
        "Completion and presentation of a Project 10 challenge demonstrating "
        "initiative, planning, and execution across a sustained piece of work.",
    ),
]


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with schema and seed data.

    All schema changes here are additive and idempotent:
    - CREATE TABLE IF NOT EXISTS for new tables
    - ALTER TABLE ADD COLUMN guarded by sqlite3.OperationalError
    - CREATE UNIQUE INDEX IF NOT EXISTS, guarded by a duplicate pre-check
    - Seed inserts gated on COUNT(*) == 0 (or table-specific presence checks)
    """
    conn = get_db()
    cursor = conn.cursor()

    # ---------------------------------------------------------------
    # Existing tables (unchanged)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # New Misk Core tables (Type 2: free-form activity log, no review)
    # ---------------------------------------------------------------
    # NOTE (Chunk 21): These tables predate the decision to convert Misk
    # Core to a structured review-driven flow (Option C). They remain in
    # the schema for now to keep this chunk additive — the free-form
    # activity log code path stays functional during the transition.
    # Chunk 22 retires the frontend that consumes them; a later cleanup
    # chunk can drop the tables and routes once we're sure nothing else
    # references them.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            display_order INTEGER,
            parent_category_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_category_id) REFERENCES activity_categories(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            activity_date DATE,
            stored_filename TEXT,
            original_filename TEXT,
            file_extension TEXT,
            file_size_bytes INTEGER,
            mime_type TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES activity_categories(id)
        )
    """)

    # ---------------------------------------------------------------
    # Idempotent ALTER TABLE migrations on evidence_submissions
    # ---------------------------------------------------------------
    for ddl in (
        "ALTER TABLE evidence_submissions ADD COLUMN stored_filename TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN original_filename TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN file_extension TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN file_size_bytes INTEGER",
        "ALTER TABLE evidence_submissions ADD COLUMN mime_type TEXT",
    ):
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError:
            pass

    # ---------------------------------------------------------------
    # UNIQUE INDEX on evidence_reviews(submission_id, teacher_id)
    # ---------------------------------------------------------------
    cursor.execute("""
        SELECT submission_id, teacher_id, COUNT(*) AS cnt
        FROM evidence_reviews
        GROUP BY submission_id, teacher_id
        HAVING cnt > 1
    """)
    duplicate_review_pairs = cursor.fetchall()
    if duplicate_review_pairs:
        print(
            f"⚠️  evidence_reviews has {len(duplicate_review_pairs)} duplicate "
            "(submission_id, teacher_id) pair(s). UNIQUE INDEX "
            "idx_evidence_reviews_submission_teacher NOT created. "
            "Reconcile duplicates manually, then restart."
        )
    else:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_reviews_submission_teacher "
            "ON evidence_reviews(submission_id, teacher_id)"
        )

    conn.commit()

    # ---------------------------------------------------------------
    # Seeding (gated, idempotent)
    # ---------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        seed_data(conn)

    cursor.execute("SELECT COUNT(*) FROM activity_categories")
    if cursor.fetchone()[0] == 0:
        seed_activity_categories(conn)

    # Chunk 21: ensure Misk Core exists as the fifth quadrant. Internally
    # gated on `name='Misk Core'` so existing DBs pick it up on next
    # startup without requiring a full reseed.
    seed_misk_core_quadrant(conn)

    conn.close()

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed_activity_categories(conn):
    """Seed the Misk Core activity taxonomy.

    NOTE (Chunk 21): the activity-category taxonomy is now legacy. It
    backs the free-form activity log that pre-dated the Option C decision
    to convert Misk Core to a structured submission flow. Categories stay
    seeded so the legacy /student/activities routes don't 500 during
    the transition; Chunk 22 stops using them.

    Idempotent — only invoked when activity_categories is empty.
    """
    cursor = conn.cursor()
    categories = [
        ("Volunteering & Community Service",
         "Activities serving the community, charitable work, and giving back.",
         1),
        ("Cultural Heritage",
         "Saudi heritage, traditions, museums, and cultural exploration.",
         2),
        ("Sports & Athletics",
         "Sports teams, athletic competitions, fitness events, and physical activity.",
         3),
        ("Arts & Creative Expression",
         "Visual art, music, theatre, creative writing, and design.",
         4),
        ("Entrepreneurship & Innovation",
         "Business projects, startups, hackathons, and innovation challenges.",
         5),
        ("Religious & Spiritual Activities",
         "Quran study, Islamic studies events, and religious programs.",
         6),
        ("Personal Development & Skills",
         "Courses, workshops, languages, hobbies, and self-directed learning.",
         7),
    ]
    for name, description, order in categories:
        cursor.execute(
            "INSERT INTO activity_categories "
            "(name, description, display_order, is_active) "
            "VALUES (?, ?, ?, 1)",
            (name, description, order)
        )
    conn.commit()
    print("✓ Activity categories seeded")


def seed_misk_core_quadrant(conn):
    """Ensure Misk Core exists as a quadrants row with its four objectives,
    and seed initial student_objective_progress rows for every existing
    student. Idempotent — gated on the absence of a row with name='Misk Core'.

    Why this lives in its own function and not in seed_data:
    - It must apply to existing DBs (the seed_data gate is COUNT(users)==0).
    - It must be safe to re-run on every startup.
    The two requirements together push it out of seed_data into its own
    idempotent seed function called unconditionally from init_database.
    """
    cursor = conn.cursor()

    # Idempotency gate: if Misk Core already exists, do nothing.
    cursor.execute(
        "SELECT id FROM quadrants WHERE name = ?",
        (MISK_CORE_QUADRANT["name"],),
    )
    existing = cursor.fetchone()
    if existing is not None:
        return

    # Reset RNG so that the random progress data we generate below is
    # deterministic across re-applications (matches the pattern used in
    # seed_data). Note this affects only this function's random calls.
    random.seed(MISK_TRACKER_SEED)

    # 1. Insert the Misk Core quadrant row, capture the assigned id.
    cursor.execute(
        "INSERT INTO quadrants (name, color_hex, display_order) VALUES (?, ?, ?)",
        (
            MISK_CORE_QUADRANT["name"],
            MISK_CORE_QUADRANT["color_hex"],
            MISK_CORE_QUADRANT["display_order"],
        ),
    )
    misk_core_id = cursor.lastrowid

    # 2. Insert the four objectives under the Misk Core quadrant.
    new_objective_ids = []
    for title, description in MISK_CORE_OBJECTIVES:
        cursor.execute(
            "INSERT INTO objectives (quadrant_id, title, description, max_points) "
            "VALUES (?, ?, ?, ?)",
            (misk_core_id, title, description, 100),
        )
        new_objective_ids.append(cursor.lastrowid)

    # 3. Initialise student_objective_progress for every existing student
    #    against each of the four new objectives. Same status-by-completion
    #    rules as the original seed_data for visual consistency in the demo.
    cursor.execute("SELECT id FROM users WHERE role = 'student'")
    student_ids = [row[0] for row in cursor.fetchall()]

    for student_id in student_ids:
        for obj_id in new_objective_ids:
            completion = random.choice([0, 15, 25, 40, 55, 65, 75, 85, 95, 100])
            if completion == 0:
                status = "not_started"
            elif completion < 50:
                # KNOWN: 'in_progress' is not in the documented status enum.
                # Preserved here to match the existing seed_data semantics
                # rather than introduce a divergence in seed shape.
                status = "in_progress"
            elif completion < 100:
                status = "pending_review"
            else:
                status = "approved"

            cursor.execute(
                """
                INSERT INTO student_objective_progress
                    (student_id, objective_id, current_points,
                     completion_percentage, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, obj_id, completion, completion, status),
            )

    conn.commit()
    print(
        f"✓ Misk Core quadrant seeded (id={misk_core_id}, "
        f"{len(new_objective_ids)} objectives, "
        f"{len(student_ids)} students initialised)"
    )


def seed_data(conn):
    """Seed database with realistic test data.

    All random draws below (student ID suffixes, progress percentages,
    submission counts, review choices) are made deterministic by seeding
    Python's RNG with MISK_TRACKER_SEED. Two fresh `diploma_tracker.db`
    rebuilds on different machines produce identical seed data, so demo
    rehearsal credentials and student profiles remain stable.
    """
    cursor = conn.cursor()

    # Lock the RNG to a known starting point.
    random.seed(MISK_TRACKER_SEED)

    # Seed quadrants — the original four. Misk Core is added by
    # seed_misk_core_quadrant() so it can also apply to existing DBs.
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

    # Seed objectives (KPIs) per quadrant for the original four.
    objectives = [
        # Academic (quadrant_id = 1)
        (1, "IGCSE Performance",
            "Track and evidence performance in IGCSE subjects, including mock exams, coursework and final grades."),
        (1, "IAL Performance",
            "Track and evidence performance in International A Level (IAL) subjects, including mock exams and final grades."),
        (1, "National Exams (NAFS / Qudrat / Tahsili)",
            "Record results and preparation evidence for national exams such as NAFS G6, NAFS G9, Qudrat and Tahsili."),
        (1, "EPQ-style Research Project",
            "Complete and document an Extended Project Qualification (EPQ) style research project with proposal, product and reflection."),

        # Internship (quadrant_id = 2)
        (2, "Industry Internship Report",
            "Complete an industry internship and submit a structured report capturing responsibilities, impact and reflections."),
        (2, "Career Planning",
            "Develop and maintain a multi-year career plan with clear milestones, target pathways and action steps."),

        # National Identity (quadrant_id = 3)
        (3, "Arabic Language Development",
            "Demonstrate growth in Arabic language through coursework, assessments and authentic communication tasks."),
        (3, "National Heritage Study",
            "Research, document and present significant aspects of Saudi national heritage, history or culture."),

        # Leadership (quadrant_id = 4)
        (4, "CMI-linked Leadership Competencies",
            "Work towards CMI (or equivalent) leadership competencies, evidencing application in real projects and roles."),
        (4, "Presentation Skills",
            "Plan, deliver and reflect on high-quality presentations to different audiences, demonstrating confident communication."),
    ]

    for quad_id, title, desc in objectives:
        cursor.execute(
            "INSERT INTO objectives (quadrant_id, title, description, max_points) VALUES (?, ?, ?, ?)",
            (quad_id, title, desc, 100)
        )

    # ---------------------------------------------------------------
    # Users — school-email-format usernames (Chunk 20)
    # ---------------------------------------------------------------
    password_hash = hash_password("password123")

    teachers = [
        ("mthomas@miskschools.edu.sa",   "Mr. Murray Thomas"),
        ("aalrashid@miskschools.edu.sa", "Mr. Ahmed Al-Rashid"),
    ]
    for identifier, full_name in teachers:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (identifier, identifier, password_hash, "teacher", full_name)
        )

    student_seed = [
        ("ahmed",    "Ahmed Al-Dosari"),
        ("fatima",   "Fatima Al-Mansouri"),
        ("mohammed", "Mohammed Al-Harbi"),
        ("sara",     "Sara Al-Ghamdi"),
        ("abdullah", "Abdullah Al-Otaibi"),
        ("noura",    "Noura Al-Qahtani"),
        ("khalid",   "Khalid Al-Mutairi"),
        ("lama",     "Lama Al-Shehri"),
        ("omar",     "Omar Al-Zahrani"),
        ("huda",     "Huda Al-Enezi"),
        ("faisal",   "Faisal Al-Dawsari"),
        ("maha",     "Maha Al-Balawi"),
        ("turki",    "Turki Al-Subaie"),
        ("reem",     "Reem Al-Shammari"),
        ("saud",     "Saud Al-Ajmi"),
        ("layla",    "Layla Al-Salem"),
        ("bandar",   "Bandar Al-Malki"),
        ("aisha",    "Aisha Al-Habib"),
        ("nawaf",    "Nawaf Al-Rashid"),
        ("shahad",   "Shahad Al-Khalifa"),
    ]

    used_suffixes = set()
    for first_lower, full_name in student_seed:
        while True:
            suffix = random.randint(1000, 9999)
            if suffix not in used_suffixes:
                used_suffixes.add(suffix)
                break
        identifier = f"{first_lower}{suffix}@miskschools.edu.sa"
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (identifier, identifier, password_hash, "student", full_name)
        )

    conn.commit()

    cursor.execute("SELECT id FROM users WHERE role='student'")
    student_ids = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT id FROM objectives")
    objective_ids = [row[0] for row in cursor.fetchall()]

    # Seed realistic progress data for each student.
    # KNOWN ISSUE: 'in_progress' is NOT in the documented status enum
    # (not_started | submitted | pending_review | approved | rejected).
    # Preserved as-is in this chunk; flagged for separate reconciliation.
    for student_id in student_ids:
        for obj_id in objective_ids:
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

        days_ago = random.randint(0, 30)
        submission_date = datetime.now() - timedelta(days=days_ago)

        cursor.execute(
            """INSERT INTO evidence_submissions
               (student_id, objective_id, file_path, file_name, description, status, submission_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, obj_id, file_path, file_name, description, status, submission_date)
        )

        submission_id = cursor.lastrowid

        if random.random() < 0.4:
            teacher_id = random.choice([3, 4])
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