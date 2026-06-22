import os
import shutil
import sqlite3
import uuid
import json
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
# Chunk 30: mandatory diploma objective model (per misk_skills_framework
# _updated.md §3, now the structural source of truth).
#
# (quadrant_name, title, description). Count thresholds (5 IGCSEs, 3 IALs,
# attempt limits) live in the description prose only — there is NO
# target_count column. seed_objective_restructure() uses this as the single
# source of truth: any objective whose (quadrant, title) matches an existing
# row is refreshed and kept active; any existing objective NOT in this set is
# soft-deprecated (is_active=0, never deleted).
#
# These are the MANDATORY diploma requirements only (the "common floor").
# Misk Core is deliberately ABSENT here: per the updated model it is an
# open-ended section of teacher-approved activities (not fixed objectives)
# that feeds the separate skills profile. Its activity model is built in a
# later chunk; for now the Misk Core quadrant simply carries no active
# objectives. Career Planning likewise moves out of Internship to become a
# Misk Core activity example, so it is not listed here either.
#
# Spelling note: "Qudurat" per the .md (supersedes the earlier "Qudrat").
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
    ("Academic", "Qudurat",
        "Sit the Qudurat (General Aptitude) national test. Up to 5 attempts are "
        "permitted; the best result is recorded as evidence."),
    ("Academic", "Tahsili",
        "Sit the Tahsili (Scholastic Achievement) national test. Up to 2 "
        "attempts are permitted; the best result is recorded as evidence."),

    # Internship (2)
    ("Internship", "HPQ or EPQ",
        "Complete either a Higher Project Qualification (HPQ) or an Extended "
        "Project Qualification (EPQ), submitting the proposal, product and reflection."),
    ("Internship", "Industry Internship",
        "Complete an industry internship and submit a structured report "
        "capturing responsibilities, impact and reflections."),

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
]

