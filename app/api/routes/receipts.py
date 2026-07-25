import os
from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import ValidationError

from app.services.receipts import (
    generate_receipts,
    DirectReceiptRequest,
    process_direct_receipt,
)
from app.services.auth import require_user

router = APIRouter(dependencies=[Depends(require_user)])

DEFAULT_BODY_TEXT_PT = os.getenv(
    "DEFAULT_BODY_TEXT_PT",
    "Recebi o recibo referente ao pagamento do mês de {ref_month}."
)
DEFAULT_BODY_TEXT_EN = os.getenv(
    "DEFAULT_BODY_TEXT_EN",
    "I received the value referred to the {ref_month}."
)


@router.post("")
async def trigger_receipt_generation(
    source_text: str = Body(..., embed=True),
    pt_br: bool = Body(True, embed=True),
) -> dict[str, object]:
    try:
        result = await generate_receipts(source_text, pt_br)
        return result.model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.post("/direct")
async def trigger_direct_receipt(payload: DirectReceiptRequest) -> dict[str, object]:
    try:
        if payload.body_text is None:
            if payload.pt_br:
                payload.body_text = DEFAULT_BODY_TEXT_PT
            else:
                payload.body_text = DEFAULT_BODY_TEXT_EN
        result = await process_direct_receipt(payload)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
