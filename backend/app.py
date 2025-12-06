from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from database import init_database
from routes import auth, student, teacher, health

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

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)

# Mount uploads directory for static file serving
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(student.router, prefix="/api/v1/student", tags=["Student"])
app.include_router(teacher.router, prefix="/api/v1/teacher", tags=["Teacher"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("🚀 Starting MISK Diploma Tracker API...")
    init_database()
    print("✅ Database initialized with seed data")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)