# ---------------------------------------------------------------------
# Chunk 24/28: hero student progress profiles for the live demo.
#
# Each key is the seed-order index of a student (0 = Ahmed Al-Dosari ...
# 5 = Hussain Alsaleh), per `student_seed` in seed_data. Each value maps
# a quadrant NAME to a dict of {objective_title: completion_percentage}.
#
# Profiles are keyed by objective TITLE (order-independent) so the same
# profile resolves correctly whether read by seed_data (legacy objectives)
# or seed_objective_restructure (the current model). A title present here
# but not an active objective is simply ignored; a real objective with no
# entry for a hero falls back to random (heroes) or 0/not_started (restructure).
#
# Chunk 30: these now cover only the MANDATORY objectives (Misk Core has no
# fixed objectives in the updated model). Shape:
#   Academic 5 | Internship 2 | National Identity 3 | Leadership 1.
# ---------------------------------------------------------------------
# Retained as the mechanism for curated seeded progress, but the only prior
# entry (Hussain, a real Year 12 student) has been removed so that no real
# student data is seeded. The demo roster is now the five archetypes, each of
# which seeds its own explicit progress in seed_demo_archetype(); they do not
# use this index map. Consumers (_resolve_progress, seed_objective_restructure)
# handle an empty map by falling back to 0/not_started. Empty by design.
HERO_PROGRESS_PROFILES = {}

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
    # Hussain (the only prior hero) has been removed; the archetypes set their
    # own student_year in seed_demo_archetype(). seed_hero_student_years()
    # handles an empty map by doing nothing. Empty by design.
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
    # Chunk 31: diploma_awards — the manually selected formal award.
    # One row per student (UNIQUE student_id). The system NEVER computes
    # Pass/Merit/Distinction; a teacher selects it at the end of the journey
    # once the student is eligible (all mandatory objectives approved). We
    # store who selected it and when for auditability.
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diploma_awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            eligible_for_diploma INTEGER NOT NULL DEFAULT 0,
            award_level TEXT,
            selected_by INTEGER,
            selected_at TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (selected_by) REFERENCES users(id)
        )
    """)

    # ---------------------------------------------------------------
    # Misk Core skill-rating layer: teacher-governed (no AI) per-activity
    # skill claims. The student selects <=3 of the 31 dimensions (20 ACP
    # leaves + 11 VAA) per activity and justifies each; the teacher rejects
    # (level 0 / 'rejected') or approves at a level (Emerging 1 / Evident 2 /
    # Embedded 3). Append-only; the skills engine reads status='approved' AND
    # level>=1. UNIQUE(activity_id, dimension) = one claim per skill per
    # activity. dimension strings are validated against skills.ALL_LEAF_DIMENSIONS
    # at the API layer on write.
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS core_skill_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            dimension TEXT NOT NULL,
            justification TEXT NOT NULL,
            level INTEGER,
            status TEXT NOT NULL DEFAULT 'pending_review',
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(activity_id, dimension),
            FOREIGN KEY (activity_id) REFERENCES student_activities(id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
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
        # Admin chunk: grade a student joined the school in. current grade
        # stays in student_year; entry_grade records the joining grade so the
        # nine-year journey baseline is captured. Nullable; teachers leave it NULL.
        "ALTER TABLE users ADD COLUMN entry_grade INTEGER",
        # Chunk 28: soft-deprecation flag for objectives. Existing rows
        # default to active; the restructure marks obsolete objectives 0.
        "ALTER TABLE objectives ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
        # Chunk 31: result capture for the 5 result-based academic objectives.
        # result_value holds a number string (IELTS/Qudurat/Tahsili) or a JSON
        # array of grade tokens (IGCSE/IAL); attempts is the sit count
        # (Qudurat/Tahsili Resilience signal). Both NULL for non-result rows.
        "ALTER TABLE student_objective_progress ADD COLUMN result_value TEXT",
        "ALTER TABLE student_objective_progress ADD COLUMN attempts INTEGER",
        # Chunk 32: Misk Core activity approval workflow. status defaults to
        # 'approved' so any pre-existing (legacy, instantly-live) activities are
        # grandfathered in; the POST /student/activities handler explicitly
        # writes 'pending_review' for all NEW activities. reviewed_by/at/feedback
        # capture the teacher decision.
        "ALTER TABLE student_activities ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'",
        "ALTER TABLE student_activities ADD COLUMN reviewed_by INTEGER",
        "ALTER TABLE student_activities ADD COLUMN reviewed_at TIMESTAMP",
        "ALTER TABLE student_activities ADD COLUMN review_feedback TEXT",
        # Misk Core skill layer: teacher confirms the academic grade against the
        # uploaded certificate before it counts (gating wired in the teacher flow).
        "ALTER TABLE student_objective_progress ADD COLUMN grade_confirmed_by INTEGER",
        "ALTER TABLE student_objective_progress ADD COLUMN grade_confirmed_at TIMESTAMP",
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

    # Chunk 32: converge the activity taxonomy to the Misk Core types every
    # startup (soft-deprecates any legacy categories on existing DBs). Runs
    # before seed_hussain_hero, which binds his evidence to these categories.
    reconcile_misk_core_activity_categories(conn)

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

    # Hussain (a real Year 12 student) is no longer seeded: his user is not
    # created and his evidence files are not written, so no real student data
    # lands on the server. seed_hussain_hero() remains defined but is
    # intentionally not called. The demo roster is the five archetypes below.

    # Demo archetypes — five distinct students whose Grade 7->12 Misk Core
    # activities light up the full skills framework, each with a different
    # signature. Idempotent; runs after the active objective set, categories,
    # and core_skill_ratings all exist.
    seed_demo_archetypes(conn)

    # A few Type 1 evidence submissions for the archetypes so the teacher
    # review queue has content. Idempotent (gated on an empty submissions
    # table); independent of diploma eligibility and the skills profile.
    seed_archetype_submissions(conn)

    # Bootstrap a single admin account from the environment, if requested.
    # Gated on (env var set) AND (no admin yet); never ships a default password.
    seed_admin_account(conn)

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
    """Seed the Misk Core activity taxonomy (Chunk 32).

    The Misk Core area is open-ended: students log activities against one of
    the Misk Core activity TYPES below. This replaces the original free-form
    taxonomy (Volunteering, Cultural Heritage, …) which is now soft-deprecated
    by reconcile_misk_core_activity_categories on every startup.

    Idempotent — only invoked when activity_categories is empty (fresh DB).
    Existing DBs converge via the reconcile function instead.
    """
    cursor = conn.cursor()
    for name, description, order in MISK_CORE_ACTIVITY_CATEGORIES:
        cursor.execute(
            "INSERT INTO activity_categories "
            "(name, description, display_order, is_active) "
            "VALUES (?, ?, ?, 1)",
            (name, description, order),
        )
    conn.commit()
    print("✓ Activity categories seeded (Misk Core types)")


# Misk Core activity types — the open-ended categories a student logs against
# (source-of-truth §6). Title-cased for display; 'Competitions and Awards' and
# 'Career Planning' are the homes for Hussain's seeded hero evidence.
MISK_CORE_ACTIVITY_CATEGORIES = [
    ("CCAP",
     "Co-Curricular Activity Programme participation.", 1),
    ("Project 10",
     "Project 10 initiatives, deliverables, and outcomes.", 2),
    ("Competitions and Awards",
     "Competitions entered and awards, medals, or honours received.", 3),
    ("Trips and Visits",
     "Educational trips, visits, and excursions.", 4),
    ("Community Service",
     "Volunteering and community service contributions.", 5),
    ("Career Planning",
     "Career exploration, work experience, and planning activities.", 6),
]


def reconcile_misk_core_activity_categories(conn):
    """Converge activity_categories to the Misk Core activity types (Chunk 32).

    Runs every startup; idempotent. Each Misk Core type is inserted if missing
    and (re)activated with a stable display order. Any OTHER category still
    marked active is soft-deprecated (is_active=0) — never deleted — so any
    existing student_activities rows keep resolving their (now-inactive)
    category name on the join. Mirrors the seed_misk_core_quadrant pattern.
    """
    cursor = conn.cursor()
    core_names = [name for name, _, _ in MISK_CORE_ACTIVITY_CATEGORIES]

    for name, description, order in MISK_CORE_ACTIVITY_CATEGORIES:
        cursor.execute(
            "SELECT id FROM activity_categories WHERE name = ?", (name,)
        )
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute(
                "INSERT INTO activity_categories "
                "(name, description, display_order, is_active) VALUES (?, ?, ?, 1)",
                (name, description, order),
            )
        else:
            cursor.execute(
                "UPDATE activity_categories "
                "SET description = ?, display_order = ?, is_active = 1 WHERE id = ?",
                (description, order, existing['id']),
            )

    placeholders = ",".join("?" for _ in core_names)
    cursor.execute(
        f"UPDATE activity_categories SET is_active = 0 "
        f"WHERE is_active = 1 AND name NOT IN ({placeholders})",
        core_names,
    )
    deactivated = cursor.rowcount
    conn.commit()
    print(
        f"✓ Misk Core activity categories reconciled "
        f"({len(core_names)} active; {deactivated} legacy deactivated)"
    )


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

    # The demo roster is the five archetypes, seeded later by
    # seed_demo_archetypes() (each creates its own user). seed_data therefore
    # seeds no students directly; Hussain (a real student) was removed so no
    # real student data is created. The loop below is kept generic so seeded
    # students can be added here again if ever needed.
    student_seed = []

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

    # seed_data no longer seeds any students directly (the five archetypes are
    # seeded later and bring their own Misk Core activities), so there is no
    # student to attach these Type 1 evidence submissions to. Guard against an
    # empty roster: with no students, num_submissions is 0 and the loop below is
    # skipped, avoiding random.choice() on an empty list. If seeded students are
    # ever re-added to student_seed, this populates the review queue again.
    num_submissions = random.randint(6, 10) if student_ids else 0

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
    """Attach Hussain Alsaleh's real evidence as approved Misk Core ACTIVITIES
    (Chunk 32).

    Five olympiad certificates bind to the "Competitions and Awards" activity
    category; the watermarked MIT sample binds to "Career Planning". Each
    becomes an APPROVED student_activities row (status='approved', attributed
    to a real teacher) with the file copied into UPLOAD_DIR under a fresh UUID
    so it serves through the normal authenticated /files route.

    Sources live in backend/seed_assets/hussain/. The five olympiad PDFs are
    NOT generated here — if a source is missing we log and skip it (drop the
    file in later and restart to seed it). The MIT sample is generated on
    demand by _ensure_mit_offer_pdf (it is fictional, so we own it).

    Idempotent: a file is skipped if Hussain already has an activity with the
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

    # Chunk 33: seed Hussain's five academic results so his skills profile shows
    # real performance scaling (otherwise approved-but-no-result falls back to a
    # flat default). Idempotent: only writes where result_value IS NULL, so a
    # teacher's later entry is never overwritten. Stored in the same format the
    # result-capture endpoint uses (number string, or JSON grade array).
    hussain_results = {
        "IELTS":   ("8.5", 1),
        "IGCSE":   (json.dumps(["A*", "A*", "A", "A", "B"]), 1),
        "IAL":     (json.dumps(["A*", "A", "A"]), 1),
        "Qudurat": ("96.0", 1),
        "Tahsili": ("92.0", 2),
    }
    for r_title, (r_value, r_attempts) in hussain_results.items():
        cursor.execute(
            """UPDATE student_objective_progress
               SET result_value = ?, attempts = ?
               WHERE student_id = ? AND result_value IS NULL
                 AND objective_id = (SELECT id FROM objectives WHERE title = ?)""",
            (r_value, r_attempts, hussain_id, r_title),
        )

    # Real teacher id for review attribution (teachers seed first → ids 1 & 2).
    cursor.execute("SELECT id FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1")
    t_row = cursor.fetchone()
    reviewer_id = t_row['id'] if t_row is not None else None

    seed_assets_dir = os.path.join("seed_assets", "hussain")
    mit_path = os.path.join(seed_assets_dir, "mit_physics_offer_sample.pdf")
    _ensure_mit_offer_pdf(mit_path)

    # (source_path, original_filename, category_name, title, activity_date,
    #  description, tags)
    items = [
        (os.path.join(seed_assets_dir, "ijso_2023_silver.pdf"),
         "IJSO 2023 Thailand - Silver Medal.pdf",
         "Competitions and Awards", "IJSO 2023 (Thailand) — Silver Medal",
         "2023-12-10",
         "International Junior Science Olympiad 2023 (Thailand) — Silver Medal.",
         ["physics", "olympiad", "silver", "international"]),
        (os.path.join(seed_assets_dir, "gulf_physics_2024_silver.pdf"),
         "Gulf Physics Olympiad 2024 - Silver.pdf",
         "Competitions and Awards", "Gulf Physics Olympiad 2024 — Silver",
         "2024-04-15",
         "Gulf Physics Olympiad 2024 — Silver Medal / 3rd place.",
         ["physics", "olympiad", "silver", "regional"]),
        (os.path.join(seed_assets_dir, "nbpho_2025_silver.pdf"),
         "NBPhO 2025 Tallinn - Silver.pdf",
         "Competitions and Awards", "NBPhO 2025 (Tallinn) — Silver Medal",
         "2025-04-26",
         "Nordic-Baltic Physics Olympiad 2025 (Tallinn) — Silver Medal.",
         ["physics", "olympiad", "silver", "international"]),
        (os.path.join(seed_assets_dir, "apho_2025_bronze.pdf"),
         "APhO 2025 Dhahran - Bronze.pdf",
         "Competitions and Awards", "APhO 2025 (Dhahran) — Bronze Medal",
         "2025-05-04",
         "Asian Physics Olympiad 2025 (Dhahran) — Bronze Medal.",
         ["physics", "olympiad", "bronze", "international"]),
        (os.path.join(seed_assets_dir, "ipho_2025_bronze.pdf"),
         "IPhO 2025 France - Bronze.pdf",
         "Competitions and Awards", "IPhO 2025 (France) — Bronze Medal",
         "2025-07-21",
         "International Physics Olympiad 2025 (France) — Bronze Medal.",
         ["physics", "olympiad", "bronze", "international"]),
        (mit_path,
         "MIT Physics Offer (SAMPLE - NOT REAL).pdf",
         "Career Planning", "MIT Physics — Sample Offer (DEMO)",
         "2025-12-01",
         "DEMO SAMPLE — fictional MIT Physics offer artefact. Not a real offer.",
         ["career", "university", "physics", "demo-sample"]),
    ]

    def _category_id(name):
        cursor.execute(
            "SELECT id FROM activity_categories WHERE name = ? AND is_active = 1",
            (name,),
        )
        r = cursor.fetchone()
        return r['id'] if r else None

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    seeded = 0
    skipped_missing = 0
    reviewed_at = datetime.utcnow().isoformat()
    for source_path, original_filename, category_name, title, activity_date, \
            description, tags in items:
        cursor.execute(
            "SELECT 1 FROM student_activities "
            "WHERE student_id = ? AND original_filename = ?",
            (hussain_id, original_filename),
        )
        if cursor.fetchone() is not None:
            continue  # already seeded

        if not os.path.isfile(source_path):
            print(f"⚠️  Hussain seed: source file missing, skipping — {source_path}")
            skipped_missing += 1
            continue

        category_id = _category_id(category_name)
        if category_id is None:
            print(f"⚠️  Hussain seed: category '{category_name}' not found/active; "
                  f"skipping {original_filename}.")
            continue

        ext = os.path.splitext(source_path)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        disk_path = os.path.join(UPLOAD_DIR, stored_filename)
        shutil.copyfile(source_path, disk_path)
        file_size_bytes = os.path.getsize(disk_path)
        mime_type = "application/pdf"

        cursor.execute(
            """INSERT INTO student_activities
               (student_id, category_id, title, description, activity_date,
                stored_filename, original_filename, file_extension, file_size_bytes,
                mime_type, tags, status, reviewed_by, reviewed_at, review_feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)""",
            (hussain_id, category_id, title, description, activity_date,
             stored_filename, original_filename, ext, file_size_bytes, mime_type,
             json.dumps(tags), reviewer_id, reviewed_at,
             "Verified certificate. Outstanding achievement."),
        )
        seeded += 1

    if seeded or skipped_missing:
        conn.commit()
        print(f"✓ Hussain hero activities seeded ({seeded} file(s); "
              f"{skipped_missing} missing source(s) skipped)")


