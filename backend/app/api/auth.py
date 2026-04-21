"""Authentication API endpoints — register, login, current user."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.schemas import UserCreate, UserOut, TokenResponse
from backend.app.utils.auth_utils import hash_password, verify_password, create_access_token
from backend.app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    
    """
    Create a new user account with role-based access control.
    
    Args:
        payload (UserCreate): The user registration details (email, password, role).
        db (AsyncSession): The asynchronous database session dependency.
        
    Raises:
        HTTPException (400): If the email is already registered in the system.
        HTTPException (400): If an invalid role is provided.
        
    Returns:
        UserOut: The newly created user record (excluding sensitive data).
    """
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if payload.role not in ("admin", "researcher", "reviewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Authenticate user credentials and return a JWT access token.
    
    Args:
        form (OAuth2PasswordRequestForm): Standard OAuth2 form containing username (email) and password.
        db (AsyncSession): The asynchronous database session dependency.
        
    Raises:
        HTTPException (401): If the email/password combination is invalid.
        HTTPException (403): If the user account has been disabled by an admin.
        
    Returns:
        TokenResponse: A dictionary containing the JWT access token and user role.
    """
    user = (await db.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", role=user.role)


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    
    Args:
        user (User): The user object injected by the get_current_user dependency 
                     after validating the incoming JWT token.
                     
    Returns:
        UserOut: The serialized user profile data.
    """
    return UserOut.model_validate(user)
