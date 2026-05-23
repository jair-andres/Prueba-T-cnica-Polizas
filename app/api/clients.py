import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from ..auth import get_current_user
from ..database import get_connection
from ..services import ClienteService
from ..schemas import ClienteCreate, ClienteResponse, StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clientes", tags=["Clientes"])


def _get_conn():
    yield from get_connection()


@router.post("/", response_model=StandardResponse[ClienteResponse], status_code=201)
def create_cliente(
    payload: ClienteCreate,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    logger.info("Creando cliente: documento=%s por usuario=%s", payload.documento, current_user["username"])
    service = ClienteService(conn)
    cliente = service.create_cliente(payload, created_by=current_user["username"])
    logger.info("Cliente creado: id=%s", cliente.id)
    return {"status": "success", "data": cliente}
