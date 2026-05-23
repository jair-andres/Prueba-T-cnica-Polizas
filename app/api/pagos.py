import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..auth import get_current_user
from ..database import get_connection
from ..services import PagoService
from ..schemas import PagoCreate, PagoResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polizas", tags=["Pagos"])


def _get_conn():
    yield from get_connection()


@router.post(
    "/{poliza_id}/pagos",
    response_model=StandardResponse[PagoResponse],
    status_code=201,
    summary="Registrar pago",
    responses={
        401: {"description": "Token ausente o inválido"},
        404: {"description": "Póliza no encontrada"},
        400: {"description": "Monto excede saldo pendiente o póliza inactiva"},
        409: {"description": "Conflicto de idempotencia (raro, ver descripción)"},
    },
    description="""
Registra un pago total o parcial sobre una póliza activa.

**Idempotencia:**
Envía `clave_idempotencia` (UUID recomendado) para hacer el endpoint idempotente.
Si el cliente reintenta con la misma clave, se devuelve el pago original sin duplicarlo.

**Concurrencia:**
El endpoint usa `SELECT ... FOR UPDATE` para serializar pagos simultáneos sobre la misma
póliza, eliminando race conditions en el cálculo del saldo.

**Reglas:**
- El `monto` no puede superar el saldo pendiente (`prima_total - suma de pagos`).
- La póliza debe tener `estado = activa`.
- Si no se envía `fecha_pago`, se usa la fecha/hora actual (UTC).
""",
)
def create_pago(
    poliza_id: int,
    payload: PagoCreate,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    logger.info(
        "Registrando pago para póliza_id=%s clave_idempotencia=%s por usuario=%s",
        poliza_id, payload.clave_idempotencia, current_user["username"],
    )
    service = PagoService(conn)
    pago = service.create_pago(poliza_id, payload, created_by=current_user["username"])
    logger.info("Pago registrado: id=%s", pago.id)
    return {"status": "success", "data": pago}
