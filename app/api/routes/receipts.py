from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from app.services.receipts import generate_receipts

router = APIRouter()


@router.post("")
async def trigger_receipt_generation(source_text: str = Body(..., embed=True)) -> dict[str, object]:
    try:
        result = await generate_receipts(source_text)
        return result.model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
