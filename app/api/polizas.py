import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..auth import get_current_user
from ..database import get_connection
from ..services import PolizaService
from ..schemas import PolizaCreate, PolizaResponse, PolizaEstadoResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polizas", tags=["Polizas"])


def _get_conn():
    yield from get_connection()


@router.post("/", response_model=StandardResponse[PolizaResponse], status_code=201)
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


@router.get("/{poliza_id}/estado", response_model=StandardResponse[PolizaEstadoResponse])
def get_estado(
    poliza_id: int,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    logger.info("Consultando estado de póliza id=%s por usuario=%s", poliza_id, current_user["username"])
    service = PolizaService(conn)
    estado = service.get_poliza_estado(poliza_id)
    return {"status": "success", "data": estado}
