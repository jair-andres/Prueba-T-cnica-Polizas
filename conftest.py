import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "postgresql://test_user:test_pass@db_test:5432/polizas_test"

from app.database import engine  # noqa: E402
from app.main import app         # noqa: E402
from app.models import metadata  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    metadata.create_all(bind=engine)  # solo crea lo que falta, nunca borra
    yield


@pytest.fixture(scope="session")
def client(setup_test_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    client.post("/auth/register", json={
        "username": "tester",
        "email": "tester@test.com",
        "password": "TestPass123",
    })
    r = client.post("/auth/login", data={"username": "tester", "password": "TestPass123"})
    assert r.status_code == 200, f"Login falló: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
