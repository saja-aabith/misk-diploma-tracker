import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta
import random
import bcrypt

# UPLOAD_DIR is the single source of truth for where evidence files live
# (school-controlled storage per policy). seed_hussain_hero() writes real
# PDFs there so they resolve through the same authenticated files route a
# normal upload uses. Imported from utils to avoid a second definition.
from utils import UPLOAD_DIR

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
# Chunk 28: locked 17-objective content model.
#
# (quadrant_name, title, description). Count thresholds (5 IGCSEs, 3 IALs,
# attempt limits) live in the description prose only — there is NO
# target_count column (agreed Option A). seed_objective_restructure()
# uses this as the single source of truth: any objective whose
# (quadrant, title) matches an existing row is refreshed and kept active;
# any existing objective NOT in this set is soft-deprecated (is_active=0,
# never deleted). Two titles intentionally match the pre-Chunk-28 rows —
# "Career Planning" (Internship) and "Project 10" (Misk Core) — so those
# carry over with their submission history intact.
#
# Title strings are a locked contract: Hussain's seeded evidence binds to
# "Competitions and Awards" (olympiads) and "Career Planning" (MIT sample)
# by exact title. Do not rename without updating seed_hussain_hero().
# ---------------------------------------------------------------------
NEW_OBJECTIVES = [
    # Academic (5)
    ("Academic", "IELTS",
        "Achieve and evidence an IELTS result meeting the diploma's English-"
        "proficiency requirement, including the official test report form."),
    ("Academic", "IGCSE",
        "Sit and pass a minimum of 5 IGCSE subjects, evidenced by statements "
        "of results across the subjects taken."),
    ("Academic", "IAL",
        "Sit and pass a minimum of 3 International A Level (IAL) subjects, "
        "evidenced by statements of results."),
    ("Academic", "Qudrat",
        "Sit the Qudrat (General Aptitude) national test. Up to 5 attempts are "
        "permitted; the best result is recorded as evidence."),
    ("Academic", "Tahsili",
        "Sit the Tahsili (Scholastic Achievement) national test. Up to 2 "
        "attempts are permitted; the best result is recorded as evidence."),

    # Internship (3)
    ("Internship", "HPQ or EPQ",
        "Complete either a Higher Project Qualification (HPQ) or an Extended "
        "Project Qualification (EPQ), submitting the proposal, product and reflection."),
    ("Internship", "Industry Internship",
        "Complete an industry internship and submit a structured report "
        "capturing responsibilities, impact and reflections."),
    ("Internship", "Career Planning",
        "Develop and maintain a multi-year career plan with clear milestones, "
        "target pathways and action steps."),

    # National Identity (3)
    ("National Identity", "Arabic Language",
        "Demonstrate growth in Arabic language through coursework, assessments "
        "and authentic communication tasks."),
    ("National Identity", "Islamic Studies",
        "Demonstrate sustained engagement and achievement in Islamic Studies "
        "through coursework and assessment."),
    ("National Identity", "Social Studies",
        "Demonstrate sustained engagement and achievement in Social Studies, "
        "including Saudi history, geography and civics."),

    # Leadership (1)
    ("Leadership", "CMI Level 2",
        "Work towards and complete the CMI (Chartered Management Institute) "
        "Level 2 qualification, evidencing applied leadership in real projects and roles."),

    # Misk Core (5)
    ("Misk Core", "CCAP",
        "Sustained participation in school CCAP strands such as sports teams, "
        "performing arts, MUN, debate, or service clubs, evidenced through "
        "teacher confirmation, photos, or reflections."),
    ("Misk Core", "Project 10",
        "Completion and presentation of a Project 10 challenge demonstrating "
        "initiative, planning, and execution across a sustained piece of work."),
    ("Misk Core", "Trips and Visits",
        "Engagement with school trips, cultural visits, residentials, or "
        "external programmes that broaden experience beyond the classroom."),
    ("Misk Core", "Competitions and Awards",
        "Participation in inter-school, regional, national, or international "
        "competitions, with achievements, certificates, or reflections documented."),
    ("Misk Core", "Community Service Hours",
        "Accumulate and log community service hours, evidencing sustained "
        "contribution to the school and the wider community."),
]

