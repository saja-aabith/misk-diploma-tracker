# DEPRECATED LOCATION — re-exports from schemas.py for backwards compatibility.
#
# As of Chunk 19, all Pydantic models live in schemas.py. This module exists
# as a thin re-export shim so existing `from models import X` imports across
# the route layer keep working without a coordinated rewrite of every file.
#
# New code should import from `schemas` directly. Do NOT add new models here
# — add them to schemas.py.
#
# This file will be removed in a future chunk once every `from models import`
# site has been migrated. Until then, the contract of this module is
# strictly "preserve the names that used to be defined here, nothing more."
# In particular, this shim deliberately does NOT re-export APIResponse,
# ErrorResponse, or any of the Misk Core schemas — those have always lived
# in schemas.py and consumers already import them from there.

from schemas import (
    # Authentication
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    # Student dashboard
    ObjectiveProgress,
    QuadrantSummary,
    StudentDashboard,
    # Submission / review (Type 1)
    SubmissionReview,
    Submission,
    # Teacher review / report
    ReviewSubmission,
    SubmissionDetail,
    ObjectiveReport,
    QuadrantReport,
    SubmissionSummary,
    StudentReport,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "ObjectiveProgress",
    "QuadrantSummary",
    "StudentDashboard",
    "SubmissionReview",
    "Submission",
    "ReviewSubmission",
    "SubmissionDetail",
    "ObjectiveReport",
    "QuadrantReport",
    "SubmissionSummary",
    "StudentReport",
]