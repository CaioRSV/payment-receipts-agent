from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from app.services.receipts import (
    generate_receipts,
    DirectReceiptRequest,
    process_direct_receipt,
)

router = APIRouter()


@router.post("")
async def trigger_receipt_generation(
    source_text: str = Body(..., embed=True),
    pt_br: bool = True
) -> dict[str, object]:
    try:
        result = await generate_receipts(source_text, pt_br)
        return result.model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.post("/direct")
async def trigger_direct_receipt(payload: DirectReceiptRequest) -> dict[str, object]:
    try:
        result = await process_direct_receipt(payload)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
