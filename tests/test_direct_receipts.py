import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.services.receipts import (
    DirectReceiptRequest,
    process_direct_receipt,
    extract_digits,
    resolve_month_value,
    resolve_year_value,
    resolve_day_value,
    resolve_referred_month_and_year,
    infer_referred_year,
    format_receipt_message,
)

client = TestClient(app)


def test_extract_digits():
    assert extract_digits(12) == 12
    assert extract_digits("15") == 15
    assert extract_digits("day 25") == 25
    with pytest.raises(ValueError):
        extract_digits("no digits here")


def test_resolve_month_value():
    warnings = []
    assert resolve_month_value(2, warnings) == "FEBRUARY"
    assert resolve_month_value("03", warnings) == "MARCH"
    assert resolve_month_value("janeiro", warnings) == "JANUARY"
    assert resolve_month_value("Feb", warnings) == "FEBRUARY"
    assert resolve_month_value("Mrach", warnings) == "MARCH"
    
    with pytest.raises(ValueError):
        resolve_month_value(13, warnings)
    with pytest.raises(ValueError):
        resolve_month_value("invalid_month", warnings)


def test_resolve_year_value():
    warnings = []
    assert resolve_year_value(2024, warnings) == 2024
    assert resolve_year_value("2023", warnings) == 2023
    assert resolve_year_value("24", warnings) == 2024
    assert "Ano de 2 dígitos" in warnings[0]
    
    with pytest.raises(ValueError):
        resolve_year_value(1899, warnings)
    with pytest.raises(ValueError):
        resolve_year_value(2101, warnings)


def test_resolve_day_value():
    warnings = []
    assert resolve_day_value(15, warnings) == 15
    assert resolve_day_value("05", warnings) == 5
    
    with pytest.raises(ValueError):
        resolve_day_value(0, warnings)
    with pytest.raises(ValueError):
        resolve_day_value(32, warnings)


def test_resolve_referred_month_and_year():
    warnings = []
    
    # 1. Standard text month, inferred year (same year because June >= Feb)
    month, year = resolve_referred_month_and_year("FEBRUARY", 2024, 6, warnings)
    assert month == "FEBRUARY"
    assert year == 2024
    
    # 2. Inferred year from previous year (Dec > June)
    warnings.clear()
    month, year = resolve_referred_month_and_year("DECEMBER", 2024, 6, warnings)
    assert month == "DECEMBER"
    assert year == 2023
    assert any("inferido" in w for w in warnings)
    
    # 3. Explicit 4-digit year with dot separator
    warnings.clear()
    month, year = resolve_referred_month_and_year("FEBRUARY.2023", 2024, 6, warnings)
    assert month == "FEBRUARY"
    assert year == 2023
    assert not warnings
    
    # 4. Explicit 2-digit year with slash separator
    warnings.clear()
    month, year = resolve_referred_month_and_year("02/23", 2024, 6, warnings)
    assert month == "FEBRUARY"
    assert year == 2023
    assert any("Ano de 2 dígitos" in w for w in warnings)
    
    # 5. Explicit 2-digit year, year first format
    warnings.clear()
    month, year = resolve_referred_month_and_year("23/02", 2024, 6, warnings)
    assert month == "FEBRUARY"
    assert year == 2023

    # 6. Explicit 4-digit year, year first format
    warnings.clear()
    month, year = resolve_referred_month_and_year("2023-02", 2024, 6, warnings)
    assert month == "FEBRUARY"
    assert year == 2023


def test_format_receipt_message():
    # Test PT-BR format
    msg_pt = format_receipt_message(date(2024, 5, 15), "MAY.2024", True)
    assert "Recibo de pagamento: pagamento efetuado em 15/05/2024 referente ao mês de maio de 2024." in msg_pt
    
    # Test EN format
    msg_en = format_receipt_message(date(2024, 5, 15), "MAY.2024", False)
    assert "Payment receipt: payment made on 2024-05-15 referred to the month of May 2024." in msg_en


