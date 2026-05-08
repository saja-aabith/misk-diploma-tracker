# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

import os
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from database import get_db
from utils import (
    EXTENSION_MIME_TYPES,
    UPLOAD_DIR,
    get_current_user,
)

router = APIRouter()


# ============================================================
# Private helpers
# ============================================================

def _is_unsafe_stored_filename(name: str) -> bool:
    """Defence-in-depth filename guard. Stored filenames are UUID-based by
    construction (utils.validate_upload), but we still validate path-param
    input here so a malformed lookup never reaches the filesystem."""
    if not name:
        return True
    if "\x00" in name:
        return True
    if ".." in name:
        return True
    if "/" in name or "\\" in name:
        return True
    return False


def _lookup_file_owner(cursor, stored_filename: str) -> Optional[int]:
    """Return the student_id that owns this stored_filename, or None.

    Files can be referenced by either evidence_submissions (Type 1: structured
    teacher-reviewed evidence) or student_activities (Type 2: free-form Misk
    Core activities). Both pipelines populate stored_filename via the same
    validate_upload helper, so a single lookup covers both.
    """
    cursor.execute(
        "SELECT student_id FROM evidence_submissions WHERE stored_filename = ? LIMIT 1",
        (stored_filename,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row['student_id']

    cursor.execute(
        "SELECT student_id FROM student_activities WHERE stored_filename = ? LIMIT 1",
        (stored_filename,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row['student_id']

    return None


def _lookup_file_metadata(cursor, stored_filename: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (original_filename, mime_type) for a stored_filename, or
    (None, None) if not found in either table."""
    cursor.execute(
        "SELECT original_filename, mime_type FROM evidence_submissions "
        "WHERE stored_filename = ? LIMIT 1",
        (stored_filename,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row['original_filename'], row['mime_type']

    cursor.execute(
        "SELECT original_filename, mime_type FROM student_activities "
        "WHERE stored_filename = ? LIMIT 1",
        (stored_filename,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row['original_filename'], row['mime_type']

    return None, None


# ============================================================
# Authenticated file route
# ============================================================

@router.get("/{stored_filename}")
async def get_file(
    stored_filename: str,
    download: int = Query(0, ge=0, le=1),
    current_user: dict = Depends(get_current_user),
):
    """Serve an uploaded file with ownership enforcement.

    Authorization:
      - Teacher: may read any file referenced by an evidence_submissions or
        student_activities row.
      - Student: may read only files where they are the owning student_id.
      - Anyone else (no token): 401 (handled by HTTPBearer before this runs).

    On unauthorized access we return 404 — never 403 — so the route does not
    disclose whether a given filename exists. The student probing for another
    student's file gets the same response as a student probing for nothing.

    Query:
      - download=1 → Content-Disposition: attachment (force download)
      - default    → Content-Disposition: inline    (render in browser)
    """
    # 1. Filename safety guard (defense in depth — UUIDs only by construction).
    if _is_unsafe_stored_filename(stored_filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    role = current_user.get("role")
    user_id = current_user.get("user_id")
    if role not in ("student", "teacher") or user_id is None:
        # Token decoded but the payload shape is unexpected. Fail closed.
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # 2. DB lookup: who owns this file?
    conn = get_db()
    cursor = conn.cursor()
    owner_id = _lookup_file_owner(cursor, stored_filename)

    # 3. Authorization (404 on miss/forbidden — no existence disclosure).
    if owner_id is None:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    if role == "student" and owner_id != user_id:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    # 4. Pull display metadata for the response headers.
    original_filename, mime_type = _lookup_file_metadata(cursor, stored_filename)
    conn.close()

    # 5. Resolve disk path with realpath containment check. Even though
    #    stored_filename is a UUID, we treat the filesystem step as if input
    #    were untrusted — cheap and prevents any future regression.
    upload_root = os.path.realpath(UPLOAD_DIR)
    candidate = os.path.realpath(os.path.join(upload_root, stored_filename))
    if not candidate.startswith(upload_root + os.sep) and candidate != upload_root:
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(candidate):
        # DB row exists but bytes are gone — surface as 404 rather than 500.
        raise HTTPException(status_code=404, detail="File not found")

    # 6. Determine MIME type. Prefer DB value; fall back to extension map;
    #    last-resort generic binary so we never 500 on legacy rows.
    if not mime_type:
        ext = os.path.splitext(stored_filename)[1].lower()
        mime_type = EXTENSION_MIME_TYPES.get(ext, "application/octet-stream")

    # 7. Disposition. inline by default; attachment if ?download=1.
    display_name = original_filename or stored_filename
    # Quote the filename to handle spaces/non-ASCII safely in the header.
    safe_display_name = display_name.replace('"', '')
    disposition = "attachment" if download == 1 else "inline"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{safe_display_name}"',
    }

    return FileResponse(
        path=candidate,
        media_type=mime_type,
        headers=headers,
    ) 