# ---------------------------------------------------------------------
# Chunk 24/28: hero student progress profiles for the live demo.
#
# Each key is the seed-order index of a student (0 = Ahmed Al-Dosari ...
# 5 = Hussain Alsaleh), per `student_seed` in seed_data. Each value maps
# a quadrant NAME to a dict of {objective_title: completion_percentage}.
#
# Chunk 28: profiles are keyed by objective TITLE (not list position).
# Rationale — these profiles are consumed under two different objective
# orderings: seed_data/seed_misk_core_quadrant seed the legacy objectives,
# while seed_objective_restructure seeds the new 17. Positional lists made
# carried-over objectives ("Career Planning", "Project 10") read the wrong
# index. Title keys are order-independent, so every consumer resolves the
# intended value and the restructure can stay insert-only (it never
# overwrites existing progress — important because Hussain is a real
# student whose reviewed progress must not be reverted on restart).
#
# A title present here but not (yet) a real objective is simply ignored.
# A real objective with no entry for a hero falls back to random (heroes)
# or, in the restructure, to 0/not_started (everyone). New objective shape:
#   Academic 5 | Internship 3 | National Identity 3 | Leadership 1 | Misk Core 5.
# ---------------------------------------------------------------------
HERO_PROGRESS_PROFILES = {
    # Profile 0 — Ahmed, near-empty (Year 7). Blank-canvas view.
    0: {
        "Academic":          {"IELTS": 0, "IGCSE": 10, "IAL": 0, "Qudrat": 0, "Tahsili": 0},
        "Internship":        {"HPQ or EPQ": 0, "Industry Internship": 0, "Career Planning": 0},
        "National Identity": {"Arabic Language": 15, "Islamic Studies": 0, "Social Studies": 0},
        "Leadership":        {"CMI Level 2": 0},
        "Misk Core":         {"CCAP": 10, "Project 10": 0, "Trips and Visits": 0,
                              "Competitions and Awards": 0, "Community Service Hours": 0},
    },
    # Profile 1 — Fatima, mid-progress balanced (Year 9).
    1: {
        "Academic":          {"IELTS": 100, "IGCSE": 60, "IAL": 40, "Qudrat": 45, "Tahsili": 35},
        "Internship":        {"HPQ or EPQ": 100, "Industry Internship": 50, "Career Planning": 30},
        "National Identity": {"Arabic Language": 65, "Islamic Studies": 100, "Social Studies": 40},
        "Leadership":        {"CMI Level 2": 50},
        "Misk Core":         {"CCAP": 60, "Project 10": 100, "Trips and Visits": 40,
                              "Competitions and Awards": 55, "Community Service Hours": 30},
    },
    # Profile 2 — Mohammed, mid-progress lopsided (Year 10).
    # Strong Academic + National Identity; lagging Internship + Leadership.
    2: {
        "Academic":          {"IELTS": 85, "IGCSE": 100, "IAL": 75, "Qudrat": 100, "Tahsili": 80},
        "Internship":        {"HPQ or EPQ": 25, "Industry Internship": 20, "Career Planning": 15},
        "National Identity": {"Arabic Language": 100, "Islamic Studies": 90, "Social Studies": 85},
        "Leadership":        {"CMI Level 2": 20},
        "Misk Core":         {"CCAP": 80, "Project 10": 100, "Trips and Visits": 65,
                              "Competitions and Awards": 90, "Community Service Hours": 70},
    },
    # Profile 3 — Sara, nearly complete with Leadership lagging (Year 12).
    3: {
        "Academic":          {"IELTS": 100, "IGCSE": 100, "IAL": 95, "Qudrat": 100, "Tahsili": 100},
        "Internship":        {"HPQ or EPQ": 100, "Industry Internship": 85, "Career Planning": 90},
        "National Identity": {"Arabic Language": 100, "Islamic Studies": 100, "Social Studies": 95},
        "Leadership":        {"CMI Level 2": 60},
        "Misk Core":         {"CCAP": 100, "Project 10": 95, "Trips and Visits": 100,
                              "Competitions and Awards": 100, "Community Service Hours": 90},
    },
    # Profile 4 — Abdullah, gold standard (Year 12). 100% everywhere.
    4: {
        "Academic":          {"IELTS": 100, "IGCSE": 100, "IAL": 100, "Qudrat": 100, "Tahsili": 100},
        "Internship":        {"HPQ or EPQ": 100, "Industry Internship": 100, "Career Planning": 100},
        "National Identity": {"Arabic Language": 100, "Islamic Studies": 100, "Social Studies": 100},
        "Leadership":        {"CMI Level 2": 100},
        "Misk Core":         {"CCAP": 100, "Project 10": 100, "Trips and Visits": 100,
                              "Competitions and Awards": 100, "Community Service Hours": 100},
    },
    # Profile 5 — Hussain Alsaleh, real Year 12 student (consent on file).
    # 100% across all quadrants; real olympiad evidence + watermarked MIT
    # sample are attached separately by seed_hussain_hero().
    5: {
        "Academic":          {"IELTS": 100, "IGCSE": 100, "IAL": 100, "Qudrat": 100, "Tahsili": 100},
        "Internship":        {"HPQ or EPQ": 100, "Industry Internship": 100, "Career Planning": 100},
        "National Identity": {"Arabic Language": 100, "Islamic Studies": 100, "Social Studies": 100},
        "Leadership":        {"CMI Level 2": 100},
        "Misk Core":         {"CCAP": 100, "Project 10": 100, "Trips and Visits": 100,
                              "Competitions and Awards": 100, "Community Service Hours": 100},
    },
}

