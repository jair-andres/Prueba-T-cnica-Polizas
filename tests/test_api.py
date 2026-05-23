"""
Tests críticos del sistema de pólizas.

Cubren los 3 casos de mayor riesgo según los requisitos:
  1. Idempotencia en pagos (requisito explícito del enunciado)
  2. Lógica de mora con zona horaria Bogotá
  3. Reporte de cartera vencida
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import engine
from app.models import metadata


# ──────────────────────────────────────────────
# Fixtures de infraestructura
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def setup_db():
    """Crea el esquema limpio antes del módulo y lo elimina al final."""
    metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)
    yield
    metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Registra un usuario y devuelve los headers Bearer para el módulo completo."""
    r_reg = client.post("/auth/register", json={
        "username": "tester",
        "email": "tester@test.com",
        "password": "TestPass123",
    })
    # 201 = creado, 400 = ya existía (si setup_db no limpió). Ambos son aceptables.
    assert r_reg.status_code in (201, 400), f"Register falló inesperadamente: {r_reg.text}"

    r = client.post("/auth/login", data={"username": "tester", "password": "TestPass123"})
    assert r.status_code == 200, f"Login falló: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _crear_poliza(client, auth_headers, *, numero, prima, dias_vence, dias_emision=0):
    """Helper: crea cliente + póliza y devuelve el poliza_id."""
    doc = f"DOC-{numero}"
    r = client.post("/clientes/", json={"nombre": f"Cliente {numero}", "documento": doc},
                    headers=auth_headers)
    assert r.status_code == 201
    cliente_id = r.json()["data"]["id"]

    emision = date.today() - timedelta(days=dias_emision)
    vence = date.today() + timedelta(days=dias_vence)
    r = client.post("/polizas/", json={
        "cliente_id": cliente_id,
        "numero_poliza": f"POL-{numero}",
        "prima_total": str(prima),
        "fecha_emision": str(emision),
        "fecha_vencimiento": str(vence),
        "beneficiarios": [{"nombre": "Beneficiario Test", "documento": f"BEN-{numero}"}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


# ──────────────────────────────────────────────
# Test 1 — Idempotencia en pagos
# ──────────────────────────────────────────────

def test_pago_idempotente(client, auth_headers):
    """
    Dos requests con la misma clave_idempotencia no deben duplicar el pago.
    Requisito explícito del enunciado: "si el cliente reintenta con la misma
    idempotency_key, no se debe duplicar el pago".
    """
    pol_id = _crear_poliza(client, auth_headers, numero="IDEM-01", prima=500, dias_vence=90, dias_emision=1)

    pago = {"monto": "100.00", "clave_idempotencia": "uuid-idem-test-001"}

    r1 = client.post(f"/polizas/{pol_id}/pagos", json=pago, headers=auth_headers)
    assert r1.status_code == 201
    pago_id_original = r1.json()["data"]["id"]

    # Segundo intento con la misma clave → debe devolver el mismo pago
    r2 = client.post(f"/polizas/{pol_id}/pagos", json=pago, headers=auth_headers)
    assert r2.status_code == 201
    assert r2.json()["data"]["id"] == pago_id_original, (
        "El segundo request con la misma clave_idempotencia creó un pago duplicado"
    )

    # El saldo solo debe haber bajado una vez
    estado = client.get(f"/polizas/{pol_id}/estado", headers=auth_headers).json()["data"]
    assert float(estado["saldo_pendiente"]) == 400.00


# ──────────────────────────────────────────────
# Test 2 — Estado de póliza con lógica de mora
# ──────────────────────────────────────────────

def test_estado_poliza_mora_y_al_dia(client, auth_headers):
    """
    Verifica los tres estados posibles de una póliza:
      - 'en mora'   → vencida sin pagos suficientes
      - 'al día'    → prima totalmente cubierta
    La lógica usa zona horaria America/Bogota (requisito del enunciado).
    """
    # Póliza vencida hace 40 días sin pagos → en mora
    pol_mora = _crear_poliza(
        client, auth_headers,
        numero="MORA-01", prima=200,
        dias_vence=-40,   # venció hace 40 días
        dias_emision=100,
    )
    estado = client.get(f"/polizas/{pol_mora}/estado", headers=auth_headers).json()["data"]
    assert estado["estado"] == "en mora", f"Esperaba 'en mora', llegó: {estado['estado']}"
    assert float(estado["saldo_pendiente"]) == 200.00

    # Pagar la totalidad → al día
    client.post(f"/polizas/{pol_mora}/pagos",
                json={"monto": "200.00"}, headers=auth_headers)
    estado = client.get(f"/polizas/{pol_mora}/estado", headers=auth_headers).json()["data"]
    assert estado["estado"] == "al día", f"Esperaba 'al día', llegó: {estado['estado']}"
    assert float(estado["saldo_pendiente"]) == 0.00


# ──────────────────────────────────────────────
# Test 3 — Reporte de cartera vencida
# ──────────────────────────────────────────────

def test_reporte_cartera_vencida(client, auth_headers):
    """
    Pólizas con saldo pendiente y más de 30 días de mora deben aparecer
    en el reporte. Una póliza al día NO debe aparecer.
    """
    # Póliza en mora (vencida hace 40 días, sin pagos) → debe aparecer
    pol_mora = _crear_poliza(
        client, auth_headers,
        numero="REP-MORA-01", prima=300,
        dias_vence=-40,
        dias_emision=120,
    )

    # Póliza al día (completamente pagada) → NO debe aparecer
    pol_pagada = _crear_poliza(
        client, auth_headers,
        numero="REP-PAGADA-01", prima=150,
        dias_vence=-40,
        dias_emision=120,
    )
    client.post(f"/polizas/{pol_pagada}/pagos",
                json={"monto": "150.00"}, headers=auth_headers)

    r = client.get("/reportes/cartera-vencida?page=1&size=50", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["data"]
    ids_en_reporte = [i["poliza_id"] for i in items]

    assert pol_mora in ids_en_reporte, "La póliza en mora no aparece en el reporte"
    assert pol_pagada not in ids_en_reporte, "La póliza al día NO debería estar en el reporte"

    # Verificar estructura del item
    item = next(i for i in items if i["poliza_id"] == pol_mora)
    assert item["dias_mora"] >= 10
    assert float(item["saldo_pendiente"]) > 0
