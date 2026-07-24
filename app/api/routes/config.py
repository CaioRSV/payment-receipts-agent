from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.services.auth import require_user, require_admin
from app.services.database import get_db_config, update_db_config

router = APIRouter()


class ConfigSchema(BaseModel):
    signer_name: str
    signer_address: str
    location: str


@router.get("", response_model=ConfigSchema)
async def get_configuration(token_data: dict = Depends(require_user)) -> dict[str, str]:
    """Retrieves the current default config settings from the database (User/Admin access)."""
    return get_db_config()


@router.put("", response_model=ConfigSchema)
async def update_configuration(payload: ConfigSchema, token_data: dict = Depends(require_admin)) -> dict[str, str]:
    """Updates the default config settings in the database (Admin only access)."""
    update_db_config(
        signer_name=payload.signer_name,
        signer_address=payload.signer_address,
        location=payload.location
    )
    return get_db_config()
