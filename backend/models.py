from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Authentication Models
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str]

class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse

# Student Models
class ObjectiveProgress(BaseModel):
    id: int
    quadrant_id: int
    quadrant_name: str
    title: str
    description: Optional[str]
    current_points: int
    max_points: int
    completion_percentage: float
    status: str
    submission_count: int
    approved_count: int

class QuadrantSummary(BaseModel):
    id: int
    name: str
    color: str
    completion_percentage: float
    objectives_completed: int
    total_objectives: int

class StudentDashboard(BaseModel):
    student_id: int
    student_name: str
    overall_completion_percentage: float
    quadrants: List[QuadrantSummary]

class SubmissionReview(BaseModel):
    id: int
    teacher_id: int
    teacher_name: str
    rating: int
    feedback: Optional[str]
    decision: str
    reviewed_at: datetime

class Submission(BaseModel):
    id: int
    student_id: int
    objective_id: int
    objective_title: str
    quadrant_name: str
    file_name: str
    file_path: str
    description: Optional[str]
    status: str
    submission_date: datetime
    review_count: int
    reviews: List[SubmissionReview]

# Teacher Models
class ReviewSubmission(BaseModel):
    submission_id: int
    rating: int
    decision: str
    feedback: Optional[str] = None

class SubmissionDetail(BaseModel):
    id: int
    student_id: int
    student_name: str
    objective_id: int
    objective_title: str
    quadrant_id: int
    quadrant_name: str
    file_name: str
    file_path: str
    description: Optional[str]
    status: str
    submission_date: datetime
    approval_progress: str
    reviews: List[SubmissionReview]

class ObjectiveReport(BaseModel):
    objective_id: int
    title: str
    completion_percentage: float
    status: str
    submissions: int
    approved: int

class QuadrantReport(BaseModel):
    quadrant_id: int
    quadrant_name: str
    color: str
    completion_percentage: float
    objectives: List[ObjectiveReport]

class SubmissionSummary(BaseModel):
    total_submitted: int
    total_approved: int
    pending_review: int
    rejected: int

class StudentReport(BaseModel):
    student_id: int
    student_name: str
    overall_completion_percentage: float
    quadrant_reports: List[QuadrantReport]
    submission_summary: SubmissionSummary