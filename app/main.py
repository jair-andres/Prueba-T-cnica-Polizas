import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

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

**Flujo para obtener el token:**

1. Registra un usuario → `POST /auth/register`
2. Obtén el token → `POST /auth/login` (username + password en form-data)
3. Haz clic en **Authorize 🔒** (arriba a la derecha) y pega el token

El token expira en `{expire}` minutos (configurable con `JWT_EXPIRATION_MINUTES`).

---

### Seguridad de credenciales

- Contraseñas hasheadas con **bcrypt**.
- Bloqueo temporal tras **{max_attempts}** intentos fallidos consecutivos.
- Todos los registros incluyen `creado_por` con el username del usuario autenticado.
""".format(
    expire=30,
    max_attempts=5,
)

_TAGS = [
    {
        "name": "Autenticación",
        "description": "Registro de usuarios y obtención de JWT. "
                       "**El token obtenido aquí se usa en el botón Authorize 🔒.**",
    },
    {
        "name": "Clientes",
        "description": "Alta de clientes. Un cliente puede tener varias pólizas activas simultáneamente.",
    },
    {
        "name": "Polizas",
        "description": "Emisión de pólizas con beneficiarios y consulta de estado (al día / en mora / pendiente).",
    },
    {
        "name": "Pagos",
        "description": "Registro de pagos parciales o totales. Soporta idempotencia mediante `clave_idempotencia`.",
    },
    {
        "name": "Reportes",
        "description": "Cartera vencida: pólizas con saldo pendiente y más de 30 días de mora.",
    },
    {
        "name": "Health",
        "description": "Verificación de disponibilidad del servicio.",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Verificando conexión a la base de datos...")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.error("No se pudo establecer la conexión a la base de datos en el arranque.", exc_info=True)
        raise
    logger.info("Conexión a la base de datos establecida correctamente.")

    yield

    logger.info("Cerrando aplicación y liberando recursos.")


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


# ──────────────────────────────────────────────
# Manejador global de excepciones - estructura unificada
# ──────────────────────────────────────────────


def _error_response(status_code: int, message: str, errors: list | None = None) -> JSONResponse:
    """Construye una respuesta de error con estructura consistente."""
    content = {"status": "error", "message": message}
    if errors:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convierte HTTPException de FastAPI a nuestra estructura estándar."""
    logger.warning("HTTP %s en %s: %s", exc.status_code, request.url.path, exc.detail)
    return _error_response(
        status_code=exc.status_code,
        message=exc.detail,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Devuelve errores de validación de Pydantic/FastAPI como JSON."""
    logger.warning("Error de validación en %s: %s", request.url.path, exc.errors())
    errors = [
        {"field": ".".join(str(p) for p in err.get("loc", [])), "message": err.get("msg", "")}
        for err in exc.errors()
    ]
    return _error_response(
        status_code=422,
        message="Error de validación en los datos enviados",
        errors=errors,
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """IntegrityErrors no capturados en el service → 409 genérico sin exponer SQL."""
    logger.warning("IntegrityError en %s: %s", request.url.path, exc.orig)
    return _error_response(status_code=409, message="Conflicto de datos: ya existe un registro con esos valores")


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Errores de base de datos inesperados → 500. No expone detalles internos."""
    logger.error("Error de base de datos en %s: %s", request.url.path, str(exc))
    return _error_response(
        status_code=500,
        message="Error interno en la base de datos. Por favor intenta nuevamente.",
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura cualquier excepción no controlada y la devuelve como JSON."""
    logger.exception("Error no controlado en %s: %s", request.url.path, str(exc))
    return _error_response(
        status_code=500,
        message="Error interno del servidor.",
    )


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

from .api.auth import router as auth_router
from .api.clients import router as clientes_router
from .api.polizas import router as polizas_router
from .api.pagos import router as pagos_router
from .api.reportes import router as reportes_router


app.include_router(auth_router)
app.include_router(clientes_router)
app.include_router(polizas_router)
app.include_router(pagos_router)
app.include_router(reportes_router)