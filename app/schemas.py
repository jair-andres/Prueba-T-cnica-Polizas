from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, condecimal, constr, validator
from pydantic.generics import GenericModel


T = TypeVar("T")


class StandardResponse(GenericModel, Generic[T]):
    status: str = Field("success", const=True)
    message: Optional[str] = None
    data: T

Money = condecimal(max_digits=12, decimal_places=2, gt=0)


class BeneficiarioCreate(BaseModel):
    nombre: constr(min_length=1, max_length=255)
    documento: constr(min_length=3, max_length=50)
    parentesco: Optional[constr(max_length=100)] = None


class BeneficiarioResponse(BeneficiarioCreate):
    id: int


class ClienteCreate(BaseModel):
    nombre: constr(min_length=1, max_length=255)
    documento: constr(min_length=3, max_length=50)
    email: Optional[constr(max_length=255)] = None


class ClienteResponse(ClienteCreate):
    id: int
    creado_en: datetime


class PolizaCreate(BaseModel):
    cliente_id: int
    prima_total: Money
    fecha_emision: date
    fecha_vencimiento: date
    beneficiarios: List[BeneficiarioCreate]

    @validator("fecha_vencimiento")
    def vencimiento_after_emision(cls, value: date, values: dict) -> date:
        fecha_emision = values.get("fecha_emision")
        if fecha_emision and value < fecha_emision:
            raise ValueError("fecha_vencimiento debe ser igual o posterior a fecha_emision")
        return value


class PolizaResponse(BaseModel):
    id: int
    cliente_id: int
    prima_total: Decimal
    fecha_emision: date
    fecha_vencimiento: date
    beneficiarios: List[BeneficiarioResponse]


class PagoCreate(BaseModel):
    monto: Money
    fecha_pago: Optional[datetime] = None
    clave_idempotencia: Optional[constr(min_length=1, max_length=100)] = None

    @validator("fecha_pago", pre=True, always=True)
    def default_fecha_pago(cls, value: Optional[datetime]) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        return value


class PagoResponse(BaseModel):
    id: int
    poliza_id: int
    monto: Decimal
    fecha_pago: datetime
    clave_idempotencia: Optional[str] = None
    creado_en: datetime


class PolizaEstadoResponse(BaseModel):
    poliza_id: int
    prima_total: Decimal
    saldo_pendiente: Decimal
    fecha_ultimo_pago: Optional[datetime] = None
    estado: str


class CarteraVencidaItem(BaseModel):
    poliza_id: int
    cliente_id: int
    cliente_nombre: str
    prima_total: Decimal
    total_pagado: Decimal
    saldo_pendiente: Decimal
    dias_mora: int
