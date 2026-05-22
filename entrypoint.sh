#!/bin/bash
set -e

echo "=== Esperando a PostgreSQL ==="
RETRIES=30
until pg_isready -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null || [ $RETRIES -eq 0 ]; do
    echo "PostgreSQL no está listo aún... ($RETRIES intentos restantes)"
    RETRIES=$((RETRIES - 1))
    sleep 2
done

if [ $RETRIES -eq 0 ]; then
    echo "ERROR: No se pudo conectar a PostgreSQL después de varios intentos."
    exit 1
fi

echo "=== PostgreSQL está listo ==="

echo "=== Inicializando esquema de base de datos ==="
python -c "
from app.database import engine
from app.models import metadata
print('Creando tablas...')
metadata.create_all(engine)
print('Tablas creadas correctamente.')
"

echo "=== Iniciando aplicación ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000