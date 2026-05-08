# STUDENT DATA: Files stored in school-controlled storage per policy.
# UPLOAD_DIR must point to Google Drive for Desktop mount or local school disk.
# Do not change storage backend without explicit school administration approval.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from database import init_database
from routes import auth, student, teacher, health, files
from utils import UPLOAD_DIR

# Initialize FastAPI app
app = FastAPI(title="MISK Diploma Tracker API", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the upload directory exists. UPLOAD_DIR comes from the env
# (default ./uploads); routes/student.py and routes/files.py read from
# the same path so the bootstrap, the writers, and the reader stay aligned.
os.makedirs(UPLOAD_DIR, exist_ok=True)

# NOTE: the previous public /uploads StaticFiles mount has been removed.
# All uploaded files are now served via the authenticated route at
# /api/v1/files/{stored_filename} (routes/files.py), which enforces
# ownership rules — students may read only their own files; teachers
# may read any file. Removing the public mount closes the spec's
# critical-priority data-exposure issue.

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(student.router, prefix="/api/v1/student", tags=["Student"])
app.include_router(teacher.router, prefix="/api/v1/teacher", tags=["Teacher"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("🚀 Starting MISK Diploma Tracker API...")
    init_database()
    print("✅ Database initialized with seed data")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)