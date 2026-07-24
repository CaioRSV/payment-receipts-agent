from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import ValidationError

from app.services.receipts import (
    generate_receipts,
    DirectReceiptRequest,
    process_direct_receipt,
)
from app.services.auth import require_user

router = APIRouter(dependencies=[Depends(require_user)])


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
        if payload.body_text is None:
            if payload.pt_br:
                payload.body_text = (
                    "RECEBI, DA SRA. WELYTÂNIA MOURA BEZERRA DE OLIVEIRA, A QUANTIA DE R$ 800, 00 (OITOCENTOS REAIS), "
                    "REFERENTE AO PAGAMENTO DO ALUGUEL DO MÊS DE {ref_month} DA CASA SITUADA NA RUA AGAMENOM MAGALHÃES, "
                    "227, LIVRAMENTO, VITÓRIA-PE."
                )
            else:
                payload.body_text = "I received the value referred to the {ref_month}."
        result = await process_direct_receipt(payload)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
