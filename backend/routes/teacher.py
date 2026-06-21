# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from database import get_db
from skills import compute_skills_profile
from models import (
    ObjectiveReport,
    QuadrantReport,
    ReviewSubmission,
    StudentReport,
    SubmissionDetail,
    SubmissionReview,
    SubmissionSummary,
)
from schemas import ActivityOut, StudentProfileOut
from utils import get_current_teacher
from report_pdf import build_student_report_pdf

router = APIRouter()


# ============================================================
# Existing routes — handler bodies preserved; role check moved
# from inline `if current_user['role'] != 'teacher'` to the
# get_current_teacher dependency (raises 403 before the body runs).
# ============================================================

@router.get("/submissions")
async def get_submissions_queue(
    status: str = "all",
    current_user: dict = Depends(get_current_teacher)
):
    """Get submissions for teacher review"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT es.id, es.student_id, u.full_name as student_name,
               es.objective_id, o.title as objective_title, q.name as quadrant_name,
               es.file_name, es.status, es.submission_date
        FROM evidence_submissions es
        JOIN users u ON es.student_id = u.id
        JOIN objectives o ON es.objective_id = o.id
        JOIN quadrants q ON o.quadrant_id = q.id
        WHERE o.is_active = 1
    """

    params = []
    if status != "all":
        query += " AND es.status = ?"
        params.append(status)

    query += " ORDER BY es.submission_date DESC"

    cursor.execute(query, params)
    submissions = []

    for row in cursor.fetchall():
        # Count reviews
        cursor.execute("""
            SELECT COUNT(*) FROM evidence_reviews WHERE submission_id = ?
        """, (row['id'],))
        review_count = cursor.fetchone()[0]

        submissions.append({
            "id": row['id'],
            "student_id": row['student_id'],
            "student_name": row['student_name'],
            "objective_id": row['objective_id'],
            "objective_title": row['objective_title'],
            "quadrant_name": row['quadrant_name'],
            "file_name": row['file_name'],
            "status": row['status'],
            "submission_date": row['submission_date'],
            "review_status": f"{review_count}/2"
        })

    conn.close()
    return {"submissions": submissions}


@router.get("/submission/{submission_id}")
async def get_submission_detail(
    submission_id: int,
    current_user: dict = Depends(get_current_teacher)
):
    """Get detailed submission info"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT es.id, es.student_id, u.full_name as student_name,
               es.objective_id, o.title as objective_title,
               o.quadrant_id, q.name as quadrant_name,
               es.file_name, es.file_path, es.description,
               es.status, es.submission_date
        FROM evidence_submissions es
        JOIN users u ON es.student_id = u.id
        JOIN objectives o ON es.objective_id = o.id
        JOIN quadrants q ON o.quadrant_id = q.id
        WHERE es.id = ?
    """, (submission_id,))

    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Get reviews
    cursor.execute("""
        SELECT er.id, er.teacher_id, u.full_name as teacher_name,
               er.rating, er.feedback, er.decision, er.reviewed_at
        FROM evidence_reviews er
        JOIN users u ON er.teacher_id = u.id
        WHERE er.submission_id = ?
        ORDER BY er.reviewed_at DESC
    """, (submission_id,))

    reviews = []
    for review_row in cursor.fetchall():
        reviews.append(SubmissionReview(
            id=review_row['id'],
            teacher_id=review_row['teacher_id'],
            teacher_name=review_row['teacher_name'],
            rating=review_row['rating'],
            feedback=review_row['feedback'],
            decision=review_row['decision'],
            reviewed_at=review_row['reviewed_at']
        ))

    approval_progress = f"{len([r for r in reviews if r.decision == 'approved'])}/2"

    conn.close()

    return SubmissionDetail(
        id=row['id'],
        student_id=row['student_id'],
        student_name=row['student_name'],
        objective_id=row['objective_id'],
        objective_title=row['objective_title'],
        quadrant_id=row['quadrant_id'],
        quadrant_name=row['quadrant_name'],
        file_name=row['file_name'],
        file_path=row['file_path'],
        description=row['description'],
        status=row['status'],
        submission_date=row['submission_date'],
        approval_progress=approval_progress,
        reviews=reviews
    )


