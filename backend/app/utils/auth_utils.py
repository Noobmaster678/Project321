"""JWT token creation/verification and password hashing utilities."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# ============================================================
# CONFIGURATION
# ============================================================

SECRET_KEY = "wildlife-platform-secret-change-in-production"
"""Secret key for JWT signing. MUST be changed in production environment."""

ALGORITHM = "HS256"
"""Algorithm used for JWT token encoding/decoding."""

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
"""Default JWT token expiration time in minutes (24 hours)."""


# ============================================================
# PASSWORD HASHING
# ============================================================


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.
    
    Args:
        plain_password: The plain-text password to hash
        
    Returns:
        str: The hashed password (bcrypt format)
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hashed password.
    
    Args:
        plain_password: The plain-text password to verify
        hashed_password: The stored hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================
# JWT TOKEN MANAGEMENT
# ============================================================


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token.
    
    Args:
        data: Dictionary containing token claims (e.g., sub, role)
        expires_delta: Optional custom expiration time. If None, uses ACCESS_TOKEN_EXPIRE_MINUTES
        
    Returns:
        str: The signed JWT token
    """
    # Copy claims to avoid modifying original dict
    token_data = data.copy()
    
    # Calculate expiration time
    if expires_delta:
        expire_time = datetime.now(timezone.utc) + expires_delta
    else:
        expire_time = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Add expiration claim
    token_data.update({"exp": expire_time})
    
    # Encode and sign token
    encoded_token = jwt.encode(
        token_data,
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    return encoded_token


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        Optional[dict]: Dictionary containing token claims if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        # Token is invalid, expired, or signature verification failed
        return None
