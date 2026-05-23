from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func, insert, select, and_, update
from sqlalchemy.engine import Connection

from .models import clientes, polizas, beneficiarios, poliza_beneficiarios, pagos, users


class UsersRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_by_username(self, username: str) -> Optional[Dict]:
        row = self.conn.execute(
            select(users).where(users.c.username == username)
        ).mappings().first()
        return dict(row) if row else None

    def get_by_email(self, email: str) -> Optional[Dict]:
        row = self.conn.execute(
            select(users).where(users.c.email == email)
        ).mappings().first()
        return dict(row) if row else None

    def create(self, username: str, email: str, hashed_password: str) -> Dict:
        stmt = (
            insert(users)
            .values(username=username, email=email, hashed_password=hashed_password)
            .returning(*users.c)
        )
        row = self.conn.execute(stmt).mappings().first()
        return dict(row)

    def increment_login_attempts(self, user_id: int, at: datetime) -> None:
        self.conn.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(
                login_attempts=users.c.login_attempts + 1,
                last_login_attempt=at,
            )
        )

    def reset_login_attempts(self, user_id: int) -> None:
        self.conn.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(login_attempts=0, last_login_attempt=None)
        )


class ClientesRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create(self, payload: Dict) -> Dict:
        stmt = insert(clientes).values(**payload).returning(*clientes.c)
        row = self.conn.execute(stmt).mappings().first()
        return dict(row) if row else {}

    def get_by_id(self, cliente_id: int) -> Optional[Dict]:
        stmt = select(clientes).where(clientes.c.id == cliente_id)
        row = self.conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_by_documento(self, documento: str) -> Optional[Dict]:
        stmt = select(clientes).where(clientes.c.documento == documento)
        row = self.conn.execute(stmt).mappings().first()
        return dict(row) if row else None


class PolizasRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create(self, payload: Dict, beneficiarios_payload: List[Dict]) -> Dict:
        with self.conn.begin():
            stmt = insert(polizas).values(**payload).returning(*polizas.c)
            pol_row = self.conn.execute(stmt).mappings().first()
            pol_id = pol_row["id"]
            benefs = []
            for b in beneficiarios_payload:
                # upsert beneficiario by documento
                existing = self.conn.execute(select(beneficiarios).where(beneficiarios.c.documento == b["documento"]))
                existing = existing.mappings().first()
                if existing:
                    benef_id = existing["id"]
                else:
                    r = self.conn.execute(insert(beneficiarios).values(**{k: v for k, v in b.items() if k != 'parentesco'}).returning(*beneficiarios.c)).mappings().first()
                    benef_id = r["id"]
                self.conn.execute(insert(poliza_beneficiarios).values(poliza_id=pol_id, beneficiario_id=benef_id, parentesco=b.get("parentesco")))
            return dict(pol_row)

    def get_by_id(self, poliza_id: int) -> Optional[Dict]:
        stmt = select(polizas).where(polizas.c.id == poliza_id)
        row = self.conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_total_pagado(self, poliza_id: int) -> Decimal:
        stmt = select(func.coalesce(func.sum(pagos.c.monto), 0)).where(pagos.c.poliza_id == poliza_id)
        val = self.conn.execute(stmt).scalar_one()
        return Decimal(val)

    def get_ultimo_pago(self, poliza_id: int) -> Optional[str]:
        stmt = select(func.max(pagos.c.fecha_pago)).where(pagos.c.poliza_id == poliza_id)
        return self.conn.execute(stmt).scalar_one()


class PagosRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_by_idempotency(self, poliza_id: int, clave: str) -> Optional[Dict]:
        if not clave:
            return None
        stmt = select(pagos).where(and_(pagos.c.poliza_id == poliza_id, pagos.c.clave_idempotencia == clave))
        row = self.conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def create(self, poliza_id: int, payload: Dict) -> Dict:
        stmt = insert(pagos).values(poliza_id=poliza_id, **payload).returning(*pagos.c)
        row = self.conn.execute(stmt).mappings().first()
        return dict(row)


class ReportesRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def list_cartera_vencida(self, fecha_corte: date, page: int, size: int) -> List[Dict]:
        offset_value = max(page - 1, 0) * size
        total_pagado = func.coalesce(func.sum(pagos.c.monto), 0).label("total_pagado")
        stmt = (
            select(
                polizas.c.id.label("poliza_id"),
                clientes.c.id.label("cliente_id"),
                clientes.c.nombre.label("cliente_nombre"),
                polizas.c.prima_total,
                total_pagado,
                polizas.c.fecha_vencimiento,
            )
            .select_from(polizas.join(clientes).outerjoin(pagos))
            .where(polizas.c.fecha_vencimiento < fecha_corte)
            .group_by(polizas.c.id, clientes.c.id, clientes.c.nombre, polizas.c.prima_total, polizas.c.fecha_vencimiento)
            .having(total_pagado < polizas.c.prima_total)
            .order_by(polizas.c.fecha_vencimiento.asc())
            .limit(size)
            .offset(offset_value)
        )
        rows = self.conn.execute(stmt).mappings().all()
        return [dict(r) for r in rows]