@router.post("/review")
async def submit_review(
    review: ReviewSubmission,
    current_user: dict = Depends(get_current_teacher)
):
    """Submit a review for a submission"""
    conn = get_db()
    cursor = conn.cursor()

    teacher_id = current_user['user_id']

    # Check if teacher already reviewed.
    # NOTE: this pre-check is the fast/cheap path for the common "user
    # already reviewed and is trying again" case. It does NOT close the
    # race against a concurrent request from the same teacher (e.g. a
    # double-click): two requests can both pass this SELECT before either
    # reaches the INSERT below. The UNIQUE INDEX
    # idx_evidence_reviews_submission_teacher (created in database.py)
    # closes that window, and the IntegrityError handler around the
    # INSERT below converts the constraint violation into the same 400
    # response shape the pre-check returns.
    cursor.execute("""
        SELECT * FROM evidence_reviews
        WHERE submission_id = ? AND teacher_id = ?
    """, (review.submission_id, teacher_id))

    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="You have already reviewed this submission")

    # Insert review. UNIQUE(submission_id, teacher_id) enforces
    # one-review-per-teacher-per-submission at the DB layer; on a race the
    # loser raises sqlite3.IntegrityError which we map to the same 400 the
    # pre-check returns so the frontend has a single error path to handle.
    try:
        cursor.execute("""
            INSERT INTO evidence_reviews (submission_id, teacher_id, rating, feedback, decision)
            VALUES (?, ?, ?, ?, ?)
        """, (review.submission_id, teacher_id, review.rating, review.feedback, review.decision))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="You have already reviewed this submission")

    review_id = cursor.lastrowid

    # Check for auto-approval
    cursor.execute("""
        SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
        FROM evidence_reviews
        WHERE submission_id = ? AND decision = 'approved'
    """, (review.submission_id,))

    result = cursor.fetchone()
    avg_rating = result['avg_rating'] if result['avg_rating'] else 0
    review_count = result['review_count']

    auto_approved = False
    message = f"Review submitted. {review_count}/2 approvals needed."

    if review_count >= 2 and avg_rating >= 2.5:
        # Auto-approve submission
        cursor.execute("""
            UPDATE evidence_submissions
            SET status = 'approved'
            WHERE id = ?
        """, (review.submission_id,))

        # Update student progress
        cursor.execute("""
            SELECT student_id, objective_id FROM evidence_submissions WHERE id = ?
        """, (review.submission_id,))
        sub = cursor.fetchone()

        cursor.execute("""
            UPDATE student_objective_progress
            SET status = 'approved', current_points = 100, completion_percentage = 100
            WHERE student_id = ? AND objective_id = ?
        """, (sub['student_id'], sub['objective_id']))

        auto_approved = True
        message = "Evidence automatically approved!"

    conn.commit()
    conn.close()

    return {
        "review_id": review_id,
        "submission_id": review.submission_id,
        "decision": review.decision,
        "auto_approved": auto_approved,
        "message": message
    }


