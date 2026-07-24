import os
import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.services.receipts import (
    DirectReceiptRequest,
    process_direct_receipt,
)
from app.services.auth import create_access_token
from app.services.database import init_db, update_db_config, get_db_config

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    from app.services.database import DEFAULT_SIGNER_NAME, DEFAULT_SIGNER_ADDRESS, DEFAULT_LOCATION
    update_db_config(
        signer_name=DEFAULT_SIGNER_NAME,
        signer_address=DEFAULT_SIGNER_ADDRESS,
        location=DEFAULT_LOCATION
    )
    yield


def test_api_auth_token_success():
    # Test admin auth
    response = client.post(
        "/auth/token",
        data={"username": "any_user", "password": "admin123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_api_direct_receipt_unauthorized():
    payload = {
        "payment_day": "10",
        "payment_month": "5",
        "payment_year": "2024",
        "referred_month": "5"
    }
    response = client.post("/receipts/direct", json=payload)
    assert response.status_code == 401


def test_api_direct_receipt_success():
    token = create_access_token(subject="admin", role="admin")
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "payment_day": "10",
        "payment_month": "fevereiro",
        "payment_year": "2024",
        "referred_month": "janeiro",
        "signer_name": "Test User Name",
        "signer_address": "Test User Address, 123",
        "location": "TEST LOCATION"
    }
    response = client.post("/receipts/direct", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sucesso"
    assert data["payment_date"] == "2024-02-10"
    if data["image_path"] and os.path.exists(data["image_path"]):
        os.remove(data["image_path"])


def test_api_update_config_and_fallback():
    token = create_access_token(subject="admin", role="admin")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Update config defaults using generic test values
    payload = {
        "signer_name": "Test Signer Editado",
        "signer_address": "Av Teste, 100",
        "location": "TEST LOCAL"
    }
    response = client.put("/config", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["signer_name"] == "Test Signer Editado"
    
    # 2. Trigger receipt without signer fields (should fallback to database)
    receipt_payload = {
        "payment_day": "15",
        "payment_month": "5",
        "payment_year": "2024",
        "referred_month": "5"
    }
    receipt_resp = client.post("/receipts/direct", json=receipt_payload, headers=headers)
    assert receipt_resp.status_code == 200
    data = receipt_resp.json()
    assert data["status"] == "sucesso"
    if data["image_path"] and os.path.exists(data["image_path"]):
        os.remove(data["image_path"])

    # Double check database got updated config settings
    db_config = get_db_config()
    assert db_config["signer_name"] == "Test Signer Editado"
    assert db_config["signer_address"] == "Av Teste, 100"
    assert db_config["location"] == "TEST LOCAL"
