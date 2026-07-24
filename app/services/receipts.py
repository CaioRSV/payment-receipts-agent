from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from datetime import date
from difflib import get_close_matches

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pathlib import Path
from jinja2 import Template
from html2image import Html2Image
from PIL import Image
from app.services.database import get_db_config


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


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def tokens(normalized_text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalized_text)


def contains_term(token_list: list[str], terms: set[str], cutoff: float = 0.84) -> bool:
    for token in token_list:
        if token in terms:
            return True
        if get_close_matches(token, list(terms), n=1, cutoff=cutoff):
            return True
    return False


def resolve_month(token_list: list[str]) -> str | None:
    for month_name, aliases in MONTH_ALIASES.items():
        if contains_term(token_list, aliases, cutoff=0.82):
            return month_name
    return None


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
    formatted_message: str


class DirectReceiptRequest(BaseModel):
    payment_day: int | str
    payment_month: int | str
    payment_year: int | str
    referred_month: int | str
    signer_name: str | None = None
    signer_address: str | None = None
    location: str | None = None
    pt_br: bool = True
    body_text: str | None = None


class DirectReceiptResponse(BaseModel):
    status: str = "sucesso"
    payment_date: date
    referred_month: str
    formatted_message: str
    image_path: str | None = None
    trigger_info: dict[str, object]


def extract_digits(value: str | int) -> int:
    if isinstance(value, int):
        return value
    val_str = str(value).strip()
    if val_str.isdigit():
        return int(val_str)
    match = re.search(r"\d+", val_str)
    if not match:
        raise ValueError(f"Não foi possível extrair número de: '{value}'")
    return int(match.group(0))


def resolve_month_value(value: str | int, warnings: list[str]) -> str:
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        num = int(value)
        if 1 <= num <= 12:
            canonical_names = [
                "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
                "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
            ]
            return canonical_names[num - 1]
        else:
            raise ValueError(f"Mês numérico deve estar entre 1 e 12: {num}")
    
    normalized = normalize_text(str(value))
    token_list = tokens(normalized)
    
    resolved = resolve_month(token_list)
    if resolved:
        if str(value).strip() != resolved:
            warnings.append(f"Mês '{value}' corrigido/normalizado para '{resolved}'")
        return resolved
        
    raise ValueError(f"Não foi possível identificar o mês a partir de: '{value}'")


def resolve_year_value(value: str | int, warnings: list[str]) -> int:
    year = extract_digits(value)
    if 0 <= year <= 99:
        corrected_year = 2000 + year
        warnings.append(f"Ano de 2 dígitos '{year}' corrigido para '{corrected_year}'")
        return corrected_year
    if year < 1900 or year > 2100:
        raise ValueError(f"Ano inválido: {year}")
    if str(value).strip() != str(year):
        warnings.append(f"Ano '{value}' extraído como '{year}'")
    return year


def resolve_day_value(value: str | int, warnings: list[str]) -> int:
    day = extract_digits(value)
    if day < 1 or day > 31:
        raise ValueError(f"Dia inválido: {day}")
    if str(value).strip() != str(day):
        warnings.append(f"Dia '{value}' extraído como '{day}'")
    return day


def infer_referred_year(
    referred_month_idx: int,
    payment_month: int,
    payment_year: int,
    referred_month_name: str,
    warnings: list[str],
) -> int:
    if referred_month_idx > payment_month:
        referred_year = payment_year - 1
        month_names_list = [
            "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
            "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
        ]
        payment_month_name = month_names_list[payment_month - 1]
        warnings.append(
            f"Ano do mês de referência inferido como '{referred_year}' "
            f"porque o mês de referência ({referred_month_name}) é posterior ao mês de pagamento ({payment_month_name})"
        )
    else:
        referred_year = payment_year
    return referred_year