@router.get("/report/{student_id}")
async def get_student_report(
    student_id: int,
    current_user: dict = Depends(get_current_teacher)
):
    """Get comprehensive student report"""
    conn = get_db()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT full_name FROM users WHERE id = ? AND role = 'student'", (student_id,))
    student = cursor.fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student_name = student['full_name']

    # Get quadrant reports
    cursor.execute("""
        SELECT q.id, q.name, q.color_hex,
               AVG(sop.completion_percentage) as avg_completion
        FROM quadrants q
        LEFT JOIN objectives o ON q.id = o.quadrant_id AND o.is_active = 1
        LEFT JOIN student_objective_progress sop ON o.id = sop.objective_id AND sop.student_id = ?
        GROUP BY q.id
        ORDER BY q.display_order
    """, (student_id,))

    quadrant_reports = []
    total_completion = 0

    for quad_row in cursor.fetchall():
        completion = quad_row['avg_completion'] if quad_row['avg_completion'] else 0
        total_completion += completion

        # Get objectives for this quadrant
        cursor.execute("""
            SELECT o.id, o.title,
                   COALESCE(sop.completion_percentage, 0) as completion_percentage,
                   COALESCE(sop.status, 'not_started') as status
            FROM objectives o
            LEFT JOIN student_objective_progress sop ON o.id = sop.objective_id AND sop.student_id = ?
            WHERE o.quadrant_id = ? AND o.is_active = 1
        """, (student_id, quad_row['id']))

        objectives = []
        for obj_row in cursor.fetchall():
            # Count submissions
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
                FROM evidence_submissions
                WHERE student_id = ? AND objective_id = ?
            """, (student_id, obj_row['id']))

            sub_counts = cursor.fetchone()

            objectives.append(ObjectiveReport(
                objective_id=obj_row['id'],
                title=obj_row['title'],
                completion_percentage=obj_row['completion_percentage'],
                status=obj_row['status'],
                submissions=sub_counts['total'] if sub_counts['total'] else 0,
                approved=sub_counts['approved'] if sub_counts['approved'] else 0
            ))

        quadrant_reports.append(QuadrantReport(
            quadrant_id=quad_row['id'],
            quadrant_name=quad_row['name'],
            color=quad_row['color_hex'],
            completion_percentage=round(completion, 1),
            objectives=objectives
        ))

    # Get submission summary
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN status IN ('submitted', 'under_review') THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
        FROM evidence_submissions
        WHERE student_id = ?
    """, (student_id,))

    summary = cursor.fetchone()

    submission_summary = SubmissionSummary(
        total_submitted=summary['total'] if summary['total'] else 0,
        total_approved=summary['approved'] if summary['approved'] else 0,
        pending_review=summary['pending'] if summary['pending'] else 0,
        rejected=summary['rejected'] if summary['rejected'] else 0
    )

    # Overall completion is the mean across however many quadrants exist.
    # Previously hardcoded to 4; updated in Chunk 21 when Misk Core was
    # added as a fifth row in the `quadrants` table.
    overall_completion = (
        round(total_completion / len(quadrant_reports), 1)
        if quadrant_reports else 0
    )

    conn.close()

    return StudentReport(
        student_id=student_id,
        student_name=student_name,
        overall_completion_percentage=overall_completion,
        quadrant_reports=quadrant_reports,
        submission_summary=submission_summary
    )


# ============================================================
# New: GET /teacher/student-profile/{student_id}
# ============================================================
# MVP shape per StudentProfileOut: identity + Misk Core activities only.
# /teacher/report/{student_id} above already covers quadrant breakdowns
# and submission summary; the frontend (Chunk 13) composes both views.
# Any future extension to this response must be additive (optional fields).

