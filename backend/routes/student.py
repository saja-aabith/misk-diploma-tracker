# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import json
import os
import re
from datetime import date, datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import ValidationError

from database import get_db
from models import (
    ObjectiveProgress,
    QuadrantSummary,
    StudentDashboard,
    Submission,
    SubmissionReview,
)
from schemas import (
    ActivityCategoryOut,
    ActivityLogIn,
    ActivityOut,
    JourneyMilestone,
    JourneyYear,
    StudentJourney,
)
from utils import (
    UPLOAD_DIR,
    get_current_student,
    validate_upload,
)

router = APIRouter()


# ============================================================
# Chunk 25 — Journey timeline: curated hero milestones
# ============================================================
# Keyed by the alphabetic prefix of a student's username (everything
# before the 4-digit suffix in e.g. 'ahmed2951@miskschools.edu.sa').
# Prefixes are stable across reseeds via MISK_TRACKER_SEED.
#
# Each entry is a list of (school_year, title, quadrant_name,
# quadrant_color, month) tuples. school_year must be in [7..12];
# `month` is the calendar month (1..12) used to construct a plausible
# display date for the milestone.
#
# WHY THIS IS A PYTHON CONSTANT (not a DB table):
#   For the MVP demo we need a coherent multi-year journey narrative
#   per hero student. Real `evidence_submissions` only span the last
#   ~30 days (seeded with random recent dates), so they cannot back a
#   Year 7→12 narrative. Rather than introduce a new milestones table
#   (which we may not need in the production model — milestones might
#   instead be auto-derived from approved submissions on capstone
#   objectives), we keep curated milestones here, clearly labelled as
#   demo-time data.
#
# WHEN TO REPLACE THIS:
#   Once real submissions span academic years (i.e. after live use for
#   one full school year), this constant can be removed and the journey
#   endpoint switched to read approved evidence_submissions filtered by
#   capstone-marker objectives (EPQ, Industry Internship Report,
#   Project 10) plus quadrant-100% achievements.
HERO_JOURNEY_MILESTONES = {
    "ahmed": [
        # Year 7, just started. Intentionally empty — demonstrates the
        # "blank canvas" view a new student sees.
    ],
    "fatima": [
        # Year 9, balanced. Sparse Year 7–8 trail, one fresh Year 9 win.
        (7, "First Arabic Language Project", "National Identity", "#2ECC71", 11),
        (8, "Community Service Award", "Misk Core", "#02664b", 4),
        (8, "Year 8 Heritage Trip — Diriyah", "Misk Core", "#02664b", 10),
        (9, "Mock IGCSE Top Score — Maths", "Academic", "#E74C3C", 3),
    ],
    "mohammed": [
        # Year 10, strong Academic + National Identity, sparse elsewhere.
        # Captures the lopsided narrative visible in the quadrant circle.
        (7, "Arabic Storytelling Festival", "National Identity", "#2ECC71", 12),
        (8, "Top of Class — Mathematics", "Academic", "#E74C3C", 6),
        (8, "Heritage Field Trip — AlUla", "Misk Core", "#02664b", 11),
        (9, "IGCSE Mock — 95th Percentile", "Academic", "#E74C3C", 5),
        (9, "Saudi National Day Speech", "National Identity", "#2ECC71", 9),
        (10, "IGCSE Distinctions × 4", "Academic", "#E74C3C", 6),
    ],
    "sara": [
        # Year 12, nearly complete, with Leadership as the lagging quadrant.
        # Dense Year 9–11 trail; current Year 12 has the EPQ milestone.
        (8, "Project 10 Concept Approved", "Misk Core", "#02664b", 1),
        (9, "IGCSE Mock Excellence", "Academic", "#E74C3C", 3),
        (9, "Arabic Heritage Documentary", "National Identity", "#2ECC71", 11),
        (10, "Cultural Residential — Diriyah", "Misk Core", "#02664b", 10),
        (10, "First Internship Application", "Internship", "#9B59B6", 4),
        (11, "IGCSE Distinctions × 7", "Academic", "#E74C3C", 6),
        (11, "Industry Internship Completed", "Internship", "#9B59B6", 8),
        (11, "Project 10 Public Launch", "Misk Core", "#02664b", 11),
        (12, "EPQ Research Project Submitted", "Academic", "#E74C3C", 2),
    ],
    "abdullah": [
        # Year 12, gold standard. Every school year flagged across all five
        # quadrants — full diploma narrative for the demo's "complete" view.
        (7, "Welcome to Misk Schools", "Misk Core", "#02664b", 9),
        (7, "Arabic Recitation Award", "National Identity", "#2ECC71", 11),
        (8, "Year 8 Maths Olympiad", "Academic", "#E74C3C", 5),
        (8, "Student Council Member", "Leadership", "#F39C12", 10),
        (9, "IGCSE Mock — Top Performer", "Academic", "#E74C3C", 3),
        (9, "Project 10 Phase 1 Complete", "Misk Core", "#02664b", 6),
        (10, "IGCSE Distinctions × 9", "Academic", "#E74C3C", 6),
        (10, "Career Plan v1 Finalised", "Internship", "#9B59B6", 11),
        (11, "Industry Internship — Aramco", "Internship", "#9B59B6", 8),
        (11, "Project 10 Showcase Winner", "Misk Core", "#02664b", 11),
        (11, "Inter-School Debate Champion", "Leadership", "#F39C12", 2),
        (12, "EPQ Distinction", "Academic", "#E74C3C", 1),
        (12, "CMI Level 3 Certified", "Leadership", "#F39C12", 3),
        (12, "Diploma Complete", "Misk Core", "#02664b", 5),
    ],
}