# ---------------------------------------------------------------------
# Demo archetypes: five distinct Grade-12 students whose Misk Core
# activities (dated across Grade 7->12) light up the full skills framework,
# so each profile reads differently. These replace the legacy random/hero
# cohort; Hussain is kept separately as the real-evidence student.
#
# Each spec: mandatory results (performance-scaled academics) + one Core
# activity per year Grade 7->12, each carrying APPROVED teacher-levelled
# skill claims (Emerging 1 / Evident 2 / Embedded 3) against the 31
# dimensions. activity_date uses the spring calendar year of each grade
# (Yr7=2021 ... Yr12=2026 for a student in Year 12 now).
# ---------------------------------------------------------------------
DEMO_ARCHETYPES = [
    {
        "username": "layla2026@miskschools.edu.sa",
        "full_name": "Layla Al-Qahtani",
        "year": 12,
        "award": ("Distinction", "Outstanding analytical ability across the diploma."),
        "results": {
            "IELTS": ("8.0", 1),
            "IGCSE": (json.dumps(["A*", "A*", "A*", "A*", "A", "A", "A", "A"]), 1),
            "IAL": (json.dumps(["A*", "A*", "A"]), 1),
            "Qudurat": ("97.0", 1),
            "Tahsili": ("96.0", 1),
        },
        "activities": [
            (2021, "CCAP", "Logic and puzzles club",
             [("Critical or logical thinking", 1)]),
            (2022, "Competitions and Awards", "Junior science fair",
             [("Precision", 2), ("Critical or logical thinking", 2)]),
            (2023, "Competitions and Awards", "Regional science fair finalist",
             [("Critical or logical thinking", 3), ("Precision", 2)]),
            (2024, "Competitions and Awards", "National maths olympiad",
             [("Complex and multi-step problem solving", 3), ("Critical or logical thinking", 2)]),
            (2025, "Project 10", "Extended research essay",
             [("Abstraction", 2), ("Precision", 3)]),
            (2026, "CCAP", "Senior ethics debate society",
             [("Seeing alternative perspectives", 2), ("Strategy-planning", 2)]),
        ],
    },
    {
        "username": "omar2026@miskschools.edu.sa",
        "full_name": "Omar Al-Subaie",
        "year": 12,
        "award": ("Distinction", "Exceptional communicator and student leader."),
        "results": {
            "IELTS": ("9.0", 1),
            "IGCSE": (json.dumps(["A", "A", "B", "B", "B"]), 1),
            "IAL": (json.dumps(["A", "B", "B"]), 1),
            "Qudurat": ("80.0", 1),
            "Tahsili": ("78.0", 1),
        },
        "activities": [
            (2021, "CCAP", "Class representative",
             [("Confident", 1), ("Collaborative", 2)]),
            (2022, "CCAP", "Student council member",
             [("Collaborative", 2), ("Confident", 2)]),
            (2023, "Competitions and Awards", "Model UN delegate",
             [("Confident", 3), ("Concerned for Society", 2)]),
            (2024, "Community Service", "Community recycling campaign lead",
             [("Concerned for Society", 3), ("Collaborative", 2)]),
            (2025, "Community Service", "Charity fundraiser organiser",
             [("Collaborative", 3), ("Concerned for Society", 3)]),
            (2026, "Competitions and Awards", "Regional public-speaking award",
             [("Confident", 3)]),
        ],
    },
    {
        "username": "sara2026@miskschools.edu.sa",
        "full_name": "Sara Al-Dossari",
        "year": 12,
        "award": ("Merit", "Inventive, enterprising and a genuine original."),
        "results": {
            "IELTS": ("7.5", 1),
            "IGCSE": (json.dumps(["A", "A", "B", "B", "C"]), 1),
            "IAL": (json.dumps(["A", "B", "C"]), 1),
            "Qudurat": ("75.0", 1),
            "Tahsili": ("73.0", 1),
        },
        "activities": [
            (2021, "CCAP", "Art club",
             [("Intellectual playfulness", 2), ("Originality", 1)]),
            (2022, "Competitions and Awards", "School art exhibition",
             [("Originality", 2), ("Intellectual playfulness", 2)]),
            (2023, "Project 10", "Designed an original board game",
             [("Fluent thinking", 2), ("Flexible thinking", 2)]),
            (2024, "Project 10", "Founded a small craft business",
             [("Creative & Enterprising", 3), ("Risk-Taking", 2)]),
            (2025, "Competitions and Awards", "Won a design competition",
             [("Originality", 3), ("Evolutionary and revolutionary thinking", 2)]),
            (2026, "Competitions and Awards", "Startup pitch competition",
             [("Creative & Enterprising", 3), ("Risk-Taking", 3)]),
        ],
    },
    {
        "username": "faisal2026@miskschools.edu.sa",
        "full_name": "Faisal Al-Harbi",
        "year": 12,
        "award": ("Distinction", "Outstanding digital builder and problem solver."),
        "results": {
            "IELTS": ("8.0", 1),
            "IGCSE": (json.dumps(["A", "A", "A", "B", "B"]), 1),
            "IAL": (json.dumps(["A", "A", "B"]), 1),
            "Qudurat": ("90.0", 1),
            "Tahsili": ("88.0", 1),
        },
        "activities": [
            (2021, "CCAP", "Coding club (beginner)",
             [("Digital Thinker", 1)]),
            (2022, "Project 10", "Built the school-club website",
             [("Digital Thinker", 2), ("Connection finding", 2)]),
            (2023, "Competitions and Awards", "Robotics team member",
             [("Digital Thinker", 3), ("Automaticity", 2)]),
            (2024, "Project 10", "Built a mobile app",
             [("Digital Thinker", 3), ("Abstraction", 2)]),
            (2025, "Project 10", "Data-science project",
             [("Digital Thinker", 3), ("Generalisation", 2), ("Speed and accuracy", 2)]),
            (2026, "Competitions and Awards", "Hackathon winner",
             [("Digital Thinker", 3), ("Connection finding", 2)]),
        ],
    },
    {
        "username": "noura2026@miskschools.edu.sa",
        "full_name": "Noura Al-Mutairi",
        "year": 12,
        "award": ("Distinction", "Remarkable resilience and sustained commitment."),
        "results": {
            "IELTS": ("8.0", 1),
            "IGCSE": (json.dumps(["A", "A", "A", "B", "B"]), 1),
            "IAL": (json.dumps(["A", "B", "B"]), 1),
            "Qudurat": ("86.0", 4),
            "Tahsili": ("84.0", 2),
        },
        "activities": [
            (2021, "Trips and Visits", "Joined the football team",
             [("Practice", 2), ("Perseverance", 2)]),
            (2022, "CCAP", "Started piano grade exams",
             [("Practice", 2), ("Perseverance", 2)]),
            (2023, "CCAP", "Kept up sport and music",
             [("Practice", 3), ("Resilience", 2)]),
            (2024, "CCAP", "Team captain",
             [("Collaborative", 2), ("Perseverance", 3)]),
            (2025, "Competitions and Awards", "Piano recital",
             [("Practice", 3), ("Confident", 2)]),
            (2026, "Competitions and Awards", "Completed a half-marathon",
             [("Resilience", 3), ("Perseverance", 3)]),
        ],
    },
]