@router.get("/student-profile/{student_id}", response_model=StudentProfileOut)
async def get_student_profile(
    student_id: int,
    category_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_teacher),
):
    """Teacher view of a student's identity and Misk Core activity log."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Verify the student exists.
    cursor.execute(
        "SELECT id, full_name, email FROM users WHERE id = ? AND role = 'student'",
        (student_id,),
    )
    student_row = cursor.fetchone()
    if student_row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Read the student's Misk Core activities (newest first), optionally
    #    filtered by category. Same join shape as /student/activities so
    #    consumers can render either feed identically.
    query = """
        SELECT sa.id, sa.student_id, sa.category_id, ac.name as category_name,
               sa.title, sa.description, sa.activity_date,
               sa.stored_filename, sa.original_filename, sa.file_extension,
               sa.file_size_bytes, sa.mime_type, sa.tags, sa.created_at,
               sa.status, sa.review_feedback
        FROM student_activities sa
        JOIN activity_categories ac ON ac.id = sa.category_id
        WHERE sa.student_id = ?
    """
    params = [student_id]

    if category_id is not None:
        query += " AND sa.category_id = ?"
        params.append(category_id)

    query += " ORDER BY sa.activity_date DESC, sa.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    activities = [_row_to_activity_out(row) for row in cursor.fetchall()]
    conn.close()

    return StudentProfileOut(
        student_id=student_row['id'],
        student_name=student_row['full_name'],
        email=student_row['email'],
        activities=activities,
    )


# ============================================================
# Private helpers
# ============================================================

def _row_to_activity_out(row) -> ActivityOut:
    """Convert a sqlite3.Row from the activities/categories join into
    an ActivityOut. Decodes tags JSON with a permissive fallback so a
    legacy NULL or malformed value doesn't 500 the profile endpoint.

    Mirrors routes/student.py._row_to_activity_out. Kept local rather
    than extracted to a shared module to keep this chunk's diff tight.
    """
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
        status=row['status'],
        review_feedback=row['review_feedback'],
    )

# ============================================================
# Chunk 31: result capture + manual diploma award
# ============================================================

# Result-based academic objectives — the only mandatory items with numeric
# performance variation. Titles must match the active objective titles.
RESULT_BASED_TITLES = {"IELTS", "IGCSE", "IAL", "Qudurat", "Tahsili"}

# Max sit count per objective (Resilience attempt signal); others = 1.
ATTEMPT_LIMITS = {"Qudurat": 5, "Tahsili": 2}

# Valid grade tokens for grade-list objectives (capture-time validation only;
# the grade->points conversion + performance ratio live in the skills engine).
IGCSE_GRADES = {"U", "G", "F", "E", "D", "C", "B", "A", "A*"}
IAL_GRADES = {"U", "E", "D", "C", "B", "A", "A*"}

# Formal diploma award bands. The system stores the teacher's selection; it
# never computes or differentiates between these.
AWARD_LEVELS = {"Pass", "Merit", "Distinction"}


class ObjectiveResultIn(BaseModel):
    student_id: int
    objective_id: int
    score: Optional[float] = None        # IELTS / Qudurat / Tahsili
    grades: Optional[List[str]] = None   # IGCSE / IAL
    attempts: Optional[int] = 1


class DiplomaAwardIn(BaseModel):
    student_id: int
    award_level: str
    notes: Optional[str] = None


def _err(status_code: int, code: str, message: str):
    """Raise an HTTPException in the target error shape."""
    raise HTTPException(status_code=status_code,
                        detail={"code": code, "message": message})


def _is_eligible(cursor, student_id: int) -> bool:
    """Eligible when every ACTIVE objective has an approved progress row.
    Misk Core has no active objectives, so this reduces to the mandatory set."""
    cursor.execute("SELECT COUNT(*) FROM objectives WHERE is_active = 1")
    active = cursor.fetchone()[0]
    if active == 0:
        return False
    cursor.execute(
        """
        SELECT COUNT(*) FROM student_objective_progress sop
        JOIN objectives o ON o.id = sop.objective_id
        WHERE sop.student_id = ? AND o.is_active = 1 AND sop.status = 'approved'
        """,
        (student_id,),
    )
    approved = cursor.fetchone()[0]
    return approved == active


@router.post("/objective-result")
async def record_objective_result(
    payload: ObjectiveResultIn,
    current_user: dict = Depends(get_current_teacher),
):
    """Record the official result for a result-based academic objective.

    Stores result_value (a number string for IELTS/Qudurat/Tahsili, or a JSON
    grade array for IGCSE/IAL) and attempts on the student's progress row.
    Capture only — performance scaling into skills happens in the skills
    engine. Teacher-only.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT title FROM objectives WHERE id = ? AND is_active = 1",
        (payload.objective_id,),
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        _err(404, "OBJECTIVE_NOT_FOUND", "Objective not found or inactive.")
    title = row['title']
    if title not in RESULT_BASED_TITLES:
        conn.close()
        _err(400, "OBJECTIVE_NOT_RESULT_BASED",
             f"'{title}' does not capture a numeric/grade result.")

    cursor.execute(
        "SELECT id FROM student_objective_progress "
        "WHERE student_id = ? AND objective_id = ?",
        (payload.student_id, payload.objective_id),
    )
    if cursor.fetchone() is None:
        conn.close()
        _err(404, "PROGRESS_ROW_NOT_FOUND",
             "No progress row for this student and objective.")

    if title in ("IELTS", "Qudurat", "Tahsili"):
        if payload.score is None:
            conn.close()
            _err(400, "RESULT_SCORE_REQUIRED", f"{title} requires a numeric score.")
        lo, hi = (0.0, 9.0) if title == "IELTS" else (0.0, 100.0)
        if not (lo <= payload.score <= hi):
            conn.close()
            _err(400, "RESULT_OUT_OF_RANGE",
                 f"{title} score must be between {lo} and {hi}.")
        result_value = str(payload.score)
    else:  # IGCSE / IAL
        if not payload.grades:
            conn.close()
            _err(400, "RESULT_GRADES_REQUIRED", f"{title} requires a list of grades.")
        valid = IGCSE_GRADES if title == "IGCSE" else IAL_GRADES
        normalised = [g.strip().upper() for g in payload.grades]
        bad = [g for g in normalised if g not in valid]
        if bad:
            conn.close()
            _err(400, "RESULT_INVALID_GRADE",
                 f"Invalid {title} grade(s): {', '.join(bad)}.")
        result_value = json.dumps(normalised)

    max_attempts = ATTEMPT_LIMITS.get(title, 1)
    attempts = payload.attempts if payload.attempts is not None else 1
    if not (1 <= attempts <= max_attempts):
        conn.close()
        _err(400, "RESULT_ATTEMPTS_INVALID",
             f"{title} allows 1 to {max_attempts} attempt(s).")

    cursor.execute(
        "UPDATE student_objective_progress SET result_value = ?, attempts = ? "
        "WHERE student_id = ? AND objective_id = ?",
        (result_value, attempts, payload.student_id, payload.objective_id),
    )
    conn.commit()
    conn.close()
    return {
        "student_id": payload.student_id,
        "objective_id": payload.objective_id,
        "title": title,
        "result_value": result_value,
        "attempts": attempts,
    }


