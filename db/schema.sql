-- db/schema.sql
-- Modelo completo y corregido de la base de datos para el MVP de pólizas.

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    documento VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255),
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_por VARCHAR(255),
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actualizado_por VARCHAR(255)
);

CREATE TABLE polizas (
    id SERIAL PRIMARY KEY,
    numero_poliza VARCHAR(50) NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    prima_total NUMERIC(12,2) NOT NULL CHECK (prima_total > 0),
    fecha_emision DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'activa',
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_por VARCHAR(255),
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actualizado_por VARCHAR(255),
    CHECK (fecha_vencimiento >= fecha_emision)
);

CREATE TABLE beneficiarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    documento VARCHAR(50) NOT NULL UNIQUE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_por VARCHAR(255),
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actualizado_por VARCHAR(255)
);

CREATE TABLE poliza_beneficiarios (
    poliza_id INTEGER NOT NULL REFERENCES polizas(id) ON DELETE CASCADE,
    beneficiario_id INTEGER NOT NULL REFERENCES beneficiarios(id) ON DELETE CASCADE,
    parentesco VARCHAR(100),
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_por VARCHAR(255),
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actualizado_por VARCHAR(255),
    PRIMARY KEY (poliza_id, beneficiario_id)
);

CREATE TABLE pagos (
    id SERIAL PRIMARY KEY,
    poliza_id INTEGER NOT NULL REFERENCES polizas(id) ON DELETE CASCADE,
    monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
    referencia VARCHAR(100),
    clave_idempotencia VARCHAR(100),
    fecha_pago TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    creado_por VARCHAR(255),
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actualizado_por VARCHAR(255),
    UNIQUE (poliza_id, clave_idempotencia)
);

-- Índices adicionales para consultas comunes
CREATE INDEX idx_polizas_cliente_id ON polizas(cliente_id);
-- Índice para consultas de reporte y búsqueda de pólizas por vencimiento
CREATE INDEX idx_polizas_fecha_vencimiento ON polizas(fecha_vencimiento);
-- Índice para buscar pagos por póliza y para sumar pagos rápidamente
CREATE INDEX idx_pagos_poliza_id ON pagos(poliza_id);
-- Índice para consultas por fecha de pagos recientes y estado de cartera
CREATE INDEX idx_pagos_fecha_pago ON pagos(fecha_pago);
-- Índice para recorrer beneficiarios por póliza
CREATE INDEX idx_poliza_beneficiarios_beneficiario_id ON poliza_beneficiarios(beneficiario_id);