@pytest.mark.anyio
async def test_process_direct_receipt_valid():
    req = DirectReceiptRequest(
        payment_day=15,
        payment_month=5,
        payment_year=2024,
        referred_month=5,
        pt_br=True
    )
    res = await process_direct_receipt(req)
    assert res.status == "sucesso"
    assert res.payment_date == date(2024, 5, 15)
    assert res.referred_month == "MAY.2024"
    assert "Recibo de pagamento" in res.formatted_message
    assert "15/05/2024" in res.formatted_message
    assert "maio de 2024" in res.formatted_message


@pytest.mark.anyio
async def test_process_direct_receipt_valid_en():
    req = DirectReceiptRequest(
        payment_day=15,
        payment_month=5,
        payment_year=2024,
        referred_month=5,
        pt_br=False
    )
    res = await process_direct_receipt(req)
    assert res.status == "sucesso"
    assert res.payment_date == date(2024, 5, 15)
    assert res.referred_month == "MAY.2024"
    assert "Payment receipt" in res.formatted_message
    assert "2024-05-15" in res.formatted_message
    assert "May 2024" in res.formatted_message


@pytest.mark.anyio
async def test_process_direct_receipt_inferred_prev_year():
    req = DirectReceiptRequest(
        payment_day=15,
        payment_month=1,
        payment_year=2024,
        referred_month="dezembro"
    )
    res = await process_direct_receipt(req)
    assert res.status == "sucesso"
    assert res.payment_date == date(2024, 1, 15)
    assert res.referred_month == "DECEMBER.2023"
    assert any("inferido" in w for w in res.trigger_info["warnings"])


@pytest.mark.anyio
async def test_process_direct_receipt_explicit_year():
    req = DirectReceiptRequest(
        payment_day=15,
        payment_month=6,
        payment_year=2024,
        referred_month="DECEMBER.2024"
    )
    res = await process_direct_receipt(req)
    assert res.status == "sucesso"
    assert res.payment_date == date(2024, 6, 15)
    assert res.referred_month == "DECEMBER.2024"


@pytest.mark.anyio
async def test_process_direct_receipt_invalid_date():
    req = DirectReceiptRequest(
        payment_day=31,
        payment_month=2,
        payment_year=2024,
        referred_month=2
    )
    with pytest.raises(ValueError, match="Data de pagamento inválida"):
        await process_direct_receipt(req)


@pytest.mark.anyio
async def test_process_direct_receipt_future_date():
    req = DirectReceiptRequest(
        payment_day=1,
        payment_month=1,
        payment_year=2099,
        referred_month=1
    )
    with pytest.raises(ValueError, match="Data de pagamento não pode estar no futuro"):
        await process_direct_receipt(req)


def test_api_direct_receipt_success():
    # 1. Default (PT-BR)
    payload = {
        "payment_day": "10",
        "payment_month": "fevereiro",
        "payment_year": "2024",
        "referred_month": "janeiro"
    }
    response = client.post("/receipts/direct", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sucesso"
    assert data["payment_date"] == "2024-02-10"
    assert data["referred_month"] == "JANUARY.2024"
    assert "Recibo de pagamento: pagamento efetuado em 10/02/2024 referente ao mês de janeiro de 2024." in data["formatted_message"]

    # 2. English (pt_br = False)
    payload["pt_br"] = False
    response = client.post("/receipts/direct", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Payment receipt: payment made on 2024-02-10 referred to the month of January 2024." in data["formatted_message"]


def test_api_direct_receipt_bad_request():
    payload = {
        "payment_day": 30,
        "payment_month": 2,
        "payment_year": 2024,
        "referred_month": 2
    }
    response = client.post("/receipts/direct", json=payload)
    assert response.status_code == 400
    assert "Data de pagamento inválida" in response.json()["detail"]


def test_api_direct_receipt_validation_error():
    payload = {
        "payment_day": 10,
        "payment_month": 2,
        "payment_year": 2024
    }
    response = client.post("/receipts/direct", json=payload)
    assert response.status_code == 422
