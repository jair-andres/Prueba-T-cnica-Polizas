import logging
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from .config import settings
from .database import engine
from .logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Prueba Técnica — Gestión de Pólizas",
    description="API REST para gestionar clientes, pólizas y pagos. Documentación automática con Swagger (OpenAPI).",
    version="0.1.0",
    contact={"name": "Autor", "email": "tu@ejemplo.com"},
    license_info={"name": "MIT"},
)


# ──────────────────────────────────────────────
# Manejador global de excepciones
# ──────────────────────────────────────────────

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Devuelve errores de validación de Pydantic como JSON."""
    logger.warning("Error de validación en %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Error de validación en los datos enviados",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Devuelve errores de base de datos como JSON en lugar de HTML."""
    logger.error("Error de base de datos en %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Error interno en la base de datos. Por favor intenta nuevamente.",
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura cualquier excepción no controlada y la devuelve como JSON."""
    logger.exception("Error no controlado en %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Error interno del servidor.",
        },
    )


# ──────────────────────────────────────────────
# Eventos de ciclo de vida
# ──────────────────────────────────────────────

@app.on_event("startup")
def verify_database_connection() -> None:
    """Verifica la conexión a la base de datos antes de arrancar la aplicación."""
    logger.info("Verificando conexión a la base de datos...")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.error("No se pudo establecer la conexión a la base de datos en el arranque.", exc_info=True)
        raise
    logger.info("Conexión a la base de datos establecida correctamente.")


@app.on_event("shutdown")
def shutdown_event() -> None:
    logger.info("Cerrando aplicación y liberando recursos.")


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Health check")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Devuelve el estado del servicio.
    """
    return {"status": "ok"}


# ──────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────

from .api.clients import router as clientes_router
from .api.polizas import router as polizas_router
from .api.pagos import router as pagos_router
from .api.reportes import router as reportes_router


app.include_router(clientes_router)
app.include_router(polizas_router)
app.include_router(pagos_router)
app.include_router(reportes_router)