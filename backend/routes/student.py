from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from database import get_db
from models import StudentDashboard, QuadrantSummary, ObjectiveProgress, Submission, SubmissionReview
from utils import get_current_user
from typing import Optional, List
import os
from datetime import datetime

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
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
    current_user: dict = Depends(get_current_user)
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

@router.post("/upload")
async def upload_evidence(
    objective_id: int = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload evidence for an objective"""
    conn = get_db()
    cursor = conn.cursor()
    
    student_id = current_user['user_id']
    
    # Validate file type
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.mp4', '.pptx']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Save file
    os.makedirs("uploads", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"submission_{student_id}_{timestamp}_{file.filename}"
    file_path = os.path.join("uploads", file_name)
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create submission record
    cursor.execute("""
        INSERT INTO evidence_submissions 
        (student_id, objective_id, file_path, file_name, description, status)
        VALUES (?, ?, ?, ?, ?, 'submitted')
    """, (student_id, objective_id, file_path, file.filename, description))
    
    submission_id = cursor.lastrowid
    
    # Update objective progress status
    cursor.execute("""
        UPDATE student_objective_progress 
        SET status = 'pending_review', updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ? AND objective_id = ?
    """, (student_id, objective_id))
    
    # If no progress record exists, create one
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO student_objective_progress 
            (student_id, objective_id, status) VALUES (?, ?, 'pending_review')
        """, (student_id, objective_id))
    
    conn.commit()
    conn.close()
    
    return {
        "submission_id": submission_id,
        "objective_id": objective_id,
        "file_name": file.filename,
        "status": "submitted",
        "submission_date": datetime.now().isoformat()
    }

@router.get("/submissions")
async def get_submissions(
    status: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """Get student submissions"""
    conn = get_db()
    cursor = conn.cursor()
    
    student_id = current_user['user_id']
    
    query = """
        SELECT es.id, es.student_id, es.objective_id, o.title as objective_title,
               q.name as quadrant_name, es.file_name, es.file_path, es.description,
               es.status, es.submission_date
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
                reviewed_at=review_row['reviewed_at']
            ))
        
        submissions.append(Submission(
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
            reviews=reviews
        ))
    
    conn.close()
    return {"submissions": submissions}