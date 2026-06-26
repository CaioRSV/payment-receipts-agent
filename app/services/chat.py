from __future__ import annotations

import logging
import os
import re
import unicodedata
from datetime import date
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.services.receipts import ReceiptGenerationResult, generate_receipts

ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_FILE = ROOT_DIR / "knowledge.md"
logger = logging.getLogger(__name__)

GENERATION_TERMS = {"gere", "gerar", "generate", "crie", "criar", "emit", "emitir"}
RECEIPT_TERMS = {"recibo", "receipt"}
GENERIC_MONTH_TERMS = {"mes", "month"}
MONTH_ALIASES = {
    "JANUARY": {"january", "janeiro", "jan", "januari", "janury"},
    "FEBRUARY": {"february", "fevereiro", "fev", "feb", "febraury", "fevereiro"},
    "MARCH": {"march", "marco", "mar", "mrach"},
    "APRIL": {"april", "abril", "apr", "aprl"},
    "MAY": {"may", "maio"},
    "JUNE": {"june", "junho", "jun"},
    "JULY": {"july", "julho", "jul"},
    "AUGUST": {"august", "agosto", "aug", "agost"},
    "SEPTEMBER": {"september", "setembro", "sep", "sept", "setenbro"},
    "OCTOBER": {"october", "outubro", "oct", "out", "octuber"},
    "NOVEMBER": {"november", "novembro", "nov", "novenber"},
    "DECEMBER": {"december", "dezembro", "dec", "dez", "decenber"},
}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    mode: str
    reply: str
    receipt: ReceiptGenerationResult | None = None


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def _tokens(normalized_text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalized_text)


def _contains_term(tokens: list[str], terms: set[str], cutoff: float = 0.84) -> bool:
    for token in tokens:
        if token in terms:
            return True
        if get_close_matches(token, list(terms), n=1, cutoff=cutoff):
            return True
    return False


def _resolve_month(tokens: list[str]) -> str | None:
    for month_name, aliases in MONTH_ALIASES.items():
        if _contains_term(tokens, aliases, cutoff=0.82):
            return month_name
    return None


def _detect_receipt_intent(message: str) -> tuple[bool, str, str]:
    normalized = _normalize_text(message)
    tokens = _tokens(normalized)

    has_generation = _contains_term(tokens, GENERATION_TERMS)
    has_receipt_noun = _contains_term(tokens, RECEIPT_TERMS)
    resolved_month = _resolve_month(tokens)
    has_generic_month = _contains_term(tokens, GENERIC_MONTH_TERMS)

    should_trigger = (has_generation and has_receipt_noun) or (has_generation and resolved_month is not None)
    if not should_trigger:
        return False, "Nenhuma combinacao de intencao de recibo encontrada", message

    if resolved_month is not None:
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", normalized)
        year_value = year_match.group(1) if year_match else str(date.today().year)
        enriched_message = f"{message}\n\nMes de referencia interpretado: {resolved_month}.{year_value}."
        return True, f"Disparo por geracao + mes ({resolved_month})", enriched_message

    if has_generation and has_receipt_noun and has_generic_month:
        current_month = date.today().strftime("%B").upper()
        current_year = str(date.today().year)
        enriched_message = f"{message}\n\nMes de referencia interpretado: {current_month}.{current_year}."
        return True, "Disparo por geracao + recibo + mes generico; assumindo mes atual", enriched_message

    return True, "Disparo por geracao + recibo", message


def _load_knowledge() -> str:
    return KNOWLEDGE_FILE.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _build_chat_agent() -> Agent:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY nao foi configurada")

    model = OpenAIChatModel(
        "openai/gpt-4o-mini",
        provider=OpenAIProvider(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
        ),
    )

    return Agent(
        model,
        result_type=str,
        system_prompt=(
            "Voce é um assistente util do agente de recibos de pagamento. "
            "Responda sempre em portugues brasileiro. "
            "Use a base de conhecimento abaixo como contexto editavel para o comportamento de fallback:\n\n"
            f"{_load_knowledge()}"
        ),
    )


async def chat(message: str) -> ChatResponse:
    should_trigger, trigger_reason, enriched_message = _detect_receipt_intent(message)
    logger.debug("Resultado da deteccao de intencao: should_trigger=%s reason=%s", should_trigger, trigger_reason)

    if should_trigger:
        try:
            receipt = await generate_receipts(enriched_message)
        except Exception as exc:
            logger.exception("Falha no fluxo de recibo apos trigger_reason=%s", trigger_reason)
            return ChatResponse(
                mode="receipt_error",
                reply=(
                    "Tentei gerar o recibo, mas ocorreu um erro. "
                    f"Motivo: {exc}"
                ),
                receipt=None,
            )

        logger.info("Fluxo de recibo disparado: %s", trigger_reason)
        return ChatResponse(
            mode="receipt",
            reply="Fluxo de geracao de recibo iniciado com sucesso.",
            receipt=receipt,
        )

    logger.info("Usando resposta de fallback do chatbot")
    result = await _build_chat_agent().run(message)
    return ChatResponse(mode="chat", reply=result.data)