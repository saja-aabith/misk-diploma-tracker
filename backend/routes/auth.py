from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from models import UserLogin, UserResponse, TokenResponse
from utils import create_access_token, verify_password, get_current_user

router = APIRouter()

# NOTE: public self-registration (POST /register) has been removed. Accounts
# are created only by an administrator via routes/admin.py (create-user),
# which is guarded by get_current_admin. This closes the prior hole where any
# unauthenticated caller on the network could create an account — including a
# privileged (teacher) one — by posting a chosen role.


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