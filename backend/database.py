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

# ---------------------------------------------------------------------
# Chunk 24: hero student profiles for the live demo.
#
# Each key is the seed-order index of a student (0 = Ahmed Al-Dosari,
# 1 = Fatima Al-Mansouri, etc., per `student_seed` in seed_data). Each
# value maps a quadrant NAME (matching `quadrants.name`, including
# "Misk Core") to a list of completion percentages — one per objective
# in display order within that quadrant.
#
# Students with no entry here, and any (student, quadrant) pair that
# isn't covered, fall back to the historical random distribution. The
# first 5 students get curated shapes so the demo dashboard tells five
# visually distinct stories side by side; the remaining 15 students
# keep the "real school" random feel.
#
# Note: each list's length must match the real objective count for that
# quadrant. As of Chunk 24:
#   Academic 4 | Internship 2 | National Identity 2 | Leadership 2 | Misk Core 4.
# If an objective is added later, extend the corresponding list in
# every profile (or accept that the extra objective falls back to
# random for that profile).
# ---------------------------------------------------------------------
HERO_PROGRESS_PROFILES = {
    # Profile 0 — Near-empty (Year 7 lookalike).
    # Quadrant circle barely filled. Demonstrates the "starting from
    # scratch" view a brand-new student sees on day one.
    0: {
        "Academic":          [0, 15, 0, 0],
        "Internship":        [0, 0],
        "National Identity": [0, 20],
        "Leadership":        [0, 0],
        "Misk Core":         [10, 0, 0, 0],
    },
    # Profile 1 — Mid-progress, balanced (Year 9–10 lookalike).
    # Symmetric ~50% across all quadrants, with one objective per
    # quadrant at 100% so pillar cards read "1 of N completed".
    1: {
        "Academic":          [100, 60, 40, 45],
        "Internship":        [100, 50],
        "National Identity": [65, 100],
        "Leadership":        [100, 50],
        "Misk Core":         [60, 100, 40, 55],
    },
    # Profile 2 — Mid-progress, lopsided.
    # Strong in Academic and National Identity, lagging in Internship
    # and Leadership. Asymmetric circle — useful demo talking point.
    2: {
        "Academic":          [85, 100, 75, 100],
        "Internship":        [25, 20],
        "National Identity": [100, 90],
        "Leadership":        [30, 15],
        "Misk Core":         [80, 100, 65, 90],
    },
    # Profile 3 — Nearly complete (Year 12 lookalike).
    # Mostly very high, with Leadership as the deliberately lagging
    # quadrant so the demo can talk about "what's left to finish".
    3: {
        "Academic":          [100, 100, 95, 100],
        "Internship":        [100, 85],
        "National Identity": [100, 100],
        "Leadership":        [65, 60],
        "Misk Core":         [100, 95, 100, 100],
    },
    # Profile 4 — Gold standard.
    # 100% across every objective. Demonstrates the "fully complete"
    # visual state of the quadrant circle.
    4: {
        "Academic":          [100, 100, 100, 100],
        "Internship":        [100, 100],
        "National Identity": [100, 100],
        "Leadership":        [100, 100],
        "Misk Core":         [100, 100, 100, 100],
    },
}


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


# ---------------------------------------------------------------------
# Chunk 24 helpers: hero profile resolution.
# Shared by seed_data (quadrants 1–4) and seed_misk_core_quadrant
# (Misk Core), so both seed paths produce consistent hero shapes.
# ---------------------------------------------------------------------
def _compute_progress_status(completion: int) -> str:
    """Map a completion percentage to a seeded status string using the
    same bucketing seed_data has always used.

    KNOWN: the 'in_progress' value is NOT in the documented status enum
    (not_started | submitted | pending_review | approved | rejected).
    It is preserved here verbatim to match existing seeded data
    semantics — reconciling it is tracked as a separate chunk per the
    handover, not Chunk 24.
    """
    if completion == 0:
        return "not_started"
    if completion < 50:
        return "in_progress"
    if completion < 100:
        return "pending_review"
    return "approved"


