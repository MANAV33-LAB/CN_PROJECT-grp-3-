import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import engine, Base

@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c

def test_register_and_login_flow(client):
    unique_user = f"user_{int(time.time())}" if 'time' in globals() else "test_auth_user"
    import time
    uname = f"u_{int(time.time())}"
    email = f"{uname}@example.com"

    # Register
    reg_resp = client.post("/api/auth/register", json={
        "username": uname,
        "email": email,
        "password": "secretpassword",
        "display_name": "Test Auth User"
    })
    assert reg_resp.status_code == 200
    data = reg_resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == uname

    # Duplicate registration should fail
    dup_resp = client.post("/api/auth/register", json={
        "username": uname,
        "email": email,
        "password": "secretpassword"
    })
    assert dup_resp.status_code == 400

    # Login
    login_resp = client.post("/api/auth/login", json={
        "username_or_email": uname,
        "password": "secretpassword"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Invalid password login
    bad_resp = client.post("/api/auth/login", json={
        "username_or_email": uname,
        "password": "wrongpassword"
    })
    assert bad_resp.status_code == 401

    # Protected me endpoint
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == uname
