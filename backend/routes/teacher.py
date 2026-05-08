# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_db
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
    """

    params = []
    if status != "all":
        query += " WHERE es.status = ?"
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

    # Check if teacher already reviewed
    cursor.execute("""
        SELECT * FROM evidence_reviews
        WHERE submission_id = ? AND teacher_id = ?
    """, (review.submission_id, teacher_id))

    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="You have already reviewed this submission")

    # Insert review
    cursor.execute("""
        INSERT INTO evidence_reviews (submission_id, teacher_id, rating, feedback, decision)
        VALUES (?, ?, ?, ?, ?)
    """, (review.submission_id, teacher_id, review.rating, review.feedback, review.decision))

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
        LEFT JOIN objectives o ON q.id = o.quadrant_id
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
            WHERE o.quadrant_id = ?
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

    overall_completion = round(total_completion / 4, 1) if quadrant_reports else 0

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
               sa.file_size_bytes, sa.mime_type, sa.tags, sa.created_at
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
    )