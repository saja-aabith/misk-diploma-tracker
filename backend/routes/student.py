# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import json
import os
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
)
from utils import (
    UPLOAD_DIR,
    get_current_student,
    validate_upload,
)

router = APIRouter()


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

    overall_completion = round(total_completion / 4, 1) if quadrants else 0

    conn.close()

    return StudentDashboard(
        student_id=student_id,
        student_name=student_name,
        overall_completion_percentage=overall_completion,
        quadrants=quadrants
    )


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
# Behaviour preserved: same status transitions on student_objective_progress,
# same response keys (additive: stored_filename, original_filename added).
# .pptx is no longer accepted (was implicit in old inline list; the spec
# allow-list does not include it).

@router.post("/upload")
async def upload_evidence(
    objective_id: int = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_student),
):
    """Upload evidence for an objective"""
    student_id = current_user['user_id']

    # 1. Validate the file (extension, size, magic bytes, filename safety).
    #    Raises HTTPException(400) with dict-detail on any failure.
    validated = await validate_upload(file)

    # 2. Verify the objective exists. Use a 404 here so the client can tell
    #    'objective not found' from 'file rejected'.
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

    # 3. Persist the file under UPLOAD_DIR using the UUID stored filename.
    #    Note: stored_filename is generated by validate_upload (UUID-based);
    #    we never write a user-supplied path.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(UPLOAD_DIR, validated.stored_filename)
    with open(disk_path, "wb") as f:
        f.write(validated.content_bytes)

    # 4. Insert the submission row, populating both legacy and new columns.
    #    file_path retains the disk path so any legacy code reading
    #    submissions still gets a string; file_name keeps the original
    #    filename for backwards-compatible frontend display.
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

    # 5. Move the objective into 'pending_review' (matches existing logic).
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
# /submissions — adds stored_filename to each row (additive)
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
        # Get reviews
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

        # Build the existing Submission model (every legacy field preserved),
        # then dump to dict and append stored_filename. This keeps all current
        # response keys identical and adds one new key.
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
# Misk Core — activity categories
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
# Misk Core — log a new activity
# ============================================================
# Multipart contract:
#   category_id   (int, required)
#   title         (str, required)
#   description   (str, optional)
#   activity_date (str ISO YYYY-MM-DD, required)
#   tags          (str, JSON-encoded array, default "[]")
#   file          (file, optional)
# Validation lives in schemas.ActivityLogIn; the route parses form fields,
# constructs the model, and lets ValidationError convert to a 400 with a
# stable code.

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

    # 1. Decode tags JSON. Empty string is also tolerated as [].
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

    # 2. Parse date (sqlite stores TEXT; we want a real date for validation).
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

    # 3. Centralised validation via the schema (length caps, tag normalisation,
    #    future-date guard).
    try:
        payload = ActivityLogIn(
            category_id=category_id,
            title=title,
            description=description,
            activity_date=parsed_date,
            tags=decoded_tags,
        )
    except ValidationError as ve:
        # First error wins; surfaces the most actionable message.
        first = ve.errors()[0] if ve.errors() else {"msg": "Invalid payload"}
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ACTIVITY_PAYLOAD_INVALID",
                "message": str(first.get("msg", "Invalid payload")),
            },
        )

    # 4. Verify the category exists and is active.
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

    # 5. Optional file attachment — same pipeline as evidence uploads.
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

    # 6. Insert. tags stored as a JSON-encoded TEXT column.
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

    # 7. Read back the full row + category name to return the canonical shape.
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
# Misk Core — list activities for the authenticated student
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

    # activity_date stored as ISO TEXT; pydantic parses str -> date.
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