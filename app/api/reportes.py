import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection
from datetime import date, timedelta

from ..auth import get_current_user
from ..database import get_connection
from ..services import ReportesService
from ..schemas import CarteraVencidaItem, StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _get_conn():
    yield from get_connection()


@router.get("/cartera-vencida", response_model=StandardResponse[list[CarteraVencidaItem]])
def cartera_vencida(
    page: int = 1,
    size: int = 20,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    fecha_corte = date.today() - timedelta(days=30)
    logger.info("Generando reporte de cartera vencida page=%s size=%s fecha_corte=%s", page, size, fecha_corte)
    service = ReportesService(conn)
    rows = service.cartera_vencida(fecha_corte, page, size)
    items = []
    for r in rows:
        items.append(
            CarteraVencidaItem(
                poliza_id=r["poliza_id"],
                cliente_id=r["cliente_id"],
                cliente_nombre=r["cliente_nombre"],
                prima_total=r["prima_total"],
                total_pagado=r["total_pagado"],
                saldo_pendiente=r["prima_total"] - r["total_pagado"],
                dias_mora=(date.today() - r["fecha_vencimiento"]).days,
            )
        )
    logger.info("Reporte de cartera vencida generado con %s items", len(items))
    return {"status": "success", "data": items}
