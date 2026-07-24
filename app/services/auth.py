import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError

# Load variables
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
USER_PASSWORD = os.getenv("USER_PASSWORD", "user123")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretjwtsigningkey12345!__")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# OAuth2 scheme setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token containing subject and role claims."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=1440)  # Default 24 hours
    
    to_encode = {
        "sub": subject,
        "role": role,
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency to extract and validate the JWT token from request authorization header."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        role: str = payload.get("role")
        sub: str = payload.get("sub")
        if role is None or sub is None:
            raise credentials_exception
        return payload
    except PyJWTError:
        raise credentials_exception


class RoleChecker:
    """FastAPI dependency to enforce role-based access control (RBAC)."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, token_data: dict = Depends(verify_token)) -> dict:
        role = token_data.get("role")
        if role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied (insufficient privileges)"
            )
        return token_data


# Instantiated guards for dependency injection
require_user = RoleChecker(["user", "admin"])
require_admin = RoleChecker(["admin"])
