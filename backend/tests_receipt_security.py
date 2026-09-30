import sys
import asyncio
from fastapi.testclient import TestClient

# Mock environment variables before importing
import os
os.environ["CHANNEL_SERVICE_SECRET"] = "test_super_secret"

from main import app
from core.config import CHANNEL_SERVICE_SECRET

client = TestClient(app)

def test_no_key():
    response = client.post("/receipt", json={"campaign_id": 1, "customer_id": 1, "status": "delivered"})
    print(f"No key -> {response.status_code}")
    assert response.status_code == 401

def test_wrong_key():
    response = client.post("/receipt", json={"campaign_id": 1, "customer_id": 1, "status": "delivered"}, headers={"X-Channel-Service-Key": "wrong"})
    print(f"Wrong key -> {response.status_code}")
    assert response.status_code == 403

def test_correct_key():
    # Because testing requires DB connection and we are just testing the boundary,
    # we expect either 200 or 500 depending on DB state, but NOT 401 or 403.
    response = client.post("/receipt", json={"campaign_id": 1, "customer_id": 1, "status": "delivered"}, headers={"X-Channel-Service-Key": "test_super_secret"})
    print(f"Correct key -> {response.status_code}")
    assert response.status_code not in (401, 403)

if __name__ == "__main__":
    test_no_key()
    test_wrong_key()
    test_correct_key()
    print("Tests passed.")
