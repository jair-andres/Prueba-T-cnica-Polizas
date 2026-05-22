from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.engine import Connection
from fastapi import HTTPException

from .repository import ClientesRepository, PolizasRepository, PagosRepository, ReportesRepository
from .schemas import ClienteCreate, ClienteResponse, PolizaCreate, PolizaResponse, PagoCreate, PagoResponse, PolizaEstadoResponse


class ClienteService:
    def __init__(self, conn: Connection):
        self.repo = ClientesRepository(conn)

    def create_cliente(self, payload: ClienteCreate) -> ClienteResponse:
        existing = self.repo.get_by_documento(payload.documento) if hasattr(self.repo, 'get_by_documento') else None
        if existing is not None:
            raise HTTPException(status_code=400, detail="El documento ya está registrado")
        row = self.repo.create(payload.dict())
        return ClienteResponse(**row)


class PolizaService:
    def __init__(self, conn: Connection):
        self.conn = conn
        self.clientes = ClientesRepository(conn)
        self.polizas = PolizasRepository(conn)

    def create_poliza(self, payload: PolizaCreate) -> PolizaResponse:
        cliente = self.clientes.get_by_id(payload.cliente_id)
        if cliente is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        poliza = self.polizas.create(
            {
                "cliente_id": payload.cliente_id,
                "prima_total": payload.prima_total,
                "fecha_emision": payload.fecha_emision,
                "fecha_vencimiento": payload.fecha_vencimiento,
            },
            [benef.dict() for benef in payload.beneficiarios],
        )
        return PolizaResponse(
            id=poliza["id"],
            cliente_id=poliza["cliente_id"],
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
        estado = "al día" if total_pagado >= poliza["prima_total"] else "en mora"
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

    def create_pago(self, poliza_id: int, payload: PagoCreate) -> PagoResponse:
        poliza = self.polizas.get_by_id(poliza_id)
        if poliza is None:
            raise HTTPException(status_code=404, detail="Póliza no encontrada")

        if payload.clave_idempotencia:
            existing = self.pagos.get_by_idempotency(poliza_id, payload.clave_idempotencia)
            if existing is not None:
                return PagoResponse(**existing)

        nuevo = self.pagos.create(poliza_id, payload.dict(exclude_unset=True))
        return PagoResponse(**nuevo)


class ReportesService:
    def __init__(self, conn: Connection):
        self.repo = ReportesRepository(conn)

    def cartera_vencida(self, fecha_corte: date, page: int, size: int):
        return self.repo.list_cartera_vencida(fecha_corte, page, size)
