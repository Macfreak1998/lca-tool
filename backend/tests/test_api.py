from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants import ROLE_ADMIN
from app.db import Base, get_db
from app.main import app
from app.models import User
from app.services.auth import hash_password


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        User(
            email="admin@localhost",
            password_hash=hash_password("admin"),
            role=ROLE_ADMIN,
            email_verified_at=datetime.utcnow(),
        )
    )
    session.commit()

    def override() -> object:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_login_and_roles():
    client = _client()
    denied = client.get("/api/roles")
    assert denied.status_code == 401
    login = client.post("/api/auth/login", json={"email": "admin@localhost", "password": "admin"})
    assert login.status_code == 200
    created = client.post("/api/roles", json={"label": "Stärke"})
    assert created.status_code == 200
    assert created.json()["slug"] == "starke"
    listed = client.get("/api/roles")
    assert listed.status_code == 200
    assert listed.json()[0]["label"] == "Stärke"