def resolve_referred_month_and_year(
    value: str | int,
    payment_year: int,
    payment_month: int,
    warnings: list[str],
) -> tuple[str, int]:
    val_str = str(value).strip()
    if val_str.isdigit():
        num = int(val_str)
        if 1 <= num <= 12:
            canonical_names = [
                "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
                "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
            ]
            month_name = canonical_names[num - 1]
            referred_year = infer_referred_year(num, payment_month, payment_year, month_name, warnings)
            return month_name, referred_year
        else:
            raise ValueError(f"Mês numérico deve estar entre 1 e 12: {num}")

    parts = re.split(r"[./\-\s]+", val_str)
    parts = [p.strip() for p in parts if p.strip()]
    
    resolved_month_name = None
    resolved_year = None
    
    if len(parts) >= 2:
        for part in parts:
            if part.isdigit():
                val_int = int(part)
                if 1900 <= val_int <= 2100:
                    resolved_year = val_int
                    break
        
        for part in parts:
            if resolved_year is not None and part.isdigit() and int(part) == resolved_year:
                continue
            
            try:
                m_name = resolve_month_value(part, [])
                resolved_month_name = m_name
                
                if resolved_year is None:
                    for other_part in parts:
                        if other_part != part and other_part.isdigit():
                            y_val = int(other_part)
                            if 1900 <= y_val <= 2100:
                                resolved_year = y_val
                            elif 0 <= y_val <= 99:
                                resolved_year = 2000 + y_val
                                warnings.append(f"Ano de 2 dígitos '{other_part}' em '{value}' corrigido para '{resolved_year}'")
                            break
                break
            except ValueError:
                continue
                
    if resolved_month_name is None:
        resolved_month_name = resolve_month_value(value, warnings)
        
    if resolved_year is None:
        month_names_list = [
            "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
            "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
        ]
        month_idx = month_names_list.index(resolved_month_name) + 1
        resolved_year = infer_referred_year(month_idx, payment_month, payment_year, resolved_month_name, warnings)
        
    return resolved_month_name, resolved_year


def format_receipt_message(payment_date: date, referred_month_str: str, pt_br: bool) -> str:
    month_name, _, referred_year = referred_month_str.partition(".")
    
    if pt_br:
        pt_months = {
            "JANUARY": "janeiro",
            "FEBRUARY": "fevereiro",
            "MARCH": "março",
            "APRIL": "abril",
            "MAY": "maio",
            "JUNE": "junho",
            "JULY": "julho",
            "AUGUST": "agosto",
            "SEPTEMBER": "setembro",
            "OCTOBER": "outubro",
            "NOVEMBER": "novembro",
            "DECEMBER": "dezembro",
        }
        pt_month = pt_months.get(month_name, month_name.lower())
        formatted_date = payment_date.strftime("%d/%m/%Y")
        return f"Recibo de pagamento: pagamento efetuado em {formatted_date} referente ao mês de {pt_month} de {referred_year}."
    else:
        formatted_date = payment_date.isoformat()
        en_month = month_name.capitalize()
        return f"Payment receipt: payment made on {formatted_date} referred to the month of {en_month} {referred_year}."


RECEIPT_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {
    margin: 0;
    padding: 0;
    background-color: #ffffff;
    width: 1650px;
    height: 1600px;
    overflow: hidden;
  }
  .receipt-container {
    width: 1650px;
    height: 1600px;
    background-color: #ffffff;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-family: 'Segoe UI Black', 'Segoe UI', sans-serif;
  }
  .thick-bar {
    height: 24px;
    background-color: #03008D;
  }
  .thin-bar {
    height: 6px;
    background-color: #03008D;
  }
  .top-bar .thin-bar {
    margin-top: 6px;
  }
  .bottom-bar .thin-bar {
    margin-bottom: 6px;
  }
  .receipt-content {
    padding: 80px 180px 100px 180px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    flex-grow: 1;
  }
  h1 {
    font-size: 68px;
    color: #000000;
    text-transform: uppercase;
    text-align: center;
    letter-spacing: 6px;
    margin: 0 0 70px 0;
    text-decoration: underline;
    text-underline-offset: 5px;
  }
  .body-text {
    font-size: 44px;
    line-height: 1.6;
    text-align: justify;
    color: #2b2b2b;
    margin: 0 0 100px 0;
  }
  .signature-container {
    text-align: center;
  }
  .date-line {
    font-size: 38px;
    color: #03008D;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 0 0 40px 0;
  }
  .signature-img {
    width: 1080px;
    height: 250px;
    display: block;
    margin: 0 auto 20px auto;
  }
  .signer-name {
    font-size: 40px;
    color: #000000;
    margin: 0;
  }
  .signer-address {
    font-size: 28px;
    color: #666666;
    margin: 10px 0 0 0;
  }