# ============================================================
# Existing routes — unchanged business logic, dependency tightened
# ============================================================

@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_student)):
    """Get student dashboard data"""
    conn = get_db()
    cursor = conn.cursor()

    student_id = current_user['user_id']

    # Get student name
    cursor.execute("SELECT full_name FROM users WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    student_name = student['full_name'] if student else "Student"

    # Get quadrant data
    cursor.execute("""
        SELECT q.id, q.name, q.color_hex,
               COUNT(o.id) as total_objectives,
               AVG(sop.completion_percentage) as avg_completion
        FROM quadrants q
        LEFT JOIN objectives o ON q.id = o.quadrant_id
        LEFT JOIN student_objective_progress sop ON o.id = sop.objective_id AND sop.student_id = ?
        GROUP BY q.id
        ORDER BY q.display_order
    """, (student_id,))

    quadrants = []
    total_completion = 0

    for row in cursor.fetchall():
        completion = row['avg_completion'] if row['avg_completion'] else 0
        total_completion += completion

        # Count completed objectives
        cursor.execute("""
            SELECT COUNT(*) FROM student_objective_progress sop
            JOIN objectives o ON sop.objective_id = o.id
            WHERE o.quadrant_id = ? AND sop.student_id = ? AND sop.status = 'approved'
        """, (row['id'], student_id))
        completed = cursor.fetchone()[0]

        quadrants.append(QuadrantSummary(
            id=row['id'],
            name=row['name'],
            color=row['color_hex'],
            completion_percentage=round(completion, 1),
            objectives_completed=completed,
            total_objectives=row['total_objectives']
        ))

    # Overall completion is the mean across however many quadrants exist.
    # Previously hardcoded to 4; updated in Chunk 21 when Misk Core was
    # added as a fifth row in the `quadrants` table.
    overall_completion = (
        round(total_completion / len(quadrants), 1) if quadrants else 0
    )

    conn.close()

    return StudentDashboard(
        student_id=student_id,
        student_name=student_name,
        overall_completion_percentage=overall_completion,
        quadrants=quadrants
    )


# ============================================================
# Journey timeline (Chunk 25)
# ============================================================

@router.get("/journey", response_model=StudentJourney)
async def get_journey(current_user: dict = Depends(get_current_student)):
    """Return the authenticated student's MISK Diploma journey timeline.

    Always returns 6 year-cells (Year 7..12). For the 5 hero students the
    timeline includes curated milestones from HERO_JOURNEY_MILESTONES; for
    everyone else the year-cells render empty (no milestones) and the
    student's current_year (if set) is highlighted.

    Auth: student-only. Each student sees only their own journey.
    """
    student_id = current_user['user_id']

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, student_year FROM users WHERE id = ?",
        (student_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        # This shouldn't happen — get_current_student already validated the
        # user — but defending against it keeps the endpoint robust.
        raise HTTPException(
            status_code=404,
            detail={
                "code": "STUDENT_NOT_FOUND",
                "message": "Authenticated student record missing.",
            },
        )

    username = row['username']
    current_year = row['student_year']  # may be None

    prefix = _resolve_username_prefix(username)
    raw_milestones = HERO_JOURNEY_MILESTONES.get(prefix, []) if prefix else []

    years = _build_journey_years(current_year, prefix, raw_milestones)

    return StudentJourney(
        current_year=current_year,
        years=years,
    )


# ============================================================
# Existing routes (continued)
# ============================================================

@router.get("/objectives")
async def get_objectives(
    quadrant_id: Optional[int] = None,
    current_user: dict = Depends(get_current_student)
):
    """Get student objectives with progress"""
    conn = get_db()
    cursor = conn.cursor()

    student_id = current_user['user_id']

    query = """
        SELECT o.id, o.quadrant_id, q.name as quadrant_name, o.title, o.description,
               o.max_points,
               COALESCE(sop.current_points, 0) as current_points,
               COALESCE(sop.completion_percentage, 0) as completion_percentage,
               COALESCE(sop.status, 'not_started') as status
        FROM objectives o
        JOIN quadrants q ON o.quadrant_id = q.id
        LEFT JOIN student_objective_progress sop ON o.id = sop.objective_id AND sop.student_id = ?
    """

    params = [student_id]
    if quadrant_id:
        query += " WHERE o.quadrant_id = ?"
        params.append(quadrant_id)

    cursor.execute(query, params)
    objectives = []

    for row in cursor.fetchall():
        # Get submission counts
        cursor.execute("""
            SELECT COUNT(*) FROM evidence_submissions
            WHERE student_id = ? AND objective_id = ?
        """, (student_id, row['id']))
        submission_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM evidence_submissions es
            WHERE es.student_id = ? AND es.objective_id = ? AND es.status = 'approved'
        """, (student_id, row['id']))
        approved_count = cursor.fetchone()[0]

        objectives.append(ObjectiveProgress(
            id=row['id'],
            quadrant_id=row['quadrant_id'],
            quadrant_name=row['quadrant_name'],
            title=row['title'],
            description=row['description'],
            current_points=row['current_points'],
            max_points=row['max_points'],
            completion_percentage=row['completion_percentage'],
            status=row['status'],
            submission_count=submission_count,
            approved_count=approved_count
        ))

    conn.close()
    return {"objectives": objectives}


# ============================================================
# /upload — migrated to validate_upload + UUID storage + metadata cols
# ============================================================

@router.post("/upload")
async def upload_evidence(
    objective_id: int = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_student),
):
    """Upload evidence for an objective"""
    student_id = current_user['user_id']

    validated = await validate_upload(file)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM objectives WHERE id = ?", (objective_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "code": "OBJECTIVE_NOT_FOUND",
                "message": f"Objective {objective_id} does not exist.",
            },
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(UPLOAD_DIR, validated.stored_filename)
    with open(disk_path, "wb") as f:
        f.write(validated.content_bytes)

    cursor.execute(
        """
        INSERT INTO evidence_submissions
            (student_id, objective_id, file_path, file_name, description, status,
             stored_filename, original_filename, file_extension, file_size_bytes, mime_type)
        VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            objective_id,
            disk_path,
            validated.original_filename,
            description,
            validated.stored_filename,
            validated.original_filename,
            validated.file_extension,
            validated.file_size_bytes,
            validated.mime_type,
        ),
    )
    submission_id = cursor.lastrowid

    cursor.execute(
        """
        UPDATE student_objective_progress
        SET status = 'pending_review', updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ? AND objective_id = ?
        """,
        (student_id, objective_id),
    )
    if cursor.rowcount == 0:
        cursor.execute(
            """
            INSERT INTO student_objective_progress
                (student_id, objective_id, status)
            VALUES (?, ?, 'pending_review')
            """,
            (student_id, objective_id),
        )

    conn.commit()
    conn.close()

    return {
        "submission_id": submission_id,
        "objective_id": objective_id,
        "file_name": validated.original_filename,
        "stored_filename": validated.stored_filename,
        "original_filename": validated.original_filename,
        "status": "submitted",
        "submission_date": datetime.now().isoformat(),
    }


