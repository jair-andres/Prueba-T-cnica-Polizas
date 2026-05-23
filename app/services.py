from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, OperationalError

from .repository import ClientesRepository, PolizasRepository, PagosRepository, ReportesRepository
from .schemas import ClienteCreate, ClienteResponse, PolizaCreate, PolizaResponse, PagoCreate, PagoResponse, PolizaEstadoResponse


def _hoy_bogota() -> date:
    """Fecha actual en la zona horaria de Bogotá (America/Bogota)."""
    return datetime.now(tz=ZoneInfo("America/Bogota")).date()


class ClienteService:
    def __init__(self, conn: Connection):
        self.repo = ClientesRepository(conn)

    def create_cliente(self, payload: ClienteCreate, created_by: Optional[str] = None) -> ClienteResponse:
        existing = self.repo.get_by_documento(payload.documento)
        if existing is not None:
            raise HTTPException(status_code=400, detail="El documento ya está registrado")
        data = payload.dict()
        if created_by:
            data["creado_por"] = created_by
            data["actualizado_por"] = created_by
        row = self.repo.create(data)
        return ClienteResponse(**row)


class PolizaService:
    def __init__(self, conn: Connection):
        self.conn = conn
        self.clientes = ClientesRepository(conn)
        self.polizas = PolizasRepository(conn)

    def create_poliza(self, payload: PolizaCreate, created_by: Optional[str] = None) -> PolizaResponse:
        cliente = self.clientes.get_by_id(payload.cliente_id)
        if cliente is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        if payload.fecha_emision > _hoy_bogota():
            raise HTTPException(status_code=400, detail="La fecha de emisión no puede ser futura")

        poliza_data = {
            "cliente_id": payload.cliente_id,
            "numero_poliza": payload.numero_poliza,
            "prima_total": payload.prima_total,
            "fecha_emision": payload.fecha_emision,
            "fecha_vencimiento": payload.fecha_vencimiento,
        }
        if created_by:
            poliza_data["creado_por"] = created_by
            poliza_data["actualizado_por"] = created_by

        benefs = [benef.dict() for benef in payload.beneficiarios]
        if created_by:
            for b in benefs:
                b["creado_por"] = created_by
                b["actualizado_por"] = created_by

        poliza = self.polizas.create(poliza_data, benefs)
        return PolizaResponse(
            id=poliza["id"],
            cliente_id=poliza["cliente_id"],
            numero_poliza=poliza.get("numero_poliza"),
            prima_total=poliza["prima_total"],
            fecha_emision=poliza["fecha_emision"],
            fecha_vencimiento=poliza["fecha_vencimiento"],
            beneficiarios=[],
        )

    def get_poliza_estado(self, poliza_id: int) -> PolizaEstadoResponse:
        poliza = self.polizas.get_by_id(poliza_id)
        if poliza is None:
            raise HTTPException(status_code=404, detail="Póliza no encontrada")

        total_pagado = self.polizas.get_total_pagado(poliza_id)
        fecha_ultimo_pago = self.polizas.get_ultimo_pago(poliza_id)
        saldo = poliza["prima_total"] - total_pagado

        # La mora se evalúa con la fecha actual en Bogotá (America/Bogota),
        # aunque los timestamps internos se almacenan en UTC.
        hoy = _hoy_bogota()
        if total_pagado >= poliza["prima_total"]:
            estado = "al día"
        elif poliza["fecha_vencimiento"] < hoy:
            estado = "en mora"
        else:
            estado = "pendiente"

        return PolizaEstadoResponse(
            poliza_id=poliza_id,
            prima_total=poliza["prima_total"],
            saldo_pendiente=saldo,
            fecha_ultimo_pago=fecha_ultimo_pago,
            estado=estado,
        )


class PagoService:
    def __init__(self, conn: Connection):
        self.conn = conn
        self.polizas = PolizasRepository(conn)
        self.pagos = PagosRepository(conn)

    def create_pago(self, poliza_id: int, payload: PagoCreate, created_by: Optional[str] = None) -> PagoResponse:
        # ── 1. Fast path: idempotencia sin lock (evita contención innecesaria) ──
        if payload.clave_idempotencia:
            existing = self.pagos.get_by_idempotency(poliza_id, payload.clave_idempotencia)
            if existing is not None:
                return PagoResponse(**existing)

        # ── 2. FOR UPDATE: serializa requests concurrentes sobre la misma póliza ──
        # lock_timeout evita que el segundo request quede bloqueado indefinidamente
        # si otro está procesando un pago simultáneo sobre la misma póliza.
        try:
            self.conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            poliza = self.polizas.get_by_id_for_update(poliza_id)
        except OperationalError:
            raise HTTPException(
                status_code=503,
                detail="Hay otro pago en proceso para esta póliza. Intenta en unos segundos.",
            )

        if poliza is None:
            raise HTTPException(status_code=404, detail="Póliza no encontrada")

        if poliza.get("estado") != "activa":
            raise HTTPException(status_code=400, detail="No se pueden registrar pagos en una póliza que no está activa")

        # ── 3. Re-check idempotencia tras el lock ──
        # Cubre el caso donde dos requests con la misma clave llegaron simultáneos:
        # el segundo llega aquí y encuentra el pago que el primero ya insertó.
        if payload.clave_idempotencia:
            existing = self.pagos.get_by_idempotency(poliza_id, payload.clave_idempotencia)
            if existing is not None:
                return PagoResponse(**existing)

        # ── 4. Saldo consistente (lectura segura porque tenemos el lock) ──
        total_pagado = self.polizas.get_total_pagado(poliza_id)
        saldo_pendiente = poliza["prima_total"] - total_pagado
        if payload.monto > saldo_pendiente:
            raise HTTPException(
                status_code=400,
                detail=f"El monto ({payload.monto}) excede el saldo pendiente ({saldo_pendiente})",
            )

        # ── 5. Insertar ──
        pago_data = payload.dict(exclude_unset=True)
        if created_by:
            pago_data["creado_por"] = created_by
            pago_data["actualizado_por"] = created_by

        try:
            nuevo = self.pagos.create(poliza_id, pago_data)
        except IntegrityError:
            # Última línea de defensa: si dos requests sin clave_idempotencia idéntica
            # pasaron el lock al mismo tiempo (no debería ocurrir), el UNIQUE constraint
            # del schema lo atrapa. Retornamos 409 en vez de 500.
            raise HTTPException(
                status_code=409,
                detail="Conflicto al registrar el pago. Verifica la clave de idempotencia.",
            )

        return PagoResponse(**nuevo)


class ReportesService:
    def __init__(self, conn: Connection):
        self.repo = ReportesRepository(conn)

    def cartera_vencida(self, fecha_corte: date, page: int, size: int):
        return self.repo.list_cartera_vencida(fecha_corte, page, size)