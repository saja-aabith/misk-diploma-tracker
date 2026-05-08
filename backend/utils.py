# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ============================================================
# Configuration
# ============================================================
# SECRET_KEY is read from the environment; on miss we fall back to the
# legacy hardcoded value with a loud warning so local dev continues to
# work but the operator is told to set it. Tokens issued before this
# change remain valid as long as the same key is still in use.
_FALLBACK_SECRET_KEY = "misk-schools-diploma-tracker-secret-key-2025"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print(
        "⚠️  SECRET_KEY not set in environment. Using fallback development "
        "key. Set SECRET_KEY in .env or your shell before deploying.",
        file=sys.stderr,
    )
    SECRET_KEY = _FALLBACK_SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Storage / upload configuration. Defaults match backend/.env.
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ============================================================
# File validation constants
# ============================================================
# Spec-locked extension allow-list. Note: this intentionally does NOT
# include .pptx. The legacy /student/upload route still has its own
# inline list that accepts .pptx; that list is collapsed into this one
# in Chunk 6 when the route switches to validate_upload().
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".mp4"}

EXTENSION_MIME_TYPES = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".mp4":  "video/mp4",
}

# Magic-byte signatures we can verify cheaply. .docx (ZIP container)
# and .mp4 (variable signature after size prefix) are extension-only.
MAGIC_BYTES = {
    ".pdf":  b"\x25\x50\x44\x46",          # %PDF
    ".jpg":  b"\xFF\xD8\xFF",
    ".jpeg": b"\xFF\xD8\xFF",
    ".png":  b"\x89\x50\x4E\x47",
}

security = HTTPBearer()


# ============================================================
# Upload validation result
# ============================================================
@dataclass
class ValidatedUpload:
    """Result of validate_upload(). The route uses these fields directly
    when writing the file to disk and persisting the metadata row."""
    stored_filename: str       # uuid-based, safe to write to disk
    original_filename: str     # raw filename from the client (sanitised)
    file_extension: str        # ".pdf", ".jpg", etc. — lowercase, dot-prefixed
    file_size_bytes: int
    mime_type: str
    content_bytes: bytes       # the file body — caller writes to disk


# ============================================================
# Existing JWT / password helpers — preserved verbatim
# ============================================================
def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """Get current user from token"""
    token = credentials.credentials
    payload = verify_token(token)
    return payload

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ============================================================
# Role-specific dependencies
# ============================================================
# Both wrap the existing get_current_user; the role claim must be present
# in the JWT payload (set by routes/auth.py at login). Failing closed if
# the claim is missing is intentional — a loud 403 surfaces the problem
# faster than a silent permissive default.

def get_current_student(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the authenticated user to have role='student'."""
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ROLE_FORBIDDEN",
                "message": "Student role required.",
            },
        )
    return current_user


def get_current_teacher(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the authenticated user to have role='teacher'."""
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ROLE_FORBIDDEN",
                "message": "Teacher role required.",
            },
        )
    return current_user


# ============================================================
# Upload validation
# ============================================================
def _is_unsafe_filename(name: str) -> bool:
    """Reject filenames containing path separators, traversal markers, or
    NUL bytes. The stored filename is always a fresh UUID so this guard
    primarily protects what we log and what we display back to the user
    via original_filename."""
    if not name:
        return True
    if "\x00" in name:
        return True
    if ".." in name:
        return True
    if "/" in name or "\\" in name:
        return True
    return False


async def validate_upload(file: UploadFile) -> ValidatedUpload:
    """Validate an UploadFile against the project's file-handling policy.

    Checks (in order, fail-fast):
      1. original filename is present and safe
      2. extension is in ALLOWED_EXTENSIONS
      3. file body is non-empty and within MAX_FILE_SIZE_BYTES
      4. magic-byte signature (for formats with a known cheap signature)

    On success returns a ValidatedUpload carrying the bytes the route
    should write to disk and the metadata it should persist. On failure
    raises HTTPException(400) with a stable error code in `detail`.

    Raises:
      HTTPException(400, detail={"code": ..., "message": ...})

    NOTE: The upload bytes are returned in-memory. The MVP cap of
    MAX_FILE_SIZE_MB makes that acceptable; if the cap grows we should
    move to streaming-write here.
    """
    # 1. Filename safety
    original = file.filename or ""
    if _is_unsafe_filename(original):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_INVALID_FILENAME",
                "message": "Filename contains invalid characters.",
            },
        )

    # 2. Extension allow-list
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_INVALID_EXTENSION",
                "message": (
                    f"File extension '{ext or '(none)'}' not allowed. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
                ),
            },
        )

    # 3. Read body and check size
    content = await file.read()
    size = len(content)
    if size == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_EMPTY",
                "message": "Uploaded file is empty.",
            },
        )
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds {MAX_FILE_SIZE_MB}MB limit.",
            },
        )

    # 4. Magic bytes (only for formats with a cheap signature)
    expected_sig = MAGIC_BYTES.get(ext)
    if expected_sig is not None and not content.startswith(expected_sig):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "FILE_CONTENT_MISMATCH",
                "message": f"File content does not match {ext} format.",
            },
        )

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    mime_type = EXTENSION_MIME_TYPES[ext]

    return ValidatedUpload(
        stored_filename=stored_filename,
        original_filename=original,
        file_extension=ext,
        file_size_bytes=size,
        mime_type=mime_type,
        content_bytes=content,
    )