# ============================================================
# /submissions
# ============================================================

@router.get("/submissions")
async def get_submissions(
    status: str = "all",
    current_user: dict = Depends(get_current_student),
):
    """Get student submissions"""
    conn = get_db()
    cursor = conn.cursor()

    student_id = current_user['user_id']

    query = """
        SELECT es.id, es.student_id, es.objective_id, o.title as objective_title,
               q.name as quadrant_name, es.file_name, es.file_path, es.stored_filename,
               es.description, es.status, es.submission_date
        FROM evidence_submissions es
        JOIN objectives o ON es.objective_id = o.id
        JOIN quadrants q ON o.quadrant_id = q.id
        WHERE es.student_id = ?
    """

    params = [student_id]
    if status != "all":
        query += " AND es.status = ?"
        params.append(status)

    query += " ORDER BY es.submission_date DESC"

    cursor.execute(query, params)
    submissions = []

    for row in cursor.fetchall():
        cursor.execute("""
            SELECT er.id, er.teacher_id, u.full_name as teacher_name,
                   er.rating, er.feedback, er.decision, er.reviewed_at
            FROM evidence_reviews er
            JOIN users u ON er.teacher_id = u.id
            WHERE er.submission_id = ?
            ORDER BY er.reviewed_at DESC
        """, (row['id'],))

        reviews = []
        for review_row in cursor.fetchall():
            reviews.append(SubmissionReview(
                id=review_row['id'],
                teacher_id=review_row['teacher_id'],
                teacher_name=review_row['teacher_name'],
                rating=review_row['rating'],
                feedback=review_row['feedback'],
                decision=review_row['decision'],
                reviewed_at=review_row['reviewed_at'],
            ))

        submission_model = Submission(
            id=row['id'],
            student_id=row['student_id'],
            objective_id=row['objective_id'],
            objective_title=row['objective_title'],
            quadrant_name=row['quadrant_name'],
            file_name=row['file_name'],
            file_path=row['file_path'],
            description=row['description'],
            status=row['status'],
            submission_date=row['submission_date'],
            review_count=len(reviews),
            reviews=reviews,
        )
        submission_dict = submission_model.model_dump()
        submission_dict['stored_filename'] = row['stored_filename']
        submissions.append(submission_dict)

    conn.close()
    return {"submissions": submissions}


