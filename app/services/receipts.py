from __future__ import annotations

import os
from functools import lru_cache
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


MONTH_NAMES = {
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
}


class ReceiptExtraction(BaseModel):
    payment_date: date
    referred_month: str = Field(description="Mes e ano no formato MONTH.YYYY")

    @field_validator("referred_month")
    @classmethod
    def validate_referred_month_format(cls, value: str) -> str:
        month_name, _, year_text = value.partition(".")
        if month_name not in MONTH_NAMES or len(year_text) != 4 or not year_text.isdigit():
            raise ValueError("referred_month deve estar no formato MONTH.YYYY")
        return value

    @model_validator(mode="after")
    def ensure_month_matches_payment_date(self) -> "ReceiptExtraction":
        if self.payment_date > date.today():
            raise ValueError("payment_date nao pode estar no futuro")
        return self


class ReceiptGenerationResult(BaseModel):
    status: str = "sucesso"
    extracted: ReceiptExtraction


@lru_cache(maxsize=1)
def _build_receipt_agent() -> Agent:
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
        result_type=ReceiptExtraction,
        system_prompt=(
            "Extraia payment_date e referred_month do texto recebido. "
            "Retorne payment_date como data ISO (YYYY-MM-DD). "
            "Retorne referred_month no formato MONTH.YYYY com nome do mes em maiusculo em ingles. "
            "Se o ano nao aparecer, use o ano atual. "
            "Responda apenas com os campos estruturados esperados."
        ),
    )
class PydanticAIReceiptExtractor:
    async def run(self, source_text: str) -> ReceiptExtraction:
        result = await _build_receipt_agent().run(source_text)
        return result.data


async def generate_receipts(source_text: str) -> ReceiptGenerationResult:
    extractor = PydanticAIReceiptExtractor()
    extracted = await extractor.run(source_text)
    return ReceiptGenerationResult(extracted=extracted)


__all__ = [
    "ReceiptGenerationResult",
    "ReceiptExtraction",
    "generate_receipts",
]