@router.get("/diploma-award/{student_id}")
async def get_diploma_award(
    student_id: int,
    current_user: dict = Depends(get_current_teacher),
):
    """Return the student's diploma award state plus live eligibility (whether
    every active mandatory objective is approved). Teacher-only."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, full_name FROM users WHERE id = ? AND role = 'student'",
        (student_id,),
    )
    student = cursor.fetchone()
    if student is None:
        conn.close()
        _err(404, "STUDENT_NOT_FOUND", "Student not found.")

    eligible = _is_eligible(cursor, student_id)

    cursor.execute(
        """
        SELECT da.award_level, da.selected_by, da.selected_at, da.notes,
               u.full_name AS selected_by_name
        FROM diploma_awards da
        LEFT JOIN users u ON u.id = da.selected_by
        WHERE da.student_id = ?
        """,
        (student_id,),
    )
    award_row = cursor.fetchone()
    conn.close()

    award = None
    if award_row is not None and award_row['award_level'] is not None:
        award = {
            "award_level": award_row['award_level'],
            "selected_by": award_row['selected_by'],
            "selected_by_name": award_row['selected_by_name'],
            "selected_at": award_row['selected_at'],
            "notes": award_row['notes'],
        }

    return {
        "student_id": student_id,
        "student_name": student['full_name'],
        "eligible_for_diploma": eligible,
        "award": award,
    }


@router.post("/diploma-award")
async def set_diploma_award(
    payload: DiplomaAwardIn,
    current_user: dict = Depends(get_current_teacher),
):
    """Manually select the formal diploma award for an eligible student.

    The system does not compute Pass/Merit/Distinction; it records the
    teacher's holistic selection plus who selected it and when. Requires the
    student to be eligible (all active mandatory objectives approved).
    Teacher-only.
    """
    if payload.award_level not in AWARD_LEVELS:
        _err(400, "AWARD_LEVEL_INVALID",
             f"award_level must be one of: {', '.join(sorted(AWARD_LEVELS))}.")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'student'",
        (payload.student_id,),
    )
    if cursor.fetchone() is None:
        conn.close()
        _err(404, "STUDENT_NOT_FOUND", "Student not found.")

    if not _is_eligible(cursor, payload.student_id):
        conn.close()
        _err(409, "DIPLOMA_NOT_ELIGIBLE",
             "Student is not yet eligible: all mandatory objectives must be approved.")

    teacher_id = current_user['user_id']
    selected_at = datetime.utcnow().isoformat()

    cursor.execute("SELECT id FROM diploma_awards WHERE student_id = ?",
                   (payload.student_id,))
    existing = cursor.fetchone()
    if existing is None:
        cursor.execute(
            "INSERT INTO diploma_awards "
            "(student_id, eligible_for_diploma, award_level, selected_by, selected_at, notes) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            (payload.student_id, payload.award_level, teacher_id, selected_at, payload.notes),
        )
    else:
        cursor.execute(
            "UPDATE diploma_awards SET eligible_for_diploma = 1, award_level = ?, "
            "selected_by = ?, selected_at = ?, notes = ? WHERE student_id = ?",
            (payload.award_level, teacher_id, selected_at, payload.notes, payload.student_id),
        )
    conn.commit()
    conn.close()

    return {
        "student_id": payload.student_id,
        "eligible_for_diploma": True,
        "award_level": payload.award_level,
        "selected_by": teacher_id,
        "selected_at": selected_at,
        "notes": payload.notes,
    }


# ============================================================
# Chunk 32: Misk Core activity review (teacher queue + decision)
# ============================================================

class ActivitySkillLevelIn(BaseModel):
    rating_id: int
    level: int                 # 0=Not evident(reject) .. 3=Embedded


class ActivityReviewIn(BaseModel):
    activity_id: int
    decision: str              # 'approved' | 'rejected'
    feedback: Optional[str] = None
    # Per-claim teacher levels for this activity's Misk Core skill claims.
    # Optional (legacy callers omit it); the new review UI sends one per claim.
    skill_levels: List[ActivitySkillLevelIn] = []


ACTIVITY_STATUSES = {"pending_review", "approved", "rejected"}


def _review_skills_by_activity(cursor, activity_ids):
    """Map activity_id -> list of its skill claims {id, dimension, justification,
    level, status} for the review queue. One query; empty input -> {}."""
    if not activity_ids:
        return {}
    placeholders = ",".join("?" for _ in activity_ids)
    cursor.execute(
        f"""
        SELECT id, activity_id, dimension, justification, level, status
        FROM core_skill_ratings
        WHERE activity_id IN ({placeholders})
        ORDER BY id ASC
        """,
        list(activity_ids),
    )
    out = {}
    for r in cursor.fetchall():
        out.setdefault(r['activity_id'], []).append({
            "id": r['id'],
            "dimension": r['dimension'],
            "justification": r['justification'],
            "level": r['level'],
            "status": r['status'],
        })
    return out


def _activity_review_row(row) -> dict:
    """Shape a student_activities row (joined with category + student) for the
    teacher review queue. Decodes the tags JSON permissively so a legacy NULL
    or malformed value doesn't 500 the queue."""
    raw_tags = row['tags']
    if not raw_tags:
        decoded_tags = []
    else:
        try:
            decoded = json.loads(raw_tags)
            decoded_tags = decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            decoded_tags = []
    return {
        "id": row['id'],
        "student_id": row['student_id'],
        "student_name": row['student_name'],
        "category_id": row['category_id'],
        "category_name": row['category_name'],
        "title": row['title'],
        "description": row['description'],
        "activity_date": row['activity_date'],
        "stored_filename": row['stored_filename'],
        "original_filename": row['original_filename'],
        "file_extension": row['file_extension'],
        "file_size_bytes": row['file_size_bytes'],
        "mime_type": row['mime_type'],
        "tags": decoded_tags,
        "created_at": row['created_at'],
        "status": row['status'],
        "review_feedback": row['review_feedback'],
        "reviewed_by": row['reviewed_by'],
        "reviewed_at": row['reviewed_at'],
    }


