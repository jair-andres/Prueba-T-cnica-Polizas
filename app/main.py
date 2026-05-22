import logging
from typing import Dict

from fastapi import FastAPI

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


@app.on_event("startup")
def verify_database_connection() -> None:
    """Verifica la conexión a la base de datos antes de arrancar la aplicación."""
    logger.info("Verificando conexión a la base de datos...")
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
    except Exception:
        logger.error("No se pudo establecer la conexión a la base de datos en el arranque.", exc_info=True)
        raise
    logger.info("Conexión a la base de datos establecida correctamente.")


@app.on_event("shutdown")
def shutdown_event() -> None:
    logger.info("Cerrando aplicación y liberando recursos.")


@app.get("/health", tags=["Health"], summary="Health check")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Devuelve el estado del servicio.
    """
    return {"status": "ok"}


from .api.clients import router as clientes_router
from .api.polizas import router as polizas_router
from .api.pagos import router as pagos_router
from .api.reportes import router as reportes_router


app.include_router(clientes_router)
app.include_router(polizas_router)
app.include_router(pagos_router)
app.include_router(reportes_router)
