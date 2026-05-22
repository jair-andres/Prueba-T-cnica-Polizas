import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..database import get_connection
from ..services import PagoService
from ..schemas import PagoCreate, PagoResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polizas", tags=["Pagos"])


def _get_conn():
    yield from get_connection()


@router.post("/{poliza_id}/pagos", response_model=StandardResponse[PagoResponse])
def create_pago(poliza_id: int, payload: PagoCreate, conn: Connection = Depends(_get_conn)):
    logger.info("Registrando pago para póliza_id=%s clave_idempotencia=%s", poliza_id, payload.clave_idempotencia)
    service = PagoService(conn)
    pago = service.create_pago(poliza_id, payload)
    logger.info("Pago registrado: id=%s", pago.id)
    return {"status": "success", "data": pago}