def _resolve_progress(student_seed_index: int, quadrant_name: str,
                      obj_index_in_quadrant: int):
    """Return (completion_percentage, status) for one seeded
    student_objective_progress row.

    If student_seed_index has a hero profile AND the profile covers
    (quadrant_name, obj_index_in_quadrant), the curated value is used.
    Otherwise the historical random distribution is consulted.

    The random fallback advances Python's global RNG, so the caller
    must seed it with MISK_TRACKER_SEED before the seeding loop for
    determinism (both seed_data and seed_misk_core_quadrant already
    do this).
    """
    profile = HERO_PROGRESS_PROFILES.get(student_seed_index)
    if profile is not None:
        quadrant_completions = profile.get(quadrant_name)
        if (quadrant_completions is not None
                and obj_index_in_quadrant < len(quadrant_completions)):
            completion = quadrant_completions[obj_index_in_quadrant]
            return completion, _compute_progress_status(completion)

    completion = random.choice([0, 15, 25, 40, 55, 65, 75, 85, 95, 100])
    return completion, _compute_progress_status(completion)


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

    Chunk 24: hero student profiles (HERO_PROGRESS_PROFILES) now apply
    to the Misk Core quadrant as well as the original four, so the demo
    narrative remains coherent across all five slices of the circle.
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

    # Reset RNG so that the random-fallback progress data we generate
    # below is deterministic across re-applications (matches the pattern
    # used in seed_data). Note this affects only this function's random
    # calls; hero students consume no RNG here.
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
    # Insertion order matches MISK_CORE_OBJECTIVES, which is also the
    # display order assumed by HERO_PROGRESS_PROFILES[*]["Misk Core"].
    new_objective_ids = []
    for title, description in MISK_CORE_OBJECTIVES:
        cursor.execute(
            "INSERT INTO objectives (quadrant_id, title, description, max_points) "
            "VALUES (?, ?, ?, ?)",
            (misk_core_id, title, description, 100),
        )
        new_objective_ids.append(cursor.lastrowid)

    # 3. Initialise student_objective_progress for every existing student
    #    against each of the four new objectives. Hero students (seed
    #    indices 0..len(HERO_PROGRESS_PROFILES)-1) get the curated shape
    #    for Misk Core; everyone else falls back to random.
    #    ORDER BY id ensures the enumerate() index lines up with the
    #    student_seed insertion order from seed_data (teachers occupy
    #    ids 1–2, students 3+).
    cursor.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
    student_ids = [row[0] for row in cursor.fetchall()]

    for student_seed_index, student_id in enumerate(student_ids):
        for obj_idx_in_quadrant, obj_id in enumerate(new_objective_ids):
            completion, status = _resolve_progress(
                student_seed_index,
                MISK_CORE_QUADRANT["name"],
                obj_idx_in_quadrant,
            )
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

    All random draws below (student ID suffixes, progress percentages
    for non-hero students, submission counts, review choices) are made
    deterministic by seeding Python's RNG with MISK_TRACKER_SEED. Two
    fresh `diploma_tracker.db` rebuilds on different machines produce
    identical seed data, so demo rehearsal credentials and student
    profiles remain stable.

    Chunk 24: the first 5 students (Ahmed, Fatima, Mohammed, Sara,
    Abdullah) receive curated "hero" progress shapes via
    HERO_PROGRESS_PROFILES so the demo dashboard tells a coherent
    visual story. Students 5..19 keep the original random shape so
    the wider class still looks like a real school.
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
    # Insertion order matches the display order assumed by the
    # corresponding lists in HERO_PROGRESS_PROFILES.
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

    # Student insertion order = the seed_index used by
    # HERO_PROGRESS_PROFILES. Do NOT reorder this list without also
    # remapping the hero profiles, or the demo narrative will silently
    # attach to the wrong student names.
    student_seed = [
        ("ahmed",    "Ahmed Al-Dosari"),       # seed_index 0 — hero: Near-empty
        ("fatima",   "Fatima Al-Mansouri"),    # seed_index 1 — hero: Mid-balanced
        ("mohammed", "Mohammed Al-Harbi"),     # seed_index 2 — hero: Mid-lopsided
        ("sara",     "Sara Al-Ghamdi"),        # seed_index 3 — hero: Nearly complete
        ("abdullah", "Abdullah Al-Otaibi"),    # seed_index 4 — hero: Gold standard
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

    # ORDER BY id so the enumerate() index matches the student_seed
    # insertion order — required for HERO_PROGRESS_PROFILES lookup.
    cursor.execute("SELECT id FROM users WHERE role='student' ORDER BY id")
    student_ids = [row[0] for row in cursor.fetchall()]

    # Metadata lookup: objective_id -> (quadrant_name, index_in_quadrant).
    # Built fresh from the rows we just inserted; sees only the four
    # quadrants seed_data owns (Misk Core is added later by
    # seed_misk_core_quadrant, which builds its own equivalent inline).
    cursor.execute("""
        SELECT o.id, q.name
        FROM objectives o
        JOIN quadrants q ON q.id = o.quadrant_id
        ORDER BY q.display_order, o.id
    """)
    objective_rows = cursor.fetchall()

    objective_meta = {}            # obj_id -> (quadrant_name, idx_in_quadrant)
    quadrant_obj_counters = {}     # quadrant_name -> next idx
    objective_ids = []
    for obj_id, qname in objective_rows:
        idx = quadrant_obj_counters.get(qname, 0)
        objective_meta[obj_id] = (qname, idx)
        quadrant_obj_counters[qname] = idx + 1
        objective_ids.append(obj_id)

    # Seed progress. Hero students get curated shapes via
    # _resolve_progress; everyone else falls back to the historical
    # random distribution. The 'in_progress' status quirk is preserved
    # inside _compute_progress_status (see its docstring).
    for student_seed_index, student_id in enumerate(student_ids):
        for obj_id in objective_ids:
            quadrant_name, obj_idx_in_quadrant = objective_meta[obj_id]
            completion, status = _resolve_progress(
                student_seed_index, quadrant_name, obj_idx_in_quadrant
            )
            cursor.execute(
                """INSERT INTO student_objective_progress
                   (student_id, objective_id, current_points, completion_percentage, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, obj_id, completion, completion, status)
            )

    # Seed evidence submissions and reviews — UNCHANGED from previous
    # chunks. The random shape is intentional: it keeps the teacher
    # submissions queue populated with realistic-looking activity from
    # across the student body. Hero student progress is decoupled from
    # this and is the visual primary signal on the student dashboard.
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