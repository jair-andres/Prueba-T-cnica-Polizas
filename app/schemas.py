from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field, condecimal, constr, validator, EmailStr
from pydantic.generics import GenericModel


T = TypeVar("T")


class UserBase(BaseModel):
    username: constr(min_length=3, max_length=255)
    email: EmailStr


class UserCreate(UserBase):
    password: constr(min_length=8)


class UserInDB(UserBase):
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    login_attempts: int = 0
    last_login_attempt: Optional[datetime] = None
    creado_en: datetime
    creado_por: Optional[str] = None
    actualizado_en: datetime
    actualizado_por: Optional[str] = None

    class Config:
        orm_mode = True


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        orm_mode = True


class UserLogin(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

    @validator("username", always=True)
    def check_username_or_email(cls, v, values):
        if not v and not values.get("email"):
            raise ValueError("Debe proporcionar un nombre de usuario o un correo electrónico.")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class StandardResponse(GenericModel, Generic[T]):
    """Estructura única de respuesta para todos los endpoints (éxito y error)."""
    status: Literal["success", "error"] = "success"
    message: Optional[str] = None
    data: Optional[T] = None


class ErrorDetail(BaseModel):
    """Detalle de un error de validación de campo."""
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    """Respuesta de error con estructura consistente."""
    status: Literal["error"] = "error"
    message: str
    errors: Optional[List[ErrorDetail]] = None


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
    email: Optional[EmailStr] = None  # Valida formato de email automáticamente


class ClienteResponse(ClienteCreate):
    id: int
    creado_en: datetime


class PolizaCreate(BaseModel):
    cliente_id: int
    numero_poliza: constr(min_length=3, max_length=50)
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

    @validator("beneficiarios")
    def al_menos_un_beneficiario(cls, value: List) -> List:
        if not value:
            raise ValueError("La póliza debe tener al menos un beneficiario")
        return value


class PolizaResponse(BaseModel):
    id: int
    cliente_id: int
    numero_poliza: Optional[str] = None
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