@router.get("/activities")
async def list_activities_for_review(
    status: str = Query("pending_review"),
    current_user: dict = Depends(get_current_teacher),
):
    """Misk Core activity review queue. `status` filters by activity status
    (pending_review | approved | rejected) or 'all'. Oldest-first (FIFO).
    Teacher-only."""
    if status != "all" and status not in ACTIVITY_STATUSES:
        _err(400, "ACTIVITY_STATUS_INVALID",
             f"status must be 'all' or one of: {', '.join(sorted(ACTIVITY_STATUSES))}.")

    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT sa.id, sa.student_id, u.full_name AS student_name,
               sa.category_id, ac.name AS category_name,
               sa.title, sa.description, sa.activity_date,
               sa.stored_filename, sa.original_filename, sa.file_extension,
               sa.file_size_bytes, sa.mime_type, sa.tags, sa.created_at,
               sa.status, sa.review_feedback, sa.reviewed_by, sa.reviewed_at
        FROM student_activities sa
        JOIN activity_categories ac ON ac.id = sa.category_id
        JOIN users u ON u.id = sa.student_id
    """
    params = []
    if status != "all":
        query += " WHERE sa.status = ?"
        params.append(status)
    query += " ORDER BY sa.created_at ASC, sa.id ASC"

    cursor.execute(query, params)
    activities = [_activity_review_row(r) for r in cursor.fetchall()]
    skills_by_activity = _review_skills_by_activity(cursor, [a["id"] for a in activities])
    for a in activities:
        a["skills"] = skills_by_activity.get(a["id"], [])
    conn.close()
    return {"activities": activities}


@router.post("/activity-review")
async def review_activity(
    payload: ActivityReviewIn,
    current_user: dict = Depends(get_current_teacher),
):
    """Approve or reject a Misk Core activity. Records the decision, reviewing
    teacher, timestamp, and optional feedback. Teacher-only.

    State: pending_review -> approved | rejected. A teacher may also correct a
    prior decision (e.g. approved -> rejected); the latest decision wins.
    """
    if payload.decision not in ("approved", "rejected"):
        _err(400, "ACTIVITY_DECISION_INVALID",
             "decision must be 'approved' or 'rejected'.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM student_activities WHERE id = ?",
                   (payload.activity_id,))
    if cursor.fetchone() is None:
        conn.close()
        _err(404, "ACTIVITY_NOT_FOUND", "Activity not found.")

    teacher_id = current_user['user_id']
    reviewed_at = datetime.utcnow().isoformat()
    cursor.execute(
        "UPDATE student_activities SET status = ?, reviewed_by = ?, "
        "reviewed_at = ?, review_feedback = ? WHERE id = ?",
        (payload.decision, teacher_id, reviewed_at, payload.feedback,
         payload.activity_id),
    )

    # Apply the per-claim decision to this activity's Misk Core skill claims.
    cursor.execute(
        "SELECT id FROM core_skill_ratings WHERE activity_id = ?",
        (payload.activity_id,),
    )
    valid_ids = {r['id'] for r in cursor.fetchall()}

    if payload.decision == "rejected":
        # Whole activity rejected -> every claim is Not evident.
        cursor.execute(
            "UPDATE core_skill_ratings SET status = 'rejected', level = 0, "
            "reviewed_by = ?, reviewed_at = ? WHERE activity_id = ?",
            (teacher_id, reviewed_at, payload.activity_id),
        )
    else:
        for sl in payload.skill_levels:
            if sl.rating_id not in valid_ids:
                conn.close()
                _err(400, "ACTIVITY_SKILL_RATING_INVALID",
                     f"Skill rating {sl.rating_id} does not belong to this activity.")
            if sl.level < 0 or sl.level > 3:
                conn.close()
                _err(400, "ACTIVITY_SKILL_LEVEL_INVALID",
                     "level must be between 0 (Not evident) and 3 (Embedded).")
            new_status = "rejected" if sl.level == 0 else "approved"
            cursor.execute(
                "UPDATE core_skill_ratings SET status = ?, level = ?, "
                "reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                (new_status, sl.level, teacher_id, reviewed_at, sl.rating_id),
            )

    conn.commit()
    updated_skills = _review_skills_by_activity(cursor, [payload.activity_id]).get(
        payload.activity_id, [])
    conn.close()

    # NOTE (Step 5, post sign-off): Gemini skill extraction for APPROVED Misk
    # Core activities is a separate, gated path (sending activity text off-site).
    # Skill levels here are TEACHER-assigned only; no AI call.

    return {
        "activity_id": payload.activity_id,
        "status": payload.decision,
        "reviewed_by": teacher_id,
        "reviewed_at": reviewed_at,
        "review_feedback": payload.feedback,
        "skills": updated_skills,
    }


@router.get("/skills-profile/{student_id}")
async def get_student_skills_profile(
    student_id: int,
    current_user: dict = Depends(get_current_teacher),
):
    """A student's 16-dimension Misk Skills Profile (teacher view).

    Computed live from approved objective progress (compute-on-read; nothing
    stored). Teacher-only; 404 if the student does not exist.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT full_name FROM users WHERE id = ? AND role = 'student'",
        (student_id,),
    )
    student = cursor.fetchone()
    if student is None:
        conn.close()
        _err(404, "STUDENT_NOT_FOUND", "Student not found.")

    profile = compute_skills_profile(cursor, student_id)
    profile["student_name"] = student['full_name']
    conn.close()
    return profile