# ============================================================
# Misk Core — activity categories (LEGACY: see Chunk 21 note in database.py)
# ============================================================

@router.get("/activity-categories")
async def get_activity_categories(
    current_user: dict = Depends(get_current_student),
):
    """List active Misk Core activity categories ordered for display."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, description, display_order
        FROM activity_categories
        WHERE is_active = 1
        ORDER BY display_order, id
        """
    )
    categories = [
        ActivityCategoryOut(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            display_order=row['display_order'],
        )
        for row in cursor.fetchall()
    ]
    conn.close()
    return {"categories": categories}


# ============================================================
# Misk Core — log a new activity (LEGACY: see Chunk 21 note in database.py)
# ============================================================

@router.post("/activities", response_model=ActivityOut)
async def create_activity(
    category_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    activity_date: str = Form(...),
    tags: str = Form("[]"),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_student),
):
    """Log a free-form Misk Core activity. Optional file attachment."""
    student_id = current_user['user_id']

    raw_tags = tags.strip() if tags else ""
    if not raw_tags:
        decoded_tags = []
    else:
        try:
            decoded_tags = json.loads(raw_tags)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ACTIVITY_TAGS_INVALID_JSON",
                    "message": "tags must be a JSON-encoded array of strings.",
                },
            )
        if not isinstance(decoded_tags, list):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ACTIVITY_TAGS_INVALID_JSON",
                    "message": "tags must be a JSON array.",
                },
            )

    try:
        parsed_date = date.fromisoformat(activity_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ACTIVITY_DATE_INVALID",
                "message": "activity_date must be in YYYY-MM-DD format.",
            },
        )

    try:
        payload = ActivityLogIn(
            category_id=category_id,
            title=title,
            description=description,
            activity_date=parsed_date,
            tags=decoded_tags,
        )
    except ValidationError as ve:
        first = ve.errors()[0] if ve.errors() else {"msg": "Invalid payload"}
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ACTIVITY_PAYLOAD_INVALID",
                "message": str(first.get("msg", "Invalid payload")),
            },
        )

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM activity_categories WHERE id = ? AND is_active = 1",
        (payload.category_id,),
    )
    cat_row = cursor.fetchone()
    if cat_row is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ACTIVITY_CATEGORY_INVALID",
                "message": f"Category {payload.category_id} is unknown or inactive.",
            },
        )

    stored_filename = None
    original_filename = None
    file_extension = None
    file_size_bytes = None
    mime_type = None

    if file is not None and (file.filename or "").strip():
        validated = await validate_upload(file)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        disk_path = os.path.join(UPLOAD_DIR, validated.stored_filename)
        with open(disk_path, "wb") as f:
            f.write(validated.content_bytes)
        stored_filename = validated.stored_filename
        original_filename = validated.original_filename
        file_extension = validated.file_extension
        file_size_bytes = validated.file_size_bytes
        mime_type = validated.mime_type

    cursor.execute(
        """
        INSERT INTO student_activities
            (student_id, category_id, title, description, activity_date,
             stored_filename, original_filename, file_extension, file_size_bytes,
             mime_type, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            payload.category_id,
            payload.title,
            payload.description,
            payload.activity_date.isoformat(),
            stored_filename,
            original_filename,
            file_extension,
            file_size_bytes,
            mime_type,
            json.dumps(payload.tags),
        ),
    )
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute(
        """
        SELECT sa.id, sa.student_id, sa.category_id, ac.name as category_name,
               sa.title, sa.description, sa.activity_date,
               sa.stored_filename, sa.original_filename, sa.file_extension,
               sa.file_size_bytes, sa.mime_type, sa.tags, sa.created_at
        FROM student_activities sa
        JOIN activity_categories ac ON ac.id = sa.category_id
        WHERE sa.id = ?
        """,
        (new_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return _row_to_activity_out(row)


# ============================================================
# Misk Core — list activities for the authenticated student (LEGACY)
# ============================================================

@router.get("/activities")
async def list_activities(
    category_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_student),
):
    """List the authenticated student's Misk Core activities."""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT sa.id, sa.student_id, sa.category_id, ac.name as category_name,
               sa.title, sa.description, sa.activity_date,
               sa.stored_filename, sa.original_filename, sa.file_extension,
               sa.file_size_bytes, sa.mime_type, sa.tags, sa.created_at
        FROM student_activities sa
        JOIN activity_categories ac ON ac.id = sa.category_id
        WHERE sa.student_id = ?
    """
    params = [current_user['user_id']]

    if category_id is not None:
        query += " AND sa.category_id = ?"
        params.append(category_id)

    query += " ORDER BY sa.activity_date DESC, sa.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    activities = [_row_to_activity_out(row) for row in cursor.fetchall()]
    conn.close()
    return {"activities": activities}


# ============================================================
# Private helpers
# ============================================================

def _row_to_activity_out(row) -> ActivityOut:
    """Convert a sqlite3.Row from the activities/categories join into
    an ActivityOut. Decodes tags JSON with a permissive fallback so a
    legacy NULL or malformed value doesn't 500 the list endpoint."""
    raw_tags = row['tags']
    if not raw_tags:
        decoded_tags = []
    else:
        try:
            decoded = json.loads(raw_tags)
            decoded_tags = decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            decoded_tags = []

    return ActivityOut(
        id=row['id'],
        student_id=row['student_id'],
        category_id=row['category_id'],
        category_name=row['category_name'],
        title=row['title'],
        description=row['description'],
        activity_date=row['activity_date'],
        stored_filename=row['stored_filename'],
        original_filename=row['original_filename'],
        file_extension=row['file_extension'],
        file_size_bytes=row['file_size_bytes'],
        mime_type=row['mime_type'],
        tags=decoded_tags,
        created_at=row['created_at'],
    )


# ---------- Journey helpers (Chunk 25) ----------

# Matches the seeded student-username format:
#   'ahmed2951@miskschools.edu.sa' -> prefix 'ahmed'
# Returns None for usernames that don't fit (e.g. teacher usernames
# or anything unexpected), so callers can degrade gracefully.
_USERNAME_PREFIX_RE = re.compile(r'^([a-zA-Z]+)\d+@')


def _resolve_username_prefix(username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    m = _USERNAME_PREFIX_RE.match(username)
    return m.group(1).lower() if m else None


def _milestone_date(current_year: Optional[int], milestone_year: int,
                    month: int) -> date:
    """Compute a plausible display date for a milestone.

    If the student has a current_year set, we anchor the milestone to
    `today.year - (current_year - milestone_year)` so a Year 10 milestone
    for a Year 12 student lands ~2 calendar years ago.

    If current_year is unknown (None), we anchor to today's year directly
    — the milestone won't render in any case (no current_year => the UI
    treats all years as future and shows no flags), so the exact date
    doesn't matter.

    Day-of-month is fixed at 15 to keep dates inside every month length
    without leap-year-style edge cases.
    """
    today_year = datetime.now().year
    if current_year is None:
        anchor_year = today_year
    else:
        anchor_year = today_year - (current_year - milestone_year)
    return date(anchor_year, month, 15)


def _build_journey_years(current_year: Optional[int],
                         username_prefix: Optional[str],
                         raw_milestones) -> list:
    """Build the per-year list (always 6 entries, Years 7..12).

    Each year's status is computed from current_year:
      - None (not set): every year is 'future'
      - set:            < current_year -> 'past'
                        == current_year -> 'current'
                        > current_year -> 'future'

    Milestones are bucketed by year. We only emit milestones for
    past/current years; a milestone whose year is ahead of the student's
    current year is dropped on the floor with no error (curated data
    shouldn't include those, but defending against typos is cheap).
    """
    # Bucket milestones by year, building stable ids for React keys.
    by_year = {}
    for idx, (m_year, title, q_name, q_color, month) in enumerate(raw_milestones):
        # Drop "future" milestones — UI doesn't render them. Curated data
        # shouldn't include any, but defending against typos costs nothing.
        if current_year is not None and m_year > current_year:
            continue
        bucket = by_year.setdefault(m_year, [])
        bucket.append(
            JourneyMilestone(
                id=f"{username_prefix or 'unknown'}-{idx}",
                title=title,
                quadrant_name=q_name,
                quadrant_color=q_color,
                date=_milestone_date(current_year, m_year, month),
            )
        )

    years = []
    for y in range(7, 13):
        if current_year is None:
            status = "future"
        elif y < current_year:
            status = "past"
        elif y == current_year:
            status = "current"
        else:
            status = "future"
        years.append(
            JourneyYear(
                year=y,
                status=status,
                completion_pct=None,  # reserved for future use
                milestones=by_year.get(y, []),
            )
        )
    return years