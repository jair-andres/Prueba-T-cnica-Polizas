from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator


T = TypeVar("T")

# ── Tipos reutilizables ────────────────────────────────────────────────────────
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2, gt=Decimal("0"))]


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    username: Annotated[str, StringConstraints(min_length=3, max_length=255)]
    email: EmailStr


class UserCreate(UserBase):
    # bcrypt tiene un límite de 72 bytes; lo validamos aquí para dar un error claro
    password: Annotated[str, StringConstraints(min_length=8, max_length=72)]


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

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    creado_en: datetime
    actualizado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

    @model_validator(mode="after")
    def check_username_or_email(self) -> UserLogin:
        if not self.username and not self.email:
            raise ValueError("Debe proporcionar un nombre de usuario o un correo electrónico.")
        return self


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── Respuestas estándar ────────────────────────────────────────────────────────

class StandardResponse(BaseModel, Generic[T]):
    """Estructura única de respuesta para todos los endpoints."""
    status: Literal["success", "error"] = "success"
    message: Optional[str] = None
    data: Optional[T] = None


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
    errors: Optional[List[ErrorDetail]] = None


# ── Clientes ──────────────────────────────────────────────────────────────────

class ClienteCreate(BaseModel):
    nombre: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    documento: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    email: Optional[EmailStr] = None


class ClienteResponse(ClienteCreate):
    id: int
    creado_en: datetime


# ── Pólizas ───────────────────────────────────────────────────────────────────

class BeneficiarioCreate(BaseModel):
    nombre: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    documento: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    parentesco: Optional[Annotated[str, StringConstraints(max_length=100)]] = None


class BeneficiarioResponse(BeneficiarioCreate):
    id: int


class PolizaCreate(BaseModel):
    cliente_id: int
    numero_poliza: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    prima_total: Money
    fecha_emision: date
    fecha_vencimiento: date
    beneficiarios: List[BeneficiarioCreate]

    @field_validator("fecha_vencimiento", mode="after")
    @classmethod
    def vencimiento_after_emision(cls, value: date, info) -> date:
        fecha_emision = info.data.get("fecha_emision")
        if fecha_emision and value < fecha_emision:
            raise ValueError("fecha_vencimiento debe ser igual o posterior a fecha_emision")
        return value

    @field_validator("beneficiarios", mode="after")
    @classmethod
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


# ── Pagos ─────────────────────────────────────────────────────────────────────

class PagoCreate(BaseModel):
    monto: Money
    fecha_pago: Optional[datetime] = None
    clave_idempotencia: Optional[Annotated[str, StringConstraints(min_length=1, max_length=100)]] = None

    @field_validator("fecha_pago", mode="before")
    @classmethod
    def default_fecha_pago(cls, value) -> datetime:
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


# ── Estado y reportes ─────────────────────────────────────────────────────────

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
