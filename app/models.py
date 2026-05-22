from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Numeric,
    Date,
    TIMESTAMP,
    ForeignKey,
    func,
    UniqueConstraint,
)

from .database import metadata


clientes = Table(
    "clientes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nombre", String(255), nullable=False),
    Column("documento", String(50), nullable=False, unique=True),
    Column("email", String(255)),
    Column("creado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_por", String(255)),
    Column("actualizado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("actualizado_por", String(255)),
)

polizas = Table(
    "polizas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("numero_poliza", String(50), nullable=False, unique=True),
    Column("cliente_id", Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
    Column("prima_total", Numeric(12, 2), nullable=False),
    Column("fecha_emision", Date, nullable=False),
    Column("fecha_vencimiento", Date, nullable=False),
    Column("estado", String(20), nullable=False, server_default="activa"),
    Column("creado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_por", String(255)),
    Column("actualizado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("actualizado_por", String(255)),
)

beneficiarios = Table(
    "beneficiarios",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nombre", String(255), nullable=False),
    Column("documento", String(50), nullable=False, unique=True),
    Column("creado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_por", String(255)),
    Column("actualizado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("actualizado_por", String(255)),
)

poliza_beneficiarios = Table(
    "poliza_beneficiarios",
    metadata,
    Column("poliza_id", Integer, ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False),
    Column("beneficiario_id", Integer, ForeignKey("beneficiarios.id", ondelete="CASCADE"), nullable=False),
    Column("parentesco", String(100)),
    Column("creado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_por", String(255)),
    Column("actualizado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("actualizado_por", String(255)),
)

pagos = Table(
    "pagos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("poliza_id", Integer, ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False),
    Column("monto", Numeric(12, 2), nullable=False),
    Column("referencia", String(100)),
    Column("clave_idempotencia", String(100)),
    Column("fecha_pago", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("creado_por", String(255)),
    Column("actualizado_en", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("actualizado_por", String(255)),
    UniqueConstraint("poliza_id", "clave_idempotencia", name="uq_pagos_poliza_idempotency"),
)
