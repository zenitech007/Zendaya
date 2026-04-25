"""
Advanced Authentication and Security Utilities
- Integrates with both local DB and external auth providers like Supabase.
- Clear separation of Pydantic schemas and database models.
- Robust JWT creation and validation flow.
- Modern password hashing with passlib.
- FastAPI dependency for getting the current authenticated user.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr

# Assuming UserCRUD and database connections are correctly set up
# These imports are structured to work with your provided main.py
from zendaya_backend.database.crud import UserCRUD
from zendaya_backend.database.connection import get_db
from zendaya_backend.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ------------------------------------------------------
# Security Schemes and Configuration
# ------------------------------------------------------

# Use OAuth2PasswordBearer for standard token handling in Swagger/OpenAPI UI
# The tokenUrl should point to your actual login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Configure password hashing
# Using bcrypt, which is a strong and widely-used hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------------------------------------------
# Pydantic Models for Data Validation and API Schemas
# ------------------------------------------------------

class Token(BaseModel):
    """Pydantic model for the access token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Pydantic model for the data encoded within the JWT."""
    sub: str  # 'sub' (subject) is the standard claim for the user identifier


class User(BaseModel):
    """
    Base Pydantic model for a User.
    This is the primary model used for API responses and dependency injection.
    It intentionally omits sensitive data like password hashes.
    """
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    disabled: bool = False

    class Config:
        # Allows creating this Pydantic model from a SQLAlchemy model instance
        from_attributes = True


# ------------------------------------------------------
# Core Security Functions
# ------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its hashed version."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.

    Args:
        data: The payload to encode (typically includes user identifier).
        expires_delta: Optional expiration time. Defaults to configured value.

    Returns:
        The encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to decode a JWT and fetch the current authenticated user.

    This function is the primary gatekeeper for protected endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode the JWT to get the payload
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        # The user identifier should be stored in the 'sub' claim
        username = payload.get("sub")
        if not isinstance(username, str):
            logger.warning("JWT token is missing the 'sub' (subject) claim.")
            raise credentials_exception

        # Create a TokenData object for validation (optional but good practice)
        token_data = TokenData(sub=username)

    except JWTError as e:
        logger.error(f"JWT decoding error: {e}")
        raise credentials_exception from e

    # Fetch the user from the database using the username from the token
    user = await UserCRUD.get_user_by_username(db, username=token_data.sub)
    if user is None:
        logger.warning(f"User '{token_data.sub}' from token not found in the database.")
        raise credentials_exception
    
    # Return the Pydantic User model, which is safe to use in the application
    return User.from_orm(user)


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency that builds on `get_current_user` to ensure the user is not disabled.
    """
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
