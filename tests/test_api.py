"""
Tests críticos del sistema de pólizas.

Cada ejecución genera IDs únicos (uuid) para evitar conflictos
de unique constraint entre corridas sin borrar la base de datos.
"""
import uuid
from datetime import date, timedelta


def _uid():
    return uuid.uuid4().hex[:8].upper()


def _crear_poliza(client, auth_headers, *, prima, dias_vence, dias_emision=1):
    uid = _uid()
    r = client.post("/clientes/", json={
        "nombre": f"Cliente {uid}",
        "documento": f"DOC-{uid}",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    cliente_id = r.json()["data"]["id"]

    r = client.post("/polizas/", json={
        "cliente_id": cliente_id,
        "numero_poliza": f"POL-{uid}",
        "prima_total": str(prima),
        "fecha_emision": str(date.today() - timedelta(days=dias_emision)),
        "fecha_vencimiento": str(date.today() + timedelta(days=dias_vence)),
        "beneficiarios": [{"nombre": "Beneficiario", "documento": f"BEN-{uid}"}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


# ── Test 1 — Idempotencia en pagos ────────────────────────────────────────────

def test_pago_idempotente(client, auth_headers):
    """Mismo clave_idempotencia no debe duplicar el pago."""
    pol_id = _crear_poliza(client, auth_headers, prima=500, dias_vence=90)
    clave = f"IDEM-{_uid()}"
    pago = {"monto": "100.00", "clave_idempotencia": clave}

    r1 = client.post(f"/polizas/{pol_id}/pagos", json=pago, headers=auth_headers)
    assert r1.status_code == 201
    pago_id = r1.json()["data"]["id"]

    r2 = client.post(f"/polizas/{pol_id}/pagos", json=pago, headers=auth_headers)
    assert r2.status_code == 201
    assert r2.json()["data"]["id"] == pago_id, "El segundo request duplicó el pago"

    estado = client.get(f"/polizas/{pol_id}/estado", headers=auth_headers).json()["data"]
    assert float(estado["saldo_pendiente"]) == 400.00


# ── Test 2 — Estado de póliza ─────────────────────────────────────────────────

def test_estado_poliza_mora_y_al_dia(client, auth_headers):
    """Póliza vencida sin pagos → en mora. Con pago total → al día."""
    pol_id = _crear_poliza(client, auth_headers, prima=200, dias_vence=-40, dias_emision=100)

    estado = client.get(f"/polizas/{pol_id}/estado", headers=auth_headers).json()["data"]
    assert estado["estado"] == "en mora", f"Esperaba 'en mora', llegó: {estado['estado']}"

    client.post(f"/polizas/{pol_id}/pagos", json={"monto": "200.00"}, headers=auth_headers)

    estado = client.get(f"/polizas/{pol_id}/estado", headers=auth_headers).json()["data"]
    assert estado["estado"] == "al día", f"Esperaba 'al día', llegó: {estado['estado']}"


# ── Test 3 — Reporte de cartera vencida ──────────────────────────────────────

def test_reporte_cartera_vencida(client, auth_headers):
    """Póliza en mora aparece en reporte. Póliza pagada no aparece."""
    pol_mora = _crear_poliza(client, auth_headers, prima=300, dias_vence=-40, dias_emision=120)
    pol_pagada = _crear_poliza(client, auth_headers, prima=150, dias_vence=-40, dias_emision=120)

    client.post(f"/polizas/{pol_pagada}/pagos", json={"monto": "150.00"}, headers=auth_headers)

    r = client.get("/reportes/cartera-vencida?page=1&size=100", headers=auth_headers)
    assert r.status_code == 200
    ids = [i["poliza_id"] for i in r.json()["data"]]

    assert pol_mora in ids, "La póliza en mora no aparece en el reporte"
    assert pol_pagada not in ids, "La póliza pagada no debería estar en el reporte"