</style>
</head>
<body>
  <div class="receipt-container">
    <div class="top-bar">
      <div class="thick-bar"></div>
      <div class="thin-bar"></div>
    </div>
    <div class="receipt-content">
      <h1>Recibo</h1>
      <p class="body-text">
        {{ body_text }}
      </p>
      <div class="signature-container">
        <p class="date-line">{{ location_date_line }}</p>
        <img class="signature-img" src="{{ signature_image_url }}" alt="Signature">
        <p class="signer-name">{{ signer_name }}</p>
        <p class="signer-address">{{ signer_address }}</p>
      </div>
    </div>
    <div class="bottom-bar">
      <div class="thin-bar"></div>
      <div class="thick-bar"></div>
    </div>
  </div>
</body>
</html>
"""


def ensure_signature_image() -> None:
    path = Path("signature.png")
    if not path.exists():
        img = Image.new("RGBA", (1080, 250), (0, 0, 0, 0))
        img.save(path)


def format_receipt_html(
    payment_date: date,
    referred_month_str: str,
    signer_name: str,
    signer_address: str,
    location: str,
    pt_br: bool,
    body_text: str
) -> str:
    """Renders the HTML template for the receipt.

    Args:
        payment_date: The date of payment.
        referred_month_str: The referred month (e.g. 'JANUARY.2024').
        signer_name: Name of the receipt signer.
        signer_address: Address of the receipt signer.
        location: Signed location.
        pt_br: True if language is pt-br, False for english.
        body_text: The receipt body text template. Must contain the placeholder '{ref_month}'.

    Raises:
        ValueError: If 'body_text' does not contain the placeholder '{ref_month}'.
    """
    if "{ref_month}" not in body_text:
        raise ValueError("O texto do corpo (body_text) deve conter a tag '{ref_month}' para substituição.")

    month_name, _, referred_year = referred_month_str.partition(".")
    
    if pt_br:
        pt_months = {
            "JANUARY": "janeiro",
            "FEBRUARY": "fevereiro",
            "MARCH": "março",
            "APRIL": "abril",
            "MAY": "maio",
            "JUNE": "junho",
            "JULY": "julho",
            "AUGUST": "agosto",
            "SEPTEMBER": "setembro",
            "OCTOBER": "outubro",
            "NOVEMBER": "novembro",
            "DECEMBER": "dezembro",
        }
        ref_month_display = f"{pt_months.get(month_name, month_name.lower())}.{referred_year}".upper()
        
        month_idx = payment_date.month
        month_names_pt = [
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
        ]
        pt_payment_month = month_names_pt[month_idx - 1]
        location_date_line = f"{location.upper()}, {payment_date.day} de {pt_payment_month} de {payment_date.year}"
    else:
        ref_month_display = f"{month_name.capitalize()} {referred_year}"
        
        month_names_en = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        en_payment_month = month_names_en[payment_date.month - 1]
        location_date_line = f"{location.upper()}, {payment_date.day} of {en_payment_month} of {payment_date.year}"
        
    formatted_body_text = body_text.replace("{ref_month}", ref_month_display)
    ensure_signature_image()
    template = Template(RECEIPT_HTML_TEMPLATE)
    sig_path = str(Path("signature.png").resolve().as_uri())
    return template.render(
        body_text=formatted_body_text,
        location_date_line=location_date_line,
        signer_name=signer_name,
        signer_address=signer_address,
        signature_image_url=sig_path
    )


async def process_direct_receipt(request: DirectReceiptRequest) -> DirectReceiptResponse:
    warnings = []
    
    try:
        payment_year = resolve_year_value(request.payment_year, warnings)
    except Exception as exc:
        raise ValueError(f"Erro no ano de pagamento: {exc}") from exc
        
    try:
        payment_month_name = resolve_month_value(request.payment_month, warnings)
    except Exception as exc:
        raise ValueError(f"Erro no mês de pagamento: {exc}") from exc
        
    month_names_list = [
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    ]
    payment_month = month_names_list.index(payment_month_name) + 1
    
    try:
        payment_day = resolve_day_value(request.payment_day, warnings)
    except Exception as exc:
        raise ValueError(f"Erro no dia de pagamento: {exc}") from exc
        
    try:
        payment_date = date(payment_year, payment_month, payment_day)
    except ValueError as exc:
        raise ValueError(f"Data de pagamento inválida ({payment_year}-{payment_month}-{payment_day}): {exc}") from exc
        
    if payment_date > date.today():
        raise ValueError(f"Data de pagamento não pode estar no futuro: {payment_date}")
        
    try:
        referred_month_name, referred_year = resolve_referred_month_and_year(
            request.referred_month, payment_year, payment_month, warnings
        )
    except Exception as exc:
        raise ValueError(f"Erro no mês de referência: {exc}") from exc
        
    referred_month_str = f"{referred_month_name}.{referred_year}"
    
    formatted_message = format_receipt_message(payment_date, referred_month_str, request.pt_br)
    
    body_txt = request.body_text
    if body_txt is None:
        if request.pt_br:
            body_txt = "Recebi o recibo referente ao pagamento do mês de {ref_month}."
        else:
            body_txt = "I received the receipt for the payment of month of {ref_month}."

    db_config = get_db_config()
    signer_name = request.signer_name or db_config["signer_name"]
    signer_address = request.signer_address or db_config["signer_address"]
    location = request.location or db_config["location"]

    html_content = format_receipt_html(
        payment_date=payment_date,
        referred_month_str=referred_month_str,
        signer_name=signer_name,
        signer_address=signer_address,
        location=location,
        pt_br=request.pt_br,
        body_text=body_txt
    )
    
    try:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        safe_referred_month = referred_month_str.replace(".", "_")
        filename = f"receipt_{payment_date}_{safe_referred_month}.png"
        image_path = output_dir / filename
        
        hti = Html2Image(output_path=str(output_dir))
        hti.screenshot(html_str=html_content, save_as=filename, size=(1650, 1600))
        image_path_str = str(image_path.resolve())
    except Exception as exc:
        warnings.append(f"Falha ao gerar imagem do recibo: {exc}")
        image_path_str = None
        
    return DirectReceiptResponse(
        status="sucesso",
        payment_date=payment_date,
        referred_month=referred_month_str,
        formatted_message=formatted_message,
        image_path=image_path_str,
        trigger_info={
            "warnings": warnings,
            "original_input": {
                "payment_day": request.payment_day,
                "payment_month": request.payment_month,
                "payment_year": request.payment_year,
                "referred_month": request.referred_month
            }
        }
    )


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


async def generate_receipts(source_text: str, pt_br: bool = True) -> ReceiptGenerationResult:
    extractor = PydanticAIReceiptExtractor()
    extracted = await extractor.run(source_text)
    formatted_message = format_receipt_message(extracted.payment_date, extracted.referred_month, pt_br)
    return ReceiptGenerationResult(extracted=extracted, formatted_message=formatted_message)


__all__ = [
    "ReceiptGenerationResult",
    "ReceiptExtraction",
    "generate_receipts",
    "DirectReceiptRequest",
    "DirectReceiptResponse",
    "process_direct_receipt",
    "MONTH_NAMES",
    "MONTH_ALIASES",
    "normalize_text",
    "tokens",
    "contains_term",
    "resolve_month",
    "resolve_referred_month_and_year",
    "infer_referred_year",
    "format_receipt_message",
    "format_receipt_html",
]
