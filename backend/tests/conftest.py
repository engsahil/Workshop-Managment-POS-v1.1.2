"""Shared test fixtures — isolated temp database, never touches real data."""
import os
import sys
import tempfile
from pathlib import Path

# Isolate runtime data BEFORE importing the app
_TMP = tempfile.mkdtemp(prefix="awp_test_")
os.environ["AWP_DATA_DIR"] = _TMP
os.environ["AWP_SECRET_KEY"] = "test-secret-key-not-for-production-32bytes+"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_engine, get_session_factory, init_db, dispose_engine
from app.main import app
from app.models import User
from app.core.security import hash_password


@pytest.fixture(scope="session")
def client():
    init_db()
    with TestClient(app) as c:
        yield c
    dispose_engine()


@pytest.fixture(scope="session")
def admin_token(client):
    # first-run setup
    r = client.get("/api/auth/setup-status")
    if r.json()["needs_setup"]:
        client.post("/api/auth/setup", json={
            "username": "admin", "full_name": "Admin",
            "password": "admin123", "password_confirm": "admin123"})
    r = client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def db_session():
    from app.core.database import get_session_factory
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def make_user(db, username, role, password="pass1234"):
    u = User(username=username, full_name=username.title(),
             password_hash=hash_password(password), role=role)
    db.add(u)
    db.commit()
    return u


def token_for(client, username, password="pass1234"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
