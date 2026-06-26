import logging

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from app.services.chat import chat

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("")
async def chat_route(message: str = Body(..., embed=True)) -> dict[str, object]:
    try:
        response = await chat(message)
        return response.model_dump()
    except ValidationError as exc:
        logger.warning("Erro de validacao no chat: %s", exc)
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except RuntimeError as exc:
        logger.error("Erro de configuracao em tempo de execucao no chat: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Erro de configuracao do servico de chat: "
                f"{exc}. Verifique OPENROUTER_API_KEY e OPENROUTER_BASE_URL no arquivo .env"
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Falha inesperada na rota de chat")
        raise HTTPException(
            status_code=500,
            detail=(
                "Erro inesperado ao processar o chat. "
                f"Motivo: {exc}"
            ),
        ) from exc