def _fmt_result(result_value):
    """Human-readable result for the PDF: grade arrays render as 'A*, A, B';
    numeric strings (IELTS/Qudurat/Tahsili) pass through; empty -> em dash."""
    if not result_value:
        return "\u2014"
    rv = str(result_value).strip()
    if rv.startswith("["):
        try:
            arr = json.loads(rv)
            if isinstance(arr, list):
                return ", ".join(str(x) for x in arr)
        except (ValueError, json.JSONDecodeError):
            pass
    return rv


@router.get("/report-pdf/{student_id}")
async def get_student_report_pdf(
    student_id: int,
    current_user: dict = Depends(get_current_teacher),
):
    """Stream a single PDF report for one student: the formal Misk Diploma
    (manual award + mandatory-objective progress) and the Misk Skills Profile.

    Teacher-only; 404 if the student does not exist. The PDF is built in memory
    and streamed straight to the authenticated teacher — nothing is written to
    disk or any third-party store (school-controlled per the data policy).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT full_name FROM users WHERE id = ? AND role = 'student'",
        (student_id,),
    )
    student = cursor.fetchone()
    if student is None:
        conn.close()
        _err(404, "STUDENT_NOT_FOUND", "Student not found.")
    student_name = student['full_name']

    # Diploma award row (if any).
    cursor.execute(
        """
        SELECT da.award_level, da.selected_at, u.full_name AS selected_by_name
        FROM diploma_awards da
        LEFT JOIN users u ON u.id = da.selected_by
        WHERE da.student_id = ?
        """,
        (student_id,),
    )
    award_row = cursor.fetchone()

    # Live eligibility + counts (same logic as _is_eligible; computed inline so
    # the report can also show "N of M approved" while in progress).
    cursor.execute("SELECT COUNT(*) FROM objectives WHERE is_active = 1")
    active_count = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM student_objective_progress sop
        JOIN objectives o ON o.id = sop.objective_id
        WHERE sop.student_id = ? AND o.is_active = 1 AND sop.status = 'approved'
        """,
        (student_id,),
    )
    approved_count = cursor.fetchone()[0]

    diploma = {
        "award_level": award_row['award_level'] if award_row else None,
        "selected_by_name": award_row['selected_by_name'] if award_row else None,
        "selected_at": award_row['selected_at'] if award_row else None,
        "eligible": active_count > 0 and approved_count == active_count,
        "approved_count": approved_count,
        "active_count": active_count,
    }

    # Mandatory-objective progress grouped by quadrant, in display order. Misk
    # Core has no active objectives, so it yields no rows and is omitted.
    cursor.execute(
        """
        SELECT q.name AS quadrant_name, q.color_hex AS color,
               o.id AS objective_id, o.title AS title,
               COALESCE(sop.status, 'not_started') AS status,
               sop.result_value AS result_value
        FROM quadrants q
        JOIN objectives o ON o.quadrant_id = q.id AND o.is_active = 1
        LEFT JOIN student_objective_progress sop
               ON sop.objective_id = o.id AND sop.student_id = ?
        ORDER BY q.display_order, o.id
        """,
        (student_id,),
    )
    quadrants = []
    by_quadrant = {}
    for row in cursor.fetchall():
        qname = row['quadrant_name']
        if qname not in by_quadrant:
            by_quadrant[qname] = {"name": qname, "color": row['color'], "objectives": []}
            quadrants.append(by_quadrant[qname])
        by_quadrant[qname]["objectives"].append({
            "title": row['title'],
            "status": row['status'],
            "result_display": _fmt_result(row['result_value']),
        })

    skills = compute_skills_profile(cursor, student_id)
    conn.close()

    report = {
        "student_name": student_name,
        "generated_at": datetime.utcnow().strftime("%d %B %Y, %H:%M UTC"),
        "diploma": diploma,
        "quadrants": quadrants,
        "skills": skills,
    }
    pdf_bytes = build_student_report_pdf(report)

    safe = "".join(c for c in student_name if c.isalnum() or c in " -_").strip()
    filename = "Misk_Diploma_Report_%s.pdf" % (safe.replace(" ", "_") or "student")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


@router.get("/students")
async def list_students(current_user: dict = Depends(get_current_teacher)):
    """The full student roster for teacher pickers (Student Reports / Profiles).

    Returns every student regardless of whether they have uploaded evidence, so
    fully-approved students with no file uploads still appear. Teacher-only.
    Shape: { "students": [ { "id", "full_name" } ] }, ordered by name.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name FROM users WHERE role = 'student' ORDER BY full_name"
    )
    students = [{"id": r['id'], "full_name": r['full_name']} for r in cursor.fetchall()]
    conn.close()
    return {"students": students}