def _demo_category_id(cursor, name):
    """Resolve an active activity-category id by name, falling back to the first
    active category so seeding never fails on a naming mismatch."""
    cursor.execute(
        "SELECT id FROM activity_categories WHERE is_active = 1 AND name = ? LIMIT 1",
        (name,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row['id']
    cursor.execute(
        "SELECT id FROM activity_categories WHERE is_active = 1 "
        "ORDER BY display_order, id LIMIT 1"
    )
    row = cursor.fetchone()
    return row['id'] if row is not None else None


def seed_demo_archetype(conn, spec):
    """Seed one demo archetype student (idempotent). Creates the user, approves
    every mandatory objective with results + teacher grade-confirmation, seeds
    its Grade 7->12 Core activities with APPROVED teacher-levelled skill claims,
    and records the manual diploma award. Safe on every startup: user created
    once; progress INSERT OR IGNORE; results/grade-confirmation written only
    where NULL; activities keyed by (student, title); claims INSERT OR IGNORE
    (UNIQUE activity/dimension); award inserted only if absent.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (spec['username'],))
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name, "
            "student_year) VALUES (?, ?, ?, 'student', ?, ?)",
            (spec['username'], spec['username'], hash_password("password123"),
             spec['full_name'], spec.get('year', 12)),
        )
        student_id = cursor.lastrowid
    else:
        student_id = row['id']

    cursor.execute("SELECT id FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1")
    t_row = cursor.fetchone()
    teacher_id = t_row['id'] if t_row is not None else None
    now = datetime.utcnow().isoformat()

    # Approve every active mandatory objective.
    cursor.execute("SELECT id FROM objectives WHERE is_active = 1")
    for obj in cursor.fetchall():
        cursor.execute(
            "INSERT OR IGNORE INTO student_objective_progress "
            "(student_id, objective_id, current_points, completion_percentage, status) "
            "VALUES (?, ?, 100, 100, 'approved')",
            (student_id, obj['id']),
        )

    # Academic results + teacher grade-confirmation (only where NULL).
    for r_title, (r_value, r_attempts) in spec['results'].items():
        cursor.execute(
            """UPDATE student_objective_progress
               SET result_value = ?, attempts = ?,
                   grade_confirmed_by = ?, grade_confirmed_at = ?
               WHERE student_id = ? AND result_value IS NULL
                 AND objective_id = (SELECT id FROM objectives WHERE title = ?)""",
            (r_value, r_attempts, teacher_id, now, student_id, r_title),
        )

    # Grade 7->12 Core activities, each with approved teacher-levelled claims.
    for year, category_name, title, claims in spec['activities']:
        cursor.execute(
            "SELECT id FROM student_activities WHERE student_id = ? AND title = ?",
            (student_id, title),
        )
        existing = cursor.fetchone()
        if existing is not None:
            activity_id = existing['id']
        else:
            cursor.execute(
                """INSERT INTO student_activities
                   (student_id, category_id, title, description, activity_date,
                    tags, status, reviewed_by, reviewed_at, review_feedback)
                   VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)""",
                (student_id, _demo_category_id(cursor, category_name), title, None,
                 f"{year}-05-15", json.dumps([]), teacher_id, now,
                 "Reviewed and approved."),
            )
            activity_id = cursor.lastrowid
        for dimension, level in claims:
            cursor.execute(
                """INSERT OR IGNORE INTO core_skill_ratings
                   (activity_id, student_id, dimension, justification, level,
                    status, reviewed_by, reviewed_at)
                   VALUES (?, ?, ?, ?, ?, 'approved', ?, ?)""",
                (activity_id, student_id, dimension,
                 f"Demonstrated {dimension} through \"{title}\".",
                 level, teacher_id, now),
            )

    # Manual diploma award (all mandatory approved -> eligible) if absent.
    award = spec.get('award')
    if award is not None:
        cursor.execute("SELECT id FROM diploma_awards WHERE student_id = ?", (student_id,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO diploma_awards (student_id, eligible_for_diploma, "
                "award_level, selected_by, selected_at, notes) VALUES (?, 1, ?, ?, ?, ?)",
                (student_id, award[0], teacher_id, now, award[1]),
            )

    conn.commit()


def seed_demo_archetypes(conn):
    """Seed the five demo archetypes. Idempotent; runs after the active objective
    set, the Misk Core categories, and the core_skill_ratings table all exist."""
    for spec in DEMO_ARCHETYPES:
        seed_demo_archetype(conn, spec)
    print(f"\u2713 Demo archetypes seeded ({len(DEMO_ARCHETYPES)} students).")


def seed_archetype_submissions(conn):
    """Seed a small set of Type 1 evidence submissions for the demo archetypes
    so the teacher review queue has content. The archetypes otherwise evidence
    everything through Misk Core activities, which would leave the structured
    submission queue empty.

    Idempotent: gated on evidence_submissions being empty, so it seeds once on a
    fresh database and never duplicates on restart.

    These rows are demo queue content ONLY. They are independent of diploma
    eligibility (driven by student_objective_progress) and of the skills profile
    (driven by core_skill_ratings), so seeding them changes neither.

    Statuses follow the documented lifecycle (submitted -> under_review ->
    approved/rejected) and any seeded reviews are kept consistent with the
    submission's status so the demo is not misleading.

    NOTE: file_path/file_name are placeholders (no real file on disk), matching
    the prior random submission seeding. The queue lists them; opening the file
    itself will not resolve to bytes.
    """
    cursor = conn.cursor()

    # Gate: only seed when there are no submissions at all.
    cursor.execute("SELECT COUNT(*) FROM evidence_submissions")
    if cursor.fetchone()[0] != 0:
        return

    cursor.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
    student_ids = [r['id'] for r in cursor.fetchall()]
    cursor.execute("SELECT id FROM objectives WHERE is_active = 1 ORDER BY id")
    objective_ids = [r['id'] for r in cursor.fetchall()]
    cursor.execute("SELECT id FROM users WHERE role = 'teacher' ORDER BY id")
    teacher_ids = [r['id'] for r in cursor.fetchall()]

    # If any of these are missing (e.g. archetypes not seeded), skip safely.
    if not student_ids or not objective_ids or not teacher_ids:
        return

    t0 = teacher_ids[0]
    t1 = teacher_ids[1] if len(teacher_ids) > 1 else teacher_ids[0]

    def pick(seq, i):
        return seq[i % len(seq)]

    # Deterministic plan (no RNG): (student_index, objective_index, status,
    # reviews). reviews = list of (teacher_id, rating, decision, feedback).
    # Spans the lifecycle so the queue shows pending and completed work.
    plan = [
        (0, 0, "submitted",    []),
        (1, 1, "submitted",    []),
        (2, 2, "submitted",    []),
        (3, 3, "under_review", [(t0, 3, "approved", "Good start; reviewing.")]),
        (4, 4, "approved",     [(t0, 4, "approved", "Strong evidence."),
                                (t1, 3, "approved", "Meets the objective.")]),
        (0, 5, "rejected",     [(t0, 1, "rejected", "Please resubmit with more detail.")]),
    ]

    seeded = 0
    for offset, (s_i, o_i, status, reviews) in enumerate(plan):
        student_id = pick(student_ids, s_i)
        objective_id = pick(objective_ids, o_i)
        submission_date = (datetime.utcnow() - timedelta(days=offset)).isoformat()
        cursor.execute(
            """INSERT INTO evidence_submissions
               (student_id, objective_id, file_path, file_name, description,
                status, submission_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, objective_id,
             f"/uploads/demo_submission_{offset + 1}.pdf",
             f"demo_submission_{offset + 1}.pdf",
             "Demo evidence submission.",
             status, submission_date),
        )
        submission_id = cursor.lastrowid
        for teacher_id, rating, decision, feedback in reviews:
            cursor.execute(
                """INSERT INTO evidence_reviews
                   (submission_id, teacher_id, rating, feedback, decision)
                   VALUES (?, ?, ?, ?, ?)""",
                (submission_id, teacher_id, rating, feedback, decision),
            )
        seeded += 1

    conn.commit()
    print(f"\u2713 Archetype demo submissions seeded ({seeded} submission(s))")

def seed_admin_account(conn):
    """Bootstrap a single admin account from the environment, if requested.

    Creates username 'admin@miskschools.edu.sa' with role 'admin' using the
    password in the ADMIN_INITIAL_PASSWORD environment variable.

    Gated on BOTH:
      1. the ADMIN_INITIAL_PASSWORD env var being set, and
      2. no admin account already existing.
    So it never ships a default/known password and never overwrites an
    existing admin. If the env var is unset and no admin exists, it prints a
    notice and does nothing (the first admin is created the next time the
    server starts with the variable set).
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cursor.fetchone()[0] != 0:
        return

    initial_pw = os.getenv("ADMIN_INITIAL_PASSWORD")
    if not initial_pw:
        print(
            "ℹ️  No admin account exists and ADMIN_INITIAL_PASSWORD is not set; "
            "skipping admin bootstrap. Set it in the environment to create the "
            "first admin on next startup."
        )
        return

    username = "admin@miskschools.edu.sa"
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, full_name) "
        "VALUES (?, ?, ?, 'admin', ?)",
        (username, username, hash_password(initial_pw), "Administrator"),
    )
    conn.commit()
    print(f"✓ Admin account bootstrapped ({username})")