import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.auth import (
    ADMIN_PASSWORD,
    USER_PASSWORD,
    create_access_token,
)

router = APIRouter()


@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """Authenticates the user using user or admin passwords and returns a JWT token."""
    password_input = form_data.password
    
    # Securely verify against the environment variables to prevent timing attacks
    if secrets.compare_digest(password_input, ADMIN_PASSWORD):
        role = "admin"
        subject = "admin"
    elif secrets.compare_digest(password_input, USER_PASSWORD):
        role = "user"
        subject = "user"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha incorreta"
        )
        
    access_token = create_access_token(subject=subject, role=role)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
