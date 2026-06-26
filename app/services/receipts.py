from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator


class ReceiptExtraction(BaseModel):
    payment_date: date
    referred_month: str = Field(description="Month and year in MONTH.YYYY format")

    @field_validator("referred_month")
    @classmethod
    def validate_referred_month_format(cls, value: str) -> str:
        if re.fullmatch(
            r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\.\d{4}",
            value,
        ) is None:
            raise ValueError("referred_month must be in MONTH.YYYY format")
        return value

    @model_validator(mode="after")
    def ensure_month_matches_payment_date(self) -> "ReceiptExtraction":
        if self.payment_date > date.today():
            raise ValueError("payment_date cannot be in the future")
        return self


class ReceiptGenerationResult(BaseModel):
    status: str = "ok"
    extracted: ReceiptExtraction


class MockPydanticAIReceiptExtractor:
    async def run(self, source_text: str) -> ReceiptExtraction:
        mocked_response = self._mock_ai_response(source_text)
        return ReceiptExtraction.model_validate(mocked_response)

    def _mock_ai_response(self, source_text: str) -> dict[str, object]:
        payment_date = self._extract_payment_date(source_text)
        referred_month = self._extract_referred_month(source_text, payment_date)

        return {
            "payment_date": payment_date.isoformat(),
            "referred_month": referred_month,
        }

    def _extract_payment_date(self, source_text: str) -> date:
        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", source_text)
        if iso_match is not None:
            return date.fromisoformat(iso_match.group(1))

        slash_match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", source_text)
        if slash_match is not None:
            day, month, year = map(int, slash_match.groups())
            return date(year, month, day)

        return date.today()

    def _extract_referred_month(self, source_text: str, payment_date: date) -> str:
        month_number_match = re.search(r"\bmonth\s+(\d{1,2})\b", source_text, re.IGNORECASE)
        if month_number_match is not None:
            month_number = int(month_number_match.group(1))
        else:
            month_name_match = re.search(
                r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
                source_text,
                re.IGNORECASE,
            )
            if month_name_match is not None:
                month_name = month_name_match.group(1).lower()
                month_number = {
                    "january": 1,
                    "february": 2,
                    "march": 3,
                    "april": 4,
                    "may": 5,
                    "june": 6,
                    "july": 7,
                    "august": 8,
                    "september": 9,
                    "october": 10,
                    "november": 11,
                    "december": 12,
                }[month_name]
            else:
                month_number = payment_date.month

        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", source_text)
        year_number = int(year_match.group(1)) if year_match is not None else date.today().year
        month_name = {
            1: "JANUARY",
            2: "FEBRUARY",
            3: "MARCH",
            4: "APRIL",
            5: "MAY",
            6: "JUNE",
            7: "JULY",
            8: "AUGUST",
            9: "SEPTEMBER",
            10: "OCTOBER",
            11: "NOVEMBER",
            12: "DECEMBER",
        }[month_number]

        return f"{month_name}.{year_number}"


async def generate_receipts(source_text: str) -> ReceiptGenerationResult:
    extractor = MockPydanticAIReceiptExtractor()
    extracted = await extractor.run(source_text)
    return ReceiptGenerationResult(extracted=extracted)


__all__ = [
    "ReceiptGenerationResult",
    "ReceiptExtraction",
    "generate_receipts",
]
