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

# ============================================================
# REGISTRATION ENDPOINT
# ============================================================


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account.
    
    Args:
        payload: User registration data (email, password, full_name, role)
        db: Database session
        
    Returns:
        UserOut: The created user profile
        
    Raises:
        HTTPException: 400 if email already exists or invalid role
    """
    # Check if email already registered
    existing_user = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate role
    valid_roles = ("admin", "researcher", "reviewer")
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )

    # Create new user with hashed password
    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    
    return UserOut.model_validate(new_user)


# ============================================================
# LOGIN ENDPOINT
# ============================================================


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT access token.
    
    Args:
        form_data: OAuth2 form with username (email) and password
        db: Database session
        
    Returns:
        TokenResponse: JWT access token and user role
        
    Raises:
        HTTPException: 401 if credentials invalid, 403 if account disabled
    """
    # Look up user by email (username field contains email)
    user = (
        await db.execute(select(User).where(User.email == form_data.username))
    ).scalar_one_or_none()
    
    # Verify credentials
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    # Generate JWT token
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role
    )


# ============================================================
# CURRENT USER ENDPOINT
# ============================================================


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    """Get the currently authenticated user profile.
    
    Args:
        user: Current authenticated user (injected via dependency)
        
    Returns:
        UserOut: The authenticated user's profile
    """
    return UserOut.model_validate(user)
