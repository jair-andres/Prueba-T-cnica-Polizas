import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..auth import get_current_user
from ..database import get_connection
from ..services import PolizaService
from ..schemas import PolizaCreate, PolizaResponse, PolizaEstadoResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polizas", tags=["Polizas"])

_401 = {401: {"description": "Token ausente o inválido"}}
_404 = {404: {"description": "Póliza no encontrada", "content": {"application/json": {"example": {"status": "error", "message": "Póliza no encontrada"}}}}}


def _get_conn():
    yield from get_connection()


@router.post(
    "/",
    response_model=StandardResponse[PolizaResponse],
    status_code=201,
    summary="Crear póliza",
    responses={
        **_401,
        400: {"description": "Cliente no encontrado o fecha de emisión futura"},
    },
    description="""
Emite una póliza asociada a un cliente existente, con uno o varios beneficiarios.

**Reglas de negocio:**
- `fecha_emision` no puede ser futura (se evalúa en zona horaria **America/Bogota**).
- `fecha_vencimiento` debe ser igual o posterior a `fecha_emision`.
- `prima_total` debe ser mayor a 0.
- Se requiere **al menos un beneficiario**.
- Un mismo beneficiario (identificado por `documento`) puede estar en pólizas de distintos clientes.
  Si el documento ya existe, se reutiliza el registro.
- `numero_poliza` debe ser único en el sistema.
""",
)
def create_poliza(
    payload: PolizaCreate,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    logger.info("Creando póliza para cliente_id=%s por usuario=%s", payload.cliente_id, current_user["username"])
    service = PolizaService(conn)
    poliza = service.create_poliza(payload, created_by=current_user["username"])
    logger.info("Póliza creada: id=%s", poliza.id)
    return {"status": "success", "data": poliza}


@router.get(
    "/{poliza_id}/estado",
    response_model=StandardResponse[PolizaEstadoResponse],
    summary="Consultar estado de póliza",
    responses={**_401, **_404},
    description="""
Devuelve el saldo pendiente, fecha del último pago y estado de la póliza.

**Estados posibles** (evaluados en zona horaria **America/Bogota**):

| Estado | Condición |
|--------|-----------|
| `al día` | Suma de pagos cubre la prima total |
| `en mora` | `fecha_vencimiento` ya pasó y hay saldo pendiente |
| `pendiente` | Aún no ha vencido pero hay saldo sin pagar |
""",
)
def get_estado(
    poliza_id: int,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    logger.info("Consultando estado de póliza id=%s por usuario=%s", poliza_id, current_user["username"])
    service = PolizaService(conn)
    estado = service.get_poliza_estado(poliza_id)
    return {"status": "success", "data": estado}
