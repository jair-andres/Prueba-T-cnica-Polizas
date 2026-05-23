import logging

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection
from datetime import timedelta

from ..auth import get_current_user
from ..database import get_connection
from ..services import ReportesService, _hoy_bogota
from ..schemas import CarteraVencidaItem, StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _get_conn():
    yield from get_connection()


@router.get(
    "/cartera-vencida",
    response_model=StandardResponse[list[CarteraVencidaItem]],
    summary="Cartera vencida",
    responses={401: {"description": "Token ausente o inválido"}},
    description="""
Lista pólizas con saldo pendiente cuya `fecha_vencimiento` es anterior a
**hoy − 30 días** (evaluado en zona horaria **America/Bogota**).

Incluye por póliza:
- Cliente, prima total, total pagado, saldo pendiente.
- `dias_mora`: días transcurridos desde el vencimiento.

Resultado paginado con `page` y `size`.
""",
)
def cartera_vencida(
    page: int = 1,
    size: int = 20,
    conn: Connection = Depends(_get_conn),
    current_user: dict = Depends(get_current_user),
):
    fecha_corte = _hoy_bogota() - timedelta(days=30)
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
                dias_mora=(_hoy_bogota() - r["fecha_vencimiento"]).days,
            )
        )
    logger.info("Reporte de cartera vencida generado con %s items", len(items))
    return {"status": "success", "data": items}
