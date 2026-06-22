import random

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from utils import get_current_admin, hash_password
from schemas import (
    AdminCreateUser,
    AdminResetPassword,
    AdminUserOut,
    AdminUserList,
)

router = APIRouter()

# Login usernames are school-email-shaped strings (not real mailboxes).
USERNAME_DOMAIN = "miskschools.edu.sa"
_MAX_SUFFIX_TRIES = 50


def _generate_username(cursor, base: str) -> str:
    """Allocate a unique '{base}{4-digit}@domain' username.

    The base is already validated (ASCII letters, lower-cased) by
    AdminCreateUser. We retry suffixes until one is free against both the
    username and email columns (they hold the same value), bounded so a
    pathological collision streak fails loudly rather than looping forever.
    """
    for _ in range(_MAX_SUFFIX_TRIES):
        suffix = random.randint(1000, 9999)
        candidate = f"{base}{suffix}@{USERNAME_DOMAIN}"
        cursor.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            (candidate, candidate),
        )
        if cursor.fetchone() is None:
            return candidate
    raise HTTPException(
        status_code=409,
        detail={
            "code": "USERNAME_ALLOCATION_FAILED",
            "message": "Could not allocate a unique username; please try again.",
        },
    )


@router.post("/create-user", response_model=AdminUserOut)
async def create_user(
    payload: AdminCreateUser,
    current_admin: dict = Depends(get_current_admin),
):
    """Create a student or teacher account (admin only).

    Username is generated server-side from the supplied first-name base plus a
    unique 4-digit suffix. For students, current_grade is stored in
    users.student_year and entry_grade in users.entry_grade; teachers carry
    neither (enforced by AdminCreateUser).
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        username = _generate_username(cursor, payload.username_base)
        cursor.execute(
            "INSERT INTO users "
            "(username, email, password_hash, role, full_name, student_year, entry_grade) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                username,
                username,
                hash_password(payload.password),
                payload.role,
                payload.full_name,
                payload.current_grade,
                payload.entry_grade,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid

        # Initialise progress rows for a new student against every active
        # objective (not_started / 0), so the dashboard is immediately
        # consistent rather than waiting for the next startup's
        # seed_objective_restructure backfill. Mirrors that backfill's shape.
        # INSERT OR IGNORE is defensive (a fresh student has no rows yet).
        if payload.role == "student":
            cursor.execute("SELECT id FROM objectives WHERE is_active = 1")
            for obj in cursor.fetchall():
                cursor.execute(
                    "INSERT OR IGNORE INTO student_objective_progress "
                    "(student_id, objective_id, current_points, "
                    "completion_percentage, status) "
                    "VALUES (?, ?, 0, 0, 'not_started')",
                    (new_id, obj["id"]),
                )
            conn.commit()

        return AdminUserOut(
            id=new_id,
            username=username,
            full_name=payload.full_name,
            role=payload.role,
            current_grade=payload.current_grade,
            entry_grade=payload.entry_grade,
        )
    finally:
        conn.close()


@router.post("/reset-password")
async def reset_password(
    payload: AdminResetPassword,
    current_admin: dict = Depends(get_current_admin),
):
    """Reset a student's or teacher's password (admin only).

    Admin accounts cannot be reset through this route (403) to avoid lockout
    or escalation games; the bootstrap is the only path that sets an admin
    password.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, role FROM users WHERE id = ?", (payload.user_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "message": "User not found."},
            )
        if row["role"] == "admin":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "CANNOT_RESET_ADMIN",
                    "message": "Admin passwords cannot be reset here.",
                },
            )
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.new_password), payload.user_id),
        )
        conn.commit()
        return {"success": True, "user_id": payload.user_id}
    finally:
        conn.close()


@router.get("/users", response_model=AdminUserList)
async def list_users(current_admin: dict = Depends(get_current_admin)):
    """List all student and teacher accounts (admin only).

    Admin rows are intentionally excluded. No password material is returned.
    current_grade maps from users.student_year.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username, full_name, role, student_year, entry_grade "
            "FROM users WHERE role IN ('student', 'teacher') ORDER BY role, id"
        )
        users = [
            AdminUserOut(
                id=r["id"],
                username=r["username"],
                full_name=r["full_name"],
                role=r["role"],
                current_grade=r["student_year"],
                entry_grade=r["entry_grade"],
            )
            for r in cursor.fetchall()
        ]
        return AdminUserList(users=users)
    finally:
        conn.close()
