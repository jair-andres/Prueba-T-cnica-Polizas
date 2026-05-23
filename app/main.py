import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .config import settings
from .database import engine
from .logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

_DESCRIPTION = """
## Sistema de Gestión de Pólizas — API REST

Permite registrar clientes, emitir pólizas con beneficiarios, registrar pagos
(totales o parciales) y consultar el estado de cartera.

---

### Autenticación

Todos los endpoints de negocio requieren un **JWT Bearer token**.

**Flujo:**
1. `POST /auth/register` — crear usuario
2. `POST /auth/login` — obtener token
3. Clic en **Authorize 🔒** → pegar el token

El token expira en 30 minutos (configurable con `JWT_EXPIRATION_MINUTES`).
Tras 5 intentos fallidos la cuenta se bloquea 15 minutos.
"""

_TAGS = [
    {"name": "Autenticación", "description": "Registro y login. Token JWT para el botón **Authorize 🔒**."},
    {"name": "Clientes", "description": "Un cliente puede tener múltiples pólizas activas."},
    {"name": "Polizas", "description": "Emisión con beneficiarios. Estado: `al día` / `en mora` / `pendiente`."},
    {"name": "Pagos", "description": "Pagos parciales o totales. Idempotencia con `clave_idempotencia`."},
    {"name": "Reportes", "description": "Cartera vencida: saldo pendiente con más de 30 días de mora."},
    {"name": "Health", "description": "Disponibilidad del servicio."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Verificando conexión a la base de datos...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.error("Fallo al conectar con la base de datos.", exc_info=True)
        raise
    logger.info("Base de datos conectada.")
    yield
    logger.info("Aplicación cerrada.")


app = FastAPI(
    title="Gestión de Pólizas",
    description=_DESCRIPTION,
    version="1.0.0",
    contact={"name": "Jair Barreto", "email": "jairbarreto23@gmail.com"},
    license_info={"name": "MIT"},
    openapi_tags=_TAGS,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "defaultModelsExpandDepth": -1,
        "tryItOutEnabled": True,
    },
)


def _error_response(status_code: int, message: str, errors: list | None = None) -> JSONResponse:
    content: dict = {"status": "error", "message": message}
    if errors:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("HTTP %s en %s: %s", exc.status_code, request.url.path, exc.detail)
    return _error_response(exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validación en %s: %s", request.url.path, exc.errors())
    errors = [
        {"field": ".".join(str(p) for p in e.get("loc", [])), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    return _error_response(422, "Error de validación en los datos enviados", errors)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("IntegrityError en %s: %s", request.url.path, exc.orig)
    return _error_response(409, "Conflicto de datos: ya existe un registro con esos valores")


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Error de base de datos en %s: %s", request.url.path, str(exc))
    return _error_response(500, "Error interno en la base de datos.")


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s: %s", request.url.path, str(exc))
    return _error_response(500, "Error interno del servidor.")


@app.get("/health", tags=["Health"], summary="Health check")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


from .api.auth import router as auth_router
from .api.clients import router as clientes_router
from .api.pagos import router as pagos_router
from .api.polizas import router as polizas_router
from .api.reportes import router as reportes_router

app.include_router(auth_router)
app.include_router(clientes_router)
app.include_router(polizas_router)
app.include_router(pagos_router)
app.include_router(reportes_router)
