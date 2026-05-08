from typing import TypeVar, Generic, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator

# ============================================================
# Generic API wrappers (existing — DO NOT change shape/behaviour)
# ============================================================
T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str


# ============================================================
# Misk Core schemas (Type 2: free-form activity log, no review)
# ============================================================
# Domain language reminder:
#   - "Misk Core activity" = free-form student log entry, NOT teacher-reviewed.
#   - Distinct pipeline from "evidence submission" (Type 1, in models.py).
# These constants are exported so the route layer (Chunk 6) imports the same
# values and validation rules don't drift between schema and handler.

MAX_ACTIVITY_TITLE_LEN = 200
MAX_ACTIVITY_DESCRIPTION_LEN = 4000
MAX_ACTIVITY_TAGS = 10
MAX_ACTIVITY_TAG_LEN = 32


class ActivityCategoryOut(BaseModel):
    """Read model for an entry in the Misk Core activity taxonomy.

    Surfaces the seeded `activity_categories` rows to the student UI for the
    'log activity' picker. `is_active` is filtered at the route layer; only
    active categories should reach the client.
    """
    id: int
    name: str
    description: Optional[str] = None
    display_order: Optional[int] = None


class ActivityLogIn(BaseModel):
    """Validated payload for creating a Misk Core activity.

    POST /student/activities is multipart (optional file attachment) so the
    route handler will receive Form/File fields directly. After parsing, the
    handler constructs an ActivityLogIn(...) to centralise validation rules
    (length caps, tag normalisation, future-date guard) here rather than in
    the route body. Keeping these rules in the schema makes them traceable
    and reusable if a JSON variant is ever added.

    NOTE: this model intentionally does NOT carry file metadata. File handling
    happens in the route via UploadFile + the shared validate_upload() helper
    (added in Chunk 4); only the parsed/validated text payload lives here.
    """
    category_id: int = Field(..., gt=0)
    title: str
    description: Optional[str] = None
    activity_date: date
    tags: List[str] = Field(default_factory=list)

    @field_validator('title')
    @classmethod
    def _validate_title(cls, v: str) -> str:
        # Strip first, then check non-empty: a whitespace-only title is invalid.
        v = (v or "").strip()
        if not v:
            raise ValueError("title cannot be empty")
        if len(v) > MAX_ACTIVITY_TITLE_LEN:
            raise ValueError(
                f"title must be {MAX_ACTIVITY_TITLE_LEN} characters or fewer"
            )
        return v

    @field_validator('description')
    @classmethod
    def _validate_description(cls, v: Optional[str]) -> Optional[str]:
        # Treat empty / whitespace-only descriptions as None so the DB stores
        # NULL rather than an empty string. Keeps downstream queries simple.
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > MAX_ACTIVITY_DESCRIPTION_LEN:
            raise ValueError(
                f"description must be {MAX_ACTIVITY_DESCRIPTION_LEN} characters or fewer"
            )
        return v

    @field_validator('activity_date')
    @classmethod
    def _validate_date_not_future(cls, v: date) -> date:
        # Activities can only be logged for things that have happened.
        # Using date.today() (process-local) is acceptable for MVP; revisit
        # if a different timezone reference becomes a requirement.
        if v > date.today():
            raise ValueError("activity_date cannot be in the future")
        return v

    @field_validator('tags')
    @classmethod
    def _normalise_tags(cls, v: List[str]) -> List[str]:
        """Lower-case, strip, dedupe, length-check, and cap tag count.

        Tags are the primary structured signal we'll feed to the post-MVP LLM
        layer, so consistency matters: we normalise here so two students who
        type 'Leadership' and 'leadership ' end up with the same tag.
        """
        if not v:
            return []
        cleaned: List[str] = []
        seen = set()
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError("tags must be strings")
            tag = raw.strip().lower()
            if not tag:
                continue
            if len(tag) > MAX_ACTIVITY_TAG_LEN:
                raise ValueError(
                    f"tag too long (max {MAX_ACTIVITY_TAG_LEN} characters): {tag!r}"
                )
            if tag in seen:
                continue
            seen.add(tag)
            cleaned.append(tag)
        if len(cleaned) > MAX_ACTIVITY_TAGS:
            raise ValueError(f"too many tags (max {MAX_ACTIVITY_TAGS})")
        return cleaned


class ActivityOut(BaseModel):
    """Read model for a single Misk Core activity.

    Constructed explicitly from a sqlite3.Row in the route layer (matching
    the existing pattern in routes/student.py). `tags` is decoded from the
    JSON-encoded TEXT column before construction; consumers see a real list.
    """
    id: int
    student_id: int
    category_id: int
    category_name: str
    title: str
    description: Optional[str] = None
    activity_date: Optional[date] = None
    stored_filename: Optional[str] = None
    original_filename: Optional[str] = None
    file_extension: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime


class StudentProfileOut(BaseModel):
    """Read model for GET /teacher/student-profile/{student_id}.

    MVP shape: identity + activities. Chunk 7 (teacher.py) will determine
    whether to extend with submission/quadrant breakdowns; any extension
    must be additive (new optional fields only) so existing consumers stay
    compatible. Distinct from StudentReport in models.py, which backs the
    older /teacher/report/{student_id} endpoint.
    """
    student_id: int
    student_name: str
    email: str
    activities: List[ActivityOut] = Field(default_factory=list)