# ---------------------------------------------------------------------
# Chunk 25: hero student grade-year assignments for the journey timeline.
#
# Indexed by the same seed_order indices used by HERO_PROGRESS_PROFILES.
# The journey timeline spans Year 7..12 (the MISK Schools Diploma window).
# Years are also displayed on the dashboard implicitly via the timeline
# UI; the value lives in users.student_year (nullable integer).
#
# Non-hero students retain a NULL student_year, which the journey
# endpoint and UI handle gracefully ("Year not yet set" subtitle, all
# nodes rendered as muted outlines).
# ---------------------------------------------------------------------
HERO_STUDENT_YEARS = {
    0: 7,   # Ahmed Al-Dosari    — Near-empty profile
    1: 9,   # Fatima Al-Mansouri — Mid-balanced profile
    2: 10,  # Mohammed Al-Harbi  — Mid-lopsided profile
    3: 12,  # Sara Al-Ghamdi     — Nearly-complete profile (Leadership lagging)
    4: 12,  # Abdullah Al-Otaibi — Gold standard profile
    5: 12,  # Hussain Alsaleh    — Real Year 12 student (olympiad evidence)
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
    # Idempotent ALTER TABLE migrations
    # ---------------------------------------------------------------
    # evidence_submissions: file metadata columns from earlier chunks.
    # users: student_year column added Chunk 25 for the journey timeline.
    for ddl in (
        "ALTER TABLE evidence_submissions ADD COLUMN stored_filename TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN original_filename TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN file_extension TEXT",
        "ALTER TABLE evidence_submissions ADD COLUMN file_size_bytes INTEGER",
        "ALTER TABLE evidence_submissions ADD COLUMN mime_type TEXT",
        "ALTER TABLE users ADD COLUMN student_year INTEGER",
        # Chunk 28: soft-deprecation flag for objectives. Existing rows
        # default to active; the restructure marks obsolete objectives 0.
        "ALTER TABLE objectives ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
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

    # Chunk 25: ensure hero students have student_year set. Idempotent —
    # only writes rows where student_year IS NULL, so existing DBs pick
    # up the hero years on next startup without overwriting any manual
    # values that might already be there.
    seed_hero_student_years(conn)

    # Chunk 28: restructure to the locked 17-objective model (soft-deprecate
    # obsolete objectives, insert new ones, backfill progress). Runs every
    # startup; idempotent and insert-only for progress. MUST run after
    # seed_misk_core_quadrant (it needs the Misk Core quadrant to exist).
    seed_objective_restructure(conn)

    # Chunk 28: seed Hussain's real olympiad evidence + watermarked MIT
    # sample. Runs AFTER the restructure so the target objectives
    # ("Competitions and Awards", "Career Planning") are active. Idempotent.
    seed_hussain_hero(conn)

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
                      objective_title: str):
    """Return (completion_percentage, status) for one seeded
    student_objective_progress row.

    If student_seed_index has a hero profile AND the profile covers
    (quadrant_name, objective_title), the curated value is used.
    Otherwise the historical random distribution is consulted.

    Chunk 28: lookup is by objective TITLE (order-independent) so the same
    profile resolves correctly whether called from seed_data (legacy
    objective ordering) or seed_misk_core_quadrant. A hero whose profile
    has no entry for this title falls through to the random distribution.

    The random fallback advances Python's global RNG, so the caller
    must seed it with MISK_TRACKER_SEED before the seeding loop for
    determinism (both seed_data and seed_misk_core_quadrant already
    do this).
    """
    profile = HERO_PROGRESS_PROFILES.get(student_seed_index)
    if profile is not None:
        quadrant_titles = profile.get(quadrant_name)
        if quadrant_titles is not None:
            completion = quadrant_titles.get(objective_title)
            if completion is not None:
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
    # We keep (title, id) pairs so progress seeding can resolve hero
    # values by title (HERO_PROGRESS_PROFILES is title-keyed as of Chunk 28).
    new_objectives = []  # list of (title, objective_id)
    for title, description in MISK_CORE_OBJECTIVES:
        cursor.execute(
            "INSERT INTO objectives (quadrant_id, title, description, max_points) "
            "VALUES (?, ?, ?, ?)",
            (misk_core_id, title, description, 100),
        )
        new_objectives.append((title, cursor.lastrowid))

    # 3. Initialise student_objective_progress for every existing student
    #    against each of the four new objectives. Hero students get the
    #    curated shape (resolved by title); everyone else falls back to
    #    random. ORDER BY id ensures the enumerate() index lines up with
    #    the student_seed insertion order from seed_data.
    cursor.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
    student_ids = [row[0] for row in cursor.fetchall()]

    for student_seed_index, student_id in enumerate(student_ids):
        for obj_title, obj_id in new_objectives:
            completion, status = _resolve_progress(
                student_seed_index,
                MISK_CORE_QUADRANT["name"],
                obj_title,
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
        f"{len(new_objectives)} objectives, "
        f"{len(student_ids)} students initialised)"
    )


def seed_hero_student_years(conn):
    """Ensure the hero students have a student_year assigned.

    Idempotent in two ways:
    1. Only fires UPDATE on rows where student_year IS NULL, so any value
       set manually (or by a previous run of this function) is preserved.
    2. Safe to call on every startup, including against DBs that predate
       Chunk 25.

    Selection: ORDER BY id LIMIT <hero count> — matches the seed_index
    0..N-1 used by HERO_PROGRESS_PROFILES / HERO_STUDENT_YEARS (students
    are inserted in deterministic order in seed_data; teachers occupy
    ids 1–2). As of Chunk 28 there are 6 heroes (Hussain added at index 5).
    """
    cursor = conn.cursor()
    hero_count = len(HERO_STUDENT_YEARS)
    cursor.execute(
        "SELECT id FROM users WHERE role = 'student' ORDER BY id LIMIT ?",
        (hero_count,),
    )
    rows = cursor.fetchall()
    if len(rows) < hero_count:
        # No students or partial seed; skip to avoid mis-assigning years.
        return

    updates = 0
    for seed_index, row in enumerate(rows):
        year = HERO_STUDENT_YEARS.get(seed_index)
        if year is None:
            continue
        cursor.execute(
            "UPDATE users SET student_year = ? "
            "WHERE id = ? AND student_year IS NULL",
            (year, row[0]),
        )
        updates += cursor.rowcount

    if updates > 0:
        conn.commit()
        print(f"✓ Hero student years seeded ({updates} updated)")


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
        ("ahmed",    "Ahmed Al-Dosari"),       # seed_index 0 — hero: Near-empty   (Year 7)
        ("fatima",   "Fatima Al-Mansouri"),    # seed_index 1 — hero: Mid-balanced (Year 9)
        ("mohammed", "Mohammed Al-Harbi"),     # seed_index 2 — hero: Mid-lopsided (Year 10)
        ("sara",     "Sara Al-Ghamdi"),        # seed_index 3 — hero: Nearly complete (Year 12)
        ("abdullah", "Abdullah Al-Otaibi"),    # seed_index 4 — hero: Gold standard (Year 12)
        ("hussain",  "Hussain Alsaleh"),       # seed_index 5 — hero: real Year 12 student (olympiad evidence)
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
        if first_lower == "hussain":
            # Real student: fixed, stable credential (hussain2026@...). We do
            # NOT draw from the RNG here, so every other student's random
            # suffix is byte-for-byte identical to the pre-Chunk-28 sequence.
            # (2026 never collides with the seeded draws under this seed, so
            # registering it below is safe and triggers no redraw.)
            suffix = 2026
        else:
            while True:
                suffix = random.randint(1000, 9999)
                if suffix not in used_suffixes:
                    break
        used_suffixes.add(suffix)
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

    # Metadata lookup: objective_id -> (quadrant_name, title). Built fresh
    # from the rows we just inserted; sees only the four quadrants seed_data
    # owns (Misk Core is added later by seed_misk_core_quadrant). Title is
    # used to resolve hero progress (HERO_PROGRESS_PROFILES is title-keyed
    # as of Chunk 28), so legacy ordering no longer matters.
    cursor.execute("""
        SELECT o.id, q.name, o.title
        FROM objectives o
        JOIN quadrants q ON q.id = o.quadrant_id
        ORDER BY q.display_order, o.id
    """)
    objective_rows = cursor.fetchall()

    objective_meta = {}            # obj_id -> (quadrant_name, title)
    objective_ids = []
    for obj_id, qname, title in objective_rows:
        objective_meta[obj_id] = (qname, title)
        objective_ids.append(obj_id)

    # Seed progress. Hero students get curated shapes via
    # _resolve_progress; everyone else falls back to the historical
    # random distribution. The 'in_progress' status quirk is preserved
    # inside _compute_progress_status (see its docstring).
    for student_seed_index, student_id in enumerate(student_ids):
        for obj_id in objective_ids:
            quadrant_name, objective_title = objective_meta[obj_id]
            completion, status = _resolve_progress(
                student_seed_index, quadrant_name, objective_title
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


# ============================================================
# Chunk 28: objective restructure + Hussain hero evidence
# ============================================================

def seed_objective_restructure(conn):
    """Migrate to the locked 17-objective model (NEW_OBJECTIVES).

    Idempotent and additive:
      - For each NEW_OBJECTIVES entry: if a row with the same
        (quadrant_id, title) exists, refresh its description and force
        is_active=1; otherwise INSERT it (is_active=1).
      - Every objective NOT in the new set is soft-deprecated (is_active=0).
        Rows are NEVER deleted — historical submissions stay attached and
        teacher detail views (/submission/{id}) remain reachable by id.
      - Backfill student_objective_progress for any (student, active
        objective) pair with no row yet. Hero students (0..5) get their
        curated title-keyed value; everyone else starts at 0/not_started.
        INSERT-ONLY: never overwrites an existing progress row, so real
        reviewed progress (including Hussain's) survives every restart.

    Depends on all quadrants (incl. Misk Core) already existing, so it is
    called after seed_misk_core_quadrant in init_database.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM quadrants")
    quad_by_name = {row['name']: row['id'] for row in cursor.fetchall()}

    inserted = 0
    refreshed = 0
    active_ids = []
    active_meta = {}  # objective_id -> (quadrant_name, title)

    for quadrant_name, title, description in NEW_OBJECTIVES:
        qid = quad_by_name.get(quadrant_name)
        if qid is None:
            print(f"⚠️  Restructure: quadrant '{quadrant_name}' not found; "
                  f"skipping objective '{title}'.")
            continue
        cursor.execute(
            "SELECT id FROM objectives WHERE quadrant_id = ? AND title = ?",
            (qid, title),
        )
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute(
                "INSERT INTO objectives (quadrant_id, title, description, "
                "max_points, is_active) VALUES (?, ?, ?, ?, 1)",
                (qid, title, description, 100),
            )
            obj_id = cursor.lastrowid
            inserted += 1
        else:
            obj_id = existing['id']
            cursor.execute(
                "UPDATE objectives SET description = ?, is_active = 1 WHERE id = ?",
                (description, obj_id),
            )
            refreshed += 1
        active_ids.append(obj_id)
        active_meta[obj_id] = (quadrant_name, title)

    # Soft-deprecate everything not in the active set.
    deactivated = 0
    if active_ids:
        placeholders = ",".join("?" * len(active_ids))
        cursor.execute(
            f"UPDATE objectives SET is_active = 0 WHERE id NOT IN ({placeholders})",
            active_ids,
        )
        deactivated = cursor.rowcount

    # Backfill progress for missing (student, active objective) pairs only.
    cursor.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
    student_ids = [row['id'] for row in cursor.fetchall()]

    progress_added = 0
    for seed_index, student_id in enumerate(student_ids):
        profile = HERO_PROGRESS_PROFILES.get(seed_index)
        for obj_id in active_ids:
            cursor.execute(
                "SELECT 1 FROM student_objective_progress "
                "WHERE student_id = ? AND objective_id = ?",
                (student_id, obj_id),
            )
            if cursor.fetchone() is not None:
                continue  # never overwrite existing progress
            quadrant_name, title = active_meta[obj_id]
            completion = 0
            if profile is not None:
                quadrant_titles = profile.get(quadrant_name)
                if quadrant_titles is not None:
                    completion = quadrant_titles.get(title, 0)
            status = _compute_progress_status(completion)
            cursor.execute(
                """INSERT INTO student_objective_progress
                   (student_id, objective_id, current_points,
                    completion_percentage, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, obj_id, completion, completion, status),
            )
            progress_added += 1

    conn.commit()
    print(
        f"✓ Objective restructure complete (inserted={inserted}, "
        f"refreshed={refreshed}, deactivated={deactivated}, "
        f"progress_rows_added={progress_added})"
    )


def _ensure_mit_offer_pdf(path):
    """Generate the DEMO MIT offer sample PDF at `path` if it doesn't exist.

    MANDATORY: this artefact is fictional and must be unmistakably marked as
    such — two large diagonal watermark lines plus a 'DEMO NOTICE' body
    paragraph — so it can never be presented as a real admissions outcome.
    Idempotent: leaves an existing file untouched.
    """
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        print("⚠️  reportlab not installed — cannot generate MIT demo sample. "
              "Run: pip install reportlab==4.2.5")
        return

    width, height = A4
    c = canvas.Canvas(path, pagesize=A4)

    # Watermark first (sits beneath the body so text stays legible).
    c.saveState()
    c.translate(width / 2.0, height / 2.0)
    c.rotate(30)
    c.setFont("Helvetica-Bold", 44)
    c.setFillGray(0.80)
    c.drawCentredString(0, 35, "DEMO — SAMPLE DOCUMENT")
    c.drawCentredString(0, -40, "NOT A REAL OFFER LETTER")
    c.restoreState()

    # Body text.
    c.setFillGray(0.0)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(25 * mm, height - 35 * mm, "Massachusetts Institute of Technology")
    c.setFont("Helvetica", 11)
    c.drawString(25 * mm, height - 45 * mm, "Department of Physics — Sample Document")

    text = c.beginText(25 * mm, height - 65 * mm)
    text.setFont("Helvetica", 11)
    for line in (
        "DEMO NOTICE",
        "",
        "This document is a sample artefact generated by the MISK Diploma",
        "Tracker for demonstration purposes only. It does not represent a",
        "real offer of admission from MIT and should not be referenced as",
        "such in any external context.",
        "",
        "Student: Hussain Alsaleh",
        "Programme: Physics (sample)",
        "Status: SAMPLE — NOT A REAL OFFER",
    ):
        text.textLine(line)
    c.drawText(text)

    c.showPage()
    c.save()


def seed_hussain_hero(conn):
    """Attach Hussain Alsaleh's real evidence (Chunk 28).

    Five olympiad certificates bind to Misk Core -> "Competitions and Awards";
    the watermarked MIT sample binds to Internship -> "Career Planning". Each
    becomes an approved evidence_submissions row (mirroring /student/upload's
    columns) with two approving teacher reviews, and the file is copied into
    UPLOAD_DIR under a fresh UUID so it serves through the normal
    authenticated files route.

    Sources live in backend/seed_assets/hussain/. The five olympiad PDFs are
    NOT generated here — if a source is missing we log and skip it (drop the
    file in later and restart to seed it). The MIT sample is generated on
    demand by _ensure_mit_offer_pdf (it is fictional, so we own it).

    Idempotent: a file is skipped if Hussain already has a submission with the
    same original_filename. Safe on every startup.
    """
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE username = ?",
        ("hussain2026@miskschools.edu.sa",),
    )
    row = cursor.fetchone()
    if row is None:
        return
    hussain_id = row['id']

    # Real teacher ids (reality over the handover's "3 & 4": teachers are
    # seeded first, so they are ids 1 & 2; students start at 3). Reviews must
    # be attributed to actual teachers, since the demo opens this evidence.
    cursor.execute("SELECT id FROM users WHERE role = 'teacher' ORDER BY id LIMIT 2")
    teacher_ids = [r['id'] for r in cursor.fetchall()]

    seed_assets_dir = os.path.join("seed_assets", "hussain")
    mit_path = os.path.join(seed_assets_dir, "mit_physics_offer_sample.pdf")
    _ensure_mit_offer_pdf(mit_path)

    # (source_path, original_filename, quadrant_name, objective_title, description)
    items = [
        (os.path.join(seed_assets_dir, "ijso_2023_silver.pdf"),
         "IJSO 2023 Thailand - Silver Medal.pdf",
         "Misk Core", "Competitions and Awards",
         "International Junior Science Olympiad 2023 (Thailand) — Silver Medal."),
        (os.path.join(seed_assets_dir, "gulf_physics_2024_silver.pdf"),
         "Gulf Physics Olympiad 2024 - Silver.pdf",
         "Misk Core", "Competitions and Awards",
         "Gulf Physics Olympiad 2024 — Silver Medal / 3rd place."),
        (os.path.join(seed_assets_dir, "nbpho_2025_silver.pdf"),
         "NBPhO 2025 Tallinn - Silver.pdf",
         "Misk Core", "Competitions and Awards",
         "Nordic-Baltic Physics Olympiad 2025 (Tallinn) — Silver Medal."),
        (os.path.join(seed_assets_dir, "apho_2025_bronze.pdf"),
         "APhO 2025 Dhahran - Bronze.pdf",
         "Misk Core", "Competitions and Awards",
         "Asian Physics Olympiad 2025 (Dhahran) — Bronze Medal."),
        (os.path.join(seed_assets_dir, "ipho_2025_bronze.pdf"),
         "IPhO 2025 France - Bronze.pdf",
         "Misk Core", "Competitions and Awards",
         "International Physics Olympiad 2025 (France) — Bronze Medal."),
        (mit_path,
         "MIT Physics Offer (SAMPLE - NOT REAL).pdf",
         "Internship", "Career Planning",
         "DEMO SAMPLE — fictional MIT Physics offer artefact. Not a real offer."),
    ]

    def _objective_id(quadrant_name, title):
        cursor.execute(
            """SELECT o.id FROM objectives o
               JOIN quadrants q ON q.id = o.quadrant_id
               WHERE q.name = ? AND o.title = ? AND o.is_active = 1""",
            (quadrant_name, title),
        )
        r = cursor.fetchone()
        return r['id'] if r else None

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    seeded = 0
    skipped_missing = 0
    for source_path, original_filename, quadrant_name, title, description in items:
        cursor.execute(
            "SELECT 1 FROM evidence_submissions "
            "WHERE student_id = ? AND original_filename = ?",
            (hussain_id, original_filename),
        )
        if cursor.fetchone() is not None:
            continue  # already seeded

        if not os.path.isfile(source_path):
            print(f"⚠️  Hussain seed: source file missing, skipping — {source_path}")
            skipped_missing += 1
            continue

        objective_id = _objective_id(quadrant_name, title)
        if objective_id is None:
            print(f"⚠️  Hussain seed: objective '{title}' in '{quadrant_name}' "
                  f"not found/active; skipping {original_filename}.")
            continue

        ext = os.path.splitext(source_path)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        disk_path = os.path.join(UPLOAD_DIR, stored_filename)
        shutil.copyfile(source_path, disk_path)
        file_size_bytes = os.path.getsize(disk_path)
        mime_type = "application/pdf"

        cursor.execute(
            """INSERT INTO evidence_submissions
               (student_id, objective_id, file_path, file_name, description, status,
                stored_filename, original_filename, file_extension, file_size_bytes, mime_type)
               VALUES (?, ?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?)""",
            (hussain_id, objective_id, disk_path, original_filename, description,
             stored_filename, original_filename, ext, file_size_bytes, mime_type),
        )
        submission_id = cursor.lastrowid

        for teacher_id in teacher_ids:
            cursor.execute(
                """INSERT INTO evidence_reviews
                   (submission_id, teacher_id, rating, feedback, decision)
                   VALUES (?, ?, ?, ?, 'approved')""",
                (submission_id, teacher_id, 5,
                 "Verified certificate. Outstanding achievement."),
            )
        seeded += 1

    if seeded or skipped_missing:
        conn.commit()
        print(f"✓ Hussain hero evidence seeded ({seeded} file(s); "
              f"{skipped_missing} missing source(s) skipped)")