import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..database import get_connection
from ..services import ClienteService
from ..schemas import ClienteCreate, ClienteResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clientes", tags=["Clientes"])


def _get_conn():
    yield from get_connection()


@router.post("/", response_model=StandardResponse[ClienteResponse])
def create_cliente(payload: ClienteCreate, conn: Connection = Depends(_get_conn)):
    logger.info("Creando cliente: documento=%s", payload.documento)
    service = ClienteService(conn)
    cliente = service.create_cliente(payload)
    logger.info("Cliente creado: id=%s", cliente.id)
    return {"status": "success", "data": cliente}
