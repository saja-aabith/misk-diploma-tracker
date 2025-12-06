from fastapi import APIRouter, HTTPException
from database import get_db
from models import UserRegister, UserLogin, UserResponse, TokenResponse
from utils import create_access_token, verify_password, hash_password, get_current_user
from fastapi import Depends

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    """Register a new user"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (user.username, user.email))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Hash password and create user
    password_hash = hash_password(user.password)
    cursor.execute(
        """INSERT INTO users (username, email, password_hash, role, full_name) 
           VALUES (?, ?, ?, ?, ?)""",
        (user.username, user.email, password_hash, user.role, user.full_name)
    )
    conn.commit()
    user_id = cursor.lastrowid
    
    # Create token
    token = create_access_token({"user_id": user_id, "username": user.username, "role": user.role})
    
    user_response = UserResponse(
        id=user_id,
        username=user.username,
        email=user.email,
        role=user.role,
        full_name=user.full_name
    )
    
    conn.close()
    return TokenResponse(access_token=token, user=user_response)

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Find user
    cursor.execute("SELECT * FROM users WHERE username = ?", (credentials.username,))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create token
    token = create_access_token({
        "user_id": user['id'],
        "username": user['username'],
        "role": user['role']
    })
    
    user_response = UserResponse(
        id=user['id'],
        username=user['username'],
        email=user['email'],
        role=user['role'],
        full_name=user['full_name']
    )
    
    conn.close()
    return TokenResponse(access_token=token, user=user_response)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (current_user['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    conn.close()
    return UserResponse(
        id=user['id'],
        username=user['username'],
        email=user['email'],
        role=user['role'],
        full_name=user['full_name']
    )